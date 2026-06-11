"""
@file        llm_translator.py
@description LLM-based NL → Ragic query parameter translation.
             Extracted from nl_parser.py to keep module sizes ≤ 300 lines.
             Handles: prompt construction, Ollama API call, response parsing,
             ArangoDB schema loading, and field_id post-validation.
@lastUpdate  2026-04-13 01:43:49
@author      Daniel Chung
@version     1.0.0
"""

import json
import logging
import os
import re
from datetime import date

import httpx

from data_agent.ragic.models import (
    NLQueryOptions,
    RagicOperator,
    RagicWhereClause,
    TranslatedParams,
)

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")


async def _get_small_model() -> str:
    from data_agent.config_reader import get_param

    return await get_param("da.small_llm_model")


async def translate_via_llm(
    query: str,
    account: str | None,
    table_key: str,
    opts: NLQueryOptions,
) -> TranslatedParams:
    """Call LLM to translate NL query into structured Ragic query params.

    Loads table schema from ArangoDB, builds a constrained prompt,
    calls Ollama, and validates field_ids against the schema.

    Args:
        query: User's natural language query.
        account: Ragic account (currently unused, reserved).
        table_key: Target table identifier (e.g. "configuration-file/10").
        opts: Query options (limit, etc).

    Returns:
        Translated query parameters with validated field_ids.
    """
    schema_context = ""
    if table_key:
        schema_context = await load_schema_from_arango(table_key)

    prompt = build_llm_prompt(query, schema_context)

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
            valid_fids = extract_field_ids(schema_context)
            return parse_llm_response(llm_response, opts, valid_fids)
    except Exception as exc:
        logger.warning("LLM fallback failed: %s", exc)
        return TranslatedParams(limit=opts.limit, naming="EID")


def build_llm_prompt(query: str, schema_context: str) -> str:
    """Build constrained prompt for LLM query translation.

    Args:
        query: User's NL query.
        schema_context: Field list loaded from ArangoDB.

    Returns:
        Full prompt string for Ollama.
    """
    today = date.today().strftime("%Y/%m/%d")
    schema_section = (
        f"\n【欄位清單（僅可使用以下 field_id）】\n{schema_context}\n"
        if schema_context
        else ""
    )
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


def extract_field_ids(schema_context: str) -> set[str]:
    """Extract valid field_ids from schema context string.

    Args:
        schema_context: Multi-line string with "field_id: field_name" per line.

    Returns:
        Set of valid field_id strings.
    """
    fids: set[str] = set()
    for line in schema_context.splitlines():
        stripped = line.strip()
        if ":" in stripped:
            fid = stripped.split(":", 1)[0].strip()
            if fid:
                fids.add(fid)
    return fids


def parse_llm_response(
    raw: str,
    opts: NLQueryOptions,
    valid_fids: set[str],
) -> TranslatedParams:
    """Parse and validate LLM JSON response into TranslatedParams.

    Drops any field_id not present in valid_fids (post-validation layer).

    Args:
        raw: Raw JSON string from LLM.
        opts: Query options for defaults.
        valid_fids: Set of valid field_ids from ArangoDB schema.

    Returns:
        Validated TranslatedParams.
    """
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
    raw_where = data.get("where")
    for w in raw_where if isinstance(raw_where, list) else []:
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
        where_clauses.append(
            RagicWhereClause(field_id=fid, operator=op, value=val)
        )

    raw_limit = data.get("limit", opts.limit)
    limit = max(
        1,
        min(
            int(raw_limit) if isinstance(raw_limit, (int, float)) else opts.limit,
            1000,
        ),
    )
    raw_offset = data.get("offset", 0)
    offset = int(raw_offset) if isinstance(raw_offset, (int, float)) else 0
    order_field = (
        str(data["order_field"]) if data.get("order_field") is not None else None
    )
    if order_field and valid_fids and order_field not in valid_fids:
        logger.warning("LLM produced unknown order_field %s — dropped", order_field)
        order_field = None
    order_dir = str(data.get("order_direction", "DESC")).upper()
    order_dir = order_dir if order_dir in ("ASC", "DESC") else "DESC"

    return TranslatedParams(
        where=where_clauses,
        limit=limit,
        offset=offset,
        naming="EID",
        order_field=order_field,
        order_direction=order_dir,
    )


async def load_schema_from_arango(table_key: str) -> str:
    """Load table field schema from ArangoDB da_tables.

    Args:
        table_key: Table identifier (e.g. "RAGICPURCHASING_1").

    Returns:
        Multi-line string of "  field_id: field_name" entries, or empty string on error.
    """
    aql = (
        "FOR d IN da_tables "
        "FILTER d._key == @table_key "
        "RETURN d.fields"
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
        if isinstance(row, dict):
            for fid, fdata in row.items():
                if isinstance(fdata, dict):
                    fname = fdata.get("name", "")
                    if fname and fid:
                        parts.append(f"  {fid}: {fname}")
    return "\n".join(parts)


async def load_schemas_for_tables(table_keys: list[str]) -> str:
    """Load schemas for multiple tables for Phase 2 LLM Schema Injection.

    Args:
        table_keys: List of table identifiers (max 5).

    Returns:
        Multi-section schema string for prompt context.
    """
    schemas: list[str] = []
    for tk in table_keys[:5]:
        schema = await load_schema_from_arango(tk)
        if schema:
            schemas.append(f"### {tk}\n{schema}")
    return "\n\n".join(schemas)
