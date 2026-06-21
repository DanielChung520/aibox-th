"""
@file        業務平台助手 — 場景一：客戶端 LINE Bot
@description Intent 分類 + L0-L4 權限檢查 + 安全回覆
@lastUpdate  2026-06-20
@author      Sisyphus
@version     1.1.0
"""

import logging
import time
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter

from bpa.welfare_secretary.router import ChatRequest, ChatResponse, call_llm, _conversations, _MAX_TURNS
from bpa.welfare_secretary.config import get_model_config

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Welfare Secretary - Customer"])

# ── Intent 分類 ──

L3_L4_KEYWORDS = [
    "報價", "金額", "價格", "多少錢", "費用", "成本",
    "合約", "條款", "折扣", "利潤",
    "下單", "改單", "取消訂單", "刪除訂單", "訂購",
]

GREETING_KEYWORDS = ["早安", "午安", "晚安", "你好", "嗨", "hello", "hi", "您好"]

_intent_cache: dict[str, tuple[list[dict], float]] = {}
_INTENT_CACHE_TTL = 300


async def _load_customer_intents() -> list[dict]:
    """從 intent_catalog 載入客戶端場景的意圖"""
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
             FILTER i.agent_key_name == @key AND i.status == 'enabled' AND i.scope == 'customer'
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
        logger.warning(f"[CustomerRouter] Intent load failed: {e}")
    return []


async def classify_customer_intent(msg: str) -> tuple[str, str]:
    """客戶端意圖分類（rule-based + intent_catalog）"""
    # Step 1: L3/L4 機密攔截（rule-based，不經 LLM）
    msg_lower = msg.lower()
    if any(kw in msg for kw in L3_L4_KEYWORDS):
        return ("confidential_query", "客戶詢問機密資訊")

    # Step 2: 簡單規則
    if any(msg.startswith(kw) or msg == kw for kw in GREETING_KEYWORDS):
        return ("greeting", "客戶問候")

    # Step 3: 從 intent_catalog 動態比對
    try:
        intents = await _load_customer_intents()
        for intent in intents:
            patterns = intent.get("nl_patterns") or []
            if any(kw in msg for kw in patterns):
                return (intent.get("name", "general_chat"), intent.get("description", ""))
    except Exception as e:
        logger.warning(f"[CustomerRouter] Intent catalog match failed: {e}")

    return ("general_chat", "")


# ── Handler ──


async def handle_customer_message(request: ChatRequest, identity: dict | None = None, persona_prefix: str = "") -> ChatResponse:
    """處理客戶端訊息，含權限分級檢查"""
    msg = request.message
    sid = request.session_id
    agent_key = request.agent_key
    history = _conversations.get(sid, [])
    identity = identity or {}
    business_user = identity.get("business_user", {})

    # 意圖分類
    intent, hint = await classify_customer_intent(msg)

    # L3/L4 機密查詢 → 依身分分流：業務本人→subagent，其他→婉拒+記錄+通知
    if intent == "confidential_query":
        from skills.confidential_handler.skill import execute as confidential_skill

        customer_name = business_user.get("name", "") or sid.split(":")[-1] if ":" in sid else "客戶"
        skill_result = await confidential_skill({
            "message": msg,
            "business_user_key": identity.get("business_user_key", ""),
            "role": identity.get("role", ""),
            "channel_key": identity.get("channel_key", ""),
            "session_id": sid,
            "customer_name": customer_name,
        })

        action = skill_result.get("action", "polite_refuse")

        if action == "route_to_subagent":
            return await _route_to_data_agent(sid, msg, agent_key, "confidential_query")

        reply = skill_result.get("reply", "您的詢問我收到了，我會轉達主管，請主管盡快回應您。")
        _save_conversation(sid, msg, reply, history)
        logger.info(f"[CustomerRouter] intent=confidential_query session={sid} action=polite_refuse")

        if skill_result.get("should_notify", False):
            business_line_id = business_user.get("line_id", "")
            if business_line_id:
                _notify_business(customer_name, skill_result.get("query_type", "機密資訊"), business_line_id)

        return ChatResponse(session_id=sid, reply=reply, intent=intent)

    # 問候處理

    if intent == "greeting":
        reply = await _handle_greeting_customer(msg)
        _save_conversation(sid, msg, reply, history)
        return ChatResponse(session_id=sid, reply=reply, intent=intent)

    # Timeline 查詢 → 摘要級
    if intent == "timeline_query":
        return await _handle_timeline_query(sid, msg, agent_key, identity)

    # 公司介紹 / 業務介紹 / 台灣長照
    if intent == "company_intro":
        return await _handle_company_intro(sid, msg, agent_key, persona_prefix)

    # 圖片處理（名片、問候圖片）
    if request.attachment and request.attachment.get("image_base64"):
        return await _handle_image_attachment(sid, request.attachment["image_base64"], agent_key, identity)

    # 不在正面表列 → LLM 先回答，背景記錄意圖
    if intent == "general_chat":
        chat_resp = await _handle_general_chat(sid, msg, history, agent_key, hint=hint, persona_prefix=persona_prefix)
        customer_name = business_user.get("name", "") or sid.split(":")[-1] if ":" in sid else "客戶"
        asyncio.ensure_future(_record_and_notify(
            message=msg, business_user_key=identity.get("business_user_key", ""),
            channel_key=identity.get("channel_key", ""),
            customer_name=customer_name, session_id=sid, business_user=business_user,
        ))
        return chat_resp


