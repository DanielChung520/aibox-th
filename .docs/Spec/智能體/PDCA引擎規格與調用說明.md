# PDCA 引擎規格與調用說明

## 概述

PDCA（Plan-Do-Check-Act）是企業級任務執行品質管理框架，導入到 AI Agent 執行流程中，確保每一個任務步驟在執行前經過審查、執行後經過驗證，形成完整的品質閉環。

本引擎透過 Ollama LLM 對每個步驟進行兩道品質把關：

- **Plan 審查**：在步驟執行前，檢查計畫是否合理、目標是否明確、方法是否可行。
- **Check 審查**：在步驟執行後，驗證結果是否符合預期、是否有遺漏或錯誤。

當審查結果為非 Approved（包含 Rejected、Clarify、Escalate）時，引擎會自動將 Todo 暫停，記錄 verdict 與摘要，等待人工介入或修正後再繼續。

這樣的設計讓 AI Agent 在自主執行的同時，保留人類監督的節點，適合需要高可靠度的企業場景。

---

## 核心概念

### Todo

Todo 是一組有序步驟的集合，代表一個可被執行的任務單元。每個 Todo 有自己的生命週期狀態，以及 PDCA 相關的審查記錄。

**狀態流：**

```
pending → running → completed
                  ↘ failed
                  ↘ paused
```

- **pending**：剛建立，尚未開始執行。
- **running**：正在執行中，至少有一個步驟在進行。
- **completed**：所有步驟皆完成，Todo 結束。
- **failed**：步驟執行失敗，Todo 終止。
- **paused**：因 PDCA 審查未通過而暫停，等待人工介入。

**PDCA 相關欄位：**

| 欄位 | 說明 |
|------|------|
| `pdca_verdict` | 最近一次 PDCA 審查的結果（Approved / Rejected / Clarify / Escalate） |
| `pdca_summary` | 審查摘要，說明核准或拒絕的原因 |

### Step

Todo 由多個步驟組成，依 `step_index` 順序執行。每一個步驟可以是不同的類型（例如一般操作、LLM 呼叫、API 請求等），並且各自獨立記錄執行狀態與結果。

**狀態流：**

```
pending → running → completed
                  ↘ failed
                  ↘ skipped
```

- **pending**：等待執行。
- **running**：正在執行中。
- **completed**：執行成功，可記錄 result。
- **failed**：執行失敗，需記錄 error 訊息。
- **skipped**：被跳過（例如條件不符時）。

### PDCA Verdict

當引擎呼叫 Ollama LLM 進行審查時，會得到以下四種 verdict：

| Verdict | 含義 | 對 Todo 的影響 |
|---------|------|----------------|
| **Approved** | 審查通過 | 繼續執行，不做任何干預 |
| **Rejected** | 計畫或結果被拒絕 | Todo 暫停（paused），記錄拒絕原因 |
| **Clarify** | 需要澄清 | Todo 暫停（paused），記錄需要釐清的問題 |
| **Escalate** | 需要升級處理 | Todo 暫停（paused），記錄升級原因（例如超出權限或資源不足） |

前三種 verdict 可透過 `revise` 或 `clarify` API 恢復執行。Escalate 通常需要更高權限的管理者介入。

---

## API 端點參考

以下所有端點以 `http://localhost:6500` 為基底 URL。

---

### Core CRUD

#### 1. POST /api/v1/todos — 建立 Todo

建立一個新的 Todo，包含標題、描述、優先級、標籤以及步驟陣列。

**Request Body：**

```json
{
  "title": "撰寫季度財報分析報告",
  "description": "蒐集 Q2 財務數據並產出分析報告",
  "priority": "high",
  "tags": ["財務", "季度報告"],
  "steps": [
    {
      "step_title": "蒐集財務數據",
      "step_type": "data_collection"
    },
    {
      "step_title": "分析數據趨勢",
      "step_type": "analysis"
    },
    {
      "step_title": "產出報告",
      "step_type": "generation"
    }
  ]
}
```

**Response（201 Created）：**

```json
{
  "success": true,
  "data": {
    "_key": "todo_001",
    "todo_no": "TD-20260515-0001",
    "title": "撰寫季度財報分析報告",
    "description": "蒐集 Q2 財務數據並產出分析報告",
    "status": "pending",
    "priority": "high",
    "current_step_index": 0,
    "total_steps": 3,
    "progress": 0,
    "tags": ["財務", "季度報告"],
    "pdca_verdict": null,
    "pdca_summary": null,
    "created_at": "2026-05-15T10:00:00Z",
    "updated_at": "2026-05-15T10:00:00Z"
  }
}
```

**curl 範例：**

```bash
curl -X POST http://localhost:6500/api/v1/todos \
  -H "Content-Type: application/json" \
  -d '{
    "title": "撰寫季度財報分析報告",
    "description": "蒐集 Q2 財務數據並產出分析報告",
    "priority": "high",
    "tags": ["財務", "季度報告"],
    "steps": [
      {"step_title": "蒐集財務數據", "step_type": "data_collection"},
      {"step_title": "分析數據趨勢", "step_type": "analysis"},
      {"step_title": "產出報告", "step_type": "generation"}
    ]
  }'
```

**備註：**
- `_key` 由系統自動產生，可用於後續操作。
- `todo_no` 為可讀性編號，格式為 `TD-YYYYMMDD-序列`。
- `steps` 陣列中的步驟會自動依序賦予 `step_index`（從 0 開始）。

---

#### 2. GET /api/v1/todos — 列出 Todos

取得所有 Todo 列表，支援依狀態與優先級篩選。

**Query Parameters：**

| 參數 | 型態 | 說明 |
|------|------|------|
| `status` | string | 篩選狀態：pending / running / completed / failed / paused |
| `priority` | string | 篩選優先級：low / medium / high / critical |

**Response（200 OK）：**

