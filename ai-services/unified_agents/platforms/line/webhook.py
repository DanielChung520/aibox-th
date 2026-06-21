import os
import base64
import httpx
import logging
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional

logger = logging.getLogger("unified_agents.line_webhook")

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

                    # OCR 名片辨識（GLM-OCR via MLX）
                    ocr_result = None
                    try:
                        async with httpx.AsyncClient(timeout=30.0) as ocr_c:
                            ocr_resp = await ocr_c.post(
                                "http://127.0.0.1:11400/v1/chat/completions",
                                json={
                                    "model": "GLM-OCR",
                                    "messages": [{"role": "user", "content": [
                                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_content}"}},
                                        {"type": "text", "text": "Text Recognition: 請讀出這張名片上所有文字"}
                                    ]}],
                                    "max_tokens": 500, "temperature": 0.1,
                                },
                            )
                            if ocr_resp.status_code == 200:
                                ot = ocr_resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                                if ot and any(k in ot for k in ["公司", "電話", "姓名", "@"]):
                                    ocr_result = {"text": ot}
                                    logger.info(f"[MEDIA] GLM-OCR card: {ot[:60]}")
                    except Exception as e:
                        logger.warning(f"[MEDIA] GLM-OCR failed: {e}")

                    # 儲存使用者發送圖片的紀錄
                    storage = ConversationStorage()
                    await storage.save_message(
                        session_id=session_id, platform="line", role="user",
                        message=f"[傳送了一張{msg_type}]",
                        metadata={"user_name": user_display_name, "media_type": msg_type, "content_id": content_id},
                    )

                    # 分流：用 Qwen2.5-VL-7B 的描述判斷是否為賀卡/問候
                    desc = (mm.get("description") or "").lower()
                    greeting_keywords = ["早安", "午安", "晚安", "祝福", "生日", "新年", "端午", "中秋", "佳節", "安好", "順心",
                                         "賀卡", "慶祝", "聖誕", "除夕", "元宵", "母親節", "父親節", "感恩"]
                    is_greeting = any(kw in desc for kw in greeting_keywords)

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

                    # 決定回覆文字
                    reply_text = ""

                    ocr_text = ocr_result.get("text", "") if ocr_result else ""
                    if ocr_text:
                        if source_type == "group":
                            reply_text = f"{user_display_name}您好，感謝您分享名片！\n\n{ocr_text}\n\n我已將資料記錄下來，將轉交業務同仁確認後建檔。"
                        else:
                            reply_text = f"感謝您分享名片！\n\n{ocr_text}\n\n我已將您的資料建檔，將轉交業務同仁處理。謝謝您！"
                    elif source_type == "group":
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        if order_result and order_result.get("status") == "success":
                            reply_text = f"{user_display_name}您好，很抱歉讓您久等。\n\n{order_result.get('message', '')}"
                        elif is_greeting:
                            greeted = await storage.get_greeting_responded_at(session_id)
                            if greeted != today_str:
                                greeting_reply = f"{user_display_name}您好！感謝您的祝福，祝您一切順利！😊"
                                reply_text = greeting_reply
                                await storage.set_greeting_responded_at(session_id, today_str)
                        elif is_first_in_session:
                            reply_text = f"{user_display_name}您好，很抱歉讓您久等。\n\n收到您的{msg_type}，已備份完成。若需要建立預購單，請提供品名、數量和單位等訂購資訊。"
                    else:
                        if order_result and order_result.get("status") == "success":
                            reply_text = order_result.get("message", "")
                        else:
                            # 一般圖片：用 Qwen2.5-VL-7B 的描述來回覆
                            scene_desc = mm.get("description", "") if mm else ""
                            if scene_desc and not scene_desc.startswith("收到一張"):
                                reply_text = f"感謝您的分享！這是一張{scene_desc[:80]}。已為您備份完成。"
                            else:
                                reply_text = f"收到您的{msg_type}，已備份完成。"

                except Exception as e:
                    logger.error(f"[MEDIA] Processing failed: {type(e).__name__}: {e}", exc_info=True)
                    reply_text = f"收到您的{msg_type}，處理時發生錯誤，請稍後再試。"

                # Step 2: 用 reply_message 回覆結果（個人/群組皆可用 reply_token）
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
