#!/usr/bin/env python3
"""
@file        seed_schema.py
@description ArangoDB Schema 初始化 — da_table_info, da_field_info, da_table_relation
@lastUpdate  2026-03-23 23:40:00
@author      Daniel Chung
@version     1.1.0
"""
import subprocess
import json

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = "root:abc_desktop_2026"

def curl_post_doc(collection: str, docs: list) -> dict:
    """Bulk insert/overwrite via ArangoDB document API."""
    payload = json.dumps(docs)
    r = subprocess.run([
        "curl", "-s", "-u", AUTH,
        f"{ARANGO_URL}/_db/{DB}/_api/document/{collection}?overwriteMode=replace",
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", payload
    ], capture_output=True, text=True)
    return json.loads(r.stdout)

def create_index(collection: str, idx_spec: dict) -> dict:
    r = subprocess.run([
        "curl", "-s", "-u", AUTH,
        f"{ARANGO_URL}/_db/{DB}/_api/index/{collection}",
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(idx_spec)
    ], capture_output=True, text=True)
    return json.loads(r.stdout)

def insert_batch(collection: str, docs: list) -> None:
    result = curl_post_doc(collection, docs)
    if isinstance(result, list):
        for i, r in enumerate(result):
            if r.get("error"):
                print(f"  ERROR {docs[i]['_key']}: {r.get('errorMessage', r)}")
            else:
                pass
    elif result.get("error"):
        print(f"  Batch error: {result}")

# ==================== TABLE INFO ====================
tables = [
    {"_key": "MM_MARA",   "table_id": "MM_MARA",   "table_name": "MARA",   "module": "MM", "description": "物料主檔 (Material Master)",     "s3_path": "s3://sap/mm/mara/",  "primary_keys": ["MATNR"], "partition_keys": [],                "record_count": 500},
    {"_key": "MM_LFA1",   "table_id": "MM_LFA1",   "table_name": "LFA1",   "module": "MM", "description": "供應商主檔 (Vendor Master)",        "s3_path": "s3://sap/mm/lfa1/",  "primary_keys": ["LIFNR"], "partition_keys": [],                "record_count": 120},
    {"_key": "MM_EKKO",   "table_id": "MM_EKKO",   "table_name": "EKKO",   "module": "MM", "description": "採購文件表頭 (PO Header)",          "s3_path": "s3://sap/mm/ekko/",  "primary_keys": ["EBELN"], "partition_keys": ["AEDAT_YEAR","AEDAT_MONTH"], "record_count": 2000},
    {"_key": "MM_EKPO",   "table_id": "MM_EKPO",   "table_name": "EKPO",   "module": "MM", "description": "採購文件行項目 (PO Item)",          "s3_path": "s3://sap/mm/ekpo/",  "primary_keys": ["EBELN","EBELP"], "partition_keys": ["AEDAT_YEAR","AEDAT_MONTH"], "record_count": 10999},
    {"_key": "MM_MSEG",   "table_id": "MM_MSEG",   "table_name": "MSEG",   "module": "MM", "description": "物料憑證行項目 (Material Document)",  "s3_path": "s3://sap/mm/mseg/",  "primary_keys": ["MBLNR","MJAHR","ZEILE"], "partition_keys": ["BUDAT_YEAR","BUDAT_MONTH"], "record_count": 8877},
    {"_key": "SD_VBAK",   "table_id": "SD_VBAK",   "table_name": "VBAK",   "module": "SD", "description": "銷售文件表頭 (Sales Order Header)",   "s3_path": "s3://sap/sd/vbak/",  "primary_keys": ["VBELN"], "partition_keys": ["ERDAT_YEAR","ERDAT_MONTH"], "record_count": 1800},
    {"_key": "SD_VBAP",   "table_id": "SD_VBAP",   "table_name": "VBAP",   "module": "SD", "description": "銷售文件行項目 (Sales Order Item)",   "s3_path": "s3://sap/sd/vbap/",  "primary_keys": ["VBELN","POSNR"], "partition_keys": ["ERDAT_YEAR","ERDAT_MONTH"], "record_count": 7135},
    {"_key": "SD_LIKP",   "table_id": "SD_LIKP",   "table_name": "LIKP",   "module": "SD", "description": "交貨文件表頭 (Delivery Header)",      "s3_path": "s3://sap/sd/likp/",  "primary_keys": ["VBELN"], "partition_keys": ["WADAT_YEAR","WADAT_MONTH"], "record_count": 600},
    {"_key": "SD_LIPS",   "table_id": "SD_LIPS",   "table_name": "LIPS",   "module": "SD", "description": "交貨文件行項目 (Delivery Item)",      "s3_path": "s3://sap/sd/lips/",  "primary_keys": ["VBELN","POSNR"], "partition_keys": ["WADAT_YEAR","WADAT_MONTH"], "record_count": 2081},
    {"_key": "SD_RBKD",   "table_id": "SD_RBKD",   "table_name": "RBKD",   "module": "SD", "description": "發票文件表頭 (Invoice Document)",      "s3_path": "s3://sap/sd/rbkd/",  "primary_keys": ["BELNR","GJAHR"], "partition_keys": ["BUDAT_YEAR","BUDAT_MONTH"], "record_count": 400},
]

