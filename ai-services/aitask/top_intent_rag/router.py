"""
TopIntentRAG Router - FastAPI routes for Top Orchestrator intent matching.

Hybrid matching: Keyword + Vector + RRF Fusion

# Last Update: 2026-04-22
# Author: Daniel Chung
# Version: 1.1.0
"""

import logging
import os
import time
from collections import defaultdict

import httpx
from fastapi import APIRouter, HTTPException, Query

from .config import (
    get_embedding_dimensions,
    get_embedding_model,
    get_matching_threshold,
    get_qdrant_collection,
)
from .embedding import get_embedding
from .models import (
    EmbedSyncResponse,
    TopIntentMatchResponse,
    TopIntentMatchResult,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/top-intent-rag", tags=["top-intent-rag"])

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

RRF_K = 60
KEYWORD_MATCH_SCORE = 10.0
DESCRIPTION_MATCH_SCORE = 5.0
NL_EXAMPLE_MATCH_SCORE = 3.0
NL_PATTERN_MATCH_SCORE = 2.0

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
VERIFY_THRESHOLD_HIGH = 0.75
VERIFY_THRESHOLD_LOW = 0.4

LLM_VERIFY_PROMPT = """你是意圖分類專家。

使用者查詢：{query}

候選意圖：
{candidates}

請判斷哪個意圖最匹配使用者查詢？

回覆格式（只回覆JSON）：
{{"best_intent": "意圖名稱", "confidence": 0.0-1.0, "reason": "原因"}}

如果沒有任何意圖匹配，回覆：
{{"best_intent": null, "confidence": 0.0, "reason": "原因"}}
"""


async def fetch_intents_from_arango() -> list[dict]:
    """Fetch orchestrator intents from intent_catalog."""
    aql = (
        "FOR doc IN intent_catalog FILTER doc.agent_scope == 'orchestrator' RETURN doc"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": aql},
                auth=(ARANGO_USER, ARANGO_PASSWORD),
            )
            if response.status_code in (200, 201):
                data = response.json()
                return data.get("result", [])
    except Exception as e:
        logger.error(f"Failed to fetch intents from ArangoDB: {e}")
    return []


def _extract_keywords(query: str) -> list[str]:
    stop_words = {
        "什麼",
        "是",
        "的",
        "了",
        "和",
        "與",
        "這",
        "那",
        "有",
        "沒有",
        "如何",
        "怎麼",
        "為什麼",
        "可以",
        "嗎",
        "呢",
        "什麼樣",
        "哪個",
        "哪些",
        "怎樣",
        "幫",
        "幫我",
        "請問",
        "想",
        "要",
        "一下",
        "一個",
    }
    words = (
        query.replace("？", " ")
        .replace("?", " ")
        .replace("，", " ")
        .replace(",", " ")
        .split()
    )
    keywords = [w for w in words if len(w) >= 2 and w not in stop_words]
    keywords.sort(key=len, reverse=True)
    return keywords[:10]


async def _keyword_search_intents(query: str, top_k: int = 10) -> list[dict]:
    keywords = _extract_keywords(query)
    if not keywords:
        logger.debug("keyword_search skip: no keywords extracted from query")
        return []

    t0 = time.time()
    bind_vars: dict[str, object] = {
        "top_k": top_k,
        "scope": "orchestrator",
        "num_kw": len(keywords),
    }
    for i, kw in enumerate(keywords):
        bind_vars[f"kw{i}"] = kw

    aql = f"""
    FOR doc IN intent_catalog
    FILTER doc.agent_scope == @scope AND doc.status == 'enabled'
    LET keyword_score = (
        SUM(
            FOR i IN RANGE(0, @num_kw)
            LET kw = CONCAT('%', @kw{{i}}, '%')
            RETURN (
                LIKE(doc.name, kw, true) ? {int(KEYWORD_MATCH_SCORE)} : 0 +
                LIKE(doc.description, kw, true) ? {int(DESCRIPTION_MATCH_SCORE)} : 0 +
                (FOR item IN doc.nl_examples ALL FILTER LIKE(item, kw, true) RETURN 1)[0] ? {int(NL_EXAMPLE_MATCH_SCORE)} : 0 +
                (FOR item IN doc.nl_patterns ALL FILTER LIKE(item, kw, true) RETURN 1)[0] ? {int(NL_PATTERN_MATCH_SCORE)} : 0
            )
        )
    )
    FILTER keyword_score > 0
    SORT keyword_score DESC
    LIMIT @top_k
    RETURN {{ doc, keyword_score }}
    """

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": aql, "bindVars": bind_vars},
                auth=(ARANGO_USER, ARANGO_PASSWORD),
            )
            if response.status_code in (200, 201):
                results = response.json().get("result", [])
                elapsed_ms = int((time.time() - t0) * 1000)
                logger.info(
                    "keyword_search | query=%s | keywords=%s | hits=%d | top_score=%.2f | latency_ms=%d",
                    query[:30],
                    keywords[:5],
                    len(results),
                    results[0].get("keyword_score", 0) if results else 0,
                    elapsed_ms,
                )
                return results
    except Exception as e:
        logger.warning("Keyword search failed: %s", e)
    return []


