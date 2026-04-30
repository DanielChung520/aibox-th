"""
@file        訂單小秘 — 服務入口
@description FastAPI 應用入口，掛載 router
@lastUpdate  2026-04-28 22:41:00
@author      AI Agent
@version     1.0.0
"""

import os

from fastapi import FastAPI

from bpa.order_secretary.router import router

app = FastAPI(title="Order Secretary", description="AIBox 訂單小秘 — 訂單解析與管理助手", version="1.0.0")
app.include_router(router, prefix="/order-secretary", tags=["Order Secretary"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "order_secretary", "port": os.environ.get("ORDER_SECRETARY_PORT", "8013")}
