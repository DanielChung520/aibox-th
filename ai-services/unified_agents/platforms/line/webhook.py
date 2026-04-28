import os
import base64
import httpx
import logging
from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional

logger = logging.getLogger("unified_agents.line_webhook")

from unified_agents.platforms.line.services import db
from shared.conversation import ConversationStorage
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


_agent_name_cache: dict[str, tuple[str, float]] = {}


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


async def call_agent_endpoint(endpoint_url: str, session_id: str, message: str, user_id: str, agent_key: str | None = None, platform: str = "line", image_content: str | None = None) -> str:
    payload = {
        "session_id": session_id,
        "message": message,
        "user_id": user_id,
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
                    group_name = (await get_group_summary(group_id, channel.get("channel_access_token", ""))).get("group_name", group_id)
                    metadata["group_name"] = group_name
                await storage.save_message(session_id=session_id, platform="line", role="user", message=text, metadata=metadata)

                if source_type in ("group", "room") and not is_mentioned_now:
                    continue

                try:
                    if agent_endpoint:
                        ai_response = await call_agent_endpoint(agent_endpoint, session_id, text, user_id, agent_key=agent_key)
                    elif agent_key:
                        ai_response = await call_ragic_helper(agent_key, session_id, text, user_id)
                    else:
                        ai_response = await call_ai_chat(user_id, session_id, text)
                except Exception as e:
                    ai_response = f"系統錯誤: {str(e)}"

                await storage.save_message(session_id=session_id, platform="line", role="assistant", message=ai_response)

                await reply_message(
                    channel_access_token=channel.get("channel_access_token", ""),
                    reply_token=reply_token,
                    messages=[{"type": "text", "text": ai_response}],
                )

            elif msg_type in ("image", "video", "audio", "file"):
                logger.info(f"[MEDIA] msg_type={msg_type} reply_token={bool(reply_token)} content_id={bool(content_id)} source_type={source_type}")
                if not reply_token or not content_id:
                    logger.warning(f"[MEDIA] Skipped: no reply_token or content_id")
                    continue
                if source_type in ("group", "room"):
                    logger.info(f"[MEDIA] Skipped: group/room not supported")
                    continue
                try:
                    content = await get_message_content(content_id, channel.get("channel_access_token", ""))
                    logger.info(f"[MEDIA] Downloaded {len(content)} bytes from LINE")
                    mime_map = {
                        "image": "image/jpeg",
                        "video": "video/mp4",
                        "audio": "audio/mpeg",
                        "file": "application/octet-stream",
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
                    # 圖片/影片/音訊只解析並存入上下文，不自動回覆
                    context_msg = f"[系統提示] 使用者剛才傳送了一張{msg_type}，以下是該{msg_type}的 AI 分析結果，請根據此描述回答使用者後續關於該{msg_type}的問題：\n\n{mm.get('description', '')}\n\n備份位置：{mm.get('seaweed_url', '')}"
                    storage = ConversationStorage()
                    await storage.save_message(session_id=session_id, platform="line", role="assistant", message=context_msg)

                    # 只在個別聊天時回應簡短確認
                    if source_type == "user" and reply_token:
                        await reply_message(
                            channel_access_token=channel.get("channel_access_token", ""),
                            reply_token=reply_token,
                            messages=[{"type": "text", "text": f"收到 {msg_type}，已解析。需要我說明內容嗎？"}],
                        )
                except Exception as e:
                    logger.error(f"[MEDIA] Failed: {type(e).__name__}: {e}", exc_info=True)
                    if reply_token:
                        await reply_message(
                            channel_access_token=channel.get("channel_access_token", ""),
                            reply_token=reply_token,
                            messages=[{"type": "text", "text": f"收到附件，處理失敗：{str(e)}"}],
                        )

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
