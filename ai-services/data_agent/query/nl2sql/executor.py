"""
NL→SQL Pipeline - DuckDB Executor

Executes validated SQL queries against DuckDB with parquet data sources.
SELECT-only enforcement at execution level as final safety net.

# Last Update: 2026-04-02 20:30:00
# Author: Daniel Chung
# Version: 2.0.0
"""

import time
import httpx

from data_agent.query.nl2sql.exceptions import ExecutionError
from data_agent.query.nl2sql.models import PipelineConfig, SQLResult


async def execute_sql(
    sql: str, config: PipelineConfig
) -> SQLResult:
    """Execute a validated SQL query using DuckDB.

    Uses DuckDB's httpfs extension for S3/parquet access.

    Args:
        sql: Validated DuckDB-compatible SQL.
        config: Pipeline configuration with S3 credentials.

    Returns:
        SQLResult with rows, columns, count, and timing.

    Raises:
        ExecutionError: When DuckDB execution fails.
    """
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        raise ExecutionError("Only SELECT queries are allowed")

    try:
        import duckdb
    except ImportError as e:
        raise ExecutionError(f"DuckDB not installed: {str(e)}")

    start_ms = time.time() * 1000

    try:
        conn = duckdb.connect(":memory:")

        conn.execute("INSTALL httpfs; LOAD httpfs;")
        if config.s3_endpoint:
            endpoint = config.s3_endpoint.replace("http://", "").replace("https://", "")
            conn.execute(f"SET s3_endpoint='{endpoint}';")
            conn.execute("SET s3_use_ssl=false;")
        if config.s3_access_key:
            conn.execute(
                f"SET s3_access_key_id='{config.s3_access_key}';"
            )
        if config.s3_secret_key:
            conn.execute(
                f"SET s3_secret_access_key='{config.s3_secret_key}';"
            )
        conn.execute("SET s3_url_style='path';")

        result = conn.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows_raw = result.fetchall()

        rows: list[dict[str, object]] = [
            dict(zip(columns, row)) for row in rows_raw
        ]

        elapsed_ms = time.time() * 1000 - start_ms

        return SQLResult(
            sql=sql,
            rows=rows,
            columns=columns,
            row_count=len(rows),
            execution_time_ms=round(elapsed_ms, 2),
        )

    except Exception as e:
        raise ExecutionError(f"DuckDB execution failed: {str(e)}")


async def execute_aql(
    aql: str, config: PipelineConfig
) -> SQLResult:
    """Execute an AQL query against ArangoDB (for Ragic data source).

    Args:
        aql: Validated ArangoDB AQL query.
        config: Pipeline configuration with ArangoDB credentials.

    Returns:
        SQLResult with rows, columns, count, and timing.

    Raises:
        ExecutionError: When ArangoDB execution fails.
    """
    aql_upper = aql.strip().upper()
    if not aql_upper.startswith("FOR") and not aql_upper.startswith("RETURN"):
        raise ExecutionError("Only AQL FOR/RETURN queries are allowed")

    start_ms = time.time() * 1000

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{config.arango_url}/_db/{config.arango_db}/_api/cursor",
                json={"query": aql},
                auth=(config.arango_user, config.arango_password),
            )
            response.raise_for_status()
            data = response.json()
            rows_raw: list[dict[str, object]] = data.get("result", [])

        rows: list[dict[str, object]] = []
        all_keys: set[str] = set()
        for raw in rows_raw:
            row: dict[str, object] = {}
            for k, v in raw.items():
                if k not in ("_key", "_id", "_rev", "_ragicId", "table_id", "created_at", "updated_at"):
                    row[k] = v
                    all_keys.add(k)
            if row:
                rows.append(row)

        columns = sorted(all_keys)
        elapsed_ms = time.time() * 1000 - start_ms

        return SQLResult(
            sql=aql,
            rows=rows,
            columns=columns,
            row_count=len(rows),
            execution_time_ms=round(elapsed_ms, 2),
        )

    except httpx.HTTPStatusError as e:
        raise ExecutionError(f"ArangoDB HTTP error: {e.response.status_code} - {e.response.text[:200]}")
    except Exception as e:
        raise ExecutionError(f"ArangoDB execution failed: {str(e)}")
