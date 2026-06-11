"""
@file        Inquiry Router
@description 提供 AIQ Inquiry 分析、狀態查詢、重置與 SSE 串流端點。
@lastUpdate  2026-04-18 19:34:34
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from importlib import import_module

from fastapi import APIRouter, Depends, Header, HTTPException
from starlette.responses import Response

from aiq_agent.inquiry.manager import InquiryManager
from aiq_agent.inquiry.models import InquiryRequest, InquiryResult, InquiryState
from aiq_agent.routers.signals import engine
from shared.security import verify_internal_token

router = APIRouter(
    tags=["AIQ Inquiry"],
    dependencies=[Depends(verify_internal_token)],
)
manager = InquiryManager()


@router.post("/inquiry/analyze", response_model=InquiryResult)
def analyze_inquiry(
    request: InquiryRequest,
    x_user_key: str = Header(..., alias="X-User-Key"),
) -> InquiryResult:
    """Analyze an inquiry request using the current perception context."""
    import asyncio
    working_context = engine.get_context(user_key=x_user_key)
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(manager.process_inquiry(
        user_key=x_user_key,
        working_context=working_context,
        request=request,
    ))


@router.get("/inquiry/state", response_model=InquiryState)
def get_inquiry_state(
    x_user_key: str = Header(..., alias="X-User-Key"),
) -> InquiryState:
    """Return the current inquiry state for the given user."""
    state = manager.get_state(x_user_key)
    if state is None:
        raise HTTPException(status_code=404, detail="Inquiry state not found.")
    return state


@router.post("/inquiry/reset")
def reset_inquiry_state(
    x_user_key: str = Header(..., alias="X-User-Key"),
) -> dict[str, str]:
    """Reset the inquiry state for the given user."""
    manager.reset_state(x_user_key)
    return {"status": "success", "user_key": x_user_key}


@router.get("/inquiry/stream")
async def stream_inquiry(
    x_user_key: str = Header(..., alias="X-User-Key"),
) -> Response:
    """Open a basic inquiry SSE stream with heartbeat events."""

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        yield {
            "event": "connected",
            "data": json.dumps({"user_key": x_user_key, "status": "connected"}),
        }
        while True:
            await asyncio.sleep(15)
            yield {
                "event": "heartbeat",
                "data": json.dumps({"user_key": x_user_key, "status": "alive"}),
            }

    event_source_response = _load_event_source_response()
    return event_source_response(event_generator())


def _load_event_source_response() -> type[Response]:
    """Load EventSourceResponse lazily to avoid hard dependency at import time."""
    try:
        module = import_module("sse_starlette.sse")
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="sse-starlette is not installed.") from exc
    event_source_response = getattr(module, "EventSourceResponse", None)
    if not isinstance(event_source_response, type) or not issubclass(event_source_response, Response):
        raise HTTPException(status_code=503, detail="sse-starlette is required for /inquiry/stream endpoint.")
    return event_source_response
