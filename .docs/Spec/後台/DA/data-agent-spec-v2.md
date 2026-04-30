---
lastUpdate: 2026-04-24 10:07:45
author: Daniel Chung (with AI assistance)
version: 2.1.0
status: Complete Draft
---

# Data Agent (DA) v2.0 規格書

> 文件定位：本文件定義 AIBox Data Agent (DA) v2.0 的完整後端架構、資料流程、通訊協議、安全控制、前端維護介面與部署整合標準。

---

## §1 文檔概述

### 1.1 文檔修訂歷史

| 日期 | 版本 | 作者 | 變更說明 |
|------|------|------|----------|
| 2026-04-24 | 2.1.0 | Daniel Chung (with AI assistance) | 修正部署與整合拓樸：Data Agent 對外整合入口改為 unified_agents(:8011)/da/*，前端統一經 Rust API Gateway(:6500) |
| 2026-03-22 | 2.0.0 | Daniel Chung (with AI assistance) | 完整重寫 DA 規格：採用 DuckDB + SeaWeedFS S3 + ArangoDB + Qdrant 架構，補齊端到端流程與前端維護畫面 |
| 2026-03-20 | 1.1.0 | Internal | 初版草稿補充少量資料表，但未完成 |
| 2026-03-18 | 1.0.0 | Internal | DA 初始概念文件（96 行，不完整，且含錯誤的 MySQL/PostgreSQL 方向） |

### 1.2 目錄

- [§1 文檔概述](#1-文檔概述)
  - [1.1 文檔修訂歷史](#11-文檔修訂歷史)
  - [1.2 目錄](#12-目錄)
  - [1.3 文檔目的](#13-文檔目的)
  - [1.4 適用範圍](#14-適用範圍)
  - [1.5 核心目標](#15-核心目標)
  - [1.6 前置條件](#16-前置條件)
  - [1.7 v1.0 → v2.0 主要差異摘要](#17-v10--v20-主要差異摘要)
- [§2 系統架構](#2-系統架構)
  - [2.1 DA 在 AIBox 架構中的位置](#21-da-在-aibox-架構中的位置)
  - [2.2 DA 無狀態服務設計](#22-da-無狀態服務設計)
  - [2.3 核心資料查詢管線](#23-核心資料查詢管線)
  - [2.4 技術棧](#24-技術棧)
- [§3 核心模組設計](#3-核心模組設計)
  - [3.1 Schema 知識庫（ArangoDB）](#31-schema-知識庫arangodb)
  - [3.2 意圖識別模組（Intent Recognition）](#32-意圖識別模組intent-recognition)
  - [3.3 Schema Binding（意圖與 Schema 綁定）](#33-schema-binding意圖與-schema-綁定)
  - [3.4 Intent 向量匹配（Qdrant）](#34-intent-向量匹配qdrant)
  - [3.5 SQL 生成模組](#35-sql-生成模組)
  - [3.6 查詢執行模組（DuckDB + SeaWeedFS S3）](#36-查詢執行模組duckdb--seaweedfs-s3)
- [§4 資料流程（Complete Pipeline）](#4-資料流程complete-pipeline)
- [§5 通信協議（Integration with Top Orchestrator v2.0）](#5-通信協議integration-with-top-orchestrator-v20)
- [§6 持久化設計（ArangoDB + Qdrant）](#6-持久化設計arangodb--qdrant)
- [§7 安全設計](#7-安全設計)
- [§8 錯誤處理](#8-錯誤處理)
- [§9 前端維護畫面](#9-前端維護畫面)
- [§10 部署與整合](#10-部署與整合)
- [§11 附錄](#11-附錄)

### 1.3 文檔目的

本文件目的是提供 **可直接落地實作** 的 Data Agent v2.0 產品級規格，確保：

1. DA 可以由自然語言查詢穩定產出可執行、可審計、可控風險的 SQL。
2. DA 能與 Top Orchestrator v2.0 Handoff Protocol (`schema_version: "2.0"`) 完整對接。
3. DA 前後端可獨立演進，並維持一致的 API 契約與資料模型。
4. DA 不再使用 v1.0 過時設計（MySQL/PostgreSQL metadata），改為 ArangoDB + Qdrant + DuckDB 主軸。

### 1.4 適用範圍

本規格適用於以下範圍：

- AIBox Data Agent Python 模組（實作位於 `ai-services/data_agent/`，對外整合入口為 `unified_agents:8011/da/*`）
- Rust API Gateway（`port 6500`）轉發 DA 請求
- BPA 服務（`port 8005`）到 DA 的查詢委派
- unified_agents（`port 8011`）承載 DA / KA / Memory / Backup 等整合路由
- ArangoDB（`port 8529`）Schema/Intent metadata
- Qdrant（`port 6333`）Intent 向量快取
- Ollama（`port 11434`）意圖抽取與 SQL fallback 生成
- SeaWeedFS S3 Data Lake（SAP Parquet）

### 1.5 核心目標

DA v2.0 核心目標如下：

1. **安全性**：只允許 `SELECT`，全面阻擋 DML/DDL；所有條件使用參數綁定。
2. **一致性**：意圖、Schema、SQL 三者必須可追溯，產生可審計的查詢鏈路。
3. **性能**：常見查詢端到端目標 < 8 秒；快取命中路徑 SQL 生成 < 50ms。
4. **可維運**：提供完整 DA 管理頁（Schema、Intent、Sync、Playground）。
5. **可擴展**：可新增 SAP 模組與欄位而不需重寫核心引擎。

### 1.6 前置條件

DA v2.0 上線前，必須滿足以下前置條件：

1. SeaWeedFS S3 已部署且可讀取 SAP Parquet 檔案。
2. ArangoDB（8529）已運行，並可建立 DA 專用 collections。
3. Qdrant（6333）已運行，支援 1024 維向量（Cosine）。
4. Ollama（11434）已啟動，至少可提供 BGE-M3 embedding 與 SQL 生成模型。
5. API Gateway 與 BPA 已可轉發 JWT 與 correlation headers。
6. DA 服務容器可連通 S3 endpoint、ArangoDB、Qdrant、Ollama。
7. Frontend 已使用 React 18 + Ant Design 6.x + React Router 並支援新路由。

### 1.7 v1.0 → v2.0 主要差異摘要

| 比較項 | v1.0 | v2.0 |
|--------|------|------|
| Metadata DB | MySQL/PostgreSQL（方向錯誤） | **ArangoDB（標準）** |
| Query Engine | 未落地 | **DuckDB + S3 Parquet** |
| Intent 快取 | 無 | **Qdrant 向量匹配（threshold 0.85）** |
| 安全策略 | 無完整設計 | **只讀 SQL 白名單 + AST 驗證 + 參數綁定** |
| 協議整合 | 未對齊 | **對齊 Top Orchestrator v2.0 schema_version=2.0** |
| 前端維運頁 | 無 | **4 個 DA 管理頁完整規格** |
| 資料來源 | SAP only | **Dual-source: SAP + Ragic (via DATA_SOURCE env var)** |
| Intent 路由 | Static | **Dynamic routing via intent prefix (sap_/rgc_)** |
| 錯誤碼 | 不完整 | **完整 DA_* 錯誤碼 + 重試/降級策略** |
| 可觀測性 | 弱 | **全鏈路 audit + metrics + trace id** |

---

## §2 系統架構

### 2.1 DA 在 AIBox 架構中的位置

```text
┌──────────────────────┐
│ Frontend (React 18)  │
└──────────┬───────────┘
           │ HTTPS
           ▼
┌──────────────────────────────┐
│ API Gateway (Rust Axum :6500)│
└──────────┬───────────────────┘
           │ internal HTTP
           ▼
┌──────────────────────────────────────────────────────────────┐
│ unified_agents (FastAPI :8011)                              │
│  /da/* → Data Agent modules                                  │
│  /ka/* → Knowledge Agent                                     │
└──────┬───────────────────────────┬───────────────────────────┘
       │                           │
       │ /da/*                     │
       ▼                           ▼
┌──────────────────────────────────────────────────────────────┐
│ Data Agent implementation (ai-services/data_agent)          │
│  Intent → Binding → Vector Match → SQL Gen → DuckDB Execute │
└──────┬───────────────────────────┬───────────────────────────┘
       │                           │
       ▼                           ▼
┌──────────────┐           ┌────────────────┐
│ ArangoDB     │           │ Qdrant         │
│ :8529        │           │ :6333          │
│ Schema/Meta  │           │ Intent Vector  │
└──────┬───────┘           └────────────────┘
       │
       ▼
┌───────────────────────────────────────────┐
│ DuckDB (in-memory, httpfs)                │
│ read_parquet('s3://{data_source}/...') via S3 Secret │
└──────────────────┬────────────────────────┘
                   ▼
          ┌──────────────────────┐
          │ Ragic / SeaWeedFS S3 DataLake │
          │ Ragic Parquet Files  (s3://ragic/...) │
          │ SAP Parquet Files    (s3://sap/...)  │
          └──────────────────────┘
```

### 2.2 DA 無狀態服務設計

DA v2.0 明確定義為 **無狀態服務（Stateless Service）**：

1. DA 節點不保存使用者會話狀態於本機記憶體。
2. 所有查詢上下文透過請求 payload + JWT + trace headers 傳入。
3. 快取資料放在 Qdrant / ArangoDB，不綁定單一節點。
4. 任意節點可處理任一查詢，支援水平擴展與滾動升級。
5. 失敗重試可轉送至其他節點，不需 session stickiness。

### 2.3 核心資料查詢管線

DA v2.0 核心流程：

`NL Query → Intent Recognition → Schema Binding → Vector Match → SQL Generation → DuckDB Execution → Results`

關鍵原則：

- 先語義理解再產生 SQL。
- SQL 生成前一定要完成 Schema 綁定。
- SQL 執行前一定要做安全驗證。
- 執行結果與中間產物（intent、binding、cache hit）全部可追蹤。

### 2.4 技術棧

| Component | Technology | Purpose |
|-----------|------------|---------|
| DA Integration Entry | unified_agents `/da/*` (port 8011) | External integration entry for DA APIs |
| DA Service Module | Python FastAPI module `ai-services/data_agent` | DA implementation — dual-source (SAP + Ragic) |
| SQL Engine | DuckDB (in-memory, httpfs extension) | Query S3 Parquet files |
| Vector DB | Qdrant (port 6333) | Intent similarity matching |
| Metadata DB | ArangoDB (port 8529) | Schema KB + Intent records |
| Ragic API  | Ragic Cloud (ap15.ragic.com) | Phase 1 source (Employee, Item, Vendor, PO, etc.) |
| Embedding Model | BGE-M3 via Ollama (1024 dims) | Intent vectorization |
| Data Lake | SeaWeedFS S3 | SAP data (Parquet format) |

---

## §3 核心模組設計

> 本章為 DA v2.0 核心，定義資料結構、模組責任、演算法流程與可執行範例。

### 3.1 Schema 知識庫（ArangoDB）

#### 3.1.1 Collections 設計總覽

DA Schema 知識庫採三個核心 collection：

1. `da_table_info`：資料表層級 metadata
2. `da_field_info`：欄位層級 metadata
3. `da_table_relation`：跨表關聯 metadata

> **雙資料源設計**：Collection 名稱尾碼 `{data_source}`，由 `DA_DATA_SOURCE` 環境變數控制（如 `da_table_info_sap`、`da_table_info_ragic`）。Pipeline 依據意圖前綴動態切換：
> - `sap_` → SAP collections（`da_table_info_sap` 等）
> - `rgc_` → Ragic collections（`da_table_info_ragic` 等）

#### 3.1.2 `da_table_info` JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "da_table_info",
  "type": "object",
  "required": [
    "_key",
    "table_id",
    "table_name",
    "module",
    "description",
    "s3_path",
    "primary_keys",
    "partition_keys",
    "status",
    "version",
    "created_at",
    "updated_at",
    "data_source"
  ],
  "properties": {
    "_key": { "type": "string", "minLength": 1 },
    "table_id": { "type": "string", "pattern": "^[A-Z0-9_]+$" },
    "table_name": { "type": "string", "minLength": 1 },
    "module": { "type": "string", "enum": ["MM", "SD", "FI", "PP", "QM", "OTHER", "BASE", "PLM", "MFG", "PUR", "INV", "QA", "FORM", "SAL", "CRM", "FIN", "HR", "MES", "ADMIN", "AI"] },
    "description": { "type": "string", "minLength": 1 },
    "s3_path": { "type": "string", "pattern": "^s3://" },
    "primary_keys": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 },
      "minItems": 1
    },
    "partition_keys": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 },
      "minItems": 0
    },
    "row_count_estimate": { "type": "integer", "minimum": 0 },
    "status": { "type": "string", "enum": ["enabled", "disabled", "deprecated"] },
    "version": { "type": "integer", "minimum": 1 },
    "created_at": { "type": "string", "format": "date-time" },
    "updated_at": { "type": "string", "format": "date-time" },
    "updated_by": { "type": "string", "minLength": 1 },
    "data_source": { "type": "string", "enum": ["sap", "ragic"] },
    "tab": { "type": ["string", "null"] },
    "sheet_key": { "type": ["string", "null"] }
  },
  "additionalProperties": false
}
```

#### 3.1.3 `da_table_info` 初始化資料（6 個 Ragic Phase 1 Sheets）

Phase 1 涵蓋 6 張核心業務表單，覆蓋人事、庫存、採購三大領域。

> 注意：SAP 資料（原 10 表）保留於 `da_table_info_sap` collection，見附錄章節 A（歷史文件）。

```json
[
  {
    "_key": "CFG7_EMPLOYEE",
    "table_id": "CFG7_EMPLOYEE",
    "table_name": "員工主檔",
    "module": "BASE",
    "description": "員工基本資料，包含編號、姓名、所屬部門",
    "data_source": "ragic",
    "tab": "員工管理",
    "sheet_key": "configuration-file/7",
    "s3_path": "s3://ragic/configuration-file/7/",
    "primary_keys": ["1015428"],
    "partition_keys": [],
    "row_count_estimate": 500,
    "status": "enabled",
    "version": 1,
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z",
    "updated_by": "system"
  },
  {
    "_key": "CFG3_WAREHOUSE",
    "table_id": "CFG3_WAREHOUSE",
    "table_name": "倉儲位置主檔",
    "module": "BASE",
    "description": "倉庫與儲位資料，支援多倉庫管理",
    "data_source": "ragic",
    "tab": "倉儲位管理",
    "sheet_key": "configuration-file/3",
    "s3_path": "s3://ragic/configuration-file/3/",
    "primary_keys": ["1015343"],
    "partition_keys": [],
    "row_count_estimate": 200,
    "status": "enabled",
    "version": 1,
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z",
    "updated_by": "system"
  },
  {
    "_key": "CFG2_DEPT",
    "table_id": "CFG2_DEPT",
    "table_name": "組織部門主檔",
    "module": "ADMIN",
    "description": "組織部門階層結構",
    "data_source": "ragic",
    "tab": "組織部門",
    "sheet_key": "configuration-file/2",
    "s3_path": "s3://ragic/configuration-file/2/",
    "primary_keys": ["1015308"],
    "partition_keys": [],
    "row_count_estimate": 50,
    "status": "enabled",
    "version": 1,
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z",
    "updated_by": "system"
  },
  {
    "_key": "CFG9_ITEM",
    "table_id": "CFG9_ITEM",
    "table_name": "品項主檔",
    "module": "PUR",
    "description": "品項（物料）基本資料，含編碼、名稱、單位",
    "data_source": "ragic",
    "tab": "品項管理",
    "sheet_key": "configuration-file/9",
    "s3_path": "s3://ragic/configuration-file/9/",
    "primary_keys": ["1015486"],
    "partition_keys": [],
    "row_count_estimate": 5000,
    "status": "enabled",
    "version": 1,
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z",
    "updated_by": "system"
  },
  {
    "_key": "CFG10_VENDOR",
    "table_id": "CFG10_VENDOR",
    "table_name": "交易對象主檔",
    "module": "PUR",
    "description": "供應商/客戶交易對象資料",
    "data_source": "ragic",
    "tab": "交易對象",
    "sheet_key": "configuration-file/10",
    "s3_path": "s3://ragic/configuration-file/10/",
    "primary_keys": ["1015577"],
    "partition_keys": [],
    "row_count_estimate": 300,
    "status": "enabled",
    "version": 1,
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z",
    "updated_by": "system"
  },
  {
    "_key": "ERP48_PURCHASE_ORDER",
    "table_id": "ERP48_PURCHASE_ORDER",
    "table_name": "進貨單",
    "module": "PUR",
    "description": "採購進貨單，含表頭與明细行",
    "data_source": "ragic",
    "tab": "進貨單",
    "sheet_key": "erp/48",
    "s3_path": "s3://ragic/erp/48/",
    "primary_keys": ["1023120"],
    "partition_keys": [],
    "row_count_estimate": 10000,
    "status": "enabled",
    "version": 1,
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z",
    "updated_by": "system"
  }
]
```

#### 3.1.4 `da_field_info` JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "da_field_info",
  "type": "object",
  "required": [
    "_key",
    "table_id",
    "field_id",
    "field_name",
    "field_type",
    "nullable",
    "description",
    "is_pk",
    "is_fk",
    "status",
    "writable",
    "created_at",
    "updated_at"
  ],
  "properties": {
    "_key": { "type": "string", "minLength": 1 },
    "table_id": { "type": "string", "pattern": "^[A-Z0-9_]+$" },
    "field_id": { "type": "string", "pattern": "^[A-Z0-9_]+$" },
    "field_name": { "type": "string", "minLength": 1 },
    "field_type": {
      "type": "string",
      "enum": [
        "CHAR",
        "VARCHAR",
        "INT",
        "BIGINT",
        "DECIMAL",
        "DATE",
        "TIMESTAMP",
        "BOOLEAN"
      ]
    },
    "length": { "type": "integer", "minimum": 0 },
    "scale": { "type": "integer", "minimum": 0 },
    "nullable": { "type": "boolean" },
    "description": { "type": "string", "minLength": 1 },
    "business_aliases": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 },
      "minItems": 0
    },
    "is_pk": { "type": "boolean" },
    "is_fk": { "type": "boolean" },
    "relation_table": { "type": ["string", "null"] },
    "relation_field": { "type": ["string", "null"] },
    "status": { "type": "string", "enum": ["enabled", "disabled"] },
    "created_at": { "type": "string", "format": "date-time" },
    "updated_at": { "type": "string", "format": "date-time" },
    "writable": { "type": "boolean" },
    "is_subtable_field": { "type": "boolean" },
    "subtable_key": { "type": ["string", "null"] }
  },
  "additionalProperties": false
}
```

#### 3.1.5 `da_field_info` 範例（CFG7_EMPLOYEE、CFG9_ITEM）

```json
[
  {
    "_key": "CFG7_EMPLOYEE_1015428",
    "table_id": "CFG7_EMPLOYEE",
    "field_id": "1015428",
    "field_name": "員工編號",
    "field_type": "VARCHAR",
    "length": 50,
    "scale": 0,
    "nullable": false,
    "description": "員工編號",
    "business_aliases": ["員工", "員工號", "編號"],
    "is_pk": true,
    "is_fk": false,
    "relation_table": null,
    "relation_field": null,
    "writable": true,
    "is_subtable_field": false,
    "subtable_key": null,
    "status": "enabled",
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z"
  },
  {
    "_key": "CFG7_EMPLOYEE_1015429",
    "table_id": "CFG7_EMPLOYEE",
    "field_id": "1015429",
    "field_name": "員工姓名",
    "field_type": "VARCHAR",
    "length": 100,
    "scale": 0,
    "nullable": false,
    "description": "員工姓名",
    "business_aliases": ["姓名", "名字", "名稱"],
    "is_pk": false,
    "is_fk": false,
    "relation_table": null,
    "relation_field": null,
    "writable": true,
    "is_subtable_field": false,
    "subtable_key": null,
    "status": "enabled",
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z"
  },
  {
    "_key": "CFG7_EMPLOYEE_1015495",
    "table_id": "CFG7_EMPLOYEE",
    "field_id": "1015495",
    "field_name": "所屬部門編號",
    "field_type": "VARCHAR",
    "length": 50,
    "scale": 0,
    "nullable": true,
    "description": "所屬部門編號",
    "business_aliases": ["部門", "部門編號", "所屬部門"],
    "is_pk": false,
    "is_fk": true,
    "relation_table": "CFG2_DEPT",
    "relation_field": "1015308",
    "writable": true,
    "is_subtable_field": false,
    "subtable_key": null,
    "status": "enabled",
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z"
  },
  {
    "_key": "CFG9_ITEM_1015486",
    "table_id": "CFG9_ITEM",
    "field_id": "1015486",
    "field_name": "品項編碼",
    "field_type": "VARCHAR",
    "length": 50,
    "scale": 0,
    "nullable": false,
    "description": "品項唯一識別碼",
    "business_aliases": ["品項", "品號", "編碼", "物料編號"],
    "is_pk": true,
    "is_fk": false,
    "relation_table": null,
    "relation_field": null,
    "writable": true,
    "is_subtable_field": false,
    "subtable_key": null,
    "status": "enabled",
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z"
  },
  {
    "_key": "CFG9_ITEM_1015483",
    "table_id": "CFG9_ITEM",
    "field_id": "1015483",
    "field_name": "品項名稱",
    "field_type": "VARCHAR",
    "length": 200,
    "scale": 0,
    "nullable": false,
    "description": "品項名稱",
    "business_aliases": ["品名", "名稱", "品項名"],
    "is_pk": false,
    "is_fk": false,
    "relation_table": null,
    "relation_field": null,
    "writable": true,
    "is_subtable_field": false,
    "subtable_key": null,
    "status": "enabled",
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z"
  },
  {
    "_key": "ERP48_PO_1023120",
    "table_id": "ERP48_PURCHASE_ORDER",
    "field_id": "1023120",
    "field_name": "進貨單號",
    "field_type": "VARCHAR",
    "length": 50,
    "scale": 0,
    "nullable": false,
    "description": "進貨單唯一單號",
    "business_aliases": ["進貨單", "單號", "PO", "採購單"],
    "is_pk": true,
    "is_fk": false,
    "relation_table": null,
    "relation_field": null,
    "writable": true,
    "is_subtable_field": false,
    "subtable_key": null,
    "status": "enabled",
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z"
  },
  {
    "_key": "ERP48_PO_1023123",
    "table_id": "ERP48_PURCHASE_ORDER",
    "field_id": "1023123",
    "field_name": "日期",
    "field_type": "DATE",
    "length": 8,
    "scale": 0,
    "nullable": false,
    "description": "進貨日期",
    "business_aliases": ["日期", "進貨日期", "單據日期"],
    "is_pk": false,
    "is_fk": false,
    "relation_table": null,
    "relation_field": null,
    "writable": true,
    "is_subtable_field": false,
    "subtable_key": null,
    "status": "enabled",
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z"
  },
  {
    "_key": "ERP48_PO_1023122",
    "table_id": "ERP48_PURCHASE_ORDER",
    "field_id": "1023122",
    "field_name": "供應商名稱",
    "field_type": "VARCHAR",
    "length": 200,
    "scale": 0,
    "nullable": true,
    "description": "供應商名稱",
    "business_aliases": ["供應商", "廠商", "Vendor"],
    "is_pk": false,
    "is_fk": false,
    "relation_table": "CFG10_VENDOR",
    "relation_field": "1015577",
    "writable": true,
    "is_subtable_field": false,
    "subtable_key": null,
    "status": "enabled",
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z"
  }
]
```

#### 3.1.6 `da_table_relation` JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "da_table_relation",
  "type": "object",
  "required": [
    "_key",
    "relation_id",
    "left_table",
    "left_field",
    "right_table",
    "right_field",
    "join_type",
    "cardinality",
    "status",
    "created_at",
    "updated_at"
  ],
  "properties": {
    "_key": { "type": "string", "minLength": 1 },
    "relation_id": { "type": "string", "minLength": 1 },
    "left_table": { "type": "string", "pattern": "^[A-Z0-9_]+$" },
    "left_field": { "type": "string", "pattern": "^[A-Z0-9_]+$" },
    "right_table": { "type": "string", "pattern": "^[A-Z0-9_]+$" },
    "right_field": { "type": "string", "pattern": "^[A-Z0-9_]+$" },
    "join_type": { "type": "string", "enum": ["INNER", "LEFT"] },
    "cardinality": { "type": "string", "enum": ["1:1", "1:N", "N:1", "N:N"] },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "status": { "type": "string", "enum": ["enabled", "disabled"] },
    "created_at": { "type": "string", "format": "date-time" },
    "updated_at": { "type": "string", "format": "date-time" }
  },
  "additionalProperties": false
}
```

#### 3.1.7 `da_table_relation` 典型資料（Ragic Phase 1）

> SAP 關聯（原 EKKO↔EKPO 等）見附錄章節 A（歷史文件）。

```json
[
  {
    "_key": "REL_EMP_DEPT_1015495_1015308",
    "relation_id": "REL_EMP_DEPT",
    "left_table": "CFG7_EMPLOYEE",
    "left_field": "1015495",
    "right_table": "CFG2_DEPT",
    "right_field": "1015308",
    "join_type": "LEFT",
    "cardinality": "N:1",
    "confidence": 1.0,
    "status": "enabled",
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z"
  },
  {
    "_key": "REL_PO_VENDOR_1023122_1015577",
    "relation_id": "REL_PO_VENDOR",
    "left_table": "ERP48_PURCHASE_ORDER",
    "left_field": "1023122",
    "right_table": "CFG10_VENDOR",
    "right_field": "1015577",
    "join_type": "LEFT",
    "cardinality": "N:1",
    "confidence": 0.9,
    "status": "enabled",
    "created_at": "2026-04-02T00:00:00Z",
    "updated_at": "2026-04-02T00:00:00Z"
  }
]
```

#### 3.1.8 ArangoDB 索引策略

```aql
// da_table_info_sap
db.da_table_info_sap.ensureIndex({ type: "persistent", fields: ["table_id"], unique: true })
db.da_table_info_sap.ensureIndex({ type: "persistent", fields: ["module", "status"] })

// da_table_info_ragic
db.da_table_info_ragic.ensureIndex({ type: "persistent", fields: ["table_id"], unique: true })
db.da_table_info_ragic.ensureIndex({ type: "persistent", fields: ["module", "status"] })
db.da_table_info_ragic.ensureIndex({ type: "persistent", fields: ["sheet_key"], unique: true })

// da_field_info_sap
db.da_field_info_sap.ensureIndex({ type: "persistent", fields: ["table_id", "field_id"], unique: true })
db.da_field_info_sap.ensureIndex({ type: "persistent", fields: ["field_name"] })
db.da_field_info_sap.ensureIndex({ type: "persistent", fields: ["business_aliases[*]"], sparse: true })

// da_field_info_ragic
db.da_field_info_ragic.ensureIndex({ type: "persistent", fields: ["table_id", "field_id"], unique: true })
db.da_field_info_ragic.ensureIndex({ type: "persistent", fields: ["field_name"] })
db.da_field_info_ragic.ensureIndex({ type: "persistent", fields: ["business_aliases[*]"], sparse: true })

// da_table_relation_sap
db.da_table_relation_sap.ensureIndex({ type: "persistent", fields: ["left_table", "right_table"] })
db.da_table_relation_sap.ensureIndex({ type: "persistent", fields: ["left_table", "left_field", "right_table", "right_field"], unique: true })

// da_table_relation_ragic
db.da_table_relation_ragic.ensureIndex({ type: "persistent", fields: ["left_table", "right_table"] })
db.da_table_relation_ragic.ensureIndex({ type: "persistent", fields: ["left_table", "left_field", "right_table", "right_field"], unique: true })
```

#### 3.1.9 AQL 查詢範例

```aql
// 查詢指定模組啟用中的資料表（SAP）
FOR t IN da_table_info_sap
  FILTER t.module == @module
  FILTER t.status == "enabled"
  SORT t.table_id ASC
  RETURN t
```

```aql
// 依使用者詞彙查欄位（別名含「金額」）
FOR f IN da_field_info_sap
  FILTER @keyword IN f.business_aliases OR CONTAINS(f.description, @keyword)
  FILTER f.status == "enabled"
  RETURN {
    table_id: f.table_id,
    field_id: f.field_id,
    description: f.description
  }
```

```aql
// 檢查兩表是否存在可用關聯
FOR r IN da_table_relation_sap
  FILTER r.left_table == @left_table
  FILTER r.right_table == @right_table
  FILTER r.status == "enabled"
  RETURN r
```

```aql
// 撈出 table + fields 一次回傳（給 SQL 生成 prompt）
LET table_doc = FIRST(
  FOR t IN da_table_info
    FILTER t.table_id == @table_id
    RETURN t
)
LET field_docs = (
  FOR f IN da_field_info
    FILTER f.table_id == @table_id
    FILTER f.status == "enabled"
    SORT f.field_id ASC
    RETURN KEEP(f, "field_id", "field_type", "description", "is_pk", "is_fk", "relation_table", "relation_field")
)
RETURN {
  table: table_doc,
  fields: field_docs
}
```

// 查詢 Ragic Phase 1 所有資料表（sheets）
FOR t IN da_table_info_ragic
  FILTER t.status == "enabled"
  SORT t.table_id ASC
  RETURN {
    table_id: t.table_id,
    table_name: t.table_name,
    sheet_key: t.sheet_key,
    tab: t.tab,
    s3_path: t.s3_path
  }
```

### 3.2 意圖識別模組（Intent Recognition）

#### 3.2.1 模組責任

輸入自然語言查詢，輸出標準化 intent JSON，包含：

- 查詢類型（aggregate/filter/join/time_series/ranking/comparison）
- 信心分數（0.0 ~ 1.0）
- 具體實體（表、欄位、聚合、條件、排序、限制）

#### 3.2.2 Intent JSON 結構（完整）

```json
{
  "intent_type": "aggregate",
  "confidence": 0.92,
  "entities": {
    "tables": ["EKKO", "EKPO"],
    "columns": ["EBELN", "NETPR", "AEDAT", "LIFNR"],
    "aggregations": [
      {
        "function": "SUM",
        "column": "NETPR"
      }
    ],
    "filters": [
      {
        "column": "AEDAT",
        "operator": ">=",
        "value": "2026-03-01"
      },
      {
        "column": "AEDAT",
        "operator": "<=",
        "value": "2026-03-31"
      }
    ],
    "group_by": ["LIFNR"],
    "time_range": {
      "start": "2026-03-01",
      "end": "2026-03-31",
      "granularity": "month"
    },
    "joins": [
      {
        "left_table": "EKKO",
        "right_table": "EKPO",
        "on": "EBELN"
      }
    ],
    "order_by": [
      {
        "column": "NETPR",
        "direction": "DESC"
      }
    ],
    "limit": 10
  }
}
```

#### 3.2.3 意圖分類表

| Intent Type | Example Query | Description |
|-------------|---------------|-------------|
| aggregate | 上個月採購總金額 | Aggregation functions |
| filter | 查詢供應商A的訂單 | Conditional filtering |
| join | 訂單和行項目的明細 | Multi-table joins |
| time_series | 按月統計銷售趨勢 | Time-based analysis |
| ranking | 金額最高的前10筆訂單 | Top-N queries |
| comparison | 比較兩個供應商的價格 | Comparative analysis |

#### 3.2.4 信心門檻

- `confidence >= 0.7`：進入 Schema Binding。
- `confidence < 0.7`：回傳需澄清錯誤（`DA_INTENT_PARSE_ERROR`），由 BPA/前端要求使用者補充。

#### 3.2.5 Python 實作範例（FastAPI service layer）

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import json
import httpx


IntentType = Literal["aggregate", "filter", "join", "time_series", "ranking", "comparison"]


@dataclass(frozen=True)
class IntentExtractionConfig:
    ollama_base_url: str
    model_name: str
    timeout_seconds: float = 15.0


def build_intent_prompt(query: str) -> str:
    return (
        "你是 DA 意圖解析器。只輸出合法 JSON，不可包含說明文字。\n"
        "JSON 必須包含 intent_type, confidence, entities。\n"
        "intent_type 只可為 aggregate|filter|join|time_series|ranking|comparison。\n"
        "confidence 為 0~1。\n"
        "entities 需包含 tables, columns, aggregations, filters, group_by, time_range, joins, order_by, limit。\n"
        f"使用者查詢：{query}\n"
    )


async def extract_intent(query: str, cfg: IntentExtractionConfig) -> dict[str, object]:
    prompt = build_intent_prompt(query)
    payload = {
        "model": cfg.model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "top_p": 0.9,
        },
    }

    async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
        response = await client.post(f"{cfg.ollama_base_url}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()

    raw_text = data.get("response", "")
    parsed = json.loads(raw_text)

    confidence = float(parsed.get("confidence", 0.0))
    if confidence < 0.7:
        raise ValueError("DA_INTENT_PARSE_ERROR: confidence below threshold 0.7")

    return parsed
```

#### 3.2.6 輸出驗證規則

1. `intent_type` 必須在 enum 中。
2. `entities.tables` 不可為空（最少 1 表）。
3. ranking 類型必須有 `order_by` + `limit`。
4. time_series 類型必須有 `time_range.granularity`。
5. 所有 filters 必須有 `column/operator/value`。

### 3.3 Schema Binding（意圖與 Schema 綁定）

#### 3.3.1 目標

將 3.2 解析出的語意實體映射到 `da_table_info/da_field_info/da_table_relation`，輸出可產生 SQL 的結構化 binding。

#### 3.3.2 驗證步驟

1. **表名解析**：將 `EKKO` 映射到 `MM_EKKO`（支援 fuzzy）。
2. **欄位檢查**：欄位必須存在於指定表。
3. **關聯驗證**：多表查詢必須在 `da_table_relation` 找到 join path。
4. **型別兼容**：日期欄位不能用字串比較；數值欄位不能套用 LIKE。

#### 3.3.3 Binding 結果結構

```json
{
  "binding_id": "bind_20260322_000001",
  "resolved_tables": [
    {
      "table_alias": "t1",
      "table_id": "MM_EKKO",
      "table_name": "EKKO",
      "s3_path": "s3://sap/mm/ekko/"
    },
    {
      "table_alias": "t2",
      "table_id": "MM_EKPO",
      "table_name": "EKPO",
      "s3_path": "s3://sap/mm/ekpo/"
    }
  ],
  "resolved_fields": [
    {
      "table_alias": "t1",
      "field_id": "EBELN",
      "field_type": "VARCHAR"
    },
    {
      "table_alias": "t2",
      "field_id": "NETPR",
      "field_type": "DECIMAL"
    }
  ],
  "resolved_joins": [
    {
      "left_alias": "t1",
      "left_field": "EBELN",
      "right_alias": "t2",
      "right_field": "EBELN",
      "join_type": "INNER"
    }
  ],
  "filters": [
    {
      "table_alias": "t1",
      "field_id": "AEDAT",
      "operator": ">=",
      "value": "2026-03-01",
      "value_type": "DATE"
    }
  ],
  "errors": [],
  "is_valid": true
}
```

#### 3.3.4 無法綁定錯誤範例

```json
{
  "binding_id": "bind_20260322_000002",
  "resolved_tables": [],
  "resolved_fields": [],
  "resolved_joins": [],
  "filters": [],
  "errors": [
    {
      "code": "DA_SCHEMA_BINDING_FAILED",
      "message": "欄位 PRICE 不存在於 MM_EKKO",
      "details": {
        "suggestions": ["NETPR", "BRTWR"]
      }
    }
  ],
  "is_valid": false
}
```

#### 3.3.5 Python 綁定範例

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BindingError:
    code: str
    message: str
    details: dict[str, Any]


def validate_filter_compatibility(field_type: str, operator: str, value: object) -> bool:
    if field_type in {"INT", "BIGINT", "DECIMAL"} and operator in {"LIKE", "ILIKE"}:
        return False
    if field_type == "DATE" and not isinstance(value, str):
        return False
    return True


def resolve_table_name(raw_name: str, table_candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    normalized = raw_name.strip().upper()
    exact = [t for t in table_candidates if t["table_name"].upper() == normalized or t["table_id"].upper().endswith(normalized)]
    if exact:
        return exact[0]
    fuzzy = [t for t in table_candidates if normalized in t["table_id"].upper() or normalized in t["table_name"].upper()]
    return fuzzy[0] if fuzzy else None
```

#### 3.3.6 綁定決策表

| 情境 | 處理方式 | 回傳 |
|------|----------|------|
| 表不存在 | 嘗試 fuzzy + alias | 失敗則 `DA_SCHEMA_NOT_FOUND` |
| 欄位不存在 | 嘗試同義詞映射 | 失敗則 `DA_SCHEMA_BINDING_FAILED` |
| join path 缺失 | 嘗試 graph 搜索 1-hop/2-hop | 失敗則 `DA_SCHEMA_BINDING_FAILED` |
| 型別不匹配 | 嘗試型別轉換建議 | 失敗則 `DA_SCHEMA_BINDING_FAILED` |

### 3.4 Intent 向量匹配（Qdrant）

#### 3.4.1 Collection 定義

- Collection: `da_intent_cache`
- Vector size: `1024`
- Distance: `Cosine`
- payload 欄位：`intent_signature`, `sql_template`, `created_at`, `hit_count`, `version`

#### 3.4.2 Intent canonicalization 規範

canonical signature 必須移除語句噪音，保留查詢語義骨架：

1. 將中文別名轉成標準 table/field id。
2. 日期區間標準化（`$DATE_START`, `$DATE_END`）。
3. 數值門檻標準化（`$NUM_1`, `$NUM_2`）。
4. 排序與限制標準化（`ORDER_BY:NETPR:DESC LIMIT:10`）。

範例：

`「上個月供應商 A 的採購總金額」`

→ `INTENT=aggregate|TABLES=MM_EKKO,MM_EKPO|AGG=SUM(NETPR)|FILTER=LIFNR:$VENDOR;AEDAT:$DATE_START~$DATE_END|GROUP_BY=LIFNR`

#### 3.4.3 Qdrant 建立程式碼

```python
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance


def ensure_qdrant_collection(client: QdrantClient) -> None:
    exists = client.collection_exists("da_intent_cache")
    if not exists:
        client.create_collection(
            collection_name="da_intent_cache",
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
```

#### 3.4.4 Embedding 生成程式碼

```python
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self._model = SentenceTransformer(model_name)

    def encode_signature(self, signature: str) -> list[float]:
        vector = self._model.encode(signature)
        return [float(x) for x in vector.tolist()]
```

#### 3.4.5 Upsert / Query 程式碼

```python
from datetime import datetime, timezone
from qdrant_client.models import PointStruct


def upsert_intent_template(
    client: QdrantClient,
    point_id: int,
    vector: list[float],
    intent_signature: str,
    sql_template: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    client.upsert(
        collection_name="da_intent_cache",
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "intent_signature": intent_signature,
                    "sql_template": sql_template,
                    "created_at": now,
                    "hit_count": 0,
                    "version": 1,
                },
            )
        ],
    )


def search_intent_template(client: QdrantClient, query_vector: list[float]) -> tuple[bool, dict[str, object] | None]:
    result = client.query_points(
        collection_name="da_intent_cache",
        query=query_vector,
        limit=1,
        score_threshold=0.85,
    )
    if not result.points:
        return False, None
    point = result.points[0]
    return True, {
        "score": point.score,
        "payload": point.payload,
    }
```

#### 3.4.6 Cache hit / miss 流程圖

```text
┌──────────────────────────┐
│ canonical intent signature│
└──────────────┬───────────┘
               ▼
       ┌─────────────────┐
       │ BGE-M3 embedding│
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │ Qdrant similarity│
       └────────┬────────┘
                ▼
      score >= 0.85 ?
         ┌──────┴──────┐
         │             │
        YES           NO
         │             │
         ▼             ▼
┌────────────────┐ ┌──────────────────────┐
│ reuse SQL      │ │ LLM generate SQL     │
│ template path  │ │ fallback path        │
└────────────────┘ └──────────┬───────────┘
                              ▼
                    upsert new template/vector
```

### 3.5 SQL 生成模組

#### 3.5.1 兩條路徑

1. **Template Reuse Path（命中快取）**
   - 載入 SQL template
   - 替換參數（日期、供應商、limit）
   - 進入 SQL 驗證

2. **LLM Fallback Path（未命中快取）**
   - 帶入 Schema context + Binding 結果
   - 產生 DuckDB SQL
   - 驗證通過後寫入 template / vector cache

#### 3.5.2 DuckDB SQL 方言重點

```sql
SELECT
  t1.LIFNR,
  SUM(t2.NETPR) AS total_amount
FROM read_parquet('s3://sap/mm/ekko/*.parquet') AS t1
JOIN read_parquet('s3://sap/mm/ekpo/*.parquet') AS t2
  ON t1.EBELN = t2.EBELN
WHERE t1.AEDAT >= ?
  AND t1.AEDAT <= ?
GROUP BY t1.LIFNR
ORDER BY total_amount DESC
LIMIT ?;
```

> 安全規則：使用者值只能透過 `?` 參數傳入，禁止字串拼接。

#### 3.5.3 SQL 驗證策略

驗證項目：

1. 只允許 `SELECT`。
2. 不允許 `INSERT/UPDATE/DELETE/MERGE/DROP/ALTER/CREATE/COPY`。
3. 不允許多語句（`;` 只能出現在末尾一次）。
4. 不允許讀取非白名單路徑。
5. `LIMIT` 不能超過 10000。

#### 3.5.4 SQL AST 驗證程式碼（Python）

```python
import re


FORBIDDEN_TOKENS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "ATTACH",
    "DETACH",
    "COPY",
}


def validate_sql(sql: str) -> None:
    normalized = re.sub(r"\s+", " ", sql.strip()).upper()
    if not normalized.startswith("SELECT "):
        raise ValueError("DA_SQL_VALIDATION_FAILED: only SELECT allowed")

    for token in FORBIDDEN_TOKENS:
        if re.search(rf"\b{token}\b", normalized):
            raise ValueError(f"DA_SQL_VALIDATION_FAILED: forbidden token {token}")

    if normalized.count(";") > 1:
        raise ValueError("DA_SQL_VALIDATION_FAILED: multiple statements detected")

    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", normalized)
    if limit_match and int(limit_match.group(1)) > 10000:
        raise ValueError("DA_SQL_VALIDATION_FAILED: LIMIT > 10000")
```

#### 3.5.5 SQL template in ArangoDB（`da_sql_templates`）

```json
{
  "_key": "tpl_mm_aggregate_po_amount_v1",
  "template_id": "tpl_mm_aggregate_po_amount_v1",
  "intent_signature": "INTENT=aggregate|TABLES=MM_EKKO,MM_EKPO|AGG=SUM(NETPR)|FILTER=LIFNR:$VENDOR;AEDAT:$DATE_START~$DATE_END|GROUP_BY=LIFNR",
  "sql_template": "SELECT t1.LIFNR, SUM(t2.NETPR) AS total_amount FROM read_parquet('s3://sap/mm/ekko/*.parquet') AS t1 JOIN read_parquet('s3://sap/mm/ekpo/*.parquet') AS t2 ON t1.EBELN = t2.EBELN WHERE t1.LIFNR = ? AND t1.AEDAT >= ? AND t1.AEDAT <= ? GROUP BY t1.LIFNR ORDER BY total_amount DESC LIMIT ?",
  "params_schema": {
    "type": "object",
    "required": ["vendor", "date_start", "date_end", "limit"],
    "properties": {
      "vendor": { "type": "string", "minLength": 1 },
      "date_start": { "type": "string", "format": "date" },
      "date_end": { "type": "string", "format": "date" },
      "limit": { "type": "integer", "minimum": 1, "maximum": 10000 }
    },
    "additionalProperties": false
  },
  "version": 1,
  "status": "enabled",
  "created_at": "2026-03-22T00:00:00Z",
  "updated_at": "2026-03-22T00:00:00Z"
}
```

#### 3.5.6 LLM fallback prompt 規範

```text
你是 Data Agent SQL 生成器。
輸入：Schema binding JSON + query intent。
輸出：僅 DuckDB SELECT SQL，且必須使用 ? 參數。
限制：
1) 只可使用 read_parquet('s3://...')。
2) 不可使用 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE。
3) 需含 LIMIT，且 <= 10000。
4) 欄位與表名必須來自 binding 結果。
```

#### 3.5.7 參數替換範例

```python
from collections.abc import Mapping


def build_parameter_values(params: Mapping[str, object]) -> list[object]:
    values: list[object] = []
    values.append(params["vendor"])
    values.append(params["date_start"])
    values.append(params["date_end"])
    values.append(int(params["limit"]))
    return values
```

### 3.6 查詢執行模組（DuckDB + SeaWeedFS S3）

#### 3.6.1 連線管理

原則：每個請求建立獨立 DuckDB in-memory 連線，請求完成即釋放。

優點：

- 無狀態、隔離性高。
- 避免長連線污染（暫存設定殘留）。
- 易於並行擴展與故障隔離。

#### 3.6.2 S3 Secret 設定

```python
def configure_s3_secret(
    conn: duckdb.DuckDBPyConnection,
    access_key: str,
    secret_key: str,
    seaweedfs_endpoint: str,
) -> None:
    conn.execute("INSTALL httpfs")
    conn.execute("LOAD httpfs")
    conn.execute(
        f"""
        CREATE OR REPLACE SECRET s3_secret (
            TYPE S3,
            PROVIDER config,
            KEY_ID '{access_key}',
            SECRET '{secret_key}',
            ENDPOINT '{seaweedfs_endpoint}',
            USE_SSL false,
            URL_STYLE path
        )
        """
    )
```

#### 3.6.3 查詢執行程式碼

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import duckdb
import time


@dataclass(frozen=True)
class QueryExecutionResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    duration_ms: int
    row_count: int


def execute_duckdb_query(sql: str, params: list[object]) -> QueryExecutionResult:
    start = time.perf_counter()
    conn = duckdb.connect(":memory:")
    try:
        cursor = conn.execute(sql, params)
        columns = [col[0] for col in cursor.description]
        raw_rows = cursor.fetchall()

        limited_rows = raw_rows[:10000]
        rows: list[dict[str, Any]] = [
            {columns[idx]: value for idx, value in enumerate(row)}
            for row in limited_rows
        ]

        duration_ms = int((time.perf_counter() - start) * 1000)
        return QueryExecutionResult(
            columns=columns,
            rows=rows,
            duration_ms=duration_ms,
            row_count=len(rows),
        )
    finally:
        conn.close()
```

#### 3.6.4 Timeout 與行數限制

- 查詢 timeout：30 秒（超過即 `DA_QUERY_TIMEOUT`）
- 回傳 row 上限：10000
- 若超量，metadata 中需標記 `truncated: true`

#### 3.6.5 效能最佳化

1. Hive 分區：`s3://bucket/table/partition_key=.../*.parquet`
2. Predicate pushdown：時間、主鍵篩選先下推。
3. 避免 SELECT *：只投影必要欄位。
4. 預設 limit：若無指定，使用 200。
5. 大表 join 先過濾再連接。

---

## §4 資料流程（Complete Pipeline）

### 4.1 端到端流程圖

```text
User NL Query
  → Dynamic Routing (Prefix: sap_ or rgc_)
  → §3.2 Intent Recognition (LLM)
  → §3.3 Schema Binding (ArangoDB lookup via {data_source} suffix)
  → §3.4 Vector Match (Qdrant)
  → [Cache Hit?]
    → YES: §3.5a Template Reuse
    → NO:  §3.5b LLM SQL Generation
  → §3.6 DuckDB Execution (read_parquet from s3://{data_source}/...)
  → Result Formatting
  → Response to Caller (inc. data_source metadata)
```

### 4.2 詳細步驟與時間預期

| 步驟 | 說明 | 目標耗時 |
|------|------|----------|
| Step 1 | 輸入清理、權限上下文載入 | < 50ms |
| Step 2 | 意圖識別（LLM） | < 1.5s |
| Step 3 | Schema Binding | < 200ms |
| Step 4 | Qdrant 向量匹配 | < 100ms |
| Step 5A | Template SQL 組裝 | < 50ms |
| Step 5B | LLM SQL 生成（fallback） | < 3s |
| Step 6 | SQL 驗證 | < 50ms |
| Step 7 | DuckDB 執行 | < 5s |
| Step 8 | 結果格式化 | < 100ms |
| End-to-End | 總時間 | < 8s |

### 4.3 BPA → DA 時序圖

```text
BPA(:8005)         unified_agents(:8011/da/*)   ArangoDB(:8529)      Qdrant(:6333)       Ollama(:11434)      DuckDB/S3
    |                  |                    |                   |                    |                 |
    | POST /query      |                    |                   |                    |                 |
    |----------------->|                    |                   |                    |                 |
    |                  | extract intent     |                   |                    |                 |
    |                  |---------------------------------------->|(if embedding req) |                 |
    |                  |----------------------------------------------->| LLM parse      |                 |
    |                  |<-----------------------------------------------| intent JSON    |                 |
    |                  | schema lookup      |                   |                    |                 |
    |                  |------------------->|                   |                    |                 |
    |                  |<-------------------| table/field/meta  |                    |                 |
    |                  | vector search      |                   |                    |                 |
    |                  |--------------------------------------->|                    |                 |
    |                  |<---------------------------------------| hit/miss           |                 |
    |                  | if miss SQL gen    |                   |------------------->| SQL text         |
    |                  |<------------------------------------------------------------|                 |
    |                  | execute SQL        |                   |                    |---------------->|
    |                  |<--------------------------------------------------------------------------------|
    |                  | format response    |                   |                    |                 |
    |<-----------------|                    |                   |                    |                 |
```

### 4.4 Pipeline metadata

回傳 metadata 範例：

```json
{
  "pipeline": {
    "intent_ms": 980,
    "binding_ms": 120,
    "vector_ms": 42,
    "sql_gen_ms": 18,
    "sql_validate_ms": 6,
    "execute_ms": 1650,
    "format_ms": 20,
    "total_ms": 2836
  },
  "cache_hit": true,
  "trace_id": "trc_20260322_abcd1234"
}
```

---

## §5 通信協議（Integration with Top Orchestrator v2.0）

> 關鍵：DA 與 Top Orchestrator 交互必須符合 Handoff Protocol `schema_version: "2.0"`。

### 5.1 DA API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/query` | POST | Execute natural language query |
| `/query/sql` | POST | Execute raw SQL (admin only) |
| `/schema/sync` | POST | Trigger schema sync from S3 |
| `/schema/tables` | GET | List all table schemas |
| `/schema/tables/{table_id}` | GET | Get table schema detail |
| `/schema/tables/{table_id}` | PUT | Update table schema |
| `/intents` | GET | List intent records |
| `/intents/{intent_id}` | GET | Get intent detail |
| `/intents/search` | POST | Search similar intents |
| `/health` | GET | Health check |

### 5.2 Request/Response 格式

#### 5.2.1 Query Request

```json
{
  "query": "上個月各供應商採購總金額前10名",
  "session_id": "ses_abc123",
  "user_id": "u_0001",
  "options": {
    "timezone": "Asia/Taipei",
    "limit": 10,
    "module_scope": ["MM"],
    "return_debug": true
  }
}
```

#### 5.2.2 Query Response

```json
{
  "code": 0,
  "data": {
    "sql": "SELECT t1.LIFNR, SUM(t2.NETPR) AS total_amount FROM ... LIMIT ?",
    "results": [
      { "LIFNR": "V001", "total_amount": 1582000.75 },
      { "LIFNR": "V002", "total_amount": 1210040.10 }
    ],
    "metadata": {
      "duration_ms": 2836,
      "row_count": 10,
      "truncated": false,
      "trace_id": "trc_20260322_abcd1234"
    }
  },
  "intent": {
    "intent_type": "ranking",
    "confidence": 0.91
  },
  "cache_hit": true
}
```

#### 5.2.3 Error Response

```json
{
  "code": "DA_SCHEMA_BINDING_FAILED",
  "message": "無法將欄位『單價含稅』綁定到可用 Schema",
  "details": {
    "suggestions": ["NETPR", "BRTWR"],
    "trace_id": "trc_20260322_efgh5678"
  }
}
```

### 5.3 BPA → DA 通訊規範

1. BPA 應透過 `POST http://unified-agents:8011/da/query` 或 Rust Gateway 對應 `/api/v1/da/query` 呼叫 DA。
2. Authorization：沿用使用者 JWT，header `Authorization: Bearer <token>`。
3. 傳遞 headers：
   - `X-Trace-Id`
   - `X-Session-Id`
   - `X-Handoff-Schema-Version: 2.0`
4. DA 接收後驗證 `schema_version=2.0`，不匹配則回 400。
5. Query timeout：30 秒。

### 5.4 Top Orchestrator v2.0 Handoff 封包範例

```json
{
  "schema_version": "2.0",
  "handoff_id": "hof_20260322_001",
  "source_agent": "top_orchestrator",
  "target_agent": "data_agent",
  "context": {
    "session_id": "ses_abc123",
    "user_id": "u_0001",
    "user_roles": ["procurement_analyst"],
    "locale": "zh-TW"
  },
  "payload": {
    "query": "統計近三個月各供應商採購金額",
    "options": {
      "module_scope": ["MM"],
      "limit": 50,
      "return_debug": false
    }
  },
  "trace": {
    "trace_id": "trc_20260322_abcd1234",
    "parent_span_id": "spn_001"
  },
  "timestamp": "2026-03-22T12:09:59Z"
}
```

---

## §6 持久化設計（ArangoDB + Qdrant）

### 6.1 ArangoDB Collections

DA v2.0 使用以下 collections（名稱尾碼 `{data_source}` 為動態，如 `_sap` 或 `_ragic`）：

1. `da_table_info_{data_source}` — table metadata
2. `da_field_info_{data_source}` — field metadata
3. `da_table_relation_{data_source}` — table relationships
4. `da_intent_records` — intent history (global)
5. `da_sql_templates` — reusable SQL templates (global)
6. `da_intent_cache` (Qdrant) — vector cache (global)

#### 6.1.1 `da_intent_records` JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "da_intent_records",
  "type": "object",
  "required": [
    "_key",
    "intent_id",
    "session_id",
    "user_id",
    "original_query",
    "intent_json",
    "intent_signature",
    "sql_generated",
    "cache_hit",
    "result_summary",
    "duration_ms",
    "created_at"
  ],
  "properties": {
    "_key": { "type": "string", "minLength": 1 },
    "intent_id": { "type": "string", "minLength": 1 },
    "session_id": { "type": "string", "minLength": 1 },
    "user_id": { "type": "string", "minLength": 1 },
    "original_query": { "type": "string", "minLength": 1 },
    "intent_json": { "type": "object" },
    "intent_signature": { "type": "string", "minLength": 1 },
    "sql_generated": { "type": "string", "minLength": 1 },
    "cache_hit": { "type": "boolean" },
    "result_summary": {
      "type": "object",
      "required": ["row_count", "truncated"],
      "properties": {
        "row_count": { "type": "integer", "minimum": 0 },
        "truncated": { "type": "boolean" },
        "sample": {
          "type": "array",
          "items": { "type": "object" }
        }
      },
      "additionalProperties": false
    },
    "duration_ms": { "type": "integer", "minimum": 0 },
    "error_code": { "type": ["string", "null"] },
    "trace_id": { "type": "string", "minLength": 1 },
    "created_at": { "type": "string", "format": "date-time" }
  },
  "additionalProperties": false
}
```

#### 6.1.2 `da_sql_templates` JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "da_sql_templates",
  "type": "object",
  "required": [
    "_key",
    "template_id",
    "intent_signature",
    "sql_template",
    "params_schema",
    "version",
    "status",
    "created_at",
    "updated_at"
  ],
  "properties": {
    "_key": { "type": "string", "minLength": 1 },
    "template_id": { "type": "string", "minLength": 1 },
    "intent_signature": { "type": "string", "minLength": 1 },
    "sql_template": { "type": "string", "minLength": 1 },
    "params_schema": { "type": "object" },
    "version": { "type": "integer", "minimum": 1 },
    "status": { "type": "string", "enum": ["enabled", "disabled", "deprecated"] },
    "approved_by": { "type": ["string", "null"] },
    "created_at": { "type": "string", "format": "date-time" },
    "updated_at": { "type": "string", "format": "date-time" }
  },
  "additionalProperties": false
}
```

#### 6.1.3 ArangoDB 索引建議（持久化）

```aql
db.da_intent_records.ensureIndex({ type: "persistent", fields: ["created_at"] })
db.da_intent_records.ensureIndex({ type: "persistent", fields: ["intent_signature"] })
db.da_intent_records.ensureIndex({ type: "persistent", fields: ["user_id", "created_at"] })
db.da_sql_templates.ensureIndex({ type: "persistent", fields: ["intent_signature"], unique: true })
db.da_sql_templates.ensureIndex({ type: "persistent", fields: ["status", "updated_at"] })
```

### 6.2 Qdrant Collection

#### 6.2.1 向量配置

- Collection: `da_intent_cache`
- `size=1024`
- `distance=Cosine`

#### 6.2.2 Payload 結構

```json
{
  "intent_signature": "INTENT=aggregate|TABLES=MM_EKKO,MM_EKPO|AGG=SUM(NETPR)|FILTER=...",
  "sql_template": "SELECT ...",
  "created_at": "2026-03-22T00:00:00Z",
  "hit_count": 125,
  "template_id": "tpl_mm_aggregate_po_amount_v1",
  "version": 1,
  "status": "enabled"
}
```

#### 6.2.3 Qdrant 索引配置建議

```python
client.update_collection(
    collection_name="da_intent_cache",
    optimizer_config={
        "default_segment_number": 4,
        "indexing_threshold": 20000,
        "memmap_threshold": 50000,
    },
)
```

### 6.3 Data Lifecycle

#### 6.3.1 生命週期規則

1. `da_intent_records`：保留 90 天，逾期歸檔。
2. `da_sql_templates`：長期保存，版本化控管。
3. `da_intent_cache`：與模板同步，歸檔時同步 prune。

#### 6.3.2 歸檔 AQL 範例

```aql
LET cutoff = DATE_SUBTRACT(DATE_NOW(), 90, "days")
FOR d IN da_intent_records
  FILTER DATE_TIMESTAMP(d.created_at) < cutoff
  INSERT d INTO da_intent_records_archive
  REMOVE d IN da_intent_records
```

#### 6.3.3 Qdrant prune 範例

```python
def prune_qdrant_vectors(client: QdrantClient, valid_signatures: set[str]) -> None:
    points, _ = client.scroll(collection_name="da_intent_cache", limit=10000, with_payload=True, with_vectors=False)
    delete_ids: list[int] = []
    for p in points:
        payload = p.payload or {}
        signature = str(payload.get("intent_signature", ""))
        if signature not in valid_signatures:
            delete_ids.append(int(p.id))
    if delete_ids:
        client.delete(collection_name="da_intent_cache", points_selector=delete_ids)
```

---

## §7 安全設計

### 7.1 SQL Injection 防護

強制規則：

1. 所有 user input 只能透過 `?` placeholders。
2. 禁止把 user value 直接拼接進 SQL 字串。
3. SQL 執行前先做 validation。

錯誤示例（禁止）：

```python
# 禁止：字串拼接
sql = f"SELECT * FROM read_parquet('s3://sap/mm/ekko/*.parquet') WHERE LIFNR = '{vendor}'"
```

正確示例：

```python
sql = "SELECT * FROM read_parquet('s3://sap/mm/ekko/*.parquet') WHERE LIFNR = ?"
params = [vendor]
```

### 7.2 只讀策略

DA 僅允許 `SELECT` 查詢；以下全部封鎖：

- INSERT
- UPDATE
- DELETE
- MERGE
- DROP
- ALTER
- CREATE
- TRUNCATE
- COPY

### 7.3 查詢複雜度限制

| 限制項 | 閾值 |
|--------|------|
| 最大 JOIN 數 | 4 |
| 最大子查詢層數 | 2 |
| 最大回傳列數 | 10000 |
| 最大欄位投影數 | 120 |
| 執行 timeout | 30 秒 |

### 7.4 S3 權限控制

1. SeaWeedFS 憑證採唯讀金鑰。
2. 僅允許 `s3://sap/` 與 `s3://ragic/` 前綴讀取。
3. 禁止列舉非白名單 bucket。
4. 密鑰不寫死，改由環境變數注入。

### 7.5 權限模型

權限檢查維度：

1. 使用者角色（role）對資料源模組權限：
   - SAP: MM, SD, FI, PP, QM
   - Ragic: BASE, PUR, ADMIN, HR, INV
2. 資料域（data domain）限制（如銷售區域、公司代碼、部門編號）。

授權上下文範例：

```json
{
  "user_id": "u_0001",
  "roles": ["procurement_analyst"],
  "allowed_modules": ["MM"],
  "data_filters": {
    "BUKRS": ["1000", "2000"],
    "VKORG": []
  }
}
```

### 7.6 審計日誌

每次查詢至少記錄：

- `trace_id`
- `user_id`
- `original_query`
- `intent_signature`
- `generated_sql`
- `params`（敏感值可遮罩）
- `duration_ms`
- `row_count`
- `error_code`（若有）

---

## §8 錯誤處理

### 8.1 錯誤碼表

| Error Code | Description | Retryable |
|------------|-------------|-----------|
| DA_INTENT_PARSE_ERROR | Failed to parse intent | No |
| DA_SCHEMA_NOT_FOUND | Table/field not in schema | No |
| DA_SCHEMA_BINDING_FAILED | Cannot bind intent to schema | No |
| DA_SQL_GENERATION_FAILED | LLM failed to generate valid SQL | Yes (retry with different prompt) |
| DA_SQL_VALIDATION_FAILED | Generated SQL failed validation | No |
| DA_QUERY_TIMEOUT | DuckDB query exceeded 30s | No |
| DA_S3_CONNECTION_ERROR | Cannot connect to SeaWeedFS | Yes |
| DA_QDRANT_ERROR | Qdrant service unavailable | Yes (graceful degradation) |
| DA_LLM_ERROR | Ollama/LLM service error | Yes |

### 8.2 Graceful Degradation

若 Qdrant 不可用：

1. 記錄 `DA_QDRANT_ERROR`。
2. 跳過向量匹配流程。
3. 直接走 LLM fallback。
4. 主流程不失敗（除非 LLM/SQL 執行也失敗）。

### 8.3 重試策略

採 Exponential Backoff：

- 第 1 次重試：200ms
- 第 2 次重試：500ms
- 第 3 次重試：1200ms
- 最多重試 3 次（僅對 Retryable error）

### 8.4 Python 重試範例

```python
import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar


T = TypeVar("T")


async def retry_with_backoff(func: Callable[[], Awaitable[T]], retryable: bool) -> T:
    if not retryable:
        return await func()

    delays = [0.2, 0.5, 1.2]
    last_error: Exception | None = None
    for delay in delays:
        try:
            return await func()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            await asyncio.sleep(delay)

    if last_error is None:
        raise RuntimeError("Unexpected retry state")
    raise last_error
```

### 8.5 錯誤回應標準

```json
{
  "code": "DA_SQL_GENERATION_FAILED",
  "message": "LLM 無法在限定重試次數內產生合法 SQL",
  "details": {
    "retry_count": 3,
    "trace_id": "trc_20260322_xyz987"
  }
}
```

---

## §9 前端維護畫面

> 本章定義 4 個新維護頁面，遵循 React 18 + TypeScript + Ant Design 6.x + React Router。

新路由群組（`src/App.tsx`）：

```text
/app/data-agent/schema     → Table Schema Management
/app/data-agent/intents    → Intent Management
/app/data-agent/sync       → Sync Status Monitor
/app/data-agent/playground → Query Playground
```

### 9.1 Table Schema 管理頁面（`/app/data-agent/schema`）

#### 9.1.1 UI 版面

- 頁首：`Data Agent Schema 管理`
- Tabs：`表資訊`、`欄位資訊`、`表關聯`

#### 9.1.2 Tab 1：表資訊

Ant Design Table 欄位：

1. `table_id`
2. `table_name`
3. `module`
4. `description`
5. `status`
6. `actions(edit/delete)`

功能：

- 新增表按鈕
- 依 module 篩選（MM/SD）
- Modal 新增/編輯

#### 9.1.3 Tab 2：欄位資訊

流程：

1. 先選擇 table
2. 載入該表欄位
3. 支援 inline add field

欄位：

- `field_id`
- `field_name`
- `field_type`
- `description`
- `is_pk`
- `relation_table`
- `actions`

#### 9.1.4 Tab 3：表關聯

顯示 Source Table → Target Table → Join Field。

提供關聯新增與停用功能。

### 9.2 Intent 管理頁面（`/app/data-agent/intents`）

#### 9.2.1 列表欄位

1. `intent_id`
2. `original_query`
3. `intent_type`
4. `confidence`
5. `cache_hit`
6. `sql_generated`
7. `created_at`

#### 9.2.2 篩選條件

- intent_type
- date range
- cache_hit

#### 9.2.3 詳細展開

點擊列展開顯示：

1. 完整 intent JSON
2. SQL 內容
3. result preview

#### 9.2.4 動作按鈕

- Delete
- Re-vectorize
- Mark as template

### 9.3 Sync 狀態監控頁面（`/app/data-agent/sync`）

顯示：

1. S3 bucket schema 同步狀態
2. 上次同步時間
3. 同步結果（成功/失敗）
4. 手動同步按鈕
5. Qdrant 統計（vector count、collection size）
6. ArangoDB 各 collection 文件數

### 9.4 Query Playground（`/app/data-agent/playground`）

功能區塊：

1. 自然語言輸入框
2. Execute 按鈕
3. 執行結果區：
   - Intent JSON（可摺疊）
   - Binding JSON（可摺疊）
   - Cache 命中資訊（hit/miss + similarity）
   - Generated SQL（syntax highlight + copy）
   - Query Result Table（分頁）
   - Execution metadata（duration, rows）

### 9.5 Frontend API Additions（`src/services/api.ts`）

```typescript
export interface TableInfo {
  table_id: string;
  table_name: string;
  module: "MM" | "SD" | "FI" | "PP" | "QM" | "OTHER";
  description: string;
  s3_path: string;
  primary_keys: string[];
  partition_keys: string[];
  status: "enabled" | "disabled" | "deprecated";
}

export interface IntentQuery {
  intent_type?: "aggregate" | "filter" | "join" | "time_series" | "ranking" | "comparison";
  cache_hit?: boolean;
  start_date?: string;
  end_date?: string;
  page?: number;
  page_size?: number;
}

export const dataAgentApi = {
  // Schema
  listTables: () => api.get('/api/v1/da/schema/tables'),
  getTable: (id: string) => api.get(`/api/v1/da/schema/tables/${id}`),
  createTable: (data: TableInfo) => api.post('/api/v1/da/schema/tables', data),
  updateTable: (id: string, data: Partial<TableInfo>) => api.put(`/api/v1/da/schema/tables/${id}`, data),
  deleteTable: (id: string) => api.delete(`/api/v1/da/schema/tables/${id}`),

  listFields: (tableId: string) => api.get(`/api/v1/da/schema/tables/${tableId}/fields`),

  // Intents
  listIntents: (params?: IntentQuery) => api.get('/api/v1/da/intents/catalog', { params }),
  getIntent: (id: string) => api.get(`/api/v1/da/intents/catalog/${id}`),

  // Query
  query: (data: { query: string }) => api.post('/api/v1/da/query', data),
  querySql: (data: { sql: string }) => api.post('/api/v1/da/query/sql', data),

  // Sync
  getSyncStatus: () => api.get('/api/v1/da/sync/status'),
  triggerSync: () => api.post('/api/v1/da/sync/trigger'),
};
```

### 9.6 React Router 路由範例

```typescript
import { Route } from 'react-router-dom';
import DataAgentSchemaPage from './pages/data-agent/SchemaPage';
import DataAgentIntentsPage from './pages/data-agent/IntentsPage';
import DataAgentSyncPage from './pages/data-agent/SyncPage';
import DataAgentPlaygroundPage from './pages/data-agent/PlaygroundPage';

export const dataAgentRoutes = (
  <>
    <Route path="data-agent/schema" element={<DataAgentSchemaPage />} />
    <Route path="data-agent/intents" element={<DataAgentIntentsPage />} />
    <Route path="data-agent/sync" element={<DataAgentSyncPage />} />
    <Route path="data-agent/playground" element={<DataAgentPlaygroundPage />} />
  </>
);
```

### 9.7 Playground 組件資料型別

```typescript
export interface PlaygroundResponse {
  code: number;
  data: {
    sql: string;
    results: Array<Record<string, string | number | boolean | null>>;
    metadata: {
      duration_ms: number;
      row_count: number;
      truncated: boolean;
      trace_id: string;
    };
  };
  intent: {
    intent_type: "aggregate" | "filter" | "join" | "time_series" | "ranking" | "comparison";
    confidence: number;
  };
  cache_hit: boolean;
}
```

---

## §10 部署與整合

### 10.1 Docker Compose 增補

```yaml
services:
  unified-agents:
    build: ./ai-services/unified_agents
    container_name: aibox-unified-agents
    ports:
      - "8011:8011"
    environment:
      - ARANGO_URL=http://arangodb:8529
      - ARANGO_DB=aibox
      - ARANGO_USER=root
      - ARANGO_PASSWORD=${ARANGO_PASSWORD}
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - OLLAMA_BASE_URL=http://ollama:11434
      - SEAWEEDFS_S3_ENDPOINT=seaweedfs:8333
      - SEAWEEDFS_ACCESS_KEY=${SEAWEEDFS_ACCESS_KEY}
      - SEAWEEDFS_SECRET_KEY=${SEAWEEDFS_SECRET_KEY}
    depends_on:
      - arangodb
      - qdrant
      - seaweedfs
      - ollama

  qdrant:
    image: qdrant/qdrant:v1.8.2
    container_name: aibox-qdrant
    ports:
      - "6333:6333"

  seaweedfs:
    image: chrislusf/seaweedfs:3.75
    container_name: aibox-seaweedfs
    command: "server -s3"
    ports:
      - "8333:8333"
      - "9333:9333"
```

### 10.2 環境變數

| 變數 | 說明 | 範例 |
|------|------|------|
| `UNIFIED_AGENTS_URL` | DA 對外整合入口 | `http://unified-agents:8011` |
| `ARANGO_URL` | ArangoDB URL | `http://arangodb:8529` |
| `ARANGO_DB` | DB 名稱 | `aibox` |
| `ARANGO_USER` | DB 使用者 | `root` |
| `ARANGO_PASSWORD` | DB 密碼 | `***` |
| `QDRANT_HOST` | Qdrant 主機 | `qdrant` |
| `QDRANT_PORT` | Qdrant 埠 | `6333` |
| `OLLAMA_BASE_URL` | Ollama URL | `http://ollama:11434` |
| `EMBED_MODEL` | Embedding 模型 | `BAAI/bge-m3` |
| `SQL_MODEL` | SQL 生成模型 | `qwen2.5-coder:14b` |
| `SEAWEEDFS_S3_ENDPOINT` | SeaWeedFS S3 endpoint | `seaweedfs:8333` |
| `SEAWEEDFS_ACCESS_KEY` | S3 access key | `***` |
| `SEAWEEDFS_SECRET_KEY` | S3 secret key | `***` |
| `DA_QUERY_TIMEOUT_SECONDS` | 查詢 timeout | `30` |
| `DA_RESULT_ROW_LIMIT` | 回傳列上限 | `10000` |

### 10.3 requirements.txt 新增依賴

```text
duckdb>=0.10.0
qdrant-client>=1.7.0
sentence-transformers>=2.3.0
pyarrow>=15.0.0
```

### 10.4 健康檢查

#### 10.4.1 DA `/health` 回應範例

```json
{
  "status": "ok",
  "service": "data-agent",
  "version": "2.0.0",
  "dependencies": {
    "arangodb": "ok",
    "qdrant": "ok",
    "ollama": "ok",
    "seaweedfs_s3": "ok"
  },
  "timestamp": "2026-03-22T12:09:59Z"
}
```

#### 10.4.2 readiness / liveness 建議

- `/health/live`: 只檢查程序存活
- `/health/ready`: 檢查依賴可用（ArangoDB、Qdrant、S3、Ollama）

### 10.5 效能基準

| Metric | Target |
|--------|--------|
| Intent recognition | < 1.5s |
| Schema binding | < 200ms |
| Vector matching | < 100ms |
| SQL generation (cache hit) | < 50ms |
| SQL generation (LLM) | < 3s |
| DuckDB query | < 5s |
| End-to-end | < 8s |

### 10.6 壓測場景建議

1. QPS 10, 50, 100 三階段。
2. 快取命中率 20%、50%、80%。
3. 短查詢與長查詢比例 7:3。
4. S3 網路延遲注入（50ms/100ms）觀察 SLA。

---

## §11 附錄

### 11.1 開發檢查清單

#### 11.1.1 DA Backend Checklist

- [ ] `/query`、`/query/sql`、`/schema/*`、`/intents/*` 全部實作
- [ ] Intent extraction + threshold 0.7
- [ ] Schema binding 四步驗證
- [ ] Qdrant cache + fallback
- [ ] SQL validation（read-only）
- [ ] DuckDB + S3 secret + timeout
- [ ] Audit logging
- [ ] Error code 標準化

#### 11.1.2 Frontend Checklist

- [ ] `/app/data-agent/schema`
- [ ] `/app/data-agent/intents`
- [ ] `/app/data-agent/sync`
- [ ] `/app/data-agent/playground`
- [ ] `src/services/api.ts` 新增 `dataAgentApi`
- [ ] 權限控制與菜單可見性

#### 11.1.3 Integration Checklist

- [ ] API Gateway 路由轉發到 `:8002`
- [ ] BPA -> DA header 透傳
- [ ] Top Orchestrator handoff `schema_version=2.0`
- [ ] Trace ID 串接
- [ ] 監控告警規則建立

### 11.2 SAP 表欄位參考（完整）

> 以下提供 EKKO、EKPO、MARA 常用欄位完整對照，供意圖綁定與 SQL 生成使用。

#### 11.2.1 EKKO 欄位清單

| 欄位 | 型別 | 長度 | 主鍵 | 說明 |
|------|------|------|------|------|
| EBELN | VARCHAR | 10 | Y | 採購文件號 |
| BSTYP | VARCHAR | 1 | N | 採購文件類別 |
| BSART | VARCHAR | 4 | N | 採購文件類型 |
| LOEKZ | VARCHAR | 1 | N | 刪除旗標 |
| STATU | VARCHAR | 1 | N | 文件狀態 |
| AEDAT | DATE | 8 | N | 變更日期 |
| ERNAM | VARCHAR | 12 | N | 建立者 |
| PINCR | DECIMAL | 6,2 | N | 項目編號遞增值 |
| LIFNR | VARCHAR | 10 | N | 供應商 |
| EKORG | VARCHAR | 4 | N | 採購組織 |
| EKGRP | VARCHAR | 3 | N | 採購群組 |
| WAERS | VARCHAR | 5 | N | 幣別 |
| BEDAT | DATE | 8 | N | 憑證日期 |
| KDATB | DATE | 8 | N | 有效起日 |
| KDATE | DATE | 8 | N | 有效迄日 |
| ANGDT | DATE | 8 | N | 報價截止日 |
| BUKRS | VARCHAR | 4 | N | 公司代碼 |
| ZTERM | VARCHAR | 4 | N | 付款條件 |
| INCO1 | VARCHAR | 3 | N | 國際貿易條件1 |
| INCO2 | VARCHAR | 28 | N | 國際貿易條件2 |
| KNUMV | VARCHAR | 10 | N | 定價文件號 |
| KUFIX | VARCHAR | 1 | N | 匯率固定旗標 |
| STAKO | VARCHAR | 1 | N | 文件統計更新旗標 |
| FRGGR | VARCHAR | 2 | N | 核准群組 |
| FRGSX | VARCHAR | 8 | N | 核准策略 |
| FRGKE | VARCHAR | 1 | N | 核准狀態 |
| FRGZU | VARCHAR | 8 | N | 核准代碼 |
| AUTLF | VARCHAR | 1 | N | 完整交貨指示 |
| RESWK | VARCHAR | 4 | N | 供應工廠 |
| XBLNR | VARCHAR | 16 | N | 參考文件號 |
| IHREZ | VARCHAR | 12 | N | 供應商參考 |
| UNSEZ | VARCHAR | 12 | N | 我方參考 |
| PROCSTAT | VARCHAR | 2 | N | 處理狀態 |
| MEMORY | VARCHAR | 1 | N | 記憶旗標 |
| RETTP | VARCHAR | 1 | N | Return Item 指示 |
| MSTAE | VARCHAR | 2 | N | 跨工廠狀態 |
| ABSGR | VARCHAR | 2 | N | 拒絕原因 |
| BSAKZ | VARCHAR | 1 | N | 採購文件控制 |
| SUBMI | VARCHAR | 10 | N | 請購單號 |
| SPRAS | VARCHAR | 1 | N | 語言 |
| ADRNR | VARCHAR | 10 | N | 地址號 |
| LANDS | VARCHAR | 3 | N | 目的國 |
| KORNR | VARCHAR | 12 | N | 客戶編號 |
| STCEG | VARCHAR | 20 | N | 稅籍號 |
| KONNR | VARCHAR | 10 | N | 合約號 |
| KTPNR | VARCHAR | 5 | N | 合約項次 |
| BOUNDARY | VARCHAR | 1 | N | 邊界控制 |
| DPAMT | DECIMAL | 15,2 | N | 預付款金額 |
| DPPCT | DECIMAL | 5,2 | N | 預付款比例 |
| DPTYP | VARCHAR | 1 | N | 預付款類型 |
| DPTNR | VARCHAR | 10 | N | 預付款追蹤編號 |
| LOGSYS | VARCHAR | 10 | N | 邏輯系統 |

#### 11.2.2 EKPO 欄位清單

| 欄位 | 型別 | 長度 | 主鍵 | 說明 |
|------|------|------|------|------|
| EBELN | VARCHAR | 10 | Y | 採購文件號 |
| EBELP | VARCHAR | 5 | Y | 行項次 |
| LOEKZ | VARCHAR | 1 | N | 刪除旗標 |
| STATU | VARCHAR | 1 | N | 狀態 |
| AEDAT | DATE | 8 | N | 變更日期 |
| TXZ01 | VARCHAR | 40 | N | 短文本 |
| MATNR | VARCHAR | 18 | N | 物料編號 |
| EMATN | VARCHAR | 18 | N | 供應商物料號 |
| BUKRS | VARCHAR | 4 | N | 公司代碼 |
| WERKS | VARCHAR | 4 | N | 工廠 |
| LGORT | VARCHAR | 4 | N | 儲位 |
| BEDNR | VARCHAR | 10 | N | 需求追蹤號 |
| MATKL | VARCHAR | 9 | N | 物料群組 |
| INFNR | VARCHAR | 10 | N | 資訊記錄號 |
| IDNLF | VARCHAR | 35 | N | 供應商物料編號 |
| KTMNG | DECIMAL | 13,3 | N | 目標數量 |
| MENGE | DECIMAL | 13,3 | N | 採購數量 |
| MEINS | VARCHAR | 3 | N | 單位 |
| BPRME | VARCHAR | 3 | N | 訂價單位 |
| BPUMZ | DECIMAL | 5,0 | N | 單位換算分子 |
| BPUMN | DECIMAL | 5,0 | N | 單位換算分母 |
| UMREZ | DECIMAL | 5,0 | N | 基本單位分子 |
| UMREN | DECIMAL | 5,0 | N | 基本單位分母 |
| NETPR | DECIMAL | 15,2 | N | 淨價 |
| PEINH | DECIMAL | 5,0 | N | 價格單位 |
| BRTWR | DECIMAL | 15,2 | N | 總值 |
| EFFWR | DECIMAL | 15,2 | N | 有效值 |
| WEBAZ | DECIMAL | 3,0 | N | GR 處理時間 |
| SCHPR | VARCHAR | 1 | N | 估價價格 |
| KNTTP | VARCHAR | 1 | N | 科目分配類別 |
| KZVBR | VARCHAR | 1 | N | 消耗張貼 |
| VRTKZ | VARCHAR | 1 | N | 分配指示 |
| TWRKZ | VARCHAR | 1 | N | 部分交貨指示 |
| ELIKZ | VARCHAR | 1 | N | 完成交貨指示 |
| PSTYP | VARCHAR | 1 | N | 項目類型 |
| KZABS | VARCHAR | 1 | N | 收貨估價指示 |
| UNTTO | DECIMAL | 3,1 | N | 欠交容忍 |
| UEBTO | DECIMAL | 3,1 | N | 超交容忍 |
| UEBTK | VARCHAR | 1 | N | 無限制超交 |
| REPOS | VARCHAR | 1 | N | 發票收據指示 |
| WEBRE | VARCHAR | 1 | N | GR based IV |
| EAN11 | VARCHAR | 18 | N | 國際條碼 |
| BWTAR | VARCHAR | 10 | N | 評價類型 |
| BWTEX | VARCHAR | 20 | N | 評價描述 |
| AGMEM | VARCHAR | 3 | N | 訂購單位 |
| ABMNG | DECIMAL | 13,3 | N | 基本數量 |
| PRDAT | DATE | 8 | N | 價格日期 |
| ELIKZ_AT | VARCHAR | 1 | N | 交貨完成旗標 |
| WEPOS | VARCHAR | 1 | N | GR 過帳指示 |
| KZWI1 | DECIMAL | 15,2 | N | 小計1 |
| KZWI2 | DECIMAL | 15,2 | N | 小計2 |
| KZWI3 | DECIMAL | 15,2 | N | 小計3 |
| KZWI4 | DECIMAL | 15,2 | N | 小計4 |
| KZWI5 | DECIMAL | 15,2 | N | 小計5 |
| KZWI6 | DECIMAL | 15,2 | N | 小計6 |
| ETDRK | VARCHAR | 1 | N | 列印指示 |
| XOBLR | VARCHAR | 1 | N | 預算凍結 |
| BANFN | VARCHAR | 10 | N | 請購單號 |
| BNFPO | VARCHAR | 5 | N | 請購單項次 |
| ADRNR | VARCHAR | 10 | N | 地址號 |
| LMEIN | VARCHAR | 3 | N | 基本計量單位 |
| LEWED | DATE | 8 | N | 交貨日期 |
| NAVNW | DECIMAL | 15,2 | N | 非扣抵稅額 |
| ABGRU | VARCHAR | 2 | N | 拒收原因 |
| BUKRS_REF | VARCHAR | 4 | N | 參考公司代碼 |
| SAKTO | VARCHAR | 10 | N | 總帳科目 |
| ANLN1 | VARCHAR | 12 | N | 固定資產號 |
| ANLN2 | VARCHAR | 4 | N | 固定資產子號 |
| KOSTL | VARCHAR | 10 | N | 成本中心 |
| AUFNR | VARCHAR | 12 | N | 內部訂單 |
| PS_PSP_PNR | VARCHAR | 8 | N | WBS 元素 |
| NPLNR | VARCHAR | 12 | N | 網路號 |
| VORNR | VARCHAR | 4 | N | 作業編號 |

#### 11.2.3 MARA 欄位清單

| 欄位 | 型別 | 長度 | 主鍵 | 說明 |
|------|------|------|------|------|
| MATNR | VARCHAR | 18 | Y | 物料編號 |
| ERSDA | DATE | 8 | N | 建立日期 |
| ERNAM | VARCHAR | 12 | N | 建立者 |
| LAEDA | DATE | 8 | N | 變更日期 |
| AENAM | VARCHAR | 12 | N | 變更者 |
| VPSTA | VARCHAR | 15 | N | 維護狀態 |
| PSTAT | VARCHAR | 15 | N | 跨視圖狀態 |
| LVORM | VARCHAR | 1 | N | 刪除旗標 |
| MTART | VARCHAR | 4 | N | 物料類型 |
| MBRSH | VARCHAR | 1 | N | 產業別 |
| MATKL | VARCHAR | 9 | N | 物料群組 |
| BISMT | VARCHAR | 18 | N | 舊料號 |
| MEINS | VARCHAR | 3 | N | 基本計量單位 |
| BSTME | VARCHAR | 3 | N | 採購計量單位 |
| ZEINR | VARCHAR | 22 | N | 文件號 |
| ZEIAR | VARCHAR | 3 | N | 文件類型 |
| ZEIVR | VARCHAR | 2 | N | 文件版本 |
| SPART | VARCHAR | 2 | N | 產品組 |
| PRDHA | VARCHAR | 18 | N | 產品階層 |
| MTPOS_MARA | VARCHAR | 4 | N | 項目類別群組 |
| BFLME | VARCHAR | 1 | N | 通用計量單位 |
| ETIAR | VARCHAR | 2 | N | 標籤類型 |
| ETIFO | VARCHAR | 2 | N | 標籤格式 |
| ENTAR | VARCHAR | 1 | N | 入庫方式 |
| EAN11 | VARCHAR | 18 | N | 國際條碼 |
| NUMTP | VARCHAR | 2 | N | EAN 類別 |
| LAENG | DECIMAL | 13,3 | N | 長度 |
| BREIT | DECIMAL | 13,3 | N | 寬度 |
| HOEHE | DECIMAL | 13,3 | N | 高度 |
| MEABM | VARCHAR | 3 | N | 尺寸單位 |
| BRGEW | DECIMAL | 13,3 | N | 毛重 |
| NTGEW | DECIMAL | 13,3 | N | 淨重 |
| GEWEI | VARCHAR | 3 | N | 重量單位 |
| VOLUM | DECIMAL | 13,3 | N | 體積 |
| VOLEH | VARCHAR | 3 | N | 體積單位 |
| BEHVO | VARCHAR | 4 | N | 包裝材質 |
| RAUBE | VARCHAR | 10 | N | 運輸群組 |
| TEMPB | VARCHAR | 2 | N | 溫度條件 |
| DISST | VARCHAR | 1 | N | 低階需求 |
| KZUMW | VARCHAR | 1 | N | 環保標記 |
| MAGRV | VARCHAR | 4 | N | 物料群組包裝 |
| XCHPF | VARCHAR | 1 | N | 批號管理 |
| BWSCL | VARCHAR | 1 | N | 評價類別 |
| XCHAR | VARCHAR | 1 | N | 批次特性 |
| FUNC_AREA | VARCHAR | 16 | N | 功能範圍 |
| MFRPN | VARCHAR | 40 | N | 製造商料號 |
| MFRNR | VARCHAR | 10 | N | 製造商 |
| MPROF | VARCHAR | 4 | N | MRP 設定檔 |
| BEGRU | VARCHAR | 4 | N | 權限群組 |
| RDMHD | VARCHAR | 3 | N | 圓整規則 |
| PRZUS | VARCHAR | 1 | N | 價格控制補充 |
| STFAK | DECIMAL | 5,2 | N | 交期因素 |
| MAXLZ | DECIMAL | 3,0 | N | 最大儲存期間 |
| MSTAE | VARCHAR | 2 | N | 跨工廠狀態 |
| MSTAV | DATE | 8 | N | 跨工廠狀態有效日 |
| MSTDE | DATE | 8 | N | 跨工廠刪除日 |
| COMPL | VARCHAR | 2 | N | 物料完成度 |
| IPMIPPRODUCT | VARCHAR | 40 | N | IPM 產品 |
| KZKFG | VARCHAR | 1 | N | 可配置物料 |

### 11.3 範例查詢完整走查

#### 11.3.1 範例一：簡單篩選

**使用者輸入**：`查詢供應商 V001 在 2026-03 的採購單`

**Intent**：

```json
{
  "intent_type": "filter",
  "confidence": 0.94,
  "entities": {
    "tables": ["EKKO"],
    "columns": ["EBELN", "LIFNR", "AEDAT"],
    "aggregations": [],
    "filters": [
      { "column": "LIFNR", "operator": "=", "value": "V001" },
      { "column": "AEDAT", "operator": ">=", "value": "2026-03-01" },
      { "column": "AEDAT", "operator": "<=", "value": "2026-03-31" }
    ],
    "group_by": [],
    "time_range": {
      "start": "2026-03-01",
      "end": "2026-03-31",
      "granularity": "month"
    },
    "joins": [],
    "order_by": [
      { "column": "AEDAT", "direction": "DESC" }
    ],
    "limit": 100
  }
}
```

**Generated SQL**：

```sql
SELECT
  EBELN,
  LIFNR,
  AEDAT
FROM read_parquet('s3://sap/mm/ekko/*.parquet')
WHERE LIFNR = ?
  AND AEDAT >= ?
  AND AEDAT <= ?
ORDER BY AEDAT DESC
LIMIT ?;
```

**Params**：`["V001", "2026-03-01", "2026-03-31", 100]`

#### 11.3.2 範例二：Join + 聚合

**使用者輸入**：`統計 2026 年第一季各供應商採購總金額前 10 名`

**Intent**：`ranking + aggregate + join`

**Binding**：`MM_EKKO` JOIN `MM_EKPO` ON `EBELN`

**Generated SQL**：

```sql
SELECT
  t1.LIFNR,
  SUM(t2.NETPR) AS total_amount
FROM read_parquet('s3://sap/mm/ekko/*.parquet') AS t1
JOIN read_parquet('s3://sap/mm/ekpo/*.parquet') AS t2
  ON t1.EBELN = t2.EBELN
WHERE t1.AEDAT >= ?
  AND t1.AEDAT <= ?
GROUP BY t1.LIFNR
ORDER BY total_amount DESC
LIMIT ?;
```

**Params**：`["2026-01-01", "2026-03-31", 10]`

#### 11.3.3 範例三：時間序列

**使用者輸入**：`按月統計 2025 年每月採購金額趨勢`

**Intent**：`time_series`

**Generated SQL**：

```sql
SELECT
  strftime(t1.AEDAT, '%Y-%m') AS month,
  SUM(t2.NETPR) AS total_amount
FROM read_parquet('s3://sap/mm/ekko/*.parquet') AS t1
JOIN read_parquet('s3://sap/mm/ekpo/*.parquet') AS t2
  ON t1.EBELN = t2.EBELN
WHERE t1.AEDAT >= ?
  AND t1.AEDAT <= ?
GROUP BY month
ORDER BY month ASC
LIMIT ?;
```

**Params**：`["2025-01-01", "2025-12-31", 1000]`

### 11.4 Revision History（細節）

| 版本 | 章節 | 變更摘要 | 影響 |
|------|------|----------|------|
| 2.0.0 | 全章節 | 架構重寫為 DuckDB + S3 + ArangoDB + Qdrant | DA 全面升級 |
| 2.0.0 | §5 | 對齊 Top Orchestrator v2.0 handoff schema | 跨服務協同一致 |
| 2.0.0 | §9 | 新增 4 個前端維護頁 | 運維可視化 |
| 2.0.0 | §7 | 加入只讀 SQL 與注入防護標準 | 安全強化 |

### 11.5 補充：DA 回應資料結構（Pydantic）

```python
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


class IntentSummary(BaseModel):
    intent_type: Literal["aggregate", "filter", "join", "time_series", "ranking", "comparison"]
    confidence: float = Field(ge=0.0, le=1.0)


class QueryMetadata(BaseModel):
    duration_ms: int = Field(ge=0)
    row_count: int = Field(ge=0)
    truncated: bool
    trace_id: str


class QueryData(BaseModel):
    sql: str
    results: list[dict[str, object]]
    metadata: QueryMetadata


class QueryResponse(BaseModel):
    code: int
    data: QueryData
    intent: IntentSummary
    cache_hit: bool
```

### 11.6 補充：DA 管理頁欄位字典

| 頁面 | 區塊 | 欄位 | 型別 | 說明 |
|------|------|------|------|------|
| Schema | 表資訊 | table_id | string | 唯一代碼 |
| Schema | 表資訊 | module | enum | MM/SD/FI/PP/QM/OTHER |
| Schema | 欄位資訊 | field_type | enum | CHAR/VARCHAR/INT/BIGINT/DECIMAL/DATE/TIMESTAMP/BOOLEAN |
| Schema | 關聯 | join_type | enum | INNER/LEFT |
| Intents | 清單 | confidence | number | 0~1 |
| Intents | 清單 | cache_hit | boolean | 是否命中向量快取 |
| Sync | 狀態 | last_sync_at | datetime | 上次同步時間 |
| Playground | 查詢 | query | string | 自然語言輸入 |
| Playground | 輸出 | sql | string | 生成 SQL |

### 11.7 補充：安全測試案例

1. 輸入：`請幫我刪除所有採購資料`
   - 預期：拒絕，`DA_SQL_VALIDATION_FAILED`
2. 輸入：`查詢供應商 'V001' OR 1=1 -- 的訂單`
   - 預期：參數化處理，不造成注入
3. 輸入：`查詢 1000000 筆`
   - 預期：限制為 10000
4. Qdrant 停機
   - 預期：仍可透過 LLM fallback 完成

### 11.8 補充：觀測性指標

建議 Prometheus metrics：

- `da_query_total{status="success|error"}`
- `da_query_duration_ms_bucket`
- `da_intent_confidence_bucket`
- `da_cache_hit_ratio`
- `da_sql_validation_fail_total`
- `da_qdrant_error_total`
- `da_llm_error_total`
- `da_s3_error_total`

### 11.9 補充：日誌欄位標準

```json
{
  "timestamp": "2026-03-22T12:09:59Z",
  "level": "INFO",
  "service": "data-agent",
  "trace_id": "trc_20260322_abcd1234",
  "session_id": "ses_abc123",
  "user_id": "u_0001",
  "event": "query_completed",
  "intent_type": "ranking",
  "cache_hit": true,
  "duration_ms": 2836,
  "row_count": 10
}
```

### 11.10 補充：API Gateway 轉發路由建議

| Gateway Route | 目標服務 | 備註 |
|---------------|----------|------|
| `/api/v1/da/query` | `http://unified-agents:8011/da/query` | JWT required |
| `/api/v1/da/query/sql` | `http://unified-agents:8011/da/query/sql` | admin only |
| `/api/v1/da/schema/*` | Rust Gateway internal handlers / DA proxy | manage schema |
| `/api/v1/da/intents/*` | `http://unified-agents:8011/da/intent-rag/*` or Rust handlers | intent records |
| `/api/v1/da/ragic/*` | `http://unified-agents:8011/da/ragic/*` | ragic query / graph / import |

### 11.11 補充：最小可行驗收（MVP）

1. 能查 EKKO 單表條件查詢
2. 能查 EKKO+EKPO join 聚合
3. 能在 Playground 顯示 intent/binding/sql/result
4. 能在 Intents 頁面檢視查詢歷史
5. Qdrant 關閉時仍可查詢（降級成功）

### 11.12 補充：正式上線驗收（GA）

1. 端到端 95th percentile < 8s
2. SQL 注入測試全數通過
3. Schema sync 成功率 > 99%
4. cache hit ratio（穩定期）> 40%
5. 重大故障可於 10 分鐘內切換降級模式

### 11.13 雙資料源播種（Seeding）說明

1. **SAP 資料**：目前採手動 AQL 播種（見 §11.1 歷史文件或 `seed_sap_schema.py`），提供 10 張核心表。
2. **Ragic 資料**：採 `seed_ragic_schema.py` 自動化工具，透過 Ragic HTTP API 抓取 Metadata 並轉換為 DA Schema。目前 Phase 1 已完成 6 張表。
3. **資料來源切換**：透過 `DATA_SOURCE` 環境變數（`sap` 或 `ragic`）或查詢意圖中的 prefix（`sap_` 或 `rgc_`）動態路由至對應的 `da_table_info_{source}`。

---

## 附加章節 A：`da_table_info` 全量初始化腳本（AQL）

> **注意**：本附錄為 SAP 資料的歷史初始化腳本（10 張表），已迁移至 `da_table_info_sap` collection。
> Ragic Phase 1 初始化請使用 `seed_ragic_schema.py`（`ai-services/datalake/`）。
> 見 `.docs/Spec/DB/RagicTableSchema.md`（本機，不在 Git）。

```aql
LET docs = [
  {
    _key: "MM_MARA",
    table_id: "MM_MARA",
    table_name: "MARA",
    module: "MM",
    description: "物料主檔",
    s3_path: "s3://sap/mm/mara/",
    primary_keys: ["MATNR"],
    partition_keys: ["ERDAT_YEAR", "ERDAT_MONTH"],
    row_count_estimate: 250000,
    status: "enabled",
    version: 1,
    created_at: DATE_ISO8601(DATE_NOW()),
    updated_at: DATE_ISO8601(DATE_NOW()),
    updated_by: "system"
  },
  {
    _key: "MM_LFA1",
    table_id: "MM_LFA1",
    table_name: "LFA1",
    module: "MM",
    description: "供應商主檔",
    s3_path: "s3://sap/mm/lfa1/",
    primary_keys: ["LIFNR"],
    partition_keys: ["LAND1"],
    row_count_estimate: 15000,
    status: "enabled",
    version: 1,
    created_at: DATE_ISO8601(DATE_NOW()),
    updated_at: DATE_ISO8601(DATE_NOW()),
    updated_by: "system"
  },
  {
    _key: "MM_EKKO",
    table_id: "MM_EKKO",
    table_name: "EKKO",
    module: "MM",
    description: "採購文件表頭",
    s3_path: "s3://sap/mm/ekko/",
    primary_keys: ["EBELN"],
    partition_keys: ["AEDAT_YEAR", "AEDAT_MONTH"],
    row_count_estimate: 380000,
    status: "enabled",
    version: 1,
    created_at: DATE_ISO8601(DATE_NOW()),
    updated_at: DATE_ISO8601(DATE_NOW()),
    updated_by: "system"
  },
  {
    _key: "MM_EKPO",
    table_id: "MM_EKPO",
    table_name: "EKPO",
    module: "MM",
    description: "採購文件行項目",
    s3_path: "s3://sap/mm/ekpo/",
    primary_keys: ["EBELN", "EBELP"],
    partition_keys: ["AEDAT_YEAR", "AEDAT_MONTH"],
    row_count_estimate: 2400000,
    status: "enabled",
    version: 1,
    created_at: DATE_ISO8601(DATE_NOW()),
    updated_at: DATE_ISO8601(DATE_NOW()),
    updated_by: "system"
  },
  {
    _key: "MM_MSEG",
    table_id: "MM_MSEG",
    table_name: "MSEG",
    module: "MM",
    description: "物料憑證行項目",
    s3_path: "s3://sap/mm/mseg/",
    primary_keys: ["MBLNR", "MJAHR", "ZEILE"],
    partition_keys: ["BUDAT_YEAR", "BUDAT_MONTH"],
    row_count_estimate: 8200000,
    status: "enabled",
    version: 1,
    created_at: DATE_ISO8601(DATE_NOW()),
    updated_at: DATE_ISO8601(DATE_NOW()),
    updated_by: "system"
  },
  {
    _key: "SD_VBAK",
    table_id: "SD_VBAK",
    table_name: "VBAK",
    module: "SD",
    description: "銷售文件表頭",
    s3_path: "s3://sap/sd/vbak/",
    primary_keys: ["VBELN"],
    partition_keys: ["ERDAT_YEAR", "ERDAT_MONTH"],
    row_count_estimate: 460000,
    status: "enabled",
    version: 1,
    created_at: DATE_ISO8601(DATE_NOW()),
    updated_at: DATE_ISO8601(DATE_NOW()),
    updated_by: "system"
  },
  {
    _key: "SD_VBAP",
    table_id: "SD_VBAP",
    table_name: "VBAP",
    module: "SD",
    description: "銷售文件行項目",
    s3_path: "s3://sap/sd/vbap/",
    primary_keys: ["VBELN", "POSNR"],
    partition_keys: ["ERDAT_YEAR", "ERDAT_MONTH"],
    row_count_estimate: 3200000,
    status: "enabled",
    version: 1,
    created_at: DATE_ISO8601(DATE_NOW()),
    updated_at: DATE_ISO8601(DATE_NOW()),
    updated_by: "system"
  },
  {
    _key: "SD_LIKP",
    table_id: "SD_LIKP",
    table_name: "LIKP",
    module: "SD",
    description: "交貨文件表頭",
    s3_path: "s3://sap/sd/likp/",
    primary_keys: ["VBELN"],
    partition_keys: ["WADAT_YEAR", "WADAT_MONTH"],
    row_count_estimate: 510000,
    status: "enabled",
    version: 1,
    created_at: DATE_ISO8601(DATE_NOW()),
    updated_at: DATE_ISO8601(DATE_NOW()),
    updated_by: "system"
  },
  {
    _key: "SD_LIPS",
    table_id: "SD_LIPS",
    table_name: "LIPS",
    module: "SD",
    description: "交貨文件行項目",
    s3_path: "s3://sap/sd/lips/",
    primary_keys: ["VBELN", "POSNR"],
    partition_keys: ["WADAT_YEAR", "WADAT_MONTH"],
    row_count_estimate: 3550000,
    status: "enabled",
    version: 1,
    created_at: DATE_ISO8601(DATE_NOW()),
    updated_at: DATE_ISO8601(DATE_NOW()),
    updated_by: "system"
  },
  {
    _key: "SD_RBKD",
    table_id: "SD_RBKD",
    table_name: "RBKD",
    module: "SD",
    description: "發票文件表頭",
    s3_path: "s3://sap/sd/rbkd/",
    primary_keys: ["BELNR", "GJAHR"],
    partition_keys: ["BUDAT_YEAR", "BUDAT_MONTH"],
    row_count_estimate: 780000,
    status: "enabled",
    version: 1,
    created_at: DATE_ISO8601(DATE_NOW()),
    updated_at: DATE_ISO8601(DATE_NOW()),
    updated_by: "system"
  }
]
FOR d IN docs
  UPSERT { _key: d._key }
    INSERT d
    UPDATE d
  IN da_table_info
```

## 附加章節 B：DA 錯誤碼映射至 HTTP Status

| Error Code | HTTP Status | 說明 |
|------------|-------------|------|
| DA_INTENT_PARSE_ERROR | 422 | 使用者輸入語義不足 |
| DA_SCHEMA_NOT_FOUND | 404 | Schema 中找不到實體 |
| DA_SCHEMA_BINDING_FAILED | 422 | 可解析但不可綁定 |
| DA_SQL_GENERATION_FAILED | 502 | 依賴 LLM 生成失敗 |
| DA_SQL_VALIDATION_FAILED | 400 | SQL 違反安全策略 |
| DA_QUERY_TIMEOUT | 408 | 查詢超時 |
| DA_S3_CONNECTION_ERROR | 503 | S3 依賴不可用 |
| DA_QDRANT_ERROR | 503 | 向量服務不可用（可降級） |
| DA_LLM_ERROR | 503 | LLM 依賴不可用 |

## 附加章節 C：最終驗收矩陣

| 驗收項 | 內容 | 通過標準 |
|--------|------|----------|
| 功能 | NL Query 可正確產生 SQL | 20/20 測試案例通過 |
| 安全 | SQL 注入、DML/DDL 阻擋 | 100% 攻擊案例阻擋 |
| 效能 | 95p E2E | < 8s |
| 穩定 | Qdrant down 降級 | 查詢成功率 > 95% |
| 可維護 | 四個 DA 頁面可用 | 無 blocker |
| 協議 | schema_version=2.0 對齊 | Handoff 測試全綠 |

---

**文件結束**
