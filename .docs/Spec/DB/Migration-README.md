---
lastUpdate: 2026-04-02 12:00:00
author: Daniel Chung
version: 1.1.0
---

# Data Agent SAP → Ragic 遷移計劃

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-02 | 1.1.0 | Daniel Chung | 將大型遷移計劃拆分為模組化文件 |
| 2026-03-31 | 1.0.0 | Daniel Chung | 初始版本 |

---

## 專案概述

本計劃定義 AIBox Data Agent 從 SAP Demo 資料來源遷移到 Ragic 實際資料來源的完整技術路徑。為了確保系統的穩定性與靈活性，我們採用 **雙資料來源架構**，允許系統在 SAP 與 Ragic 之間進行切換。

### 核心策略：雙 Collections 模式

- **完全隔離**：現有的 SAP Collections 將重新命名並保留（加上 `_sap` 後綴），新建 Ragic 專用的 Collections（加上 `_ragic` 後綴）。
- **動態路由**：Schema Retriever 會根據系統參數 `DATA_SOURCE` 自動選擇讀取哪一套 Collections。
- **S3 路徑切換**：SQL Generator 根據資料來源自動切換 `s3://sap/` 或 `s3://ragic/` 路徑前綴。

### 注意事項

- **ETL 範圍**：實際的資料同步（Ragic → Parquet → S3）由獨立的 ETL 專案負責，本計劃僅涵蓋 Data Agent 的對接與查詢邏輯。
- **DuckDB 引擎**：由於資料最終都存放為 Parquet 格式，DuckDB 查詢引擎層級保持不變。

---

## 遷移階段目錄

本遷移計劃分為四個階段執行，請點擊下方連結查看詳細規格：

| 階段 | 標題 | 範圍與重點 |
|------|------|------------|
| [Phase 1](./Migration-Phase1-Backend.md) | **Schema 遷移** | T-000 ~ T-003：建立 ArangoDB 新 Collection 與 Seed 腳本 |
| [Phase 2](./Migration-Phase2-Backend.md) | **Pipeline 重寫** | T-004 ~ T-009：更新 NL2SQL 核心邏輯、Prompt 與 Intent RAG |
| [Phase 3](./Migration-Phase3-Frontend.md) | **前端頁面更新** | T3-1 ~ T3-8：Schema 管理頁面支援雙來源過濾與 Ragic 欄位 |
| [Phase 4](./Migration-Phase4-Docs.md) | **規格文件與附錄** | T4-1 ~ T4-3：更新系統規格書、API 文件與風險評估 |

---

## 快速參考：任務清單

| 編號 | 任務名稱 | 負責方 | 狀態 | 詳情 |
|------|----------|--------|------|------|
| T-000 | Rename 現有 Collections 為 _sap | 後端 | Pending | [Phase 1](./Migration-Phase1-Backend.md#t-000) |
| T-001 | 建立 Ragic Schema Seed Script | 後端 | Pending | [Phase 1](./Migration-Phase1-Backend.md#t-001) |
| T-004 | 更新 SQL Generator 路徑動態化 | 後端 | Pending | [Phase 2](./Migration-Phase2-Backend.md#t-004) |
| T3-1 | 更新 前端 API Types | 前端 | Pending | [Phase 3](./Migration-Phase3-Frontend.md#t3-1) |

> **即時進度追蹤**：請參閱 [Migration-Progress.md](./Migration-Progress.md)（如已建立）獲取最新執行狀態。
