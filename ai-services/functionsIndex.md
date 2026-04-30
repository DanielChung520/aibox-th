---
lastUpdate: 2026-04-30 01:30:00
author: Daniel Chung
version: 1.0.0
---

# functionsIndex.md — AI Services 複用函式索引

本文件記錄所有 AI Services 中可複用的標準函式，供 Agent 開發時直接引用。**未來所有新開發的複用函式都必須記錄於此**，避免重複實作。

---

## 📋 函式清單

| 函式 | 模組路徑 | 用途 | 適用場景 |
|------|----------|------|----------|
| `resolve_llm_config` | `shared/llm_resolver.py` | Model ID → provider → base_url + api_key 統一解析 | 任何需要呼叫 LLM 的服務 |
| `RagicCache` | `shared/ragic_cache.py` | Ragic 資料通用快取讀寫（含 Table Lock 防 Stampeding） | 任何需要快取 Ragic 資料的 Skill |

---

## 🗂️ 函式詳細規格

---

### RagicCache

**模組**：`shared/ragic_cache.py`

**用途**：對 Ragic 任一資料表（全部 263 張）進行通用快取讀寫。支援 TTL 失效、背景自動刷新、欄位對應。

**為什麼需要**：
- `product_cache` 只適用 STOCK_16，且儲存格式為字串，無法結構化查詢
- 263 張表不能各自建立獨立快取集合
- `da_table_data_ragic` 是原始資料，無快取 TTL

**集合設計**：`ragic_cache`（單一集合，多張表共用）

```json
{
  "_key": "STOCK_16",           // Ragic 表名
  "table_id": "STOCK_16",
  "table_name_cn": "庫存表",
  "row_count": 30,
  "field_mapping": {             // 欄位 ID → 人類可讀名稱
    "1018133": "品項名稱",
    "1018271": "庫存數量",
    "1018130": "單位"
  },
  "rows": [
    {
      "_key": "row-001",
      "品項名稱": "帶皮薑頭原料",
      "庫存數量": 1000,
      "單位": "公克(g)",
      "_raw": { "1018133": "帶皮薑頭原料", "1018271": 1000, "1018130": "公克(g)" }
    }
  ],
  "cached_at": "2026-04-29T11:36:38Z",
  "updated_at": "2026-04-29T11:36:38Z",
  "ttl_seconds": 3600
}
```

**核心方法**：

| 方法 | 參數 | 回傳 | 說明 |
|------|------|------|------|
| `read(table_id)` | `table_id: str` | `dict \| None` | 讀取快取，TTL 內直接回傳，過期回 None |
| `write(table_id, rows, field_mapping)` | 表名、資料列、欄位對應 | `bool` | 寫入快取（UPSERT） |
| `refresh(table_id)` | `table_id: str` | `bool` | 強制從 Ragic API 重新拉取並寫入 |
| `is_fresh(table_id)` | `table_id: str` | `bool` | 檢查快取是否在 TTL 內 |
| `delete(table_id)` | `table_id: str` | `bool` | 刪除快取 |

**使用範例**：

```python
from shared.ragic_cache import RagicCache

cache = RagicCache()

# 讀取快取（自動處理 TTL）
data = await cache.read("STOCK_16")
if data is None:
    # TTL 過期或無快取，主動刷新
    await cache.refresh("STOCK_16")
    data = await cache.read("STOCK_16")

# 直接刷新（強制從 Ragic 拉取）
await cache.refresh("STOCK_16")

# 查詢特定欄位（結構化好，可以做篩選）
for row in data["rows"]:
    if row["品項名稱"].startswith("牛肉"):
        print(row["庫存數量"], row["單位"])
```

**相依服務**：

| 服務 | 用途 |
|------|------|
| ArangoDB `ragic_cache` 集合 | 快取儲存 |
| Rust API `/api/v1/da/ragic/proxy/{table_key}/data` | Ragic 原始資料讀取 |
| ArangoDB `da_field_info_ragic` | 欄位 ID → 名稱對應 |

