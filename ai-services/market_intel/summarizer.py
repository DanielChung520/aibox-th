"""
@file        market_intel/summarizer.py
@description AI 摘要 + 分析 + 策略建議 via LLM API direct call
@lastUpdate  2026-06-14
@author      Daniel Chung
@version     1.1.0
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CLOUD_MODEL: str | None = None
CLOUD_BASE: str = "https://api.deepseek.com/v1"
CLOUD_KEY: str = ""
_token_usage: dict[str, int] = {"prompt": 0, "completion": 0, "total": 0}


def get_token_usage() -> dict[str, int]:
    return dict(_token_usage)


def reset_token_usage() -> None:
    _token_usage.clear()
    _token_usage.update({"prompt": 0, "completion": 0, "total": 0})


async def _get_cloud_config() -> tuple[str, str, str]:
    """讀取 LLM 設定（market_intel.llm_provider + market_intel.llm_model）"""
    global CLOUD_MODEL, CLOUD_BASE, CLOUD_KEY
    if CLOUD_MODEL:
        return CLOUD_MODEL, CLOUD_BASE, CLOUD_KEY
    try:
        from data_agent.config_reader import get_param
        provider_key = await get_param("market_intel.llm_provider") or "deepseek"
        model_name = await get_param("market_intel.llm_model") or "deepseek-v4-flash"
        from shared.llm_resolver import resolve
        cfg = await resolve(f"{provider_key}:{model_name}")
        if cfg:
            CLOUD_MODEL = cfg.model_name
            CLOUD_BASE = cfg.endpoint or cfg.base_url
            CLOUD_KEY = cfg.api_key or ""
        else:
            CLOUD_MODEL = "deepseek-v4-flash"; CLOUD_BASE = "https://api.deepseek.com/v1/chat/completions"; CLOUD_KEY = ""
    except Exception:
        CLOUD_MODEL = "deepseek-v4-flash"; CLOUD_BASE = "https://api.deepseek.com/v1/chat/completions"; CLOUD_KEY = ""
    return CLOUD_MODEL, CLOUD_BASE, CLOUD_KEY


async def _call_llm(messages: list[dict], max_tokens: int = 800) -> str:
    """呼叫 LLM API"""
    model, endpoint, key = await _get_cloud_config()
    is_ollama = "localhost" in endpoint or "127.0.0.1" in endpoint
    prompt_tokens = sum(len(m.get("content", "")) for m in messages) // 4

    if is_ollama:
        url = endpoint.rstrip("/chat/completions") + "/api/chat"
        payload = {"model": model, "messages": messages, "stream": False, "options": {"temperature": 0.3, "num_predict": max_tokens}}
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(url, json=payload)
            if r.status_code == 200:
                text = r.json().get("message", {}).get("content", "")
                _token_usage["prompt"] += prompt_tokens
                _token_usage["completion"] += len(text) // 4
                _token_usage["total"] += prompt_tokens + len(text) // 4
                return text
    else:
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        payload = {"model": model, "messages": messages, "temperature": 0.3, "max_tokens": max_tokens}
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(endpoint, json=payload, headers=headers)
            if r.status_code == 200:
                data = r.json()
                msg = data.get("choices", [{}])[0].get("message", {})
                text = msg.get("content", "") or msg.get("reasoning_content", "") or ""
                usage = data.get("usage", {})
                pu = usage.get("prompt_tokens", 0) or prompt_tokens
                cu = usage.get("completion_tokens", 0) or (len(text) // 4)
                _token_usage["prompt"] += pu
                _token_usage["completion"] += cu
                _token_usage["total"] += pu + cu
                return text
    return ""


async def summarize_article(title: str, content: str) -> dict[str, Any]:
    """單篇新聞摘要 + 關聯性判斷 + 行動建議"""
    body = content[:2500] if len(content) > 20 else title

    prompt = f"""你是一個專業的市場分析助理，專門協助台灣福祉科技（復康巴士、福祉車、長照設備）的業務團隊掌握市場動態。

請分析以下文章，以 JSON 格式回覆：

文章標題：{title}
文章內容：{body[:2500]}

回覆 JSON（嚴格格式，不要其他文字）：
{{
  "summary": "200 字內摘要",
  "relevance": "high/medium/low",
  "relevance_reason": "為什麼這篇跟台灣福祉有關或無關（30字）",
  "key_point": "這篇最重要的資訊是什麼（50字）",
  "action": "業務團隊應該做什麼（50字，若無則 null）",
  "impact": "對業務的影響（positive/negative/neutral）"
}}"""

    try:
        text = await _call_llm([{"role": "user", "content": prompt}], max_tokens=2000)
        result = _try_parse_json(text)
        if result:
            return result
    except Exception:
        pass
    return {"summary": content[:200] or title[:200], "relevance": "low", "relevance_reason": "AI 摘要失敗", "key_point": "", "action": None, "impact": "neutral"}


async def generate_daily_report(articles: list[dict[str, Any]]) -> dict[str, Any]:
    """整合每日所有文章，產出綜合快報"""
    condensed = "\n".join(
        f"- [{a.get('relevance', 'medium')}] {a['title']}：{a.get('summary', '')[:150]}"
        for a in articles
    )

    prompt = f"""你是台灣福祉科技的市場分析長。以下是今日蒐集到的市場資訊，請整合分析：

{condensed}

以 JSON 格式回覆：
{{
  "daily_focus": "一句話總結今天最重要的市場變化（30字）",
  "key_trends": ["趨勢1", "趨勢2", "趨勢3"],
  "attention_points": ["注意事項1", "注意事項2"],
  "opportunities": ["商機1", "商機2"],
  "overall_assessment": "今日市場狀態總結（100字）"
}}"""

    try:
        text = await _call_llm([{"role": "user", "content": prompt}], max_tokens=2000)
        result = _try_parse_json(text)
        if result:
            return result
    except Exception:
        pass
    return {"daily_focus": "今日市場資訊整理完成", "key_trends": [], "attention_points": [], "opportunities": [], "overall_assessment": "AI 分析暫時無法使用。"}


def _try_parse_json(text: str) -> dict | None:
    """嘗試解析 JSON，支援從 markdown code block 或 reasoning 中提取"""
    import re, json
    text = text.strip()
    # 移除 markdown code block
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("\n", 1)[0]
    # 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 嘗試從文字中提取 {...} 區塊
    m = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if m:
        candidate = m.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    # 沒救
    return None
