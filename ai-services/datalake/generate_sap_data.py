#!/usr/bin/env python3
"""
SAP Data Lake Generator - Generate 2 years of fake SAP data as Parquet files.
Writes to SeaWeedFS S3 (s3://sap/{module}/{table}/).

@file        generate_sap_data.py
@description 產生模擬 SAP MM/SD 模組 Parquet 資料湖，供 NL→SQL Pipeline 使用
@lastUpdate  2026-03-23 23:40:00
@author      Daniel Chung
@version     1.1.0
"""
import io
import random
from datetime import datetime, timedelta

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import boto3
from faker import Faker

fake = Faker(['zh_TW', 'en_US'])
Faker.seed(42)
random.seed(42)

S3_ENDPOINT = 'http://localhost:8334'
S3_KEY = 'admin'
S3_SECRET = 'admin123'
BUCKET = 'sap'

s3 = boto3.client(
    's3', endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_KEY, aws_secret_access_key=S3_SECRET,
    region_name='us-east-1',
    config=boto3.session.Config(signature_version='s3v4')
)

NOW = datetime(2026, 3, 22)
START = datetime(2024, 3, 22)
YEARS_SPAN = 2

COUNT_MARA = 500
COUNT_LFA1 = 120
COUNT_EKKO = 2000
COUNT_VBAK = 1800
COUNT_LIKP = 600
COUNT_RBKD = 400
ITEMS_PER_PO = (3, 8)
ITEMS_PER_SO = (2, 6)
ITEMS_PER_DELIVERY = (2, 5)
LINES_PER_INVOICE = 1

MAT_TYPES = ['HALB', 'ROH', 'HAWA', 'FERT', 'HIBE', 'VERP', 'DIEN']
MAT_GROUPS = [f'G{i:02d}' for i in range(1, 21)]
COUNTRIES = ['TW', 'CN', 'JP', 'KR', 'US', 'DE', 'TH', 'VN', 'MY', 'SG']
UNITS = ['PC', 'KG', 'BOX', 'SET', 'M', 'L', 'PCS']
WEIGHT_UNITS = ['KG', 'G', 'LB', 'TO']
CURRENCIES = ['TWD', 'USD', 'CNY', 'EUR']
COST_CENTERS = [f'CC{i:04d}' for i in range(100, 200)]
CITIES_TW = ['台北市', '新北市', '桃園市', '台中市', '台南市', '高雄市', '新竹市', '嘉義市']
STREETS_TW = ['中正路', '中山路', '忠孝東路', '民生東路', '復興北路', '南京東路', '信義路', '敦化南路']
BUKRS = '1000'
WERKS = ['TW01', 'TW02', 'CN01']
LGORT_LIST = ['TW01-S1', 'TW01-S2', 'TW02-S1', 'CN01-S1']

MATERIALS = None
VENDORS = None
CUSTOMERS = None

def pad_sap_id(value: int, length: int = 10) -> str:
    return str(value).zfill(length)

def rand_date(start: datetime, end: datetime) -> str:
    delta = end - start
    days = random.randint(0, delta.days)
    d = start + timedelta(days=days)
    return d.strftime('%Y%m%d')

MATERIAL_DESCS = [
    '不鏽鋼板材', '銅管組件', '塑膠外殼', '電子零件套組', '包裝紙箱',
    '螺絲M6x20', '橡膠墊圈', '鋁合金框架', '矽膠密封條', '碳纖維板',
    '光學鏡片', '陶瓷基板', '磁性元件', '散熱片', '印刷電路板',
    '齒輪組', '軸承套件', '氣壓缸', '感測器模組', '電源供應器',
]

