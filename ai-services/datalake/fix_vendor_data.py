#!/usr/bin/env python3
"""Fix vendor data field IDs in da_table_data_ragic.

The faker script used wrong field IDs for CONFIGURATIONFILE_10.
This script:
1. Deletes existing vendor records
2. Generates 50 vendors with CORRECT field IDs from da_field_info_ragic
3. Inserts corrected data
"""
import random
import httpx

ARANGO_URL = "http://localhost:8529"
ARANGO_DB = "abc_desktop"
AUTH = ("root", "abc_desktop_2026")

START_DATE = "2025-10-01"
END_DATE = "2026-04-01"

N_VENDOR = 50

CUSTOMER_TYPES = ["經銷商", "直客", "餐飲", "食品加工"]
VENDOR_TYPES = ["製造商", "代理商", "經銷商"]
VENDOR_STATUSES = ["交易中", "交易中", "交易中", "評估中"]
CURRENCIES = ["TWD", "USD", "CNY"]
PAYMENT_TERMS = ["月結30天", "月結45天", "月結60天", "現結", "票期30天"]

industry_names = [
    "食品", "包裝", "生技", "化工", "物流", "機械", "紡織", "水產",
    "蔬果", "肉品", "乳品", "烘焙", "餐飲",
]
cities = ["台北市", "新北市", "桃園市", "台中市", "台南市", "高雄市",
          "新竹縣", "彰化縣", "屏東縣", "宜蘭縣"]
districts = ["中正區", "大同區", "中山區", "松山區", "萬華區",
             "大安區", "北投區", "士林區", "內湖區", "南港區"]

# Simple fake generator (no faker dependency)
_first_names = ["志明", "淑芬", "雅婷", "家豪", "怡君", "承翰", "詩涵", "宥廷",
                "欣怡", "宇軒", "語彤", "柏宇", "于萱", "建豪", "依宸", "晉安"]
_last_names = ["張", "王", "李", "陳", "劉", "楊", "黃", "周", "吳", "徐",
               "孫", "胡", "朱", "高", "林", "何", "郭", "馬", "羅", "梁"]
_domains = ["gmail.com", "yahoo.com.tw", "hotmail.com", "company.org", "example.com"]


def seq(prefix: str, i: int) -> str:
    return f"{prefix}{i:05d}"


def fake_name() -> str:
    return random.choice(_first_names) + random.choice(_last_names)


def fake_email() -> str:
    return f"{fake_name()[:2]}{random.randint(10, 99)}@{random.choice(_domains)}"


def fake_phone() -> str:
    return f"09{random.randint(10000000, 99999999)}"


def fake_address() -> str:
    return f"{random.choice(districts)}{random.choice(['中山路', '中華路', '民生路', '成功路', '和平路'])}{random.randint(1, 999)}號"


def gen_date() -> str:
    from datetime import date, timedelta
    start = date.fromisoformat(START_DATE)
    end = date.fromisoformat(END_DATE)
    delta = (end - start).days
    return str(start + timedelta(days=random.randint(0, delta)))


def generate_vendors() -> list[dict]:
    vendors = []
    for i in range(N_VENDOR):
        is_vendor = random.random() > 0.2
        is_customer = random.random() > 0.6
        vendor_ragic = f"CFG10-{i + 1:04d}"
        city = random.choice(cities)
        district = random.choice(districts)

        d = {
            "_key": f"CFG10_{i + 1:04d}",
            "_ragicId": vendor_ragic,
            "table_id": "CONFIGURATIONFILE_10",
            "1015575": vendor_ragic,
            "1015576": vendor_ragic,
            "1015577": seq("VND", i + 1),
            "1015578": random.choice(industry_names) + random.choice(["有限公司", "股份有限公司", "商行"]),
            "1015579": random.choice(industry_names) + random.choice(["企業", "實業", "股份"])[:15] if random.random() > 0.3 else None,
            "1015581": f"{random.randint(10000000, 99999999)}",
            "1015582": fake_email(),
            "1015583": fake_phone(),
            "1015584": fake_phone() if random.random() > 0.5 else None,
            "1015589": fake_name(),
            "1015590": f"www.{random.choice(['company', 'corp', 'biz'])}.com.tw" if random.random() > 0.5 else None,
            "1015593": f"TF{random.randint(100000, 999999)}",
            "1015594": None,
            "1015598": is_customer,
            "1015599": is_vendor,
            "1015604": fake_name(),
            "1015605": fake_phone(),
            "1015606": fake_phone() if random.random() > 0.5 else None,
            "1015608": city,
            "1015609": district,
            "1015610": f"{city}{district}{fake_address()}",
            "1015611": random.choice(["業務部", "採購部", "管理部"]),
            "1015626": random.choice(VENDOR_STATUSES),
            "1015627": random.choice(industry_names),
            "1015631": random.choice(PAYMENT_TERMS),
            "1015634": random.choice(["現金", "轉帳", "票據"]),
            "1015638": random.choice(CURRENCIES),
            "1015639": random.choice(["應稅", "免稅"]),
            "1015640": round(random.uniform(0, 0.1), 4),
            "1015641": random.choice(["二聯式發票", "三聯式發票"]),
            "1015643": random.choice(["EXW", "FOB", "CIF", "DDP"]),
            "1015647": f"備註-{i+1}" if random.random() > 0.7 else None,
            "1016116": fake_email(),
            "1016481": city,
            "1016482": district,
            "1019926": random.choice(CUSTOMER_TYPES) if is_customer else None,
            "1019994": random.choice(VENDOR_TYPES) if is_vendor else None,
            "105": gen_date(),
            "109": gen_date(),
        }
        vendors.append(d)
    return vendors


def arango_upsert(docs: list[dict]) -> int:
    count = 0
    async def _upsert():
        nonlocal count
        async with httpx.AsyncClient(timeout=30.0) as client:
            for doc in docs:
                doc_key = doc.get("_key", "")
                try:
                    response = await client.post(
                        f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/da_table_data_ragic?overwrite=true",
                        json=doc,
                        auth=AUTH,
                    )
                    if response.status_code in (200, 201, 202):
                        count += 1
                except Exception as e:
                    print(f"  Error upserting {doc_key}: {e}")
    import asyncio
    asyncio.run(_upsert())
    return count


def delete_vendors() -> int:
    deleted = 0
    async def _delete():
        nonlocal deleted
        async with httpx.AsyncClient(timeout=30.0) as client:
            cursor_resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={
                    "query": "FOR d IN da_table_data_ragic FILTER d.table_id == @tid REMOVE d IN da_table_data_ragic RETURN d._key",
                    "bindVars": {"tid": "CONFIGURATIONFILE_10"},
                },
                auth=AUTH,
            )
            result = cursor_resp.json()
            deleted = len(result.get("result", []))
    import asyncio
    asyncio.run(_delete())
    return deleted


def main():
    print("=" * 60)
    print("Fix VENDOR data — correct field IDs")
    print("=" * 60)

    print("\n§1 Deleting existing vendor records...")
    deleted = delete_vendors()
    print(f"  Deleted: {deleted} records")

    print("\n§2 Generating 50 vendors with correct field IDs...")
    vendors = generate_vendors()
    print(f"  Generated: {len(vendors)} vendors")

    print("\n§3 Inserting corrected data into ArangoDB...")
    count = arango_upsert(vendors)
    print(f"  Inserted: {count} records")

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
