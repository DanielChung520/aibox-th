#!/usr/bin/env python3
"""
@file        seed_intent_logs_collection.py
@description 建立 intent_logs 集合及索引
@lastUpdate  2026-04-16 20:34:33
@author      Daniel Chung
@version     1.0.0
"""

import json
import subprocess

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = "root:abc_desktop_2026"
COLLECTION = "intent_logs"


def run_curl(method: str, url: str, data: dict[str, object] | None = None) -> dict[str, object]:
    cmd = ["curl", "-s", "-u", AUTH, "-X", method, url, "-H", "Content-Type: application/json"]
    if data:
        cmd.extend(["-d", json.dumps(data)])
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return json.loads(r.stdout) if r.stdout.strip() else {}


def main() -> None:
    print(f"=== Creating {COLLECTION} collection ===")
    base = f"{ARANGO_URL}/_db/{DB}"

    result = run_curl("POST", f"{base}/_api/collection", {"name": COLLECTION, "type": 2})
    if result.get("error") and result.get("errorNum") != 1207:
        print(f"  Collection error: {result}")
    else:
        print(f"  ✓ Collection {COLLECTION} ready")

    indexes = [
        {"type": "persistent", "fields": ["intent_id"], "name": "idx_intent_id"},
        {"type": "persistent", "fields": ["user_id", "intent_id"], "name": "idx_user_intent"},
        {"type": "persistent", "fields": ["page_type"], "name": "idx_page_type"},
        {"type": "persistent", "fields": ["action"], "name": "idx_action"},
        {"type": "persistent", "fields": ["created_at"], "name": "idx_created_at"},
    ]

    for idx in indexes:
        r = run_curl("POST", f"{base}/_api/index?collection={COLLECTION}", idx)
        if r.get("error"):
            print(f"  Index error [{idx['name']}]: {r}")
        else:
            print(f"  ✓ Index {idx['name']} ready")

    print("\n  Done.")


if __name__ == "__main__":
    main()
