#!/usr/bin/env python3
"""
CRM 來源資料 LLM 比對工具

比對商業司與衛福部的機構名稱（用 LLM 理解正規化），
為同一機構標記類型（以衛福部為準），無匹配者設為「其他」。

分階段執行：
   python3 scripts/crm_source_dedup.py --phase norm      # LLM 正規化
   python3 scripts/crm_source_dedup.py --phase match     # 比對 + CSV
   python3 scripts/crm_source_dedup.py --phase apply     # 寫入資料庫

一氣呵成：
   python3 scripts/crm_source_dedup.py --all
   python3 scripts/crm_source_dedup.py --all --apply
"""

import csv
import json
import os
import re
import sys
import time
from collections import defaultdict

import requests

OMLX_URL = "http://localhost:11400"
LLM_MODEL = "Qwen3-VL-8B"
BATCH_SIZE = 60

ARANGO_URL = "http://localhost:8529"
ARANGO_DB = "abc_desktop"
ARANGO_USER = "root"
ARANGO_PASS = "abc_desktop_2026"

BASE_DIR = os.path.dirname(__file__)
OUT_DIR = os.path.join(BASE_DIR, "..", "outputs")
NORM_FILE = os.path.join(OUT_DIR, "normalized_names.json")

SYSTEM_PROMPT = (
    "Extract the core institution name from the following Taiwanese "
    "organization names. Remove prefixes like 00_, 00台北市_, remove "
    "parenthetical notes like (社照C), (原民C), remove city/county "
    "prefixes like 臺北市, 新北市, remove detailed address suffixes "
    "after '-', and remove branch suffixes like _分店. "
    "Output one name per line. No explanations, no numbering."
)


