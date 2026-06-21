---
lastUpdate: 2026-06-20
author: Sisyphus
version: 1.0.0
---

# Agent 標準規範

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-06-20 | 1.0.0 | Sisyphus | 初始版本：完整 Agent 架構定義、生命週期、技能管理、意圖框架、協作模式、治理安全、MCP 整合、範本指南 |

---

## 1. 定位與角色

### 1.1 什麼是 Agent

Agent（智能體）是 AIBox 系統中具備以下特質的自主運算單元：

- **意圖感知**：能夠理解使用者輸入的意圖，並據此決定行為
- **技能組合**：透過組合多個 Skills 完成業務任務，而非在 LLM 呼叫中硬寫邏輯
- **狀態管理**：維護對話上下文、工作階段與記憶
- **邊界控制**：受限於信任等級（Trust Tier）與場景（Scene）定義的資料存取範圍
- **可路由**：可經由意圖分類系統被呼叫，也可將任務 handoff 給其他 Agent

Agent 不是一個單純的 API 端點。它是承載業務邏輯、安全邊界與互動模式的自主單元。

### 1.2 Agent - Skill - Tool 三層架構

```
┌──────────────────────────────────────────────────┐
│                    Agent                          │
│  (意圖路由 + 安全邊界 + 場景控制 + 對話管理)      │
│                                                   │
│  ┌────────────────────────────────────────┐       │
│  │         Intent Classifier              │       │
│  │  關鍵字 → Embedding → LLM 三層漏斗    │       │
│  └────────────┬───────────────────────────┘       │
│               ▼                                   │
│  ┌────────────────────────────────────────┐       │
│  │      Skill Dispatcher (router.py)      │       │
│  │   skills.greeting_engine.execute()     │       │
│  │   skills.timeline_engine.execute()     │       │
│  │   skills.image_processor.execute()     │       │
│  └────────────┬───────────────────────────┘       │
│               ▼                                   │
│  ┌────────────────────────────────────────┐       │
│  │        Tool Execution Layer            │       │
│  │  MCP Tools / ArangoDB / LINE API / ... │       │
│  └────────────────────────────────────────┘       │
└──────────────────────────────────────────────────┘
```

| 層級 | 職責 | 實作方式 |
|------|------|----------|
| **Agent** | 意圖分類、場景控制、安全邊界、對話管理、跨 Agent 協作 | FastAPI router + router.py |
| **Skill** | 單一職責的業務邏輯單元，無狀態、可複用 | `skills/<name>/skill.py` + `execute(params) → dict` |
| **Tool** | 底層資源操作（資料庫、外部 API、檔案系統） | MCP protocol / 直接 SDK 呼叫 |

### 1.3 Agent 類型

AIBox 定義四種 Agent 類型，涵蓋不同場景與權限需求：

| 類型 | 代號 | 說明 | 信任等級 | 範例 |
|------|------|------|----------|------|
| 業務流程 Agent | **BPA** | 頻繁讀寫內部系統（ERP、CRM、Timeline），組合技能完成業務流程 | T2-T3 | 福祉業務小秘、訂單秘書 |
| 內部顧問 Agent | **Advisor** | 唯讀顧問角色，提供分析、建議、診斷，不寫入資料 | T1-T2 | 效能工具代理 |
| 外部工具 Agent | **Tool Agent** | 包裝外部服務（搜尋、翻譯、地圖），以 Agent 形式提供介面 | T1 | Web Search Agent |
| 知識查詢 Agent | **Oracle** | 查詢向量知識庫、FAQ、文件，回覆事實性問題 | T1 | Knowledge Agent |

#### 1.3.1 BPA（Business Process Agent）

BPA 為 AIBox 的核心 Agent 類型，具備以下特性（依 AGENTS.md §1.9）：

- **內部知識與資料交互**：需頻繁讀寫 ERP、CRM、資料庫、Timeline 等系統
- **嚴格的安全管理**：System Prompt 與技能調用需經審查，禁止外部 LLM 隨意讀寫資料
- **受控的資料邊界**：客戶端（場景一）與內部（場景二）的權限必須分離
- **技能組合**：透過組合多個 Skills 完成任務，而非直接在 LLM 呼叫中處理業務邏輯

#### 1.3.2 Advisor（內部顧問 Agent）

Advisor 提供唯讀的深度分析能力：

- 不寫入任何資料，不執行命令
- 可被自動觸發（如慢查詢偵測）或手動呼叫（如 `@效能顧問`）
- 分析結果附加到主流程回應中，不阻塞主要 Pipeline

#### 1.3.3 Tool Agent（外部工具 Agent）

Tool Agent 是外部服務的 Agent 化包裝：

- 每個 Tool Agent 封裝一個外部服務（搜尋引擎、地圖 API、翻譯服務）
- 透過 MCP 協定暴露工具清單
- 不維護對話狀態，每次呼叫為原子操作

#### 1.3.4 Oracle（知識查詢 Agent）

Oracle 專注於事實性知識檢索：

- 查詢 RAG 向量庫（Qdrant）與結構化知識庫
- 回覆產品 FAQ、操作說明、政策文件等
- 支援 citation 來源引用

---

## 2. Agent 生命週期

每個 Agent 從定義到除役遵循六階段生命週期：

```
定義 → 登記 → 部署 → 運行 → 監控 → 除役
```

### 2.1 定義（Define）

