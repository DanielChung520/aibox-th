"""
Intent RAG Router - Multi-scope Qdrant-based intent matching, embedding sync, Ollama models.

Supports parameterized {scope} routes so that both orchestrator and data_agent
(and future agent scopes) share the same embedding/matching pipeline while
keeping separate Qdrant collections.

ArangoDB source: unified `intent_catalog` collection, filtered by `agent_scope`.
Qdrant target: per-scope collection (see SCOPE_QDRANT_MAP).

# Last Update: 2026-04-13 06:08:56
# Author: Daniel Chung
# Version: 3.3.0
"""

import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path as PathParam
from pydantic import BaseModel
from shared.security import verify_internal_token

from data_agent.config_reader import get_param

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_internal_token)])

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")
MATCH_THRESHOLD_DEFAULT = float(os.getenv("MATCH_THRESHOLD", "0.45"))

SCOPE_QDRANT_MAP: dict[str, str] = {
    "data_agent": "da_intents",
    "orchestrator": "orchestrator_intents",
}

VALID_SCOPES = set(SCOPE_QDRANT_MAP.keys())


def _resolve_qdrant_collection(scope: str) -> str:
    """Resolve scope to Qdrant collection name, raise 400 if unknown."""
    if scope not in SCOPE_QDRANT_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scope '{scope}'. Valid scopes: {sorted(VALID_SCOPES)}",
        )
    return SCOPE_QDRANT_MAP[scope]


class IntentMatchRequest(BaseModel):
    """Intent match request body."""

    query: str
    top_k: int = 3


class IntentMatchResult(BaseModel):
    """Single intent match result."""

    intent_id: str
    score: float
    intent_data: dict[str, object]


class IntentMatchResponse(BaseModel):
    """Intent match response."""

    query: str
    matches: list[IntentMatchResult]
    best_match: Optional[IntentMatchResult] = None


class EmbedSyncResponse(BaseModel):
    """Embedding sync response."""

    synced_count: int
    collection: str
    status: str


async def get_embedding(text: str) -> list[float]:
    """Get embedding vector from Ollama using configured model."""
    embedding_model = await get_param("da.embedding_model")
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/v1/embeddings",
            json={"model": embedding_model, "input": text},
        )
        response.raise_for_status()
        data = response.json()
        embeddings = data.get("embeddings", [])
        if embeddings and len(embeddings) > 0:
            return list(embeddings[0])
        return []


async def fetch_intents_from_arango(scope: str) -> list[dict[str, object]]:
    """Fetch intents from unified intent_catalog filtered by agent_scope.

    Falls back to legacy collection (da_intents / orch_intents) if
    intent_catalog yields no results, for backward compatibility during
    migration.
    """
    # Primary: unified intent_catalog
    aql = "FOR doc IN intent_catalog FILTER doc.agent_scope == @scope RETURN doc"
    bind_vars: dict[str, str] = {"scope": scope}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": aql, "bindVars": bind_vars},
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        if response.status_code in (200, 201):
            data = response.json()
            result: list[dict[str, object]] = data.get("result", [])
            if result:
                return result

    # Fallback: legacy collection (removed after Phase 5 migration)
    legacy_map: dict[str, str] = {
        "data_agent": "da_intents",
        "orchestrator": "orch_intents",
    }
    legacy_col = legacy_map.get(scope)
    if legacy_col:
        fallback_aql = f"FOR doc IN {legacy_col} RETURN doc"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": fallback_aql},
                auth=(ARANGO_USER, ARANGO_PASSWORD),
            )
            if response.status_code in (200, 201):
                data = response.json()
                fallback_result: list[dict[str, object]] = data.get("result", [])
                if fallback_result:
                    logger.info(
                        "Scope '%s': using legacy collection '%s' (%d intents)",
                        scope,
                        legacy_col,
                        len(fallback_result),
                    )
                    return fallback_result

    return []


@router.get("/{scope}/models")
async def list_ollama_models(
    scope: str = PathParam(..., description="Agent scope"),
) -> dict[str, object]:
    """List available Ollama models (scope-aware for future per-scope model config)."""
    _resolve_qdrant_collection(scope)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            data = response.json()
            models_data = data.get("models", [])
            model_names: list[str] = []
            for m in models_data:
                name = m.get("name", "")
                if isinstance(name, str) and name:
                    model_names.append(name)
            result: dict[str, object] = {
                "models": model_names,
                "count": len(model_names),
                "scope": scope,
            }
            return result
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama service unavailable: {str(e)}",
        )


