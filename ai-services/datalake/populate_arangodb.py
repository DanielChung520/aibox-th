#!/usr/bin/env python3
"""
@file        populate_arangodb.py
@description ArangoDB 資料填充 — 11 張 MM/SD 表，1 年模擬資料 (2025-03 ~ 2026-03)
@lastUpdate  2026-03-24 00:00:00
@author      Daniel Chung
@version     1.0.0
"""

import json
import random
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Any

from faker import Faker

fake = Faker(["zh_TW", "en_US"])
Faker.seed(42)
random.seed(42)

# ==================== ArangoDB Config ====================
ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = "root:abc_desktop_2026"

# ==================== Date Range ====================
START_DATE = datetime(2025, 3, 22)
END_DATE = datetime(2026, 3, 22)
DATE_RANGE_DAYS = (END_DATE - START_DATE).days


def rand_date() -> str:
    delta = random.randint(0, DATE_RANGE_DAYS)
    d = START_DATE + timedelta(days=delta)
    return d.strftime("%Y%m%d")


def rand_datetime() -> str:
    delta = random.randint(0, DATE_RANGE_DAYS * 24 * 60 - 1)
    d = START_DATE + timedelta(minutes=delta)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def pad(value: int, length: int = 10) -> str:
    return str(value).zfill(length)


# ==================== Reference Data ====================
MATERIAL_DESCS = [
    "不鏽鋼板材",
    "銅管組件",
    "塑膠外殼",
    "電子零件套組",
    "包裝紙箱",
    "螺絲M6x20",
    "橡膠墊圈",
    "鋁合金框架",
    "矽膠密封條",
    "碳纖維板",
    "光學鏡片",
    "陶瓷基板",
    "磁性元件",
    "散熱片",
    "印刷電路板",
    "齒輪組",
    "軸承套件",
    "氣壓缸",
    "感測器模組",
    "電源供應器",
]
MAT_TYPES = ["HALB", "ROH", "HAWA", "FERT", "HIBE", "VERP", "DIEN"]
MAT_GROUPS = [f"G{i:02d}" for i in range(1, 21)]
COUNTRIES = ["TW", "CN", "JP", "KR", "US", "DE", "TH", "VN", "MY", "SG"]
UNITS = ["PC", "KG", "BOX", "SET", "M", "L", "PCS"]
WEIGHT_UNITS = ["KG", "G", "LB", "TO"]
CURRENCIES = ["TWD", "USD", "CNY", "EUR"]
COST_CENTERS = [f"CC{i:04d}" for i in range(100, 200)]
CITIES_TW = [
    "台北市",
    "新北市",
    "桃園市",
    "台中市",
    "台南市",
    "高雄市",
    "新竹市",
    "嘉義市",
]
STREETS_TW = [
    "中正路",
    "中山路",
    "忠孝東路",
    "民生東路",
    "復興北路",
    "南京東路",
    "信義路",
    "敦化南路",
]
BUKRS = "1000"
WERKS = ["TW01", "TW02", "CN01"]
LGORT_LIST = ["TW01-S1", "TW01-S2", "TW02-S1", "CN01-S1"]
USERS = ["SAPUSER", "ADMIN", "MM001", "MM002", "MM003", "SD001", "SD002", "SD003"]
ORDER_TYPES = ["OR", "ZOR", "CR"]
DOC_STATUS = ["O", "A", "C"]
BUKRS_LIST = ["1000", "1100", "1200"]

# ==================== ArangoDB Helpers ====================


