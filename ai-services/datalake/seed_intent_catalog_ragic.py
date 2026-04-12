#!/usr/bin/env python3
"""
@file        seed_intent_catalog_ragic.py
@description Ragic data intents (Groups A-C: Phase 1 with real field IDs; Groups D-F: Phase 2 placeholders).
              Phase 1 (Groups A-C) implemented with actual Ragic table structures:
              - Group A: CFG7_EMPLOYEE, CFG2_DEPT (Employee & Department)
              - Group B: CFG9_ITEM, CFG3_WAREHOUSE (Items & Warehouses)
              - Group C: ERP48_PURCHASE_ORDER, CFG10_VENDOR (Purchase Orders & Vendors)
              Phase 2 (Groups D-F) remain as placeholders for future migration.
@lastUpdate  2026-04-13 01:54:04
@author      Daniel Chung
@version     2.1.0
"""

from .seed_intent_catalog_shared import make_doc, make_orch_doc, DA

# ===========================================================================
# Group A — 員工與部門 CFG7_EMPLOYEE / CFG2_DEPT (3 intents)
# ===========================================================================

GROUP_A = [
    make_doc(
        "rgc_a01",
        DA,
        name="員工基本資料查詢",
        description="查詢 Ragic 員工表中的基本資料，包含編號、姓名、部門、聯絡方式等",
        intent_type="filter",
        group="員工管理",
        tables=["CFG7_EMPLOYEE"],
        generation_strategy="tool_calling",
        sql_template=(
            'SELECT "1015428", "1015429", "1015495", "1015439", "1015444" '
            "FROM read_parquet('s3://ragic/employees/*.parquet') "
            "WHERE \"1015428\" = '{employee_id}' LIMIT 1"
        ),
        core_fields=["1015428", "1015429", "1015495", "1015439"],
        nl_examples=[
            "查詢員工 E001 的資料",
            "員工李明的部門和聯絡方式",
            "查詢王美玲的基本資訊",
        ],
    ),
    make_doc(
        "rgc_a02",
        DA,
        name="部門人員統計",
        description="依部門統計員工人數及任職狀態分佈",
        intent_type="aggregate",
        group="員工管理",
        tables=["CFG7_EMPLOYEE", "CFG2_DEPT"],
        generation_strategy="tool_calling",
        query_type="aggregate",
        sql_template=(
            'SELECT "1015495", COUNT(*) AS emp_count, COUNT(CASE WHEN "1015443" = \'在職\' THEN 1 END) AS active_count '
            "FROM read_parquet('s3://ragic/employees/*.parquet') "
            'GROUP BY "1015495" ORDER BY emp_count DESC'
        ),
        core_fields=["1015495", "emp_count", "active_count"],
        nl_examples=[
            "各部門有多少員工",
            "銷售部的人數統計",
            "每個部門的在職人數",
        ],
    ),
    make_doc(
        "rgc_a03",
        DA,
        name="新入職員工查詢",
        description="查詢指定期間新到職的員工清單",
        intent_type="filter",
        group="員工管理",
        tables=["CFG7_EMPLOYEE"],
        generation_strategy="tool_calling",
        sql_template=(
            'SELECT "1015428", "1015429", "1015444", "1015495", "1015496" '
            "FROM read_parquet('s3://ragic/employees/*.parquet') "
            "WHERE \"1015444\" >= '{start_date}' AND \"1015444\" <= '{end_date}' "
            'ORDER BY "1015444" DESC LIMIT {limit}'
        ),
        core_fields=["1015428", "1015429", "1015444", "1015495"],
        nl_examples=[
            "這個月新入職的員工",
            "上季新招聘的人員名單",
            "2026年3月入職的員工",
        ],
    ),
]

# ===========================================================================
# Group B — 物料與倉庫 CFG9_ITEM / CFG3_WAREHOUSE (3 intents)
# ===========================================================================

