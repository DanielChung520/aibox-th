#!/usr/bin/env python3
"""
@file        seed_intent_catalog_sap.py
@description SAP data intents (Groups A-F) and orchestrator intents for intent catalog seeding.
@lastUpdate  2026-03-29 02:42:47
@author      Daniel Chung
@version     1.0.0
"""

from .seed_intent_catalog_shared import make_doc, make_orch_doc, DA

# ===========================================================================
# Group A — 採購訂單 EKKO/EKPO (7 intents)
# ===========================================================================

GROUP_A = [
    make_doc(
        "mm_a01",
        DA,
        name="採購訂單查詢（日期範圍）",
        description="依日期範圍查詢採購訂單清單，支援年、月、季度等時間篩選",
        intent_type="filter",
        group="採購",
        tables=["EKKO"],
        generation_strategy="template",
        sql_template=(
            "SELECT EBELN, LIFNR, WAERS, AEDAT, STATP "
            "FROM read_parquet('s3://sap/mm/ekko/*.parquet') "
            "WHERE AEDAT >= '{start_date}' AND AEDAT <= '{end_date}' "
            "ORDER BY AEDAT DESC LIMIT {limit}"
        ),
        core_fields=["EBELN", "AEDAT", "LIFNR", "WAERS", "STATP"],
        nl_examples=[
            "查詢 2025 年 3 月的採購訂單",
            "2024 年的採購訂單有哪些",
            "今年 Q1 的採購訂單",
            "上個月的採購單",
        ],
    ),
    make_doc(
        "mm_a02",
        DA,
        name="採購訂單明細（含供應商 JOIN）",
        description="查詢採購訂單行項目明細，JOIN 供應商主檔取得供應商名稱",
        intent_type="join",
        group="採購",
        tables=["EKKO", "EKPO", "LFA1"],
        generation_strategy="small_llm",
        sql_template=(
            "SELECT h.EBELN, h.LIFNR, v.NAME1 AS vendor_name, "
            "p.EBELP, p.MATNR, p.TXZ01, p.MENGE, p.MEINS, p.NETPR "
            "FROM read_parquet('s3://sap/mm/ekko/*.parquet') AS h "
            "JOIN read_parquet('s3://sap/mm/ekpo/*.parquet') AS p ON h.EBELN = p.EBELN "
            "LEFT JOIN read_parquet('s3://sap/mm/lfa1/*.parquet') AS v ON h.LIFNR = v.LIFNR "
            "WHERE h.EBELN = '{po_number}' "
            "LIMIT {limit}"
        ),
        core_fields=["EBELN", "EBELP", "LIFNR", "MATNR", "MENGE", "NETPR"],
        nl_examples=[
            "採購單 4500000001 的詳細資訊，包含供應商名稱",
            "供應商 V001 上個月賣了什麼物料給我們",
            "查詢採購訂單行項目明細",
        ],
    ),
    make_doc(
        "mm_a03",
        DA,
        name="採購總金額（聚合）",
        description="彙總指定期間的採購總金額，可依公司代碼或幣別分組",
        intent_type="aggregate",
        group="採購",
        tables=["EKKO", "EKPO"],
        generation_strategy="template",
        sql_template=(
            "SELECT SUM(p.MENGE * p.NETPR / p.PEINH) AS total_amount, h.WAERS "
            "FROM read_parquet('s3://sap/mm/ekko/*.parquet') AS h "
            "JOIN read_parquet('s3://sap/mm/ekpo/*.parquet') AS p ON h.EBELN = p.EBELN "
            "WHERE h.AEDAT >= '{start_date}' AND h.AEDAT <= '{end_date}' "
            "GROUP BY h.WAERS"
        ),
        core_fields=["MENGE", "NETPR", "PEINH", "WAERS"],
        nl_examples=[
            "上個月的採購總金額是多少",
            "今年的採購金額合計",
            "2025 年 Q2 採購總金額",
        ],
    ),
    make_doc(
        "mm_a04",
        DA,
        name="採購趨勢（時間序列）",
        description="按月/季度統計採購金額趨勢，用於折線圖或時間序列分析",
        intent_type="time_series",
        group="採購",
        tables=["EKKO", "EKPO"],
        generation_strategy="template",
        sql_template=(
            "SELECT DATE_TRUNC('month', CAST(h.AEDAT AS DATE)) AS month, "
            "SUM(p.MENGE * p.NETPR / p.PEINH) AS total_amount "
            "FROM read_parquet('s3://sap/mm/ekko/*.parquet') AS h "
            "JOIN read_parquet('s3://sap/mm/ekpo/*.parquet') AS p ON h.EBELN = p.EBELN "
            "WHERE h.AEDAT >= '{start_date}' AND h.AEDAT <= '{end_date}' "
            "GROUP BY 1 ORDER BY 1"
        ),
        core_fields=["AEDAT", "MENGE", "NETPR"],
        nl_examples=[
            "過去一年的採購趨勢",
            "每月採購金額走勢",
            "2024 年採購月趨勢",
        ],
    ),
    make_doc(
        "mm_a05",
        DA,
        name="採購金額最高的物料 TOP N",
        description="依採購金額排名，找出採購金額最高的前 N 種物料",
        intent_type="ranking",
        group="採購",
        tables=["EKPO", "MARA"],
        generation_strategy="small_llm",
        sql_template=(
            "SELECT p.MATNR, m.MAKTX AS material_desc, "
            "SUM(p.MENGE * p.NETPR / p.PEINH) AS total_amount "
            "FROM read_parquet('s3://sap/mm/ekpo/*.parquet') AS p "
            "LEFT JOIN read_parquet('s3://sap/mm/mara/*.parquet') AS m ON p.MATNR = m.MATNR "
            "GROUP BY p.MATNR, m.MAKTX "
            "ORDER BY total_amount DESC LIMIT {limit}"
        ),
        core_fields=["MATNR", "MENGE", "NETPR", "PEINH"],
        nl_examples=[
            "採購金額最高的前 10 種物料",
            "哪些物料的採購單價超過 1000",
            "上個月採購金額前 5 的物料及描述",
        ],
    ),
    make_doc(
        "mm_a06",
        DA,
        name="各工廠採購金額",
        description="依工廠分組統計採購金額，用於工廠採購績效比較",
        intent_type="aggregate",
        group="採購",
        tables=["EKPO"],
        generation_strategy="template",
        sql_template=(
            "SELECT WERKS AS plant, "
            "SUM(MENGE * NETPR / PEINH) AS total_amount, "
            "COUNT(DISTINCT EBELN) AS po_count "
            "FROM read_parquet('s3://sap/mm/ekpo/*.parquet') "
            "WHERE WERKS = COALESCE('{plant}', WERKS) "
            "GROUP BY WERKS ORDER BY total_amount DESC"
        ),
        core_fields=["WERKS", "MENGE", "NETPR", "EBELN"],
        nl_examples=[
            "各工廠的採購金額比較",
            "工廠 1000 的採購金額",
            "每個工廠的採購總額",
        ],
    ),
    make_doc(
        "mm_a07",
        DA,
        name="各幣別採購金額分布",
        description="依幣別分組統計採購金額，分析多幣別採購結構",
        intent_type="aggregate",
        group="採購",
        tables=["EKKO", "EKPO"],
        generation_strategy="template",
        sql_template=(
            "SELECT h.WAERS AS currency, "
            "SUM(p.MENGE * p.NETPR / p.PEINH) AS total_amount, "
            "COUNT(DISTINCT h.EBELN) AS po_count "
            "FROM read_parquet('s3://sap/mm/ekko/*.parquet') AS h "
            "JOIN read_parquet('s3://sap/mm/ekpo/*.parquet') AS p ON h.EBELN = p.EBELN "
            "GROUP BY h.WAERS ORDER BY total_amount DESC"
        ),
        core_fields=["WAERS", "MENGE", "NETPR"],
        nl_examples=[
            "各幣別的採購金額分布",
            "採購訂單幣別統計",
            "不同幣別的採購量比較",
        ],
    ),
]

