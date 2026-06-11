"""
@file        nl_parser.py
@description NL → Ragic API parameter translator (優化版).
             Uses HybridRanker for Phase 1 (intent matching + complexity).
             Phase 2: SIMPLE → template translation, COMPLEX → LLM Schema Injection.
             Date expressions are detected — caller receives flag for clarification.
@lastUpdate  2026-04-13
@author      Daniel Chung
@version     2.0.0
"""

import logging
import time

from data_agent.ragic.date_resolver import contains_date_expression
from data_agent.ragic.hybrid_ranker import RagicHybridRanker, QueryComplexity
from data_agent.ragic.intent_store import IntentVectorStore
from data_agent.ragic.llm_translator import translate_via_llm
from data_agent.ragic.models import (
    MatchedIntentInfo,
    NLQueryOptions,
    RagicQueryParams,
    RagicSortDirection,
    RagicWhereClause,
    TranslatedParams,
)

logger = logging.getLogger(__name__)


class RagicNLParser:
    def __init__(
        self,
        intent_store: IntentVectorStore | None = None,
    ) -> None:
        self._intents = intent_store or IntentVectorStore()
        self._ranker = RagicHybridRanker()

    async def parse(
        self,
        query: str,
        account: str | None = None,
        table_key: str | None = None,
        options: NLQueryOptions | None = None,
    ) -> "ParseResult":
        start = time.monotonic()
        opts = options or NLQueryOptions()

        candidates = await self._ranker.rank(
            query=query,
            account=account or "",
            top_k=8,
        )

        resolved_table_key = table_key or (candidates[0].table_key if candidates else "")
        complexity = candidates[0].complexity if candidates else QueryComplexity.SIMPLE

        multi_table_hint = len(set(c.table_key for c in candidates[:3])) > 1

        if candidates and complexity == QueryComplexity.SIMPLE:
            intent_info = MatchedIntentInfo(
                intent_id=candidates[0].table_key,
                score=candidates[0].score,
                action="list",
                table_key=candidates[0].table_key,
            )
            payload = None
            if resolved_table_key:
                hits = await self._intents.search(
                    query=query,
                    account=account,
                    top_k=1,
                    score_threshold=0.0,
                )
                if hits:
                    payload = hits[0].get("payload")
                    if isinstance(payload, dict):
                        intent_info.intent_id = str(payload.get("intent_id") or payload.get("expression_key", candidates[0].table_key))
            translated = self._translate_from_payload(payload if isinstance(payload, dict) else None, opts) if payload else TranslatedParams(limit=opts.limit, naming="EID")
            confidence = "high"
            llm_fallback_failed = False
        else:
            intent_info = None
            if candidates:
                intent_info = MatchedIntentInfo(
                    intent_id=candidates[0].table_key,
                    score=candidates[0].score,
                    action="list",
                    table_key=candidates[0].table_key,
                )
            translated = await translate_via_llm(
                query, account, resolved_table_key, opts
            )
            confidence = "medium" if translated.where or translated.order_field else "low"
            llm_fallback_failed = len(translated.where) == 0 and not translated.order_field

        has_date_expr = contains_date_expression(query)
        has_date_where = any(
            "/" in wc.value and len(wc.value) >= 8
            for wc in translated.where
        )
        needs_date_clarification = has_date_expr and not has_date_where

        elapsed_ms = (time.monotonic() - start) * 1000

        resolved_query_type = "simple_filter" if complexity == QueryComplexity.SIMPLE else "complex_aggregate"

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

    def _translate_from_payload(
        self,
        payload: dict | None,
        opts: NLQueryOptions,
    ) -> TranslatedParams:
        if not payload:
            return TranslatedParams(limit=opts.limit, naming="EID")
        filter_raw = payload.get("filter_template")
        if not isinstance(filter_raw, dict):
            return TranslatedParams(limit=opts.limit, naming="EID")
        try:
            from data_agent.ragic.models import RagicOperator
            op_str = str(filter_raw.get("operator", "eq"))
            try:
                op = RagicOperator(op_str)
            except ValueError:
                op = RagicOperator.EQ
            return TranslatedParams(
                where=[RagicWhereClause(
                    field_id=str(filter_raw.get("field_id", "")),
                    operator=op,
                    value=str(filter_raw.get("value", "")),
                )],
                limit=opts.limit,
                naming="EID",
            )
        except Exception:
            return TranslatedParams(limit=opts.limit, naming="EID")

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
