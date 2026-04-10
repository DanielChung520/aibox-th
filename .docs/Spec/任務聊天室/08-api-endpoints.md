---
lastUpdate: 2026-04-10 21:15:31
author: Daniel Chung
version: 1.1.0
status: 正式版
parent: 00-index.md
---

# 08 — API 端點規格

> **前置閱讀**: [00-index.md](./00-index.md)、[01-architecture.md](./01-architecture.md)  
> **本文件涵蓋**: 12 個新增 Gateway 端點、7 個 Top Orchestrator 端點、詳細 Request/Response 格式、SSE 端點修改、4 個現有端點修改清單，前端 chatApi TypeScript 定義  
> **遵循規範**: `.docs/Spec/API Specification.md` 通用回應格式

---

## 8.0 工作區隔離機制

> **重要更新 (v1.1)**: 所有聊天 API 皆透過 JWT Token 中的 `sub` claim 提取 `user_key`，並據此過濾資料，確保多租戶隔離。

### user_key 提取流程

```
JWT Token → Authorization: Bearer xxx → verify_jwt() → claims.sub → user_key
```

### 資料隔離策略

| 操作 | 隔離方式 |
|------|----------|
| `list_sessions` | `FILTER s.user_key == @user_key` |
| `get_session` | `FILTER s._key == @key AND s.user_key == @user_key` |
| `delete_session` | 需驗證 ownership (`user_key` 匹配) |
| `send_message` | 需驗證 session ownership |
| `get_messages` | `FILTER m.session_key == @key` (session_key 已在有 ownership 的 session 下) |

### 模型選擇邏輯

> **重要更新 (v1.1)**: 模型選擇優先使用所選 provider 的第一個模型，而非系統預設值。

前端發送請求時的模型選擇邏輯：

```typescript
// 優先使用所選 provider 的第一個模型
model: providerConfig?.models?.[0]?.model_id ?? this.getDefaultModel(),
```

**說明**：
- 當使用者選擇 `gemini` provider → 使用 gemini 的模型
- 當使用者選擇 `ollama` provider → 使用 ollama 的模型
- 只有當所選 provider 沒有模型時，才 fallback 到系統預設 (`task_chat.default_model`)

---

## 8.1 任務聊天系統參數

> **系統參數位置**: `system_params` collection，category = `task_chat`

### 8.1.1 系統參數列表

| 參數鍵 | 預設值 | 說明 |
|--------|--------|------|
| `task_chat.default_provider` | `ollama` | 預設 AI provider |
| `task_chat.default_model` | `llama3.2:latest` | 預設模型 |
| `task_chat.temperature` | `0.7` | 生成溫度 (0-1) |
| `task_chat.max_tokens` | `4096` | 最大輸出 token |
| `task_chat.max_history_messages` | `20` | 上下文保留訊息數 |
| `task_chat.greeting_message` | `你好！我是你的 AI 工作助理，有什麼可以幫你的嗎？` | 歡迎訊息 |
| `task_chat.system_prompt` | `你是一個綜合工作協作者...` | 系統提示詞 |

### 8.1.2 系統提示詞模板

```rust
// backend: api/src/api/chat.rs

let system_prompt = get_value("task_chat.system_prompt").unwrap_or_else(|| {
    let base = "你是一個綜合工作協作者，可以天南地北無所不談，協助使用者完成各種工作任務。";
    let mermaid_hint = r#"

【Mermaid 圖表生成須知】
生成 Mermaid 圖表時，請遵守以下規則以確保能正常渲染：
1. 禁止在節點標籤中使用冒號 `:` 或管道符 `|`
2. 禁止使用中文全形括號【】（）《》，請改用英文方括號 `[]` 或尖括號 `<>`
3. 禁止使用中文書名號《》，可用 `<>` 替代
4. 禁止使用中文引號「」或「」，請改用英文單引號 `'` 或雙引號 `"`
5. 節點標籤內如有換行需求，請使用 `<br>`
6. 確保所有 `(` `[` `<` 都有配對的 `)` `]` `>`
7. 不要在 flowchart 的 node ID 中使用中文，請用英文或數字 ID"#;
    format!("{}{}", base, mermaid_hint)
});
```

### 8.1.3 模型供應商 (model_providers)

> **位置**: `model_providers` collection

| Code | 名稱 | 範例模型 |
|------|------|----------|
| `ollama` | Ollama Local | `llama3.2:latest`, `gpt-oss:120b-cloud` |
| `gemini` | Google Gemini | `gemini-2.0-flash` |
| `openai` | OpenAI | `gpt-4o` |
| `anthropic` | Anthropic Claude | `claude-3-5-sonnet` |
| `minimax` | MiniMax | `abab6.5s-chat` |

前端取得 provider 清單後，優先使用所選 provider 的第一個模型：

```typescript
// frontend: src/stores/chatStore.ts
const selectedProvider = this.state.selectedProvider ?? this.getDefaultProviderCode() ?? undefined;
const providerConfig = this.getProviderByCode(selectedProvider ?? null);

