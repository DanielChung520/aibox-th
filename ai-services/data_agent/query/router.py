"""
Query Router - NL→AQL and NL→SQL query endpoints.

Provides:
- NL→AQL: Natural language to ArangoDB AQL conversion + execution
- NL→SQL: 3-tier hybrid NL→SQL pipeline (template/small_llm/large_llm)
  over Parquet data lake via DuckDB

# Last Update: 2026-03-26 08:58:10
# Author: Daniel Chung
# Version: 2.2.0
"""

import logging
import os
import time
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_agent.query.nl2sql import run_nl2sql_pipeline
from data_agent.query.nl2sql.models import PipelineConfig

router = APIRouter()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")

SYSTEM_PROMPT = """You are a database expert. Convert the user's natural language \
query into an ArangoDB AQL query.

Rules:
1. Only query collections: users, roles, system_params, functions, role_functions, \
da_intents, da_table_info, da_field_info, da_table_relation
2. Use FOR...FILTER...RETURN pattern
3. Always use parameterized values with @ symbol
4. Return ONLY valid AQL, no explanation
5. If query is not about data, say "NO_QUERY"

Examples:
- "show all users" -> FOR u IN users RETURN u
- "get admin user" -> FOR u IN users FILTER u.username == @username RETURN u
- "list enabled users" -> FOR u IN users FILTER u.status == 'enabled' RETURN u
"""


logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    natural_language: str
    collection: Optional[str] = None
    context: Optional[dict[str, object]] = None


class ExplainRequest(BaseModel):
    aql: str


class NL2SqlRequest(BaseModel):
    natural_language: str


async def generate_aql(natural_language: str) -> str:
    """Generate AQL from natural language via Ollama."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": DEFAULT_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": natural_language},
                ],
                "stream": False,
                "temperature": 0.3,
            },
        )
        response.raise_for_status()
        data = response.json()
        content: str = data.get("message", {}).get("content", "").strip()
        return content


async def execute_aql_query(aql_query: str) -> tuple[list[dict[str, object]], float]:
    """Execute AQL query against ArangoDB."""
    start = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": aql_query},
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        response.raise_for_status()
        data = response.json()
        results: list[dict[str, object]] = data.get("result", [])
    execution_time = time.time() - start
    return results, execution_time


@router.post("/query")
async def query(request: QueryRequest) -> dict[str, object]:
    """Convert natural language to AQL and execute."""
    try:
        aql = await generate_aql(request.natural_language)

        if "NO_QUERY" in aql.upper():
            return {
                "natural_language": request.natural_language,
                "aql": "",
                "results": [],
                "message": "Query could not be generated from input",
            }

        if not aql.upper().strip().startswith("FOR"):
            return {
                "natural_language": request.natural_language,
                "aql": aql,
                "results": [],
                "message": "Invalid AQL generated",
            }

        results, execution_time = await execute_aql_query(aql)

        return {
            "natural_language": request.natural_language,
            "aql": aql,
            "results": results,
            "execution_time": execution_time,
        }

    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Service unavailable: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain")
async def explain_aql(request: ExplainRequest) -> dict[str, object]:
    """Get AQL explain plan."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/explain",
                json={"query": request.aql},
                auth=(ARANGO_USER, ARANGO_PASSWORD),
            )
            response.raise_for_status()
            result: dict[str, object] = response.json()
            return result
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"ArangoDB unavailable: {str(e)}")


@router.post("/nl2sql")
async def nl2sql(request: NL2SqlRequest) -> dict[str, object]:
    """NL→SQL pipeline: natural language → DuckDB SQL over Parquet data lake."""
    try:
        result = await run_nl2sql_pipeline(query=request.natural_language)
        return result.model_dump()
    except Exception as e:
        logger.error("NL→SQL endpoint error: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_name}/preview")
