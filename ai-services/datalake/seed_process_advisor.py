#!/usr/bin/env python3
"""
Seed script for Process Advisor (Oracle Agent) in ArangoDB tools collection.
"""

import httpx
from datetime import datetime, timezone

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = ("root", "abc_desktop_2026")
COLLECTION = "tools"

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

PROCESS_ADVISOR_TOOL = {
    "_key": "process-advisor",
    "code": "process-advisor",
    "name": "流程顧問",
    "description": "Oracle Agent - 深度流程顧問，專精於複雜系統架構決策與流程優化。支援三種模式：一般諮詢(advisory)、計劃審計(audit)、Bug 分析(debug)。",
    "tool_type": "oracle",
    "icon": "RobotOutlined",
    "status": "online",
    "usage_count": 0,
    "group_key": "advisor",
    "intent_tags": ["架構", "決策", "審計", "分析", "顧問", "bug", "優化", "流程", "process", "oracle"],
    "nl_examples": [
        "幫我看看這個微服務架構設計是否有問題",
        "審計這個系統遷移計劃",
        "這個流程有什麼可以優化的地方",
        "為什麼系統會一直超時",
        "這個架構決定合理嗎",
        "檢查一下我們的部署流程",
        "幫我分析這個錯誤的根本原因",
        "這兩個系統的整合方案哪個更好",
        "評估一下這個技術選型的風險",
        "我們的 CI/CD 流程可以怎麼改進",
    ],
    "endpoint_url": "http://localhost:8004/process-advisor",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "使用者的查詢"},
            "context": {"type": "object", "description": "上下文（計劃內容、錯誤日誌、系統狀態）"},
            "mode": {"type": "string", "enum": ["advisory", "audit", "debug"], "default": "advisory"},
            "params": {"type": "object", "description": "額外參數（llm_model, temperature, max_tokens）"},
        },
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "mode": {"type": "string"},
            "model_used": {"type": "string"},
            "timestamp": {"type": "string"},
        },
    },
    "timeout_ms": 60000,
    "llm_model": "gemma4:31b",
    "temperature": 0.7,
    "max_tokens": 32000,
    "extra_params": {
        "allowed_context_types": ["plan", "error_log", "system_state", "code"],
        "max_context_length": 10000,
    },
    "visibility": "role",
    "visibility_roles": ["admin", "architect"],
    "visibility_accounts": [],
    "created_by": "system",
    "updated_by": "system",
    "created_at": NOW,
    "updated_at": NOW,
}


def upsert_tool(client: httpx.Client, doc: dict) -> None:
    key = doc["_key"]
    aql = """
    UPSERT { _key: @key }
    INSERT @doc
    UPDATE @doc
    IN tools
    RETURN { action: OLD ? 'updated' : 'inserted', _key: NEW._key }
    """
    resp = client.post(
        f"{ARANGO_URL}/_db/{DB}/_api/cursor",
        json={"query": aql, "bindVars": {"key": key, "doc": doc}},
        auth=AUTH,
    )
    result = resp.json()
    if resp.status_code not in (200, 201) or result.get("error"):
        print(f"  ✗ {key}: {result}")
    else:
        action = result["result"][0]["action"] if result.get("result") else "?"
        print(f"  ✓ {key} [{action}]")


def main() -> None:
    print(f"=== Seed Process Advisor → ArangoDB ({DB}.{COLLECTION}) ===")
    with httpx.Client(timeout=10.0) as client:
        upsert_tool(client, PROCESS_ADVISOR_TOOL)
    print(f"\n✅ Done — Process Advisor seeded.")


if __name__ == "__main__":
    main()
