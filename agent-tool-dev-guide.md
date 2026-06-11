---
lastUpdate: 2026-04-29 14:00:00
author: AI Agent
version: 1.3.0
---

# AI Agent / Tool 開發指引（#dev）

當使用者輸入 `#dev {需求編號}` 時，AI Coder 應按照本指引進行開發工作。

## 觸發條件

使用者訊息包含 `#dev` 關鍵字，後接需求編號（格式：`A01-2617-001`）。

## 執行步驟

### Step 1：提取需求編號

從使用者輸入中解析需求編號，格式為 `A{tab}-{YYWW}-{seq}` 或 `T{tab}-{YYWW}-{seq}`。

### Step 2：調用 API 取得需求與規格

```
GET http://localhost:3001/api/v1/agent-requirements/by-req-no/{req_no}
```

回應包含完整需求資訊：`agent_name`, `goal`, `expected_effect`, `problem_description`, `dev_spec`, `ai_review`。

### Step 3：複製規格書到工作區

將規格書內容寫入專案工作目錄：

```
.sisyphus/plans/{req_no}-spec.md
```

或若使用 OpenCode：
```
.opencode/plans/{req_no}-spec.md
```

### Step 4：解析並確認

AI Coder 必須先完成以下分析，再開始寫程式碼：

1. **需求理解**：用自己的話重述需求目標與預期效果
2. **技術棧確認**：確認建議的技術都在本系統範圍內
3. **模組拆解**：列出需要建立/修改的檔案
4. **依賴檢查**：確認是否有未滿足的前置條件
5. **向使用者確認**：以上分析完成後，請使用者確認是否開始開發

### Step 5：開始開發

使用者確認後，按照 AGENTS.md 的開發規範進行實作。

## API 參考

| 端點 | 用途 |
|------|------|
| `GET /api/v1/agent-requirements/by-req-no/{no}` | 依編號查詢需求 |
| `GET /api/v1/agent-requirements/{key}` | 依 key 查詢需求 |
| `GET /api/v1/agent-requirements/{key}/spec.md` | 下載規格書 Markdown |

## Step 5-A：建立 Agent 記錄（ArangoDB）

開發完成後，必須在 ArangoDB `agents` 集合建立 Agent 記錄，才能在智能體市集看到。

### Rust `Agent` struct 必填欄位

> 若欄位缺失，Rust API `GET /api/v1/agents` 會 500，因為 serde 反序列化失敗。

| 欄位 | 型別 | 必填 | 說明 | 範例 |
|------|------|------|------|------|
| `_key` | string | ✅ | UUID v4 | `e7af2ad8-b6fe-43cb-be03-c4c722932346` |
| `name` | string | ✅ | Agent 顯示名稱 | `訂單小秘` |
| `agent_type` | string | ✅ | `bpa` / `tool` / `system` | `bpa` |
| `endpoint_url` | string | ✅ | Python 服務端點 | `http://localhost:8011/order-secretary/chat` |
| `llm_model` | string | ✅ | ModelProvider 中的 model_id | `deepseek-v4-flash` |
| `status` | string | ✅ | `enabled` / `disabled` / `online` | `enabled` |
| `visibility` | string | ✅ | `public` / `private` / `role` | `public` |
| `source` | string | ✅ | `local` / `external` | `local` |
| **`usage_count`** | int | ✅ | **初始為 0，忘記會 500** | `0` |
| **`group_key`** | string | ✅ | **Agent 分組，忘記會 500** | `bpa` |
| `created_at` | string | ✅ | ISO 8601 時間戳 | `2026-04-28T14:41:00Z` |
| `updated_at` | string | ✅ | ISO 8601 時間戳（同 created_at） | `2026-04-28T14:41:00Z` |
| `description` | string | ❌ | 功能描述 | `解析 LINE 訂單文字、圖片...` |
| `system_prompt` | string | ❌ | LLM system prompt（可存在 system_params） | `你是一個專業的...` |
| `tools` | list | ❌ | 工具權限 key 陣列 | `["line_bot_key"]` |

### 建立方式

**優先使用 Rust API**（自動填 `usage_count`/`group_key`）：

```bash
curl -X POST "http://localhost:6500/api/v1/agents" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "訂單小秘",
    "agent_type": "bpa",
    "endpoint_url": "http://localhost:8011/order-secretary/chat",
    "llm_model": "deepseek-v4-flash",
    "status": "enabled",
    "visibility": "public",
    "source": "local",
    "description": "解析 LINE 平台的訂單文字...",
    "system_prompt": "你是一個專業的...",
    "group_key": "bpa"
  }'
```

**直接寫 ArangoDB 務必補上 `usage_count: 0` + `group_key`**（否則 500）。

### 註冊到 unified_agents

在 `ai-services/unified_agents/main.py` 加入路由：

```python
from bpa.order_secretary.router import router as order_secretary_router
app.include_router(order_secretary_router, prefix="/order-secretary")
```

### ⭐ 通訊類 Agent 標準模板：Ragic 小幫手

所有通訊平台（LINE、WhatsApp、Dingtalk 等）的 Agent 一律以 Ragic 小幫手為標準模板：

- **參考實作**：`ai-services/bpa/ragic_agent/`
- **完整規格書**：`.docs/Spec/智能體/Ragic小幫手.md`

> Ragic 小幫手已驗證：意圖分類、KA HybridRAG、多 Provider LLM、多輪對話持久化、LINE 群聊/私聊、圖片理解 — 這些都是通訊類 Agent 的標準能力。

### BPA Agent 標準檔案結構

```
bpa/{agent_name}/
├── __init__.py
├── main.py          # FastAPI 入口
├── config.py        # 環境變數 + System Prompt
├── router.py        # ★ 核心：意圖分類 + LLM + RAG
└── graph/           # LangGraph 節點（預留）
    ├── state.py
    ├── builder.py
    └── nodes/
```

## 開發規範參考

- 系統開發基準：`dev.spec_context` 系統參數（於 `/app/params` 查看）
- 規格產出模型：`dev.requirement_spec_model`（模型名稱，如 `deepseek-v4-flash`）
- 規格產出 Provider：`dev.requirement_spec_provider`（Provider Code，如 `deepseek`，須與 `model_providers` 集合中的記錄對應）
- 完整開發規範：`AGENTS.md`
- 系統規格索引：`.docs/Spec/系統開發/00-index.md`

## 範例

使用者輸入：
```
#dev A01-2617-001 請開始開發 Ragic 小幫手
```

AI Coder 應：
1. 解析 `A01-2617-001`
2. 調用 `GET /api/v1/agent-requirements/by-req-no/A01-2617-001`
3. 取得規格書，寫入 `.opencode/plans/A01-2617-001-spec.md`
4. 分析規格書，列出開發計畫
5. 向使用者確認後開始開發

## 修改歷程
| 日期 | 版本 | 作者 | 變更 |
|------|------|------|------|
| 2026-04-29 | 1.3.0 | AI Agent | @dev 改為 #dev 避免與 OpenCode 快速指令衝突 |
| 2026-04-28 | 1.2.0 | AI Agent | 新增通訊類 Agent 標準模板（Ragic 小幫手） |
| 2026-04-28 | 1.1.0 | AI Agent | 新增 Agent 記錄必填欄位表、`usage_count`/`group_key` 陷阱、建立方式、註冊 unified_agents、BPA 標準檔案結構 |
| 2026-04-27 | 1.0.0 | AI Agent | 初始版本 |