def _rrf_fuse(
    keyword_results: list[dict],
    vector_results: list[dict],
    keyword_weight: float = 1.0,
    vector_weight: float = 1.0,
    top_k: int = 10,
) -> list[tuple[str, float]]:
    scores: dict[str, float] = defaultdict(float)

    for rank, item in enumerate(keyword_results):
        doc_key = str(
            item.get("doc", {}).get("intent_id", item.get("doc", {}).get("_key", ""))
        )
        scores[doc_key] += keyword_weight * (1.0 / (RRF_K + rank + 1))

    for rank, item in enumerate(vector_results):
        doc_key = str(item.get("payload", {}).get("intent_id", item.get("id", "")))
        scores[doc_key] += vector_weight * (1.0 / (RRF_K + rank + 1))

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]


async def _llm_verify_intent(
    query: str,
    candidates: list[TopIntentMatchResult],
    model: str = "qwen2.5-coder:7b",
) -> TopIntentMatchResult | None:
    if not candidates:
        return None

    t0 = time.time()
    candidates_text = "\n".join(
        f"{i + 1}. {c.name} - {c.description}" for i, c in enumerate(candidates[:5])
    )
    prompt = LLM_VERIFY_PROMPT.format(
        query=query,
        candidates=candidates_text,
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 100},
                },
            )
            response.raise_for_status()
            raw = response.json().get("response", "")

        import json

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw[start:end])
            best_intent_id = parsed.get("best_intent_id")
            confidence = float(parsed.get("confidence", 0.5))
            elapsed_ms = int((time.time() - t0) * 1000)
            if best_intent_id:
                for c in candidates:
                    if c.intent_id == best_intent_id:
                        c.score = confidence
                        c.source = "llm_verify"
                        logger.info(
                            "llm_verify success | query=%s | best_intent=%s | confidence=%.4f | latency_ms=%d",
                            query[:30],
                            best_intent_id,
                            confidence,
                            elapsed_ms,
                        )
                        return c
            logger.info(
                "llm_verify no_match | query=%s | confidence=%.4f | latency_ms=%d",
                query[:30],
                confidence,
                elapsed_ms,
            )
        else:
            logger.warning(
                "llm_verify parse_failed | query=%s | raw=%s", query[:30], raw[:100]
            )
    except Exception as e:
        logger.warning("llm_verify failed | query=%s | error=%s", query[:30], e)
    return None


@router.post("/sync", response_model=EmbedSyncResponse)
async def sync_to_qdrant() -> EmbedSyncResponse:
    t0 = time.time()
    intents = await fetch_intents_from_arango()
    if not intents:
        logger.info("intent_sync skipped: no intents found in ArangoDB")
        return EmbedSyncResponse(
            synced_count=0, collection="orchestrator_intents", status="no_intents_found"
        )

    collection = await get_qdrant_collection()
    embedding_dim = await get_embedding_dimensions()
    embedding_model = await get_embedding_model()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.put(
                f"{QDRANT_URL}/collections/{collection}",
                json={
                    "vectors": {
                        "size": embedding_dim,
                        "distance": "Cosine",
                    }
                },
            )
    except Exception as e:
        logger.warning("Failed to create Qdrant collection: %s", e)

    points = []
    embed_failures = 0
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

        embedding = await get_embedding(embed_text, embedding_model)
        if not embedding:
            embed_failures += 1
            continue

        point: dict = {
            "id": idx + 1,
            "vector": embedding,
            "payload": {
                "intent_id": intent_id,
                "name": str(intent.get("name", "")),
                "description": description,
                "intent_type": str(intent.get("intent_type", "")),
                "domain": str(intent.get("domain", "")),
                "action_type": str(intent.get("action_type", "")),
                "target_agent": str(intent.get("target_agent", "")),
                "tool_category": str(intent.get("tool_category", "")),
                "tool_name": str(intent.get("tool_name", "")),
                "bpa_id": str(intent.get("bpa_id", "")),
                "pdca_id": str(intent.get("pdca_id", "")),
                "ca_id": str(intent.get("ca_id", "")),
                "response_strategy": str(intent.get("response_strategy", "")),
                "confidence_threshold": float(intent.get("confidence_threshold", 0.7)),
                "nl_examples": nl_examples,
                "nl_patterns": nl_patterns,
            },
        }
        points.append(point)

    if points:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                await client.put(
                    f"{QDRANT_URL}/collections/{collection}/points",
                    json={"points": points},
                )
        except Exception as e:
            raise HTTPException(
                status_code=502, detail=f"Failed to upsert to Qdrant: {e}"
            )

    elapsed_ms = int((time.time() - t0) * 1000)
    logger.info(
        "intent_sync | collection=%s | total_intents=%d | synced=%d | embed_failures=%d | latency_ms=%d",
        collection,
        len(intents),
        len(points),
        embed_failures,
        elapsed_ms,
    )

    return EmbedSyncResponse(
        synced_count=len(points), collection=collection, status="ok"
    )


