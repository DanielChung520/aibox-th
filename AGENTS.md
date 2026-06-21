---
lastUpdate: 2026-06-17 12:00:00
author: Daniel Chung
version: 2.2.0
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

### 1.4 系統參數管理原則（憲法級規範）

所有系統參數存放於 `system_params` 集合，嚴禁 hardcode。

#### 新增規範

新增 `system_param` 前，必須先查詢所有現有 key：

```sql
FOR p IN system_params RETURN p._key
```

確認無重複或可複用後，才新增。違反此規範的 PR 不予合併。

#### 禁止行為

- 未經查詢直接新增 system_param
- 為相同用途重複建立不同 key 的參數
- 在程式碼中硬編寫 system_param 的 key 字串（應集中管理）

### 1.5 請求轉發架構（憲法級規範）

所有前端請求必須經過 **Rust API Gateway**（port 6500），禁止前端直接呼叫 Python 服務。

```
前端 (Vite proxy:1420) → Rust API Gateway (6500) → Python 後端服務
```

- 前端程式碼一律使用相對路徑（如 `/order-secretary/preorders`），禁止 hardcode 任何 Python 服務的 IP/Port
- Vite proxy 僅轉發到 `http://localhost:6500`，不直接 proxy 到 Python 服務
- 新增後端路由時，必須在 `api/src/api/` 新增 proxy handler，並在 `api/src/api/mod.rs` 註冊
- 違反此原則的 PR 不予合併（參見 `vite.config.ts` 與 `api/src/api/order_secretary.rs` 範例）

### 1.6 Cloudflare Tunnel（基礎設施層，專案不管理）

> ⚠️ 本機部署的服務透過 Cloudflare Tunnel 對外暴露，Tunnel 由 Cloudflare Dashboard 統一管理，非專案層級管轄範圍。

- **Domain 對應**（定義於 `~/.cloudflared/config.yml`，僅供參考，勿手動修改）：

  | Domain | 指向 |
  |--------|------|
  | `eea.ent4i.com` | `localhost:1420`（frontend：`serve dist/`） |
  | `eeaapi.ent4i.com` | `localhost:6500`（Rust API Gateway） |

- **前端請求流程**：
  ```
  瀏覽器 https://eea.ent4i.com
    → Cloudflare Tunnel
    → localhost:1420 (serve dist/)
    → JS 發起 API 請求至 https://eeaapi.ent4i.com/api/v1/...
    → Cloudflare Tunnel
    → localhost:6500 (Rust API Gateway)
  ```

- 所有靜態資源和 API 請求的 HTTPS  termination 由 Cloudflare 處理，本機無需配置憑證。
- Tunnel 的啟動/停止/重啟由 `checkTunnel.sh` 腳本輔助檢查，但**實際管理在 Cloudflare Zero Trust Dashboard**。
- 開發者不應手動操作 cloudflared process，tunnel 異常時請先確認 Cloudflare 端狀態。

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

### 1.8 Skills 統一管理原則（憲法級規範）

所有可複用的業務邏輯技能（Skills）必須集中於 `ai-services/skills/` 目錄，並遵循登記與呼叫規範。

#### 1.8.1 Skills 目錄結構

```
ai-services/skills/
├── skills.json               ← 技能登記與發現 registry（必要）
├── __init__.py               ← 套件匯出
├── <skill_name>/             ← 每個技能一個子目錄
│   ├── skill.py              ← 主要實作（必要，統一介面）
│   └── __init__.py           ← 子套件匯出（選用）
```

#### 1.8.2 登記規則（skills.json）

每個技能必須在 `skills.json` 中登記以下資訊：

| 欄位 | 必填 | 說明 |
|------|:----:|------|
| `name` | ✅ | 技能唯一名稱（ snake_case ） |
| `description` | ✅ | 功能說明，供 LLM 工具發現使用 |
| `version` | ✅ | 語意版本號 |
| `source` | ✅ | 相對於 `ai-services/skills/` 的路徑 |
| `intent_hints` | ❌ | 意圖輔助判斷：`{triggers, keywords[], example_phrases[]}`，供 router/intent_classifier 比對使用 |
| `input` | ✅ | 輸入參數規格（參數名 → 說明） |
| `output` | ✅ | 輸出屬性規格 |
| `dependencies` | ❌ | 依賴的外部服務或模組 |