```json
{
  "success": true,
  "data": [
    {
      "_key": "todo_001",
      "todo_no": "TD-20260515-0001",
      "title": "撰寫季度財報分析報告",
      "status": "pending",
      "priority": "high",
      "current_step_index": 0,
      "total_steps": 3,
      "progress": 0,
      "pdca_verdict": null,
      "created_at": "2026-05-15T10:00:00Z"
    },
    {
      "_key": "todo_002",
      "todo_no": "TD-20260515-0002",
      "title": "更新客戶聯絡資訊",
      "status": "running",
      "priority": "medium",
      "current_step_index": 1,
      "total_steps": 2,
      "progress": 50,
      "pdca_verdict": "Approved",
      "created_at": "2026-05-15T09:30:00Z"
    }
  ],
  "total": 2
}
```

**curl 範例：**

```bash
# 列出所有 Todos
curl http://localhost:6500/api/v1/todos

# 篩選狀態為 running 的 Todos
curl "http://localhost:6500/api/v1/todos?status=running"

# 篩選優先級為 high 的 Todos
curl "http://localhost:6500/api/v1/todos?priority=high"

# 多重篩選
curl "http://localhost:6500/api/v1/todos?status=paused&priority=high"
```

**備註：**
- 不傳入任何篩選參數時，回傳所有 Todo。
- 結果依 `created_at` 降序排列。

---

#### 3. GET /api/v1/todos/{key} — 查詢單一 Todo

根據 `_key` 取得特定 Todo 的詳細資訊。

**Query Parameters：**

| 參數 | 型態 | 說明 |
|------|------|------|
| `steps` | boolean | 設為 `true` 時一併回傳步驟列表 |

**Response（200 OK）：**

```json
{
  "success": true,
  "data": {
    "_key": "todo_001",
    "todo_no": "TD-20260515-0001",
    "title": "撰寫季度財報分析報告",
    "description": "蒐集 Q2 財務數據並產出分析報告",
    "status": "running",
    "priority": "high",
    "current_step_index": 1,
    "total_steps": 3,
    "progress": 33,
    "pdca_verdict": "Approved",
    "pdca_summary": "計畫完整，步驟合理，核准執行。",
    "tags": ["財務", "季度報告"],
    "created_at": "2026-05-15T10:00:00Z",
    "updated_at": "2026-05-15T10:05:00Z",
    "steps": [
      {
        "_key": "step_001",
        "todo_key": "todo_001",
        "step_index": 0,
        "step_title": "蒐集財務數據",
        "step_type": "data_collection",
        "status": "completed",
        "result": "成功取得 Q2 財務報表",
        "error": null,
        "started_at": "2026-05-15T10:01:00Z",
        "completed_at": "2026-05-15T10:03:00Z",
        "duration_ms": 120000
      },
      {
        "_key": "step_002",
        "todo_key": "todo_001",
        "step_index": 1,
        "step_title": "分析數據趨勢",
        "step_type": "analysis",
        "status": "running",
        "result": null,
        "error": null,
        "started_at": "2026-05-15T10:05:00Z",
        "completed_at": null,
        "duration_ms": null
      },
      {
        "_key": "step_003",
        "todo_key": "todo_001",
        "step_index": 2,
        "step_title": "產出報告",
        "step_type": "generation",
        "status": "pending",
        "result": null,
        "error": null,
        "started_at": null,
        "completed_at": null,
        "duration_ms": null
      }
    ]
  }
}
```

**curl 範例：**

```bash
# 基本查詢
curl http://localhost:6500/api/v1/todos/todo_001

# 一併回傳步驟
curl "http://localhost:6500/api/v1/todos/todo_001?steps=true"
```

---

#### 4. PATCH /api/v1/todos/{key} — 更新 Todo

更新 Todo 的標題、描述、優先級或標籤。不可直接修改狀態或步驟（需透過專用端點）。

**Request Body：**

```json
{
  "title": "撰寫 Q2 季度財報分析報告（更新版）",
  "priority": "critical",
  "tags": ["財務", "季度報告", "緊急"]
}
```

**Response（200 OK）：**

```json
{
  "success": true,
  "data": {
    "_key": "todo_001",
    "title": "撰寫 Q2 季度財報分析報告（更新版）",
    "priority": "critical",
    "tags": ["財務", "季度報告", "緊急"],
    "updated_at": "2026-05-15T11:00:00Z"
  }
}
```

**curl 範例：**

```bash
curl -X PATCH http://localhost:6500/api/v1/todos/todo_001 \
  -H "Content-Type: application/json" \
  -d '{
    "title": "撰寫 Q2 季度財報分析報告（更新版）",
    "priority": "critical",
    "tags": ["財務", "季度報告", "緊急"]
  }'
```

**備註：**
- 僅能更新中繼資料（metadata），無法透過此端點修改狀態或步驟。
- 未提供的欄位維持原值不變。

---

#### 5. DELETE /api/v1/todos/{key} — 刪除 Todo

刪除指定的 Todo 及其關聯的所有步驟與日誌。

**Response（200 OK）：**

```json
{
  "success": true,
  "message": "Todo todo_001 已成功刪除"
}
```

**curl 範例：**

```bash
curl -X DELETE http://localhost:6500/api/v1/todos/todo_001
```

**備註：**
- 此操作不可逆，會一併刪除該 Todo 的所有步驟與執行日誌。
- 建議在刪除前先查詢確認 Todo 是否已被正確完成或不再需要。

---

### State Machine

#### 6. POST /api/v1/todos/{key}/start — 開始執行

將 Todo 狀態從 `pending` 變更為 `running`，並將第一個步驟設為 `running`。

**Response（200 OK）：**

```json
{
  "success": true,
  "data": {
    "_key": "todo_001",
    "status": "running",
    "current_step_index": 0,
    "progress": 0,
    "updated_at": "2026-05-15T10:01:00Z"
  }
}
```

