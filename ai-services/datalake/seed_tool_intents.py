#!/usr/bin/env python3
"""
@file        seed_tool_intents.py
@description 將工具意圖登記進 ArangoDB intent_catalog collection
@lastUpdate  2026-04-08 00:00:00
@author      Daniel Chung
@version     1.0.0
"""

import json
import subprocess
from datetime import datetime, timezone

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = "root:abc_desktop_2026"
COLLECTION = "intent_catalog"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
TOOL_SCOPE = "tool"


def curl_post_doc(docs: list) -> list:
    payload = json.dumps(docs)
    r = subprocess.run(
        [
            "curl",
            "-s",
            "-u",
            AUTH,
            f"{ARANGO_URL}/_db/{DB}/_api/document/{COLLECTION}?overwriteMode=replace",
            "-X",
            "POST",
            "-H",
            "Content-Type: application/json",
            "-d",
            payload,
        ],
        capture_output=True,
        text=True,
    )
    return json.loads(r.stdout)


def insert_batch(docs: list, label: str) -> None:
    result = curl_post_doc(docs)
    errors = 0
    if isinstance(result, list):
        for i, r in enumerate(result):
            if r.get("error"):
                print(f"  ERROR [{docs[i]['_key']}]: {r.get('errorMessage', r)}")
                errors += 1
    elif isinstance(result, dict) and result.get("error"):
        print(f"  Batch error for {label}: {result}")
        errors += 1
    ok = len(docs) - errors
    print(f"  ✓ {label}: {ok}/{len(docs)} inserted/updated")


def make_tool_intent(
    intent_id: str,
    tool_key: str,
    name: str,
    description: str,
    nl_examples: list[str],
    intent_type: str = "query",
) -> dict:
    return {
        "_key": intent_id,
        "intent_id": intent_id,
        "tool_key": tool_key,
        "name": name,
        "description": description,
        "intent_type": intent_type,
        "group": tool_key,
        "nl_examples": nl_examples,
        "status": "enabled",
        "created_at": NOW,
        "updated_at": NOW,
        "updated_by": "system",
    }


TOOL_INTENTS = [
    make_tool_intent(
        intent_id="tool-weather-current",
        tool_key="weather",
        name="即時天氣查詢",
        description="查詢指定城市或座標的即時天氣資訊",
        nl_examples=[
            "現在天氣如何？",
            "台北今天天氣怎樣？",
            "帮我查一下北京的气温",
            "這週會下雨嗎？",
            "明天適合出門嗎？",
        ],
    ),
    make_tool_intent(
        intent_id="tool-weather-temp",
        tool_key="weather",
        name="氣溫查詢",
        description="查詢特定地點的溫度",
        nl_examples=[
            "現在幾度？",
            "今天最高溫是多少？",
            "明天會很冷嗎？",
            "東京的平均氣溫？",
        ],
    ),
    make_tool_intent(
        intent_id="tool-weather-forecast",
        tool_key="forecast",
        name="天氣預報查詢",
        description="查詢未來1-7天的天氣預報",
        nl_examples=[
            "明天天氣怎樣？",
            "這週會下雨嗎？",
            "週末天氣如何？",
            "未來一週的天氣預報",
            "下周去東京，該帶什麼衣服？",
        ],
    ),
    make_tool_intent(
        intent_id="tool-weather-rain",
        tool_key="forecast",
        name="降雨預報查詢",
        description="查詢未來是否有降雨",
        nl_examples=[
            "這幾天會下雨嗎？",
            "明天要不要帶傘？",
            "週末會下雨嗎？",
        ],
    ),
    make_tool_intent(
        intent_id="tool-web-search-general",
        tool_key="web_search",
        name="一般網路搜尋",
        description="執行網路搜尋取得資訊",
        nl_examples=[
            "搜尋一下",
            "幫我查一下",
            "網路上怎麼說",
            "相關資訊",
        ],
    ),
    make_tool_intent(
        intent_id="tool-web-search-news",
        tool_key="web_search",
        name="新聞搜尋",
        description="搜尋最新新聞或時事資訊",
        nl_examples=[
            "最新新聞",
            "今天有什麼大事？",
            "最近的科技新聞",
            "這個月的重要消息",
        ],
    ),
    make_tool_intent(
        intent_id="tool-web-search-product",
        tool_key="web_search",
        name="產品/價格搜尋",
        description="搜尋產品資訊或價格比較",
        nl_examples=[
            "這個產品多少錢？",
            "哪裡可以買到？",
            "推薦什麼品牌？",
            "比較一下規格",
        ],
    ),
    make_tool_intent(
        intent_id="tool-web-search-howto",
        tool_key="web_search",
        name="操作指引搜尋",
        description="搜尋如何操作或解決問題的指引",
        nl_examples=[
            "怎麼做？",
            "如何安裝？",
            "這個錯誤怎麼解決？",
            "步驟是什麼？",
        ],
    ),
]


def ensure_collection(client) -> None:
    r = client.get(f"{ARANGO_URL}/_db/{DB}/_api/collection/{COLLECTION}")
    if r.status_code == 404:
        r2 = client.post(
            f"{ARANGO_URL}/_db/{DB}/_api/collection",
            json={"name": COLLECTION},
        )
        if r2.status_code in (200, 201):
            print(f"  Created collection: {COLLECTION}")
        else:
            print(f"  Failed to create collection: {r2.text}")
    else:
        print(f"  Collection '{COLLECTION}' already exists")


def main() -> None:
    import httpx

    print(f"=== Seed tool intents → ArangoDB ({DB}.{COLLECTION}) ===")
    with httpx.Client(timeout=10.0) as client:
        ensure_collection(client)
        insert_batch(TOOL_INTENTS, f"{len(TOOL_INTENTS)} tool intents")

    print(f"\n✅ Done — {len(TOOL_INTENTS)} tool intents seeded.")


if __name__ == "__main__":
    main()
