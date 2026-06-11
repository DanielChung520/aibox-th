"""
NL→SQL Pipeline - Intent Classifier

Classifies natural language queries by matching against Qdrant-indexed intents.
Searches Qdrant directly for embedding similarity.

# Last Update: 2026-03-24 14:12:23
# Author: Daniel Chung
# Version: .1.0
"""

import httpx

from data_agent.query.nl2sql.exceptions import IntentNotFoundError
from data_agent.query.nl2sql.models import (
    GenerationStrategy,
    IntentMatch,
    PipelineConfig,
)


def _parse_payload(payload: dict[str, object], score: float) -> IntentMatch:
    """Parse a Qdrant search result payload into IntentMatch."""
    strategy_str = str(payload.get("generation_strategy", "template"))
    try:
        strategy = GenerationStrategy(strategy_str)
    except ValueError:
        strategy = GenerationStrategy.TEMPLATE

    def _str_list(key: str) -> list[str]:
        raw = payload.get(key, [])
        return [str(x) for x in raw] if isinstance(raw, list) else []

    return IntentMatch(
        intent_id=str(payload.get("intent_id", "")),
        score=score,
        generation_strategy=strategy,
        sql_template=str(payload.get("sql_template", "")),
        tables=_str_list("tables"),
        core_fields=_str_list("core_fields"),
        description=str(payload.get("description", "")),
        intent_type=str(payload.get("intent_type", "")),
        group=str(payload.get("group", "")),
        nl_examples=_str_list("nl_examples"),
        example_sqls=_str_list("example_sqls"),
    )


async def _search_qdrant(
    query: str, config: PipelineConfig, limit: int = 3,
) -> list[dict[str, object]]:
    """Search Qdrant for similar intents and return raw results."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{config.qdrant_url}/collections/"
                f"{config.qdrant_collection}/points/search",
                json={
                    "vector": await _get_query_embedding(query, config),
                    "limit": limit,
                    "with_payload": True,
                },
            )
            response.raise_for_status()
            data = response.json()
        return list(data.get("result", []))
    except httpx.HTTPError as e:
        raise IntentNotFoundError(f"Qdrant service unavailable: {str(e)}")


async def classify_intent(
    query: str, config: PipelineConfig,
) -> IntentMatch:
    """Classify query by returning the single best intent above threshold.

    Raises:
        IntentNotFoundError: When no intent matches above threshold.
    """
    results = await _search_qdrant(query, config)
    for r in results:
        score = float(r.get("score", 0.0))
        if score < config.match_threshold:
            continue
        payload: dict[str, object] = r.get("payload", {})
        return _parse_payload(payload, score)

    raise IntentNotFoundError(
        f"No intent matched above threshold {config.match_threshold} "
        f"for query: {query}"
    )


async def classify_intent_candidates(
    query: str, config: PipelineConfig, limit: int = 3,
) -> list[IntentMatch]:
    """Return all intent candidates above threshold (up to limit).

    Used by reranker when top-1 score is below confidence threshold.
    Returns empty list if no matches found.
    """
    results = await _search_qdrant(query, config, limit=limit)
    candidates: list[IntentMatch] = []
    for r in results:
        score = float(r.get("score", 0.0))
        if score < config.match_threshold:
            continue
        payload: dict[str, object] = r.get("payload", {})
        candidates.append(_parse_payload(payload, score))
    return candidates


async def _get_query_embedding(
    text: str, config: PipelineConfig
) -> list[float]:
    """Get embedding vector for a query via Ollama."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{config.ollama_base_url}/api/embed",
            json={"model": config.embedding_model, "input": text},
        )
        response.raise_for_status()
        data = response.json()
        embeddings = data.get("embeddings", [])
        if embeddings and len(embeddings) > 0:
            result: list[float] = list(embeddings[0])
            return result
        return []
