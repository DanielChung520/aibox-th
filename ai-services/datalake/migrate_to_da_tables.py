#!/usr/bin/env python3
"""
@file        migrate_to_da_tables.py
@description 遷移腳本：將 da_table_info_ragic + da_field_info_ragic +
             da_table_relation_ragic 合併寫入新的 da_tables 和 da_expressions collections。
             da_tables 採用方案 A（fields + relationships 嵌入）。
@lastUpdate  2026-04-13 05:21:08
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import json
import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone

ARANGO_URL = os.environ.get("ARANGODB_URL", "http://localhost:8529")
DB = os.environ.get("ARANGODB_DATABASE", "abc_desktop")
_user = os.environ.get("ARANGODB_USERNAME", "root")
_pass = os.environ.get("ARANGODB_PASSWORD", "")
AUTH = f"{_user}:{_pass}"
SOURCE_TABLES = (
    "da_table_info_ragic",
    "da_field_info_ragic",
    "da_table_relation_ragic",
)
TARGET_TABLES = ("da_tables", "da_expressions")
MODULE_TO_DOMAIN = {
    "BASE": "base",
    "QC": "quality",
    "MFG": "manufacturing",
    "CRM_SCM": "sales",
    "TRADE": "trade",
    "MGMT": "management",
}
FIELD_TYPE_MAP = {
    "文字": "text",
    "數字": "number",
    "日期": "date",
    "選擇": "select",
    "多選": "multi_select",
    "勾選": "checkbox",
    "子表格": "subtable",
}
CARDINALITY_MAP = {"many-to-one": "n:1", "one-to-many": "1:n"}


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_curl(url: str, method: str = "POST", payload: object | None = None) -> object:
    command = ["curl", "-s", "-u", AUTH, url, "-X", method]
    if payload is not None:
        command.extend(["-H", "Content-Type: application/json", "-d", json.dumps(payload, ensure_ascii=False)])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"curl failed: {result.stderr.strip() or result.stdout.strip()}")
    data = json.loads(result.stdout)
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data))
    return data


def aql(query: str) -> list[dict[str, object]]:
    data = run_curl(
        f"{ARANGO_URL}/_db/{DB}/_api/cursor",
        payload={"query": query},
    )
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected cursor response")
    result = data.get("result")
    if not isinstance(result, list):
        raise RuntimeError("Cursor result is not a list")
    rows = [row for row in result if isinstance(row, dict)]
    while bool(data.get("hasMore")):
        cursor_id = data.get("id")
        if not isinstance(cursor_id, str):
            raise RuntimeError("Cursor missing id while hasMore is true")
        data = run_curl(f"{ARANGO_URL}/_db/{DB}/_api/cursor/{cursor_id}", method="PUT")
        if not isinstance(data, dict):
            raise RuntimeError("Unexpected cursor page response")
        page_result = data.get("result")
        if not isinstance(page_result, list):
            raise RuntimeError("Cursor page result is not a list")
        rows.extend(row for row in page_result if isinstance(row, dict))
    return rows


def ensure_collection(name: str) -> None:
    result = subprocess.run(
        ["curl", "-s", "-u", AUTH, f"{ARANGO_URL}/_db/{DB}/_api/collection/{name}", "-X", "GET"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl failed: {result.stderr.strip() or result.stdout.strip()}")
    data = json.loads(result.stdout)
    if isinstance(data, dict) and data.get("errorNum") == 1203:
        run_curl(
            f"{ARANGO_URL}/_db/{DB}/_api/collection",
            payload={"name": name, "type": 2},
        )
        print(f"✓ created collection: {name}")
        return
    print(f"✓ collection ready: {name}")


def bulk_upsert(collection: str, docs: list[dict[str, object]], batch_size: int = 30) -> None:
    if not docs:
        return
    total_errors: list[dict[str, object]] = []
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i + batch_size]
        data = run_curl(
            f"{ARANGO_URL}/_db/{DB}/_api/document/{collection}?overwriteMode=replace",
            payload=batch,
        )
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected bulk upsert response for {collection}")
        errors = [item for item in data if isinstance(item, dict) and item.get("error")]
        total_errors.extend(errors)
        print(f"  {collection} batch {i // batch_size + 1}: {len(batch) - len(errors)}/{len(batch)} ok")
    if total_errors:
        raise RuntimeError(f"Bulk upsert failed for {collection}: {total_errors[:3]}")
    print(f"✓ upserted {len(docs)} docs into {collection}")


def normalize_relation_key(value: str) -> str:
    return value.replace("-", "").upper()


def map_domain(module: object) -> str:
    if isinstance(module, str):
        return MODULE_TO_DOMAIN.get(module, module.lower())
    return "unknown"


def map_field_type(value: object) -> str:
    if isinstance(value, str):
        return FIELD_TYPE_MAP.get(value, "text")
    return "text"


def map_semantic_type(field_type: str) -> str | None:
    if field_type == "date":
        return "timestamp"
    if field_type == "number":
        return "measure"
    return None


def resolve_table_key(raw_key: object, table_ref_map: dict[str, str]) -> str:
    if not isinstance(raw_key, str):
        return ""
    return table_ref_map.get(raw_key, raw_key)


def build_field_doc(field: dict[str, object]) -> dict[str, object]:
    raw_type = field.get("field_type")
    mapped_type = map_field_type(raw_type)
    writable = bool(field.get("writable", False))
    return {
        "field_id": str(field.get("field_id", "")),
        "name": str(field.get("field_name", "")),
        "type": mapped_type,
        "semantic_type": map_semantic_type(mapped_type),
        "filterable": writable or raw_type != "子表格",
        "aggregatable": mapped_type in {"number", "date"},
        "aliases": [],
    }


def build_relationship_doc(relation: dict[str, object], table_ref_map: dict[str, str]) -> dict[str, object]:
    return {
        "target_table": resolve_table_key(relation.get("target_table"), table_ref_map),
        "join_keys": [
            {
                "source_field": str(relation.get("source_field", "")),
                "target_field": str(relation.get("target_field", "")),
            }
        ],
        "cardinality": CARDINALITY_MAP.get(str(relation.get("relation_type", "")), str(relation.get("relation_type", ""))),
    }


def build_expression_doc(table_doc: dict[str, object], timestamp: str) -> dict[str, object]:
    table_key = str(table_doc["_key"])
    display_name = str(table_doc["display_name"])
    return {
        "_key": f"{table_key}_default",
        "table_key": table_key,
        "angle": "default",
        "name": display_name,
        "description": f"查詢「{display_name}」資料表",
        "aliases": [display_name],
        "nl_examples": [f"查詢{display_name}", f"列出{display_name}資料"],
        "embedding_text": display_name,
        "status": str(table_doc["status"]),
        "updated_at": timestamp,
    }


def main() -> None:
    timestamp = iso_now()
    print("Loading source collections...")
    table_rows = aql("FOR doc IN da_table_info_ragic RETURN doc")
    field_rows = aql("FOR doc IN da_field_info_ragic RETURN doc")
    relation_rows = aql("FOR doc IN da_table_relation_ragic RETURN doc")

    field_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    relation_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    table_ref_map: dict[str, str] = {}

    for table in table_rows:
        table_key = str(table.get("_key", ""))
        relation_key = normalize_relation_key(f"{table.get('tab', '')}_{table.get('sheet_number', '')}")
        table_ref_map[table_key] = table_key
        table_ref_map[relation_key] = table_key

    for field in field_rows:
        field_groups[str(field.get("table_id", ""))].append(field)

    for relation in relation_rows:
        source_table = resolve_table_key(relation.get("source_table"), table_ref_map)
        relation_groups[source_table].append(relation)

    table_docs: list[dict[str, object]] = []
    expression_docs: list[dict[str, object]] = []
    domain_counter: Counter[str] = Counter()

    for table in table_rows:
        table_key = str(table.get("_key", ""))
        fields = [build_field_doc(field) for field in field_groups.get(table_key, [])]
        relationships = [build_relationship_doc(rel, table_ref_map) for rel in relation_groups.get(table_key, [])]
        has_number = any(str(field["type"]) == "number" for field in fields)
        has_date = any(str(field["type"]) == "date" for field in fields)
        domain = map_domain(table.get("module"))
        table_doc = {
            "_key": table_key,
            "display_name": str(table.get("table_name", "")),
            "description": "",
            "domain": domain,
            "status": str(table.get("status", "enabled")),
            "identifiers": {
                "primary": str(table.get("table_id", table_key)),
                "source": str(table.get("data_source", "ragic")),
                "aliases": [],
            },
            "source_meta": {
                "tab": str(table.get("tab", "")),
                "tab_name": str(table.get("tab_name", "")),
                "sheet_key": str(table.get("sheet_key", "")),
                "sheet_number": str(table.get("sheet_number", "")),
                "sheet_url": str(table.get("sheet_url", "")),
                "api_url": str(table.get("api_url", "")),
            },
            "capabilities": {
                "simple_filter": True,
                "aggregate": has_number,
                "time_series": has_date,
                "cross_table": len(relationships) > 0,
            },
            "fields": fields,
            "relationships": relationships,
            "updated_at": timestamp,
        }
        table_docs.append(table_doc)
        expression_docs.append(build_expression_doc(table_doc, timestamp))
        domain_counter[domain] += 1

    print("Ensuring target collections...")
    for collection in TARGET_TABLES:
        ensure_collection(collection)

    print("Writing merged documents...")
    bulk_upsert("da_tables", table_docs)
    bulk_upsert("da_expressions", expression_docs)

    print("\nMigration complete")
    print(f"tables: {len(table_docs)}")
    print(f"expressions: {len(expression_docs)}")
    print("domain distribution:")
    for domain, count in sorted(domain_counter.items(), key=lambda item: (-item[1], item[0])):
        print(f"- {domain}: {count}")
    print("source collections:")
    print(f"- tables: {SOURCE_TABLES[0]} ({len(table_rows)})")
    print(f"- fields: {SOURCE_TABLES[1]} ({len(field_rows)})")
    print(f"- relations: {SOURCE_TABLES[2]} ({len(relation_rows)})")


if __name__ == "__main__":
    main()