**curl 範例：**

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_001/start
```

**備註：**
- 僅 `pending` 狀態的 Todo 可以啟動。
- 若 Todo 狀態不是 `pending`，回傳 400 錯誤。

---

#### 7. POST /api/v1/todos/{key}/pause — 暫停

手動將 Todo 暫停。與 PDCA 審查失敗自動暫停不同，此為手動觸發。

**Response（200 OK）：**

```json
{
  "success": true,
  "data": {
    "_key": "todo_001",
    "status": "paused",
    "pdca_verdict": null,
    "pdca_summary": "手動暫停",
    "updated_at": "2026-05-15T10:30:00Z"
  }
}
```

**curl 範例：**

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_001/pause
```

**備註：**
- 僅 `running` 狀態的 Todo 可以暫停。
- 手動暫停不會寫入 PDCA verdict，僅記錄摘要為「手動暫停」。

---

#### 8. POST /api/v1/todos/{key}/restart — 重頭開始

將 Todo 狀態與所有步驟重置回初始狀態（`pending`），`current_step_index` 歸零。

**Response（200 OK）：**

```json
{
  "success": true,
  "data": {
    "_key": "todo_001",
    "status": "pending",
    "current_step_index": 0,
    "progress": 0,
    "updated_at": "2026-05-15T10:35:00Z"
  }
}
```

**curl 範例：**

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_001/restart
```

**備註：**
- 任何狀態的 Todo 都可以重頭開始。
- 所有步驟的狀態、結果、錯誤訊息、時間戳都會被重置。
- 日誌（logs）不受影響，仍保留歷史記錄。

---

### Step Operations

#### 9. POST /api/v1/todos/{key}/step/{index}/complete — 完成步驟

將指定步驟標記為完成，可附帶執行結果。

**Request Body：**

```json
{
  "result": "成功取得 Q2 財務報表，包含損益表與資產負債表"
}
```

**Response（200 OK）：**

```json
{
  "success": true,
  "data": {
    "_key": "step_001",
    "step_index": 0,
    "status": "completed",
    "result": "成功取得 Q2 財務報表，包含損益表與資產負債表",
    "completed_at": "2026-05-15T10:03:00Z",
    "duration_ms": 120000
  }
}
```

**curl 範例：**

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_001/step/0/complete \
  -H "Content-Type: application/json" \
  -d '{"result": "成功取得 Q2 財務報表，包含損益表與資產負債表"}'
```

**備註：**
- `result` 為選填，建議填寫以便後續 Check 審查使用。
- 完成步驟後，若還有下一個步驟，`current_step_index` 會自動推進。
- 若這是最後一個步驟，Todo 會自動變為 `completed`。

---

#### 10. POST /api/v1/todos/{key}/step/{index}/fail — 步驟失敗

將指定步驟標記為失敗，需提供錯誤訊息。

**Request Body：**

```json
{
  "error": "資料庫連線超時，無法取得財務報表"
}
```

**Response（200 OK）：**

```json
{
  "success": true,
  "data": {
    "_key": "step_001",
    "step_index": 0,
    "status": "failed",
    "error": "資料庫連線超時，無法取得財務報表",
    "completed_at": "2026-05-15T10:03:00Z",
    "duration_ms": 30000
  }
}
```

**curl 範例：**

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_001/step/0/fail \
  -H "Content-Type: application/json" \
  -d '{"error": "資料庫連線超時，無法取得財務報表"}'
```

**備註：**
- `error` 為必填。
- 步驟失敗會導致 Todo 狀態變為 `failed`。

---

#### 11. POST /api/v1/todos/{key}/step/{index}/skip — 跳過步驟

將指定步驟標記為跳過，不需要提供原因，但建議記錄。

**Request Body（選填）：**

```json
{
  "reason": "該步驟在本次執行中不適用"
}
```

**Response（200 OK）：**

```json
{
  "success": true,
  "data": {
    "_key": "step_002",
    "step_index": 1,
    "status": "skipped",
    "result": "該步驟在本次執行中不適用",
    "completed_at": "2026-05-15T10:04:00Z"
  }
}
```

**curl 範例：**

```bash
# 不帶原因
curl -X POST http://localhost:6500/api/v1/todos/todo_001/step/1/skip

# 帶原因
curl -X POST http://localhost:6500/api/v1/todos/todo_001/step/1/skip \
  -H "Content-Type: application/json" \
  -d '{"reason": "該步驟在本次執行中不適用"}'
```

**備註：**
- 跳過步驟後，`current_step_index` 會自動推進到下一個步驟。
- 跳過不會觸發 PDCA Check 審查。

---

#### 12. POST /api/v1/todos/{key}/step/{index}/retry — 重試步驟

將已失敗或已跳過的步驟重置回 `pending` 狀態，允許重新執行。

**Response（200 OK）：**

```json
{
  "success": true,
  "data": {
    "_key": "step_001",
    "step_index": 0,
    "status": "pending",
    "updated_at": "2026-05-15T10:10:00Z"
  }
}
```

**curl 範例：**

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_001/step/0/retry
```

**備註：**
- 僅 `failed` 與 `skipped` 狀態的步驟可以重試。
- 重試後需要再次呼叫 `start` 來恢復執行。

---

### PDCA（核心功能）

#### 13. POST /api/v1/todos/{key}/step/{index}/plan — PDCA Plan 審查

在步驟執行前進行計畫審查。引擎會將 Todo 與步驟的上下文包裝成 prompt，送給 Ollama LLM 進行評估。

**Request Body：**

```json
{
  "context": {
    "todo_title": "撰寫季度財報分析報告",
    "step_title": "蒐集財務數據",
    "step_type": "data_collection",
    "plan": "將透過 SQL 查詢資料庫取得 Q2 損益表與資產負債表"
  }
}
```

**Response（200 OK）- Approved：**

```json
{
  "success": true,
  "data": {
    "pdca_verdict": "Approved",
    "pdca_summary": "計畫明確，資料來源正確認，核准執行。",
    "todo_status": "running",
    "todo_paused": false
  }
}
```

**Response（200 OK）- Rejected：**

