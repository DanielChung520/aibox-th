---
lastUpdate: 2026-04-02 09:22:42
author: Daniel Chung
version: 1.1.0
---

# Data Agent SAP→Ragic 遷移計劃 — 進度追蹤

## 模組化拆分進度

| 模組 | 來源行數 | 目標 | 狀態 | 完成日期 |
|------|---------|------|------|---------|
| `seed_intent_catalog.py` 拆分 | 1129 行 | 4 個檔案 | ✅ 完成 | 2026-04-02 |
| `dataAgentApi.ts` 拆分 | 305 行 | 3 個檔案 | ✅ 完成 | 2026-04-02 |
| 遷移計劃文件拆分 | 1209 行 | 5 個 doc | ✅ 完成 | 2026-04-02 |

---

## Phase 1：程式碼模組化

### 1.1 `seed_intent_catalog.py` 拆分

| 子模組 | 檔案 | 行數（估）| 狀態 | 完成日期 |
|--------|------|----------|------|---------|
| 共用 helpers | `seed_intent_catalog_shared.py` | 133 | ✅ | 2026-04-02 |
| SAP Intent Templates | `seed_intent_catalog_sap.py` | 956 | ✅ | 2026-04-02 |
| Ragic Intent Templates | `seed_intent_catalog_ragic.py` | 433 | ✅ | 2026-04-02 |
| 主入口 | `seed_intent_catalog.py`（覆寫）| 57 | ✅ | 2026-04-02 |

**產出**：
- SAP DA: 37 intents (Groups A-F)
- Ragic DA: 18 intents (Groups A-F, Phase 2 placeholder)
- Orchestrator: 7 intents
- 驗證：`ruff check` + `mypy` 全部 clean ✅

**拆分策略**：
- `seed_intent_catalog_shared.py`：Header、imports、constants、`make_doc`、`make_orch_doc`、`curl_post_doc`、`insert_batch`、`ARANGO_URL`、`DB`、`AUTH`、`COLLECTION`、`TS`、`DA`、`ORCH`
- `seed_intent_catalog_sap.py`：`GROUP_A` ~ `GROUP_F`（35 個 SAP Data Agent intents）+ `ORCHESTRATOR_INTENTS`（7 個 Orchestrator intents）
- `seed_intent_catalog_ragic.py`：（遷移時新增）Ragic Data Agent intents Group A'~Group F'
- `seed_intent_catalog.py`（覆寫）：import 並組裝以上三個模組，main 邏輯

### 1.2 `dataAgentApi.ts` 拆分

| 子模組 | 檔案 | 行數（估）| 狀態 | 完成日期 |
|--------|------|----------|------|---------|
| 所有 TypeScript Interfaces | `dataAgentApi_types.ts` | 192 | ✅ | 2026-04-02 |
| API Endpoint 函式 | `dataAgentApi_endpoints.ts` | 136 | ✅ | 2026-04-02 |
| 主入口（re-export）| `dataAgentApi.ts`（覆寫）| 32 | ✅ | 2026-04-02 |

**產出**：
- 18 interfaces, 24 API endpoints
- LSP diagnostics: 0 errors ✅
- 下游消費者無需修改 import 語句

---

## Phase 2：遷移計劃文件拆分

| 檔案 | 內容 | 行數（估）| 狀態 | 完成日期 |
|------|------|----------|------|---------|
| `Migration-README.md` | 總覽：架構圖、階段、人天、入口連結 | ~57 | ✅ | 2026-04-02 |
| `Migration-Phase1-Backend.md` | T-000 ~ T-003：Schema Migration | ~300 | ✅ | 2026-04-02 |
| `Migration-Phase2-Backend.md` | T-004 ~ T-010：Pipeline 重寫 | ~400 | ✅ | 2026-04-02 |
| `Migration-Phase3-Frontend.md` | T3-1 ~ T3-8：前端 Schema 頁面 | ~350 | ✅ | 2026-04-02 |
| `Migration-Phase4-Docs.md` | T4-1 ~ T4-3：規格文件更新 + 附錄 | ~150 | ✅ | 2026-04-02 |

> **注意**：原 1209 行大文件已刪除（`DataAgent-SAP-to-Ragic-Migration-Plan.md`），所有內容已遷移至上方 5 個文件中。

**每個 Phase plan 的標準結構**：

```markdown
## 目標
[一句話描述]

## 對應 T-XXX 任務

## 前置條件
- 完成 [上一個 Phase]

## 實作時必讀檔案
- ai-services/...

## 驗收標準
- [ ] ...

## 依賴模組
- seed_intent_catalog_shared.py
- dataAgentApi_types.ts
```

---

## Phase 3：後端遷移實作

> 以下為 Phase 1（模組化）完成後才開始