# ===========================================================================
# Group B — 供應商 LFA1 (6 intents)
# ===========================================================================

GROUP_B = [
    make_doc(
        "mm_b01",
        DA,
        name="供應商列表（含國家篩選）",
        description="查詢供應商清單，支援依國家代碼或供應商帳號篩選",
        intent_type="filter",
        group="供應商",
        tables=["LFA1"],
        generation_strategy="template",
        sql_template=(
            "SELECT LIFNR, NAME1, LAND1, ORT01, STCD1 "
            "FROM read_parquet('s3://sap/mm/lfa1/*.parquet') "
            "WHERE LAND1 = COALESCE('{country}', LAND1) "
            "AND LIFNR = COALESCE('{vendor_id}', LIFNR) "
            "ORDER BY LIFNR LIMIT {limit}"
        ),
        core_fields=["LIFNR", "NAME1", "LAND1", "ORT01"],
        nl_examples=[
            "列出所有供應商",
            "台灣的供應商有哪些",
            "供應商 V001 的基本資料",
        ],
    ),
    make_doc(
        "mm_b02",
        DA,
        name="供應商採購金額統計",
        description="依供應商彙總採購金額，分析各供應商的採購佔比",
        intent_type="aggregate",
        group="供應商",
        tables=["EKKO", "EKPO", "LFA1"],
        generation_strategy="small_llm",
        sql_template=(
            "SELECT h.LIFNR, v.NAME1 AS vendor_name, "
            "SUM(p.MENGE * p.NETPR / p.PEINH) AS total_amount "
            "FROM read_parquet('s3://sap/mm/ekko/*.parquet') AS h "
            "JOIN read_parquet('s3://sap/mm/ekpo/*.parquet') AS p ON h.EBELN = p.EBELN "
            "LEFT JOIN read_parquet('s3://sap/mm/lfa1/*.parquet') AS v ON h.LIFNR = v.LIFNR "
            "WHERE h.LIFNR = COALESCE('{vendor_id}', h.LIFNR) "
            "GROUP BY h.LIFNR, v.NAME1 ORDER BY total_amount DESC LIMIT {limit}"
        ),
        core_fields=["LIFNR", "MENGE", "NETPR"],
        nl_examples=[
            "各供應商的採購金額統計",
            "供應商 V003 今年的採購金額趨勢",
        ],
    ),
    make_doc(
        "mm_b03",
        DA,
        name="供應商比較",
        description="比較兩個或多個供應商的採購金額、數量等指標",
        intent_type="comparison",
        group="供應商",
        tables=["EKKO", "EKPO", "LFA1"],
        generation_strategy="small_llm",
        sql_template=(
            "SELECT h.LIFNR, v.NAME1, "
            "SUM(p.MENGE * p.NETPR / p.PEINH) AS total_amount, "
            "COUNT(DISTINCT h.EBELN) AS po_count "
            "FROM read_parquet('s3://sap/mm/ekko/*.parquet') AS h "
            "JOIN read_parquet('s3://sap/mm/ekpo/*.parquet') AS p ON h.EBELN = p.EBELN "
            "LEFT JOIN read_parquet('s3://sap/mm/lfa1/*.parquet') AS v ON h.LIFNR = v.LIFNR "
            "WHERE h.LIFNR IN ({vendor_list}) "
            "GROUP BY h.LIFNR, v.NAME1"
        ),
        core_fields=["LIFNR", "MENGE", "NETPR", "EBELN"],
        nl_examples=[
            "比較供應商 V001 和 V002 的採購金額",
            "供應商 V001 vs V003 的績效",
        ],
    ),
    make_doc(
        "mm_b04",
        DA,
        name="採購金額前 N 的供應商",
        description="排名採購金額最高的供應商，取前 N 名",
        intent_type="ranking",
        group="供應商",
        tables=["EKKO", "EKPO", "LFA1"],
        generation_strategy="small_llm",
        sql_template=(
            "SELECT h.LIFNR, v.NAME1, "
            "SUM(p.MENGE * p.NETPR / p.PEINH) AS total_amount "
            "FROM read_parquet('s3://sap/mm/ekko/*.parquet') AS h "
            "JOIN read_parquet('s3://sap/mm/ekpo/*.parquet') AS p ON h.EBELN = p.EBELN "
            "LEFT JOIN read_parquet('s3://sap/mm/lfa1/*.parquet') AS v ON h.LIFNR = v.LIFNR "
            "GROUP BY h.LIFNR, v.NAME1 ORDER BY total_amount DESC LIMIT {limit}"
        ),
        core_fields=["LIFNR", "MENGE", "NETPR"],
        nl_examples=[
            "採購金額前 10 的供應商",
            "哪個供應商交貨最多",
        ],
    ),
    make_doc(
        "mm_b05",
        DA,
        name="供應商月度採購趨勢",
        description="查詢特定供應商的月度採購金額趨勢，用於時間序列分析",
        intent_type="time_series",
        group="供應商",
        tables=["EKKO", "EKPO"],
        generation_strategy="template",
        sql_template=(
            "SELECT DATE_TRUNC('month', CAST(h.AEDAT AS DATE)) AS month, "
            "SUM(p.MENGE * p.NETPR / p.PEINH) AS total_amount "
            "FROM read_parquet('s3://sap/mm/ekko/*.parquet') AS h "
            "JOIN read_parquet('s3://sap/mm/ekpo/*.parquet') AS p ON h.EBELN = p.EBELN "
            "WHERE h.LIFNR = '{vendor_id}' "
            "AND h.AEDAT >= '{start_date}' AND h.AEDAT <= '{end_date}' "
            "GROUP BY 1 ORDER BY 1"
        ),
        core_fields=["LIFNR", "AEDAT", "MENGE", "NETPR"],
        nl_examples=[
            "供應商 V001 過去半年的月度採購趨勢",
        ],
    ),
    make_doc(
        "mm_b06",
        DA,
        name="供應商供應物料品項（large_llm）",
        description="查詢供應商供應的物料品項數，需要跨採購明細與物料主檔做複雜 JOIN 分析",
        intent_type="join",
        group="供應商",
        tables=["EKKO", "EKPO", "MARA", "LFA1"],
        generation_strategy="large_llm",
        sql_template="",
        core_fields=["LIFNR", "MATNR", "MAKTX"],
        nl_examples=[
            "供應商 V001 供應哪些物料",
            "每個供應商供應的物料品項數",
            "哪個供應商供應最多種物料",
        ],
    ),
]

