#!/usr/bin/env python3
"""
Generate Faker data for MKPF, MARD, MCHB and upload to SeaWeedFS S3.

@file        generate_inventory_data.py
@description 補齊庫存交易體系 Parquet 資料: MKPF, MARD, MCHB
@lastUpdate  2026-03-22 17:08:09
@author      Daniel Chung
@version     1.0.0
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

COUNT_MARA = 500
WERKS = ['TW01', 'TW02', 'CN01']
LGORT_LIST = ['TW01-S1', 'TW01-S2', 'TW02-S1', 'CN01-S1']
COUNT_MKPF = 5000
COUNT_MARD = 3000
COUNT_MCHB = 2000

TCODES = ['MIGO', 'MB01', 'MB1A', 'MB1B', 'MB1C', 'MB31', 'MBST', 'MI01', 'MI04', 'MI07']
VGART_LIST = ['WA', 'WE', 'WI', 'WL', 'WF']


def pad_sap_id(value: int, length: int = 10) -> str:
    return str(value).zfill(length)


def rand_date(start: datetime, end: datetime) -> str:
    delta = end - start
    days = random.randint(0, delta.days)
    d = start + timedelta(days=days)
    return d.strftime('%Y%m%d')


def upload_parquet_single(df: pd.DataFrame, key: str) -> int:
    """Upload a single Parquet file."""
    buffer = io.BytesIO()
    pq.write_table(
        pa.table(df),
        buffer,
        compression='snappy',
        use_dictionary=True
    )
    buffer.seek(0)
    s3.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())
    return len(df)


def upload_partitioned(df: pd.DataFrame, module: str, table: str, partition_col: str) -> int:
    """Upload partitioned by year-month."""
    if df.empty:
        return 0
    total = 0
    year_col = f'{partition_col}_YEAR'
    month_col = f'{partition_col}_MONTH'
    for (year, month), grp in df.groupby([year_col, month_col]):
        grp_clean = grp.drop(columns=[year_col, month_col], errors='ignore')
        key = f'{module}/{table.lower()}/{year}-{int(month):02d}.parquet'
        n = upload_parquet_single(grp_clean, key)
        total += n
        print(f'  ✓ {key} ({n} rows)')
    return total


def generate_mkpf() -> pd.DataFrame:
    """Generate MKPF (Material Document Header)."""
    records = []
    for i in range(1, COUNT_MKPF + 1):
        budat = rand_date(START, NOW)
        bldat = budat  # typically same as posting date
        cpudt = budat
        records.append({
            'MBLNR': pad_sap_id(i),
            'MJAHR': budat[:4],
            'BLDAT': bldat,
            'BUDAT': budat,
            'USNAM': random.choice(['SAPUSER', 'MM001', 'MM002', 'MM003', 'WM001']),
            'TCODE': random.choice(TCODES),
            'XBLNR': f'REF-{random.randint(10000, 99999)}' if random.random() > 0.4 else None,
            'BKTXT': fake.sentence(nb_words=4) if random.random() > 0.5 else None,
            'VGART': random.choice(VGART_LIST),
            'CPUDT': cpudt,
            'BUDAT_YEAR': budat[:4],
            'BUDAT_MONTH': budat[4:6],
        })
    return pd.DataFrame(records)


def generate_mard() -> pd.DataFrame:
    """Generate MARD (Storage Location Stock) — snapshot table, no time partition."""
    records = []
    seen = set()
    attempts = 0
    while len(records) < COUNT_MARD and attempts < COUNT_MARD * 5:
        attempts += 1
        matnr = pad_sap_id(random.randint(1, COUNT_MARA))
        werks = random.choice(WERKS)
        lgort = random.choice(LGORT_LIST)
        key = (matnr, werks, lgort)
        if key in seen:
            continue
        seen.add(key)

        labst = round(random.uniform(0, 10000), 3)
        insme = round(random.uniform(0, labst * 0.1), 3) if random.random() > 0.6 else 0.0
        speme = round(random.uniform(0, labst * 0.05), 3) if random.random() > 0.7 else 0.0
        umlme = round(random.uniform(0, labst * 0.08), 3) if random.random() > 0.75 else 0.0
        retme = round(random.uniform(0, labst * 0.02), 3) if random.random() > 0.85 else 0.0

        recent_year = str(random.choice([2025, 2026]))
        recent_month = f'{random.randint(1, 12):02d}'

        records.append({
            'MATNR': matnr,
            'WERKS': werks,
            'LGORT': lgort,
            'LABST': labst,
            'INSME': insme,
            'SPEME': speme,
            'UMLME': umlme,
            'RETME': retme,
            'LFGJA': recent_year,
            'LFMON': recent_month,
        })
    return pd.DataFrame(records)


def generate_mchb() -> pd.DataFrame:
    """Generate MCHB (Batch Stock) — snapshot table, no time partition."""
    records = []
    seen = set()
    attempts = 0
    while len(records) < COUNT_MCHB and attempts < COUNT_MCHB * 5:
        attempts += 1
        matnr = pad_sap_id(random.randint(1, COUNT_MARA))
        werks = random.choice(WERKS)
        lgort = random.choice(LGORT_LIST)
        charg = f'B{random.randint(100000, 999999)}'
        key = (matnr, werks, lgort, charg)
        if key in seen:
            continue
        seen.add(key)

        clabs = round(random.uniform(0, 5000), 3)
        cinsm = round(random.uniform(0, clabs * 0.08), 3) if random.random() > 0.7 else 0.0
        cspem = round(random.uniform(0, clabs * 0.03), 3) if random.random() > 0.8 else 0.0

        mfg_date = rand_date(START - timedelta(days=365), NOW)
        shelf_days = random.randint(180, 1095)
        mfg_dt = datetime.strptime(mfg_date, '%Y%m%d')
        exp_dt = mfg_dt + timedelta(days=shelf_days)
        vfdat = exp_dt.strftime('%Y%m%d') if random.random() > 0.3 else None

        records.append({
            'MATNR': matnr,
            'WERKS': werks,
            'LGORT': lgort,
            'CHARG': charg,
            'CLABS': clabs,
            'CINSM': cinsm,
            'CSPEM': cspem,
            'HSDAT': mfg_date if random.random() > 0.2 else None,
            'VFDAT': vfdat,
        })
    return pd.DataFrame(records)


def run() -> None:
    print('=== Inventory Data Generator (MKPF, MARD, MCHB) ===')
    print(f'S3: {S3_ENDPOINT}/{BUCKET}')
    grand_total = 0

    # MKPF (partitioned by BUDAT)
    print('\n--- MKPF (Material Document Header) ---')
    mkpf = generate_mkpf()
    total = upload_partitioned(mkpf, 'mm', 'mkpf', 'BUDAT')
    grand_total += total
    print(f'  Total MKPF: {total} rows')

    # MARD (snapshot, single file)
    print('\n--- MARD (Storage Location Stock) ---')
    mard = generate_mard()
    n = upload_parquet_single(mard, 'mm/mard/all.parquet')
    grand_total += n
    print(f'  ✓ mm/mard/all.parquet ({n} rows)')

    # MCHB (snapshot, single file)
    print('\n--- MCHB (Batch Stock) ---')
    mchb = generate_mchb()
    n = upload_parquet_single(mchb, 'mm/mchb/all.parquet')
    grand_total += n
    print(f'  ✓ mm/mchb/all.parquet ({n} rows)')

    print(f'\n=== Done! Total new records: {grand_total:,} ===')


if __name__ == '__main__':
    run()