def generate_materials() -> pd.DataFrame:
    rows = []
    for i in range(1, COUNT_MARA + 1):
        unit = random.choice(UNITS)
        rows.append({
            'MATNR': pad_sap_id(i),
            'MAKTX': f'{random.choice(MATERIAL_DESCS)}-{i:04d}',
            'MTART': random.choice(MAT_TYPES),
            'MATKL': random.choice(MAT_GROUPS),
            'MEINS': unit,
            'BRGEW': round(random.uniform(0.01, 500.0), 3) if unit in ('PC', 'SET', 'BOX') else None,
            'GEWEI': random.choice(WEIGHT_UNITS) if unit in ('PC', 'SET', 'BOX') else None,
            'MATNR2': pad_sap_id(random.randint(1, COUNT_MARA)) if random.random() > 0.7 else None,
            'ERSDA': rand_date(START - timedelta(days=730), START),
            'ERNAM': random.choice(['SAPUSER', 'ADMIN', 'MM001', 'MM002']),
            'MBRSH': random.choice(['M', 'P', 'C']),
            'BISMT': pad_sap_id(random.randint(1, COUNT_MARA)) if random.random() > 0.8 else None,
            'PSTAT': random.choice(['KV', 'KVA', 'KDV', 'KL']),
        })
    return pd.DataFrame(rows)

def generate_vendors() -> pd.DataFrame:
    rows = []
    for i in range(1, COUNT_LFA1 + 1):
        country = random.choice(COUNTRIES)
        rows.append({
            'LIFNR': pad_sap_id(i),
            'NAME1': fake.company(),
            'NAME2': fake.company_suffix() if random.random() > 0.5 else None,
            'ORT01': random.choice(CITIES_TW) if country == 'TW' else fake.city(),
            'STRAS': random.choice(STREETS_TW) + str(random.randint(1, 200)) + '號' if country == 'TW' else fake.street_address(),
            'LAND1': country,
            'REGIO': fake.administrative_unit() if random.random() > 0.3 else None,
            'STCD1': fake.ein() if random.random() > 0.4 else None,
            'STCD2': f"{random.choice(['DE','FR','IT','ES','NL','AT','BE','CH'])}{random.randint(1000000000, 9999999999)}" if random.random() > 0.6 else None,
            'KTOKK': random.choice(['KRED', 'LIEF', 'PERS']),
            'ERDAT': rand_date(START - timedelta(days=730), START),
            'ZTERM': random.choice(['K000', 'K030', 'K060', 'K090']),
        })
    return pd.DataFrame(rows)

def generate_customers() -> pd.DataFrame:
    rows = []
    for i in range(1, 201):
        rows.append({
            'KUNNR': pad_sap_id(i),
            'NAME1': fake.company(),
            'LAND1': random.choice(COUNTRIES),
            'REGIO': fake.state() if random.random() > 0.5 else None,
            'STCD1': fake.ein() if random.random() > 0.5 else None,
        })
    return pd.DataFrame(rows)

def upload_parquet(df: pd.DataFrame, module: str, table: str, year: int, month: int) -> int:
    buffer = io.BytesIO()
    pq.write_table(
        pa.table(df),
        buffer,
        compression='snappy',
        use_dictionary=True
    )
    buffer.seek(0)
    key = f'{module}/{table.lower()}/{year}-{month:02d}.parquet'
    s3.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())
    return len(df)

def generate_ekko(mats: pd.DataFrame, vendors: pd.DataFrame) -> pd.DataFrame:
    records = []
    vendors_list = vendors['LIFNR'].tolist()
    for i in range(1, COUNT_EKKO + 1):
        doc_date = rand_date(START, NOW)
        records.append({
            'EBELN': pad_sap_id(i),
            'BUKRS': BUKRS,
            'BSTYP': 'F',
            'LIFNR': random.choice(vendors_list),
            'AEDAT': doc_date,
            'ERDAT': doc_date,
            'ERNAM': random.choice(['SAPUSER', 'MM001', 'MM002', 'MM003']),
            'KNUMV': pad_sap_id(i),
            'STATP': random.choice(['O', 'A', 'C']),
            'WAERS': random.choice(CURRENCIES),
            'WKTNR': pad_sap_id(random.randint(1, 500)) if random.random() > 0.7 else None,
            'KONNR': pad_sap_id(random.randint(1, 1000)) if random.random() > 0.6 else None,
            'AEDAT_YEAR': doc_date[:4],
            'AEDAT_MONTH': doc_date[4:6],
        })
    return pd.DataFrame(records)

