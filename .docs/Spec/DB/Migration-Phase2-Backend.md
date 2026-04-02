---
lastUpdate: 2026-04-02 12:00:00
author: Daniel Chung
version: 1.1.0
---

# Migration Phase 2: Pipeline 重寫 (Backend)

## §1 Phase 2 概述

本階段任務是更新 NL→SQL Pipeline 的核心邏輯，使其能夠根據 `DATA_SOURCE` 參數動態處理 SAP 與 Ragic 的查詢語境。

**核心範圍**：
- SQL 生成器路徑動態化（T-004）。
- 意圖分類器 Prompt 更新（T-005）。
- Intent RAG 範本更新（T-006）。
- Schema Retriever 與 Config Reader 更新（T-008 ~ T-009）。

---

## §2 SQL Generator 更新 (T2-1)

**檔案**：`ai-services/data_agent/query/nl2sql/sql_generator.py`

**變更點**：
- 將硬編碼路徑改為由 `PipelineConfig.data_source` 動態控制。
- `s3://sap/` → `f"s3://{data_source}/"` （data_source 由 `DATA_SOURCE` 參數決定）。
- 搜尋範圍：`sql_generator.py`、`seed_intent_catalog.py`、所有 prompt templates。
- DuckDB SQL 語法不變（Parquet 結構相同）。
- Prompt 中使用 `FROM read_parquet('s3://{data_source}/...')`。

---

## §3 Intent Classifier Prompts (T2-2)

**檔案**：`ai-services/data_agent/query/nl2sql/intent_classifier.py`

**變更點**：更新 Prompt 範例，加入 Ragic 業務語境，同時保留 SAP 範例供相容使用。

```python
# Ragic 新範例（新增於 Prompt 中）
{
    "nl": "查詢近30天各供應商的進貨明細",
    "tables": ["進貨單", "品項管理", "交易對象"],
    "intent": "filter+join"
}
{
    "nl": "查詢某員工最近領料記錄",
    "tables": ["領料單", "員工管理"],
    "intent": "filter"
}
{
    "nl": "查詢某品項的庫存現量",
    "tables": ["庫存表", "品項管理", "倉儲位管理"],
    "intent": "filter+aggregate"
}
```

---

## §4 Intent RAG Templates (T2-3)

**檔案**：`ai-services/datalake/seed_intent_catalog.py`

**變更點**：
- 新增 Ragic Intent Templates，同時保留 SAP Templates。
- SQL Template 路徑動態化或明確標註為 `s3://ragic/`。

```python
# 範例：Ragic Intent Template
{
    "intent_id": "ragic_po_summary",
    "nl_examples": [
        "查詢近30天各供應商的進貨總金額",
        "統計本月各供應商採購金額",
        "各供應商進貨金額排名"
    ],
    "tables": ["CFG_PURCHASE_進貨單", "CFG_ITEM", "CFG_VENDOR"],
    "sql_template": """
        SELECT t1.交易對象, SUM(t2.進貨金額) AS total
        FROM read_parquet('s3://ragic/purchase_orders/*.parquet') AS t1
        JOIN read_parquet('s3://ragic/purchase_order_items/*.parquet') AS t2
          ON t1._ragicId = t2._parentId
        WHERE t1.進貨日期 >= ? AND t1.進貨日期 <= ?
        GROUP BY t1.交易對象
        ORDER BY total DESC
        LIMIT ?
    """,
    "generation_strategy": "template",
    "hit_count": 0
}
```

---

## §5 Schema Retriever (T2-4)

**檔案**：`ai-services/data_agent/query/nl2sql/schema_retriever.py`

**變更點**：
- `table_id` 格式變更（例如：`MM_EKKO` → `CFG_PURCHASE_進貨單`）。
- 回傳時同時包含 `field_id`（Ragic Field ID）和 `field_name`（中文名稱）。
- LLM Prompt 中使用中文欄位名稱，SQL 生成時替換為實際 Parquet 欄位名。

---

## §6 Config Reader (T2-5)

**檔案**：`ai-services/data_agent/config_reader.py`

**變更點**：
- 新增環境變數：`DA_S3_BUCKET`（預設 `ragic`）。
- 確保 `DATA_SOURCE` 參數能正確傳遞至 Pipeline 全域設定。

---

## §7 詳細任務卡片 (T-004 ~ T-009)

### T-004：更新 SQL Generator 路徑動態化

```
輸入：ai-services/data_agent/query/nl2sql/sql_generator.py
輸出：路徑由 PipelineConfig.data_source 動態控制

工作內容：
1. 將所有硬編碼 s3://sap/ 改為 f"s3://{config.data_source}/"
2. grep -r "s3://sap/" ai-services/data_agent/ 確認無殘留
3. Prompt templates 中使用 {data_source} 變數
4. 執行 mypy + ruff check
```

### T-005：新增 Intent Classifier Ragic 範例

```
輸入：ai-services/data_agent/query/nl2sql/intent_classifier.py
輸出：Prompt 中新增 Ragic 業務範例，SAP 範例保留

工作內容：
1. 讀取現有 prompt templates
2. 設計新的 Ragic 業務範例（至少 10 個）
3. 新增而非替換，SAP 範例保留供 SAP 模式使用
4. 執行單元測試驗證
```

### T-006：新增 Ragic Intent RAG Templates

```
輸入：ai-services/datalake/seed_intent_catalog.py
輸出：Qdrant 中的 Ragic Intent Templates

工作內容：
1. 新增 Ragic Intent Templates（Phase 1: 6 張 sheets 的常見查詢），SAP Templates 保留
2. 執行 seed_intent_catalog.py
3. 驗證 Qdrant collection 中同時存在 SAP 與 Ragic templates
```

### T-007：更新 Pipeline Models

```
輸入：ai-services/data_agent/query/nl2sql/models.py
輸出：新增 Ragic 相關欄位

工作內容：
1. TableSchema 新增：tab, sheet_key, s3_path
2. FieldSchema 新增：field_id (Ragic), writable, is_subtable_field, subtable_key
3. PipelineConfig 新增：S3_BUCKET 預設值改為 ragic
4. 執行 mypy check
```

### T-008：更新 Config Reader

```
輸入：ai-services/data_agent/config_reader.py
輸出：新增 Ragic 相關環境變數

工作內容：
1. 新增 DA_S3_BUCKET 環境變數讀取
2. 確保 PipelineConfig 正確傳遞
3. 更新 .env 範例檔（如有）
```

### T-009：更新 Schema Retriever Collection Routing

```
輸入：ai-services/data_agent/query/nl2sql/schema_retriever.py
輸出：依 DATA_SOURCE 動態選擇 Collection

工作內容：
1. 實作 _get_collection_name() helper，依 data_source 返回正確 Collection 名稱
2. _fetch_tables 改為查詢 da_table_info_{data_source}
3. _fetch_fields 改為查詢 da_field_info_{data_source}
4. _fetch_relations 改為查詢 da_table_relation_{data_source}
5. 執行單元測試
```

### T-010：端到端測試

```
輸入：所有 Phase 1–2 變更
輸出：NL 查詢能正確產出 SQL 並回傳結果

測試案例：
1. 「查詢所有員工名單」→ SQL 正確讀取 ragic/employees/*.parquet
2. 「查詢近30天進貨明細」→ SQL 正確過濾日期範圍
3. 「查詢各部門員工人數」→ SQL 正確 JOIN employees + departments
4. Query Playground 顯示正確結果
```