```json
{
  "success": true,
  "data": {
    "pdca_verdict": "Rejected",
    "pdca_summary": "缺少資料庫連線憑證配置，無法確保查詢可正常執行。請補充連線資訊後重新提交。",
    "todo_status": "paused",
    "todo_paused": true
  }
}
```

**Response（200 OK）- Clarify：**

```json
{
  "success": true,
  "data": {
    "pdca_verdict": "Clarify",
    "pdca_summary": "請問要使用正式環境還是測試環境的資料庫？兩者的資料範圍不同。",
    "todo_status": "paused",
    "todo_paused": true,
    "question": "請問要使用正式環境還是測試環境的資料庫？"
  }
}
```

**Response（200 OK）- Escalate：**

```json
{
  "success": true,
  "data": {
    "pdca_verdict": "Escalate",
    "pdca_summary": "此步驟需要資料庫管理員權限，當前 Agent 無權限執行。請指派 DBA 處理。",
    "todo_status": "paused",
    "todo_paused": true
  }
}
```

**curl 範例：**

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_001/step/0/plan \
  -H "Content-Type: application/json" \
  -d '{
    "context": {
      "todo_title": "撰寫季度財報分析報告",
      "step_title": "蒐集財務數據",
      "step_type": "data_collection",
      "plan": "將透過 SQL 查詢資料庫取得 Q2 損益表與資產負債表"
    }
  }'
```

**備註：**
- 此端點會同步呼叫 Ollama LLM，回應時間取決於 LLM 的回應速度。
- 非 Approved 的 verdict 會自動將 Todo 暫停（paused）。
- 審查記錄會自動寫入 `todo_logs` 以供後續追蹤。

---

#### 14. POST /api/v1/todos/{key}/step/{index}/check — PDCA Check 審查

在步驟完成後進行結果驗證。引擎會將步驟的執行結果送給 Ollama LLM 評估是否符合預期。

**Request Body：**

```json
{
  "context": {
    "todo_title": "撰寫季度財報分析報告",
    "step_title": "蒐集財務數據",
    "step_type": "data_collection",
    "result": "成功取得 Q2 財務報表，包含損益表與資產負債表"
  }
}
```

**Response（200 OK）- Approved：**

```json
{
  "success": true,
  "data": {
    "pdca_verdict": "Approved",
    "pdca_summary": "資料完整且正確，通過驗證。",
    "todo_status": "running",
    "todo_paused": false
  }
}
```

**Response（200 OK）- Rejected：**

```json
{
  "success": true,
  "data": {
    "pdca_verdict": "Rejected",
    "pdca_summary": "僅取得損益表，缺少資產負債表與現金流量表，資料不完整。請補充後重新提交。",
    "todo_status": "paused",
    "todo_paused": true
  }
}
```

**curl 範例：**

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_001/step/0/check \
  -H "Content-Type: application/json" \
  -d '{
    "context": {
      "todo_title": "撰寫季度財報分析報告",
      "step_title": "蒐集財務數據",
      "step_type": "data_collection",
      "result": "成功取得 Q2 財務報表，包含損益表與資產負債表"
    }
  }'
```

**備註：**
- 建議在步驟完成後立即呼叫 Check 審查，以確保結果品質。
- Check 與 Plan 共用同一套 verdict 邏輯與暫停機制。

---

### Human-in-the-Loop

#### 15. POST /api/v1/todos/{key}/revise — 提交修正計畫

當 PDCA 審查結果為 Rejected 時，人類可透過此端點提交修正計畫，將 Todo 恢復為 `running` 狀態。

**Request Body：**

```json
{
  "plan": "已補充資料庫連線憑證，使用測試環境的唯讀帳號進行查詢。"
}
```

**Response（200 OK）：**

```json
{
  "success": true,
  "data": {
    "_key": "todo_001",
    "status": "running",
    "pdca_verdict": null,
    "pdca_summary": null,
    "message": "修正計畫已提交，Todo 已恢復執行。",
    "updated_at": "2026-05-15T10:20:00Z"
  }
}
```

**curl 範例：**

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_001/revise \
  -H "Content-Type: application/json" \
  -d '{"plan": "已補充資料庫連線憑證，使用測試環境的唯讀帳號進行查詢。"}'
```

**備註：**
- 僅 `paused` 狀態且 `pdca_verdict` 為 Rejected 的 Todo 可以呼叫 revise。
- 修正計畫提交後，`pdca_verdict` 與 `pdca_summary` 會被清空，Todo 恢復執行。
- 修正後的步驟應再次發起 Plan 審查。

---

#### 16. POST /api/v1/todos/{key}/step/{index}/clarify — 回答澄清問題

當 PDCA Plan 審查結果為 Clarify 時，人類可回答 LLM 提出的問題，然後將 Todo 恢復為 `running` 狀態。

**Request Body：**

```json
{
  "response": "請使用測試環境的資料庫。"
}
```

**Response（200 OK）：**

```json
{
  "success": true,
  "data": {
    "_key": "todo_001",
    "status": "running",
    "pdca_verdict": null,
    "pdca_summary": null,
    "message": "澄清回應已記錄，Todo 已恢復執行。",
    "updated_at": "2026-05-15T10:25:00Z"
  }
}
```

**curl 範例：**

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_001/step/0/clarify \
  -H "Content-Type: application/json" \
  -d '{"response": "請使用測試環境的資料庫。"}'
```

**備註：**
- 僅 `paused` 狀態且該步驟的 PDCA verdict 為 Clarify 時可以呼叫。
- 回應後引擎會自動將人類的回應併入 context，重新發起 Plan 審查。

---

### Logs

#### 17. GET /api/v1/todos/{key}/logs — 查詢執行日誌

取得指定 Todo 的所有執行日誌，包含 PDCA 審查記錄與步驟變更記錄。

**Query Parameters：**

| 參數 | 型態 | 說明 |
|------|------|------|
| `step_index` | integer | 篩選特定步驟的日誌 |
| `log_type` | string | 篩選日誌類型：plan / check / system / human |