GROUP_B = [
    make_doc(
        "rgc_b01",
        DA,
        name="品項基本資料查詢",
        description="查詢 Ragic 品項表中的編碼、名稱、分類、規格及庫存等資訊",
        intent_type="filter",
        group="物料管理",
        tables=["CFG9_ITEM"],
        generation_strategy="tool_calling",
        sql_template=(
            'SELECT "1015486", "1015483", "1018425", "1018426", "1018434", "1018430" '
            "FROM read_parquet('s3://ragic/items/*.parquet') "
            "WHERE \"1015486\" = '{item_code}' LIMIT 1"
        ),
        core_fields=["1015486", "1015483", "1018425", "1018434"],
        nl_examples=[
            "查詢品項 IT001 的資料",
            "品項白鐵不鏽鋼螺絲的規格和單價",
            "查詢品項編碼 KIT-2024-001",
        ],
    ),
    make_doc(
        "rgc_b02",
        DA,
        name="倉庫儲位庫存查詢",
        description="查詢倉庫及儲位的庫存分佈情況",
        intent_type="filter",
        group="物料管理",
        tables=["CFG3_WAREHOUSE"],
        generation_strategy="tool_calling",
        sql_template=(
            'SELECT "1015398", "1015397", "1015403", "1015406", "1015402" '
            "FROM read_parquet('s3://ragic/warehouses/*.parquet') "
            "WHERE \"1015398\" = '{warehouse_code}' LIMIT {limit}"
        ),
        core_fields=["1015398", "1015397", "1015403", "1015406"],
        nl_examples=[
            "查詢倉庫 WH-001 的儲位清單",
            "主倉庫的所有儲位",
            "料架 A-01 下有哪些儲位",
        ],
    ),
    make_doc(
        "rgc_b03",
        DA,
        name="品項分類及採購成本統計",
        description="按主副類別統計品項數量及採購成本",
        intent_type="aggregate",
        group="物料管理",
        tables=["CFG9_ITEM"],
        generation_strategy="tool_calling",
        query_type="aggregate",
        sql_template=(
            'SELECT "1018425", "1018426", COUNT(*) AS item_count, AVG("1018432") AS avg_cost '
            "FROM read_parquet('s3://ragic/items/*.parquet') "
            'GROUP BY "1018425", "1018426" ORDER BY "1018425"'
        ),
        core_fields=["1018425", "1018426", "item_count", "avg_cost"],
        nl_examples=[
            "各主類別的品項數量統計",
            "電子類品項的平均採購成本",
            "按分類統計品項和成本",
        ],
    ),
]

# ===========================================================================
# Group C — 供應商與採購 ERP48_PURCHASE_ORDER / CFG10_VENDOR (3 intents)
# ===========================================================================

GROUP_C = [
    make_doc(
        "rgc_c01",
        DA,
        name="進貨訂單查詢",
        description="查詢 Ragic 進貨訂單表中的訂單編號、日期、供應商、金額等關鍵資訊",
        intent_type="filter",
        group="採購管理",
        tables=["ERP48_PURCHASE_ORDER"],
        generation_strategy="tool_calling",
        sql_template=(
            'SELECT "1023120", "1023123", "1023121", "1023122", "1023148" '
            "FROM read_parquet('s3://ragic/purchase_orders/*.parquet') "
            "WHERE \"1023120\" = '{po_number}' LIMIT 1"
        ),
        core_fields=["1023120", "1023123", "1023121", "1023148"],
        nl_examples=[
            "查詢進貨單 PO2026001 的資料",
            "進貨單編號 PO2026-003 的詳細內容",
            "查詢供應商ABC公司的進貨訂單",
        ],
    ),
    make_doc(
        "rgc_c02",
        DA,
        name="供應商採購金額統計",
        description="依供應商統計採購總額、訂單數及平均採購金額",
        intent_type="aggregate",
        group="採購管理",
        tables=["ERP48_PURCHASE_ORDER", "CFG10_VENDOR"],
        generation_strategy="tool_calling",
        query_type="aggregate",
        sql_template=(
            'SELECT "1023122", COUNT(*) AS po_count, SUM("1023148") AS total_amount, AVG("1023148") AS avg_amount '
            "FROM read_parquet('s3://ragic/purchase_orders/*.parquet') "
            'GROUP BY "1023122" ORDER BY total_amount DESC'
        ),
        core_fields=["1023122", "po_count", "total_amount", "avg_amount"],
        nl_examples=[
            "各供應商的採購金額統計",
            "與供應商ABC的採購金額",
            "採購金額排名前10的供應商",
        ],
    ),
    make_doc(
        "rgc_c03",
        DA,
        name="進貨訂單明細及收貨統計",
        description="按進貨訂單匯總明細品項、採購數量、收貨數量及退貨情況",
        intent_type="aggregate",
        group="採購管理",
        tables=["ERP48_PURCHASE_ORDER"],
        generation_strategy="tool_calling",
        query_type="aggregate",
        sql_template=(
            'SELECT "1023120", "1023129", SUM("1023130") AS total_qty, SUM("1023131") AS received_qty, SUM("1023154") AS return_qty '
            "FROM read_parquet('s3://ragic/purchase_orders/*.parquet') "
            'GROUP BY "1023120", "1023129" ORDER BY "1023120"'
        ),
        core_fields=["1023120", "1023129", "total_qty", "received_qty", "return_qty"],
        nl_examples=[
            "進貨訂單的採購數量和收貨情況",
            "未全部收貨的進貨訂單",
            "有退貨的進貨訂單明細",
        ],
    ),
]

