#!/usr/bin/env python3
"""
@file        generate_ragic_fake_data.py
@description Ragic Phase 1 假資料產生器
              產生 CSV Parquet 格式資料 + 寫入 ArangoDB _ragic Collections。
              資料時間範圍：最近半年（2025-10-01 ~ 2026-04-02）
@lastUpdate  2026-04-02 09:30:00
@author      Daniel Chung
@version     1.0.0
"""

import csv
import json
import random
import subprocess
import uuid
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

fake = Faker("zh_TW")

# ============================================================================
# Config
# ============================================================================

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = "root:abc_desktop_2026"
OUTPUT_DIR = Path("/Users/daniel/GitHub/AIBox/.tmp/ragic_fake_data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 資料量設定
N_DEPT = 20
N_WAREHOUSE = 10
N_LOCATION_PER_WH = 50
N_EMPLOYEE = 100
N_ITEM = 500
N_VENDOR = 30
N_PO = 1000  # 最近半年的進貨單

# 時間範圍（最近半年）
END_DATE = date(2026, 4, 2)
START_DATE = date(2025, 10, 1)

TS = "2026-04-02T00:00:00Z"


# ============================================================================
# Helpers
# ============================================================================


def curl(method: str, path: str, data: str | None = None) -> dict:
    cmd = [
        "curl", "-s", "-u", AUTH,
        f"{ARANGO_URL}/_db/{DB}/{path}",
        "-X", method,
        "-H", "Content-Type: application/json",
    ]
    if data:
        cmd += ["-d", data]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"raw": r.stdout, "stderr": r.stderr}


def arango_upsert(collection: str, docs: list, batch_size: int = 200) -> dict:
    """Bulk upsert to ArangoDB — batched to avoid curl argument limit."""
    results = []
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i + batch_size]
        payload = json.dumps(batch)
        results.append(curl("POST", f"_api/document/{collection}?overwriteMode=replace", payload))
    return results


def gen_date(start: date, end: date) -> str:
    """Generate random date between start and end."""
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, delta))).isoformat()


def seq(prefix: str, n: int, width: int = 3) -> str:
    return f"{prefix}-{str(n).zfill(width)}"


# ============================================================================
# §1 CFG2_DEPT (組織部門)
# ============================================================================

def gen_departments() -> list[dict]:
    """
    產生 20 個部門。
    - 上級部門形成樹狀結構（Level 0: 3 個顶层部門，Level 1: 每個顶层部門下 3~5 個子部門）
    - Level 2: 剩餘為基層部門
    """
    depts = []
    dept_keys = []  # (ragicId, 1015391_code)

    # Level 0: 3 個顶层部門
    top_names = ["管理部", "生產部", "業務部"]
    for i, name in enumerate(top_names):
        d = {
            "_key": f"CFG2_{i + 1:03d}",
            "_ragicId": f"CFG2-{i + 1:03d}",
            "1015395": "ORG",
            "1015391": seq("DEPT", i + 1),
            "1015392": name,
            "1022588": None,
            "1015394": "組織部門建檔",
            "105": gen_date(START_DATE, END_DATE),
            "109": gen_date(START_DATE, END_DATE),
        }
        depts.append(d)
        dept_keys.append((d["_ragicId"], d["1015391"]))

    # Level 1: 每個顶层部門下 3~5 個子部門
    child_idx = len(top_names) + 1
    for top_idx in range(3):
        top_ragic, top_code = dept_keys[top_idx]
        n_children = random.randint(3, 5)
        for j in range(n_children):
            name = fake.word(ext_word_list=["研發組", "品質組", "倉管組", "採購組",
                                           "人資組", "財務組", "資訊組", "業務組",
                                           "生技組", "品保組", "包裝組", "物流組"])
            d = {
                "_key": f"CFG2_{child_idx:03d}",
                "_ragicId": f"CFG2-{child_idx:03d}",
                "1015395": "ORG",
                "1015391": seq("DEPT", child_idx),
                "1015392": f"{top_code} {name}",
                "1022588": top_ragic,
                "1015394": "組織部門建檔",
                "105": gen_date(START_DATE, END_DATE),
                "109": gen_date(START_DATE, END_DATE),
            }
            depts.append(d)
            dept_keys.append((d["_ragicId"], d["1015391"]))
            child_idx += 1

    # Level 2: 剩餘為基層部門
    while len(depts) < N_DEPT:
        parent = random.choice(dept_keys[:3])  # 掛在顶层部門下
        name = fake.word(ext_word_list=["工場", "班", "組", "課"])
        d = {
            "_key": f"CFG2_{child_idx:03d}",
            "_ragicId": f"CFG2-{child_idx:03d}",
            "1015395": "ORG",
            "1015391": seq("DEPT", child_idx),
            "1015392": f"{parent[1]} {name}",
            "1022588": parent[0],
            "1015394": "組織部門建檔",
            "105": gen_date(START_DATE, END_DATE),
            "109": gen_date(START_DATE, END_DATE),
        }
        depts.append(d)
        dept_keys.append((d["_ragicId"], d["1015391"]))
        child_idx += 1

    return depts


