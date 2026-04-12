"""
@file        arango_writer.py
@description Write ParsedTable schemas, fields, and intents to ArangoDB collections
             (da_table_info_ragic, da_field_info_ragic, da_table_relation_ragic, intent_catalog).
@lastUpdate  2026-04-12 21:06:05
@author      Daniel Chung
@version     1.3.0
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from data_agent.ragic.models import RagicIntent
    from data_agent.ragic.models_phase9 import ParsedField, ParsedTable, TableRelationEdge

logger = logging.getLogger(__name__)

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")

_TABLE_COLLECTION = "da_table_info_ragic"
_FIELD_COLLECTION = "da_field_info_ragic"
_RELATION_COLLECTION = "da_table_relation_ragic"
_INTENT_COLLECTION = "intent_catalog"
_BATCH_SIZE = 50


def _make_table_id(account: str, table: ParsedTable) -> str:
    return f"{account}_{table.tab_path}_{table.sheet_index}"


def _make_table_doc(table: ParsedTable, account: str) -> dict[str, object]:
    table_id = _make_table_id(account, table)
    return {
        "_key": table_id,
        "table_name": table.table_name,
        "description": table.table_name,
        "row_count_estimate": 0,
        "module": table.tab_name,
        "tab": table.tab_path,
        "sheet_key": str(table.sheet_index),
        "s3_path": "",
        "account": account,
    }


def _make_field_doc(
    field: ParsedField,
    table_id: str,
    is_subtable: bool = False,
    subtable_key: str = "",
) -> dict[str, object]:
    return {
        "_key": f"{table_id}_{field.field_id}",
        "table_id": table_id,
        "field_name": field.name,
        "field_type": field.field_type,
        "description": "",
        "is_pk": False,
        "field_id": field.field_id,
        "writable": field.writable,
        "is_subtable": is_subtable,
        "subtable_key": subtable_key,
    }


class RagicArangoWriter:

    def __init__(
        self,
        arango_url: str | None = None,
        arango_db: str | None = None,
        arango_user: str | None = None,
        arango_password: str | None = None,
    ) -> None:
        self._url = arango_url or ARANGO_URL
        self._db = arango_db or ARANGO_DB
        self._user = arango_user or ARANGO_USER
        self._password = arango_password or ARANGO_PASSWORD

    @property
    def _base(self) -> str:
        return f"{self._url}/_db/{self._db}"

    @property
    def _auth(self) -> tuple[str, str]:
        return (self._user, self._password)

    async def ensure_collections(self) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for name in (_TABLE_COLLECTION, _FIELD_COLLECTION, _RELATION_COLLECTION):
                resp = await client.post(
                    f"{self._base}/_api/collection",
                    json={"name": name, "type": 2},
                    auth=self._auth,
                )
                if resp.status_code in (200, 201, 202):
                    logger.info("Created collection '%s'", name)
                elif resp.status_code == 409:
                    pass
                else:
                    logger.warning(
                        "Collection create '%s' returned %d: %s",
                        name, resp.status_code, resp.text[:200],
                    )

    async def clear_collections(self, account: str) -> dict[str, int]:
        result: dict[str, int] = {}
        async with httpx.AsyncClient(timeout=30.0) as client:
            for coll in (_TABLE_COLLECTION, _FIELD_COLLECTION, _RELATION_COLLECTION):
                aql = f'FOR d IN {coll} FILTER d.account == @account REMOVE d IN {coll} RETURN 1'
                resp = await client.post(
                    f"{self._base}/_api/cursor",
                    json={"query": aql, "bindVars": {"account": account}},
                    auth=self._auth,
                )
                if resp.status_code == 201:
                    removed = resp.json().get("result", [])
                    result[coll] = len(removed)
                else:
                    result[coll] = 0
        return result

    async def write_tables(self, tables: list[ParsedTable], account: str) -> int:
        docs = [_make_table_doc(t, account) for t in tables]
        return await self._batch_upsert(_TABLE_COLLECTION, docs)

    async def write_fields(self, tables: list[ParsedTable], account: str) -> int:
        docs: list[dict[str, object]] = []
        for table in tables:
            table_id = _make_table_id(account, table)
            for field in table.fields:
                docs.append(_make_field_doc(field, table_id))
            for sub_key, sub_fields in table.subtables.items():
                for field in sub_fields:
                    docs.append(
                        _make_field_doc(field, table_id, is_subtable=True, subtable_key=sub_key)
                    )
        return await self._batch_upsert(_FIELD_COLLECTION, docs)

    async def write_relations(
        self, relations: list[TableRelationEdge], account: str
    ) -> int:
        docs: list[dict[str, object]] = []
        join_map = {"link": "LEFT", "load": "LEFT"}
        for rel in relations:
            raw = f"{account}_{rel.from_table}_{rel.from_field_id}_{rel.relation_type}"
            key = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
            docs.append({
                "_key": key,
                "left_table": f"{account}_{rel.from_table}",
                "left_field": rel.from_field,
                "right_table": f"{account}_{rel.to_table}",
                "right_field": rel.to_field,
                "join_type": join_map.get(rel.relation_type, "LEFT"),
                "sync_mode": rel.sync_mode or "",
                "account": account,
            })
        return await self._batch_upsert(_RELATION_COLLECTION, docs)

    async def _batch_upsert(self, collection: str, docs: list[dict[str, object]]) -> int:
        if not docs:
            return 0
        total = 0
        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(0, len(docs), _BATCH_SIZE):
                batch = docs[i : i + _BATCH_SIZE]
                aql = (
                    "FOR doc IN @batch "
                    f"UPSERT {{_key: doc._key}} INSERT doc UPDATE doc IN {collection} "
                    "RETURN 1"
                )
                resp = await client.post(
                    f"{self._base}/_api/cursor",
                    json={"query": aql, "bindVars": {"batch": batch}},
                    auth=self._auth,
                )
                if resp.status_code in (200, 201):
                    total += len(resp.json().get("result", []))
                else:
                    logger.error(
                        "ArangoDB upsert to '%s' failed: %d %s",
                        collection, resp.status_code, resp.text[:200],
                    )
        logger.info("Upserted %d docs into '%s'", total, collection)
        return total

    async def fetch_table_id_map(self, account: str) -> dict[str, dict[str, str]]:
        aql = (
            "FOR t IN da_table_info_ragic "
            "FILTER t.account == @account "
            "LET tk = CONCAT(t.tab, '/', t.sheet_key) "
            "RETURN {table_key: tk, table_id: t._key, sheet_key: t.sheet_key}"
        )
        result: dict[str, dict[str, str]] = {}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._base}/_api/cursor",
                json={"query": aql, "bindVars": {"account": account}},
                auth=self._auth,
            )
            if resp.status_code in (200, 201):
                for row in resp.json().get("result", []):
                    result[row["table_key"]] = {
                        "table_id": row["table_id"],
                        "sheet_key": row["sheet_key"],
                    }
        logger.info("Fetched table_id_map: %d entries for account '%s'", len(result), account)
        return result

    async def write_intents(self, intents: list[RagicIntent], account: str) -> int:
        docs: list[dict[str, object]] = []
        for intent in intents:
            docs.append({
                "_key": intent.intent_id,
                "intent_id": intent.intent_id,
                "account": intent.account,
                "scope": "data_agent",
                "description": intent.description,
                "action": intent.action,
                "table_key": intent.table_key,
                "table_id": intent.table_id,
                "sheet_key": intent.sheet_key,
                "nl_patterns": intent.nl_patterns,
                "filter_template": (
                    intent.filter_template.model_dump()
                    if intent.filter_template
                    else None
                ),
                "api_template": intent.api_template,
                "source": "auto_generated",
            })
        return await self._batch_upsert(_INTENT_COLLECTION, docs)
