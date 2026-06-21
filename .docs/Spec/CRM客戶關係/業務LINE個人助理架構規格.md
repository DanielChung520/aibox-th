---
lastUpdate: 2026-06-19
author: Sisyphus
version: 1.1.0
status: Implementation In Progress
---

# 業務 LINE 個人助理架構規格（跨域整合）

> 本規格橫跨三大模組：[福祉業務小秘]（BPA Agent）、[通訊頻道管理]（Channels）、[我的 LINE 助手]（前端頁面），為獨立於各模組規格之外的整合架構文件。

## 1. 概述

每位業務員擁有自己的 LINE 官方帳號作為個人助理，所有業務員的 LINE 助理統一路由至「福祉業務小秘」中央 agent，由中央 agent 根據 channel 與用戶身份做 persona 差異化回應。

### 1.1 目標

- 每位業務員擁有獨立的 LINE 互動管道
- 統一維護一套中央 agent 邏輯（福祉業務小秘）
- 中央 agent 能區分不同業務員，提供個人化回應
- 管理員可透過後台統一管理所有業務員的 LINE channel

### 1.2 用詞定義

| 用詞 | 定義 |
|------|------|
| **LINE OA** | LINE Official Account，由業務員或公司申請的 LINE 官方帳號 |
| **Channel** | 系統內紀錄，對應一個 LINE OA 的 Messaging API 設定（channel_secret、access_token） |
| **channel_key** | Channel 的唯一識別碼，也是 webhook URL 路徑的一部份 |
| **業務員身份** | 儲存在 channel 的 `business_user_key` 欄位，用於區分不同業務員 |
| **福祉業務小秘** | 中央 BPA Agent，所有 channel 的訊息最終路由至此 |

## 2. 架構總覽

```
業務員A LINE OA      業務員B LINE OA      業務員C LINE OA
    │ (ch_A)             │ (ch_B)             │ (ch_C)
    │ webhook            │ webhook            │ webhook
    ▼                    ▼                    ▼
/api/v1/webhook/line/ch_A  /.../ch_B  /.../ch_C
    │                    │                    │
    │ (Rust API Gateway proxy, passthrough x-line-signature)
    │                    │                    │
    └────────────────────┼────────────────────┘
                         ▼
            unified_agents LINE webhook (webhook.py)
                         │
                查 channels 集合 → channel_key
                         │
                取得 linked_agent_key="welfare_secretary"
                         │
                查 agents 集合 → endpoint_url
                         │
                POST /welfare-secretary/chat
                         │
                   [福祉業務小秘]
                         │
             ┌───────────┼────────────┐
             │           │            │
         Intent      Skills      Knowledge
       Classification          (RAG, Ragic)
             │           │            │
             └───────────┴────────────┘
                         │
                reply_message(channel access_token) 返回 LINE
```

### 2.1 訊息流說明

1. 客戶透過業務員的 LINE OA 發送訊息
2. LINE Platform 呼叫該 OA 設定的 webhook URL（含 channel_key）
3. Cloudflare Tunnel → Rust API Gateway (6500) proxy → unified_agents (8011)
4. `webhook.py` 依 channel_key 取得 channel 設定（secret、token、linked_agent_key）
5. 驗證簽名，解析訊息，建立 session_id（格式：`line:{channel_key}:{user_id}`）
6. 依 linked_agent_key 查詢 agent 的 endpoint_url
7. 呼叫福祉業務小秘的 chat endpoint，帶入 session_id、訊息、channel 資訊
8. 福祉業務小秘從 session_id 解析 channel_key → 查 business_user_key → 載入對應 persona
9. 執行 intent classification → skills → LLM → 回應
10. webhook.py 透過 channel 的 access_token 回覆訊息

## 3. 資料模型

### 3.1 Channels 集合（ArangoDB `channels`）

```json
{
  "_key": "ch_abc123",
  "platform": "line",
  "business_user_key": "sales_001",
  "role": "業務員",
  "name": "王大明 - LINE 助理",
  "status": "active",
  "linked_agent_key": "welfare_secretary",
  "config": {
    "channel_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "access_token": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
    "webhook_url": "https://eeaapi.ent4i.com/api/v1/webhook/line/ch_abc123"
  },
  "metadata": {
    "avatar": "https://..." ,
    "description": "業務員王大明的個人 LINE 助理",
    "tags": ["北區", "資深業務"]
  },
  "created_at": "ISO datetime",
  "updated_at": "ISO datetime"
}
```

