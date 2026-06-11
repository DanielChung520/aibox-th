import asyncio
import os
from datetime import datetime
from typing import Any, Optional

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from shared.logging import LoggingMiddleware, setup_logging

setup_logging("mcp_tools", os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="TWHC MCP Tools Service",
    description="MCP tool execution service.",
    version="2.0.0",
)
app.add_middleware(LoggingMiddleware, service_name="mcp_tools")

from tools.process_advisor.router import app as process_advisor_app  # noqa: E402
app.mount("/process-advisor", process_advisor_app)

from mcp_tools.mcp_gateway import router as mcp_gateway_router  # noqa: E402
app.include_router(mcp_gateway_router)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

_TOOL_REGISTRY = {
    "calculator": {
        "name": "Calculator",
        "description": "Perform mathematical calculations",
        "parameters": {"expression": "str"},
    },
    "web_search": {
        "name": "Web Search",
        "description": "Search the web for information",
        "parameters": {"query": "str", "num": "int", "location": "str?"},
    },
    "weather": {
        "name": "Weather",
        "description": "Get current weather for a location",
        "parameters": {"city": "str?", "lat": "float?", "lon": "float?", "units": "str?"},
    },
    "forecast": {
        "name": "Forecast",
        "description": "Get weather forecast for the next few days",
        "parameters": {"city": "str?", "lat": "float?", "lon": "float?", "days": "int?", "units": "str?"},
    },
    "code_executor": {
        "name": "Code Executor",
        "description": "Execute Python code safely",
        "parameters": {"code": "str"},
    },
    "tool_reports": {
        "name": "Report Generator",
        "description": "Generate HTML report from dataset with charts",
        "parameters": {
            "dataset": "dict|list",
            "report_goal": "str",
            "preferred_chart": "str?",
            "knowledge_domain": "str?",
            "hints": "str?",
            "title": "str?",
            "author": "str?",
            "username": "str?",
        },
    },
    "linear_mcp": {
        "name": "Linear MCP",
        "description": "Project management via Linear MCP. Requires LINEAR_API_KEY environment variable.",
        "parameters": {
            "operation": "str",
        },
    },
}

_tool_instances: dict[str, Any] = {}


def _get_tool(name: str) -> Any:
    if name not in _tool_instances:
        if name == "web_search":
            from tools.web_search.web_search_tool import WebSearchTool
            _tool_instances[name] = WebSearchTool()
        elif name == "weather":
            from tools.weather.weather_tool import WeatherTool
            _tool_instances[name] = WeatherTool()
        elif name == "forecast":
            from tools.weather.forecast_tool import ForecastTool
            _tool_instances[name] = ForecastTool()
    return _tool_instances.get(name)


class ToolCall(BaseModel):
    tool: str
    parameters: dict[str, Any]


class ToolResult(BaseModel):
    tool: str
    success: bool
    result: Any
    error: Optional[str] = None


class ServiceInfo(BaseModel):
    service: str
    description: str
    version: str
    port: int
    status: str


class HealthResponse(BaseModel):
    status: str
    service: str


async def execute_calculator(expression: str) -> float | str:
    try:
        allowed_chars = set("0123456789+-*/.() ")
        if not all(c in allowed_chars for c in expression):
            raise ValueError("Invalid characters in expression")
        result = eval(expression)  # noqa: S307
        return result
    except Exception as e:
        return f"Error: {str(e)}"


async def execute_web_search(query: str, num: int = 10, location: Optional[str] = None) -> dict:
    try:
        from tools.web_search.web_search_tool import WebSearchInput
        tool = _get_tool("web_search")
        if tool is None:
            return {"error": "WebSearchTool not available"}
        inp = WebSearchInput(query=query, num=num, location=location)
        result = await tool.execute(inp)
        return result.model_dump()
    except Exception as e:
        return {"error": str(e)}


async def execute_weather(city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None, units: str = "metric") -> dict:
    try:
        from tools.weather.weather_tool import WeatherInput
        tool = _get_tool("weather")
        if tool is None:
            return {"error": "WeatherTool not available"}
        inp = WeatherInput(city=city, lat=lat, lon=lon, units=units)
        result = await tool.execute(inp)
        return result.model_dump()
    except Exception as e:
        return {"error": str(e)}