const request = {
  provider: selectedProvider,
  model: providerConfig?.models?.[0]?.model_id ?? this.getDefaultModel(),
  // ...
};
```

### 8.1.4 Multi-Provider 實作 (aitask)

> **位置**: `ai-services/aitask/main.py`
> **功能**: 支援 Ollama、MiniMax、OpenAI、Gemini、Anthropic 五種 AI Provider 的串流生成

#### Provider 路由架構

```
get_provider_config(provider, provider_base_url)
    │
    ├── "ollama"     → OLLAMA_BASE_URL + /api/chat
    ├── "openai"     → OPENAI_BASE_URL + /chat/completions
    ├── "minimax"    → MINIMAX_BASE_URL + /chat/completions
    ├── "gemini"     → GEMINI_BASE_URL + /models/{model}:generateContent
    └── "anthropic"  → ANTHROPIC_BASE_URL + /v1/messages
```

#### 串流生成器工廠

```python
# ai-services/aitask/main.py

def get_streaming_generator(provider, base_url, model, messages, temperature, max_tokens):
    if provider == "ollama":
        return stream_ollama(base_url, model, messages, temperature)
    elif provider in ("openai", "minimax"):
        return stream_openai_compatible(base_url, model, messages, temperature, max_tokens)
    elif provider == "gemini":
        return stream_gemini(base_url, model, messages, temperature)
    elif provider == "anthropic":
        return stream_anthropic(base_url, model, messages, temperature, max_tokens)
    else:
        return stream_ollama(base_url, model, messages, temperature)
```

#### Provider 實作差異

| Provider | 端點格式 | 特殊處理 |
|----------|----------|----------|
| Ollama | `/api/chat` | SSE lines 直接轉發 |
| OpenAI/MiniMax | `/chat/completions` | OpenAI-compatible 格式 |
| Gemini | `/models/{model}:generateContent` | 需轉換訊息格式為 `contents` 結構 |
| Anthropic | `/v1/messages` | 需分离 system prompt，使用 `x-api-key` header |

#### Gemini 訊息格式轉換

```python
# 轉換一般訊息格式為 Gemini 格式
gemini_contents = []
for msg in messages:
    if msg["role"] == "user":
        gemini_contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
    elif msg["role"] == "assistant":
        gemini_contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
```

#### Anthropic 訊息格式轉換

```python
# 分離 system prompt 與 user messages
anthropic_messages = []
system_prompt = ""
for msg in messages:
    if msg["role"] == "system":
        system_prompt = msg["content"]
    elif msg["role"] == "user":
        anthropic_messages.append({"role": "user", "content": msg["content"]})
    elif msg["role"] == "assistant":
        anthropic_messages.append({"role": "assistant", "content": msg["content"]})
