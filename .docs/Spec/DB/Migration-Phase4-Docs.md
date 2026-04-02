---
lastUpdate: 2026-04-02 12:00:00
author: Daniel Chung
version: 1.1.0
---

# Migration Phase 4: 規格文件與附錄

## §1 Phase 4 概述

本階段任務是完成所有技術文件的更新，並定義交付標準與風險對策。

**核心範圍**：
- 更新 Data Agent 規格書（T4-1）。
- 更新 API 規格書（T4-2）。
- 更新 Ragic 資料表對應表（T4-3）。
- 風險與交付標準（MVP）。

---

## §2 詳細任務卡片 (T4-1 ~ T4-3)

### T4-1：更新 data-agent-spec-v2.md

**檔案**：`.docs/Spec/後台/DA/data-agent-spec-v2.md`

**變更點**：
- 將 DuckDB + SAP Parquet 架構圖更新為 Ragic + S3 Parquet 架構圖。
- `da_table_info`、`da_field_info`、`da_table_relation` JSON Schema 更新為 Ragic 格式。
- 移除所有 SAP 初始化資料（10 表）。
- 補充 Ragic Sheet 初始化資料（Phase 1 的 6 張核心 sheets）。
- 新增 `DATA_SOURCE` 系統級設定說明。

### T4-2：更新 API Specification.md

**檔案**：`.docs/API Specification.md`

**變更點**：
- 新增 `DATA_SOURCE` 參數對 API 的影響說明。
- 備註 ETL 是獨立專案，Data Agent 只接收已同步的 Parquet 資料。

### T4-3：更新 RagicTableSchema.md

**檔案**：`.docs/Spec/DB/RagicTableSchema.md`

**變更點**：
- 確認並補充 Phase 1 的 6 張 sheets 的完整欄位定義（含子表格）。
- 補充所有已知 Tab 的 Sheet Key 對照表。

---

## §3 附錄：Ragic API Handoff 規格

本章節提供給 ETL 專案參考，定義 Data Agent 需要的 Parquet 格式與元資料。

### 3.1 Parquet 寫出路徑規範

```
s3://{bucket}/
├── {sheet_name_slug}/
│   ├── YYYY-MM.parquet    # 當月分區
│   └── _sync_meta.json     # 同步元資料（last_sync_time, record_count）
```

- `bucket`：由 `DA_S3_BUCKET` 環境變數指定（預設 `ragic`）。
- `sheet_name_slug`：將 Sheet 名稱轉換為小寫底線格式（例如：員工管理 → `employees`）。

### 3.2 系統欄位對應 (Field ID)

- **建立日期**: `105`
- **建立者**: `108`
- **最後更新日期**: `109`

---

## §4 風險與對策

| 風險 | 對策 |
|------|------|
| Ragic Field ID 與 Parquet 欄位名稱不一致 | ArangoDB 同時儲存 Field ID 與中文名稱；Prompt 中使用中文名稱讓 LLM 推理。 |
| Ragic Schema 變動 | ETL 每次執行前比對 schema，有變更時重新執行 Seed ArangoDB。 |
| 子表格資料龐大 | MVP 階段先不做子表格展開；Phase 2 以獨立 sheet 形式實作。 |
| 連結欄位顯示值 ≠ 實際 ID | ETL 同步時解析連結欄位，還原為實際 Record ID。 |

---

## §5 交付標準 (MVP)

### MVP 完成定義（後端）

- [ ] Ragic Schema Collections 已建立並完成 Phase 1 資料寫入。
- [ ] SQL Generator 路徑由 `DATA_SOURCE` 參數動態控制。
- [ ] SAP Collections 保留並可透過 `DATA_SOURCE=sap` 切換使用。
- [ ] NL 查詢「查詢近30天員工進貨明細」能正確產出 SQL 並回傳結果。
- [ ] 程式碼通過 `mypy` 與 `ruff` 檢查。

### MVP 完成定義（前端）

- [ ] SchemaPage.tsx 支援 Tab Filter 與 `dataSourceFilter`。
- [ ] Module Select 依資料來源動態切換清單。
- [ ] 欄位 Modal 支援顯示 `writable` 標記。
- [ ] QueryPlayground.tsx 預設範例更新為 Ragic 場景。

---

## §6 環境變數說明

| 變數名 | 說明 | 預設值 |
|--------|------|--------|
| `DATA_SOURCE` | 資料來源：`sap` 或 `ragic` | `sap` |
| `DA_S3_BUCKET` | 資料湖 Bucket 名稱 | `ragic` |
| `S3_BUCKET` | 共通 S3 Bucket | `ragic` |
| `ARANGO_URL` | ArangoDB 位址 | `http://localhost:8529` |
