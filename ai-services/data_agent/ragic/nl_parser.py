"""
@file        nl_parser.py
@description NL → Ragic API parameter translator.
             Matches user query to stored intents via Qdrant vector search,
             then translates to RagicQueryParams. Falls back to LLM for
             unmatched or ambiguous queries. Three-tier confidence system.
             Date expressions are detected (not resolved) — the caller
             receives a flag so the router can return a clarification.
@lastUpdate  2026-04-13 02:14:43
@author      Daniel Chung
@version     1.6.0
"""

import logging
import time

from data_agent.ragic.date_resolver import contains_date_expression
from data_agent.ragic.intent_store import IntentVectorStore
from data_agent.ragic.llm_translator import translate_via_llm
from data_agent.ragic.models import (
    MatchedIntentInfo,
    NLQueryOptions,
    RagicIntent,
    RagicQueryParams,
    RagicSortDirection,
    RagicWhereClause,
    TranslatedParams,
)

logger = logging.getLogger(__name__)

CONFIDENCE_HIGH_THRESHOLD = 0.65
CONFIDENCE_LOW_THRESHOLD = 0.45


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
            translated = await translate_via_llm(
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

        resolved_query_type = (
            matched_intent.query_type if matched_intent else "simple_filter"
        )

        return ParseResult(
            intent_matched=intent_info,
            translated_params=translated,
            table_key=resolved_table_key,
            parse_time_ms=round(elapsed_ms, 2),
            multi_table_hint=multi_table_hint,
            confidence=confidence,
            llm_fallback_failed=llm_fallback_failed,
            date_clarification_needed=needs_date_clarification,
            query_type=resolved_query_type,
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
        "confidence",
        "llm_fallback_failed",
        "date_clarification_needed",
        "query_type",
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
        query_type: str = "simple_filter",
    ) -> None:
        self.intent_matched = intent_matched
        self.translated_params = translated_params
        self.table_key = table_key
        self.parse_time_ms = parse_time_ms
        self.multi_table_hint = multi_table_hint
        self.confidence = confidence
        self.llm_fallback_failed = llm_fallback_failed
        self.date_clarification_needed = date_clarification_needed
        self.query_type = query_type