@router.post("/{scope}/embed-sync", response_model=EmbedSyncResponse)
async def embed_sync(
    scope: str = PathParam(..., description="Agent scope"),
) -> EmbedSyncResponse:
    """Sync intents from ArangoDB to Qdrant for given scope.

    data_agent reads from da_intents collection.
    orchestrator reads from intent_catalog.
    """
    qdrant_collection = _resolve_qdrant_collection(scope)

    try:
        # Determine source collection based on scope
        if scope == "data_agent":
            aql = "FOR d IN da_intents RETURN d"
        else:
            aql = f"FOR d IN intent_catalog FILTER d.agent_scope == '{scope}' RETURN d"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": aql},
                auth=(ARANGO_USER, ARANGO_PASSWORD),
            )
            if response.status_code in (200, 201):
                intents = response.json().get("result", [])
            else:
                intents = []

        if not intents:
            return EmbedSyncResponse(
                synced_count=0,
                collection=qdrant_collection,
                status="no_intents_found",
            )

        embedding_dim = int(await get_param("da.embedding_dimension"))
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.put(
                f"{QDRANT_URL}/collections/{qdrant_collection}",
                json={
                    "vectors": {
                        "size": embedding_dim,
                        "distance": "Cosine",
                    }
                },
            )

        synced = 0
        points: list[dict[str, object]] = []

        for idx, intent in enumerate(intents):
            intent_id = str(intent.get("intent_id", intent.get("_key", "")))
            description = str(intent.get("description", ""))
            nl_examples = intent.get("nl_examples", [])
            nl_patterns = intent.get("nl_patterns", [])

            embed_parts = [description]
            for source in (nl_examples, nl_patterns):
                if isinstance(source, list):
                    for ex in source:
                        if isinstance(ex, str) and ex not in embed_parts:
                            embed_parts.append(ex)
            embed_text = " ".join(embed_parts)

            embedding = await get_embedding(embed_text)
            if not embedding:
                continue

            point: dict[str, object] = {
                "id": idx + 1,
                "vector": embedding,
                "payload": {
                    "intent_id": intent_id,
                    "agent_scope": scope,
                    "account": str(intent.get("account", "")),
                    "name": str(intent.get("name", "")),
                    "description": description,
                    "status": str(intent.get("status", "enabled")),
                    "priority": intent.get("priority", 0),
                    "intent_type": str(intent.get("intent_type", "")),
                    "group": str(intent.get("group", "")),
                    "tables": intent.get("tables", []),
                    "table_id": str(intent.get("table_id", "")),
                    "sheet_key": str(intent.get("sheet_key", "")),
                    "table_key": str(intent.get("table_key", "")),
                    "action": str(intent.get("action", "")),
                    "generation_strategy": str(
                        intent.get("generation_strategy", "tool_calling")
                    ),
                    "query_type": str(
                        intent.get("query_type", "simple_filter")
                    ),
                    "tool_schema": intent.get("tool_schema"),
                    "involved_tables": intent.get("involved_tables", []),
                    "join_keys": intent.get("join_keys", []),
                    "sql_template": str(intent.get("sql_template", "")),
                    "core_fields": intent.get("core_fields", []),
                    "nl_examples": nl_examples,
                    "nl_patterns": intent.get("nl_patterns", []),
                    "example_sqls": intent.get("example_sqls", []),
                    "filter_template": intent.get("filter_template"),
                },
            }
            points.append(point)
            synced += 1

        if points:
            async with httpx.AsyncClient(timeout=120.0) as client:
                await client.put(
                    f"{QDRANT_URL}/collections/{qdrant_collection}/points",
                    json={"points": points},
                )

        return EmbedSyncResponse(
            synced_count=synced,
            collection=qdrant_collection,
            status="ok",
        )

    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Sync failed: {str(e)}")


@router.post("/{scope}/intent/match", response_model=IntentMatchResponse)
async def match_intent(
    request: IntentMatchRequest,
    scope: str = PathParam(..., description="Agent scope"),
) -> IntentMatchResponse:
    """Match a natural language query to the closest intent(s) via Qdrant for the given scope."""
    qdrant_collection = _resolve_qdrant_collection(scope)

    try:
        threshold_str = await get_param("intent.match_threshold")
        try:
            match_threshold = float(threshold_str)
        except (ValueError, TypeError):
            match_threshold = MATCH_THRESHOLD_DEFAULT

        query_embedding = await get_embedding(request.query)
        if not query_embedding:
            raise HTTPException(
                status_code=500, detail="Failed to generate query embedding"
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{QDRANT_URL}/collections/{qdrant_collection}/points/search",
                json={
                    "vector": query_embedding,
                    "limit": request.top_k,
                    "with_payload": True,
                },
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("result", [])
        matches: list[IntentMatchResult] = []

        for r in results:
            score = float(r.get("score", 0.0))
            if score < match_threshold:
                continue
            payload = r.get("payload", {})
            intent_id = str(
                payload.get("intent_id")
                or payload.get("expression_key", "")
                or payload.get("_key", "")
            )
            matches.append(
                IntentMatchResult(
                    intent_id=intent_id,
                    score=score,
                    intent_data=payload,
                )
            )

        best = matches[0] if matches else None

        return IntentMatchResponse(
            query=request.query,
            matches=matches,
            best_match=best,
        )

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Qdrant service unavailable: {str(e)}",
        )