| 步驟 | 產出 | 負責人 |
|------|------|--------|
| 1. 確定 Agent 類型與場景 | BPA / Advisor / Tool Agent / Oracle | 產品經理 |
| 2. 定義能力邊界 | 能做 / 不能做清單 | 產品經理 + 開發者 |
| 3. 設計意圖清單 | `declared_intents[]` 初版 | 開發者 |
| 4. 綁定技能 | 確定要組合哪些現有 Skills | 開發者 |
| 5. 設定信任等級 | T1-T4 | 安全負責人 |
| 6. 撰寫 System Prompt | 角色說明 + 行為規則 | 開發者 + 領域專家 |

定義階段的產出是一份 Agent 規格書（參照第 9 章範本），送審通過後進入登記階段。

### 2.2 登記（Register）

將 Agent 元資料寫入 ArangoDB `agents` 集合（詳見第 3 章 Schema 定義）：

- 填寫所有必要欄位（_key, name, type, version, endpoint_url, scenes）
- 設定 `declared_intents[]` 清單
- 綁定 Skills（填入 `bound_skills[]`）
- 設定治理欄位（trust_tier, max_turns, requires_approval_for）
- 登記完成後取得 agent_key，作為系統內唯一識別

### 2.3 部署（Deploy）

| 環境 | 動作 | 檢查項目 |
|------|------|----------|
| 開發 (dev) | 掛載 router 到 unified_agents | Lint、單元測試、意圖分類測試 |
| 測試 (staging) | 整合測試 + 業務驗收 | 所有意圖路徑驗證、安全性掃描 |
| 正式 (production) | 逐步放量（canary） | 錯誤率監控、回應延遲、資源用量 |

部署檢查清單：

- [ ] Agent router.py 已實作意圖分類與技能分派
- [ ] 所有綁定 Skills 的 execute() 呼叫正確
- [ ] 依 AGENTS.md §1.5 所有請求經由 Rust API Gateway（:6500）
- [ ] 依 AGENTS.md §1.7 LLM 呼叫統一使用 `shared/llm_resolver.py`
- [ ] Rust Gateway 已註冊 proxy 路由
- [ ] 信任等級限制已生效
- [ ] 場景隔離已實作

### 2.4 運行（Run）

運行階段包含以下常駐行為：

- **意圖分類**：接收使用者輸入，經三層漏斗分類後路由
- **技能執行**：呼叫綁定 Skills 的 `execute()` 方法
- **對話管理**：維護 session 內的對話歷史（受 max_turns 限制）
- **安全檢查**：每筆請求通過信任等級與場景邊界驗證
- **日誌記錄**：所有互動寫入 audit log

### 2.5 監控（Monitor）

| 指標 | 說明 | 警示閾值 |
|------|------|----------|
| `agent_requests_total` | 請求總量 | — |
| `agent_latency_ms` | 回應延遲（P50/P95/P99） | P95 > 5000ms |
| `agent_error_rate` | 錯誤率 | > 5% |
| `agent_intent_fallback_rate` | 落入 general_chat 的比例 | > 30% |
| `agent_skill_execution_errors` | Skill 執行錯誤 | > 0 |
| `agent_approval_pending_count` | 等待人工作業的請求數 | > 10 |

### 2.6 除役（Retire）

| 步驟 | 動作 |
|------|------|
| 1. 標記停用 | 設定 `agents.status = "disabled"` |
| 2. 關閉路由 | 從 TopOrchestrator 移除路由規則 |
| 3. 保留資料 | 保留對話記錄與 audit log 供查核 |
| 4. 通知使用者 | 公告該 Agent 已停用 |
| 5. 清理資源 | 移除 Rust Gateway proxy 路由（N 個月後） |

---

## 3. Agent 定義規範

### 3.1 agents 集合 Schema

所有 Agent 元資料統一存放於 ArangoDB `agents` 集合，Schema 定義如下：

| 欄位 | 型別 | 必填 | 說明 |
|------|------|:----:|------|
| `_key` | string | ✅ | Agent 唯一識別鍵（snake_case，如 `welfare_secretary`） |
| `name` | string | ✅ | 顯示名稱（如「福祉業務小秘」） |
| `type` | string | ✅ | Agent 類型：`bpa` / `advisor` / `tool_agent` / `oracle` |
| `version` | string | ✅ | 語意版本號（SemVer） |
| `description` | string | ✅ | 功能說明，供路由系統發現使用 |
| `endpoint_url` | string | ✅ | 服務端點路徑（如 `/order-secretary`），由 Rust Gateway 轉發 |
| `status` | string | ✅ | `enabled` / `disabled` / `maintenance` |
| `scenes` | array | ✅ | 支援的場景清單：`["internal", "customer", "public"]` |
| `trust_tier` | string | ✅ | 信任等級：`T1` / `T2` / `T3` / `T4` |
| `max_turns` | number | ✅ | 單一 session 最大對話回合數（0 = 不限制） |
| `max_delegation_depth` | number | ✅ | 最大代理委託深度（預設 3） |
| `requires_approval_for` | array | ❌ | 需要審批的操作類型：`["write", "delete", "broadcast", "financial"]` |
| `bound_skills` | array | ❌ | 綁定的 Skills 名稱清單：`["greeting_engine", "timeline_engine"]` |
| `declared_intents` | array | ❌ | 該 Agent 聲明的意圖清單（詳見第 5 章） |
| `allowed_scopes` | array | ❌ | 允許存取的 scope 清單：`["erp", "crm", "timeline", "faq"]` |
| `system_prompt` | string | ❌ | System Prompt 模板或參考路徑 |
| `llm_config` | object | ❌ | LLM 配置覆寫：`{model, temperature, max_tokens}` |
| `tag` | array | ❌ | 標籤，用於分類與搜尋 |
| `created_at` | string | ✅ | ISO 8601 建立時間 |
| `updated_at` | string | ✅ | ISO 8601 更新時間 |

