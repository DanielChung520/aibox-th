---
lastUpdate: 2026-04-28 21:22:11
author: AI Agent
version: 2.0.0
---

# Ragic 小幫手 — 規格書 v2.0

> 需求編號：`A01-2617-001`

## 概述

Ragic 小幫手是 ABC Desktop 智能體市集中第一個正式部署的 AI Agent。透過 **Agent 記錄 → Rust API 動態路由 → Python 端點** 的架構，讓使用者可在 LINE、Web 前端與 Ragic 小幫手進行多輪對話。整合 KA HybridRAG 知識庫、多媒體解讀器、多 Provider LLM（Ollama / DeepSeek / OpenAI-compatible）。

## 部署架構

```
LINE 使用者                    Web 前端
   │ 圖片/文字                    │ 文字
   ▼                              ▼
LINE Webhook                TaskSessionChat (agent mode)
   │                              │
   ▼                              ▼
Rust API Gateway (port 6500)
   │ POST /api/v1/webhook/line/{channel_key}     │ POST /api/v1/agents/{key}/chat
   ▼ 查 channel.linked_agent_key                 ▼ 查 agent.endpoint_url
   │                                              │
   ▼                                              ▼
unified_agents:8011                         動態路由到
   │ /webhook/line/{channel_key}              http://localhost:8011/ragic-agent/chat
   │ 圖片 → /mcp/multimedia-analyzer
   │ 文字 → POST endpoint_url
   ▼
POST /ragic-agent/chat
   │ 讀取 agent_key → 查 Agent 記錄
   │ llm_model → 查 ModelProvider → base_url + api_key
   │ 多輪歷史 ← bot_chat_sessions (shared.conversation)
   │
   ├── 時間查詢 → Python datetime.now() 直回
   ├── ragic_question → KA HybridRAG → LLM
   ├── complaint       → LLM 溫暖回應
   └── general_chat    → LLM 一般回應
```

## Agent 記錄（DB）

| 欄位 | 值 | 說明 |
|------|-----|------|
| `_key` | `e7af2ad8-b6fe-43cb-be03-c4c722932346` | Agent 唯一識別 |
| `name` | Ragic 小幫手 | |
| `agent_type` | `bpa` | 出現在市集「BPA代理」分類 |
| `endpoint_url` | `http://localhost:8011/ragic-agent/chat` | 動態路由目標 |
| `llm_model` | `deepseek-v4-flash` | 從 ModelProvider 查 base_url |
| `source` | `local` | 本機內部 agent |
| `tools` | `[line_bot_key, multimedia-analyzer_key]` | 工具權限 |
| `visibility` | `public` | |

## API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/ragic-agent/chat` | 主要聊天介面 |

### Request

```json
{
  "session_id": "string",        // 多輪對話 session ID
  "message": "string",            // 使用者訊息
  "user_id": "string",            // 使用者 ID（預設 anonymous）
  "agent_key": "string | null"   // Agent 識別鍵（可選，用於讀取 Agent 配置）
}
```

### Response

```json
{
  "session_id": "string",
  "reply": "string",              // AI 回應
  "sources": ["string"]           // 知識庫來源
}
```

## Rust API 通用代理

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/api/v1/agents/{key}/chat` | 讀取 Agent 的 `endpoint_url`，動態 POST 代理 |

## LINE 整合

### Webhook 路由

```
LINE → https://eeaapi.ent4i.com/api/v1/webhook/line/{channel_key}
    → tunnel → Rust:6500
    → unified_agents:8011/webhook/line/{channel_key}
    → 讀取 channel.linked_agent_key
    → 查 Agent.endpoint_url
    → POST 到該 endpoint
```

### Channel 設定

- `linked_agent_key`：在 ChannelDetailPanel 選擇有 LINE Bot 工具權限的 Agent
- 測試連線：同時驗證 LINE token + Agent endpoint

### 群組支援

- 群組聊天：監聽所有訊息，僅在 @提及 時回覆
- 個別聊天：每則訊息都回覆
- session_id 格式：`line:group:{ch_key}:{group_id}:{user_id}` / `line:{ch_key}:{user_id}`
- 群名：透過 LINE API `get_group_summary()` 查詢並存入 metadata
- 使用者名稱：透過 LINE API `get_user_profile()` 查詢並存入 metadata
- 歷史記錄：ChatHistoryDrawer 支援多群/多用戶分頁

### 圖片處理

```
LINE 圖片
  → webhook 下載（api-data.line.me）
  → POST /mcp/multimedia-analyzer/analyze → qwen3-vl 分析
  → 圖片描述存入 bot_chat_sessions (role: assistant，含系統提示格式)
  → 個別聊天：回覆「收到 image，已解析。需要我說明內容嗎？」
  → 群組聊天：不回覆
  → 使用者後續提問 → Agent 從 bot_chat_sessions 載入上下文 → 基於圖片描述回答
