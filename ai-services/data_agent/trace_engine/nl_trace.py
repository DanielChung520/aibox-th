"""
@file        nl_trace.py
@description Natural language trace query parser (keyword/regex, no LLM).
@lastUpdate  2026-05-17
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import logging
import re
from typing import Callable, Optional

from data_agent.trace_engine.models import TraceScenario

logger = logging.getLogger(__name__)

# Type alias for a pattern extractor: receives a regex Match and returns
# a (scenario_str, batch_value) tuple.
_Extractor = Callable[[re.Match[str]], tuple[str, str]]


class NlParseResult:
    """Result of parsing a natural language query."""

    def __init__(
        self,
        parsed: bool = False,
        scenario: Optional[TraceScenario] = None,
        batch_no: str = "",
        suggestion: str = "",
        from_date: str = "",
        to_date: str = "",
        supplier_code: str = "",
    ) -> None:
        self.parsed = parsed
        self.scenario = scenario
        self.batch_no = batch_no
        self.suggestion = suggestion
        self.from_date = from_date
        self.to_date = to_date
        self.supplier_code = supplier_code

    def to_dict(self) -> dict[str, object]:
        return {
            "parsed": self.parsed,
            "scenario": self.scenario.value if self.scenario else None,
            "batch_no": self.batch_no,
            "suggestion": self.suggestion,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "supplier_code": self.supplier_code,
        }


class NlTraceParser:
    """Parse natural language trace queries using regex + keyword matching."""

    # Mapping from scenario string keys to TraceScenario enum values.
    _SCENARIO_MAP: dict[str, TraceScenario] = {
        "incoming_batch": TraceScenario.INCOMING_BATCH,
        "shipment_batch": TraceScenario.SHIPMENT_BATCH,
        "product_full_history": TraceScenario.PRODUCT_FULL_HISTORY,
        "work_order": TraceScenario.WORK_ORDER,
        "complaint_recall": TraceScenario.COMPLAINT_RECALL,
        "expiry_tracking": TraceScenario.EXPIRY_TRACKING,
        "quality_issue": TraceScenario.QUALITY_ISSUE,
        "supplier_trace": TraceScenario.SUPPLIER_TRACE,
    }

    # Pattern matching rules: (compiled_regex, extractor_callable)
    PATTERNS: list[tuple[re.Pattern[str], _Extractor]] = [
        # "追蹤批號 B001" / "查批號 B001"
        (
            re.compile(
                r"(?:追蹤|查詢?|查)\s*(?:批號|批次)?\s*([A-Za-z0-9\-_]+)",
                re.IGNORECASE,
            ),
            lambda m: ("incoming_batch", m.group(1)),
        ),
        # "XXX 出給哪些客戶" / "XXX 出貨給誰" → shipment batch
        (
            re.compile(r"([A-Za-z0-9\-_]+)\s*(?:出貨|出給|銷貨)", re.IGNORECASE),
            lambda m: ("shipment_batch", m.group(1)),
        ),
        # "查成品 XXX 的履歷" / "XXX 的完整履歷" → product full history
        (
            re.compile(
                r"(?:查|查詢?)?\s*(?:成品|產品)?\s*([A-Za-z0-9\-_]+)\s*(?:的)?\s*(?:完整)?履歷",
                re.IGNORECASE,
            ),
            lambda m: ("product_full_history", m.group(1)),
        ),
        # "供應商 XXX 的料" / "XXX 供應商" → supplier trace
        (
            re.compile(r"(?:供應商|廠商)\s*([A-Za-z0-9\-_]+)", re.IGNORECASE),
            lambda m: ("supplier_trace", m.group(1)),
        ),
        # "工單 XXX" / "製令 XXX" → work order
        (
            re.compile(
                r"(?:工單|製令|MFG|WO)\s*:?\s*([A-Za-z0-9\-_]+)", re.IGNORECASE
            ),
            lambda m: ("work_order", m.group(1)),
        ),
        # "QC XXX" / "品質 XXX" / "檢驗 XXX" → quality issue
        (
            re.compile(
                r"(?:QC|品質|檢驗|品檢)\s*:?\s*([A-Za-z0-9\-_]+)", re.IGNORECASE
            ),
            lambda m: ("quality_issue", m.group(1)),
        ),
        # "效期" / "到期" → expiry tracking (date-range query, batch empty)
        (
            re.compile(r"(?:效期|到期|過期|expir)", re.IGNORECASE),
            lambda m: ("expiry_tracking", ""),
        ),
    ]

    def parse(self, text: str) -> NlParseResult:
        """Parse a natural language query string.

        Args:
            text: The user's natural language query (e.g. "追蹤批號 B001").

        Returns:
            An NlParseResult with parsed fields set on success, or
            parsed=False with a suggestion on failure.
        """
        text = text.strip()
        if not text:
            return NlParseResult(
                parsed=False, suggestion="請輸入查詢內容，例如「追蹤批號 B001」"
            )

        for pattern, extractor in self.PATTERNS:
            match = pattern.search(text)
            if match:
                try:
                    scenario_str, batch_val = extractor(match)
                    scenario = self._SCENARIO_MAP.get(scenario_str)
                    if scenario is not None:
                        return NlParseResult(
                            parsed=True,
                            scenario=scenario,
                            batch_no=batch_val if batch_val else "",
                        )
                except Exception:
                    logger.debug(
                        "Pattern extraction failed for: %r", text, exc_info=True
                    )
                    continue

        return NlParseResult(
            parsed=False,
            suggestion=(
                "無法解析查詢。請嘗試：\n"
                "• 「追蹤批號 B001」\n"
                "• 「查成品 ABC 的履歷」\n"
                "• 「供應商 XYZ 的料」\n"
                "• 「工單 MFG001」\n"
                "• 「效期追蹤」"
            ),
        )


async def handle_nl_parse(text: str) -> dict[str, object]:
    """Convenience async handler for parsing a natural language trace query.

    Args:
        text: The raw query string from the user.

    Returns:
        A dict suitable for JSON serialisation (see NlParseResult.to_dict).
    """
    parser = NlTraceParser()
    result = parser.parse(text)
    return result.to_dict()