@router.post("/match", response_model=TopIntentMatchResponse)
async def match_intent(
    query: str = Query(..., description="User query to match against intents"),
    top_k: int = Query(5, description="Number of top matches to return"),
) -> TopIntentMatchResponse:
    t0 = time.time()
    collection = await get_qdrant_collection()
    threshold = await get_matching_threshold()
    if threshold is None:
        threshold = 0.5
    embedding_model = await get_embedding_model()

    t1 = time.time()
    keyword_results = await _keyword_search_intents(query, top_k=top_k)
    keyword_ms = int((time.time() - t1) * 1000)

    t2 = time.time()
    query_embedding = await get_embedding(query, embedding_model)
    embed_ms = int((time.time() - t2) * 1000)
    if not query_embedding:
        raise HTTPException(
            status_code=500, detail="Failed to generate query embedding"
        )

    t3 = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{QDRANT_URL}/collections/{collection}/points/search",
                json={
                    "vector": query_embedding,
                    "limit": top_k,
                    "with_payload": True,
                },
            )
            response.raise_for_status()
            vector_results = response.json().get("result", [])
    except httpx.HTTPError:
        vector_results = []
    vector_ms = int((time.time() - t3) * 1000)

    t4 = time.time()
    fused_ranks = _rrf_fuse(keyword_results, vector_results, top_k=top_k * 2)
    fusion_ms = int((time.time() - t4) * 1000)

    intent_map: dict[str, dict] = {}
    for item in keyword_results:
        doc = item.get("doc", {})
        intent_id = str(doc.get("intent_id", doc.get("_key", "")))
        intent_map[intent_id] = {
            "doc": doc,
            "keyword_score": item.get("keyword_score", 0),
        }

    for r in vector_results:
        payload = r.get("payload", {})
        intent_id = str(payload.get("intent_id", ""))
        if intent_id and intent_id not in intent_map:
            intent_map[intent_id] = {
                "doc": {"intent_id": intent_id, **payload},
                "vector_score": r.get("score", 0),
            }
        elif intent_id in intent_map:
            intent_map[intent_id]["vector_score"] = r.get("score", 0)

    matches = []
    for intent_id, fused_score in fused_ranks:
        info = intent_map.get(intent_id, {})
        doc = info.get("doc", {})
        payload = (
            doc
            if doc.get("intent_id")
            else {
                "intent_id": doc.get("intent_id", intent_id),
                "name": doc.get("name", ""),
                "description": doc.get("description", ""),
                "intent_type": doc.get("intent_type", ""),
                "domain": doc.get("domain", ""),
                "action_type": doc.get("action_type"),
                "target_agent": doc.get("target_agent"),
                "tool_category": doc.get("tool_category"),
                "tool_name": doc.get("tool_name"),
                "bpa_id": doc.get("bpa_id"),
                "pdca_id": doc.get("pdca_id"),
                "ca_id": doc.get("ca_id"),
                "response_strategy": doc.get("response_strategy"),
                "confidence_threshold": doc.get("confidence_threshold", 0.7),
            }
        )

        kw_src = (
            "keyword"
            if intent_id
            in [str(i.get("doc", {}).get("intent_id", "")) for i in keyword_results]
            else ""
        )
        vec_src = (
            "vector"
            if any(
                str(r.get("payload", {}).get("intent_id", "")) == intent_id
                for r in vector_results
            )
            else ""
        )
        source = "hybrid" if (kw_src and vec_src) else (kw_src or vec_src or "unknown")

        matches.append(
            TopIntentMatchResult(
                intent_id=str(payload.get("intent_id", intent_id)),
                score=round(fused_score, 4),
                name=str(payload.get("name", "")),
                description=str(payload.get("description", "")),
                intent_type=str(payload.get("intent_type", "")),
                domain=str(payload.get("domain", "")),
                action_type=payload.get("action_type"),
                target_agent=payload.get("target_agent"),
                tool_category=payload.get("tool_category"),
                tool_name=payload.get("tool_name"),
                bpa_id=payload.get("bpa_id"),
                pdca_id=payload.get("pdca_id"),
                ca_id=payload.get("ca_id"),
                response_strategy=payload.get("response_strategy"),
                confidence_threshold=float(payload.get("confidence_threshold", 0.7)),
                source=source,
            )
        )

    best = matches[0] if matches else None
    llm_verify_triggered = False
    llm_verify_ms = 0

    if best and VERIFY_THRESHOLD_LOW < best.score < VERIFY_THRESHOLD_HIGH:
        t5 = time.time()
        verified = await _llm_verify_intent(query, matches[:3])
        llm_verify_ms = int((time.time() - t5) * 1000)
        llm_verify_triggered = True
        if verified:
            matches = [verified] + [
                m for m in matches if m.intent_id != verified.intent_id
            ]
            best = matches[0]

    if best and best.score < VERIFY_THRESHOLD_LOW:
        total_ms = int((time.time() - t0) * 1000)
        logger.info(
            "intent_match abstained | query=%s | best_score=%.4f | "
            "keyword_ms=%d | embed_ms=%d | vector_ms=%d | fusion_ms=%d | llm_verify_ms=%d | total_ms=%d",
            query[:50],
            best.score,
            keyword_ms,
            embed_ms,
            vector_ms,
            fusion_ms,
            llm_verify_ms,
            total_ms,
        )
        return TopIntentMatchResponse(
            query=query,
            matches=matches,
            best_match=None,
            multi_intent={"primary": "unknown", "secondary": []},
            reasoning="Intent confidence too low. Please clarify your request.",
        )

    multi_intent = _detect_multi_intent(matches)
    reasoning = _generate_reasoning(query, matches, multi_intent)
    total_ms = int((time.time() - t0) * 1000)

    logger.info(
        "intent_match | query=%s | best_match=%s | best_score=%.4f | source=%s | "
        "keyword_count=%d | vector_count=%d | llm_verify=%s | "
        "keyword_ms=%d | embed_ms=%d | vector_ms=%d | fusion_ms=%d | llm_verify_ms=%d | total_ms=%d",
        query[:50],
        best.intent_id if best else None,
        best.score if best else 0,
        best.source if best else None,
        len(keyword_results),
        len(vector_results),
        str(llm_verify_triggered),
        keyword_ms,
        embed_ms,
        vector_ms,
        fusion_ms,
        llm_verify_ms,
        total_ms,
    )

    return TopIntentMatchResponse(
        query=query,
        matches=matches,
        best_match=best,
        multi_intent=multi_intent,
        reasoning=reasoning,
    )