# ===========================================================================
# Group C — 物料主檔 MARA (4 intents)
# ===========================================================================

GROUP_C = [
    make_doc(
        "mm_c01",
        DA,
        name="物料基本資料查詢",
        description="依物料編號查詢物料主檔基本資料，包含描述、類型、單位等",
        intent_type="filter",
        group="物料",
        tables=["MARA"],
        generation_strategy="template",
        sql_template=(
            "SELECT MATNR, MAKTX, MTART, MATKL, MEINS, BRGEW, GEWEI, ERSDA "
            "FROM read_parquet('s3://sap/mm/mara/*.parquet') "
            "WHERE MATNR = '{material_id}' LIMIT 1"
        ),
        core_fields=["MATNR", "MAKTX", "MTART", "MEINS"],
        nl_examples=[
            "查詢物料 M-0001 的資料",
            "物料 M-0050 的重量是多少",
        ],
    ),
    make_doc(
        "mm_c02",
        DA,
        name="物料類型篩選",
        description="依物料類型（MTART）篩選物料清單，如原物料、半成品、成品",
        intent_type="filter",
        group="物料",
        tables=["MARA"],
        generation_strategy="template",
        sql_template=(
            "SELECT MATNR, MAKTX, MTART, MATKL, MEINS "
            "FROM read_parquet('s3://sap/mm/mara/*.parquet') "
            "WHERE MTART = '{material_type}' "
            "ORDER BY MATNR LIMIT {limit}"
        ),
        core_fields=["MATNR", "MAKTX", "MTART"],
        nl_examples=[
            "列出所有原物料",
            "半成品物料有幾個",
            "列出所有成品物料",
        ],
    ),
    make_doc(
        "mm_c03",
        DA,
        name="各物料群組統計",
        description="依物料群組（MATKL）彙總統計物料數量，分析物料結構",
        intent_type="aggregate",
        group="物料",
        tables=["MARA"],
        generation_strategy="template",
        sql_template=(
            "SELECT MATKL AS material_group, COUNT(*) AS count "
            "FROM read_parquet('s3://sap/mm/mara/*.parquet') "
            "GROUP BY MATKL ORDER BY count DESC LIMIT {limit}"
        ),
        core_fields=["MATKL"],
        nl_examples=[
            "各物料群組有多少物料",
            "物料數量最多的物料類型",
        ],
    ),
    make_doc(
        "mm_c04",
        DA,
        name="新增物料查詢",
        description="查詢指定期間內新建立的物料清單，依建立日期篩選",
        intent_type="filter",
        group="物料",
        tables=["MARA"],
        generation_strategy="template",
        sql_template=(
            "SELECT MATNR, MAKTX, MTART, ERSDA "
            "FROM read_parquet('s3://sap/mm/mara/*.parquet') "
            "WHERE ERSDA >= '{start_date}' AND ERSDA <= '{end_date}' "
            "ORDER BY ERSDA DESC LIMIT {limit}"
        ),
        core_fields=["MATNR", "ERSDA", "MTART"],
        nl_examples=[
            "這個月新增了哪些物料",
            "上季新建立的物料",
        ],
    ),
]

