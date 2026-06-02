"""
Backup Agent Service - ArangoDB & Qdrant Backup Management

# Last Update: 2026-04-04
# Author: Daniel Chung
# Version: 1.0.0
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backup_agent.routers.backup import router as backup_router

app = FastAPI(
    title="TWHC Backup Agent",
    description="ArangoDB & Qdrant backup and restore service",
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

app.include_router(backup_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "backup_agent", "version": "1.0.0", "port": "8010"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "backup_agent"}