async def _handle_company_intro(sid: str, msg: str, agent_key: str, persona_prefix: str = "") -> ChatResponse:
    """公司/業務介紹：先查知識庫，再用 LLM 回答"""
    import httpx
    kb_context = ""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("http://127.0.0.1:8011/ka/hybrid/search", json={
                "query": msg, "collection": "knowledge_default", "top_k": 3,
                "root_id": "kb_1782029005450",
            })
            if resp.status_code == 200:
                hits = resp.json().get("results", [])
                texts = [h["content"].strip()[:400] for h in hits if h.get("content") and len(h["content"].strip()) > 30]
                if texts:
                    kb_context = "\n\n參考資料：\n" + "\n---\n".join(texts[:2])
    except Exception:
        pass

    model, api_base, api_key, system_prompt = await get_model_config(agent_key)
    identity_prefix = persona_prefix + "\n\n" if persona_prefix else ""
    messages = [
        {"role": "system", "content": f"{identity_prefix}{system_prompt}\n\n你是真人客服，語氣溫暖自然。請根據資料回答，不確定的就誠實說不知道。{kb_context}"},
        {"role": "user", "content": msg},
    ]
    reply = await call_llm(messages, model, api_base, api_key, temperature=0.1)
    if not reply:
        from skills.customer_safe_reply.skill import execute as safe_reply
        fb = await safe_reply({"message": msg, "customer_name": "客戶"})
        reply = fb.get("reply_text", "感謝您的詢問！")
    history = _conversations.get(sid, [])
    _save_conversation(sid, msg, reply, history)
    _persist_conversation(sid, msg, reply)
    return ChatResponse(session_id=sid, reply=reply, intent="company_intro")


async def _record_and_notify(
    message: str, business_user_key: str, channel_key: str,
    customer_name: str, session_id: str, business_user: dict,
):
    """背景記錄意圖，僅高度相關時通知業務"""
    try:
        from skills.customer_intent_recorder.skill import execute as intent_record
        result = await intent_record({"message": message, "business_user_key": business_user_key,
            "channel_key": channel_key, "customer_name": customer_name, "session_id": session_id})
        if result.get("should_notify", False):
            business_line_id = business_user.get("line_id", "")
            if business_line_id:
                _notify_business(customer_name, result.get("analysis",{}).get("inferred_intent","客戶詢問"), business_line_id)
    except Exception:
        pass


async def _handle_greeting_customer(msg: str) -> str:
    """客戶問候回應"""
    from skills.greeting_engine.skill import execute as greeting_skill

    result = await greeting_skill({
        "customer_name": "客戶",
        "greeting_type": "morning",
        "extra_context": msg,
    })
    return result.get("greeting_text", "您好！祝您有美好的一天！")


