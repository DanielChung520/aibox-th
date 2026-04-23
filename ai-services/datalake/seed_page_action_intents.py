#!/usr/bin/env python3
"""
@file        seed_page_action_intents.py
@description 種子腳本：寫入 ~39 筆 page_action 意圖模板到 intent_catalog，
             供艾企浮動助手 Level 1 靜態模板匹配使用。
@lastUpdate  2026-04-23 22:29:26
@author      Daniel Chung
@version     1.2.0
"""

from seed_intent_catalog_shared import insert_batch, TS

PA = "page_action"


def make_page_action_doc(
    intent_id: str,
    name: str,
    description: str,
    page_type: str,
    intent_type: str,
    response_strategy: str,
    side_effect: str,
    nl_examples: list[str],
    suggested_text: str,
    priority: int = 10,
) -> dict[str, object]:
    """Build a page_action intent document for intent_catalog."""
    return {
        "_key": intent_id,
        "intent_id": intent_id,
        "agent_scope": PA,
        "name": name,
        "description": description,
        "page_type": page_type,
        "intent_type": intent_type,
        "response_strategy": response_strategy,
        "side_effect": side_effect,
        "nl_examples": nl_examples,
        "suggested_text": suggested_text,
        "priority": priority,
        "status": "enabled",
        "source": "seed",
        "learn_stats": {
            "confirmed": 0,
            "rejected": 0,
            "modified": 0,
            "ignored": 0,
        },
        "created_at": TS,
        "updated_at": TS,
        "updated_by": "system",
    }


# ── data_table (6) ──
data_table_intents = [
    make_page_action_doc(
         "pa_dt_explain", "告訴我這個功能的操作說明", "說明此資料表頁面的功能與操作方式",
         "data_table", "explain", "direct_llm", "none",
         ["這個頁面怎麼用", "操作說明", "功能介紹"],
         "告訴我「{page_name}」的操作說明", 20,
     ),
     make_page_action_doc(
         "pa_dt_search", "精確搜尋", "在表格中搜尋特定記錄",
         "data_table", "action", "tool_execute", "none",
         ["搜尋", "找一下", "查詢某筆資料"],
         "幫我在「{table_name}」中搜尋特定記錄", 15,
     ),
     make_page_action_doc(
         "pa_dt_filter", "進階篩選", "依條件篩選表格資料",
         "data_table", "action", "tool_execute", "none",
         ["篩選", "過濾", "只看某些資料"],
         "幫我篩選「{table_name}」中符合條件的資料", 14,
     ),
     make_page_action_doc(
         "pa_dt_export", "匯出資料", "將當前表格資料匯出",
         "data_table", "action", "confirm_then_execute", "none",
         ["匯出", "下載", "導出 Excel"],
         "幫我匯出「{table_name}」的這些資料", 12,
     ),
     make_page_action_doc(
         "pa_dt_stats", "統計摘要", "顯示當前表格的統計資訊",
         "data_table", "query", "direct_llm", "none",
         ["統計", "總共幾筆", "摘要"],
         "這張表目前有 {record_count} 筆記錄，幫我做統計摘要", 13,
     ),
     make_page_action_doc(
         "pa_dt_sort", "排序", "依指定欄位排序表格",
         "data_table", "action", "tool_execute", "none",
         ["排序", "按什麼排", "由大到小"],
         "幫我依指定欄位排序「{table_name}」", 11,
     ),
]

# ── form_crud (4) ──
form_crud_intents = [
    make_page_action_doc(
         "pa_fc_explain", "告訴我這個功能的操作說明", "說明此表單頁面的操作方式",
         "form_crud", "explain", "direct_llm", "none",
         ["怎麼新增", "怎麼編輯", "操作說明"],
         "告訴我「{page_name}」的操作說明", 20,
     ),
     make_page_action_doc(
         "pa_fc_create", "新增記錄", "建立一筆新記錄",
         "form_crud", "action", "confirm_then_execute", "reversible",
         ["新增", "建立", "加一筆"],
         "幫我在「{page_name}」中新增一筆記錄", 15,
     ),
     make_page_action_doc(
         "pa_fc_edit", "編輯記錄", "修改現有記錄",
         "form_crud", "action", "confirm_then_execute", "reversible",
         ["編輯", "修改", "更新"],
         "幫我編輯「{page_name}」中的這筆記錄", 14,
     ),
     make_page_action_doc(
         "pa_fc_delete", "刪除記錄", "刪除選中的記錄",
         "form_crud", "action", "confirm_then_execute", "destructive",
         ["刪除", "移除", "刪掉"],
         "幫我刪除「{page_name}」中的這筆記錄", 10,
     ),
]

