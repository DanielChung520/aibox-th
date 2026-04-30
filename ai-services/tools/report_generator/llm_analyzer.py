import json
import os
import re
import time as _time
from typing import Any

import httpx

from shared.llm_resolver import resolve as resolve_llm
from .prompts import SYSTEM_PROMPT

_GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:6500")
_cache: dict[str, tuple[str, float]] = {}
_NUM_CACHE: dict[str, tuple[float, float]] = {}
_CACHE_TTL = 300


def _get_cached(key: str) -> str | None:
    if key in _cache:
        value, ts = _cache[key]
        if value and (_time.time() - ts) < _CACHE_TTL:
            return value
    return None


def _set_cached(key: str, value: str) -> None:
    _cache[key] = (value, _time.time())


def _get_cached_num(key: str) -> float | None:
    if key in _NUM_CACHE:
        value, ts = _NUM_CACHE[key]
        if value and (_time.time() - ts) < _CACHE_TTL:
            return value
    return None


def _set_cached_num(key: str, value: float) -> None:
    _NUM_CACHE[key] = (value, _time.time())


async def _get_tool_config() -> dict[str, Any] | None:
    """Fetch tool configuration from tools collection (Rust API Gateway).

    Returns the tool document if found, None otherwise.
    Cached internally with same TTL as system_params.
    """
    cached = _get_cached("_tool_config_raw")
    if cached:
        try:
            return json.loads(cached)
        except Exception:
            pass
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{_GATEWAY_URL}/api/v1/tools/report-agent")
            if resp.status_code == 200:
                data = resp.json().get("data")
                if data:
                    _set_cached(
                        "_tool_config_raw", json.dumps(data, ensure_ascii=False)
                    )
                    return data
    except Exception:
        pass
    return None


async def _get_llm_config() -> tuple[str, str, str, float, float]:
    """
    Resolve LLM configuration for report generation.

    Priority:
    1. tool config → model_id (e.g. "deepseek:DeepSeek-V4-Flash"),
       temperature, max_tokens
    2. model_id → shared.llm_resolver → endpoint + api_key
    3. system_params → env → defaults for temperature / max_tokens
    """
    tool_config = await _get_tool_config()
    model_id = "llama3.2:latest"

    if tool_config:
        if tool_config.get("llm_model"):
            model_id = str(tool_config["llm_model"])
        if tool_config.get("temperature") is not None:
            _set_cached_num("report.llm_temperature", float(tool_config["temperature"]))
        if tool_config.get("max_tokens") is not None:
            _set_cached_num(
                "report.llm_max_tokens", int(float(tool_config["max_tokens"]))
            )

    resolved = await resolve_llm(model_id)
    endpoint = resolved.endpoint
    model = resolved.model_name
    api_key = resolved.api_key

    temperature = _get_cached_num("report.llm_temperature")
    if temperature is None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{_GATEWAY_URL}/api/v1/system-params/report.llm_temperature"
                )
                if resp.status_code == 200:
                    tv = resp.json().get("data", {}).get("param_value", "")
                    if tv:
                        temperature = float(tv)
        except Exception:
            pass
        if temperature is None:
            temperature = 0.3
        _set_cached_num("report.llm_temperature", temperature)

    max_tokens = _get_cached_num("report.llm_max_tokens")
    if max_tokens is None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{_GATEWAY_URL}/api/v1/system-params/report.llm_max_tokens"
                )
                if resp.status_code == 200:
                    mv = resp.json().get("data", {}).get("param_value", "")
                    if mv:
                        max_tokens = int(float(mv))
        except Exception:
            pass
        if max_tokens is None:
            max_tokens = 4000
        _set_cached_num("report.llm_max_tokens", max_tokens)

    return endpoint, model, api_key, temperature, max_tokens


