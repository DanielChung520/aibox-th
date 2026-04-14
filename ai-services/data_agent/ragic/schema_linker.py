"""
@file        schema_linker.py
@description Links a matched intent to its table's field schema from ArangoDB,
             then builds a JSON Schema enum constraint for tool-calling.
             Flow: intent.table_key → da_tables.fields → LinkedSchema.
@lastUpdate  2026-04-13
@author      Daniel Chung
@version     2.0.0
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
    """Load field definitions from ArangoDB da_tables for a given table_key.

    Args:
        table_key: Table identifier (e.g. "RAGICPURCHASING_1").

    Returns:
        List of dicts with field_id, field_name, field_type keys.
    """
    aql = (
        "FOR d IN da_tables "
        "FILTER d._key == @table_key "
        "RETURN d.fields"
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
    result = resp.json().get("result", [])
    if result:
        raw_fields = result[0]
        if isinstance(raw_fields, list):
            for f in raw_fields:
                if isinstance(f, dict):
                    fid = str(f.get("field_id", ""))
                    fname = f.get("name", "")
                    ftype = f.get("type", "text")
                    if fname and fid:
                        rows.append({
                            "field_id": fid,
                            "field_name": fname,
                            "field_type": str(ftype),
                        })
        elif isinstance(raw_fields, dict):
            for fid, fdata in raw_fields.items():
                if isinstance(fdata, dict):
                    fname = fdata.get("name", "")
                    ftype = fdata.get("type", "text")
                    if fname and fid:
                        rows.append({
                            "field_id": fid,
                            "field_name": fname,
                            "field_type": str(ftype),
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

    MAX_SCHEMA_FIELDS = 30
    if len(fields) > MAX_SCHEMA_FIELDS:
        logger.info("Limiting %s from %d to %d fields for tool-calling", table_key, len(fields), MAX_SCHEMA_FIELDS)
        fields = fields[:MAX_SCHEMA_FIELDS]

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
