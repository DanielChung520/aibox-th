"""
Structured SQL Generator — 將 StructuredQueryRequest 翻譯為 DuckDB SQL。

使用本地 SQL 專用模型 (duckdb-nsql / sqlcoder) 生成，
支援主模型 + fallback 模型重試機制。

# Last Update: 2026-04-16 19:52:01
# Author: Daniel Chung
# Version: 1.1.0
"""

import asyncio
import logging
import os
import re

import httpx

from data_agent.config_reader import get_param
from data_agent.query.nl2sql.exceptions import SQLGenerationError
from data_agent.query.nl2sql.models import StructuredQueryRequest

logger = logging.getLogger(__name__)

_OLLAMA_BASE_URL = os.getenv("MLX_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11400"))
_LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234")


def _build_prompt(
    request: StructuredQueryRequest,
    table_columns: list[dict[str, str]] | None = None,
) -> str:
    parts: list[str] = [
        f"Table: {request.table}",
    ]

    if table_columns:
        col_desc = ", ".join(
            f"{c['column_name']} ({c['data_type']})" for c in table_columns
        )
        parts.append(f"Columns: {col_desc}")

    parts.append(f"Intent: {request.intent}")

    if request.fields:
        parts.append(f"Fields: {', '.join(request.fields)}")

    if request.filters:
        filter_descs = [
            f"{f.field} {f.op} {f.value}" for f in request.filters
        ]
        parts.append(f"Filters: {'; '.join(filter_descs)}")

    if request.aggregations:
        parts.append(f"Aggregations: {', '.join(request.aggregations)}")

    if request.group_by:
        parts.append(f"Group by: {', '.join(request.group_by)}")

    if request.sort:
        parts.append(f"Sort: {request.sort.field} {request.sort.order}")

    parts.append(f"Limit: {request.limit}")

    return "\n".join(parts)


_SYSTEM_PROMPT = (
    "You are a DuckDB SQL expert. Generate a single SELECT statement.\n"
    "Rules:\n"
    "1. Use ONLY the table and columns provided. NEVER invent columns.\n"
    "2. Output ONLY the SQL, no explanation.\n"
    "3. Use DuckDB-compatible syntax.\n"
    "4. For count intent with NO filters: SELECT COUNT(*) FROM table. Do NOT add WHERE.\n"
    "5. For aggregate intent: use the specified aggregation functions.\n"
    "6. For filter intent: use WHERE clauses ONLY with the filters provided.\n"
    "7. For top_n intent: use ORDER BY + LIMIT.\n"
    "8. Always respect the LIMIT value.\n"
    "9. Do NOT add conditions that are not explicitly requested."
)


def _provider_url(provider: str) -> str:
    if provider == "lm_studio":
        return f"{_LM_STUDIO_URL}/v1/chat/completions"
    return f"{_OLLAMA_BASE_URL}/v1/chat/completions"


def _is_openai_compatible(provider: str) -> bool:
    return provider == "lm_studio"


async def _call_model(
    model: str,
    provider: str,
    prompt: str,
    temperature: float,
    timeout_seconds: float = 60.0,
) -> str:
    url = _provider_url(provider)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    if _is_openai_compatible(provider):
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
    else:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }

    async with httpx.AsyncClient(timeout=timeout_seconds + 5.0) as client:
        response = await asyncio.wait_for(
            client.post(url, json=payload),
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

    if _is_openai_compatible(provider):
        content = str(
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
    else:
        content = str(data[0].get("message",{}).get("content",""))

    return _extract_sql(content)


def _extract_sql(content: str) -> str:
    sql_match = re.search(r"```(?:sql)?\s*([\s\S]*?)```", content)
    if sql_match:
        return sql_match.group(1).strip()

    cleaned = content.strip()
    if cleaned.upper().startswith("SELECT"):
        return cleaned

    raise SQLGenerationError(f"No valid SQL in model response: {content[:200]}")


async def generate_structured_sql(
    request: StructuredQueryRequest,
    previous_error: str = "",
    table_columns: list[dict[str, str]] | None = None,
) -> tuple[str, str]:
    """Generate DuckDB SQL from a StructuredQueryRequest.

    Returns:
        (sql, model_used) tuple.

    Raises:
        SQLGenerationError on all attempts exhausted.
    """
    sql_model = await get_param("da.sql_model")
    sql_provider = await get_param("da.sql_model_provider")
    fallback_model = await get_param("da.sql_fallback_model")
    fallback_provider = await get_param("da.sql_fallback_provider")
    temperature = float(await get_param("da.sql_temperature") or "0.1")
    max_retries = int(await get_param("da.sql_max_retries") or "2")

    prompt = _build_prompt(request, table_columns)
    if previous_error:
        prompt += f"\n\nPrevious attempt failed: {previous_error}\nFix and regenerate."

    last_error = ""
    for attempt in range(max_retries + 1):
        model = sql_model if attempt == 0 else fallback_model
        provider = sql_provider if attempt == 0 else fallback_provider

        try:
            sql = await _call_model(model, provider, prompt, temperature)
            return sql, model
        except (SQLGenerationError, httpx.HTTPError, asyncio.TimeoutError) as e:
            last_error = str(e)
            logger.warning(
                "SQL generation attempt %d/%d failed (model=%s): %s",
                attempt + 1,
                max_retries + 1,
                model,
                last_error,
            )
            if attempt < max_retries:
                prompt += f"\n\nAttempt {attempt + 1} error: {last_error}\nFix and regenerate."

    raise SQLGenerationError(
        f"All {max_retries + 1} attempts failed. Last error: {last_error}"
    )
