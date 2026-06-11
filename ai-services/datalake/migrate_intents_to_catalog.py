#!/usr/bin/env python3
"""
@file        migrate_intents_to_catalog.py
@description 將 da_ragic_intents (111 筆) 合併到 intent_catalog，
             用 da_table_info_ragic 映射 table_key → table_id + sheet_key。
@lastUpdate  2026-04-12 21:00:53
@author      Daniel Chung
@version     1.0.0
"""

import json
import os
import subprocess
import sys
from typing import Any

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")
ARANGO_AUTH = f"{ARANGO_USER}:{ARANGO_PASSWORD}"

SOURCE_COLLECTION = "da_ragic_intents"
TARGET_COLLECTION = "intent_catalog"


def aql_query(query: str, bind_vars: dict[str, Any] | None = None) -> list[Any]:
    """Execute AQL query via ArangoDB HTTP API."""
    body: dict[str, Any] = {"query": query, "batchSize": 10000}
    if bind_vars:
        body["bindVars"] = bind_vars
    url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor"
    r = subprocess.run(
        ["curl", "-s", "-u", ARANGO_AUTH, url,
         "-X", "POST", "-H", "Content-Type: application/json",
         "-d", json.dumps(body)],
        capture_output=True, text=True, timeout=30,
    )
    data = json.loads(r.stdout)
    if data.get("error"):
        print(f"  AQL Error: {data.get('errorMessage', data)}")
        return []
    return data.get("result", [])


def build_table_key_mapping() -> dict[str, dict[str, str]]:
    """Build table_key → {table_id, sheet_key, table_name} mapping."""
    rows = aql_query(
        "FOR t IN da_table_info_ragic "
        "LET tk = CONCAT(t.tab, '/', t.sheet_number) "
        "RETURN {table_key: tk, table_id: t.table_id, "
        "sheet_key: t.sheet_key, table_name: t.table_name}"
    )
    mapping: dict[str, dict[str, str]] = {}
    for row in rows:
        tk = str(row.get("table_key", ""))
        if tk:
            mapping[tk] = {
                "table_id": str(row.get("table_id", "")),
                "sheet_key": str(row.get("sheet_key", "")),
                "table_name": str(row.get("table_name", "")),
            }
    return mapping


def fetch_source_intents() -> list[dict[str, Any]]:
    """Fetch all intents from da_ragic_intents."""
    return aql_query(f"FOR d IN {SOURCE_COLLECTION} RETURN d")


def fetch_existing_keys() -> set[str]:
    """Fetch existing _key values from intent_catalog for data_agent."""
    rows = aql_query(
        f"FOR d IN {TARGET_COLLECTION} "
        "FILTER d.agent_scope == 'data_agent' "
        "RETURN d._key"
    )
    return {str(r) for r in rows}