def generate_ekpo(ekko: pd.DataFrame, mats: pd.DataFrame, vendors: pd.DataFrame) -> pd.DataFrame:
    records = []
    mats_list = mats['MATNR'].tolist()
    vendors_list = vendors['LIFNR'].tolist()
    for _, po in ekko.iterrows():
        item_count = random.randint(*ITEMS_PER_PO)
        for j in range(1, item_count + 1):
            qty = round(random.uniform(10, 5000), 3)
            price = round(random.uniform(5, 5000), 2)
            records.append({
                'EBELN': po['EBELN'],
                'EBELP': pad_sap_id(j, 5),
                'MATNR': random.choice(mats_list) if random.random() > 0.1 else None,
                'TXZ01': fake.catch_phrase(),
                'MENGE': qty,
                'MEINS': random.choice(UNITS),
                'NETPR': price,
                'PEINH': random.choice([1, 10, 100]),
                'WERKS': random.choice(WERKS),
                'LGORT': random.choice(LGORT_LIST),
                'BANFN': pad_sap_id(random.randint(1, 5000)) if random.random() > 0.5 else None,
                'BNFPO': pad_sap_id(random.randint(1, 999)) if random.random() > 0.5 else None,
                'ELIFB': random.choice(vendors_list) if random.random() > 0.7 else None,
                'RETAM': round(qty * random.uniform(0, 0.05), 3),
                'AEDAT_YEAR': po['AEDAT_YEAR'],
                'AEDAT_MONTH': po['AEDAT_MONTH'],
            })
    return pd.DataFrame(records)

def generate_mseg(ekko: pd.DataFrame, mats: pd.DataFrame) -> pd.DataFrame:
    records = []
    mats_list = mats['MATNR'].tolist()
    vendors_list = ekko['LIFNR'].unique().tolist()
    for _, po in ekko.iterrows():
        item_count = random.randint(1, ITEMS_PER_PO[1])
        mblnr_seq = random.randint(1, 100000)
        for j in range(item_count):
            mblnr = pad_sap_id(mblnr_seq + j)
            mjahr = rand_date(START, NOW)[:4]
            budat = rand_date(START, NOW)
            qty = round(random.uniform(5, 3000), 3)
            bwart = random.choice(['101', '102', '103', '201', '202', '301', '601', '602', '701', '702'])
            # KOSTL: cost center (for consumption postings 201/261)
            kostl = random.choice(COST_CENTERS) if bwart in ('201', '261', '202') else None
            # UMLGO: receiving storage location (for transfer postings 301/311)
            umlgo = random.choice(LGORT_LIST) if bwart in ('301', '302', '311') else None
            records.append({
                'MBLNR': mblnr,
                'MJAHR': mjahr,
                'ZEILE': pad_sap_id(j + 1, 4),
                'BUKRS': BUKRS,
                'BUDAT': budat,
                'MATNR': random.choice(mats_list) if random.random() > 0.1 else None,
                'WERKS': random.choice(WERKS),
                'LGORT': random.choice(LGORT_LIST),
                'BWART': bwart,
                'DMBTR': round(random.uniform(100, 100000), 2),
                'MENGE': qty,
                'MEINS': random.choice(UNITS),
                'WAERS': random.choice(CURRENCIES),
                'KOSTL': kostl,
                'UMLGO': umlgo,
                'LIFNR': random.choice(vendors_list) if bwart in ('101', '102', '103', '161') else None,
                'EBELN': po['EBELN'] if random.random() > 0.3 else None,
                'EBELP': pad_sap_id(random.randint(1, 10), 5) if random.random() > 0.3 else None,
                'BUDAT_YEAR': budat[:4],
                'BUDAT_MONTH': budat[4:6],
            })
    return pd.DataFrame(records)