def _detect_multi_intent(matches: list[TopIntentMatchResult]) -> dict[str, object]:
    if not matches:
        return {"primary": "unknown", "secondary": []}

    task_intents = [m for m in matches if m.intent_type == "task"]
    chat_intents = [m for m in matches if m.intent_type == "chat"]

    if task_intents and chat_intents:
        top_task = task_intents[0]
        top_chat = chat_intents[0]
        score_gap = abs(top_task.score - top_chat.score)
        if score_gap < 0.15:
            return {
                "primary": "task",
                "secondary": [top_chat.intent_id],
            }

    if best := matches[0]:
        primary_type = "task" if best.intent_type == "task" else "chat"
        return {"primary": primary_type, "secondary": []}

    return {"primary": "unknown", "secondary": []}


def _generate_reasoning(
    query: str,
    matches: list[TopIntentMatchResult],
    multi_intent: dict[str, object],
) -> str:
    if not matches:
        return "No matching intent found above threshold."

    if multi_intent.get("primary") == "task" and multi_intent.get("secondary"):
        secondary = multi_intent["secondary"]
        if isinstance(secondary, list) and secondary:
            return (
                f"Multi-intent detected: task intent '{matches[0].intent_id}' "
                f"with emotion response '{secondary[0]}'. "
                f"Will execute task first, then include emotion response."
            )

    return (
        f"Matched intent '{matches[0].intent_id}' "
        f"(score: {matches[0].score:.2f}) - {matches[0].description}"
    )
