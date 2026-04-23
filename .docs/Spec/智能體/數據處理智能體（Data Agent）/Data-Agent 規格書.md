---
lastUpdate: 2026-04-16 17:43:24
author: Daniel Chung
version: 1.0.0
---

# 數據處理智能體（Data Agent）規格書

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-16 | 1.0.0 | Daniel Chung | 初始版本：從 NL→SQL over S3 架構遷移至結構化查詢 + 本地 SQL 模型架構 |

---

## 1. 定位與職責

### 1.1 定位

Data Agent 是 AIBox 系統中負責**資料查詢執行**的專職智能體。它不做意圖判斷、不做多輪對話管理，而是接收來自**艾企 Agent** 的精準查詢指令，翻譯為 SQL/AQL 並執行。

### 1.2 職責邊界

| 職責 | Data Agent | 艾企 Agent | TopOrchestrator |
|------|-----------|-----------|-----------------|
| 意圖理解 | ❌ | ✅ | ❌ |
| 查詢指令組裝 | ❌ | ✅（利用前端上下文） | ❌ |
| SQL 生成 | ✅ | ❌ | ❌ |
| SQL 驗證 | ✅ | ❌ | ❌ |
| SQL 執行 | ✅ | ❌ | ❌ |
| 結果格式化 | ✅ | ✅（組自然語言回覆） | ❌ |
| 多輪對話 | ❌ | ✅ | ✅（歷史存儲） |
| 鑑權 | ❌ | ❌ | ✅ |

### 1.3 設計原則

- **接收精準指令，不猜意圖**：艾企已利用前端上下文（tableId, fields, actionTrail）組好查詢，Data Agent 直接翻譯執行
- **專用 SQL 模型**：使用 `duckdb-nsql` / `sqlcoder` 等專為 SQL 訓練的本地模型，不浪費通用 LLM token
- **三層查詢源**：瀏覽器 DuckDB-WASM（最快，前端直接執行）→ Server DuckDB Cache → Data Agent
- **安全第一**：只允許 SELECT / FOR-RETURN，驗證層不可繞過

---

## 2. 系統架構

### 2.1 整體位置

```
┌─────────────────────────────────────────────────────────┐
│                    前端（React + Tauri）                   │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ actionTrail   │  │ intentEngine │  │ duckdbWasm    │  │
│  │ 操作記錄      │  │ 意圖猜測     │  │ 瀏覽器 DuckDB │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         │                 │                   │          │
│         └────────┬────────┘                   │          │
│                  ▼                            │          │
│         ┌──────────────┐     簡單查詢直接執行  │          │
│         │  ChatModal   │ ◄───────────────────┘          │
│         │  艾企前端 UI  │                                │
│         └──────┬───────┘                                │
└────────────────┼────────────────────────────────────────┘
                 │ SSE
                 ▼
┌────────────────────────┐
│   TopOrchestrator      │  Rust Axum (port 6500)
│   鑑權 → 路由 → 歷史   │
│   SSE proxy            │
└────────┬───────────────┘
         │ HTTP
         ▼
┌────────────────────────┐
│      艾企 Agent        │  Python (port 8001)
│   ReAct loop           │
│   function calling     │
│   工具選擇             │
└────────┬───────────────┘
         │ HTTP (工具呼叫)
         ▼
┌────────────────────────────────────────┐
│         Data Agent (port 8003)         │
│  ┌──────────────────────────────────┐  │
│  │  /query/structured  ← 新端點     │  │
│  │  結構化指令 → SQL 生成 → 執行    │  │
│  ├──────────────────────────────────┤  │
│  │  /query/nl  ← NL fallback       │  │
│  │  自然語言 → SQL（帶 hints）      │  │
│  ├──────────────────────────────────┤  │
│  │  /query/sql  ← 直接 SQL         │  │
│  │  已有端點，Rust 直接呼叫         │  │
│  └──────────────────────────────────┘  │
│                                        │
│  SQL 模型層：                          │
│  ┌─────────────────┐  ┌────────────┐  │
│  │ duckdb-nsql     │  │ sqlcoder   │  │
│  │ (主模型)        │  │ (備用)     │  │
│  └─────────────────┘  └────────────┘  │
│                                        │
│  執行層：                              │
│  ┌─────────────────┐  ┌────────────┐  │
│  │ Server DuckDB   │  │ ArangoDB   │  │
│  │ Cache           │  │ AQL        │  │
│  └─────────────────┘  └────────────┘  │
└────────────────────────────────────────┘
```

