---
lastUpdate: 2026-04-29 14:00:00
author: AI Agent
version: 1.0.0
---

# AI Skill 開發指引

## 概述

Skill（技能）是平台中可被任何 Agent 或 Tool 調用的最小執行單元。每個 Skill 是**無狀態、可測試、版本管控**的程式碼，有嚴格的輸入輸出規範。

## 角色

| 角色 | 職責 | 可操作狀態 |
|------|------|-----------|
| **顧問** | 提出技能需求、描述流程、驗收測試 | draft, testing |
| **開發者** | 程式碼實作、單元測試、版控 | spec, developing, testing |
| **管理員** | 審查上線、版本發布 | live, deprecated |

## 狀態流程

```
draft → spec → developing → testing → live → deprecated
  ^                                      │
  └──────────────────────────────────────┘
           (可回退重新開發)
```

| 狀態 | 說明 | 責任人 |
|------|------|--------|
| `draft` | 顧問提交技能需求（文字描述 + 預想步驟） | 顧問 |
| `spec` | 開發者/管理員接手，分析產出規格書 | 開發者 |
| `developing` | 程式碼實作中 | 開發者 |
| `testing` | 實作完成，待顧問驗證 | 顧問 |
| `live` | 審查通過，正式上線（可被路由） | 管理員 |
| `deprecated` | 已淘汰，不再路由 | 管理員 |

## 技能編號格式

```
SKL-{YY}{WW}-{NNN}
範例：SKL-2618-001
│    ││ ││  │
│    ││ ││  └── 本週第 001 號技能（自動遞增）
│    ││ │└───── 年份末兩碼（2026）
│    ││ └────── 週次（ISO week 18）
│    │└─────── 前綴固定 SKL
```

## Skill Spec 結構（ArangoDB `skill_specs`）

```json
{
  "_key": "uuid",
  "skill_id": "SKL-2618-001",
  "name": "query_stock",
  "title": "庫存品項查詢",
  "version": "v1.0.0",
  "status": "draft | spec | developing | testing | live | deprecated",
  "skill_type": "data | knowledge | tool | process | system",
  "tags": ["庫存", "品項查詢", "STOCK_16"],
  "description": "查詢可訂購品項及庫存數量",
  "steps": ["從 product_cache 讀取資料", "套用 allowed_fields 過濾", "LLM 格式化輸出"],
  "guardrails": ["禁止編造不存在的產品", "禁止輸出 JSON", "禁止顯示價格欄位"],
  "data_scope": {
    "tables": ["STOCK_16"],
    "allowed_fields": { "1018133": "品項名稱", "1018271": "存放數量", "1018130": "單位" },
    "denied_fields": { "1018138": "入庫單價/g", "1018139": "庫存總金額/批" }
  },
  "linked_intents": ["product_list"],
  "code_language": "python",
  "spec_md_url": "s3://skills/query_stock/v1.0.0/spec.md",
  "source_url": "s3://skills/query_stock/v1.0.0/src/",
  "created_by": "顧問名稱",
  "developed_by": "開發者名稱",
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

## 開發流程

### Step 1：提交技能需求（顧問）

在技能管理頁面建立新技能，填寫：
- 技能名稱（英文代號）
- 描述（中文）
- 預想步驟
- 護欄規則
- 標籤（便於 AI 搜尋）
- 資料範圍（選擇表格、允許/禁止欄位）

狀態：`draft`

### Step 2：規格分析（開發者）

接收後：
1. 調用 `GET /api/v1/skills/by-no/{skill_no}` 取得需求
2. 分析技術可行性
3. 產出規格書（AI 輔助）
4. 寫入 `spec_md_url`（SeaweedFS/S3）

狀態：`spec` → `spec_ready`

### Step 3：程式碼實作（開發者）

建立 Python 模組：

```python
from shared.tools.registry import SkillDefinition, ToolResult, ToolExecutionContext

@skill_definition(
    name="query_stock",
    version="v1.0.0",
    skill_type="data",
    tags=["庫存", "STOCK_16"],
    guardrails=["禁止編造產品", "禁止輸出JSON"],
)
async def query_stock(params: dict, context: ToolExecutionContext) -> ToolResult:
    """查詢庫存品項 — 穩定程式碼，無 LLM 自由發揮"""
    try:
        # 從 ArangoDB cache 讀取
        cache = await read_cache("stock_16_products")
        if not cache:
            return ToolResult(success=False, error="暫無庫存資料")
        return ToolResult(success=True, result=cache)
    except Exception as e:
        return ToolResult(success=False, error=str(e))
