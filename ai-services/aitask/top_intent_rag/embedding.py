"""
Embedding utilities for TopIntentRAG.

# Last Update: 2026-04-14
# Author: AI Agent
# Version: 1.0.0
"""

import os

import httpx


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_EMBEDDING_MODEL = "bge-m3"


async def get_embedding(text: str, model: str | None = None) -> list[float]:
    """Get embedding vector from Ollama."""
    embedding_model = model or DEFAULT_EMBEDDING_MODEL
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL.rstrip('/')}/v1/embeddings",
            json={"model": embedding_model, "input": text},
        )
        response.raise_for_status()
        data = response.json()
    embeddings = data.get("embeddings", [])
    if isinstance(embeddings, list) and embeddings:
        first_embedding = embeddings[0]
        if isinstance(first_embedding, list):
            return [float(value) for value in first_embedding]
    return []