ts = "2026-03-22T00:00:00Z"
print("Seeding da_table_info...")
for t in tables:
    t["status"] = "enabled"
    t["version"] = 1
    t["created_at"] = ts
    t["updated_at"] = ts
    t["updated_by"] = "system"
insert_batch("da_table_info", tables)

# ==================== FIELD INFO ====================
fields = [
    # MARA
    {"_key": "MM_MARA_MATNR",   "table_id": "MM_MARA", "field_id": "MATNR",   "field_name": "MATNR",   "field_type": "VARCHAR",   "length": 18, "scale": 0, "nullable": False, "description": "物料編號",                           "business_aliases": ["物料","料號","品號"],       "is_pk": True,  "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARA_MAKTX",   "table_id": "MM_MARA", "field_id": "MAKTX",   "field_name": "MAKTX",   "field_type": "VARCHAR",   "length": 40, "scale": 0, "nullable": True,  "description": "物料描述",                           "business_aliases": ["品名","說明","描述"],       "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARA_MTART",   "table_id": "MM_MARA", "field_id": "MTART",   "field_name": "MTART",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": False, "description": "物料類型",                           "business_aliases": ["類型"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARA_MATKL",   "table_id": "MM_MARA", "field_id": "MATKL",   "field_name": "MATKL",   "field_type": "VARCHAR",   "length": 9,  "scale": 0, "nullable": True,  "description": "物料群組",                           "business_aliases": ["群組"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARA_MEINS",   "table_id": "MM_MARA", "field_id": "MEINS",   "field_name": "MEINS",   "field_type": "VARCHAR",   "length": 3,  "scale": 0, "nullable": False, "description": "基本單位",                           "business_aliases": ["單位"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARA_BRGEW",   "table_id": "MM_MARA", "field_id": "BRGEW",   "field_name": "BRGEW",   "field_type": "DECIMAL",   "length": 13, "scale": 3, "nullable": True,  "description": "毛重",                               "business_aliases": ["重量"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARA_GEWEI",   "table_id": "MM_MARA", "field_id": "GEWEI",   "field_name": "GEWEI",   "field_type": "VARCHAR",   "length": 3,  "scale": 0, "nullable": True,  "description": "重量單位",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARA_MATNR2",  "table_id": "MM_MARA", "field_id": "MATNR2",  "field_name": "MATNR2",  "field_type": "VARCHAR",   "length": 18, "scale": 0, "nullable": True,  "description": "替代物料",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARA_ERSDA",   "table_id": "MM_MARA", "field_id": "ERSDA",   "field_name": "ERSDA",   "field_type": "DATE",      "length": 8,  "scale": 0, "nullable": False, "description": "建立日期",                           "business_aliases": ["建立日","建立日期"],         "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARA_ERNAM",   "table_id": "MM_MARA", "field_id": "ERNAM",   "field_name": "ERNAM",   "field_type": "VARCHAR",   "length": 12, "scale": 0, "nullable": False, "description": "建立者",                             "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARA_MBRSH",    "table_id": "MM_MARA", "field_id": "MBRSH",   "field_name": "MBRSH",   "field_type": "VARCHAR",   "length": 1,  "scale": 0, "nullable": False, "description": "產業領域",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARA_BISMT",   "table_id": "MM_MARA", "field_id": "BISMT",   "field_name": "BISMT",   "field_type": "VARCHAR",   "length": 18, "scale": 0, "nullable": True,  "description": "舊物料編號",                        "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MARA_PSTAT",   "table_id": "MM_MARA", "field_id": "PSTAT",   "field_name": "PSTAT",   "field_type": "VARCHAR",   "length": 20, "scale": 0, "nullable": True,  "description": "維護狀態",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    # LFA1
    {"_key": "MM_LFA1_LIFNR",   "table_id": "MM_LFA1", "field_id": "LIFNR",   "field_name": "LIFNR",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "供應商帳號",                         "business_aliases": ["供應商","Vendor"],           "is_pk": True,  "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_LFA1_NAME1",   "table_id": "MM_LFA1", "field_id": "NAME1",   "field_name": "NAME1",   "field_type": "VARCHAR",   "length": 30, "scale": 0, "nullable": False, "description": "供應商名稱",                         "business_aliases": ["名稱","供應商名"],           "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_LFA1_NAME2",   "table_id": "MM_LFA1", "field_id": "NAME2",   "field_name": "NAME2",   "field_type": "VARCHAR",   "length": 30, "scale": 0, "nullable": True,  "description": "供應商名稱2",                        "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_LFA1_ORT01",   "table_id": "MM_LFA1", "field_id": "ORT01",   "field_name": "ORT01",   "field_type": "VARCHAR",   "length": 35, "scale": 0, "nullable": True,  "description": "城市",                               "business_aliases": ["城市","City"],               "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_LFA1_STRAS",   "table_id": "MM_LFA1", "field_id": "STRAS",   "field_name": "STRAS",   "field_type": "VARCHAR",   "length": 35, "scale": 0, "nullable": True,  "description": "街道/地址",                          "business_aliases": ["地址","Address"],            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_LFA1_LAND1",   "table_id": "MM_LFA1", "field_id": "LAND1",   "field_name": "LAND1",   "field_type": "VARCHAR",   "length": 3,  "scale": 0, "nullable": False, "description": "國家代碼",                           "business_aliases": ["國家"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_LFA1_REGIO",   "table_id": "MM_LFA1", "field_id": "REGIO",   "field_name": "REGIO",   "field_type": "VARCHAR",   "length": 3,  "scale": 0, "nullable": True,  "description": "地區/省份",                         "business_aliases": ["省份","地區"],               "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_LFA1_STCD1",   "table_id": "MM_LFA1", "field_id": "STCD1",   "field_name": "STCD1",   "field_type": "VARCHAR",   "length": 16, "scale": 0, "nullable": True,  "description": "統一編號",                           "business_aliases": ["統編","稅號"],               "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_LFA1_STCD2",   "table_id": "MM_LFA1", "field_id": "STCD2",   "field_name": "STCD2",   "field_type": "VARCHAR",   "length": 18, "scale": 0, "nullable": True,  "description": "稅籍編號",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_LFA1_KTOKK",   "table_id": "MM_LFA1", "field_id": "KTOKK",   "field_name": "KTOKK",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": False, "description": "帳戶組",                             "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_LFA1_ERDAT",   "table_id": "MM_LFA1", "field_id": "ERDAT",   "field_name": "ERDAT",   "field_type": "DATE",      "length": 8,  "scale": 0, "nullable": False, "description": "建立日期",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_LFA1_ZTERM",   "table_id": "MM_LFA1", "field_id": "ZTERM",   "field_name": "ZTERM",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": True,  "description": "付款條件",                           "business_aliases": ["付款"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    # EKKO
    {"_key": "MM_EKKO_EBELN",   "table_id": "MM_EKKO", "field_id": "EBELN",   "field_name": "EBELN",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "採購單號",                           "business_aliases": ["採購單","PO","訂單號"],       "is_pk": True,  "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKKO_BUKRS",   "table_id": "MM_EKKO", "field_id": "BUKRS",   "field_name": "BUKRS",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": False, "description": "公司代碼",                           "business_aliases": ["公司"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKKO_BSTYP",   "table_id": "MM_EKKO", "field_id": "BSTYP",   "field_name": "BSTYP",   "field_type": "VARCHAR",   "length": 1,  "scale": 0, "nullable": False, "description": "文件類型",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKKO_LIFNR",   "table_id": "MM_EKKO", "field_id": "LIFNR",   "field_name": "LIFNR",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "供應商代碼",                         "business_aliases": ["供應商"],                   "is_pk": False, "is_fk": True,  "relation_table": "MM_LFA1", "relation_field": "LIFNR"},
    {"_key": "MM_EKKO_AEDAT",   "table_id": "MM_EKKO", "field_id": "AEDAT",   "field_name": "AEDAT",   "field_type": "DATE",      "length": 8,  "scale": 0, "nullable": False, "description": "最後變更日期",                       "business_aliases": ["日期","變更日"],             "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKKO_ERDAT",   "table_id": "MM_EKKO", "field_id": "ERDAT",   "field_name": "ERDAT",   "field_type": "DATE",      "length": 8,  "scale": 0, "nullable": False, "description": "建立日期",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKKO_ERNAM",   "table_id": "MM_EKKO", "field_id": "ERNAM",   "field_name": "ERNAM",   "field_type": "VARCHAR",   "length": 12, "scale": 0, "nullable": False, "description": "建立者",                             "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKKO_KNUMV",   "table_id": "MM_EKKO", "field_id": "KNUMV",   "field_name": "KNUMV",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "文件條件號",                        "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKKO_STATP",   "table_id": "MM_EKKO", "field_id": "STATP",   "field_name": "STATP",   "field_type": "VARCHAR",   "length": 1,  "scale": 0, "nullable": False, "description": "文件狀態",                           "business_aliases": ["狀態"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKKO_WAERS",   "table_id": "MM_EKKO", "field_id": "WAERS",   "field_name": "WAERS",   "field_type": "VARCHAR",   "length": 5,  "scale": 0, "nullable": False, "description": "貨幣",                               "business_aliases": ["幣別","幣種"],               "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKKO_WKTNR",   "table_id": "MM_EKKO", "field_id": "WKTNR",   "field_name": "WKTNR",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": True,  "description": "契約號碼",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKKO_KONNR",   "table_id": "MM_EKKO", "field_id": "KONNR",   "field_name": "KONNR",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": True,  "description": "報價單號",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    # EKPO
    {"_key": "MM_EKPO_EBELN",   "table_id": "MM_EKPO", "field_id": "EBELN",   "field_name": "EBELN",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "採購單號",                           "business_aliases": ["採購單","PO"],               "is_pk": True,  "is_fk": True,  "relation_table": "MM_EKKO", "relation_field": "EBELN"},
    {"_key": "MM_EKPO_EBELP",   "table_id": "MM_EKPO", "field_id": "EBELP",   "field_name": "EBELP",   "field_type": "VARCHAR",   "length": 5,  "scale": 0, "nullable": False, "description": "採購單行號",                        "business_aliases": ["行項目","行號","Line"],       "is_pk": True,  "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKPO_MATNR",   "table_id": "MM_EKPO", "field_id": "MATNR",   "field_name": "MATNR",   "field_type": "VARCHAR",   "length": 18, "scale": 0, "nullable": True,  "description": "物料編號",                           "business_aliases": ["物料","料號"],               "is_pk": False, "is_fk": True,  "relation_table": "MM_MARA", "relation_field": "MATNR"},
    {"_key": "MM_EKPO_TXZ01",   "table_id": "MM_EKPO", "field_id": "TXZ01",   "field_name": "TXZ01",   "field_type": "VARCHAR",   "length": 40, "scale": 0, "nullable": False, "description": "短文本",                             "business_aliases": ["品名","說明"],               "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKPO_MENGE",   "table_id": "MM_EKPO", "field_id": "MENGE",   "field_name": "MENGE",   "field_type": "DECIMAL",   "length": 13, "scale": 3, "nullable": False, "description": "採購數量",                           "business_aliases": ["數量","Qty"],                "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKPO_MEINS",   "table_id": "MM_EKPO", "field_id": "MEINS",   "field_name": "MEINS",   "field_type": "VARCHAR",   "length": 3,  "scale": 0, "nullable": False, "description": "訂購單位",                           "business_aliases": ["單位"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKPO_NETPR",   "table_id": "MM_EKPO", "field_id": "NETPR",   "field_name": "NETPR",   "field_type": "DECIMAL",   "length": 15, "scale": 2, "nullable": False, "description": "淨價",                               "business_aliases": ["單價","價格","Price"],        "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKPO_PEINH",   "table_id": "MM_EKPO", "field_id": "PEINH",   "field_name": "PEINH",   "field_type": "DECIMAL",   "length": 5,  "scale": 0, "nullable": False, "description": "價格單位",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKPO_WERKS",   "table_id": "MM_EKPO", "field_id": "WERKS",   "field_name": "WERKS",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": False, "description": "工廠",                               "business_aliases": ["工廠"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKPO_LGORT",   "table_id": "MM_EKPO", "field_id": "LGORT",   "field_name": "LGORT",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": True,  "description": "儲存地點",                           "business_aliases": ["倉庫","倉別"],               "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKPO_BANFN",   "table_id": "MM_EKPO", "field_id": "BANFN",   "field_name": "BANFN",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": True,  "description": "請購單號",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKPO_BNFPO",   "table_id": "MM_EKPO", "field_id": "BNFPO",   "field_name": "BNFPO",   "field_type": "VARCHAR",   "length": 5,  "scale": 0, "nullable": True,  "description": "請購單行號",                        "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_EKPO_ELIFB",   "table_id": "MM_EKPO", "field_id": "ELIFB",   "field_name": "ELIFB",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": True,  "description": "供應商帳號",                         "business_aliases": [],                            "is_pk": False, "is_fk": True,  "relation_table": "MM_LFA1", "relation_field": "LIFNR"},
    {"_key": "MM_EKPO_RETAM",   "table_id": "MM_EKPO", "field_id": "RETAM",   "field_name": "RETAM",   "field_type": "DECIMAL",   "length": 13, "scale": 3, "nullable": False, "description": "退貨數量",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    # MSEG
    {"_key": "MM_MSEG_MBLNR",   "table_id": "MM_MSEG", "field_id": "MBLNR",   "field_name": "MBLNR",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "物料憑證號",                         "business_aliases": ["憑證號","M-doc"],            "is_pk": True,  "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_MJAHR",   "table_id": "MM_MSEG", "field_id": "MJAHR",   "field_name": "MJAHR",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": False, "description": "憑證年份",                           "business_aliases": [],                            "is_pk": True,  "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_ZEILE",   "table_id": "MM_MSEG", "field_id": "ZEILE",   "field_name": "ZEILE",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": False, "description": "行項目",                             "business_aliases": ["行號"],                     "is_pk": True,  "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_BUKRS",   "table_id": "MM_MSEG", "field_id": "BUKRS",   "field_name": "BUKRS",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": False, "description": "公司代碼",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_BUDAT",   "table_id": "MM_MSEG", "field_id": "BUDAT",   "field_name": "BUDAT",   "field_type": "DATE",      "length": 8,  "scale": 0, "nullable": False, "description": "憑證日期",                           "business_aliases": ["日期"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_MATNR",   "table_id": "MM_MSEG", "field_id": "MATNR",   "field_name": "MATNR",   "field_type": "VARCHAR",   "length": 18, "scale": 0, "nullable": True,  "description": "物料編號",                           "business_aliases": [],                            "is_pk": False, "is_fk": True,  "relation_table": "MM_MARA", "relation_field": "MATNR"},
    {"_key": "MM_MSEG_WERKS",   "table_id": "MM_MSEG", "field_id": "WERKS",   "field_name": "WERKS",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": False, "description": "工廠",                               "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_LGORT",   "table_id": "MM_MSEG", "field_id": "LGORT",   "field_name": "LGORT",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": True,  "description": "儲存地點",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_BWART",   "table_id": "MM_MSEG", "field_id": "BWART",   "field_name": "BWART",   "field_type": "VARCHAR",   "length": 3,  "scale": 0, "nullable": False, "description": "移動類型",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_DMBTR",   "table_id": "MM_MSEG", "field_id": "DMBTR",   "field_name": "DMBTR",   "field_type": "DECIMAL",   "length": 13, "scale": 2, "nullable": False, "description": "金額(本幣)",                         "business_aliases": ["金額"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_MENGE",   "table_id": "MM_MSEG", "field_id": "MENGE",   "field_name": "MENGE",   "field_type": "DECIMAL",   "length": 13, "scale": 3, "nullable": False, "description": "數量",                               "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_MEINS",   "table_id": "MM_MSEG", "field_id": "MEINS",   "field_name": "MEINS",   "field_type": "VARCHAR",   "length": 3,  "scale": 0, "nullable": True,  "description": "基本單位",                           "business_aliases": ["單位","UoM"],                "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_WAERS",   "table_id": "MM_MSEG", "field_id": "WAERS",   "field_name": "WAERS",   "field_type": "VARCHAR",   "length": 5,  "scale": 0, "nullable": True,  "description": "貨幣",                               "business_aliases": ["幣別"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_KOSTL",   "table_id": "MM_MSEG", "field_id": "KOSTL",   "field_name": "KOSTL",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": True,  "description": "成本中心",                           "business_aliases": ["成本中心","Cost Center"],    "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_UMLGO",   "table_id": "MM_MSEG", "field_id": "UMLGO",   "field_name": "UMLGO",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": True,  "description": "收貨儲存地點",                       "business_aliases": ["收貨倉庫","目的倉"],         "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "MM_MSEG_LIFNR",   "table_id": "MM_MSEG", "field_id": "LIFNR",   "field_name": "LIFNR",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": True,  "description": "供應商帳號",                         "business_aliases": ["供應商"],                   "is_pk": False, "is_fk": True,  "relation_table": "MM_LFA1", "relation_field": "LIFNR"},
    {"_key": "MM_MSEG_EBELN",   "table_id": "MM_MSEG", "field_id": "EBELN",   "field_name": "EBELN",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": True,  "description": "採購單號",                           "business_aliases": [],                            "is_pk": False, "is_fk": True,  "relation_table": "MM_EKKO", "relation_field": "EBELN"},
    {"_key": "MM_MSEG_EBELP",   "table_id": "MM_MSEG", "field_id": "EBELP",   "field_name": "EBELP",   "field_type": "VARCHAR",   "length": 5,  "scale": 0, "nullable": True,  "description": "採購單行號",                        "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    # VBAK
    {"_key": "SD_VBAK_VBELN",   "table_id": "SD_VBAK", "field_id": "VBELN",   "field_name": "VBELN",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "銷售單號",                           "business_aliases": ["銷售單","SO"],               "is_pk": True,  "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAK_KUNNR",   "table_id": "SD_VBAK", "field_id": "KUNNR",   "field_name": "KUNNR",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "客戶代碼",                           "business_aliases": ["客戶","Customer"],          "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAK_ERDAT",   "table_id": "SD_VBAK", "field_id": "ERDAT",   "field_name": "ERDAT",   "field_type": "DATE",      "length": 8,  "scale": 0, "nullable": False, "description": "建立日期",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAK_ERNAM",   "table_id": "SD_VBAK", "field_id": "ERNAM",   "field_name": "ERNAM",   "field_type": "VARCHAR",   "length": 12, "scale": 0, "nullable": False, "description": "建立者",                             "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAK_AUART",   "table_id": "SD_VBAK", "field_id": "AUART",   "field_name": "AUART",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": False, "description": "訂單類型",                           "business_aliases": ["類型"],                     "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAK_VBTYP",   "table_id": "SD_VBAK", "field_id": "VBTYP",   "field_name": "VBTYP",   "field_type": "VARCHAR",   "length": 1,  "scale": 0, "nullable": False, "description": "單據類別",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAK_NETWR",   "table_id": "SD_VBAK", "field_id": "NETWR",   "field_name": "NETWR",   "field_type": "DECIMAL",   "length": 15, "scale": 2, "nullable": False, "description": "淨值",                               "business_aliases": ["金額","總金額"],             "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAK_WAERK",   "table_id": "SD_VBAK", "field_id": "WAERK",   "field_name": "WAERK",   "field_type": "VARCHAR",   "length": 5,  "scale": 0, "nullable": False, "description": "幣別",                               "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAK_AUDAT",   "table_id": "SD_VBAK", "field_id": "AUDAT",   "field_name": "AUDAT",   "field_type": "DATE",      "length": 8,  "scale": 0, "nullable": False, "description": "文件日期",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAK_STAWN",   "table_id": "SD_VBAK", "field_id": "STAWN",   "field_name": "STAWN",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": True,  "description": "海關稅號",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    # VBAP
    {"_key": "SD_VBAP_VBELN",   "table_id": "SD_VBAP", "field_id": "VBELN",   "field_name": "VBELN",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "銷售單號",                           "business_aliases": [],                            "is_pk": True,  "is_fk": True,  "relation_table": "SD_VBAK", "relation_field": "VBELN"},
    {"_key": "SD_VBAP_POSNR",   "table_id": "SD_VBAP", "field_id": "POSNR",   "field_name": "POSNR",   "field_type": "VARCHAR",   "length": 6,  "scale": 0, "nullable": False, "description": "行項目號",                           "business_aliases": [],                            "is_pk": True,  "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAP_MATNR",   "table_id": "SD_VBAP", "field_id": "MATNR",   "field_name": "MATNR",   "field_type": "VARCHAR",   "length": 18, "scale": 0, "nullable": True,  "description": "物料編號",                           "business_aliases": [],                            "is_pk": False, "is_fk": True,  "relation_table": "MM_MARA", "relation_field": "MATNR"},
    {"_key": "SD_VBAP_KDMAT",   "table_id": "SD_VBAP", "field_id": "KDMAT",   "field_name": "KDMAT",   "field_type": "VARCHAR",   "length": 35, "scale": 0, "nullable": True,  "description": "客戶物料",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAP_KWMENG",  "table_id": "SD_VBAP", "field_id": "KWMENG",  "field_name": "KWMENG",  "field_type": "DECIMAL",   "length": 13, "scale": 3, "nullable": False, "description": "數量",                               "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAP_VRKME",   "table_id": "SD_VBAP", "field_id": "VRKME",   "field_name": "VRKME",   "field_type": "VARCHAR",   "length": 3,  "scale": 0, "nullable": False, "description": "銷售單位",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAP_NETWR",   "table_id": "SD_VBAP", "field_id": "NETWR",   "field_name": "NETWR",   "field_type": "DECIMAL",   "length": 15, "scale": 2, "nullable": False, "description": "淨值",                               "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAP_WERKS",   "table_id": "SD_VBAP", "field_id": "WERKS",   "field_name": "WERKS",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": False, "description": "工廠",                               "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_VBAP_ERDAT",   "table_id": "SD_VBAP", "field_id": "ERDAT",   "field_name": "ERDAT",   "field_type": "DATE",      "length": 8,  "scale": 0, "nullable": False, "description": "建立日期",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    # LIKP
    {"_key": "SD_LIKP_VBELN",   "table_id": "SD_LIKP", "field_id": "VBELN",   "field_name": "VBELN",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "交貨單號",                           "business_aliases": ["交貨單","Delivery"],         "is_pk": True,  "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_LIKP_KUNNR",   "table_id": "SD_LIKP", "field_id": "KUNNR",   "field_name": "KUNNR",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "客戶代碼",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_LIKP_WADAT",   "table_id": "SD_LIKP", "field_id": "WADAT",   "field_name": "WADAT",   "field_type": "DATE",      "length": 8,  "scale": 0, "nullable": False, "description": "實際交貨日期",                       "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_LIKP_ERDAT",   "table_id": "SD_LIKP", "field_id": "ERDAT",   "field_name": "ERDAT",   "field_type": "DATE",      "length": 8,  "scale": 0, "nullable": False, "description": "建立日期",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_LIKP_LIFSP",   "table_id": "SD_LIKP", "field_id": "LIFSP",   "field_name": "LIFSP",   "field_type": "VARCHAR",   "length": 2,  "scale": 0, "nullable": True,  "description": "出貨地點",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_LIKP_VBTYP",   "table_id": "SD_LIKP", "field_id": "VBTYP",   "field_name": "VBTYP",   "field_type": "VARCHAR",   "length": 1,  "scale": 0, "nullable": False, "description": "單據類別",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_LIKP_WADAT_IST","table_id": "SD_LIKP","field_id": "WADAT_IST","field_name":"WADAT_IST","field_type":"DATE",       "length": 8,  "scale": 0, "nullable": True,  "description": "實際裝運日期",                       "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    # LIPS
    {"_key": "SD_LIPS_VBELN",   "table_id": "SD_LIPS", "field_id": "VBELN",   "field_name": "VBELN",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "交貨單號",                           "business_aliases": [],                            "is_pk": True,  "is_fk": True,  "relation_table": "SD_LIKP", "relation_field": "VBELN"},
    {"_key": "SD_LIPS_POSNR",   "table_id": "SD_LIPS", "field_id": "POSNR",   "field_name": "POSNR",   "field_type": "VARCHAR",   "length": 6,  "scale": 0, "nullable": False, "description": "行項目號",                           "business_aliases": [],                            "is_pk": True,  "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_LIPS_MATNR",   "table_id": "SD_LIPS", "field_id": "MATNR",   "field_name": "MATNR",   "field_type": "VARCHAR",   "length": 18, "scale": 0, "nullable": True,  "description": "物料編號",                           "business_aliases": [],                            "is_pk": False, "is_fk": True,  "relation_table": "MM_MARA", "relation_field": "MATNR"},
    {"_key": "SD_LIPS_LFIMG",   "table_id": "SD_LIPS", "field_id": "LFIMG",   "field_name": "LFIMG",   "field_type": "DECIMAL",   "length": 13, "scale": 3, "nullable": False, "description": "已交貨數量",                         "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_LIPS_VRKME",   "table_id": "SD_LIPS", "field_id": "VRKME",   "field_name": "VRKME",   "field_type": "VARCHAR",   "length": 3,  "scale": 0, "nullable": False, "description": "銷售單位",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_LIPS_WERKS",   "table_id": "SD_LIPS", "field_id": "WERKS",   "field_name": "WERKS",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": False, "description": "工廠",                               "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_LIPS_LGORT",   "table_id": "SD_LIPS", "field_id": "LGORT",   "field_name": "LGORT",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": True,  "description": "庫存地點",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    # RBKD
    {"_key": "SD_RBKD_BELNR",   "table_id": "SD_RBKD", "field_id": "BELNR",   "field_name": "BELNR",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "發票號碼",                           "business_aliases": ["發票","Invoice"],            "is_pk": True,  "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_RBKD_GJAHR",   "table_id": "SD_RBKD", "field_id": "GJAHR",   "field_name": "GJAHR",   "field_type": "VARCHAR",   "length": 4,  "scale": 0, "nullable": False, "description": "會計年度",                           "business_aliases": [],                            "is_pk": True,  "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_RBKD_KUNNR",   "table_id": "SD_RBKD", "field_id": "KUNNR",   "field_name": "KUNNR",   "field_type": "VARCHAR",   "length": 10, "scale": 0, "nullable": False, "description": "客戶代碼",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_RBKD_BUDAT",   "table_id": "SD_RBKD", "field_id": "BUDAT",   "field_name": "BUDAT",   "field_type": "DATE",      "length": 8,  "scale": 0, "nullable": False, "description": "發票日期",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_RBKD_WRBTR",   "table_id": "SD_RBKD", "field_id": "WRBTR",   "field_name": "WRBTR",   "field_type": "DECIMAL",   "length": 13, "scale": 2, "nullable": False, "description": "發票金額",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_RBKD_WMWST",   "table_id": "SD_RBKD", "field_id": "WMWST",   "field_name": "WMWST",   "field_type": "DECIMAL",   "length": 13, "scale": 2, "nullable": False, "description": "稅額",                               "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_RBKD_ZUONR",   "table_id": "SD_RBKD", "field_id": "ZUONR",   "field_name": "ZUONR",   "field_type": "VARCHAR",   "length": 18, "scale": 0, "nullable": True,  "description": "分配號碼",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
    {"_key": "SD_RBKD_SGTXT",   "table_id": "SD_RBKD", "field_id": "SGTXT",   "field_name": "SGTXT",   "field_type": "VARCHAR",   "length": 50, "scale": 0, "nullable": True,  "description": "說明文字",                           "business_aliases": [],                            "is_pk": False, "is_fk": False, "relation_table": None, "relation_field": None},
]

print("Seeding da_field_info...")
for f in fields:
    f["status"] = "enabled"
    f["created_at"] = ts
    f["updated_at"] = ts
insert_batch("da_field_info", fields)

# ==================== TABLE RELATIONS ====================
relations = [
    {"_key": "REL_MM_EKKO_EKPO_EBELN",  "relation_id": "REL_MM_EKKO_EKPO_EBELN",  "left_table": "MM_EKKO", "left_field": "EBELN", "right_table": "MM_EKPO", "right_field": "EBELN", "join_type": "INNER", "cardinality": "1:N", "confidence": 1.0},
    {"_key": "REL_MM_EKPO_MARA_MATNR",  "relation_id": "REL_MM_EKPO_MARA_MATNR",  "left_table": "MM_EKPO", "left_field": "MATNR", "right_table": "MM_MARA", "right_field": "MATNR", "join_type": "LEFT",  "cardinality": "N:1", "confidence": 0.95},
    {"_key": "REL_MM_EKKO_LFA1_LIFNR",  "relation_id": "REL_MM_EKKO_LFA1_LIFNR",  "left_table": "MM_EKKO", "left_field": "LIFNR", "right_table": "MM_LFA1", "right_field": "LIFNR", "join_type": "LEFT",  "cardinality": "N:1", "confidence": 1.0},
    {"_key": "REL_MM_MSEG_EKKO_EBELN",  "relation_id": "REL_MM_MSEG_EKKO_EBELN",  "left_table": "MM_MSEG", "left_field": "EBELN", "right_table": "MM_EKKO", "right_field": "EBELN", "join_type": "LEFT",  "cardinality": "1:N", "confidence": 0.9},
    {"_key": "REL_MM_MSEG_MARA_MATNR",  "relation_id": "REL_MM_MSEG_MARA_MATNR",  "left_table": "MM_MSEG", "left_field": "MATNR", "right_table": "MM_MARA", "right_field": "MATNR", "join_type": "LEFT",  "cardinality": "N:1", "confidence": 0.95},
    {"_key": "REL_SD_VBAK_VBAP_VBELN",  "relation_id": "REL_SD_VBAK_VBAP_VBELN",  "left_table": "SD_VBAK", "left_field": "VBELN", "right_table": "SD_VBAP", "right_field": "VBELN", "join_type": "INNER", "cardinality": "1:N", "confidence": 1.0},
    {"_key": "REL_SD_VBAP_MARA_MATNR",  "relation_id": "REL_SD_VBAP_MARA_MATNR",  "left_table": "SD_VBAP", "left_field": "MATNR", "right_table": "MM_MARA", "right_field": "MATNR", "join_type": "LEFT",  "cardinality": "N:1", "confidence": 0.9},
    {"_key": "REL_SD_LIKP_LIPS_VBELN",  "relation_id": "REL_SD_LIKP_LIPS_VBELN",  "left_table": "SD_LIKP", "left_field": "VBELN", "right_table": "SD_LIPS", "right_field": "VBELN", "join_type": "INNER", "cardinality": "1:N", "confidence": 1.0},
    {"_key": "REL_SD_LIPS_MARA_MATNR",  "relation_id": "REL_SD_LIPS_MARA_MATNR",  "left_table": "SD_LIPS", "left_field": "MATNR", "right_table": "MM_MARA", "right_field": "MATNR", "join_type": "LEFT",  "cardinality": "N:1", "confidence": 0.9},
]

print("Seeding da_table_relation...")
for r in relations:
    r["status"] = "enabled"
    r["created_at"] = ts
    r["updated_at"] = ts
insert_batch("da_table_relation", relations)

# Create indexes
print("\nCreating indexes...")
indexes = [
    ("da_table_info", [{"type": "persistent", "fields": ["table_id"], "unique": True}]),
    ("da_table_info", [{"type": "persistent", "fields": ["module", "status"]}]),
    ("da_field_info", [{"type": "persistent", "fields": ["table_id", "field_id"], "unique": True}]),
    ("da_field_info", [{"type": "persistent", "fields": ["field_name"]}]),
    ("da_table_relation", [{"type": "persistent", "fields": ["left_table", "right_table"]}]),
    ("da_table_relation", [{"type": "persistent", "fields": ["left_table", "left_field", "right_table", "right_field"], "unique": True}]),
]
for coll, idx_list in indexes:
    for idx in idx_list:
        r = subprocess.run([
            "curl", "-s", "-u", AUTH,
            f"{ARANGO_URL}/_db/{DB}/_api/index/{coll}",
            "-X", "POST", "-H", "Content-Type: application/json",
            "-d", json.dumps(idx)
        ], capture_output=True, text=True)
        d = json.loads(r.stdout)
        if d.get("error", False) and "duplicate" not in d.get("errorMessage","").lower():
            print(f"  Index may exist or error: {d.get('errorMessage', d)}")
        else:
            print(f"  ✓ Index on {coll}: {idx['fields']}")

print("\n✅ Schema seeding complete!")
print(f"  Tables: {len(tables)}")
print(f"  Fields: {len(fields)}")
print(f"  Relations: {len(relations)}")