# ===========================================================================
# Group D — 庫存 MARD/MCHB (8 intents)
# ===========================================================================

GROUP_D = [
    make_doc(
        "mm_d01",
        DA,
        name="物料庫存查詢",
        description="查詢特定物料在工廠/倉庫的現有庫存量",
        intent_type="filter",
        group="庫存",
        tables=["MARD"],
        generation_strategy="template",
        sql_template=(
            "SELECT MATNR, WERKS, LGORT, LABST AS unrestricted_stock "
            "FROM read_parquet('s3://sap/mm/mard/*.parquet') "
            "WHERE MATNR = COALESCE('{material_id}', MATNR) "
            "AND WERKS = COALESCE('{plant}', WERKS) "
            "AND LGORT = COALESCE('{storage_loc}', LGORT) "
            "ORDER BY LABST DESC LIMIT {limit}"
        ),
        core_fields=["MATNR", "WERKS", "LGORT", "LABST"],
        nl_examples=[
            "物料 M-0001 的庫存多少",
            "工廠 1000 倉庫 0001 的庫存",
        ],
    ),
    make_doc(
        "mm_d02",
        DA,
        name="各工廠庫存總量",
        description="依工廠彙總庫存總量，用於工廠庫存比較",
        intent_type="aggregate",
        group="庫存",
        tables=["MARD"],
        generation_strategy="template",
        sql_template=(
            "SELECT WERKS AS plant, "
            "SUM(LABST) AS total_unrestricted, "
            "COUNT(DISTINCT MATNR) AS material_count "
            "FROM read_parquet('s3://sap/mm/mard/*.parquet') "
            "GROUP BY WERKS ORDER BY total_unrestricted DESC"
        ),
        core_fields=["WERKS", "LABST"],
        nl_examples=[
            "各工廠的庫存總量",
        ],
    ),
    make_doc(
        "mm_d03",
        DA,
        name="庫存總覽",
        description="全廠庫存彙總總覽，包含限制使用庫存、在途庫存等各類庫存",
        intent_type="aggregate",
        group="庫存",
        tables=["MARD"],
        generation_strategy="template",
        sql_template=(
            "SELECT "
            "SUM(LABST) AS unrestricted, "
            "SUM(EINME) AS in_transit, "
            "SUM(INSME) AS in_quality, "
            "COUNT(DISTINCT MATNR) AS material_count "
            "FROM read_parquet('s3://sap/mm/mard/*.parquet')"
        ),
        core_fields=["LABST", "EINME", "INSME"],
        nl_examples=[
            "目前庫存總覽",
        ],
    ),
    make_doc(
        "mm_d04",
        DA,
        name="低庫存/安全庫存不足物料",
        description="找出庫存量低於安全庫存或低於指定閾值的物料清單",
        intent_type="filter",
        group="庫存",
        tables=["MARD"],
        generation_strategy="template",
        sql_template=(
            "SELECT MATNR, WERKS, LGORT, LABST "
            "FROM read_parquet('s3://sap/mm/mard/*.parquet') "
            "WHERE LABST < {threshold} "
            "ORDER BY LABST ASC LIMIT {limit}"
        ),
        core_fields=["MATNR", "LABST", "WERKS"],
        nl_examples=[
            "庫存低於 100 的物料",
            "安全庫存不足的物料清單",
        ],
    ),
    make_doc(
        "mm_d05",
        DA,
        name="批次庫存查詢",
        description="查詢指定批次編號的批次庫存，或查詢哪些物料有批次庫存",
        intent_type="filter",
        group="庫存",
        tables=["MCHB"],
        generation_strategy="template",
        sql_template=(
            "SELECT MATNR, WERKS, LGORT, CHARG AS batch, CLABS AS batch_stock "
            "FROM read_parquet('s3://sap/mm/mchb/*.parquet') "
            "WHERE CHARG = COALESCE('{batch_id}', CHARG) "
            "AND MATNR = COALESCE('{material_id}', MATNR) "
            "ORDER BY CLABS DESC LIMIT {limit}"
        ),
        core_fields=["MATNR", "CHARG", "CLABS"],
        nl_examples=[
            "批次 B001 的庫存",
            "哪些物料有批次庫存",
        ],
    ),
    make_doc(
        "mm_d06",
        DA,
        name="即將過期批次",
        description="查詢在指定天數內即將到期的批次庫存，避免物料過期損失",
        intent_type="filter",
        group="庫存",
        tables=["MCHB"],
        generation_strategy="template",
        sql_template=(
            "SELECT MATNR, CHARG AS batch, WERKS, CLABS AS stock, VFDAT AS expiry_date "
            "FROM read_parquet('s3://sap/mm/mchb/*.parquet') "
            "WHERE VFDAT BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '{days} days' "
            "AND CLABS > 0 ORDER BY VFDAT ASC LIMIT {limit}"
        ),
        core_fields=["CHARG", "VFDAT", "CLABS"],
        nl_examples=[
            "30 天內即將過期的批次",
        ],
    ),
    make_doc(
        "mm_d07",
        DA,
        name="庫存量最多的前 N 種物料",
        description="依庫存量排名，找出庫存最多的前 N 種物料",
        intent_type="ranking",
        group="庫存",
        tables=["MARD"],
        generation_strategy="template",
        sql_template=(
            "SELECT MATNR, SUM(LABST) AS total_stock "
            "FROM read_parquet('s3://sap/mm/mard/*.parquet') "
            "GROUP BY MATNR ORDER BY total_stock DESC LIMIT {limit}"
        ),
        core_fields=["MATNR", "LABST"],
        nl_examples=[
            "庫存量最多的前 20 種物料",
        ],
    ),
    make_doc(
        "mm_d08",
        DA,
        name="在途庫存（small_llm）",
        description="查詢已下採購單但尚未到貨的在途庫存，需結合採購訂單分析",
        intent_type="filter",
        group="庫存",
        tables=["MARD", "EKPO"],
        generation_strategy="small_llm",
        sql_template="",
        core_fields=["MATNR", "EINME"],
        nl_examples=[
            "在途庫存有多少",
            "在途物料清單及數量",
        ],
    ),
]

