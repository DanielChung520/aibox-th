# 智能體通用 Orchestrator 規格說明書

| 版本 | 日期 | 修訂內容 | 修訂人 |
|------|------|----------|--------|
| 1.0 | 2026-04-21 | 新增元件層編排框架章節（第九、十章）：shared/orchestration/ 架構、核心類別、標準節點、工具執行框架、Agent 等級、新建 Agent 檢查清單 | Daniel Chung |

---

## 一、系統架構

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Task Chat (顶层)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  - 一般聊天（LLM 直接回复）                                          ││
│  │  - 任务感知 + 初级编排                                               ││
│  │  - 路由到指定 BPA                                                    ││
│  │  - BPA 多轮对话的中转站                                              ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                              │                                          │
│                    ┌─────────┴─────────┐                               │
│                    │  Handoff Protocol │                               │
│                    └─────────┬─────────┘                               │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         BPA Orchestrator                                │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  - 深层流程编排                                                      ││
│  │  - 进一步分解任务                                                    ││
│  │  - 调用 DA (Data Agent)                                             ││
│  │  - 多轮对话（通过 Top 与用户交互）                                   ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Data Agent (DA)                                 │
│                    数据抽象层：CRUD + 聚合计算                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 二、Task Chat 顶层架构

### 2.1 功能定义

| 功能 | 描述 |
|-----|------|
| **一般聊天** | 无需执行任务的闲聊、问答，LLM 直接回复 |
| **任务感知** | 检测用户输入是否包含工作任务 |
| **初级编排** | 简单拆分任务为子任务，不深入细节 |
| **BPA 路由** | 将任务交给指定的 BPA Agent 处理 |
| **消息中转** | BPA 与用户之间的多轮对话由此中转 |

### 2.2 消息流程

```
用户输入
    │
    ▼
┌───────────────────────┐
│  1. 一般聊天？        │──是──► LLM 直接回复 ──► 用户
└───────────┬───────────┘
            │否
            ▼
┌───────────────────────┐
│  2. 任务感知          │──否──► LLM 直接回复 ──► 用户
└───────────┬───────────┘
            │是
            ▼
┌───────────────────────┐
│  3. 初级编排          │  简单拆分为子任务
│  (Top Orchestrator)  │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  4. 确认 + 指定 BPA   │  展示计划 + 用户确认
└───────────┬───────────┘
            │确认
            ▼
┌───────────────────────┐
│  5. Handoff to BPA    │
│  指定 bpa_id          │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  6. BPA 处理          │
│  - 深层编排           │
│  - 调用 DA            │
│  - 需要用户输入时     │
│    通过 Top 询问      │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  7. 结果返回          │
│  (经过 Top 整合)      │
└───────────────────────┘
```

---

## 三、Top Orchestrator

### 3.1 核心职责

| 职责 | 描述 |
|-----|------|
| **会话管理** | 启动/切换/结束 Task Chat |
| **上下文管理** | 对话历史、跨轮次实体记忆 |
| **指代消解** | 将"那个订单"、"它"解析为具体实体 |
| **记忆** | 短期（会话内）+ 长期（用户偏好） |
| **任务感知** | 检测是否需要执行工作 |
| **初级编排** | 简单拆分任务为子任务 |
| **消息中转** | BPA ↔ 用户之间的消息传递 |

### 3.2 任务感知 Prompt

```
你是一个任务分类器。

判断用户消息是否需要执行工作任务：
- task: 需要执行操作（查询、执行、创建、修改、删除）
- chat: 闲聊、问答、情感表达

用户消息：{user_message}

输出 JSON：
{"intent": "task|chat", "confidence": 0.0-1.0}
```

### 3.3 初级编排 Prompt

```
用户需要完成一个任务，请进行简单的任务拆分。

任务：{user_task}

要求：
1. 只做简单拆分，不深入细节
2. 每个子任务应该清晰可理解
3. 标注每个子任务适合由哪个 BPA 处理（如果有）

输出格式：
{"subtasks": [{"id": 1, "description": "...", "bpa_hint": "..."}]}
```

### 3.4 指代消解 Prompt

