"""
@file        schema_linker.py
@description Links a matched intent to its table's field schema from ArangoDB,
             then builds a JSON Schema enum constraint for tool-calling.
             Flow: intent.table_key → da_table_info_ragic → da_field_info_ragic
             → LinkedSchema (tool_schema + field_label_map).
@lastUpdate  2026-04-13 02:14:43
@author      Daniel Chung
@version     1.0.0
"""

import logging
import os

import httpx

from data_agent.ragic.tool_calling_engine import build_tool_schema

logger = logging.getLogger(__name__)

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")


class LinkedSchema:
    """Result of linking an intent to its table field schema."""

    __slots__ = (
        "tool_schema",
        "field_label_map",
        "field_ids",
        "table_key",
        "field_count",
        "success",
        "error_message",
    )

    def __init__(
        self,
        tool_schema: dict[str, object],
        field_label_map: dict[str, str],
        field_ids: list[str],
        table_key: str = "",
        success: bool = True,
        error_message: str = "",
    ) -> None:
        self.tool_schema = tool_schema
        self.field_label_map = field_label_map
        self.field_ids = field_ids
        self.table_key = table_key
        self.field_count = len(field_ids)
        self.success = success
        self.error_message = error_message


async def load_fields_from_arango(
    table_key: str,
) -> list[dict[str, str]]:
    """Load field definitions from ArangoDB for a given table_key.

    Uses the same JOIN pattern as query_engine._load_field_labels:
    da_table_info_ragic JOIN da_field_info_ragic on table_id == t._key.

    Args:
        table_key: e.g. "configuration-file/10" (tab/sheet_number).

    Returns:
        List of dicts with field_id, field_name, field_type keys.
    """
    aql = (
        "FOR t IN da_table_info_ragic "
        'FILTER CONCAT(t.tab, "/", t.sheet_number) == @table_key '
        "FOR f IN da_field_info_ragic "
        "FILTER f.table_id == t._key "
        "RETURN {field_id: f.field_id, field_name: f.field_name, "
        "field_type: TO_STRING(f.field_type)}"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": aql, "bindVars": {"table_key": table_key}},
                auth=(ARANGO_USER, ARANGO_PASSWORD),
            )
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("Failed to load fields from ArangoDB for %s: %s", table_key, exc)
        return []

    rows: list[dict[str, str]] = []
    for row in resp.json().get("result", []):
        fid = str(row.get("field_id", ""))
        fname = str(row.get("field_name", ""))
        if fid and fname:
            rows.append({
                "field_id": fid,
                "field_name": fname,
                "field_type": str(row.get("field_type", "text")),
            })
    return rows


async def link_intent_to_schema(table_key: str) -> LinkedSchema:
    """Link a table_key to its field schema and build tool-calling constraint.

    Args:
        table_key: Table key from matched intent (e.g. "configuration-file/10").

    Returns:
        LinkedSchema with tool_schema and field_label_map ready for tool_calling_engine.
    """
    if not table_key:
        return LinkedSchema(
            tool_schema={},
            field_label_map={},
            field_ids=[],
            table_key=table_key,
            success=False,
            error_message="table_key 為空",
        )

    fields = await load_fields_from_arango(table_key)
    if not fields:
        return LinkedSchema(
            tool_schema={},
            field_label_map={},
            field_ids=[],
            table_key=table_key,
            success=False,
            error_message=f"無法從 ArangoDB 載入欄位資訊：{table_key}",
        )

    field_ids = [f["field_id"] for f in fields]
    field_label_map = {f["field_id"]: f["field_name"] for f in fields}

    tool_schema = build_tool_schema(field_ids)

    logger.info(
        "Linked table %s → %d fields for tool-calling",
        table_key,
        len(field_ids),
    )

    return LinkedSchema(
        tool_schema=tool_schema,
        field_label_map=field_label_map,
        field_ids=field_ids,
        table_key=table_key,
    )