# ===========================================================================
# Group E — 庫存異動 MSEG/MKPF (8 intents)
# ===========================================================================

GROUP_E = [
    make_doc(
        "mm_e01",
        DA,
        name="收貨記錄",
        description="查詢指定期間的收貨記錄（移動類型 101），包含物料、數量、工廠",
        intent_type="filter",
        group="庫存異動",
        tables=["MSEG"],
        generation_strategy="small_llm",
        sql_template=(
            "SELECT MBLNR, BUDAT, MATNR, WERKS, LGORT, MENGE, MEINS, DMBTR "
            "FROM read_parquet('s3://sap/mm/mseg/*.parquet') "
            "WHERE BWART = '101' "
            "AND BUDAT >= '{start_date}' AND BUDAT <= '{end_date}' "
            "AND MATNR = COALESCE('{material_id}', MATNR) "
            "AND WERKS = COALESCE('{plant}', WERKS) "
            "ORDER BY BUDAT DESC LIMIT {limit}"
        ),
        core_fields=["BWART", "BUDAT", "MATNR", "MENGE", "DMBTR"],
        nl_examples=[
            "上個月的收貨記錄",
            "物料 M-0010 上個月的所有異動",
            "收貨金額前 10 的物料",
            "工廠 1000 的異動記錄",
        ],
    ),
    make_doc(
        "mm_e02",
        DA,
        name="發料記錄",
        description="查詢指定期間的發料記錄（移動類型 201），支援成本中心篩選",
        intent_type="filter",
        group="庫存異動",
        tables=["MSEG"],
        generation_strategy="small_llm",
        sql_template=(
            "SELECT MBLNR, BUDAT, MATNR, WERKS, KOSTL, MENGE, MEINS, DMBTR "
            "FROM read_parquet('s3://sap/mm/mseg/*.parquet') "
            "WHERE BWART = '201' "
            "AND BUDAT >= '{start_date}' AND BUDAT <= '{end_date}' "
            "AND KOSTL = COALESCE('{cost_center}', KOSTL) "
            "ORDER BY BUDAT DESC LIMIT {limit}"
        ),
        core_fields=["BWART", "BUDAT", "MATNR", "KOSTL", "MENGE"],
        nl_examples=[
            "上個月的發料記錄",
            "物料 M-0001 今年被領料幾次",
            "成本中心 CC001 的領料記錄",
        ],
    ),
    make_doc(
        "mm_e03",
        DA,
        name="異動類型統計",
        description="依移動類型（BWART）彙總統計庫存異動數量與筆數",
        intent_type="aggregate",
        group="庫存異動",
        tables=["MSEG"],
        generation_strategy="template",
        sql_template=(
            "SELECT BWART AS movement_type, "
            "COUNT(*) AS transaction_count, "
            "SUM(MENGE) AS total_qty "
            "FROM read_parquet('s3://sap/mm/mseg/*.parquet') "
            "WHERE BWART = COALESCE('{movement_type}', BWART) "
            "GROUP BY BWART ORDER BY transaction_count DESC"
        ),
        core_fields=["BWART", "MENGE"],
        nl_examples=[
            "各異動類型的數量統計",
            "異動類型 101 的數量",
            "哪種異動類型金額最高",
        ],
    ),
    make_doc(
        "mm_e04",
        DA,
        name="庫存異動趨勢",
        description="按月統計庫存異動量與金額趨勢，用於時間序列分析",
        intent_type="time_series",
        group="庫存異動",
        tables=["MSEG"],
        generation_strategy="small_llm",
        sql_template=(
            "SELECT DATE_TRUNC('month', CAST(BUDAT AS DATE)) AS month, "
            "BWART, SUM(MENGE) AS total_qty, SUM(DMBTR) AS total_amount "
            "FROM read_parquet('s3://sap/mm/mseg/*.parquet') "
            "WHERE BUDAT >= '{start_date}' AND BUDAT <= '{end_date}' "
            "GROUP BY 1, BWART ORDER BY 1, BWART"
        ),
        core_fields=["BUDAT", "BWART", "MENGE", "DMBTR"],
        nl_examples=[
            "過去一年的庫存異動趨勢",
            "上季度每月的收貨與發料對比",
        ],
    ),
    make_doc(
        "mm_e05",
        DA,
        name="物料憑證明細",
        description="查詢指定物料憑證號碼的完整行項目明細",
        intent_type="filter",
        group="庫存異動",
        tables=["MSEG"],
        generation_strategy="small_llm",
        sql_template=(
            "SELECT MBLNR, MJAHR, ZEILE, BUDAT, MATNR, BWART, "
            "MENGE, MEINS, DMBTR, WAERS, WERKS, LGORT "
            "FROM read_parquet('s3://sap/mm/mseg/*.parquet') "
            "WHERE MBLNR = '{document_id}' "
            "ORDER BY ZEILE"
        ),
        core_fields=["MBLNR", "MJAHR", "ZEILE", "BWART"],
        nl_examples=[
            "物料憑證 5000000001 的明細",
        ],
    ),
    make_doc(
        "mm_e06",
        DA,
        name="庫存異動金額",
        description="彙總指定期間庫存異動的財務金額，依移動類型分組",
        intent_type="aggregate",
        group="庫存異動",
        tables=["MSEG"],
        generation_strategy="template",
        sql_template=(
            "SELECT BWART, SUM(DMBTR) AS total_amount, h.WAERS "
            "FROM read_parquet('s3://sap/mm/mseg/*.parquet') AS m "
            "WHERE BUDAT >= '{start_date}' AND BUDAT <= '{end_date}' "
            "GROUP BY BWART, h.WAERS ORDER BY total_amount DESC"
        ),
        core_fields=["BWART", "DMBTR", "BUDAT"],
        nl_examples=[
            "上個月庫存異動的總金額",
            "今年的庫存異動金額",
        ],
    ),
    make_doc(
        "mm_e07",
        DA,
        name="退貨統計（large_llm）",
        description="分析退貨記錄與退貨率，需結合採購訂單與移動類型複雜計算",
        intent_type="aggregate",
        group="庫存異動",
        tables=["MSEG", "EKKO", "LFA1"],
        generation_strategy="large_llm",
        sql_template="",
        core_fields=["BWART", "DMBTR", "LIFNR"],
        nl_examples=[
            "上個月有退貨的物料",
            "上個月的退貨統計",
            "退貨率最高的供應商",
            "各供應商的退貨金額排名",
        ],
    ),
    make_doc(
        "mm_e08",
        DA,
        name="調撥記錄",
        description="查詢庫存調撥記錄（移動類型 311/313），包含來源與目標儲存地點",
        intent_type="filter",
        group="庫存異動",
        tables=["MSEG"],
        generation_strategy="small_llm",
        sql_template=(
            "SELECT MBLNR, BUDAT, MATNR, WERKS, LGORT, UMLGO AS target_sloc, "
            "BWART, MENGE, MEINS "
            "FROM read_parquet('s3://sap/mm/mseg/*.parquet') "
            "WHERE BWART IN ('311','313') "
            "AND BUDAT >= '{start_date}' AND BUDAT <= '{end_date}' "
            "ORDER BY BUDAT DESC LIMIT {limit}"
        ),
        core_fields=["BWART", "LGORT", "UMLGO", "MENGE"],
        nl_examples=[
            "上個月的調撥記錄",
            "哪些物料上個月有調撥進出",
        ],
    ),
]