### 3.2 完整文件範例

```json
{
  "_key": "welfare_secretary",
  "name": "福祉業務小秘",
  "type": "bpa",
  "version": "1.0.0",
  "description": "業務人員專用 BPA，支援客戶管理、問候發送、行程安排、ERP/CRM 查詢",
  "endpoint_url": "/welfare-secretary",
  "status": "enabled",
  "scenes": ["internal", "customer"],
  "trust_tier": "T2",
  "max_turns": 50,
  "max_delegation_depth": 3,
  "requires_approval_for": ["broadcast", "delete"],
  "bound_skills": [
    "greeting_engine",
    "timeline_engine",
    "image_processor",
    "push_engine",
    "crm_query",
    "visit_plan",
    "knowledge_agent",
    "customer_safe_reply",
    "business_notification",
    "ragic_timeline_poller"
  ],
  "declared_intents": [
    {
      "name": "greeting_customer",
      "description": "代理客戶問候，生成個人化早安/節日/生日祝福",
      "keywords": ["問候", "早安", "祝福", "賀詞", "發送問候"],
      "scene": "internal"
    },
    {
      "name": "crm_query",
      "description": "查詢客戶基本資料、聯絡資訊",
      "keywords": ["客戶", "聯絡人", "電話", "地址", "CRM"],
      "scene": "internal"
    },
    {
      "name": "broadcast",
      "description": "群發推播訊息給指定客群",
      "keywords": ["群發", "公告", "通知", "宣傳", "發送給"],
      "scene": "internal",
      "requires_approval": true
    }
  ],
  "allowed_scopes": ["erp", "crm", "timeline", "faq"],
  "system_prompt": "configs/welfare_secretary/system_prompt_internal.txt",
  "llm_config": {
    "model": "qwen2.5:7b",
    "temperature": 0.3,
    "max_tokens": 2048
  },
  "tag": ["bpa", "business", "secretary"],
  "created_at": "2026-06-15T10:00:00Z",
  "updated_at": "2026-06-20T08:30:00Z"
}
```

### 3.3 索引建議

| 索引 | 欄位 | 用途 |
|------|------|------|
| Primary | `_key` | 唯一查找 |
| By type | `type` | 依類型篩選 Agent |
| By status | `status` | 查詢啟用中的 Agent |
| By scene | `scenes` | Array index，依場景查詢可用 Agent |

---

## 4. 技能管理標準

本章重申並擴充 AGENTS.md §1.8 的 Skills 統一管理原則。

### 4.1 目錄結構

```
ai-services/skills/
├── skills.json               ← 技能登記與發現 registry（必要）
├── __init__.py               ← 套件匯出
├── <skill_name>/             ← 每個技能一個子目錄
│   ├── skill.py              ← 主要實作（必要，統一介面）
│   └── __init__.py           ← 子套件匯出（選用）
```

### 4.2 skills.json 登記規則

| 欄位 | 必填 | 型別 | 說明 |
|------|:----:|------|------|
| `name` | ✅ | string | 技能唯一名稱（snake_case） |
| `description` | ✅ | string | 功能說明，供 LLM 工具發現使用 |
| `version` | ✅ | string | 語意版本號（SemVer） |
| `source` | ✅ | string | 相對於 `ai-services/skills/` 的路徑 |
| `intent_hints` | ❌ | object | 意圖輔助判斷：`{triggers[], keywords[], example_phrases[]}` |
| `input` | ✅ | object | 輸入參數規格（參數名 → 說明） |
| `output` | ✅ | object | 輸出屬性規格 |
| `dependencies` | ❌ | array | 依賴的外部服務或模組 |

#### skills.json 完整範本

```json
{
  "meta": {
    "version": "1.0.0",
    "lastUpdate": "2026-06-20",
    "description": "Skills 統一登記與發現目錄"
  },
  "skills": [
    {
      "name": "your_skill_name",
      "description": "簡潔描述此技能的單一職責",
      "version": "1.0.0",
      "source": "skills/your_skill_name/skill.py",
      "intent_hints": {
        "triggers": ["trigger_a", "trigger_b"],
        "keywords": ["關鍵字A", "關鍵字B"],
        "example_phrases": [
          "使用範例句子一",
          "使用範例句子二"
        ]
      },
      "input": {
        "param1": "string: 參數說明",
        "param2": "number: 參數說明"
      },
      "output": {
        "result_field": "type: 輸出說明"
      },
      "dependencies": ["模組A", "模組B"]
    }
  ]
}
```

### 4.3 呼叫介面規範

所有 Skill 必須實作統一的非同步進入點：

```python
async def execute(params: dict) -> dict:
    """統一呼叫介面。

    Args:
        params: 依 skills.json 定義的 input 規格

    Returns:
        依 skills.json 定義的 output 規格
    """
```

呼叫方式：

```python
from skills.<name>.skill import execute
result = await execute({"param1": "value1", "param2": "value2"})
```

### 4.4 開發規範

