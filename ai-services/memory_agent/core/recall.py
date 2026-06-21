"""
Memory recall module - AI-driven memory retrieval.
"""

import httpx
from datetime import datetime

from memory_agent.core.models import Memory, RecallResult


OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5-coder:7b"
VECTOR_MODEL = "bge-m3:latest"


def calculate_freshness(created_at: datetime) -> str:
    delta = datetime.now() - created_at
    if delta.days == 0:
        return "today"
    elif delta.days == 1:
        return "yesterday"
    else:
        return f"{delta.days} days ago"


def needs_verification(created_at: datetime) -> bool:
    delta = datetime.now() - created_at
    return delta.days > 1


async def get_embedding(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/v1/embeddings",
            json={"model": VECTOR_MODEL, "input": text},
        )
        response.raise_for_status()
        data = response.json()
        embeddings = data.get("embeddings", [])
        if embeddings and len(embeddings) > 0:
            return list(embeddings[0])
        return []


async def recall_memories(
    query: str,
    memories: list[Memory],
    top_k: int = 5,
) -> list[RecallResult]:
    if not memories:
        return []
    available_memories_text = "\n".join(
        [
            f"- [{m.type.value}] {m.memory_id} ({calculate_freshness(m.created_at)}): {m.description}"
            for m in memories
        ]
    )
    prompt = f"""Given the user's query, select up to {top_k} relevant memories.

Query: {query}

Available memories:
{available_memories_text}

Select memories that are relevant to the query. Return only the memory IDs, one per line.
If none are relevant, return "NONE"."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "").strip()
            if content == "NONE":
                return []
            selected_ids = [
                line.strip().split("]")[0].replace("[", "").replace("-", "").strip()
                for line in content.split("\n")
                if line.strip() and not line.strip().startswith("NONE")
            ]
            results: list[RecallResult] = []
            for memory in memories:
                if memory.memory_id in selected_ids and len(results) < top_k:
                    freshness = calculate_freshness(memory.created_at)
                    verification_needed = needs_verification(memory.created_at)
                    results.append(
                        RecallResult(
                            memory=memory,
                            relevance_score=0.8,
                            freshness=freshness,
                            needs_verification=verification_needed,
                        )
                    )
            return results
    except Exception:
        fallback_results = []
        for memory in memories[:top_k]:
            freshness = calculate_freshness(memory.created_at)
            verification_needed = needs_verification(memory.created_at)
            fallback_results.append(
                RecallResult(
                    memory=memory,
                    relevance_score=0.5,
                    freshness=freshness,
                    needs_verification=verification_needed,
                )
            )
        return fallback_results


async def generate_system_prompt(memory_dir: str) -> str:
    prompt = """# Memory System

You have a persistent, file-based memory system at `<memoryDir>`.
This directory already exists — write to it directly with the Write tool.

You should build up this memory system over time so that future conversations
can have a complete picture of who the user is, how they'd like to collaborate
with you, what behaviors to avoid or repeat, and the context behind the work.

## Types of memory
- **user**: 用戶畫像、角色、目標、知識背景
- **feedback**: 工作方式指導（糾正和確認）
- **project**: 項目進展、目標、截止日期
- **reference**: 外部系統指針

## What NOT to Save
- 代碼模式、架構、文件路徑（可從代碼推導）
- Git 歷史（git log 是權威來源）
- 調試方案（修復在代碼中）
- CLAUDE.md 已有的內容
- 臨時任務細節

## How to Save
1. Write file with frontmatter
2. Add entry to MEMORY.md index

## When to Access
- 看起来相關時
- 用戶明確要求時（必須訪問）
- 用戶說"忽略記憶"時，假裝 MEMORY.md 為空

## Before Using a Memory
- 提到文件路徑 → 檢查文件是否存在
- 提到函數/標誌 → grep 搜索
- 用戶要行動 → 先驗證

## Memory freshness
記憶新鮮度用自然語言："today", "yesterday", "47 days ago"
超過 1 天的記憶，在使用前必須驗證。"""
    return prompt