### 2.2 三層查詢決策

| 層級 | 查詢源 | 條件 | 延遲 | 呼叫方 |
|------|--------|------|------|--------|
| L1 | 瀏覽器 DuckDB-WASM | 表已載入 + 簡單查詢 | <100ms | 艾企前端直接呼叫 `duckdbWasm.query()` |
| L2 | Server DuckDB Cache | 表在 server cache + 中等查詢 | <500ms | Rust `/api/v1/da/query/sql` |
| L3 | Data Agent | 複雜分析 / 多表 / NL fallback | 1-10s | Data Agent `/query/structured` |

---

## 3. API 端點規格

### 3.1 `POST /query/structured`（新增）

艾企 Agent 呼叫的主要端點。接收結構化查詢指令，跳過意圖分類和 schema 檢索。

**Request**：

```json
{
  "table": "t_items_management",
  "table_id": "1018437",
  "intent": "count",
  "fields": ["item_name", "price", "status"],
  "filters": [
    {"field": "status", "op": "eq", "value": "active"},
    {"field": "price", "op": "gt", "value": "100"}
  ],
  "aggregations": ["count", "sum:price", "avg:price"],
  "group_by": ["status"],
  "sort": {"field": "price", "order": "desc"},
  "limit": 100,
  "source": "server_cache"
}
```

**欄位說明**：

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `table` | string | ✅ | DuckDB cache 中的表名（`t_<sanitized_tableId>`） |
| `table_id` | string | ❌ | 原始 Ragic table ID（用於 AQL 查詢） |
| `intent` | string | ✅ | 查詢意圖：`count`, `list`, `aggregate`, `filter`, `top_n`, `trend`, `detail` |
| `fields` | string[] | ❌ | 需要查詢的欄位（空=全部） |
| `filters` | Filter[] | ❌ | 過濾條件 |
| `aggregations` | string[] | ❌ | 聚合操作：`count`, `sum:<field>`, `avg:<field>`, `max:<field>`, `min:<field>` |
| `group_by` | string[] | ❌ | 分組欄位 |
| `sort` | Sort | ❌ | 排序 |
| `limit` | int | ❌ | 結果上限（預設 100） |
| `source` | string | ❌ | 資料源：`server_cache`（預設）、`arangodb` |

**Filter 結構**：

| 欄位 | 類型 | 說明 |
|------|------|------|
| `field` | string | 欄位名稱或 field_id |
| `op` | string | `eq`, `ne`, `gt`, `lt`, `gte`, `lte`, `like`, `in`, `between` |
| `value` | string / string[] | 比較值（between 用 `["start", "end"]`） |

**Response**：

```json
{
  "success": true,
  "generated_sql": "SELECT status, COUNT(*) AS cnt, SUM(price) AS total FROM t_items_management WHERE status = 'active' AND price > 100 GROUP BY status ORDER BY price DESC LIMIT 100",
  "execution_result": {
    "rows": [{"status": "active", "cnt": 42, "total": 15800.5}],
    "columns": ["status", "cnt", "total"],
    "row_count": 1,
    "execution_time_ms": 12.3
  },
  "model_used": "duckdb-nsql:latest",
  "total_time_ms": 850.2
}
```

**錯誤 Response**：

```json
{
  "success": false,
  "error": "SQL validation failed: column 'xyz' not found",
  "generated_sql": "SELECT xyz FROM ...",
  "model_used": "duckdb-nsql:latest",
  "fallback_model_used": "sqlcoder:7b",
  "attempts": 3,
  "total_time_ms": 2100.5
}
```

### 3.2 `POST /query/nl`（NL Fallback，新增）

當艾企無法組結構化指令時（例如非常模糊的問題），退回自然語言模式，但帶有 hints 縮小範圍。

