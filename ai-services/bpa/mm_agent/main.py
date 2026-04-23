"""
BPA MM Agent - Material Management Business Process Automation

Provides workflow automation and orchestration for SAP MM module.
Migrated from bpa/ root to bpa/mm_agent/ with port 8005.

# Last Update: 2026-03-23 18:40:25
# Author: Daniel Chung
# Version: 2.0.0
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

STARTED_AT = datetime.now(timezone.utc).isoformat()

app = FastAPI(
    title="AIBox BPA MM Agent",
    description="Material Management business process automation.",
    version="2.0.0",
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

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")
DATA_AGENT_URL = os.getenv("DATA_AGENT_URL", "http://localhost:8003")


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Individual step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStep(BaseModel):
    """A single step in a workflow execution."""
    id: str
    name: str
    action: str
    parameters: dict[str, object] = Field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Optional[dict[str, object]] = None
    error: Optional[str] = None


class Workflow(BaseModel):
    """A complete workflow execution."""
    id: str
    name: str
    description: Optional[str] = None
    steps: list[WorkflowStep]
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[dict[str, object]] = None


class WorkflowExecution(BaseModel):
    """Request to execute a workflow."""
    workflow_id: str
    parameters: dict[str, object] = Field(default_factory=dict)


# MM-specific workflow definitions
WORKFLOWS: dict[str, dict[str, object]] = {
    "mm_purchase_order": {
        "name": "MM Purchase Order Process",
        "description": "Create and process SAP MM purchase orders",
        "steps": [
            {"id": "1", "name": "Validate PO Data", "action": "validate_po",
             "parameters": {}},
            {"id": "2", "name": "Check Budget", "action": "check_budget",
             "parameters": {}},
            {"id": "3", "name": "Create PO", "action": "create_po",
             "parameters": {}},
            {"id": "4", "name": "Send Approval", "action": "send_approval",
             "parameters": {}},
        ],
    },
    "mm_goods_receipt": {
        "name": "MM Goods Receipt Process",
        "description": "Process goods receipt for purchase orders",
        "steps": [
            {"id": "1", "name": "Verify PO", "action": "verify_po",
             "parameters": {}},
            {"id": "2", "name": "Quality Check", "action": "quality_check",
             "parameters": {}},
            {"id": "3", "name": "Post GR", "action": "post_goods_receipt",
             "parameters": {}},
        ],
    },
    "mm_inventory_count": {
        "name": "MM Inventory Count",
        "description": "Physical inventory count and adjustment",
        "steps": [
            {"id": "1", "name": "Create Count Document", "action": "create_count",
             "parameters": {}},
            {"id": "2", "name": "Enter Counts", "action": "enter_counts",
             "parameters": {}},
            {"id": "3", "name": "Post Differences", "action": "post_diff",
             "parameters": {}},
        ],
    },
}


async def execute_step(
    step: WorkflowStep, context: dict[str, object]
) -> WorkflowStep:
    """Execute a single workflow step."""
    step.status = StepStatus.RUNNING

    try:
        match step.action:
            case "validate_po":
                step.result = {"valid": True, "message": "PO data validated"}
            case "check_budget":
                step.result = {"budget_ok": True, "remaining": 50000.0}
            case "create_po":
                po_number = f"PO-{uuid.uuid4().hex[:8].upper()}"
                step.result = {"po_number": po_number, "status": "created"}
            case "send_approval":
                step.result = {"approval_sent": True, "approver": "manager"}
            case "verify_po":
                step.result = {"po_verified": True}
            case "quality_check":
                step.result = {"quality_ok": True, "inspection": "passed"}
            case "post_goods_receipt":
                gr_number = f"GR-{uuid.uuid4().hex[:8].upper()}"
                step.result = {"gr_number": gr_number, "posted": True}
            case "create_count":
                step.result = {"count_doc": f"CD-{uuid.uuid4().hex[:6]}"}
            case "enter_counts":
                step.result = {"items_counted": 0}
            case "post_diff":
                step.result = {"adjustments": 0, "posted": True}
            case "query_data":
                # Call Data Agent for NL queries
                query_str = str(context.get("query", ""))
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{DATA_AGENT_URL}/query/query",
                        json={"natural_language": query_str},
                    )
                    response.raise_for_status()
                    step.result = response.json()
            case _:
                step.error = f"Unknown action: {step.action}"
                step.status = StepStatus.FAILED
                return step

        step.status = StepStatus.COMPLETED

    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)

    return step


@app.get("/")
def root() -> dict[str, str]:
    """Service information."""
    return {
        "service": "bpa_mm_agent",
        "description": "Material Management process automation",
        "version": "2.0.0",
        "port": "8005",
        "status": "running",
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok", "service": "bpa_mm_agent", "started_at": STARTED_AT}


@app.get("/workflows")
async def list_workflows() -> dict[str, object]:
    """List available MM workflows."""
    result: dict[str, object] = {"workflows": WORKFLOWS}
    return result


@app.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str) -> dict[str, object]:
    """Get workflow definition."""
    if workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")
    result: dict[str, object] = dict(WORKFLOWS[workflow_id])
    return result


@app.post("/execute")
async def execute_workflow(execution: WorkflowExecution) -> dict[str, object]:
    """Execute a workflow synchronously."""
    if execution.workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow_def = WORKFLOWS[execution.workflow_id]
    workflow_id = str(uuid.uuid4())
    steps_def = workflow_def.get("steps", [])
    step_list: list[dict[str, object]] = (
        steps_def if isinstance(steps_def, list) else []
    )

    steps = [
        WorkflowStep(
            id=str(s.get("id", "")),
            name=str(s.get("name", "")),
            action=str(s.get("action", "")),
            parameters=dict(s.get("parameters", {}))
            if isinstance(s.get("parameters"), dict) else {},
        )
        for s in step_list
    ]

    workflow = Workflow(
        id=workflow_id,
        name=str(workflow_def.get("name", "")),
        description=str(workflow_def.get("description", "")) or None,
        steps=steps,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    context: dict[str, object] = dict(execution.parameters)

    for step in workflow.steps:
        step = await execute_step(step, context)
        if step.status == StepStatus.FAILED:
            workflow.status = WorkflowStatus.FAILED
            workflow.completed_at = datetime.now(timezone.utc).isoformat()
            result: dict[str, object] = {
                "workflow": workflow.model_dump(),
                "success": False,
            }
            return result
        if step.result is not None:
            context[step.id] = step.result

    workflow.status = WorkflowStatus.COMPLETED
    workflow.completed_at = datetime.now(timezone.utc).isoformat()
    workflow.result = context

    result = {"workflow": workflow.model_dump(), "success": True}
    return result


@app.post("/execute-async")
async def execute_workflow_async(
    execution: WorkflowExecution,
) -> dict[str, str]:
    """Execute a workflow asynchronously."""
    if execution.workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")

    execution_id = str(uuid.uuid4())
    asyncio.create_task(
        _run_workflow_bg(
            execution.workflow_id, dict(execution.parameters), execution_id
        )
    )
    return {"execution_id": execution_id, "status": "started"}


async def _run_workflow_bg(
    workflow_id: str,
    parameters: dict[str, object],
    execution_id: str,
) -> None:
    """Run workflow in background."""
    workflow_def = WORKFLOWS[workflow_id]
    steps_def = workflow_def.get("steps", [])
    step_list: list[dict[str, object]] = (
        steps_def if isinstance(steps_def, list) else []
    )

    steps = [
        WorkflowStep(
            id=str(s.get("id", "")),
            name=str(s.get("name", "")),
            action=str(s.get("action", "")),
            parameters=dict(s.get("parameters", {}))
            if isinstance(s.get("parameters"), dict) else {},
        )
        for s in step_list
    ]

    context: dict[str, object] = dict(parameters)
    for step in steps:
        step = await execute_step(step, context)
        if step.status == StepStatus.FAILED:
            break
        if step.result is not None:
            context[step.id] = step.result
