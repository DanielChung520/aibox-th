#!/usr/bin/env python3
"""Seed Ragic Data Agent Intents into ArangoDB intent_catalog."""

import os
import httpx

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")

AUTH = (ARANGO_USER, ARANGO_PASSWORD)


def rag_intent(
    intent_id: str,
    name: str,
    description: str,
    intent_type: str,
    group: str,
    tables: list[str],
    strategy: str,
    aql_template: str,
    core_fields: list[str],
    nl_examples: list[str],
) -> dict:
    return {
        "_key": intent_id,
        "intent_id": intent_id,
        "agent_scope": "data_agent",
        "name": name,
        "description": description,
        "intent_type": intent_type,
        "group": group,
        "tables": tables,
        "generation_strategy": strategy,
        "sql_template": aql_template,
        "core_fields": core_fields,
        "nl_examples": nl_examples,
        "example_sqls": [],
        "tool_name": "",
        "status": "enabled",
        "created_at": "2026-04-02T12:00:00Z",
        "updated_at": "2026-04-02T12:00:00Z",
        "updated_by": "system",
    }


INTENTS: list[dict] = [

    # ── Vendors (CONFIGURATIONFILE_10) ─────────────────────────────────────────
    rag_intent(
        intent_id="rgc_vendor_01",
        name="供應商列表",
        description="查詢所有已建檔的供應商廠商列表",
        intent_type="filter",
        group="採購-供應商",
        tables=["CONFIGURATIONFILE_10"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'CONFIGURATIONFILE_10' "
            "SORT d['交易對象簡稱'] ASC "
            "LIMIT {limit} "
            "RETURN {"
            "'供應商編碼': d['交易對象編碼'], "
            "'供應商簡稱': d['交易對象簡稱'], "
            "'供應商全稱': d['交易對象全稱'], "
            "'交易狀態': d['交易狀態'], "
            "'連絡人': d['連絡人'], "
            "'電話': d['電話'], "
            "'E-mail': d['E-mail']}"
        ),
        core_fields=["交易對象編碼", "交易對象簡稱", "交易狀態", "連絡人"],
        nl_examples=[
            "查詢所有供應商",
            "有哪些供應商",
            "供應商列表",
            "顯示所有已建檔的廠商",
        ],
    ),
    rag_intent(
        intent_id="rgc_vendor_02",
        name="供應商名稱搜尋",
        description="依供應商簡稱或全稱關鍵字模糊搜尋",
        intent_type="filter",
        group="採購-供應商",
        tables=["CONFIGURATIONFILE_10"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'CONFIGURATIONFILE_10' "
            "AND ("
            "CONTAINS(d['交易對象簡稱'], '{keyword}', true) OR "
            "CONTAINS(d['交易對象全稱'], '{keyword}', true)"
            ") "
            "LIMIT {limit} "
            "RETURN {"
            "'供應商編碼': d['交易對象編碼'], "
            "'供應商簡稱': d['交易對象簡稱'], "
            "'供應商全稱': d['交易對象全稱'], "
            "'付款條件': d['付款條件'], "
            "'連絡人': d['連絡人'], "
            "'電話': d['電話']}"
        ),
        core_fields=["交易對象編碼", "交易對象簡稱", "付款條件", "連絡人"],
        nl_examples=[
            "找「龍達」供應商",
            "搜尋名稱包含電子科技的廠商",
            "哪家供應商叫聯強",
        ],
    ),
    rag_intent(
        intent_id="rgc_vendor_03",
        name="供應商基本資料查詢",
        description="依供應商編碼查詢完整基本資料（含地址、銀行資訊）",
        intent_type="filter",
        group="採購-供應商",
        tables=["CONFIGURATIONFILE_10"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'CONFIGURATIONFILE_10' "
            "AND d['交易對象編碼'] == '{vendor_code}' "
            "LIMIT 1 "
            "RETURN {"
            "'供應商編碼': d['交易對象編碼'], "
            "'供應商簡稱': d['交易對象簡稱'], "
            "'供應商全稱': d['交易對象全稱'], "
            "'統一編號': d['統一編號'], "
            "'地址': d['地址'], "
            "'連絡人': d['連絡人'], "
            "'電話': d['電話'], "
            "'手機': d['手機'], "
            "'E-mail': d['E-mail'], "
            "'付款方式': d['付款方式'], "
            "'付款條件': d['付款條件'], "
            "'交易幣別': d['交易幣別'], "
            "'銀行代號': d['銀行代號'], "
            "'分行代號': d['分行代號'], "
            "'戶名': d['戶名'], "
            "'帳號': d['帳號']}"
        ),
        core_fields=["交易對象編碼", "交易對象簡稱", "付款條件", "地址", "統一編號"],
        nl_examples=[
            "供應商 V001 的完整資料",
            "查供應商編號 ABC123 的資訊",
            "聯強的銀行帳號是什麼",
        ],
    ),

    # ── Products (CONFIGURATIONFILE_9) ────────────────────────────────────────
    rag_intent(
        intent_id="rgc_product_01",
        name="品項列表",
        description="查詢所有已建檔的品項商品列表",
        intent_type="filter",
        group="採購-品項",
        tables=["CONFIGURATIONFILE_9"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'CONFIGURATIONFILE_9' "
            "SORT d['品項名稱'] ASC "
            "LIMIT {limit} "
            "RETURN {"
            "'品項編碼': d['品項編碼'], "
            "'品項名稱': d['品項名稱'], "
            "'品項版次': d['品項版次'], "
            "'狀態': d['狀態'], "
            "'主供應商': d['主供應商名稱'], "
            "'採購價': d['採購價'], "
            "'建議售價': d['批發價']}"
        ),
        core_fields=["品項編碼", "品項名稱", "主供應商名稱", "採購價"],
        nl_examples=[
            "查詢所有品項",
            "有哪些商品",
            "品項列表",
            "顯示所有已建檔的產品",
        ],
    ),
    rag_intent(
        intent_id="rgc_product_02",
        name="品項名稱搜尋",
        description="依品項名稱關鍵字模糊搜尋商品",
        intent_type="filter",
        group="採購-品項",
        tables=["CONFIGURATIONFILE_9"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'CONFIGURATIONFILE_9' "
            "AND CONTAINS(d['品項名稱'], '{keyword}', true) "
            "LIMIT {limit} "
            "RETURN {"
            "'品項編碼': d['品項編碼'], "
            "'品項名稱': d['品項名稱'], "
            "'主供應商': d['主供應商名稱'], "
            "'採購價': d['採購價'], "
            "'採購前置期': d['採購前置期'], "
            "'安全庫存下限': d['安全庫存下限'], "
            "'安全庫存上限': d['安全庫存上限']}"
        ),
        core_fields=["品項編碼", "品項名稱", "主供應商名稱", "採購價"],
        nl_examples=[
            "找「巧克力」相關品項",
            "搜尋名稱包含草莓的產品",
            "有哪些口味的冰淇淋",
        ],
    ),
    rag_intent(
        intent_id="rgc_product_03",
        name="品項安全庫存警示",
        description="查詢安全庫存不足（低於下限）的品項",
        intent_type="filter",
        group="採購-品項",
        tables=["CONFIGURATIONFILE_9"],
        strategy="small_llm",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'CONFIGURATIONFILE_9' "
            "AND d['安全庫存下限'] IS NOT null "
            "AND d['安全庫存上限'] IS NOT null "
            "LIMIT {limit} "
            "RETURN {"
            "'品項編碼': d['品項編碼'], "
            "'品項名稱': d['品項名稱'], "
            "'安全庫存下限': d['安全庫存下限'], "
            "'安全庫存上限': d['安全庫存上限'], "
            "'採購前置期': d['採購前置期'], "
            "'主供應商': d['主供應商名稱']}"
        ),
        core_fields=["品項編碼", "品項名稱", "安全庫存下限", "安全庫存上限"],
        nl_examples=[
            "哪些品項庫存不足",
            "安全庫存快見底的商品",
            "需要補貨的品項有哪些",
        ],
    ),

    # ── Warehouses (CONFIGURATIONFILE_3) ────────────────────────────────────
    rag_intent(
        intent_id="rgc_wh_01",
        name="倉庫列表",
        description="查詢所有已建檔的倉庫儲位資料",
        intent_type="filter",
        group="倉儲-倉庫",
        tables=["CONFIGURATIONFILE_3"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'CONFIGURATIONFILE_3' "
            "SORT d['倉庫名稱'] ASC "
            "LIMIT {limit} "
            "RETURN {"
            "'倉庫編碼': d['倉庫編碼'], "
            "'倉庫名稱': d['倉庫名稱'], "
            "'儲位代碼': d['儲位代碼'], "
            "'儲位名稱': d['儲位名稱'], "
            "'料架代碼': d['料架代碼'], "
            "'料架名稱': d['料架名稱']}"
        ),
        core_fields=["倉庫編碼", "倉庫名稱", "儲位代碼", "料架代碼"],
        nl_examples=[
            "查詢所有倉庫",
            "有哪些倉庫",
            "倉庫列表",
            "儲位資料",
        ],
    ),

    # ── Purchase Orders (ERP_13) ──────────────────────────────────────────────
    rag_intent(
        intent_id="rgc_po_01",
        name="採購單列表（日期範圍）",
        description="依日期範圍查詢採購單列表，含供應商名稱",
        intent_type="filter",
        group="採購-採購單",
        tables=["ERP_13"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_13' "
            "AND d['採購日期'] >= '{start_date}' "
            "AND d['採購日期'] <= '{end_date}' "
            "SORT d['採購日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'採購單號': d['採購單號'], "
            "'採購日期': d['採購日期'], "
            "'供應商名稱': d['供應商名稱'], "
            "'品項名稱': d['品項名稱'], "
            "'供應商編碼': d['供應商編碼'], "
            "'品項編碼': d['品項編碼'], "
            "'含稅總計': d['含稅總計'], "
            "'進貨狀態': d['進貨狀態'], "
            "'狀態': d['狀態']}"
        ),
        core_fields=["採購單號", "採購日期", "供應商名稱", "含稅總計", "進貨狀態"],
        nl_examples=[
            "查詢 2026 年 3 月的採購單",
            "上個月的採購單有哪些",
            "最近一個月的採購訂單",
            "2026/01 到 2026/03 的採購記錄",
        ],
    ),
    rag_intent(
        intent_id="rgc_po_02",
        name="採購單明細查詢",
        description="依採購單號查詢完整明細，含報價、包裝、數量、單價等資訊",
        intent_type="filter",
        group="採購-採購單",
        tables=["ERP_13"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_13' "
            "AND d['採購單號'] == '{po_number}' "
            "LIMIT {limit} "
            "RETURN {"
            "'採購單號': d['採購單號'], "
            "'採購日期': d['採購日期'], "
            "'需求日期': d['需求日期'], "
            "'預計到貨日期': d['預計到貨日期'], "
            "'供應商名稱': d['供應商名稱'], "
            "'品項名稱': d['品項名稱'], "
            "'品項編碼': d['品項編碼'], "
            "'包裝規格': d['包裝規格'], "
            "'採購數量': d['採購數量'], "
            "'單位': d['單位'], "
            "'單價': d['單價'], "
            "'小計': d['小計'], "
            "'含稅總計': d['含稅總計'], "
            "'稅率': d['稅率'], "
            "'稅額': d['稅額'], "
            "'進貨狀態': d['進貨狀態'], "
            "'備註': d['備註']}"
        ),
        core_fields=["採購單號", "採購日期", "供應商名稱", "品項名稱", "採購數量", "單價", "含稅總計"],
        nl_examples=[
            "採購單 PO000001 的詳細資訊",
            "查詢採購單 ABC123 的明細",
            "PO000050 的報價內容",
        ],
    ),
    rag_intent(
        intent_id="rgc_po_03",
        name="依供應商查詢採購單",
        description="依供應商名稱或編碼查詢該供應商的所有採購單",
        intent_type="filter",
        group="採購-採購單",
        tables=["ERP_13"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_13' "
            "AND ("
            "CONTAINS(d['供應商名稱'], '{vendor}', true) OR "
            "CONTAINS(d['供應商編碼'], '{vendor}', true)"
            ") "
            "SORT d['採購日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'採購單號': d['採購單號'], "
            "'採購日期': d['採購日期'], "
            "'供應商名稱': d['供應商名稱'], "
            "'品項名稱': d['品項名稱'], "
            "'含稅總計': d['含稅總計'], "
            "'進貨狀態': d['進貨狀態']}"
        ),
        core_fields=["採購單號", "採購日期", "供應商名稱", "含稅總計", "進貨狀態"],
        nl_examples=[
            "找聯強供應商的採購單",
            "V001 這個供應商的所有訂單",
            "哪家供應商最近有下單",
        ],
    ),
    rag_intent(
        intent_id="rgc_po_04",
        name="採購單未完成進貨查詢",
        description="查詢已建立但尚未完成進貨的採購單",
        intent_type="filter",
        group="採購-採購單",
        tables=["ERP_13"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_13' "
            "AND d['進貨狀態'] != '已完成' "
            "AND d['進貨狀態'] != '完成' "
            "AND d['進貨狀態'] != '已結案' "
            "SORT d['預計到貨日期'] ASC "
            "LIMIT {limit} "
            "RETURN {"
            "'採購單號': d['採購單號'], "
            "'採購日期': d['採購日期'], "
            "'預計到貨日期': d['預計到貨日期'], "
            "'供應商名稱': d['供應商名稱'], "
            "'品項名稱': d['品項名稱'], "
            "'品項編碼': d['品項編碼'], "
            "'已進貨數量': d['已進貨數量'], "
            "'採購數量': d['採購數量'], "
            "'未進貨數量': d['未進貨數量'], "
            "'進貨狀態': d['進貨狀態']}"
        ),
        core_fields=["採購單號", "預計到貨日期", "供應商名稱", "已進貨數量", "未進貨數量", "進貨狀態"],
        nl_examples=[
            "有哪些採購單還沒進貨",
            "待進貨的訂單",
            "還沒完成的採購單",
        ],
    ),

    # ── Goods Receipts (ERP_48) ────────────────────────────────────────────────
    rag_intent(
        intent_id="rgc_gr_01",
        name="進貨單列表（日期範圍）",
        description="依日期範圍查詢進貨單列表",
        intent_type="filter",
        group="採購-進貨",
        tables=["ERP_48"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_48' "
            "AND d['收貨日期'] >= '{start_date}' "
            "AND d['收貨日期'] <= '{end_date}' "
            "SORT d['收貨日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'進貨單號': d['進貨單號'], "
            "'收貨日期': d['收貨日期'], "
            "'來源採購單號': d['來源採購單號'], "
            "'供應商名稱': d['供應商名稱'], "
            "'品項名稱': d['品項名稱'], "
            "'品項編碼': d['品項編碼'], "
            "'收貨數量': d['收貨數量'], "
            "'含稅總計': d['含稅總計'], "
            "'退貨': d['退貨'], "
            "'有效日期': d['有效日期']}"
        ),
        core_fields=["進貨單號", "收貨日期", "來源採購單號", "供應商名稱", "收貨數量", "含稅總計"],
        nl_examples=[
            "查詢 2026 年 3 月的進貨單",
            "這個月的進貨記錄",
            "最近一週的進貨資料",
        ],
    ),
    rag_intent(
        intent_id="rgc_gr_02",
        name="進貨單明細查詢",
        description="依進貨單號查詢完整進貨明細",
        intent_type="filter",
        group="採購-進貨",
        tables=["ERP_48"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_48' "
            "AND d['進貨單號'] == '{gr_number}' "
            "LIMIT {limit} "
            "RETURN {"
            "'進貨單號': d['進貨單號'], "
            "'收貨單號': d['收貨單號'], "
            "'收貨日期': d['收貨日期'], "
            "'來源採購單號': d['來源採購單號'], "
            "'供應商名稱': d['供應商名稱'], "
            "'品項名稱': d['品項名稱'], "
            "'品項編碼': d['品項編碼'], "
            "'批號': d['批號'], "
            "'收貨數量': d['收貨數量'], "
            "'單價': d['單價'], "
            "'小計': d['小計'], "
            "'含稅總計': d['含稅總計'], "
            "'退貨': d['退貨'], "
            "'退貨數量': d['退貨數量'], "
            "'有效日期': d['有效日期'], "
            "'更新採購單狀態': d['更新採購單狀態']}"
        ),
        core_fields=["進貨單號", "收貨日期", "來源採購單號", "品項名稱", "收貨數量", "含稅總計"],
        nl_examples=[
            "進貨單 GR000001 的詳細資訊",
            "查詢進貨單 ABC123 的內容",
        ],
    ),
    rag_intent(
        intent_id="rgc_gr_03",
        name="依採購單查詢進貨",
        description="依來源採購單號查詢關聯的進貨記錄",
        intent_type="filter",
        group="採購-進貨",
        tables=["ERP_48"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_48' "
            "AND d['來源採購單號'] == '{po_number}' "
            "SORT d['收貨日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'進貨單號': d['進貨單號'], "
            "'收貨日期': d['收貨日期'], "
            "'品項名稱': d['品項名稱'], "
            "'品項編碼': d['品項編碼'], "
            "'收貨數量': d['收貨數量'], "
            "'批號': d['批號'], "
            "'有效日期': d['有效日期'], "
            "'退貨': d['退貨']}"
        ),
        core_fields=["進貨單號", "來源採購單號", "收貨日期", "品項名稱", "收貨數量"],
        nl_examples=[
            "PO000001 的進貨記錄",
            "採購單 ABC123 已進貨幾筆",
            "這張採購單對應哪些進貨單",
        ],
    ),
    rag_intent(
        intent_id="rgc_gr_04",
        name="進貨總金額彙總",
        description="彙總指定期間的進貨含稅總金額",
        intent_type="aggregate",
        group="採購-進貨",
        tables=["ERP_48"],
        strategy="small_llm",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_48' "
            "AND d['收貨日期'] >= '{start_date}' "
            "AND d['收貨日期'] <= '{end_date}' "
            "LIMIT {limit} "
            "RETURN {"
            "'收貨日期': d['收貨日期'], "
            "'進貨單號': d['進貨單號'], "
            "'供應商名稱': d['供應商名稱'], "
            "'品項名稱': d['品項名稱'], "
            "'含稅總計': d['含稅總計']}"
        ),
        core_fields=["收貨日期", "進貨單號", "供應商名稱", "含稅總計"],
        nl_examples=[
            "這個月的進貨總金額",
            "2026 年第一季進貨合計多少",
            "本月進貨費用統計",
        ],
    ),

    # ── Sales Orders (ERP_26) ────────────────────────────────────────────────
    rag_intent(
        intent_id="rgc_so_01",
        name="銷貨單列表（日期範圍）",
        description="依日期範圍查詢銷貨單列表",
        intent_type="filter",
        group="銷貨-銷貨單",
        tables=["ERP_26"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_26' "
            "AND d['銷貨日期'] >= '{start_date}' "
            "AND d['銷貨日期'] <= '{end_date}' "
            "SORT d['銷貨日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'銷貨單號': d['銷貨單號'], "
            "'銷貨日期': d['銷貨日期'], "
            "'訂單單號': d['訂單單號'], "
            "'客戶名稱': d['客戶名稱'], "
            "'客戶編號': d['客戶編號'], "
            "'品項名稱': d['品項名稱'], "
            "'品項編號': d['品項編號'], "
            "'含稅總計': d['含稅總計'], "
            "'訂單狀態': d['訂單狀態']}"
        ),
        core_fields=["銷貨單號", "銷貨日期", "客戶名稱", "含稅總計", "訂單狀態"],
        nl_examples=[
            "查詢 2026 年 3 月的銷貨單",
            "這個月的銷貨記錄",
            "最近一個月的銷售資料",
        ],
    ),
    rag_intent(
        intent_id="rgc_so_02",
        name="依客戶查詢銷貨",
        description="依客戶名稱或編號查詢該客戶的所有銷貨單",
        intent_type="filter",
        group="銷貨-銷貨單",
        tables=["ERP_26"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_26' "
            "AND ("
            "CONTAINS(d['客戶名稱'], '{customer}', true) OR "
            "CONTAINS(d['客戶編號'], '{customer}', true)"
            ") "
            "SORT d['銷貨日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'銷貨單號': d['銷貨單號'], "
            "'銷貨日期': d['銷貨日期'], "
            "'客戶名稱': d['客戶名稱'], "
            "'品項名稱': d['品項名稱'], "
            "'含稅總計': d['含稅總計'], "
            "'數量': d['數量'], "
            "'訂單狀態': d['訂單狀態']}"
        ),
        core_fields=["銷貨單號", "銷貨日期", "客戶名稱", "含稅總計", "訂單狀態"],
        nl_examples=[
            "找客戶 ABC 的所有銷貨單",
            "C001 這個客戶的購買記錄",
            "哪家客戶最近有下單",
        ],
    ),
    rag_intent(
        intent_id="rgc_so_03",
        name="銷貨單未出貨查詢",
        description="查詢尚未出貨的銷貨單",
        intent_type="filter",
        group="銷貨-銷貨單",
        tables=["ERP_26"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_26' "
            "AND d['訂單狀態'] != '已出貨' "
            "AND d['訂單狀態'] != '已完成' "
            "AND d['訂單狀態'] != '完成' "
            "SORT d['銷貨日期'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'銷貨單號': d['銷貨單號'], "
            "'銷貨日期': d['銷貨日期'], "
            "'客戶名稱': d['客戶名稱'], "
            "'品項名稱': d['品項名稱'], "
            "'數量': d['數量'], "
            "'預出數量': d['預出數量'], "
            "'訂單狀態': d['訂單狀態']}"
        ),
        core_fields=["銷貨單號", "銷貨日期", "客戶名稱", "數量", "預出數量", "訂單狀態"],
        nl_examples=[
            "有哪些訂單還沒出貨",
            "待出貨的銷貨單",
            "還沒完成的銷售訂單",
        ],
    ),
    rag_intent(
        intent_id="rgc_so_04",
        name="銷貨總金額彙總",
        description="彙總指定期間的銷貨含稅總金額",
        intent_type="aggregate",
        group="銷貨-銷貨單",
        tables=["ERP_26"],
        strategy="small_llm",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'ERP_26' "
            "AND d['銷貨日期'] >= '{start_date}' "
            "AND d['銷貨日期'] <= '{end_date}' "
            "LIMIT {limit} "
            "RETURN {"
            "'銷貨日期': d['銷貨日期'], "
            "'銷貨單號': d['銷貨單號'], "
            "'客戶名稱': d['客戶名稱'], "
            "'含稅總計': d['含稅總計']}"
        ),
        core_fields=["銷貨日期", "銷貨單號", "客戶名稱", "含稅總計"],
        nl_examples=[
            "這個月的銷貨總金額",
            "2026 年第一季銷售合計多少",
            "本月銷售額統計",
        ],
    ),

    # ── Stock Inventory (STOCK_16) ────────────────────────────────────────────
    rag_intent(
        intent_id="rgc_stock_01",
        name="即時庫存查詢",
        description="查詢所有品項的即時庫存資訊",
        intent_type="filter",
        group="倉儲-庫存",
        tables=["STOCK_16"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'STOCK_16' "
            "SORT d['品項名稱'] ASC "
            "LIMIT {limit} "
            "RETURN {"
            "'批號': d['批號'], "
            "'品項編號': d['品項編號'], "
            "'品項名稱': d['品項名稱'], "
            "'品項類型': d['品項類型'], "
            "'倉庫名稱': d['倉庫名稱'], "
            "'即時庫存': d['即時庫存'], "
            "'即時庫存(完整包裝)': d['即時庫存(完整包裝)'], "
            "'即時庫存(零數)': d['即時庫存(零數)'], "
            "'有效日期': d['有效日期'], "
            "'效期剩餘天數': d['效期剩餘天數']}"
        ),
        core_fields=["批號", "品項編號", "品項名稱", "倉庫名稱", "即時庫存", "有效日期"],
        nl_examples=[
            "查詢即時庫存",
            "現在各品項的庫存有多少",
            "目前倉庫的存貨",
        ],
    ),
    rag_intent(
        intent_id="rgc_stock_02",
        name="依品項查詢庫存",
        description="依品項名稱或編號查詢該品項的庫存（含各倉庫）",
        intent_type="filter",
        group="倉儲-庫存",
        tables=["STOCK_16"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'STOCK_16' "
            "AND ("
            "CONTAINS(d['品項名稱'], '{item}', true) OR "
            "CONTAINS(d['品項編號'], '{item}', true)"
            ") "
            "SORT d['即時庫存'] DESC "
            "LIMIT {limit} "
            "RETURN {"
            "'批號': d['批號'], "
            "'品項編號': d['品項編號'], "
            "'品項名稱': d['品項名稱'], "
            "'倉庫名稱': d['倉庫名稱'], "
            "'即時庫存': d['即時庫存'], "
            "'有效日期': d['有效日期'], "
            "'效期剩餘天數': d['效期剩餘天數'], "
            "'批號出貨數量': d['批號出貨數量']}"
        ),
        core_fields=["批號", "品項編號", "品項名稱", "倉庫名稱", "即時庫存"],
        nl_examples=[
            "找「巧克力」的庫存",
            "品項 P001 目前庫存多少",
            "這個品項在哪個倉庫有貨",
        ],
    ),
    rag_intent(
        intent_id="rgc_stock_03",
        name="依倉庫查詢庫存",
        description="依倉庫名稱查詢該倉庫的所有庫存",
        intent_type="filter",
        group="倉儲-庫存",
        tables=["STOCK_16"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'STOCK_16' "
            "AND CONTAINS(d['倉庫名稱'], '{warehouse}', true) "
            "SORT d['品項名稱'] ASC "
            "LIMIT {limit} "
            "RETURN {"
            "'批號': d['批號'], "
            "'品項編號': d['品項編號'], "
            "'品項名稱': d['品項名稱'], "
            "'即時庫存': d['即時庫存'], "
            "'即時庫存(完整包裝)': d['即時庫存(完整包裝)'], "
            "'即時庫存(零數)': d['即時庫存(零數)'], "
            "'有效日期': d['有效日期'], "
            "'效期剩餘天數': d['效期剩餘天數']}"
        ),
        core_fields=["批號", "品項編號", "品項名稱", "倉庫名稱", "即時庫存"],
        nl_examples=[
            "查詢台北倉庫的庫存",
            "A01 倉庫有哪些品項",
            "倉庫 ABC 的存貨有多少",
        ],
    ),
    rag_intent(
        intent_id="rgc_stock_04",
        name="效期管理查詢",
        description="查詢即將到期（效期剩餘天數少於門檻）的庫存",
        intent_type="filter",
        group="倉儲-庫存",
        tables=["STOCK_16"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'STOCK_16' "
            "AND d['效期剩餘天數'] IS NOT null "
            "AND d['效期剩餘天數'] <= {days} "
            "SORT d['效期剩餘天數'] ASC "
            "LIMIT {limit} "
            "RETURN {"
            "'批號': d['批號'], "
            "'品項編號': d['品項編號'], "
            "'品項名稱': d['品項名稱'], "
            "'倉庫名稱': d['倉庫名稱'], "
            "'即時庫存': d['即時庫存'], "
            "'有效日期': d['有效日期'], "
            "'效期剩餘天數': d['效期剩餘天數']}"
        ),
        core_fields=["批號", "品項名稱", "倉庫名稱", "有效日期", "效期剩餘天數", "即時庫存"],
        nl_examples=[
            "哪些庫存快過期",
            "效期在 30 天內的品項",
            "需要優先出貨的臨期品項",
        ],
    ),
    rag_intent(
        intent_id="rgc_stock_05",
        name="批號查詢",
        description="依批號查詢特定批次的所有庫存資訊",
        intent_type="filter",
        group="倉儲-庫存",
        tables=["STOCK_16"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'STOCK_16' "
            "AND d['批號'] == '{batch_number}' "
            "LIMIT {limit} "
            "RETURN {"
            "'批號': d['批號'], "
            "'品項編號': d['品項編號'], "
            "'品項名稱': d['品項名稱'], "
            "'倉庫名稱': d['倉庫名稱'], "
            "'即時庫存': d['即時庫存'], "
            "'即時庫存(完整包裝)': d['即時庫存(完整包裝)'], "
            "'即時庫存(零數)': d['即時庫存(零數)'], "
            "'製造/進貨日期': d['製造/進貨日期'], "
            "'有效日期': d['有效日期'], "
            "'效期剩餘天數': d['效期剩餘天數'], "
            "'批號出貨數量': d['批號出貨數量'], "
            "'客戶名稱': d['客戶名稱'], "
            "'客戶/供應商名稱': d['客戶/供應商名稱']}"
        ),
        core_fields=["批號", "品項名稱", "倉庫名稱", "即時庫存", "有效日期", "效期剩餘天數"],
        nl_examples=[
            "查批號 B20260315",
            "這個批號的庫存在哪裡",
            "批號 ABC123 多少數量",
        ],
    ),

    # ── Warehouse Inventory (STOCK_17) ────────────────────────────────────────
    rag_intent(
        intent_id="rgc_whinv_01",
        name="倉庫別庫存彙總",
        description="依倉庫別彙總所有品項的即時庫存",
        intent_type="filter",
        group="倉儲-庫存",
        tables=["STOCK_17"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'STOCK_17' "
            "SORT d['倉庫名稱'] ASC, d['品項名稱'] ASC "
            "LIMIT {limit} "
            "RETURN {"
            "'倉庫名稱': d['倉庫名稱'], "
            "'品項編號': d['品項編號'], "
            "'品項名稱': d['品項名稱'], "
            "'批號': d['批號'], "
            "'存放數量': d['存放數量'], "
            "'即時庫存(完整包裝)': d['即時庫存(完整包裝)'], "
            "'即時庫存(零數)': d['即時庫存(零數)'], "
            "'有效日期': d['有效日期'], "
            "'效期剩餘天數': d['效期剩餘天數']}"
        ),
        core_fields=["倉庫名稱", "品項編號", "品項名稱", "存放數量", "有效日期"],
        nl_examples=[
            "查詢各倉庫的庫存彙總",
            "各倉庫存貨統計",
            "每個倉庫有哪些品項",
        ],
    ),
    rag_intent(
        intent_id="rgc_whinv_02",
        name="依倉庫別查詢庫存",
        description="依倉庫名稱查詢該倉庫的所有品項庫存",
        intent_type="filter",
        group="倉儲-庫存",
        tables=["STOCK_17"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'STOCK_17' "
            "AND CONTAINS(d['倉庫名稱'], '{warehouse}', true) "
            "SORT d['品項名稱'] ASC "
            "LIMIT {limit} "
            "RETURN {"
            "'倉庫名稱': d['倉庫名稱'], "
            "'品項編號': d['品項編號'], "
            "'品項名稱': d['品項名稱'], "
            "'批號': d['批號'], "
            "'存放數量': d['存放數量'], "
            "'即時庫存(完整包裝)': d['即時庫存(完整包裝)'], "
            "'即時庫存(零數)': d['即時庫存(零數)'], "
            "'有效日期': d['有效日期']}"
        ),
        core_fields=["倉庫名稱", "品項編號", "品項名稱", "批號", "存放數量"],
        nl_examples=[
            "台北倉庫的品項",
            "A01 倉庫庫存清單",
            "這個倉庫有哪些品項",
        ],
    ),
    rag_intent(
        intent_id="rgc_whinv_03",
        name="批號庫存查詢",
        description="依批號查詢倉儲批號庫存資訊",
        intent_type="filter",
        group="倉儲-庫存",
        tables=["STOCK_17"],
        strategy="template",
        aql_template=(
            "FOR d IN da_table_data_ragic "
            "FILTER d.table_id == 'STOCK_17' "
            "AND d['批號'] == '{batch_number}' "
            "LIMIT {limit} "
            "RETURN {"
            "'批號': d['批號'], "
            "'批號QR CODE': d['批號QR CODE'], "
            "'品項編號': d['品項編號'], "
            "'品項名稱': d['品項名稱'], "
            "'倉庫名稱': d['倉庫名稱'], "
            "'存放數量': d['存放數量'], "
            "'即時庫存(完整包裝)': d['即時庫存(完整包裝)'], "
            "'即時庫存(零數)': d['即時庫存(零數)'], "
            "'有效日期': d['有效日期'], "
            "'效期剩餘天數': d['效期剩餘天數'], "
            "'報廢數量': d['報廢數量']}"
        ),
        core_fields=["批號", "品項名稱", "倉庫名稱", "存放數量", "有效日期"],
        nl_examples=[
            "查批號 XYZ789 的庫存",
            "這個批號在哪個倉庫",
        ],
    ),
]


