"""
Query Router - NL→AQL and NL→SQL query endpoints.

Provides:
- NL→AQL: Natural language to ArangoDB AQL conversion + execution
- NL→SQL: 3-tier hybrid NL→SQL pipeline (template/small_llm/large_llm)
  over Parquet data lake via DuckDB

# Last Update: 2026-04-16 17:50:29
# Author: Daniel Chung
# Version: 2.3.0
"""

import logging
import os
import time
from typing import Optional, cast

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from shared.security import verify_internal_token
from shared.logging import get_structured_logger, log_nl_sql_request

from data_agent.query.nl2sql import run_nl2sql_pipeline
from data_agent.query.nl2sql.models import (
    GenerationStrategy,
    IntentMatch,
    NLQueryRequest,
    PipelineConfig,
    QueryPlan,
    QueryPlanFilter,
    StructuredQueryRequest,
)
from data_agent.query.nl2sql.plan_generator import generate_query_plan
from data_agent.query.nl2sql.structured_orchestrator import run_structured_pipeline

router = APIRouter(dependencies=[Depends(verify_internal_token)])

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")

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


class QueryPlanRequest(BaseModel):
    natural_language: str
    table_key: Optional[str] = None
    top_k: int = 3


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
    logger = get_structured_logger("data_agent", "nl2sql")
    timer = log_nl_sql_request(
        logger,
        query=request.natural_language,
        intent_type="nl2sql",
    )
    try:
        result = await run_nl2sql_pipeline(query=request.natural_language)
        timer.stop(
            success=True,
            strategy=result.strategy.value if hasattr(result, "strategy") else "unknown",
            rows_returned=len(result.data) if hasattr(result, "data") else 0,
        )
        return result.model_dump()
    except Exception as e:
        timer.stop(success=False, error=str(e))
        logger.error("nl_sql_error", error=str(e))
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

        table_id = str(table_info.get("table_id", table_name))

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
            s3_path = str(table_info.get("s3_path", ""))
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
    field_map = {str(f["field_id"]): str(f["field_name"]) for f in fields if f.get("field_id")}
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
                row[str(name)] = value
            rows.append(row)
        return total, rows


def _query_parquet_preview(
    s3_path: str, offset: int, limit: int
) -> tuple[int, list[dict[str, object]]]:
    import duckdb

    config = PipelineConfig(
        s3_endpoint=os.getenv("S3_ENDPOINT", "http://localhost:8334"),
        s3_access_key=os.getenv("S3_ACCESS_KEY", ""),
        s3_secret_key=os.getenv("S3_SECRET_KEY", ""),
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


# ---------------------------------------------------------------------------
# Intent Plan Endpoint - three-layer routing (rule-based / small / large LLM)
# ---------------------------------------------------------------------------

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "da_intents"
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.45"))


async def _get_embedding(text: str) -> list[float]:
    model = os.getenv("OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:latest")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": model, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings", [])
        if embeddings:
            return list(embeddings[0])
        return []


async def _search_da_intents(
    query: str, table_key: str | None, top_k: int,
) -> dict[str, object] | None:
    embedding = await _get_embedding(query)
    if not embedding:
        return None

    search_payload: dict[str, object] = {
        "vector": embedding,
        "limit": top_k,
        "with_payload": True,
    }
    if table_key:
        search_payload["filter"] = {
            "must": [{"key": "table_key", "match": {"value": table_key}}]
        }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/search",
            json=search_payload,
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])

    for r in results:
        score = float(r.get("score", 0.0))
        if score >= MATCH_THRESHOLD:
            return {"payload": r.get("payload", {}), "score": score}
    return None


AGGREGATION_KEYWORDS = ["統計", "數量", "總計", "平均", "總和", "合計", "最大", "最小", "count", "sum", "avg", "max", "min", "排名", "前十", "top"]


def _route_strategy(query_type: str, difficulty_level: str, nl_query: str = "") -> tuple[GenerationStrategy, str]:
    if query_type == "simple_filter":
        if nl_query and any(kw in nl_query.lower() for kw in [k.lower() for k in AGGREGATION_KEYWORDS]):
            return GenerationStrategy.SMALL_LLM, "small LLM (nl含聚合關鍵字)"
        return GenerationStrategy.TEMPLATE, "rule-based (tool_schema解析)"
    if query_type == "aggregate":
        if difficulty_level == "easy":
            return GenerationStrategy.TEMPLATE, "rule-based (easy aggregate)"
        if difficulty_level == "medium":
            return GenerationStrategy.SMALL_LLM, "small LLM"
        return GenerationStrategy.LARGE_LLM, "large LLM"
    return GenerationStrategy.LARGE_LLM, "large LLM fallback"