# ===========================================================================
# Group F — 複合分析 large_llm (4 intents)
# ===========================================================================

GROUP_F = [
    make_doc(
        "mm_f01",
        DA,
        name="採購前置時間分析",
        description="計算從採購訂單建立到收貨的平均前置時間，需跨 EKKO 與 MSEG 做時間差計算",
        intent_type="aggregate",
        group="複合分析",
        tables=["EKKO", "MSEG"],
        generation_strategy="large_llm",
        sql_template="",
        core_fields=["EBELN", "ERDAT", "BUDAT", "LIFNR"],
        nl_examples=[
            "採購到收貨的平均前置時間",
            "哪些物料的前置時間超過 30 天",
            "前置時間最長的前 5 個供應商",
            "供應商 V001 的平均交貨天數",
        ],
    ),
    make_doc(
        "mm_f02",
        DA,
        name="採購量與消耗量對比",
        description="比較物料的採購量與實際消耗量，識別過剩或不足",
        intent_type="comparison",
        group="複合分析",
        tables=["EKPO", "MSEG"],
        generation_strategy="large_llm",
        sql_template="",
        core_fields=["MATNR", "MENGE", "BWART"],
        nl_examples=[
            "物料的採購量與消耗量對比",
            "哪些物料的消耗量遠超採購量",
            "過去半年每月的採購 vs 消耗趨勢圖資料",
            "哪些物料有採購但從未消耗",
        ],
    ),
    make_doc(
        "mm_f03",
        DA,
        name="庫存周轉率",
        description="計算各物料的庫存周轉率（消耗量/平均庫存），識別滯銷與快銷品",
        intent_type="aggregate",
        group="複合分析",
        tables=["MARD", "MSEG"],
        generation_strategy="large_llm",
        sql_template="",
        core_fields=["MATNR", "LABST", "MENGE"],
        nl_examples=[
            "各物料的庫存周轉率",
            "周轉率低於 2 的滯銷物料",
            "各工廠的庫存周轉天數",
        ],
    ),
    make_doc(
        "mm_f04",
        DA,
        name="ABC 分析",
        description="對物料進行 ABC 分類分析，依採購金額或消耗量占比分 A/B/C 等級",
        intent_type="aggregate",
        group="複合分析",
        tables=["EKPO", "MSEG", "MARA"],
        generation_strategy="large_llm",
        sql_template="",
        core_fields=["MATNR", "MENGE", "NETPR"],
        nl_examples=[
            "做一個 ABC 分析",
            "A 類物料有哪些",
            "採購金額佔總額 80% 的核心物料",
        ],
    ),
]

