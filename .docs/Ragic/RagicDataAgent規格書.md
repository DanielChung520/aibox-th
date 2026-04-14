# RagicDataAgent 規格書

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-11 | 2.3.0 | Daniel Chung | Phase 1-8 全部實作完成，更新實作進度狀態 |
| 2026-04-11 | 2.2.0 | Daniel Chung | 新增顧問系統參數（企業規模、預算、安全需求） |
| 2026-04-11 | 2.1.0 | Daniel Chung | 改為 Ragic 系統管理模組儲存多客戶配置 |
| 2026-04-11 | 2.0.0 | Daniel Chung | 重構：移除 SAP/DuckDB/S3，改為純 Ragic API 直讀 + Qdrant |
| 2026-04-11 | 1.1.0 | Daniel Chung | 新增 Dayang 服務帳號配置 |
| 2026-04-11 | 1.0.0 | Daniel Chung | 初始版本 |

---

## 1. 定位與角色

### 1.1 服務定位

**RagicDataAgent** 是專門為 Ragic 資料庫設計的 Natural Language → Ragic API 查詢轉換工具，屬於 AIBox 效能工具（Performance Advisor）系列。

- **整合方式**：以 FastAPI service 形式存在，掛載於 Data Agent service 底下（`/ragic` 端點）
- **部署位置**：port 8003（與 Data Agent 共用）
- **核心能力**：將自然語言查詢轉換為 Ragic API 參數，直接呼叫 Ragic API 讀取資料
- **設計原則**：
  - Read-only 工具，只讀取資料，不寫入任何資料
  - **零資料同步**：不需將 Ragic 資料拉回本地
  - 即時查詢：每次查詢都是 Ragic 最新資料

### 1.2 與現有架構的關係

```
TopOrchestrator (意圖路由)
    └── Data Agent
            ├── /query        ← NL→SQL (已移除 SAP)
            ├── /advisor      ← 效能顧問
            └── /ragic        ← RagicDataAgent ⭐ (本文件)
```

### 1.3 能力邊界

| 能力 | 說明 |
|------|------|
| ✅ NL→Ragic API 參數轉換 | 將自然語言轉換為 `where`、`limit`、`order` 等參數 |
| ✅ 直接讀取 Ragic API | 不同步資料，每次查詢即時取得 |
| ✅ Schema + Intents 存 Qdrant | 向量檢索快速匹配意圖 |
| ✅ 多客戶支援 | 透過 Ragic 系統管理模組切換不同 Ragic 帳號 |
| ✅ 多種輸出格式 | 支援 JSON（預設）、CSV、Excel |
| ✅ 分頁處理 | 自動處理 Ragic 1000 筆上限的分頁 |
| ✅ 篩選條件翻譯 | 支援 eq、like、gte、lte、gt、lt、regex |
| ✅ 子表格處理 | 支援讀取子表格資料 |
| ❌ 不寫入資料 | 純顧問工具，只讀取 |
| ❌ 不同步資料 | 不拉回本地，零資料儲存 |

---

## 2. 系統架構

### 2.1 整體架構圖

```
┌─────────────────────────────────────────────────────────────────┐
│                    RagicDataAgent (port 8003)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────────┐ │
│  │ NL Parser   │────▶│  Qdrant     │────▶│ Ragic API Client │ │
│  │ (意圖解析)   │     │ (Intents +  │     │ (直接讀取)       │ │
│  │             │     │  Schema)     │     │                  │ │
│  └─────────────┘     └──────────────┘     └──────────────────┘ │
│         │                    │                     │              │
│         ▼                    ▼                     ▼              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Query Engine (查詢引擎)                 │   │
│  │  • NL → Ragic 參數翻譯                                  │   │
│  │  • 分頁邏輯                                              │   │
│  │  • 輸出格式轉換 (JSON/CSV/Excel)                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  API Response (回應)                      │   │
│  │  • records, record_count, pagination                      │   │
│  │  • execution_time_ms                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                    │                    │
                    ▼                    ▼
          ┌──────────────┐    ┌────────────────────────────┐
          │   Qdrant     │    │     Ragic Cloud API       │
          │ (向量儲存)   │    │  https://ap{15}.ragic.com│
          │ port 6333   │    │  直接讀取，無資料同步      │
          └──────────────┘    └────────────────────────────┘
```