**Response（200 OK）：**

```json
{
  "success": true,
  "data": [
    {
      "_key": "log_001",
      "todo_key": "todo_001",
      "step_index": 0,
      "log_type": "plan",
      "message": "PDCA Plan 審查：Approved",
      "details": "計畫明確，資料來源正確認，核准執行。",
      "created_at": "2026-05-15T10:01:30Z"
    },
    {
      "_key": "log_002",
      "todo_key": "todo_001",
      "step_index": 0,
      "log_type": "system",
      "message": "步驟 0 完成",
      "details": "成功取得 Q2 財務報表，包含損益表與資產負債表",
      "created_at": "2026-05-15T10:03:00Z"
    },
    {
      "_key": "log_003",
      "todo_key": "todo_001",
      "step_index": 0,
      "log_type": "check",
      "message": "PDCA Check 審查：Approved",
      "details": "資料完整且正確，通過驗證。",
      "created_at": "2026-05-15T10:03:30Z"
    }
  ],
  "total": 3
}
```

**curl 範例：**

```bash
# 查詢所有日誌
curl http://localhost:6500/api/v1/todos/todo_001/logs

# 篩選特定步驟的日誌
curl "http://localhost:6500/api/v1/todos/todo_001/logs?step_index=0"

# 篩選特定類型的日誌
curl "http://localhost:6500/api/v1/todos/todo_001/logs?log_type=plan"

# 多重篩選
curl "http://localhost:6500/api/v1/todos/todo_001/logs?step_index=0&log_type=check"
```

**備註：**
- 日誌不可刪除或修改，確保審計軌跡的完整性。
- `log_type` 包含三種：`plan`（Plan 審查）、`check`（Check 審查）、`system`（系統操作）、`human`（人類介入）。

---

## 資料模型

### TodoItem

Todo 的主資料模型，儲存於 `todos` 集合中。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `_key` | string | 系統產生 | 唯一識別碼 |
| `todo_no` | string | 系統產生 | 可讀性編號，格式：TD-YYYYMMDD-XXXX |
| `title` | string | 是 | Todo 標題 |
| `description` | string | 否 | Todo 詳細描述 |
| `status` | string | 是 | 狀態：pending / running / completed / failed / paused |
| `priority` | string | 否 | 優先級：low / medium / high / critical（預設 medium） |
| `current_step_index` | integer | 是 | 目前執行到的步驟索引（從 0 開始） |
| `total_steps` | integer | 是 | 步驟總數 |
| `progress` | integer | 是 | 進度百分比（0-100） |
| `pdca_verdict` | string | 否 | PDCA 審查結果：Approved / Rejected / Clarify / Escalate |
| `pdca_summary` | string | 否 | PDCA 審查摘要 |
| `tags` | array | 否 | 標籤列表 |
| `created_at` | datetime | 是 | 建立時間 |
| `updated_at` | datetime | 是 | 最後更新時間 |

### TodoStep

步驟資料模型，儲存於 `todo_steps` 集合中。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `_key` | string | 系統產生 | 唯一識別碼 |
| `todo_key` | string | 是 | 所屬 Todo 的 `_key` |
| `step_index` | integer | 是 | 步驟序號（從 0 開始） |
| `step_title` | string | 是 | 步驟名稱 |
| `step_type` | string | 否 | 步驟類型（例如 data_collection / analysis / generation） |
| `status` | string | 是 | 狀態：pending / running / completed / failed / skipped |
| `result` | string | 否 | 執行結果 |
| `error` | string | 否 | 錯誤訊息 |
| `started_at` | datetime | 否 | 開始執行時間 |
| `completed_at` | datetime | 否 | 完成時間 |
| `duration_ms` | integer | 否 | 執行耗时（毫秒） |

### TodoLog

執行日誌資料模型，儲存於 `todo_logs` 集合中。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `_key` | string | 系統產生 | 唯一識別碼 |
| `todo_key` | string | 是 | 所屬 Todo 的 `_key` |
| `step_index` | integer | 否 | 關聯的步驟索引（若適用） |
| `log_type` | string | 是 | 類型：plan / check / system / human |
| `message` | string | 是 | 日誌訊息摘要 |
| `details` | string | 否 | 詳細內容 |
| `created_at` | datetime | 是 | 建立時間 |

---

## PDCA 流程範例

以下展示一個完整的端到端 PDCA 流程，從建立 Todo 到完成所有步驟。

### 第 1 步：建立 Todo（含 3 個步驟）

```bash
curl -X POST http://localhost:6500/api/v1/todos \
  -H "Content-Type: application/json" \
  -d '{
    "title": "資料備份與還原測試",
    "description": "執行資料庫備份並驗證備份檔案可成功還原",
    "priority": "high",
    "tags": ["維運", "備份"],
    "steps": [
      {"step_title": "執行資料庫備份", "step_type": "operation"},
      {"step_title": "驗證備份檔案完整性", "step_type": "verification"},
      {"step_title": "執行還原測試", "step_type": "testing"}
    ]
  }'
```

**預期回應：**

```json
{
  "success": true,
  "data": {
    "_key": "todo_backup_001",
    "todo_no": "TD-20260515-0003",
    "status": "pending",
    "total_steps": 3,
    "progress": 0
  }
}
```

### 第 2 步：開始執行

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_backup_001/start
```

**預期回應：**

```json
{
  "success": true,
  "data": {
    "_key": "todo_backup_001",
    "status": "running",
    "current_step_index": 0,
    "progress": 0
  }
}
```

### 第 3 步：Plan 審查 → Rejected → Todo 暫停

對步驟 0 發起 Plan 審查，模擬 LLM 認為計畫不完整的情境。

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_backup_001/step/0/plan \
  -H "Content-Type: application/json" \
  -d '{
    "context": {
      "todo_title": "資料備份與還原測試",
      "step_title": "執行資料庫備份",
      "step_type": "operation",
      "plan": "執行 pg_dump 備份資料庫"
    }
  }'
```