def seed() -> tuple[int, list[str]]:
    count = 0
    errors: list[str] = []

    async def _seed():
        nonlocal count
        async with httpx.AsyncClient(timeout=30.0) as client:
            for intent in INTENTS:
                try:
                    # Use PUT with overwrite=true to upsert (insert or update)
                    doc_key = intent.get("_key") or intent.get("intent_id")
                    response = await client.put(
                        f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/intent_catalog/{doc_key}?overwrite=true",
                        json=intent,
                        auth=AUTH,
                    )
                    if response.status_code in (200, 201, 202):
                        count += 1
                        print(f"  ✓ {intent['intent_id']}: {intent['name']}")
                    else:
                        body = response.json()
                        err_msg = body.get("errorMessage", response.text[:100])
                        errors.append(f"{intent['intent_id']}: {err_msg}")
                        print(f"  ✗ {intent['intent_id']}: {err_msg}")
                except Exception as e:
                    errors.append(f"{intent['intent_id']}: {type(e).__name__}: {e}")
                    print(f"  ✗ {intent['intent_id']}: {e}")

    import asyncio
    asyncio.run(_seed())
    return count, errors


def main() -> None:
    print("=" * 60)
    print("Ragic Data Agent Intent Seed")
    print("=" * 60)
    print(f"Intents to seed: {len(INTENTS)}")
    print()

    count, errors = seed()
    print()
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    print(f"Seeded: {count}/{len(INTENTS)} intents")


if __name__ == "__main__":
    main()