### 2.2 與舊架構的差異

| 項目 | 舊架構 (NL→SQL) | 新架構 (RagicDataAgent) |
|------|------------------|--------------------------|
| **資料來源** | SAP (Parquet/S3) | Ragic API |
| **查詢方式** | DuckDB → S3 Parquet | 直接 call Ragic API |
| **Schema 儲存** | ArangoDB | Qdrant (向量檢索) |
| **Intents 儲存** | ArangoDB → Qdrant | Qdrant (直接) |
| **資料同步** | 需要（昂貴） | ❌ 不需要 |
| **設備成本** | 高（需大儲存） | ✅ 低（只存 Schema） |

### 2.3 目錄結構

```
ai-services/
├── data_agent/
│   └── ragic/                      # RagicDataAgent (與 Data Agent 整合)
│       ├── __init__.py
│       ├── client.py               # Ragic API 客戶端
│       ├── schema_store.py        # Qdrant Schema 儲存
│       ├── intent_store.py        # Qdrant Intent 儲存
│       ├── nl_parser.py           # 自然語言解析器
│       ├── query_engine.py        # 查詢引擎
│       ├── config_loader.py       # 從 Ragic 系統管理模組讀取配置
│       ├── models.py              # Pydantic 模型
│       ├── exceptions.py          # 自訂例外
│       └── router.py              # FastAPI 路由
│
└── datalake/                      # 僅保留 Schema Seed 腳本
    ├── seed_ragic_schema.py       # Ragic Schema 播種到 Qdrant
    └── seed_ragic_intents.py      # Ragic Intents 播種到 Qdrant
```

---

## 3. 設定管理

### 3.1 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `QDRANT_URL` | Qdrant URL | `http://localhost:6333` |
| `OLLAMA_BASE_URL` | Ollama API URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama 模型名稱 | `qwen2.5-coder:7b` |
| `RAGIC_DEFAULT_ACCOUNT` | 預設 Ragic 帳號 | `2025shianyong` |
| `RAGIC_MASTER_ACCOUNT` | 主控帳號（用於讀取系統管理配置） | `2025shianyong` |
| `RAGIC_MASTER_API_KEY` | 主控帳號的 API Key | — |

> **重要**：`RAGIC_MASTER_ACCOUNT` 和 `RAGIC_MASTER_API_KEY` 用於讀取「系統管理」模組中的多客戶配置。

### 3.2 多客戶設定（存於 Ragic 系統管理模組）

**配置統一存放在 Ragic 的「系統管理」模組**，無需獨立設定檔。

```
┌─────────────────────────────────────────────────────────┐
│  Ragic 系統管理模組 (ragic-setup/6)                     │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Ragic 多客戶設定表 (ragic-setup/6)              │   │
│  │                                                  │   │
│  │ account_name | api_key | server | enabled | ... │   │
│  │ -------------|---------|--------|---------|-----│   │
│  │ 2025shianyong| *****   | ap15  | true    | ... │   │
│  │ twbraun      | *****   | ap15  | true    | ... │   │
│  │ dayang       | *****   | ap13  | true    | ... │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 3.3 系統管理表單欄位

#### 表單：Ragic 多客戶設定（ragic-setup/6）

| 欄位 ID | 欄位名稱 | 類型 | 說明 |
|---------|----------|------|------|
| `account_name` | 帳號名稱 | 文字 | 唯一識別，如 `2025shianyong` |
| `api_key` | API Key | 文字 | Ragic API Key（加密儲存） |
| `server_prefix` | 伺服器前綴 | 文字 | 如 `ap15`、`ap13` |
| `enabled` | 啟用狀態 | 單選 | `啟用`、`停用` |
| `description` | 說明 | 文字 | 用途描述 |
| `created_at` | 建立時間 | 日期 | 自動記錄 |

#### 表單：Schema 快取設定（ragic-setup/6）

| 欄位 ID | 欄位名稱 | 類型 | 說明 |
|---------|----------|------|------|
| `schema_cache_ttl_hours` | 快取有效期（小時） | 數字 | 預設 `6` |
| `auto_sync_on_startup` | 啟動時自動同步 | 單選 | `是`、`否` |
| `ollama_model` | Ollama 模型 | 文字 | 預設 `qwen2.5-coder:7b` |

### 3.4 配置讀取流程

```python
class RagicConfigLoader:
    """從 Ragic 系統管理模組讀取配置"""
    
    def __init__(self, master_account: str, master_api_key: str):
        self.master_client = RagicAPIClient(
            account=master_account,
            api_key=master_api_key
        )
        self.cache = {}
    
    async def get_all_connections(self) -> list[dict]:
        """取得所有已啟用的 Ragic 連線設定"""
        # 從 Ragic 系統管理表單讀取
        records = await self.master_client.get_records(
            path="/ragic-setup",
            sheet_index=6,
            params={"where": "enabled,eq,啟用"}
        )
        return [self._parse_connection(r) for r in records]
    
    async def get_connection(self, account_name: str) -> dict | None:
        """取得特定帳號的設定"""
        records = await self.master_client.get_records(
            path="/ragic-setup",
            sheet_index=6,
            params={"where": "account_name,eq," + account_name}
        )
        if records:
            return self._parse_connection(records[0])
        return None
    
    def _parse_connection(self, record: dict) -> dict:
        """解析連線設定"""
        return {
            "name": record.get("account_name"),
            "account": record.get("account_name"),
            "api_key": record.get("api_key"),
            "server_prefix": record.get("server_prefix"),
            "enabled": record.get("enabled") == "啟用",
            "description": record.get("description", "")
        }