1. **單一職責**：一個 Skill 只做一件事
2. **無狀態**：Skill 不應有內部狀態，所有配置透過 params 傳入
3. **可複用**：不寫死特定 Agent 名稱或業務邏輯，透過參數化支援不同情境
4. **自包含**：每個 Skill 目錄完整，不依賴其他 Skill 的內部實作
5. **錯誤處理**：所有異常必須捕捉並回傳 `{"error": "描述"}`，不可拋出未處理例外
6. **文件**：每個 skill.py 必須包含 Skill 規範區塊（用途、輸入、輸出、依賴）

### 4.5 版本管理

| 變更類型 | 版本更新 | 說明 |
|----------|----------|------|
| 向下相容的新功能 | MINOR (+0.1) | 新增參數、新增輸出欄位 |
| 向下不相容的變更 | MAJOR (+1.0) | 移除或改名參數/輸出、變更行為 |
| Bug 修復 | PATCH (+0.0.1) | 不影響介面的內部修正 |

### 4.6 違反規範的處理

- 在 `ai-services/skills/` 之外建立可複用技能 → 不予合併
- Skill 缺少 `skills.json` 登記 → 不予合併
- Skill 未實作 `execute(params) -> dict` 統一介面 → 不予合併
- Skill 將特定 Agent 邏輯寫死在程式碼中（如 hardcode agent_key）→ 退回重構
- Skill 違反單一職責原則 → 退回拆分

---

## 5. 意圖管理框架

意圖管理是 Agent 系統的核心。本章定義三層分類漏斗、意圖定義 Schema、Agent 中心的意圖所有權模型，以及與既有 `intent_catalog` 的相容策略。

### 5.1 三層分類漏斗

```
使用者輸入（NL Query）
     │
     ▼
┌──────────────────────────────────┐
│ Layer 1: 關鍵字快速匹配          │
│ 關鍵字清單 → O(1) lookup        │
│ 延遲：< 1ms                      │
│                                  │
│ 命中 → 直接路由                  │
│ 未命中 → Layer 2                │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│ Layer 2: Embedding 向量檢索      │
│ Qdrant 語意相似度搜尋            │
│ 延遲：10-50ms                    │
│                                  │
│ 信心度 ≥ auto_route 門檻 → 路由  │
│ 信心度 ≥ verify 門檻 → 要求驗證  │
│ 信心度 < verify 門檻 → Layer 3  │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│ Layer 3: LLM 語意分類            │
│ 使用 shared/llm_resolver.py     │
│ 延遲：200-2000ms                 │
│                                  │
│ 輸出：intent_name + confidence   │
│ 若仍無法分類 → general_chat     │
└──────────────────────────────────┘
```

| 層級 | 技術 | 延遲 | 適合場景 |
|------|------|------|----------|
| Layer 1: 關鍵字 | Token 比對（Python `in` / Trie） | < 1ms | 明確的操作型意圖（查詢、問候、群發） |
| Layer 2: Embedding | Qdrant 向量檢索 | 10-50ms | 語意相似但關鍵字不明確的情境 |
| Layer 3: LLM | LLM 分類 + 提示工程 | 200-2000ms | 模糊意圖、多義句、複合請求 |

### 5.2 意圖定義 Schema

每個意圖是一個結構化文件，可存放於 `agents.declared_intents[]`（新架構）或 `intent_catalog` 集合（既有架構）。

| 欄位 | 型別 | 必填 | 說明 |
|------|------|:----:|------|
| `name` | string | ✅ | 意圖唯一名稱（snake_case，如 `greeting_customer`） |
| `description` | string | ✅ | 意圖功能說明 |
| `keywords` | array | ✅ | Layer 1 關鍵字比對清單 |
| `nl_patterns` | array | ❌ | 模板化 NL 模式（如 `發送{早安\|晚安}問候給{客戶名}`），供 Layer 2 訓練 |
| `exclusion_patterns` | array | ❌ | 排除模式：符合這些模式的輸入不應匹配此意圖 |
| `routing` | object | ✅ | 路由目標定義 |
| `routing.target_type` | string | ✅ | `skill` / `agent` / `llm_direct` / `tool` |
| `routing.target` | string | ✅ | 目標名稱（skill 名稱或 agent_key 或 tool_name） |
| `routing.parallel` | boolean | ❌ | 是否並行呼叫多個目標 |
| `confidence` | object | ✅ | 信心度門檻 |
| `confidence.auto_route` | number | ✅ | 高於此值自動路由（0.0-1.0） |
| `confidence.verify` | number | ✅ | 高於此值但未達 auto_route 時要求使用者驗證（0.0-1.0） |
| `scene` | string | ❌ | 所屬場景：`internal` / `customer` / `public` |
| `auth` | object | ❌ | 權限限制 |
| `auth.trust_level` | string | ❌ | 最低需求信任等級（`T1` / `T2` / `T3` / `T4`） |
| `requires_approval` | boolean | ❌ | 是否需人工審批（預設 false） |

#### 完整範例

```json
{
  "name": "greeting_morning",
  "description": "發送個人化早安問候給指定客戶",
  "keywords": ["早安", "晨間問候", "早安圖", "早安問候"],
  "nl_patterns": [
    "發送早安問候給{客戶名}",
    "跟{客戶名}說早安"
  ],
  "exclusion_patterns": [
    "早安你好",           # 純打招呼，非業務操作
    "早安\\d{1,2}月\\d{1,2}日"  # 日期提醒，非問候操作
  ],
  "routing": {
    "target_type": "skill",
    "target": "greeting_engine",
    "parallel": false
  },
  "confidence": {
    "auto_route": 0.85,
    "verify": 0.6
  },
  "scene": "internal",
  "auth": {
    "trust_level": "T2"
  },
  "requires_approval": false
}
```

