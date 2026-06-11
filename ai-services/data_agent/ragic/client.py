"""
@file        client.py
@description Ragic API client — read-only, zero local sync.
             Handles auth, rate-limit guard, pagination, and error mapping.
@lastUpdate  2026-04-11 12:52:25
@author      Daniel Chung
@version     1.0.0
"""

import asyncio
import logging
import time

import httpx

from data_agent.ragic.exceptions import (
    RagicAuthError,
    RagicError,
    RagicForbiddenError,
    RagicNotFoundError,
    RagicRateLimitError,
    RagicTimeoutError,
)
from data_agent.ragic.models import (
    RagicConnectionConfig,
    RagicPagination,
    RagicQueryParams,
    RagicQueryResult,
    RagicRecord,
    RagicWhereClause,
)

logger = logging.getLogger(__name__)

# Ragic enforces max 5 req/s per account; we stay at 4 to be safe.
_MIN_REQUEST_INTERVAL: float = 0.25


class RagicAPIClient:
    """Read-only HTTP client for Ragic Cloud API.

    Each instance is bound to one RagicConnectionConfig (account + api_key).
    All queries hit the remote Ragic server directly — no local caching of
    record data.
    """

    def __init__(self, config: RagicConnectionConfig) -> None:
        self._config = config
        self._last_request_ts: float = 0.0

    @property
    def account(self) -> str:
        return self._config.account

    @property
    def base_url(self) -> str:
        return self._config.base_url

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Basic {self._config.api_key}"}

    async def _throttle(self) -> None:
        """Enforce minimum interval between requests (rate-limit guard)."""
        elapsed = time.monotonic() - self._last_request_ts
        if elapsed < _MIN_REQUEST_INTERVAL:
            await asyncio.sleep(_MIN_REQUEST_INTERVAL - elapsed)

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Map Ragic HTTP errors to typed exceptions."""
        status = response.status_code
        if status < 400:
            return
        body = response.text[:500]
        if status == 401:
            raise RagicAuthError(f"HTTP 401: {body}")
        if status == 403:
            raise RagicForbiddenError(f"HTTP 403: {body}")
        if status == 404:
            raise RagicNotFoundError(f"HTTP 404: {body}")
        if status == 429:
            raise RagicRateLimitError(f"HTTP 429: {body}")
        if status == 504:
            raise RagicTimeoutError(f"HTTP 504: {body}")
        raise RagicError(f"HTTP {status}: {body}", code="RAGIC_SERVER_ERROR")

    def _build_query_string(self, params: RagicQueryParams) -> dict[str, str]:
        """Convert RagicQueryParams into Ragic-compatible query-string dict."""
        qs: dict[str, str] = {"api": "", "naming": params.naming}

        if params.where:
            for idx, clause in enumerate(params.where):
                key = "where" if idx == 0 else f"where_{idx + 1}"
                qs[key] = f"{clause.field_id},{clause.operator.value},{clause.value}"

        if params.offset > 0 or params.limit != 1000:
            qs["limit"] = f"{params.offset},{params.limit}"

        if params.order_field:
            qs["order"] = f"{params.order_field},{params.order_direction.value}"

        if params.subtables is not None:
            qs["subtables"] = str(params.subtables)

        if params.info:
            qs["info"] = "true"

        return qs

    def _parse_records(self, raw: dict[str, object]) -> list[RagicRecord]:
        """Parse Ragic JSON response into a list of RagicRecord."""
        records: list[RagicRecord] = []
        for ragic_id, fields in raw.items():
            if not isinstance(fields, dict):
                continue
            records.append(
                RagicRecord(ragic_id=str(ragic_id), fields=fields)
            )
        return records

    async def get_records(
        self,
        tab_path: str,
        sheet_index: int,
        params: RagicQueryParams | None = None,
    ) -> RagicQueryResult:
        """Fetch records from a Ragic sheet.

        Args:
            tab_path: Tab path segment, e.g. "configuration-file".
            sheet_index: Sheet number within the tab.
            params: Optional query parameters (where, limit, order, etc.).

        Returns:
            RagicQueryResult with records and pagination metadata.
        """
        if params is None:
            params = RagicQueryParams()

        url = f"{self.base_url}/{self._config.account}/{tab_path}/{sheet_index}"
        qs = self._build_query_string(params)

        start = time.monotonic()
        await self._throttle()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url, headers=self._auth_headers(), params=qs
                )
        except httpx.TimeoutException as exc:
            raise RagicTimeoutError(f"Timeout reaching {url}") from exc
        except httpx.ConnectError as exc:
            raise RagicError(
                f"Cannot connect to {url}: {exc}",
                code="RAGIC_CONNECTION_ERROR",
            ) from exc

        self._last_request_ts = time.monotonic()
        self._raise_for_status(response)

        raw: dict[str, object] = response.json()
        records = self._parse_records(raw)
        elapsed_ms = (time.monotonic() - start) * 1000

        table_key = f"{tab_path}/{sheet_index}"

        return RagicQueryResult(
            records=records,
            record_count=len(records),
            pagination=RagicPagination(
                offset=params.offset,
                limit=params.limit,
                returned_count=len(records),
                has_more=len(records) >= params.limit,
            ),
            execution_time_ms=round(elapsed_ms, 2),
            connection=self._config.account,
            table_key=table_key,
            raw_url=str(response.url),
        )

    async def get_record(
        self,
        tab_path: str,
        sheet_index: int,
        record_id: int,
    ) -> RagicRecord | None:
        """Fetch a single record by its Ragic row ID."""
        url = (
            f"{self.base_url}/{self._config.account}"
            f"/{tab_path}/{sheet_index}/{record_id}"
        )
        qs: dict[str, str] = {"api": "", "naming": "EID"}

        await self._throttle()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url, headers=self._auth_headers(), params=qs
                )
        except httpx.TimeoutException as exc:
            raise RagicTimeoutError(f"Timeout reaching {url}") from exc

        self._last_request_ts = time.monotonic()

        if response.status_code == 404:
            return None
        self._raise_for_status(response)

        raw: dict[str, object] = response.json()
        records = self._parse_records(raw)
        return records[0] if records else None

    async def get_all_records(
        self,
        tab_path: str,
        sheet_index: int,
        where: list[RagicWhereClause] | None = None,
        page_size: int = 1000,
    ) -> RagicQueryResult:
        """Auto-paginate through all matching records (max 1000 per page).

        Merges pages into a single RagicQueryResult.
        """
        all_records: list[RagicRecord] = []
        offset = 0
        start = time.monotonic()

        while True:
            params = RagicQueryParams(
                where=where or [],
                limit=page_size,
                offset=offset,
            )
            page = await self.get_records(tab_path, sheet_index, params)
            all_records.extend(page.records)

            if not page.pagination.has_more:
                break
            offset += page_size

        elapsed_ms = (time.monotonic() - start) * 1000
        table_key = f"{tab_path}/{sheet_index}"

        return RagicQueryResult(
            records=all_records,
            record_count=len(all_records),
            pagination=RagicPagination(
                offset=0,
                limit=len(all_records),
                returned_count=len(all_records),
                has_more=False,
            ),
            execution_time_ms=round(elapsed_ms, 2),
            connection=self._config.account,
            table_key=table_key,
        )

    async def check_health(self) -> dict[str, object]:
        """Verify connectivity by listing the account's tabs."""
        url = f"{self.base_url}/{self._config.account}"
        qs: dict[str, str] = {"api": ""}

        await self._throttle()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    url, headers=self._auth_headers(), params=qs
                )
        except httpx.TimeoutException:
            return {"ok": False, "error": "timeout"}
        except httpx.ConnectError as exc:
            return {"ok": False, "error": str(exc)}

        self._last_request_ts = time.monotonic()

        if response.status_code >= 400:
            return {
                "ok": False,
                "error": f"HTTP {response.status_code}",
                "body": response.text[:200],
            }

        return {
            "ok": True,
            "account": self._config.account,
            "server": self._config.server_prefix,
        }