async def _handle_timeline_query(sid: str, msg: str, agent_key: str, identity: dict | None = None) -> ChatResponse:
    """客戶查詢 Timeline（僅回傳摘要）"""
    from bpa.welfare_secretary.timeline import query_timeline

    bu = (identity or {}).get("business_user", {})
    bu_key = (identity or {}).get("business_user_key", "")
    customer_id = bu.get("customer_id", f"customer_from_{sid.replace(':', '_')}")

    result = await query_timeline(customer_id, level="summary")
    events = result.get("events", [])

    if not events:
        reply = "目前尚無與您相關的互動記錄。"
        return ChatResponse(session_id=sid, reply=reply, intent="timeline_query")

    # 僅回傳摘要
    summary_lines = []
    for e in events[-5:]:  # 最近 5 筆
        summary_lines.append(f"- {e.get('timestamp', '')[:10]}：{e.get('summary', '')}")
    reply = "以下是您近期的互動摘要：\n" + "\n".join(summary_lines)
    return ChatResponse(session_id=sid, reply=reply, intent="timeline_query")


async def _handle_image_attachment(sid: str, image_base64: str, agent_key: str, identity: dict | None = None) -> ChatResponse:
    """處理客戶傳送的圖片（名片 OCR / 問候圖片）"""
    from skills.image_processor.skill import execute as image_skill

    result = await image_skill({
        "image_base64": image_base64,
        "mode": "auto",
        "customer_name": "客戶",
    })

    classification = result.get("classification", "other")

    if classification == "business_card":
        reply = "已收到您的名片資料，將轉交業務同仁確認後建檔。謝謝您！"
        structured = result.get("structured_data")
        if structured:
            bu_key = (identity or {}).get("business_user_key", "")
            ch_key = (identity or {}).get("channel_key", "")
            saved = await _save_crm_contact(bu_key, ch_key, sid, structured)
            logger.info(f"[CustomerRouter] Business card saved={saved} for business_user={bu_key} channel={ch_key}")

    elif classification == "greeting":
        reply = result.get("reply_text", "謝謝您的問候！祝您一切順心！")

    else:
        reply = result.get("description", "已收到您的圖片，謝謝分享！")

    return ChatResponse(session_id=sid, reply=reply, intent=f"image_{classification}")