```

#### 環境變數

| 變數 | 預設值 | 用途 |
|------|--------|------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API |
| `OPENAI_BASE_URL` | `https://api.openai.com` | OpenAI API |
| `MINIMAX_BASE_URL` | `https://api.minimax.chat` | MiniMax API |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com` | Google Gemini API |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Anthropic API |
| `ANTHROPIC_API_KEY` | 環境變數 | Anthropic API Key |

---

## 8.2 新增端點總覽

> 所有端點皆需 JWT 認證（除非另行標註）。遵循 `.docs/Spec/API Specification.md` 通用回應格式。

### Rust API Gateway 新增端點

| 方法 | 端點 | 說明 | 認證 |
|------|------|------|------|
| POST | `/api/v1/chat/sessions` | 建立新會話 | 是 |
| GET | `/api/v1/chat/sessions` | 取得會話列表（按 user_key 過濾） | 是 |
| GET | `/api/v1/chat/sessions/:key` | 取得會話詳情（含訊息） | 是 |
| PUT | `/api/v1/chat/sessions/:key` | 更新會話（標題、狀態） | 是 |
| DELETE | `/api/v1/chat/sessions/:key` | 刪除會話 | 是 |
| POST | `/api/v1/chat/sessions/:key/messages` | 發送聊天訊息 | 是 |
| POST | `/api/v1/chat/bpa/start` | 啟動 BPA 工作流（Path B） | 是 |
| POST | `/api/v1/chat/bpa/:taskId/reply` | 回覆 BPA 提問 | 是 |
| POST | `/api/v1/chat/bpa/:taskId/cancel` | 取消 BPA 任務 | 是 |
| POST | `/api/v1/chat/bpa/:taskId/pause` | 暫停 BPA 任務 | 是 |
| POST | `/api/v1/chat/bpa/:taskId/resume` | 恢復 BPA 任務 | 是 |
| GET | `/api/v1/sse/chat/:contextId` | SSE 聊天串流（修改現有） | 是 |

### Top Orchestrator 新增端點 (port 8001)

| 方法 | 端點 | 說明 |
|------|------|------|
| POST | `/chat` | 接收聊天訊息，啟動 LangGraph |
| POST | `/bpa/handover` | 接收 TASK_HANDOVER，轉發 BPA |
| POST | `/bpa/reply` | 接收 USER_MESSAGE，轉發 BPA |
| POST | `/bpa/control` | BPA 控制操作（cancel/pause/resume） |
| GET | `/tools` | 取得可用工具清單 |
| POST | `/tools/refresh` | 刷新工具註冊表 |
| GET | `/health` | 健康檢查 |

---

## 8.3 端點詳細規格

### 8.2.1 POST /api/v1/chat/sessions

建立新的聊天會話。

**Request**:
```json
{
  "title": "新對話（可選）",
  "provider": "ollama",
  "model": "llama3.2:latest"
}
```

**Response** (200):
```json
{
  "code": 0,
  "data": {
    "_key": "ses_uuid_v4",
    "title": "新對話",
    "provider": "ollama",
    "model": "llama3.2:latest",
    "status": "active",
    "user_key": "admin",
    "created_at": "2026-03-27T10:00:00Z",
    "updated_at": "2026-03-27T10:00:00Z"
  }
}
```

**說明**：
- `user_key` 從 JWT claims.sub 自動提取
- `provider` + `model` 決定該 session 使用的 AI 模型

### 8.2.2 GET /api/v1/chat/sessions

取得使用者的會話列表（按 user_key 自動過濾）。

**Response** (200):
```json
{
  "code": 0,
  "data": [
    {
      "_key": "ses_uuid_v4",
      "title": "物料查詢",
      "provider": "ollama",
      "model": "llama3.2:latest",
      "status": "active",
      "user_key": "admin",
      "created_at": "2026-03-27T10:00:00Z",
      "updated_at": "2026-03-27T10:30:00Z"
    }
  ]
}
```

### 8.2.3 GET /api/v1/chat/sessions/:key

取得會話詳情，包含完整訊息列表。

**Response** (200):
```json
{
  "code": 0,
  "data": {
    "session": {
      "_key": "ses_uuid_v4",
      "title": "物料查詢",
      "provider": "ollama",
      "model": "llama3.2:latest",
      "status": "active",
      "user_key": "admin",
      "tags_5w1h": {
        "what": "...",
        "who": "...",
        "when": "...",
        "where": "...",
        "why": "...",
        "how": "..."
      },
      "created_at": "2026-03-27T10:00:00Z",
      "updated_at": "2026-03-27T10:30:00Z"
    },
    "messages": [
      {
        "_key": "msg_uuid",
        "session_key": "ses_uuid_v4",
        "role": "user",
        "content": "查詢 A 倉庫的螺絲庫存",
        "tokens": null,
        "created_at": "2026-03-27T10:05:00Z"
      },
      {
        "_key": "msg_uuid",
        "session_key": "ses_uuid_v4",
        "role": "assistant",
        "content": "根據查詢結果，A 倉庫目前有...",
        "thinking": "...",
        "tokens": 1650,
        "created_at": "2026-03-27T10:05:03Z"
      }
    ]
  }
}
```
  }
}
```

