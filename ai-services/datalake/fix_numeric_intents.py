#!/usr/bin/env python3
"""
@file        fix_numeric_intents.py
@description 修正使用數字 field_id 的意圖 SQL template，改為中文欄位名。
              同時修復 rgc_rfq_01（缺 SQL template）。
@lastUpdate  2026-04-11 21:45:43
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = "root:abc_desktop_2026"

FIXES: list[dict[str, Any]] = [
    {
        "_key": "rgc_rfq_01",
        "name": "詢價單列表（日期範圍）",
        "description": "依日期範圍查詢詢價單列表",
        "sql_template": (
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_59' "
            "AND d['詢價日期'] >= '{start_date}' "
            "AND d['詢價日期'] <= '{end_date}' "
            "SORT d['詢價日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'詢價單號': d['詢價單號'], "
            "'詢價日期': d['詢價日期'], "
            "'供應商名稱': d['供應商名稱'], "
            "'供應商編碼': d['供應商編碼'], "
            "'詢價狀態': d['詢價狀態'], "
            "'預估金額': d['預估金額']}"
        ),
        "core_fields": ["詢價單號", "詢價日期", "供應商名稱", "詢價狀態"],
        "nl_examples": [
            "查詢最近的詢價單",
            "上個月有哪些詢價",
            "2026年3月的詢價單列表",
        ],
    },
    {
        "_key": "rgc_rfq_02",
        "sql_template": (
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_59' "
            "AND ("
            "CONTAINS(d['供應商名稱'], '{vendor}', true) OR "
            "CONTAINS(d['供應商編碼'], '{vendor}', true)"
            ") "
            "SORT d['詢價日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'詢價單號': d['詢價單號'], "
            "'供應商名稱': d['供應商名稱'], "
            "'詢價日期': d['詢價日期'], "
            "'詢價狀態': d['詢價狀態']}"
        ),
        "core_fields": ["詢價單號", "供應商名稱", "詢價日期", "詢價狀態"],
    },
    {
        "_key": "rgc_quote_01",
        "sql_template": (
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_66' "
            "AND d['報價日期'] >= '{start_date}' "
            "AND d['報價日期'] <= '{end_date}' "
            "SORT d['報價日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'報價單號': d['報價單號'], "
            "'供應商名稱': d['供應商名稱'], "
            "'報價日期': d['報價日期'], "
            "'報價狀態': d['報價狀態'], "
            "'含稅總計': d['含稅總計']}"
        ),
        "core_fields": ["報價單號", "供應商名稱", "報價日期", "含稅總計"],
    },
    {
        "_key": "rgc_return_01",
        "sql_template": (
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_52' "
            "AND d['退貨日期'] >= '{start_date}' "
            "AND d['退貨日期'] <= '{end_date}' "
            "SORT d['退貨日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'退貨單號': d['退貨單號'], "
            "'來源進貨單號': d['來源進貨單號'], "
            "'退貨日期': d['退貨日期'], "
            "'供應商名稱': d['供應商名稱'], "
            "'退貨數量': d['退貨數量'], "
            "'退貨狀態': d['退貨狀態']}"
        ),
        "core_fields": ["退貨單號", "來源進貨單號", "退貨日期", "退貨數量", "退貨狀態"],
    },
    {
        "_key": "rgc_pd_01",
        "sql_template": (
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_57' "
            "AND d['需求日期'] >= '{start_date}' "
            "AND d['需求日期'] <= '{end_date}' "
            "SORT d['需求日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'需求單號': d['需求單號'], "
            "'銷貨單號': d['銷貨單號'], "
            "'需求日期': d['需求日期'], "
            "'品項名稱': d['品項名稱'], "
            "'需求數量': d['需求數量'], "
            "'需求狀態': d['需求狀態']}"
        ),
        "core_fields": ["需求單號", "銷貨單號", "需求日期", "品項名稱", "需求狀態"],
    },
    {
        "_key": "rgc_mrp_01",
        "sql_template": (
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_58' "
            "AND d['MRP日期'] >= '{start_date}' "
            "AND d['MRP日期'] <= '{end_date}' "
            "SORT d['MRP日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'MRP單號': d['MRP單號'], "
            "'生產需求單號': d['生產需求單號'], "
            "'MRP日期': d['MRP日期'], "
            "'品項名稱': d['品項名稱'], "
            "'需求數量': d['需求數量'], "
            "'庫存狀態': d['庫存狀態']}"
        ),
        "core_fields": ["MRP單號", "生產需求單號", "MRP日期", "品項名稱", "庫存狀態"],
    },
    {
        "_key": "rgc_wo_01",
        "sql_template": (
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_55' "
            "AND d['工單日期'] >= '{start_date}' "
            "AND d['工單日期'] <= '{end_date}' "
            "SORT d['工單日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'工單編號': d['工單編號'], "
            "'生產需求單號': d['生產需求單號'], "
            "'工單日期': d['工單日期'], "
            "'品項名稱': d['品項名稱'], "
            "'生產數量': d['生產數量'], "
            "'工單狀態': d['工單狀態']}"
        ),
        "core_fields": ["工單編號", "生產需求單號", "工單日期", "品項名稱", "工單狀態"],
    },
    {
        "_key": "rgc_pick_01",
        "sql_template": (
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_42' "
            "AND d['領料日期'] >= '{start_date}' "
            "AND d['領料日期'] <= '{end_date}' "
            "SORT d['領料日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'領料單號': d['領料單號'], "
            "'工單編號': d['工單編號'], "
            "'領料日期': d['領料日期'], "
            "'實發數量': d['實發數量'], "
            "'領料狀態': d['領料狀態']}"
        ),
        "core_fields": ["領料單號", "工單編號", "領料日期", "實發數量", "領料狀態"],
    },
    {
        "_key": "rgc_dispatch_01",
        "sql_template": (
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_44' "
            "AND d['派工日期'] >= '{start_date}' "
            "AND d['派工日期'] <= '{end_date}' "
            "SORT d['派工日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'派工單號': d['派工單號'], "
            "'工單編號': d['工單編號'], "
            "'派工日期': d['派工日期'], "
            "'品項名稱': d['品項名稱'], "
            "'派工數量': d['派工數量'], "
            "'派工狀態': d['派工狀態']}"
        ),
        "core_fields": ["派工單號", "工單編號", "派工日期", "品項名稱", "派工狀態"],
    },
    {
        "_key": "rgc_iqc_01",
        "sql_template": (
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_51' "
            "AND d['檢驗日期'] >= '{start_date}' "
            "AND d['檢驗日期'] <= '{end_date}' "
            "SORT d['檢驗日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'檢驗單號': d['檢驗單號'], "
            "'來源進貨單號': d['來源進貨單號'], "
            "'檢驗日期': d['檢驗日期'], "
            "'品項名稱': d['品項名稱'], "
            "'檢驗結果': d['檢驗結果'], "
            "'合格率': d['合格率']}"
        ),
        "core_fields": ["檢驗單號", "來源進貨單號", "檢驗日期", "檢驗結果", "合格率"],
    },
    {
        "_key": "rgc_fg_01",
        "sql_template": (
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_63' "
            "AND d['入庫日期'] >= '{start_date}' "
            "AND d['入庫日期'] <= '{end_date}' "
            "SORT d['入庫日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'入庫單號': d['入庫單號'], "
            "'工單編號': d['工單編號'], "
            "'入庫日期': d['入庫日期'], "
            "'品項名稱': d['品項名稱'], "
            "'入庫數量': d['入庫數量'], "
            "'入庫狀態': d['入庫狀態']}"
        ),
        "core_fields": ["入庫單號", "工單編號", "入庫日期", "品項名稱", "入庫狀態"],
    },
    {
        "_key": "rgc_budget_01",
        "sql_template": (
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_71' "
            "AND d['預算日期'] >= '{start_date}' "
            "AND d['預算日期'] <= '{end_date}' "
            "SORT d['預算日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'預算單號': d['預算單號'], "
            "'MRP單號': d['MRP單號'], "
            "'預算日期': d['預算日期'], "
            "'預算金額': d['預算金額'], "
            "'預算狀態': d['預算狀態']}"
        ),
        "core_fields": ["預算單號", "MRP單號", "預算日期", "預算金額", "預算狀態"],
    },
    {
        "_key": "rgc_production_flow_01",
        "sql_template": (
            "LET so = (FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_26' "
            "AND d['銷貨日期'] >= '{start_date}' "
            "AND d['銷貨日期'] <= '{end_date}' "
            "SORT d['銷貨日期'] DESC LIMIT 3 RETURN d) "
            "LET pd = (FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_57' "
            "SORT d['需求日期'] DESC LIMIT 5 RETURN d) "
            "LET wo = (FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_55' "
            "SORT d['工單日期'] DESC LIMIT 5 RETURN d) "
            "LET fg = (FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_63' "
            "SORT d['入庫日期'] DESC LIMIT 5 RETURN d) "
            "RETURN {'銷貨單': so, '生產需求': pd, '製令單': wo, '成品入庫': fg}"
        ),
        "core_fields": ["銷貨單號", "需求單號", "工單編號", "入庫單號"],
    },
]


def patch_intent(fix: dict[str, Any]) -> bool:
    key = fix["_key"]
    payload = {k: v for k, v in fix.items() if k != "_key"}
    r = subprocess.run(
        [
            "curl", "-s", "-u", AUTH,
            f"{ARANGO_URL}/_db/{DB}/_api/document/intent_catalog/{key}",
            "-X", "PATCH",
            "-H", "Content-Type: application/json",
            "-d", json.dumps(payload),
        ],
        capture_output=True, text=True,
    )
    body: dict[str, Any] = json.loads(r.stdout)
    return not body.get("error", False)


def main() -> None:
    print("=" * 60)
    print("修正意圖 SQL template：數字 field_id → 中文欄位名")
    print("=" * 60)

    ok = 0
    for fix in FIXES:
        success = patch_intent(fix)
        marker = "✓" if success else "✗"
        name = fix.get("name", fix["_key"])
        print(f"  {marker} {fix['_key']}: {name}")
        if success:
            ok += 1

    print(f"\n修正結果: {ok}/{len(FIXES)} 筆成功")


if __name__ == "__main__":
    main()