def _extract_filters_from_nl(
    nl_query: str,
    tool_schema: dict[str, object],
    field_names: list[str],
    field_id_to_name: dict[str, str],
) -> list[QueryPlanFilter]:
    field_enums: list[str] = []
    props_obj = tool_schema.get("properties", {})
    if isinstance(props_obj, dict):
        filters_prop = props_obj.get("filters", {})
        if isinstance(filters_prop, dict):
            items = filters_prop.get("items", {})
            if isinstance(items, dict):
                item_props = items.get("properties", {})
                if isinstance(item_props, dict):
                    field_enum = item_props.get("field_id", {})
                    if isinstance(field_enum, dict):
                        enum_values = field_enum.get("enum", [])
                        if isinstance(enum_values, list):
                            field_enums = [str(value) for value in enum_values]

    query_lower = nl_query.lower()
    filters: list[QueryPlanFilter] = []

    for field_id in field_enums:
        field_name = field_id_to_name.get(field_id, "").lower()
        if not field_name or field_name not in query_lower:
            continue

        operator = "eq"
        value = ""
        raw_ops = [
            ("gt", ["超過", "大於", "高於", "多於", "大于", "高于"]),
            ("lt", ["低於", "小於", "少於", "低于", "少于"]),
            ("like", ["包含", "含有", "內含", "含", "内含"]),
        ]
        for op, keywords in raw_ops:
            if any(kw in query_lower for kw in keywords):
                operator = op
                break

        parts = query_lower.split(field_name)
        if len(parts) > 1:
            after = parts[1].strip()
            eq_kw = ["為", "是", "等於", "等于"]
            for kw in eq_kw:
                if after.startswith(kw):
                    after = after[len(kw):].strip()
                    break
            stop_chars = ["，", ",", "。", ".", " ", "的", "有", "和", "與"]
            for ch in stop_chars:
                idx = after.find(ch)
                if idx >= 0:
                    value = after[:idx].strip()
                    break
            if not value and after:
                value = after.strip()

        filters.append(QueryPlanFilter(field=field_id, operator=operator, value=value))

    return filters


async def _fetch_field_names(table_key: str) -> dict[str, str]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={
                "query": "FOR t IN da_tables FILTER t._key == @key LIMIT 1 RETURN t",
                "bindVars": {"key": table_key},
            },
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        if resp.status_code in (200, 201):
            result = resp.json().get("result", [])
            if result:
                fields = result[0].get("fields", [])
                return {str(f.get("field_id", "")): str(f.get("name", "")) for f in fields if f.get("field_id")}
    return {}


def _truncate_tool_schema(tool_schema: dict[str, object], max_fields: int = 30) -> dict[str, object]:
    """Truncate tool_schema to limit number of fields for simpler queries."""
    if not tool_schema:
        return tool_schema
    props = tool_schema.get("properties", {})
    if not isinstance(props, dict):
        return tool_schema
    filters = props.get("filters", {})
    if not isinstance(filters, dict):
        return tool_schema
    items = filters.get("items", {})
    if not isinstance(items, dict):
        return tool_schema
    items_props = items.get("properties", {})
    if not isinstance(items_props, dict):
        return tool_schema
    field_id_config = items_props.get("field_id", {})
    if not isinstance(field_id_config, dict):
        return tool_schema
    field_enum = field_id_config.get("enum", [])
    if not isinstance(field_enum, list):
        return tool_schema
    if len(field_enum) > max_fields:
        logger = logging.getLogger(__name__)
        logger.info("Truncating tool_schema from %d to %d fields", len(field_enum), max_fields)
        new_enum = list(field_enum[:max_fields])
        new_items_props = dict(items_props)
        new_items_props["field_id"] = dict(new_items_props.get("field_id", {}))
        new_items_props["field_id"]["enum"] = new_enum
        new_items = dict(items)
        new_items["properties"] = new_items_props
        new_filters = dict(filters)
        new_filters["items"] = new_items
        new_props = dict(props)
        new_props["filters"] = new_filters
        new_tool_schema = dict(tool_schema)
        new_tool_schema["properties"] = new_props
        return new_tool_schema
    return tool_schema


async def _build_rule_plan(
    nl_query: str, intent_data: dict[str, object],
) -> QueryPlan:
    tool_schema_obj = intent_data.get("tool_schema", {})
    if not isinstance(tool_schema_obj, dict):
        tool_schema_obj = {}
    tool_schema = _truncate_tool_schema(cast(dict[str, object], tool_schema_obj), max_fields=30)
    table_key = str(intent_data.get("table_key", ""))
    field_id_to_name = await _fetch_field_names(table_key)
    field_names = list(field_id_to_name.values())
    filters = _extract_filters_from_nl(nl_query, tool_schema, field_names, field_id_to_name)

    return QueryPlan(
        intent_type=str(intent_data.get("action", "query")),
        primary_table=table_key,
        tables=[table_key] if table_key else [],
        filters=filters,
        limit=100,
    )


async def _get_default_model() -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])
            if models:
                return models[0].get("name", "gemma4:31b")
        except Exception:
            pass
    return "gemma4:31b"


