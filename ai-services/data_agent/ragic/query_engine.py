"""
@file        query_engine.py
@description Ragic query execution engine — auto-pagination, field-name
             resolution via Schema, and result formatting.
@lastUpdate  2026-04-11 13:17:39
@author      Daniel Chung
@version     1.0.0
"""

import logging
import math
import time

from data_agent.ragic.client import RagicAPIClient
from data_agent.ragic.models import (
    FormattedRecord,
    QueryEngineResult,
    RagicQueryParams,
    RagicRecord,
    RagicTableSchema,
)
from data_agent.ragic.schema_store import RagicSchemaStore

logger = logging.getLogger(__name__)


class RagicQueryEngine:
    def __init__(
        self,
        schema_store: RagicSchemaStore | None = None,
    ) -> None:
        self._schemas = schema_store or RagicSchemaStore()

    async def execute(
        self,
        client: RagicAPIClient,
        tab_path: str,
        sheet_index: int,
        params: RagicQueryParams,
        account: str = "",
        auto_paginate: bool = False,
    ) -> QueryEngineResult:
        start = time.monotonic()
        table_key = f"{tab_path}/{sheet_index}"

        field_labels = await self._load_field_labels(account, table_key)

        if auto_paginate:
            raw_result = await client.get_all_records(
                tab_path=tab_path,
                sheet_index=sheet_index,
                where=params.where or None,
                page_size=params.limit,
            )
        else:
            raw_result = await client.get_records(
                tab_path=tab_path,
                sheet_index=sheet_index,
                params=params,
            )

        formatted = self._format_records(raw_result.records, field_labels)

        total_count = raw_result.record_count
        page_size = params.limit if params.limit > 0 else 1000
        current_page = (params.offset // page_size) + 1 if not auto_paginate else 1
        total_pages = max(1, math.ceil(total_count / page_size)) if total_count > 0 else 1

        elapsed_ms = (time.monotonic() - start) * 1000

        return QueryEngineResult(
            records=formatted,
            record_count=total_count,
            total_pages=total_pages,
            current_page=current_page,
            page_size=page_size,
            has_more=raw_result.pagination.has_more,
            execution_time_ms=round(elapsed_ms, 2),
            table_key=table_key,
            connection=account or client.account,
        )

    async def _load_field_labels(
        self, account: str, table_key: str
    ) -> dict[str, str]:
        if not account:
            return {}

        try:
            hits = await self._schemas.search(
                query=table_key,
                account=account,
                top_k=1,
                score_threshold=0.2,
            )
            if not hits:
                return {}

            payload = hits[0].get("payload", {})
            if not isinstance(payload, dict):
                return {}

            schema = RagicSchemaStore.payload_to_schema(payload)
            return self._extract_field_labels(schema)
        except Exception as exc:
            logger.debug("Failed to load field labels for %s: %s", table_key, exc)
            return {}

    @staticmethod
    def _extract_field_labels(schema: RagicTableSchema) -> dict[str, str]:
        labels: dict[str, str] = {}
        for field_id, field_schema in schema.fields.items():
            labels[field_id] = field_schema.name
        return labels

    @staticmethod
    def _format_records(
        records: list[RagicRecord],
        field_labels: dict[str, str],
    ) -> list[FormattedRecord]:
        formatted: list[FormattedRecord] = []
        for record in records:
            record_labels: dict[str, str] = {}
            for fid in record.fields:
                if fid in field_labels:
                    record_labels[fid] = field_labels[fid]

            formatted.append(
                FormattedRecord(
                    ragic_id=record.ragic_id,
                    fields=record.fields,
                    field_labels=record_labels,
                )
            )
        return formatted
