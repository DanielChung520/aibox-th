import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from unified_agents.platforms.line.models import (
    CreateOfficialAccountRequest,
    CreateChannelRequest,
    UpdateChannelRequest,
    PublishChannelRequest,
    TestConnectionResult,
)
from unified_agents.platforms.line.services import db
from unified_agents.platforms.line.services.line_api import test_channel_connection

router = APIRouter(tags=["LINE Platform"])
logger = logging.getLogger(__name__)


@router.get("/official-accounts")
async def list_official_accounts():
    await db.ensure_collections()
    accounts = await db.list_official_accounts()
    for acc in accounts:
        channels = await db.list_channels(acc["_key"])
        acc["channels"] = channels
    return {"code": 200, "data": accounts}


@router.post("/official-accounts")
async def create_official_account(req: CreateOfficialAccountRequest):
    await db.ensure_collections()
    data = {
        "_key": f"oa_{datetime.utcnow().timestamp()}",
        "provider_name": req.provider_name,
        "name": req.name,
    }
    result = await db.create_official_account(data)
    return {"code": 200, "data": result}


@router.get("/official-accounts/{key}")
async def get_official_account(key: str):
    await db.ensure_collections()
    account = await db.get_official_account(key)
    if not account:
        raise HTTPException(status_code=404, detail="官方帳號不存在")
    channels = await db.list_channels(key)
    account["channels"] = channels
    return {"code": 200, "data": account}


@router.put("/official-accounts/{key}")
async def update_official_account(key: str, data: dict):
    await db.ensure_collections()
    result = await db.update_official_account(key, data)
    if not result:
        raise HTTPException(status_code=404, detail="官方帳號不存在")
    return {"code": 200, "data": result}


@router.delete("/official-accounts/{key}")
async def delete_official_account(key: str):
    await db.ensure_collections()
    success = await db.delete_official_account(key)
    if not success:
        raise HTTPException(status_code=404, detail="官方帳號不存在")
    return {"code": 200, "message": "已刪除"}


@router.post("/official-accounts/{key}/channels")
async def create_channel(key: str, req: CreateChannelRequest):
    await db.ensure_collections()
    account = await db.get_official_account(key)
    if not account:
        raise HTTPException(status_code=404, detail="官方帳號不存在")
    data = {
        "_key": f"ch_{datetime.utcnow().timestamp()}",
        "official_account_key": key,
        "channel_name": req.channel_name,
        "channel_id": req.channel_id,
        "channel_secret": req.channel_secret,
        "channel_access_token": req.channel_access_token,
        "channel_icon": req.channel_icon,
        "channel_description": req.channel_description,
    }
    result = await db.create_channel(data)
    return {"code": 200, "data": result}


@router.get("/channels/{channel_key}")
async def get_channel(channel_key: str):
    await db.ensure_collections()
    channel = await db.get_channel(channel_key)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel 不存在")
    return {"code": 200, "data": channel}


@router.put("/channels/{channel_key}")
async def update_channel(channel_key: str, req: UpdateChannelRequest):
    await db.ensure_collections()
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    result = await db.update_channel(channel_key, data)
    if not result:
        raise HTTPException(status_code=404, detail="Channel 不存在")
    return {"code": 200, "data": result}


@router.delete("/channels/{channel_key}")
async def delete_channel(channel_key: str):
    await db.ensure_collections()
    success = await db.delete_channel(channel_key)
    if not success:
        raise HTTPException(status_code=404, detail="Channel 不存在")
    return {"code": 200, "message": "已刪除"}


@router.post("/channels/{channel_key}/test-connection")
async def test_connection(channel_key: str):
    await db.ensure_collections()
    channel = await db.get_channel(channel_key)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel 不存在")

    # Phase 1: 驗證 LINE Channel 連線
    token = channel.get("channel_access_token")
    if not token:
        return {"code": 200, "data": TestConnectionResult(success=False, error="未設定 Access Token")}
    line_result = await test_channel_connection(token)
    if not line_result["success"]:
        return {"code": 200, "data": TestConnectionResult(**line_result)}

    # 更新 LINE 連線資訊
    await db.update_channel(channel_key, {
        "bot_user_id": line_result.get("bot_user_id"),
        "last_connected_at": datetime.utcnow().isoformat(),
    })

    # Phase 2: 若有 linked_agent_key，驗證 Agent 端點
    agent_key = channel.get("linked_agent_key")
    agent_result = None
    if agent_key:
        agent = await db.get_agent(agent_key)
        if not agent:
            agent_result = {"success": False, "error": f"Agent ({agent_key}) 不存在"}
        else:
            endpoint_url = agent.get("endpoint_url", "")
            if not endpoint_url:
                agent_result = {"success": False, "error": f"Agent「{agent.get('name','')}」未設定 endpoint_url"}
            else:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(
                            endpoint_url,
                            json={
                                "session_id": f"test_{channel_key}",
                                "message": "你好，這是一則連線測試訊息",
                                "user_id": "tester",
                                "agent_key": agent_key,
                            },
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            reply = data.get("reply") or data.get("response", "")
                            agent_result = {
                                "success": True,
                                "bot_user_id": line_result.get("bot_user_id"),
                                "agent_name": agent.get("name"),
                                "agent_reply": reply[:100],
                            }
                        else:
                            agent_result = {"success": False, "error": f"Agent 回應異常 (HTTP {resp.status_code})"}
                except httpx.TimeoutException:
                    agent_result = {"success": False, "error": "Agent 端點連線逾時"}
                except httpx.RequestError as e:
                    agent_result = {"success": False, "error": f"Agent 端點無法連線: {e}"}

    merged = {
        "success": line_result["success"] and (agent_result is None or agent_result["success"]),
        "bot_user_id": line_result.get("bot_user_id"),
    }
    if agent_result:
        merged["agent_name"] = agent_result.get("agent_name")
        merged["agent_reply"] = agent_result.get("agent_reply")
        if not agent_result["success"]:
            merged["error"] = agent_result["error"]
    return {"code": 200, "data": merged}


class PublishResponse(BaseModel):
    success: bool
    message: str


@router.post("/channels/{channel_key}/publish", response_model=PublishResponse)
async def publish_channel(channel_key: str, req: PublishChannelRequest):
    await db.ensure_collections()
    channel = await db.get_channel(channel_key)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel 不存在")
    await db.update_channel(channel_key, {
        "publication_status": "published",
        "published_bot_key": req.bot_key,
        "published_bot_name": f"Bot {req.bot_key}",
    })
    return PublishResponse(success=True, message="已發布")


@router.delete("/channels/{channel_key}/publish", response_model=PublishResponse)
async def unpublish_channel(channel_key: str):
    await db.ensure_collections()
    channel = await db.get_channel(channel_key)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel 不存在")
    await db.update_channel(channel_key, {
        "publication_status": "unpublished",
        "published_bot_key": None,
        "published_bot_name": None,
    })
    return PublishResponse(success=True, message="已取消發布")