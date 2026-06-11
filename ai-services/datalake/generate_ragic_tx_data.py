#!/usr/bin/env python3
"""
@file        generate_ragic_tx_data.py
@description 庫存/採購/訂單核心 tables 的模擬資料
             目標：CONFIGURATIONFILE_10(供應商)、CONFIGURATIONFILE_9(品項)、
             CONFIGURATIONFILE_3(倉庫)、ERP_13(採購單)、ERP_48(進貨單)、
             ERP_26(銷貨單)、STOCK_16(庫存表)、STOCK_17(倉儲庫存表)
@lastUpdate  2026-04-02 12:00:00
@author      Daniel Chung
@version     1.0.0
"""

import random
import subprocess
import json
from datetime import datetime, timedelta, UTC
from faker import Faker

fake = Faker(["zh_TW", "en_US"])
Faker.seed(42)
random.seed(42)

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = "root:abc_desktop_2026"
COLLECTION = "da_table_data_ragic"
TS = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
START = datetime(2025, 10, 1)
END = datetime(2026, 4, 2)
DAYS = (END - START).days

def rand_date() -> str:
    d = START + timedelta(days=random.randint(0, DAYS))
    return d.strftime("%Y-%m-%d")

def rand_date_yyyymmdd() -> str:
    d = START + timedelta(days=random.randint(0, DAYS))
    return d.strftime("%Y%m%d")

def pad(n: int, w: int = 6) -> str:
    return str(n).zfill(w)

VENDORS = []
ITEMS = []
WAREHOUSES = []
PO_REFS = []
GR_REFS = []

CATEGORIES = ["原料", "半成品", "成品", "商品", "物料", "添加物"]
UNITS = ["公斤(kg)", "公克(g)", "包", "盒", "罐", "桶", "箱", "袋"]
PAYMENT_TERMS = ["月結30天", "月結60天", "票到30天", "預付", "現結"]
TAX_TYPES = ["應稅", "零稅", "免稅"]
VENDOR_TYPES = ["製造商", "經銷商", "代理商", "貿易商"]

def make_key(table: str, n: int) -> str:
    return f"{table}_{pad(n)}"

