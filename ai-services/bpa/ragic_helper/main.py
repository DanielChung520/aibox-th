"""
Ragic Helper Agent - LINE Bot Agent with Intent Detection, Hybrid RAG, and Multi-turn Dialogue

# Last Update: 2026-04-20
# Author: Daniel Chung
# Version: 1.0.0
"""

import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ragic_helper.router import router as ragic_router

STARTED_AT = datetime.now(timezone.utc).isoformat()

app = FastAPI(
    title="AIBox Ragic Helper Agent",
    description="LINE Bot Agent with Intent Detection, Hybrid RAG, and Multi-turn Dialogue",
    version="1.0.0",
)

ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:1420,http://localhost:6500",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ragic_router, prefix="/ragic", tags=["Ragic Helper"])

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "ragic-helper",
        "version": "1.0.0",
        "description": "Ragic Helper Agent - LINE Bot with Intent Detection, Hybrid RAG, Multi-turn Dialogue",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ragic-helper", "started_at": STARTED_AT}