### 5.3 Agent 中心的意圖所有權

不同於傳統集中式意圖目錄，AIBox 採用 **Agent 聲明意圖（Declared Intents）** 模型：

```
agents 集合（ArangoDB）
  │
  ├── welfare_secretary
  │     └── declared_intents: [
  │           { name: "greeting_customer", routing→skill: greeting_engine },
  │           { name: "crm_query",        routing→skill: crm_query },
  │           { name: "broadcast",        routing→skill: push_engine }
  │         ]
  │
  ├── order_secretary
  │     └── declared_intents: [
  │           { name: "po_query",        routing→skill: erp_query },
  │           { name: "order_status",   routing→skill: erp_query }
  │         ]
  │
  └── performance_advisor
        └── declared_intents: [
              { name: "query_analysis",  routing→llm_direct },
              { name: "schema_check",    routing→agent: data_agent }
            ]
```

**原則**：

1. 每個 Agent 在其 `agents` 文件的 `declared_intents[]` 中聲明自己負責的意圖
2. 意圖的 `routing.target_type` 指向 Agent 擁有的 Skill 或其他 Agent
3. TopOrchestrator 匯集所有 Agent 的 `declared_intents[]`，建立全域意圖路由表
4. 意圖名稱在 Agent 範圍內唯一，跨 Agent 可重名（不同 Agent 可處理同名但語義不同的意圖）
5. 當一個意圖被觸發時，該 Agent 的場景（scene）和安全限制（trust_tier）一併生效

### 5.4 與既有 intent_catalog 的相容性

系統中存在兩種意圖存放方式，需逐步收斂：

| 面向 | 既有模式（intent_catalog） | 目標模式（declared_intents） |
|------|---------------------------|------------------------------|
| 存放位置 | ArangoDB `intent_catalog` 集合 | `agents[].declared_intents[]` |
| 所有權 | 隱含（agent_scope 欄位標記） | 明確（屬於宣告它的 Agent） |
| 適用範圍 | Data Agent 資料查詢意圖 + Orchestrator 操作意圖 | 所有 Agent 的意圖 |
| Scope 區分 | `intent_catalog` 通用 / `da_intents` 資料語意 | 由 Agent 的 `scenes[]` 決定 |

#### 遷移路徑

| Phase | 內容 |
|-------|------|
| Phase 1（現狀） | 既有 `intent_catalog` 持續運作，Data Agent 使用 `da_intents` |
| Phase 2 | 新 Agent 使用 `declared_intents[]` 宣告意圖，`intent_catalog` 維持唯讀 |
| Phase 3 | 將 `intent_catalog` 中的 Data Agent 意圖轉移至 `agents.data_agent.declared_intents[]` |
| Phase 4 | 將 Orchestrator 意圖對應到各 Agent 的意圖宣告 |
| Phase 5 | `intent_catalog` 標記為 deprecated，唯讀保留供查詢歷史 |
| Phase 6 | `intent_catalog` 除役，全部由 `agents[].declared_intents[]` 取代 |

遷移期間，TopOrchestrator 同時查詢兩種來源，以 `intent_catalog` 為優先（向後相容）。

### 5.5 意圖 - 技能 - 工具映射

```
┌────────────────────────────────────────────────────────────┐
│                     TopOrchestrator                        │
│  匯集全域 declared_intents + intent_catalog 建立路由表     │
└──────────┬─────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────────┐
│  匹配的 Intent                                             │
│  { name: "greeting_customer",                              │
│    routing: { target_type: "skill", target: "greeting_engine" }}│
└──────────┬─────────────────────────────────────────────────┘
           │ 路由到目標 Agent
           ▼
┌────────────────────────────────────────────────────────────┐
│  Agent: welfare_secretary                                  │
│                                                            │
│  1. 載入 scene = "internal" 的安全邊界                      │
│  2. 檢查 trust_tier = T2 是否足夠                           │
│  3. 初始化 session / 恢復對話歷史                            │
│  4. 呼叫技能                                               │
└──────────┬─────────────────────────────────────────────────┘
           │ skill.execute(params)
           ▼
┌────────────────────────────────────────────────────────────┐
│  Skill: greeting_engine                                    │
│  1. 查 CRM 取得客戶尊稱                                     │
│  2. 呼叫 llm_resolver 生成問候內容                          │
│  3. 寫入 customer_timelines                                 │
│  4. 回傳 { greeting_text, honorific, tone }                │
└──────────┬─────────────────────────────────────────────────┘
           │ 內部使用工具
           ▼
┌──────────┴──────────┐  ┌──────────┴──────────┐
│ Tool: ArangoDB      │  │ Tool: llm_resolver  │
│ CRM 客戶查詢        │  │ 問候內容生成         │
└─────────────────────┘  └─────────────────────┘
```

---

## 6. 跨 Agent 協作

單一 Agent 無法處理所有請求，跨 Agent 協作是必要的。

### 6.1 Handoff 模式

定義三種標準 Handoff 模式：

#### 6.1.1 Tail-Call Handoff（尾呼叫轉交）

當前 Agent 完成判斷後，將控制權完全移交給目標 Agent。

```
Agent A (判斷意圖屬於 Agent B)
  │
  ├─ 準備 context（當前 session 摘要）
  ├─ 呼叫 Agent B 的 endpoint
  └─ Agent B 接手，Agent A 不再參與
```

**適用場景**：General Chat 判斷為查詢請求時轉交 Data Agent。

#### 6.1.2 Subagent（子代理）

