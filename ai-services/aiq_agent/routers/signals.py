"""Signal and intent-state router for AIQ Agent.

@lastUpdate  2026-04-18 21:33:24
@author      AI Agent
@version     2.0.0
"""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, Depends, Header

from aiq_agent.perception.engine import PerceptionEngine
from aiq_agent.perception.models import CommitRequest, SignalPushRequest, WorkingContext
from shared.security import verify_internal_token

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["AIQ Signals"],
    dependencies=[Depends(verify_internal_token)],
)
engine = PerceptionEngine()

MAX_SIGNALS_PER_PUSH = int(os.environ.get("AIQ_MAX_SIGNALS_PER_PUSH", "100"))
DATA_AGENT_URL = os.environ.get("DATA_AGENT_URL", "http://localhost:8003")
KNOWLEDGE_AGENT_URL = os.environ.get("KNOWLEDGE_AGENT_URL", "http://localhost:8007")
COMMIT_TIMEOUT = float(os.environ.get("AIQ_COMMIT_TIMEOUT", "120.0"))
KA_SEARCH_TOP_K = int(os.environ.get("AIQ_KA_SEARCH_TOP_K", "5"))


@router.post("/signals/push", response_model=WorkingContext)
def push_signals(
    request: SignalPushRequest,
    x_user_key: str = Header(..., alias="X-User-Key"),
) -> WorkingContext:
    """Push frontend signals and return the updated working context."""
    signals = request.signals[:MAX_SIGNALS_PER_PUSH]
    return engine.process_signals(user_key=x_user_key, signals=signals)


@router.get("/intent-state", response_model=WorkingContext)
def get_intent_state(
    x_user_key: str = Header(..., alias="X-User-Key"),
) -> WorkingContext:
    """Return the current working context for the given user."""
    return engine.get_context(user_key=x_user_key)


@router.post("/intent-state/commit")
async def commit_intent_state(
    request: CommitRequest,
    x_user_key: str = Header(..., alias="X-User-Key"),
) -> dict[str, object]:
    """Route a committed hypothesis to the appropriate downstream agent."""
    logger.info(
        "Committed hypothesis user=%s id=%s path=%s",
        x_user_key,
        request.hypothesis_id,
        request.execution_path,
    )

    if request.execution_path == "route_to_data":
        return await _route_to_data_agent(request, x_user_key)

    if request.execution_path == "knowledge_search":
        return await _route_to_knowledge_agent(request, x_user_key)

    return {
        "status": "success",
        "action": "chat",
        "execution_path": request.execution_path,
        "user_key": x_user_key,
        "hypothesis_id": request.hypothesis_id,
    }


async def _route_to_data_agent(
    request: CommitRequest, user_key: str
) -> dict[str, object]:
    enriched_query = _build_enriched_query(request)
    try:
        async with httpx.AsyncClient(timeout=COMMIT_TIMEOUT) as client:
            response = await client.post(
                f"{DATA_AGENT_URL.rstrip('/')}/query/nl2sql",
                json={"natural_language": enriched_query},
                headers={
                    "X-User-Key": user_key,
                    "X-Internal-Token": os.environ.get("INTERNAL_SERVICE_TOKEN", ""),
                },
            )
            response.raise_for_status()
            da_result: dict[str, object] = response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("DA returned %s: %s", exc.response.status_code, exc.response.text)
        return {
            "status": "error",
            "action": "route_to_data",
            "error": f"Data Agent returned {exc.response.status_code}",
        }
    except httpx.HTTPError as exc:
        logger.error("DA connection error: %s", exc)
        return {
            "status": "error",
            "action": "route_to_data",
            "error": "Data Agent unreachable",
        }

    return {
        "status": "success",
        "action": "route_to_data",
        "hypothesis_id": request.hypothesis_id,
        "result": da_result,
    }


def _build_enriched_query(request: CommitRequest) -> str:
    parts: list[str] = []
    ctx = request.context

    if ctx.table_name:
        parts.append(f"針對「{ctx.table_name}」表")
    if ctx.domain_name:
        parts.append(f"（{ctx.domain_name}模組）")
    if ctx.field_hints:
        parts.append(f"，關注欄位：{', '.join(ctx.field_hints)}")

    parts.append(f"，{request.natural_language}" if parts else request.natural_language)
    return "".join(parts)


async def _route_to_knowledge_agent(
    request: CommitRequest, user_key: str
) -> dict[str, object]:
    try:
        async with httpx.AsyncClient(timeout=COMMIT_TIMEOUT) as client:
            response = await client.post(
                f"{KNOWLEDGE_AGENT_URL.rstrip('/')}/search",
                json={"query": request.natural_language, "top_k": KA_SEARCH_TOP_K},
                headers={
                    "X-User-Key": user_key,
                    "X-Internal-Token": os.environ.get("INTERNAL_SERVICE_TOKEN", ""),
                },
            )
            response.raise_for_status()
            ka_result: dict[str, object] = response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("KA returned %s: %s", exc.response.status_code, exc.response.text)
        return {
            "status": "error",
            "action": "knowledge_search",
            "error": f"Knowledge Agent returned {exc.response.status_code}",
        }
    except httpx.HTTPError as exc:
        logger.error("KA connection error: %s", exc)
        return {
            "status": "error",
            "action": "knowledge_search",
            "error": "Knowledge Agent unreachable",
        }

    return {
        "status": "success",
        "action": "knowledge_search",
        "hypothesis_id": request.hypothesis_id,
        "result": ka_result,
    }