```

### 3.5 配置快取策略

| 策略 | TTL | 說明 |
|------|-----|------|
| 首次讀取 | — | 從 Ragic 系統管理模組讀取 |
| 後續讀取 | 5 分鐘 | 記憶體快取 |
| 強制更新 | — | 呼叫 `/ragic/config/reload` 清除快取 |

### 3.6 API Key 安全性

| 策略 | 說明 |
|------|------|
| **加密儲存** | API Key 在 Ragic 中可使用加密欄位 |
| **環境變數備援** | 也支援從環境變數讀取（`RAGIC_API_KEY_{ACCOUNT}`） |
| **最小權限** | 每個 Ragic 帳號建議使用專用 Service Account |

---

## 4. Qdrant 儲存結構

### 4.1 Collection 設計

| Collection | 用途 | Payload 包含 |
|------------|------|-------------|
| `ragic_schemas` | Schema 儲存與檢索 | account, table_key, table_name, fields, subtables |
| `ragic_intents` | Intent 匹配 | account, intent_id, nl_patterns, action, api_template |

### 4.2 Schema Document 結構

```json
{
  "id": "2025shianyong_configuration-file_10",
  "vector": [0.123, -0.456, ...],
  "payload": {
    "account": "2025shianyong",
    "table_key": "configuration-file/10",
    "table_name": "交易對象(客戶/供應商)",
    "tab_path": "/configuration-file",
    "sheet_index": 10,
    "version": "2026-04-11T10:00:00Z",
    "fields": {
      "1015575": {"name": "建檔對象", "type": "select", "options": ["客戶", "供應商"]},
      "1015577": {"name": "交易對象編碼", "type": "text"},
      "1015626": {"name": "交易狀態", "type": "select", "options": ["評估中", "交易中"]},
      "105": {"name": "建立日期", "type": "date"},
      "109": {"name": "最後更新", "type": "date"}
    },
    "subtables": {}
  }
}
```

### 4.3 Intent Document 結構

```json
{
  "id": "2025shianyong_intent_list_vendors",
  "vector": [0.789, -0.123, ...],
  "payload": {
    "account": "2025shianyong",
    "intent_id": "list_vendors",
    "nl_patterns": [
      "列出所有供應商",
      "查詢所有供應商",
      "取得供應商列表"
    ],
    "description": "列出所有交易對象中類型為供應商的資料",
    "action": "list",
    "table_key": "configuration-file/10",
    "filter_template": {
      "field_id": "1015575",
      "operator": "eq",
      "value": "供應商"
    },
    "api_template": "/{account}/configuration-file/10?api&naming=EID&where={field_id},{operator},{value}"
  }
}
```

---

## 5. API 規格

### 5.1 端點清單

| 方法 | 路徑 | 說明 |
|------|------|------|
| `POST` | `/ragic/query` | 自然語言查詢 Ragic 資料 |
| `GET` | `/ragic/query/records` | 直接用 Ragic 參數查詢 |
| `POST` | `/ragic/schema/tables` | 取得 Table Schema 清單 |
| `POST` | `/ragic/schema/tables/{table_key}` | 取得特定 Table 的 Schema |
| `POST` | `/ragic/schema/sync` | 手動觸發 Schema 同步（從 Ragic API） |
| `POST` | `/ragic/schema/diff` | 比對本地 Schema 與 Ragic 差異 |
| `POST` | `/ragic/intent/sync` | 同步 Intents 到 Qdrant |
| `POST` | `/ragic/config/reload` | 重新載入設定（清除快取） |
| `GET` | `/ragic/health` | 健康檢查 |

### 5.2 POST /ragic/query

**Request**：
```json
{
  "query": "找出所有供應商",
  "connection_name": "2025shianyong",
  "table_key": "configuration-file/10",
  "output_format": "json",
  "options": {
    "include_subtables": true,
    "limit": 100
  }
}
```

**Response**：
```json
{
  "code": 0,
  "data": {
    "query": "找出所有供應商",
    "intent_matched": {
      "intent_id": "list_vendors",
      "score": 0.92
    },
    "translated_params": {
      "where": [
        {"field_id": "1015575", "operator": "eq", "value": "供應商"}
      ],
      "limit": 100,
      "naming": "EID"
    },
    "records": [
      {
        "_ragicId": 502,
        "1015575": "供應商",
        "1015577": "S001",
        "1015578": "test公司"
      }
    ],
    "record_count": 1,
    "pagination": {
      "has_more": false,
      "total_pages": 1
    },
    "execution_time_ms": 850
  },
  "metadata": {
    "connection": "2025shianyong",
    "table_key": "configuration-file/10",
    "output_format": "json"
  }
}
```

### 5.3 GET /ragic/query/records

**Request**：
```
GET /ragic/query/records?connection=2025shianyong&table_key=configuration-file/10&where=1015575,eq,供應商&limit=100&naming=EID
```

### 5.4 POST /ragic/schema/sync

**用途**：從 Ragic API 取得 Schema 並更新到 Qdrant。

**Request**：
```json
{
  "connection_name": "2025shianyong",
  "table_keys": ["configuration-file/10"]
}
```

### 5.5 POST /ragic/intent/sync

**用途**：同步 Intents 到 Qdrant。

**Request**：
```json
{
  "connection_name": "2025shianyong"
}
```

---

## 6. 自然語言解析

### 6.1 NL → Ragic 參數轉換流程

```
1. 使用者 NL 輸入
       │
       ▼