### 8.2.4 POST /api/v1/chat/send

發送聊天訊息（Path A 核心端點）。

**Request**:
```json
{
  "session_id": "ses_a1b2c3d4",
  "message": "上個月 A 倉庫的螺絲出貨量是多少？",
  "reply_mode": "auto",
  "context_id": "ctx_x1y2z3"
}
```

**Response** (202 Accepted):
```json
{
  "code": 0,
  "data": {
    "message_id": "msg_003",
    "context_id": "ctx_x1y2z3",
    "status": "processing"
  }
}
```

**說明**：
- 回應 202（非 200），表示訊息已接受但處理尚未完成
- 實際回應透過 SSE `/api/v1/sse/chat/{context_id}` 串流傳送
- Gateway 收到請求後：
  1. 寫入 `chat_messages` (role: user)
  2. 轉發至 Top Orchestrator `POST /chat`
  3. Top Orchestrator 啟動 LangGraph，透過 SSE 回傳結果

### 8.2.5 POST /api/v1/chat/bpa/start

啟動 BPA 工作流（Path B 核心端點）。

**Request**:
```json
{
  "session_id": "ses_b1c2d3e4",
  "agent_id": "agents/mm_agent_001",
  "user_input": "查詢本月所有低於安全庫存的物料",
  "context": {
    "warehouse": "A",
    "date_range": "2026-03"
  }
}
```

**Response** (202 Accepted):
```json
{
  "code": 0,
  "data": {
    "task_id": "task_uuid_001",
    "context_id": "ctx_y1z2a3",
    "agent_name": "物料管理代理",
    "status": "started"
  }
}
```

**說明**：
- Gateway 建構 TASK_HANDOVER 訊息（[04-path-b-bpa-workflow.md](./04-path-b-bpa-workflow.md) §4.3 格式）
- 轉發至 Top Orchestrator `POST /bpa/handover`
- Top Orchestrator 轉發至對應 BPA service
- BPA 回應透過 SSE 串流

### 8.2.6 POST /api/v1/chat/bpa/:taskId/reply

回覆 BPA 的 `BPA_ASK_USER` 提問。

**Request**:
```json
{
  "session_id": "ses_b1c2d3e4",
  "message": "確認，使用預設的安全庫存計算公式",
  "reply_to_step": "ask_user_confirmation"
}
```

**Response** (202 Accepted):
```json
{
  "code": 0,
  "data": {
    "message_id": "msg_reply_001",
    "status": "processing"
  }
}
```

### 8.2.7 BPA 控制端點

**POST /api/v1/chat/bpa/:taskId/cancel**
```json
// Request
{ "session_id": "ses_b1c2d3e4", "reason": "使用者手動取消" }
// Response (200)
{ "code": 0, "data": { "status": "cancelled" } }
```

**POST /api/v1/chat/bpa/:taskId/pause**
```json
// Request
{ "session_id": "ses_b1c2d3e4" }
// Response (200)
{ "code": 0, "data": { "status": "paused", "checkpoint_version": 3 } }
```

**POST /api/v1/chat/bpa/:taskId/resume**
```json
// Request
{ "session_id": "ses_b1c2d3e4" }
// Response (200)
{ "code": 0, "data": { "status": "resumed" } }
```

---

## 8.4 SSE 端點修改

### GET /api/v1/sse/chat/:contextId（修改現有）

現有 `api/src/api/sse.rs` 的 `chat_stream` 函數需要從模擬數據改為真實代理回應。

**修改重點**：

1. **移除模擬邏輯**：刪除 `tokio::time::sleep` + 固定文字的模擬回應
2. **建立代理連線**：與 Top Orchestrator SSE endpoint 建立反向代理
3. **事件轉發**：Top Orchestrator 的 SSE 事件 → 轉發給前端 EventSource
4. **心跳機制**：每 15 秒發送 `event: heartbeat`

