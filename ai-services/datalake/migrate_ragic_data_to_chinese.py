#!/usr/bin/env python3
"""
@file        migrate_ragic_data_to_chinese.py
@description 方案 B 轉換腳本：將 da_table_data_ragic 的數字 field_id key 轉為中文欄位名，
              同時補齊 da_field_info_ragic 映射。
@lastUpdate  2026-04-11 21:45:43
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from .ragic_field_mapping import (
    EXTRA_TABLE_MAP,
    KEY_PREFIX_TABLE_MAP,
    SYSTEM_FIELDS,
    TABLE_FIELD_MAP,
)

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = "root:abc_desktop_2026"
DATA_COLL = "da_table_data_ragic"
FIELD_COLL = "da_field_info_ragic"


def aql(query: str, bind: dict[str, Any] | None = None) -> list[Any]:
    payload: dict[str, Any] = {"query": query, "batchSize": 10000}
    if bind:
        payload["bindVars"] = bind
    r = subprocess.run(
        [
            "curl", "-s", "-u", AUTH,
            f"{ARANGO_URL}/_db/{DB}/_api/cursor",
            "-X", "POST",
            "-H", "Content-Type: application/json",
            "-d", json.dumps(payload),
        ],
        capture_output=True, text=True,
    )
    body: dict[str, Any] = json.loads(r.stdout)
    if body.get("error"):
        print(f"AQL ERROR: {body.get('errorMessage', 'unknown')}", file=sys.stderr)
        return []
    result: list[Any] = body.get("result", [])
    return result


def bulk_replace(docs: list[dict[str, Any]], batch_size: int = 200) -> int:
    ok_count = 0
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        payload = json.dumps(batch)
        r = subprocess.run(
            [
                "curl", "-s", "-u", AUTH,
                f"{ARANGO_URL}/_db/{DB}/_api/document/{DATA_COLL}?overwriteMode=replace",
                "-X", "POST",
                "-H", "Content-Type: application/json",
                "-d", payload,
            ],
            capture_output=True, text=True,
        )
        results = json.loads(r.stdout)
        ok_count += sum(
            1 for x in results
            if isinstance(x, dict) and not x.get("error")
        )
    return ok_count


def resolve_table_id(doc: dict[str, Any]) -> str | None:
    raw_tid: object = doc.get("table_id")
    if isinstance(raw_tid, str) and raw_tid:
        return raw_tid
    key: str = str(doc.get("_key", ""))
    for prefix, table in sorted(KEY_PREFIX_TABLE_MAP.items(), key=lambda x: -len(x[0])):
        if key.startswith(prefix):
            return table
    return None


def get_field_map(table_id: str) -> dict[str, str] | None:
    if table_id in TABLE_FIELD_MAP:
        return TABLE_FIELD_MAP[table_id]
    if table_id in EXTRA_TABLE_MAP:
        return EXTRA_TABLE_MAP[table_id]
    return None


def convert_doc(doc: dict[str, Any], field_map: dict[str, str]) -> dict[str, Any]:
    new_doc: dict[str, Any] = {}
    for k, v in doc.items():
        if k in SYSTEM_FIELDS or k.startswith("_"):
            new_doc[k] = v
        elif k in field_map:
            new_doc[field_map[k]] = v
        else:
            new_doc[k] = v
    return new_doc


def seed_field_info(table_id: str, field_map: dict[str, str]) -> int:
    docs: list[dict[str, Any]] = []
    for fid, fname in field_map.items():
        doc_key = f"{table_id}_{fid}"
        docs.append({
            "_key": doc_key,
            "table_id": table_id,
            "field_id": fid,
            "field_name": fname,
            "field_type": "VARCHAR",
            "is_required": False,
            "description": fname,
        })
    if not docs:
        return 0
    payload = json.dumps(docs)
    r = subprocess.run(
        [
            "curl", "-s", "-u", AUTH,
            f"{ARANGO_URL}/_db/{DB}/_api/document/{FIELD_COLL}?overwriteMode=replace",
            "-X", "POST",
            "-H", "Content-Type: application/json",
            "-d", payload,
        ],
        capture_output=True, text=True,
    )
    results = json.loads(r.stdout)
    return sum(
        1 for x in results
        if isinstance(x, dict) and not x.get("error")
    )


def main() -> None:
    print("=" * 60)
    print("方案 B：da_table_data_ragic 數字 ID → 中文欄位名轉換")
    print("=" * 60)

    dry_run = "--dry-run" in sys.argv

    all_docs: list[dict[str, Any]] = aql(
        f"FOR d IN {DATA_COLL} RETURN d"
    )
    print(f"\n讀取 {len(all_docs)} 筆文件")

    table_stats: dict[str, int] = {}
    converted: list[dict[str, Any]] = []
    skipped = 0
    no_map = 0

    for doc in all_docs:
        table_id = resolve_table_id(doc)
        if not table_id:
            skipped += 1
            continue

        field_map = get_field_map(table_id)
        if not field_map:
            no_map += 1
            continue

        new_doc = convert_doc(doc, field_map)
        if table_id not in TABLE_FIELD_MAP and table_id in EXTRA_TABLE_MAP:
            new_doc["table_id"] = table_id
        converted.append(new_doc)
        table_stats[table_id] = table_stats.get(table_id, 0) + 1

    print("\n轉換結果:")
    print(f"  已轉換: {len(converted)}")
    print(f"  跳過(無 table_id): {skipped}")
    print(f"  跳過(無映射): {no_map}")
    print("\n各表統計:")
    for tid in sorted(table_stats.keys()):
        print(f"  {tid}: {table_stats[tid]} 筆")

    if dry_run:
        print("\n[DRY RUN] 不寫入，顯示前 3 筆轉換範例:")
        for doc in converted[:3]:
            tid = doc.get("table_id", "?")
            key = doc.get("_key", "?")
            fields = {k: v for k, v in doc.items() if k not in SYSTEM_FIELDS and not k.startswith("_")}
            print(f"\n  [{tid}] {key}:")
            for k, v in list(fields.items())[:5]:
                print(f"    {k}: {v}")
            if len(fields) > 5:
                print(f"    ... ({len(fields) - 5} more fields)")
        return

    print(f"\n寫入 {DATA_COLL}...")
    ok = bulk_replace(converted)
    print(f"  ✓ {ok}/{len(converted)} 筆寫入成功")

    print(f"\n補齊 {FIELD_COLL}...")
    all_tables = {**TABLE_FIELD_MAP}
    for extra_tid, extra_map in EXTRA_TABLE_MAP.items():
        all_tables[extra_tid] = extra_map
    total_fields = 0
    for tid, fmap in sorted(all_tables.items()):
        count = seed_field_info(tid, fmap)
        total_fields += count
        print(f"  ✓ {tid}: {count} 欄位")

    print(f"\n{'=' * 60}")
    print("✅ 完成！")
    print(f"  資料轉換: {ok}/{len(converted)} 筆")
    print(f"  欄位映射: {total_fields} 筆 → {FIELD_COLL}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
