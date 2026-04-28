from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from shared.conversation import QueryEngine
from .agent import chat_with_agent
from .config import (
    get_agent_llm_config,
    get_conversation_history,
    save_message,
)

router = APIRouter(tags=["Ragic Helper"])


class ChatRequest(BaseModel):
    agent_key: str
    session_id: str
    message: str
    user_id: Optional[str] = None
    platform: Optional[str] = "line"
    image_content: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    agent_key: str
    intent_matched: bool = False


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if not request.agent_key:
        raise HTTPException(status_code=400, detail="agent_key is required")

    if not request.message:
        raise HTTPException(status_code=400, detail="message is required")

    session_id = request.session_id or f"agent:{request.agent_key}:{request.user_id or 'anonymous'}"

    agent_config = await get_agent_llm_config(request.agent_key)

    history = await get_conversation_history(session_id, limit=10)

    await save_message(session_id, "user", request.message, request.platform or "line")

    images: list[str] | None = None
    if request.image_content:
        images = [request.image_content]

    response_text = await chat_with_agent(
        query=request.message,
        session_id=session_id,
        agent_config=agent_config,
        conversation_history=history,
        images=images,
        user_id=request.user_id or "anonymous",
    )

    await save_message(session_id, "assistant", response_text, request.platform or "line")

    return ChatResponse(
        response=response_text,
        session_id=session_id,
        agent_key=request.agent_key,
        intent_matched=False,
    )


@router.get("/session/{session_id}/history")
async def get_history(session_id: str, limit: int = 20):
    history = await get_conversation_history(session_id, limit=limit)
    return {"session_id": session_id, "history": history, "count": len(history)}


@router.get("/sessions")
async def list_sessions(platform: str = Query("line"), channel_id: str = Query(""), limit: int = Query(50)):
    engine = QueryEngine()
    raw = await engine.get_sessions_by_platform(platform, limit=limit)
    if channel_id:
        raw = [s for s in raw if channel_id in s.get("session_id", "")]
    import httpx, os, base64
    sessions_out = []
    name_cache: dict[str, str] = {}
    for s in raw:
        sid = s.get("session_id", "")
        entry = dict(s)
        if sid not in name_cache:
            name_cache[sid] = ""
        sessions_out.append(entry)
    # 批次查 metadata 中的 user_name 和 group_name
    for sid in list(name_cache.keys()):
        try:
            cred = f"{os.getenv('ARANGO_USER','root')}:{os.getenv('ARANGO_PASSWORD','')}"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Basic {base64.b64encode(cred.encode()).decode()}",
            }
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{os.getenv('ARANGO_URL','http://localhost:8529')}/_db/{os.getenv('ARANGO_DATABASE','abc_desktop')}/_api/cursor",
                    json={"query": "FOR m IN bot_chat_sessions FILTER m.session_id == @sid AND m.metadata != null LIMIT 1 RETURN m.metadata", "bindVars": {"sid": sid}},
                    headers=headers,
                )
                if resp.status_code in (200, 201):
                    rows = resp.json().get("result", [])
                    if rows:
                        meta = rows[0]
                        name_cache[sid] = meta.get("user_name", "") or meta.get("group_name", "") or ""
        except Exception:
            pass
    for s in sessions_out:
        sid = s.get("session_id", "")
        if name_cache.get(sid):
            if ":group:" in sid:
                s["group_name"] = name_cache[sid]
            else:
                s["user_name"] = name_cache[sid]
    return {"sessions": sessions_out, "count": len(sessions_out)}


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    pass
    return {"session_id": session_id, "status": "deleted"}