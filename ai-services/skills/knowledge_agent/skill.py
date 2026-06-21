"""
@file        knowledge_agent/skill.py
@description 知識庫 FAQ 檢索 Skill：透過 Knowledge Agent 向量檢索 FAQ
@lastUpdate  2026-06-20
@author      Sisyphus
@version     1.0.0

# Skill 規範
## 用途
將客戶問題送往 Knowledge Agent 進行向量檢索，回傳 FAQ 匹配結果。
"""

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)

KNOWLEDGE_AGENT_URL = "http://localhost:8011/ka"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    import httpx

    query = params.get("query", "")
    top_k = params.get("top_k", 3)

    if not query:
        return {"error": "query is required", "answers": [], "total": 0}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{KNOWLEDGE_AGENT_URL}/search",
                json={"query": query, "top_k": top_k},
            )
            if resp.status_code == 200:
                data = resp.json()
                answers = data.get("results", data.get("data", []))
                return {
                    "answers": answers if isinstance(answers, list) else [],
                    "total": len(answers) if isinstance(answers, list) else 0,
                }
    except Exception as e:
        logger.warning(f"[KnowledgeAgent] Search failed: {e}")

    return {"answers": [], "total": 0}