```
以下是对话历史，找出"它/他/她/这个/那个"等指代词具体指代什么。

对话历史：
{history}

当前消息：{current_message}

输出 JSON：
{"resolved": "具体指代的内容", "entity_type": "order|customer|..."}
```

---

## 四、BPA Orchestrator

### 4.1 核心职责

| 职责 | 描述 |
|-----|------|
| **深层编排** | 详细的任务分解和流程编排 |
| **DA 调用** | 调用 Data Agent 执行数据操作 |
| **多轮对话** | 与用户交互获取信息/确认 |
| **状态管理** | 任务执行状态追踪 |
| **结果聚合** | 汇总各子任务结果 |

### 4.2 BPA 定义格式

```json
{
  "id": "order-bpa",
  "name": "订单管理 BPA",
  "description": "处理订单相关业务",
  "version": "1.0.0",
  
  "capabilities": [
    "order_query",
    "order_update",
    "return_process",
    "refund_execute"
  ],
  
  "tools": [
    "db-order-query",
    "db-order-update",
    "payment-refund"
  ],
  
  "prompts": {
    "task_decomposition": "你是一个订单管理专家...",
    "flow_orchestration": "根据任务类型，选择合适的流程...",
    "result_summary": "订单处理完成："
  }
}
```

### 4.3 动态注册

```python
class BPARegistry:
    """运行时动态注册 BPA"""
    
    def register(self, bpa_config: dict):
        bpa = BPAOrchestrator(bpa_config)
        self.bpas[bpa_config["id"]] = bpa
    
    def get(self, bpa_id: str) -> BPAOrchestrator:
        if bpa_id not in self.bpas:
            raise BPANotFoundError(f"BPA {bpa_id} 未注册")
        return self.bpas[bpa_id]
```

---

## 五、通信协议 (Handoff Protocol)

### 5.1 协议消息类型

| 消息类型 | 方向 | 描述 |
|---------|------|------|
| `TASK_HANDOVER` | Top → BPA | 启动任务 |
| `USER_MESSAGE` | Top → BPA | 转发用户消息 |
| `BPA_RESPONSE` | BPA → Top | BPA 回复 |
| `BPA_ASK_USER` | BPA → Top | BPA 需要用户输入 |
| `TASK_STATUS` | BPA → Top | 任务进度更新 |
| `TASK_COMPLETE` | BPA → Top | 任务完成 |
| `TASK_FAILED` | BPA → Top | 任务失败 |

### 5.2 TASK_HANDOVER (Top → BPA)

```json
{
  "type": "TASK_HANDOVER",
  "session_id": "sess_xxx",
  "user_id": "user_xxx",
  
  "handover_data": {
    "user_intent": "处理订单退货",
    "initial_message": "帮我处理订单OR-001的退货",
    
    "extracted_entities": {
      "order_id": "OR-001",
      "action": "return"
    },
    
    "top_level_subtasks": [
      {"id": 1, "description": "查询订单状态"},
      {"id": 2, "description": "检查退货条件"},
      {"id": 3, "description": "执行退货"}
    ],
    
    "conversation_context": {
      "language": "zh-TW",
      "user_preference": {}
    },
    
    "history": [
      {"role": "user", "content": "我想退货"},
      {"role": "assistant", "content": "请提供订单号"}
    ]
  },
  
  "timestamp": "2024-03-19T10:00:00Z"
}
```

### 5.3 BPA_RESPONSE / BPA_ASK_USER (BPA → Top)

```json
{
  "type": "BPA_RESPONSE",
  "session_id": "sess_xxx",
  "bpa_id": "order-bpa",
  
  "response": {
    "message": "订单OR-001状态为已发货，可以申请退货。",
    "needs_user_input": false,
    
    "task_status": {
      "task_1": {"status": "completed", "result": "已发货"},
      "task_2": {"status": "pending"},
      "task_3": {"status": "pending"}
    }
  },
  
  "timestamp": "2024-03-19T10:01:00Z"
}
```

```json
{
  "type": "BPA_ASK_USER",
  "session_id": "sess_xxx",
  "bpa_id": "order-bpa",
  
  "ask": {
    "question": "请确认退货原因：",
    "options": [
      {"id": "quality", "label": "质量问题"},
      {"id": "wrong_item", "label": "发错商品"},
      {"id": "changed_mind", "label": "不想要了"}
    ],
    "required": true
  },
  
  "task_status": {
    "task_1": "completed",
    "task_2": "running"
  },
  
  "timestamp": "2024-03-19T10:02:00Z"
}
```

