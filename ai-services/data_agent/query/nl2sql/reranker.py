"""
NL→SQL Pipeline - Post-Retrieval Reranker

LLM-based reranking of intent candidates when top-1 score is ambiguous.
Only triggered when best match score < RERANK_THRESHOLD (0.75).

# Last Update: 2026-03-24 14:12:23
# Author: Daniel Chung
# Version: 1.0.0
"""

import logging
import re

import httpx

from data_agent.query.nl2sql.models import IntentMatch, PipelineConfig

logger = logging.getLogger(__name__)

RERANK_THRESHOLD = 0.75

_RERANK_PROMPT = """你是一個意圖分類專家。請從以下候選意圖中選出最匹配使用者查詢的意圖。

使用者查詢: "{query}"

候選意圖:
{candidates_text}

請僅回傳最佳匹配的 intent_id，格式: {{"best_intent_id": "xxx"}}
不要解釋，只回傳 JSON。"""


def _build_candidates_text(candidates: list[IntentMatch]) -> str:
    lines: list[str] = []
    for i, c in enumerate(candidates, 1):
        examples = ", ".join(c.nl_examples[:3]) if c.nl_examples else "無"
        lines.append(
            f"{i}. intent_id={c.intent_id} | score={c.score:.3f} | "
            f"描述={c.description} | 範例查詢=[{examples}]"
        )
    return "\n".join(lines)


async def rerank_candidates(
    query: str,
    candidates: list[IntentMatch],
    config: PipelineConfig,
) -> IntentMatch:
    """Rerank intent candidates using small LLM.

    Falls back to first candidate if LLM call fails or returns invalid id.
    """
    if len(candidates) <= 1:
        return candidates[0]

    prompt = _RERANK_PROMPT.format(
        query=query,
        candidates_text=_build_candidates_text(candidates),
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{config.ollama_base_url}/api/generate",
                json={
                    "model": config.small_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 50},
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")

        match = re.search(r'"best_intent_id"\s*:\s*"([^"]+)"', raw)
        if match:
            best_id = match.group(1)
            for c in candidates:
                if c.intent_id == best_id:
                    logger.info(
                        "Reranker selected %s (was #1: %s)",
                        best_id, candidates[0].intent_id,
                    )
                    return c

        logger.warning("Reranker returned unknown id: %s, using top-1", raw[:80])
    except (httpx.HTTPError, Exception) as e:
        logger.warning("Reranker failed, using top-1: %s", str(e)[:120])

    return candidates[0]
