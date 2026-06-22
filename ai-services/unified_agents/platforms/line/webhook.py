import os
import base64
import httpx
import logging
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional

logger = logging.getLogger("unified_agents.line_webhook")

MLX_API = os.getenv("MLX_BASE_URL", "http://127.0.0.1:11400/v1")
CARD_MODEL = "Qwen3-VL-8B"


# 簡繁轉換對照表（LLM 常錯的字）
_S2T = str.maketrans({
    '吕':'呂','实':'實','识':'識','认':'認','荣':'榮','幸':'幸','会':'會','机':'機','与':'與',
    '关':'關','系':'係','门':'門','开':'開','发':'發','长':'長','国':'國','为':'為',
    '说':'說','话':'話','时':'時','间':'間','对':'對','动':'動','业':'業','经':'經','来':'來',
    '过':'過','还':'還','这':'這','个':'個','谢':'謝','称':'稱','呼':'呼',
    '电':'電','导':'導','师':'師','总':'總','理':'理',
    '后':'後','前':'前','点':'點','钱':'錢','体':'體','复':'複','兩':'兩','過':'過',
    '現':'現','將':'將','從':'從','時':'時','書':'書','萬':'萬','歷':'歷',
    '气':'氣','兴':'興','们':'們','尔':'爾','吗':'嗎','么':'麼','乐':'樂',
    '几':'幾','尽':'盡','当':'當','只':'隻','双':'雙','队':'隊','阳':'陽',
    '阴':'陰','险':'險','际':'際','陆':'陸','际':'際','虽':'雖','随':'隨',
})

def _ensure_traditional(text: str) -> str:
    return text.translate(_S2T)


