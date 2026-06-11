"""
@file        訂單小秘 — FastAPI Router
@description 意圖分類（訂單文字/訂單跟進/時間/一般）+ 多 Provider LLM
             收到訂單自動建立預購單（order_preorders），支援庫存確認與跟單追蹤。
             Phase 1 僅支援 LINE。
@lastUpdate  2026-04-28 22:41:00
@author      AI Agent
@version     1.1.0
"""

import logging
import os
import time
import httpx
import base64
import json
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel
from bpa.order_secretary.skills.order_preorder_collect import execute as execute_order_inquiry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Order Secretary"])
_conversations: dict[str, list[dict[str, str]]] = {}
_intent_cache: dict[str, tuple[list[dict], float]] = {}
_INTENT_CACHE_TTL = 300
MAX_TURNS = 10

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")

FALLBACK_MODEL = os.getenv("ORDER_SECRETARY_MODEL", "qwen3-next:latest")
FALLBACK_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
FALLBACK_SYSTEM_PROMPT = "你是一個專業的「訂單小秘」，協助客戶透過 LINE 提交訂單。請用繁體中文回覆，語氣親切專業。若客戶提供訂單資訊，回覆時應包含結構化訂單摘要。若資訊不完整，友善詢問缺少的欄位。\n\n重要規則：\n1. 嚴禁自行編造產品資訊、價格、庫存資料。\n2. 產品列表只能來自系統提供的庫存資料，不可自己想像。\n3. 若系統查無產品資料，請直接告知使用者目前暫無資料，不要推薦任何產品。\n4. 若使用者詢問查詢功能以外的問題，正常回答即可，但不可編造公司產品資訊。"


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


def _format_items_for_llm(items: list[dict]) -> str:
    """將 SKL-2618-002 回傳的結構化品項轉換為親切的文字列表，交給 LLM 加上禮貌用語"""
    if not items:
        return "（目前無品項）"
    lines = []
    for i, item in enumerate(items, 1):
        name = item.get("item_name", "").strip()
        spec = item.get("spec", "").strip()
        qty = item.get("stock_qty", 0)
        unit = item.get("unit", "").strip()
        spec_str = f"（{spec}）" if spec else ""
        lines.append(f"{i}. {name}{spec_str} — 庫存 {qty:,} {unit}")
    return "\n".join(lines)


def _extract_filter_term(msg: str) -> str:
    """嘗試從使用者訊息中提取品名關鍵字（如「我要看蒜」「有薑嗎」）"""
    msg = msg.strip()
    # 移除常見問句開頭
    for prefix in ["我要看", "有", "嗎", "?", "？", "查看", "查", "看"]:
        if msg.startswith(prefix):
            msg = msg[len(prefix):]
    # 移除結尾的空白/標點
    msg = msg.strip().rstrip("?？")
    # 若剩下 2 字以上，視為品名關鍵字
    if len(msg) >= 2:
        return msg
    return ""


async def resolve_llm_config(agent_key: str | None) -> tuple[str, str, str, str]:
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
        system_prompt = f"{system_prompt}\n\n{agent_prompt}"

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
                data = r.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        return str(content)
                logger.warning(f"[LLM] no content in response: {str(data)[:200]}")
            else:
                logger.warning(f"[LLM] non-200: {r.status_code} body={r.text[:200]}")
    return "抱歉，暫時無法處理您的請求。請稍後再試。"


async def load_agent_intents(agent_key: str) -> list[dict]:
    """從 intent_catalog 載入指定 Agent 的啟用意圖，含 300s 快取"""
    now = time.time()
    cached = _intent_cache.get(agent_key)
    if cached and now - cached[1] < _INTENT_CACHE_TTL:
        return cached[0]
    intents = await query_arango(
        "FOR i IN intent_catalog FILTER i.agent_key == @key AND i.status == 'enabled' SORT i.priority DESC RETURN i",
        {"key": agent_key},
    )
    _intent_cache[agent_key] = (intents, now)
    return intents


async def classify_intent(msg: str, agent_key: str | None) -> tuple[str, str]:
    """從 Agent 的 intent_catalog 動態匹配意圖。fallback 到 rule-based 內建意圖。"""
    time_keywords = ["時間", "幾點", "日期", "今天幾號", "星期幾", "現在"]
    if any(k in msg for k in time_keywords):
        return ("time_query", "")

    if agent_key:
        try:
            intents = await load_agent_intents(agent_key)
            for intent in intents:
                patterns = intent.get("nl_patterns") or []
                if any(kw in msg for kw in patterns):
                    return (intent.get("name", "general_chat"), intent.get("description", ""))
        except Exception as e:
            logger.warning(f"Intent load failed: {e}")

    return ("general_chat", "")


def _extract_user_name(session_id: str) -> str:
    """從 session_id 推測用戶名稱"""
    if ":" in session_id:
        parts = session_id.split(":")
        if len(parts) >= 3:
            return parts[-1]  # user_id 通常是最後一段
    return session_id