# ===========================================================================
# Orchestrator Intents (7 intents)
# ===========================================================================

ORCHESTRATOR_INTENTS = [
    make_orch_doc(
        "orch_chat",
        name="一般問答 / 閒聊",
        description="處理一般性問答、閒聊、問候、情感表達等不需要執行業務操作的對話。intent=chat 直接由 LLM 回覆，不路由到任何 BPA。",
        intent_type="chat",
        domain="general",
        bpa_id=None,
        capabilities=[],
        confidence_threshold=0.7,
        priority=0,
        response_strategy="direct_llm",
        nl_examples=[
            "你好",
            "謝謝你的幫助",
            "今天天氣怎麼樣",
            "系統功能有哪些",
            "你是誰",
        ],
    ),
    make_orch_doc(
        "orch_data_query",
        name="資料查詢（路由至 Data Agent）",
        description="使用者查詢 SAP 資料（採購、庫存、物料、供應商等），路由至 Data Agent NL→SQL Pipeline 處理。",
        intent_type="task",
        domain="data_query",
        bpa_id="data-agent",
        capabilities=["data_query", "nl2sql", "report_generation"],
        task_type="query",
        confidence_threshold=0.7,
        priority=10,
        response_strategy="handoff_bpa",
        nl_examples=[
            "查詢採購訂單",
            "物料庫存多少",
            "供應商清單",
            "各工廠庫存",
            "庫存異動記錄",
            "採購總金額",
        ],
    ),
    make_orch_doc(
        "orch_order_query",
        name="訂單查詢",
        description="查詢銷售訂單、採購訂單、退貨訂單等業務訂單狀態與明細，路由至 Order BPA 處理。",
        intent_type="task",
        domain="order",
        bpa_id="order-bpa",
        capabilities=["order_query"],
        task_type="query",
        confidence_threshold=0.7,
        priority=8,
        response_strategy="handoff_bpa",
        nl_examples=[
            "訂單 OR-001 的狀態",
            "查詢客戶 C001 的未結訂單",
            "今天有哪些新訂單",
            "訂單進度如何",
            "查訂單",
        ],
    ),
    make_orch_doc(
        "orch_order_action",
        name="訂單操作（退貨 / 更新）",
        description="對訂單執行業務操作，如退貨申請、訂單狀態更新、取消訂單等寫入操作，路由至 Order BPA。",
        intent_type="task",
        domain="order",
        bpa_id="order-bpa",
        capabilities=["order_update", "return_process", "refund_execute"],
        task_type="action",
        confidence_threshold=0.75,
        priority=9,
        response_strategy="confirm_then_execute",
        nl_examples=[
            "幫我退貨訂單 OR-001",
            "取消訂單 OR-002",
            "更新訂單交期",
            "申請退款",
        ],
    ),
    make_orch_doc(
        "orch_material_mgmt",
        name="物料管理業務流程",
        description="涉及物料主資料維護、庫存調整、請購等需要 Material BPA 協作的業務流程。",
        intent_type="task",
        domain="material",
        bpa_id="material-bpa",
        capabilities=[
            "material_master",
            "inventory_adjustment",
            "purchase_requisition",
        ],
        task_type="workflow",
        confidence_threshold=0.75,
        priority=7,
        response_strategy="confirm_then_execute",
        nl_examples=[
            "新增物料主資料",
            "調整庫存",
            "建立請購單",
            "物料狀態變更",
        ],
    ),
    make_orch_doc(
        "orch_finance_query",
        name="財務查詢",
        description="查詢財務相關資料，如發票、付款記錄、會計憑證等，路由至 Finance BPA。",
        intent_type="task",
        domain="finance",
        bpa_id="finance-bpa",
        capabilities=["finance_report", "invoice_query"],
        task_type="query",
        confidence_threshold=0.7,
        priority=6,
        response_strategy="handoff_bpa",
        nl_examples=[
            "查詢發票狀態",
            "付款記錄",
            "會計期間結帳",
            "應付帳款查詢",
        ],
    ),
    make_orch_doc(
        "orch_report",
        name="跨模組報表生成",
        description="生成涉及多個業務模組的彙整報表，如採購+庫存報表、財務摘要等，需要多 BPA 協作的 workflow。",
        intent_type="task",
        domain="data_query",
        bpa_id="data-agent",
        capabilities=["report_generation", "cross_module_query"],
        task_type="workflow",
        confidence_threshold=0.75,
        priority=5,
        response_strategy="confirm_then_execute",
        nl_examples=[
            "產生本月採購報表",
            "庫存月報",
            "供應商績效報告",
            "產生財務摘要報表",
        ],
    ),
]