### 5.4 TASK_COMPLETE (BPA → Top)

```json
{
  "type": "TASK_COMPLETE",
  "session_id": "sess_xxx",
  "bpa_id": "order-bpa",
  
  "result": {
    "summary": "订单OR-001退货已处理完成",
    
    "tasks": [
      {
        "id": 1,
        "description": "查询订单状态",
        "status": "completed",
        "result": {"status": "已发货", "can_return": true}
      },
      {
        "id": 2,
        "description": "检查退货条件",
        "status": "completed",
        "result": {"eligible": true, "reason": "未超过7天"}
      },
      {
        "id": 3,
        "description": "执行退货",
        "status": "completed",
        "result": {"return_id": "RET-001", "refund_amount": 299}
      }
    ],
    
    "next_actions": [
      "是否需要查看退款到账状态？"
    ]
  },
  
  "timestamp": "2024-03-19T10:05:00Z"
}
```

---

## 六、对话流程示例

### 6.1 一般聊天流程

```
👤 用户: "今天天气怎么样"
🤖 Top: 任务感知 → chat
🤖 LLM: 返回天气信息
👤  用户: "谢谢"
🤖 Top: chat → LLM直接回复
```

### 6.2 任务执行流程

```
👤 用户: "帮我处理订单OR-001的退货"
🤖 Top: 任务感知 → task
🤖 Top: 初级编排 → 拆分为3个子任务
🤖 Top: [展示计划]
    1. 查询订单状态
    2. 检查退货条件
    3. 执行退货
    
👤 用户: "确认"
🤖 Top: Handover to order-bpa

📦 order-bpa:
  - 深层编排: 确定具体流程
  - 调用 DA 查询订单 → 返回状态
  - 检查退货条件
  
📦 order-bpa → Top: "订单OR-001已发货，可申请退货，请确认退货原因"
👤 Top → 用户: "订单OR-001已发货，可申请退货，请确认退货原因：1.质量问题 2.发错商品 3.不想要了"

👤 用户: "质量问题"
📦 Top → order-bpa: 用户选择"质量问题"

📦 order-bpa:
  - 记录退货原因
  - 执行退货流程
  - 调用 DA 更新订单
  
📦 order-bpa → Top: TASK_COMPLETE

👤 Top: "订单OR-001退货已完成，退款金额299元将原路返回"
```

---

## 七、状态管理

### 7.1 Top 状态

```python
class TopState:
    def __init__(self):
        self.mode: str = "chat"              # chat | task
        self.active_bpa: Optional[str] = None  # 当前活跃的 BPA ID
        
        # 会话管理
        self.session_id: str = ""
        self.user_id: str = ""
        
        # 上下文
        self.entities: Dict[str, Any] = {}   # 当前会话记住的实体
        self.history: List[Message] = []     # 对话历史
        
        # 记忆
        self.short_term: Dict = {}           # 会话级记忆
        self.long_term: Dict = {}            # 用户偏好等
```

### 7.2 BPA 状态

```python
class BPAState:
    def __init__(self, bpa_id: str):
        self.bpa_id = bpa_id
        
        # 任务
        self.tasks: List[Task] = []
        self.current_task: Optional[str] = None
        
        # 执行状态
        self.status: str = "idle"            # idle | running | waiting | completed | failed
        
        # 中间结果
        self.results: Dict[str, Any] = {}
        
        # 与用户交互
        pending_questions: List[Question] = []
```

### 7.3 任务状态机

```
IDLE ──[接收任务]──► RUNNING
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
     COMPLETED    WAITING      FAILED
          │           │
          ▼           ▼
    [返回结果]  [等待用户输入]
                      │
                      ▼
               [用户输入后] ──► RUNNING
```

---

## 八、错误处理

### 8.1 错误类型