# ── config (4) ──
config_intents = [
    make_page_action_doc(
         "pa_cfg_explain", "告訴我這個功能的操作說明", "說明系統配置頁面的功能",
         "config", "explain", "direct_llm", "none",
         ["這些參數是什麼意思", "配置說明", "操作說明"],
         "告訴我「{page_name}」的操作說明", 20,
     ),
     make_page_action_doc(
         "pa_cfg_modify", "修改配置", "修改系統參數值",
         "config", "action", "confirm_then_execute", "reversible",
         ["修改參數", "改設定", "調整配置"],
         "幫我在「{page_name}」中修改參數", 15,
     ),
     make_page_action_doc(
         "pa_cfg_search", "搜尋參數", "在配置中搜尋特定參數",
         "config", "action", "tool_execute", "none",
         ["找參數", "搜尋設定"],
         "幫我在「{page_name}」中搜尋特定的參數", 14,
     ),
     make_page_action_doc(
         "pa_cfg_reset", "重設預設值", "將參數重設為預設值",
         "config", "action", "confirm_then_execute", "reversible",
         ["重設", "恢復預設", "還原"],
         "幫我將「{page_name}」中的參數重設為預設值", 10,
     ),
]

# ── dashboard (3) ──
dashboard_intents = [
    make_page_action_doc(
         "pa_dash_explain", "告訴我這個功能的操作說明", "說明儀表板頁面的功能",
         "dashboard", "explain", "direct_llm", "none",
         ["首頁有什麼", "操作說明", "功能介紹"],
         "告訴我「{page_name}」的功能", 20,
     ),
     make_page_action_doc(
         "pa_dash_status", "系統狀態", "查看系統運行狀態概覽",
         "dashboard", "query", "direct_llm", "none",
         ["系統狀態", "運行情況", "健康檢查"],
         "系統目前的運行狀態如何？請在「{page_name}」中顯示", 15,
     ),
     make_page_action_doc(
         "pa_dash_todo", "待辦事項", "查看今日待辦任務",
         "dashboard", "query", "direct_llm", "none",
         ["待辦", "今天要做什麼", "任務"],
         "今天在「{page_name}」中有什麼待辦事項？", 14,
     ),
]

# ── data_query (8) ──
data_query_intents = [
    make_page_action_doc(
         "pa_dq_explain", "告訴我這個功能的操作說明", "說明資料查詢頁面的操作方式",
         "data_query", "explain", "direct_llm", "none",
         ["怎麼查詢", "操作說明", "功能介紹"],
         "告訴我「{page_name}」的操作說明", 20,
     ),
     make_page_action_doc(
         "pa_dq_nl_query", "自然語言查詢", "用自然語言描述查詢需求",
         "data_query", "query", "tool_execute", "none",
         ["幫我查", "我想知道", "查一下"],
         "用自然語言描述關於「{table_name}」的查詢需求", 18,
     ),
     make_page_action_doc(
         "pa_dq_schema", "查看表結構", "瀏覽資料表的欄位與結構",
         "data_query", "query", "direct_llm", "none",
         ["表結構", "有哪些欄位", "Schema"],
         "「{table_name}」有哪些欄位和結構？", 15,
     ),
     make_page_action_doc(
         "pa_dq_sample", "取樣資料", "查看前幾筆資料取樣",
         "data_query", "query", "tool_execute", "none",
         ["看幾筆", "取樣", "預覽"],
         "讓我看看「{table_name}」的前幾筆資料", 14,
     ),
     make_page_action_doc(
         "pa_dq_aggregate", "聚合統計", "執行聚合統計查詢",
         "data_query", "query", "tool_execute", "none",
         ["統計", "加總", "平均", "分組"],
         "幫我對「{table_name}」做聚合統計", 13,
     ),
     make_page_action_doc(
         "pa_dq_filter", "條件篩選", "依條件篩選查詢結果",
         "data_query", "query", "tool_execute", "none",
         ["篩選", "條件", "只看某些"],
         "幫我篩選「{table_name}」中符合條件的資料", 12,
     ),
     make_page_action_doc(
         "pa_dq_export", "匯出查詢結果", "將查詢結果匯出",
         "data_query", "action", "confirm_then_execute", "none",
         ["匯出", "下載結果"],
         "幫我匯出「{page_name}」的查詢結果到檔案", 10,
     ),
     make_page_action_doc(
         "pa_dq_gen_sql", "產生查詢語句", "根據需求產生 SQL 查詢",
         "data_query", "query", "tool_execute", "none",
         ["產生 SQL", "寫查詢", "生成語句"],
         "幫我為「{table_name}」產生查詢語句", 16,
     ),
]