當前 Agent 呼叫子 Agent 執行特定子任務，子任務完成後回傳結果。

```
Agent A (主要)
  │
  ├─ call Agent B (subagent)
  │     └─ Agent B 執行查詢，回傳結果
  ├─ 合併結果到回應
  └─ 繼續處理
```

**適用場景**：BPA 需要同時查詢 CRM 和 ERP 後組合回應。

#### 6.1.3 Router（路由器）

專用路由 Agent 負責將請求分發到正確的目標 Agent。

```
TopOrchestrator (路由器)
  │
  ├─ Intent 分類
  ├─ 根據 routing.target 分發
  │     ├─ BPA A
  │     ├─ BPA B
  │     └─ Advisor C
  └─ 收集結果（若 parallel）
```

**適用場景**：最上層的意圖路由與請求分發。

### 6.2 Context 共享模型

| 模式 | 說明 | 資料量 | 適用時機 |
|------|------|--------|----------|
| **Full** | 傳遞完整 session context | 大 | 深度協作，子 Agent 需要完整背景 |
| **Summary** | LLM 生成的摘要 context | 中 | 一般 handoff，目標 Agent 了解大致背景即可 |
| **Sanitized** | 移除敏感資訊後的 context | 小 | 跨場景 handoff（內部→客戶端） |

Sanitized context 須移除以下內容：

- 內部系統路徑與 IP
- 機密客戶資料（如完整身份證字號需遮罩）
- 內部審批意見與備註
- 其他 Agent 宣告為 internal 的內容

### 6.3 Delegation 深度限制

| 層級 | 說明 | 限制 |
|------|------|------|
| L0 | 當前 Agent | — |
| L1 | 直接呼叫子 Agent | max_delegation_depth ≥ 1 |
| L2 | 子 Agent 再呼叫另一 Agent | max_delegation_depth ≥ 2 |
| L3 | 三層委託 | max_delegation_depth ≥ 3 |
| L4+ | 超過深度上限 | 禁止，回傳「已達委託深度上限」 |

每個 Agent 的 `max_delegation_depth` 欄位控制該 Agent 發起的最大委託深度，超過時應回傳錯誤而非靜默繼續。

### 6.4 Handoff Topology 定義

系統中的 Agent 協作拓撲應明確定義，避免循環 Handoff：

```
TopOrchestrator
  │
  ├── Welfare Secretary (BPA)
  │     ├── Data Agent (透過 API 查詢 ERP)
  │     └── Knowledge Agent (FAQ 查詢)
  │
  ├── Order Secretary (BPA)
  │     └── Data Agent
  │
  ├── Performance Advisor
  │     └── Data Agent (唯讀分析)
  │
  └── Knowledge Agent (Oracle)
```

**禁止**：

- A → B → A 的循環 Handoff
- 無限制的委託鏈（超過 max_delegation_depth 即拒絕）
- 跨場景的未消毒 context 傳遞（如內部場景直接傳遞完整 context 到客戶端場景）

---

## 7. 治理與安全

### 7.1 信任等級系統（Trust Tier）

基於 Anthropic Agent 安全規範，定義四級信任系統：

| 等級 | 名稱 | 說明 | 允許操作 | 審批要求 |
|:----:|------|------|----------|----------|
| **T1** | 公開 | 公開資訊查詢、FAQ 回覆 | 唯讀公共資料 | 無 |
| **T2** | 內部 | 內部業務查詢、基本寫入 | 讀取內部資料、寫入非敏感記錄 | 寫入操作需記錄 |
| **T3** | 受限 | 機密資料存取、刪除操作 | 讀取機密資料、刪除記錄、大量異動 | 刪除/大量操作需人工審批 |
| **T4** | 管制 | 高風險操作、財務/法務 | 所有操作（含財務交易、合約異動） | 所有操作需雙人審批 |

**信任等級判定流程**：

```
1. 取三者最小值：
   a. Agent 本身的 trust_tier
   b. 場景要求的 trust_tier（scene → trust_tier 映射）
   c. 意圖要求的 trust_tier（intent.auth.trust_level）
2. 以最小值作為有效信任等級
3. 若操作類型在 requires_approval_for 清單中，觸發審批流程
```

### 7.2 防護柵欄（Guardrails）

| 防護機制 | 參數 | 預設值 | 違規處理 |
|----------|------|--------|----------|
| 最大對話輪數 | `max_turns` | 50 | 終止 session，提示「已達對話上限」 |
| 最大委託深度 | `max_delegation_depth` | 3 | 回傳「已達委託深度上限」 |
| 操作審批 | `requires_approval_for` | `[]` | 暫停執行，發送審批請求 |
| 場景隔離 | `scenes[]` | — | 拒絕跨場景未授權存取 |
| Scope 限制 | `allowed_scopes[]` | — | 拒絕 scope 外的資料存取 |
| LLM Provider 統一 | — | — | 強制使用 `shared/llm_resolver.py` |

### 7.3 審計日誌（Audit Log）

所有 Agent 互動必須記錄到 `audit_logs` 集合：

| 欄位 | 說明 |
|------|------|
| `_key` | 日誌唯一 ID（自動產生） |
| `timestamp` | 事件時間（ISO 8601） |
| `agent_key` | 處理 Agent 的識別鍵 |
| `session_id` | 對話 session ID |
| `user_id` | 使用者 ID |
| `intent_name` | 匹配到的意圖名稱 |
| `input_summary` | 輸入摘要（前 200 字） |
| `output_summary` | 輸出摘要（前 200 字） |
| `skills_invoked` | 呼叫的 Skills 清單 |
| `trust_tier_effective` | 生效的信任等級 |
| `requires_approval` | 是否觸發審批 |
| `approved_by` | 審批人（若有） |
| `latency_ms` | 處理延遲 |
| `status` | `success` / `error` / `blocked` / `pending_approval` |
| `error` | 錯誤資訊（若有） |
| `metadata` | 額外上下文 |