| 错误码 | 描述 | 处理方式 |
|-------|------|---------|
| `BPA_NOT_FOUND` | BPA 不存在 | 提示用户，检查 BPA ID |
| `BPA_TIMEOUT` | BPA 执行超时 | 重试或询问用户 |
| `BPA_ERROR` | BPA 执行失败 | 返回错误，询问重试 |
| `DA_ERROR` | Data Agent 错误 | BPA 自行处理 |
| `SESSION_LOST` | 会话丢失 | 重新初始化 |

### 8.2 错误响应格式

```json
{
  "type": "TASK_FAILED",
  "session_id": "sess_xxx",
  "bpa_id": "order-bpa",
  
  "error": {
    "code": "DA_ERROR",
    "message": "数据库连接失败",
    "can_retry": true
  },
  
  "partial_results": [
    {"task_id": 1, "status": "completed", "result": {...}}
  ],
  
  "suggested_actions": [
    "重试操作",
    "稍后再试"
  ],
  
  "timestamp": "2024-03-19T10:05:00Z"
}
```

---

## 九、兩層編排架構

本系統採用**兩層編排架構**，各層職責分明：

| 層級 | 編排器 | 位置 | 職責 |
|------|--------|------|------|
| **系統層**（System-level） | Top Orchestrator | `aitask/` | 路由：User → 哪個 Agent（BPA/DA/KA...） |
| **元件層**（Agent-level） | Agent Orchestrator | `shared/orchestration/` | 每個 Agent 內部的 workflow 框架 |

### 9.1 兩層協作關係

```
User 輸入
    │
    ▼
┌─────────────────────────────────────────────┐
│  系統層：Top Orchestrator                    │
│  - 意圖檢測（task vs chat）                 │
│  - 路由到指定 Agent（BPA/DA/KA）           │
│  - Handoff Protocol                        │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  元件層：每個 Agent 內部                     │
│  shared/orchestration/ 框架                │
│  - 狀態管理 (AgentState)                   │
│  - LLM 節點 (意圖分類、對話)               │
│  - 工具執行節點 (shared/tools/)            │
│  - 路由節點 (action_plan routing)          │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
          Agent 執行結果
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  系統層：Top Orchestrator 彙集回覆          │
└─────────────────────────────────────────────┘
```

### 9.2 元件層框架約束

所有 Agent（無論 BPA、DA、KA 或未來新建的 Agent）**必須**使用 `shared/orchestration/` 框架實作內部編排，**禁止**自行實作：

- ❌ 自行寫 tool loop（應用 `tool_executor_node`）
- ❌ 自行寫 LangGraph StateGraph（應用 `AgentGraphBuilder`）
- ❌ 自行寫工具 HTTP 呼叫（應用 `shared/tools/` ToolRegistry）
- ❌ 跳過 `OrchestrationEngine.run()` 自己實作執行邏輯

---

## 十、Agent 內部編排框架（元件層）

### 10.1 框架定位

`shared/orchestration/` 是**標準化的 Agent 內部編排框架**，所有 Agent 共享同一套工具執行、狀態管理、節點路由機制。

### 10.2 目錄結構

```
ai-services/shared/
├── orchestration/               # 編排框架
│   ├── __init__.py             # 導出：AgentGraphBuilder, OrchestrationEngine, AgentState, AgentRunResult
│   ├── state.py                # AgentState (TypedDict) + AgentRunResult
│   ├── engine.py               # OrchestrationEngine.run() — 標準 tool loop 執行器
│   ├── builder.py              # AgentGraphBuilder — 建構 LangGraph 節點圖
│   └── nodes/
│       ├── __init__.py         # 導出：llm_node, router_node, tool_executor_node
│       ├── router.py           # 根據 action_plan 路由到下一節點
│       ├── llm_node.py        # 標準 LLM 呼叫（含 function calling）
│       └── tool_executor.py    # 執行 tool_calls → shared/tools/
│
├── tools/                      # 工具框架
│   ├── __init__.py            # 導出：ToolRegistry, ToolExecutionContext, ToolResult, ToolSource
│   ├── registry.py             # 工具發現、LLM function schema、派發
│   └── executors.py            # MCPToolExecutor, DataAgentExecutor, KnowledgeAgentExecutor, BuiltinExecutor
│
└── conversation/               # 對話歷史（各 Agent 共用）
    ├── storage.py              # 儲存訊息
    └── query.py                # 查詢歷史
```