# ── schema_manage (6) ──
schema_manage_intents = [
    make_page_action_doc(
         "pa_sm_explain", "告訴我這個功能的操作說明", "說明 Schema 管理頁面的功能與操作方式",
         "schema_manage", "explain", "direct_llm", "none",
         ["這個頁面怎麼用", "Schema 頁怎麼操作", "操作說明"],
         "告訴我「{page_name}」的操作說明", 20,
     ),
     make_page_action_doc(
         "pa_sm_view_structure", "查看表結構", "說明目前 Schema 頁面的表結構瀏覽方式",
         "schema_manage", "query", "direct_llm", "none",
         ["如何看表結構", "Schema 怎麼看", "有哪些表"],
         "告訴我在「{page_name}」中如何查看表結構", 17,
     ),
     make_page_action_doc(
         "pa_sm_view_columns", "查看欄位資訊", "查看指定資料表的欄位與型別資訊",
         "schema_manage", "action", "tool_execute", "none",
         ["查看欄位", "欄位資訊", "看欄位型別"],
         "幫我在「{page_name}」中查看這張表的欄位資訊", 16,
     ),
     make_page_action_doc(
         "pa_sm_preview_data", "預覽資料", "開啟資料表的預覽內容",
         "schema_manage", "action", "tool_execute", "none",
         ["預覽資料", "看資料內容", "打開資料預覽"],
         "幫我在「{page_name}」中預覽這張表的資料", 15,
     ),
     make_page_action_doc(
         "pa_sm_import_schema", "匯入 Schema", "匯入或同步新的 Schema 結構",
         "schema_manage", "action", "confirm_then_execute", "reversible",
         ["匯入 schema", "導入表結構", "同步 schema"],
         "幫我在「{page_name}」中匯入新的 Schema", 14,
     ),
     make_page_action_doc(
         "pa_sm_search_table", "搜尋資料表", "在 Schema 清單中搜尋指定資料表",
         "schema_manage", "action", "tool_execute", "none",
         ["搜尋資料表", "找表", "查 table"],
         "幫我在「{page_name}」中搜尋指定資料表", 13,
     ),
]

# ── knowledge (5) ──
knowledge_intents = [
    make_page_action_doc(
         "pa_kb_explain", "告訴我這個功能的操作說明", "說明知識庫頁面的功能與操作",
         "knowledge", "explain", "direct_llm", "none",
         ["知識庫怎麼用", "操作說明"],
         "告訴我「{page_name}」的操作說明", 20,
     ),
     make_page_action_doc(
         "pa_kb_create", "建立知識庫", "建立新的知識庫",
         "knowledge", "action", "confirm_then_execute", "reversible",
         ["建立知識庫", "新增知識庫"],
         "幫我建立一個新的知識庫「{domain_name}」", 15,
     ),
     make_page_action_doc(
         "pa_kb_upload", "上傳文件", "上傳文件到知識庫",
         "knowledge", "action", "confirm_then_execute", "reversible",
         ["上傳", "匯入文件", "加文件"],
         "幫我上傳文件到「{domain_name}」知識庫", 14,
     ),
     make_page_action_doc(
         "pa_kb_search", "搜尋知識", "在知識庫中搜尋相關內容",
         "knowledge", "query", "tool_execute", "none",
         ["搜尋知識", "找資料", "查文件"],
         "幫我在「{domain_name}」中搜尋相關知識", 13,
     ),
     make_page_action_doc(
         "pa_kb_vectorize", "向量化", "對知識庫進行向量化處理",
         "knowledge", "action", "confirm_then_execute", "none",
         ["向量化", "Embedding", "建索引"],
         "幫我對「{domain_name}」進行向量化處理", 12,
     ),
]

