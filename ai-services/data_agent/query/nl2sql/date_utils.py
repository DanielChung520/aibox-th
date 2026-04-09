"""
NL→SQL Pipeline - Date Utility Functions

Parses natural language temporal expressions (Chinese + English) into
concrete date ranges for SQL template placeholder replacement.

# Last Update: 2026-03-24 15:51:03
# Author: Daniel Chung
# Version: 1.0.0
"""

import re
from datetime import date, timedelta


def compute_date_range(query: str) -> tuple[str, str]:
    """Extract date range from NL query temporal expressions.

    Supports Chinese and English temporal patterns:
    - 上個月 / 上月 / last month
    - 本月 / 這個月 / this month
    - 過去N個月 / last N months
    - 過去一年 / last year / 去年
    - 本季 / 上季 / this quarter / last quarter
    - YYYY年MM月 / YYYY-MM
    - 今年 / this year
    - 上半年 / 下半年

    Args:
        query: Natural language query string.

    Returns:
        Tuple of (start_date, end_date) as 'YYYY-MM-DD' strings
        (matching ArangoDB Ragic date column format).
        Returns 12-month lookback if no temporal expression is found.
    """
    today = date.today()

    # --- 上個月 / last month ---
    if re.search(r"上個月|上月|last\s+month", query, re.IGNORECASE):
        first_of_this_month = today.replace(day=1)
        end = first_of_this_month - timedelta(days=1)
        start = end.replace(day=1)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    # --- 本月 / this month ---
    if re.search(r"本月|這個月|这个月|this\s+month", query, re.IGNORECASE):
        start = today.replace(day=1)
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

    # --- 過去N個月 / last N months ---
    m = re.search(r"過去(\d+)個月|近(\d+)個月|last\s+(\d+)\s+months?", query, re.IGNORECASE)
    if m:
        n = int(m.group(1) or m.group(2) or m.group(3))
        start = _months_ago(today, n)
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

    # --- 過去一年 / 去年 / last year ---
    if re.search(r"過去一年|去年|last\s+year", query, re.IGNORECASE):
        start = date(today.year - 1, 1, 1)
        end = date(today.year - 1, 12, 31)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    # --- 今年 / this year ---
    if re.search(r"今年|this\s+year|本年", query, re.IGNORECASE):
        start = date(today.year, 1, 1)
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

    # --- 上半年 ---
    if re.search(r"上半年|first\s+half", query, re.IGNORECASE):
        start = date(today.year, 1, 1)
        end = date(today.year, 6, 30)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    # --- 下半年 ---
    if re.search(r"下半年|second\s+half", query, re.IGNORECASE):
        start = date(today.year, 7, 1)
        end = date(today.year, 12, 31)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    # --- 本季 / this quarter ---
    if re.search(r"本季|這一季|this\s+quarter", query, re.IGNORECASE):
        q = (today.month - 1) // 3
        start = date(today.year, q * 3 + 1, 1)
        return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")

    # --- 上季 / last quarter ---
    if re.search(r"上季|上一季|last\s+quarter", query, re.IGNORECASE):
        q = (today.month - 1) // 3
        if q == 0:
            start = date(today.year - 1, 10, 1)
            end = date(today.year - 1, 12, 31)
        else:
            start = date(today.year, (q - 1) * 3 + 1, 1)
            end_month = q * 3
            end = date(today.year, end_month, _last_day(today.year, end_month))
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    # --- Q1/Q2/Q3/Q4 ---
    qm = re.search(r"Q([1-4])", query, re.IGNORECASE)
    if qm:
        q_num = int(qm.group(1))
        year = today.year
        ym = re.search(r"(\d{4})\s*年?\s*Q", query, re.IGNORECASE)
        if ym:
            year = int(ym.group(1))
        start_month = (q_num - 1) * 3 + 1
        end_month = q_num * 3
        start = date(year, start_month, 1)
        end = date(year, end_month, _last_day(year, end_month))
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    # --- YYYY年MM月 or YYYY-MM ---
    ym_match = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月|(\d{4})-(\d{2})", query)
    if ym_match:
        year = int(ym_match.group(1) or ym_match.group(3))
        month = int(ym_match.group(2) or ym_match.group(4))
        if 1 <= month <= 12:
            start = date(year, month, 1)
            end = date(year, month, _last_day(year, month))
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    # --- YYYY年 (whole year) ---
    y_match = re.search(r"(\d{4})\s*年(?!\s*\d)", query)
    if y_match:
        year = int(y_match.group(1))
        return date(year, 1, 1).strftime("%Y-%m-%d"), date(year, 12, 31).strftime("%Y-%m-%d")

    # --- Default: 12-month lookback ---
    start = _months_ago(today, 12)
    return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


def _months_ago(ref: date, n: int) -> date:
    """Compute date N months before ref, clamping day to valid range."""
    month = ref.month - n
    year = ref.year
    while month <= 0:
        month += 12
        year -= 1
    day = min(ref.day, _last_day(year, month))
    return date(year, month, day)


def _last_day(year: int, month: int) -> int:
    """Return the last day of the given year-month."""
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timedelta(days=1)).day