def _summarize_data(data: Any, depth: int = 0, max_items: int = 5) -> str:
    if depth > 3:
        return "..."
    if isinstance(data, dict):
        items = list(data.items())
        summary = []
        for k, v in items[:max_items]:
            if isinstance(v, (dict, list)):
                summary.append(f"{k}: {_summarize_data(v, depth + 1)}")
            else:
                summary.append(f"{k}: {v}")
        leftover = len(items) - max_items
        if leftover > 0:
            summary.append(f"...（還有 {leftover} 個欄位）")
        return "{" + ", ".join(summary) + "}"
    elif isinstance(data, list):
        if not data:
            return "[]"
        if isinstance(data[0], dict):
            return (
                f"陣列（{len(data)} 筆），第一筆：{_summarize_data(data[0], depth + 1)}"
            )
        return f"陣列（{len(data)} 筆）：{data[:max_items]}..."
    return str(data)[:100]


async def analyze_and_generate(
    dataset: dict | list[dict],
    report_goal: str,
    preferred_chart: str | None = None,
    domain_context: str | None = None,
) -> dict[str, Any]:
    import json as _json

    data_str = _json.dumps(dataset, ensure_ascii=False)
    chart_type_str = preferred_chart if preferred_chart else "餅圖、柱狀圖、線圖"
    context_block = f"\n知識領域上下文：{domain_context}" if domain_context else ""

    user_message = (
        "請分析以下 JSON 資料，並生成對應的圖表資料陣列。\n\n"
        f"完整資料：\n{data_str}\n"
        f"{context_block}\n\n"
        f"報表目標：{report_goal}\n\n"
        f"希望生成的圖表類型：{chart_type_str}\n\n"
        "請用以下 JSON 格式回覆（只回覆 JSON，不要其他文字）：\n"
        '{"chart_data": [{"name": "類別A", "value": 100}], '
        '"chart_type": "pie", '
        '"analysis_summary": "分析文字（繁體中文，200-300字）"}\n\n'
        "注意事項：\n"
        "- chart_type 只能填寫以下單一值之一：pie / bar / line / area / scatter / combo\n"
        '- 不要使用 | 連接多個值，例如不要寫 "pie|bar"\n'
        "- chart_data 的 name 對應圖表的類別名稱標籤，直接使用資料中的分類欄位\n"
        "- chart_data 的 value 對應圖表的數值，直接使用資料中的數值欄位\n"
        "- analysis_summary 用繁體中文撰寫 200-300 字的圖表分析說明，必須包含具體數字與佔比\n"
        "- 不要輸出 HTML/CSS 結構"
    )

    endpoint, model, api_key, temperature, max_tokens = await _get_llm_config()

    _LLM_TIMEOUT = 300.0

    if endpoint.endswith("/api/chat"):
        async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
            response = await client.post(
                endpoint,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False,
                },
            )
            response.raise_for_status()
            result_text = response.json().get("message", {}).get("content", "")
    else:
        async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            response = await client.post(
                endpoint,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                headers=headers,
            )
            response.raise_for_status()
            result_text = (
                response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

    try:
        json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            chart_data = result.get("chart_data", [])
            raw_chart_type = result.get("chart_type", "")

            VALID_CHART_TYPES = {"pie", "bar", "line", "area", "scatter", "combo"}
            if raw_chart_type in VALID_CHART_TYPES:
                chart_type = raw_chart_type
            elif preferred_chart in VALID_CHART_TYPES:
                chart_type = preferred_chart
            else:
                chart_type = "bar"

            analysis = result.get("analysis_summary", "（無分析）") or "（無分析）"
            if not chart_data:
                return {
                    "chart_data": [],
                    "chart_type": chart_type,
                    "analysis_summary": "（無法分析資料）",
                }
            return {
                "chart_data": chart_data,
                "chart_type": chart_type,
                "analysis_summary": analysis,
            }
    except Exception:
        pass

    return {
        "chart_data": [],
        "chart_type": preferred_chart
        if preferred_chart in {"pie", "bar", "line", "area", "scatter", "combo"}
        else "bar",
        "analysis_summary": "（無法分析資料）",
    }
