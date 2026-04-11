"""
@file        nl_parser.py
@description NL → Ragic API parameter translator.
             Matches user query to stored intents via Qdrant vector search,
             then translates to RagicQueryParams. Falls back to LLM for
             unmatched or ambiguous queries.
@lastUpdate  2026-04-11 17:43:04
@author      Daniel Chung
@version     1.1.0
"""

import json
import logging
import os
import re
import time

import httpx

from data_agent.ragic.intent_store import RagicIntentStore
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
from data_agent.ragic.schema_store import RagicSchemaStore

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Intent match score ≥ this → use template directly, skip LLM
TEMPLATE_CONFIDENCE_THRESHOLD = 0.60


async def _get_small_model() -> str:
    from data_agent.config_reader import get_param

    return await get_param("da.small_llm_model")


class RagicNLParser:
    def __init__(
        self,
        intent_store: RagicIntentStore | None = None,
        schema_store: RagicSchemaStore | None = None,
    ) -> None:
        self._intents = intent_store or RagicIntentStore()
        self._schemas = schema_store or RagicSchemaStore()

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
            account=account,
            top_k=3,
            score_threshold=0.3,
        )

        matched_intent: RagicIntent | None = None
        match_score = 0.0

        if intent_hits:
            best = intent_hits[0]
            payload = best.get("payload", {})
            if isinstance(payload, dict):
                matched_intent = RagicIntentStore.payload_to_intent(payload)
                raw_score = best.get("score", 0.0)
                match_score = float(raw_score) if isinstance(raw_score, (int, float)) else 0.0

        resolved_table_key = table_key or (matched_intent.table_key if matched_intent else "")

        if matched_intent and match_score >= TEMPLATE_CONFIDENCE_THRESHOLD:
            translated = self._translate_from_template(
                matched_intent, opts
            )
        else:
            translated = await self._translate_via_llm(
                query, account, resolved_table_key, opts
            )

        if not resolved_table_key and translated.where:
            pass

        multi_table_hint = False
        if match_score < TEMPLATE_CONFIDENCE_THRESHOLD:
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
        )

    async def _detect_multi_table_intent(
        self, query: str, account: str | None
    ) -> tuple[bool, list[str]]:
        hits = await self._intents.search(
            query=query, account=account, top_k=5, score_threshold=0.3
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
        if table_key and account:
            schema_hits = await self._schemas.search(
                query=table_key, account=account, top_k=1
            )
            if schema_hits:
                payload = schema_hits[0].get("payload", {})
                if isinstance(payload, dict):
                    fields = payload.get("fields", {})
                    if isinstance(fields, dict):
                        parts: list[str] = []
                        for fid, fdata in fields.items():
                            if isinstance(fdata, dict):
                                fname = fdata.get("name", fid)
                                ftype = fdata.get("field_type", "text")
                                parts.append(f"  {fid}: {fname} ({ftype})")
                        schema_context = "\n".join(parts)

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
                return self._parse_llm_response(llm_response, opts)
        except Exception as exc:
            logger.warning("LLM fallback failed: %s", exc)
            return TranslatedParams(limit=opts.limit, naming="EID")

    def _build_llm_prompt(self, query: str, schema_context: str) -> str:
        schema_section = f"\n【欄位清單】\n{schema_context}\n" if schema_context else ""
        return (
            "你是 RagicDataAgent 的查詢參數翻譯器。"
            "將使用者的自然語言轉換為 Ragic API 查詢參數。"
            f"{schema_section}"
            "【規則】"
            "1. where: 篩選條件陣列 (field_id, operator:eq/like/gt/gte/lt/lte/regex, value) "
            "2. limit: 1-1000 3. offset: 跳過筆數 4. order_field: 排序欄位 "
            "5. order_direction: ASC/DESC 6. 日期: yyyy/MM/dd "
            f"【使用者輸入】{query} "
            '【輸出 JSON】'
            '{"where": [{"field_id": "...", "operator": "...", "value": "..."}],'
            ' "limit": 1000, "offset": 0, "order_field": null, "order_direction": "DESC"}'
        )

    def _parse_llm_response(
        self, raw: str, opts: NLQueryOptions
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
            if fid and val:
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


class ParseResult:
    __slots__ = (
        "intent_matched",
        "translated_params",
        "table_key",
        "parse_time_ms",
        "multi_table_hint",
    )

    def __init__(
        self,
        intent_matched: MatchedIntentInfo | None,
        translated_params: TranslatedParams,
        table_key: str,
        parse_time_ms: float,
        multi_table_hint: bool = False,
    ) -> None:
        self.intent_matched = intent_matched
        self.translated_params = translated_params
        self.table_key = table_key
        self.parse_time_ms = parse_time_ms
        self.multi_table_hint = multi_table_hint
