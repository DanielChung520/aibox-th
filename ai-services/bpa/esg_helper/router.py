"""
@file        ESG小幫手 — FastAPI Router
@description ESGen 意圖分類 + LLM 回應（支援 agent_key 動態設定）
             支援 LINE 平台訊息處理。
             Phase 1 支援 LINE 文字訊息。
@lastUpdate  2026-05-16 00:02:00
@author      System
@version     1.0.0
"""

import logging
import os
import time
import base64
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ESG Helper"])
_conversations: dict[str, list[dict[str, str]]] = {}
MAX_TURNS = 10

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")

FALLBACK_MODEL = os.getenv("ESG_HELPER_MODEL", "gemini-2.5-flash")
FALLBACK_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
FALLBACK_SYSTEM_PROMPT = (
    "你是 ESG（環境、社會、治理）領域的專業 AI 助理，名為「ESG小幫手」。\n"
    "你的職責：\n"
    "1. 回答 ESG 相關問題，包含碳排放計算、碳足跡、溫室氣體盤查、永續報告書、CSR、綠色供應鏈、循環經濟等\n"
    "2. 協助查詢 ESG 數據、指標與評級\n"
    "3. 提供 ESG 法規與標準的最新資訊（如 GRI、SASB、TCFD、IFRS S1/S2、歐盟CSRD、台灣金管會永續發展路徑圖）\n"
    "4. 引導使用者了解如何改善企業的 ESG 績效與 sustainability 策略\n"
    "5. 解釋 ESG 投資、綠色金融、影響力投資等概念\n\n"
    "請用繁體中文回答，語氣專業且親切。回答應具體、有參考價值，並在適當時提供數據來源或進一步建議。"
)


class ChatRequest(BaseModel):
    session_id: str
    message: str
    user_id: str = "anonymous"
    agent_key: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    sources: list[str] = []


async def query_arango(aql: str, bind_vars: dict | None = None) -> list[dict]:
    auth_cred = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(auth_cred.encode()).decode()}",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": aql, "bindVars": bind_vars or {}},
            headers=headers,
        )
        if resp.status_code not in (200, 201):
            return []
        return resp.json().get("result", [])


async def resolve_llm_config(agent_key: str | None) -> tuple[str, str, str, str]:
    """從 agents 集合載入 LLM 設定 + system_prompt，若無則使用 fallback"""
    model = FALLBACK_MODEL
    api_base = FALLBACK_OLLAMA_URL
    system_prompt = FALLBACK_SYSTEM_PROMPT
    api_key = ""

    if not agent_key:
        return model, api_base, system_prompt, api_key

    agents = await query_arango(
        "FOR a IN agents FILTER a._key == @key LIMIT 1 RETURN a",
        {"key": agent_key},
    )
    if not agents:
        return model, api_base, system_prompt, api_key

    agent = agents[0]
    agent_model = agent.get("llm_model") or ""
    if agent_model:
        model = agent_model
    agent_prompt = agent.get("system_prompt") or ""
    if agent_prompt:
        system_prompt = agent_prompt

    # 從 model_providers 查 model 對應的 base_url 與 api_key
    providers = await query_arango(
        "FOR p IN model_providers FILTER p.status == 'enabled' RETURN p",
    )
    for p in providers:
        p_models = p.get("models") or []
        for m in p_models:
            if isinstance(m, dict) and m.get("model_id") == model:
                api_base = (p.get("base_url") or "").rstrip("/")
                api_key = p.get("api_key") or ""
                break
        if api_base != FALLBACK_OLLAMA_URL:
            break

    return model, api_base, system_prompt, api_key


async def call_llm(messages: list[dict], model: str, api_base: str, api_key: str = "") -> str:
    """支援 Ollama / OpenAI-compatible API"""
    if "localhost" in api_base or "127.0.0.1" in api_base:
        url = f"{api_base}/api/chat"
        payload = {"model": model, "messages": messages, "stream": False}
        async with httpx.AsyncClient(timeout=180.0) as c:
            r = await c.post(url, json=payload)
            if r.status_code == 200:
                return str(r.json().get("message", {}).get("content", ""))
    else:
        url = f"{api_base}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {"model": model, "messages": messages, "stream": False}
        async with httpx.AsyncClient(timeout=180.0) as c:
            r = await c.post(url, json=payload, headers=headers)
            if r.status_code == 200:
                choices = r.json().get("choices", [])
                if choices:
                    return str(choices[0].get("message", {}).get("content", ""))
    return "抱歉，暫時無法處理您的請求。請稍後再試。"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    start = time.monotonic()
    msg = request.message
    sid = request.session_id
    agent_key = request.agent_key
    history = _conversations.get(sid, [])

    # 內建能力：時間查詢
    time_keywords = ["時間", "幾點", "日期", "今天幾號", "星期幾", "現在", "time", "date"]
    if any(k in msg for k in time_keywords):
        now = datetime.now(timezone.utc).astimezone()
        tw_now = now.astimezone(__import__("zoneinfo", fromlist=[""]).ZoneInfo("Asia/Taipei"))
        time_reply = f"現在時間是 {tw_now.strftime('%Y年%m月%d日 %H:%M:%S')}（台灣時間，UTC+8）"
        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": time_reply})
        _conversations[sid] = history[-MAX_TURNS * 2:]
        return ChatResponse(session_id=sid, reply=time_reply, sources=[])

    # 從 bot_chat_sessions 載入持久化歷史
    try:
        from shared.conversation import QueryEngine
        engine = QueryEngine()
        db_all = await engine.get_history(sid, limit=100, include_metadata=False)
        if db_all:
            history = db_all[-MAX_TURNS * 2:]
    except Exception:
        pass

    model, api_base, system_prompt, api_key = await resolve_llm_config(agent_key)

    msgs: list[dict] = [{"role": "system", "content": system_prompt}]
    msgs.extend(history[-MAX_TURNS:])
    msgs.append({"role": "user", "content": msg})

    reply = await call_llm(msgs, model, api_base, api_key)

    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": reply})
    _conversations[sid] = history[-MAX_TURNS * 2:]

    # 持久化到 bot_chat_sessions
    try:
        from shared.conversation import ConversationStorage
        storage = ConversationStorage()
        await storage.save_message(session_id=sid, platform="agent", role="user", message=msg)
        await storage.save_message(session_id=sid, platform="agent", role="assistant", message=reply)
    except Exception:
        pass

    elapsed = time.monotonic() - start
    logger.info(f"[ESG] agent_key={agent_key} model={model} reply_len={len(reply)} elapsed={elapsed:.1f}s")
    return ChatResponse(session_id=sid, reply=reply, sources=[])
