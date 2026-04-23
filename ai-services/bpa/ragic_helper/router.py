from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

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


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    pass
    return {"session_id": session_id, "status": "deleted"}