import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="TWHC Memory Agent Service",
    description="AI-Augmented Memory System for persistent, long-term memory capabilities.",
    version="1.1.0",
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

from memory_agent.routers.memory import router as memory_router
from memory_agent.routers.session import router as session_router
from memory_agent.routers.working import router as working_router
from memory_agent.routers.consolidation import router as consolidation_router
from memory_agent.routers.index import router as index_router

app.include_router(memory_router)
app.include_router(session_router)
app.include_router(working_router)
app.include_router(consolidation_router)
app.include_router(index_router)


@app.get("/")
def root() -> dict:
    return {
        "service": "memory_agent",
        "description": "AI-Augmented Memory System",
        "version": "1.1.0",
        "port": "8008",
        "status": "running",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "memory_agent"}
