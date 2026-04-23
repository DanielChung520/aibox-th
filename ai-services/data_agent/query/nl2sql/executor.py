"""
NL→SQL Pipeline - DuckDB Executor + ArangoDB AQL Executor

Executes validated SQL queries against DuckDB with parquet data sources,
or validated AQL queries against ArangoDB for Ragic data sources.
SELECT-only enforcement at execution level as final safety net.

# Last Update: 2026-04-16 17:50:29
# Author: Daniel Chung
# Version: 3.1.0
"""

import codecs
import json
import logging
import os
import re
import time

import httpx

from data_agent.query.nl2sql.exceptions import ExecutionError
from data_agent.query.nl2sql.models import PipelineConfig, SQLResult

logger = logging.getLogger(__name__)


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


async def _fetch_ragic_field_mappings(
    table_ids: list[str], config: PipelineConfig
) -> dict[str, str]:
    """Fetch field_id → field_name mappings for Ragic tables from ArangoDB."""
    mappings: dict[str, str] = {}
    if not table_ids:
        return mappings
    async with httpx.AsyncClient(timeout=15.0) as client:
        for table_id in table_ids:
            resp = await client.post(
                f"{config.arango_url}/_db/{config.arango_db}/_api/cursor",
                json={
                    "query": (
                        "FOR f IN da_field_info_ragic "
                        "FILTER f.table_id == @table_id "
                        "RETURN {field_id: f.field_id, field_name: f.field_name}"
                    ),
                    "bindVars": {"table_id": table_id},
                },
                auth=(config.arango_user, config.arango_password),
            )
            resp.raise_for_status()
            for f in resp.json().get("result", []):
                fid = str(f.get("field_id", ""))
                fname = str(f.get("field_name", ""))
                if fid and fname:
                    mappings[fid] = fname
    return mappings


async def execute_aql(
    aql: str, config: PipelineConfig,
    field_mappings: dict[str, str] | None = None,
) -> SQLResult:
    """Execute an AQL query against ArangoDB (for Ragic data source).

    Args:
        aql: Validated ArangoDB AQL query.
        config: Pipeline configuration with ArangoDB credentials.
        field_mappings: Optional dict of field_id → field_name for remapping.
                        If not provided, fetched automatically from da_field_info_ragic.

    Returns:
        SQLResult with rows, columns, count, and timing.

    Raises:
        ExecutionError: When ArangoDB execution fails.
    """
    aql_upper = aql.strip().upper()
    if not aql_upper.startswith("FOR") and not aql_upper.startswith("RETURN"):
        raise ExecutionError("Only AQL FOR/RETURN queries are allowed")

    start_ms = time.time() * 1000

    if field_mappings is None:
        table_id_match = re.search(r"d\.table_id\s*==\s*['\"]([^'\"]+)['\"]", aql)
        if table_id_match:
            field_mappings = await _fetch_ragic_field_mappings(
                [table_id_match.group(1)], config
            )
        else:
            field_mappings = {}

    # Build name→ID mapping from all schema field mappings.
    # The "fname not in reverse_map" guard prevents duplicate field names
    # from overwriting earlier (correct) entries in the dict.
    # We no longer restrict to sample_keys because a field may exist in the
    # schema but be NULL/empty in the first sample row (e.g. 1018437 "品項名稱").
    reverse_map: dict[str, str] = {}
    for fid, fname in field_mappings.items():
        if fname not in reverse_map:
            reverse_map[fname] = fid

    aql_rewritten = aql
    for field_name, field_id in reverse_map.items():
        aql_rewritten = aql_rewritten.replace(f"d['{field_name}']", f'd["{field_id}"]')

    def _fix_return_object(m: re.Match) -> str:
        inner = m.group(1)
        if inner.startswith("{"):
            inner = inner[1:]
        if inner.endswith("}"):
            inner = inner[:-1]

        def _esc_key(km: re.Match) -> str:
            decoded = codecs.decode(json.dumps(km.group(1))[1:-1], "unicode_escape")
            return '"' + decoded + '": '

        fixed_inner = re.sub(r"'([^']+)':\s*", _esc_key, inner)
        return "RETURN {" + fixed_inner + "}"

    aql_rewritten = re.sub(r"RETURN\s*\{([^}]+)\}", _fix_return_object, aql_rewritten)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{config.arango_url}/_db/{config.arango_db}/_api/cursor",
                json={"query": aql_rewritten},
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
                    mapped_key = field_mappings.get(k, k)
                    row[mapped_key] = v
                    all_keys.add(mapped_key)
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


async def fetch_table_schema(
    table_name: str,
    gateway_url: str = "",
) -> list[dict[str, str]]:
    """Fetch column schema from server DuckDB cache via information_schema.

    Returns list of dicts: [{"column_name": "...", "data_type": "..."}, ...]
    """
    if not gateway_url:
        gateway_url = os.getenv("GATEWAY_URL", "http://localhost:6500")

    sql = (
        f"SELECT column_name, data_type FROM information_schema.columns "
        f"WHERE table_name = '{table_name}' ORDER BY ordinal_position;"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{gateway_url}/api/v1/da/query/sql",
                json={"sql": sql},
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 0:
            logger.warning("Failed to fetch schema for %s: %s", table_name, data.get("message"))
            return []

        return list(data.get("data", {}).get("results", []))

    except Exception as e:
        logger.warning("Schema fetch error for %s: %s", table_name, e)
        return []


async def execute_on_server_cache(
    sql: str,
    gateway_url: str = "",
) -> SQLResult:
    """Execute SQL on the Rust API Gateway's Server DuckDB Cache.

    Calls POST /api/v1/da/query/sql which runs against the file-backed
    DuckDB at ./data/table_cache.duckdb.
    """
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        raise ExecutionError("Only SELECT queries are allowed")

    if not gateway_url:
        gateway_url = os.getenv("GATEWAY_URL", "http://localhost:6500")

    start_ms = time.time() * 1000

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{gateway_url}/api/v1/da/query/sql",
                json={"sql": sql},
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 0:
            raise ExecutionError(
                f"Server cache query failed: {data.get('message', 'unknown error')}"
            )

        result_data = data.get("data", {})
        rows: list[dict[str, object]] = result_data.get("results", [])
        columns: list[str] = result_data.get("columns", [])
        elapsed_ms = time.time() * 1000 - start_ms

        return SQLResult(
            sql=sql,
            rows=rows,
            columns=columns,
            row_count=len(rows),
            execution_time_ms=round(elapsed_ms, 2),
        )

    except httpx.HTTPStatusError as e:
        raise ExecutionError(
            f"Server cache HTTP error: {e.response.status_code}"
        )
    except httpx.ConnectError:
        raise ExecutionError("Server cache connection error: All connection attempts failed")
    except httpx.HTTPError as e:
        raise ExecutionError(f"Server cache connection error: {str(e)}")