```

- 程式碼必須有單元測試
- 通過 `ruff check` + `mypy`
- 上傳原始碼到 SeaweedFS/S3（`source_url`）

狀態：`developing`

### Step 4：測試驗證（顧問）

- 呼叫 `POST /api/v1/skills/{skill_id}/test` 執行測試
- 顧問在 UI 上驗證結果
- 若有問題，退回 `developing`

狀態：`testing`

### Step 5：審查上線（管理員）

- 確認規格書、程式碼、測試皆完備
- 標記為 `live`
- 對應的 `intent_catalog` 意圖可開始路由到此技能

狀態：`live`

## API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/v1/skills` | 列表（支援 status/tag 過濾） |
| POST | `/api/v1/skills` | 建立技能需求 |
| GET | `/api/v1/skills/{id}` | 取得技能規格 |
| PUT | `/api/v1/skills/{id}` | 更新技能（含狀態變更） |
| DELETE | `/api/v1/skills/{id}` | 刪除技能 |
| POST | `/api/v1/skills/{id}/analyze` | AI 分析產出規格書 |
| POST | `/api/v1/skills/{id}/test` | 執行測試 |
| POST | `/api/v1/skills/{id}/publish` | 發布上線（draft → live） |
| GET | `/api/v1/skills/by-no/{skill_no}` | 依技能編號查詢 |
| GET | `/api/v1/skills/{id}/spec.md` | 下載規格書 |

## Skill Registry（執行層）

執行階段由 `shared/tools/registry.py` 統一管理：

```python
from shared.tools.registry import SkillRegistry, ToolExecutionContext

registry = SkillRegistry()

# 註冊（啟動時載入所有 status=live 的技能）
registry.register(query_stock)

# 執行
result = await registry.execute(
    skill_name="query_stock",
    params={"filter": "全蛋液"},
    context=ToolExecutionContext(user_id="...", session_id="..."),
)
```

## 與 Agent 的關係

```
Agent 意圖匹配
    ↓
intent_catalog.linked_skills → ["query_stock"]
    ↓
SkillRegistry.execute("query_stock", params)
    ↓
回傳 ToolResult → Agent 格式化成回覆
```

Agent 不直接實作技能邏輯。Agent 負責意圖匹配 + 回應格式化，技能負責穩定的資料處理。

## Preorder Creation 技能規範（order_preorder_collect）

所有預購單建立操作必須透過 `POST /order-secretary/skills/order_preorder_collect` 技能端點，**禁止直接呼叫 raw CRUD API**。

### 路由架構

```
前端表單 (PreorderBoard) ──┐
Chat Agent (order_text) ──┼──→ POST /skills/order_preorder_collect → 寫入 DB
LINE 圖片/文字 ────────────┘
```

### 三種輸入模式

| media_type | 適用場景 | content 格式 |
|-----------|---------|-------------|
| `structured` | 前端表單、Chat Agent 已提取的結構化資料 | `{"items": [...], "notes": "..."}` JSON 字串 |
| `text` | LINE/對話原始文字 | 自然語言描述 |
| `image` | LINE 圖片 | base64 編碼圖片 |

### 呼叫範例

**結構化輸入（前端表單 / Chat Agent）：**

```typescript
// PreorderBoard.tsx
fetch(`${API}/skills/order_preorder_collect`, {
  method: 'POST',
  body: JSON.stringify({
    content: JSON.stringify({
      items: [{ product_name: '鋼板', quantity: 20, unit: '噸', spec: '5mm' }],
      notes: '急單',
    }),
    media_type: 'structured',
    user_id: 'u001',
    user_name: '王小明',
    session_id: 'web:u001',
  }),
});
```

**文字輸入（對話 / LINE）：**

```python
# router.py 或 LINE webhook
from bpa.order_secretary.skills.order_preorder_collect import execute as skill_execute

result = await skill_execute({
    "content": "我要訂購鋼板20噸",
    "media_type": "text",
    "user_id": user_id,
    "user_name": user_name,
    "session_id": session_id,
})
```

### 回應格式

```json
{
  "status": "success | error",
  "order_id": "PO-260429-0001",    // 成功時
  "message": "已為您建立預購單...",
  "missing_fields": [],             // 不完整時列出
  "error_code": "INVALID_JSON | MISSING_ITEMS | DB_WRITE_ERROR | MEDIA_PARSE_FAILED"
}
```

### 兩階段回應流程

需要長時間處理的技能（如檔案分析），必須先回 ack 再處理：

```
呼叫端收到請求
    ↓
Step 1: 立即 reply ACK_MESSAGE（引用技能定義的常數，禁止 hardcode）
    ↓
呼叫端非同步處理（呼叫技能 execute）
    ↓
Step 2: 用 result.message 回覆使用者
```

