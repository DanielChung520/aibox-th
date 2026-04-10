---
lastUpdate: 2026-04-10 21:15:31
author: Daniel Chung
version: 1.1.0
status: 正式版
---

# 任務聊天室功能規格書 — 索引與閱讀指南

> **版本**: 1.1.0  
> **狀態**: 正式版  
> **範疇**: 前端 + Top Orchestrator + LangGraph + BPA 整合  
> **目標讀者**: AI Coder Agent（用於實作開發）

---

## TL;DR

任務聊天室是 AIBox 的核心對話介面，提供兩條對話路徑：

- **Path A（開放聊天）**：使用者直接輸入自然語言，經由 LangGraph 驅動的 Top Orchestrator 進行意圖分類、指代消解、工具調用，多輪對話記憶管理，並透過 SSE 串流回應。
- **Path B（BPA 代理工作流）**：使用者從「瀏覽代理」頁面選擇企業流程代理（BPA Agent），前端 ChatOrchestrator 協調分析後，透過 Top Orchestrator 發送 TASK_HANDOVER 給 BPA，執行結構化企業流程。
- **附屬功能：檔案上傳 + 知識向量化**：使用者在聊天中上傳檔案，系統自動呼叫知識庫向量及圖譜產生代碼，透過 Celery Queue Work 异步處理，資料落地至 SeaWeedFS（原始檔）、ArangoDB（圖譜資料）、Qdrant（向量檢索），綁定至當前任務會話（task session）。

**技術架構決策**：

| 決策項目 | 選擇 |
|---------|------|
| 串流技術 | SSE 為主 + WebSocket 為輔（僅 BPA 多輪互動時啟用 WS） |
| LangGraph 整合 | 升級 aitask (port 8001) 為 Top Orchestrator |
| 前端編排 | ChatOrchestrator 狀態機（模式：`open_chat` / `bpa_workflow` / `bpa_param_collection`） |
| 對話持久化 | ArangoDB（自訂 LangGraph Checkpointer 適配器） |
| 協議版本 | Handoff Protocol v2.0（與現有 Top/BPA 規格一致） |
| **工作區隔離 (v1.1)** | 所有 API 透過 JWT `sub` claim 提取 `user_key`，按此過濾資料 |
| **模型選擇 (v1.1)** | 優先使用所選 provider 的第一個模型，而非系統預設 |
| **Multi-Provider (v1.1)** | aitask 支援 Ollama/MiniMax/OpenAI/Gemini/Anthropic，透過 `provider` + `provider_base_url` 參數動態路由 |

**v1.1 更新內容 (2026-04-10)**：
1. 新增 `user_key` 欄位用於多租戶隔離
2. 所有 API 端點增加 `user_key` 過濾
3. 修復模型選擇邏輯：優先使用所選 provider 的模型
4. Ragic 聊天使用獨立命名空間 store (`ragicChatStore`)
5. **Multi-Provider 支援**：aitask 支援 Ollama、MiniMax、OpenAI、Gemini、Anthropic 五種 AI Provider

**參考標準**：
- Agent Protocol（Task/Step/Artifact 模型）
- Model Context Protocol (MCP)（JSON-RPC 2.0 工具整合）
- LangGraph Supervisor Pattern（多代理編排）

---

## 文件地圖

本規格書拆分為 12 個檔案，每個檔案可獨立閱讀。AI Coder Agent 實作特定功能時，只需載入對應檔案 + 此索引。

| 編號 | 檔案 | 內容 | 適合閱讀時機 |
|------|------|------|------------|
| 00 | [00-index.md](./00-index.md)（本文件） | TL;DR、術語、文件地圖、閱讀指南 | **首先閱讀** |
| 01 | [01-architecture.md](./01-architecture.md) | 四層架構、元件職責、資料流、端口清單 | 理解整體架構時 |
| 02 | [02-protocol.md](./02-protocol.md) | 協議棧、16 種 SSE 事件、WebSocket 格式、Handoff v2.0、Headers | 實作通訊層時 |
| 03 | [03-path-a-open-chat.md](./03-path-a-open-chat.md) | TopState、LangGraph 圖結構、8 個節點、意圖分類、指代消解、記憶管理、SSE 串流 | 實作 Path A（開放聊天）時 |
| 04 | [04-path-b-bpa-workflow.md](./04-path-b-bpa-workflow.md) | BPA 觸發路徑、bpa_orchestrator 節點、TASK_HANDOVER、BPA 回應處理、多輪互動、控制操作 | 實作 Path B（BPA 工作流）時 |
| 05 | [05-frontend-orchestrator.md](./05-frontend-orchestrator.md) | FSM 三模式、狀態轉移規則、ChatMessage 介面、SSEManager、ChatStore、路由整合 | 實作前端狀態機時 |
| 06 | [06-data-model.md](./06-data-model.md) | 5 個 ArangoDB Collections、Schema、Checkpointer 適配器、記憶持久化、會話恢復 | 實作資料層時 |
| 07 | [07-mcp-tools.md](./07-mcp-tools.md) | ToolDefinition、ToolRegistry、4 種 Executor、LangGraph tool node、權限控制 | 實作工具整合時 |
| 08 | [08-api-endpoints.md](./08-api-endpoints.md) | 12 個新增 + 4 個修改端點、Request/Response 格式、前端 chatApi TypeScript | 實作 API 層時 |
| 09 | [09-error-security.md](./09-error-security.md) | 14 個錯誤碼、錯誤處理矩陣、JWT 認證鏈、速率限制、追蹤、Token 追蹤 | 實作錯誤處理與安全時 |
| 10 | [10-implementation-phases.md](./10-implementation-phases.md) | 7 個實施階段、依賴圖、詳細任務列表、~97hr 預估、風險 | 制定工作計劃時 |
| 11 | [11-appendix.md](./11-appendix.md) | Path A/B SSE 完整範例、配置參數表、現有檔案修改清單、術語對照 | 參考實作範例時 |
| 12 | [12-file-upload.md](./12-file-upload.md) | 檔案上傳流程、向量化/圖譜處理、Queue Work 架構、儲存目標（SeaWeedFS/ArangoDB/Qdrant） | 實作檔案上傳時 |

