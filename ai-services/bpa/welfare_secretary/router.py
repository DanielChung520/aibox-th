"""
@file        業務平台助手 — 統一入口 Router
@description 接收來自各管道（LINE Webhook / 內部 API）的請求，依來源分流
@lastUpdate  2026-06-19
@author      Sisyphus
@version     1.0.0
"""

import logging
import time
import base64
from fastapi import APIRouter
from pydantic import BaseModel

from bpa.welfare_secretary.config import ARANGO_URL, ARANGO_DB, ARANGO_USER, ARANGO_PASSWORD

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Welfare Secretary - Unified"])

_conversations: dict[str, list[dict[str, str]]] = {}
_MAX_TURNS = 10


class ChatRequest(BaseModel):
    session_id: str
    message: str
    user_id: str = "anonymous"
    agent_key: str = "welfare_secretary"
    source: str = "customer"  # "customer" | "internal"
    channel_key: str = ""  # 管道識別
    attachment: dict | None = None  # 附加檔案


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str = ""
    sources: list[str] = []


async def _query_arango(aql: str, bind_vars: dict | None = None) -> list[dict]:
    """ArangoDB AQL 查詢"""
    import httpx
    auth_cred = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(auth_cred.encode()).decode()}",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": aql, "bindVars": bind_vars or {}},
                headers=headers,
            )
            if resp.status_code in (200, 201):
                return resp.json().get("result", [])
    except Exception as e:
        logger.warning(f"[Router] AQL query failed: {e}")
    return []


async def resolve_identity(session_id: str, channel_key: str = "") -> dict:
    """從 session_id 或 channel_key 解析業務員身份。

    依序嘗試：
    1. 若 channel_key 有值，直接查 channels 集合
    2. 從 session_id 格式 'line:{channel_key}:{user_id}' 解析 channel_key
    3. 回傳身份資訊（含 business_user、persona_config）
    """
    resolved_channel_key = channel_key

    if not resolved_channel_key and ":" in session_id:
        parts = session_id.split(":")
        if len(parts) >= 3:
            resolved_channel_key = parts[1]

    identity: dict = {
        "channel_key": resolved_channel_key,
        "business_user_key": "",
        "business_user": {},
        "role": "業務員",
        "persona_config": {},
    }

    if resolved_channel_key:
        channels = await _query_arango(
            "FOR c IN channels FILTER c._key == @key LIMIT 1 RETURN c",
            {"key": resolved_channel_key},
        )
        if channels:
            ch = channels[0]
            identity["role"] = ch.get("role", "業務員")
            bu_key = ch.get("business_user_key", "")
            identity["business_user_key"] = bu_key

            if bu_key:
                users = await _query_arango(
                    "FOR u IN business_users FILTER u._key == @key LIMIT 1 RETURN u",
                    {"key": bu_key},
                )
                if users:
                    u = users[0]
                    identity["business_user"] = u
                    identity["persona_config"] = u.get("persona_config", {})

    return identity


async def build_persona_prompt(identity: dict) -> str:
    """根據業務員身份組合個人化 system prompt 前綴"""
    bu = identity.get("business_user", {})
    pc = identity.get("persona_config", {})
    if not bu:
        return ""
    parts = [
        f"你現在是 {bu.get('name', '業務員')} 的個人業務助理。",
        f"角色：{identity.get('role', '業務員')}",
    ]
    if bu.get("region"):
        parts.append(f"負責區域：{bu['region']}")
    expertise = pc.get("expertise")
    if expertise:
        parts.append(f"專業領域：{', '.join(expertise if isinstance(expertise, list) else [expertise])}")
    segment = pc.get("customer_segment")
    if segment:
        parts.append(f"主要客戶類型：{segment}")
    signature = pc.get("signature")
    if signature:
        parts.append(f"署名：{signature}")
    style = pc.get("greeting_style")
    if style:
        parts.append(f"問候風格：{style}")
    return "\n".join(parts)


async def call_llm(messages: list[dict], model: str, api_base: str, api_key: str = "", temperature: float | None = None) -> str:
    """多 Provider LLM 呼叫（OpenAI-compatible / MLX）"""
    import httpx

    llm_options = {}
    if temperature is not None:
        llm_options["temperature"] = temperature
    base = api_base.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    url = f"{base}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": model, "messages": messages, "stream": False, **llm_options}
    async with httpx.AsyncClient(timeout=180.0) as c:
        r = await c.post(url, json=payload, headers=headers)
        if r.status_code == 200:
            data = r.json()
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content:
                    return str(content)
    return "抱歉，暫時無法處理您的請求。請稍後再試。"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """統一入口：解析身份 → 依 source 分流到 customer 或 internal"""
    start = time.monotonic()

    # 解析業務員身份
    identity = await resolve_identity(request.session_id, request.channel_key)
    persona_prefix = await build_persona_prompt(identity)

    if request.source == "internal":
        return await _handle_internal(request, identity, persona_prefix)
    return await _handle_customer(request, identity, persona_prefix)


async def _handle_customer(request: ChatRequest, identity: dict, persona_prefix: str) -> ChatResponse:
    from bpa.welfare_secretary.customer_router import handle_customer_message
    return await handle_customer_message(request, identity, persona_prefix)


async def _handle_internal(request: ChatRequest, identity: dict, persona_prefix: str) -> ChatResponse:
    from bpa.welfare_secretary.internal_router import handle_internal_message
    return await handle_internal_message(request, identity, persona_prefix)
