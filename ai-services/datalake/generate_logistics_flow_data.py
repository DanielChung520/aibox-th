#!/usr/bin/env python3
"""
@file        generate_logistics_flow_data.py
@description 採購-訂單-生產全流程模擬資料（完整關聯版本）
              所有 FK 關聯在記憶體中建立後一次性寫入，確保關聯完整。
@lastUpdate  2026-04-08 23:00:00
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
END = datetime(2026, 4, 8)
DAYS = (END - START).days

VENDORS = []
ITEMS = []
WAREHOUSES = []
EMPLOYEES = []
PRODUCT_ITEMS = []

RFQ_LIST = []
QUOTE_LIST = []
PO_LIST = []
GR_LIST = []
RETURN_LIST = []
SO_LIST = []
PD_LIST = []
MRP_LIST = []
BUDGET_LIST = []
WO_LIST = []
PICK_LIST = []
DISPATCH_LIST = []
QC_LIST = []
FG_LIST = []

UNITS = ["公斤(kg)", "公克(g)", "包", "盒", "罐", "桶", "箱", "袋"]
PAYMENT_TERMS = ["月結30天", "月結60天", "票到30天", "預付", "現結"]
TAX_TYPES = ["應稅", "零稅", "免稅"]
PRODUCTION_TYPES = ["本廠生產", "委外生產", "本廠再製"]
QC_RESULTS = ["合格", "不合格", "讓步受入", "特採"]
WORK_SHIFT = ["早班", "中班", "晚班"]


def rand_date():
    d = START + timedelta(days=random.randint(0, DAYS))
    return d.strftime("%Y-%m-%d")


def rand_date_yyyymmdd():
    d = START + timedelta(days=random.randint(0, DAYS))
    return d.strftime("%Y%m%d")


def pad(n, w=6):
    return str(n).zfill(w)


def make_key(prefix, n):
    return f"{prefix}_{pad(n)}"


def curl_post(docs):
    payload = json.dumps(docs)
    r = subprocess.run(
        ["curl", "-s", "-u", AUTH,
         f"{ARANGO_URL}/_db/{DB}/_api/document/{COLLECTION}?overwriteMode=replace",
         "-X", "POST", "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except:
        return [{"error": True, "raw": r.stdout[:200]}]


def insert_batch(label, docs, batch_size=100):
    total = len(docs)
    for i in range(0, total, batch_size):
        batch = docs[i:i+batch_size]
        result = curl_post(batch)
        ok = 0
        for r in result:
            if isinstance(r, dict) and r.get("error") == True:
                pass
            else:
                ok += 1
        print(f"  {label} [{i//batch_size+1}]: {ok}/{len(batch)} ok")


def gen_master():
    global VENDORS, ITEMS, WAREHOUSES, EMPLOYEES, PRODUCT_ITEMS
    cats = ["原料", "半成品", "成品", "商品", "添加物", "包材"]
    for i in range(1, 51):
        vid = f"V{pad(i,5)}"
        VENDORS.append({"code": vid, "name": f"{fake.company()} {random.choice(['實業','貿易','工業','食品','材料'])}"})
    for i in range(1, 201):
        iid = f"ITEM{pad(i,5)}"
        cat = random.choice(cats)
        price = round(random.uniform(50, 5000), 2)
        ITEMS.append({"code": iid, "name": f"{cat}-{fake.word().capitalize()}-{iid}", "cat": cat, "unit": random.choice(UNITS), "price": price})
    for i in range(1, 31):
        iid = f"FG{pad(i,5)}"
        PRODUCT_ITEMS.append({"code": iid, "name": f"成品-{fake.word().capitalize()}-{iid}", "cat": "成品", "unit": random.choice(["箱","盒","罐"]), "price": round(random.uniform(200, 8000), 2)})
        ITEMS.append(PRODUCT_ITEMS[-1])
    for i in range(1, 16):
        wid = f"WH{pad(i,3)}"
        WAREHOUSES.append({"code": wid, "name": f"{random.choice(['台北','桃園','台中','台南','高雄'])}倉庫{i}"})
    for i in range(1, 31):
        EMPLOYEES.append({"code": f"EMP{pad(i,4)}", "name": fake.name()})


def gen_rfq(n):
    docs = []
    for i in range(1, n+1):
        rfq_no = f"RFQ{pad(i,6)}"
        vendor = random.choice(VENDORS)
        emp = random.choice(EMPLOYEES)
        date = rand_date()
        RFQ_LIST.append((rfq_no, vendor["code"]))
        docs.append({
            "_key": make_key("RFQ59", i), "_ragicId": f"RFQ59-{pad(i)}", "table_id": "ERP_59",
            "1018382": rfq_no, "1018383": date, "1018384": vendor["code"], "1018385": vendor["name"],
            "1018386": emp["code"], "1018387": emp["name"],
            "1018388": random.choice(["備料中","已發出","已回覆"]),
            "1018389": fake.sentence(nb_words=6), "1018390": rand_date(), "1018391": rand_date(),
            "1018392": random.choice(PAYMENT_TERMS), "1018393": random.choice(TAX_TYPES),
            "1018394": round(random.uniform(5000, 50000), 0),
            "1018395": fake.phone_number(), "1018396": fake.email(),
            "105": date, "109": date, "created_at": TS, "updated_at": TS,
        })
    return docs


def gen_quotations(n):
    docs = []
    for i in range(1, n+1):
        quote_no = f"QU{pad(i,6)}"
        vendor = random.choice(VENDORS)
        emp = random.choice(EMPLOYEES)
        date = rand_date()
        valid = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")
        subtotal = round(random.uniform(10000, 200000), 0)
        tax = round(subtotal * 0.05, 0)
        QUOTE_LIST.append((quote_no, vendor["code"]))
        docs.append({
            "_key": make_key("QU66", i), "_ragicId": f"QU66-{pad(i)}", "table_id": "ERP_66",
            "1016153": quote_no, "1016084": date, "1016154": valid,
            "1016155": vendor["code"], "1016156": vendor["name"],
            "1016157": emp["code"], "1016158": emp["name"],
            "1016159": random.choice(["报价中","已接受","已拒絕"]),
            "1016160": subtotal, "1016161": random.choice(TAX_TYPES), "1016162": 5, "1016163": tax,
            "1016164": subtotal + tax,
            "1016165": random.choice(PAYMENT_TERMS),
            "1016166": rand_date(), "1016167": rand_date(),
            "1016168": fake.phone_number(), "1016169": fake.email(),
            "1016172": fake.sentence(nb_words=4),
            "1016175": random.choice(["FOB","EXW","CIF","DDP"]),
            "105": date, "109": date, "created_at": TS, "updated_at": TS,
        })
    return docs


def gen_purchase_orders(n):
    docs = []
    for i in range(1, n+1):
        po_no = f"PO{pad(i,6)}"
        vendor = random.choice(VENDORS)
        emp = random.choice(EMPLOYEES)
        date = rand_date()
        delivery = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=random.randint(7, 60))).strftime("%Y-%m-%d")
        subtotal = round(random.uniform(5000, 200000), 0)
        discount = round(random.uniform(0, subtotal * 0.1), 0)
        tax = round((subtotal - discount) * 0.05, 0)
        freight = round(random.uniform(0, 2000), 0)
        total = subtotal - discount + tax + freight
        PO_LIST.append((po_no, vendor["code"]))
        q_ref = random.choice(QUOTE_LIST)[0] if (random.random() < 0.7 and QUOTE_LIST) else ""
        r_ref = random.choice(RFQ_LIST)[0] if (not q_ref and RFQ_LIST) else ""
        docs.append({
            "_key": make_key("PO13", i), "_ragicId": f"PO13-{pad(i)}", "table_id": "ERP_13",
            "1013009": rand_date_yyyymmdd(), "1018421": po_no, "1018423": date, "1018425": delivery,
            "1018473": rand_date(), "1018422": vendor["code"], "1018424": vendor["name"],
            "1018426": fake.numerify("########"),
            "1018428": emp["code"], "1018429": vendor.get("payment", random.choice(PAYMENT_TERMS)),
            "1018430": fake.phone_number(), "1018427": emp["name"],
            "1018431": fake.phone_number(), "1018432": fake.phone_number(),
            "1018434": fake.email(), "1018433": fake.address()[:50],
            "1018436": random.randint(0, 5), "1018442": random.choice(TAX_TYPES), "1018444": 5,
            "1018443": subtotal, "1018445": discount, "1018446": tax, "1018447": freight,
            "1018450": total, "1018454": fake.sentence(nb_words=6),
            "1018466": random.choice(["一般","緊急","研發樣品"]),
            "1018609": random.choice(["未進貨完成","部分進貨","已進貨完成"]),
            "1018457": q_ref, "1018458": r_ref,
            "105": date, "109": date, "created_at": TS, "updated_at": TS,
        })
    return docs


def gen_goods_receipts(n):
    docs = []
    for i in range(1, n+1):
        gr_no = f"GR{pad(i,6)}"
        vendor = random.choice(VENDORS)
        po_pair = random.choice(PO_LIST) if PO_LIST else (f"PO{random.randint(1,999):06d}", vendor["code"])
        po_no = po_pair[0]
        date = rand_date()
        subtotal = round(random.uniform(3000, 150000), 0)
        discount = round(random.uniform(0, subtotal * 0.05), 0)
        tax = round((subtotal - discount) * 0.05, 0)
        freight = round(random.uniform(0, 1500), 0)
        total = subtotal - discount + tax + freight
        GR_LIST.append((gr_no, po_no))
        docs.append({
            "_key": make_key("GR48", i), "_ragicId": f"GR48-{pad(i)}", "table_id": "ERP_48",
            "1023120": gr_no, "1023121": vendor["code"], "1023122": vendor["name"],
            "1023124": po_no, "1023125": f"RECV{random.randint(1,9999):04d}",
            "1023126": date, "1023130": random.randint(1, 500), "1023131": random.randint(1, 500),
            "1023132": random.choice(UNITS), "1023133": round(random.uniform(50, 3000), 2),
            "1023134": round(random.uniform(5000, 100000), 2),
            "1023135": fake.bothify("??###"), "1023136": rand_date(),
            "1023151": date[:7], "1023153": 0, "1023154": random.randint(0, 50),
            "1024656": subtotal, "1024657": discount,
            "1024658": round(discount / subtotal * 100, 1) if subtotal > 0 else 0,
            "1024659": fake.sentence(nb_words=4), "1024660": random.choice(TAX_TYPES),
            "1024661": 5, "1024662": tax, "1024663": freight, "1024664": total,
            "1024665": f"INV{random.randint(100000, 999999)}",
            "1021011": random.choice(["未進貨完成","已進貨完成"]),
            "105": date, "109": date, "created_at": TS, "updated_at": TS,
        })
    return docs


def gen_returns(n):
    docs = []
    for i in range(1, n+1):
        ret_no = f"RET{pad(i,6)}"
        gr_pair = random.choice(GR_LIST) if GR_LIST else (f"GR{random.randint(1,999):06d}", f"PO{random.randint(1,999):06d}")
        gr_no, po_no = gr_pair
        vendor = random.choice(VENDORS)
        date = rand_date()
        return_qty = random.randint(1, 100)
        unit_price = round(random.uniform(50, 3000), 2)
        RETURN_LIST.append((ret_no, gr_no, po_no))
        docs.append({
            "_key": make_key("RET52", i), "_ragicId": f"RET52-{pad(i)}", "table_id": "ERP_52",
            "1023200": ret_no, "1023201": date, "1023202": gr_no, "1023203": po_no,
            "1023204": vendor["code"], "1023205": vendor["name"],
            "1023206": random.choice(EMPLOYEES)["code"], "1023207": random.choice(EMPLOYEES)["name"],
            "1023208": return_qty, "1023209": random.choice(UNITS),
            "1023210": unit_price, "1023211": return_qty * unit_price,
            "1023212": random.choice(["品質問題","數量不符","規格錯誤","其他"]),
            "1023213": fake.sentence(nb_words=6),
            "1023214": random.choice(["待處理","已退貨","已退款","已沖帳"]),
            "105": date, "109": date, "created_at": TS, "updated_at": TS,
        })
    return docs


def gen_sales_orders(n):
    docs = []
    for i in range(1, n+1):
        so_no = f"SO{pad(i,6)}"
        customer = random.choice(VENDORS)
        emp = random.choice(EMPLOYEES)
        date = rand_date()
        delivery = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=random.randint(14, 90))).strftime("%Y-%m-%d")
        subtotal = round(random.uniform(2000, 100000), 0)
        discount = round(random.uniform(0, subtotal * 0.08), 0)
        tax = round((subtotal - discount) * 0.05, 0)
        SO_LIST.append((so_no, customer["code"]))
        q_ref = random.choice(QUOTE_LIST)[0] if (random.random() < 0.6 and QUOTE_LIST) else ""
        docs.append({
            "_key": make_key("SO26", i), "_ragicId": f"SO26-{pad(i)}", "table_id": "ERP_26",
            "1019100": rand_date_yyyymmdd(), "1019101": so_no, "1019102": date,
            "1019115": customer["code"], "1019116": customer["name"],
            "1019117": fake.numerify("########"),
            "1019120": emp["code"], "1019122": emp["name"],
            "1019124": customer.get("payment", random.choice(PAYMENT_TERMS)),
            "1019126": fake.phone_number(), "1019128": fake.email(), "1019129": fake.address()[:50],
            "1019130": random.randint(1, 50), "1019131": random.randint(1, 50),
            "1019132": random.choice(UNITS),
            "1019133": round(random.uniform(20, 2000), 2), "1019134": round(random.uniform(1000, 50000), 2),
            "1019135": random.randint(0, 100), "1019136": round(random.uniform(0, 1000), 2),
            "1019137": round(random.uniform(0, 500), 0), "1019138": round(random.uniform(1000, 55000), 2),
            "1019139": random.choice(TAX_TYPES), "1019140": 5, "1019142": fake.sentence(nb_words=5),
            "1019143": delivery, "1019144": q_ref,
            "1019145": random.choice(["待出貨","已出貨","部分出貨","已結案"]),
            "105": date, "109": date, "created_at": TS, "updated_at": TS,
        })
    return docs


def gen_production_demand(n):
    docs = []
    for i in range(1, n+1):
        pd_no = f"PD{pad(i,6)}"
        so_pair = random.choice(SO_LIST) if SO_LIST else (f"SO{random.randint(1,999):06d}", "CUST001")
        so_no = so_pair[0]
        emp = random.choice(EMPLOYEES)
        date = rand_date()
        req_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=random.randint(7, 30))).strftime("%Y-%m-%d")
        PD_LIST.append((pd_no, so_no))
        item = random.choice(PRODUCT_ITEMS) if PRODUCT_ITEMS else random.choice(ITEMS)
        docs.append({
            "_key": make_key("PD57", i), "_ragicId": f"PD57-{pad(i)}", "table_id": "ERP_57",
            "1023300": pd_no, "1023301": date, "1023302": req_date,
            "1023303": so_no, "1023304": so_pair[1],
            "1023305": item["code"], "1023306": item["name"],
            "1023307": random.randint(10, 500), "1023308": item["unit"],
            "1023309": round(random.uniform(1000, 50000), 2),
            "1023310": random.choice(["備料中","已排程","已發放","已完工"]),
            "1023311": emp["code"], "1023312": emp["name"],
            "1023313": fake.sentence(nb_words=4),
            "1023314": random.choice(PRODUCTION_TYPES),
            "1023315": rand_date(), "1023316": rand_date(),
            "105": date, "109": date, "created_at": TS, "updated_at": TS,
        })
    return docs


def gen_mrp(n):
    docs = []
    for i in range(1, n+1):
        mrp_no = f"MRP{pad(i,6)}"
        pd_pair = random.choice(PD_LIST) if PD_LIST else (f"PD{random.randint(1,999):06d}", f"SO{random.randint(1,999):06d}")
        pd_no, so_no = pd_pair
        date = rand_date()
        req_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=random.randint(5, 20))).strftime("%Y-%m-%d")
        MRP_LIST.append((mrp_no, pd_no))
        docs.append({
            "_key": make_key("MRP58", i), "_ragicId": f"MRP58-{pad(i)}", "table_id": "ERP_58",
            "1023400": mrp_no, "1023401": date, "1023402": req_date,
            "1023403": pd_no, "1023404": so_no,
            "1023405": random.choice(ITEMS)["code"], "1023406": random.choice(ITEMS)["name"],
            "1023407": random.randint(5, 300), "1023408": random.choice(UNITS),
            "1023409": round(random.uniform(100, 10000), 2), "1023410": round(random.uniform(500, 50000), 2),
            "1023411": random.choice(["庫存不足","備料中","已滿足","已分配"]),
            "1023412": random.choice(ITEMS)["code"], "1023413": random.randint(0, 200),
            "1023414": random.randint(0, 200), "1023415": fake.sentence(nb_words=4),
            "1023416": random.choice(["採購","庫存","調撥","委外"]),
            "1023417": rand_date(),
            "105": date, "109": date, "created_at": TS, "updated_at": TS,
        })
    return docs


def gen_purchase_budgets(n):
    docs = []
    for i in range(1, n+1):
        budget_no = f"BUD{pad(i,6)}"
        mrp_pair = random.choice(MRP_LIST) if MRP_LIST else (f"MRP{random.randint(1,999):06d}", f"PD{random.randint(1,999):06d}")
        mrp_no, pd_no = mrp_pair
        date = rand_date()
        budget_amt = round(random.uniform(5000, 100000), 0)
        BUDGET_LIST.append((budget_no, mrp_no, pd_no))
        docs.append({
            "_key": make_key("BUD71", i), "_ragicId": f"BUD71-{pad(i)}", "table_id": "ERP_71",
            "1023500": budget_no, "1023501": date, "1023502": mrp_no, "1023503": pd_no,
            "1023504": random.choice(VENDORS)["code"], "1023505": random.choice(VENDORS)["name"],
            "1023506": budget_amt, "1023507": round(random.uniform(0, budget_amt * 0.2), 0),
            "1023508": round(budget_amt * 0.05, 0), "1023509": round(budget_amt * 1.05, 0),
            "1023510": random.choice(["已核准","審核中","已駁回","已超支"]),
            "1023511": random.choice(EMPLOYEES)["code"], "1023512": random.choice(EMPLOYEES)["name"],
            "1023513": rand_date(), "1023514": rand_date(),
            "1023515": fake.sentence(nb_words=4),
            "105": date, "109": date, "created_at": TS, "updated_at": TS,
        })
    return docs


def gen_production_orders(n):
    docs = []
    for i in range(1, n+1):
        wo_no = f"MFG{pad(i,6)}"
        pd_pair = random.choice(PD_LIST) if PD_LIST else (f"PD{random.randint(1,999):06d}", f"SO{random.randint(1,999):06d}")
        pd_no, so_no = pd_pair
        item = random.choice(PRODUCT_ITEMS) if PRODUCT_ITEMS else random.choice(ITEMS)
        date = rand_date()
        start = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d")
        end = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=random.randint(3, 20))).strftime("%Y-%m-%d")
        WO_LIST.append((wo_no, pd_no))
        docs.append({
            "_key": make_key("MFG55", i), "_ragicId": f"MFG55-{pad(i)}", "table_id": "ERP_55",
            "1017704": wo_no, "1017705": date, "1017706": pd_no, "1017707": so_no,
            "1017708": item["code"], "1017709": item["name"],
            "1017710": random.randint(10, 500), "1017711": item["unit"],
            "1017712": start, "1017713": end,
            "1017714": random.choice(["計劃中","已發放","已開工","已完工","已結案"]),
            "1017715": random.choice(["本廠","委外"]),
            "1017716": random.randint(80, 120),
            "1017717": round(random.uniform(1000, 50000), 2),
            "1017718": round(random.uniform(500, 20000), 2),
            "1017719": round(random.uniform(0, 5000), 2),
            "1017720": fake.sentence(nb_words=4),
            "1017721": random.choice(EMPLOYEES)["code"], "1017722": random.choice(EMPLOYEES)["name"],
            "1017723": rand_date(), "1017724": rand_date(),
            "105": date, "109": date, "created_at": TS, "updated_at": TS,
        })
    return docs


def gen_pick_lists(n):
    docs = []
    for i in range(1, n+1):
        pick_no = f"PK{pad(i,6)}"
        wo_pair = random.choice(WO_LIST) if WO_LIST else (f"MFG{random.randint(1,999):06d}", f"PD{random.randint(1,999):06d}")
        wo_no, pd_no = wo_pair
        date = rand_date()
        PICK_LIST.append((pick_no, wo_no))
        docs.append({
            "_key": make_key("PK42", i), "_ragicId": f"PK42-{pad(i)}", "table_id": "ERP_42",
            "1017456": pick_no, "1017457": date, "1017458": wo_no, "1017459": pd_no,
            "1017460": random.randint(1, 200), "1017461": random.choice(UNITS),
            "1017462": random.randint(1, 200), "1017463": random.choice(UNITS),
            "1017464": round(random.uniform(500, 10000), 2), "1017465": round(random.uniform(500, 10000), 2),
            "1017466": random.choice(EMPLOYEES)["code"], "1017467": random.choice(EMPLOYEES)["name"],
            "1017468": random.choice(["未領料","部分領料","已領料"]),
            "1017469": rand_date(), "1017470": rand_date(),
            "1017471": fake.sentence(nb_words=4),
            "1017472": random.choice(PRODUCTION_TYPES),
            "1017473": random.choice(WAREHOUSES)["code"], "1017474": random.choice(WAREHOUSES)["name"],
            "105": date, "109": date, "created_at": TS, "updated_at": TS,
        })
    return docs


def gen_dispatch_orders(n):
    docs = []
    for i in range(1, n+1):
        dispatch_no = f"DIS{pad(i,6)}"
        wo_pair = random.choice(WO_LIST) if WO_LIST else (f"MFG{random.randint(1,999):06d}", f"PD{random.randint(1,999):06d}")
        wo_no, pd_no = wo_pair
        date = rand_date()
        st = f"{random.randint(6, 18):02d}:{random.choice(['00','30'])}"
        et = f"{random.randint(8, 20):02d}:{random.choice(['00','30'])}"
        DISPATCH_LIST.append((dispatch_no, wo_no))
        item = random.choice(PRODUCT_ITEMS) if PRODUCT_ITEMS else random.choice(ITEMS)
        docs.append({
            "_key": make_key("DIS44", i), "_ragicId": f"DIS44-{pad(i)}", "table_id": "ERP_44",
            "1023600": dispatch_no, "1023601": date, "1023602": wo_no, "1023603": pd_no,
            "1023604": item["code"], "1023605": item["name"],
            "1023606": random.randint(10, 500), "1023607": item["unit"],
            "1023608": st, "1023609": et,
            "1023610": round(random.uniform(8, 12), 1),
            "1023611": round(random.uniform(500, 5000), 2),
            "1023612": random.choice(EMPLOYEES)["code"], "1023613": random.choice(EMPLOYEES)["name"],
            "1023614": random.choice(EMPLOYEES)["code"], "1023615": random.choice(EMPLOYEES)["name"],
            "1023616": random.choice(WORK_SHIFT),
            "1023617": random.choice(["計劃中","已派工","已完成","已取消"]),
            "1023618": round(random.uniform(100, 2000), 2),
            "1023619": fake.sentence(nb_words=4),
            "105": date, "109": date, "created_at": TS, "updated_at": TS,
        })
    return docs


def gen_qc_records(n):
    docs = []
    for i in range(1, n+1):
        qc_no = f"QC{pad(i,6)}"
        gr_pair = random.choice(GR_LIST) if GR_LIST else (f"GR{random.randint(1,999):06d}", f"PO{random.randint(1,999):06d}")
        gr_no, po_no = gr_pair
        date = rand_date()
        inspect_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=random.randint(0, 3))).strftime("%Y-%m-%d")
        qty_total = random.randint(80, 500)
        qty_fail = random.randint(0, 20)
        qty_pass = qty_total - qty_fail
        QC_LIST.append((qc_no, gr_no, po_no))
        docs.append({
            "_key": make_key("QC51", i), "_ragicId": f"QC51-{pad(i)}", "table_id": "ERP_51",
            "1023700": qc_no, "1023701": inspect_date, "1023702": gr_no, "1023703": po_no,
            "1023704": random.choice(ITEMS)["code"], "1023705": random.choice(ITEMS)["name"],
            "1023706": qty_total, "1023707": qty_pass, "1023708": qty_fail,
            "1023709": round(qty_pass / qty_total * 100, 1) if qty_total > 0 else 100,
            "1023710": random.choice(QC_RESULTS),
            "1023711": random.choice(EMPLOYEES)["code"], "1023712": random.choice(EMPLOYEES)["name"],
            "1023713": fake.sentence(nb_words=4), "1023714": rand_date(), "1023715": rand_date(),
            "1023716": random.choice(["AQL","全檢","抽檢"]), "1023717": fake.bothify("??####"),
            "105": inspect_date, "109": inspect_date, "created_at": TS, "updated_at": TS,
        })
    return docs


def gen_finished_goods(n):
    docs = []
    for i in range(1, n+1):
        fg_no = f"FG{pad(i,6)}"
        wo_pair = random.choice(WO_LIST) if WO_LIST else (f"MFG{random.randint(1,999):06d}", f"PD{random.randint(1,999):06d}")
        wo_no, pd_no = wo_pair
        date = rand_date()
        in_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=random.randint(0, 2))).strftime("%Y-%m-%d")
        qty = random.randint(10, 200)
        item = random.choice(PRODUCT_ITEMS) if PRODUCT_ITEMS else random.choice(ITEMS)
        wh = random.choice(WAREHOUSES)
        FG_LIST.append((fg_no, wo_no, pd_no))
        docs.append({
            "_key": make_key("FG63", i), "_ragicId": f"FG63-{pad(i)}", "table_id": "ERP_63",
            "1023800": fg_no, "1023801": in_date, "1023802": wo_no, "1023803": pd_no,
            "1023804": item["code"], "1023805": item["name"],
            "1023806": qty, "1023807": item["unit"],
            "1023808": round(item["price"] * qty * random.uniform(0.8, 1.2), 2),
            "1023809": wh["code"], "1023810": wh["name"],
            "1023811": random.choice(["待入庫","已入庫","已封存"]),
            "1023812": random.choice(EMPLOYEES)["code"], "1023813": random.choice(EMPLOYEES)["name"],
            "1023814": fake.bothify("??####"), "1023815": rand_date(), "1023816": rand_date(),
            "1023817": fake.sentence(nb_words=4),
            "105": in_date, "109": in_date, "created_at": TS, "updated_at": TS,
        })
    return docs


def main():
    all_docs = []
    gen_master()
    rfqs = gen_rfq(30); all_docs.extend(rfqs)
    quotes = gen_quotations(40); all_docs.extend(quotes)
    pos = gen_purchase_orders(100); all_docs.extend(pos)
    gres = gen_goods_receipts(120); all_docs.extend(gres)
    rets = gen_returns(20); all_docs.extend(rets)
    sos = gen_sales_orders(80); all_docs.extend(sos)
    pds = gen_production_demand(60); all_docs.extend(pds)
    mrps = gen_mrp(60); all_docs.extend(mrps)
    budgets = gen_purchase_budgets(40); all_docs.extend(budgets)
    mos = gen_production_orders(50); all_docs.extend(mos)
    picks = gen_pick_lists(50); all_docs.extend(picks)
    dispatches = gen_dispatch_orders(80); all_docs.extend(dispatches)
    qcs = gen_qc_records(60); all_docs.extend(qcs)
    fgs = gen_finished_goods(50); all_docs.extend(fgs)

    table_counts = {}
    for d in all_docs:
        tid = d.get("table_id", "?")
        table_counts[tid] = table_counts.get(tid, 0) + 1

    print("=" * 60)
    print("採購-訂單-生產 全流程模擬資料生成")
    print("=" * 60)
    print(f"\n總筆數: {len(all_docs)}")
    for tid, cnt in sorted(table_counts.items()):
        print(f"  {tid}: {cnt}")

    print("\n寫入 da_table_data_ragic...")
    insert_batch("logistics", all_docs)

    r = subprocess.run(
        ["curl", "-s", "-u", AUTH,
         f"{ARANGO_URL}/_db/{DB}/_api/cursor",
         "-X", "POST", "-H", "Content-Type: application/json",
         "-d", json.dumps({"query": "RETURN LENGTH(FOR d IN da_table_data_ragic RETURN d)"})],
        capture_output=True, text=True)
    try:
        count = json.loads(r.stdout)["result"][0]
        print(f"\n✓ da_table_data_ragic: {count} 筆")
    except:
        print("\n✓ 寫入完成")

    print("\n" + "=" * 60)
    print("關聯鏈路摘要")
    print("=" * 60)
    chains = [
        ("RFQ_LIST", RFQ_LIST[:3]),
        ("QUOTE_LIST", QUOTE_LIST[:3]),
        ("PO_LIST (po_no, vendor_code)", PO_LIST[:3]),
        ("GR_LIST (gr_no, po_no)", GR_LIST[:3]),
        ("RETURN_LIST (ret_no, gr_no, po_no)", RETURN_LIST[:3]),
        ("SO_LIST (so_no, customer_code)", SO_LIST[:3]),
        ("PD_LIST (pd_no, so_no)", PD_LIST[:3]),
        ("MRP_LIST (mrp_no, pd_no)", MRP_LIST[:3]),
        ("BUDGET_LIST (budget_no, mrp_no, pd_no)", BUDGET_LIST[:3]),
        ("WO_LIST (wo_no, pd_no)", WO_LIST[:3]),
        ("PICK_LIST (pick_no, wo_no)", PICK_LIST[:3]),
        ("DISPATCH_LIST (dispatch_no, wo_no)", DISPATCH_LIST[:3]),
        ("QC_LIST (qc_no, gr_no, po_no)", QC_LIST[:3]),
        ("FG_LIST (fg_no, wo_no, pd_no)", FG_LIST[:3]),
    ]
    for name, items in chains:
        print(f"\n  {name}:")
        for item in items:
            print(f"    {item}")


if __name__ == "__main__":
    main()