索引：`[platform, business_user_key]`、`[platform, status]`

### 3.2 Agents 集合（既有福祉業務小秘紀錄）

```json
{
  "_key": "welfare_secretary",
  "name": "福祉業務小秘",
  "agent_type": "bpa",
  "endpoint_url": "http://localhost:8011/welfare-secretary/chat",
  "llm_model": "gpt-4o",
  "system_prompt": "你是福祉業務小秘...",
  "visibility": "public",
  "status": "active"
}
```

### 3.3 Business Users 集合（業務員資料，可為既有 users 集合擴充或獨立集合）

Channel 的 `business_user_key` 指向的使用者資料，用於 persona 客製化：

```json
{
  "_key": "sales_001",
  "name": "王大明",
  "role": "業務員",
  "region": "北區",
  "team": "業務一部",
  "line_channel_key": "ch_abc123",
  "persona_config": {
    "greeting_style": "正式",
    "expertise": ["電動輪椅", "爬梯機", "居家無障礙"],
    "customer_segment": "醫療器材行",
    "signature": "業務員 王大明\n台灣福祉股份有限公司"
  },
  "created_at": "ISO datetime",
  "updated_at": "ISO datetime"
}
```

## 4. Session 設計

### 4.1 Session ID 格式

```
line:{channel_key}:{user_id}
line:group:{channel_key}:{group_id}:{user_id}
line:room:{channel_key}:{room_id}:{user_id}
```

### 4.2 從 Session ID 解析業務員身份

福祉業務小秘收到請求後：

```python
# 偽碼
def resolve_identity(session_id: str) -> dict:
    # "line:ch_abc123:Uxxxxxxxx"
    parts = session_id.split(":")
    channel_key = parts[1]
    line_user_id = parts[2]

    # 查 channel 取得 business_user_key
    channel = db.get_channel(channel_key)
    
    # 查業務員資料
    business_user = db.get_user(channel["business_user_key"])
    
    return {
        "channel_key": channel_key,
        "line_user_id": line_user_id,
        "business_user": business_user,
        "role": channel.get("role"),
        "persona_config": business_user.get("persona_config", {})
    }
```

### 4.3 對話隔離

- 不同 channel 的 session 完全隔離（channel_key 不同）
- 同 channel 不同 LINE user 的 session 也隔離（user_id 不同）
- 同 channel 同 user 的對話上下文連續（既有 ConversationStorage 機制）

## 5. 福祉業務小秘的 Persona 差異化邏輯

### 5.1 差異化維度

| 維度 | 資料來源 | 用途 |
|------|---------|------|
| 業務員姓名 | business_user.name | 自稱/署名 |
| 區域 | business_user.region | 區域相關資訊優先 |
| 專業領域 | persona_config.expertise | 傾向回答擅長領域 |
| 客戶類型 | persona_config.customer_segment | 產品推薦策略 |
| 問候風格 | persona_config.greeting_style | 正式/親切 |
| 簽名檔 | persona_config.signature | 訊息結尾署名 |

### 5.2 System Prompt 組合策略

```python
SYSTEM_PROMPT_TEMPLATE = """
你是 {business_user.name} 的個人業務助理，由福祉業務小秘提供技術支援。

【業務員身份】
- 姓名：{business_user.name}
- 角色：{role}
- 負責區域：{region}
- 專業領域：{expertise}

【回應風格】
- 語氣：{greeting_style}
- 署名：每則訊息末尾附上簽名檔

【權限】
- 客戶查詢：可查詢 {customer_segment} 相關客戶資料
- 產品建議：以 {expertise} 為優先
- 機密資料：金額、成本、合約細節等不可透露給外部客戶

【核心能力】
（以下為福祉業務小秘標準行為...）
"""
```

## 6. API 端點

### 6.1 LINE Channel 管理（既有，需擴充）

