"""
@file        Inquiry Layer LLM Client
@description 呼叫 Ollama 分析意圖假設與邊界狀態。
              模型與相關參數統一從 ArangoDB system_params 讀取（透過 Rust API Gateway）。
@lastUpdate  2026-04-19 02:30:00
@author      Daniel Chung
@version     1.1.0
"""

from __future__ import annotations

import json
import logging
import os
import time
from json import JSONDecodeError

import httpx

from aiq_agent.inquiry.models import (
    BoundaryStatus,
    BoundaryStatusEnum,
    Evidence,
    ExecutionPath,
    Hypothesis,
    LLMAnalysisRequest,
    LLMAnalysisResponse,
)

logger = logging.getLogger(__name__)

_GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:6500")
_CACHE_TTL = int(os.getenv("AIQ_CONFIG_CACHE_TTL", "300"))
_param_cache: dict[str, tuple[str, float]] = {}

# Intent 相關參數讀取順序：ArangoDB system_params → env fallback
_PARAM_FALLBACKS: dict[str, tuple[str, str]] = {
    "intent.small_model_name": ("AIQ_INQUIRY_MODEL", "qwen3.5:0.8b"),
    "intent.use_small_model": ("AIQ_USE_SMALL_MODEL", "true"),
    "intent.small_model_temperature": ("AIQ_TEMPERATURE", "0.45"),
}


def _get_cached(key: str) -> str | None:
    """Read from in-process cache if still valid."""
    if key in _param_cache:
        value, ts = _param_cache[key]
        if time.time() - ts < _CACHE_TTL:
            return value
    return None


def _set_cached(key: str, value: str) -> None:
    _param_cache[key] = (value, time.time())