2. Embedding (Ollama) → 向量
       │
       ▼
3. Qdrant Search (ragic_intents) → 匹配 Intent
       │
       ▼
4. 取出 Intent payload (filter_template, api_template)
       │
       ▼
5. Qdrant Search (ragic_schemas) → 取得 Table Schema
       │
       ▼
6. 組合 Ragic API URL + 參數
       │
       ▼
7. 直接呼叫 Ragic API → 取得資料
```

### 6.2 支援的 NL 模式

| 模式 | 範例 | 轉換結果 |
|------|------|----------|
| 簡單篩選 | 「找出狀態是已啟用的」 | `where=<status>,eq,已啟用` |
| 多重篩選 | 「找出狀態是已完成且金額大於1000的」 | `where=<status>,eq,已完成&where=<amount>,gt,1000` |
| 日期範圍 | 「找出2026年3月的資料」 | `where=<date>,gte,2026/03/01&where=<date>,lte,2026/03/31` |
| 模糊搜尋 | 「找出名稱包含「電腦」的品項」 | `where=<name>,like,電腦` |
| 排序指定 | 「找出最新建立的10筆」 | `order=<date>,DESC&limit=10` |
| 分頁指定 | 「取得第3頁，每頁50筆」 | `offset=100&limit=50` |
| 匯出格式 | 「匯出成 CSV」 | output_format=csv |

### 6.3 Intent 匹配 Prompt

```
你是 RagicDataAgent 的意圖分類器。
根據使用者的自然語言，查詢最匹配的 Intent。

【意圖庫】
{intents}

【規則】
1. 找出 NL 模式最匹配的 Intent
2. 回傳 Intent ID 和置信度
3. 若無匹配，回傳 null

