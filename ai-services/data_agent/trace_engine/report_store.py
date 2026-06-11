"""
@file        report_store.py
@description CRUD for trace reports in ArangoDB (trace_reports collection).
@lastUpdate  2026-05-17
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from data_agent.trace_engine.models import Report, TraceResult, TraceScenario, TraceSummary

logger = logging.getLogger(__name__)

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")
_COLLECTION = "trace_reports"


class ReportStore:
    """ArangoDB-backed persistence for trace reports."""

    def __init__(self) -> None:
        self._arango_url = ARANGO_URL
        self._arango_db = ARANGO_DB
        self._auth = (ARANGO_USER, ARANGO_PASSWORD)

    async def _ensure_collection(self) -> None:
        """Create trace_reports collection if it doesn't exist."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._arango_url}/_db/{self._arango_db}/_api/collection/{_COLLECTION}",
                auth=self._auth,
            )
            if resp.status_code == 200:
                return
            resp = await client.post(
                f"{self._arango_url}/_db/{self._arango_db}/_api/collection",
                json={"name": _COLLECTION},
                auth=self._auth,
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "Failed to create collection %s: %s", _COLLECTION, resp.text
                )

    async def save_report(self, report: Report) -> str:
        """Save a report to ArangoDB. Returns the document _key."""
        await self._ensure_collection()
        now = datetime.now(timezone.utc).isoformat()
        doc: dict[str, object] = {
            "name": report.name,
            "scenario": report.scenario.value,
            "entry_table": report.entry_table,
            "entry_batch": report.entry_batch,
            "trace_result": report.trace_result.model_dump() if report.trace_result else None,
            "summary": report.summary.model_dump() if report.summary else {},
            "tags": report.tags,
            "created_by": report.created_by,
            "created_at": now,
            "updated_at": now,
        }
        if report.id:
            doc["_key"] = report.id

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._arango_url}/_db/{self._arango_db}/_api/document/{_COLLECTION}?returnNew=true",
                json=doc,
                auth=self._auth,
            )
            resp.raise_for_status()
            result = resp.json()
            return str(result.get("_key", ""))

    async def get_report(self, report_id: str) -> Optional[Report]:
        """Get a report by its _key."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._arango_url}/_db/{self._arango_db}/_api/document/{_COLLECTION}/{report_id}",
                auth=self._auth,
            )
            if resp.status_code == 404:
                return None
            if resp.status_code != 200:
                logger.warning("Failed to get report %s: %s", report_id, resp.text)
                return None
            doc = resp.json()
            return self._doc_to_report(doc)

    def _doc_to_report(self, doc: dict[str, Any]) -> Report:
        """Convert ArangoDB document to Report model."""
        trace_result = None
        if doc.get("trace_result"):
            try:
                trace_result = TraceResult(**doc["trace_result"])
            except Exception:
                pass

        summary_data = doc.get("summary", {})
        summary = TraceSummary(**summary_data) if summary_data else TraceSummary()

        return Report(
            id=str(doc.get("_key", "")),
            name=str(doc.get("name", "")),
            scenario=TraceScenario(doc.get("scenario", "incoming_batch")),
            entry_table=str(doc.get("entry_table", "")),
            entry_batch=str(doc.get("entry_batch", "")),
            trace_result=trace_result,
            summary=summary,
            tags=list(doc.get("tags", [])),
            created_by=str(doc.get("created_by", "")),
            created_at=str(doc.get("created_at", "")),
            updated_at=str(doc.get("updated_at", "")),
        )

    async def list_reports(
        self,
        scenario: Optional[str] = None,
        tags: Optional[list[str]] = None,
        page: int = 1,
        limit: int = 20,
    ) -> list[Report]:
        """List reports with optional filtering and pagination."""
        page = max(1, page)
        limit = max(1, min(100, limit))
        binds: dict[str, object] = {"offset": (page - 1) * limit, "limit": limit}
        filters: list[str] = []

        if scenario:
            filters.append("FILTER d.scenario == @scenario")
            binds["scenario"] = scenario
        if tags:
            filters.append("FILTER d.tags ANY IN @tags")
            binds["tags"] = tags

        where = " ".join(filters)
        aql = (
            f"FOR d IN {_COLLECTION} "
            f"{where} "
            "SORT d.created_at DESC "
            "LIMIT @offset, @limit "
            "RETURN d"
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._arango_url}/_db/{self._arango_db}/_api/cursor",
                json={"query": aql, "bindVars": binds},
                auth=self._auth,
            )
            if resp.status_code not in (200, 201):
                logger.warning("Failed to list reports: %s", resp.text)
                return []
            results = resp.json().get("result", [])
            return [self._doc_to_report(d) for d in results]

    async def delete_report(self, report_id: str) -> bool:
        """Delete a report by _key. Returns True if deleted."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"{self._arango_url}/_db/{self._arango_db}/_api/document/{_COLLECTION}/{report_id}",
                auth=self._auth,
            )
            return resp.status_code in (200, 202)