範例：
```json
{
  "name": "ragic_timeline_poller",
  "description": "輪巡 Ragic 表單，比對客戶名稱，將活動摘要寫入 customer_timelines",
  "version": "1.0.0",
  "source": "skills/ragic_timeline_poller/skill.py",
  "input": { "table_configs": "array...", "mode": "enum: poll_all | poll_table | manual_sync" },
  "output": { "synced_count": "number", "errors": "array" },
  "dependencies": ["data_agent.ragic.client", "shared.multimedia"]
}
```

#### 1.8.3 呼叫介面規範

所有 skill 必須實作統一的非同步進入點：

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

#### 1.8.4 Skill 開發規範

1. **單一職責**：一個 skill 只做一件事（如 ragic_timeline_poller 只負責輪巡+寫入，不負責問候生成）
2. **無狀態**：skill 不應有內部狀態，所有配置透過 params 傳入
3. **可複用**：不寫死特定 agent 名稱或業務邏輯，透過參數化支援不同情境
4. **自包含**：每個 skill 目錄完整，不依賴其他 skill 的內部實作
5. **錯誤處理**：所有異常必須捕捉並回傳 `{"error": "描述"}`，不可拋出未處理例外
6. **文件**：每個 skill.py 必須包含 Skill 規範區塊（用途、輸入、輸出、依賴）

### 1.9 BPA Agent 定義

BPA（Business Process Agent）是一種 Agent 類型，具備以下特性：

- **內部知識與資料交互**：BPA 需頻繁讀寫內部系統（ERP、CRM、資料庫、Timeline 等），不是單純的對話型 Agent
- **嚴格的安全管理**：因涉及內部資料，BPA 的 system prompt 與技能調用需經過審查，禁止外部 LLM 隨意讀取或寫入資料
- **受控的資料邊界**：BPA 的資料存取範圍應明確定義，場景一（客戶端）與場景二（內部）的權限必須分離
- **技能組合**：BPA 透過組合多個 skills 完成任務，而非直接在 LLM 呼叫中處理業務邏輯

#### 1.9.1 Skill 與 BPA Agent 的關係

- BPA Agent（如 `業務平台助手`）透過 `router.py` 呼叫 skills
- Agent 不直接實作業務邏輯，而是組合多個 skills 完成任務
- Skills 可被多個 Agent 共用（如 `image_processor` 可同時給客戶端 Bot 和內部助理使用）

```
BPA Agent router.py
  │
  ├── skills.greeting_engine       → 個人化問候
  ├── skills.image_processor       → 名片 OCR / 圖片分類
  ├── skills.ragic_timeline_poller → ERP 活動輪巡
  ├── skills.timeline_engine       → Timeline 讀寫
  └── skills.push_engine           → 排程推播
```

#### 1.8.6 既有 Skills 一覽

| Skill 名稱 | 路徑 | 用途 |
|-----------|------|------|
| `ragic_timeline_poller` | `ai-services/skills/ragic_timeline_poller/skill.py` | Ragic 表輪巡 → customer_timelines 寫入 |
| `timeline_engine` | `ai-services/skills/timeline_engine/skill.py` | Timeline 查詢/寫入/刪除（含 level 過濾） |
| `image_processor` | `ai-services/skills/image_processor/skill.py` | 圖片分類 + 問候生成 + 名片 OCR + 摘要 |
| `greeting_engine` | `ai-services/skills/greeting_engine/skill.py` | CRM 尊稱查詢 + LLM 問候生成 |
| `push_engine` | `ai-services/skills/push_engine/skill.py` | LINE Push 逐筆發送（取代 Broadcast） |

#### 1.8.7 違反此原則的處理

- 在 `ai-services/skills/` 之外建立可複用技能 → 不予合併
- Skill 缺少 `skills.json` 登記 → 不予合併
- Skill 未實作 `execute(params) -> dict` 統一介面 → 不予合併
- Skill 將特定 Agent 邏輯寫死在程式碼中（如 hardcode agent_key）→ 退回重構

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
| 2026-06-17 | 2.2.0 | Daniel Chung | 新增 1.6 Cloudflare Tunnel 說明：Tunnel 由 Cloudflare Dashboard 統一管理，非專案層級管轄 |
| 2026-06-14 | 2.1.0 | Daniel Chung | 新增 1.8 Skills 統一管理原則：目錄結構、登記規則、呼叫介面規範、開發規範、BPA Agent 關係、既有 Skills 一覽、違規處理 |
| 2026-05-21 | 2.0.0 | Daniel Chung | 新增 1.5 請求轉發架構原則（憲法級） |
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
