---
lastUpdate: 2026-05-08 23:55:00
author: Daniel Chung
version: 1.0.0
---

# 外部 MCP Tool 設定規範（tools-mcp Settings）

## 概述

外部 MCP Tool 是透過 **Model Context Protocol (MCP)** 連接的第三方 AI Agent。  
與本機 Agent 不同，外部 MCP Tool 的執行邏輯不在本系統內，而是由外部服務提供。

## 架構

```
用戶 → BrowseAgent → chat → Rust API Gateway (6500)
  → 判斷 source=mcp
  → 轉發到 MCP Gateway (8004)
    → tools/list 發現外部服務的工具
    → LLM 決定呼叫哪個工具
    → tools/call 執行
    → LLM 總結結果回覆用戶
```

## Agent 設定欄位

所有設定儲存在 ArangoDB `agents` 集合，透過前端 Agent 編輯表單設定。

### 基本設定

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `name` | string | ✅ | Agent 顯示名稱 |
| `description` | string | ❌ | 功能描述，顯示在卡片上 |
| `icon` | string | ❌ | 圖示名稱 (Ant Design Icon) |
| `status` | string | ❌ | online / maintenance / deprecated |
| `group_key` | string | ❌ | 分組，預設 productivity |
| `visibility` | string | ❌ | public / private / role |

### 來源設定

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `source` | string | ✅ | 必須為 `mcp` |
| `endpoint_url` | string | ✅ | MCP Server 連線位址 (e.g. `https://mcp.example.com/mcp`) |
| `mcp_url` | string | ❌ | MCP 端點，優先於 endpoint_url |
| `mcp_transport` | string | ❌ | 傳輸方式: `streamable-http` / `stdio` / `sse` |
| `mcp_command` | string | ❌ | stdio 模式的啟動指令 (e.g. npx) |
| `mcp_args` | string[] | ❌ | stdio 模式的啟動參數 |
| `api_key` | string | ❌ | API Key / Bearer Token |
| `auth_type` | string | ❌ | none / bearer / basic / oauth2 |

### LLM 設定

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `llm_model` | string | ✅ | Model ID，用於工具選擇與回覆生成 (e.g. `deepseek:deepseek-v4-flash`) |
| `system_prompt` | string | ❌ | System Prompt，定義 Agent 的角色行為 |
| `temperature` | float | ❌ | 預設 0.7 |
| `max_tokens` | int | ❌ | 預設 2000 |

## MCP Gateway 行為

MCP Gateway (`ai-services/mcp_tools/mcp_gateway.py`) 負責橋接聊天訊息與 MCP 協議：

### 流程

1. 接收 Rust API 轉發的聊天請求（含 agent_key）
2. 透過 Rust API 讀取 Agent 配置（含 MCP URL、API Key、LLM 模型）
3. 呼叫 MCP `tools/list` 發現外部服務提供的工具
4. 將工具描述餵給 LLM，讓 LLM 決定呼叫哪個工具與參數
5. 呼叫 MCP `tools/call` 執行
6. 將執行結果交給 LLM 生成自然語言回覆
7. 回傳結果

### MCP 協議支援

| 傳輸方式 | 支援 | 說明 |
|---------|------|------|
| JSON-RPC over HTTP | ✅ | 標準 MCP，無 session 管理（Linear、GitHub MCP 等） |
| Streamable HTTP | ⚠️ 部分 | 需要 SSE session 管理，部分 server 有相容問題 |
| SSE | ⚠️ | 需要持久連線，Gateway 目前不支援 |
| stdio | ❌ | 需 process 生命週期管理，未來可實作 |

### 工具發現機制

Gateway **不硬編碼任何工具定義**。每次對話時透過 `tools/list` 動態發現外部服務提供的工具清單，再交由 LLM 判斷使用哪個工具。

## 系統參數（system_params）

全域性的 MCP Gateway 設定存放在 ArangoDB `system_params` 集合：

| param_key | 型態 | 預設值 | 說明 |
|-----------|------|--------|------|
| `mcp_gateway.enabled` | bool | `true` | 是否啟用 MCP Gateway 功能 |
| `mcp_gateway.default_llm_model` | string | - | 當 Agent 未指定 LLM 時的預設模型 |
| `mcp_gateway.mcp_call_timeout` | int | `30` | 呼叫外部 MCP Server 的超時秒數 |
| `mcp_gateway.llm_call_timeout` | int | `60` | LLM 呼叫的超時秒數 |

## 與本機 Agent 的差異

| 面向 | 本機 Agent (source=local) | 外部 MCP Tool (source=mcp) |
|------|--------------------------|----------------------------|
| 開發規範 | `agent-tool-dev-guide.md` | `Agents-mcp-Settings.md` |
| 執行位置 | Python FastAPI 服務（本機） | 外部 MCP Server（任何位置） |
| 工具定義 | Python 程式碼 | MCP tools/list 動態發現 |
| 執行方式 | LLM + Python 邏輯 | LLM + tools/call |
| 狀態管理 | 服務自帶 | MCP Server 自理 |
| 路由註冊 | unified_agents / Rust | MCP Gateway（8004） |
| 認證方式 | 內部 Token | API Key / Bearer / OAuth2 |

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-05-08 | 1.0.0 | Daniel Chung | 初始版本 |