def acmd(method: str, path: str, data: Any = None, params: dict | None = None) -> Any:
    cmd = ["curl", "-s", "-u", AUTH, f"{ARANGO_URL}/_db/{DB}{path}"]
    cmd.insert(1, "-X")
    cmd.insert(2, method.upper())
    if data is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(data)]
    if params:
        for k, v in params.items():
            cmd += ["-d", f"{k}={v}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"raw": r.stdout, "stderr": r.stderr}


def create_collection(name: str) -> None:
    r = acmd("post", "/_api/collection", {"name": name})
    if r.get("error") and "duplicate" not in str(r.get("errorMessage", "")).lower():
        print(f"  Collection '{name}' may already exist: {r.get('errorMessage', r)}")
    else:
        print(f"  ✓ Collection '{name}' created")


def create_index(
    collection: str, idx_type: str, fields: list[str], unique: bool = False
) -> None:
    r = subprocess.run(
        [
            "curl",
            "-s",
            "-u",
            AUTH,
            f"{ARANGO_URL}/_db/{DB}/_api/index?collection={collection}",
            "-X",
            "POST",
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps({"type": idx_type, "fields": fields, "unique": unique}),
        ],
        capture_output=True,
        text=True,
    )
    d = json.loads(r.stdout)
    if d.get("error"):
        msg = d.get("errorMessage", "")
        if "duplicate" in msg.lower() or "already" in msg.lower():
            print(f"  ✓ Index already exists: {collection} {fields}")
        else:
            print(f"  Index warning: {msg}")
    else:
        print(f"  ✓ Index on {collection}: {fields}")


def upsert_doc(collection: str, key: str, doc: dict) -> None:
    acmd("put", f"/_api/document/{collection}/{key}", doc)


def batch_upsert(collection: str, docs: list[dict]) -> None:
    if not docs:
        return
    payload = json.dumps(docs)
    r = subprocess.run(
        [
            "curl",
            "-s",
            "-u",
            AUTH,
            f"{ARANGO_URL}/_db/{DB}/_api/document/{collection}?overwriteMode=update",
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
    result = json.loads(r.stdout)
    if isinstance(result, list):
        errors = [d for d in result if d.get("error")]
        if errors:
            print(f"  Batch errors: {errors[:3]}")
    elif result.get("error"):
        print(f"  Batch error: {result}")


def truncate_collection(name: str) -> None:
    r = subprocess.run(
        [
            "curl",
            "-s",
            "-u",
            AUTH,
            f"{ARANGO_URL}/_db/{DB}/_api/cursor",
            "-X",
            "POST",
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps({"query": f"FOR doc IN {name} REMOVE doc IN {name}"}),
        ],
        capture_output=True,
        text=True,
    )
    d = json.loads(r.stdout)
    if d.get("error"):
        print(f"  Could not truncate {name}: {d.get('errorMessage', d)}")
    else:
        print(f"  ✓ Truncated '{name}'")


# ==================== Data Generators ====================


def gen_mara(count: int) -> list[dict]:
    docs = []
    for i in range(1, count + 1):
        unit = random.choice(UNITS)
        docs.append(
            {
                "_key": pad(i),
                "MATNR": pad(i),
                "MAKTX": f"{random.choice(MATERIAL_DESCS)}-{i:04d}",
                "MTART": random.choice(MAT_TYPES),
                "MATKL": random.choice(MAT_GROUPS),
                "MEINS": unit,
                "BRGEW": round(random.uniform(0.01, 500.0), 3)
                if unit in ("PC", "SET", "BOX")
                else None,
                "GEWEI": random.choice(WEIGHT_UNITS)
                if unit in ("PC", "SET", "BOX")
                else None,
                "MATNR2": pad(random.randint(1, count))
                if random.random() > 0.7
                else None,
                "ERSDA": rand_date(),
                "ERNAM": random.choice(USERS),
                "MBRSH": random.choice(["M", "P", "C"]),
                "BISMT": pad(random.randint(1, count))
                if random.random() > 0.8
                else None,
                "PSTAT": random.choice(["KV", "KVA", "KDV", "KL"]),
            }
        )
    return docs


def gen_lfa1(count: int) -> list[dict]:
    docs = []
    for i in range(1, count + 1):
        country = random.choice(COUNTRIES)
        docs.append(
            {
                "_key": pad(i),
                "LIFNR": pad(i),
                "NAME1": fake.company(),
                "NAME2": fake.company_suffix() if random.random() > 0.5 else None,
                "ORT01": random.choice(CITIES_TW) if country == "TW" else fake.city(),
                "STRAS": random.choice(STREETS_TW) + str(random.randint(1, 200)) + "號"
                if country == "TW"
                else fake.street_address(),
                "LAND1": country,
                "REGIO": fake.administrative_unit() if random.random() > 0.3 else None,
                "STCD1": fake.ein() if random.random() > 0.4 else None,
                "STCD2": f"{random.choice(['DE', 'FR', 'IT', 'ES', 'NL', 'AT', 'BE', 'CH'])}{random.randint(1000000000, 9999999999)}"
                if random.random() > 0.6
                else None,
                "KTOKK": random.choice(["KRED", "LIEF", "PERS"]),
                "ERDAT": rand_date(),
                "ZTERM": random.choice(["K000", "K030", "K060", "K090"]),
            }
        )
    return docs


def gen_vendors_lifnrs(count: int) -> list[str]:
    return [pad(i) for i in range(1, count + 1)]


def gen_customers(count: int) -> list[dict]:
    docs = []
    for i in range(1, count + 1):
        docs.append(
            {
                "_key": pad(i),
                "KUNNR": pad(i),
                "NAME1": fake.company(),
                "LAND1": random.choice(COUNTRIES),
                "REGIO": fake.state() if random.random() > 0.5 else None,
                "STCD1": fake.ein() if random.random() > 0.5 else None,
            }
        )
    return docs


def gen_ekko(count: int, vendor_lifnrs: list[str]) -> list[dict]:
    docs = []
    for i in range(1, count + 1):
        doc_date = rand_date()
        docs.append(
            {
                "_key": pad(i),
                "EBELN": pad(i),
                "BUKRS": random.choice(BUKRS_LIST),
                "BSTYP": "F",
                "LIFNR": random.choice(vendor_lifnrs),
                "AEDAT": doc_date,
                "ERDAT": doc_date,
                "ERNAM": random.choice(USERS),
                "KNUMV": pad(i),
                "STATP": random.choice(DOC_STATUS),
                "WAERS": random.choice(CURRENCIES),
                "WKTNR": pad(random.randint(1, 500)) if random.random() > 0.7 else None,
                "KONNR": pad(random.randint(1, 1000))
                if random.random() > 0.6
                else None,
            }
        )
    return docs


def gen_ekpo(
    ekko_list: list[dict], matnr_list: list[str], vendor_lifnrs: list[str]
) -> list[dict]:
    docs = []
    for po in ekko_list:
        item_count = random.randint(3, 8)
        for j in range(1, item_count + 1):
            qty = round(random.uniform(10, 5000), 3)
            price = round(random.uniform(5, 5000), 2)
            docs.append(
                {
                    "_key": f"{po['EBELN']}-{pad(j, 5)}",
                    "EBELN": po["EBELN"],
                    "EBELP": pad(j, 5),
                    "MATNR": random.choice(matnr_list)
                    if random.random() > 0.1
                    else None,
                    "TXZ01": fake.catch_phrase(),
                    "MENGE": qty,
                    "MEINS": random.choice(UNITS),
                    "NETPR": price,
                    "PEINH": random.choice([1, 10, 100]),
                    "WERKS": random.choice(WERKS),
                    "LGORT": random.choice(LGORT_LIST),
                    "BANFN": pad(random.randint(1, 5000))
                    if random.random() > 0.5
                    else None,
                    "BNFPO": pad(random.randint(1, 999))
                    if random.random() > 0.5
                    else None,
                    "ELIFB": random.choice(vendor_lifnrs)
                    if random.random() > 0.7
                    else None,
                    "RETAM": round(qty * random.uniform(0, 0.05), 3),
                }
            )
    return docs


VGART_LIST = ["MB", "R1", "R2", "R3", "W1"]
BATCHES_PER_MAT = 3


def gen_mkpf(count: int) -> list[dict]:
    docs = []
    counter = [1]
    for _ in range(count):
        seq = counter[0]
        counter[0] += 1
        budat = rand_date()
        docs.append(
            {
                "_key": f"{pad(seq)}-{budat[:4]}",
                "MBLNR": pad(seq),
                "MJAHR": budat[:4],
                "BLDAT": budat,
                "BUDAT": budat,
                "CPUDT": rand_date(),
                "VGART": random.choice(VGART_LIST),
                "TCODE": random.choice(["MB01", "MB1A", "MB1B", "MB1C", "MB51"])
                if random.random() > 0.3
                else None,
                "USNAM": random.choice(USERS),
                "BKTXT": None,
                "XBLNR": f"REF-{pad(random.randint(1, 99999))}"
                if random.random() > 0.5
                else None,
            }
        )
    return docs


def gen_mard(matnr_list: list[str]) -> list[dict]:
    docs = []
    for matnr in matnr_list:
        for werks in WERKS:
            for lgort in LGORT_LIST:
                docs.append(
                    {
                        "_key": f"{matnr}-{werks}-{lgort}",
                        "MATNR": matnr,
                        "WERKS": werks,
                        "LGORT": lgort,
                        "LABST": round(random.uniform(0, 5000), 3),
                        "SPEME": round(random.uniform(0, 500), 3),
                        "INSME": round(random.uniform(0, 200), 3),
                        "UMLME": round(random.uniform(0, 1000), 3),
                        "RETME": round(random.uniform(0, 100), 3),
                        "LFGJA": str(random.randint(2025, 2026)),
                        "LFMON": f"{random.randint(1, 12):02d}",
                    }
                )
    return docs


def gen_mchb(matnr_list: list[str]) -> list[dict]:
    docs = []
    for matnr in matnr_list:
        for werks in WERKS:
            for lgort in LGORT_LIST:
                for _ in range(random.randint(1, BATCHES_PER_MAT)):
                    docs.append(
                        {
                            "_key": f"{matnr}-{werks}-{lgort}-B{pad(random.randint(1, 99999))}",
                            "MATNR": matnr,
                            "WERKS": werks,
                            "LGORT": lgort,
                            "CHARG": f"B{pad(random.randint(1, 99999))}",
                            "CLABS": round(random.uniform(0, 2000), 3),
                            "CSPEM": round(random.uniform(0, 200), 3),
                            "CINSM": round(random.uniform(0, 100), 3),
                            "HSDAT": rand_date(),
                            "VFDAT": rand_date() if random.random() > 0.3 else None,
                        }
                    )
    return docs


def gen_mseg(
    ekko_list: list[dict], matnr_list: list[str], vendor_lifnrs: list[str]
) -> list[dict]:
    docs = []
    mseg_counter = [1]

    def next_mblnr() -> int:
        v = mseg_counter[0]
        mseg_counter[0] += 1
        return v

    for po in ekko_list:
        item_count = random.randint(1, 6)
        for j in range(item_count):
            mblnr_seq = next_mblnr()
            budat = rand_date()
            qty = round(random.uniform(5, 3000), 3)
            bwart = random.choice(
                ["101", "102", "103", "201", "202", "301", "601", "602", "701", "702"]
            )
            docs.append(
                {
                    "_key": f"{pad(mblnr_seq)}-{budat[:4]}-{pad(j + 1, 4)}",
                    "MBLNR": pad(mblnr_seq),
                    "MJAHR": budat[:4],
                    "ZEILE": pad(j + 1, 4),
                    "BUKRS": random.choice(BUKRS_LIST),
                    "BUDAT": budat,
                    "MATNR": random.choice(matnr_list)
                    if random.random() > 0.1
                    else None,
                    "WERKS": random.choice(WERKS),
                    "LGORT": random.choice(LGORT_LIST),
                    "BWART": bwart,
                    "DMBTR": round(random.uniform(100, 100000), 2),
                    "MENGE": qty,
                    "MEINS": random.choice(UNITS),
                    "WAERS": random.choice(CURRENCIES),
                    "KOSTL": random.choice(COST_CENTERS)
                    if bwart in ("201", "261", "202")
                    else None,
                    "UMLGO": random.choice(LGORT_LIST)
                    if bwart in ("301", "302", "311")
                    else None,
                    "LIFNR": random.choice(vendor_lifnrs)
                    if bwart in ("101", "102", "103", "161")
                    else None,
                    "EBELN": po["EBELN"] if random.random() > 0.3 else None,
                    "EBELP": pad(random.randint(1, 10), 5)
                    if random.random() > 0.3
                    else None,
                }
            )
    return docs


def gen_vbak(count: int, kunnr_list: list[str]) -> list[dict]:
    docs = []
    for i in range(1, count + 1):
        doc_date = rand_date()
        docs.append(
            {
                "_key": pad(i),
                "VBELN": pad(i),
                "KUNNR": random.choice(kunnr_list),
                "ERDAT": doc_date,
                "ERNAM": random.choice(USERS),
                "AUART": random.choice(ORDER_TYPES),
                "VBTYP": "C",
                "NETWR": round(random.uniform(10000, 500000), 2),
                "WAERK": random.choice(CURRENCIES),
                "AUDAT": doc_date,
                "STAWN": pad(random.randint(1, 10000))
                if random.random() > 0.5
                else None,
            }
        )
    return docs


def gen_vbap(vbak_list: list[dict], matnr_list: list[str]) -> list[dict]:
    docs = []
    for so in vbak_list:
        item_count = random.randint(2, 6)
        for j in range(1, item_count + 1):
            docs.append(
                {
                    "_key": f"{so['VBELN']}-{pad(j * 10)}",
                    "VBELN": so["VBELN"],
                    "POSNR": pad(j * 10),
                    "MATNR": random.choice(matnr_list)
                    if random.random() > 0.1
                    else None,
                    "KDMAT": fake.text(max_nb_chars=30)
                    if random.random() > 0.7
                    else None,
                    "KWMENG": round(random.uniform(10, 1000), 3),
                    "VRKME": random.choice(UNITS),
                    "NETWR": round(random.uniform(1000, 50000), 2),
                    "WERKS": random.choice(WERKS),
                    "ERDAT": so["ERDAT"],
                }
            )
    return docs


def gen_likp(count: int, kunnr_list: list[str]) -> list[dict]:
    docs = []
    for i in range(1, count + 1):
        doc_date = rand_date()
        docs.append(
            {
                "_key": pad(i),
                "VBELN": pad(i),
                "KUNNR": random.choice(kunnr_list),
                "WADAT": doc_date,
                "ERDAT": doc_date,
                "LIFSP": random.choice(["01", "02", "03"]),
                "VBTYP": "J",
                "WADAT_IST": rand_date() if random.random() > 0.5 else None,
            }
        )
    return docs


def gen_lips(likp_list: list[dict], matnr_list: list[str]) -> list[dict]:
    docs = []
    for dl in likp_list:
        item_count = random.randint(2, 5)
        for j in range(1, item_count + 1):
            docs.append(
                {
                    "_key": f"{dl['VBELN']}-{pad(j * 10)}",
                    "VBELN": dl["VBELN"],
                    "POSNR": pad(j * 10),
                    "MATNR": random.choice(matnr_list)
                    if random.random() > 0.1
                    else None,
                    "LFIMG": round(random.uniform(5, 800), 3),
                    "VRKME": random.choice(UNITS),
                    "WERKS": random.choice(WERKS),
                    "LGORT": random.choice(LGORT_LIST),
                }
            )
    return docs


def gen_rbkd(count: int, kunnr_list: list[str]) -> list[dict]:
    docs = []
    for i in range(1, count + 1):
        year = str(random.randint(2025, 2026))
        docs.append(
            {
                "_key": f"{pad(i)}-{year}",
                "BELNR": pad(i),
                "GJAHR": year,
                "KUNNR": random.choice(kunnr_list),
                "BUDAT": rand_date(),
                "WRBTR": round(random.uniform(5000, 300000), 2),
                "WMWST": round(random.uniform(500, 30000), 2),
                "ZUONR": pad(random.randint(1, 2000))
                if random.random() > 0.5
                else None,
                "SGTXT": fake.sentence(nb_words=6) if random.random() > 0.6 else None,
            }
        )
    return docs


# ==================== Batch Insert ====================

BATCH_SIZE = 200


def insert_batched(collection: str, docs: list[dict]) -> None:
    total = len(docs)
    for i in range(0, total, BATCH_SIZE):
        batch = docs[i : i + BATCH_SIZE]
        batch_upsert(collection, batch)
    print(f"  ✓ {collection}: {total} rows inserted")


# ==================== Main ====================


def run() -> None:
    print("=" * 60)
    print("ArangoDB Data Population — 1 Year (2025-03 ~ 2026-03)")
    print("=" * 60)

    # 1. Create collections
    print("\n[1] Creating collections...")
    collections = [
        "MARA",
        "LFA1",
        "MKPF",
        "MARD",
        "MCHB",
        "EKKO",
        "EKPO",
        "MSEG",
        "VBAK",
        "VBAP",
        "LIKP",
        "LIPS",
        "RBKD",
    ]
    for c in collections:
        create_collection(c)

    # 2. Create indexes
    print("\n[2] Creating indexes...")
    create_index("MARA", "persistent", ["MATNR"], unique=True)
    create_index("LFA1", "persistent", ["LIFNR"], unique=True)
    create_index("MKPF", "persistent", ["MBLNR", "MJAHR"], unique=True)
    create_index("MKPF", "persistent", ["BUDAT"])
    create_index("MARD", "persistent", ["MATNR", "WERKS", "LGORT"], unique=True)
    create_index("MARD", "persistent", ["MATNR"])
    create_index("MARD", "persistent", ["WERKS"])
    create_index(
        "MCHB", "persistent", ["MATNR", "WERKS", "LGORT", "CHARG"], unique=True
    )
    create_index("MCHB", "persistent", ["MATNR"])
    create_index("MCHB", "persistent", ["WERKS"])
    create_index("EKKO", "persistent", ["EBELN"], unique=True)
    create_index("EKKO", "persistent", ["LIFNR"])
    create_index("EKKO", "persistent", ["AEDAT"])
    create_index("EKPO", "persistent", ["EBELN", "EBELP"], unique=True)
    create_index("EKPO", "persistent", ["MATNR"])
    create_index("MSEG", "persistent", ["MBLNR", "MJAHR", "ZEILE"], unique=True)
    create_index("MSEG", "persistent", ["BUDAT"])
    create_index("MSEG", "persistent", ["MATNR"])
    create_index("VBAK", "persistent", ["VBELN"], unique=True)
    create_index("VBAK", "persistent", ["KUNNR"])
    create_index("VBAK", "persistent", ["ERDAT"])
    create_index("VBAP", "persistent", ["VBELN", "POSNR"], unique=True)
    create_index("VBAP", "persistent", ["MATNR"])
    create_index("LIKP", "persistent", ["VBELN"], unique=True)
    create_index("LIKP", "persistent", ["KUNNR"])
    create_index("LIPS", "persistent", ["VBELN", "POSNR"], unique=True)
    create_index("LIPS", "persistent", ["MATNR"])
    create_index("RBKD", "persistent", ["BELNR", "GJAHR"], unique=True)
    create_index("RBKD", "persistent", ["KUNNR"])

    # 3. Generate reference data
    print("\n[3] Generating reference data...")
    mara_docs = gen_mara(500)
    print(f"  MARA: {len(mara_docs)} rows")
    matnr_list = [d["MATNR"] for d in mara_docs]

    lfa1_docs = gen_lfa1(120)
    print(f"  LFA1: {len(lfa1_docs)} rows")
    lifnr_list = [d["LIFNR"] for d in lfa1_docs]

    cust_docs = gen_customers(200)
    print(f"  Customers (virtual): {len(cust_docs)} rows")
    kunnr_list = [d["KUNNR"] for d in cust_docs]

    # 4. Generate stock & document data
    print("\n[4] Generating MM inventory documents...")
    mkpf_docs = gen_mkpf(5000)
    print(f"  MKPF: {len(mkpf_docs)} rows")

    mard_docs = gen_mard(matnr_list)
    print(f"  MARD: {len(mard_docs)} rows")

    mchb_docs = gen_mchb(matnr_list)
    print(f"  MCHB: {len(mchb_docs)} rows")

    # 5. Generate MM transactions
    print("\n[5] Generating MM transactions...")
    ekko_docs = gen_ekko(2000, lifnr_list)
    print(f"  EKKO: {len(ekko_docs)} rows")

    ekpo_docs = gen_ekpo(ekko_docs, matnr_list, lifnr_list)
    print(f"  EKPO: {len(ekpo_docs)} rows")

    mseg_docs = gen_mseg(ekko_docs, matnr_list, lifnr_list)
    print(f"  MSEG: {len(mseg_docs)} rows")

    print("\n[6] Generating SD transactions...")
    vbak_docs = gen_vbak(1800, kunnr_list)
    print(f"  VBAK: {len(vbak_docs)} rows")

    vbap_docs = gen_vbap(vbak_docs, matnr_list)
    print(f"  VBAP: {len(vbap_docs)} rows")

    likp_docs = gen_likp(600, kunnr_list)
    print(f"  LIKP: {len(likp_docs)} rows")

    lips_docs = gen_lips(likp_docs, matnr_list)
    print(f"  LIPS: {len(lips_docs)} rows")

    rbkd_docs = gen_rbkd(400, kunnr_list)
    print(f"  RBKD: {len(rbkd_docs)} rows")

    # 6. Insert data
    print("\n[7] Inserting data into ArangoDB...")
    insert_batched("MARA", mara_docs)
    insert_batched("LFA1", lfa1_docs)
    insert_batched("MKPF", mkpf_docs)
    insert_batched("MARD", mard_docs)
    insert_batched("MCHB", mchb_docs)
    insert_batched("EKKO", ekko_docs)
    insert_batched("EKPO", ekpo_docs)
    insert_batched("MSEG", mseg_docs)
    insert_batched("VBAK", vbak_docs)
    insert_batched("VBAP", vbap_docs)
    insert_batched("LIKP", likp_docs)
    insert_batched("LIPS", lips_docs)
    insert_batched("RBKD", rbkd_docs)

    # 7. Verify counts
    print("\n[8] Verifying row counts...")
    grand = 0
    for coll in collections:
        r = acmd("get", f"/_api/collection/{coll}/count")
        cnt = r.get("count", 0)
        grand += cnt
        print(f"  {coll}: {cnt:,} documents")
    print(f"\n✅ Total: {grand:,} documents across {len(collections)} collections")
    print(
        f"   Date range: {START_DATE.strftime('%Y-%m-%d')} ~ {END_DATE.strftime('%Y-%m-%d')}"
    )


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