# ── chat (3) ──
chat_intents = [
    make_page_action_doc(
         "pa_chat_explain", "告訴我這個功能的操作說明", "說明 AI 對話頁面的功能",
         "chat", "explain", "direct_llm", "none",
         ["對話怎麼用", "操作說明"],
         "告訴我「{page_name}」的操作說明", 20,
     ),
     make_page_action_doc(
         "pa_chat_new", "開始新對話", "開啟新的 AI 對話",
         "chat", "action", "navigate", "none",
         ["新對話", "重新開始"],
         "在「{page_name}」中開始一個新的對話", 15,
     ),
     make_page_action_doc(
         "pa_chat_commands", "支援指令", "查看支援的指令列表",
         "chat", "query", "direct_llm", "none",
         ["有哪些指令", "支援什麼", "指令列表"],
         "「{page_name}」中有哪些支援的指令？", 14,
     ),
]

# ── browse (3) ──
browse_intents = [
    make_page_action_doc(
         "pa_browse_explain", "告訴我這個功能的操作說明", "說明瀏覽頁面的功能",
         "browse", "explain", "direct_llm", "none",
         ["有哪些可用的", "操作說明"],
         "告訴我「{page_name}」的操作說明", 20,
     ),
     make_page_action_doc(
         "pa_browse_list", "瀏覽列表", "查看可用的項目列表",
         "browse", "query", "direct_llm", "none",
         ["列出所有", "有哪些", "全部"],
         "在「{page_name}」中列出所有可用的項目", 15,
     ),
     make_page_action_doc(
         "pa_browse_detail", "查看詳情", "查看特定項目的詳細資訊",
         "browse", "query", "direct_llm", "none",
         ["詳情", "詳細說明", "看一下"],
         "查看「{page_name}」中這個項目的詳細資訊", 14,
     ),
]

# ── common (3) — 所有頁面共用 ──
common_intents = [
    make_page_action_doc(
         "pa_common_help", "使用幫助", "提供整體系統使用說明",
         "common", "explain", "direct_llm", "none",
         ["幫助", "怎麼用", "使用說明"],
         "系統有哪些功能？請為我說明「{page_name}」", 5,
     ),
     make_page_action_doc(
         "pa_common_shortcut", "快捷操作", "常用功能快捷入口",
         "common", "action", "navigate", "none",
         ["快捷", "快速", "跳轉"],
         "「{page_name}」中有哪些快捷操作？", 4,
     ),
     make_page_action_doc(
         "pa_common_feedback", "回報問題", "回報系統問題或建議",
         "common", "action", "direct_llm", "none",
         ["回報", "建議", "問題回饋"],
         "我想回報關於「{page_name}」的問題", 3,
     ),
]


def main() -> None:
    """Seed all page_action intents into intent_catalog."""
    print("=== Seeding page_action intents ===")

    all_groups = [
        (data_table_intents, "data_table"),
        (form_crud_intents, "form_crud"),
        (config_intents, "config"),
        (dashboard_intents, "dashboard"),
        (data_query_intents, "data_query"),
        (schema_manage_intents, "schema_manage"),
        (knowledge_intents, "knowledge"),
        (chat_intents, "chat"),
        (browse_intents, "browse"),
        (common_intents, "common"),
    ]

    total = 0
    for docs, label in all_groups:
        insert_batch(docs, f"page_action/{label}")
        total += len(docs)

    print(f"\n  Total: {total} page_action intents seeded.")


if __name__ == "__main__":
    main()