ack 訊息定義在技能的 `SKILL_DEFINITION` 或常數中，呼叫端應引用而非 hardcode：

```python
# ✅ 正確：引用技能常數
from skills.order_preorder_collect import ACK_MESSAGE_FILE
await reply_message(messages=[{"type": "text", "text": ACK_MESSAGE_FILE}])

# ❌ 錯誤：hardcode
await reply_message(messages=[{"type": "text", "text": "收到您的檔案..."}])
```

### 禁止行為

- ❌ 前端直接呼叫 `POST /order-secretary/preorders`（應走 skill）
- ❌ Chat Agent 直接 import `preorder.create_preorder`（應走 skill）
- ❌ 任何模組直接操作 ArangoDB order_preorders/order_preorder_items（應走 skill）
- ❌ 呼叫端 hardcode ack 訊息（應引用技能常數 `ACK_MESSAGE_FILE`）

### 參考實作

- 技能實作：`ai-services/bpa/order_secretary/skills/order_preorder_collect.py`
- 路由註冊：`ai-services/bpa/order_secretary/router.py`（`skill_order_preorder_collect` 端點）
- 前端呼叫：`src/pages/PreorderBoard.tsx`（`handleCreate`）

---

## 標籤分類

技能可透過 tags 分類，便於開發時 AI 快速搜尋：

| 標籤 | 說明 | 範例 |
|------|------|------|
| `庫存` | 庫存相關 | `query_stock` |
| `訂單` | 訂單/預購相關 | `create_preorder`, `order_track` |
| `ragic` | Ragic 資料源 | 所有 Ragic 技能 |
| `sap` | SAP 資料源（預留） | 未來 SAP 技能 |
| `oracle` | Oracle 資料源（預留） | 未來 Oracle 技能 |
| `data` | 資料查詢類 | `query_stock` |
| `process` | 流程類 | `create_preorder` |

## 安全規範

1. 所有技能必須定義 `data_scope`，否則不允許存取任何資料表
2. `guardrails` 在執行時注入 LLM system prompt，不可由 LLM 自行覆寫
3. 技能不可直接發起 HTTP 請求到外部服務（需透過 Data Agent / MCP Tools）
4. 技能必須是無狀態的（stateless），所有狀態應由呼叫方管理
5. 技能執行超時預設 30 秒，可依 `timeout_seconds` 調整

## 參考

- Agent 開發流程：`agent-tool-dev-guide.md`
- Agent 規範總覽：`AGENTS.md`
- 工具註冊框架：`ai-services/shared/tools/`
- 技能規格集合：ArangoDB `skill_specs`

## 修改歷程
| 日期 | 版本 | 作者 | 變更 |
|------|------|------|------|
| 2026-04-29 | 1.0.0 | AI Agent | 初始版本 |

---

## 附錄：AI 開發觸發（#dev）

當技能規格書產出後，開發者可使用 `#dev {技能編號}` 觸發 AI 開發：

### 觸發條件

使用者訊息包含 `#dev` 關鍵字，後接技能編號（格式：`SKL-2618-001`）。

### 執行步驟

#### Step 1：提取技能編號

從使用者輸入中解析技能編號，格式為 `SKL-{YYWW}-{NNN}`。

#### Step 2：調用 API 取得技能規格

```
GET http://localhost:6500/api/v1/skills/by-no/{skill_no}
```

回應包含完整技能資訊：`title`, `description`, `steps`, `guardrails`, `dev_spec`。

#### Step 3：複製規格書到工作區

```
.opencode/plans/{skill_no}-spec.md
```

#### Step 4：AI Coder 解析

1. **技能理解**：用自己的話重述技能目標與預期行為
2. **技術棧確認**：確認建議的技術都在系統範圍內
3. **模組拆解**：列出需要建立/修改的檔案
4. **實作 SkillDefinition**：使用 `@skill_definition` 裝飾器
5. **單元測試**：確保測試覆蓋率
6. **向使用者確認**：以上分析完成後，請使用者確認是否開始開發

#### Step 5：開始開發

使用者確認後，按照 `AGENTS.md` 的開發規範進行實作。

#### Step 6：發布上線

完成後更新狀態為 `testing` → `live`。

### 範例

```
使用者輸入：
#dev SKL-2618-001 請開始開發庫存查詢技能

AI Coder 應：
1. 解析 `SKL-2618-001`
2. 調用 GET /api/v1/skills/by-no/SKL-2618-001
3. 取得規格書，寫入 .opencode/plans/SKL-2618-001-spec.md
4. 分析規格書，列出開發計畫
5. 向使用者確認後開始開發
```
