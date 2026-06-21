"""
da_expressions → Qdrant sync router.

Reads da_expressions from ArangoDB (enhanced with 3-layer fields),
builds rich embedding text, and upserts to Qdrant da_intents collection.

每筆 da_expression 代表一個意圖，payload 包含三層：
- 感知層: nl_examples, action, domain
- 對策層: table_key, query_type, tool_schema
- 學習層: golden_sql, difficulty_level

# Last Update: 2026-04-13
# Author: Daniel Chung
# Version: 3.0.0
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Path as PathParam
from pydantic import BaseModel

from data_agent.config_reader import get_param

logger = logging.getLogger(__name__)

router = APIRouter()

OLLAMA_BASE_URL = os.getenv("MLX_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11400"))
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")

QDRANT_COLLECTION = "da_intents"
ARANGO_EXPRESSIONS = "da_expressions"
ARANGO_TABLES = "da_tables"


class DaSyncResponse(BaseModel):
    synced_count: int
    collection: str
    status: str


def _deterministic_point_id(seed: str) -> int:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return int(digest[:15], 16)


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


async def _fetch_tables() -> dict[str, dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": "FOR d IN da_tables RETURN d", "batchSize": 1000},
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
    if resp.status_code in (200, 201):
        result = resp.json().get("result", [])
        return {str(t.get("_key", "")): t for t in result}
    return {}


async def _fetch_expressions() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": f"FOR d IN {ARANGO_EXPRESSIONS} FILTER d.status == 'enabled' RETURN d", "batchSize": 1000},
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
    if resp.status_code in (200, 201):
        return resp.json().get("result", [])
    return []


def _build_tool_schema(table: dict[str, Any]) -> dict[str, Any]:
    filterable_fields: list[dict] = []
    for f in table.get("fields", []):
        if isinstance(f, dict) and f.get("filterable") is True:
            filterable_fields.append({
                "field_id": str(f.get("field_id", "")),
                "name": f.get("name", ""),
                "type": f.get("type", "text"),
                "aggregatable": f.get("aggregatable", False),
            })

    field_ids = [f["field_id"] for f in filterable_fields if f["field_id"]]
    return {
        "type": "object",
        "fields": filterable_fields,
        "properties": {
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "string", "enum": field_ids},
                        "operator": {"type": "string", "enum": ["eq", "ne", "gt", "gte", "lt", "lte", "like", "regex"]},
                        "value": {"type": "string"},
                    },
                },
            },
            "order_field": {"type": "string", "enum": field_ids},
            "order_direction": {"type": "string", "enum": ["ASC", "DESC"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
        },
    }


def _build_embed_text(expr: dict[str, Any], table: dict[str, Any] | None = None) -> str:
    parts: list[str] = []
    name = str(expr.get("name", ""))
    if name:
        parts.append(name)
    desc = str(expr.get("description", ""))
    if desc:
        parts.append(desc)
    action = str(expr.get("action", ""))
    if action:
        parts.append(action)
    domain = str(expr.get("domain", ""))
    if domain:
        parts.append(domain)
    for ex in expr.get("nl_examples", []):
        if isinstance(ex, str) and ex not in parts:
            parts.append(ex)
    if table:
        for alias in expr.get("aliases", []):
            if isinstance(alias, str) and alias not in parts:
                parts.append(alias)
        for f in table.get("fields", []):
            if isinstance(f, dict) and f.get("filterable") is True:
                fname = str(f.get("name", ""))
                if fname and fname not in parts:
                    parts.append(fname)
    return " ".join(parts)


async def _ensure_qdrant_collection(dim: int) -> None:
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


@router.post("/{scope}/sync-da-expressions", response_model=DaSyncResponse)
async def sync_da_expressions(
    scope: str = PathParam(..., description="Agent scope"),
) -> DaSyncResponse:
    if scope != "data_agent":
        raise HTTPException(status_code=400, detail="Only data_agent scope supported")

    try:
        expressions = await _fetch_expressions()
        if not expressions:
            return DaSyncResponse(synced_count=0, collection=QDRANT_COLLECTION, status="no_expressions")

        table_map = await _fetch_tables()
        embedding_dim = int(await get_param("da.embedding_dimension"))
        await _ensure_qdrant_collection(embedding_dim)

        points: list[dict[str, Any]] = []
        synced = 0

        for expr in expressions:
            table_key = str(expr.get("table_key", ""))
            table = table_map.get(table_key)
            expr_id = str(expr.get("_key", ""))

            embed_text = _build_embed_text(expr, table)
            if not embed_text:
                continue

            embedding = await _get_embedding(embed_text)
            if not embedding:
                logger.warning("Empty embedding for %s, skipping", expr_id)
                continue

            point_id = _deterministic_point_id(f"da_expr_{expr_id}")

            # 三層 payload
            payload: dict[str, Any] = {
                # 感知層
                "nl_examples": expr.get("nl_examples", []),
                "action": expr.get("action", "query"),
                "domain": expr.get("domain", "base"),
                # 對策層
                "table_key": table_key,
                "query_type": expr.get("query_type", "simple_filter"),
                "tool_schema": _build_tool_schema(table) if table else {},
                "capabilities": table.get("capabilities", {}) if table else {},
                # 學習層
                "golden_sql": expr.get("golden_sql", ""),
                "difficulty_level": expr.get("difficulty_level", "easy"),
                "expected_output": expr.get("expected_output", {}),
                # 中介層
                "is_template": expr.get("is_template", True),
                # 共用欄位
                "_key": expr_id,
                "intent_id": expr_id,  # 保持與 _key 一致，確保向量化匹配時能正確解析
                "name": expr.get("name", ""),
                "description": expr.get("description", ""),
                "aliases": expr.get("aliases", []),
                "status": expr.get("status", "enabled"),
                "embedding_text": embed_text,
            }

            if table:
                payload["display_name"] = table.get("display_name", "")

            points.append({
                "id": point_id,
                "vector": embedding,
                "payload": payload,
            })
            synced += 1

        if points:
            async with httpx.AsyncClient(timeout=300.0) as client:
                batch_size = 100
                for i in range(0, len(points), batch_size):
                    batch = points[i : i + batch_size]
                    await client.put(
                        f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points",
                        json={"points": batch},
                    )

        logger.info("Synced %d da_expressions to Qdrant '%s'", synced, QDRANT_COLLECTION)
        return DaSyncResponse(synced_count=synced, collection=QDRANT_COLLECTION, status="ok")

    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Sync failed: {e!s}")


@router.post("/{scope}/upsert-expression/{key}")
async def upsert_expression(
    scope: str, key: str,
) -> dict[str, object]:
    if scope != "data_agent":
        raise HTTPException(status_code=400, detail="Only data_agent scope supported")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={
                "query": "FOR e IN da_expressions FILTER e._key == @key LIMIT 1 RETURN e",
                "bindVars": {"key": key},
            },
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        if resp.status_code not in (200, 201) or not resp.json().get("result"):
            raise HTTPException(status_code=404, detail=f"Expression {key} not found")
        expr = resp.json()["result"][0]

        tables_resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": "FOR t IN da_tables RETURN t", "batchSize": 1000},
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        table_map = {}
        if tables_resp.status_code in (200, 201):
            for t in tables_resp.json().get("result", []):
                table_map[str(t.get("_key", ""))] = t

    table_key = str(expr.get("table_key", ""))
    table = table_map.get(table_key)
    embed_text = _build_embed_text(expr, table)
    embedding = await _get_embedding(embed_text)
    if not embedding:
        raise HTTPException(status_code=500, detail="Failed to generate embedding")

    point_id = _deterministic_point_id(f"da_expr_{key}")
    payload: dict[str, Any] = {
        "nl_examples": expr.get("nl_examples", []),
        "action": expr.get("action", "query"),
        "domain": expr.get("domain", "base"),
        "table_key": table_key,
        "query_type": expr.get("query_type", "simple_filter"),
        "tool_schema": _build_tool_schema(table) if table else {},
        "capabilities": table.get("capabilities", {}) if table else {},
        "golden_sql": expr.get("golden_sql", ""),
        "difficulty_level": expr.get("difficulty_level", "easy"),
        "expected_output": expr.get("expected_output", {}),
        "is_template": expr.get("is_template", True),
        "_key": key,
        "name": expr.get("name", ""),
        "description": expr.get("description", ""),
        "aliases": expr.get("aliases", []),
        "status": expr.get("status", "enabled"),
        "embedding_text": embed_text,
    }
    if table:
        payload["display_name"] = table.get("display_name", "")

    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.put(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points",
            json={"points": [{"id": point_id, "vector": embedding, "payload": payload}]},
        )

    logger.info("Upserted expression %s to Qdrant", key)
    return {"status": "ok", "key": key}


@router.delete("/{scope}/delete-expression/{key}")
async def delete_expression(scope: str, key: str) -> dict[str, object]:
    if scope != "data_agent":
        raise HTTPException(status_code=400, detail="Only data_agent scope supported")

    point_id = _deterministic_point_id(f"da_expr_{key}")
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(
            f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/delete",
            json={"points": [point_id]},
        )

    logger.info("Deleted expression %s from Qdrant", key)
    return {"status": "ok", "key": key}
