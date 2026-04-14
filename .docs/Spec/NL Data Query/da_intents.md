# da_intents Collection 設計規格

## 三層架構

### 1. 感知層 (Perception Layer)
負責將自然語言轉化為系統的「直覺」，解決選錯表的問題。

| 欄位 | 類型 | 說明 |
|------|------|------|
| `nl_examples` | list[string] | 場景範例池，如「查詢料號庫存數」、「統計三月交易量」|
| `action` | string | 動作意圖：query / count / sum / update |
| `domain` | string | 業務領域：inventory / sales / finance / crm / contract |

### 2. 對策層 (Strategy Layer)
當系統確認目標後，決定 Agent 該如何精確執行。

| 欄位 | 類型 | 說明 |
|------|------|------|
| `table_key` | string | 目標對象（如 erp/52）|
| `query_type` | string | 執行路徑：simple_filter（Path A）/ aggregate（Path B）|
| `tool_schema` | object | 該表欄位的 JSON Schema Enum，確保 LLM 不會產生欄位幻覺 |

### 3. 學習層 (Learning Layer)
在運行中累積訓練資料。

| 欄位 | 類型 | 說明 |
|------|------|------|
| `expected_output` | object | 預期 JSON 結果（如 {"field_id": "123", "operator": "eq"}）|
| `golden_sql` | string | 經過驗證的正確 SQL 範本 |
| `user_feedback_score` | number | 使用者對此查詢結果的滿意度 |
| `difficulty_level` | string | 難度標記：easy / medium / hard |

---

## 範例文件

```json
{
  "intent_id": "inv_stock_query_001",
  "agent_scope": "data_agent",
  "name": "料號庫存查詢",
  "description": "針對特定料號查詢目前在庫數量",

  // 感知層
  "nl_examples": [
    "查詢料號庫存數",
    "目前 A123 的庫存是多少",
    "幫我查一下料號交易數與庫存"
  ],
  "action": "query",
  "domain": "inventory",

  // 對策層
  "table_key": "inv/stock_table",
  "query_type": "simple_filter",
  "tool_schema": {
    "type": "object",
    "properties": {
      "filters": {
        "items": {
          "properties": {
            "field_id": { "enum": ["料號ID", "庫存數", "倉庫編號"] }
          }
        }
      }
    }
  },

  // 學習層
  "expected_output": {
    "filters": [{"field_id": "料號ID", "operator": "eq", "value": "A123"}]
  },
  "golden_sql": "SELECT stock_qty FROM inv_table WHERE part_no = 'A123'",
  "difficulty_level": "easy"
}
```

---

## Collection 現況

| Collection | 用途 | 狀態 |
|------------|------|------|
| `da_tables` | Schema 定義（fields, capabilities, relationships）| ✅ 已建立 |
| `da_expressions` | 前端頁面管理（舊格式）| ⚠️ 維護中 |
| `da_intents` | 新設計的三層意圖 collection | 🔄 建構中 |
| `da_table_relation_ragic` | FK 圖譜 | ✅ 已有 |

---

## 新增欄位說明

| 欄位 | 說明 |
|------|------|
| `action` | 動作意圖：query（查詢）/ count（計數）/ sum（加總）/ update（更新）|
| `domain` | 業務領域標籤，用於縮小搜索範圍 |
| `tool_schema` | JSON Schema，含 field_id enum 約束，防止 LLM 幻覺 |
| `expected_output` | 黃金標準輸出，用於未來微調 |
| `golden_sql` | 驗證過的標準 SQL |
| `difficulty_level` | 難度：easy / medium / hard |

---

## 相關檔案

- `ai-services/data_agent/intent_rag/da_intents_sync.py` - 同步腳本
- `ai-services/data_agent/ragic/intent_store.py` - Qdrant client
- `.docs/Spec/NL Data Query/Sales模組_da_intents設計方案.md` - Sales 模組設計
