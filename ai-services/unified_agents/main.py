import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.logging import LoggingMiddleware, setup_logging

setup_logging("unified_agents", os.getenv("LOG_LEVEL", "INFO"))

STARTED_AT = datetime.now(timezone.utc).isoformat()

app = FastAPI(
    title="TWHC Unified Agents",
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
from data_agent.trace_engine.router import router as trace_router  # noqa: E402

app.include_router(intent_rag_router, prefix="/da/intent-rag", tags=["DA Intent RAG"])
app.include_router(da_sync_router, prefix="/da/intent-rag", tags=["DA Expressions Sync"])
app.include_router(da_intents_router, prefix="/da/intent-rag", tags=["DA Intents Sync"])
app.include_router(query_router, prefix="/da/query", tags=["DA Query"])
app.include_router(ragic_router, prefix="/da/ragic", tags=["DA Ragic"])
app.include_router(ragic_import_router, prefix="/da/ragic", tags=["DA Ragic Import"])
app.include_router(trace_router, prefix="/da/trace-engine", tags=["DA Trace Engine"])

from backup_agent.routers.backup import router as backup_router  # noqa: E402

app.include_router(backup_router, prefix="/backup", tags=["Backup"])

from unified_agents.platforms.line.router import router as line_router  # noqa: E402
from unified_agents.platforms.line.webhook import router as line_webhook_router  # noqa: E402

app.include_router(line_router, prefix="/platforms/line", tags=["LINE Platform"])
app.include_router(line_webhook_router, tags=["LINE Webhook"])

from tools.process_advisor.router import app as process_advisor_app  # noqa: E402
from tools.report_agent.router import app as report_agent_app  # noqa: E402
from tools.multimedia_analyzer.router import app as multimedia_analyzer_app  # noqa: E402
from market_intel.main import app as market_intel_app  # noqa: E402

app.mount("/mcp/process-advisor", process_advisor_app)
app.mount("/mcp/report-agent", report_agent_app)
app.mount("/mcp/multimedia-analyzer", multimedia_analyzer_app)
app.mount("/market-intel", market_intel_app)

from bpa.ragic_agent.router import router as ragic_agent_router  # noqa: E402
app.include_router(ragic_agent_router, prefix="/ragic-agent")

from bpa.order_secretary.router import router as order_secretary_router  # noqa: E402
from bpa.order_secretary.preorder import router as order_preorder_router  # noqa: E402
app.include_router(order_secretary_router, prefix="/order-secretary")
app.include_router(order_preorder_router, prefix="/order-secretary")

from bpa.preorder_agent.router import router as preorder_agent_router  # noqa: E402
app.include_router(preorder_agent_router, prefix="/preorder-agent")

from bpa.esg_helper.router import router as esg_helper_router  # noqa: E402
app.include_router(esg_helper_router, prefix="/esg-helper")

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

from bpa.welfare_secretary.main import router as welfare_secretary_router  # noqa: E402
app.include_router(welfare_secretary_router, prefix="/welfare-secretary")

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


class ToolCallRequest(BaseModel):
    tool: str
    parameters: dict[str, Any]


class ToolResultResponse(BaseModel):
    tool: str
    success: bool
    result: Any = None
    error: str | None = None
    async_mode: bool = False


@app.post("/mcp/execute", response_model=ToolResultResponse, tags=["MCP Execute"])
async def mcp_execute(call: ToolCallRequest) -> ToolResultResponse:
    """統一的 MCP 工具執行端點"""
    try:
        if call.tool == "tool_reports":
            from tools.report_generator.tool_reports import tool_reports_execute
            output = await tool_reports_execute(call.parameters)
            return ToolResultResponse(
                tool=call.tool,
                success=output.success,
                result={
                    "report_url": output.report_url,
                    "filename": output.filename,
                    "title": output.title,
                    "chart_type": output.chart_type,
                    "analysis_summary": output.analysis_summary,
                    "size_bytes": output.size_bytes,
                    "warnings": output.warnings,
                } if output.success else None,
                error=output.error,
            )

        import httpx
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"http://localhost:8004/execute",
                json={"tool": call.tool, "parameters": call.parameters},
            )
            if resp.status_code == 200:
                data = resp.json()
                return ToolResultResponse(
                    tool=data.get("tool", call.tool),
                    success=data.get("success", False),
                    result=data.get("result"),
                    error=data.get("error"),
                )
            return ToolResultResponse(
                tool=call.tool,
                success=False,
                error=f"mcp_tools error: {resp.status_code}",
            )
    except Exception as e:
        return ToolResultResponse(
            tool=call.tool,
            success=False,
            error=str(e),
        )


