#!/usr/bin/env python3
"""
@file        seed_ragic_schema_full.py
@description 全量遷移 Ragic sheets 至 ArangoDB（支援多帳號）
@lastUpdate  2026-04-19 01:54:35
@author      Daniel Chung
@version     2.0.0
"""

import os
import re
import subprocess
import json
from datetime import datetime, UTC
from pathlib import Path

ARANGO_URL = os.environ.get("ARANGODB_URL", "http://localhost:8529")
DB = os.environ.get("ARANGODB_DATABASE", "abc_desktop")
_user = os.environ.get("ARANGODB_USERNAME", "root")
_pass = os.environ.get("ARANGODB_PASSWORD", "")
AUTH = f"{_user}:{_pass}"
TS = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
SCHEMA_FILE = Path(__file__).parent.parent.parent / ".docs/Ragic/dawnlink/dawnlink202604.md"

TYPE_MAP = {
    "文字": "VARCHAR", "數字": "DECIMAL", "日期": "DATE",
    "單選": "VARCHAR", "多選": "VARCHAR", "核取方塊": "BOOLEAN",
    "勾選": "BOOLEAN", "電話": "VARCHAR", "電子郵件": "VARCHAR",
    "URL": "VARCHAR", "計算": "DECIMAL", "自動編號": "VARCHAR",
    "地址": "VARCHAR", "圖片": "VARCHAR", "附件": "VARCHAR",
    "貨幣": "DECIMAL", "百分比": "DECIMAL", "子表格": "SUBTABLE",
    "分段": "VARCHAR", "備註": "TEXT", "公式": "VARCHAR",
    "組織選擇": "VARCHAR", "連結欄位": "VARCHAR", "html": "TEXT",
}

TAB_MODULE = {
    "configuration-file": "BASE", "database": "BASE", "erp": "ERP",
    "forms4": "ERP", "form": "ERP", "ragicpurchasing": "PURCHASE",
    "ragicforms3": "PURCHASE", "order-operation": "SALES",
    "ragicsales": "SALES", "stock": "INVENTORY",
    "inventory-management": "INVENTORY", "inventory-check": "INVENTORY",
    "production-management": "PRODUCTION", "mes2": "PRODUCTION",
    "accounts": "ACCOUNTING", "accounts-payable": "ACCOUNTING",
    "plm-4": "PLM", "plm-": "PLM", "plm-bom": "PLM",
    "plm-3": "PLM", "plm-5": "PLM", "plm-6": "PLM", "plm-7": "PLM",
    "customer-service-management": "CRM", "work-reporting-area": "HR",
    "work-reporting-and-vehicle-dispatch": "HR",
    "service-tickets": "SERVICE", "shared-data": "BASE",
    "iso2": "ISO", "system-requirements-planning": "SRP",
    "not-follow-up-form": "CRM", "forms9": "MISC",
    "config-file-details": "BASE", "ragicforms6": "MISC",
    "ragicsystem": "BASE", "ragicproject-management": "PROJECT",
}

PHASE1_ALIAS = {
    "組織部門": "CFG2_DEPT", "倉儲位管理": "CFG3_WAREHOUSE",
    "員工管理": "CFG7_EMPLOYEE", "品項管理": "CFG9_ITEM",
    "交易對象": "CFG10_VENDOR", "員工清單": "CFG7_EMPLOYEE",
    "進貨明細": "ERP48_PURCHASE_ORDER", "進貨單": "ERP_PURCHASE_ORDER",
}


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", text)[:30]


def slug_upper(text: str) -> str:
    return slug(text).upper()


def infer_field_type(t: str) -> str:
    for key, dtype in TYPE_MAP.items():
        if key in t:
            return dtype
    return "VARCHAR"


def infer_module(tab: str) -> str:
    tab_l = tab.lower()
    for key, mod in TAB_MODULE.items():
        if key in tab_l or tab_l in key:
            return mod
    return "MISC"


def is_writable(w: str) -> bool:
    return "可寫入" in w or "可寫" in w


def is_pk(memo: str) -> bool:
    return "不可重複" in memo


def make_field_key(table_id: str, field_id: str) -> str:
    return f"{slug(table_id)[:20]}_{slug(field_id)[:20]}"


def normalize_tab(t: str) -> str:
    return t.strip()