async def _create_preorder_from_llm(reply: str, user_id: str, user_name: str, session_id: str, parsed: dict | None = None) -> str | None:
    """從 LLM 回覆的 JSON 中提取訂單資訊 → 透過 skill 建立預購單。回傳預購單編號或 None。"""
    try:
        p: dict = parsed  # type: ignore
        if p is None:
            start = reply.find("{")
            end = reply.rfind("}")
            if start == -1 or end == -1:
                return None
            p = json.loads(reply[start:end+1])
        if not isinstance(p.get("items"), list) or len(p["items"]) == 0:  # type: ignore
            return None
    except (json.JSONDecodeError, TypeError):
        return None

    # 透過 skill endpoint 建立預購單（統一 skills 框架入口）
    from bpa.order_secretary.skills.order_preorder_collect import execute as skill_execute

    skill_params = {
        "content": json.dumps({
            "items": [{
                "product_name": i.get("name", i.get("product_name", "")),
                "quantity": float(i.get("quantity", 0)),
                "unit": i.get("unit", ""),
                "spec": i.get("spec", ""),
                "notes": "",
            } for i in p["items"]],
            "notes": p.get("notes", ""),
        }),
        "media_type": "structured",
        "user_id": user_id,
        "user_name": user_name,
        "session_id": session_id,
    }
    result = await skill_execute(skill_params)
    if result.get("status") == "success":
        return result.get("order_id")
    logger.warning(f"[Router] Skill preorder creation failed: {result.get('message')}")
    return None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    start = time.monotonic()
    msg = request.message
    sid = request.session_id
    agent_key = request.agent_key
    user_id = request.user_id
    user_name = _extract_user_name(sid)
    history = _conversations.get(sid, [])

    intent, hint = await classify_intent(msg, agent_key)

    if intent == "time_query":
        now = datetime.now(timezone.utc)
        import zoneinfo
        tw_now = now.astimezone(zoneinfo.ZoneInfo("Asia/Taipei"))
        time_reply = f"現在時間是 {tw_now.strftime('%Y年%m月%d日 %H:%M:%S')}（台灣時間，UTC+8）"
        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": time_reply})
        _conversations[sid] = history[-MAX_TURNS * 2:]
        return ChatResponse(session_id=sid, reply=time_reply, sources=[])

    # 從 bot_chat_sessions 載入持久化歷史（跨頁面重整保留）
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

    if hint:
        msgs.append({"role": "system", "content": f"[意圖提示] {hint}"})

    if intent == "order_text":
        order_prompt = """請從使用者的訊息中提取訂單資訊，並以 JSON 格式回覆：
{
  "type": "order",
  "items": [{"name": "商品名稱", "quantity": 數量, "spec": "規格", "unit": "單位"}],
  "delivery_date": "交期或空字串",
  "notes": "備註",
  "missing_fields": ["缺少的欄位"],
  "reply": "給客戶的回覆文字（繁體中文，親切專業）"
}
若無法提取完整訂單資訊，在 missing_fields 列出缺少欄位並友善詢問。"""
        msgs.append({"role": "system", "content": order_prompt})
        msgs.extend(history[-MAX_TURNS:])
        msgs.append({"role": "user", "content": msg})
        reply = await call_llm(msgs, model, api_base, api_key)

        # LLM 可能回傳 JSON 格式，擷取 reply 文字
        try:
            parsed = json.loads(reply)
            if isinstance(parsed, dict):
                text_reply = parsed.get("reply", "")
                if text_reply:
                    reply = text_reply
                # 只有 type=order 且有 items 才建立預購單
                if parsed.get("type") == "order" and parsed.get("items"):
                    preorder_id = await _create_preorder_from_llm(reply, user_id, user_name, sid, parsed)
                    if preorder_id:
                        reply += f"\n\n📋 已為您建立預購單 **{preorder_id}**，狀態：開立。我們將儘快為您處理訂單。"
        except (json.JSONDecodeError, TypeError):
            pass

    elif intent == "order_track":
        # 查詢該用戶的預購單
        try:
            from bpa.order_secretary.preorder import get_preorders_by_user
            preorders = await get_preorders_by_user(user_id)
            if preorders:
                lines = ["您目前的預購單狀態：\n"]
                for p in preorders[:5]:
                    items_summary = ", ".join(f"{i.get('name','?')} x{i.get('quantity','?')}" for i in (p.get("items") or []))
                    lines.append(f"- **{p.get('preorder_id','?')}** | {p.get('status','?')} | {items_summary}")
                track_context = "\n".join(lines)
                track_prompt = f"使用者查詢訂單狀態。以下是該用戶的預購單資料：\n{track_context}\n請根據這些資料回答使用者。"
            else:
                track_prompt = "使用者查詢訂單狀態，但目前沒有任何預購單記錄。請友善告知。"
        except Exception as e:
            logger.warning(f"Preorder query failed: {e}")
            track_prompt = "使用者正在查詢訂單狀態或跟進資訊。"

        msgs.append({"role": "system", "content": track_prompt})
        msgs.extend(history[-MAX_TURNS:])
        msgs.append({"role": "user", "content": msg})
        reply = await call_llm(msgs, model, api_base, api_key)

    elif intent == "product_list":
        # 使用 SKL-2618-002 query_preorder_items 技能查詢預購品項
        try:
            from bpa.preorder_agent.skills.query_preorder_items import execute as exec_preorder_items
            # 取出 filter_term（使用者可能在訊息中提及特定品項）
            filter_term = _extract_filter_term(msg)
            skill_result = await exec_preorder_items({
                "session_id": sid,
                "user_id": user_id or "anonymous",
                "filter_term": filter_term,
            })
            if skill_result.get("success") and skill_result.get("data"):
                raw_items = skill_result["data"]
                # 格式化為親切的品項列表交代給 LLM
                items_formatted = _format_items_for_llm(raw_items)
                product_context = (
                    "以下是可供預購的品項（由系統即時查詢）：\n"
                    + items_formatted
                    + "\n\n若客戶感興趣，請協助確認品名、數量與單位，以便為客戶建立預購單。"
                )
            elif skill_result.get("success") and not skill_result.get("data"):
                product_context = "目前暫無可預購的品項資料，或許您可以看看其他時間是否有新到貨品項。"
            else:
                # skill 執行失敗，走 fallback
                err = skill_result.get("error", "")
                logger.warning(f"[Router] query_preorder_items failed: {err}")
                product_context = f"目前無法即時查詢品項資料（{err}），建議客戶稍後再試或洽客服了解。"
        except Exception as e:
            logger.warning(f"[Router] product_list skill error: {e}")
            product_context = "查詢品項資料時發生異常，請稍後再試。"

        msgs.append({"role": "system", "content": product_context})
        msgs.extend(history[-MAX_TURNS:])
        msgs.append({"role": "user", "content": msg})
        reply = await call_llm(msgs, model, api_base, api_key)

    else:
        msgs.extend(history[-MAX_TURNS:])
        msgs.append({"role": "user", "content": msg})
        reply = await call_llm(msgs, model, api_base, api_key)

    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": reply})
    _conversations[sid] = history[-MAX_TURNS * 2:]
    # 持久化到 bot_chat_sessions（跨頁面重整保留）
    try:
        from shared.conversation import ConversationStorage
        storage = ConversationStorage()
        await storage.save_message(session_id=sid, platform="agent", role="user", message=msg)
        await storage.save_message(session_id=sid, platform="agent", role="assistant", message=reply)
    except Exception:
        pass
    logger.info(f"[OrderSec] intent={intent} agent_key={agent_key} model={model} reply_len={len(reply)} elapsed={time.monotonic()-start:.1f}s")
    return ChatResponse(session_id=sid, reply=reply, sources=[])