async def execute_forecast(city: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None, days: int = 3, units: str = "metric") -> dict:
    try:
        from tools.weather.forecast_tool import ForecastInput
        tool = _get_tool("forecast")
        if tool is None:
            return {"error": "ForecastTool not available"}
        inp = ForecastInput(city=city, lat=lat, lon=lon, days=days, units=units)
        result = await tool.execute(inp)
        return result.model_dump()
    except Exception as e:
        return {"error": str(e)}


async def execute_code(code: str) -> dict:
    try:
        local_vars: dict[str, Any] = {}
        exec(code, {"__builtins__": __builtins__}, local_vars)  # noqa: S102
        return {"success": True, "output": local_vars.get("result", "Code executed")}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def execute_tool(tool_name: str, parameters: dict[str, Any]) -> ToolResult:
    try:
        match tool_name:
            case "calculator":
                result = await execute_calculator(parameters.get("expression", ""))
            case "web_search":
                result = await execute_web_search(
                    parameters.get("query", ""),
                    parameters.get("num", 10),
                    parameters.get("location"),
                )
            case "weather":
                result = await execute_weather(
                    city=parameters.get("city"),
                    lat=parameters.get("lat"),
                    lon=parameters.get("lon"),
                    units=parameters.get("units", "metric"),
                )
            case "forecast":
                result = await execute_forecast(
                    city=parameters.get("city"),
                    lat=parameters.get("lat"),
                    lon=parameters.get("lon"),
                    days=parameters.get("days", 3),
                    units=parameters.get("units", "metric"),
                )
            case "code_executor":
                result = await execute_code(parameters.get("code", ""))
            case "tool_reports":
                from tools.report_generator.tool_reports import tool_reports_execute
                output = await tool_reports_execute(parameters)
                result = output.to_dict()
            case "linear_mcp":
                from tools.linear.linear_mcp import execute_linear_mcp
                operation = parameters.get("operation", "linear_search_issues")
                kwargs = {k: v for k, v in parameters.items() if k != "operation" and v is not None}
                result = await execute_linear_mcp(operation, **kwargs)
            case _:
                return ToolResult(tool=tool_name, success=False, result=None, error=f"Unknown tool: {tool_name}")

        if isinstance(result, dict) and result.get("error"):
            return ToolResult(tool=tool_name, success=False, result=result, error=result.get("error"))

        return ToolResult(tool=tool_name, success=True, result=result)
    except Exception as e:
        return ToolResult(tool=tool_name, success=False, result=None, error=str(e))


@app.get("/", response_model=ServiceInfo)
def root() -> ServiceInfo:
    return ServiceInfo(service="mcp_tools", description="MCP tool execution", version="2.0.0", port=8004, status="running")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="mcp_tools")


@app.get("/tools")
async def list_tools() -> dict:
    return {"tools": _TOOL_REGISTRY}


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall) -> ToolResult:
    return await execute_tool(call.tool, call.parameters)


@app.post("/execute-batch")
async def execute_batch(calls: list[ToolCall]) -> list[ToolResult]:
    tasks = [execute_tool(call.tool, call.parameters) for call in calls]
    results = await asyncio.gather(*tasks)
    return results


@app.post("/tools/{tool_key}/sync")
async def sync_tool_intents(tool_key: str, payload: dict) -> dict:
    """Sync tool intents to Qdrant for semantic matching."""
    try:
        intent_tags = payload.get("intent_tags", [])
        nl_examples = payload.get("nl_examples", [])
        
        # TODO: Implement Qdrant sync logic
        # For now, just log the payload
        print(f"[sync_tool_intents] tool_key={tool_key}, intent_tags={intent_tags}, nl_examples={nl_examples}")
        
        return {"code": 0, "message": "已同步到 Qdrant", "synced_at": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"code": 1, "message": f"同步失敗: {str(e)}"}


@app.post("/chat-with-tools")
async def chat_with_tools(messages: list[dict], tools: list[str]) -> dict:
    tool_schemas = [_TOOL_REGISTRY[t] for t in tools if t in _TOOL_REGISTRY]
    system_prompt = f"""You have access to the following tools:
{', '.join([f"{t['name']}: {t['description']}" for t in tool_schemas])}

When asked to perform tasks, use these tools."""

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": DEFAULT_MODEL,
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "stream": False,
                "temperature": 0.5,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data
