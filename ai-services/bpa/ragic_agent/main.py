"""
@file        Ragic Agent — 服務入口
@description FastAPI 應用入口，掛載 router
@lastUpdate  2026-04-27 18:30:00
@author      AI Agent
@version     1.0.0
"""

import os

from fastapi import FastAPI

from bpa.ragic_agent.router import router

app = FastAPI(title="Ragic Agent", description="艾企 Ragic 小幫手", version="1.0.0")
app.include_router(router, prefix="/ragic-agent", tags=["Ragic Agent"])

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ragic_agent", "port": os.environ.get("RAGIC_AGENT_PORT", "8012")}
