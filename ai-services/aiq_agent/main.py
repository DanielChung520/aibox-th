"""
@file        AIQ Agent 服務入口
@description 艾企助手 L3 Perception + Inquiry Layer service.
@lastUpdate  2026-04-18 20:12:44
@author      Daniel Chung
@version     2.1.0
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aiq_agent.routers.inquiry import manager as inquiry_manager
from aiq_agent.routers.inquiry import router as inquiry_router
from aiq_agent.routers.learning import manager as learning_manager
from aiq_agent.routers.learning import router as learning_router
from aiq_agent.routers.signals import router as signals_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage startup/shutdown lifecycle."""
    yield
    await inquiry_manager._llm_client.close()
    await learning_manager.close()


app = FastAPI(
    title="AIQ Agent",
    description="艾企助手 L3 Perception + Inquiry Layer service.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals_router)
app.include_router(inquiry_router)
app.include_router(learning_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Return the service health status."""
    return {
        "status": "ok",
        "service": "aiq_agent",
        "port": "8009",
    }
