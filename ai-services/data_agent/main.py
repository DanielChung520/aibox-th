"""
Data Agent Service - Unified Data Query & Intent Management

Combines intent RAG (Qdrant-based intent matching, embedding sync)
and query execution (NL→AQL, NL→SQL pipeline) under a single FastAPI app.

# Last Update: 2026-04-13 05:49:05
# Author: Daniel Chung
# Version: 2.3.0
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from data_agent.intent_rag.router import router as intent_rag_router
from data_agent.intent_rag.da_sync import router as da_sync_router
from data_agent.intent_rag.da_intents_sync import router as da_intents_router
from data_agent.query.router import router as query_router
from data_agent.ragic.router import router as ragic_router
from data_agent.ragic.router_import import router as ragic_import_router

app = FastAPI(
    title="AIBox Data Agent Service",
    description="Unified data query and intent management service.",
    version="2.1.0",
)

# CORS configuration
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

# Mount sub-routers
app.include_router(intent_rag_router, prefix="/intent-rag", tags=["Intent RAG"])
app.include_router(da_sync_router, prefix="/intent-rag", tags=["DA Expressions Sync"])
app.include_router(da_intents_router, prefix="/intent-rag", tags=["DA Intents Sync"])
app.include_router(query_router, prefix="/query", tags=["Query"])
app.include_router(ragic_router, prefix="/ragic", tags=["Ragic"])
app.include_router(ragic_import_router, prefix="/ragic", tags=["Ragic Import"])


@app.get("/")
def root() -> dict[str, str]:
    """Service information."""
    return {
        "service": "data_agent",
        "description": "Unified data query and intent management",
        "version": "2.0.0",
        "port": "8003",
        "status": "running",
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok", "service": "data_agent"}