```rust
// 修改前 (模擬)
async fn chat_stream(Path(context_id): Path<String>) -> Sse<impl Stream<Item = ...>> {
    let stream = stream::iter(vec!["模擬回應..."])
        .map(|chunk| Ok(Event::default().event("chunk").data(chunk)));
    Sse::new(stream)
}

// 修改後 (真實代理)
async fn chat_stream(
    Path(context_id): Path<String>,
    State(state): State<AppState>,
) -> Sse<impl Stream<Item = ...>> {
    // 建立與 Top Orchestrator 的 SSE 連線
    // 透過 reqwest 連線至 http://localhost:8001/stream/{context_id}
    // 轉發所有事件給前端
}
```

---

## 8.5 現有端點修改清單

| 端點 | 檔案 | 修改內容 |
|------|------|---------|
| `POST /api/v1/ai/chat` | `api/src/api/ai.rs` | 移除 echo mock，改為轉發至 Top Orchestrator |
| `GET /api/v1/sse/chat/:id` | `api/src/api/sse.rs` | 移除模擬，建立真實 SSE 代理 |
| `forward_bpa` | `api/src/services/ai_proxy.rs` | 端點從 `/start` 改為 `/process` |
| `routes` | `api/src/api/mod.rs` | 新增 chat/bpa 路由群組 |

---

## 8.6 前端 API 層新增

```typescript
// src/services/api.ts — 新增 chatApi

export interface CreateSessionRequest {
  mode: 'open_chat' | 'bpa_workflow';
  title?: string;
  bpa_agent_id?: string;
}

export interface CreateSessionResponse {
  session_id: string;
  context_id: string;
  mode: string;
  created_at: string;
}

export interface SendMessageRequest {
  session_id: string;
  message: string;
  reply_mode: 'auto' | 'fast' | 'detail';
  context_id: string;
}

export interface BpaStartRequest {
  session_id: string;
  agent_id: string;
  user_input: string;
  context?: Record<string, unknown>;
}

export const chatApi = {
  // === 會話管理 ===
  createSession: (data: CreateSessionRequest) =>
    api.post<{ code: number; data: CreateSessionResponse }>('/api/v1/chat/sessions', data),
  
  listSessions: (params?: { page?: number; page_size?: number; status?: string }) =>
    api.get<{ code: number; data: { sessions: any[]; total: number } }>('/api/v1/chat/sessions', { params }),
  
  getSession: (id: string, params?: { message_limit?: number; before?: string }) =>
    api.get<{ code: number; data: any }>(`/api/v1/chat/sessions/${id}`, { params }),
  
  deleteSession: (id: string) =>
    api.delete(`/api/v1/chat/sessions/${id}`),
  
  updateSession: (id: string, data: { title?: string; status?: string }) =>
    api.patch(`/api/v1/chat/sessions/${id}`, data),
  
  // === Path A: 開放聊天 ===
  sendMessage: (data: SendMessageRequest) =>
    api.post<{ code: number; data: { message_id: string; context_id: string } }>('/api/v1/chat/send', data),
  
  // === Path B: BPA 工作流 ===
  startBpa: (data: BpaStartRequest) =>
    api.post<{ code: number; data: { task_id: string; context_id: string } }>('/api/v1/chat/bpa/start', data),
  
  replyBpa: (taskId: string, data: { session_id: string; message: string }) =>
    api.post(`/api/v1/chat/bpa/${taskId}/reply`, data),
  
  cancelBpa: (taskId: string, data: { session_id: string; reason?: string }) =>
    api.post(`/api/v1/chat/bpa/${taskId}/cancel`, data),
  
  pauseBpa: (taskId: string, data: { session_id: string }) =>
    api.post(`/api/v1/chat/bpa/${taskId}/pause`, data),
  
  resumeBpa: (taskId: string, data: { session_id: string }) =>
    api.post(`/api/v1/chat/bpa/${taskId}/resume`, data),
};
```

---

> **SSE 事件格式定義**：見 [02-protocol.md](./02-protocol.md) §2.2。  
> **錯誤碼與 HTTP 狀態**：見 [09-error-security.md](./09-error-security.md) §9.1.1。
