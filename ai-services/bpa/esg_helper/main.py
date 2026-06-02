"""
@file        ESG小幫手 — 服務入口
@description FastAPI 應用入口，掛載 router
@lastUpdate  2026-05-16 00:02:00
@author      System
@version     1.0.0
"""

import os

from fastapi import FastAPI

from bpa.esg_helper.router import router

app = FastAPI(title="ESG Helper", description="TWHC ESG 小幫手 — ESG 領域 AI 助理", version="1.0.0")
app.include_router(router, prefix="/esg-helper", tags=["ESG Helper"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "esg_helper", "port": os.environ.get("ESG_HELPER_PORT", "8011")}