# ============================================================================
# §2 CFG3_WAREHOUSE (倉儲位管理)
# ============================================================================

def gen_warehouses() -> list[dict]:
    """產生 N_WAREHOUSE 個倉庫。"""
    warehouses = []
    wh_names = ["台北倉庫", "桃園倉庫", "台中倉庫", "台南倉庫", "高雄倉庫",
                "新竹倉庫", "彰化倉庫", "嘉義倉庫", "屏東倉庫", "宜蘭倉庫"]
    for i in range(N_WAREHOUSE):
        d = {
            "_key": f"CFG3_{i + 1:03d}",
            "_ragicId": f"CFG3-{i + 1:03d}",
            "1015396": "WH",
            "1015398": seq("WH", i + 1),
            "1015397": wh_names[i] if i < len(wh_names) else f"倉庫{i + 1}",
            "1015399": "倉儲建檔",
            "105": gen_date(START_DATE, END_DATE),
            "109": gen_date(START_DATE, END_DATE),
        }
        warehouses.append(d)
    return warehouses


def gen_locations(warehouses: list[dict]) -> list[dict]:
    """為每個倉庫產生 N_LOCATION_PER_WH 個儲位。"""
    locations = []
    loc_idx = 1
    rack_names = ["A", "B", "C", "D", "E", "F", "G", "H"]
    for wh in warehouses:
        for i in range(N_LOCATION_PER_WH):
            rack = rack_names[i % len(rack_names)]
            shelf = (i // len(rack_names)) + 1
            d = {
                "_key": f"CFG3_LOC_{loc_idx:04d}",
                "_ragicId": f"CFG3-LOC-{loc_idx:04d}",
                "_parent_ragicId": wh["_ragicId"],
                "1015402": str(i + 1),
                "1015403": f"{wh['1015397']}-{rack}-{shelf:02d}",
                "1015405": str((i // (len(rack_names) * 5)) + 1),
                "1015406": f"料架-{(i // (len(rack_names) * 5)) + 1}",
                "1015407": wh["1015397"],
                "1015408": wh["1015398"],
                "1016686": fake.ean8(),
                "1015401": f"{wh['1015398']}-{rack}{shelf:02d}",
                "1020233": f"{wh['1015398']}-{rack}{shelf:02d}",
                "1015404": f"{rack}{shelf:02d}",
                "1020234": f"{rack}{shelf:02d}",
            }
            locations.append(d)
            loc_idx += 1
    return locations


# ============================================================================
# §3 CFG7_EMPLOYEE (員工管理)
# ============================================================================

GENDERS = ["男", "女"]
EDUCATIONS = ["高中職", "專科", "大學", "碩士", "博士"]
EMPLOYEE_TYPES = ["正職", "約聘", "工讀生", "兼職"]
SALARY_TYPES = ["月薪", "日薪", "時薪"]
STATUSES = ["在職", "在職", "在職", "留職停薪"]  # 在職比例高
PAYMENT_METHODS = ["匯款", "匯款", "匯款", "領現"]
IS_RETIRE = ["是", "否"]


def gen_employees(depts: list[dict]) -> list[dict]:
    """
    產生 N_EMPLOYEE 個員工，FK 部門隨機選擇。
    """
    employees = []
    first_names = ["志明", "雅婷", "家豪", "欣怡", "承翰", "怡君", "柏宇", "雅筑",
                   "彥廷", "思穎", "宥廷", "雨萱", "睿庭", "品妤", "宥勝", "怡萱",
                   "辰昕", "妤安", "宥辰", "苡甯", "語希", "星宇", "品妍", "沂真"]
    last_names = ["王", "李", "張", "劉", "陳", "楊", "黃", "吳", "林", "周",
                  "江", "郭", "何", "高", "蕭", "羅", "簡", "朱", "徐", "馬"]

    banks = [
        ("008", "華南銀行"), ("005", "彰化銀行"), ("007", "第一銀行"),
        ("012", "台北富邦"), ("013", "國泰世華"), ("822", "中國信託"),
        ("809", "凱基銀行"), ("815", "兆豐銀行"), ("017", "兆豐銀行"),
    ]

    for i in range(N_EMPLOYEE):
        gender = random.choice(GENDERS)
        first = random.choice(first_names)
        last = random.choice(last_names)
        name = last + first
        emp_code = seq("EMP", i + 1)
        emp_ragic = f"CFG7-{i + 1:04d}"
        dept = random.choice(depts)
        status = random.choice(STATUSES)

        hire_date = gen_date(date(2020, 1, 1), date(2025, 12, 31))
        if status == "在職":
            term_date = None
        else:
            term_date = gen_date(date(2025, 10, 1), END_DATE)

        salary = round(random.uniform(28000, 120000), 0)
        dept_agent = random.choice([e["_ragicId"] for e in employees]) if employees else None

        d = {
            "_key": f"CFG7_{i + 1:03d}",
            "_ragicId": emp_ragic,
            "1015427": "EMP",
            "1015428": emp_code,
            "1015429": name,
            "1015430": gender,
            "1015437": fake.phone_number()[:15],
            "1015438": fake.phone_number()[:12],
            "1015439": f"{name.lower().replace(' ', '.')}@company.com",
            "1015443": status,
            "1015444": hire_date,
            "1015445": term_date,
            "1015433": fake.date_of_birth(minimum_age=22, maximum_age=65).isoformat(),
            "1015436": fake.bothify("?????????"),
            "1015440": fake.address(),
            "1015441": fake.address(),
            "1015432": fake.name(),
            "1015434": str(random.randint(22, 65)),
            "1015477": random.choice(EDUCATIONS),
            "1015498": random.choice(EMPLOYEE_TYPES),
            "1015496": random.choice(["工程師", "主管", "助理", "組長", "經理",
                                     "專員", "技術員", "文員", "主任"]),
            "1015480": str(round(random.uniform(0.5, 10), 1)),
            "1015525": f"{random.randint(100, 999)}",
            "1015505": random.choice(SALARY_TYPES),
            "1015506": salary,
            "1015507": random.choice(PAYMENT_METHODS),
            "1015511": random.choice(IS_RETIRE),
            "1015516": random.choice(banks)[0],
            "1015518": random.choice(banks)[1],
            "1015520": fake.credit_card_number()[-10:],
            "1015524": random.choice(["正常", ""]),
            "1015495": dept["_ragicId"],
            "1015494": dept["1015392"],
            "1022594": random.choice(depts)["_ragicId"] if random.random() > 0.5 else None,
            "1022596": random.choice(depts)["_ragicId"] if random.random() > 0.7 else None,
            "1022595": None,
            "1022597": None,
            "1015500": dept_agent,
            "1015501": None,
            "105": hire_date,
            "109": gen_date(START_DATE, END_DATE),
        }
        employees.append(d)
    return employees


# ============================================================================
# §4 CFG10_VENDOR (交易對象)
# ============================================================================

CATEGORIES = ["原材料", "半成品", "成品", "商品", "包裝材", "消耗性材料"]
VENDOR_TYPES = ["原材料", "消耗性材料", "包裝材"]
CUSTOMER_TYPES = ["下游業者", "消費者"]
VENDOR_STATUSES = ["交易中", "交易中", "交易中", "評估中"]
CURRENCIES = ["TWD", "USD", "CNY"]
PAYMENT_TERMS = ["月結30天", "月結45天", "月結60天", "現結", "票期30天"]


def gen_vendors() -> list[dict]:
    """產生 N_VENDOR 個交易對象（供應商/客戶）。"""
    vendors = []
    industry_names = [
        "食品", "包裝", "生技", "科技", "化工", "物流", "機械",
        "紡織", "水產", "蔬果", "肉品", "乳品", "烘焙", "餐飲",
    ]
    cities = ["台北市", "新北市", "桃園市", "台中市", "台南市", "高雄市",
              "新竹縣", "彰化縣", "屏東縣", "宜蘭縣"]
    districts = ["中正區", "大同區", "中山區", "松山區", "萬華區",
                  "大安區", "北投區", "士林區", "內湖區", "南港區"]

    for i in range(N_VENDOR):
        is_vendor = random.random() > 0.2  # 80% 供應商
        is_customer = random.random() > 0.6  # 40% 客戶
        vendor_ragic = f"CFG10-{i + 1:04d}"
        city = random.choice(cities)
        district = random.choice(districts)

        d = {
            "_key": f"CFG10_{i + 1:03d}",
            "_ragicId": vendor_ragic,
            "1015616": vendor_ragic,
            "1015577": seq("VND", i + 1),
            "1015578": random.choice(industry_names) + fake.company_suffix(),
            "1015579": fake.company()[:15] if random.random() > 0.5 else None,
            "1019926": random.choice(CUSTOMER_TYPES) if is_customer else None,
            "1019994": random.choice(VENDOR_TYPES) if is_vendor else None,
            "1015626": random.choice(VENDOR_STATUSES),
            "1015589": fake.name(),
            "1015611": random.choice(["業務部", "採購部", "管理部"]),
            "1015604": fake.name(),
            "1015605": fake.phone_number()[:15],
            "1015581": fake.bothify("########"),
            "1015593": f"TF{random.randint(100000, 999999)}",
            "1015594": None,
            "1016482": city,
            "1016483": district,
            "1016484": f"{city}{district}{fake.street_address()}",
            "1016486": fake.phone_number()[:15],
            "1016487": f"{fake.email()}",
            "1016489": f"www.{fake.domain_name()}",
            "1015599": random.choice(CURRENCIES),
            "1015600": random.choice(PAYMENT_TERMS),
            "1015602": round(random.uniform(100000, 5000000), 0),
            "1015622": random.choice(["正常", ""]),
            "105": gen_date(START_DATE, END_DATE),
            "109": gen_date(START_DATE, END_DATE),
        }
        vendors.append(d)
    return vendors


# ============================================================================
# §5 CFG9_ITEM (品項管理)
# ============================================================================

ITEM_CATEGORIES = ["原料", "半成品", "成品", "商品", "包裝材", "消耗性材料"]
ITEM_UNITS = ["公斤", "公克", "公升", "毫升", "包", "箱", "桶", "罐", "盒", "袋", "個"]
PACK_UNITS = ["g", "kg", "ml", "L"]


def gen_items(vendors: list[dict]) -> list[dict]:
    """產生 N_ITEM 個品項，FK 供應商隨機選擇。"""
    items = []
    product_prefixes = [
        "香蒜", "麻辣", "原味", "芥末", "蔥燒", "椒鹽", "蜜汁", "碳烤",
        "草莓", "芒果", "藍莓", "蘋果", "檸檬", "葡萄", "水蜜桃", "百香果",
        "高麗", "青蔥", "蒜苗", "洋蔥", "番茄", "胡瓜", "南瓜", "茄子",
        "豬肉", "牛肉", "雞肉", "羊肉", "海鮮", "魚肉", "蝦仁", "透抽",
        "奶粉", "砂糖", "麵粉", "奶油", "酵母", "鹽", "胡椒", "香料",
    ]

    for i in range(N_ITEM):
        cat = random.choice(ITEM_CATEGORIES)
        prefix = random.choice(product_prefixes)
        item_ragic = f"CFG9-{i + 1:05d}"
        vendor = random.choice(vendors)
        pack_unit = random.choice(PACK_UNITS)
        pack_weight = round(random.uniform(50, 5000), 0)
        std_price = round(random.uniform(50, 5000), 2)
        tax_price = round(std_price * 1.05, 2)
        cost_price = round(std_price * random.uniform(0.6, 0.8), 2)
        tax_cost = round(cost_price * 1.05, 2)
        safe_stock = round(random.uniform(10, 500), 0)

        d = {
            "_key": f"CFG9_{i + 1:05d}",
            "_ragicId": item_ragic,
            "1015229": seq("ITEM", i + 1),
            "1015486": seq("P", i + 1),
            "1015483": f"{prefix}{cat}{random.choice(['醬', '粉', '膏', '汁', '罐', '包', '袋', '盒'])}",
            "1015225": f"規格：{random.choice(['500', '1000', '2500'])}g / {random.choice(['鋁箔袋', '鐵罐', '玻璃罐', '紙盒'])}",
            "1015223": fake.sentence(nb_words=6)[:100],
            "1015328": f"{seq('P', i + 1)}-00",
            "1015224": f"{prefix} {cat}",
            "1022774": random.choice([prefix, ""]),
            "1016531": cat,
            "1015230": None,
            "1018425": cat,
            "1018426": random.choice(["A級", "B級", "C級", ""]),
            "1018427": str(pack_weight),
            "1018428": pack_unit,
            "1018429": random.choice(ITEM_UNITS),
            "1018430": std_price,
            "1018431": tax_price,
            "1018432": cost_price,
            "1018433": tax_cost,
            "1018434": round(random.uniform(50, 2000), 0),
            "1018435": safe_stock,
            "1018436": f"{seq('P', i + 1)}-00",
            "1018420": vendor["1015577"],
            "1018422": vendor["1015578"],
            "1018437": None,
            "1018439": None,
            "1018440": None,
            "1018441": None,
            "1015423": None,
            "1022528": vendor["_ragicId"],
            "1022529": vendor["1015578"],
            "105": gen_date(START_DATE, END_DATE),
            "109": gen_date(START_DATE, END_DATE),
        }
        items.append(d)
    return items


# ============================================================================
# §6 ERP48_PURCHASE_ORDER (進貨單)
# ============================================================================

PO_STATUSES = ["已進貨完成", "未進貨完成", "已進貨完成", "已進貨完成"]
TAX_TYPES = ["內含", "外加", "不計稅"]
UNIT_LIST = ["公斤", "公克", "公升", "毫升", "包", "箱", "桶", "罐", "盒", "袋", "個"]


def gen_purchase_orders(vendors: list[dict], items: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    產生 N_PO 張進貨單（最近半年）+ 子表明細。
    返回 (po_headers, po_items)
    """
    po_headers = []
    po_items = []

    for i in range(N_PO):
        po_ragic = f"ERP48-{i + 1:06d}"
        vendor = random.choice(vendors)
        po_date = gen_date(START_DATE, END_DATE)

        # 子表明細：2~5 行
        n_lines = random.randint(2, 5)
        subtotal = 0.0
        line_items = []

        for j in range(n_lines):
            item = random.choice(items)
            qty = round(random.uniform(10, 500), 2)
            unit_price = round(random.uniform(50, 3000), 2)
            line_total = round(qty * unit_price, 2)
            subtotal += line_total

            # 有效日期（PO date 後 30~365 天）
            expiry_days = random.randint(30, 365)
            expiry_date = (date.fromisoformat(po_date) + timedelta(days=expiry_days)).isoformat()

            li = {
                "_key": f"ERP48_ITEM_{i + 1:06d}_{j + 1:02d}",
                "_ragicId": f"{po_ragic}-L{j + 1:02d}",
                "_parent_ragicId": po_ragic,
                "1023127": item["1015577"] if item.get("1015577") else None,
                "1023130": qty,
                "1023131": round(qty * random.uniform(0.9, 1.0), 2),
                "1023132": random.choice(UNIT_LIST),
                "1023133": unit_price,
                "1023134": line_total,
                "1023135": fake.ean8(),
                "1023136": expiry_date,
                "1023137": random.choice(["鋁箔袋", "鐵罐", "玻璃罐", "紙盒", "塑膠盒"]),
                "1023138": random.choice(["包", "盒", "罐", "箱"]),
                "1023153": random.choice(["Yes", "No"]),
                "1023154": 0 if random.random() > 0.1 else round(qty * random.uniform(0.01, 0.1), 2),
                "1023151": po_date[:7].replace("-", "/"),
                "1023128": item["1015229"],
                "1023129": item["1015483"],
            }
            line_items.append(li)

        # 折扣
        discount_pct = random.uniform(0, 0.05)
        discount_amt = round(subtotal * discount_pct, 2)
        net_amount = subtotal - discount_amt
        tax_rate = random.choice([0, 0.05, 0.05, 0.05])
        tax_amt = round(net_amount * tax_rate, 2)
        freight = round(random.uniform(0, 2000), 0)
        total = round(net_amount + tax_amt + freight, 2)

        po = {
            "_key": f"ERP48_{i + 1:06d}",
            "_ragicId": po_ragic,
            "1023120": po_ragic,
            "1023123": po_date,
            "1023126": po_date if random.random() > 0.2 else None,
            "1023162": random.choice(PO_STATUSES),
            "1023124": None,
            "1023125": None,
            "1023139": subtotal,
            "1023140": random.choice(TAX_TYPES),
            "1023141": discount_amt,
            "1023142": tax_rate,
            "1023143": round(discount_pct * 100, 2),
            "1023144": tax_amt,
            "1023147": freight,
            "1023148": total,
            "1024650": f"INV{random.randint(100000, 999999)}",
            "1024656": subtotal,
            "1024657": discount_amt,
            "1024658": round(discount_pct * 100, 2),
            "1024660": None,
            "1024661": tax_rate,
            "1024662": tax_amt,
            "1024663": freight,
            "1024664": total,
            "1023121": vendor["1015577"],
            "1023122": vendor["1015578"],
            "105": po_date,
            "109": po_date,
        }
        po_headers.append(po)
        po_items.extend(line_items)

    return po_headers, po_items


# ============================================================================
# §7 CSV Export
# ============================================================================


def write_csv(filename: str, rows: list[dict]) -> None:
    if not rows:
        return
    path = OUTPUT_DIR / filename
    # CSV header = 所有唯一 key（排除 _key, _id, _rev, _parent_ragicId, _ragicId 系統欄位用於參考，保留）
    keys = set()
    for r in rows:
        keys.update(r.keys())
    # 排序：_ragicId, _parent_ragicId, 系統欄位優先
    priority = ["_ragicId", "_parent_ragicId"]
    sorted_keys = priority + sorted(k for k in keys if k not in priority)

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=sorted_keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  CSV: {path} ({len(rows)} rows)")


# ============================================================================
# §8 Main
# ============================================================================

def main():
    print(f"\n{'=' * 60}")
    print("Ragic Phase 1 — 假資料產生器")
    print(f"  時間範圍: {START_DATE} ~ {END_DATE}（最近半年）")
    print(f"  輸出目錄: {OUTPUT_DIR}")
    print(f"{'=' * 60}\n")

    # Phase 1: Master Data（依賴順序）
    print("§1 產生 組織部門 (CFG2_DEPT)...")
    depts = gen_departments()
    print(f"  → {len(depts)} 部門")

    print("\n§2 產生 倉儲位 (CFG3_WAREHOUSE)...")
    warehouses = gen_warehouses()
    locations = gen_locations(warehouses)
    print(f"  → {len(warehouses)} 倉庫 + {len(locations)} 儲位")

    print("\n§3 產生 員工 (CFG7_EMPLOYEE)...")
    employees = gen_employees(depts)
    print(f"  → {len(employees)} 員工")

    print("\n§4 產生 交易對象 (CFG10_VENDOR)...")
    vendors = gen_vendors()
    print(f"  → {len(vendors)} 交易對象")

    print("\n§5 產生 品項 (CFG9_ITEM)...")
    items = gen_items(vendors)
    print(f"  → {len(items)} 品項")

    print("\n§6 產生 進貨單 (ERP48_PURCHASE_ORDER)...")
    po_headers, po_items = gen_purchase_orders(vendors, items)
    print(f"  → {len(po_headers)} 進貨單表頭 + {len(po_items)} 明細行")

    # CSV Export
    print(f"\n{'=' * 60}")
    print("寫出 CSV 檔案...")
    write_csv("cfg2_dept.csv", depts)
    write_csv("cfg3_warehouse.csv", warehouses)
    write_csv("cfg3_location.csv", locations)
    write_csv("cfg7_employee.csv", employees)
    write_csv("cfg10_vendor.csv", vendors)
    write_csv("cfg9_item.csv", items)
    write_csv("erp48_purchase_order.csv", po_headers)
    write_csv("erp48_purchase_order_item.csv", po_items)

    # ArangoDB Upsert
    print(f"\n{'=' * 60}")
    print("寫入 ArangoDB...")

    collections = [
        ("da_table_data_ragic", depts, "部門"),
        ("da_table_data_ragic", warehouses, "倉庫"),
        ("da_table_data_ragic", locations, "儲位"),
        ("da_table_data_ragic", employees, "員工"),
        ("da_table_data_ragic", vendors, "交易對象"),
        ("da_table_data_ragic", items, "品項"),
        ("da_table_data_ragic", po_headers, "進貨單"),
        ("da_table_data_ragic", po_items, "進貨明細"),
    ]

    total_arangodb = 0
    for coll, docs, label in collections:
        if not docs:
            continue
        result = arango_upsert(coll, docs)
        ok_count = len([d for d in docs])
        total_arangodb += ok_count
        print(f"  ✓ {label}: {ok_count} → {coll}")

    print(f"\n{'=' * 60}")
    print("✅ 完成！")
    print(f"  CSV: {OUTPUT_DIR}")
    print(f"  ArangoDB: {total_arangodb} documents → da_table_data_ragic")
    print(f"  部門: {len(depts)} | 倉庫: {len(warehouses)} | 儲位: {len(locations)}")
    print(f"  員工: {len(employees)} | 供應商: {len(vendors)} | 品項: {len(items)}")
    print(f"  進貨單: {len(po_headers)} | 明細: {len(po_items)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
