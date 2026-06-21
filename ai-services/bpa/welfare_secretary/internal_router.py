"""
@file        業務平台助手 — 場景二：內部工作助理
@description 業務人員專用，可查詢 ERP/CRM/Timeline，執行代理問候、群發等操作
@lastUpdate  2026-06-19
@author      Sisyphus
@version     1.0.0
"""

import logging
import time
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel

from bpa.welfare_secretary.router import ChatRequest, ChatResponse, call_llm, _conversations, _MAX_TURNS
from bpa.welfare_secretary.config import get_model_config, SYSTEM_PROMPT_INTERNAL

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Welfare Secretary - Internal"])

_intent_cache: dict[str, tuple[list[dict], float]] = {}
_INTENT_CACHE_TTL = 300
_pending_greeting_ops: dict[str, dict] = {}  # sid → pending operation


async def _load_internal_intents() -> list[dict]:
    """從 intent_catalog 載入內部助理場景的意圖"""
    import base64
    import httpx
    from bpa.welfare_secretary.config import ARANGO_URL, ARANGO_DB, ARANGO_USER, ARANGO_PASSWORD

    now = time.time()
    agent_key = "welfare_secretary"
    cached = _intent_cache.get(agent_key)
    if cached and now - cached[1] < _INTENT_CACHE_TTL:
        return cached[0]

    auth_cred = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {__import__('base64').b64encode(auth_cred.encode()).decode()}",
    }
    aql = """FOR i IN intent_catalog
             FILTER i.agent_key_name == @key AND i.status == 'enabled' AND i.scope == 'internal'
             SORT i.priority DESC
             RETURN i"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": aql, "bindVars": {"key": agent_key}},
                headers=headers,
            )
            if resp.status_code in (200, 201):
                intents = resp.json().get("result", [])
                _intent_cache[agent_key] = (intents, now)
                return intents
    except Exception as e:
        logger.warning(f"[InternalRouter] Intent load failed: {e}")
    return []


async def classify_internal_intent(msg: str) -> tuple[str, str]:
    """內部助理意圖分類（合併為 4 大類）"""
    data_keywords = ["報價", "訂單", "出貨", "庫存", "ERP", "查詢", "客戶", "聯絡人", "電話", "地址", "CRM", "timeline", "歷史", "活動", "互動記錄", "歷程", "合約", "市場", "業績", "銷售", "分析", "報表"]
    send_keywords = ["問候", "早安", "祝福", "賀詞", "發送問候", "群發", "公告", "通知", "宣傳", "發送給", "促銷", "優惠", "排程"]
    visit_keywords = ["行程", "拜訪", "預約", "安排", "估程", "維保", "保養"]

    if any(kw in msg for kw in data_keywords):
        return ("data_query", "公司資料查詢")
    if any(kw in msg for kw in send_keywords):
        return ("send_message", "發送訊息")
    if any(kw in msg for kw in visit_keywords):
        return ("schedule_visit", "行程安排")

    try:
        intents = await _load_internal_intents()
        for intent in intents:
            patterns = intent.get("nl_patterns") or []
            if any(kw in msg for kw in patterns):
                return (intent.get("name", "general_chat"), intent.get("description", ""))
    except Exception:
        pass

    return ("general_chat", "")


CONFIRM_KEYWORDS = ["好", "可以", "確認", "是", "執行", "對", "沒錯", "yes", "ok", "確定", "要"]


async def handle_internal_message(request: ChatRequest, identity: dict | None = None, persona_prefix: str = "") -> ChatResponse:
    """處理內部業務人員訊息"""
    msg = request.message
    sid = request.session_id
    agent_key = request.agent_key
    history = _conversations.get(sid, [])
    identity = identity or {}
    business_user = identity.get("business_user", {})

    # 檢查是否有待確認的問候設定操作
    pending = _pending_greeting_ops.get(sid)
    if pending and any(kw in msg for kw in CONFIRM_KEYWORDS):
        from skills.greeting_settings.skill import execute as settings_skill
        result = await settings_skill({**pending, "dry_run": False})
        del _pending_greeting_ops[sid]
        reply_text = result.get("message", "設定已更新")
        return ChatResponse(session_id=sid, reply=f"✅ {reply_text}", intent="greeting_settings")

    # 意圖分類
    intent, hint = await classify_internal_intent(msg)

    # 資料查詢（ERP/CRM/Timeline/知識庫）→ 導向 Data Agent
    if intent == "data_query":
        return await _route_to_data_agent(sid, msg, agent_key)

    # 發送訊息（問候/促銷/公告排程）
    if intent == "send_message":
        return await _handle_greeting_internal(sid, msg, agent_key, identity)

    # 行程安排 → 導向 visit_plan skill
    if intent == "schedule_visit":
        return await _handle_schedule_visit(sid, msg, agent_key)

    # 一般對話 → LLM（含知識庫全文權限）
    return await _handle_general_chat(sid, msg, history, agent_key, hint=hint, persona_prefix=persona_prefix)


async def _route_to_data_agent(sid: str, msg: str, agent_key: str) -> ChatResponse:
    """導向 Data Agent 進行 ERP 查詢"""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "http://localhost:8011/da/ragic/chat",
                json={"session_id": sid, "message": msg, "user_id": "internal"},
            )
            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("reply") or data.get("response") or str(data)
                return ChatResponse(session_id=sid, reply=reply, intent="erp_query")
    except Exception as e:
        logger.warning(f"[InternalRouter] Data Agent call failed: {e}")

    # fallback: 直接 LLM
    model, api_base, api_key, system_prompt = await get_model_config(agent_key)
    messages = [
        {"role": "system", "content": f"{system_prompt}\n\n注意：目前無法連接到 ERP 查詢系統，請告知使用者暫時無法查詢。"},
        {"role": "user", "content": msg},
    ]
    reply = await call_llm(messages, model, api_base, api_key)
    return ChatResponse(session_id=sid, reply=reply, intent="data_query")


async def _handle_schedule_visit(sid: str, msg: str, agent_key: str) -> ChatResponse:
    """行程安排 → visit_plan skill"""
    from skills.visit_plan.skill import execute as visit_skill

    result = await visit_skill({"query": msg})
    reply = result.get("message", "行程已記錄")
    return ChatResponse(session_id=sid, reply=reply, intent="schedule_visit")


async def _handle_greeting_internal(sid: str, msg: str, agent_key: str, identity: dict | None = None) -> ChatResponse:
    """代理客戶問候 — 分流：設定指令 → greeting_settings，生成指令 → greeting_engine"""
    identity = identity or {}
    business_user_key = identity.get("business_user_key", "")

    # 設定相關關鍵字 → 導向 greeting_settings skill（先 dry_run 預覽）
    settings_keywords = ["設定", "排程", "模板", "啟用", "停用", "查看", "設定檔", "配置"]
    if any(kw in msg for kw in settings_keywords):
        from skills.greeting_settings.skill import execute as settings_skill

        result = await settings_skill({
            "business_user_key": business_user_key,
            "instruction": msg,
            "dry_run": True,
        })
        if result.get("dry_run"):
            _pending_greeting_ops[sid] = {
                "business_user_key": business_user_key,
                "action": result.get("action"),
                "greeting_type": result.get("greeting_type"),
                "settings": result.get("settings", {}),
            }
            preview = result.get("preview", "即將更新問候設定")
            reply = f"📋 {preview}\n\n請確認是否執行？（回覆「好」、「確認」或「是」）"
        else:
            reply = result.get("message", "設定已更新")
        return ChatResponse(session_id=sid, reply=reply, intent="greeting_settings")

    # 一般問候生成 → greeting_engine
    from skills.greeting_engine.skill import execute as greeting_skill

    result = await greeting_skill({
        "customer_name": "客戶",
        "greeting_type": "morning",
        "extra_context": msg,
    })
    greeting_text = result.get("greeting_text", "您好！")

    model, api_base, api_key, system_prompt = await get_model_config(agent_key)
    messages = [
        {"role": "system", "content": "你正在協助業務人員準備發送給客戶的問候。請根據以下生成的問候內容，給予業務人員適當的建議。"},
        {"role": "user", "content": f"已生成問候內容：{greeting_text}\n\n請幫我潤飾後回覆。"},
    ]
    reply = await call_llm(messages, model, api_base, api_key)
    return ChatResponse(session_id=sid, reply=f"✅ 已生成問候內容：\n\n{greeting_text}\n\n---\n{reply}", intent="greeting_customer")


async def _handle_general_chat(
    sid: str, msg: str, history: list, agent_key: str, hint: str = "", persona_prefix: str = ""
) -> ChatResponse:
    """一般對話 → LLM"""
    model, api_base, api_key, system_prompt = await get_model_config(agent_key)

    final_system = system_prompt
    if persona_prefix:
        final_system = f"{persona_prefix}\n\n{system_prompt}"
    messages: list[dict] = [{"role": "system", "content": final_system}]
    if hint:
        messages.append({"role": "system", "content": f"[意圖提示] {hint}"})

    # 載入持久化歷史
    try:
        from shared.conversation import QueryEngine
        engine = QueryEngine()
        db_all = await engine.get_history(sid, limit=100, include_metadata=False)
        if db_all:
            history = db_all[-_MAX_TURNS * 2:]
    except Exception:
        pass

    messages.extend(history[-_MAX_TURNS:])
    messages.append({"role": "user", "content": msg})

    reply = await call_llm(messages, model, api_base, api_key)

    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": reply})
    _conversations[sid] = history[-_MAX_TURNS * 2:]

    _persist_conversation(sid, msg, reply)

    return ChatResponse(session_id=sid, reply=reply, intent="general_chat")


def _persist_conversation(sid: str, msg: str, reply: str):
    """持久化對話到 ArangoDB"""
    try:
        from shared.conversation import ConversationStorage
        import asyncio
        storage = ConversationStorage()
        asyncio.ensure_future(storage.save_message(session_id=sid, platform="agent", role="user", message=msg))
        asyncio.ensure_future(storage.save_message(session_id=sid, platform="agent", role="assistant", message=reply))
    except Exception:
        pass
