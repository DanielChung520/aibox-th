"""
@file        schema_sync.py
@description Auto-sync Ragic table schemas into Qdrant by fetching one
             record with both EID and field_name naming modes.
@lastUpdate  2026-04-11 13:28:14
@author      Daniel Chung
@version     1.0.0
"""

import logging

from data_agent.ragic.client import RagicAPIClient
from data_agent.ragic.models import (
    RagicFieldSchema,
    RagicQueryParams,
    RagicTableSchema,
)
from data_agent.ragic.schema_store import RagicSchemaStore

logger = logging.getLogger(__name__)


class RagicSchemaSync:
    def __init__(
        self,
        schema_store: RagicSchemaStore | None = None,
    ) -> None:
        self._store = schema_store or RagicSchemaStore()

    async def sync_table(
        self,
        client: RagicAPIClient,
        tab_path: str,
        sheet_index: int,
        table_name: str = "",
        description: str = "",
        module: str = "",
    ) -> RagicTableSchema | None:
        eid_fields, name_fields = await self._fetch_field_mapping(
            client, tab_path, sheet_index
        )
        if not eid_fields:
            logger.warning(
                "No records in %s/%d, cannot extract schema",
                tab_path,
                sheet_index,
            )
            return None

        schema = self._build_schema(
            account=client.account,
            tab_path=tab_path,
            sheet_index=sheet_index,
            eid_fields=eid_fields,
            name_fields=name_fields,
            table_name=table_name,
            description=description,
            module=module,
        )

        await self._store.upsert([schema])
        logger.info(
            "Synced schema for %s/%d with %d fields",
            tab_path,
            sheet_index,
            len(schema.fields),
        )
        return schema

    async def sync_tables(
        self,
        client: RagicAPIClient,
        table_keys: list[str],
    ) -> list[RagicTableSchema]:
        synced: list[RagicTableSchema] = []
        for key in table_keys:
            parts = key.rsplit("/", 1)
            if len(parts) != 2:
                logger.warning("Invalid table_key format: %s", key)
                continue

            tab_path = parts[0]
            try:
                sheet_index = int(parts[1])
            except ValueError:
                logger.warning("Invalid sheet_index in key: %s", key)
                continue

            schema = await self.sync_table(client, tab_path, sheet_index)
            if schema:
                synced.append(schema)

        return synced

    async def _fetch_field_mapping(
        self,
        client: RagicAPIClient,
        tab_path: str,
        sheet_index: int,
    ) -> tuple[dict[str, object], dict[str, object]]:
        eid_params = RagicQueryParams(naming="EID", limit=1)
        eid_result = await client.get_records(tab_path, sheet_index, eid_params)
        if not eid_result.records:
            return {}, {}

        name_params = RagicQueryParams(naming="", limit=1)
        name_result = await client.get_records(
            tab_path, sheet_index, name_params
        )
        if not name_result.records:
            return {}, {}

        return eid_result.records[0].fields, name_result.records[0].fields

    @staticmethod
    def _build_schema(
        account: str,
        tab_path: str,
        sheet_index: int,
        eid_fields: dict[str, object],
        name_fields: dict[str, object],
        table_name: str = "",
        description: str = "",
        module: str = "",
    ) -> RagicTableSchema:
        eid_keys = [k for k in eid_fields if not k.startswith("_")]
        name_keys = [k for k in name_fields if not k.startswith("_")]

        field_map: dict[str, str] = {}
        for eid_key, name_key in zip(eid_keys, name_keys):
            field_map[eid_key] = name_key

        fields: dict[str, RagicFieldSchema] = {}
        for field_id, field_name in field_map.items():
            raw_value = eid_fields.get(field_id)
            field_type = _infer_field_type(raw_value)

            options: list[str] = []
            if isinstance(raw_value, list):
                options = [str(v) for v in raw_value]

            fields[field_id] = RagicFieldSchema(
                name=field_name,
                field_type=field_type,
            )
            if options:
                fields[field_id].options = options

        table_key = f"{tab_path}/{sheet_index}"

        return RagicTableSchema(
            account=account,
            table_key=table_key,
            table_name=table_name or table_key,
            tab_path=tab_path,
            sheet_index=sheet_index,
            description=description,
            module=module,
            version="auto-sync",
            fields=fields,
        )


def _infer_field_type(value: object) -> str:
    if isinstance(value, bool):
        return "checkbox"
    if isinstance(value, int):
        return "number"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "select"
    if isinstance(value, dict):
        return "subtable"
    if isinstance(value, str):
        if "/" in value and len(value) <= 10:
            parts = value.split("/")
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                return "date"
        return "text"
    return "text"
