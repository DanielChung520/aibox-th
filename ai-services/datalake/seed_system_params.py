"""
@file        seed_system_params.py
@description 將系統預設參數寫入 ArangoDB system_params collection
             確保新環境首次啟動就有合理的預設值，避免前端 404
@lastUpdate  2026-05-30 14:00:00
@author      Sisyphus
@version     1.0.0
"""

import json
import httpx
from datetime import datetime, timezone

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = ("root", "abc_desktop_2026")
COLLECTION = "system_params"

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

PARAMS: list[dict] = [
    {
        "_key": "basic.avatar",
        "param_key": "basic.avatar",
        "param_value": "曉晴",
        "param_type": "string",
        "category": "basic",
        "require_restart": False,
        "description": "系統預設頭像名稱（對應 src/assets/avatar/ 下的 PNG 檔名）",
        "updated_at": NOW,
    },
    {
        "_key": "basic.system_type",
        "param_key": "basic.system_type",
        "param_value": "ragic",
        "param_type": "string",
        "category": "basic",
        "require_restart": False,
        "description": "系統類型（sap / ragic），影響資料源行為",
        "updated_at": NOW,
    },
    {
        "_key": "app.logo",
        "param_key": "app.logo",
        "param_value": "",
        "param_type": "string",
        "category": "basic",
        "require_restart": True,
        "description": "應用程式 Logo（Base64 data URL，留空使用預設）",
        "updated_at": NOW,
    },
    {
        "_key": "app.version",
        "param_key": "app.version",
        "param_value": "1.0.0",
        "param_type": "string",
        "category": "basic",
        "require_restart": False,
        "description": "系統版本號（唯讀，由後端維護）",
        "updated_at": NOW,
    },
]


def upsert_param(client: httpx.Client, doc: dict) -> None:
    key = doc["_key"]
    aql = """
    UPSERT { _key: @key }
    INSERT @doc
    UPDATE @doc
    IN system_params
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
    print(f"=== Seed System Params → ArangoDB ({DB}.{COLLECTION}) ===")
    with httpx.Client(timeout=15.0) as client:
        for doc in PARAMS:
            upsert_param(client, doc)
    print("✅ Done — System params seeded.")


if __name__ == "__main__":
    main()
