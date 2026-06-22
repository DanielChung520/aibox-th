#!/usr/bin/env python3
"""
刪除 CRM 重複記錄：商業司中已匹配衛福部的資料。

使用方式：
  python3 scripts/crm_delete_duplicates.py

安全說明：
  此為不可逆操作，執行前會顯示預覽與確認提示。
"""
import csv
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ai-services", ".venv", "lib", "python3.14", "site-packages"))
from arango import ArangoClient

ARANGO_URL = "http://localhost:8529"
ARANGO_DB = "abc_desktop"
ARANGO_USER = "root"
ARANGO_PASS = "abc_desktop_2026"

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MATCHED_CSV = os.path.join(BASE_DIR, "outputs", "crm_dedup_matched.csv")


def main():
    # 讀取待刪除清單
    if not os.path.exists(MATCHED_CSV):
        print(f"找不到 {MATCHED_CSV}")
        sys.exit(1)

    with open(MATCHED_CSV, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    keys = [r["key"] for r in rows]
    print(f"待刪除: {len(keys)} 筆商業司記錄（已匹配衛福部）")
    print()

    # 預覽前 5 筆
    print("前 5 筆預覽:")
    for r in rows[:5]:
        print(f"  {r['bk_name'][:50]:50s} → 保留衛福部: {r['matched_mohw'][:40]}")
    print()

    # 確認
    confirm = input("是否執行刪除？(yes/no): ").strip().lower()
    if confirm != "yes":
        print("已取消")
        return

    # 連線 ArangoDB
    print("\n連線 ArangoDB...")
    client = ArangoClient(hosts=ARANGO_URL)
    db = client.db(ARANGO_DB, username=ARANGO_USER, password=ARANGO_PASS)
    db.collections()
    print("OK")

    # 分批刪除
    batch_size = 500
    ok, fail = 0, 0
    for i in range(0, len(keys), batch_size):
        batch = keys[i:i + batch_size]
        try:
            db.aql.execute(
                "FOR key IN @keys REMOVE key IN crm_customers",
                bind_vars={"keys": batch},
            )
            ok += len(batch)
        except Exception as e:
            print(f"批次 {i//batch_size + 1} 失敗: {e}")
            fail += len(batch)
        print(f"  進度: {ok}/{len(keys)}")

    # 驗證
    total = db.aql.execute("RETURN LENGTH(crm_customers)").next()
    mohw = db.aql.execute('RETURN LENGTH(FOR c IN crm_customers FILTER c.source=="mohw" RETURN c)').next()
    bk = db.aql.execute('RETURN LENGTH(FOR c IN crm_customers FILTER c.source=="business_kindom" RETURN c)').next()

    print(f"\n{'='*40}")
    print(f"成功刪除: {ok}")
    print(f"失敗: {fail}")
    print(f"資料庫總數: {total}")
    print(f"  衛福部: {mohw}")
    print(f"  商業司: {bk}")
    print(f"{'='*40}")


if __name__ == "__main__":
    main()