def curl_post(collection: str, docs: list) -> list:
    payload = json.dumps(docs)
    r = subprocess.run(
        ["curl", "-s", "-u", AUTH,
         f"{ARANGO_URL}/_db/{DB}/_api/document/{collection}?overwriteMode=replace",
         "-X", "POST", "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return [{"error": True, "errorMessage": r.stdout[:200]}]


def insert_batch(collection: str, docs: list, label: str, batch_size: int = 50) -> None:
    total = len(docs)
    for i in range(0, total, batch_size):
        batch = docs[i:i + batch_size]
        result = curl_post(collection, batch)
        errors = sum(1 for r in result if isinstance(r, dict) and r.get("error"))
        if errors > 0:
            for r in result[:3]:
                if isinstance(r, dict) and r.get("error"):
                    print(f"  ERR [{r.get('_key','?')}]: {r.get('errorMessage','?')}")
        print(f"  {label} [{i//batch_size+1}]: {len(batch)-errors}/{len(batch)} ok")
    print(f"  ✓ {label}: {total} total")


def clear_collection(collection: str) -> None:
    r = subprocess.run(
        ["curl", "-s", "-u", AUTH,
         f"{ARANGO_URL}/_db/{DB}/_api/collection/{collection}/truncate",
         "-X", "PUT"],
        capture_output=True, text=True)
    try:
        result = json.loads(r.stdout)
        if not result.get("error"):
            print(f"  ✓ Cleared {collection}")
        else:
            print(f"  ⚠ {collection}: {result.get('errorMessage','truncate failed')}")
    except Exception:
        print(f"  ⚠ {collection}: truncate failed")


def build_sheet_map(raw_sheets: list) -> dict:
    sheet_map = {}
    for raw in raw_sheets:
        lines = raw.strip().split("\n")
        name = lines[0].strip()
        tab, sheet_key = "", ""
        for line in lines[:15]:
            m = re.search(r"ap15\.ragic\.com/[^/]+/([^/]+)/(\d+)", line)
            if m:
                tab = normalize_tab(m.group(1))
                sheet_key = m.group(2)
                break
        tab_s = slug_upper(tab) or "MISC"
        table_id = f"{tab_s}_{sheet_key}" if sheet_key else f"{tab_s}_X"
        sheet_map[name] = table_id
    return sheet_map


def sheet_to_table_id(name: str, sheet_map: dict) -> str:
    if name in PHASE1_ALIAS:
        return PHASE1_ALIAS[name]
    if name in sheet_map:
        return sheet_map[name]
    return slug_upper(name)


def parse_field_table(lines: list, table_id: str, subtable_key: str | None,
                      is_subtable: bool, sheet_map: dict) -> list:
    fields = []
    data_lines = [l for l in lines
                  if l.startswith("|") and "---" not in l
                  and "Field Name" not in l and "Field ID" not in l]
    for line in data_lines:
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) < 4:
            continue
        fname, fid = cols[0], cols[1]
        if not fname or not fid or fid == "Field ID":
            continue
        ragic_type = cols[2]
        writable = cols[3]
        # Memo is 6th column (index 5) — some tables only have 5 cols (no write_format)
        memo = cols[5] if len(cols) > 5 else (cols[4] if len(cols) > 4 else "")

        rel_table, rel_field = None, None
        lm = re.search(r"連結到(.+?)表單上的(.+?)(?:從|$)", memo)
        if lm:
            rel_table = sheet_to_table_id(lm.group(1).strip(), sheet_map)
            rel_field = lm.group(2).strip()

        fields.append({
            "_key": make_field_key(table_id, fid),
            "table_id": table_id,
            "field_id": fid,
            "field_name": fname,
            "field_type": infer_field_type(ragic_type),
            "nullable": not is_pk(memo),
            "description": memo[:200],
            "business_aliases": [fname],
            "is_pk": is_pk(memo),
            "is_fk": rel_table is not None,
            "relation_table": rel_table,
            "relation_field": rel_field or "_ragicId",
            "writable": is_writable(writable),
            "is_subtable_field": is_subtable,
            "subtable_key": subtable_key,
            "status": "enabled",
        })
    return fields


def parse_sheet(raw: str, sheet_map: dict) -> dict:
    lines = raw.strip().split("\n")
    name = lines[0].strip()
    tab, sheet_key, form_key = "", "", ""

    for line in lines[:15]:
        m = re.search(r"ap15\.ragic\.com/[^/]+/([^/]+)/(\d+)", line)
        if m:
            tab = normalize_tab(m.group(1))
            sheet_key = m.group(2)
            break
        m2 = re.search(r"主表單Key:\s*(\d+)", line)
        if m2:
            form_key = m2.group(1)

    tab_s = slug_upper(tab) or "MISC"
    table_id = f"{tab_s}_{sheet_key}" if sheet_key else f"{tab_s}_X"

    sections: list[tuple[str, str]] = []
    buf, in_sub = [], False
    sub_name = ""

    for line in lines:
        if "#### 子表格欄位標頭" in line:
            if buf:
                sections.append(("", "\n".join(buf)))
                buf = []
            m = re.search(r"子表格Key:\s*(\d+)", line)
            sk = m.group(1) if m else sheet_key
            sub_name = f"{table_id}_SUB_{sk}"
            in_sub = True
        elif line.startswith("#### ") and in_sub:
            sections.append((sub_name, "\n".join(buf)))
            buf, in_sub = [], False
        else:
            buf.append(line)
    if buf:
        sections.append(("", "\n".join(buf)))

    all_fields = []
    for st_name, st_content in sections:
        is_sub = st_name != ""
        fields = parse_field_table(
            st_content.split("\n"), table_id,
            st_name if is_sub else None, is_sub, sheet_map)
        all_fields.extend(fields)

    table = {
        "_key": table_id,
        "table_id": table_id,
        "table_name": name,
        "tab": tab,
        "sheet_key": sheet_key,
        "form_key": form_key,
        "module": infer_module(tab),
        "description": name,
        "s3_path": f"s3://ragic/{tab}/{table_id.lower()}/",
        "primary_keys": ["_ragicId"],
        "partition_keys": [],
        "record_count": 0,
        "data_source": "ragic",
        "status": "enabled",
        "version": 1,
        "created_at": TS,
        "updated_at": TS,
        "updated_by": "system",
    }
    return {"table": table, "fields": all_fields}


def main():
    print("=" * 60)
    print("Full Ragic Schema Migration")
    print("=" * 60)

    content = SCHEMA_FILE.read_text(encoding="utf-8")
    raw_sheets = re.split(r"^### 表單: ", content, flags=re.MULTILINE)[1:]
    print(f"\nParsing {len(raw_sheets)} sheets...")

    sheet_map = build_sheet_map(raw_sheets)

    tables, all_fields, relations = [], [], []
    seen, key_counter = set(), 0

    for raw in raw_sheets:
        try:
            result = parse_sheet(raw, sheet_map)
        except Exception as e:
            print(f"  ⚠ Parse error '{raw[:30]}': {e}")
            continue

        table = result["table"]
        fields = result["fields"]

        while table["_key"] in seen:
            key_counter += 1
            table["_key"] = f"{table['_key']}_{key_counter}"
            table["table_id"] = table["_key"]

        seen.add(table["_key"])

        for f in fields:
            f["table_id"] = table["_key"]
            f["_key"] = make_field_key(table["_key"], f["field_id"])
            if f.get("relation_table"):
                rel_key = f"rel_{slug(f['table_id'])}_{slug(f['field_id'])}"
                relations.append({
                    "_key": rel_key,
                    "relation_id": rel_key,
                    "source_table": f["table_id"],
                    "source_field": f["field_id"],
                    "target_table": f["relation_table"],
                    "target_field": f["relation_field"] or "_ragicId",
                    "relation_type": "many-to-one",
                    "description": f["field_name"],
                    "data_source": "ragic",
                    "status": "enabled",
                    "created_at": TS,
                    "updated_at": TS,
                    "updated_by": "system",
                })

        tables.append(table)
        all_fields.extend(fields)
        print(f"  ✓ {table['_key']}: {len(fields)} fields | tab={table['tab']}")

    print(f"\n  Total: {len(tables)} tables, {len(all_fields)} fields, {len(relations)} relations")

    print("\n" + "=" * 60)
    print("Clearing existing Ragic collections...")
    for col in ["da_table_info_ragic", "da_field_info_ragic", "da_table_relation_ragic"]:
        clear_collection(col)

    print("\n" + "=" * 60)
    print("Inserting da_table_info_ragic...")
    insert_batch("da_table_info_ragic", tables, "tables")

    print("\n" + "=" * 60)
    print("Inserting da_field_info_ragic...")
    insert_batch("da_field_info_ragic", all_fields, "fields")

    print("\n" + "=" * 60)
    print("Inserting da_table_relation_ragic...")
    insert_batch("da_table_relation_ragic", relations, "relations")

    print("\n" + "=" * 60)
    print("Verifying...")
    for col, expected in [
        ("da_table_info_ragic", len(tables)),
        ("da_field_info_ragic", len(all_fields)),
        ("da_table_relation_ragic", len(relations)),
    ]:
        r = subprocess.run(
            ["curl", "-s", "-u", AUTH,
             f"{ARANGO_URL}/_db/{DB}/_api/cursor",
             "-X", "POST", "-H", "Content-Type: application/json",
             "-d", json.dumps({"query": f"RETURN LENGTH(FOR d IN {col} RETURN d)"})],
            capture_output=True, text=True)
        try:
            count = json.loads(r.stdout)["result"][0]
            status = "✓" if count == expected else f"⚠ expected {expected}"
            print(f"  {col}: {count} {status}")
        except Exception as e:
            print(f"  {col}: verify failed — {e}")

    print(f"\n{'=' * 60}")
    print("Done! Tables={}, Fields={}, Relations={}".format(
        len(tables), len(all_fields), len(relations)))


if __name__ == "__main__":
    main()
