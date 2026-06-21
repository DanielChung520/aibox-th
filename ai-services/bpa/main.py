"""
BPA Service - Business Process Automation

Provides workflow automation and orchestration.

# Last Update: 2026-03-18 03:50:00
# Author: Daniel Chung
# Version: 1.0.0
"""

import asyncio
import os
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="TWHC BPA Service",
    description="Business process automation service.",
    version="1.0.0",
)

OLLAMA_BASE_URL = os.getenv("MLX_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11400"))
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStep(BaseModel):
    id: str
    name: str
    action: str
    parameters: dict[str, Any]
    status: StepStatus = StepStatus.PENDING
    result: Optional[dict] = None
    error: Optional[str] = None


class Workflow(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    steps: list[WorkflowStep]
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[dict] = None


class WorkflowExecution(BaseModel):
    workflow_id: str
    parameters: dict[str, Any]


class ServiceInfo(BaseModel):
    service: str
    description: str
    version: str
    port: int
    status: str


class HealthResponse(BaseModel):
    status: str
    service: str


WORKFLOWS: dict[str, dict] = {
    "user_onboarding": {
        "name": "User Onboarding",
        "description": "Onboard new user with default settings",
        "steps": [
            {"id": "1", "name": "Create User", "action": "create_user", "parameters": {}},
            {"id": "2", "name": "Send Welcome Email", "action": "send_email", "parameters": {}},
            {"id": "3", "name": "Assign Default Role", "action": "assign_role", "parameters": {}},
        ],
    },
    "data_backup": {
        "name": "Data Backup",
        "description": "Backup database collections",
        "steps": [
            {"id": "1", "name": "Export Users", "action": "export_collection", "parameters": {"collection": "users"}},
            {"id": "2", "name": "Export Roles", "action": "export_collection", "parameters": {"collection": "roles"}},
            {"id": "3", "name": "Export Functions", "action": "export_collection", "parameters": {"collection": "functions"}},
        ],
    },
}


async def execute_step(step: WorkflowStep, context: dict[str, Any]) -> WorkflowStep:
    step.status = StepStatus.RUNNING

    try:
        match step.action:
            case "create_user":
                step.result = {"user_key": f"user_{uuid.uuid4().hex[:8]}", "status": "created"}

            case "send_email":
                step.result = {"email_sent": True, "recipient": context.get("email", "user@example.com")}

            case "assign_role":
                step.result = {"role_assigned": context.get("role", "user"), "status": "ok"}

            case "export_collection":
                collection = step.parameters.get("collection", "")
                step.result = {"collection": collection, "records": 0, "status": "exported"}

            case "http_request":
                url = step.parameters.get("url", "")
                method = step.parameters.get("method", "GET")
                async with httpx.AsyncClient() as client:
                    response = await client.request(method, url)
                    step.result = {"status_code": response.status_code}

            case _:
                step.error = f"Unknown action: {step.action}"
                step.status = StepStatus.FAILED
                return step

        step.status = StepStatus.COMPLETED

    except Exception as e:
        step.status = StepStatus.FAILED
        step.error = str(e)

    return step


@app.get("/", response_model=ServiceInfo)
def root() -> ServiceInfo:
    return ServiceInfo(
        service="bpa",
        description="Business process automation",
        version="1.0.0",
        port=8005,
        status="running",
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="bpa")


@app.get("/workflows")
async def list_workflows() -> dict:
    return {"workflows": WORKFLOWS}


@app.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str) -> dict:
    if workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return WORKFLOWS[workflow_id]


@app.post("/execute")
async def execute_workflow(execution: WorkflowExecution) -> dict:
    if execution.workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow_def = WORKFLOWS[execution.workflow_id]
    workflow_id = str(uuid.uuid4())

    steps = [
        WorkflowStep(
            id=step["id"],
            name=step["name"],
            action=step["action"],
            parameters=step["parameters"],
        )
        for step in workflow_def["steps"]
    ]

    workflow = Workflow(
        id=workflow_id,
        name=workflow_def["name"],
        description=workflow_def.get("description"),
        steps=steps,
        created_at=datetime.utcnow().isoformat(),
    )

    context = {**execution.parameters}

    for step in workflow.steps:
        step = await execute_step(step, context)
        if step.status == StepStatus.FAILED:
            workflow.status = WorkflowStatus.FAILED
            workflow.completed_at = datetime.utcnow().isoformat()
            return {"workflow": workflow.model_dump(), "success": False}

        context[step.id] = step.result

    workflow.status = WorkflowStatus.COMPLETED
    workflow.completed_at = datetime.utcnow().isoformat()
    workflow.result = context

    return {"workflow": workflow.model_dump(), "success": True}


@app.post("/execute-async")
async def execute_workflow_async(execution: WorkflowExecution) -> dict:
    if execution.workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")

    execution_id = str(uuid.uuid4())

    asyncio.create_task(run_workflow(execution.workflow_id, execution.parameters, execution_id))

    return {"execution_id": execution_id, "status": "started"}


async def run_workflow(workflow_id: str, parameters: dict[str, Any], execution_id: str) -> None:
    workflow_def = WORKFLOWS[workflow_id]
    steps = [
        WorkflowStep(
            id=step["id"],
            name=step["name"],
            action=step["action"],
            parameters=step["parameters"],
        )
        for step in workflow_def["steps"]
    ]

    context = {**parameters}

    for step in steps:
        step = await execute_step(step, context)
        if step.status == StepStatus.FAILED:
            break
        context[step.id] = step.result


@app.get("/executions")
async def list_executions() -> dict:
    return {"executions": []}
