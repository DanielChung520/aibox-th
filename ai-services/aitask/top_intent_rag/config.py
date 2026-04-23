"""
Configuration reader for TopIntentRAG.

Reads system params from ArangoDB.

# Last Update: 2026-04-14
# Author: AI Agent
# Version: 1.0.0
"""

import os

import httpx


ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")


async def get_intent_param(key: str, default: str = "") -> str:
    """Get an intent system param from ArangoDB system_params collection."""
    aql = "FOR p IN system_params FILTER p.param_key == @key RETURN p.param_value"
    bind_vars = {"key": key}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": aql, "bindVars": bind_vars},
                auth=(ARANGO_USER, ARANGO_PASSWORD),
            )
            if response.status_code in (200, 201):
                data = response.json()
                result = data.get("result", [])
                if result:
                    return str(result[0])
    except Exception:
        pass
    return default


async def get_matching_threshold() -> float:
    """Get intent matching threshold."""
    value = await get_intent_param("intent.matching_threshold", "0.45")
    try:
        return float(value)
    except ValueError:
        return 0.45


async def get_embedding_model() -> str:
    """Get embedding model for intent matching."""
    return await get_intent_param("intent.qdrant_embedding_model", "BAAI/bge-m3")


async def get_embedding_dimensions() -> int:
    """Get embedding dimensions."""
    value = await get_intent_param("intent.qdrant_embedding_dimensions", "1024")
    try:
        return int(value)
    except ValueError:
        return 1024


async def get_qdrant_collection() -> str:
    """Get Qdrant collection name for orchestrator intents."""
    return await get_intent_param("intent.qdrant_collection", "orchestrator_intents")
