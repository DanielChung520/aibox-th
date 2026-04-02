#!/usr/bin/env python3
"""
@file        seed_intent_catalog_ragic.py
@description Ragic data intents (Groups A-F) with placeholder intent definitions.
             During Phase 2 migration (T-006), these templates will be populated with
             actual Ragic table structures and semantics.
@lastUpdate  2026-03-29 02:42:47
@author      Daniel Chung
@version     1.0.0
"""

from .seed_intent_catalog_shared import make_doc, make_orch_doc, DA

# ===========================================================================
# Group A — 員工與部門 CFG7_EMPLOYEE / CFG2_DEPT (3 intents)
# TODO: Add Ragic intents during migration Phase 2 (T-006)
# ===========================================================================

GROUP_A = [
    make_doc(
        "rgc_a01",
        DA,
        name="員工基本資料查詢",
        description="查詢 Ragic 員工表中的基本資料，包含編號、姓名、部門等",
        intent_type="filter",
        group="員工管理",
        tables=["CFG7_EMPLOYEE"],
        generation_strategy="template",
        sql_template=(
            "SELECT emp_id, emp_name, dept_id, email, hire_date "
            "FROM read_parquet('s3://ragic/employees/*.parquet') "
            "WHERE emp_id = '{employee_id}' LIMIT 1"
        ),
        core_fields=["emp_id", "emp_name", "dept_id", "email"],
        nl_examples=[
            "查詢員工 E001 的資料",
            "員工 E050 的部門是什麼",
        ],
    ),
    make_doc(
        "rgc_a02",
        DA,
        name="部門人員統計",
        description="依部門統計員工人數及相關信息",
        intent_type="aggregate",
        group="員工管理",
        tables=["CFG7_EMPLOYEE", "CFG2_DEPT"],
        generation_strategy="template",
        sql_template=(
            "SELECT d.dept_id, d.dept_name, COUNT(e.emp_id) AS emp_count "
            "FROM read_parquet('s3://ragic/departments/*.parquet') AS d "
            "LEFT JOIN read_parquet('s3://ragic/employees/*.parquet') AS e "
            "ON d.dept_id = e.dept_id "
            "GROUP BY d.dept_id, d.dept_name"
        ),
        core_fields=["dept_id", "dept_name", "emp_count"],
        nl_examples=[
            "各部門的人員數量",
            "部門 D001 有多少員工",
        ],
    ),
    make_doc(
        "rgc_a03",
        DA,
        name="新入職員工查詢",
        description="查詢指定期間新入職的員工清單",
        intent_type="filter",
        group="員工管理",
        tables=["CFG7_EMPLOYEE"],
        generation_strategy="template",
        sql_template=(
            "SELECT emp_id, emp_name, hire_date, dept_id "
            "FROM read_parquet('s3://ragic/employees/*.parquet') "
            "WHERE hire_date >= '{start_date}' AND hire_date <= '{end_date}' "
            "ORDER BY hire_date DESC LIMIT {limit}"
        ),
        core_fields=["emp_id", "emp_name", "hire_date"],
        nl_examples=[
            "這個月新入職的員工",
            "上季新招聘的人員",
        ],
    ),
]

# ===========================================================================
# Group B — 物料與倉庫 CFG8_ITEM / CFG3_WAREHOUSE (3 intents)
# TODO: Add Ragic intents during migration Phase 2 (T-006)
# ===========================================================================

