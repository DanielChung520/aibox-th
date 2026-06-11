#!/usr/bin/env python3
"""
Incremental seed: Add MKPF, MARD, MCHB tables + update MSEG description.

@file        seed_inventory_tables.py
@description 補齊 MM 庫存交易體系: MKPF(物料憑證表頭), MARD(倉庫庫存), MCHB(批次庫存)
@lastUpdate  2026-03-22 17:08:09
@author      Daniel Chung
@version     1.0.0
"""
import subprocess
import json

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = "root:abc_desktop_2026"
TS = "2026-03-22T00:00:00Z"


def aql_exec(query: str, bind_vars: dict | None = None) -> dict:
    """Execute AQL query via HTTP API."""
    payload: dict = {"query": query}
    if bind_vars:
        payload["bindVars"] = bind_vars
    r = subprocess.run([
        "curl", "-s", "-u", AUTH,
        f"{ARANGO_URL}/_db/{DB}/_api/cursor",
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(payload)
    ], capture_output=True, text=True)
    return json.loads(r.stdout)


def upsert_doc(collection: str, doc: dict) -> None:
    """Insert or update document by _key."""
    r = subprocess.run([
        "curl", "-s", "-u", AUTH,
        f"{ARANGO_URL}/_db/{DB}/_api/document/{collection}/{doc['_key']}",
        "-X", "PUT",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(doc)
    ], capture_output=True, text=True)
    result = json.loads(r.stdout)
    if result.get("error") and result.get("errorNum") == 1202:
        # Document not found, create it
        subprocess.run([
            "curl", "-s", "-u", AUTH,
            f"{ARANGO_URL}/_db/{DB}/_api/document/{collection}",
            "-X", "POST",
            "-H", "Content-Type: application/json",
            "-d", json.dumps(doc)
        ], capture_output=True, text=True)


def bulk_upsert(collection: str, docs: list) -> None:
    """Upsert multiple documents."""
    for doc in docs:
        upsert_doc(collection, doc)


# ==================== 1. UPDATE MSEG description ====================
print("1. Updating MSEG description...")
aql_exec(
    'UPDATE @key WITH { description: @desc, updated_at: @ts } IN da_table_info',
    {"key": "MM_MSEG", "desc": "庫存交易/物料憑證行項目 (Stock Movement / Material Document)", "ts": TS}
)
print("  ✓ MSEG description updated")

# ==================== 2. NEW TABLES ====================
print("\n2. Seeding new tables: MKPF, MARD, MCHB...")

new_tables = [
    {
        "_key": "MM_MKPF", "table_id": "MM_MKPF", "table_name": "MKPF",
        "module": "MM",
        "description": "物料憑證表頭 (Material Document Header)",
        "s3_path": "s3://sap/mm/mkpf/",
        "primary_keys": ["MBLNR", "MJAHR"],
        "partition_keys": ["BUDAT_YEAR", "BUDAT_MONTH"],
        "record_count": 5000,
        "row_count_estimate": 50000,
        "status": "enabled", "version": 1,
        "created_at": TS, "updated_at": TS, "updated_by": "system"
    },
    {
        "_key": "MM_MARD", "table_id": "MM_MARD", "table_name": "MARD",
        "module": "MM",
        "description": "倉庫層級庫存 (Storage Location Stock)",
        "s3_path": "s3://sap/mm/mard/",
        "primary_keys": ["MATNR", "WERKS", "LGORT"],
        "partition_keys": [],
        "record_count": 3000,
        "row_count_estimate": 30000,
        "status": "enabled", "version": 1,
        "created_at": TS, "updated_at": TS, "updated_by": "system"
    },
    {
        "_key": "MM_MCHB", "table_id": "MM_MCHB", "table_name": "MCHB",
        "module": "MM",
        "description": "批次庫存 (Batch Stock)",
        "s3_path": "s3://sap/mm/mchb/",
        "primary_keys": ["MATNR", "WERKS", "LGORT", "CHARG"],
        "partition_keys": [],
        "record_count": 2000,
        "row_count_estimate": 20000,
        "status": "enabled", "version": 1,
        "created_at": TS, "updated_at": TS, "updated_by": "system"
    },
]