| 方法 | 路徑 | 說明 |
|:----:|------|------|
| GET | /api/v1/platforms/line/official-accounts | 官方帳號列表 |
| POST | /api/v1/platforms/line/official-accounts | 新增官方帳號 |
| GET | /api/v1/platforms/line/channels | Channel 列表 |
| POST | /api/v1/platforms/line/channels | 新增 channel（需傳入 channel_secret/access_token） |
| PUT | /api/v1/platforms/line/channels/{key} | 更新 channel（含 linked_agent_key） |
| POST | /api/v1/platforms/line/channels/{key}/test | 測試連線 |
| POST | /api/v1/platforms/line/channels/{key}/publish | 發布（設定 webhook URL） |

### 6.2 Channels 統一管理（既有，建議優先使用）

| 方法 | 路徑 | 說明 |
|:----:|------|------|
| GET | /api/v1/channels | 全部 channel（支援 platform=line 過濾） |
| POST | /api/v1/channels | 新增 channel（含 platform/business_user_key/config） |
| PUT | /api/v1/channels/{key} | 更新 channel |
| DELETE | /api/v1/channels/{key} | 刪除 channel |

### 6.3 業務員管理（新增）

| 方法 | 路徑 | 說明 |
|:----:|------|------|
| GET | /api/v1/business-users | 業務員列表（含 LINE channel 綁定狀態） |
| POST | /api/v1/business-users | 新增業務員資料（含 persona_config） |
| PUT | /api/v1/business-users/{key} | 更新 persona_config |
| GET | /api/v1/business-users/{key}/channels | 查詢該業務員綁定的 channel |

### 6.4 Webhook（既有）

| 方法 | 路徑 | 說明 |
|:----:|------|------|
| POST | /api/v1/webhook/line/{channel_key} | LINE 事件接收（Rust proxy → unified_agents） |

## 7. 福祉業務小秘 BPA Agent 結構

```
ai-services/bpa/welfare_secretary/
├── __init__.py
├── main.py                 # FastAPI 入口，prefix="/welfare-secretary"
├── config.py               # 環境變數、system prompt 模板
├── router.py               # 核心：接收 chat 請求 → resolve_identity → LLM 回覆
├── skills/
│   ├── __init__.py
│   ├── customer_greeting.py    # 客戶問候
│   └── business_notification.py # 通知業務員
└── graph/
    ├── state.py
    └── builder.py
```

### 7.1 Router 核心流程

```python
@router.post("/chat")
async def chat(request: ChatRequest):
    # 1. 從 session_id 解析業務員身份
    identity = resolve_identity(request.session_id)

    # 2. 載入 conversation history
    history = conversation_storage.get_session(request.session_id)

    # 3. 組合 system prompt（動態 + 固定）
    system_prompt = build_persona_prompt(identity)

    # 4. Intent classification
    intent = classify_intent(request.message, identity)

    # 5. 執行對應 handler
    if intent == "customer_query":
        result = await handle_customer_query(request.message, identity)
    elif intent == "product_inquiry":
        result = await handle_product_inquiry(request.message, identity)
    elif intent == "business_operation":
        result = await handle_business_operation(request.message, identity)
    else:
        result = await call_llm(system_prompt, history, request.message)

    # 6. 回覆
    return {"response": result}
```

## 8. 實作步驟

### ✅ Phase 1：建立福祉業務小秘 BPA Agent（已完成）

| 步驟 | 狀態 | 說明 |
|:----:|:----:|------|
| 1 | ✅ | 建立 `ai-services/bpa/welfare_secretary/` 目錄（含 7 個模組） |
| 2 | ✅ | 實作 `router.py`：resolve_identity + 動態 persona + LLM 呼叫 |
| 3 | ✅ | 在 `unified_agents/main.py` 註冊（mount `/welfare-secretary`） |
| 4 | ✅ | DB seed：建立 `welfare_secretary` agent 紀錄 + 新集合 |
| 5 | ✅ | LSP 零錯誤通過 |

### 🟡 Phase 2：建立或遷移 LINE Channels（待串接，基礎建設已完成）

| 步驟 | 狀態 | 說明 |
|:----:|:----:|------|
| 1 | ⏳ | 為第一位業務員申請 LINE OA（LINE Developers Console）→ 待執行 |
| 2 | ⏳ | 取得 channel_secret / access_token → 待執行 |
| 3 | ✅ | 後台頻道建立 UI（含 `linked_agent_key`、`business_user_key` 欄位）→ 已可使用 |
| 4 | ⏳ | 設定 webhook URL → 待執行 |
| 5 | ⏳ | 端到端測試 → 待執行 |