GROUP_B = [
    make_doc(
        "rgc_b01",
        DA,
        name="Ragic 物料清單查詢",
        description="查詢 Ragic 物料表中的基本資訊",
        intent_type="filter",
        group="物料管理",
        tables=["CFG8_ITEM"],
        generation_strategy="template",
        sql_template=(
            "SELECT item_id, item_name, item_category, unit_price "
            "FROM read_parquet('s3://ragic/items/*.parquet') "
            "WHERE item_id = '{item_id}' LIMIT 1"
        ),
        core_fields=["item_id", "item_name", "item_category", "unit_price"],
        nl_examples=[
            "查詢物料 IT001 的資料",
            "物料 IT050 的單價是多少",
        ],
    ),
    make_doc(
        "rgc_b02",
        DA,
        name="倉庫庫存統計",
        description="依倉庫統計物料庫存量",
        intent_type="aggregate",
        group="物料管理",
        tables=["CFG3_WAREHOUSE"],
        generation_strategy="template",
        sql_template=(
            "SELECT warehouse_id, warehouse_name, SUM(stock_qty) AS total_stock "
            "FROM read_parquet('s3://ragic/warehouses/*.parquet') "
            "GROUP BY warehouse_id, warehouse_name"
        ),
        core_fields=["warehouse_id", "warehouse_name", "total_stock"],
        nl_examples=[
            "各倉庫的庫存總量",
            "倉庫 W001 的庫存",
        ],
    ),
    make_doc(
        "rgc_b03",
        DA,
        name="物料類別統計",
        description="按物料類別統計物料數量",
        intent_type="aggregate",
        group="物料管理",
        tables=["CFG8_ITEM"],
        generation_strategy="template",
        sql_template=(
            "SELECT item_category, COUNT(*) AS item_count "
            "FROM read_parquet('s3://ragic/items/*.parquet') "
            "GROUP BY item_category"
        ),
        core_fields=["item_category", "item_count"],
        nl_examples=[
            "各物料類別有多少件",
            "物料分類統計",
        ],
    ),
]

# ===========================================================================
# Group C — 供應商與採購 ERP48_PURCHASE_ORDER / CFG9_VENDOR (3 intents)
# TODO: Add Ragic intents during migration Phase 2 (T-006)
# ===========================================================================

GROUP_C = [
    make_doc(
        "rgc_c01",
        DA,
        name="採購訂單查詢",
        description="查詢 Ragic 採購訂單表中的訂單資訊",
        intent_type="filter",
        group="採購管理",
        tables=["ERP48_PURCHASE_ORDER"],
        generation_strategy="template",
        sql_template=(
            "SELECT po_id, po_date, vendor_id, po_amount, status "
            "FROM read_parquet('s3://ragic/purchase_orders/*.parquet') "
            "WHERE po_id = '{po_id}' LIMIT 1"
        ),
        core_fields=["po_id", "po_date", "vendor_id", "po_amount"],
        nl_examples=[
            "查詢採購單 PO001 的資料",
            "採購訂單 PO050 的狀態",
        ],
    ),
    make_doc(
        "rgc_c02",
        DA,
        name="供應商採購金額統計",
        description="依供應商統計採購金額",
        intent_type="aggregate",
        group="採購管理",
        tables=["ERP48_PURCHASE_ORDER", "CFG9_VENDOR"],
        generation_strategy="template",
        sql_template=(
            "SELECT v.vendor_id, v.vendor_name, SUM(po.po_amount) AS total_amount "
            "FROM read_parquet('s3://ragic/purchase_orders/*.parquet') AS po "
            "LEFT JOIN read_parquet('s3://ragic/vendors/*.parquet') AS v "
            "ON po.vendor_id = v.vendor_id "
            "GROUP BY v.vendor_id, v.vendor_name"
        ),
        core_fields=["vendor_id", "vendor_name", "total_amount"],
        nl_examples=[
            "各供應商的採購金額",
            "供應商 V001 的採購總額",
        ],
    ),
    make_doc(
        "rgc_c03",
        DA,
        name="採購訂單狀態統計",
        description="按訂單狀態統計採購訂單數量",
        intent_type="aggregate",
        group="採購管理",
        tables=["ERP48_PURCHASE_ORDER"],
        generation_strategy="template",
        sql_template=(
            "SELECT status, COUNT(*) AS po_count, SUM(po_amount) AS total_amount "
            "FROM read_parquet('s3://ragic/purchase_orders/*.parquet') "
            "GROUP BY status"
        ),
        core_fields=["status", "po_count", "total_amount"],
        nl_examples=[
            "採購訂單狀態統計",
            "待確認的訂單有多少",
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
        generation_strategy="template",
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
        generation_strategy="template",
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
        generation_strategy="template",
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
        generation_strategy="template",
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
        generation_strategy="template",
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
        generation_strategy="template",
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
        generation_strategy="template",
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
        generation_strategy="template",
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
        generation_strategy="template",
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
