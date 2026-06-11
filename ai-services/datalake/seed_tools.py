"""
@file        seed_tools.py
@description 將 ai-services/tools/ 下的工具登記進 ArangoDB tools collection
@lastUpdate  2026-04-08 00:00:00
@author      Daniel Chung
@version     1.2.0
@changelog
- 2026-04-08 | 1.2.0 | 新增 nl_examples 自然語言範例
- 2026-04-08 | 1.1.0 | tool_type 從 "api" 改為 "tool"，符合統一框架
"""

import httpx
from datetime import datetime, timezone

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = ("root", "abc_desktop_2026")
COLLECTION = "tools"

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

TOOLS: list[dict] = [
    # ── Linear MCP ─────────────────────────────────────────────────────────────
    {
        "_key": "linear_mcp",
        "code": "linear_mcp",
        "name": "Linear 專案管理",
        "description": "透過 Linear MCP 協定連接 Linear 專案管理工具。支援搜尋、建立、更新 Issue，查詢團隊、里程碑等操作。需要設定 LINEAR_API_KEY 環境變數。",
        "tool_type": "tool",
        "icon": "ProjectOutlined",
        "status": "online",
        "usage_count": 0,
        "group_key": "utility",
        "intent_tags": ["專案管理", "issue", "task", "Linear", "專案", "任務", "bug追蹤"],
        "nl_examples": [
            "搜尋 Linear 上的 authentication bug issue",
            "幫我在 Linear 建立一個新 task",
            "查詢我的團隊有哪些成員",
            "列出所有 in progress 的 issue",
            "幫我更新這個 issue 的狀態",
            "查詢某個 milestone 的進度",
            "幫我指派 issue 給某個人",
            "在 Linear 上建立一個 bug report",
        ],
        "endpoint_url": None,
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "Linear MCP 操作：linear_search_issues, linear_create_issue, linear_get_teams, linear_create_project_milestone, 等",
                },
                "team_id": {"type": "string", "description": "團隊 ID"},
                "title": {"type": "string", "description": "Issue 標題"},
                "description": {"type": "string", "description": "Issue 描述"},
                "query": {"type": "string", "description": "搜尋關鍵字"},
                "limit": {"type": "integer", "description": "回傳數量上限"},
                "priority": {"type": "integer", "description": "優先級：0=無, 1=緊急, 2=高, 3=中, 4=低"},
                "status": {"type": "string", "description": "Issue 狀態"},
                "assignee_id": {"type": "string", "description": "指派對象 ID"},
                "issue_id": {"type": "string", "description": "Issue ID"},
                "milestone_id": {"type": "string", "description": "里程碑 ID"},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "result": {"type": "object", "description": "Linear MCP 執行結果"},
                "duration_ms": {"type": "integer", "description": "執行耗時（毫秒）"},
            },
        },
        "timeout_ms": 30000,
        "llm_model": None,
        "temperature": None,
        "max_tokens": None,
        "auth_config": {
            "provider": "linear",
            "api_key_env": "LINEAR_API_KEY",
            "mcp_endpoint": "https://mcp.linear.app/mcp",
        },
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },

    # ── Weather ────────────────────────────────────────────────────────────────
    {
        "_key": "weather",
        "code": "weather",
        "name": "即時天氣查詢",
        "description": "依城市名稱或經緯度取得即時天氣（溫度、濕度、風速、天氣描述等）。使用 OpenWeatherMap API，支援 metric/imperial 單位，結果快取 10 分鐘。",
        "tool_type": "tool",
        "icon": "CloudOutlined",
        "status": "online",
        "usage_count": 0,
        "group_key": "weather",
        "intent_tags": ["天氣", "weather", "氣象", "溫度", "humidity"],
        "nl_examples": [
            "台北現在天氣怎樣？",
            "今天氣溫多少度？",
            "幫我查一下北京的天氣",
            "現在外面冷嗎？",
            "今天會下雨嗎？",
            "今天適合出門嗎？",
            "外面風大嗎？",
            "今天濕度高嗎？",
            "幫我看看東京現在的天氣",
            "今天天氣好不好？",
        ],
        "endpoint_url": None,
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名稱（city 與 lat/lon 二選一）"
                },
                "lat": {
                    "type": "number",
                    "description": "緯度（需搭配 lon）"
                },
                "lon": {
                    "type": "number",
                    "description": "經度（需搭配 lat）"
                },
                "units": {
                    "type": "string",
                    "enum": ["metric", "imperial"],
                    "default": "metric",
                    "description": "溫度單位：metric(°C) / imperial(°F)"
                }
            }
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "country": {"type": "string"},
                "temperature": {"type": "number", "description": "氣溫"},
                "feels_like": {"type": "number", "description": "體感溫度"},
                "humidity": {"type": "integer", "description": "濕度 (%)"},
                "pressure": {"type": "integer", "description": "氣壓 (hPa)"},
                "description": {"type": "string", "description": "天氣描述"},
                "icon": {"type": "string"},
                "wind_speed": {"type": "number", "description": "風速 (m/s)"},
                "wind_direction": {"type": "integer", "description": "風向 (°)"},
                "visibility": {"type": "integer", "description": "能見度 (m)"},
                "uv_index": {"type": "number", "description": "紫外線指數"},
                "timestamp": {"type": "number"}
            }
        },
        "timeout_ms": 10000,
        "llm_model": None,
        "temperature": None,
        "max_tokens": None,
        "auth_config": {
            "provider": "openweathermap",
            "api_key_env": "OPENWEATHERMAP_API_KEY"
        },
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },

    # ── Forecast ───────────────────────────────────────────────────────────────
    {
        "_key": "forecast",
        "code": "forecast",
        "name": "天氣預報查詢",
        "description": "依城市名稱或經緯度取得未來 1–7 天天氣預報，支援每日摘要與逐小時預報。使用 OpenWeatherMap API，結果快取 1 小時。",
        "tool_type": "tool",
        "icon": "CloudSyncOutlined",
        "status": "online",
        "usage_count": 0,
        "group_key": "weather",
        "intent_tags": ["天氣預報", "forecast", "明天天氣", "未來天氣", "一週天氣"],
        "nl_examples": [
            "明天天氣怎樣？",
            "這週會下雨嗎？",
            "週末天氣如何？",
            "未來一週的天氣預報",
            "下週去東京該帶什麼衣服？",
            "這幾天會變冷嗎？",
            "禮拜五天氣好嗎？",
            "明天適合去郊外踏青嗎？",
            "這幾天氣溫變化大嗎？",
            "未來三天會下雪嗎？",
            "下禮拜二是晴天嗎？",
            "這週末要去墾丁，天氣怎樣？",
        ],
        "endpoint_url": None,
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名稱（city 與 lat/lon 二選一）"
                },
                "lat": {
                    "type": "number",
                    "description": "緯度"
                },
                "lon": {
                    "type": "number",
                    "description": "經度"
                },
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 7,
                    "default": 3,
                    "description": "預報天數（1–7）"
                },
                "hourly": {
                    "type": "boolean",
                    "default": False,
                    "description": "是否包含逐小時預報"
                },
                "units": {
                    "type": "string",
                    "enum": ["metric", "imperial"],
                    "default": "metric"
                }
            }
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "country": {"type": "string"},
                "forecasts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string"},
                            "temperature": {"type": "number"},
                            "min_temp": {"type": "number"},
                            "max_temp": {"type": "number"},
                            "description": {"type": "string"},
                            "icon": {"type": "string"},
                            "humidity": {"type": "integer"},
                            "wind_speed": {"type": "number"},
                            "precipitation": {"type": "number"},
                            "hourly": {"type": "array"},
                            "timestamp": {"type": "number"}
                        }
                    }
                }
            }
        },
        "timeout_ms": 10000,
        "llm_model": None,
        "temperature": None,
        "max_tokens": None,
        "auth_config": {
            "provider": "openweathermap",
            "api_key_env": "OPENWEATHERMAP_API_KEY"
        },
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },

    # ── Web Search ─────────────────────────────────────────────────────────────
    {
        "_key": "web_search",
        "code": "web_search",
        "name": "網路搜尋",
        "description": "執行網路搜尋，支援多 Provider 自動切換（Serper → SerpAPI → ScraperAPI → Google CSE）。回傳標題、連結、摘要等搜尋結果，結果快取 30 分鐘。",
        "tool_type": "tool",
        "icon": "SearchOutlined",
        "status": "online",
        "usage_count": 0,
        "group_key": "search",
        "intent_tags": ["搜尋", "search", "網路", "web", "查詢", "資訊"],
        "nl_examples": [
            "搜尋一下最近的科技新聞",
            "幫我查一下這個公司的資料",
            "網路上怎麼說",
            "幫我找一下這個問題的解答",
            "這個術語是什麼意思？",
            "搜尋相關資訊",
            "幫我查一下這個產品的使用評價",
            "最新的人工智慧發展動態",
            "搜尋一下這個錯誤的解決方法",
            "這個東西哪裡可以買到？",
            "搜尋一下旅遊景點推薦",
            "幫我查一下食譜做法",
        ],
        "endpoint_url": None,
        "input_schema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜尋關鍵字或自然語言查詢句"
                },
                "num": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                    "description": "回傳結果筆數"
                },
                "location": {
                    "type": "string",
                    "description": "地區語言限制（選填，如 'tw', 'us'）"
                }
            }
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "provider": {"type": "string", "description": "實際使用的 Provider"},
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "link": {"type": "string"},
                            "snippet": {"type": "string"},
                            "result_type": {
                                "type": "string",
                                "enum": ["organic", "featured", "news"],
                                "default": "organic"
                            },
                            "position": {"type": "integer"}
                        }
                    }
                },
                "total": {"type": "integer"},
                "status": {
                    "type": "string",
                    "description": "success / failed"
                }
            }
        },
        "timeout_ms": 15000,
        "llm_model": None,
        "temperature": None,
        "max_tokens": None,
        "auth_config": {
            "providers": ["serper", "serpapi", "scraper", "google_cse"],
            "config_endpoint": "/api/v1/web-search/config",
            "note": "API keys managed via system_params in ArangoDB"
        },
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },
]


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
    print(f"=== Seed tools → ArangoDB ({DB}.{COLLECTION}) ===")
    with httpx.Client(timeout=10.0) as client:
        # 確認 collection 存在
        r = client.get(
            f"{ARANGO_URL}/_db/{DB}/_api/collection/{COLLECTION}",
            auth=AUTH,
        )
        if r.status_code == 404:
            client.post(
                f"{ARANGO_URL}/_db/{DB}/_api/collection",
                json={"name": COLLECTION},
                auth=AUTH,
            )
            print(f"  Created collection: {COLLECTION}")

        for doc in TOOLS:
            upsert_tool(client, doc)

    print(f"\n✅ Done — {len(TOOLS)} tools seeded.")


if __name__ == "__main__":
    main()