def llm_batch_normalize(names):
    names_text = "\n".join(names)
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Normalize:\n{names_text}"},
        ],
        "temperature": 0.05,
        "max_tokens": max(200, len(names) * 15),
    }
    for attempt in range(2):
        try:
            resp = requests.post(
                f"{OMLX_URL}/v1/chat/completions", json=payload, timeout=120
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            lines = [l.strip() for l in content.split("\n") if l.strip()]
            if len(lines) >= len(names) * 0.8:
                return lines[: len(names)]
        except Exception as e:
            print(f"  LLM error: {e}", file=sys.stderr)
            time.sleep(3)
    return None


def phase_norm():
    from arango import ArangoClient

    print("Connecting ArangoDB...")
    client = ArangoClient(hosts=ARANGO_URL)
    db = client.db(ARANGO_DB, username=ARANGO_USER, password=ARANGO_PASS)
    db.collections()
    print("OK")

    print("\nLoading unique names...")
    cursor = db.aql.execute(
        "FOR c IN crm_customers COLLECT name = c.name RETURN name"
    )
    unique_names = [doc for doc in cursor]
    print(f"  {len(unique_names)} unique names")

    done = {}
    if os.path.exists(NORM_FILE):
        with open(NORM_FILE, "r", encoding="utf-8") as f:
            done = json.load(f)
        print(f"  Resume: {len(done)} already done")
        remaining = [n for n in unique_names if n not in done]
    else:
        remaining = unique_names
    if not remaining:
        print("  All done")
        return

    print(f"\nLLM: {LLM_MODEL}, batch={BATCH_SIZE}, {len(remaining)} names")
    total = len(remaining)
    start = time.time()

    for i in range(0, total, BATCH_SIZE):
        batch = remaining[i : i + BATCH_SIZE]
        result = llm_batch_normalize(batch)
        if result:
            for orig, norm in zip(batch, result):
                done[orig] = norm
        else:
            for orig in batch:
                done[orig] = orig

        if (i // BATCH_SIZE) % 5 == 0:
            os.makedirs(OUT_DIR, exist_ok=True)
            with open(NORM_FILE, "w", encoding="utf-8") as f:
                json.dump(done, f, ensure_ascii=False, indent=2)

        elapsed = time.time() - start
        done_count = i + len(batch)
        pct = done_count * 100 // total
        rate = done_count / elapsed if elapsed > 0 else 0
        eta = (total - done_count) / rate if rate > 0 else 0
        print(f"  {pct}% ({done_count}/{total})  {rate:.1f}/s  ETA {eta:.0f}s")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(NORM_FILE, "w", encoding="utf-8") as f:
        json.dump(done, f, ensure_ascii=False, indent=2)
    print(f"\nDone -> {NORM_FILE}")


def phase_match():
    from arango import ArangoClient

    if not os.path.exists(NORM_FILE):
        print("Run --phase norm first")
        sys.exit(1)

    print("Loading normalized names...")
    with open(NORM_FILE, "r", encoding="utf-8") as f:
        norm_map = json.load(f)
    print(f"  {len(norm_map)} entries")

    print("\nConnecting ArangoDB...")
    client = ArangoClient(hosts=ARANGO_URL)
    db = client.db(ARANGO_DB, username=ARANGO_USER, password=ARANGO_PASS)
    db.collections()

    print("Loading all records...")
    cursor = db.aql.execute("FOR c IN crm_customers RETURN c")
    all_records = [doc for doc in cursor]

    by_source = defaultdict(list)
    for r in all_records:
        by_source[r.get("source")].append(r)
    mohw = by_source.get("mohw", [])
    bk = by_source.get("business_kindom", [])
    print(f"  BK: {len(bk)}, MOHW: {len(mohw)}")

    def get_norm(rec):
        n = rec.get("name") or rec.get("name_raw") or ""
        return norm_map.get(n, n)

    print("Grouping by normalized name...")
    groups = defaultdict(list)
    for r in mohw:
        groups[get_norm(r)].append(("mohw", r))
    for r in bk:
        groups[get_norm(r)].append(("bk", r))

    matched = []
    unmatched = []
    for norm, entries in groups.items():
        has_mohw = any(s == "mohw" for s, _ in entries)
        has_bk = any(s == "bk" for s, _ in entries)
        if not has_bk:
            continue
        mw_cats = set()
        mw_names = []
        for s, rec in entries:
            if s == "mohw":
                mw_names.append(rec.get("name"))
                cats = rec.get("category") or []
                if isinstance(cats, list):
                    for c in cats:
                        if not re.match(r"^[A-Za-z0-9]+$", c):
                            mw_cats.add(c)
        new_type = list(mw_cats)[0] if mw_cats else None
        for s, rec in entries:
            if s != "bk":
                continue
            item = {
                "_key": rec["_key"], "name": rec.get("name", ""),
                "norm_group": norm,
            }
            if new_type:
                item["new_category"] = [new_type]
                item["matched_mohw"] = mw_names[0] if mw_names else ""
                matched.append(item)
            else:
                item["new_category"] = ["其他"]
                unmatched.append(item)

    mw_only = sum(1 for _, es in groups.items() if all(s == "mohw" for s, _ in es))
    bk_only = sum(1 for _, es in groups.items() if all(s == "bk" for s, _ in es))
    both = sum(1 for _, es in groups.items()
               if any(s == "mohw" for s, _ in es) and any(s == "bk" for s, _ in es))

    print(f"\n{'='*50}")
    print(f"Groups: {len(groups)}")
    print(f"  MOHW only: {mw_only}")
    print(f"  BK only:   {bk_only}")
    print(f"  Cross:     {both}")
    print(f"  BK match:  {len(matched)}")
    print(f"  BK other:  {len(unmatched)}")
    print(f"{'='*50}")

    tdist = defaultdict(int)
    for u in matched:
        for t in u["new_category"]:
            tdist[t] += 1
    for u in unmatched:
        for t in u["new_category"]:
            tdist[t] += 1

    print(f"\nTypes:")
    for t, c in sorted(tdist.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")

    os.makedirs(OUT_DIR, exist_ok=True)

    f1 = os.path.join(OUT_DIR, "crm_dedup_matched.csv")
    with open(f1, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["key", "bk_name", "matched_mohw", "type", "norm_group"])
        for u in matched:
            w.writerow([u["_key"], u["name"], u["matched_mohw"],
                        u["new_category"][0], u["norm_group"]])
    print(f"\nMatched: {f1} ({len(matched)})")

    f2 = os.path.join(OUT_DIR, "crm_dedup_unmatched.csv")
    with open(f2, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["key", "name", "type", "norm_group"])
        for u in unmatched:
            w.writerow([u["_key"], u["name"], u["new_category"][0], u["norm_group"]])
    print(f"Unmatched: {f2} ({len(unmatched)})")

    f3 = os.path.join(OUT_DIR, "crm_dedup_summary.csv")
    with open(f3, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["type", "count"])
        for t, c in sorted(tdist.items(), key=lambda x: -x[1]):
            w.writerow([t, c])
    print(f"Summary: {f3}")

    updates = matched + unmatched
    f4 = os.path.join(OUT_DIR, "crm_updates.json")
    with open(f4, "w", encoding="utf-8") as f:
        json.dump(updates, f, ensure_ascii=False, indent=2)
    print(f"Updates: {f4} ({len(updates)})")


def phase_apply():
    from arango import ArangoClient

    f = os.path.join(OUT_DIR, "crm_updates.json")
    if not os.path.exists(f):
        print("Run --phase match first")
        sys.exit(1)

    print("Loading updates...")
    with open(f, "r", encoding="utf-8") as fp:
        updates = json.load(fp)
    print(f"  {len(updates)} updates")

    print("\nConnecting ArangoDB...")
    client = ArangoClient(hosts=ARANGO_URL)
    db = client.db(ARANGO_DB, username=ARANGO_USER, password=ARANGO_PASS)
    db.collections()

    print("Writing...")
    ok, fail = 0, 0
    now = __import__("datetime").datetime.utcnow().isoformat() + "Z"
    for item in updates:
        try:
            db.aql.execute(
                "UPDATE @key WITH { category: @cat, updated_at: @now } IN crm_customers",
                bind_vars={"key": item["_key"], "cat": item["new_category"], "now": now},
            )
            ok += 1
        except Exception as e:
            print(f"  FAIL {item['_key']}: {e}")
            fail += 1
        if ok % 500 == 0:
            print(f"  {ok}/{len(updates)}...")
    print(f"\nDone: {ok} ok, {fail} failed")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CRM dedup")
    parser.add_argument("--phase", choices=["norm", "match", "apply"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.all:
        phase_norm()
        phase_match()
        if args.apply:
            phase_apply()
    elif args.phase == "norm":
        phase_norm()
    elif args.phase == "match":
        phase_match()
    elif args.phase == "apply":
        phase_apply()
    else:
        parser.print_help()
