import hashlib
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Path as PathParam
from pydantic import BaseModel

from data_agent.config_reader import get_param

logger = logging.getLogger(__name__)

router = APIRouter()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")

QDRANT_COLLECTION = "da_intents"
ARANGO_TABLES = "da_tables"
ARANGO_EXPRESSIONS = "da_expressions"
ARANGO_INTENTS = "da_intents"


class DaIntentsSyncResponse(BaseModel):
    synced_count: int
    collection: str
    status: str


def _deterministic_point_id(seed: str) -> int:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return int(digest[:15], 16)


def _get_field_names(fields: list[dict]) -> list[str]:
    names: list[str] = []
    for f in fields:
        if not isinstance(f, dict):
            continue
        if f.get("filterable") is not True:
            continue
        fname = str(f.get("name", ""))
        if fname:
            names.append(fname)
        for alias in f.get("aliases", []):
            if isinstance(alias, str) and alias not in names:
                names.append(alias)
    return names


def _build_embed_text(doc: dict) -> str:
    """Build rich embedding text for da_intents 3-layer structure."""
    parts: list[str] = []

    parts.append(doc.get("name", ""))
    parts.append(doc.get("description", ""))

    for ex in doc.get("nl_examples", []):
        if isinstance(ex, str) and ex not in parts:
            parts.append(ex)

    parts.append(doc.get("action", ""))
    parts.append(doc.get("domain", ""))

    for field_name in doc.get("field_names", []):
        if field_name not in parts:
            parts.append(field_name)

    return " ".join(parts)


async def _get_embedding(text: str) -> list[float]:
    model = await get_param("da.embedding_model")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/v1/embeddings",
            json={"model": model, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings", [])
        if embeddings and len(embeddings) > 0:
            return list(embeddings[0])
        return []


async def _fetch_all(table_name: str) -> list[dict]:
    aql = f"FOR d IN {table_name} RETURN d"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": aql, "batchSize": 1000},
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        if resp.status_code in (200, 201):
            return resp.json().get("result", [])
    return []


async def _ensure_collection(dim: int) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        check = await client.get(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}")
        if check.status_code == 200:
            return
        await client.put(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}",
            json={
                "vectors": {"size": dim, "distance": "Cosine"},
                "optimizers_config": {"indexing_threshold": 10000},
            },
        )


async def _ensure_arangodb_collection() -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        check = await client.get(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/collection/{ARANGO_INTENTS}"
        )
        if check.status_code == 200:
            return
        await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/collection",
            json={"name": ARANGO_INTENTS, "type": 2},
        )


@router.post("/{scope}/sync-da-intents", response_model=DaIntentsSyncResponse)
async def sync_da_intents(
    scope: str = PathParam(..., description="Agent scope"),
) -> DaIntentsSyncResponse:
    if scope != "data_agent":
        raise HTTPException(status_code=400, detail="Only data_agent scope supported")

    try:
        tables = await _fetch_all(ARANGO_TABLES)
        expressions = await _fetch_all(ARANGO_EXPRESSIONS)

        expr_map: dict[str, dict] = {}
        for expr in expressions:
            tk = str(expr.get("table_key", ""))
            if tk:
                expr_map[tk] = expr

        await _ensure_arangodb_collection()

        embedding_dim = int(await get_param("da.embedding_dimension"))
        await _ensure_collection(embedding_dim)

        intent_docs: list[dict] = []
        points: list[dict] = []
        synced = 0

        for table in tables:
            table_key = str(table.get("_key", ""))
            if not table_key:
                continue

            expr = expr_map.get(table_key, {})

            field_names = _get_field_names(table.get("fields", []))

            doc = {
                "_key": f"{table_key}_intent",
                "intent_id": f"{table_key}_intent",
                "agent_scope": "data_agent",
                "account": table.get("identifiers", {}).get("source", "ragic"),
                "name": table.get("display_name", ""),
                "description": table.get("description", ""),
                "status": table.get("status", "enabled"),

                "nl_examples": expr.get("nl_examples", []),
                "aliases": expr.get("aliases", []),
                "field_names": field_names,
                "domain": table.get("domain", ""),
                "action": "query",

                "table_key": table_key,
                "query_type": _infer_query_type(table, expr),
                "tool_schema": _build_tool_schema(table),

                "capabilities": table.get("capabilities", {}),
                "field_count": len(table.get("fields", [])),
                "updated_at": table.get("updated_at", ""),
            }

            embed_text = _build_embed_text(doc)
            if not embed_text:
                continue

            embedding = await _get_embedding(embed_text)
            if not embedding:
                logger.warning("Empty embedding for %s, skipping", table_key)
                continue

            point_id = _deterministic_point_id(f"da_intent_{table_key}")

            points.append({
                "id": point_id,
                "vector": embedding,
                "payload": doc,
            })
            intent_docs.append(doc)
            synced += 1

        if intent_docs:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.put(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/{ARANGO_INTENTS}?overwriteMode=replace",
                    json=intent_docs,
                )

        if points:
            async with httpx.AsyncClient(timeout=300.0) as client:
                await client.post(
                    f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/delete",
                    json={"filter": {}},
                )
                batch_size = 100
                for i in range(0, len(points), batch_size):
                    batch = points[i : i + batch_size]
                    await client.put(
                        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points",
                        json={"points": batch},
                    )

        logger.info("Synced %d da_intents to Qdrant '%s'", synced, QDRANT_COLLECTION)
        return DaIntentsSyncResponse(
            synced_count=synced, collection=QDRANT_COLLECTION, status="ok"
        )

    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Sync failed: {e!s}")


def _infer_query_type(table: dict, expr: dict) -> str:
    caps = table.get("capabilities", {})
    if caps.get("aggregate"):
        return "aggregate"
    if caps.get("time_series"):
        return "time_series"
    nl_examples = expr.get("nl_examples", [])
    for ex in nl_examples:
        if isinstance(ex, str):
            ex_lower = ex.lower()
            if any(kw in ex_lower for kw in ["統計", "平均", "總和", "count", "sum"]):
                return "aggregate"
    return "simple_filter"


def _build_tool_schema(table: dict) -> dict:
    fields = table.get("fields", {})
    if not isinstance(fields, dict):
        return {"type": "object", "properties": {}}

    properties: dict = {}
    for fid, fdata in fields.items():
        if not isinstance(fdata, dict):
            continue
        ftype = fdata.get("type", "text")
        schema_type = "string"
        if ftype == "number":
            schema_type = "number"
        elif ftype == "date":
            schema_type = "string"
        properties[fid] = {
            "type": schema_type,
            "name": fdata.get("name", ""),
            "aggregatable": fdata.get("aggregatable", False),
        }

    return {
        "type": "object",
        "properties": {
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_id": {
                            "type": "string",
                            "enum": list(properties.keys()),
                        },
                        "operator": {
                            "type": "string",
                            "enum": ["eq", "ne", "gt", "gte", "lt", "lte", "like", "regex"],
                        },
                        "value": {"type": "string"},
                    },
                },
            },
            "order_field": {"type": "string", "enum": list(properties.keys())},
            "order_direction": {"type": "string", "enum": ["ASC", "DESC"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
        },
    }