### 7.4 資訊分級（L0 - L4）

專案自訂的資訊分類系統，用於控制 Agent 的資料存取範圍：

| 等級 | 名稱 | 定義 | 範例 | 最低信任等級需求 |
|:----:|------|------|------|:----------------:|
| **L0** | 公開 | 可對外公開的資訊 | 產品型號、服務據點、營業時間 | T1 |
| **L1** | 內部一般 | 內部員工可存取 | 內部流程文件、部門聯絡方式 | T2 |
| **L2** | 機密業務 | 限特定角色存取 | 客戶名單、報價記錄、銷售數據 | T2 |
| **L3** | 敏感客戶 | 高度敏感的客戶資料 | 完整身份證字號、病歷、財務帳戶 | T3 |
| **L4** | 管制資料 | 法定保護資料 | 合約正本、審批文件、稽核記錄 | T4 |

**L0-L4 與場景的對應關係**：

```
客戶端場景 (customer)  →  僅可存取 L0
內部場景 (internal)    →  可存取 L0-L2（特殊角色可存取 L3）
管理員場景 (admin)     →  可存取 L0-L4
```

---

## 8. MCP 工具整合

MCP（Model Context Protocol）是 Agent 與外部工具互動的標準協定。

### 8.1 Progressive Discovery 模式

```
Agent 啟動
  │
  ├─ 1. tools/list
  │     查詢 MCP Server 提供的工具清單
  │     回傳：tools[] { name, description, inputSchema }
  │
  ├─ 2. 將 tools[] 注入 LLM 的 tool calling context
  │
  ├─ 3. LLM 決定呼叫某個 tool
  │     └─ tools/call { name, arguments }
  │
  └─ 4. 接收 tool 執行結果，回傳給 LLM 處理
```

### 8.2 工具註冊

所有工具需在 `mcp_tools/` 服務中註冊：

| 欄位 | 必填 | 說明 |
|------|:----:|------|
| `name` | ✅ | 工具名稱（snake_case） |
| `description` | ✅ | 工具說明，供 LLM 判斷何時使用 |
| `input_schema` | ✅ | JSON Schema 定義輸入參數 |
| `server` | ✅ | 所屬 MCP Server 名稱 |
| `auth_required` | ❌ | 是否需要認證 |
| `rate_limit` | ❌ | 速率限制（req/min） |

### 8.3 共享工具 vs Agent 特定工具

| 類型 | 範圍 | 註冊位置 | 範例 |
|------|------|----------|------|
| **共享工具** | 所有 Agent 皆可使用 | `mcp_tools/` 全域註冊 | web_search、translate、calculator |
| **Agent 特定工具** | 僅限特定 Agent 使用 | Agent 內部設定 | send_line_message（僅 BPA 可用） |

共享工具透過 MCP Server 的 `tools/list` 統一暴露。Agent 特定工具則在 Agent 的 `router.py` 中定義，不對外暴露。

### 8.4 外部工具整合流程

```
Agent
  │
  ├─ 前端請求 → Rust API Gateway (:6500) → Agent endpoint
  │
  ├─ Agent 判斷需要外部工具
  │     └─ 呼叫 MCP Tools Service (:8004)
  │           ├─ POST /mcp/tools/list    → 查詢可用工具
  │           ├─ POST /mcp/tools/call    → 執行工具
  │           └─ POST /mcp/tools/status  → 查詢非同步工具狀態
  │
  └─ 取得結果後，組合回應回傳
```

---

## 9. 範本使用指南

本章逐步說明如何根據此規範建立一個新的 Agent。

### 9.1 建立新 Agent 步驟

#### Step 1：定義 Agent 基本資訊

填寫以下資訊：

| 項目 | 說明 | 範例 |
|------|------|------|
| Agent 名稱 | 顯示名稱 | 「訂單管理助手」 |
| Agent Key | `_key` 值（snake_case） | `order_assistant` |
| 類型 | bpa / advisor / tool_agent / oracle | bpa |
| 場景 | internal / customer / public | internal |
| 目的 | 一句話描述 | 協助業務人員查詢與管理訂單 |

#### Step 2：撰寫 System Prompt

建立 `ai-services/bpa/<agent_key>/config.py`，包含：

- 角色設定
- 行為規則
- 資料邊界描述
- 不應處理的事項
- LLM 模型設定（model, temperature, max_tokens）

#### Step 3：設計意圖清單

在 `declared_intents[]` 中定義每個意圖（參照 5.2 節 Schema）：

1. 列出 Agent 需要處理的所有使用者請求類型
2. 每個請求類型對應一個意圖
3. 每個意圖指定：
   - Layer 1 關鍵字
   - Layer 2 NL patterns / embedding examples
   - routing 目標（skill / agent / llm_direct）
   - confidence 門檻

#### Step 4：綁定 Skills

1. 查閱 `skills.json` 確認哪些既有 Skills 可複用
2. 若需要新 Skill，按第 4 章規範建立（skills/ 目錄 + skills.json 登記）
3. 在 `agents` 文件的 `bound_skills[]` 中列出

#### Step 5：實作 Router