@app.post("/mcp/execute-async", tags=["MCP Execute"])
async def mcp_execute_async(call: ToolCallRequest) -> dict[str, Any]:
    import json as _json
    import httpx

    gateway = os.getenv("GATEWAY_URL", "http://localhost:6500")

    if call.tool != "tool_reports":
        return {"success": False, "error": f"Async not supported for tool: {call.tool}"}

    report_name = call.parameters.get("report_goal", "未命名報告")[:20]
    table_id = call.parameters.get("table_id", "unknown")
    username = call.parameters.get("username", "anonymous")
    schedule_type = call.parameters.get("schedule_type")
    schedule_time = call.parameters.get("schedule_time")

    schedule_params = None
    if schedule_type and schedule_time:
        schedule_params = _json.dumps({
            "report_goal": call.parameters.get("report_goal"),
            "preferred_chart": call.parameters.get("preferred_chart"),
            "field_hints": call.parameters.get("field_hints"),
            "special_notes": call.parameters.get("special_notes"),
            "legend_show": call.parameters.get("legend_show", True),
            "legend_position": call.parameters.get("legend_position", "bottom"),
            "hints": call.parameters.get("hints"),
        }, ensure_ascii=False)

    async with httpx.AsyncClient(timeout=10.0) as client:
        create_resp = await client.post(
            f"{gateway}/api/v1/da/schema-reports",
            json={
                "table_id": table_id,
                "report_name": report_name,
                "username": username,
                "status": "generating",
                "schedule_type": schedule_type,
                "schedule_time": schedule_time,
                "schedule_days": call.parameters.get("schedule_days"),
                "schedule_params": schedule_params,
            },
        )
        if create_resp.status_code not in (200, 201):
            return {"success": False, "error": "Failed to create report record"}
        report = create_resp.json().get("data", {})

    from celery_app.tasks import generate_report_task

    result = generate_report_task.delay(
        report_key=report["_key"],
        params=call.parameters,
        gateway_url=gateway,
    )

    return {
        "success": True,
        "async": True,
        "report_key": report["_key"],
        "task_id": result.id,
        "status": "generating",
        "report_name": report_name,
    }


@app.get("/ka/health")
def ka_health() -> dict[str, str]:
    return {"status": "ok", "service": "knowledge_agent", "started_at": STARTED_AT}


@app.get("/memory/health")
def memory_health() -> dict[str, str]:
    return {"status": "ok", "service": "memory_agent", "started_at": STARTED_AT}


@app.get("/ragic/health")
def ragic_health() -> dict[str, str]:
    return {"status": "ok", "service": "ragic-helper", "started_at": STARTED_AT}


@app.get("/order-secretary/health")
def order_secretary_health() -> dict[str, str]:
    return {"status": "ok", "service": "order_secretary", "started_at": STARTED_AT}


@app.get("/media/proxy/{path:path}")
async def media_proxy(path: str):
    """SeaweedFS 媒體檔案代理 — 將 /media/proxy/line/xxx 轉發到 SeaweedFS"""
    import httpx
    seaweed_url = os.getenv("SEAWEED_URL", "http://localhost:8888")
    target_url = f"{seaweed_url}/{path}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(target_url)
        from fastapi.responses import Response
        media_type = resp.headers.get("content-type", "application/octet-stream")
        return Response(content=resp.content, media_type=media_type)


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
