#!/usr/bin/env python3
"""
@file        seed_ragic_intents_from_qdrant.py
@description 從 Qdrant ragic_intents 同步到 ArangoDB ragic_intents collection，
              將 table_key、action、nl_patterns 等欄位同步到 ArangoDB，
              讓子頁面 SchemaIntentModal 能看到 Qdrant 的完整意圖資料。
@lastUpdate  2026-04-12 02:00:00
@author      Daniel Chung
@version     1.0.0
"""

import json
import os
import subprocess
import sys
from typing import Any

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "ragic_intents"

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")
ARANGO_AUTH = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
ARANGO_COLLECTION = "da_ragic_intents"


def curl_get(url: str) -> dict[str, Any]:
    r = subprocess.run(
        ["curl", "-s", "-u", ARANGO_AUTH, url],
        capture_output=True, text=True,
    )
    return json.loads(r.stdout)


def curl_post(url: str, payload: dict) -> dict[str, Any]:
    r = subprocess.run(
        ["curl", "-s", "-u", ARANGO_AUTH, url, "-X", "POST",
         "-H", "Content-Type: application/json", "-d", json.dumps(payload)],
        capture_output=True, text=True,
    )
    return json.loads(r.stdout)


def curl_put(url: str, payload: dict) -> dict[str, Any]:
    r = subprocess.run(
        ["curl", "-s", "-u", ARANGO_AUTH, url, "-X", "PUT",
         "-H", "Content-Type: application/json", "-d", json.dumps(payload)],
        capture_output=True, text=True,
    )
    return json.loads(r.stdout)


def arango_upsert_batch(docs: list[dict]) -> tuple[int, int]:
    if not docs:
        return 0, 0
    url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/{ARANGO_COLLECTION}?overwriteMode=replace"
    payload = json.dumps(docs)
    r = subprocess.run(
        ["curl", "-s", "-u", ARANGO_AUTH, url, "-X", "POST",
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True,
    )
    try:
        result = json.loads(r.stdout)
    except json.JSONDecodeError:
        print(f"    JSON parse error: {r.stdout[:100]}")
        return 0, len(docs)
    errors = 0
    if isinstance(result, dict) and result.get("error"):
        errors = len(docs)
    elif isinstance(result, list):
        errors = sum(1 for r in result if r.get("error"))
    return len(docs) - errors, errors


def ensure_arango_collection() -> bool:
    url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/collection/{ARANGO_COLLECTION}"
    existing = curl_get(url)
    if existing.get("name") == ARANGO_COLLECTION:
        print(f"  Collection '{ARANGO_COLLECTION}' already exists.")
        return True
    result = curl_post(
        f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/collection",
        {"name": ARANGO_COLLECTION, "type": 2},
    )
    if result.get("name") == ARANGO_COLLECTION or result.get("id"):
        print(f"  Created collection '{ARANGO_COLLECTION}'.")
        return True
    print(f"  Failed to create collection: {result}")
    return False


def fetch_all_qdrant_intents() -> list[dict[str, Any]]:
    all_points: list[dict[str, Any]] = []
    offset = None
    limit = 200
    while True:
        body: dict[str, Any] = {"limit": limit, "with_payload": True, "with_vector": False}
        if offset:
            body["offset"] = offset
        r = subprocess.run(
            ["curl", "-s", "-X", "POST",
             f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/scroll",
             "-H", "Content-Type: application/json", "-d", json.dumps(body)],
            capture_output=True, text=True, timeout=60,
        )
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            print(f"  Qdrant scroll error: {r.stdout[:200]}")
            break
        result = data.get("result", {})
        points = result.get("points", [])
        if not points:
            break
        all_points.extend(points)
        next_offset = result.get("next_page_offset")
        if not next_offset:
            break
        offset = next_offset
    return all_points


def qdrant_to_arangodb_doc(point: dict[str, Any]) -> dict[str, Any]:
    payload = point.get("payload", {})
    intent_id = str(payload.get("intent_id", ""))
    key = intent_id.replace(".", "_").replace("-", "_")

    raw_patterns = payload.get("nl_patterns", [])
    nl_patterns = [str(p) for p in raw_patterns] if isinstance(raw_patterns, list) else []
    description = str(payload.get("description", ""))
    name = nl_patterns[0] if nl_patterns else description[:40]
    action = str(payload.get("action", "list"))
    table_key = str(payload.get("table_key", ""))

    intent_type_map = {"list": "filter", "get": "filter", "count": "aggregate", "search": "filter"}
    intent_type = intent_type_map.get(action, "filter")

    group = table_key.split("/")[0].upper() if table_key else ""

    filter_tpl = payload.get("filter_template")
    core_fields = []
    if isinstance(filter_tpl, dict) and filter_tpl.get("field_id"):
        core_fields = [str(filter_tpl["field_id"])]

    return {
        "_key": key,
        "intent_id": intent_id,
        "agent_scope": "data_agent",
        "name": name,
        "description": description,
        "intent_type": intent_type,
        "group": group,
        "tables": [table_key] if table_key else [],
        "generation_strategy": "template",
        "sql_template": payload.get("api_template", ""),
        "core_fields": core_fields,
        "nl_examples": nl_patterns,
        "nl_patterns": nl_patterns,
        "example_sqls": [],
        "tool_name": "",
        "status": "enabled",
        "account": str(payload.get("account", "")),
        "action": action,
        "table_key": table_key,
        "api_template": str(payload.get("api_template", "")),
        "filter_template": filter_tpl if isinstance(filter_tpl, dict) else None,
        "created_at": "2026-04-12T00:00:00Z",
        "updated_at": "2026-04-12T00:00:00Z",
        "updated_by": "system",
        "synced_from": "qdrant",
    }


def main() -> None:
    print("=" * 60)
    print("Sync Qdrant ragic_intents → ArangoDB ragic_intents")
    print("=" * 60)

    if not ensure_arango_collection():
        sys.exit(1)

    points = fetch_all_qdrant_intents()
    print(f"\nTotal Qdrant intents: {len(points)}")
    if not points:
        sys.exit(1)

    docs = []
    for point in points:
        try:
            docs.append(qdrant_to_arangodb_doc(point))
        except Exception as e:
            print(f"  Skip {point.get('id')}: {e}")

    batch_size = 50
    total_ok = 0
    total_errors = 0
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i + batch_size]
        ok, errors = arango_upsert_batch(batch)
        total_ok += ok
        total_errors += errors
        print(f"  Batch {i // batch_size + 1}: {ok}/{len(batch)} OK, {errors} errors")

    print(f"\nSYNC COMPLETE: {total_ok}/{len(docs)} synced, {total_errors} errors")
    print("=" * 60)
    print("\nSample synced intents (first 5):")
    for doc in docs[:5]:
        print(f"  {doc['intent_id']} → table_key={doc.get('table_key')}, action={doc.get('action')}")


if __name__ == "__main__":
    main()
