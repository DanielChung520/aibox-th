"""
@file        nl_parser.py
@description NL → Ragic API parameter translator.
             Matches user query to stored intents via Qdrant vector search,
             then translates to RagicQueryParams. Falls back to LLM for
             unmatched or ambiguous queries. Three-tier confidence system.
             Date expressions are detected (not resolved) — the caller
             receives a flag so the router can return a clarification.
@lastUpdate  2026-04-12 23:43:06
@author      Daniel Chung
@version     1.4.0
"""

import json
import logging
import os
import re
import time
from datetime import date

import httpx

from data_agent.ragic.date_resolver import contains_date_expression
from data_agent.ragic.intent_store import IntentVectorStore
from data_agent.ragic.models import (
    MatchedIntentInfo,
    NLQueryOptions,
    RagicIntent,
    RagicOperator,
    RagicQueryParams,
    RagicSortDirection,
    RagicWhereClause,
    TranslatedParams,
)

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")

CONFIDENCE_HIGH_THRESHOLD = 0.65
CONFIDENCE_LOW_THRESHOLD = 0.45


async def _get_small_model() -> str:
    from data_agent.config_reader import get_param

    return await get_param("da.small_llm_model")


class RagicNLParser:
    def __init__(
        self,
        intent_store: IntentVectorStore | None = None,
    ) -> None:
        self._intents = intent_store or IntentVectorStore()

    async def parse(
        self,
        query: str,
        account: str | None = None,
        table_key: str | None = None,
        options: NLQueryOptions | None = None,
    ) -> "ParseResult":
        start = time.monotonic()
        opts = options or NLQueryOptions()

        intent_hits = await self._intents.search(
            query=query,
            top_k=3,
            score_threshold=0.3,
        )

        matched_intent: RagicIntent | None = None
        match_score = 0.0

        if intent_hits:
            best = intent_hits[0]
            payload = best.get("payload", {})
            if isinstance(payload, dict):
                matched_intent = IntentVectorStore.payload_to_intent(payload)
                raw_score = best.get("score", 0.0)
                match_score = float(raw_score) if isinstance(raw_score, (int, float)) else 0.0

        resolved_table_key = table_key or (matched_intent.table_key if matched_intent else "")

        confidence = "low"
        llm_fallback_failed = False

        if matched_intent and match_score >= CONFIDENCE_HIGH_THRESHOLD:
            translated = self._translate_from_template(
                matched_intent, opts
            )
            confidence = "high"
        elif matched_intent and match_score >= CONFIDENCE_LOW_THRESHOLD:
            translated = await self._translate_via_llm(
                query, account, resolved_table_key, opts
            )
            confidence = "medium"
            llm_fallback_failed = len(translated.where) == 0 and not translated.order_field
        else:
            translated = TranslatedParams(limit=opts.limit, naming="EID")
            confidence = "low"

        if not resolved_table_key and translated.where:
            pass

        has_date_expr = contains_date_expression(query)
        has_date_where = any(
            "/" in wc.value and len(wc.value) >= 8
            for wc in translated.where
        )
        needs_date_clarification = has_date_expr and not has_date_where

        multi_table_hint = False
        if match_score < CONFIDENCE_HIGH_THRESHOLD:
            multi_table_hint, _ = await self._detect_multi_table_intent(
                query, account
            )

        intent_info: MatchedIntentInfo | None = None
        if matched_intent:
            intent_info = MatchedIntentInfo(
                intent_id=matched_intent.intent_id,
                score=match_score,
                action=matched_intent.action,
                table_key=matched_intent.table_key,
            )

        elapsed_ms = (time.monotonic() - start) * 1000

        return ParseResult(
            intent_matched=intent_info,
            translated_params=translated,
            table_key=resolved_table_key,
            parse_time_ms=round(elapsed_ms, 2),
            multi_table_hint=multi_table_hint,
            confidence=confidence,
            llm_fallback_failed=llm_fallback_failed,
            date_clarification_needed=needs_date_clarification,
        )

    async def _detect_multi_table_intent(
        self, query: str, account: str | None
    ) -> tuple[bool, list[str]]:
        hits = await self._intents.search(
            query=query, top_k=5, score_threshold=0.3
        )
        if len(hits) < 2:
            return False, []
        table_keys: list[str] = []
        for hit in hits[:2]:
            score = hit.get("score", 0.0)
            if not isinstance(score, (int, float)) or score < 0.40:
                continue
            payload = hit.get("payload", {})
            tk = str(payload.get("table_key", "")) if isinstance(payload, dict) else ""
            if tk:
                table_keys.append(tk)
        unique = list(dict.fromkeys(table_keys))
        return (len(unique) >= 2, unique)

    def _translate_from_template(
        self,
        intent: RagicIntent,
        opts: NLQueryOptions,
    ) -> TranslatedParams:
        where_clauses: list[RagicWhereClause] = []
        if intent.filter_template:
            where_clauses.append(
                RagicWhereClause(
                    field_id=intent.filter_template.field_id,
                    operator=intent.filter_template.operator,
                    value=intent.filter_template.value,
                )
            )
        return TranslatedParams(
            where=where_clauses,
            limit=opts.limit,
            naming="EID",
        )

    async def _translate_via_llm(
        self,
        query: str,
        account: str | None,
        table_key: str,
        opts: NLQueryOptions,
    ) -> TranslatedParams:
        schema_context = ""
        if table_key:
            schema_context = await self._load_schema_from_arango(table_key)

        prompt = self._build_llm_prompt(query, schema_context)

        try:
            model = await _get_small_model()
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                    },
                )
                resp.raise_for_status()
                llm_response = resp.json().get("response", "")
                valid_fids = self._extract_field_ids(schema_context)
                return self._parse_llm_response(llm_response, opts, valid_fids)
        except Exception as exc:
            logger.warning("LLM fallback failed: %s", exc)
            return TranslatedParams(limit=opts.limit, naming="EID")

    def _build_llm_prompt(self, query: str, schema_context: str) -> str:
        today = date.today().strftime("%Y/%m/%d")
        schema_section = f"\n【欄位清單（僅可使用以下 field_id）】\n{schema_context}\n" if schema_context else ""
        return (
            "你是查詢參數翻譯器，將自然語言轉換為 API 查詢參數。"
            f"\n【今天日期】{today}"
            f"{schema_section}"
            "【規則】"
            "1. where: 篩選條件陣列 (field_id, operator:eq/like/gt/gte/lt/lte/regex, value) "
            "2. field_id 必須來自上方欄位清單，嚴禁自行編造不存在的 field_id "
            "3. 若找不到對應欄位，回傳空 where 陣列，不要猜測 "
            "4. limit: 1-1000 5. offset: 跳過筆數 6. order_field: 排序欄位 "
            "7. order_direction: ASC/DESC 8. 日期格式: yyyy/MM/dd "
            f"【使用者輸入】{query} "
            '【輸出 JSON】'
            '{"where": [{"field_id": "...", "operator": "...", "value": "..."}],'
            ' "limit": 1000, "offset": 0, "order_field": null, "order_direction": "DESC"}'
        )

    @staticmethod
    def _extract_field_ids(schema_context: str) -> set[str]:
        fids: set[str] = set()
        for line in schema_context.splitlines():
            stripped = line.strip()
            if ":" in stripped:
                fid = stripped.split(":", 1)[0].strip()
                if fid:
                    fids.add(fid)
        return fids

    def _parse_llm_response(
        self, raw: str, opts: NLQueryOptions, valid_fids: set[str],
    ) -> TranslatedParams:
        try:
            cleaned = raw.strip()
            json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group()
            data = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse LLM response as JSON: %s", raw[:200])
            return TranslatedParams(limit=opts.limit, naming="EID")

        where_clauses: list[RagicWhereClause] = []
        for w in data.get("where", []) if isinstance(data.get("where"), list) else []:
            if not isinstance(w, dict):
                continue
            fid, val = str(w.get("field_id", "")), str(w.get("value", ""))
            if not fid or not val:
                continue
            if valid_fids and fid not in valid_fids:
                logger.warning("LLM produced unknown field_id %s — dropped", fid)
                continue
            try:
                op = RagicOperator(str(w.get("operator", "eq")))
            except ValueError:
                op = RagicOperator.EQ
            where_clauses.append(RagicWhereClause(field_id=fid, operator=op, value=val))

        raw_limit = data.get("limit", opts.limit)
        limit = max(1, min(int(raw_limit) if isinstance(raw_limit, (int, float)) else opts.limit, 1000))
        raw_offset = data.get("offset", 0)
        offset = int(raw_offset) if isinstance(raw_offset, (int, float)) else 0
        order_field = str(data["order_field"]) if data.get("order_field") is not None else None
        if order_field and valid_fids and order_field not in valid_fids:
            logger.warning("LLM produced unknown order_field %s — dropped", order_field)
            order_field = None
        order_dir = str(data.get("order_direction", "DESC")).upper()
        order_dir = order_dir if order_dir in ("ASC", "DESC") else "DESC"

        return TranslatedParams(
            where=where_clauses, limit=limit, offset=offset,
            naming="EID", order_field=order_field, order_direction=order_dir,
        )

    def translated_to_query_params(self, t: TranslatedParams) -> RagicQueryParams:
        return RagicQueryParams(
            where=t.where, limit=t.limit, offset=t.offset,
            order_field=t.order_field, naming=t.naming,
            order_direction=RagicSortDirection.ASC if t.order_direction == "ASC" else RagicSortDirection.DESC,
        )

    @staticmethod
    async def _load_schema_from_arango(table_key: str) -> str:
        aql = (
            "FOR t IN da_table_info_ragic "
            'FILTER CONCAT(t.tab, "/", t.sheet_number) == @table_key '
            "FOR f IN da_field_info_ragic "
            "FILTER f.table_id == t._key "
            "RETURN {field_id: f.field_id, field_name: f.field_name}"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                    json={"query": aql, "bindVars": {"table_key": table_key}},
                    auth=(ARANGO_USER, ARANGO_PASSWORD),
                )
                resp.raise_for_status()
        except Exception:
            logger.warning("Failed to load schema from ArangoDB for %s", table_key)
            return ""

        parts: list[str] = []
        for row in resp.json().get("result", []):
            fid = str(row.get("field_id", ""))
            fname = str(row.get("field_name", ""))
            if fid and fname:
                parts.append(f"  {fid}: {fname}")
        return "\n".join(parts)


class ParseResult:
    __slots__ = (
        "intent_matched",
        "translated_params",
        "table_key",
        "parse_time_ms",
        "multi_table_hint",
        "confidence",
        "llm_fallback_failed",
        "date_clarification_needed",
    )

    def __init__(
        self,
        intent_matched: MatchedIntentInfo | None,
        translated_params: TranslatedParams,
        table_key: str,
        parse_time_ms: float,
        multi_table_hint: bool = False,
        confidence: str = "low",
        llm_fallback_failed: bool = False,
        date_clarification_needed: bool = False,
    ) -> None:
        self.intent_matched = intent_matched
        self.translated_params = translated_params
        self.table_key = table_key
        self.parse_time_ms = parse_time_ms
        self.multi_table_hint = multi_table_hint
        self.confidence = confidence
        self.llm_fallback_failed = llm_fallback_failed
        self.date_clarification_needed = date_clarification_needed
