---
lastUpdate: 2026-05-09 04:30:00
author: Daniel Chung
version: 2.0.0
---

> ⚠️ **絕對遵守**：所有破壞性操作（刪除、重建、覆寫、還原）一律參照 `.sisyphus/safety-rules.md` 的安全規範，**先輸出指令，經確認後由使用者手動執行**。AI 不得自行執行。

# AGENTS.md — ABC Desktop AI Agent 規範

## 開發觸發指令 #dev

當使用者輸入 `#dev {需求編號}` 時，AI Coder 必須參照 `agent-tool-dev-guide.md` 進行開發工作。

詳見：[agent-tool-dev-guide.md](./agent-tool-dev-guide.md)

> **提醒**：`#dev` 僅用於**本機 Agent**（`source=local`）的開發。
> 外部 MCP Tool 的整合設定請參照 `tools-mcp-Settings.md`。

---

## Project Overview

- **Name**: ABC Desktop (abc-desktop)
- **Type**: Tauri + React + TypeScript desktop application
- **UI Framework**: Ant Design 6.x
- **State Management**: Custom AuthStore pattern (see `src/stores/auth.ts`)
- **HTTP Client**: Axios
- **Python Services**: FastAPI

---

## 開發原則

### 0. 產品思維（Product Mindset）

這是**產品專案開發**，不是臨時方案。所有程式碼與設計必須符合產品標準：

- **標準化** — 遵循專案既有慣例與風格，不為求快走捷徑
- **正規化** — 架構設計要完整，不偷工減料
- **參數化** — 配置一律放資料庫或環境變數，嚴禁 hardcode
- **產品觀** — 開發環境的程式碼品質 = 上線標準，沒有「先求有再求好」

### 1. Product Development Principles

- **避免硬編碼**：所有配置性內容應存放於資料庫或環境變數
- **適當解耦**：模組間保持低耦合，透過介面/接口通訊
- **標準化**：遵循現有程式碼風格與專案慣例
- **可維護性**：程式碼應具有可讀性與可擴展性

### 1.1 Data Agent / Intent 邊界原則（憲法級規範）

`intent_catalog` 僅負責通用/操作性意圖，`da_intents` 僅負責資料語意/資料工程意圖。嚴禁混用。

### 1.2 Agent 選擇規範（視覺/樣式工作）

所有 UI、樣式、CSS、前端視覺相關的工作，必須委託 `visual-engineering` agent 處理。

### 1.4 系統參數管理原則

所有系統參數存放於 `system_params` 集合，嚴禁 hardcode。

### 1.5 請求轉發架構（憲法級規範）

所有前端請求必須經過 **Rust API Gateway**（port 6500），禁止前端直接呼叫 Python 服務。

```
前端 (Vite proxy:1420) → Rust API Gateway (6500) → Python 後端服務
```

- 前端程式碼一律使用相對路徑（如 `/order-secretary/preorders`），禁止 hardcode 任何 Python 服務的 IP/Port
- Vite proxy 僅轉發到 `http://localhost:6500`，不直接 proxy 到 Python 服務
- 新增後端路由時，必須在 `api/src/api/` 新增 proxy handler，並在 `api/src/api/mod.rs` 註冊
- 違反此原則的 PR 不予合併（參見 `vite.config.ts` 與 `api/src/api/order_secretary.rs` 範例）

### 1.7 LLM Provider 解析標準

所有 LLM 呼叫統一透過 `shared/llm_resolver.py` 解析，嚴禁各服務自行實作。

### 2. Code & File Header Standards

所有程式碼檔案必須包含表頭註解，格式如下：

```typescript
/**
 * @file        檔案說明概要
 * @description 詳細說明（可選）
 * @lastUpdate  YYYY-MM-DD HH:MM:SS
 * @author      更新者名稱
 * @version     1.0.0
 */
```

> 時間戳使用 `date "+%Y-%m-%d %H:%M:%S"` 取得

### 3. Duplicate Prevention Check

新增任何程式碼或檔案前，必須：
1. 查看 `README.md` 與 `AGENTS.md` 確認現有結構
2. 搜尋現有功能
3. 確認複用可能性

### 3.5 Module Size Guidelines

| 語言 | 單檔上限 | 建議上限 |
|------|---------|---------|
| Rust | 500 行 | 300 行 |
| TypeScript | 400 行 | 250 行 |
| Python | 400 行 | 250 行 |

### 1.6 Temporary Files Management

所有臨時檔案統一放置於 `.tmp/` 目錄，禁止散落在專案根目錄。

### 1.8 Safe Operation Rules

> ⚠️ **基礎設施操作一律須經確認**：Cloudflare、DNS、資料庫、sudo、生產服務等操作，AI 僅能輸出指令，由使用者手動執行。

破壞性操作必須事先取得同意（詳見 `.sisyphus/safety-rules.md`）：

| 操作 | 說明 |
|------|------|
| `git checkout` / revert | 會丟失未 commit 的工作進度 |
| 刪除檔案 | 可能造成功能損失 |
| 大規模重寫 | 風險高 |
| `git reset` / `git stash drop` | 不可逆 |
| 修改資料庫資料 | 需先查詢確認 |
| ArangoDB 文件更新 | 一律用 PATCH，禁用 PUT（詳見 safety-rules.md） |

---

## 快速啟動

```bash
# 前端開發
npm run dev

# Rust API
cd api && cargo run --release

# AI Services（使用 .venv）
cd ai-services && source .venv/bin/activate
uvicorn mcp_tools.main:app --port 8004 --reload
uvicorn aitask.main:app --port 8001 --reload

# 狀態檢查
./start.sh status
```

---

## 文件索引

| 文件 | 內容 |
|------|------|
| `.sisyphus/safety-rules.md` | **安全規範** — 破壞性操作 SOP |
| `agent-tool-dev-guide.md` | 本機 Agent 開發（`#dev` 流程） |
| `tools-mcp-Settings.md` | 外部 MCP Tool 設定 |
| `coding-standards.md` | 編碼規範（命名、import、元件結構、錯誤處理） |
| `DESIGN.md` | UI/UX 設計規範、視覺風格、元件使用原則 |
| `project-architecture.md` | 服務架構、Port 表、執行環境 |
| `agent-development.md` | Agent 建立指南、BPA 開發 |
| `.docs/API Specification.md` | API 端點定義 |
| `README.md` | 完整安裝與啟動說明 |

---

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-05-21 | 2.1.0 | Daniel Chung | 新增 1.5 請求轉發架構原則（憲法級） |
| 2026-05-09 | 2.0.0 | Daniel Chung | 重構為框架性文件，拆出編碼規範/架構/Agent 指南為獨立文件 |
| 2026-04-30 | 1.13.0 | Daniel Chung | 新增 functionsIndex.md 複用函式索引 |
| 2026-04-21 | 1.11.0 | Daniel Chung | 新增 Agent 建立指南 |
| 2026-04-19 | 1.9.0 | Daniel Chung | 新增 Service Architecture 原則 |
| 2026-03-27 | 1.5.0 | Daniel Chung | Temporary Files Management |
| 2026-03-25 | 1.4.1 | Daniel Chung | 資料庫修改確認規則 |
| 2026-03-19 | 1.4.0 | Daniel Chung | Safe Operation Rules |
| 2026-03-18 | 1.3.0 | Daniel Chung | Tauri Desktop 規範 |
| 2026-03-18 | 1.2.0 | Daniel Chung | API 開發規範 |
| 2026-03-18 | 1.1.0 | Daniel Chung | Python mypy/ruff 規範、Module Size |
| 2026-03-17 | 1.0.0 | Daniel Chung | 初始版本 |
