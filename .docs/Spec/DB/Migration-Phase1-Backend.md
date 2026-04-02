---
lastUpdate: 2026-04-02 12:00:00
author: Daniel Chung
version: 1.1.0
---

# Migration Phase 1: Schema Migration (Backend)

## §1 Phase 1 概述

本階段主要任務是將 ArangoDB 中的 Schema 知識庫從單一資料來源擴展為雙資料來源架構。

**核心範圍**：
- 完成現有 SAP Collections 的重新命名（T-000）。
- 建立 Ragic 專屬的 Schema Seed 腳本與 Collections（T-001 ~ T-003）。
- 更新後端 Pipeline 模型以支援動態 Collection 選擇（T1-3）。

---

## §2 SAP Schema Seed 保留 (T1-1)

**說明**：新架構中 SAP 與 Ragic 各自使用獨立的 Collections，SAP Schema Seed (`seed_schema.py`) 維持不變，寫入 `da_table_info_sap`、`da_field_info_sap`、`da_table_relation_sap`。

**驗證**：執行後 `da_table_info_sap` 中保有 SAP 表 records（MM_MARA, MM_LFA1 等）。

---

## §3 Ragic Schema Seed Script 計劃 (T1-2)

**檔案**：`ai-services/datalake/seed_ragic_schema.py`（新建）

**寫入 Collections**：
- `da_table_info_ragic`
- `da_field_info_ragic`
- `da_table_relation_ragic`

**功能**：
1. 從 `RagicTableSchema.md` 或直接呼叫 Ragic API `GET /?api&hdr=1` 取得所有 Sheets 的 schema。
2. 將每張 Sheet 轉換為 `da_table_info_ragic` document（詳見 T-001）。
3. 將每個欄位轉換為 `da_field_info_ragic` document（詳見 T-001）。
4. 建立 `da_table_relation_ragic`（處理 Ragic 連結欄位關聯）。

**優先順序**：先完成 Phase 1 的 6 張核心 sheets，其餘依序擴展。

---

## §4 Pipeline Models 更新計劃 (T1-3)

**檔案**：`ai-services/data_agent/query/nl2sql/models.py`

**變更點**：
- `TableSchema` 新增欄位：`tab`, `sheet_key`, `s3_path`, `record_count`, `data_source`。
- `FieldSchema` 新增欄位：`field_id`（Ragic Field ID）、`writable`、`is_subtable_field`、`subtable_key`。
- `PipelineConfig` 新增欄位：`data_source: str`（預設 `sap`，由 `DATA_SOURCE` 參數決定）。
- 移除或標記廢除欄位：`row_count_estimate` → 改為 `record_count`（實際值）。
- **新增 collection name helper**：Schema Retriever 依 `data_source` 動態選擇 Collection 名稱（`da_table_info_{data_source}`）。

---

## §5 詳細任務卡片 (T-000 ~ T-003)

### T-000：Rename 現有 Collections 為 _sap（破壞性操作，請先確認）

```
⚠️ 此為破壞性操作，必須在所有程式碼更新完成後執行

輸入：ArangoDB
輸出：da_table_info → da_table_info_sap, da_field_info → da_field_info_sap, da_table_relation → da_table_relation_sap

前置條件：
  - T-009（Schema Retriever Collection Routing）已實作完成
  - 所有讀取 da_table_info 的程式碼已改為動態 Collection 名稱

工作內容：
1. 執行 Collection rename（見下方 API 指令）
2. 驗證 rename 後的 Collections 中資料完整
3. 更新 seed_schema.py 中的 Collection 名稱為 _sap 後綴

ArangoDB Rename API：
  POST /_api/collection/da_table_info/rename
  Body: {"name": "da_table_info_sap"}

  POST /_api/collection/da_field_info/rename
  Body: {"name": "da_field_info_sap"}

  POST /_api/collection/da_table_relation/rename
  Body: {"name": "da_table_relation_sap"}

驗證：
  GET /_api/collection/da_table_info_sap  # 確認存在
  GET /_api/collection/da_table_info       # 確認不存在（404）
```

### T-001：建立 Ragic Schema Seed Script

```
輸入：RagicTableSchema.md 或 Ragic API schema endpoint
輸出：ai-services/datalake/seed_ragic_schema.py

工作內容：
1. 建立 script 框架
2. 定義 sheet_metadata 清單（Phase 1: 6 張核心 sheets）
3. 實作 da_table_info 產生邏輯
4. 實作 da_field_info 產生邏輯（包含 writable、subtable_key）
5. 實作 da_table_relation 產生邏輯（處理連結欄位）
6. 測試執行並驗證 ArangoDB documents 正確寫入

# da_table_info_ragic record 格式範例
{
    "_key": "CFG7_EMPLOYEE",
    "table_id": "CFG7_EMPLOYEE",           # 格式：{Tab}{SheetKey}_{中文簡稱}
    "table_name": "員工管理",
    "tab": "configuration-file",
    "sheet_key": "7",
    "module": "HR",                          # 由 Tab 推斷
    "description": "員工主檔，含基本資料與緊急聯絡人",
    "s3_path": "s3://ragic/employees/",    # Parquet 資料路徑（ETL 同步後產生）
    "primary_keys": ["_ragicId"],
    "partition_keys": ["_year", "_month"],
    "record_count": 0,
    "status": "enabled",
    "version": 1,
    "created_at": "2026-03-31T00:00:00Z",
    "updated_at": "2026-03-31T00:00:00Z",
    "updated_by": "system"
}

# da_field_info_ragic record 格式範例
{
    "_key": "CFG7_1015429",
    "table_id": "CFG7_EMPLOYEE",
    "field_id": "1015429",                  # Ragic Field ID
    "field_name": "員工姓名",
    "field_type": "VARCHAR",                # 從 Ragic Type 映射
    "length": None,
    "nullable": False,
    "description": "不可重複必填",
    "business_aliases": ["姓名", "員工名"],
    "is_pk": False,
    "is_fk": False,
    "writable": True,                       # Ragic Writable 屬性
    "is_subtable_field": False,
    "subtable_key": None,
    "relation_table": None,
    "relation_field": None,
    "status": "enabled",
    "created_at": "2026-03-31T00:00:00Z",
    "updated_at": "2026-03-31T00:00:00Z"
}
```

### T-002：建立 Ragic Schema Collections

```
輸入：ArangoDB
輸出：建立 da_table_info_ragic、da_field_info_ragic、da_table_relation_ragic

工作內容：
1. 在 ArangoDB 中建立新的 Collections
2. 建立必要索引（table_id unique index、module+status index 等）
3. 驗證 Collections 已建立
```

### T-003：執行 Phase 1 Schema Seed

```
輸入：ai-services/datalake/seed_ragic_schema.py
輸出：寫入 da_table_info_ragic、da_field_info_ragic、da_table_relation_ragic

工作內容：
1. 確認 Ragic API Key 有效
2. 執行 seed_ragic_schema.py（Phase 1: 員工管理、品項管理、交易對象、倉儲位管理、組織部門、進貨單）
3. 驗證 da_table_info_ragic、da_field_info_ragic、da_table_relation_ragic records 數量正確
```