async def preview_table_data(
    table_name: str,
    offset: int = 0,
    limit: int = 20,
) -> dict[str, object]:
    try:
        table_info: dict[str, object] = {}
        data_source = "sap"

        async with httpx.AsyncClient(timeout=15.0) as client:
            for collection, source in [("da_table_info", "sap"), ("da_table_info_ragic", "ragic")]:
                info_resp = await client.post(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                    json={
                        "query": f"FOR t IN {collection} FILTER t.table_id == @table_name LIMIT 1 RETURN t",
                        "bindVars": {"table_name": table_name},
                    },
                    auth=(ARANGO_USER, ARANGO_PASSWORD),
                )
                info_resp.raise_for_status()
                info_data = info_resp.json()
                if info_data.get("result"):
                    table_info = info_data["result"][0]
                    data_source = source
                    break

        if not table_info:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        table_id = table_info.get("table_id", table_name)

        field_col = "da_field_info" if data_source == "sap" else "da_field_info_ragic"
        async with httpx.AsyncClient(timeout=15.0) as client:
            fields_resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={
                    "query": f"FOR f IN {field_col} FILTER f.table_id == @table_id SORT f.field_name ASC RETURN f",
                    "bindVars": {"table_id": table_id},
                },
                auth=(ARANGO_USER, ARANGO_PASSWORD),
            )
            fields_resp.raise_for_status()
            fields = fields_resp.json().get("result", [])

        if data_source == "sap":
            s3_path = table_info.get("s3_path", "")
            if not s3_path:
                raise HTTPException(status_code=404, detail=f"No s3_path configured for table '{table_name}'")
            total, rows = _query_parquet_preview(s3_path, offset, limit)
        else:
            total, rows = await _query_arangodb_preview(table_id, offset, limit, fields)

        return {
            "table_name": table_name,
            "table_id": table_id,
            "table_info": table_info,
            "fields": fields,
            "rows": rows,
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    except HTTPException:
        raise
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=404, detail="Table not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _query_arangodb_preview(
    table_id: str,
    offset: int,
    limit: int,
    fields: list[dict[str, object]],
) -> tuple[int, list[dict[str, object]]]:
    field_map = {str(f["field_id"]): f["field_name"] for f in fields if f.get("field_id")}
    async with httpx.AsyncClient(timeout=15.0) as client:
        count_resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={
                "query": "RETURN LENGTH(FOR d IN da_table_data_ragic FILTER d.table_id == @table_id RETURN d)",
                "bindVars": {"table_id": table_id},
            },
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        count_resp.raise_for_status()
        total = count_resp.json().get("result", [0])[0] or 0

        rows_resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={
                "query": "FOR d IN da_table_data_ragic FILTER d.table_id == @table_id SORT d._key ASC LIMIT @offset, @limit RETURN d",
                "bindVars": {"table_id": table_id, "limit": limit, "offset": offset},
            },
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        rows_resp.raise_for_status()
        rows_raw = rows_resp.json().get("result", [])
        rows = []
        for raw in rows_raw:
            row: dict[str, object] = {}
            for key, value in raw.items():
                if key in ("_key", "_id", "_rev", "_ragicId", "table_id", "created_at", "updated_at"):
                    continue
                name = field_map.get(key, key)
                row[name] = value
            rows.append(row)
        return total, rows


def _query_parquet_preview(
    s3_path: str, offset: int, limit: int
) -> tuple[int, list[dict[str, object]]]:
    import duckdb

    config = PipelineConfig(
        s3_endpoint=os.getenv("S3_ENDPOINT", "http://localhost:8334"),
        s3_access_key=os.getenv("S3_ACCESS_KEY", "admin"),
        s3_secret_key=os.getenv("S3_SECRET_KEY", "admin123"),
    )

    parquet_glob = f"{s3_path}*.parquet"

    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL httpfs; LOAD httpfs;")
    if config.s3_endpoint:
        endpoint = config.s3_endpoint.replace("http://", "").replace("https://", "")
        conn.execute(f"SET s3_endpoint='{endpoint}';")
        conn.execute("SET s3_use_ssl=false;")
    if config.s3_access_key:
        conn.execute(f"SET s3_access_key_id='{config.s3_access_key}';")
    if config.s3_secret_key:
        conn.execute(f"SET s3_secret_access_key='{config.s3_secret_key}';")
    conn.execute("SET s3_url_style='path';")

    count_result = conn.execute(
        f"SELECT COUNT(*) FROM read_parquet('{parquet_glob}')"
    ).fetchone()
    total = count_result[0] if count_result else 0

    rows_result = conn.execute(
        f"SELECT * FROM read_parquet('{parquet_glob}') LIMIT {limit} OFFSET {offset}"
    )
    columns = [desc[0] for desc in rows_result.description]
    rows: list[dict[str, object]] = [
        dict(zip(columns, row)) for row in rows_result.fetchall()
    ]

    conn.close()
    return total, rows


@router.get("/health")
def query_health() -> dict[str, str]:
    return {"status": "ok", "sub_service": "query", "version": "2.1.0"}