| 任務 | 代碼 | 狀態 | 完成日期 |
|------|------|------|---------|
| Rename Collections 為 _sap | T-000 | ⏳ | — |
| 建立 Ragic Schema Seed Script | T-001 | ✅ 完成 | 2026-04-02 |
| 建立 _ragic Collections | T-002 | ✅ 完成 | 2026-04-02 |
| 執行 Phase 1 Schema Seed | T-003 | ✅ 完成 | 2026-04-02 |
| SQL Generator 路徑動態化 | T-004 | ✅ 完成 | 2026-04-02 |
| Intent Classifier 新增 Ragic 範例 | T-005 | ✅ 完成 | 2026-04-02 |
| Intent RAG Templates 新增 Ragic | T-006 | ✅ 完成 | 2026-04-02 |
| Pipeline Models 更新 | T-007 | ✅ 完成 | 2026-04-02 |
| Config Reader 更新 | T-008 | ✅ 完成 | 2026-04-02 |
| Schema Retriever Collection Routing | T-009 | ✅ 完成 | 2026-04-02 |
| 端到端測試 | T-010 | ✅ 靜態驗證完成 | 2026-04-02 |

---

## Phase 4：前端遷移實作

| 任務 | 代碼 | 狀態 | 完成日期 |
|------|------|------|---------|
| API Types 更新 | T3-1 | ⏳ | — |
| SchemaPage 資料來源過濾 | T3-2 | ⏳ | — |
| Tab Filter UI | T3-3 | ⏳ | — |
| Module Select 動態化 | T3-4 | ⏳ | — |
| Table Columns 新增欄位 | T3-5 | ⏳ | — |
| 新增資料表 Modal | T3-6 | ⏳ | — |
| 欄位 Modal Writable 標記 | T3-7 | ⏳ | — |
| QueryPlayground 更新 | T3-8 | ⏳ | — |

---

## Phase 5：規格文件更新

| 任務 | 代碼 | 狀態 | 完成日期 |
|------|------|------|---------|
| 更新 data-agent-spec-v2.md | T4-1 | ⏳ | — |
| 更新 API Specification.md | T4-2 | ⏳ | — |
| 更新 RagicTableSchema.md | T4-3 | ⏳ | — |

---

## 總工時追蹤

| Phase | 預估人天 | 實際人天 | 狀態 |
|-------|---------|---------|------|
| Phase 1：程式碼模組化 | 待估 | ~0.5 人天 | ✅ 完成 |
| Phase 2：遷移計劃文件拆分 | 待估 | ~0.5 人天 | ✅ 完成 |
| Phase 3：後端遷移實作 | 6 人天 | — | ⏳ |
| Phase 4：前端遷移實作 | 2.5 人天 | — | ⏳ |
| Phase 5：規格文件更新 | 0.5 人天 | — | ⏳ |
| **合計** | **9+ 人天** | **~1 人天** | — |

---

## 更新記錄

| 日期 | 更新者 | 變更內容 |
|------|--------|---------|
| 2026-04-02 | Daniel Chung | Phase 1+2 完成：seed_intent_catalog.py (1129→4), dataAgentApi.ts (305→3), 遷移計劃文件 (1209→5) |
| 2026-04-02 | Daniel Chung | T-001 完成：建立 seed_ragic_schema.py (717 行)，含 6 張 Ragic Phase1 表格、202 個欄位、8 個關聯 |
| 2026-04-02 | Daniel Chung | T-002 完成：建立 da_table_info_ragic, da_field_info_ragic, da_table_relation_ragic 三個 Collections |
| 2026-04-02 | Daniel Chung | T-003 完成：執行 seed_ragic_schema.py，6 表 / 202 欄位 / 8 關聯寫入 ArangoDB |
| 2026-04-02 | Daniel Chung | T-004 完成：sql_generator.py 路徑由 `config.s3_bucket` 動態控制（_format_schema_brief 函式） |
| 2026-04-02 | Daniel Chung | T-005+T-006 完成：seed_intent_catalog_ragic.py Groups A/B/C 更新為 Phase 1 實欄位（9 intents），Groups D/E/F 保留 Phase 2 placeholder，seed 執行成功 |
| 2026-04-02 | Daniel Chung | T-007 完成：models.py 新增 TableSchema(tab, sheet_key, s3_path) + FieldSchema(field_id, writable, is_subtable_field, subtable_key) |
| 2026-04-02 | Daniel Chung | T-008 完成：config_reader.py 新增 da.data_source 參數讀取 (DA_DATA_SOURCE env) |
| 2026-04-02 | Daniel Chung | T-009 完成：schema_retriever 依 config.data_source 動態路由 collection；orchestrator intent ID 以「rgc_」前綴自動切換至 ragic |
| 2026-04-02 | Daniel Chung | T-010 完成（靜態驗證）：完整 pipeline 鏈路驗證通過，intent 路由 → collection 動態選擇 → SQL 路徑動態化 |
| 2026-03-31 | Daniel Chung | 初始版本 |