### 10.3 核心類別

#### AgentState

所有 Agent 的**最小共用狀態**（TypedDict + LangGraph `add_messages`）：

```python
class AgentState(TypedDict):
    session_id: str                              # Session 識別
    user_id: str                               # 用戶識別
    messages: Annotated[list[BaseMessage], add_messages]  # 對話歷史（自動合併）
    state_version: int                          # 狀態版本（每次更新 +1）
    tool_results: list[dict[str, Any]]         # 工具執行結果
    pending_tool_calls: list[dict[str, Any]]   # 待執行的 tool_calls
    extra: dict[str, Any]                      # Agent 可自行擴展
```

各 Agent 可**擴展** AgentState，例如：

```python
class RagicHelperState(AgentState):
    matched_intent: dict | None
    intent_confidence: float
    action_plan: Literal["direct_answer", "tool_call", "unknown"]
```

#### AgentRunResult

`OrchestrationEngine.run()` 的輸出結構：

```python
class AgentRunResult(TypedDict):
    session_id: str                     # Session ID
    response: str                       # 最終回覆文字
    messages: list[BaseMessage]         # 更新後的訊息歷史
    tool_results: list[dict[str, Any]]  # 所有工具執行結果
    state_version: int                  # 最終狀態版本
    trace_id: str                       # 本次追蹤 ID
    success: bool                       # 是否成功完成
    error: str | None                   # 若失敗，錯誤原因
```

#### ToolExecutionContext

工具執行的上下文，攜帶追蹤資訊：

```python
class ToolExecutionContext(BaseModel):
    user_id: str        # 用戶識別
    session_id: str     # Session 識別
    trace_id: str       # 追蹤 ID（格式：{session_id}-{version}-{correlation_id}）
    auth_token: str     # 認證 Token
    correlation_id: str  # 工具呼叫 ID（用於關聯 tool_calls 和結果）
```

#### ToolResult

工具執行結果：

```python
class ToolResult(BaseModel):
    tool_name: str           # 工具名稱
    tool_call_id: str        # 本次呼叫 ID
    success: bool            # 是否成功
    result: object           # 成功時的結果（dict/list/str）
    error: str | None       # 失敗時的錯誤訊息
    duration_ms: int         # 執行耗時（毫秒）
    source: ToolSource       # 工具來源（MCP/DATA_AGENT/KNOWLEDGE/BUILTIN）
    trace_id: str | None    # 追蹤 ID
```

#### ToolSource

工具來源枚舉：

```python
class ToolSource(str, Enum):
    MCP = "mcp"                    # MCP Tools 服務（port 8004）
    DATA_AGENT = "data_agent"     # NL→SQL 查詢（port 8003）
    KNOWLEDGE = "knowledge"       # 知識庫 RAG（port 8007）
    BUILTIN = "builtin"           # 內建工具（current_time, session_summary）
```

### 10.4 標準節點

#### router_node

根據 `action_plan` 路由到下一節點：

```python
def router_node(state: AgentState) -> str:
    action_plan = state.get("action_plan", "direct_answer")
    return str(action_plan)
```

**可用 action_plan 值**：

| action_plan | 下一節點 | 說明 |
|-------------|----------|------|
| `direct_answer` | chat_responder | LLM 直接回覆 |
| `tool_call` | tool_executor | 執行工具 |
| `process_orchestration` | bpa_orchestrator | BPA 流程編排 |

#### llm_node

標準 LLM 呼叫節點，支援 function calling：

```python
async def llm_node(
    state: dict[str, Any],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]
```

#### tool_executor_node

執行 LLM 發出的 tool_calls，使用 `shared/tools/`：

```python
async def tool_executor_node(state: AgentState) -> dict[str, Any]:
    # 1. 從 state["messages"][-1] 取得 tool_calls
    # 2. 透過 ToolRegistry 執行每個工具
    # 3. 回傳 {messages: [ToolMessage, ...], tool_results: [...], state_version: +1}
```

### 10.5 工具執行框架（shared/tools/）

#### ToolRegistry

工具發現、LLM function schema 產生、執行派發：