**預期回應（Rejected）：**

```json
{
  "success": true,
  "data": {
    "pdca_verdict": "Rejected",
    "pdca_summary": "缺少備份檔案的儲存路徑與保留策略，且未指定要備份的資料庫名稱。請補充後重新提交。",
    "todo_status": "paused",
    "todo_paused": true
  }
}
```

此時 Todo 自動暫停，等待人工介入。

### 第 4 步：提交修正計畫（revise）→ Todo 恢復

人類檢視 Rejected 原因後，提交修正計畫。

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_backup_001/revise \
  -H "Content-Type: application/json" \
  -d '{
    "plan": "使用 pg_dump 備份 myapp_production 資料庫，備份檔案儲存於 /backup/postgres/ 目錄，保留最近 7 天的備份。"
  }'
```

**預期回應：**

```json
{
  "success": true,
  "data": {
    "_key": "todo_backup_001",
    "status": "running",
    "pdca_verdict": null,
    "pdca_summary": null
  }
}
```

修正後，再次發起 Plan 審查確認修正後的計畫。

```bash
# 重新進行 Plan 審查
curl -X POST http://localhost:6500/api/v1/todos/todo_backup_001/step/0/plan \
  -H "Content-Type: application/json" \
  -d '{
    "context": {
      "todo_title": "資料備份與還原測試",
      "step_title": "執行資料庫備份",
      "step_type": "operation",
      "plan": "使用 pg_dump 備份 myapp_production 資料庫，備份檔案儲存於 /backup/postgres/ 目錄，保留最近 7 天的備份。"
    }
  }'
```

**預期回應（Approved）：**

```json
{
  "success": true,
  "data": {
    "pdca_verdict": "Approved",
    "pdca_summary": "計畫完整，儲存路徑與保留策略明確，核准執行。",
    "todo_status": "running",
    "todo_paused": false
  }
}
```

### 第 5 步：完成步驟 1

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_backup_001/step/0/complete \
  -H "Content-Type: application/json" \
  -d '{"result": "成功備份 myapp_production 資料庫，備份檔案大小 2.3GB，儲存於 /backup/postgres/backup_20260515.sql.gz"}'
```

**預期回應：**

```json
{
  "success": true,
  "data": {
    "_key": "step_backup_001",
    "step_index": 0,
    "status": "completed",
    "result": "成功備份 myapp_production 資料庫，備份檔案大小 2.3GB，儲存於 /backup/postgres/backup_20260515.sql.gz"
  }
}
```

### 第 6 步：Check 審查步驟 1 → Approved

```bash
curl -X POST http://localhost:6500/api/v1/todos/todo_backup_001/step/0/check \
  -H "Content-Type: application/json" \
  -d '{
    "context": {
      "todo_title": "資料備份與還原測試",
      "step_title": "執行資料庫備份",
      "step_type": "operation",
      "result": "成功備份 myapp_production 資料庫，備份檔案大小 2.3GB，儲存於 /backup/postgres/backup_20260515.sql.gz"
    }
  }'
```

**預期回應（Approved）：**

```json
{
  "success": true,
  "data": {
    "pdca_verdict": "Approved",
    "pdca_summary": "備份成功，檔案大小合理，儲存位置正確，通過驗證。",
    "todo_status": "running",
    "todo_paused": false
  }
}
```

### 第 7 步：完成步驟 2（驗證備份檔案完整性）

```bash
# Plan 審查
curl -X POST http://localhost:6500/api/v1/todos/todo_backup_001/step/1/plan \
  -H "Content-Type: application/json" \
  -d '{
    "context": {
      "todo_title": "資料備份與還原測試",
      "step_title": "驗證備份檔案完整性",
      "step_type": "verification",
      "plan": "使用 gzip -t 檢查備份檔案的完整性"
    }
  }'
```

**預期回應（Approved）：**

```json
{
  "success": true,
  "data": {
    "pdca_verdict": "Approved",
    "pdca_summary": "驗證方式適當，核准執行。",
    "todo_status": "running",
    "todo_paused": false
  }
}
```

```bash
# 完成步驟
curl -X POST http://localhost:6500/api/v1/todos/todo_backup_001/step/1/complete \
  -H "Content-Type: application/json" \
  -d '{"result": "gzip -t 驗證通過，備份檔案無損壞"}'
```

```bash
# Check 審查
curl -X POST http://localhost:6500/api/v1/todos/todo_backup_001/step/1/check \
  -H "Content-Type: application/json" \
  -d '{
    "context": {
      "todo_title": "資料備份與還原測試",
      "step_title": "驗證備份檔案完整性",
      "step_type": "verification",
      "result": "gzip -t 驗證通過，備份檔案無損壞"
    }
  }'
```

**預期回應（Approved）：**

```json
{
  "success": true,
  "data": {
    "pdca_verdict": "Approved",
    "pdca_summary": "備份檔案完整無損，通過驗證。",
    "todo_status": "running",
    "todo_paused": false
  }
}
```

### 第 8 步：完成步驟 3 → 自動完成

```bash
# Plan 審查
curl -X POST http://localhost:6500/api/v1/todos/todo_backup_001/step/2/plan \
  -H "Content-Type: application/json" \
  -d '{
    "context": {
      "todo_title": "資料備份與還原測試",
      "step_title": "執行還原測試",
      "step_type": "testing",
      "plan": "將備份檔案還原到測試資料庫 myapp_staging，確認資料表與資料筆數正確"
    }
  }'
```

**預期回應（Approved）：**

```json
{
  "success": true,
  "data": {
    "pdca_verdict": "Approved",
    "pdca_summary": "還原測試計畫完整，核准執行。",
    "todo_status": "running",
    "todo_paused": false
  }
}
```

```bash
# 完成最後一個步驟
curl -X POST http://localhost:6500/api/v1/todos/todo_backup_001/step/2/complete \
  -H "Content-Type: application/json" \
  -d '{"result": "還原成功，15 個資料表全部還原，總計 120 萬筆資料，資料一致無誤"}'
```