async def _build_llm_plan(
    nl_query: str, intent_data: dict[str, object],
    strategy: GenerationStrategy,
) -> QueryPlan:
    from data_agent.query.nl2sql.models import SchemaContext, TableSchema, FieldSchema
    table_key = str(intent_data.get("table_key", ""))

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": "FOR t IN da_tables FILTER t._key == @key LIMIT 1 RETURN t",
                  "bindVars": {"key": table_key}},
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        if resp.status_code not in (200, 201):
            return QueryPlan(primary_table=table_key, tables=[table_key] if table_key else [])
        result = resp.json().get("result", [])
        if not result:
            return QueryPlan(primary_table=table_key, tables=[table_key] if table_key else [])
        table_doc = result[0]

    table_schemas = [TableSchema(
        table_name=table_key,
        description=str(table_doc.get("description", "")),
        module=str(table_doc.get("domain", "")),
    )]
    field_schemas: list[FieldSchema] = []
    for f in table_doc.get("fields", []):
        if isinstance(f, dict):
            field_schemas.append(FieldSchema(
                table_name=table_key,
                field_name=str(f.get("name", "")),
                field_id=str(f.get("field_id", "")),
                data_type=str(f.get("type", "text")),
            ))

    schema = SchemaContext(tables=table_schemas, fields=field_schemas, relations=[], join_graph={})

    default_model = await _get_default_model()
    intent_match = IntentMatch(
        intent_id=str(intent_data.get("_key", "")),
        score=0.0,
        generation_strategy=strategy,
        tables=[table_key] if table_key else [],
        description=str(intent_data.get("description", "")),
        intent_type=str(intent_data.get("action", "query")),
    )

    config = PipelineConfig(
        ollama_base_url=OLLAMA_BASE_URL,
        small_model=default_model,
        large_model=default_model,
        qdrant_collection=QDRANT_COLLECTION,
    )
    try:
        import asyncio
        async with asyncio.timeout(45.0):
            plan = await generate_query_plan(nl_query, intent_match, schema, config)
            return plan
    except TimeoutError:
        logger.warning("LLM plan generation timed out after 45s for intent %s", intent_data.get("_key", ""))
        return QueryPlan(
            primary_table=table_key,
            tables=[table_key] if table_key else [],
            intent_type=str(intent_data.get("action", "query")),
            filters=[],
            limit=100,
        )
    except Exception as e:
        logger.warning("LLM plan generation failed: %s", str(e))
        return QueryPlan(
            primary_table=table_key,
            tables=[table_key] if table_key else [],
            intent_type=str(intent_data.get("action", "query")),
            filters=[],
            limit=100,
        )


@router.post("/plan")
async def query_plan(request: QueryPlanRequest) -> dict[str, object]:
    matched = await _search_da_intents(
        request.natural_language, request.table_key, request.top_k,
    )
    if not matched:
        return {
            "success": False,
            "query": request.natural_language,
            "error": "No intent matched above threshold",
            "strategy": "none",
            "query_plan": None,
        }

    payload = matched.get("payload", {})
    intent_data = cast(dict[str, object], payload if isinstance(payload, dict) else {})
    raw_score = matched.get("score", 0.0)
    score = float(raw_score if isinstance(raw_score, int | float | str) else 0.0)
    query_type = str(intent_data.get("query_type", "simple_filter"))
    difficulty = str(intent_data.get("difficulty_level", "easy"))

    strategy, strategy_desc = _route_strategy(query_type, difficulty, request.natural_language)

    if strategy == GenerationStrategy.TEMPLATE:
        query_plan = await _build_rule_plan(request.natural_language, intent_data)
    else:
        query_plan = await _build_llm_plan(
            request.natural_language, intent_data, strategy,
        )

    return {
        "success": True,
        "query": request.natural_language,
        "matched_intent": {
            "intent_id": str(intent_data.get("_key", "")),
            "name": str(intent_data.get("name", "")),
            "table_key": str(intent_data.get("table_key", "")),
            "query_type": query_type,
            "difficulty_level": difficulty,
            "score": round(score, 3),
        },
        "strategy": strategy_desc,
        "generation_strategy": strategy.value,
        "query_plan": query_plan.model_dump(),
    }


@router.post("/structured")
async def structured_query(request: StructuredQueryRequest) -> dict[str, object]:
    result = await run_structured_pipeline(request)
    return result.model_dump()


@router.post("/nl")
async def nl_query_with_hints(request: NLQueryRequest) -> dict[str, object]:
    config = PipelineConfig(
        ollama_base_url=OLLAMA_BASE_URL,
    )
    pipeline_result = await run_nl2sql_pipeline(
        request.natural_language, config,
    )
    return pipeline_result.model_dump()


@router.get("/health")
def query_health() -> dict[str, str]:
    return {"status": "ok", "sub_service": "query", "version": "2.3.0"}