**Request**：

```json
{
  "natural_language": "品項管理中價格最高的前10筆",
  "table_hint": "t_items_management",
  "table_id_hint": "1018437",
  "field_hints": ["item_name", "price"],
  "source": "server_cache"
}
```

**Response**：同 `/query/structured`。

### 3.3 現有端點（保留不變）

| 端點 | 方法 | 說明 | 變更 |
|------|------|------|------|
| `POST /query/query` | POST | NL→AQL 直接執行 | 不變 |
| `POST /query/nl2sql` | POST | 舊版 NL→SQL 完整 pipeline | **標記 DEPRECATED**，保留相容 |
| `POST /query/plan` | POST | 查詢計劃生成 | 不變 |
| `POST /query/explain` | POST | AQL explain | 不變 |
| `GET /query/tables/{name}/preview` | GET | 表格預覽 | 不變 |
| `GET /query/health` | GET | 健康檢查 | 不變 |

### 3.4 Rust API Gateway 端點（保留不變）

| 端點 | 說明 |
|------|------|
| `POST /api/v1/da/query/sql` | 直接在 Server DuckDB Cache 執行 SQL |
| `POST /api/v1/da/query/nl2sql` | 轉發到 Python Data Agent |
| `GET /api/v1/da/health` | 健康檢查 |

**新增轉發**：

| 端點 | 說明 |
|------|------|
| `POST /api/v1/da/query/structured` | 轉發到 Data Agent `/query/structured` |
| `POST /api/v1/da/query/nl` | 轉發到 Data Agent `/query/nl` |

---

## 4. SQL 模型架構

### 4.1 模型選擇策略

```
艾企組結構化指令
    ↓
Data Agent 收到 /query/structured
    ↓
┌─────────────────────────┐
│ 用 da.sql_model          │  (預設: duckdb-nsql:latest)
│ 生成 DuckDB SQL          │
│ temperature: da.sql_temperature (0.1)
└─────────┬───────────────┘
          ↓
┌─────────────────────────┐
│ SQL 驗證（validator.py） │
│ Layer 1: 正則檢查        │
│ Layer 2: AST 解析        │
│ Layer 3: 語義檢查(可選)   │
└─────────┬───────────────┘
          ↓
     驗證通過？
    ┌───┴───┐
    Yes     No
    ↓       ↓
  執行    ┌─────────────────────────┐
          │ 用 da.sql_fallback_model │  (預設: sqlcoder:7b)
          │ 重新生成                 │
          └─────────┬───────────────┘
                    ↓
              再次驗證 → 重試最多 da.sql_max_retries 次
```

### 4.2 系統參數

| 參數 key | 說明 | 預設值 | 可選值 |
|----------|------|--------|--------|
| `da.sql_model` | SQL 生成主模型 | `duckdb-nsql:latest` | 任何 Ollama/LM Studio 模型 |
| `da.sql_model_provider` | 主模型提供者 | `ollama` | `ollama`, `lm_studio` |
| `da.sql_fallback_model` | SQL 備用模型 | `sqlcoder:7b` | 任何 SQL 專用模型 |
| `da.sql_fallback_provider` | 備用提供者 | `ollama` | `ollama`, `lm_studio` |
| `da.sql_temperature` | 生成溫度 | `0.1` | 0.0 - 1.0（SQL 推薦低溫度） |
| `da.sql_max_retries` | 驗證失敗重試 | `2` | 0-5 |
| `da.query_source` | 預設查詢源 | `server_cache` | `server_cache`, `browser`, `datalake` |
| `da.data_source` | 原始資料源 | `ragic` | `ragic`, `sap` |
| `da.embedding_model` | 嵌入模型 | `qwen3-embedding:latest` | — |
| `da.embedding_dimension` | 嵌入維度 | `4096` | — |
| `da.large_llm_model` | 大型推理模型 | `qwen3-coder:30b` | — |
| `da.llm_model` | 通用模型 | `qwen3-coder:30b` | — |

### 4.3 Prompt 設計

**duckdb-nsql 專用 Prompt**（結構化模式）：

