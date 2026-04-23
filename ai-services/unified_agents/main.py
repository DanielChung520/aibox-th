import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.logging import LoggingMiddleware, setup_logging

setup_logging("unified_agents", os.getenv("LOG_LEVEL", "INFO"))

STARTED_AT = datetime.now(timezone.utc).isoformat()

app = FastAPI(
    title="AIBox Unified Agents",
    description="Unified entry point for all AI agents: data_agent, knowledge_agent, memory_agent, backup_agent, mcp_tools",
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
app.add_middleware(LoggingMiddleware, service_name="unified_agents")

from data_agent.intent_rag.router import router as intent_rag_router  # noqa: E402
from data_agent.intent_rag.da_sync import router as da_sync_router  # noqa: E402
from data_agent.intent_rag.da_intents_sync import router as da_intents_router  # noqa: E402
from data_agent.query.router import router as query_router  # noqa: E402
from data_agent.ragic.router import router as ragic_router  # noqa: E402
from data_agent.ragic.router_import import router as ragic_import_router  # noqa: E402

app.include_router(intent_rag_router, prefix="/da/intent-rag", tags=["DA Intent RAG"])
app.include_router(da_sync_router, prefix="/da/intent-rag", tags=["DA Expressions Sync"])
app.include_router(da_intents_router, prefix="/da/intent-rag", tags=["DA Intents Sync"])
app.include_router(query_router, prefix="/da/query", tags=["DA Query"])
app.include_router(ragic_router, prefix="/da/ragic", tags=["DA Ragic"])
app.include_router(ragic_import_router, prefix="/da/ragic", tags=["DA Ragic Import"])

from backup_agent.routers.backup import router as backup_router  # noqa: E402

app.include_router(backup_router, prefix="/backup", tags=["Backup"])

from unified_agents.platforms.line.router import router as line_router  # noqa: E402
from unified_agents.platforms.line.webhook import router as line_webhook_router  # noqa: E402

app.include_router(line_router, prefix="/platforms/line", tags=["LINE Platform"])
app.include_router(line_webhook_router, tags=["LINE Webhook"])

from tools.process_advisor.router import app as process_advisor_app  # noqa: E402
from tools.report_agent.router import app as report_agent_app  # noqa: E402
from tools.multimedia_analyzer.router import app as multimedia_analyzer_app  # noqa: E402

app.mount("/mcp/process-advisor", process_advisor_app)
app.mount("/mcp/report-agent", report_agent_app)
app.mount("/mcp/multimedia-analyzer", multimedia_analyzer_app)

from knowledge_agent.routers.hybrid import router as hybrid_router  # noqa: E402
from knowledge_agent.routers.intent import router as intent_router  # noqa: E402
from knowledge_agent.routers.search import router as search_router  # noqa: E402
from knowledge_agent.routers.pipeline import router as pipeline_router  # noqa: E402

app.include_router(hybrid_router, prefix="/ka", tags=["KA HybridRAG"])
app.include_router(intent_router, prefix="/ka", tags=["KA Intent"])
app.include_router(search_router, prefix="/ka", tags=["KA Search"])
app.include_router(pipeline_router, prefix="/ka", tags=["KA Pipeline"])

from memory_agent.routers.memory import router as memory_router  # noqa: E402
from memory_agent.routers.session import router as session_router  # noqa: E402
from memory_agent.routers.working import router as working_router  # noqa: E402
from memory_agent.routers.consolidation import router as consolidation_router  # noqa: E402
from memory_agent.routers.index import router as index_router  # noqa: E402

app.include_router(memory_router, prefix="/memory", tags=["Memory"])

from bpa.ragic_helper.router import router as ragic_router  # noqa: E402

app.include_router(ragic_router, prefix="/ragic", tags=["Ragic Helper"])
app.include_router(session_router, prefix="/memory", tags=["Memory Session"])
app.include_router(working_router, prefix="/memory", tags=["Memory Working"])
app.include_router(consolidation_router, prefix="/memory", tags=["Memory Consolidation"])
app.include_router(index_router, prefix="/memory", tags=["Memory Index"])


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "unified_agents",
        "version": "1.0.0",
        "agents": ["data_agent", "knowledge_agent", "memory_agent", "backup_agent", "mcp_tools"],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "unified_agents", "started_at": STARTED_AT}


@app.get("/da/health")
def da_health() -> dict[str, str]:
    return {"status": "ok", "service": "data_agent", "started_at": STARTED_AT}


@app.get("/backup/health")
def backup_health() -> dict[str, str]:
    return {"status": "ok", "service": "backup_agent", "started_at": STARTED_AT}


@app.get("/mcp/health")
def mcp_health() -> dict[str, str]:
    return {"status": "ok", "service": "mcp_tools", "started_at": STARTED_AT}


@app.get("/ka/health")
def ka_health() -> dict[str, str]:
    return {"status": "ok", "service": "knowledge_agent", "started_at": STARTED_AT}


@app.get("/memory/health")
def memory_health() -> dict[str, str]:
    return {"status": "ok", "service": "memory_agent", "started_at": STARTED_AT}


@app.get("/ragic/health")
def ragic_health() -> dict[str, str]:
    return {"status": "ok", "service": "ragic-helper", "started_at": STARTED_AT}


@app.get("/celery/health")
def celery_health() -> dict[str, str]:
    try:
        from celery_app.app import app as celery_app

        inspector = celery_app.control.inspect()
        stats = inspector.stats()
        if stats:
            return {"status": "ok", "service": "celery", "started_at": STARTED_AT}
        return {"status": "error", "service": "celery", "started_at": STARTED_AT}
    except Exception:
        return {"status": "error", "service": "celery", "started_at": STARTED_AT}
