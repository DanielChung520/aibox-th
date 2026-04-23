# EEA AIBOX 執行架構

---
lastUpdate: 2026-04-14
author: AI Agent (根據代碼調查與 Oracle 架構分析)
version: 1.1.0
---

## 目錄

1. [系統概覽](#1-系統概覽)
2. [流程圖架構](#2-流程圖架構)
3. [現有程式碼地圖](#3-現有程式碼地圖)
4. [缺口分析](#4-缺口分析)
5. [與現有程式碼的整合點](#5-與現有程式碼的整合點)
6. [安全性分析與 Security Agent](#6-安全性分析與-security-agent)
   - [6.1 當前安全狀態](#61-當前安全狀態)
   - [6.2 攻擊面分析](#62-攻擊面分析)
   - [6.3 必須修復的安全問題](#63-必須修復的安全問題)
   - [6.4 Security Agent（安全代理）](#64-security-agent安全代理)
7. [Phase 實作規劃](#7-phase-實作規劃)
8. [風險與對策](#8-風險與對策)
9. [附錄：關鍵程式碼位置索引](#9-附錄關鍵程式碼位置索引)

---

## 1. 系統概覽

### 1.1 設計願景

EEA AIBOX 是一個企業級 AI Agent 平台，透過三層 Agent 架構實現智慧化任務執行：

| Agent 類型 | 職責 | 特點 |
|------------|------|------|
| **Top Orchestrator** | 統一意圖理解與任務分發 | SLM Fine-tune + Intents RAG |
| **BPA Agent** | 固定業務流程執行 | Domain-specific (MM/FI/HR) |
| **CA Agent** | 臨時主題顧問咨詢 | 動態工具掛載、多維度檢索 |
| **PDCA Agent** | 複雜任務閉環管理 | Plan-Do-Check-Act + Clarification |

### 1.2 設計原則

| 原則 | 說明 |
|------|------|
| **Single Source of Truth** | ArangoDB `intent_catalog` 是唯一主資料來源 |
| **職責分離** | BPA 專注流程、CA 負責探索、PDCA 負責管理 |
| **自我進化** | 透過 ISFTA 收集負面教材，累積 2000 筆後 Fine-tune |
| **安全第一** | 所有執行點必須有 Permission Guardrail |

---

## 2. 流程圖架構

### 2.1 Top Orchestrator

![1776140148451](image/EEAAIBOX執行架構/1776140148451.png)

**核心邏輯**：

```
User Input
    ↓
Intent Understanding (Intent LLM)
  ├── 理解用戶意圖
  ├── 識別實體
  └── 判斷動作類型
        ↓
┌────────────────────────────────────────────┐
│ Action Execution                           │
├────────────────────────────────────────────┤
│ Direct Answer → LLM Response              │
│ Tool Call → Tool Registry → (Web/Data/Knowledge) │
│ Process → Orchestrator                     │
│   ├── create task / create session         │
│   ├── assign agent                         │
│   ├── monitor                             │
│   └── report                              │
└────────────────────────────────────────────┘
    ↓
Feedback Loop (Learning)
```

**特點**：
- **雙軌比對機制**：SLM Fine-tune（速度）+ Intents RAG（知識擴充）
- **三類 Action 分流**：Direct Answer / Tool Call / Process
- **Feedback Loop**：將執行結果回流至 Intents RAG，累積學習

---

### 2.2 BPA（Business Process Agent）

![1776140201430](image/EEAAIBOX執行架構/1776140201430.png)

**核心邏輯**：

```
User Request (自然語言)
    ↓
Intent Understanding
    ↓
Determine Action
├── Query/Report → Data Agent
├── Workflow → BPA Agent
└── Knowledge → Knowledge Agent
    ↓
Action Execution
    ↓
Result/Response
```

**特點**：
- **Domain-specific**：專注於 MM (物料管理)、FI (財務)、HR (人力資源)
- **預先定義的工具**：SOP、API、審批流程
- **強約束**：減少靈活性換取穩定性

---

### 2.3 PDCA Agent

![1776140311755](image/EEAAIBOX執行架構/1776140311755.png)

**核心邏輯**：

```
Plan
├── Create task list (編排 todos)
└── Set task goals (設置任務節點目標)
    ↓
Do
├── Submit Celery async execution (提交 Celery 異步執行)
└── [If problem] → Clarify Session (澄清 session)
    ↓
Check
├── Verify completion (檢驗是否完成目標)
└── Validate results (監督執行)
    ↓
Act
├── Optimize & Report (回報優化結果)
└── End PDCA Session (結束 pdca session)
```

**特點**：
- **里程碑式記憶 (Milestone Memory)**：只保留關鍵決策，而非所有思考鏈
- **Clarification Session**：遇問題時創建澄清 session，獲得答案後繼續
- **Break Point 保護**：防止死循環

---

### 2.4 CA（Consultant Agent）- 待補充

> **規劃中**：CA 的流程與 BPA 類似，但更側重臨時主題處理。

**與 BPA 的差異**：

| 維度 | BPA | CA |
|-----|-----|-----|
| 目標 | 固定業務流程 | 臨時性、探索性主題 |
| 工具 | 預先定義好的 Internal Tools | 需動態掛載 |
| 深度 | 單一系統深耕 | 多系統廣度串聯 |
| 記憶 | 不需要長期 | 需要 User Preference 記憶 |

**CA 的多維度檢索流程**：
```
1. 主題理解 → Tool Catalog 搜尋
2. 動態掛載相關 Tools
3. 跨系統資料對齊 (Web + DB + Knowledge)
4. 產出顧問建議
5. 若需要執行 → 升級到 BPA 或建立 PDCA Run
```

---

## 3. 現有程式碼地圖

### 3.1 目錄結構

```
ai-services/
├── aitask/                          # AITask - 主要 Orchestrator
│   ├── main.py                       # FastAPI 入口
│   ├── config.py                     # 設定檔
│   ├── graph/
│   │   ├── state.py                  # TopState 定義
│   │   ├── builder.py                # LangGraph 建構
│   │   └── nodes/
│   │       ├── intent_classifier.py  # 意圖分類（3層 cascade）
│   │       ├── chat_responder.py     # 聊天回覆
│   │       ├── tool_executor.py      # 工具執行
│   │       ├── bpa_orchestrator.py   # BPA 入口（目前 stub）
│   │       ├── da_query.py           # Data Agent 查詢
│   │       ├── ka_search.py          # Knowledge Agent 搜尋
│   │       └── memory_manager.py     # 記憶管理
│   ├── tools/
│   │   ├── registry.py               # 工具註冊表
│   │   └── executors.py              # 工具執行器
│   └── checkpointer/
│       └── arango_saver.py           # LangGraph ArangoDB checkpoint
│
├── bpa/                              # BPA 服務
│   ├── main.py                       # 通用 BPA
│   └── mm_agent/                     # MM 特定 BPA
│       └── main.py
│
├── celery_app/
│   ├── app.py                        # Celery 設定
│   └── tasks.py                      # 非同步任務
│
├── security_agent/                    # Security Agent (新增)
│   ├── main.py                       # FastAPI 入口
│   ├── config.py                     # 設定檔
│   ├── auth/
│   │   ├── token_verifier.py         # JWT 驗證
│   │   └── user_resolver.py          # 用戶身份解析
│   ├── permission/
│   │   ├── rbac_checker.py           # RBAC 權限檢查
│   │   └── resource_guard.py          # 資源保護
│   ├── audit/
│   │   ├── logger.py                 # 審計日誌寫入
│   │   ├── report_generator.py        # 審計報告生成
│   │   └── anomaly_detector.py        # 異常行為偵測
│   └── models.py                     # Pydantic 模型
│
├── memory_agent/                     # 記憶服務
│   ├── main.py
│   └── core/
│       ├── models.py
│       ├── session_memory.py
│       ├── working_memory.py
│       ├── storage.py
│       ├── recall.py
│       └── consolidation.py
│
├── mcp_tools/                        # MCP 工具服務
│   └── main.py                       # /tools, /execute 端點
│
├── data_agent/                        # Data Agent
│   ├── intent_rag/
│   │   └── router.py                 # Qdrant intent matching
│   └── query/
│       └── nl2sql/
│           ├── orchestrator.py
│           └── intent_classifier.py
│
└── tools/                            # 工具實作
    ├── web_search/
    └── weather/

api/src/                              # Rust API Gateway
├── api/
│   ├── chat.rs                       # Chat session CRUD
│   ├── intent.rs                     # 意圖路由
│   └── mod.rs
├── services/chat/
│   ├── orchestrator.rs               # 聊天協調器
│   ├── clients.rs                    # HTTP 客戶端
│   ├── repo.rs                      # 資料庫操作
│   └── sse_proxy.rs                 # SSE 代理
└── db/
    └── mod.rs                        # DB 模型與初始化
```

---

### 3.2 現有實作狀態矩陣

| 流程圖元件 | 現有實作 | 檔案位置 | 狀態 |
|-----------|---------|---------|------|
| Intent Understanding | ✅ | `aitask/graph/nodes/intent_classifier.py` | 3層 cascade，但 hardcoded regex |
| Direct Answer | ✅ | `aitask/graph/nodes/chat_responder.py` | 完整 |
| Tool Call | ✅ | `aitask/graph/nodes/tool_executor.py` | 完整，但 auth_token="" |
| Process Orchestrator | ⚠️ | `aitask/graph/nodes/bpa_orchestrator.py` | **Stub** |
| PDCA Loop | ❌ | - | 不存在 |
| Clarify Session | ❌ | - | 不存在 |
| Celery Async | ⚠️ | `celery_app/tasks.py` | 只有 KB tasks |
| Memory Manager | ⚠️ | `aitask/graph/nodes/memory_manager.py` | 滑動窗口，非 Milestone |
| Shared Workspace | ⚠️ | `memory_agent/core/storage.py` | per-project 目錄 |
| Permission Check | ⚠️ | `api/src/api/mod.rs` | 只有 listing filter |
| Tool Registry | ✅ | `aitask/tools/registry.py` | 靜態註冊 |
| Dynamic Tool Catalog | ❌ | - | 不存在 |
| **Security Agent** | ❌ | - | **不存在，需新增** |
| Audit Logging | ❌ | - | **不存在，需新增** |
| Anomaly Detection | ❌ | - | **不存在，需新增** |

---

## 4. 缺口分析

### 4.1 Stub 元件盤點

#### bpa_orchestrator.py（完整 stub）

```python
# 檔案：ai-services/aitask/graph/nodes/bpa_orchestrator.py
async def bpa_orchestrator_node(state: TopState) -> dict[str, object]:
    return {
        "messages": [
            AIMessage(content="BPA 流程功能開發中，目前暫不支援。")
        ]
    }
```

**問題**：沒有任何實作，只有錯誤訊息。

#### tool_executor.py（auth_token 問題）

```python
# 檔案：ai-services/aitask/graph/nodes/tool_executor.py (約第 86-92 行)
context = ToolExecutionContext(
    user_id=state["user_id"],
    session_id=state["session_id"],
    trace_id=...,
    auth_token="",  # ← 永遠是空的！
    correlation_id=tool_call_id,
)
```

**問題**：無法對下游服務進行身份驗證。

#### intent_classifier.py（hardcoded regex）

```python
# 檔案：ai-services/aitask/graph/nodes/intent_classifier.py (約第 18-35 行)
RULE_PATTERNS = {
    "data_query": re.compile(r"(查詢|查看|報表|...)"),
    "knowledge": re.compile(r"(知識|文件|...)"),
    "tool_use": re.compile(r"(執行|運行|...)"),
    "bpa_task": re.compile(r"(流程|審批|...)"),
}
```

**問題**：意圖規則寫死在程式碼，非從 `intent_catalog` 動態載入。

---

### 4.2 安全缺口

#### 4.2.1 無執行權限檢查

| 服務 | 端點 | Auth | Permission Check |
|------|------|------|------------------|
| MCP Tools | `/execute` | ❌ 無 | ❌ 無 |
| BPA | `/execute` | ❌ 無 | ❌ 無 |
| BPA | `/execute-async` | ❌ 無 | ❌ 無 |
| AITask | `/v1/graph/chat` | ⚠️ JWT in headers | ❌ 無 downstream |

**風險**：任何能發請求的人都可以執行任何工具和 BPA 流程！

#### 4.2.2 Token 未轉發

```rust
// 檔案：api/src/services/chat/clients.rs (約第 18-31 行)
pub async fn call_aitask_chat(body: serde_json::Value) -> Result<reqwest::Response, StatusCode> {
    let response = HTTP_CLIENT
        .post(format!("{}/v1/chat/completions", CONFIG.ai_services.aitask_url))
        .json(&body)
        .send()
        .await
        // ❌ 沒有附加 Authorization header！
```

---

### 4.3 架構缺口

#### 4.3.1 PDCA 元件完全欠缺

| 元件 | 說明 | 現有 |
|------|------|------|
| `orchestrator_runs` | PDCA run 持久化 | ❌ 不存在 |
| `pdca_breaker` | Break Point 保護 | ❌ 不存在 |
| `definition_of_done` | DoD 生成器 | ❌ 不存在 |
| `clarification_session` | 澄清 session 管理 | ❌ 不存在 |
| `milestone_memory` | 里程碑記憶 | ⚠️ 只有 summary |

#### 4.3.2 CA Agent 完全欠缺

| 元件 | 說明 | 現有 |
|------|------|------|
| `consultant_agent` | CA 主體 | ❌ 不存在 |
| `tool_catalog` | 工具索引目錄 | ⚠️ 只有靜態 registry |
| `dynamic_tool_loader` | 動態工具掛載 | ❌ 不存在 |

---

## 5. 與現有程式碼的整合點

### 5.1 Intent Layer 整合

#### 現有流程

```
User Message → classify_intent_node → route_by_intent → [chat_responder|da_query|ka_search|tool_executor|bpa_orchestrator]
```

#### 改造目標

```
User Message → match_intent_node → planner_node → [execute_direct|execute_tool|execute_pdca]
```

#### 整合點

| 元件 | 檔案 | 整合方式 |
|------|------|---------|
| Qdrant Intent Match | `data_agent/intent_rag/router.py` | 復用 `/intent/match` API |
| 小模型分類 | 新增 `intent_classifier_node` | 使用 `qwen2.5:1.5b` |
| ActionPlan Schema | 新增 `aitask/pdca/action_plan.py` | 定义 direct_answer/tool_call/process_orchestration |
| 現有 intent_classifier | `aitask/graph/nodes/intent_classifier.py` | 廢除 hardcoded regex |

---

### 5.2 Tool Execution 整合

#### 現有流程

```
LLM response with tool_calls → tool_executor_node → ToolRegistry.execute → [MCPToolExecutor|DataAgentExecutor|KnowledgeAgentExecutor|BuiltinExecutor]
```

#### 改造目標

```
planner_node output: pending_tool_calls → tool_executor_node → execute with real auth_token
```

#### 整合點

| 元件 | 檔案 | 整合方式 |
|------|------|---------|
| TopState 擴展 | `aitask/graph/state.py` | 新增 `pending_tool_calls` 欄位 |
| tool_executor 改造 | `aitask/graph/nodes/tool_executor.py` | 支援 `pending_tool_calls` + 真实 `auth_token` |
| clients 改造 | `api/src/services/chat/clients.rs` | 轉發 Authorization header |
| MCP auth | `ai-services/mcp_tools/main.py` | `/execute` 新增 token 驗證 |

---

### 5.3 PDCA 執行整合

#### 現有流程

```
bpa_orchestrator (stub) → 返回 "不支援" 訊息
```

#### 改造目標

```
planner_node (process_orchestration) → execute_pdca → orchestrator_runs → Celery tasks
```

#### 整合點

| 元件 | 檔案 | 整合方式 |
|------|------|---------|
| orchestrator_runs | 新增 collection | 持久化 PDCA run 狀態 |
| bpa_orchestrator | `aitask/graph/nodes/bpa_orchestrator.py` | 完全重寫 |
| pdca_breaker | 新增 `aitask/pdca/pdca_breaker.py` | Break Point 邏輯 |
| definition_of_done | 新增 `aitask/pdca/definition_of_done.py` | DoD 生成與驗證 |
| Celery tasks | `celery_app/tasks.py` | 擴展支援 BPA tasks |
| BPA MM | `ai-services/bpa/mm_agent/main.py` | 對接 PDCA 執行 |

---

### 5.4 Memory 整合

#### 現有流程

```
memory_manager_node → 滑動窗口 summary → long_term_memory
```

#### 改造目標

```
milestone_checkpoint → MilestoneRecord → orchestrator_runs.milestones
```

#### 整合點

| 元件 | 檔案 | 整合方式 |
|------|------|---------|
| SessionMemory | `memory_agent/core/session_memory.py` | 擴展 `key_results` 為正式 Milestone |
| milestone_memory | 新增 `aitask/pdca/milestone_memory.py` | 結構化里程碑 |
| memory_manager | `aitask/graph/nodes/memory_manager.py` | 改為 Milestone 觸發 |

---

### 5.5 Session 整合

#### 現有 Session 模型

```rust
// 檔案：api/src/db/mod.rs
struct ChatSession {
    _key: Option<String>,
    title: Option<String>,
    provider: String,
    model: String,
    status: String,
    tags_5w1h: Option<serde_json::Value>,
    user_key: String,
    created_at: String,
    updated_at: String,
}
```

#### 建議新增 OrchestratorRun 模型

```rust
// 新增 collection: orchestrator_runs
struct OrchestratorRun {
    _key: Option<String>,        // run_id
    session_key: String,         // 關聯的 chat session
    parent_run_id: Option<String>, // 父 run (for clarification)
    kind: String,               // "pdca" | "clarify"
    status: String,             // "running" | "waiting" | "completed" | "failed"
    phase: String,              // "plan" | "do" | "check" | "act"
    intent_type: String,        // matched intent
    matched_intent_id: Option<String>,
    tool_name: Option<String>,
    workflow_id: Option<String>,
    checkpoint_id: Option<String>,
    milestones: Vec<Milestone>,
    definition_of_done: Vec<CompletionCriterion>,
    current_goal: Option<String>,
    todo_list: Vec<TodoItem>,
    summary: Option<String>,
    last_error: Option<String>,
    created_at: String,
    updated_at: String,
}

struct Milestone {
    milestone_id: String,
    title: String,
    decision: Option<String>,
    result: Option<String>,
    verified_facts: Vec<String>,
    status: String,
    created_at: String,
}

struct TodoItem {
    todo_id: String,
    title: String,
    status: String,
    goal: Option<String>,
    celery_task_id: Option<String>,
}

struct CompletionCriterion {
    criterion_id: String,
    type: String,       // "api_call" | "data_exists" | "semantic_match"
    params: serde_json::Value,
    status: String,     // "pending" | "verified" | "failed"
}
```

---

## 6. 安全性分析與 Security Agent

### 6.1 當前安全狀態

| 層級 | 保護狀態 | 說明 |
|------|---------|------|
| API Gateway | ✅ JWT | Rust middleware 驗證 |
| Session Listing | ✅ RBAC | 只顯示允許的 session |
| Function Listing | ✅ RBAC | 根據 role 過濾 |
| **Tool Execution** | ❌ **裸奔** | **無任何權限檢查** |
| **BPA Execution** | ❌ **裸奔** | **無任何權限檢查** |
| **MCP Execute** | ❌ **裸奔** | **無任何權限檢查** |

### 6.2 攻擊面分析

```
攻擊者取得一般用戶 token
    ↓
透過 Chat API 發送惡意意圖
    ↓
觸發 tool_call → MCP /execute
    ↓
執行 web_search / data_query 等工具
    ↓
無需任何額外權限！
```

### 6.3 必須修復的安全問題

#### 6.3.1 修復 auth_token="" 問題

**檔案**：`ai-services/aitask/graph/nodes/tool_executor.py`

**現有**：
```python
context = ToolExecutionContext(
    auth_token="",
    ...
)
```

**改造後**：
```python
# 從 TopState 或 request context 取得真實 token
auth_token = state.get("auth_token", "")
context = ToolExecutionContext(
    auth_token=auth_token,
    ...
)
```

#### 6.3.2 轉發 Authorization Header

**檔案**：`api/src/services/chat/clients.rs`

**現有**：
```rust
pub async fn call_aitask_chat(body: serde_json::Value) -> Result<reqwest::Response, StatusCode> {
    let response = HTTP_CLIENT
        .post(format!("{}/v1/chat/completions", CONFIG.ai_services.aitask_url))
        .json(&body)
        .send()
        .await
        // ❌ 沒有附加 Authorization
```

**改造後**：
```rust
pub async fn call_aitask_chat(
    body: serde_json::Value,
    auth_header: Option<String>,
) -> Result<reqwest::Response, StatusCode> {
    let mut request = HTTP_CLIENT
        .post(format!("{}/v1/chat/completions", CONFIG.ai_services.aitask_url))
        .json(&body);
    
    if let Some(auth) = auth_header {
        request = request.header("Authorization", auth);
    }
    
    request.send().await...
}
```

#### 6.3.3 BPA /execute 加入 Permission Check

**檔案**：`ai-services/bpa/mm_agent/main.py`

**現有**：
```python
@app.post("/execute")
async def execute_workflow(request: WorkflowExecutionRequest):
    # ❌ 無任何權限檢查
    return await execute_workflow_impl(request)
```

**改造後**：
```python
@app.post("/execute")
async def execute_workflow(
    request: WorkflowExecutionRequest,
    Authorization: str = Header(None),
):
    # 1. 驗證 token
    user = await verify_token(Authorization)
    
    # 2. 檢查權限
    workflow_perms = await get_workflow_permissions(request.workflow_id)
    if not user_has_permission(user, workflow_perms):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return await execute_workflow_impl(request)
```

---

### 6.4 Security Agent（安全代理）

#### 6.4.1 設計理念

> **「安全是第一天就該建設的，不是事後補丁。」**
>
> Security Agent 作為一個專門的小模型 Agent，負責所有身份驗證、權限檢查、審計記錄與異常偵測工作。

**核心職責**：

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Agent                            │
│                  (專用小模型: qwen2.5:1.5b)                   │
├─────────────────────────────────────────────────────────────┤
│  1. 身份驗證 (Authentication)                              │
│     - 驗證 JWT token 有效性                                 │
│     - 解析用戶身份與角色                                   │
│     - 防止 Token 偽造/過期                                │
│                                                             │
│  2. 權限檢查 (Authorization)                                │
│     - 查詢 user → roles → permissions                     │
│     - 檢查 tool/workflow 是否有權限執行                    │
│     - 資源訪問控制 (data, API, workflow)                    │
│                                                             │
│  3. 審計日誌 (Audit Logging)                               │
│     - 記錄所有執行嘗試 (成功/失敗)                         │
│     - 記錄時間、用戶、資源、動作、結果                      │
│     - 即時寫入 ArangoDB audit_logs                         │
│                                                             │
│  4. 異常偵測 (Anomaly Detection)                           │
│     - 速率限制 (rate limit)                                │
│     - 異常時間訪問                                         │
│     - 大量失敗嘗試                                         │
│     - 跨帳戶異常訪問                                        │
│                                                             │
│  5. 審計報告 (Audit Reporting)                             │
│     - 產出結構化審計報告                                   │
│     - 異常行為分析                                         │
│     - 合規性報表                                           │
└─────────────────────────────────────────────────────────────┘
```

**為什麼要用專用小模型？**

| 考量 | 大模型 (GPT-4/Claude) | 專用小模型 (qwen2.5:1.5b) |
|------|----------------------|---------------------------|
| 延遲 | 高 (2-5秒) | 低 (<100ms) |
| 成本 | 高 (每次 $0.01+) | 低 (接近零) |
| 能力 | 過度複雜 | 剛好够用 (簡單 yes/no) |
| 穩定性 | 可能有創意性輸出 | 確定性輸出 |

#### 6.4.2 架構設計

**目錄結構**：

```
ai-services/
└── security_agent/                    # 新增
    ├── main.py                        # FastAPI 入口
    ├── config.py                      # 設定檔
    ├── auth/
    │   ├── token_verifier.py         # JWT 驗證
    │   └── user_resolver.py          # 用戶身份解析
    ├── permission/
    │   ├── rbac_checker.py          # RBAC 權限檢查
    │   └── resource_guard.py         # 資源保護
    ├── audit/
    │   ├── logger.py                 # 審計日誌寫入
    │   ├── report_generator.py       # 審計報告生成
    │   └── anomaly_detector.py       # 異常行為偵測
    └── models.py                     # Pydantic 模型
```

**與現有架構的整合**：

```
┌────────────────────────────────────────────────────────────────────┐
│                        請求流程                                      │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   User Request                                                      │
│        │                                                           │
│        ▼                                                           │
│   ┌─────────────────┐                                              │
│   │  API Gateway    │ ─── JWT 初步驗證                             │
│   │  (Rust)         │                                              │
│   └────────┬────────┘                                              │
│            │                                                        │
│            ▼                                                        │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │              Security Agent Check                            │  │
│   │  ┌─────────────────────────────────────────────────────┐   │  │
│   │  │  1. Token Verification (驗證 JWT)                    │   │  │
│   │  │  2. RBAC Permission Check (權限檢查)                 │   │  │
│   │  │  3. Anomaly Detection (異常偵測)                     │   │  │
│   │  │  4. Audit Log (寫入審計日誌)                        │   │  │
│   │  └─────────────────────────────────────────────────────┘   │  │
│   │                        │                                    │  │
│   │         ┌────────────┴────────────┐                        │  │
│   │         ▼                         ▼                        │  │
│   │    [Allowed]                [Denied]                        │  │
│   │         │                         │                        │  │
│   │         ▼                         ▼                        │  │
│   │   下游服務執行              Return 403                    │  │
│   │         │                   + Audit Log                   │  │
│   │         ▼                                                  │  │
│   │   [Success/Failure]                                        │  │
│   │         │                                                  │  │
│   │         ▼                                                  │  │
│   │   Audit Log (成功/失敗)                                    │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

#### 6.4.3 API 設計

**Endpoints**:

| 方法 | 端點 | 說明 |
|------|------|------|
| POST | `/security/check` | 權限檢查 |
| POST | `/security/log` | 寫入審計日誌 |
| POST | `/security/log/denial` | 寫入拒絕日誌 |
| GET | `/security/logs` | 查詢審計日誌 |
| GET | `/security/reports` | 獲取審計報告 |
| POST | `/security/reports/generate` | 生成報告 |
| GET | `/security/anomalies` | 查詢異常事件 |
| GET | `/health` | 健康檢查 |

**Request/Response 範例**：

```python
# Request: 權限檢查
class SecurityCheckRequest(BaseModel):
    user_token: str                    # Bearer token
    action: str                       # "execute_tool" | "execute_workflow" | "access_data"
    resource: str                     # tool_name | workflow_id | data_resource
    params: Optional[dict]            # 額外參數
    ip_address: Optional[str]         # 用戶 IP
    session_key: Optional[str]        # session 關聯

# Response: 權限檢查結果
class SecurityCheckResponse(BaseModel):
    allowed: bool                     # 是否允許
    denied_reason: Optional[str]      # 如果 denied， reason
    user_key: str                    # 用戶 key
    user_role: str                   # 用戶角色
    permissions: list[str]           # 用戶擁有的權限
    checked_at: datetime              # 檢查時間
    risk_score: float                # 風險分數 (0-1)
    anomalies: list[dict]            # 偵測到的異常

# Request: 審計日誌
class AuditLogRequest(BaseModel):
    user_key: str
    user_role: str
    action: str                      # "execute_tool" | "execute_workflow" | "access_data"
    resource: str
    resource_params: Optional[dict]
    decision: str                    # "allowed" | "denied"
    denied_reason: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    execution_result: Optional[str]  # "success" | "failure" | None
    error_message: Optional[str]
    session_key: Optional[str]
    run_id: Optional[str]
    tokens_used: Optional[int]
```

#### 6.4.4 異常偵測規則

```python
# 異常偵測規則定義
ANOMALY_RULES = [
    # 1. 速率限制
    {
        "type": "rate_limit",
        "name": "請求頻率過高",
        "threshold": 100,            # 100 次
        "window": 60,                 # 60 秒內
        "action": "flag",            # "flag" | "deny" | "block"
    },
    
    # 2. 異常時間
    {
        "type": "unusual_hours",
        "name": "異常工作時間",
        "allowed_hours": list(range(7, 22)),  # 7:00 - 22:00
        "action": "flag",
    },
    
    # 3. 大量訪問
    {
        "type": "bulk_access",
        "name": "短時間大量資源訪問",
        "threshold": 50,             # 50 次
        "window": 300,              # 5 分鐘內
        "action": "flag",
    },
    
    # 4. 連續失敗
    {
        "type": "failed_attempts",
        "name": "連續認證失敗",
        "threshold": 5,              # 5 次
        "window": 600,              # 10 分鐘內
        "action": "deny",           # 鎖定帳戶
    },
    
    # 5. 跨帳戶訪問
    {
        "type": "cross_account_access",
        "name": "跨帳戶異常訪問",
        "enabled": True,
        "threshold": 3,              # 跨 3 個帳戶
        "window": 3600,             # 1 小時內
        "action": "flag",
    },
    
    # 6. 權限提升偵測
    {
        "type": "privilege_escalation",
        "name": "權限提升嘗試",
        "enabled": True,
        "suspicious_actions": ["admin_access", "role_change", "permission_grant"],
        "action": "deny",
    },
]
```

#### 6.4.5 審計報告類型

| 報告類型 | 觸發條件 | 內容 |
|---------|---------|------|
| **即時報告** | 每次 denial | 誰、被拒絕原因、嘗試的資源、時間 |
| **每日報告** | 每天凌晨 | 總結統計、熱門動作、異常統計、用戶排名 |
| **每週報告** | 每週一 | 趨勢分析、異常用戶、權限變化、異常模式 |
| **異常報告** | 偵測到異常時 | 異常詳情、受影響資源、攻擊者指紋、建議 |

**報告 Schema**：

```python
class AuditReport(BaseModel):
    _key: Optional[str]
    report_type: str                 # "realtime" | "daily" | "weekly" | "anomaly"
    period_start: datetime
    period_end: datetime
    summary: ReportSummary
    anomalies: list[AnomalyRecord]
    generated_by: str                 # "system" | "user_request"
    generated_at: datetime
    status: str                      # "draft" | "published" | "archived"

class ReportSummary(BaseModel):
    total_requests: int
    allowed: int
    denied: int
    by_user: dict[str, int]          # user_key -> count
    by_action: dict[str, int]        # action -> count
    by_resource: dict[str, int]      # resource -> count
    by_result: dict[str, int]        # result -> count
    avg_response_time_ms: float
    top_denied_reasons: list[dict]   # [{"reason": "...", "count": N}]

class AnomalyRecord(BaseModel):
    anomaly_id: str
    anomaly_type: str
    description: str
    severity: str                     # "low" | "medium" | "high" | "critical"
    affected_users: list[str]
    affected_resources: list[str]
    first_occurred: datetime
    last_occurred: datetime
    occurrence_count: int
    recommendation: str
```

#### 6.4.6 ArangoDB Collections

**audit_logs**:

```json
{
  "_key": "audit_xxx",
  "timestamp": "2026-04-14T10:30:00Z",
  "user_key": "user_123",
  "username": "john.doe",
  "user_role": "admin",
  "action": "execute_tool",
  "resource": "web_search",
  "resource_params": {
    "query": "..."
  },
  "decision": "allowed",
  "denied_reason": null,
  "risk_score": 0.2,
  "anomalies_detected": [],
  "ip_address": "192.168.1.1",
  "user_agent": "...",
  "execution_result": "success",
  "error_message": null,
  "session_key": "session_xxx",
  "run_id": "pdca_run_xxx",
  "tokens_used": 1234,
  "latency_ms": 150
}
```

**audit_reports**:

```json
{
  "_key": "report_xxx",
  "report_type": "daily",
  "period_start": "2026-04-13T00:00:00Z",
  "period_end": "2026-04-14T00:00:00Z",
  "summary": {
    "total_requests": 1000,
    "allowed": 950,
    "denied": 50,
    "by_user": {"user_123": 200, "user_456": 150},
    "by_action": {"execute_tool": 600, "execute_workflow": 400},
    "by_resource": {"web_search": 300, "data_query": 250},
    "by_result": {"success": 900, "failure": 100},
    "avg_response_time_ms": 85.5,
    "top_denied_reasons": [
      {"reason": "insufficient_permissions", "count": 30},
      {"reason": "rate_limit_exceeded", "count": 15}
    ]
  },
  "anomalies": [
    {
      "anomaly_id": "ano_001",
      "anomaly_type": "rate_limit",
      "description": "用戶 user_789 在 1 分鐘內發起 120 次請求",
      "severity": "medium",
      "affected_users": ["user_789"],
      "occurrence_count": 5
    }
  ],
  "generated_at": "2026-04-14T00:05:00Z",
  "status": "published"
}
```

#### 6.4.7 與現有程式碼的整合點

**整合點總覽**：

| 現有檔案 | 改動方式 | 說明 |
|---------|---------|------|
| `mcp_tools/main.py` | Middleware/Dependency | 所有 `/execute` 請求經過 Security Agent |
| `bpa/mm_agent/main.py` | Middleware/Dependency | 所有 `/execute` 請求經過 Security Agent |
| `bpa/main.py` | Middleware/Dependency | 所有 `/execute` 請求經過 Security Agent |
| `tool_executor.py` | Header 注入 | 注入已驗證的 user_key, user_role |
| `clients.rs` | Header 轉發 | 轉發 Authorization header |

**整合範例 - MCP Tools**:

```python
# ai-services/mcp_tools/main.py

# 1. 新增 Security Agent 依賴
from security_agent import SecurityAgent

security_agent = SecurityAgent()

# 2. 所有 execute 請求經過 Security Check
@app.post("/execute")
async def execute_tool(
    request: ToolCall,
    Authorization: str = Header(None),
):
    # Security Check
    check_result = await security_agent.check(
        user_token=Authorization,
        action="execute_tool",
        resource=request.tool,
        params=request.parameters,
    )
    
    # 如果 denied
    if not check_result.allowed:
        # 記錄 denial
        await security_agent.log_denial(
            user_key=check_result.user_key,
            action="execute_tool",
            resource=request.tool,
            denied_reason=check_result.denied_reason,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Access denied",
                "reason": check_result.denied_reason,
                "user_key": check_result.user_key,
            }
        )
    
    # 執行工具
    result = await execute_tool_impl(request)
    
    # 記錄成功
    await security_agent.log_success(
        user_key=check_result.user_key,
        action="execute_tool",
        resource=request.tool,
        result="success",
    )
    
    return result
```

**整合範例 - BPA**:

```python
# ai-services/bpa/mm_agent/main.py

from security_agent import SecurityAgent

security_agent = SecurityAgent()

@app.post("/execute")
async def execute_workflow(
    request: WorkflowExecutionRequest,
    Authorization: str = Header(None),
):
    # Security Check
    check_result = await security_agent.check(
        user_token=Authorization,
        action="execute_workflow",
        resource=request.workflow_id,
        params=request.dict(),
    )
    
    if not check_result.allowed:
        await security_agent.log_denial(
            user_key=check_result.user_key,
            action="execute_workflow",
            resource=request.workflow_id,
            denied_reason=check_result.denied_reason,
        )
        raise HTTPException(status_code=403, detail=check_result.denied_reason)
    
    return await execute_workflow_impl(request)
```

#### 6.4.8 注意事項與最佳實踐

**部署注意事項**：

| 項目 | 說明 |
|------|------|
| **模型選擇** | 使用 `qwen2.5:1.5b-instruct`（平衡速度與準確性） |
| **延遲目標** | P99 < 100ms，不應成為系統瓶頸 |
| **可用性** | Security Agent 故障時應預設 deny，而非 allow |
| **日誌保留** | audit_logs 建議保留 90 天 |
| **報告生成** | 避免在 request path 內生成大型報告 |

**安全注意事項**：

| 項目 | 說明 |
|------|------|
| **Token 驗證** | 所有 token 必須經密碼學驗證，不可只做字串比對 |
| **RBAC 查詢** | 權限查詢結果應緩存，但需設定 TTL |
| **異常閾值** | 閾值應可動態調整，無需重啟服務 |
| **敏感資料** | 審計日誌中的 resource_params 應脫敏處理 |
| **審計完整性** | 關鍵操作採用 append-only 日誌 |

**效能注意事項**：

| 項目 | 說明 |
|------|------|
| **快取策略** | 用戶權限快取 5-15 分鐘 |
| **連接池** | 使用連接池而非每次新建連接 |
| **非同步寫入** | 審計日誌非同步寫入，不阻塞主流程 |
| **批量寫入** | 高頻日誌採用批量寫入減少 IO |

#### 6.4.9 與 Phase 0 的關係

> **Phase 0 的安全強化工作，應該由 Security Agent 來統一實作，而非分散在各個服務中手動添加。**

```
Phase 0 實作策略：
┌────────────────────────────────────────────────────────────┐
│  Step 0.1: 部署 Security Agent 服務                       │
│  Step 0.2: 整合 mcp_tools/main.py → Security Agent      │
│  Step 0.3: 整合 bpa/mm_agent/main.py → Security Agent   │
│  Step 0.4: 整合 bpa/main.py → Security Agent            │
│  Step 0.5: 開啟審計日誌 (audit_logs)                     │
│  Step 0.6: 設定異常偵測規則                              │
└────────────────────────────────────────────────────────────┘
```

---

## 7. Phase 實作規劃

### Phase 0: 安全強化（以 Security Agent 為核心）

| Step | 檔案/新增 | 改動 | 優先級 |
|------|---------|------|--------|
| 0.1 | `ai-services/security_agent/` | 部署 Security Agent 服務 | **高** |
| 0.2 | `mcp_tools/main.py` | 整合 Security Agent | **高** |
| 0.3 | `bpa/mm_agent/main.py` | 整合 Security Agent | **高** |
| 0.4 | `bpa/main.py` | 整合 Security Agent | **高** |
| 0.5 | `api/src/db/mod.rs` | 新增 `audit_logs` collection | **高** |
| 0.6 | `security_agent` | 開啟異常偵測規則 | **中** |

---

### Phase 1: 意圖分析核心

| Step | 檔案/新增 | 改動 | 優先級 |
|------|---------|------|--------|
| 1.1 | `api/src/db/mod.rs` | 新增 `orchestrator_runs` collection | **高** |
| 1.2 | `aitask/pdca/action_plan.py` | 新增 ActionPlan schema | **高** |
| 1.3 | `aitask/graph/nodes/matcher_node.py` | 新增 matcher_node (Qdrant + 小模型) | **高** |
| 1.4 | `aitask/graph/nodes/planner_node.py` | 新增 planner_node (輸出 ActionPlan) | **高** |
| 1.5 | `aitask/graph/state.py` | 新增 `pending_tool_calls`, `action_plan` 欄位 | **中** |
| 1.6 | `aitask/graph/builder.py` | 整合 matcher_node, planner_node | **中** |

**新增 matcher_node 邏輯**：
```python
# 偽代碼
async def matcher_node(state: TopState) -> dict:
    # 1. Qdrant first (用 Data Agent intent_rag)
    matched = await call_data_agent_intent_match(
        query=state["messages"][-1].content,
        scope="orchestrator"
    )
    
    # 2. 小模型綜合判斷 (qwen2.5:1.5b)
    action_plan = await small_llm_judge(
        query=state["messages"][-1].content,
        matched_intents=matched,
        available_tools=["web_search", "data_query", "knowledge"],
        available_workflows=["pdca", "bpa_mm"]
    )
    
    return {
        "matched_intent": matched,
        "action_plan": action_plan,
        "intent_confidence": matched.score,
    }
```

---

### Phase 2: PDCA 執行層

| Step | 檔案/新增 | 改動 | 優先級 |
|------|---------|------|--------|
| 2.1 | `aitask/pdca/pdca_breaker.py` | 新增 PDCABreaker (break point) | **高** |
| 2.2 | `aitask/pdca/definition_of_done.py` | 新增 DoD 生成器 | **中** |
| 2.3 | `aitask/pdca/milestone_memory.py` | 新增 Milestone 記憶 | **中** |
| 2.4 | `aitask/graph/nodes/bpa_orchestrator.py` | 完全重寫 (PDCA 邏輯) | **高** |
| 2.5 | `celery_app/tasks.py` | 擴展支援 BPA tasks | **中** |

**新增 bpa_orchestrator 邏輯**：
```python
# 偽代碼
async def bpa_orchestrator_node(state: TopState) -> dict:
    action_plan = state.get("action_plan")
    
    if action_plan.action_type == "process_orchestration":
        # 1. Create PDCA Run
        run = await create_orchestrator_run(
            session_key=state["session_key"],
            kind="pdca",
            intent_type=action_plan.intent_type,
        )
        
        # 2. Plan: 分解 todos + 生成 DoD
        todos = await plan_decomposition(action_plan.goal)
        dod = await generate_dod(action_plan.goal)
        
        # 3. Submit Celery tasks
        for todo in todos:
            task_id = await submit_celery_task(todo)
            await update_run_todos(run.run_id, todo, task_id)
        
        return {"run_id": run.run_id, "status": "executing"}
    
    elif action_plan.action_type == "clarification":
        # 建立澄清 session
        clarify_run = await create_orchestrator_run(
            parent_run_id=state.get("parent_run_id"),
            kind="clarify",
        )
        return {"clarify_session": clarify_run}
```

---

### Phase 3: CA Agent

| Step | 檔案/新增 | 改動 | 優先級 |
|------|---------|------|--------|
| 3.1 | `aitask/graph/nodes/consultant_agent.py` | 新增 CA node | **中** |
| 3.2 | `aitask/tools/tool_catalog.py` | 新增 Tool Catalog | **中** |
| 3.3 | `mcp_tools/main.py` | 新增 `/tools/search` 端點 | **低** |
| 3.4 | `aitask/graph/builder.py` | 整合 consultant_agent | **低** |

---

### Phase 4: 自我進化（ISFTA）

| Step | 檔案/新增 | 改動 | 優先級 |
|------|---------|------|--------|
| 4.1 | `orchestrator_runs` | 新增 `feedback` 欄位 | **低** |
| 4.2 | `aitask/pdca/feedback_collector.py` | 收集執行結果 | **低** |
| 4.3 | 外部腳本 | SLM Fine-tune 流程 | **低** |

---

## 8. 風險與對策

### 8.1 風險矩陣

| 風險 | 機率 | 影響 | 等級 | 對策 |
|------|------|------|------|------|
| 三套 intent logic 分裂 | 高 | 高 | **嚴重** | 統一走 Data Agent intent_rag |
| Tool/BPA 無權限被濫用 | 高 | 嚴重 | **嚴重** | Phase 0 立即修復 |
| PDCA 死循環 | 中 | 高 | **高** | pdca_breaker 加入 MAX_ITERATIONS |
| 過早 PDCA 化所有請求 | 中 | 中 | **中** | 嚴格區分三類 action plan |
| Planner 過度自由 | 低 | 高 | **中** | 限制只能從 tool/workflow registry 選擇 |

### 8.2 緩解措施細節

#### 8.2.1 統一 Intent Logic

**問題**：目前有三套可能分裂的 intent logic
1. Rust legacy intent routing (`api/src/api/intent.rs`)
2. AITask intent classifier (`aitask/graph/nodes/intent_classifier.py`)
3. Data Agent intent_rag (`data_agent/intent_rag/router.py`)

**對策**：
```
廢除 1, 2 兩套
統一走 3 (Data Agent intent_rag)
```

#### 8.2.2 PDCA Break Point

```python
class PDCABreaker:
    MAX_ITERATIONS = 3
    MAX_CHECK_ATTEMPTS = 2
    MAX_TOKEN_BUDGET = 50000
    
    async def should_break(self, iteration: int, failures: int, tokens: int) -> bool:
        return (
            iteration >= self.MAX_ITERATIONS or
            failures >= self.MAX_CHECK_ATTEMPTS or
            tokens >= self.MAX_TOKEN_BUDGET
        )
```

#### 8.2.3 限制 Planner 自由度

```python
# planner 只能從以下範圍選擇
AVAILABLE_TOOLS = ["web_search", "data_query", "knowledge"]
AVAILABLE_WORKFLOWS = ["pdca", "bpa_mm"]
# 不允許自由生成未知 tool
```

---

## 9. 附錄：關鍵程式碼位置索引

### 9.1 Intent 與路由

| 檔案 | 說明 | 關鍵函數/類別 |
|------|------|--------------|
| `ai-services/aitask/graph/nodes/intent_classifier.py` | 現有志圖分類 (3層) | `_try_rule_match`, `_try_semantic_match`, `_try_llm_classify` |
| `ai-services/aitask/graph/builder.py` | LangGraph 建構 | `build_graph`, `route_by_intent` |
| `ai-services/data_agent/intent_rag/router.py` | Qdrant Intent Match API | `/intent/match`, `embed_sync` |
| `api/src/api/intent.rs` | Rust 意圖路由 (legacy) | `route_tool_intent` |

### 9.2 工具執行

| 檔案 | 說明 | 關鍵函數/類別 |
|------|------|--------------|
| `ai-services/aitask/tools/registry.py` | 工具註冊表 | `ToolRegistry`, `get_tools_for_llm`, `execute` |
| `ai-services/aitask/tools/executors.py` | 工具執行器 | `MCPToolExecutor`, `DataAgentExecutor`, `KnowledgeAgentExecutor` |
| `ai-services/aitask/graph/nodes/tool_executor.py` | 工具執行 node | `tool_executor_node` |
| `ai-services/mcp_tools/main.py` | MCP 工具服務 | `/tools`, `/execute` |
| `ai-services/tools/web_search/web_search_tool.py` | Web Search 工具 | `WebSearchTool.execute` |

### 9.3 記憶管理

| 檔案 | 說明 | 關鍵函數/類別 |
|------|------|--------------|
| `ai-services/aitask/graph/nodes/memory_manager.py` | 記憶管理 node | `memory_manager_node`, `_summarize_messages` |
| `ai-services/memory_agent/core/session_memory.py` | Session 記憶 | `SessionMemory`, `update_session_memory` |
| `ai-services/memory_agent/core/working_memory.py` | 工作記憶 | `WorkingMemory`, `set_working_memory` |
| `ai-services/memory_agent/core/storage.py` | 記憶儲存 | `ensure_memory_dir`, `add_to_index` |
| `ai-services/memory_agent/core/recall.py` | 記憶召回 | `needs_verification`, `generate_system_prompt` |

### 9.4 BPA 與工作流程

| 檔案 | 說明 | 關鍵函數/類別 |
|------|------|--------------|
| `ai-services/bpa/main.py` | 通用 BPA | `execute_workflow`, `execute_workflow_async` |
| `ai-services/bpa/mm_agent/main.py` | MM BPA | `execute_step`, `_run_workflow_bg` |
| `ai-services/aitask/graph/nodes/bpa_orchestrator.py` | BPA Orchestrator (stub) | `bpa_orchestrator_node` |
| `ai-services/celery_app/tasks.py` | Celery 任務 | `vectorize_task`, `graph_task` |

### 9.5 API 與協調

| 檔案 | 說明 | 關鍵函數/類別 |
|------|------|--------------|
| `api/src/services/chat/orchestrator.rs` | Chat 協調器 | `handle_send_message` |
| `api/src/services/chat/clients.rs` | HTTP 客戶端 | `call_aitask_chat`, `call_aitask_graph_chat` |
| `api/src/services/chat/repo.rs` | DB 操作 | `insert_message`, `get_message_history` |
| `api/src/api/chat.rs` | Chat API | `create_session`, `send_message` |
| `api/src/db/mod.rs` | DB 模型 | `ChatSession`, `ChatMessage` |

### 9.6 Security Agent

| 檔案 | 說明 | 關鍵函數/類別 |
|------|------|--------------|
| `ai-services/security_agent/main.py` | Security Agent 入口 | `/security/check`, `/security/log` |
| `ai-services/security_agent/auth/token_verifier.py` | JWT 驗證 | `verify_jwt`, `decode_token` |
| `ai-services/security_agent/auth/user_resolver.py` | 用戶身份解析 | `resolve_user`, `get_user_roles` |
| `ai-services/security_agent/permission/rbac_checker.py` | RBAC 檢查 | `check_permission`, `get_user_permissions` |
| `ai-services/security_agent/permission/resource_guard.py` | 資源保護 | `guard_resource`, `check_access` |
| `ai-services/security_agent/audit/logger.py` | 審計日誌 | `log_denial`, `log_success`, `log_anomaly` |
| `ai-services/security_agent/audit/report_generator.py` | 報告生成 | `generate_report`, `generate_daily_report` |
| `ai-services/security_agent/audit/anomaly_detector.py` | 異常偵測 | `detect_anomalies`, `check_rate_limit` |

### 9.7 LangGraph Checkpoint

| 檔案 | 說明 | 關鍵函數/類別 |
|------|------|--------------|
| `ai-services/aitask/checkpointer/arango_saver.py` | ArangoDB Checkpoint | `ArangoDBSaver`, `aput`, `aget_tuple` |
| `ai-services/aitask/graph/state.py` | Graph State | `TopState` |
| `ai-services/aitask/collections.py` | Collection 管理 | `ensure_chat_checkpoints` |

---

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-14 | 1.1.0 | AI Agent | 新增 Security Agent 詳細規格（設計理念、架構、API、異常偵測、審計報告、整合點、注意事項） |
| 2026-04-14 | 1.0.0 | AI Agent | 初始版本：整合流程圖分析、程式碼地圖、缺口分析、整合點、安全性分析、實作規劃 |
