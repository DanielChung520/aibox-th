"""
Knowledge Intent RAG - Intent-based routing for Knowledge Agent.

Provides intent matching for the knowledge domain using Qdrant-based
semantic search, similar to data_agent/intent_rag but for knowledge queries.

@lastUpdate: 2026-04-05 12:00:00
@author: Daniel Chung
@version: 1.0.0
"""

from __future__ import annotations

import logging
import os
import time
from typing import Final

import httpx
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")

KNOWLEDGE_SCOPE: Final[str] = "knowledge"
KNOWLEDGE_QDRANT_COLLECTION: Final[str] = "knowledge_intents"
_MATCH_THRESHOLD_DEFAULT: float = 0.45


_threshold_cache: float | None = None
_threshold_cache_ts: float = 0.0
_THRESHOLD_CACHE_TTL: float = 60.0


async def _get_match_threshold() -> float:
    global _threshold_cache, _threshold_cache_ts
    now = time.monotonic()
    if _threshold_cache is not None and (now - _threshold_cache_ts) < _THRESHOLD_CACHE_TTL:
        return _threshold_cache

    aql = "FOR p IN system_params FILTER p.param_key == @key RETURN p.param_value"
    value = _MATCH_THRESHOLD_DEFAULT
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": aql, "bindVars": {"key": "intent.matching_threshold"}},
                auth=(ARANGO_USER, ARANGO_PASSWORD),
            )
            if response.status_code in (200, 201):
                data = response.json()
                result = data.get("result", [])
                if result:
                    value = float(result[0])
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logging.getLogger(__name__).warning("Failed to read match threshold from DB: %s", exc)

    _threshold_cache = value
    _threshold_cache_ts = now
    return value


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class IntentMatchRequest(BaseModel):
    """Intent match request."""

    query: str
    top_k: int = 3


class IntentMatchResult(BaseModel):
    """Single intent match result."""

    intent_id: str
    score: float
    intent_data: dict


class IntentMatchResponse(BaseModel):
    """Intent match response."""

    query: str
    matches: list[IntentMatchResult]
    best_match: IntentMatchResult | None = None


# ---------------------------------------------------------------------------
# Router Implementation
# ---------------------------------------------------------------------------


async def get_embedding(text: str, embedding_model: str = "bge-m3:latest") -> list[float]:
    """Get embedding vector from Ollama.

    Args:
        text: Text to embed.
        embedding_model: Ollama embedding model name.

    Returns:
        Embedding vector.
    """
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


async def fetch_intents_from_arango(scope: str) -> list[dict]:
    """Fetch intents from ArangoDB intent_catalog filtered by agent_scope.

    Args:
        scope: Agent scope (e.g., "knowledge").

    Returns:
        List of intent documents.
    """
    aql = "FOR doc IN intent_catalog FILTER doc.agent_scope == @scope RETURN doc"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": aql, "bindVars": {"scope": scope}},
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        if response.status_code in (200, 201):
            data = response.json()
            return data.get("result", [])
    return []


async def embed_sync() -> dict:
    """Sync knowledge intents from ArangoDB to Qdrant.

    Returns:
        Sync result with count and status.
    """
    # Fetch intents from ArangoDB
    intents = await fetch_intents_from_arango(KNOWLEDGE_SCOPE)
    if not intents:
        return {"synced_count": 0, "status": "no_intents_found"}

    # Get embedding dimension
    embedding_model = "bge-m3:latest"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/v1/embeddings",
                json={"model": embedding_model, "input": "test"},
            )
            if resp.status_code == 200:
                embeddings = resp.json().get("embeddings", [])
                if embeddings:
                    embedding_dim = len(embeddings[0])
                else:
                    embedding_dim = 1024
            else:
                embedding_dim = 1024
    except Exception:
        embedding_dim = 1024

    # Create/ensure Qdrant collection
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.put(
            f"{QDRANT_URL}/collections/{KNOWLEDGE_QDRANT_COLLECTION}",
            json={
                "vectors": {
                    "size": embedding_dim,
                    "distance": "Cosine",
                }
            },
        )

    # Build and upsert points
    points: list[dict] = []
    for idx, intent in enumerate(intents):
        intent_id = str(intent.get("intent_id", intent.get("_key", "")))
        description = str(intent.get("description", ""))
        nl_examples = intent.get("nl_examples", [])

        embed_parts = [description]
        if isinstance(nl_examples, list):
            for ex in nl_examples:
                if isinstance(ex, str):
                    embed_parts.append(ex)
        embed_text = " ".join(embed_parts)

        embedding = await get_embedding(embed_text, embedding_model)
        if not embedding:
            continue

        point = {
            "id": idx + 1,
            "vector": embedding,
            "payload": {
                "intent_id": intent_id,
                "agent_scope": KNOWLEDGE_SCOPE,
                "description": description,
                "query_type": str(intent.get("query_type", "")),
                "intent_type": str(intent.get("intent_type", "")),
                "nl_examples": nl_examples,
                "name": str(intent.get("name", "")),
            },
        }
        points.append(point)

    if points:
        async with httpx.AsyncClient(timeout=120.0) as client:
            await client.put(
                f"{QDRANT_URL}/collections/{KNOWLEDGE_QDRANT_COLLECTION}/points",
                json={"points": points},
            )

    return {
        "synced_count": len(points),
        "collection": KNOWLEDGE_QDRANT_COLLECTION,
        "status": "ok",
    }


async def match_intent(
    query: str,
    top_k: int = 3,
) -> IntentMatchResponse:
    """Match a query to the best matching knowledge intent.

    Args:
        query: Natural language query.
        top_k: Number of top matches to return.

    Returns:
        IntentMatchResponse with matches.
    """
    # Get query embedding
    embedding_model = "bge-m3:latest"
    query_embedding = await get_embedding(query, embedding_model)
    if not query_embedding:
        raise ValueError("Failed to generate query embedding")

    # Search Qdrant
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{QDRANT_URL}/collections/{KNOWLEDGE_QDRANT_COLLECTION}/points/search",
                json={
                    "vector": query_embedding,
                    "limit": top_k,
                    "with_payload": True,
                },
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("result", [])
    except Exception as e:
        raise ValueError(f"Qdrant search failed: {e}")

    # Build response
    threshold = await _get_match_threshold()
    matches: list[IntentMatchResult] = []
    for r in results:
        score = float(r.get("score", 0.0))
        if score < threshold:
            continue
        payload = r.get("payload", {})
        matches.append(
            IntentMatchResult(
                intent_id=str(payload.get("intent_id", "")),
                score=score,
                intent_data=payload,
            )
        )

    best = matches[0] if matches else None

    return IntentMatchResponse(
        query=query,
        matches=matches,
        best_match=best,
    )