def transform_intent(
    doc: dict[str, Any],
    mapping: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Transform a da_ragic_intents doc for intent_catalog."""
    table_key = str(doc.get("table_key", ""))
    mapped = mapping.get(table_key, {})
    table_id = mapped.get("table_id", "")
    sheet_key = mapped.get("sheet_key", "")

    nl_patterns = doc.get("nl_patterns", [])
    if not isinstance(nl_patterns, list):
        nl_patterns = []
    nl_examples = doc.get("nl_examples", [])
    if not isinstance(nl_examples, list):
        nl_examples = nl_patterns.copy()

    return {
        "_key": str(doc.get("_key", doc.get("intent_id", ""))),
        "intent_id": str(doc.get("intent_id", "")),
        "agent_scope": "data_agent",
        "name": str(doc.get("name", nl_patterns[0] if nl_patterns else "")),
        "description": str(doc.get("description", "")),
        "status": str(doc.get("status", "enabled")),
        "priority": doc.get("priority", 0),
        "table_id": table_id,
        "sheet_key": sheet_key,
        "table_key": table_key,
        "tables": [table_id] if table_id else [],
        "action": str(doc.get("action", "list")),
        "group": str(doc.get("group", "")),
        "intent_type": str(doc.get("intent_type", "filter")),
        "generation_strategy": str(doc.get("generation_strategy", "template")),
        "sql_template": str(doc.get("sql_template", "")),
        "core_fields": doc.get("core_fields", []),
        "nl_examples": nl_examples,
        "nl_patterns": nl_patterns,
        "example_sqls": doc.get("example_sqls", []),
        "api_template": str(doc.get("api_template", "")),
        "filter_template": doc.get("filter_template"),
        "account": str(doc.get("account", "")),
        "tool_name": str(doc.get("tool_name", "")),
        "created_at": str(doc.get("created_at", "2026-04-12T00:00:00Z")),
        "updated_at": "2026-04-12T21:00:00Z",
        "updated_by": "migration_script",
        "migrated_from": SOURCE_COLLECTION,
    }


def upsert_batch(docs: list[dict[str, Any]]) -> tuple[int, int]:
    """Batch upsert documents into intent_catalog."""
    url = (
        f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/"
        f"{TARGET_COLLECTION}?overwriteMode=replace"
    )
    r = subprocess.run(
        ["curl", "-s", "-u", ARANGO_AUTH, url,
         "-X", "POST", "-H", "Content-Type: application/json",
         "-d", json.dumps(docs)],
        capture_output=True, text=True, timeout=30,
    )
    try:
        result = json.loads(r.stdout)
    except json.JSONDecodeError:
        return 0, len(docs)

    errors = 0
    if isinstance(result, dict) and result.get("error"):
        errors = len(docs)
    elif isinstance(result, list):
        errors = sum(1 for item in result if item.get("error"))
    return len(docs) - errors, errors


def main() -> None:
    print("=" * 60)
    print("Migrate da_ragic_intents → intent_catalog")
    print("=" * 60)

    # Step 1: Build mapping
    print("\n[1/4] Building table_key → table_id mapping...")
    mapping = build_table_key_mapping()
    print(f"  Loaded {len(mapping)} table_key mappings")

    # Step 2: Fetch source
    print("\n[2/4] Fetching da_ragic_intents...")
    source = fetch_source_intents()
    print(f"  Found {len(source)} intents")
    if not source:
        print("  No intents to migrate. Exiting.")
        sys.exit(0)

    # Step 3: Check existing
    existing = fetch_existing_keys()
    print(f"  Existing data_agent keys in intent_catalog: {len(existing)}")

    # Step 4: Transform and upsert
    print("\n[3/4] Transforming and upserting...")
    transformed: list[dict[str, Any]] = []
    unmapped = 0
    for doc in source:
        t = transform_intent(doc, mapping)
        if not t["table_id"]:
            unmapped += 1
            tk = t.get("table_key", "?")
            print(f"  ⚠ No mapping for table_key='{tk}' (intent={t['intent_id']})")
        transformed.append(t)

    batch_size = 50
    total_ok = 0
    total_err = 0
    for i in range(0, len(transformed), batch_size):
        batch = transformed[i : i + batch_size]
        ok, err = upsert_batch(batch)
        total_ok += ok
        total_err += err

    # Step 5: Summary
    print(f"\n[4/4] Migration Summary")
    print(f"  Source intents:     {len(source)}")
    print(f"  Transformed:       {len(transformed)}")
    print(f"  Mapped to table_id:{len(transformed) - unmapped}")
    print(f"  Unmapped:          {unmapped}")
    print(f"  Upserted OK:       {total_ok}")
    print(f"  Errors:            {total_err}")

    # Verify
    print("\n[Verify] Counting intent_catalog data_agent scope...")
    count = aql_query(
        f"FOR d IN {TARGET_COLLECTION} "
        "FILTER d.agent_scope == 'data_agent' "
        "COLLECT WITH COUNT INTO c RETURN c"
    )
    print(f"  intent_catalog data_agent total: {count[0] if count else '?'}")

    # Sample
    print("\n[Sample] First 5 migrated intents:")
    for doc in transformed[:5]:
        print(
            f"  {doc['intent_id']} → "
            f"table_id={doc['table_id']}, "
            f"sheet_key={doc['sheet_key']}, "
            f"action={doc['action']}"
        )

    print("\n" + "=" * 60)
    if total_err == 0 and unmapped == 0:
        print("✅ Migration completed successfully!")
    elif total_err == 0:
        print(f"⚠ Migration completed with {unmapped} unmapped intents.")
    else:
        print(f"❌ Migration completed with {total_err} errors.")
    print("=" * 60)


if __name__ == "__main__":
    main()