async def _save_crm_contact(business_user_key: str, channel_key: str, session_id: str, ocr_data: dict) -> bool:
    """將 OCR 名片寫入 crm_contacts 集合，含業務綁定與 channel 來源"""
    import base64
    import httpx
    import uuid
    from bpa.welfare_secretary.config import ARANGO_URL, ARANGO_DB, ARANGO_USER, ARANGO_PASSWORD

    auth_cred = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(auth_cred.encode()).decode()}",
    }
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "_key": str(uuid.uuid4()),
        "name_cn": ocr_data.get("name"),
        "source": "line_card",
        "line_status": "connected",
        "owner_key": business_user_key,
        "channel_key": channel_key,
        "organizations": [],
        "phones": [],
        "emails": [],
        "card_images": [],
        "notes": f"來源：LINE 名片 OCR（session: {session_id}）",
        "created_at": now,
        "updated_at": now,
    }
    if ocr_data.get("company") or ocr_data.get("title"):
        org = {}
        if ocr_data.get("company"):
            org["name"] = ocr_data["company"]
        if ocr_data.get("title"):
            org["title"] = ocr_data["title"]
        org["is_primary"] = True
        doc["organizations"] = [org]
    if ocr_data.get("phone"):
        doc["phones"] = [{"number": ocr_data["phone"], "code": "+886", "type": "mobile", "is_primary": True}]
    if ocr_data.get("email"):
        doc["emails"] = [{"address": ocr_data["email"], "type": "work", "is_primary": True}]
    if ocr_data.get("address"):
        doc["notes"] = (doc.get("notes", "") + f"\n地址：{ocr_data['address']}").strip()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/crm_contacts",
                json=doc,
                headers=headers,
            )
            if resp.status_code in (200, 201, 202):
                logger.info(f"[CustomerRouter] CRM contact saved: {doc.get('name_cn')} for owner={business_user_key}")
                return True
            logger.warning(f"[CustomerRouter] Failed to save CRM contact: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"[CustomerRouter] CRM contact save error: {e}")
    return False


async def _route_to_data_agent(sid: str, msg: str, agent_key: str, intent_label: str = "data_query") -> ChatResponse:
    """將查詢導向 Data Agent（供業務本人透過客戶端管道查詢 ERP 資料）"""
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
                return ChatResponse(session_id=sid, reply=reply, intent=intent_label)
    except Exception as e:
        logger.warning(f"[CustomerRouter] Data Agent call failed: {e}")

    model, api_base, api_key, system_prompt = await get_model_config(agent_key)
    messages = [
        {"role": "system", "content": f"{system_prompt}\n\n注意：目前無法連接到 ERP 查詢系統，請告知使用者暫時無法查詢。"},
        {"role": "user", "content": msg},
    ]
    reply = await call_llm(messages, model, api_base, api_key)
    return ChatResponse(session_id=sid, reply=reply, intent=intent_label)


async def _handle_general_chat(
    sid: str, msg: str, history: list, agent_key: str, hint: str = "", persona_prefix: str = ""
) -> ChatResponse:
    """一般對話 → 先查知識庫輔助，再用 LLM 回答"""
    model, api_base, api_key, system_prompt = await get_model_config(agent_key)
    final_system = system_prompt
    if persona_prefix:
        final_system = f"{persona_prefix}\n\n{system_prompt}"
    if hint:
        final_system += f"\n\n[意圖提示] {hint}"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post("http://127.0.0.1:8011/ka/hybrid/search", json={
                "query": msg, "collection": "knowledge_default", "top_k": 2, "root_id": "kb_1782029005450",
            })
            if resp.status_code == 200:
                hits = resp.json().get("results", [])
                texts = [h["content"].strip()[:400] for h in hits if h.get("content") and len(h["content"].strip()) > 30]
                if texts:
                    final_system += "\n\n參考知識庫：\n" + "\n---\n".join(texts[:2])
    except Exception:
        pass
    try:
        from shared.conversation import QueryEngine
        engine = QueryEngine()
        db_all = await engine.get_history(sid, limit=100, include_metadata=False)
        if db_all:
            history = db_all[-_MAX_TURNS * 2:]
    except Exception:
        pass
    messages = [{"role": "system", "content": final_system}]
    messages.extend(history[-_MAX_TURNS:])
    messages.append({"role": "user", "content": msg})
    reply = await call_llm(messages, model, api_base, api_key, temperature=0.3)
    _save_conversation(sid, msg, reply, history)
    _persist_conversation(sid, msg, reply)
    return ChatResponse(session_id=sid, reply=reply, intent="general_chat")


def _save_conversation(sid: str, msg: str, reply: str, history: list):
    """儲存對話到記憶體"""
    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": reply})
    _conversations[sid] = history[-_MAX_TURNS * 2:]


def _persist_conversation(sid: str, msg: str, reply: str):
    """持久化對話到 ArangoDB"""
    try:
        from shared.conversation import ConversationStorage
        storage = ConversationStorage()
        asyncio.ensure_future(storage.save_message(session_id=sid, platform="agent", role="user", message=msg))
        asyncio.ensure_future(storage.save_message(session_id=sid, platform="agent", role="assistant", message=reply))
    except Exception:
        pass


def _notify_business(customer_name: str, query_type: str, business_line_id: str):
    """非同步通知業務人員（L3/L4 機密查詢觸發）"""
    asyncio.ensure_future(_do_notify(customer_name, query_type, business_line_id))


async def _do_notify(customer_name: str, query_type: str, business_line_id: str):
    """實際執行業務通知（非同步，不阻斷回覆流程）"""
    try:
        from skills.business_notification.skill import execute as notify

        await notify({
            "customer_name": customer_name,
            "query_type": query_type,
            "business_line_id": business_line_id,
        })
        logger.info(f"[CustomerRouter] Business notified: {customer_name} asked about {query_type}")
    except Exception as e:
        logger.warning(f"[CustomerRouter] Business notification failed: {e}")
