import os
import httpx
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .prompts import ORACLE_SYSTEM_PROMPT, PROCESS_ADVISOR_PROMPT
from .config import ProcessAdvisorConfig

app = FastAPI(title="Process Advisor", description="Oracle Agent - Process Advisor")
config = ProcessAdvisorConfig()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")


class QueryRequest(BaseModel):
    query: str
    context: Optional[dict] = None
    mode: str = "advisory"
    params: Optional[dict] = None


class AuditRequest(BaseModel):
    plan_content: str
    plan_type: str = "general"
    params: Optional[dict] = None


class DebugRequest(BaseModel):
    error_log: str
    context: Optional[dict] = None
    params: Optional[dict] = None


def build_system_prompt(mode: str) -> str:
    if mode == "audit":
        return ORACLE_SYSTEM_PROMPT + "\n\n[模式切換：計劃審計模式]\n請專注於審計計劃的可行性、風險與合規性。"
    elif mode == "debug":
        return ORACLE_SYSTEM_PROMPT + "\n\n[模式切換：Bug 分析模式]\n請專注於分析錯誤的根本原因並提供修復建議。"
    return ORACLE_SYSTEM_PROMPT + "\n\n" + PROCESS_ADVISOR_PROMPT


async def call_llm(
    prompt: str,
    user_message: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 32000,
) -> str:
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=f"LLM call failed: {str(e)}")


@app.post("/query")
async def query(request: QueryRequest) -> dict:
    system_prompt = build_system_prompt(request.mode)

    user_message = request.query
    if request.context:
        user_message += f"\n\n## 上下文\n```json\n{request.context}\n```"

    answer = await call_llm(
        prompt=system_prompt,
        user_message=user_message,
        model=request.params.get("llm_model") if request.params else None,
        temperature=request.params.get("temperature", 0.7) if request.params else 0.7,
        max_tokens=request.params.get("max_tokens", 32000) if request.params else 32000,
    )

    return {
        "code": 0,
        "data": {
            "answer": answer,
            "mode": request.mode,
            "model_used": request.params.get("llm_model", DEFAULT_MODEL) if request.params else DEFAULT_MODEL,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


@app.post("/audit")
async def audit(request: AuditRequest) -> dict:
    system_prompt = build_system_prompt("audit")

    user_message = f"""請審計以下計劃：

## 計劃內容
{request.plan_content}

## 計劃類型
{request.plan_type}

請根據回覆格式，提供完整的審計報告。"""

    answer = await call_llm(
        prompt=system_prompt,
        user_message=user_message,
        model=request.params.get("llm_model") if request.params else None,
        temperature=request.params.get("temperature", 0.7) if request.params else 0.7,
        max_tokens=request.params.get("max_tokens", 4000) if request.params else 4000,
    )

    return {
        "code": 0,
        "data": {
            "answer": answer,
            "mode": "audit",
            "plan_type": request.plan_type,
            "model_used": request.params.get("llm_model", DEFAULT_MODEL) if request.params else DEFAULT_MODEL,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


@app.post("/debug")
async def debug(request: DebugRequest) -> dict:
    system_prompt = build_system_prompt("debug")

    user_message = f"""請分析以下錯誤：

## 錯誤日誌
```
{request.error_log}
```

## 上下文
```json
{request.context or {}}
```

請根據回覆格式，提供根因分析與修復建議。"""

    answer = await call_llm(
        prompt=system_prompt,
        user_message=user_message,
        model=request.params.get("llm_model") if request.params else None,
        temperature=request.params.get("temperature", 0.5) if request.params else 0.5,
        max_tokens=request.params.get("max_tokens", 4000) if request.params else 4000,
    )

    return {
        "code": 0,
        "data": {
            "answer": answer,
            "mode": "debug",
            "model_used": request.params.get("llm_model", DEFAULT_MODEL) if request.params else DEFAULT_MODEL,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


@app.get("/config")
async def get_config() -> dict:
    return {
        "code": 0,
        "data": {
            "name": config.name,
            "display_name": config.display_name,
            "description": config.description,
            "llm_model": config.llm_model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "timeout_ms": config.timeout_ms,
            "visibility": config.visibility,
            "visibility_roles": config.visibility_roles,
        },
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "process-advisor"}


@app.get("/")
async def root() -> dict:
    return {
        "service": "process-advisor",
        "version": "1.0.0",
        "description": "Oracle Agent - Process Advisor",
    }
