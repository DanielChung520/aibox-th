"""
@file        query_engine.py
@description Ragic query execution engine — auto-pagination, field-name
             resolution via ArangoDB da_tables, and result formatting.
@lastUpdate  2026-04-13
@author      Daniel Chung
@version     2.0.0
"""

import logging
import math
import os
import time

import httpx

from data_agent.ragic.client import RagicAPIClient
from data_agent.ragic.models import (
    FormattedRecord,
    QueryEngineResult,
    RagicQueryParams,
    RagicRecord,
)

logger = logging.getLogger(__name__)

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")


class RagicQueryEngine:
    def __init__(self) -> None:
        pass

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
            aql = (
                "FOR d IN da_tables "
                "FILTER d._key == @table_key "
                "RETURN d.fields"
            )
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                    json={"query": aql, "bindVars": {"table_key": table_key}},
                    auth=(ARANGO_USER, ARANGO_PASSWORD),
                )
                resp.raise_for_status()

            labels: dict[str, str] = {}
            result = resp.json().get("result", [])
            if result and isinstance(result[0], dict):
                fields = result[0]
                if isinstance(fields, dict):
                    for fid, fdata in fields.items():
                        if isinstance(fdata, dict):
                            fname = fdata.get("name", "")
                            if fname and fid:
                                labels[fid] = fname

            logger.debug("Loaded %d field labels for %s", len(labels), table_key)
            return labels
        except Exception as exc:
            logger.debug("Failed to load field labels for %s: %s", table_key, exc)
            return {}

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