```python
class ToolRegistry:
    async def initialize(
        self,
        mcp_tools_url: str,
        data_agent_url: str,
        knowledge_agent_url: str,
        auth_token: str = "",
    ) -> None:
        self._executors = {
            ToolSource.MCP: MCPToolExecutor(mcp_tools_url),
            ToolSource.DATA_AGENT: DataAgentExecutor(data_agent_url),
            ToolSource.KNOWLEDGE: KnowledgeAgentExecutor(knowledge_agent_url),
            ToolSource.BUILTIN: BuiltinExecutor(),
        }

    def get_tools_for_llm(self) -> list[dict[str, Any]]:
        # 產生 LLM function calling schema

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolResult:
        # 派發到對應 Executor 執行
```

#### 已內建工具

| 工具名稱 | 來源 | 參數 | 說明 |
|----------|------|------|------|
| `da_query` | DATA_AGENT | `query: str` | 自然語言查詢資料 |
| `da_visualize` | DATA_AGENT | `query: str` | 查詢視覺化資料 |
| `ka_search` | KNOWLEDGE | `query: str` | 知識庫 RAG 檢索 |
| `ka_doc_retrieve` | KNOWLEDGE | `query: str` | 擷取知識庫文件內容 |
| `current_time` | BUILTIN | — | 取得目前 UTC 時間 |
| `session_summary` | BUILTIN | — | 取得 session 摘要 |

### 10.6 OrchestrationEngine.run() 使用方式

```python
from shared.orchestration import AgentGraphBuilder, OrchestrationEngine
from shared.tools import ToolRegistry

# 1. 初始化 ToolRegistry（整個 service 只做一次）
registry = ToolRegistry()
await registry.initialize(
    mcp_tools_url="http://localhost:8004",
    data_agent_url="http://localhost:8003",
    knowledge_agent_url="http://localhost:8007",
)

# 2. 取得 LLM function calling schema
tools = registry.get_tools_for_llm()

# 3. 建構 Agent 節點圖
builder = AgentGraphBuilder()
builder.add_node("classify_intent", my_intent_classifier_node)
builder.add_node("router", router_node)
builder.add_node("tool_executor", tool_executor_node)
builder.add_node("chat_responder", my_chat_responder_node)
builder.set_entry("classify_intent")
builder.add_edge("classify_intent", "router")
builder.add_conditional_edges("router", route_by_action, {
    "direct_answer": "chat_responder",
    "tool_call": "tool_executor",
})
graph = builder.build()

# 4. 執行
engine = OrchestrationEngine(graph, max_tool_loops=3)
result = await engine.run(
    session_id="sess_123",
    user_id="user_456",
    user_message="查詢庫存",
    tools=tools,
)
# result.response       — 最終回覆文字
# result.messages      — 訊息歷史
# result.tool_results  — 工具執行結果
# result.success       — 是否成功
```

### 10.7 Agent 等級

| 等級 | 說明 | 所需框架 |
|------|------|----------|
| **L1 純聊天** | 無工具，只能 LLM 對話 | 直接 call LLM |
| **L2 RAG 增強** | L1 + 意圖判斷 + 知識庫 RAG | `detect_intent()` + `hybrid_search()` |
| **L3 工具呼叫** | L2 + 工具執行 | `shared/tools/` ToolRegistry + `tool_executor_node` |
| **L4 完整編排** | L3 + 工作編排 + 多步任務 | `shared/orchestration/` OrchestrationEngine |

### 10.8 新建 Agent 檢查清單

建立新 Agent 前確認：

- [ ] 目錄位於 `bpa/` 或 `agents/` 下
- [ ] 使用 `shared/orchestration/` 而非自行實作編排
- [ ] 使用 `shared/tools/` 而非自行寫 httpx 呼叫工具
- [ ] 使用 `shared/conversation/` 而非自行實作歷史儲存
- [ ] `ruff check` 無 error
- [ ] `mypy --ignore-missing-imports` 無 type error
- [ ] 環境變數皆從 `os.getenv()` 讀取，無 hardcode URL
- [ ] 檔案表頭有標準 docstring（`@file` + `@lastUpdate` + `@author`）
- [ ] 在 `AGENTS.md` Port 註冊表（10.6）新增獨立 port（如有）

---

## 十一、後續討論主題