【使用者輸入】
{user_query}

【輸出格式】
{
  "intent_id": "...",
  "score": 0.0~1.0,
  "params": {...}
}
```

---

## 7. Ragic API 客戶端

### 7.1 支援的 HTTP 方法

| 方法 | 用途 |
|------|------|
| `GET` | 讀取資料列表（主要） |
| `GET` (with ID) | 讀取單筆資料 |

### 7.2 直接讀取（不經過本地）

```python
class RagicAPIClient:
    def __init__(self, base_url: str, api_key: str, account: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.account = account

    async def get_records(
        self,
        path: str,
        sheet_index: int,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """直接呼叫 Ragic API，不做本地快取"""
        url = f"{self.base_url}/{self.account}/{path}/{sheet_index}"
        headers = {"Authorization": f"Basic {self.api_key}"}
        query_params = {"api": "", "naming": "EID"}
        if params:
            query_params.update(params)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers, params=query_params)
            response.raise_for_status()
            return response.json()
```

### 7.3 API 參數對照

| RagicDataAgent 參數 | Ragic API 參數 | 說明 |
|---------------------|----------------|------|
| `where` | `where` | 篩選條件，格式：`field_id,operator,value` |
| `limit` | `limit` | 每頁筆數，格式：`offset,limit` |
| `order` | `order` | 排序，格式：`field_id,ASC|DESC` |
| `naming` | `naming` | `EID`=欄位ID，`FNAME`=欄位名稱 |
| `subtables` | `subtables` | `0`=不包含子表格 |
| `info` | `info` | `true`=包含系統資訊 |
| `offset` | (在 limit 中) | 跳過筆數 |

---

## 8. 輸出格式

### 8.1 JSON（預設）

```json
{
  "code": 0,
  "data": {
    "records": [...],
    "record_count": 100
  }
}
```

### 8.2 CSV

```json
{
  "query": "...",
  "output_format": "csv"
}
```

**Response**：回傳 `Content-Type: text/csv` 的檔案下載。

### 8.3 Excel

```json
{
  "query": "...",
  "output_format": "excel"
}
```

**Response**：回傳 `.xlsx` 檔案下載。

---

## 9. 錯誤處理

### 9.1 錯誤碼

| 錯誤碼 | HTTP 狀態 | 說明 |
|--------|-----------|------|
| `RAGIC_SUCCESS` | 200 | 成功 |
| `RAGIC_PARAM_ERROR` | 400 | 參數錯誤 |
| `RAGIC_AUTH_FAILED` | 401 | API Key 無效或過期 |
| `RAGIC_FORBIDDEN` | 403 | 無存取權限 |
| `RAGIC_NOT_FOUND` | 404 | Table 或 Record 不存在 |
| `RAGIC_RATE_LIMITED` | 429 | 請求頻率過高（Ragic 限制：每秒 5 次） |
| `RAGIC_SERVER_ERROR` | 500 | Ragic 伺服器錯誤 |
| `RAGIC_TIMEOUT` | 504 | 請求超時 |

### 9.2 錯誤回應格式

```json
{
  "code": "RAGIC_AUTH_FAILED",
  "message": "API Key 無效或已過期",
  "details": {
    "connection": "2025shianyong",
    "suggestion": "請更新 RAGIC_API_KEY_2025SHIANYONG 環境變數"
  }
}
```

---

## 10. 多客戶支援

### 10.1 客戶切換流程

```
1. 使用者指定 connection_name 或使用預設帳號
       │
       ▼
2. 從 Ragic 系統管理模組讀取該帳號設定
       │
       ▼
3. 用該帳號的 API Key + Server Prefix 建構 URL
       │
       ▼
4. 直接呼叫 Ragic API
```

### 10.2 預設帳號

若未指定 `connection_name`，使用 `RAGIC_DEFAULT_ACCOUNT`（預設：`2025shianyong`）。

### 10.3 管理介面

多客戶設定透過 Ragic 原生介面管理：

```
┌─────────────────────────────────────────────────────────────┐
│  Ragic 系統管理 - 多客戶設定表                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  帳號名稱      │ API Key     │ 伺服器 │ 啟用 │ 說明      │
│  ──────────────┼─────────────┼────────┼──────┼────────── │
│  2025shianyong │ *********** │ ap15  │ 啟用 │ 主要業務  │
│  twbraun       │ *********** │ ap15  │ 啟用 │ 測試環境  │
│  dayang        │ *********** │ ap13  │ 停用 │ 服務帳號  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 10.4 AI 管理功能

透過自然語言管理多客戶設定：

| NL 指令 | 對應操作 |
|---------|----------|
| 「新增一個 Ragic 帳號」 | 新增一筆設定記錄 |
| 「停用 twbraun 帳號」 | 更新 enabled=停用 |
| 「更新 dayang 的 API Key」 | 更新 api_key 欄位 |
| 「列出所有啟用的帳號」 | 查詢並回傳 |

### 10.5 設定變更生效

| 變更類型 | 生效方式 |
|----------|----------|
| 新增帳號 | 立即生效（快取 5 分鐘後更新） |
| 停用帳號 | 立即生效 |
| 更新 API Key | 立即生效 |
| 強制生效 | 呼叫 `POST /ragic/config/reload` 清除快取 |

---

## 11. 分層架構（共享 + 隔離）

### 11.1 分層設計

```
Qdrant Collections
│
├── 共享層 (ragic_schemas / ragic_intents)
│   └── Standard Fields (1015xxx 系列)
│
└── 帳號隔離層
    ├── 2025shianyong_*
    │   └── 帳號特定 Schema + Intents
    │
    ├── twbraun_*
    │   └── 帳號特定 Schema + Intents
    │
    └── dayang_*
        └── 帳號特定 Schema + Intents
```

### 11.2 向量檢索策略

```python
async def search_schema(query_vector: list[float], account: str) -> list[dict]:
    """搜尋 Schema，優先回傳該帳號的結果"""
    results = await qdrant.search(
        collection="ragic_schemas",
        vector=query_vector,
        limit=10,
        score_threshold=0.5
    )
    
    # 過濾：优先返回匹配帳號的結果
    account_results = [r for r in results if r.payload.get("account") == account]
    if account_results:
        return account_results
    
    # 若無匹配，回傳其他帳號
    return results
```

---

## 12. Ragic API 限制

| 限制項目 | 說明 |
|----------|------|
| HTTPS 強制 | 所有請求必須使用 HTTPS |
| 預設分頁 | 最多回傳 1000 筆 |
| API Key 權限 | API Key 擁有該使用者的所有權限 |
| 佇列限制 | 每帳號最多 50 個 API 請求排隊 |
| 請求頻率 | **超過每秒 5 次會觸發人工審核** |
| 日期格式 | 必須使用 `yyyy/MM/dd` 或 `yyyy/MM/dd HH:mm:ss` |

---

## 13. 實作規劃

| Phase | 內容 | 優先度 | 狀態 |
|-------|------|--------|------|
| **Phase 1** | 建立 RagicAPIClient（直接讀取）+ 基本 GET 查詢 | P0 | ✅ 完成 |
| **Phase 2** | Qdrant Schema Store（讀寫） | P0 | ✅ 完成 |
| **Phase 3** | Qdrant Intent Store（讀寫） | P0 | ✅ 完成 |
| **Phase 4** | NL Parser（意圖分類 + 參數翻換） | P1 | ✅ 完成 |
| **Phase 5** | Query Engine（分頁、格式化） | P1 | ✅ 完成 |
| **Phase 6** | 多格式輸出（JSON/CSV/Excel） | P2 | ✅ 完成 |
| **Phase 7** | 多客戶支援（Ragic 系統管理模組） | P2 | ✅ 完成 |
| **Phase 8** | Schema Sync（從 Ragic API 同步） | P2 | ✅ 完成 |

---

## 14. 與 Data Agent 的整合

### 14.1 掛載方式

```python
# ai-services/data_agent/main.py
from data_agent.ragic import router as ragic_router

app.include_router(ragic_router, prefix="/ragic", tags=["ragic"])
```

### 14.2 與現有 Pipeline 的差異

| 項目 | 舊 Pipeline | RagicDataAgent |
|------|-------------|----------------|
| **入口** | `/query` | `/ragic/query` |
| **意圖分類** | NL→SQL Intent Classifier | NL→Ragic Intent Classifier |
| **Schema 來源** | ArangoDB | Qdrant |
| **查詢執行** | DuckDB → S3 Parquet | Ragic API (直接) |
| **回應格式** | SQLResult | RagicResponse |

---

## 附錄 A：Dayang 服務帳號資訊

> **建立時間**：2026/04/11 11:37:32（台北時間 UTC+8）

| 欄位 | 內容 |
|------|------|
| **帳號名稱** | `dayang` |
| **Server Prefix** | `ap15`（實際為 ap13，需確認） |
| **API Key** | `SG8zMTk0NEZCN3NONFgxUmJMTi9rRzlxbWoxSXN5SXM5eUVwbm12WU1rV2lPMVRTajBxTEp4UE5qM0wvU0N0bWMySGVFNWk2N3QzSXdKaisvZHR0SlE9PQ` |

---

## 附錄 B：2025shianyong Schema 現況

| 頁籤 | 表格數 | 狀態 |
|------|--------|------|
| 基本資料維護檔 | 1 | ✅ 已確認 |
| 進銷存表單 | 1 | ✅ 已確認 |
| Ragic系統管理 | 1 | ✅ 已確認 |
| ISO表單範本 | 1 | ✅ 已確認 |
| SCM | 2 | ✅ 已確認 |
| 採購(測試) | 2 | ✅ 已確認 |
| CRM | 3 | ✅ 已確認 |
| 客戶端問卷 | 1 | ✅ 已確認 |
| 活動管理 | 4 | ✅ 已確認 |
| **總計** | **16** | |

> **注意**：目前 API Key 權限受限，完整結構（278+ sheets）需用管理員 API Key 才能看到。

---

## 附錄 C：顧問系統參數（預設）

顧問系統根據企業規模、使用者規模、預算及安全需求，提供不同方案。以下是預設的參數：

### C.1 部署參數

| 參數 | 說明 | 預設值 | 範例 |
|------|------|--------|------|
| `DEPLOYMENT_ID` | 部署唯一識別 | — | `dept-001`、`cloud-tw` |
| `DEPLOYMENT_MODE` | 部署類型 | `cloud` | `on-premise`、`cloud` |
| `DEPLOYMENT_SECRET` | 部署密鑰（用於驗證） | — | `openssl rand -hex 32` |
| `TENANT_ID` | 租戶識別 | — | `twbraun`、`2025shianyong` |

### C.2 企業規模參數

| 參數 | 說明 | 預設值 | 方案影響 |
|------|------|--------|----------|
| `COMPANY_SIZE` | 企業規模 | `smb` | 影響部署硬體規格 |
| `USER_COUNT` | 使用者人數 | `10` | 影響併發數限制 |
| `RAGIC_ACCOUNTS` | Ragic 帳號數量 | `1` | 影響連線池大小 |
| `DATA_VOLUME` | 預估資料量 | `small` | `small` / `medium` / `large` |

#### COMPANY_SIZE 選項

| 值 | 說明 | 建議部署 |
|------|------|----------|
| `micro` | 1-5 人 | 共享 VPS 或最小規格 |
| `smb` | 6-50 人 | 標準 VPS |
| `mid` | 51-200 人 | 中等規格獨立部署 |
| `enterprise` | 200+ 人 | 企業級獨立部署 |

### C.3 預算參數

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `BUDGET_TIER` | 預算等級 | `standard` |
| `MAX_MONTHLY_COST` | 每月預算上限（USD） | `500` |

#### BUDGET_TIER 選項

| 值 | 說明 | 包含功能 |
|------|------|----------|
| `basic` | 基本方案 | NL 查詢、基础報表 |
| `standard` | 標準方案 | NL 查詢、報表、分析 |
| `premium` | 高級方案 | NL 查詢、報表、分析、API |
| `enterprise` | 企業方案 | 全功能 + 優先支援 |

### C.4 安全需求參數

| 參數 | 說明 | 預設值 | 選項 |
|------|------|--------|------|
| `SECURITY_LEVEL` | 安全等級 | `standard` | `basic`、`standard`、`high`、`max` |
| `DATA_RESIDENCY` | 資料存放地 | `taiwan` | `taiwan`、`singapore`、`us`、`eu` |
| `REQUIRE_VPN` | 是否需要 VPN | `false` | `true`、`false` |
| `AUDIIT_LOG` | 是否啟用審計日誌 | `true` | `true`、`false` |

#### SECURITY_LEVEL 選項

| 值 | 說明 | 功能 |
|------|------|------|
| `basic` | 基本安全 | HTTPS、 기본認證 |
| `standard` | 標準安全 | HTTPS、API Key、審計日誌 |
| `high` | 高安全 | VPN、IP 白名單、雙重認證 |
| `max` | 最高安全 | 硬體加密、隔離網路、SOC2 |

### C.5 資源配置參數（自動計算）

| 參數 | 說明 | 計算公式 |
|------|------|----------|
| `QDRANT_MEMORY` | Qdrant 記憶體 | `USER_COUNT * 100MB`（最小 512MB） |
| `OLLAMA_GPU` | 是否需要 GPU | `USER_COUNT > 50 ? true : false` |
| `MAX_CONCURRENT_QUERIES` | 最大併發查詢 | `USER_COUNT * 2` |
| `RATE_LIMIT_RPM` | 每分鐘頻率限制 | `MAX_CONCURRENT_QUERIES * 0.5` |

### C.6 方案組合建議

| 方案 | 規模 | 預算 | 安全 | 建議配置 |
|------|------|------|------|----------|
| `micro-cloud-basic` | micro | basic | basic | 共享 VPS、最小資源 |
| `smb-cloud-standard` | smb | standard | standard | 標準 VPS、獨立 Qdrant |
| `mid-cloud-premium` | mid | premium | high | 中等規格、GPU 加速 |
| `enterprise-onprem-max` | enterprise | enterprise | max | 獨立伺服器、VPN、隔離 |

### C.7 環境變數範例

```bash
# ============ 部署基本資訊 ============
DEPLOYMENT_ID=prod-taiwan-smb-001
DEPLOYMENT_MODE=cloud
DEPLOYMENT_SECRET=a1b2c3d4e5f6...(產生方式: openssl rand -hex 32)
TENANT_ID=twbraun

# ============ 企業規模 ============
COMPANY_SIZE=smb
USER_COUNT=25
RAGIC_ACCOUNTS=3
DATA_VOLUME=medium

# ============ 預算與安全 ============
BUDGET_TIER=standard
MAX_MONTHLY_COST=300
SECURITY_LEVEL=standard
DATA_RESIDENCY=taiwan
REQUIRE_VPN=false
AUDIT_LOG=true

# ============ 自動計算（請勿手動修改）===========
# QDRANT_MEMORY=2048MB (USER_COUNT * 100MB, min 512MB)
# OLLAMA_GPU=false (USER_COUNT <= 50)
# MAX_CONCURRENT_QUERIES=50 (USER_COUNT * 2)
# RATE_LIMIT_RPM=25 (MAX_CONCURRENT_QUERIES * 0.5)
```

### C.8 部署 Secret 產生方式

```bash
# 方式 1: OpenSSL
openssl rand -hex 32

# 方式 2: Python
python3 -c "import secrets; print(secrets.token_hex(32))"

# 方式 3: macOS
cat /dev/urandom | head -c 32 | xxd -p -c 32
```

---

## 附錄 D：Ragic API 關鍵限制摘要

| 限制項目 | 說明 |
|----------|------|
| HTTPS 強制 | 所有請求必須使用 HTTPS |
| 預設分頁 | 最多回傳 1000 筆 |
| API Key 權限 | API Key 擁有該使用者的所有權限 |
| 佇列限制 | 每帳號最多 50 個 API 請求排隊 |
| 請求頻率 | 超過每秒 5 次會觸發人工審核 |
| 日期格式 | 必須使用 `yyyy/MM/dd` 或 `yyyy/MM/dd HH:mm:ss` |

---

## 附錄 D：移除的元件（相較舊架構）

| 移除項目 | 舊位置 | 移除原因 |
|----------|--------|----------|
| SAP NL→SQL Pipeline | `data_agent/query/nl2sql/` | 只支援 Ragic |
| DuckDB | `executor.py` | 不需要本地查詢 |
| S3/MinIO | `datalake/generate_*.py` | 不同步資料 |
| SeaWeedFS Parquet | `tools/report_agent/` | 不需要 |
| ArangoDB Schema | `datalake/seed_schema.py` | 改用 Qdrant |