```
Generate a DuckDB SQL query for the following structured request.

Table: {table}
Available columns: {fields}
Intent: {intent}
Filters: {filters_json}
Aggregations: {aggregations}
Group by: {group_by}
Sort: {sort}
Limit: {limit}

Rules:
1. ONLY SELECT statements
2. Use exact column names as provided
3. Table name is: {table}
4. Output ONLY valid DuckDB SQL, no explanation
```

**sqlcoder fallback Prompt**（帶錯誤上下文）：

```
Previous SQL generation failed with error: {error}

Fix and regenerate. {same schema context}
```

---

## 5. 資料源架構

### 5.1 Server DuckDB Cache

- **位置**：`./data/table_cache.duckdb`（file-backed）
- **模組**：`api/src/table_cache/` (Rust)
- **表名慣例**：`t_<sanitized_tableId>`（與瀏覽器 DuckDB-WASM 一致）
- **資料來源**：Ragic API → ArangoDB → DuckDB Cache
- **查詢端點**：`POST /api/v1/da/query/sql`（Rust 直接執行）

### 5.2 瀏覽器 DuckDB-WASM

- **模組**：`src/services/duckdbWasm.ts`
- **表名慣例**：`t_<sanitized_tableId>`
- **載入時機**：用戶在 SchemaDataPreview 開表時
- **查詢方式**：`duckdbWasm.query(SQL)` 前端直接執行
- **檢查快取**：`duckdbWasm.hasTable(tableId)`

### 5.3 ArangoDB（Ragic 原始資料）

- **集合**：`da_table_data_ragic`
- **查詢方式**：AQL（FOR d IN ... FILTER ... RETURN）
- **欄位映射**：field_id → field_name（`da_field_info_ragic` 集合）

### 5.4 S3 Datalake（舊，計劃廢棄）

- **位置**：MinIO S3 `s3://sap/{module}/{table}/*.parquet`
- **查詢方式**：DuckDB + httpfs extension
- **狀態**：保留相容但不再作為主要查詢源

---

## 6. 安全機制

### 6.1 SQL 驗證（三層）

| 層級 | 檢查內容 | 實作 |
|------|----------|------|
| Layer 1 | 正則：禁止 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE | `validator.py` regex |
| Layer 2 | AST：sqlglot 解析，確認結構合法 | `validator.py` sqlglot |
| Layer 3 | 語義：LLM 驗證 SQL 與原始意圖是否匹配（僅 LARGE_LLM 策略） | `validator.py` LLM |

### 6.2 執行層安全

- `execute_sql()`: 強制 `sql.upper().startswith("SELECT")`
- `execute_aql()`: 強制 `aql.upper().startswith("FOR") or startswith("RETURN")`
- Server DuckDB Cache: Rust 端 `execute_direct_sql()` 同樣有 SELECT-only 檢查

### 6.3 權限控制

- Data Agent 本身不做鑑權
- 由 TopOrchestrator 在 HandoffContext 中傳遞 `policy.allowed_collections`
- 艾企 Agent 負責根據 policy 過濾可查詢的表

---

## 7. 現有程式碼結構

