"""
@file        step_executor.py
@description Execute a single step in a multi-step Ragic query pipeline.
             Wraps RagicQueryEngine with timeout, error capture, and
             dependent-step FK filtering.
@lastUpdate  2026-04-11 17:26:16
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import asyncio
import logging
import time

from data_agent.ragic.client import RagicAPIClient
from data_agent.ragic.config_loader import RagicConfigLoader
from data_agent.ragic.exceptions import RagicError
from data_agent.ragic.models import (
    RagicOperator,
    RagicQueryParams,
    RagicWhereClause,
)
from data_agent.ragic.models_phase9 import StepResult
from data_agent.ragic.query_engine import RagicQueryEngine

logger = logging.getLogger(__name__)

_MAX_FK_VALUES = 10


class RagicStepExecutor:
    """Execute a single Ragic API query step with timeout and error capture."""

    def __init__(
        self,
        query_engine: RagicQueryEngine,
        config_loader: RagicConfigLoader,
    ) -> None:
        self._query_engine = query_engine
        self._config_loader = config_loader

    async def execute(
        self,
        step_index: int,
        table_name: str,
        table_key: str,
        query_params: RagicQueryParams,
        account: str,
        timeout_s: float = 15.0,
    ) -> StepResult:
        """Execute a single step query against Ragic API.

        Args:
            step_index: Index of this step in the pipeline.
            table_name: Human-readable table name.
            table_key: Ragic table key (e.g. "tab_path/sheet_index").
            query_params: Query parameters for the Ragic API call.
            account: Ragic account name for connection lookup.
            timeout_s: Max seconds before timeout.

        Returns:
            StepResult with records on success or error message on failure.
        """
        start = time.monotonic()
        params_dict = query_params.model_dump()

        conn = await self._config_loader.get_connection(account)
        if conn is None:
            elapsed = (time.monotonic() - start) * 1000
            return StepResult(
                step_index=step_index,
                table_key=table_key,
                table_name=table_name,
                query_params=params_dict,
                records=[],
                record_count=0,
                execution_time_ms=round(elapsed, 2),
                error=f"No connection found for account '{account}'",
            )

        client = RagicAPIClient(conn)
        tab_path, sheet_index = self._parse_table_key(table_key)

        try:
            result = await asyncio.wait_for(
                self._query_engine.execute(
                    client=client,
                    tab_path=tab_path,
                    sheet_index=sheet_index,
                    params=query_params,
                    account=account,
                ),
                timeout=timeout_s,
            )
            elapsed = (time.monotonic() - start) * 1000
            records: list[dict[str, object]] = [
                {"ragic_id": r.ragic_id, **r.fields}
                for r in result.records
            ]
            return StepResult(
                step_index=step_index,
                table_key=table_key,
                table_name=table_name,
                query_params=params_dict,
                records=records,
                record_count=len(records),
                execution_time_ms=round(elapsed, 2),
                error=None,
            )
        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - start) * 1000
            return StepResult(
                step_index=step_index,
                table_key=table_key,
                table_name=table_name,
                query_params=params_dict,
                records=[],
                record_count=0,
                execution_time_ms=round(elapsed, 2),
                error=f"Step timeout after {timeout_s}s",
            )
        except RagicError as exc:
            elapsed = (time.monotonic() - start) * 1000
            return StepResult(
                step_index=step_index,
                table_key=table_key,
                table_name=table_name,
                query_params=params_dict,
                records=[],
                record_count=0,
                execution_time_ms=round(elapsed, 2),
                error=str(exc),
            )

    async def execute_dependent(
        self,
        step_index: int,
        table_name: str,
        table_key: str,
        fk_field_id: str,
        fk_values: list[str],
        account: str,
        timeout_s: float = 15.0,
    ) -> StepResult:
        """Execute a dependent step using FK values from a prior step.

        Builds WHERE clauses from FK values (max 10) and delegates to execute().

        Args:
            step_index: Index of this step in the pipeline.
            table_name: Human-readable table name.
            table_key: Ragic table key.
            fk_field_id: Field ID to filter on.
            fk_values: Foreign key values from the parent step.
            account: Ragic account name.
            timeout_s: Max seconds before timeout.

        Returns:
            StepResult with filtered records.
        """
        capped = fk_values[:_MAX_FK_VALUES]
        where_clauses = [
            RagicWhereClause(
                field_id=fk_field_id,
                operator=RagicOperator.EQ,
                value=v,
            )
            for v in capped
        ]
        params = RagicQueryParams(where=where_clauses, limit=1000)
        return await self.execute(
            step_index=step_index,
            table_name=table_name,
            table_key=table_key,
            query_params=params,
            account=account,
            timeout_s=timeout_s,
        )

    @staticmethod
    def _parse_table_key(table_key: str) -> tuple[str, int]:
        # "database/1" -> ("database", 1)
        parts = table_key.rsplit("/", 1)
        if len(parts) == 2:
            try:
                return parts[0], int(parts[1])
            except ValueError:
                pass
        return table_key, 0
