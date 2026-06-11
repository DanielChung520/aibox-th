"""
NL→SQL Pipeline - Post-query Error Explainer

When the pipeline fails (SQL generation error, DuckDB execution error,
timeout, etc.), this module asks the LLM to produce a human-readable
explanation in Chinese with actionable suggestions.

# Last Update: 2026-03-24 16:17:53
# Author: Daniel Chung
# Version: 1.0.0
"""

import json
import logging

import httpx

from data_agent.query.nl2sql.models import ErrorExplanation, PipelineConfig

logger = logging.getLogger(__name__)

EXPLAIN_SYSTEM = (
    "你是一個資料查詢錯誤分析助手。使用者嘗試用自然語言查詢資料但失敗了。\n"
    "根據以下錯誤資訊，用繁體中文提供：\n"
    "1. 錯誤類型分類\n"
    "2. 簡明易懂的錯誤說明（非技術用語）\n"
    "3. 可行的改進建議（1-3 條）\n\n"
    "常見錯誤類型：\n"
    "- intent_not_found: 找不到匹配的查詢意圖\n"
    "- sql_generation_failed: SQL 生成失敗\n"
    "- sql_validation_failed: SQL 語法或安全驗證失敗\n"
    "- execution_error: DuckDB 執行 SQL 時發生錯誤\n"
    "- timeout: 查詢超時\n"
    "- schema_error: 找不到對應的資料表結構\n\n"
    "回傳嚴格 JSON（不要 markdown 或多餘文字）：\n"
    '{"error_type": "分類", "explanation": "說明", '
    '"suggestions": ["建議1", "建議2"]}'
)


async def explain_error(
    query: str,
    error_message: str,
    phase: str,
    config: PipelineConfig,
) -> ErrorExplanation:
    """Ask LLM to explain a pipeline failure in human-readable Chinese."""
    user_msg = (
        f"使用者查詢: {query}\n"
        f"失敗階段: {phase}\n"
        f"錯誤訊息: {error_message}"
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{config.ollama_base_url}/api/chat",
                json={
                    "model": config.small_model,
                    "messages": [
                        {"role": "system", "content": EXPLAIN_SYSTEM},
                        {"role": "user", "content": user_msg},
                    ],
                    "stream": False,
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            content = str(resp.json().get("message", {}).get("content", ""))

        return _parse_explanation(content, phase, error_message)

    except (httpx.HTTPError, Exception) as e:
        logger.warning("Error explainer LLM call failed: %s", e)
        return _fallback_explanation(phase, error_message)


def _parse_explanation(
    raw: str, phase: str, error_message: str,
) -> ErrorExplanation:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                return _fallback_explanation(phase, error_message)
        else:
            return _fallback_explanation(phase, error_message)

    return ErrorExplanation(
        error_type=str(data.get("error_type", phase)),
        explanation=str(data.get("explanation", error_message)),
        suggestions=[str(s) for s in data.get("suggestions", [])],
    )


def _fallback_explanation(phase: str, error_message: str) -> ErrorExplanation:
    type_map = {
        "intent_classification": ("intent_not_found", "找不到匹配的查詢意圖"),
        "sql_generation": ("sql_generation_failed", "SQL 查詢生成失敗"),
        "sql_validation": ("sql_validation_failed", "SQL 語法或安全驗證未通過"),
        "execution": ("execution_error", "資料庫執行查詢時發生錯誤"),
        "schema_retrieval": ("schema_error", "找不到對應的資料表結構"),
    }
    matched_key = next((k for k in type_map if k in phase), "")
    error_type, default_msg = type_map.get(matched_key, ("unknown", "查詢處理過程中發生未知錯誤"))

    return ErrorExplanation(
        error_type=error_type,
        explanation=f"{default_msg}：{error_message[:200]}",
        suggestions=["嘗試更具體的查詢描述", "確認查詢內容與可用資料領域相關"],
    )