def curl_post(docs: list) -> list:
    payload = json.dumps(docs)
    r = subprocess.run(
        ["curl", "-s", "-u", AUTH,
         f"{ARANGO_URL}/_db/{DB}/_api/document/{COLLECTION}?overwriteMode=upsert",
         "-X", "POST", "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except:
        return [{"error": True, "msg": r.stdout[:200]}]

def insert_batch(label: str, docs: list, batch_size: int = 100) -> None:
    total = len(docs)
    for i in range(0, total, batch_size):
        batch = docs[i:i+batch_size]
        result = curl_post(batch)
        ok = sum(1 for r in result if not (isinstance(r, dict) and r.get("error")))
        print(f"  {label} [{i//batch_size+1}]: {ok}/{len(batch)} ok")

# ==================== CONFIGURATIONFILE_10 交易對象/供應商 ====================
def gen_vendors(n: int) -> list:
    docs = []
    for i in range(1, n+1):
        vid = f"V{pad(i, 5)}"
        vtype = random.choice(VENDOR_TYPES)
        tax_type = random.choice(TAX_TYPES)
        tax_rate = random.choice([0, 5, 0])
        city = random.choice(["台北市", "新北市", "桃園市", "台中市", "台南市", "高雄市", "新竹縣", "彰化縣"])
        district = random.choice(["中正區", "大同區", "中山區", "松山區", "萬華區", "大安區", "南港區", "汐止區"])
        payment = random.choice(PAYMENT_TERMS)
        docs.append({
            "_key": make_key("V10", i),
            "_ragicId": f"V10-{pad(i)}",
            "table_id": "CONFIGURATIONFILE_10",
            "1015575": vid,
            "1015576": f"{vtype}-{vid}",
            "1015577": vid,
            "1015578": f"{fake.company()} {vtype}",
            "1015579": fake.company_suffix(),
            "1015581": fake.numerify("########"),
            "1015582": f"統編{fake.numerify('########')}",
            "1015589": fake.name(),
            "1015604": fake.name(),
            "1015605": fake.phone_number(),
            "1015606": fake.phone_number(),
            "1015583": fake.phone_number(),
            "1015584": fake.phone_number(),
            "1016116": fake.email(),
            "1015608": f"{city}{district}{fake.street_address()}",
            "1015590": fake.uri(),
            "1015598": True,
            "1015599": True,
            "1015625": random.choice(["國內", "國外"]),
            "1015626": random.choice(["正常往來", "新進", "暂停交易"]),
            "1015627": random.choice(["食品製造", "食品貿易", "餐飲服務", "物流配送"]),
            "1015631": payment,
            "1015634": random.choice(["銀行轉帳", "支票", "現金"]),
            "1015638": random.choice(["TWD", "USD", "CNY"]),
            "1015639": tax_type,
            "1015640": tax_rate,
            "1015641": "二聯式發票",
            "1015643": random.choice(["EXW", "FOB", "CIF", "DDP"]),
            "1015628": random.choice(["一般納稅人", "小規模", "免稅"]),
            "1015647": fake.sentence(nb_words=8),
            "105": rand_date(),
            "109": rand_date(),
            "created_at": TS,
            "updated_at": TS,
        })
        VENDORS.append({
            "code": vid, "name": docs[-1]["1015578"],
            "city": city, "payment": payment
        })
    return docs

# ==================== CONFIGURATIONFILE_9 品項 ====================
def gen_items(n: int) -> list:
    docs = []
    for i in range(1, n+1):
        iid = f"ITEM{pad(i, 5)}"
        cat = random.choice(CATEGORIES)
        unit = random.choice(UNITS)
        price = round(random.uniform(50, 5000), 2)
        vendor = random.choice(VENDORS)
        origin = random.choice(["台灣", "中國", "日本", "美國", "泰國", "越南"])
        shelf_life = random.choice([30, 60, 90, 180, 365, None])
        docs.append({
            "_key": make_key("I9", i),
            "_ragicId": f"I9-{pad(i)}",
            "table_id": "CONFIGURATIONFILE_9",
            "1015486": iid,
            "1015483": f"{cat}-{fake.word().capitalize()}-{iid}",
            "1015225": fake.sentence(nb_words=6),
            "1015230": random.choice(["正常", "試驗中", "停產"]),
            "1015329": random.choice(["原料", "添加物", "包材", "成品"]),
            "1015221": random.choice(["啟用", "停用"]),
            "1015233": random.choice(["{unit}"], ),
            "1015560": price,
            "1015556": round(price * 0.8, 2),
            "1015227": fake.ean8(),
            "1015558": round(price * 1.3, 2),
            "1015228": fake.ean13(),
            "1015269": origin,
            "1015220": fake.word().upper(),
            "1015561": shelf_life,
            "1015554": random.randint(100, 10000),
            "1015555": random.choice(["公斤", "公克", "包", "箱"]),
            "1015270": random.choice(["常溫", "冷藏", "冷凍", "通風"]),
            "1015223": fake.text(max_nb_chars=30),
            "1015273": random.choice(["牛", "豬", "雞", "魚", None]),
            "1015322": random.choice([True, False]),
            "1015263": random.choice(["添加物A", "添加物B", "添加物C"]),
            "1015539": random.randint(0, 5),
            "1015559": random.randint(10, 1000),
            "1020001": round(random.uniform(5, 50), 1),
            "1020002": random.randint(1, 100),
            "1020003": random.randint(1, 30),
            "1022528": vendor["code"],
            "1022529": vendor["name"],
            "1022632": round(price * 0.75, 2),
            "1022623": random.choice([0, 5, 10]),
            "1022626": random.randint(10, 500),
            "1022629": random.randint(100, 10000),
            "1022631": random.choice(["包", "盒", "罐"]),
            "1015542": random.choice(["A", "B", "C", None]),
            "1015315": f"https://example.com/product/{iid}",
            "1015277": random.choice(["牛肉", "豬肉", "雞肉", "魚肉", "素食", None]),
            "1015327": random.choice(["甲殼類", "芒果", "花生", "牛奶", "蛋", None]),
            "105": rand_date(),
            "109": rand_date(),
            "created_at": TS,
            "updated_at": TS,
        })
        ITEMS.append({
            "code": iid, "name": docs[-1]["1015483"],
            "cat": cat, "price": price, "unit": unit
        })
    return docs

# ==================== CONFIGURATIONFILE_3 倉庫 ====================
def gen_warehouses(n: int) -> list:
    docs = []
    for i in range(1, n+1):
        wid = f"WH{pad(i, 3)}"
        city = random.choice(["台北", "新北", "桃園", "台中", "台南", "高雄", "新竹"])
        docs.append({
            "_key": make_key("W3", i),
            "_ragicId": f"W3-{pad(i)}",
            "table_id": "CONFIGURATIONFILE_3",
            "1015396": wid,
            "1015398": wid,
            "1015397": f"{city}倉庫 {fake.word().capitalize()}",
            "1015399": random.choice(["自有", "租賃", "委外"]),
            "1015400": random.randint(50, 500),
            "1015401": random.randint(100, 2000),
            "1015402": random.choice(["常溫", "冷藏", "冷凍", "恆溫"]),
            "1015403": fake.street_address(),
            "1015404": fake.phone_number(),
            "1015405": fake.name(),
            "105": rand_date(),
            "109": rand_date(),
            "created_at": TS,
            "updated_at": TS,
        })
        WAREHOUSES.append({"code": wid, "name": docs[-1]["1015397"]})
    return docs

# ==================== ERP_13 採購單 ====================
def gen_purchase_orders(n: int) -> list:
    docs = []
    for i in range(1, n+1):
        po_no = f"PO{pad(i, 6)}"
        vendor = random.choice(VENDORS)
        emp = f"EMP{pad(random.randint(1,30), 4)}"
        emp_name = fake.name()
        date = rand_date()
        tax_type = random.choice(TAX_TYPES)
        tax_rate = 5
        subtotal = round(random.uniform(5000, 200000), 0)
        discount = round(random.uniform(0, subtotal * 0.1), 0)
        tax = round((subtotal - discount) * tax_rate / 100, 0)
        freight = round(random.uniform(0, 2000), 0)
        total = subtotal - discount + tax + freight
        PO_REFS.append(po_no)
        docs.append({
            "_key": make_key("PO13", i),
            "_ragicId": f"PO13-{pad(i)}",
            "table_id": "ERP_13",
            "1013009": rand_date_yyyymmdd(),
            "1018421": po_no,
            "1018423": date,
            "1018425": rand_date(),
            "1018473": rand_date(),
            "1018422": vendor["code"],
            "1018424": vendor["name"],
            "1018426": fake.numerify("########"),
            "1018428": emp,
            "1018429": vendor["payment"],
            "1018430": fake.phone_number(),
            "1018427": fake.name(),
            "1018431": fake.phone_number(),
            "1018432": fake.phone_number(),
            "1018434": fake.email(),
            "1018433": fake.address()[:50],
            "1018436": random.randint(0, 5),
            "1018442": tax_type,
            "1018444": tax_rate,
            "1018443": subtotal,
            "1018445": discount,
            "1018446": tax,
            "1018447": freight,
            "1018450": total,
            "1018454": fake.sentence(nb_words=6),
            "1018466": random.choice(["一般", "緊急", "研發樣品"]),
            "1018452": fake.email(),
            "1018453": fake.phone_number(),
            "1018456": fake.address()[:50],
            "1018609": random.choice(["未進貨完成", "部分進貨", "已進貨完成"]),
            "105": rand_date(),
            "109": rand_date(),
            "created_at": TS,
            "updated_at": TS,
        })
    return docs

# ==================== ERP_48 進貨單 ====================
def gen_goods_receipts(n: int) -> list:
    docs = []
    for i in range(1, n+1):
        gr_no = f"GR{pad(i, 6)}"
        vendor = random.choice(VENDORS)
        po_ref = random.choice(PO_REFS) if PO_REFS else f"PO{random.randint(1,1000):06d}"
        date = rand_date()
        subtotal = round(random.uniform(3000, 150000), 0)
        discount = round(random.uniform(0, subtotal * 0.05), 0)
        tax = round((subtotal - discount) * 0.05, 0)
        freight = round(random.uniform(0, 1500), 0)
        total = subtotal - discount + tax + freight
        GR_REFS.append(gr_no)
        docs.append({
            "_key": make_key("GR48", i),
            "_ragicId": f"GR48-{pad(i)}",
            "table_id": "ERP_48",
            "1023120": gr_no,
            "1023121": vendor["code"],
            "1023122": vendor["name"],
            "1023124": po_ref,
            "1023125": f"RECV{random.randint(1,9999):04d}",
            "1023126": date,
            "1023130": random.randint(1, 500),
            "1023131": random.randint(1, 500),
            "1023132": random.choice(UNITS),
            "1023133": round(random.uniform(50, 3000), 2),
            "1023134": round(random.uniform(5000, 100000), 2),
            "1023135": fake.bothify("??###"),
            "1023136": rand_date(),
            "1023151": date[:7],
            "1023153": 0,
            "1023154": random.randint(0, 50),
            "1024656": subtotal,
            "1024657": discount,
            "1024658": round(discount/subtotal*100, 1) if subtotal > 0 else 0,
            "1024659": fake.sentence(nb_words=4),
            "1024660": random.choice(TAX_TYPES),
            "1024661": 5,
            "1024662": tax,
            "1024663": freight,
            "1024664": total,
            "1024665": f"INV{random.randint(100000, 999999)}",
            "1023153": random.randint(0, 10),
            "1021011": random.choice(["未進貨完成", "已進貨完成"]),
            "105": rand_date(),
            "109": rand_date(),
            "created_at": TS,
            "updated_at": TS,
        })
    return docs

# ==================== ERP_26 銷貨單 ====================
def gen_sales_orders(n: int) -> list:
    docs = []
    for i in range(1, n+1):
        so_no = f"SO{pad(i, 6)}"
        customer = random.choice(VENDORS)
        emp = f"EMP{random.randint(1,20):04d}"
        date = rand_date()
        subtotal = round(random.uniform(2000, 100000), 0)
        discount = round(random.uniform(0, subtotal * 0.08), 0)
        tax = round((subtotal - discount) * 0.05, 0)
        total = subtotal - discount + tax
        docs.append({
            "_key": make_key("SO26", i),
            "_ragicId": f"SO26-{pad(i)}",
            "table_id": "ERP_26",
            "1019100": rand_date_yyyymmdd(),
            "1019101": so_no,
            "1019102": date,
            "1019115": customer["code"],
            "1019116": customer["name"],
            "1019117": fake.numerify("########"),
            "1019120": emp,
            "1019122": fake.name(),
            "1019124": customer["payment"],
            "1019126": fake.phone_number(),
            "1019128": fake.email(),
            "1019129": fake.address()[:50],
            "1019130": random.randint(1, 50),
            "1019131": random.randint(1, 50),
            "1019132": random.choice(UNITS),
            "1019133": round(random.uniform(20, 2000), 2),
            "1019134": round(random.uniform(1000, 50000), 2),
            "1019135": random.randint(0, 100),
            "1019136": round(random.uniform(0, 1000), 2),
            "1019137": round(random.uniform(0, 500), 0),
            "1019138": round(random.uniform(1000, 55000), 2),
            "1019139": random.choice(TAX_TYPES),
            "1019140": 5,
            "1019142": fake.sentence(nb_words=5),
            "1019105": random.choice(["待出貨", "已出貨", "部分出貨"]),
            "105": rand_date(),
            "109": rand_date(),
            "created_at": TS,
            "updated_at": TS,
        })
    return docs

# ==================== STOCK_16 庫存表 ====================
def gen_stock_inventory(n: int) -> list:
    docs = []
    for i in range(1, n+1):
        item = random.choice(ITEMS)
        wh = random.choice(WAREHOUSES)
        batch = fake.bothify("??####")
        mfg_date = rand_date()
        exp_date = (datetime.strptime(mfg_date, "%Y-%m-%d") + timedelta(days=random.randint(30, 365))).strftime("%Y-%m-%d")
        in_qty = random.randint(100, 5000)
        out_qty = random.randint(0, in_qty)
        stock_qty = in_qty - out_qty
        docs.append({
            "_key": make_key("ST16", i),
            "_ragicId": f"ST16-{pad(i)}",
            "table_id": "STOCK_16",
            "1018127": item["code"],
            "1018133": item["name"],
            "1018128": batch,
            "1018129": in_qty,
            "1018130": item["unit"],
            "1018131": random.randint(0, 5),
            "1018134": mfg_date,
            "1018135": exp_date,
            "1018271": in_qty,
            "1018275": out_qty,
            "1018273": random.randint(0, 10),
            "1018274": random.randint(0, 5),
            "1018276": abs(in_qty - out_qty - random.randint(0, 20)),
            "1018277": stock_qty,
            "1018138": round(item["price"], 2),
            "1018139": round(stock_qty * item["price"], 2),
            "1018140": wh["code"],
            "1018141": wh["name"],
            "1018142": stock_qty,
            "1018269": random.randint(0, 100),
            "1018164": random.randint(0, 200),
            "1018165": random.randint(-10, 10),
            "1018166": item["unit"],
            "1018167": wh["code"],
            "1018168": wh["name"],
            "1018282": random.randint(0, 50),
            "1019614": f"PRD{random.randint(1,200):05d}",
            "1019289": f"INV{random.randint(1,500):05d}",
            "1018132": random.randint(0, 10),
            "1022907": random.randint(0, 365),
            "1020310": random.randint(0, 5),
            "1019290": i,
            "105": rand_date(),
            "109": rand_date(),
            "created_at": TS,
            "updated_at": TS,
        })
    return docs

# ==================== STOCK_17 倉儲庫存表 ====================
def gen_warehouse_inventory(n: int) -> list:
    docs = []
    for i in range(1, n+1):
        wh = random.choice(WAREHOUSES)
        item = random.choice(ITEMS)
        docs.append({
            "_key": make_key("ST17", i),
            "_ragicId": f"ST17-{pad(i)}",
            "table_id": "STOCK_17",
            "1018140": wh["code"],
            "1018141": wh["name"],
            "1018142": random.randint(0, 500),
            "1018127": item["code"],
            "1018133": item["name"],
            "1018128": fake.bothify("??###"),
            "1018271": random.randint(0, 300),
            "1018275": random.randint(0, 200),
            "1018277": random.randint(0, 500),
            "1018130": item["unit"],
            "1018135": rand_date(),
            "1018144": fake.name(),
            "1018145": rand_date(),
            "105": rand_date(),
            "109": rand_date(),
            "created_at": TS,
            "updated_at": TS,
        })
    return docs

def main():
    print("=" * 60)
    print("Ragic 庫存/採購/訂單 模擬資料生成")
    print("=" * 60)

    all_docs = []

    print("\n[1/7] 生成供應商 (CONFIGURATIONFILE_10)...")
    vendors = gen_vendors(50)
    all_docs.extend(vendors)
    print(f"  生成 {len(vendors)} 筆")

    print("\n[2/7] 生成品項 (CONFIGURATIONFILE_9)...")
    items = gen_items(200)
    all_docs.extend(items)
    print(f"  生成 {len(items)} 筆")

    print("\n[3/7] 生成倉庫 (CONFIGURATIONFILE_3)...")
    warehouses = gen_warehouses(15)
    all_docs.extend(warehouses)
    print(f"  生成 {len(warehouses)} 筆")

    print("\n[4/7] 生成採購單 (ERP_13)...")
    pos = gen_purchase_orders(100)
    all_docs.extend(pos)
    print(f"  生成 {len(pos)} 筆")

    print("\n[5/7] 生成進貨單 (ERP_48)...")
    gres = gen_goods_receipts(200)
    all_docs.extend(gres)
    print(f"  生成 {len(gres)} 筆")

    print("\n[6/7] 生成銷貨單 (ERP_26)...")
    sos = gen_sales_orders(80)
    all_docs.extend(sos)
    print(f"  生成 {len(sos)} 筆")

    print("\n[7/7] 生成庫存表 (STOCK_16)...")
    stocks = gen_stock_inventory(500)
    all_docs.extend(stocks)
    print(f"  生成 {len(stocks)} 筆")

    print("\n[Extra] 生成倉儲庫存表 (STOCK_17)...")
    whinv = gen_warehouse_inventory(200)
    all_docs.extend(whinv)
    print(f"  生成 {len(whinv)} 筆")

    print(f"\n總計: {len(all_docs)} 筆")
    print("寫入 da_table_data_ragic...")

    insert_batch("all", all_docs)

    # Verify
    r = subprocess.run(
        ["curl", "-s", "-u", AUTH,
         f"{ARANGO_URL}/_db/{DB}/_api/cursor",
         "-X", "POST", "-H", "Content-Type: application/json",
         "-d", json.dumps({"query": "RETURN LENGTH(FOR d IN da_table_data_ragic RETURN d)"})],
        capture_output=True, text=True)
    count = json.loads(r.stdout)["result"][0]
    print(f"\n✓ da_table_data_ragic: {count} 筆")

if __name__ == "__main__":
    main()