# ===========================================================================
# Group D — 銷售與客戶 (3 intents)
# TODO: Add Ragic intents during migration Phase 2 (T-006)
# ===========================================================================

GROUP_D = [
    make_doc(
        "rgc_d01",
        DA,
        name="銷售訂單查詢",
        description="查詢 Ragic 銷售訂單相關資訊",
        intent_type="filter",
        group="銷售管理",
        tables=["SALES_ORDER"],
        generation_strategy="tool_calling",
        sql_template=(
            "SELECT so_id, so_date, customer_id, so_amount, status "
            "FROM read_parquet('s3://ragic/sales_orders/*.parquet') "
            "WHERE so_id = '{so_id}' LIMIT 1"
        ),
        core_fields=["so_id", "so_date", "customer_id", "so_amount"],
        nl_examples=[
            "查詢銷售單 SO001 的資料",
            "銷售訂單 SO050 的狀態",
        ],
    ),
    make_doc(
        "rgc_d02",
        DA,
        name="客戶銷售金額統計",
        description="依客戶統計銷售金額",
        intent_type="aggregate",
        group="銷售管理",
        tables=["SALES_ORDER"],
        generation_strategy="tool_calling",
        query_type="aggregate",
        sql_template=(
            "SELECT customer_id, SUM(so_amount) AS total_sales "
            "FROM read_parquet('s3://ragic/sales_orders/*.parquet') "
            "GROUP BY customer_id"
        ),
        core_fields=["customer_id", "total_sales"],
        nl_examples=[
            "各客戶的銷售金額",
            "客戶 C001 的銷售總額",
        ],
    ),
    make_doc(
        "rgc_d03",
        DA,
        name="銷售訂單狀態統計",
        description="按狀態統計銷售訂單數量",
        intent_type="aggregate",
        group="銷售管理",
        tables=["SALES_ORDER"],
        generation_strategy="tool_calling",
        query_type="aggregate",
        sql_template=(
            "SELECT status, COUNT(*) AS so_count, SUM(so_amount) AS total_amount "
            "FROM read_parquet('s3://ragic/sales_orders/*.parquet') "
            "GROUP BY status"
        ),
        core_fields=["status", "so_count", "total_amount"],
        nl_examples=[
            "銷售訂單狀態統計",
            "待出貨的訂單有多少",
        ],
    ),
]

# ===========================================================================
# Group E — 生產與製造 (3 intents)
# TODO: Add Ragic intents during migration Phase 2 (T-006)
# ===========================================================================