```

## 意圖分類

使用 rule-based 關鍵字匹配，無需額外 LLM 調用：

| 意圖 | 觸發關鍵字 | 處理流程 |
|------|-----------|----------|
| `ragic_question` | Ragic, 表單, 欄位, 新增, 修改, 刪除, 查詢, 匯出, 報表, 權限, 篩選 | KA HybridRAG → LLM |
| `complaint` | 抱怨, 客訴, 不滿 | LLM 溫暖回應 |
| `time_query` | 時間, 幾點, 日期, 今天幾號, 星期幾, 現在 | Python `datetime.now()` 直回 |
| `general_chat` | 其他 | LLM 一般回應 |

## 內建能力

| 能力 | 實作 | 說明 |
|------|------|------|
| **時間查詢** | `datetime.now()` 直回 | 台灣時間 UTC+8，不走 LLM |
| **多輪上下文** | `shared.conversation.QueryEngine` | 從 `bot_chat_sessions` 讀取持久化歷史 |
| **圖片理解** | 多媒體解讀器 → 圖片分析注入上下文 | Agent 可基於圖片描述回答後續問題 |

## 知識庫整合

- **端點**：`unified_agents:8011/ka/hybrid/search`
- **過濾**：`root_id = kb_1776656567810`（Ragic操作說明書）
- **機制**：KA HybridRAG（ArangoDB 全文 + Qdrant 向量 + 知識圖譜）
- **取樣**：Top 2 筆結果，每筆截取 150 字元注入 prompt

## LLM 配置

| 參數 | 值 | 說明 |
|------|-----|------|
| 模型來源 | Agent 記錄 `llm_model` | 動態讀取，不再硬編碼 |
| 當前模型 | `deepseek-v4-flash` | 透過 DeepSeek API |
| API 格式 | Ollama `/api/chat` 或 OpenAI `/chat/completions` | 自動辨識 |
| API Key | 從 ModelProvider 記錄讀取 | |
| Timeout | 180 秒 | |
| System Prompt | 從 Agent 記錄讀取，fallback 為 Ragic 操作助手 | |

## 多輪對話

- 以 `session_id` 區分不同對話
- **雙層歷史**：記憶體 `_conversations` + `bot_chat_sessions` 持久化
- 保留最近 10 輪對話歷史（20 條訊息）
- 優先使用 DB 持久化歷史（跨重啟保留）

## 檔案結構

```
ai-services/bpa/ragic_agent/
├── __init__.py          # 套件入口
├── main.py              # FastAPI 應用（獨立 port 8012，備用）
├── router.py            # ★ API Router → unified_agents:8011
│                        #    - ArangoDB 查詢（agent 記錄、model_providers）
│                        #    - 多 Provider LLM 呼叫（Ollama / OpenAI-compatible）
│                        #    - 多輪上下文載入（shared.conversation）
│                        #    - 內建時間查詢
├── config.py            # 環境變數 + Fallback System Prompt（備用）
├── agent.py             # 核心邏輯（備用，sync 版本）
├── graph/               # LangGraph 節點（預留架構，未啟用）
│   ├── state.py
│   ├── builder.py
│   └── nodes/
│       ├── intent_classifier.py
│       └── ragic_handler.py
```

## 相關服務

| 服務 | 用途 | 端點 |
|------|------|------|
| **多媒體解讀器** | 圖片/影片/音訊分析 | `/mcp/multimedia-analyzer/analyze` |
| **Shared Conversation** | 持久化對話歷史 | `bot_chat_sessions` (ArangoDB) |
| **ModelProvider** | LLM base_url + api_key | `model_providers` 集合 |

## 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama 服務位址（fallback） |
| `KNOWLEDGE_AGENT_URL` | `http://127.0.0.1:8011/ka` | KA HybridRAG 位址 |
| `RAGIC_AGENT_MODEL` | `qwen3-next:latest` | 使用模型（fallback，Agent 記錄優先） |
| `RAGIC_KB_ROOT_ID` | `kb_1776656567810` | 知識庫根目錄 ID |
| `ARANGO_URL` | `http://localhost:8529` | ArangoDB 位址 |
| `ARANGO_DATABASE` | `abc_desktop` | 資料庫名稱 |

## 已知限制

- 不支援串流回應（`stream: false`）
- 無 WebSocket / SSE
- 抱怨僅標記，未落地 ArangoDB（預留 `ragic_complaints` 集合）
- 圖片上下文僅在新圖片後生效（需重新發送）

## 開發歷程

| 日期 | 版本 | 變更 |
|------|------|------|
| 2026-04-28 | 2.0.0 | Agent 市集註冊、Rust 動態代理、LINE Webhook 整合、多 Provider LLM、多輪上下文持久化、多媒體圖片處理、內建時間、LINE 群組多群管理 |
| 2026-04-27 | 1.0.0 | 初始版本：意圖分類、KA HybridRAG、Ollama、多輪對話 |

## 相關文件

- [系統開發區 Index](../系統開發/00-index.md)
- [需求提交與審查](../系統開發/01-需求提交與審查.md)
- [需求看板](../系統開發/02-需求看板.md)
- [規格產出](../系統開發/03-規格產出.md)
- [AI Agent 開發指引](../../agent-tool-dev-guide.md)
- [智能體與工具市集](../智能體與工具市集/)