**預期回應（最後一個步驟完成，Todo 自動完成）：**

```json
{
  "success": true,
  "data": {
    "_key": "step_backup_003",
    "step_index": 2,
    "status": "completed",
    "result": "還原成功，15 個資料表全部還原，總計 120 萬筆資料，資料一致無誤",
    "todo_status": "completed",
    "todo_progress": 100
  }
}
```

### 第 9 步：查詢 Logs 確認 PDCA 軌跡

```bash
curl "http://localhost:6500/api/v1/todos/todo_backup_001/logs"
```

**預期回應：**

```json
{
  "success": true,
  "data": [
    {"log_type": "system", "message": "Todo 建立", "created_at": "2026-05-15T14:00:00Z"},
    {"log_type": "system", "message": "Todo 啟動", "created_at": "2026-05-15T14:00:05Z"},
    {"log_type": "plan", "message": "PDCA Plan 審查：Rejected", "details": "缺少備份檔案的儲存路徑與保留策略", "created_at": "2026-05-15T14:00:10Z"},
    {"log_type": "human", "message": "人類提交修正計畫", "details": "使用 pg_dump 備份 myapp_production 資料庫...", "created_at": "2026-05-15T14:05:00Z"},
    {"log_type": "plan", "message": "PDCA Plan 審查：Approved", "created_at": "2026-05-15T14:05:05Z"},
    {"log_type": "system", "message": "步驟 0 完成", "created_at": "2026-05-15T14:10:00Z"},
    {"log_type": "check", "message": "PDCA Check 審查：Approved", "created_at": "2026-05-15T14:10:05Z"},
    {"log_type": "plan", "message": "PDCA Plan 審查：Approved", "details": "步驟 1", "created_at": "2026-05-15T14:10:10Z"},
    {"log_type": "system", "message": "步驟 1 完成", "created_at": "2026-05-15T14:12:00Z"},
    {"log_type": "check", "message": "PDCA Check 審查：Approved", "details": "步驟 1", "created_at": "2026-05-15T14:12:05Z"},
    {"log_type": "plan", "message": "PDCA Plan 審查：Approved", "details": "步驟 2", "created_at": "2026-05-15T14:12:10Z"},
    {"log_type": "system", "message": "步驟 2 完成", "created_at": "2026-05-15T14:20:00Z"},
    {"log_type": "system", "message": "Todo 完成", "created_at": "2026-05-15T14:20:00Z"}
  ],
  "total": 13
}
```

---

## Agent 調用指南

### Python Agent 如何透過 HTTP 調用 PDCA 引擎

以下是一個建議的調用模式，適用於任何 Python 開發的 AI Agent。

```python
import httpx
from typing import Optional

class PDCAEngineClient:
    """PDCA 引擎 HTTP 客戶端"""

    def __init__(self, base_url: str = "http://localhost:6500"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def create_todo(self, title: str, steps: list, description: str = "",
                    priority: str = "medium") -> dict:
        """建立 Todo 並回傳 _key"""
        payload = {
            "title": title,
            "description": description,
            "priority": priority,
            "steps": [{"step_title": s, "step_type": "generic"} for s in steps]
        }
        resp = self.client.post(f"{self.base_url}/api/v1/todos", json=payload)
        resp.raise_for_status()
        return resp.json()["data"]

    def start_todo(self, todo_key: str) -> dict:
        """啟動 Todo"""
        resp = self.client.post(f"{self.base_url}/api/v1/todos/{todo_key}/start")
        resp.raise_for_status()
        return resp.json()["data"]

    def plan_review(self, todo_key: str, step_index: int, plan: str,
                    todo_title: str = "", step_title: str = "",
                    step_type: str = "generic") -> dict:
        """發起 Plan 審查，回傳 verdict"""
        payload = {
            "context": {
                "todo_title": todo_title,
                "step_title": step_title,
                "step_type": step_type,
                "plan": plan
            }
        }
        resp = self.client.post(
            f"{self.base_url}/api/v1/todos/{todo_key}/step/{step_index}/plan",
            json=payload
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def complete_step(self, todo_key: str, step_index: int, result: str) -> dict:
        """完成步驟"""
        resp = self.client.post(
            f"{self.base_url}/api/v1/todos/{todo_key}/step/{step_index}/complete",
            json={"result": result}
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def check_review(self, todo_key: str, step_index: int, result: str,
                     todo_title: str = "", step_title: str = "",
                     step_type: str = "generic") -> dict:
        """發起 Check 審查"""
        payload = {
            "context": {
                "todo_title": todo_title,
                "step_title": step_title,
                "step_type": step_type,
                "result": result
            }
        }
        resp = self.client.post(
            f"{self.base_url}/api/v1/todos/{todo_key}/step/{step_index}/check",
            json=payload
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def pause(self, todo_key: str) -> dict:
        """手動暫停 Todo"""
        resp = self.client.post(f"{self.base_url}/api/v1/todos/{todo_key}/pause")
        resp.raise_for_status()
        return resp.json()["data"]

    def revise(self, todo_key: str, plan: str) -> dict:
        """提交修正計畫"""
        resp = self.client.post(
            f"{self.base_url}/api/v1/todos/{todo_key}/revise",
            json={"plan": plan}
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def clarify(self, todo_key: str, step_index: int, response: str) -> dict:
        """回答澄清問題"""
        resp = self.client.post(
            f"{self.base_url}/api/v1/todos/{todo_key}/step/{step_index}/clarify",
            json={"response": response}
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def get_logs(self, todo_key: str, step_index: Optional[int] = None,
                 log_type: Optional[str] = None) -> list:
        """查詢日誌"""
        params = {}
        if step_index is not None:
            params["step_index"] = step_index
        if log_type:
            params["log_type"] = log_type
        resp = self.client.get(
            f"{self.base_url}/api/v1/todos/{todo_key}/logs",
            params=params
        )
        resp.raise_for_status()
        return resp.json()["data"]
```

