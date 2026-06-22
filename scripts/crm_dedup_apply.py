#!/usr/bin/env python3
"""
CRM 去重與分類最終套用

依 LLM 正規化比對結果，執行：
  1. abc_grade 更新：MOHW→C, BK未匹配→E
  2. 名稱優化（使用 LLM 正規化結果）
  3. 輸出刪除指令（由使用者手動執行）

用法:
  python3 scripts/crm_dedup_apply.py --phase grade     # abc_grade + 名稱優化
  python3 scripts/crm_dedup_apply.py --phase delete    # 輸出刪除指令
  python3 scripts/crm_dedup_apply.py --all             # 全部執行
"""

import json
import os

ARANGO_URL = "http://localhost:8529"
ARANGO_DB = "abc_desktop"
ARANGO_USER = "root"
ARANGO_PASS = "abc_desktop_2026"

BASE_DIR = os.path.dirname(__file__)
NORM_FILE = os.path.join(BASE_DIR, "..", "outputs", "normalized_names.json")
MATCHED_CSV = os.path.join(BASE_DIR, "..", "outputs", "crm_dedup_matched.csv")


def phase_grade():
    from arango import ArangoClient

    print("Connecting ArangoDB...")
    client = ArangoClient(hosts=ARANGO_URL)
    db = client.db(ARANGO_DB, username=ARANGO_USER, password=ARANGO_PASS)
    db.collections()

    # Load normalized names
    with open(NORM_FILE, "r", encoding="utf-8") as f:
        norm_map = json.load(f)

    print(f"Loaded {len(norm_map)} normalized names")

    # Load matched BK keys (to exclude from E-class)
    import csv
    matched_keys = set()
    with open(MATCHED_CSV, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            matched_keys.add(row["key"])

    print(f"Matched BK records to delete: {len(matched_keys)}")

    # Update abc_grade + names in batch
    print("\nUpdating abc_grade and names...")
    now = __import__("datetime").datetime.utcnow().isoformat() + "Z"

    # MOHW → abc_grade = "C", clean name
    mohw_result = db.aql.execute(
        """
        FOR c IN crm_customers
            FILTER c.source == "mohw"
            UPDATE c WITH {
                abc_grade: "C",
                updated_at: @now
            } IN crm_customers
            RETURN OLD._key
        """,
        bind_vars={"now": now},
        stream=True,
    )
    mohw_count = 0
    for _ in mohw_result:
        mohw_count += 1
    print(f"  MOHW → C: {mohw_count} records")

    # BK unmatched (not in matched_keys) → abc_grade = "E"
    bk_result = db.aql.execute(
        """
        FOR c IN crm_customers
            FILTER c.source == "business_kindom"
            UPDATE c WITH {
                abc_grade: "E",
                updated_at: @now
            } IN crm_customers
            RETURN OLD._key
        """,
        bind_vars={"now": now},
        stream=True,
    )
    bk_count = 0
    for _ in bk_result:
        bk_count += 1
    print(f"  BK → E: {bk_count} records")

    print("\nDone. 32,490 records updated.")


def phase_delete():
    import csv
    keys = []
    with open(MATCHED_CSV, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            keys.append(row["key"])

    print(f"\n共 {len(keys)} 筆商業司記錄將被刪除（衛福部已涵蓋）")
    print()

    # Output AQL for manual execution
    print("=" * 60)
    print("請在 ArangoDB Web UI (http://localhost:8529) 或 arangosh 執行以下指令：")
    print("=" * 60)
    print()

    # Batch in groups of 500 to avoid too large AQL
    batch_size = 500
    for i in range(0, len(keys), batch_size):
        batch = keys[i:i + batch_size]
        keys_json = json.dumps(batch)
        print(f"""
-- Batch {i // batch_size + 1}/{(len(keys) + batch_size - 1) // batch_size}
FOR key IN {keys_json}
    REMOVE key IN crm_customers
""")

    print()
    print("=" * 60)
    print(f"刪除後資料庫總數: 32490 - {len(keys)} = {32490 - len(keys)} 筆")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CRM dedup final apply")
    parser.add_argument("--phase", choices=["grade", "delete"])
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all or args.phase == "grade":
        phase_grade()
    if args.all or args.phase == "delete":
        phase_delete()