bulk_upsert("da_table_info", new_tables)
print(f"  ✓ {len(new_tables)} tables upserted")

# ==================== 3. NEW FIELDS ====================
print("\n3. Seeding fields for MKPF, MARD, MCHB...")

new_fields = [
    # ---- MKPF (物料憑證表頭) ----
    {"_key": "MM_MKPF_MBLNR", "table_id": "MM_MKPF", "field_id": "MBLNR", "field_name": "MBLNR", "field_type": "VARCHAR", "length": 10, "scale": 0, "nullable": False,
     "description": "物料憑證號", "business_aliases": ["憑證號", "M-doc"], "is_pk": True, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MKPF_MJAHR", "table_id": "MM_MKPF", "field_id": "MJAHR", "field_name": "MJAHR", "field_type": "VARCHAR", "length": 4, "scale": 0, "nullable": False,
     "description": "憑證年份", "business_aliases": ["年份"], "is_pk": True, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MKPF_BLDAT", "table_id": "MM_MKPF", "field_id": "BLDAT", "field_name": "BLDAT", "field_type": "DATE", "length": 8, "scale": 0, "nullable": False,
     "description": "文件日期", "business_aliases": ["文件日"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MKPF_BUDAT", "table_id": "MM_MKPF", "field_id": "BUDAT", "field_name": "BUDAT", "field_type": "DATE", "length": 8, "scale": 0, "nullable": False,
     "description": "過帳日期", "business_aliases": ["過帳日", "記帳日期"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MKPF_USNAM", "table_id": "MM_MKPF", "field_id": "USNAM", "field_name": "USNAM", "field_type": "VARCHAR", "length": 12, "scale": 0, "nullable": False,
     "description": "使用者名稱", "business_aliases": ["建立者"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MKPF_TCODE", "table_id": "MM_MKPF", "field_id": "TCODE", "field_name": "TCODE", "field_type": "VARCHAR", "length": 20, "scale": 0, "nullable": True,
     "description": "交易碼", "business_aliases": ["T-code"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MKPF_XBLNR", "table_id": "MM_MKPF", "field_id": "XBLNR", "field_name": "XBLNR", "field_type": "VARCHAR", "length": 16, "scale": 0, "nullable": True,
     "description": "參考文件號", "business_aliases": ["參考號"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MKPF_BKTXT", "table_id": "MM_MKPF", "field_id": "BKTXT", "field_name": "BKTXT", "field_type": "VARCHAR", "length": 25, "scale": 0, "nullable": True,
     "description": "憑證表頭文字", "business_aliases": ["備註"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MKPF_VGART", "table_id": "MM_MKPF", "field_id": "VGART", "field_name": "VGART", "field_type": "VARCHAR", "length": 2, "scale": 0, "nullable": False,
     "description": "交易/事件類型", "business_aliases": [], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MKPF_CPUDT", "table_id": "MM_MKPF", "field_id": "CPUDT", "field_name": "CPUDT", "field_type": "DATE", "length": 8, "scale": 0, "nullable": False,
     "description": "輸入日期 (CPU)", "business_aliases": [], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},

    # ---- MARD (倉庫層級庫存) ----
    {"_key": "MM_MARD_MATNR", "table_id": "MM_MARD", "field_id": "MATNR", "field_name": "MATNR", "field_type": "VARCHAR", "length": 18, "scale": 0, "nullable": False,
     "description": "物料編號", "business_aliases": ["物料", "料號"], "is_pk": True, "is_fk": True, "relation_table": "MM_MARA", "relation_field": "MATNR"},
    {"_key": "MM_MARD_WERKS", "table_id": "MM_MARD", "field_id": "WERKS", "field_name": "WERKS", "field_type": "VARCHAR", "length": 4, "scale": 0, "nullable": False,
     "description": "工廠", "business_aliases": ["工廠"], "is_pk": True, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARD_LGORT", "table_id": "MM_MARD", "field_id": "LGORT", "field_name": "LGORT", "field_type": "VARCHAR", "length": 4, "scale": 0, "nullable": False,
     "description": "儲存地點", "business_aliases": ["倉庫", "倉別", "庫位"], "is_pk": True, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARD_LABST", "table_id": "MM_MARD", "field_id": "LABST", "field_name": "LABST", "field_type": "DECIMAL", "length": 13, "scale": 3, "nullable": False,
     "description": "非限制使用庫存", "business_aliases": ["可用庫存", "自由庫存", "在庫量"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARD_INSME", "table_id": "MM_MARD", "field_id": "INSME", "field_name": "INSME", "field_type": "DECIMAL", "length": 13, "scale": 3, "nullable": False,
     "description": "品質檢驗庫存", "business_aliases": ["檢驗庫存", "QI庫存"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARD_SPEME", "table_id": "MM_MARD", "field_id": "SPEME", "field_name": "SPEME", "field_type": "DECIMAL", "length": 13, "scale": 3, "nullable": False,
     "description": "凍結庫存", "business_aliases": ["鎖定庫存", "Blocked Stock"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARD_UMLME", "table_id": "MM_MARD", "field_id": "UMLME", "field_name": "UMLME", "field_type": "DECIMAL", "length": 13, "scale": 3, "nullable": False,
     "description": "在途轉撥庫存", "business_aliases": ["在途庫存"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARD_RETME", "table_id": "MM_MARD", "field_id": "RETME", "field_name": "RETME", "field_type": "DECIMAL", "length": 13, "scale": 3, "nullable": False,
     "description": "退貨庫存", "business_aliases": ["退貨量"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARD_LFGJA", "table_id": "MM_MARD", "field_id": "LFGJA", "field_name": "LFGJA", "field_type": "VARCHAR", "length": 4, "scale": 0, "nullable": True,
     "description": "最近收貨年度", "business_aliases": [], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARD_LFMON", "table_id": "MM_MARD", "field_id": "LFMON", "field_name": "LFMON", "field_type": "VARCHAR", "length": 2, "scale": 0, "nullable": True,
     "description": "最近收貨月份", "business_aliases": [], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},

    # ---- MCHB (批次庫存) ----
    {"_key": "MM_MCHB_MATNR", "table_id": "MM_MCHB", "field_id": "MATNR", "field_name": "MATNR", "field_type": "VARCHAR", "length": 18, "scale": 0, "nullable": False,
     "description": "物料編號", "business_aliases": ["物料", "料號"], "is_pk": True, "is_fk": True, "relation_table": "MM_MARA", "relation_field": "MATNR"},
    {"_key": "MM_MCHB_WERKS", "table_id": "MM_MCHB", "field_id": "WERKS", "field_name": "WERKS", "field_type": "VARCHAR", "length": 4, "scale": 0, "nullable": False,
     "description": "工廠", "business_aliases": ["工廠"], "is_pk": True, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MCHB_LGORT", "table_id": "MM_MCHB", "field_id": "LGORT", "field_name": "LGORT", "field_type": "VARCHAR", "length": 4, "scale": 0, "nullable": False,
     "description": "儲存地點", "business_aliases": ["倉庫", "倉別"], "is_pk": True, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MCHB_CHARG", "table_id": "MM_MCHB", "field_id": "CHARG", "field_name": "CHARG", "field_type": "VARCHAR", "length": 10, "scale": 0, "nullable": False,
     "description": "批次號碼", "business_aliases": ["批號", "Batch", "Lot"], "is_pk": True, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MCHB_CLABS", "table_id": "MM_MCHB", "field_id": "CLABS", "field_name": "CLABS", "field_type": "DECIMAL", "length": 13, "scale": 3, "nullable": False,
     "description": "批次可用庫存", "business_aliases": ["批次庫存", "Batch Stock"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MCHB_CINSM", "table_id": "MM_MCHB", "field_id": "CINSM", "field_name": "CINSM", "field_type": "DECIMAL", "length": 13, "scale": 3, "nullable": False,
     "description": "批次品質檢驗庫存", "business_aliases": ["批次QI"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MCHB_CSPEM", "table_id": "MM_MCHB", "field_id": "CSPEM", "field_name": "CSPEM", "field_type": "DECIMAL", "length": 13, "scale": 3, "nullable": False,
     "description": "批次凍結庫存", "business_aliases": ["批次鎖定"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MCHB_HSDAT", "table_id": "MM_MCHB", "field_id": "HSDAT", "field_name": "HSDAT", "field_type": "DATE", "length": 8, "scale": 0, "nullable": True,
     "description": "製造日期", "business_aliases": ["生產日期"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MCHB_VFDAT", "table_id": "MM_MCHB", "field_id": "VFDAT", "field_name": "VFDAT", "field_type": "DATE", "length": 8, "scale": 0, "nullable": True,
     "description": "有效期限", "business_aliases": ["到期日", "Shelf Life"], "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
]

for f in new_fields:
    f["status"] = "enabled"
    f["created_at"] = TS
    f["updated_at"] = TS

bulk_upsert("da_field_info", new_fields)
print(f"  ✓ {len(new_fields)} fields upserted")

# ==================== 4. NEW RELATIONS ====================
print("\n4. Seeding new relations...")

new_relations = [
    # MKPF ↔ MSEG (表頭-行項目)
    {
        "_key": "REL_MM_MKPF_MSEG_MBLNR",
        "relation_id": "REL_MM_MKPF_MSEG_MBLNR",
        "left_table": "MM_MKPF", "left_field": "MBLNR",
        "right_table": "MM_MSEG", "right_field": "MBLNR",
        "join_type": "INNER", "cardinality": "1:N", "confidence": 1.0
    },
    # MARD → MARA (庫存-物料主檔)
    {
        "_key": "REL_MM_MARD_MARA_MATNR",
        "relation_id": "REL_MM_MARD_MARA_MATNR",
        "left_table": "MM_MARD", "left_field": "MATNR",
        "right_table": "MM_MARA", "right_field": "MATNR",
        "join_type": "INNER", "cardinality": "N:1", "confidence": 1.0
    },
    # MCHB → MARA (批次庫存-物料主檔)
    {
        "_key": "REL_MM_MCHB_MARA_MATNR",
        "relation_id": "REL_MM_MCHB_MARA_MATNR",
        "left_table": "MM_MCHB", "left_field": "MATNR",
        "right_table": "MM_MARA", "right_field": "MATNR",
        "join_type": "INNER", "cardinality": "N:1", "confidence": 1.0
    },
    # MCHB → MARD (批次庫存-倉庫庫存, 同工廠+倉庫)
    {
        "_key": "REL_MM_MCHB_MARD_MATNR_WERKS_LGORT",
        "relation_id": "REL_MM_MCHB_MARD_MATNR_WERKS_LGORT",
        "left_table": "MM_MCHB", "left_field": "MATNR",
        "right_table": "MM_MARD", "right_field": "MATNR",
        "join_type": "INNER", "cardinality": "N:1", "confidence": 0.95
    },
    # MSEG → MKPF (行項目-表頭, reverse lookup)
    {
        "_key": "REL_MM_MSEG_MKPF_MBLNR",
        "relation_id": "REL_MM_MSEG_MKPF_MBLNR",
        "left_table": "MM_MSEG", "left_field": "MBLNR",
        "right_table": "MM_MKPF", "right_field": "MBLNR",
        "join_type": "LEFT", "cardinality": "N:1", "confidence": 1.0
    },
]

for r in new_relations:
    r["status"] = "enabled"
    r["created_at"] = TS
    r["updated_at"] = TS

bulk_upsert("da_table_relation", new_relations)
print(f"  ✓ {len(new_relations)} relations upserted")

# ==================== 5. VERIFY ====================
print("\n5. Verification...")
result = aql_exec("FOR t IN da_table_info FILTER t.module == 'MM' RETURN t.table_name")
mm_tables = result.get("result", [])
print(f"  MM tables ({len(mm_tables)}): {', '.join(sorted(mm_tables))}")

result = aql_exec("RETURN LENGTH(da_table_info)")
total_tables = result.get("result", [0])[0]
print(f"  Total tables: {total_tables}")

result = aql_exec("RETURN LENGTH(da_table_relation)")
total_rels = result.get("result", [0])[0]
print(f"  Total relations: {total_rels}")

result = aql_exec("RETURN LENGTH(da_field_info)")
total_fields = result.get("result", [0])[0]
print(f"  Total fields: {total_fields}")

print("\n✅ Inventory tables seeding complete!")