### 建議的調用模式

Agent 在執行任務時，建議遵循以下模式：

```
   ┌─────────────────────────────┐
   │  1. 創建 Todo               │
   │     create_todo()           │
   └──────────┬──────────────────┘
              ▼
   ┌─────────────────────────────┐
   │  2. 啟動 Todo               │
   │     start_todo()            │
   └──────────┬──────────────────┘
              ▼
   ┌─────────────────────────────┐
   │  3. Plan 審查               │
   │     plan_review()           │
   └──────────┬──────────────────┘
              ▼
      ┌───────┴───────┐
      │               │
   Approved      Rejected/Clarify
      │               │
      ▼               ▼
   ┌────────┐  ┌────────────────┐
   │ 繼續   │  │ 記錄問題       │
   │ 執行   │  │ 等待人類回應   │
   └───┬────┘  └────────┬───────┘
       │                │
       ▼                ▼
   ┌─────────────┐  ┌───────────────────┐
   │ 4. 執行步驟  │  │ 人類回應後呼叫     │
   │ complete_   │  │ revise() 或       │
   │ step()      │  │ clarify()         │
   └──────┬──────┘  └────────┬──────────┘
          │                  │
          ▼                  │
   ┌─────────────┐           │
   │ 5. Check    │           │
   │ 審查        │           │
   │ check_      │           │
   │ review()    │           │
   └──────┬──────┘           │
          │                  │
     ┌────┴────┐             │
     │         │             │
  Approved  Rejected─────────┘ (回到第 3 步)
     │
     ▼
   ┌────────────────┐
   │ 6. 重複直到    │
   │    完成所有步驟 │
   └────────────────┘
```

**核心邏輯（pseudocode）：**

```python
def execute_todo(todo_data: dict):
    # 1. 建立 Todo
    todo = client.create_todo(
        title=todo_data["title"],
        steps=todo_data["steps"]
    )
    todo_key = todo["_key"]

    # 2. 啟動
    client.start_todo(todo_key)

    for step_index, step in enumerate(todo_data["steps"]):
        while True:  # 重試迴圈，直到 Plan 通過
            # 3. Plan 審查
            plan_verdict = client.plan_review(
                todo_key=todo_key,
                step_index=step_index,
                plan=step["plan"],
                todo_title=todo_data["title"],
                step_title=step["title"]
            )

            if plan_verdict["pdca_verdict"] == "Approved":
                break  # 計畫通過，跳出重試迴圈

            elif plan_verdict["pdca_verdict"] == "Rejected":
                # 記錄問題，等待人類修正
                log_error(f"步驟 {step_index} 計畫被拒絕：{plan_verdict['pdca_summary']}")
                # 等待外部呼叫 revise()，然後重試
                wait_for_human_intervention()
                # 人類已呼叫 revise()，重試 Plan 審查
                continue

            elif plan_verdict["pdca_verdict"] == "Clarify":
                # 記錄問題，等待人類回答
                log_info(f"需要澄清：{plan_verdict['pdca_summary']}")
                wait_for_human_clarification()
                # 人類已呼叫 clarify()，重試 Plan 審查
                continue

        # 4. 執行步驟（Agent 的實際邏輯）
        result = execute_step_logic(step)

        # 5. 完成步驟
        client.complete_step(todo_key, step_index, result)

        # 6. Check 審查
        check_verdict = client.check_review(
            todo_key=todo_key,
            step_index=step_index,
            result=result,
            todo_title=todo_data["title"],
            step_title=step["title"]
        )

        if check_verdict["pdca_verdict"] != "Approved":
            # Check 未通過，記錄問題並停止
            log_error(f"步驟 {step_index} 驗證失敗：{check_verdict['pdca_summary']}")
            break

    # 7. 完成後查詢日誌
    logs = client.get_logs(todo_key)
    return logs
```

---

## 設計原則

### 輕量

PDCA 引擎的設計強調輕量與簡單：

- **無新增資料表**：僅使用 `todos`、`todo_steps`、`todo_logs` 三個集合，不引入額外儲存層。
- **無背景輪巡**：沒有排程器、沒有 cron job、沒有背景 worker。所有操作皆由 API 請求觸發。
- **無事件佇列**：不依賴 RabbitMQ、Redis Queue 或任何事件匯流排。Plan 與 Check 為同步 HTTP 請求。
- **無狀態**：引擎本身不維護記憶體狀態，所有狀態皆持久化在資料庫中，重啟後不遺失。

### Human-in-the-Loop

PDCA 的品質把關依賴人類的判斷：

- 非 Approved 的 verdict（Rejected / Clarify / Escalate）會自動將 Todo 暫停，等待人類處理。
- 人類可以透過 `revise` 提交修正計畫、透過 `clarify` 回答問題。
- 引擎不強制人類回應，但暫停的 Todo 不會繼續執行，迫使流程停下來等人。
- Escalate 情況需要更高權限的管理者介入，引擎僅記錄原因。

### 可追蹤

所有 PDCA 審查記錄都會寫入 `todo_logs`，確保完整的審計軌跡：

- 每次 Plan 審查與 Check 審查都會產生日誌（`log_type: plan` / `log_type: check`）。
- 人類的每次介入（revise / clarify）也會記錄（`log_type: human`）。
- 系統操作（建立、啟動、完成、暫停）都會記錄（`log_type: system`）。
- 日誌不可刪除或修改，確保追溯能力。

### 同步

Plan 與 Check 審查採用同步設計：

- Plan/Check 是同步 HTTP 請求，caller 發起請求後等待 LLM 回應。
- 這種設計讓 caller 可以精確控制流程，不需要實作 callback 或 webhook。
- 同步方式簡化了錯誤處理，caller 可以直接在請求回應中得知 verdict。
- 缺點是 LLM 回應時間會直接影響 caller 的等待時間，建議設定合理的 HTTP timeout。