async def _fetch_from_system_params(param_key: str) -> str | None:
    """Read a single param from ArangoDB via Rust API Gateway."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{_GATEWAY_URL}/api/v1/system-params/{param_key}",
            )
            if resp.status_code == 200:
                data = resp.json()
                return str(data.get("data", {}).get("param_value", ""))
    except Exception as e:
        logger.warning("[llm_client] Failed to read param %s from system_params: %s", param_key, e)
    return None


async def _resolve_intent_model() -> str:
    """Resolve the intent LLM model: ArangoDB → env fallback → known-good default."""
    cached = _get_cached("intent.small_model_name")
    if cached is not None:
        return cached

    value = await _fetch_from_system_params("intent.small_model_name")
    if not value:
        env_key, default = _PARAM_FALLBACKS["intent.small_model_name"]
        value = os.getenv(env_key, default)

    _set_cached("intent.small_model_name", value)
    logger.info("[llm_client] Resolved intent model: %s", value)
    return value


async def _resolve_temperature() -> float:
    """Resolve LLM temperature: ArangoDB → env fallback."""
    cached = _get_cached("intent.small_model_temperature")
    if cached is not None:
        return float(cached)

    value = await _fetch_from_system_params("intent.small_model_temperature")
    if not value:
        _, default = _PARAM_FALLBACKS["intent.small_model_temperature"]
        value = os.getenv("AIQ_TEMPERATURE", default)

    _set_cached("intent.small_model_temperature", value)
    return float(value)


def invalidate_cache(param_key: str | None = None) -> None:
    """Clear cached config — single key or all intent params."""
    if param_key:
        _param_cache.pop(param_key, None)
    else:
        _param_cache.clear()


class InquiryLLMClient:
    """LLM client for AIQ inquiry analysis."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        """Initialize client. base_url from env; model resolved lazily on first analyze()."""
        self._base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self._model_override = model
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def analyze(self, request: LLMAnalysisRequest) -> LLMAnalysisResponse:
        model = self._model_override or await _resolve_intent_model()
        temperature = await _resolve_temperature()
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(request)

        for attempt in range(2):
            try:
                response = await self._client.post(
                    f"{self._base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": temperature},
                    },
                )
                response.raise_for_status()
                payload: object = response.json()
                content = _extract_message_content(payload)
                if content is None:
                    return self._fallback_response(request, "LLM response missing message content.")
                return self._parse_response(content, request)
            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt == 1:
                    return self._fallback_response(request, "LLM request timeout or connection error.")
            except (httpx.HTTPError, ValueError, JSONDecodeError):
                return self._fallback_response(request, "LLM returned invalid inquiry payload.")

        return self._fallback_response(request, "LLM analysis fallback triggered.")

    def _build_system_prompt(self) -> str:
        """Build the system prompt for strict inquiry analysis."""
        return (
            "你是 AIBox-TH 艾企助手的意圖分析引擎。\n"
            "請根據 working context、query 與 candidate seeds，推理最可能的使用者意圖。\n"
            "可用 ExecutionPath 選項如下：\n"
            "- knowledge_search: 需要知識庫或文件檢索\n"
            "- operation_guide: 需要操作步驟或使用指引\n"
            "- route_to_data: 需要資料查詢、資料表或分析路由\n"
            "- todo_generate: 需要拆解任務、待辦或執行計畫\n"
            "- llm_answer: 可直接由一般 LLM 回覆\n"
            "- web_fallback: 需要外部網路資訊補充\n"
            "- tool_call: 需要觸發可能有副作用的工具或系統動作\n"
            "輸出必須是嚴格 JSON，且符合 LLMAnalysisResponse schema。\n"
            "限制：\n"
            "1. hypotheses 最多 3 個\n"
            "2. 每個 confidence 必須介於 0.0 到 1.0\n"
            "3. 必須提供 boundary_status 與需要時的 suggested_questions\n"
            "4. 僅輸出 JSON，不要附加 markdown 或說明文字"
        )

    def _build_user_prompt(self, request: LLMAnalysisRequest) -> str:
        """Build the user prompt payload."""
        candidate_seeds_json = json.dumps(request.candidate_seeds, ensure_ascii=False)
        query_text = request.query or ""
        return (
            "請分析以下輸入並輸出 JSON。\n"
            f"working_context_json: {request.working_context_json}\n"
            f"query: {query_text}\n"
            f"candidate_seeds: {candidate_seeds_json}"
        )

    def _parse_response(
        self,
        content: str,
        request: LLMAnalysisRequest,
    ) -> LLMAnalysisResponse:
        try:
            raw: object = json.loads(content)
        except JSONDecodeError:
            return self._fallback_response(request, "LLM JSON parse failure.")

        try:
            return LLMAnalysisResponse.model_validate(raw)
        except ValueError:
            return self._best_effort_response(raw, request)

    def _best_effort_response(
        self,
        raw: object,
        request: LLMAnalysisRequest,
    ) -> LLMAnalysisResponse:
        """Handle LLM responses that don't match the strict schema."""
        if not isinstance(raw, dict):
            return self._fallback_response(request, "LLM returned non-dict payload.")

        timestamp = int(time.time())
        hypotheses: list[Hypothesis] = []
        raw_hypotheses = raw.get("hypotheses") or raw.get("results") or []
        for item in raw_hypotheses:
            if not isinstance(item, dict):
                continue
            hypothesis_raw = item.get("hypothesis") or item.get("intent_label") or item.get("label") or "unknown"
            confidence = float(item.get("confidence") or 0.3)
            execution_path_raw = item.get("execution_path") or item.get("path") or "llm_answer"
            try:
                exec_path = ExecutionPath(execution_path_raw)
            except ValueError:
                exec_path = ExecutionPath.LLM_ANSWER
            hypotheses.append(Hypothesis(
                id=f"he-{timestamp}-{len(hypotheses)}",
                intent_label=hypothesis_raw,
                execution_path=exec_path,
                confidence=confidence,
                evidence_chain=[],
                parameters={},
            ))

        if not hypotheses:
            return self._fallback_response(request, "LLM returned no valid hypotheses.")

        bs_raw = raw.get("boundary_status") or raw.get("boundary") or {}
        bs_status_str = str(bs_raw) if not isinstance(bs_raw, dict) else bs_raw.get("status") or "insufficient"
        try:
            bs_status = BoundaryStatusEnum(bs_status_str)
        except ValueError:
            bs_status = BoundaryStatusEnum.INSUFFICIENT

        suggested = raw.get("suggested_questions") or raw.get("questions") or []
        boundary_status = BoundaryStatus(
            status=bs_status,
            missing_dimensions=[],
            suggested_questions=suggested if isinstance(suggested, list) else [],
        )

        return LLMAnalysisResponse(
            hypotheses=hypotheses,
            boundary_status=boundary_status,
            suggested_questions=suggested if isinstance(suggested, list) else [],
            reasoning=raw.get("reasoning") or "",
        )

    def _fallback_response(
        self,
        request: LLMAnalysisRequest,
        reason: str,
    ) -> LLMAnalysisResponse:
        """Return a conservative fallback result when LLM parsing fails."""
        timestamp = int(time.time())
        evidence_chain: list[Evidence] = []
        if request.query:
            evidence_chain.append(
                Evidence(
                    source="query",
                    signal=request.query,
                    contribution=0.3,
                    timestamp=timestamp,
                )
            )

        fallback_hypothesis = Hypothesis(
            id=f"fallback-{timestamp}",
            intent_label="general_assistance",
            execution_path=ExecutionPath.LLM_ANSWER,
            confidence=0.3,
            evidence_chain=evidence_chain,
            parameters={"fallback_reason": reason},
        )
        return LLMAnalysisResponse(
            hypotheses=[fallback_hypothesis],
            boundary_status=BoundaryStatus(
                status=BoundaryStatusEnum.INSUFFICIENT,
                missing_dimensions=["intent_specificity"],
                suggested_questions=["請補充你希望完成的具體目標或輸出內容。"],
            ),
            suggested_questions=["請補充你希望完成的具體目標或輸出內容。"],
            reasoning=reason,
        )


def _extract_message_content(payload: object) -> str | None:
    """Extract chat message content from Ollama response payload."""
    if not isinstance(payload, dict):
        return None

    message = payload.get("message")
    if not isinstance(message, dict):
        return None

    content = message.get("content")
    return content if isinstance(content, str) else None
