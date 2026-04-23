#!/usr/bin/env python3
"""
@file        parse_dawnlink_schema.py
@description Parse dawnlink202604.md and extract schema for Qdrant sync.
@lastUpdate  2026-04-18
@author      Daniel Chung
@version     1.0.0
"""

import re
import json
import httpx
from pathlib import Path
from collections import defaultdict
from typing import Optional

ARANGO_URL = "http://localhost:8529"
QDRANT_URL = "http://localhost:6333"
ARANGO_DB = "abc_desktop"
ARANGO_AUTH = ("root", "abc_desktop_2026")
RAGIC_KEY = "aUlySUNpcE1NY3FFVWVlZ0hWRVU1S3Y0VXRSYnFGcXJJZ1BwL20xV2F4QTN1K0NnVVZodzNwWmdjUFBkMmVYMg=="

# Module inference mapping
TAB_MODULE = {
    "database": "BASE",
    "configuration-file": "BASE",
    "config-file-details": "BASE",
    "erp": "ERP",
    "forms4": "ERP",
    "form": "ERP",
    "forms": "ERP",
    "ragicpurchasing": "PURCHASE",
    "ragicforms3": "PURCHASE",
    "procurement": "PURCHASE",
    "ragicsales": "SALES",
    "forms9": "SALES",
    "not-follow-up-form": "SALES",
    "stock": "INVENTORY",
    "mes": "PRODUCTION",
    "mes2": "PRODUCTION",
    "quality-forms": "PRODUCTION",
    "manage-4-forms": "PRODUCTION",
    "-v2": "TEST",
    "iso2": "ISO",
    "work-reporting-area": "HR",
    "ragicadministration": "ADMIN",
    "ragicforms": "CRM",
    "ragicforms4": "CRM",
    "ragicforms6": "MISC",
    "ragicproject-management": "PROJECT",
    "ragicsystem": "SYSTEM",
}


def slug(text: str) -> str:
    """Convert text to a slug for IDs."""
    return re.sub(r"[^A-Za-z0-9]", "", text)[:30]


def infer_module(tab: str) -> str:
    """Infer module from tab path."""
    tab_lower = tab.lower()
    for key, mod in TAB_MODULE.items():
        if key in tab_lower or tab_lower in key:
            return mod
    return "MISC"


def parse_sheet_section(section: str, tab_path: str, sheet_idx: str) -> Optional[dict]:
    """Parse a single sheet section and extract field info."""
    lines = section.strip().split("\n")
    
    # Get sheet name
    name_match = re.search(r'### 表單:\s*(.+?)(?:\n|$)', section)
    if not name_match:
        return None
    sheet_name = name_match.group(1).strip()
    
    # Build table key
    table_key = f"{tab_path}/{sheet_idx}"
    
    # Extract field information
    # Pattern: | Field Name | Field ID | Type | ... |
    field_pattern = r'\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|'
    fields = {}
    
    for line in lines:
        match = re.search(field_pattern, line)
        if match:
            fname = match.group(1).strip()
            fid = match.group(2).strip()
            if fname and fid and fname != "Field Name":
                # Use 'name' as required by RagicFieldSchema model
                fields[fid] = {
                    "name": fname,
                    "field_type": "text",
                }
    
    return {
        "account": "dawnlink",
        "table_key": table_key,
        "table_name": sheet_name,
        "tab_path": tab_path,
        "sheet_index": int(sheet_idx) if sheet_idx.isdigit() else 0,
        "description": f"{sheet_name} - {tab_path}",
        "module": infer_module(tab_path),
        "version": "1.0.0",
        "fields": fields,
        "subtables": {},
    }


def parse_dawnlink_md(md_path: Path) -> list[dict]:
    """Parse dawnlink202604.md and extract all sheets."""
    
    content = md_path.read_text(encoding='utf-8')
    
    # Split by "### 表單:" to get individual sheet sections
    # Each sheet section starts with "### 表單:"
    parts = re.split(r'(?=### 表單:)', content)
    
    schemas = []
    for part in parts:
        if not part.strip().startswith('### 表單:'):
            continue
        
        # Extract tab path and sheet index from URLs in this section
        url_match = re.search(r'ap15\.ragic\.com/dawnlink/([^/]+)/(\d+)', part)
        if not url_match:
            continue
        
        tab_path = url_match.group(1)
        sheet_idx = url_match.group(2)
        
        schema = parse_sheet_section(part, tab_path, sheet_idx)
        if schema:
            schemas.append(schema)
    
    return schemas


def get_sheet_name_from_toc(content: str) -> dict:
    """Extract sheet names from Table of Contents."""
    # Pattern: "- Sheet: SHEET_NAME"
    sheet_pattern = r'- Sheet:\s*(.+?)(?:\n|$)'
    sheets = re.findall(sheet_pattern, content)
    return {name.strip(): name.strip() for name in sheets}


def sync_to_qdrant(schemas: list[dict]) -> dict:
    """Sync schemas to Qdrant ragic_schemas collection."""
    
    # Prepare points for Qdrant - using zero vector placeholder (size 1024)
    zero_vector = [0.0] * 1024
    points = []
    for i, schema in enumerate(schemas):
        point = {
            "id": i + 1,
            "vector": zero_vector,
            "payload": schema,
        }
        points.append(point)
    
    # Upsert to Qdrant
    response = httpx.put(
        f"{QDRANT_URL}/collections/ragic_schemas/points",
        json={"points": points},
        timeout=120.0,
    )
    
    return response.json()


def main():
    print("=" * 60)
    print("Dawnlink Schema Parser for Qdrant Sync")
    print("=" * 60)
    
    # Path to dawnlink backup
    md_path = Path("/Users/daniel/GitHub/AIBox/.docs/Ragic/dawnlink/dawnlink202604.md")
    
    if not md_path.exists():
        print(f"ERROR: File not found: {md_path}")
        return
    
    print(f"\nParsing: {md_path}")
    schemas = parse_dawnlink_md(md_path)
    print(f"Found {len(schemas)} sheets")
    
    # Show breakdown by module
    modules = defaultdict(int)
    for schema in schemas:
        modules[schema["module"]] += 1
    
    print("\nBreakdown by module:")
    for mod, count in sorted(modules.items()):
        print(f"  {mod}: {count}")
    
    # Show first 3 schemas as preview
    print("\nFirst 3 schemas (preview):")
    for schema in schemas[:3]:
        print(f"  - {schema['table_name']} ({schema['tab_path']}/{schema['sheet_index']})")
        print(f"    Fields: {len(schema['fields'])}")
    
    # Sync to Qdrant
    print("\n" + "=" * 60)
    print("Syncing to Qdrant...")
    result = sync_to_qdrant(schemas)
    
    if result.get("status") == "ok":
        print(f"✓ Successfully synced {len(schemas)} schemas to Qdrant")
    else:
        print(f"⚠ Qdrant response: {result}")
    
    print("\n" + "=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()