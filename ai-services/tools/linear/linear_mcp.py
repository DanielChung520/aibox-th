from __future__ import annotations

import os
import time
from typing import Any

import httpx


class LinearMCPClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("LINEAR_API_KEY", "")
        self.base_url = "https://mcp.linear.app/mcp"
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def list_tools(self) -> list[dict[str, Any]]:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self.base_url,
                json=payload,
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", {}).get("tools", [])

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
            "id": 2,
        }
        start = time.time()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self.base_url,
                json=payload,
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            duration_ms = int((time.time() - start) * 1000)
            result = data.get("result", {})
            return {
                "success": True,
                "result": result,
                "duration_ms": duration_ms,
            }


async def execute_linear_mcp(
    operation: str, **kwargs: Any
) -> dict[str, Any]:
    api_key = os.getenv("LINEAR_API_KEY", "")
    if not api_key:
        return {"error": "LINEAR_API_KEY not set. Please configure your Linear API key."}
    client = LinearMCPClient(api_key=api_key)
    try:
        result = await client.call_tool(operation, kwargs)
        return result
    except Exception as e:
        return {"error": str(e)}