建立 `ai-services/bpa/<agent_key>/router.py`：

```
router.py 範本結構：
├─ ChatRequest / ChatResponse (Pydantic)
├─ 意圖分類函式（三層漏斗）
├─ 技能分派函式（if/elif 根據意圖呼叫對應 skill.execute()）
├─ LLM 回退處理（general_chat）
└─ FastAPI router 註冊
```

#### Step 6：註冊到 Rust Gateway

在 `api/src/api/mod.rs` 中加入 proxy 路由（依 AGENTS.md §1.5）：

```rust
.route("/order-assistant/*", any(proxy_to_unified_agents))
```

#### Step 7：登記到 ArangoDB

寫入 `agents` 集合：

```json
{
  "_key": "order_assistant",
  "name": "訂單管理助手",
  "type": "bpa",
  "version": "1.0.0",
  "description": "協助業務人員查詢與管理訂單",
  "endpoint_url": "/order-assistant",
  "status": "enabled",
  "scenes": ["internal"],
  "trust_tier": "T2",
  "max_turns": 50,
  "max_delegation_depth": 3,
  "requires_approval_for": [],
  "bound_skills": ["crm_query", "timeline_engine"],
  "declared_intents": [
    {
      "name": "order_status_query",
      "description": "查詢訂單狀態",
      "keywords": ["訂單", "出貨", "狀態", "進度"],
      "routing": { "target_type": "skill", "target": "erp_query", "parallel": false },
      "confidence": { "auto_route": 0.85, "verify": 0.6 },
      "scene": "internal",
      "auth": { "trust_level": "T2" }
    }
  ],
  "allowed_scopes": ["erp", "crm"],
  "created_at": "2026-06-20T00:00:00Z",
  "updated_at": "2026-06-20T00:00:00Z"
}
```

#### Step 8：部署檢查清單

- [ ] Agent 規格書已更新
- [ ] `agents` 集合已登記
- [ ] `skills.json` 已更新（若新增 Skill）
- [ ] Rust Gateway 已註冊 proxy 路由
- [ ] LLM 呼叫使用 `shared/llm_resolver.py`
- [ ] 三層意圖分類已實作
- [ ] 信任等級限制已生效
- [ ] 場景隔離已實作（若有多場景）
- [ ] 測試案例已涵蓋所有意圖
- [ ] 錯誤處理已涵蓋所有 Skill 呼叫
- [ ] 審計日誌已串接

### 9.2 目錄結構範本

```
ai-services/bpa/<agent_key>/
├── __init__.py
├── router.py              # FastAPI router（主要進入點）
├── config.py              # System Prompt + LLM 設定
├── internal_router.py     # 內部場景的邏輯（若與客戶端分離）
├── customer_router.py     # 客戶端場景的邏輯（若有）
├── skills/                # Agent 特定技能（少用，優先複用既有 Skills）
│   └── ...
└── tests/
    ├── test_intents.py    # 意圖分類測試
    └── test_skills.py     # Skill 呼叫測試
```

### 9.3 文件位置索引

| 文件 | 位置 | 用途 |
|------|------|------|
| Agent 規格書 | `.docs/Spec/智能體與工具市集/<Agent名稱>/` | 規格定義與設計文件 |
| Agent 程式碼 | `ai-services/bpa/<agent_key>/` | 主要實作 |
| Agent 登記 | ArangoDB `agents` 集合 | 運行時元資料 |
| Skills 登記 | `ai-services/skills/skills.json` | 技能發現與註冊 |
| Rust Gateway 路由 | `api/src/api/mod.rs` | 請求轉發 |
| 專案規範 | `AGENTS.md` | 憲法級開發原則 |

---

## 附錄 A：名詞對照表

| 中文 | English | 說明 |
|------|---------|------|
| 智能體 | Agent | 具備意圖感知、技能組合與安全邊界的自主運算單元 |
| 技能 | Skill | 單一職責的業務邏輯單元，無狀態、可複用 |
| 工具 | Tool | 底層資源操作的抽象（MCP / API / SDK） |
| 意圖 | Intent | 使用者請求的分類標籤，對應一個處理路徑 |
| 信任等級 | Trust Tier | T1-T4 的四級信任系統 |
| 場景 | Scene | Agent 的執行場景（internal / customer / public） |
| 資訊分級 | Info Classification | L0-L4 的五級資訊敏感度分級 |
| 委託深度 | Delegation Depth | Agent 跨 Agent 呼叫的巢狀層數 |
| 審計日誌 | Audit Log | 所有 Agent 互動的不可否認性記錄 |
| MCP | Model Context Protocol | Agent 與外部工具互動的標準協定 |
| Handoff | Handoff | Agent 間的控制權移交 |
| Router | Router | 負責請求分發的路由 Agent 或路由邏輯 |
| LLM Resolver | LLM Resolver | 統一 LLM 呼叫解析器（`shared/llm_resolver.py`） |

---

## 附錄 B：相關文件

| 文件 | 內容 |
|------|------|
| `AGENTS.md` | 憲法級開發原則、Skills 管理、BPA 定義、請求轉發架構 |
| `project-architecture.md` | 服務架構、Port 表、執行環境 |
| `agent-development.md` | Agent 建立指南、BPA 開發實務 |
| `tools-mcp-Settings.md` | 外部 MCP Tool 設定 |
| `coding-standards.md` | 編碼規範（命名、import、元件結構、錯誤處理） |
| `.sisyphus/safety-rules.md` | 破壞性操作安全規範 |