async def _refresh_product_cache():
    """背景更新產品快取（寫入 ArangoDB product_cache 集合）"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "http://localhost:6500/api/v1/da/ragic/proxy/STOCK_16/data",
                params={"offset": 0, "limit": 99999},
            )
            if resp.status_code != 200:
                return
            body = resp.json()
            rows = body.get("rows", []) if isinstance(body, dict) else []
            seen = set()
            items = []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                name = str(r.get("1018133", "")).strip()
                qty = str(r.get("1018271", "0"))
                unit = str(r.get("1018130", "")).strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                unit_suffix = f" ({unit})" if unit and unit != "0" else ""
                items.append(f"- {name}（庫存 {qty}{unit_suffix}）")
            if not items:
                return
            now_ts = time.time()
            upsert_aql = """
            UPSERT { _key: @key }
            INSERT { _key: @key, items: @items, cached_at: @ts, updated_at: @ts_str }
            UPDATE { items: @items, cached_at: @ts, updated_at: @ts_str }
            IN product_cache
            """
            ts_str = datetime.now(timezone.utc).isoformat()
            await query_arango(upsert_aql, {"key": "stock_16_products", "items": items, "ts": now_ts, "ts_str": ts_str})
            logger.info(f"[Cache] Product cache refreshed: {len(items)} items")
    except Exception as e:
        logger.warning(f"[Cache] Refresh failed: {e}")


class SkillExecuteRequest(BaseModel):
    content: str
    media_type: str = "text"
    session_id: str = ""
    user_id: str = "anonymous"
    user_name: str = ""
    filename: str = ""
    reference_llm: dict | None = None


class SkillExecuteResponse(BaseModel):
    status: str
    order_id: str | None = None
    message: str = ""
    missing_fields: list[str] = []
    error_code: str | None = None


@router.post("/skills/order_preorder_collect", response_model=SkillExecuteResponse)
async def skill_order_preorder_collect(request: SkillExecuteRequest) -> SkillExecuteResponse:
    """技能端點：訂單預購單收集 — 文字/圖片 → 解析 → 檢驗 → 寫入"""
    result = await execute_order_inquiry(request.model_dump())
    return SkillExecuteResponse(**result)