**TTL 設定**：
- 預設 3600 秒（1 小時）
- 可透過 `system_params` 的 `ragic.cache.ttl_seconds` 動態調整

**注意事項**：
- `rows` 內的欄位名稱已從 `field_mapping` 對應為人類可讀
- `_raw` 保留原始 Ragic 欄位 ID，方便未來擴充
- `row_count` 為快取當下的資料列數，供監控使用

---

### resolve_llm_config

**模組**：`shared/llm_resolver.py`

**用途**：統一解析 Model ID（如 `deepseek:DeepSeek-V4-Flash` 或 `llama3.2:latest`）→ provider → base_url + api_key。從 `system_params` 的 `llm.providers` 讀取 provider 設定，自動構建正確的 API endpoint。

**為什麼需要**：
- 每個呼叫 LLM 的服務不應各自實作 provider 解析邏輯（已有 `aitask/main.py` 和 `llm_analyzer.py` 兩套重複實作）
- 新增 provider 時只需更新 `llm.providers` system_params，無需改程式碼
- 自動處理 Ollama (`/api/chat`) vs OpenAI-compatible (`/v1/chat/completions`) 的路徑差異

**核心方法**：

| 方法 | 參數 | 回傳 | 說明 |
|------|------|------|------|
| `resolve(model_id)` | `model_id: str` | `ResolvedLLMConfig` | 解析 Model ID，回傳 endpoint / model_name / api_key |
| `invalidate_cache()` | — | `None` | 清除內部快取（providers + api_key） |

**ResolvedLLMConfig 結構**：

```python
class ResolvedLLMConfig(BaseModel):
    provider: str       # e.g. "deepseek", "ollama"
    model_name: str     # e.g. "DeepSeek-V4-Flash", "llama3.2:latest"
    endpoint: str       # e.g. "https://api.deepseek.com/v1/chat/completions"
    api_key: str        # resolved from system_params if api_key_param is set
    base_url: str       # raw base_url from provider config
```

**使用範例**：

```python
from shared.llm_resolver import resolve as resolve_llm

# 從工具設定取得 model_id（如 "deepseek:DeepSeek-V4-Flash"）
model_id = tool_config.get("llm_model", "llama3.2:latest")

# 解析
config = await resolve_llm(model_id)

# 發送請求
if config.endpoint.endswith("/api/chat"):
    # Ollama 格式
    resp = await client.post(config.endpoint, json={
        "model": config.model_name,
        "messages": [...],
    })
else:
    # OpenAI-compatible 格式
    resp = await client.post(config.endpoint,
        json={"model": config.model_name, "messages": [...]},
        headers={"Authorization": f"Bearer {config.api_key}"},
    )
```

**相依服務**：

| 服務 | 用途 |
|------|------|
| Rust API `/api/v1/system-params/llm.providers` | Provider 設定（base_url + api_key_param） |
| Rust API `/api/v1/system-params/{api_key_param}` | API key 查詢 |

**URL 構建規則**：

| Provider base_url 範例 | 結果 endpoint |
|------------------------|---------------|
| `http://localhost:11434` | `http://localhost:11434/api/chat` |
| `http://localhost:11434/api/chat` | 直接使用 |
| `https://api.deepseek.com/v1` | `https://api.deepseek.com/v1/chat/completions` |
| `https://api.deepseek.com/v1/chat/completions` | 直接使用 |

**⚠️ 嚴禁**：各服務不應再自行實作 provider 解析、URL 拼接、API key 查詢 — 一律透過此函式。

---

## 🔧 新增函式指南

新增複用函式時，請依序完成以下步驟：

1. **實作函式**：放在 `ai-services/shared/` 對應子目錄
2. **建立 `__init__.py` 導出**：若為新目錄，需建立 `__init__.py`
3. **填寫上方表格**：列名、模組路徑、用途、適用場景
4. **填寫上方詳細規格**：包含參數、回傳、範例、相依服務
5. **通過品質檢查**：`ruff check` + `mypy --strict`

---

## 📝 修改記錄

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-30 | 1.0.0 | Daniel Chung | 初始版本，新增 RagicCache |