def generate_vbak(mats: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    records = []
    cust_list = customers['KUNNR'].tolist()
    for i in range(1, COUNT_VBAK + 1):
        doc_date = rand_date(START, NOW)
        records.append({
            'VBELN': pad_sap_id(i),
            'KUNNR': random.choice(cust_list),
            'ERDAT': doc_date,
            'ERNAM': random.choice(['SAPUSER', 'SD001', 'SD002']),
            'AUART': random.choice(['OR', 'ZOR', 'CR']),
            'VBTYP': 'C',
            'NETWR': round(random.uniform(10000, 500000), 2),
            'WAERK': random.choice(CURRENCIES),
            'AUDAT': doc_date,
            'STAWN': pad_sap_id(random.randint(1, 10000)) if random.random() > 0.5 else None,
            'ERDAT_YEAR': doc_date[:4],
            'ERDAT_MONTH': doc_date[4:6],
        })
    return pd.DataFrame(records)

def generate_vbap(vbak: pd.DataFrame, mats: pd.DataFrame) -> pd.DataFrame:
    records = []
    mats_list = mats['MATNR'].tolist()
    for _, so in vbak.iterrows():
        item_count = random.randint(*ITEMS_PER_SO)
        for j in range(1, item_count + 1):
            records.append({
                'VBELN': so['VBELN'],
                'POSNR': pad_sap_id(j * 10),
                'MATNR': random.choice(mats_list) if random.random() > 0.1 else None,
                'KDMAT': fake.text(max_nb_chars=30) if random.random() > 0.7 else None,
                'KWMENG': round(random.uniform(10, 1000), 3),
                'VRKME': random.choice(UNITS),
                'NETWR': round(random.uniform(1000, 50000), 2),
                'WERKS': random.choice(WERKS),
                'ERDAT': so['ERDAT'],
                'ERDAT_YEAR': so['ERDAT_YEAR'],
                'ERDAT_MONTH': so['ERDAT_MONTH'],
            })
    return pd.DataFrame(records)

def generate_likp(vbak: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    records = []
    cust_list = customers['KUNNR'].tolist()
    for i in range(1, COUNT_LIKP + 1):
        doc_date = rand_date(START, NOW)
        records.append({
            'VBELN': pad_sap_id(i),
            'KUNNR': random.choice(cust_list),
            'WADAT': doc_date,
            'ERDAT': doc_date,
            'LIFSP': random.choice(['01', '02', '03']),
            'VBTYP': 'J',
            'WADAT_IST': rand_date(START, NOW) if random.random() > 0.5 else None,
            'WADAT_YEAR': doc_date[:4],
            'WADAT_MONTH': doc_date[4:6],
        })
    return pd.DataFrame(records)

def generate_lips(likp: pd.DataFrame, mats: pd.DataFrame) -> pd.DataFrame:
    records = []
    mats_list = mats['MATNR'].tolist()
    for _, dl in likp.iterrows():
        item_count = random.randint(*ITEMS_PER_DELIVERY)
        for j in range(1, item_count + 1):
            records.append({
                'VBELN': dl['VBELN'],
                'POSNR': pad_sap_id(j * 10),
                'MATNR': random.choice(mats_list) if random.random() > 0.1 else None,
                'LFIMG': round(random.uniform(5, 800), 3),
                'VRKME': random.choice(UNITS),
                'WERKS': random.choice(WERKS),
                'LGORT': random.choice(LGORT_LIST),
                'WADAT_YEAR': dl['WADAT_YEAR'],
                'WADAT_MONTH': dl['WADAT_MONTH'],
            })
    return pd.DataFrame(records)

def generate_rbkd() -> pd.DataFrame:
    records = []
    for i in range(1, COUNT_RBKD + 1):
        year = str(random.randint(2024, 2026))
        records.append({
            'BELNR': pad_sap_id(i),
            'GJAHR': int(year),
            'KUNNR': pad_sap_id(random.randint(1, 200)),
            'BUDAT': rand_date(START, NOW),
            'WRBTR': round(random.uniform(5000, 300000), 2),
            'WMWST': round(random.uniform(500, 30000), 2),
            'ZUONR': pad_sap_id(random.randint(1, 2000)) if random.random() > 0.5 else None,
            'SGTXT': fake.sentence(nb_words=6) if random.random() > 0.6 else None,
            'BUDAT_YEAR': rand_date(START, NOW)[:4],
            'BUDAT_MONTH': rand_date(START, NOW)[4:6],
        })
    return pd.DataFrame(records)

def upload_partitioned(df: pd.DataFrame, module: str, table: str, partition_col: str):
    if df.empty:
        return 0
    total = 0
    for (year, month), grp in df.groupby([f'{partition_col}_YEAR', f'{partition_col}_MONTH']):
        grp_clean = grp.drop(columns=[f'{partition_col}_YEAR', f'{partition_col}_MONTH'], errors='ignore')
        n = upload_parquet(grp_clean, module, table, int(year), int(month))
        total += n
        print(f'  ✓ {module}/{table}/{year}-{int(month):02d} ({n} rows)')
    return total

def run():
    print('=== SAP Data Lake Generator (2 years: 2024-03 ~ 2026-03) ===')
    print(f'S3: {S3_ENDPOINT}/{BUCKET}')

    print('\nGenerating base data...')
    global MATERIALS, VENDORS, CUSTOMERS
    MATERIALS = generate_materials()
    VENDORS = generate_vendors()
    CUSTOMERS = generate_customers()
    print(f'  Materials: {len(MATERIALS)}, Vendors: {len(VENDORS)}, Customers: {len(CUSTOMERS)}')

    grand_total = 0

    # MM Module
    print('\n--- MM Module ---')

    # MARA
    marapq = pa.table(MATERIALS)
    buf = io.BytesIO()
    pq.write_table(marapq, buf, compression='snappy', use_dictionary=True)
    buf.seek(0)
    s3.put_object(Bucket=BUCKET, Key='mm/mara/all.parquet', Body=buf.getvalue())
    print(f'  ✓ mm/mara/all.parquet ({len(MATERIALS)} rows)')

    # LFA1
    buf = io.BytesIO()
    pq.write_table(pa.table(VENDORS), buf, compression='snappy', use_dictionary=True)
    buf.seek(0)
    s3.put_object(Bucket=BUCKET, Key='mm/lfa1/all.parquet', Body=buf.getvalue())
    print(f'  ✓ mm/lfa1/all.parquet ({len(VENDORS)} rows)')

    # EKKO
    print('  Generating EKKO...')
    ekko = generate_ekko(MATERIALS, VENDORS)
    total = upload_partitioned(ekko, 'mm', 'ekko', 'AEDAT')
    grand_total += total
    print(f'  ✓ mm/ekko ({total} rows)')

    # EKPO
    print('  Generating EKPO...')
    ekpo = generate_ekpo(ekko, MATERIALS, VENDORS)
    total = upload_partitioned(ekpo, 'mm', 'ekpo', 'AEDAT')
    grand_total += total
    print(f'  ✓ mm/ekpo ({total} rows)')

    # MSEG
    print('  Generating MSEG...')
    mseg = generate_mseg(ekko, MATERIALS)
    total = upload_partitioned(mseg, 'mm', 'mseg', 'BUDAT')
    grand_total += total
    print(f'  ✓ mm/mseg ({total} rows)')

    # SD Module
    print('\n--- SD Module ---')

    print('  Generating VBAK...')
    vbak = generate_vbak(MATERIALS, CUSTOMERS)
    total = upload_partitioned(vbak, 'sd', 'vbak', 'ERDAT')
    grand_total += total
    print(f'  ✓ sd/vbak ({total} rows)')

    print('  Generating VBAP...')
    vbap = generate_vbap(vbak, MATERIALS)
    total = upload_partitioned(vbap, 'sd', 'vbap', 'ERDAT')
    grand_total += total
    print(f'  ✓ sd/vbap ({total} rows)')

    print('  Generating LIKP...')
    likp = generate_likp(vbak, CUSTOMERS)
    total = upload_partitioned(likp, 'sd', 'likp', 'WADAT')
    grand_total += total
    print(f'  ✓ sd/likp ({total} rows)')

    print('  Generating LIPS...')
    lips = generate_lips(likp, MATERIALS)
    total = upload_partitioned(lips, 'sd', 'lips', 'WADAT')
    grand_total += total
    print(f'  ✓ sd/lips ({total} rows)')

    print('  Generating RBKD...')
    rbkd = generate_rbkd()
    # RBKD doesn't have a natural partition in the df, but BUDAT is there
    total = upload_partitioned(rbkd, 'sd', 'rbkd', 'BUDAT')
    grand_total += total
    print(f'  ✓ sd/rbkd ({total} rows)')

    print(f'\n=== Done! Total records: {grand_total:,} ===')

if __name__ == '__main__':
    run()
