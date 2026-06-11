#!/usr/bin/env python3
import httpx
from datetime import datetime, timezone

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = ("root", "abc_desktop_2026")
COLLECTION = "tools"

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

REPORT_AGENT_TOOL = {
    "_key": "report-agent",
    "code": "report-agent",
    "name": "報表生成器",
    "description": "將 JSON 資料轉換為視覺化 HTML 報表。使用本地 LLM 生成圖表代碼，支援餅圖、柱狀圖、線圖等標準圖表，輸出到 SeaWeedFS。",
    "tool_type": "tool",
    "icon": "BarChartOutlined",
    "status": "online",
    "usage_count": 0,
    "group_key": "utility",
    "intent_tags": ["報表", "report", "圖表", "chart", "視覺化", "dashboard"],
    "nl_examples": [
        "幫我生成銷售報表",
        "製作一個營收趨勢圖",
        "把這份資料做成餅圖",
        "生成一個資料視覺化報告",
        "製作一個月報圖表",
        "把資料轉換成柱狀圖",
        "製作一個 KPI 儀表板",
    ],
    "endpoint_url": "http://localhost:8004/report-agent",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "報告標題"},
            "author": {"type": "string", "description": "作者"},
            "username": {"type": "string", "description": "使用者名稱（用於儲存路徑）"},
            "data": {"type": "object", "description": "JSON 格式的資料"},
            "chart_types": {"type": "array", "items": {"type": "string"}, "description": "希望生成的圖表類型"},
            "params": {"type": "object", "description": "額外參數"},
        },
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "report_url": {"type": "string", "description": "報告 URL"},
            "filename": {"type": "string", "description": "檔案名"},
            "chart_type": {"type": "string", "description": "生成的圖表類型"},
            "analysis": {"type": "string", "description": "資料分析文字"},
        },
    },
    "timeout_ms": 60000,
    "llm_model": "gemma4:31b",
    "temperature": 0.3,
    "max_tokens": 4000,
    "visibility": "public",
    "visibility_roles": [],
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
    print(f"=== Seed Report Agent → ArangoDB ({DB}.{COLLECTION}) ===")
    with httpx.Client(timeout=10.0) as client:
        upsert_tool(client, REPORT_AGENT_TOOL)
    print(f"\n✅ Done — Report Agent seeded.")


if __name__ == "__main__":
    main()
