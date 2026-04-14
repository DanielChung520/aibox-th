"""
@file        query_type_inferrer.py
@description Rule-based query_type inference (Phase 1b).
             Given a user query + matched table's capabilities/fields,
             dynamically determine the appropriate query_type without
             relying on static intent metadata.
@lastUpdate  2026-04-13 06:16:12
@author      Daniel Chung
@version     1.0.0
"""

import logging
import os
import re

import httpx

logger = logging.getLogger(__name__)

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")

VALID_QUERY_TYPES = {"simple_filter", "aggregate", "cross_table", "time_series"}

_AGGREGATE_KEYWORDS = re.compile(
    r"(總[計共額量]|合計|平均|統計|加總|小計|"
    r"sum|avg|average|total|count|max|min|"
    r"多少|幾[筆個項條]|數量|佔比|百分比|比例|"
    r"排[名行序]|top\s?\d|前\s?\d|"
    r"分[析佈布]|group\s*by|彙[總整])",
    re.IGNORECASE,
)

_TIME_SERIES_KEYWORDS = re.compile(
    r"(趨勢|走勢|變化|成長|增[長減]|波動|"
    r"按[月日週年季]|每[月日週年季]|逐[月日週年]|"
    r"同期|環比|年增|月增|"
    r"時間[序線]|time\s*series|trend|"
    r"歷[年月史]|近\s?\d+\s?[月日年週])",
    re.IGNORECASE,
)

_CROSS_TABLE_KEYWORDS = re.compile(
    r"(關聯|連結|join|合併|cross|"
    r"對[照應]|比[較對].*表|"
    r"跨表|多表|兩[張個]表|"
    r"搭配.*表|結合.*表)",
    re.IGNORECASE,
)


class TableCapabilities:
    """Lightweight container for da_tables capabilities."""

    __slots__ = ("simple_filter", "aggregate", "time_series", "cross_table")

    def __init__(
        self,
        simple_filter: bool = True,
        aggregate: bool = False,
        time_series: bool = False,
        cross_table: bool = False,
    ) -> None:
        self.simple_filter = simple_filter
        self.aggregate = aggregate
        self.time_series = time_series
        self.cross_table = cross_table


async def _fetch_table_capabilities(table_key: str) -> TableCapabilities | None:
    """Fetch capabilities from da_tables by _key (e.g. 'ERP_13')."""
    raw_key = table_key.split("/")[0] if "/" in table_key else table_key
    aql = (
        "FOR d IN da_tables FILTER d._key == @key "
        "RETURN { capabilities: d.capabilities }"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": aql, "bindVars": {"key": raw_key}},
                auth=(ARANGO_USER, ARANGO_PASSWORD),
            )
            if resp.status_code not in (200, 201):
                return None
            results: list[dict[str, object]] = resp.json().get("result", [])
            if not results:
                return None
            caps_raw = results[0].get("capabilities", {})
            if not isinstance(caps_raw, dict):
                return None
            return TableCapabilities(
                simple_filter=bool(caps_raw.get("simple_filter", True)),
                aggregate=bool(caps_raw.get("aggregate", False)),
                time_series=bool(caps_raw.get("time_series", False)),
                cross_table=bool(caps_raw.get("cross_table", False)),
            )
    except httpx.HTTPError:
        logger.warning("Failed to fetch capabilities for %s", raw_key)
        return None


def _keyword_match(query: str) -> str | None:
    if _CROSS_TABLE_KEYWORDS.search(query):
        return "cross_table"
    if _TIME_SERIES_KEYWORDS.search(query):
        return "time_series"
    if _AGGREGATE_KEYWORDS.search(query):
        return "aggregate"
    return None


async def infer_query_type(
    query: str,
    table_key: str,
) -> str:
    """Infer query_type from user query + table capabilities.

    Strategy:
    1. Keyword detection from the user query.
    2. Cross-check with table capabilities — only assign
       a type if the table actually supports it.
    3. Default to simple_filter.
    """
    if not table_key:
        return "simple_filter"

    keyword_type = _keyword_match(query)

    if keyword_type is None:
        return "simple_filter"

    caps = await _fetch_table_capabilities(table_key)
    if caps is None:
        logger.debug(
            "No capabilities found for %s, using keyword inference: %s",
            table_key,
            keyword_type,
        )
        return keyword_type

    if keyword_type == "aggregate" and caps.aggregate:
        return "aggregate"
    if keyword_type == "time_series" and caps.time_series:
        return "time_series"
    if keyword_type == "cross_table" and caps.cross_table:
        return "cross_table"

    if keyword_type == "aggregate" and not caps.aggregate:
        logger.debug(
            "Query suggests aggregate but table %s lacks numeric fields, "
            "falling back to simple_filter",
            table_key,
        )
        return "simple_filter"
    if keyword_type == "time_series" and not caps.time_series:
        logger.debug(
            "Query suggests time_series but table %s lacks date fields, "
            "falling back to simple_filter",
            table_key,
        )
        return "simple_filter"
    if keyword_type == "cross_table" and not caps.cross_table:
        logger.debug(
            "Query suggests cross_table but table %s has no relationships, "
            "falling back to simple_filter",
            table_key,
        )
        return "simple_filter"

    return "simple_filter"