async def _llm_reply(system_prompt: str, user_msg: str) -> str:
    """呼叫 MLX LLM 生成回覆文字"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            resp = await c.post(f"{MLX_API}/chat/completions", json={
                "model": CARD_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 300,
                "temperature": 0.7,
            })
            if resp.status_code == 200:
                content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                if content:
                    content = _ensure_traditional(content)
                    logger.info(f"[LLM Reply] generated ({len(content)} chars): {content[:100]}")
                return content
    except Exception as e:
        logger.warning(f"[LLM Reply] failed: {e}")
    return ""

from unified_agents.platforms.line.services import db
from shared.conversation import ConversationStorage, QueryEngine
from unified_agents.platforms.line.services.line_api import (
    verify_line_signature,
    reply_message,
    get_message_content,
    get_group_summary,
    get_user_profile,
)

router = APIRouter(tags=["LINE Webhook"])

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DB", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")


async def ensure_crm_contact(line_user_id: str, display_name: str, channel_key: str, owner_key: str = "", introducer: str = ""):
    """檢查並自動建立 CRM 聯絡人"""
    try:
        auth = (ARANGO_USER, ARANGO_PASSWORD)
        base = f"{ARANGO_URL}/_db/{ARANGO_DB}"
        async with httpx.AsyncClient(timeout=10.0, auth=auth) as c:
            # 查是否已存在
            q = {"query": f"FOR c IN crm_contacts FILTER c.line_user_id == @uid LIMIT 1 RETURN c._key",
                 "bindVars": {"uid": line_user_id}}
            resp = await c.post(f"{base}/_api/cursor", json=q)
            if resp.status_code == 201:
                data = resp.json()
                if data.get("result") and len(data["result"]) > 0:
                    return  # 已存在
            # 不存在，自動建立
            import uuid
            now = datetime.utcnow().isoformat() + "Z"
            doc = {
                "_key": str(uuid.uuid4()),
                "name_cn": display_name,
                "source": "line",
                "line_user_id": line_user_id,
                "line_status": "connected",
                "channel_key": channel_key,
                "owner_key": owner_key or "",
                "created_at": now,
                "updated_at": now,
                "created_by": "line_webhook",
            }
            if introducer:
                doc["line_introducer"] = introducer
            await c.post(f"{base}/_api/document/crm_contacts", json=doc)
            logger.info(f"[CRM] Auto-created contact: {display_name} ({line_user_id})")
    except Exception as e:
        logger.warning(f"[CRM] Failed to auto-create contact: {e}")

MULTIMEDIA_TOOL_URL = os.getenv("MULTIMEDIA_TOOL_URL", "http://localhost:8011/mcp/multimedia-analyzer")

AITASK_URL = os.getenv("AITASK_URL", "http://localhost:8001")
RAGIC_HELPER_URL = os.getenv("RAGIC_HELPER_URL", "http://localhost:8011")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")


async def get_group_name_cached(
    storage: ConversationStorage,
    session_id: str,
    group_id: str,
    channel_access_token: str,
) -> str:
    cached = await storage.get_session_group_name(session_id)
    if cached:
        return cached
    result = await get_group_summary(group_id, channel_access_token)
    name = result.get("group_name", group_id)
    await storage.ensure_session_metadata_collection()
    await storage.upsert_session_group_name(session_id, name, platform="line")
    return name


_agent_name_cache: dict[str, tuple[str, float]] = {}
_llm_config_cache: dict[str, tuple[dict, float]] = {}


async def query_arango_raw(aql: str, bind_vars: dict | None = None) -> list[dict]:
    """查詢 ArangoDB（被 resolve_llm_config_for_agent 共用）"""
    import httpx
    import base64
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


async def resolve_llm_config_for_agent(agent_key: str) -> dict | None:
    """解析 agent 的 LLM 設定，回傳 reference_llm dict 或 None"""
    import time as time_module
    now = time_module.time()
    if agent_key in _llm_config_cache:
        cfg, ts = _llm_config_cache[agent_key]
        if now - ts < 300:
            return cfg

    agents = await query_arango_raw(
        "FOR a IN agents FILTER a._key == @key LIMIT 1 RETURN a",
        {"key": agent_key},
    )
    if not agents:
        return None
    model = agents[0].get("llm_model", "")
    if not model:
        return None

    providers = await query_arango_raw(
        "FOR p IN model_providers FILTER p.status == 'enabled' RETURN p",
    )
    for p in providers:
        for m in (p.get("models") or []):
            if isinstance(m, dict) and m.get("model_id") == model:
                base_url = (p.get("base_url") or "").rstrip("/")
                api_key = p.get("api_key") or ""
                is_local = "localhost" in base_url or "127.0.0.1" in base_url
                cfg = {
                    "model": model,
                    "api_base": base_url,
                    "api_key": api_key,
                    "provider_type": "ollama" if is_local else "openai",
                }
                _llm_config_cache[agent_key] = (cfg, now)
                return cfg
    return None


async def get_agent_name(agent_key: str) -> str:
    if agent_key == "default" or not agent_key:
        return "機器人"

    now = __import__("time").time()
    if agent_key in _agent_name_cache:
        name, timestamp = _agent_name_cache[agent_key]
        if now - timestamp < 300:
            return name

    aql = "FOR doc IN agents FILTER doc._key == @key LIMIT 1 RETURN doc.name"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": aql, "bindVars": {"key": agent_key}},
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            results = data.get("result", [])
            if results:
                name = results[0] or "機器人"
                _agent_name_cache[agent_key] = (name, now)
                return name
    return "機器人"


def build_session_id(source: dict, channel_key: str) -> str:
    source_type = source.get("type", "user")
    user_id = source.get("userId", "unknown")

    if source_type == "group":
        group_id = source.get("groupId", "unknown")
        return f"line:group:{channel_key}:{group_id}:{user_id}"
    elif source_type == "room":
        room_id = source.get("roomId", "unknown")
        return f"line:room:{channel_key}:{room_id}:{user_id}"
    else:
        return f"line:{channel_key}:{user_id}"


def is_mentioned(text: str, bot_name: str) -> bool:
    if not text or not bot_name:
        return False
    return f"@{bot_name}" in text or f"@{bot_name} " in text


async def call_agent_endpoint(endpoint_url: str, session_id: str, message: str, user_id: str, agent_key: str | None = None, platform: str = "line", image_content: str | None = None, channel_key: str = "") -> str:
    payload: dict = {
        "session_id": session_id,
        "message": message,
        "user_id": user_id,
        "source": "customer",
        "channel_key": channel_key,
    }
    if agent_key:
        payload["agent_key"] = agent_key
    if image_content:
        payload["image_content"] = image_content
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(endpoint_url, json=payload)
        if resp.status_code != 200:
            return f"AI 服務錯誤: {resp.status_code}"
        data = resp.json()
        return data.get("reply", data.get("response", str(data)))


async def call_ragic_helper(agent_key: str, session_id: str, message: str, user_id: str, platform: str = "line", image_content: str | None = None) -> str:
    payload = {
        "agent_key": agent_key,
        "session_id": session_id,
        "message": message,
        "user_id": user_id,
        "platform": platform,
    }
    if image_content:
        payload["image_content"] = image_content
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{RAGIC_HELPER_URL}/ragic/chat",
            json=payload,
        )
        if resp.status_code != 200:
            return f"AI 服務錯誤: {resp.status_code}"
        data = resp.json()
        return data.get("response", str(data))


async def call_ai_chat(user_id: str, session_id: str, message: str) -> str:
    """
    呼叫 AITask /chat 取得 AI 回應（同步版本）。

    Returns:
        AI 回應文字
    """
    payload = {
        "messages": [{"role": "user", "content": message}],
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{AITASK_URL}/chat",
            json=payload,
        )
        if resp.status_code != 200:
            return f"AI 服務錯誤: {resp.status_code}"
        data = resp.json()
        if isinstance(data, dict) and "error" in data:
            return f"AI 錯誤: {data['error']}"
        # /chat returns {"model": ..., "message": {"role": "assistant", "content": "..."}, "done": true}
        msg = data.get("message", {})
        content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
        return content or str(data)


@router.get("/webhook/line/{channel_key}")
async def handle_line_webhook_get(channel_key: str):
    channel = await db.get_channel(channel_key)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel 不存在")
    return {"status": "ok"}


@router.post("/webhook/line/{channel_key}")
async def handle_line_webhook(
    channel_key: str,
    request: Request,
    x_line_signature: Optional[str] = Header(None),
):
    """
    接收 LINE Platform 發送的 webhook 事件。

    流程:
    1. 驗證 x-line-signature
    2. 解析 events[]
    3. 對每個 message event: 呼叫 AI → 回覆 LINE 用戶
    """
    channel = await db.get_channel(channel_key)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel 不存在")

    if not channel.get("webhook_enabled", False):
        return {"status": "ignored", "reason": "webhook_disabled"}

    channel_secret = channel.get("channel_secret", "")
    body = await request.body()
    body_str = body.decode("utf-8")

    if x_line_signature and channel_secret:
        if not verify_line_signature(body_str, x_line_signature, channel_secret):
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    events = payload.get("events", [])

    if not events:
        return {"status": "ok"}

    agent_key = channel.get("linked_agent_key") or ""
    bot_name = await get_agent_name(agent_key) if agent_key else "機器人"
    channel_name = channel.get("channel_name", "")

    # 若 channel 有 linked_agent_key，查該 Agent 的 endpoint_url 做動態路由
    agent_endpoint: str | None = None
    if agent_key:
        try:
            agent_doc = await db.get_agent(agent_key)
            if agent_doc:
                ep = agent_doc.get("endpoint_url", "")
                if ep:
                    agent_endpoint = ep
        except Exception:
            pass

    for event in events:
        event_type = event.get("type")
        source = event.get("source", {})
        source_type = source.get("type", "user")
        user_id = source.get("userId", "unknown")
        reply_token = event.get("replyToken", "")
        session_id = build_session_id(source, channel_key)

        if event_type == "message":
            msg = event.get("message", {})
            msg_type = msg.get("type", "text")
            content_id = msg.get("id") or msg.get("contentId")  # LINE uses "id"

            if msg_type == "text":
                text = msg.get("text", "")
                if not reply_token or not text:
                    continue

                is_mentioned_now = is_mentioned(text, bot_name) or is_mentioned(text, channel_name)

                storage = ConversationStorage()
                user_profile = await get_user_profile(user_id, channel.get("channel_access_token", ""))
                user_display_name = user_profile.get("display_name", user_id)
                metadata: dict = {"user_name": user_display_name}
                if source_type == "group":
                    group_id = source.get("groupId", "")
                    group_name = await get_group_name_cached(
                        storage, session_id, group_id, channel.get("channel_access_token", "")
                    )
                    metadata["group_name"] = group_name
                await storage.save_message(session_id=session_id, platform="line", role="user", message=text, metadata=metadata)
                await ensure_crm_contact(user_id, user_display_name, channel_key, owner_key=channel.get("business_user_key", ""))

                if source_type in ("group", "room") and not is_mentioned_now:
                    continue

                try:
                    if agent_endpoint:
                        ai_response = await call_agent_endpoint(agent_endpoint, session_id, text, user_id, agent_key=agent_key, channel_key=channel_key)
                    elif agent_key:
                        ai_response = await call_ragic_helper(agent_key, session_id, text, user_id)
                    else:
                        ai_response = await call_ai_chat(user_id, session_id, text)
                except Exception as e:
                    ai_response = f"系統錯誤: {str(e)}"

                if source_type == "group":
                    ai_response = f"{user_display_name}您好，很抱歉讓您久等。\n\n{ai_response}"

                await storage.save_message(session_id=session_id, platform="line", role="assistant", message=ai_response)

                await reply_message(
                    channel_access_token=channel.get("channel_access_token", ""),
                    reply_token=reply_token,
                    messages=[{"type": "text", "text": ai_response}],
                )

            elif msg_type == "file":
                logger.info(f"[FILE] msg_type={msg_type} reply_token={bool(reply_token)} content_id={bool(content_id)} source_type={source_type}")
                if not reply_token or not content_id:
                    logger.warning("[FILE] Skipped: no reply_token or content_id")
                    continue

                order_result = None
                reply_text = ""
                try:
                    # 下載檔案內容（繞過多媒體分析器，直接 Python 解析）
                    content = await get_message_content(content_id, channel.get("channel_access_token", ""))
                    logger.info(f"[FILE] Downloaded {len(content)} bytes from LINE")

                    user_profile = await get_user_profile(user_id, channel.get("channel_access_token", ""))
                    user_display_name = user_profile.get("display_name", user_id)

                    is_first_in_session = False
                    if source_type == "group":
                        engine = QueryEngine()
                        history = await engine.get_history(session_id, limit=1)
                        is_first_in_session = len(history) == 0

                    file_name = msg.get("fileName", f"file_{content_id}")
                    b64_content = base64.b64encode(content).decode()

                    # 儲存使用者發送檔案的紀錄
                    storage = ConversationStorage()
                    await storage.save_message(
                        session_id=session_id, platform="line", role="user",
                        message=f"[傳送了一個檔案：{file_name}]",
                        metadata={"user_name": user_display_name, "media_type": "file", "content_id": content_id, "file_name": file_name},
                    )

                    # 直接呼叫 order_preorder_collect（不走多媒體分析器）
                    try:
                        llm_config = await resolve_llm_config_for_agent(agent_key) if agent_key else None
                        skill_payload = {
                            "content": b64_content,
                            "media_type": "file",
                            "session_id": session_id,
                            "user_id": user_id,
                            "user_name": user_display_name,
                            "filename": file_name,
                        }
                        if llm_config:
                            skill_payload["reference_llm"] = llm_config
                        async with httpx.AsyncClient(timeout=60.0) as oc:
                            order_resp = await oc.post(
                                "http://127.0.0.1:8011/order-secretary/skills/order_preorder_collect",
                                json=skill_payload,
                            )
                            if order_resp.status_code == 200:
                                order_result = order_resp.json()
                    except Exception as e:
                        logger.warning(f"[FILE] Order extraction failed: {e}")

                    # 決定回覆文字
                    reply_text = ""
                    if source_type == "group":
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        if order_result and order_result.get("status") == "success":
                            reply_text = f"{user_display_name}您好，很抱歉讓您久等。\n\n{order_result.get('message', '')}"
                        elif is_first_in_session:
                            reply_text = f"{user_display_name}您好，很抱歉讓您久等。\n\n收到您的檔案（{file_name}），已備份完成。若需要建立預購單，請提供品名、數量和單位等訂購資訊。"
                    else:
                        if order_result and order_result.get("status") == "success":
                            reply_text = order_result.get("message", "") or f"收到您的檔案（{file_name}），已備份完成。若需要建立預購單，請提供品名、數量和單位等訂購資訊。"
                        else:
                            reply_text = f"收到您的檔案（{file_name}），已備份完成。若需要建立預購單，請提供品名、數量和單位等訂購資訊。"

                except Exception as e:
                    logger.error(f"[FILE] Processing failed: {type(e).__name__}: {e}", exc_info=True)
                    reply_text = f"收到您的檔案，處理時發生錯誤，請稍後再試。"

                try:
                    if reply_text:
                        await reply_message(
                            channel_access_token=channel.get("channel_access_token", ""),
                            reply_token=reply_token,
                            messages=[{"type": "text", "text": reply_text}],
                        )
                except Exception as e:
                    logger.warning(f"[FILE] Reply failed: {e}")

            elif msg_type in ("image", "video", "audio"):
                logger.info(f"[MEDIA] msg_type={msg_type} reply_token={bool(reply_token)} content_id={bool(content_id)} source_type={source_type}")
                if not reply_token or not content_id:
                    logger.warning("[MEDIA] Skipped: no reply_token or content_id")
                    continue

                # Step 1: 非同步處理 — 所有人（個人/群組）都執行，下載 → 分析 → 技能
                order_result = None
                mm = None
                reply_text = ""
                try:
                    content = await get_message_content(content_id, channel.get("channel_access_token", ""))
                    logger.info(f"[MEDIA] Downloaded {len(content)} bytes from LINE")

                    user_profile = await get_user_profile(user_id, channel.get("channel_access_token", ""))
                    user_display_name = user_profile.get("display_name", user_id)

                    is_first_in_session = False
                    if source_type == "group":
                        engine = QueryEngine()
                        history = await engine.get_history(session_id, limit=1)
                        is_first_in_session = len(history) == 0

                    mime_map = {
                        "image": "image/jpeg",
                        "video": "video/mp4",
                        "audio": "audio/mpeg",
                    }
                    b64_content = base64.b64encode(content).decode()
                    payload = {
                        "content": b64_content,
                        "media_type": msg_type,
                        "filename": f"{msg_type}_{content_id}",
                        "platform": "line",
                        "user_id": user_id,
                        "mime_type": mime_map.get(msg_type, "application/octet-stream"),
                    }
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        resp = await client.post(
                            f"{MULTIMEDIA_TOOL_URL}/analyze",
                            json=payload,
                        )
                        resp.raise_for_status()
                        mm = resp.json()
                    logger.info(f"[MEDIA] Analyzed: desc={mm.get('description','')[:60]}... seaweed={mm.get('seaweed_url','')}")

                    # Qwen3-VL-8B 場景描述已包含所有資訊，直接從描述提取名片結構
                    ocr_result = None
                    scene_desc = mm.get("description", "") if mm else ""
                    if scene_desc and any(k in scene_desc for k in ["名片", "公司", "電話", "姓名"]):
                        _extract = await _llm_reply(
                            "你只會輸出 JSON，不准輸出其他文字。",
                            f"從以下名片描述提取姓名(name)和職稱(title)，只回 JSON：\n{scene_desc[:500]}"
                        )
                        if _extract:
                            import json as _json
                            _e = _extract.strip()
                            if "```json" in _e: _e = _e.split("```json")[1].split("```")[0].strip()
                            elif "```" in _e: _e = _e.split("```")[1].split("```")[0].strip()
                            try:
                                _c = _json.loads(_e)
                                _n = _c.get("name") or _c.get("姓名") or ""
                                _t = _c.get("title") or _c.get("職稱") or ""
                                if _n and not any(k in _n for k in ["黨","會","社","公司","企業","集團"]):
                                    ocr_result = {"name": _n, "title": _t, "raw": _e}
                                    logger.info(f"[MEDIA] VL card: {_n} / {_t}")
                            except:
                                pass

                    # 儲存使用者發送圖片的紀錄
                    storage = ConversationStorage()
                    await storage.save_message(
                        session_id=session_id, platform="line", role="user",
                        message=f"[傳送了一張{msg_type}]",
                        metadata={"user_name": user_display_name, "media_type": msg_type, "content_id": content_id},
                    )

                    # 用 LLM 判斷是否為節慶/問候/節氣圖片（取代關鍵字比對）
                    desc_raw = mm.get("description") or ""
                    is_greeting = False
                    if desc_raw:
                        cls = await _llm_reply(
                            "你是一個圖片分類助理。根據圖片描述，判斷這張圖片是否與節慶、節氣、祝福、問候、感恩或慶祝相關。"
                            "包含但不限於：新年、端午、中秋、聖誕、生日、母親節、父親節、情人節、元宵、"
                            "春分、夏至、立秋、冬至等二十四節氣，以及早安、晚安、祝福、感謝、賀卡、慶祝、恭喜等情境。"
                            "請只回覆一個字：Y 表示是，N 表示否。",
                            f"圖片描述：{desc_raw}"
                        )
                        is_greeting = cls.strip().upper().startswith("Y")
                    desc = desc_raw.lower()

                    # 若不是祝福圖片，且描述長度足夠，嘗試解析訂單
                    if not is_greeting and len(desc) > 20:
                        try:
                            llm_config = await resolve_llm_config_for_agent(agent_key) if agent_key else None
                            skill_payload = {
                                "content": desc,
                                "media_type": "text",
                                "session_id": session_id,
                                "user_id": user_id,
                                "user_name": user_display_name,
                                "filename": f"image_analysis_{content_id}",
                            }
                            if llm_config:
                                skill_payload["reference_llm"] = llm_config
                            async with httpx.AsyncClient(timeout=60.0) as oc:
                                order_resp = await oc.post(
                                    "http://127.0.0.1:8011/order-secretary/skills/order_preorder_collect",
                                    json=skill_payload,
                                )
                                if order_resp.status_code == 200:
                                    order_result = order_resp.json()
                        except Exception as e:
                            logger.warning(f"[MEDIA] Order extraction attempt failed: {e}")

                    # 儲存分析結果到對話歷史（群組也儲存，讓 @mention 時可參考上下文）
                    if mm:
                        context_msg = f"[系統提示] {user_display_name}剛才傳送了一張{msg_type}，以下是該{msg_type}的 AI 分析結果，請根據此描述回答使用者後續關於該{msg_type}的問題：\n\n{mm.get('description', '')}\n\n備份位置：{mm.get('seaweed_url', '')}"
                        await storage.save_message(session_id=session_id, platform="line", role="assistant", message=context_msg)

                    # 決定回覆文字（由 LLM 生成）
                    reply_text = ""
                    scene_desc = (mm.get("description") or "") if mm else ""
                    card_name = ocr_result.get("name", "") if ocr_result else ""
                    card_title = ocr_result.get("title", "") if ocr_result else ""
                    card_company = ocr_result.get("company", "") if ocr_result else ""

                    logger.info(f"[IMG] GLM-OCR: name={card_name} title={card_title} company={card_company}")
                    logger.info(f"[IMG] Scene desc: {scene_desc[:100]}")
                    # 用 GLM-OCR 結構化輸出提取稱呼
                    import re
                    TITLES = {"副總經理":"總經理", "總經理":"總經理", "協理":"協理", "經理":"經理", "副理":"經理",
                              "主任":"主任", "組長":"組長", "工程師":"老師", "設計師":"老師", "分析師":"老師",
                              "導入師":"老師", "醫師":"老師", "律師":"老師", "教授":"老師", "副總":"副總",
                              "董事長":"執行長", "執行長":"執行長", "院長":"院長", "所長":"所長", "顧問":"顧問", "專員":"專員"}

                    # 統整稱謂：名片OCR優先，其次LINE顯示名稱，最後用「您」
                    card_greeting = "您"
                    if card_name:
                        surname = next((ch for ch in card_name if '\u4e00' <= ch <= '\u9fff'), "")
                        raw_title = card_title if card_title and not any(card_title.endswith(k) for k in ["公司","企業","集團","行號"]) else ""
                        matched_title = next((short for t, short in TITLES.items() if t in raw_title), "")
                        if surname and matched_title:
                            card_greeting = f"{surname}老師" if matched_title == "老師" else f"{surname}{matched_title}"
                        elif surname:
                            card_greeting = f"{surname}老師"
                    addr = card_greeting if card_greeting != "您" else (user_display_name or "您")

                    if card_name:
                        surname = ""
                        for ch in card_name:
                            if '\u4e00' <= ch <= '\u9fff':
                                surname = ch
                                break
                        # 檢查 title 是否真的像職稱（不是公司名）
                        raw_title = card_title if card_title and not any(card_title.endswith(k) for k in ["公司","企業","集團","行號"]) else ""
                        logger.info(f"[IMG] Card greeting resolved: {addr}")
                        # 判斷語言：姓名或公司有中文字→繁體中文，否則英文
                        check_text = f"{card_name} {card_company}"
                        is_chinese = any('\u4e00' <= c <= '\u9fff' for c in check_text)
                        if is_chinese:
                            prompt = f"用繁體中文寫這句話：{addr}，感謝您分享名片，很高興認識您。全中文，不要任何英文單字。"
                            sys_p = "你是台灣的業務助理，只能用繁體中文，不可以夾雜英文。"
                        else:
                            prompt = f"Reply in English: Address the person as \"{addr}\", thank them for sharing their business card, express pleasure in meeting them. One sentence only."
                            sys_p = "You are a professional business assistant. Respond politely and warmly."
                        reply_text = await _llm_reply(sys_p, prompt)
                        if not reply_text:
                            reply_text = "您好！感謝您分享的名片。"

                    elif is_greeting:
                        logger.info(f"[IMG] Greeting card detected: {scene_desc[:60]}")
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        greeted = await storage.get_greeting_responded_at(session_id)
                        if greeted != today_str:
                            prompt = (
                                f"{addr}傳了一張節慶/問候圖片。\n"
                                f"圖片描述：{scene_desc}\n\n"
                                f"請先感謝{addr}的祝福，再接一句簡短優美應景的話（30~50字）。"
                                f"全文不超過60字。不要詩詞堆砌，不要分段，自然溫暖即可。"
                            )
                            sys_p = "你是溫暖真誠的業務助理，用繁體中文，簡潔有力。"
                            reply_text = await _llm_reply(sys_p, prompt)
                            if reply_text:
                                await storage.set_greeting_responded_at(session_id, today_str)

                    elif source_type == "group":
                        if order_result and order_result.get("status") == "success":
                            reply_text = f"{user_display_name}您好，很抱歉讓您久等。\n\n{order_result.get('message', '')}"
                        elif is_first_in_session:
                            reply_text = f"{user_display_name}您好，很抱歉讓您久等。\n\n收到您的{msg_type}，已備份完成。若需要建立預購單，請提供品名、數量和單位等訂購資訊。"

                    if not reply_text:
                        if scene_desc and not scene_desc.startswith("收到一張"):
                            # 判斷是否包含名片資訊（GLM-OCR 沒抓到但 vision 有看到）
                            is_card_scene = any(kw in scene_desc for kw in ["名片", "醫院", "公司", "電話", "醫師", "經理"])
                            if is_card_scene:
                                logger.info(f"[IMG] Fallback card detected from scene desc")
                                prompt = f"圖片描述：{scene_desc}\n\n注意：對方傳了一張名片。請用繁體中文回覆，感謝對方分享名片。若名片有姓氏和職稱，用「姓氏+職稱」稱呼（如：藍醫師、王總經理）。職稱含「師」字者也可稱「姓氏+老師」（如：藍老師）。簡短溫暖，一兩句話即可。不要描述場景。"
                                sys_p = "你是專業的業務助理，使用繁體中文，回應簡潔溫暖得體。"
                            else:
                                prompt = f"對方傳了一張圖片。圖片描述：{scene_desc}\n\n請用繁體中文、簡單感謝對方分享即可，一句話就好。語氣溫暖。"
                                sys_p = "你是親切的客服助理，使用繁體中文。"
                            reply_text = await _llm_reply(sys_p, prompt)
                        if not reply_text:
                            reply_text = f"收到您的{msg_type}，已備份完成。"

                except Exception as e:
                    logger.error(f"[MEDIA] Processing failed: {type(e).__name__}: {e}", exc_info=True)
                    reply_text = f"收到您的{msg_type}，處理時發生錯誤，請稍後再試。"

                # Step 2: 用 reply_message 回覆結果
                if reply_text:
                    logger.info(f"[MEDIA] Reply to user: {reply_text[:120]}")
                    await storage.save_message(session_id=session_id, platform="line", role="assistant", message=reply_text)
                try:
                    if reply_text:
                        await reply_message(
                            channel_access_token=channel.get("channel_access_token", ""),
                            reply_token=reply_token,
                            messages=[{"type": "text", "text": reply_text}],
                        )
                except Exception as e:
                    logger.warning(f"[MEDIA] Reply failed: {e}")

            elif msg_type == "sticker":
                if not reply_token:
                    continue
                if source_type in ("group", "room"):
                    continue
                sticker_id = msg.get("stickerId", "")
                await reply_message(
                    channel_access_token=channel.get("channel_access_token", ""),
                    reply_token=reply_token,
                    messages=[{"type": "text", "text": f"收到貼圖 (ID: {sticker_id})，謝謝！"}],
                )

            elif msg_type == "location":
                if not reply_token:
                    continue
                if source_type in ("group", "room"):
                    continue
                latitude = msg.get("latitude", 0)
                longitude = msg.get("longitude", 0)
                address = msg.get("address", "未知位置")
                try:
                    loc_text = f"[收到位置分享] 地址：{address}，座標：{latitude},{longitude}"
                    if agent_endpoint:
                        ai_response = await call_agent_endpoint(agent_endpoint, session_id, loc_text, user_id, agent_key=agent_key)
                    elif agent_key:
                        ai_response = await call_ragic_helper(agent_key, session_id, loc_text, user_id)
                    else:
                        ai_response = loc_text
                except Exception:
                    ai_response = f"收到位置分享：{address}"
                await reply_message(
                    channel_access_token=channel.get("channel_access_token", ""),
                    reply_token=reply_token,
                    messages=[{"type": "text", "text": ai_response}],
                )

            elif msg_type == "contact":
                logger.info(f"[CONTACT] reply_token={bool(reply_token)} source_type={source_type}")
                if not reply_token:
                    continue
                contact_info = msg.get("contact", {})
                contact_name = contact_info.get("name", "未知")
                contact_user_id = contact_info.get("userId", "")
                if contact_user_id:
                    storage = ConversationStorage()
                    user_profile = await get_user_profile(contact_user_id, channel.get("channel_access_token", ""))
                    display_name = user_profile.get("display_name", contact_name)
                    await storage.save_message(
                        session_id=build_session_id({"userId": contact_user_id}, channel_key),
                        platform="line", role="user",
                        message=f"[分享名片] {display_name}",
                        metadata={"user_name": display_name, "media_type": "contact", "contact_user_id": contact_user_id},
                    )
                    await ensure_crm_contact(contact_user_id, display_name, channel_key,
                                             owner_key=channel.get("business_user_key", ""),
                                             introducer=user_id)
                await reply_message(
                    channel_access_token=channel.get("channel_access_token", ""),
                    reply_token=reply_token,
                    messages=[{"type": "text", "text": f"感謝您分享{contact_name}的名片，我已記錄下來。"}],
                )

        elif event_type == "follow":
            if reply_token:
                await reply_message(
                    channel_access_token=channel.get("channel_access_token", ""),
                    reply_token=reply_token,
                    messages=[{"type": "text", "text": "感謝您加入！我們的 AI 助理隨時為您服務。"}],
                )

        elif event_type == "postback":
            if reply_token:
                postback_data = event.get("postback", {}).get("data", "")
                try:
                    if agent_endpoint:
                        ai_response = await call_agent_endpoint(agent_endpoint, session_id, postback_data, user_id, agent_key=agent_key)
                    elif agent_key:
                        ai_response = await call_ragic_helper(agent_key, session_id, postback_data, user_id)
                    else:
                        ai_response = f"收到回傳資料：{postback_data}"
                    await reply_message(
                        channel_access_token=channel.get("channel_access_token", ""),
                        reply_token=reply_token,
                        messages=[{"type": "text", "text": ai_response}],
                    )
                except Exception:
                    pass

    return {"status": "ok"}