---

## 閱讀順序建議

### 新手 Agent（首次接觸此專案）

1. **00-index.md**（本文件）→ 理解全局
2. **01-architecture.md** → 理解系統架構
3. **按實作階段**載入對應檔案（見 [10-implementation-phases.md](./10-implementation-phases.md)）

### 實作特定階段

| 實作階段 | 需載入的檔案 |
|---------|------------|
| Phase 1: 基礎建設 | 00 + 06 + 08 + 05 (骨架部分) |
| Phase 2: Path A 核心 | 00 + 01 + 03 + 02 + 05 |
| Phase 3: 工具整合 | 00 + 07 + 03 (tool_executor 節點) |
| Phase 4: 對話智能 | 00 + 03 (意圖分類/指代消解/記憶管理) |
| Phase 5: Path B BPA | 00 + 04 + 05 (BPA 模式) + 02 (Handoff v2.0) |
| Phase 6: 錯誤強化 | 00 + 09 |
| Phase 7: 會話管理 | 00 + 06 (會話恢復) + 08 (會話 API) |
| Phase 8: 檔案上傳與知識向量化 | 00 + 12 + 06 (會話綁定) |

---

## 術語定義

| 術語 | 定義 |
|------|------|
| **Top Orchestrator** | 頂層編排器（升級自 aitask:8001），負責意圖分類、路由、會話管理 |
| **BPA** | Business Process Automation，企業流程自動化代理 |
| **DA** | Data Agent，自然語言→SQL 查詢代理 (port 8003) |
| **KA** | Knowledge Agent，知識庫 RAG 代理 (port 8007) |
| **MCP** | Model Context Protocol，工具整合標準協議 |
| **ChatOrchestrator** | 前端狀態機，協調 Path A/B 的對話流程 |
| **Checkpointer** | LangGraph 狀態持久化適配器（ArangoDB 實作） |
| **SSOT** | Single Source of Truth，唯一真相來源 |
| **Handoff Protocol v2.0** | Top↔BPA 通訊協議（schema_version: "2.0"） |
| **SSE** | Server-Sent Events，伺服器推送事件串流 |
| **HITL** | Human-in-the-Loop，人機互動迴圈 |
| **FSM** | Finite State Machine，有限狀態機 |
| **Context ID** | SSE 連線標識，由後端分配 |

---

## 相關文件（外部）

| 文件 | 路徑 | 說明 |
|------|------|------|
| Top Orchestrator 規格 v2 | `.docs/Spec/後台/top-orchestrator-spec-v2.md` | Top 狀態模型、路由、Handoff v2.0 |
| BPA 物料管理規格 | `.docs/Spec/後台/BPA/material-management-bpa-spec.md` | BPA 協議、步驟模型、checkpoint |
| Data Agent 規格 v2 | `.docs/Spec/後台/DA/data-agent-spec-v2.md` | DA 端點、請求/回應格式 |
| 任務對話 UI 規格 | `.docs/Spec/前端頁面/AI 聊天室「任務對話」畫面規格書.md` | 前端畫面設計 |
| 瀏覽代理規格 | `.docs/Spec/前端頁面/瀏覽代理功能規格書.md` | Agent 瀏覽 UI |
| API Specification | `.docs/Spec/API Specification.md` | 全域 API 規範 |

---

## 端口速查表

| 服務 | 端口 | 角色 |
|------|------|------|
| API Gateway | 6500 | 閘道、SSE/WS 代理 |
| Top Orchestrator | 8001 | LangGraph 編排器（升級自 aitask） |
| Data Agent | 8003 | NL→SQL 查詢 |
| MCP Tools | 8004 | 工具執行 |
| BPA MM Agent | 8005 | 物料管理流程 |
| Knowledge Agent | 8007 | RAG 檢索 |
| ArangoDB | 8529 | 資料持久化 |
| Qdrant | 6333 | 向量檢索 |
| Ollama | 11434 | 本地 LLM |
| Frontend (dev) | 1420 | Vite dev server |