```
ai-services/data_agent/
├── __init__.py
├── main.py                          # FastAPI 入口 (port 8003)
├── config_reader.py                 # 系統參數讀取（param_key → API → env fallback）
├── intent_rag/                      # 意圖 RAG 子模組
│   ├── router.py                    # /intent-rag/* 路由
│   ├── da_sync.py                   # 表達式同步
│   └── da_intents_sync.py           # 意圖同步
├── query/                           # 查詢子模組
│   ├── router.py                    # /query/* 路由 (676 行，需拆分)
│   └── nl2sql/                      # NL→SQL Pipeline
│       ├── orchestrator.py          # Pipeline 主流程 (214 行)
│       ├── intent_classifier.py     # Qdrant 意圖分類 (127 行)
│       ├── schema_retriever.py      # ArangoDB schema 檢索 (201 行)
│       ├── plan_generator.py        # 查詢計劃生成 (215 行)
│       ├── sql_generator.py         # 3-tier SQL 生成 (303 行)
│       ├── validator.py             # SQL 驗證 (225 行)
│       ├── executor.py              # DuckDB/AQL 執行 (221 行)
│       ├── models.py                # Pydantic 模型 (230 行)
│       ├── query_clarifier.py       # 查詢澄清 (167 行)
│       ├── reranker.py              # 意圖重排序 (91 行)
│       ├── error_explainer.py       # 錯誤解釋 (123 行)
│       ├── date_utils.py            # 日期工具 (149 行)
│       └── exceptions.py            # 自訂例外 (59 行)
└── ragic/                           # Ragic 整合子模組
    ├── router.py                    # /ragic/* 路由
    ├── router_import.py             # /ragic/import 路由
    ├── tool_calling_engine.py       # Tool calling 引擎
    ├── query_engine.py              # Ragic 查詢引擎
    ├── multi_step_orchestrator.py   # 多步驟編排
    ├── aggregation_builder.py       # 聚合建構器
    ├── schema_store.py              # Schema 向量儲存
    ├── intent_store.py              # Intent 向量儲存
    ├── arango_writer.py             # ArangoDB 寫入
    ├── config_loader.py             # Ragic 配置載入
    ├── client.py                    # Ragic API 客戶端
    ├── models.py                    # Ragic 模型
    ├── models_phase9.py             # Phase 9 擴展模型
    └── ...                          # 其他輔助模組
```

---

## 8. 效能指標

### 8.1 目標延遲

| 查詢類型 | 目標延遲 | 說明 |
|----------|----------|------|
| L1 瀏覽器 DuckDB | <100ms | 前端直接執行，不經網路 |
| L2 Server Cache SQL | <500ms | Rust 直接執行，無 LLM |
| L3 結構化查詢 | <3s | SQL 模型推理 + 執行 |
| L3 NL fallback | <10s | 完整 pipeline |

### 8.2 監控指標

- `sql_generation_time_ms`：SQL 模型推理耗時
- `sql_validation_attempts`：驗證重試次數
- `execution_time_ms`：查詢執行耗時
- `total_time_ms`：端到端耗時
- `model_used`：使用的模型（主模型 / 備用）
- `fallback_count`：觸發 fallback 次數

---

## 9. 與艾企 Agent 的互動協議

### 9.1 艾企呼叫 Data Agent 的時機

1. 用戶問資料查詢問題（如「品項管理有多少筆記錄？」）
2. 艾企判斷意圖為 data_query
3. 艾企根據前端上下文（tableId, fields, actionTrail）組結構化指令
4. 三層決策：
   - 表在瀏覽器 DuckDB + 簡單查詢 → 前端直接 `duckdbWasm.query()`
   - 表在 server cache → Rust `/api/v1/da/query/sql`
   - 複雜查詢 → Data Agent `/query/structured`

### 9.2 HandoffContext（從艾企傳入）

```json
{
  "table": "t_items_management",
  "table_id": "1018437",
  "table_name": "品項管理",
  "fields": [
    {"field_id": "1018438", "name": "品項名稱", "type": "text"},
    {"field_id": "1018439", "name": "價格", "type": "number"}
  ],
  "user_query": "品項管理中價格最高的前10筆",
  "source": "server_cache"
}
```

### 9.3 結果回傳格式

Data Agent 回傳結構化結果，艾企負責組成自然語言回覆給用戶。

```json
{
  "success": true,
  "generated_sql": "SELECT ...",
  "execution_result": {
    "rows": [...],
    "columns": [...],
    "row_count": 10,
    "execution_time_ms": 45.2
  },
  "model_used": "duckdb-nsql:latest",
  "total_time_ms": 1200.5
}
```

---

## 10. 未來擴展

| 階段 | 功能 | 說明 |
|------|------|------|
| Phase 1 | 結構化查詢端點 | `/query/structured` + SQL 模型整合 |
| Phase 2 | 查詢快取 | 相同結構化指令 → 快取 SQL + 結果 |
| Phase 3 | 查詢建議 | 根據表 schema 自動推薦常見查詢 |
| Phase 4 | 跨表查詢 | 多表 JOIN（需 schema relation 支援） |
| Phase 5 | 寫入操作 | 經審批的 INSERT/UPDATE（未來） |