GROUP_E = [
    make_doc(
        "rgc_e01",
        DA,
        name="生產訂單查詢",
        description="查詢 Ragic 生產訂單相關資訊",
        intent_type="filter",
        group="生產管理",
        tables=["WORK_ORDER"],
        generation_strategy="tool_calling",
        sql_template=(
            "SELECT wo_id, wo_date, product_id, quantity, status "
            "FROM read_parquet('s3://ragic/work_orders/*.parquet') "
            "WHERE wo_id = '{wo_id}' LIMIT 1"
        ),
        core_fields=["wo_id", "wo_date", "product_id", "quantity"],
        nl_examples=[
            "查詢工單 WO001 的資料",
            "工單 WO050 的進度",
        ],
    ),
    make_doc(
        "rgc_e02",
        DA,
        name="生產產能統計",
        description="統計生產訂單的產量和進度",
        intent_type="aggregate",
        group="生產管理",
        tables=["WORK_ORDER"],
        generation_strategy="tool_calling",
        query_type="aggregate",
        sql_template=(
            "SELECT status, COUNT(*) AS wo_count, SUM(quantity) AS total_quantity "
            "FROM read_parquet('s3://ragic/work_orders/*.parquet') "
            "GROUP BY status"
        ),
        core_fields=["status", "wo_count", "total_quantity"],
        nl_examples=[
            "生產訂單進度統計",
            "已完成的工單數量",
        ],
    ),
    make_doc(
        "rgc_e03",
        DA,
        name="生產成本分析",
        description="分析生產訂單的成本",
        intent_type="aggregate",
        group="生產管理",
        tables=["WORK_ORDER"],
        generation_strategy="tool_calling",
        query_type="aggregate",
        sql_template=(
            "SELECT product_id, AVG(unit_cost) AS avg_cost "
            "FROM read_parquet('s3://ragic/work_orders/*.parquet') "
            "GROUP BY product_id"
        ),
        core_fields=["product_id", "avg_cost"],
        nl_examples=[
            "產品的平均成本",
            "生產成本分析",
        ],
    ),
]

# ===========================================================================
# Group F — 財務與會計 (3 intents)
# TODO: Add Ragic intents during migration Phase 2 (T-006)
# ===========================================================================

GROUP_F = [
    make_doc(
        "rgc_f01",
        DA,
        name="發票查詢",
        description="查詢 Ragic 發票表中的發票資訊",
        intent_type="filter",
        group="財務管理",
        tables=["INVOICE"],
        generation_strategy="tool_calling",
        sql_template=(
            "SELECT inv_id, inv_date, vendor_id, inv_amount, status "
            "FROM read_parquet('s3://ragic/invoices/*.parquet') "
            "WHERE inv_id = '{inv_id}' LIMIT 1"
        ),
        core_fields=["inv_id", "inv_date", "vendor_id", "inv_amount"],
        nl_examples=[
            "查詢發票 INV001 的資料",
            "發票 INV050 的狀態",
        ],
    ),
    make_doc(
        "rgc_f02",
        DA,
        name="付款記錄統計",
        description="統計付款記錄和應付帳款",
        intent_type="aggregate",
        group="財務管理",
        tables=["INVOICE"],
        generation_strategy="tool_calling",
        query_type="aggregate",
        sql_template=(
            "SELECT status, COUNT(*) AS inv_count, SUM(inv_amount) AS total_amount "
            "FROM read_parquet('s3://ragic/invoices/*.parquet') "
            "GROUP BY status"
        ),
        core_fields=["status", "inv_count", "total_amount"],
        nl_examples=[
            "應付發票統計",
            "待付款的發票金額",
        ],
    ),
    make_doc(
        "rgc_f03",
        DA,
        name="供應商應付款查詢",
        description="查詢供應商的應付款金額",
        intent_type="aggregate",
        group="財務管理",
        tables=["INVOICE"],
        generation_strategy="tool_calling",
        query_type="aggregate",
        sql_template=(
            "SELECT vendor_id, SUM(inv_amount) AS payable_amount "
            "FROM read_parquet('s3://ragic/invoices/*.parquet') "
            "WHERE status = 'unpaid' "
            "GROUP BY vendor_id"
        ),
        core_fields=["vendor_id", "payable_amount"],
        nl_examples=[
            "各供應商的應付款",
            "供應商 V001 的應付金額",
        ],
    ),
]

# ===========================================================================
# Orchestrator Intents — Ragic (reuses SAP orchestrator model)
# ===========================================================================

ORCHESTRATOR_INTENTS = [
    make_orch_doc(
        "orch_ragic_data_query",
        name="Ragic 資料查詢",
        description="查詢 Ragic 資料（員工、物料、採購、銷售等），路由至 Data Agent NL→SQL Pipeline 處理。",
        intent_type="task",
        domain="data_query",
        bpa_id="data-agent",
        capabilities=["ragic_query", "nl2sql"],
        task_type="query",
        confidence_threshold=0.7,
        priority=10,
        response_strategy="handoff_bpa",
        nl_examples=[
            "Ragic 的員工有多少",
            "查詢 Ragic 物料清單",
            "Ragic 採購訂單統計",
        ],
    ),
]
