"""
@file        date_resolver.py
@description Rule-based date extraction from Chinese natural language queries.
             Converts expressions like '上個月', '近7天', '2026年3月' into
             Ragic-compatible date ranges (gte/lte where clauses).
@lastUpdate  2026-04-12 23:50:45
@author      Daniel Chung
@version     1.2.0
"""

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class DateRange:
    start: date
    end: date

    def start_str(self) -> str:
        return self.start.strftime("%Y/%m/%d")

    def end_str(self) -> str:
        return self.end.strftime("%Y/%m/%d")


_RELATIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"今天|今日"), "today"),
    (re.compile(r"昨天|昨日"), "yesterday"),
    (re.compile(r"前天"), "day_before_yesterday"),
    (re.compile(r"這個?月|本月"), "this_month"),
    (re.compile(r"上個?月"), "last_month"),
    (re.compile(r"這個?[禮礼]?[拜週周]|本[週周]"), "this_week"),
    (re.compile(r"上個?[禮礼]?[拜週周]|上[週周]"), "last_week"),
    (re.compile(r"今年|本年"), "this_year"),
    (re.compile(r"去年|上一?年"), "last_year"),
    (re.compile(r"[近最](\d+)\s*天"), "recent_days"),
    (re.compile(r"[近最](\d+)\s*[週周]"), "recent_weeks"),
    (re.compile(r"[近最](\d+)\s*[個]?月"), "recent_months"),
]

_ABSOLUTE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(\d{4})\s*[年/\-]\s*(\d{1,2})\s*[月/\-]\s*(\d{1,2})\s*[日號号]?"), "full_date"),
    (re.compile(r"(\d{4})\s*[年/\-]\s*(\d{1,2})\s*月?(?!\s*\d)"), "year_month"),
    (re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日號号]"), "month_day"),
    (re.compile(r"(\d{1,2})\s*月(?!\s*\d)"), "month_only"),
]


_CN_DIGIT: dict[str, int] = {
    "〇": 0, "零": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def _cn_to_int(text: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text == "十":
        return 10
    if len(text) == 1:
        return _CN_DIGIT.get(text)
    if text.startswith("十"):
        unit = _CN_DIGIT.get(text[1])
        return 10 + unit if unit is not None else None
    if len(text) == 2 and text[1] == "十":
        tens = _CN_DIGIT.get(text[0])
        return tens * 10 if tens is not None else None
    if len(text) == 3 and text[1] == "十":
        tens = _CN_DIGIT.get(text[0])
        ones = _CN_DIGIT.get(text[2])
        if tens is not None and ones is not None:
            return tens * 10 + ones
    return None


_CN_NUM_RE = re.compile(
    r"([〇零一二兩三四五六七八九十]{1,3})\s*([月日號号])"
)


def _normalize_cn_numbers(query: str) -> str:
    def _replace(m: re.Match[str]) -> str:
        n = _cn_to_int(m.group(1))
        return f"{n}{m.group(2)}" if n is not None else m.group(0)
    return _CN_NUM_RE.sub(_replace, query)


def _month_range(year: int, month: int) -> DateRange:
    last_day = calendar.monthrange(year, month)[1]
    return DateRange(start=date(year, month, 1), end=date(year, month, last_day))


def _week_range(ref: date, offset: int = 0) -> DateRange:
    monday = ref - timedelta(days=ref.weekday()) + timedelta(weeks=offset)
    sunday = monday + timedelta(days=6)
    return DateRange(start=monday, end=sunday)


def resolve(query: str, today: date | None = None) -> DateRange | None:
    ref = today or date.today()
    query = _normalize_cn_numbers(query)

    for pattern, kind in _RELATIVE_PATTERNS:
        m = pattern.search(query)
        if not m:
            continue

        if kind == "today":
            return DateRange(start=ref, end=ref)
        if kind == "yesterday":
            d = ref - timedelta(days=1)
            return DateRange(start=d, end=d)
        if kind == "day_before_yesterday":
            d = ref - timedelta(days=2)
            return DateRange(start=d, end=d)
        if kind == "this_month":
            return _month_range(ref.year, ref.month)
        if kind == "last_month":
            first = date(ref.year, ref.month, 1)
            prev = first - timedelta(days=1)
            return _month_range(prev.year, prev.month)
        if kind == "this_week":
            return _week_range(ref, offset=0)
        if kind == "last_week":
            return _week_range(ref, offset=-1)
        if kind == "this_year":
            return DateRange(start=date(ref.year, 1, 1), end=date(ref.year, 12, 31))
        if kind == "last_year":
            y = ref.year - 1
            return DateRange(start=date(y, 1, 1), end=date(y, 12, 31))
        if kind == "recent_days":
            n = int(m.group(1))
            return DateRange(start=ref - timedelta(days=n), end=ref)
        if kind == "recent_weeks":
            n = int(m.group(1))
            return DateRange(start=ref - timedelta(weeks=n), end=ref)
        if kind == "recent_months":
            n = int(m.group(1))
            y = ref.year
            mo = ref.month - n
            while mo <= 0:
                mo += 12
                y -= 1
            return DateRange(start=date(y, mo, ref.day if ref.day <= 28 else 28), end=ref)

    for pattern, kind in _ABSOLUTE_PATTERNS:
        m = pattern.search(query)
        if not m:
            continue

        if kind == "full_date":
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return DateRange(start=d, end=d)
        if kind == "year_month":
            return _month_range(int(m.group(1)), int(m.group(2)))
        if kind == "month_day":
            d = date(ref.year, int(m.group(1)), int(m.group(2)))
            return DateRange(start=d, end=d)
        if kind == "month_only":
            return _month_range(ref.year, int(m.group(1)))

    return None


def contains_date_expression(query: str) -> bool:
    """Check whether *query* contains any recognisable date expression.

    This is a lightweight wrapper around :func:`resolve` used by the NL
    parser to decide whether a clarification should be requested from the
    caller (the front-end orchestrator) without actually resolving the
    date into an absolute range.
    """
    return resolve(query) is not None
