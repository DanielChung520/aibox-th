import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AIBox Knowledge Agent Service",
    description="RAG-based knowledge retrieval service.",
    version="2.1.0",
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

from knowledge_agent.routers.hybrid import router as hybrid_router
from knowledge_agent.routers.intent import router as intent_router
from knowledge_agent.routers.search import router as search_router
from knowledge_agent.routers.pipeline import router as pipeline_router

app.include_router(hybrid_router)
app.include_router(intent_router)
app.include_router(search_router)
app.include_router(pipeline_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "knowledge_agent",
        "description": "RAG-based knowledge retrieval",
        "version": "2.1.0",
        "port": "8007",
        "status": "running",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "knowledge_agent"}