### ✅ Phase 3：建立業務員資料（已完成）

| 步驟 | 狀態 | 說明 |
|:----:|:----:|------|
| 1 | ✅ | Rust API：`business_users` CRUD（`api/src/api/business_users.rs`） |
| 2 | ✅ | 前端後台：ChannelAdminPage 新增「業務員管理」分頁（含 persona 編輯） |
| 3 | ✅ | 福祉業務小秘 `resolve_identity()` 可從 channel_key 反查 business_user |
| 4 | ✅ | 動態 persona system prompt 組合（`build_persona_prompt()`） |

### Phase 4：擴充其他業務員（待 Phase 2 啟動後執行）

| 步驟 | 狀態 | 說明 |
|:----:|:----:|------|
| 1 | ⏳ | 重複 Phase 2 為其他業務員建立 LINE OA |
| 2 | ⏳ | 後台建立對應業務員資料與 channel |

## 9. 管理員後台功能

既有的 ChannelAdminPage 需擴充以下功能：

- **Channel 列表**：顯示所有 LINE channel，包含對應業務員姓名、狀態
- **Channel 綁定**：建立 channel 時可選擇對應的業務員
- **業務員管理**：CRUD 業務員資料（含 persona_config）
- **一覽狀態**：顯示各業務員 LINE OA 連線狀態、最近活動時間

## 10. 限制與注意事項

| 項目 | 說明 |
|:----:|------|
| **LINE OA 數量** | 每位業務員需要一個 LINE Official Account。LINE 允許一個開發者帳號下建立多個 OA，無數量上限。但每個 OA 需獨立完成審核與設定。 |
| **Webhook 唯一性** | 每個 LINE OA 只能設定一個 webhook URL。本架構中每個 OA 的 webhook URL 因 `channel_key` 不同而不同，符合限制。 |
| **LINE 免費方案限制** | 免費方案：好友上限 500 人、群發訊息 500 則/月。若業務員需要大規模推播，需升級。 |
| **Webhook 回應時限** | LINE 要求 webhook 5 秒內回應 HTTP 200。目前 webhook處理為同步，若 LLM 回應超過 5 秒 LINE 會 retry。解法：webhook.py 先回覆 HTTP 200，非同步處理後再 push_message。 |
| **簽名驗證** | 每個 channel 有獨立的 channel_secret，webhook.py 驗證 x-line-signature 時需用對應 secret。既有實作已支援。 |
| **Token 管理** | 每個 channel 的 access_token 有有效期（透過 LINE 的 channel access token）。需實作 token 自動更新機制。 |

## 11. 既有程式參考

| 檔案 | 用途 |
|------|------|
| `ai-services/unified_agents/platforms/line/webhook.py` | LINE webhook 接收與路由（channel 查詢、session 建立、agent 調用） |
| `ai-services/unified_agents/platforms/line/services/db.py` | LINE channel 的 ArangoDB 操作 |
| `ai-services/unified_agents/platforms/line/services/line_api.py` | LINE Messaging API 封裝（reply_message、push_message） |
| `ai-services/bpa/order_secretary/router.py` | BPA Agent 參考實作（intent 分類、LLM 調用、conversation 管理） |
| `api/src/api/platforms/line.rs` | Rust API Gateway LINE proxy |
| `api/src/api/channels.rs` | Channels 統一管理 API |
| `src/pages/eea-crm/ChannelAdminPage.tsx` | 管理員後台 channel 管理頁面 |
| `ai-services/shared/conversation/storage.py` | 平台無關的對話儲存層 |
| `ai-services/skills/timeline_engine/skill.py` | Timeline 查詢 skill |
| `ai-services/skills/push_engine/skill.py` | LINE 推播訊技能 |

---

## 修改歷程

| 日期 | 版本 | 作者 | 變更 |
|------|:----:|------|------|
| 2026-06-19 | 1.0.0 | Sisyphus | 初版規格 |
| 2026-06-19 | 1.1.0 | Sisyphus | 更新實作狀態：Phase 1 ✅ Phase 2 🟡 基建完 Phase 3 ✅ |
