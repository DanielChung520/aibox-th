---
lastUpdate: 2026-04-23 22:19:30
author: Daniel Chung
version: 1.12.0
---
# AGENTS.md - Daniel Chung Guide for ABC Desktop

## Project Overview

- **Name**: ABC Desktop (abc-desktop)
- **Type**: Tauri + React + TypeScript desktop application
- **UI Framework**: Ant Design 6.x
- **State Management**: Custom AuthStore pattern (see `src/stores/auth.ts`)
- **HTTP Client**: Axios
- **Python Services**: FastAPI

---

## Development Guidelines

請注意，AI coder agent，盡量Thinking、回復都使用繁體中文輸出

### 1. Product Development Principles

本項目為產品開發，請遵循以下原則：

- **避免硬編碼**：所有配置性內容應存放於資料庫或環境變數，而非寫死在程式碼中
- **適當解耦**：模組間保持低耦合，透過介面/接口通訊
- **標準化**：遵循現有程式碼風格與專案慣例
- **可維護性**：程式碼应具有可讀性與可擴展性

### 1.1 Data Agent / Intent 邊界原則（憲法級規範）

**重要**：`intent_catalog` 與 `da_intents` 雖然都屬於「意圖」領域，但責任完全不同，**嚴禁混用**。

#### 核心原則

Data Agent 的挑戰不只是「辨識使用者想做什麼」，而是要根據 schema、relation、顧問知識與資料上下游關聯，產生 SQL、Pandas、追查步驟甚至多階段資料工程流程。因此：

- **`intent_catalog` 僅負責通用/操作性意圖（operational intents）**
- **`da_intents` 僅負責資料語意/資料工程意圖（data-semantic intents）**

這條分界是系統憲法，後續前端、Rust API、Python services、Qdrant sync、assistant routing 都必須遵守。

#### 1.1.1 `intent_catalog` 的責任範圍（通用/操作性意圖）

`intent_catalog` 適合承載：

- 頁面操作說明（例如：如何查看資料表、如何開啟預覽）
- UI/功能導航（例如：這個功能在哪裡、如何切換設定）
- 一般性 CRUD/設定流程意圖
- 與模組無強耦合的共通操作問題
- assistant 在頁面層的操作性提示、澄清與導引

**典型問題範例**：

- 「如何查看這張表的欄位？」
- 「怎麼切換 preview mode？」
- 「哪裡可以設定查詢模型？」
- 「這個頁面怎麼匯入 schema？」

#### 1.1.2 `da_intents` 的責任範圍（資料語意/資料工程意圖）

`da_intents` 適合承載：

- 根據資料表/欄位/關聯生成 SQL 或 Pandas 查詢
- 跨表、跨領域、跨來源的資料追查（trace / lineage / root cause）
- 依靠 Data Agent schema 能力與顧問知識的資料問題求解
- 需要 query planning、relation traversal、aggregation、multi-step pipeline 的意圖
- 與資料本身有關，而不是與頁面操作有關的問題

**典型問題範例**：

- 「客戶退貨時，幫我追這批貨的製造批次、供應商、機台、人員」
- 「這個異常數據可能來自哪些上游表？」
- 「幫我找出這批庫存與採購、製令、收貨之間的關聯」
- 「根據 schema 與 relation，產生可執行的查詢方案」

#### 1.1.3 禁止混放（Hard Rules）

- ❌ 不得將複雜資料查詢、cross-table trace、lineage 分析放進 `intent_catalog`
- ❌ 不得將純 UI 操作教學、頁面導航、功能位置提示放進 `da_intents`
- ❌ 不得以「暫時方便」為由，把資料語意意圖塞回通用 catalog
- ❌ 不得讓 assistant routing 對這兩類意圖做模糊混用，必須先判斷是「操作性問題」還是「資料語意問題」

#### 1.1.4 過渡期原則（Migration / Transition）

目前系統允許過渡，但必須遵守以下原則：

1. **Data Agent 模組（Schema / Query / Trace）優先視 `da_intents` 為資料語意意圖主來源**
2. **`intent_catalog` 可保留作為通用操作性意圖與頁面導引的主來源**
3. 若某功能同時涉及兩者，必須先拆解為：
   - 操作性部分 → `intent_catalog`
   - 資料語意部分 → `da_intents`
4. 未來若要再次統一，必須先證明 unified model 能完整承載 Data Agent 的 query planning / trace / consultant knowledge，而不是只做表面欄位合併

#### 1.1.5 Schema 與 Intent 的轉接原則

`SchemaPage` 屬於 Data Agent 的獨立模組，重點在資料結構（table / field / relation / capability）。

因此，對 Data Agent 而言，正確轉接應為：

```text
Schema / Table / Field / Relation
    ↓
da_intents（資料語意意圖 / query semantics）
    ↓
Qdrant / NL2SQL / Pandas / Trace Runtime
```

而不是：

```text
Schema
    ↓
通用 intent_catalog
    ↓
硬套成 Data Agent runtime
```

若 assistant 在 Schema 頁面中提供建議，也必須區分：

- 問「這頁怎麼操作」 → `intent_catalog`
- 問「這張表的資料怎麼查 / 怎麼追」 → `da_intents`

### 1.2 Agent 選擇規範 (視覺/樣式工作)

**重要**：所有涉及 UI、樣式、CSS、前端視覺相關的工作，**必須委託視覺工程 Agent** 處理。

#### 觸發條件

當任務涉及以下任一項目時，必須呼叫 `visual-engineering` agent：

| 條件 | 範例 |
|------|------|
| 新增或修改頁面樣式 | 建立新頁面、修改現有頁面外觀 |
| UI 組件開發 | 按鈕、卡片、表單、表格等視覺組件 |
| 響應式設計 | 適配不同螢幕尺寸、折疊選單 |
| 主題/配色調整 | 修改顏色、陰影、圓角等 Design Tokens |
| CSS 動畫/過渡 | 按鈕 hover 效果、頁面切換動畫 |
| 圖示/插圖整合 | 新增 icon、使用 SVG/圖片 |

#### 執行流程

```
1. 收到視覺/樣式相關任務
2. 立即呼叫 visual-engineering agent，載入以下規範：
   - prompt 任務描述
   - 附上 DESIGN.md 路徑與內容摘要
3. 由 visual-engineering agent 完成視覺工作
4. 由本 agent (build) 整合到專案中
```

#### Prompt 範例

```
任務：為 ABC Desktop 新增「系統公告」頁面

規範文件：
- 設計系統：./DESIGN.md
- UI 框架：Ant Design 6.x
- 主題：雙層架構 (Shell 固定深色 + Content 可切換亮/暗)

請 visual-engineering agent：
1. 根據 DESIGN.md 規範設計公告列表頁面
2. 包含公告卡片、發布時間、狀態標籤
3. 支援亮/暗主題切換
4. 使用 Ant Design 組件
```

#### 為什麼要委託視覺工程 Agent？

| 自己處理 | 委託視覺工程 Agent |
|----------|-------------------|
| 缺乏專業 UI/UX 視角 | 專業設計視角 |
| 可能破壞 Design System 一致性 | 完全遵循 DESIGN.md |
| 動畫/響應式處理粗糙 | 精細的動效與響應式 |
| 耗費大量時間調試 | 高效產出 |

**⚠️ 警告**：即使任務看似簡單（如「只是加個顏色」），也請委託視覺工程 Agent，確保符合整體 Design System。

#### 硬編碼避免清單

| 類型     | 正確做法                                 |
| -------- | ---------------------------------------- |
| API URL  | 存放於環境變數或配置檔                   |
| 功能開關 | 存放於資料庫 `system_params`           |
| 權限配置 | 存放於資料庫 `roles` / `permissions` |
| 菜單配置 | 存放於資料庫 `functions`               |
| 常數配置 | 存放於 `src/config/` 或環境變數        |

### 1.4 系統參數管理原則（system_params）

#### 核心原則

**所有系統參數（功能開關、模型配置、行為閾值等）一律存放於 ArangoDB `system_params` 集合，嚴禁直接 hardcode 在 Python / Rust 程式碼中。**

例外：極少數與啟動相關的必要參數（如 `PORT`、`ARANGODB_URL`、`ARANGODB_PASSWORD`）放在 `.env`，其餘所有參數都走 `system_params`。

#### 參數讀取範圍（優先順序）

```
1. ArangoDB system_params  ← 主要來源
       ↓
2. Rust API: GET /api/v1/system-params/{param_key}
       ↓
3. 環境變數 fallback（原則上只是過渡，不應長期依賴）
       ↓
4. 預設值（last resort）
```

#### Python 服務讀取方式

每個 Python 服務應參考 `data_agent/config_reader.py` 的模式，透過 Rust API Gateway 讀取 `system_params`：

```python
# aiq_agent 的標準做法（參照 data_agent/config_reader.py）
_GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:6500")
_cache: dict[str, tuple[str, float]] = {}

async def get_param(param_key: str) -> str:
    cached = _cache.get(param_key)
    if cached and time.time() - cached[1] < 300:
        return cached[0]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{_GATEWAY_URL}/api/v1/system-params/{param_key}")
            if resp.status_code == 200:
                value = resp.json()["data"]["param_value"]
                _cache[param_key] = (value, time.time())
                return value
    except Exception:
        pass
    return os.getenv(fallback_env_key, default_value)
```

#### 新增參數前 — 必須先調查現有參數

**杜絕重複創建**。新增任何 `system_params` 之前，必須先確認是否已存在：

```bash
# 查詢是否已有相關參數（模糊比對）
curl -s -u "root:abc_desktop_2026" \
  "http://localhost:8529/_db/abc_desktop/_api/cursor" \
  -H "Content-Type: application/json" \
  -d '{"query":"FOR p IN system_params FILTER STARTS_WITH(p.param_key, @prefix) RETURN p"}' \
  --data '{"prefix":"intent."}' | python3 -m json.tool

# 確認意圖相關參數
curl -s -u "root:abc_desktop_2026" \
  "http://localhost:8529/_db/abc_desktop/_api/cursor" \
  -H "Content-Type: application/json" \
  -d '{"query":"FOR p IN system_params FILTER p.param_key LIKE @kw RETURN p"}' \
  --data '{"kw":"%model%"}' | python3 -m json.tool
```

**已知的系統參數前綴（避免重複）**：

| 前綴 | 用途 |
|------|------|
| `aiq.` | 艾企助手感知/意圖引擎行為參數 |
| `intent.` | 通用意圖分析（RAG/LLM）配置 |
| `da.` | Data Agent NL→SQL 配置 |
| `knowledge.` | 知識庫 RAG 配置 |
| `task_chat.` | 任務對話模型配置 |
| `bpa.` | BPA 工作流參數 |
| `weather.` | 天氣工具配置 |
| `web_search.` | 網路搜尋配置 |

#### 禁止行為

- ❌ `os.environ.get("SOME_MODEL", "qwen3:32b")` — 直接寫死不存在的模型
- ✅ `await get_param("intent.small_model_name")` — 從 system_params 動態讀取
- ❌ 新增 `aiq.inquiry_model` 前先沒查是否已有 `intent.small_model_name`
- ✅ 查詢現有參數 → 確認無重複 → 再新增

#### 參數變更流程

1. 透過 Rust API 變更：`PUT /api/v1/system-params/{key}`，快取自動失效（TTL 300s 內生效）
2. 或直接改 ArangoDB 文件，快取 TTL 後自動同步
3. Python 服務無需重啟，下次 `get_param()` 時自動讀新值

---

### 1.5 Safe Operation Rules（破壞性操作必須事先取得同意）

以下操作在執行前**必須先問使用者**，取得同意後才能執行：

| 操作                               | 說明                     | 原因                       |
| ---------------------------------- | ------------------------ | -------------------------- |
| `git checkout` / revert          | 還原檔案或目錄到之前狀態 | 會丟失未 commit 的工作進度 |
| 刪除檔案                           | 刪除任何程式碼或設定檔   | 可能造成功能損失           |
| 大規模重寫                         | 一次性重寫整個檔案或模組 | 風險高且難以追蹤變更       |
| `git reset` / `git stash drop` | 丟棄 commit 或 stash     | 不可逆，會丟失程式碼       |
| 修改資料庫資料                     | INSERT / UPDATE / DELETE 任何集合資料 | 可能影響線上資料或破壞資料完整性 |

**正確做法**：先問「我可以 revert 這個檔案嗎？」或「我可以修改 XX 集合的資料嗎？」，等待回覆後再執行。

---

### 1.5.1 ⚠️ ArangoDB 文件更新 — PATCH vs PUT（已造成多次資料遺失，嚴禁再犯）

**ArangoDB REST API 文件更新有兩種行為，差異巨大：**

| HTTP 方法 | ArangoDB 行為 | 適用場景 |
|-----------|--------------|---------|
| **PATCH** | **只更新指定欄位，其餘保留** | 更新文件中的一到多個欄位 |
| **PUT** | **替換整份文件（舊的全部消失）** | 替換整份文件（極少用） |

**⚠️ 教訓：已發生至少 2 次因 PUT 導致文件欄位全部遺失的事故。**

**常見錯誤：**

```bash
# ❌ 錯誤：PUT 會清除所有未指定的欄位
curl -X PUT "http://localhost:8529/_db/abc_desktop/_api/document/collection/doc_key" \
  -u "root:password" \
  -d '{"webhook_url": "https://new-url.com"}'

# ✅ 正確：使用 PATCH 只更新指定欄位
curl -X PATCH "http://localhost:8529/_db/abc_desktop/_api/document/collection/doc_key" \
  -u "root:password" \
  -d '{"webhook_url": "https://new-url.com"}'
```

**或使用 AQL PATCH（推薦）：**

```bash
curl -s -X POST "http://localhost:8529/_db/abc_desktop/_api/cursor" \
  -u "root:password" \
  -H "Content-Type: application/json" \
  -d '{"query": "FOR doc IN collection FILTER doc._key == @key PATCH doc WITH { webhook_url: @url } IN collection", "bindVars": {"key": "doc_key", "url": "https://new-url.com"}}'
```

**操作前的 SOP：**
1. **先查詢**完整文件內容，確認所有欄位值
2. **自問**：要改的是「一個欄位」還是「整份」？
   - 一個欄位 → **PATCH**
   - 整份替換 → 先備份完整內容，再問使用者確認
3. **更新完成後**：再次查詢確認所有欄位仍在

**Python 建議**：使用 ArangoDB Python SDK 的 `update.match(doc)` 方法（自動 PATCH）。

---

### 1.6 Temporary Files Management（臨時檔案管理）

**原則**：非必要請勿在專案目錄根層新增任何臨時檔案。所有臨時檔案應統一放置於 `.tmp/` 目錄。

#### 允許的臨時檔案位置

| 目錄        | 用途                                   |
| ----------- | -------------------------------------- |
| `.tmp/`     | 所有 AI Agent 測試腳本、截圖、傾印檔  |

#### 禁止的行為

- ❌ 將 `.cjs`、`.mjs`、`.js` 等測試腳本直接放在專案根目錄
- ❌ 將截圖檔案 (`*.png`) 直接放在專案根目錄
- ❌ 將任何除錯用的臨時檔案散落在 `src/`、`tests/`、`api/` 等正常目錄之外

#### 正確做法

```bash
# 臨時測試腳本 → .tmp/
# ❌ 錯誤
node test-chat.mjs
# ✅ 正確
mkdir -p .tmp && mv test-chat.mjs .tmp/

# 臨時截圖 → .tmp/
# ❌ 錯誤
mv screenshot.png ./screenshot.png
# ✅ 正確
mkdir -p .tmp && mv screenshot.png .tmp/
```

#### 定期清理

`.tmp/` 目錄需定期清理，避免累積無用檔案。建議每次開發結束後主動移除不再需要的臨時檔案，或使用以下指令：

```bash
# 清理 .tmp 目錄（確認後再刪除）
ls .tmp/    # 先確認內容
rm -rf .tmp/*   # 確認無誤後執行清理
```

---

### 2. Code & File Header Standards

所有程式碼檔案必須包含表頭註解，格式如下：

#### TypeScript / React

```typescript
/**
 * @file        檔案說明概要
 * @description 詳細說明（可選）
 * @lastUpdate  YYYY-MM-DD HH:MM:SS
 * @author      更新者名稱
 * @version     1.0.0
 * @history
 * - YYYY-MM-DD HH:MM:SS | 更新者 | 版本 | 變更說明
 */
```

> **取得正確時間**：在終端執行 `date "+%Y-%m-%d %H:%M:%S"` 取得當前時間戳記

#### Rust

```rust
//! 檔案說明概要
//!
//! # Description
//! 詳細說明（可選）
//!
//! # Last Update: YYYY-MM-DD HH:MM:SS
//! # Author: 更新者名稱
//! # Version: 1.0.0
```

> **取得正確時間**：在終端執行 `date "+%Y-%m-%d %H:%M:%S"` 取得當前時間戳記

> **注意**：不需要在每個檔案添加變更歷史 (history)，避免代碼膨脹。統一在 CHANGELOG.md 或版本控制中管理變更記錄。

#### Markdown 文件

```markdown
---
lastUpdate: YYYY-MM-DD HH:MM:SS
author: 更新者名稱
version: 1.0.0
---

# 標題

## 修改歷程
| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| YYYY-MM-DD | 1.0.0 | 作者 | 初始版本 |
```

> **取得正確時間**：在終端執行 `date "+%Y-%m-%d %H:%M:%S"` 取得當前時間戳記

---

### 3. Duplicate Prevention Check

在新增任何程式碼或檔案之前，必須執行以下檢查：

1. **查看專案架構**：閱讀 `README.md` 與 `AGENTS.md` 確認現有結構
2. **搜尋現有功能**：使用 grep 搜尋是否已有類似功能
3. **確認複用可能**：評估是否能複用現有模組

#### 新增功能前檢查清單

- [ ] 確認 `README.md` 專案結構說明
- [ ] 確認 `AGENTS.md` 相關開發規範
- [ ] 確認 `.docs/API Specification.md` API 端點說明
- [ ] 確認 `src/services/api.ts` 是否有可複用 API
- [ ] 搜尋現有程式碼是否有類似功能
- [ ] 確認現有 API 是否可複用
- [ ] 確認現有元件是否可擴展

---

### 3.5 Module Size Guidelines (模組大小規範)

為避免單一檔案過大導致 AI Agent context 記憶體不足，請遵守以下規範：

#### 檔案行數上限

| 語言       | 單檔上限 | 建議上限 |
| ---------- | -------- | -------- |
| Rust       | 500 行   | 300 行   |
| TypeScript | 400 行   | 250 行   |
| Python     | 400 行   | 250 行   |

#### 切割時機

當單一檔案接近上限時，應考慮切割：

1. **測試代碼分離**：將測試移至獨立檔案 `modulename_test.rs` 或 `module.test.ts`
2. **子模組拆分**：將大型模組拆分為多個子模組
3. **關注點分離**：將不同職責的代碼分離

#### 範例

```rust
// 原始：500 行的 module.rs
// 拆分為：
src/
├── module/           # 主模組目錄
│   ├── mod.rs        # 導出子模組 (50 行)
│   ├── core.rs       # 核心邏輯 (200 行)
│   ├── handler.rs    # 處理器 (150 行)
│   ├── storage.rs    # 儲存相關 (100 行)
│   └── lib.rs        # 模組入口 (30 行)
```

#### 實施檢查清單

- [ ] 單一檔案不超過 300 行 (Rust) / 250 行 (TS/Python)
- [ ] 測試代碼獨立存放 (`tests/` 目錄)
- [ ] 模組職責單一 (Single Responsibility)
- [ ] 導出清晰，易於理解

#### 測試文件放置規範

為避免測試文件與代碼腳本混雜導致項目結構複雜，請遵守以下規範：

| 語言       | 測試位置         | 範例                             |
| ---------- | ---------------- | -------------------------------- |
| Rust       | `.tests/rs/`   | `.tests/rs/error_test.rs`      |
| Python     | `.tests/py/`   | `.tests/py/test_auth.py`       |
| TypeScript | `.tests/ts/`   | `.tests/ts/auth.test.ts`       |
| JSON       | `.tests/json/` | `.tests/json/schema_test.json` |

**禁止**：

- ❌ 在模組目錄內放置測試 (`mod.rs` 同層)
- ❌ 使用 `mod_test.rs` 命名
- ❌ 混合測試與業務代碼

**正確做法**：

- ✅ 測試統一放置在 `.tests/` 目錄，按語言分開
- ✅ 每個模組對應一個測試檔案
- ✅ 使用描述性的測試檔案名稱

---

### 4. Deletion Approval Process

**刪除程式碼或檔案必須獲得同意**，流程如下：

1. **提出刪除請求**：說明要刪除的檔案/程式碼及原因
2. **影響範圍評估**：確認是否有其他功能依賴
3. **獲得同意**：確認刪除不會造成系統異常
4. **執行刪除**：完成後更新相關文件

#### 禁止直接刪除

- 系統核心模組
- 資料庫結構定義
- API 端點（應標記為廢棄）
- 共用元件

---

## Build & Development Commands

### Core Commands

```bash
# Start development server (Vite on port 1420)
npm run dev

# Build for production (runs TypeScript check + Vite build)
npm run build

# Preview production build
npm run preview

# Tauri commands (build, dev, etc.)
npm run tauri [command]
```

### Running Tests

> **Note**: No test framework is currently configured. To add tests:

```bash
# Install Vitest (recommended for Vite projects)
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom

# Run all tests
npx vitest

# Run a single test file
npx vitest run src/stores/auth.test.ts

# Watch mode
npx vitest
```

### Type Checking

```bash
# Run TypeScript compiler check only
npx tsc --noEmit
```

### Linting

> **Note**: No ESLint is configured. Recommended setup:

```bash
# Install ESLint
npm install -D eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin eslint-plugin-react eslint-plugin-react-hooks

# Run ESLint
npx eslint src/
```

### Python AI Services

```bash
# Install Python dependencies
cd ai-services && pip install -r requirements.txt

# Run mypy type check
cd ai-services && mypy . --strict --ignore-missing-imports --exclude 'aitask/main.py'

# Run ruff linting
cd ai-services && ruff check .

# Format code
cd ai-services && ruff format .

# Run all checks (CI/CD)
cd ai-services && ruff check . && ruff format --check . && mypy . --strict --ignore-missing-imports --exclude 'aitask/main.py'

# Start AI service (example: aitask)
cd ai-services/aitask && uvicorn main:app --port 8001 --reload
```

---

## 執行環境 (Execution Environment)

### Python 服務執行環境

**重要**：所有 Python AI 服務必須使用 `.venv` 虛擬環境執行，**禁止使用系統 Python**。

#### 確認虛擬環境

```bash
# 確認 .venv 存在
ls -la ai-services/.venv/bin/python

# 確認當前使用的 Python 版本（應為 3.14）
ai-services/.venv/bin/python --version
```

#### 服務啟動命令（使用 .venv）

```bash
# 進入 ai-services 目錄
cd ai-services

# 啟動所有 Python AI 服務（使用 .venv）
source .venv/bin/activate

# AITask (port 8001) - AI 任務編排
.venv/bin/python -m uvicorn aitask.main:app --port 8001 --host 127.0.0.1

# Data Agent (port 8003) - NL→SQL 查詢
.venv/bin/python -m uvicorn data_agent.main:app --port 8003 --host 127.0.0.1

# MCP Tools (port 8004) - MCP 工具執行
.venv/bin/python -m uvicorn mcp_tools.main:app --port 8004 --host 127.0.0.1

# BPA MM Agent (port 8005) - 物料管理流程
.venv/bin/python -m uvicorn bpa.mm_agent.main:app --port 8005 --host 127.0.0.1

# Knowledge Agent (port 8007) - 知識庫 RAG
.venv/bin/python -m uvicorn knowledge_agent.main:app --port 8007 --host 127.0.0.1

# Memory Agent (port 8008) - AI 增強記憶
.venv/bin/python -m uvicorn memory_agent.main:app --port 8008 --host 127.0.0.1

# Backup Agent (port 8010)
.venv/bin/python -m uvicorn backup_agent.main:app --port 8010 --host 127.0.0.1
```

#### 快速重啟單一服務

```bash
# 找到並 kill 舊进程
pkill -f "uvicorn aitask.main:app"

# 使用 .venv 重啟
cd ai-services
nohup .venv/bin/python -m uvicorn aitask.main:app --port 8001 --host 127.0.0.1 > .tmp/aitask.log 2>&1 &
```

---

### Rust API Gateway 執行環境

#### 環境變數配置

Rust API Gateway 使用 `api/.env` 檔案：

```bash
# 進入 api 目錄
cd api

# 確認 .env 存在
cat .env | grep PORT

# 啟動 API（自動讀取 .env）
cd ..
./target/release/abc-api
```

#### 環境變數範例 (api/.env)

```env
# ===================
# Server
# ===================
PORT=6500
HOST=127.0.0.1

# ===================
# Database
# ===================
DATABASE_URL=http://localhost:8529
DATABASE_NAME=abc_desktop
DATABASE_USER=root
DATABASE_PASSWORD=abc_desktop_2026

# ===================
# JWT
# ===================
JWT_SECRET=your-secret-key
JWT_EXPIRATION_HOURS=24

# ===================
# AI Services
# ===================
AITASK_URL=http://localhost:8001
DATA_AGENT_URL=http://localhost:8003
KNOWLEDGE_AGENT_URL=http://localhost:8007
MCP_TOOLS_URL=http://localhost:8004
BPA_MM_AGENT_URL=http://localhost:8005
OLLAMA_BASE_URL=http://localhost:11434
LM_STUDIO_URL=http://localhost:1234

# ===================
# External Services
# ===================
QDRANT_URL=http://localhost:6333
SEAWEED_AIBOX_URL=http://localhost:8888
SEAWEED_USER=admin
SEAWEED_PASS=admin123

# ===================
# Rate Limiting
# ===================
RATE_LIMIT_MAX_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# ===================
# Billing
# ===================
BILLING_FREE_TOKENS_PER_MONTH=10000
BILLING_PRICE_PER_1K_TOKENS=0.001
```

#### 確認服務正常

```bash
# Rust API Gateway
curl http://localhost:6500/health

# Python AI Services
curl http://localhost:8001/health  # AITask
curl http://localhost:8003/health  # Data Agent
```

---

## Code Style Guidelines

### TypeScript Configuration

The project uses `strict: true` in `tsconfig.json`. All TypeScript rules are enforced:

- `noUnusedLocals: true`
- `noUnusedParameters: true`
- `noFallthroughCasesInSwitch: true`

**Never use `any` type or suppress errors with `@ts-ignore`**.

---

### 5. Python Code Quality Standards

本專案 Python 程式碼必須通過 mypy 與 ruff 檢查：

#### mypy (類型檢查)

```bash
# Install mypy
pip install mypy

# Run mypy check
cd ai-services && mypy . --ignore-missing-imports

# Strict mode (recommended)
mypy . --strict --ignore-missing-imports --exclude 'aitask/main.py'
```

#### ruff (Linting/Formatting)

```bash
# Install ruff
pip install ruff

# Run ruff check
ruff check ai-services/

# Auto-fix issues
ruff check ai-services/ --fix

# Format code
ruff format ai-services/
```

#### CI/CD 整合

```bash
# 提交前必須通過檢查
ruff check ai-services/ && ruff format --check ai-services/ && mypy ai-services/
```

#### 規範要點

| 規則                  | 說明                         |
| --------------------- | ---------------------------- |
| mypy                  | 必須通過 `--strict` 檢查   |
| ruff                  | 使用 `ruff check` 發現問題 |
| 類型提示              | 所有函數必須有型別提示       |
| docstring             | 公開 API 必須有 docstring    |
| 禁止 `Any`          | 不使用 `Any` 類型          |
| 禁止 `type: ignore` | 不使用 `# type: ignore`    |

#### 範例

```python
# 正確範例
def calculate_total(items: list[Item]) -> float:
    """Calculate total price of items.
  
    Args:
        items: List of items to calculate.
      
    Returns:
        Total price as float.
    """
    return sum(item.price for item in items)

# 錯誤範例 (不要這樣做)
def calculate_total(items):  # 缺少類型提示
    return sum([i['price'] for i in items])  # 使用字典而非 TypedDict
```

### Imports & Organization

```typescript
// 1. React imports
import { useState, useEffect } from 'react';

// 2. External libraries (Ant Design, React Router, etc.)
import { Form, Input, Button } from 'antd';
import { useNavigate } from 'react-router-dom';

// 3. Internal services/stores
import { authApi, userApi, User } from '../services/api';
import { authStore } from '../stores/auth';

// 4. Components (local)
import UserManagement from './UserManagement';

// 5. Styles (if any)
import './styles.css';
```

### Naming Conventions

| Element                 | Convention | Example                                        |
| ----------------------- | ---------- | ---------------------------------------------- |
| Components              | PascalCase | `UserManagement.tsx`, `MainLayout.tsx`     |
| Functions/variables     | camelCase  | `fetchUsers()`, `loading`, `editingUser` |
| Interfaces              | PascalCase | `User`, `LoginRequest`, `LoginResponse`  |
| File names (utilities)  | camelCase  | `auth.ts`, `api.ts`                        |
| File names (components) | PascalCase | `Login.tsx`, `UserManagement.tsx`          |

### Component Structure

Follow the pattern in `src/pages/UserManagement.tsx`:

```typescript
// 1. Imports
import { useState, useEffect } from 'react';
import { Table, Button, message } from 'antd';
import { userApi, User } from '../services/api';

// 2. Interface definitions (if component-specific)
interface UserManagementProps {
  // props
}

// 3. Main component with default export
export default function UserManagement() {
  // 4. State hooks first
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);

  // 5. Data fetching functions
  const fetchUsers = async () => {
    // try/catch with message.error()
  };

  // 6. Effect hooks
  useEffect(() => {
    fetchUsers();
  }, []);

  // 7. Event handlers
  const handleDelete = async (key: string) => { };

  // 8. Render (JSX)
  return (
    <div>
      {/* ... */}
    </div>
  );
}
```

### Error Handling

Always use try/catch with Ant Design's `message` component:

```typescript
try {
  const response = await userApi.list();
  setUsers(response.data.data || []);
} catch (error: any) {
  message.error(error.response?.data?.message || '操作失败');
} finally {
  setLoading(false);
}
```

### API Layer Pattern

Define interfaces and API methods in `src/services/api.ts`:

```typescript
// Define response interfaces
export interface User {
  _key: string;
  username: string;
  name: string;
  role_key: string;
  status: string;
  created_at: string;
}

// Create API object with typed methods
export const userApi = {
  list: () => api.get<{ code: number; data: User[] }>('/api/v1/users'),
  get: (key: string) => api.get<{ code: number; data: User }>(`/api/v1/users/${key}`),
  create: (data: Partial<User> & { password_hash: string }) => api.post('/api/v1/users', data),
  update: (key: string, data: Partial<User>) => api.put(`/api/v1/users/${key}`, data),
  delete: (key: string) => api.delete(`/api/v1/users/${key}`),
};
```

### State Management

Use the custom AuthStore pattern from `src/stores/auth.ts`:

```typescript
class AuthStore {
  private state: AuthState = { /* initial state */ };
  private listeners: Set<() => void> = new Set();

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  getState() { return this.state; }

  login(user: User, token: string) {
    this.state = { /* new state */ };
    this.notify();
  }

  private notify() { this.listeners.forEach(listener => listener()); }
}

export const authStore = new AuthStore();
```

### Styling

- Use Ant Design's built-in styling system (tokens, theme)
- Use inline styles for dynamic theming (see `Login.tsx` for dark/light mode)
- Use CSS files for static styles (e.g., `App.css`)

### UI Language

The application uses **Chinese** for all UI text:

- Button labels: `登录`, `新增用户`, `编辑`, `删除`
- Messages: `登录成功`, `获取用户列表失败`
- Form labels: `用户名`, `密码`, `角色`

---

## Project Structure

```
src/
├── main.tsx              # Entry point
├── App.tsx               # Main app with routing & theme
├── pages/                # Page components
│   ├── Login.tsx
│   ├── MainLayout.tsx
│   ├── UserManagement.tsx
│   ├── RoleManagement.tsx
│   ├── SystemParams.tsx
│   └── Welcome.tsx
├── services/
│   └── api.ts            # API interfaces & methods
├── stores/
│   └── auth.ts           # Custom auth store
└── assets/
    └── react.svg
```

---

## Common Tasks

### Adding a New Page

1. Create component in `src/pages/`
2. Add route in `App.tsx`
3. Use `MainLayout` for authenticated pages

### Adding a New API

> **重要**：請先閱讀 [API 開發規範](#api-開發規範-api-specification) 章節

1. 查閱 `.docs/API Specification.md` 確認現有端點
2. 定義 interface 在 `src/services/api.ts`
3. 確認請求/回應格式符合規範
4. 新增 API 方法並實作類型
5. 在元件中引入使用

### Adding a New Store

1. Create file in `src/stores/`
2. Follow AuthStore pattern (subscribe, getState, notify)
3. Import in components and subscribe to changes

---

## API 開發規範 (API Specification)

### 強制要求

**所有 API 開發必須遵循 `.docs/API Specification.md` 文件**：

- 任何接口調用必須參考 API Specification
- 新增 API 端點必須遵循現有命名規範
- 請求/回應格式必須符合通用格式
- 錯誤處理必須使用 ApiError 枚舉

### API Specification 位置

```
.docs/
└── API Specification.md
```

### 調用 API 前的檢查清單

在調用任何 API 端點之前：

- [ ] 確認端點存在於 API Specification
- [ ] 確認請求格式與文件一致
- [ ] 確認是否需要認證 (JWT Token)
- [ ] 確認正確的 HTTP 方法 (GET/POST/PUT/DELETE)
- [ ] 確認錯誤處理方式

### 常見 API 端點參考

| 功能         | 端點                      | 方法 | 認證 |
| ------------ | ------------------------- | ---- | ---- |
| 登入         | `/api/v1/auth/login`    | POST | 否   |
| 取得當前用戶 | `/api/v1/auth/me`       | GET  | 是   |
| 使用者列表   | `/api/v1/users`         | GET  | 是   |
| 角色列表     | `/api/v1/roles`         | GET  | 否   |
| 系統參數     | `/api/v1/system-params` | GET  | 否   |
| AI 對話      | `/api/v1/ai/chat`       | POST | 是   |

### 新增 API 流程

1. 查閱 `.docs/API Specification.md` 確認現有端點
2. 遵循文件中的「新增 API 流程」章節
3. 新增對應的單元測試
4. 更新 API Specification 文件

### API 錯誤碼對照

| 狀態碼 | 說明           | 常見原因             |
| ------ | -------------- | -------------------- |
| 400    | Bad Request    | 請求格式錯誤         |
| 401    | Unauthorized   | JWT Token 無效或過期 |
| 403    | Forbidden      | 權限不足             |
| 404    | Not Found      | 資源不存在           |
| 500    | Internal Error | 伺服器錯誤           |

---

## Tauri Desktop 桌面殼開發規範

### 1. 專案結構

```
src-tauri/
├── src/
│   ├── lib.rs           # 桌面殼入口 (Tauri 配置)
│   └── main.rs          # 程式入口
├── Cargo.toml           # Rust 依賴
├── tauri.conf.json      # Tauri 配置
├── icons/               # 應用圖標
└── capabilities/       # 權限配置

src/                    # React 前端
├── pages/              # 頁面元件
│   ├── Login.tsx       # 登入頁
│   ├── MainLayout.tsx  # 主佈局
│   ├── UserManagement.tsx
│   ├── RoleManagement.tsx
│   ├── SystemParams.tsx
│   └── Welcome.tsx
├── services/
│   └── api.ts          # API 調用層
├── stores/
│   └── auth.ts         # 認證狀態管理
└── App.tsx             # 路由配置
```

### 2. API 調用規範

> **重要**：所有 API 調用必須遵循 [API 開發規範](#api-開發規範-api-specification)

#### 2.1 API 服務層 (src/services/api.ts)

所有 API 調用必須透過 `api.ts` 統一管理：

```typescript
// 1. 定義 Request/Response 介面
export interface User {
  _key: string;
  username: string;
  name: string;
  role_key: string;
  status: string;
  created_at: string;
}

// 2. 建立 API 物件
export const userApi = {
  // GET 請求
  list: () => api.get<{ code: number; data: User[] }>('/api/v1/users'),
  get: (key: string) => api.get<{ code: number; data: User }>(`/api/v1/users/${key}`),
  
  // POST 請求
  create: (data: Partial<User> & { password_hash: string }) => 
    api.post('/api/v1/users', data),
  
  // PUT 請求
  update: (key: string, data: Partial<User>) => 
    api.put(`/api/v1/users/${key}`, data),
  
  // DELETE 請求
  delete: (key: string) => api.delete(`/api/v1/users/${key}`),
};
```

#### 2.2 錯誤處理

```typescript
// 正確的錯誤處理方式
try {
  const response = await userApi.list();
  setUsers(response.data.data || []);
} catch (error: any) {
  message.error(error.response?.data?.message || '操作失败');
} finally {
  setLoading(false);
}
```

#### 2.3 認證 Token 處理

Token 會自動透過 Axios Interceptor 添加：

```typescript
// api.ts 中的攔截器配置
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 401 自動跳轉登入
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

### 3. 新增頁面流程

#### 3.1 建立頁面元件

在 `src/pages/` 目錄下建立新元件：

```typescript
/**
 * @file        新功能頁面
 * @description 新功能說明
 * @lastUpdate  YYYY-MM-DD HH:MM:SS
 * @author      更新者名稱
 * @version     1.0.0
 */

import { useState, useEffect } from 'react';
import { Table, Button, message, Form, Input } from 'antd';
import { userApi, User } from '../services/api';

export default function NewFeature() {
  const [data, setData] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);

  // 資料獲取
  const fetchData = async () => {
    setLoading(true);
    try {
      const response = await userApi.list();
      setData(response.data.data || []);
    } catch (error: any) {
      message.error(error.response?.data?.message || '獲取數據失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div>
      <Table dataSource={data} loading={loading} rowKey="_key">
        <Table.Column title="用戶名" dataIndex="username" key="username" />
        <Table.Column title="姓名" dataIndex="name" key="name" />
        <Table.Column title="狀態" dataIndex="status" key="status" />
      </Table>
    </div>
  );
}
```

#### 3.2 新增路由

在 `src/App.tsx` 中新增路由：

```typescript
import NewFeature from './pages/NewFeature';

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Welcome />} />
        <Route path="users" element={<UserManagement />} />
        <Route path="roles" element={<RoleManagement />} />
        <Route path="new-feature" element={<NewFeature />} />  {/* 新增路由 */}
      </Route>
    </Routes>
  );
}
```

#### 3.3 新增功能到菜單

功能菜單存放在資料庫 `functions` 集合，透過以下 API 管理：

```bash
# 新增功能
curl -X POST http://localhost:6500/api/v1/functions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "_key": "system.newfeature",
    "code": "system.newfeature",
    "name": "新功能",
    "description": "新功能說明",
    "function_type": "sub_function",
    "parent_key": "system",
    "path": "/app/new-feature",
    "icon": "ToolOutlined",
    "sort_order": 5,
    "status": "enabled"
  }'
```

### 4. 新增 API 端點

#### 4.1 後端 Rust API

> **重要**：參考 `.docs/API Specification.md` 新增 API

1. 在 `api/src/api/mod.rs` 新增路由
2. 實作處理函數
3. 使用資料庫操作
4. 新增單元測試

#### 4.2 前端 API 調用

1. 在 `src/services/api.ts` 新增介面定義
2. 新增 API 方法
3. 在元件中調用

### 5. 狀態管理

使用自訂 AuthStore 模式：

```typescript
// src/stores/auth.ts
class AuthStore {
  private state: AuthState = { token: null, user: null };
  private listeners: Set<() => void> = new Set();

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  getState() { return this.state; }

  setToken(token: string) {
    this.state = { ...this.state, token };
    localStorage.setItem('token', token);
    this.notify();
  }

  logout() {
    this.state = { token: null, user: null };
    localStorage.removeItem('token');
    this.notify();
  }

  private notify() { this.listeners.forEach(listener => listener()); }
}

export const authStore = new AuthStore();
```

### 6. 桌面殼擴展 (Tauri Commands)

如需在桌面殼執行原生功能，可在 `src-tauri/src/lib.rs` 新增 Commands：

```rust
use tauri::command;

#[command]
fn greet(name: &str) -> String {
    format!("Hello, {}!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![greet])  // 註冊命令
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

前端調用：

```typescript
import { invoke } from '@tauri-apps/api/core';

const greeting = await invoke<string>('greet', { name: 'World' });
```

### 7. 環境配置

| 變數               | 說明           | 預設值                    |
| ------------------ | -------------- | ------------------------- |
| `VITE_API_URL`   | API 伺服器地址 | `http://localhost:6500` |
| `VITE_APP_TITLE` | 應用標題       | ABC Desktop               |

### 8. 開發命令

```bash
# 啟動開發伺服器 (前端)
npm run dev

# 啟動 Tauri 開發模式
npm run tauri dev

# 建構生產版本
npm run tauri build

# 建構 DMG (macOS)
npm run tauri build -- --target x86_64-apple-darwin
```

---

## Recommended Extensions

- VS Code
- Tauri VS Code extension
- rust-analyzer
- ESLint
- Prettier (format on save)

---

## 10. 服務架構原則 (Service Architecture)

### 10.1 核心原則

**所有前端請求必須透過 Rust API Gateway (6500) 轉發，嚴禁前端直接呼叫 Python 服務。**

```
Frontend → Rust API Gateway (6500) → Python Services
                                      │
                                      ├── unified_agents (8011)
                                      │       ├── /da/*
                                      │       ├── /ka/*
                                      │       ├── /memory/*
                                      │       ├── /backup/*
                                      │       ├── /tools/*
                                      │       └── /platforms/*
                                      │
                                      └── [其他獨立服務]
```

**目的**：統一管理、負載平衡、未來可拆分。

### 10.2 服務分類

| 分類 | 服務 | Port | 說明 | 整合進 unified_agents |
|------|------|------|------|----------------------|
| **獨立** | aitask | 8001 | AI 任務編排 | ❌ |
| **獨立** | bpa_mm_agent | 8005 | 物料管理流程 | ❌ |
| **獨立** | celery | - | 非同步任務佇列 Worker | ❌ |
| **獨立** | mcp_tools | 8004 | MCP 工具執行 | ❌ |
| **獨立** | static | 6000 | 靜態檔案 hosting (DMG) | ❌ |
| **統一** | unified_agents | 8011 | 所有通用工具與平台整合 | ✅ |

### 10.3 unified_agents 路由約定

所有整合進 unified_agents 的服務，必須遵循以下路由前綴：

| 前綴 | 用途 | 範例 |
|------|------|------|
| `/da/*` | Data Agent (NL→SQL, Ragic) | `/da/query/nl`, `/da/intent-rag/*` |
| `/ka/*` | Knowledge Agent (Hybrid RAG) | `/ka/search`, `/ka/hybrid/*` |
| `/memory/*` | Memory Agent | `/memory/recall`, `/memory/session/*` |
| `/backup/*` | Backup Agent | `/backup/status`, `/backup/arangodb/*` |
| `/tools/*` | 通用工具 | `/tools/execute`, `/tools/weather/*` |
| `/platforms/*` | 平台整合 | `/platforms/line/*`, `/platforms/whatsapp/*` |
| `/mcp/*` | MCP 工具 | `/mcp/process-advisor`, `/mcp/report-agent` |

### 10.4 禁止隨意開 Port

**新規範**：未來任何新增的 Python 服務，必須先確認是否應整合進 unified_agents。

#### 允許獨立開 Port 的情況

1. 需要自己的非同步 Worker（Celery 模式）
2. 需要長時間運算的獨立行程
3. 與外部系統有特殊連線需求
4. 已經是既定獨立服務（aitask, bpa_mm_agent, mcp_tools）

#### 必須整合進 unified_agents 的情況

1. 工具類（weather, web_search, calculator...）
2. 平台整合類（LINE, WhatsApp, DingTalk...）
3. Agent 類（da, ka, memory, backup）

### 10.5 負載平衡原則

unified_agents 內的各模組可以未來獨立出去，不影響前端：

```
目前：
unified_agents (8011)
  ├── /platforms/line/*  → LINE Bot
  └── /tools/*           → Weather, WebSearch

未來負載過高時可拆分：
unified_agents (8011)              line-service (8012)
  └── /platforms/*  ──────────────→  /platforms/line/*
                                      /platforms/whatsapp/*
```

**關鍵**：Rust API Gateway 依照 URL path 轉發，拆分時只需改變轉發目標（`api/.env`），**前端與後端 Python 程式碼無需修改**。

### 10.6 Port 註冊表

| Port | Service | 用途 | 整合 |
|------|---------|------|------|
| 6000 | static | 桌面 App 安裝檔 hosting | 獨立 |
| 6500 | Rust API | API Gateway | - |
| 8001 | aitask | AI 任務編排 | 獨立 |
| 8004 | mcp_tools | MCP 工具執行 | 獨立 |
| 8005 | bpa_mm_agent | 物料管理流程 | 獨立 |
| 8011 | unified_agents | 統一入口 | ✅ |
| 8529 | ArangoDB | 資料庫 | - |
| 6333 | Qdrant | 向量檢索 | - |
| 8888 | SeaweedFS Filer | 統一檔案備份儲存 | - |
| 9333 | SeaweedFS Master | SeaweedFS叢集協調 | - |

### 10.7 新增 Service 檢查清單

新增 Python 服務前，必須確認：

- [ ] 這個服務屬於「獨立」還是「統一」？
- [ ] 如果是「統一」，路由前綴是什麼？
- [ ] Port 是否已被佔用？是否需要新增 Port 註冊？
- [ ] 是否需要更新 `api/.env`？
- [ ] 是否需要更新 AGENTS.md？

### 10.8 檔案備份儲存規範（SeaweedFS）

所有檔案備份統一使用 **SeaweedFS Filer REST API (port 8888)**，嚴禁直接寫入磁碟或使用其他儲存介面。

#### 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `SEAWEED_URL` | SeaweedFS Filer URL | `http://localhost:8888` |
| `SEAWEED_USER` | Filer 基本認證帳號 | `admin` |
| `SEAWEED_PASS` | Filer 基本認證密碼 | `admin123` |

#### 儲存路徑格式

| 用途 | 路徑格式 |
|------|----------|
| 任務對話檔案 | `sessions/{session_key}/{file_key}.{ext}` |
| 知識庫檔案 | `knowledge/{root_id}/{file_key}.{ext}` |
| LINE 多媒體 | `line/{platform}/{user_id}/{filename}` |

#### 上傳範例（Python）

```python
import httpx
import os

SEAWEED_URL = os.getenv("SEAWEED_URL", "http://localhost:8888")
SEAWEED_USER = os.getenv("SEAWEED_USER", "admin")
SEAWEED_PASS = os.getenv("SEAWEED_PASS", "admin123")

async def upload_to_seaweedfs(content: bytes, path: str) -> str:
    url = f"{SEAWEED_URL}/{path}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.put(url, content=content, auth=(SEAWEED_USER, SEAWEED_PASS))
        resp.raise_for_status()
    return url
```

#### 禁止事項

- ❌ 嚴禁使用 MinIO/S3 介面（port 8334）— 已廢棄
- ❌ 嚴禁直接寫入本地磁碟作為長期備份
- ❌ 嚴禁上傳到其他第三方儲存服務（除非明確業務需求）

### 10.9 標準工具編排框架（shared/tools/）

所有 Agent 的工具發現、調用、執行監督必須複用 `shared/tools/` 框架，**嚴禁每個 Agent 自行實作工具調用邏輯**。

#### 目錄結構

```
ai-services/shared/tools/
├── __init__.py      # 導出 ToolRegistry, ToolExecutionContext, ToolResult, ToolSource
├── registry.py      # ToolRegistry（工具發現/派發）、ToolDefinition、ToolExecutionContext
└── executors.py     # MCPToolExecutor、DataAgentExecutor、KnowledgeAgentExecutor、BuiltinExecutor
```

#### 核心類別

| 類別 | 職責 |
|------|------|
| `ToolRegistry` | 工具發現、LLM function schema 產生、執行派發 |
| `ToolExecutionContext` | 攜帶 user_id/session_id/trace_id，追蹤 tool call 上下文 |
| `ToolResult` | 工具執行結果（success/result/error/duration_ms） |
| `ToolSource` | 工具來源 enum（MCP/DATA_AGENT/KNOWLEDGE/BUILTIN） |

#### 使用方式

```python
from shared.tools import ToolRegistry, ToolExecutionContext
import uuid, json

# 1. 初始化 Registry（每個 service 只做一次）
registry = ToolRegistry()
await registry.initialize(
    mcp_tools_url="http://localhost:8004",
    data_agent_url="http://localhost:8003",
    knowledge_agent_url="http://localhost:8007",
)

# 2. 取得 LLM function calling schema
tools = registry.get_tools_for_llm()  # 傳給 Ollama / LLM 的 tools 參數

# 3. 執行工具
context = ToolExecutionContext(
    user_id="user123",
    session_id="session456",
    trace_id=f"{session_id}-{uuid.uuid4().hex[:8]}",
    auth_token="",
    correlation_id="tool-call-1",
)
result = await registry.execute("ka_search", {"query": "如何建立採購單"}, context)
# result.success, result.result, result.error
```

#### 工具來源

| Source | Executor | 用途 |
|--------|----------|------|
| `MCP` | `MCPToolExecutor` | MCP Tools 服務（`/tools` → `/execute`） |
| `DATA_AGENT` | `DataAgentExecutor` | NL→SQL 查詢（`/query/query`） |
| `KNOWLEDGE` | `KnowledgeAgentExecutor` | 知識庫 RAG（`/query`, `/search`） |
| `BUILTIN` | `BuiltinExecutor` | 內建工具（`current_time`, `session_summary`） |

#### 已有內建工具

| 工具名稱 | 來源 | 參數 | 說明 |
|----------|------|------|------|
| `da_query` | DATA_AGENT | `query: str` | 自然語言查詢資料 |
| `da_visualize` | DATA_AGENT | `query: str` | 查詢視覺化資料 |
| `ka_search` | KNOWLEDGE | `query: str` | 知識庫 RAG 檢索 |
| `ka_doc_retrieve` | KNOWLEDGE | `query: str` | 擷取知識庫文件內容 |
| `current_time` | BUILTIN | — | 取得目前 UTC 時間 |
| `session_summary` | BUILTIN | — | 取得 session 摘要 |

#### 禁止事項

- ❌ 嚴禁在 `agent.py` 裡自己寫 `httpx.post` 呼叫工具服務（應透過 ToolRegistry）
- ❌ 嚴禁每個 agent 自行實作工具執行邏輯
- ❌ 禁止直接 hardcode 工具 URL，應透過環境變數傳入 `initialize()`

#### 執行流程（Tool Loop）

每個 Agent 的對話循環應遵循以下流程：

```
輸入 →意圖判斷 → 路由
                  ↓
         ┌───────┴───────┐
         ↓               ↓
    direct_answer    tool_call
         ↓               ↓
    LLM 純回覆      執行工具迴圈
         ↓               ↓
         └───────┬───────┘
                 ↓
           儲存歷史 → 回覆
```

#### 輸出結構（ToolResult）

```python
class ToolResult(BaseModel):
    tool_name: str          # 工具名稱
    tool_call_id: str       # 本次呼叫 ID
    success: bool            # 是否成功
    result: object          # 成功時的結果（dict/list/str）
    error: str | None       # 失敗時的錯誤訊息
    duration_ms: int         # 執行耗時（毫秒）
    source: ToolSource      # 工具來源（MCP/DATA_AGENT/KNOWLEDGE/BUILTIN）
    trace_id: str | None    # 追蹤 ID
```

#### 執行失敗時的處理原則

- 工具執行失敗 → 仍回傳 `ToolResult`（`success=False`），由 LLM 決定如何處理
- LLM 可依據錯誤訊息重試或放棄
- 不得 silent swallow exception

---

### 10.10 標準工作編排框架（shared/orchestration/）

所有需要工作編排的 Agent，必須使用 `shared/orchestration/` 框架，嚴禁自行實作 LangGraph 圖。

#### 設計原則

| 原則 | 說明 |
|------|------|
| 狀態隔離 | `AgentState` 為最小共用狀態，各 Agent 可擴展 |
| 標準節點 | `router`、`llm`、`tool_executor`、`memory` 為標準節點 |
| 自訂節點 | 各 Agent 實作自己的意圖分類、知識庫搜尋等節點 |
| 嚴禁複製 | `aitask/graph/` 的節點實作不得複製到其他 Agent，應在 `shared/orchestration/` 定義標準介面 |

#### 目錄結構

```
ai-services/shared/orchestration/
├── __init__.py               # 導出 OrchestrationEngine, AgentState, AgentNode
├── state.py                   # AgentState 定義（session_id, user_id, messages, tool_results...）
├── engine.py                  # OrchestrationEngine（執行器，tool loop + state management）
├── nodes/
│   ├── __init__.py
│   ├── router.py             # 標準路由節點（action_plan 路由）
│   ├── llm_node.py           # 標準 LLM 呼叫節點（支援 function calling）
│   └── tool_executor.py      # 標準工具執行節點（呼叫 shared/tools/）
└── builder.py                 # AgentGraphBuilder（建構 LangGraph）
```

#### AgentState（最小共用狀態）

```python
class AgentState(TypedDict):
    session_id: str                           # Session 識別
    user_id: str                              # 用戶識別
    messages: Annotated[list[BaseMessage], add_messages]  # 對話歷史（LangGraph 自動合併）
    state_version: int                        # 狀態版本（每次更新 +1）
    # 工具相關
    tool_results: list[dict[str, Any]]        # 工具執行結果
    pending_tool_calls: list[dict[str, Any]]  # 待執行的 tool_calls
    # 擴展欄位（各 Agent 可自行擴展）
    extra: dict[str, Any]                     # 預留擴展
```

#### 執行流程

```
Agent 輸入
    ↓
OrchestrationEngine.run(session_id, user_id, user_message)
    ↓
┌─ 是否需要工具？ ──────────────────────────┐
│  是                                        │  否
│  ↓                                        ↓
│ LLM + tools schema → tool_calls        LLM 純回覆
│        ↓                                    ↓
│ ToolExecutor 執行工具                   回覆訊息
│        ↓                                    ↓
│ tool_results 寫入 state                  儲存歷史
│        ↓                                    ↓
│ LLM 根據結果繼續對話                       回傳
│ (最多 N 輪)
│        ↓
│ 回傳最終回覆
└────────────────────────────────────────────┘
```

#### 核心類別

| 類別 | 檔案 | 職責 |
|------|------|------|
| `AgentState` | `state.py` | 所有 Agent 共用的狀態結構 |
| `OrchestrationEngine` | `engine.py` | 執行 tool loop、管理 state、處理路由 |
| `AgentGraphBuilder` | `builder.py` | 幫各 Agent 建構 LangGraph |
| `router_node` | `nodes/router.py` | 根據 `action_plan` 路由到對應節點 |
| `llm_node` | `nodes/llm_node.py` | 標準 LLM 呼叫（含 function calling） |
| `tool_executor_node` | `nodes/tool_executor.py` | 標準工具執行（使用 `shared/tools/`） |

#### 使用方式（各 Agent）

```python
from shared.orchestration import (
    AgentGraphBuilder,
    OrchestrationEngine,
)

# 1. 定義自訂節點（意圖分類）
async def intent_classifier(state: AgentState) -> dict[str, Any]:
    # 分析 state["messages"][-1]，產生 action_plan
    return {
        "action_plan": "tool_call",
        "matched_intent": {...},
        "state_version": state["state_version"] + 1,
    }

# 2. 建構圖
builder = AgentGraphBuilder()
builder.add_node("classify_intent", intent_classifier)
builder.add_node("tool_executor", tool_executor_node)  # 標準節點
builder.add_node("chat_responder", chat_responder_node)
builder.set_entry("classify_intent")
builder.add_edge("classify_intent", "router")
builder.add_conditional_edges("router", route_by_action, {...})
graph = builder.build()

# 3. 執行
engine = OrchestrationEngine(graph)
result = await engine.run(
    session_id="sess_123",
    user_id="user_456",
    user_message="查詢庫存",
    tools=registry.get_tools_for_llm(),
)
# result["messages"][-1] 為最終回覆
```

#### OrchestrationEngine.run() 輸入/輸出

**輸入（Input）**：

| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `session_id` | `str` | ✅ | Session 識別 |
| `user_id` | `str` | ✅ | 用戶識別 |
| `user_message` | `str` | ✅ | 使用者的新訊息 |
| `tools` | `list[dict]` | ❌ | LLM function calling schema，若有工具則啟用 tool loop |
| `extra` | `dict` | ❌ | 額外 state 擴展 |

**輸出（Output）**：

```python
class AgentRunResult(TypedDict):
    session_id: str                                    # Session ID
    response: str                                      # 最終回覆文字
    messages: list[BaseMessage]                        # 更新後的訊息歷史
    tool_results: list[dict[str, Any]]                 # 所有工具執行結果
    state_version: int                                 # 最終狀態版本
    trace_id: str                                      # 本次追蹤 ID
    success: bool                                       # 是否成功完成
    error: str | None                                  # 若失敗，錯誤原因
```

#### 禁止事項

- ❌ 嚴禁在 Agent 內直接建立 LangGraph StateGraph（應用 `AgentGraphBuilder`）
- ❌ 嚴禁在 Agent 內自己寫 tool loop（應用 `OrchestrationEngine.run()`）
- ❌ `aitask/graph/` 的節點實作不得直接複製到其他 Agent
- ❌ State 不得直接寫入，必須透過節點回傳 dict 更新

---

## 11. Agent 建立指南

本指南說明如何建立一個使用 `shared/orchestration/` 框架的標準 Agent。

### 11.1 目錄結構規範

每個 Agent 應有獨立目錄，統一放在 `bpa/` 或 `agents/` 下：

```
ai-services/
├── bpa/
│   └── my_agent/           # 每個 Agent 獨立目錄
│       ├── __init__.py
│       ├── main.py          # FastAPI 入口，掛載 router
│       ├── router.py         # API 路由定義
│       ├── agent.py          # Agent 核心邏輯（意圖判斷、RAG、工具迴圈）
│       ├── config.py        # 環境變數與設定讀取
│       └── nodes/           # Agent 專用節點（可選）
│           └── my_node.py
```

### 11.2 建立步驟

#### Step 1：建立 Service 入口（main.py）

```python
from fastapi import FastAPI
from my_agent.router import router

app = FastAPI()
app.include_router(router, prefix="/my-agent", tags=["My Agent"])
```

#### Step 2：定義 Router（router.py）

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class ChatRequest(BaseModel):
    agent_key: str
    session_id: str
    message: str
    user_id: str | None = None
    platform: str = "web"

@router.post("/chat")
async def chat(request: ChatRequest):
    # 呼叫 agent.py 的 chat_with_agent()
    pass
```

#### Step 3：實作 Agent 邏輯（agent.py）

```python
# 1. 必要的 helper 函式（意圖判斷、RAG 等 Agent 特定邏輯）
async def detect_intent(query: str) -> dict | None:
    # 调用 unified_agents 的 intent RAG
    pass

async def build_rag_context(query: str) -> str:
    # 调用 unified_agents 的 hybrid search
    pass

# 2. 工具迴圈（使用 shared/orchestration.nodes.tool_executor_node）
async def chat_with_agent(
    query: str,
    session_id: str,
    agent_config: dict,
    conversation_history: list[dict],
    user_id: str = "anonymous",
) -> str:
    # 組合 system prompt + conversation history
    # 初始化 shared/tools ToolRegistry（如需要工具）
    # 執行 LLM 呼叫
    # 如有 tool_calls，呼叫 tool_executor_node
    # Tool results 附加到 messages，繼續對話
    # 最多 max_tool_loops 輪
    pass
```

#### Step 4：設定環境變數（config.py）

```python
import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
INTENT_RAG_URL = os.getenv("INTENT_RAG_URL", "http://localhost:8011/da/intent-rag")
HYBRID_RAG_URL = os.getenv("HYBRID_RAG_URL", "http://localhost:8011/ka/hybrid")
MCP_TOOLS_URL = os.getenv("MCP_TOOLS_URL", "http://localhost:8004")
DATA_AGENT_URL = os.getenv("DATA_AGENT_URL", "http://localhost:8003")
KNOWLEDGE_AGENT_URL = os.getenv("KNOWLEDGE_AGENT_URL", "http://localhost:8007")
```

### 11.3 Agent 等級分類

| 等級 | 說明 | 所需框架 |
|------|------|----------|
| **L1 純聊天** | 無工具，只能 LLM 對話 | 直接 call LLM |
| **L2 RAG 增強** | L1 + 意圖判斷 + 知識庫 RAG | `detect_intent()` + `hybrid_search()` |
| **L3 工具呼叫** | L2 + 工具執行 | `shared/tools/` ToolRegistry + `tool_executor_node` |
| **L4 完整編排** | L3 + 工作編排 + 多步任務 | `shared/orchestration/` OrchestrationEngine |

### 11.4 對話歷史管理

所有 Agent 的對話歷史應統一使用 `shared/conversation/`：

```python
from shared.conversation import ConversationStorage, QueryEngine

# 儲存
storage = ConversationStorage()
await storage.save_message(
    session_id=session_id,
    platform=platform,
    role="user" | "assistant",
    message="...",
)

# 查詢
engine = QueryEngine()
history = await engine.get_history(session_id, limit=20)
```

### 11.5 port 分配規則

| 情境 | 做法 |
|------|------|
| 獨立 Agent（如 aitask、bpa_mm_agent） | 獨立 port（如 8001、8005） |
| 小型 Agent（無長時間運算） | 整合進 unified_agents（8011） |
| 工具類 | 放在 `tools/` 目錄，mount 到 `/mcp/` |

### 11.6 範例：升級現有 Agent 到 L3

假設現有 `my_agent/agent.py` 已有 `chat_with_agent()` 但工具是自己寫的 httpx 呼叫：

**Before（❌ 禁止）**：
```python
async def execute_tool(tool_name: str, args: dict):
    if tool_name == "ka_search":
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{KA_URL}/search", json=args)  # 自己寫！
```

**After（✅ 正確）**：
```python
from shared.tools import ToolRegistry, ToolExecutionContext
import uuid

async def execute_tools(tool_calls: list[dict], session_id: str, user_id: str):
    registry = ToolRegistry()
    await registry.initialize(
        mcp_tools_url=MCP_TOOLS_URL,
        data_agent_url=DATA_AGENT_URL,
        knowledge_agent_url=KNOWLEDGE_AGENT_URL,
    )
    results = []
    for i, call in enumerate(tool_calls):
        context = ToolExecutionContext(
            user_id=user_id,
            session_id=session_id,
            trace_id=f"{session_id}-{uuid.uuid4().hex[:8]}",
            auth_token="",
            correlation_id=call.get("id", f"tool-call-{i}"),
        )
        result = await registry.execute(call["name"], call["arguments"], context)
        results.append(result)
    return results
```

### 11.7 程式碼品質檢查清單

建立 Agent 後，確保通過以下檢查：

- [ ] `ruff check my_agent/` — 無 error
- [ ] `mypy my_agent/ --ignore-missing-imports` — 無 type error
- [ ] 環境變數皆從 `os.getenv()` 讀取，無 hardcode URL
- [ ] 所有 API 呼叫皆有 try/except，不得 silent swallow
- [ ] 檔案表頭有 `@file` + `@lastUpdate` + `@author` docstring
- [ ] 匯入 `shared/conversation/` 而非自己實作歷史儲存

### 11.8 新增 Port 的審批流程

新增獨立 port 的 Agent 必須：

1. 在 `AGENTS.md` 的 Port 註冊表（10.6）新增記錄
2. 在 `api/.env` 新增對應 URL 環境變數
3. 確認不是「應該整合進 unified_agents」的服務
4. 更新 `start.sh` 加入健康檢查（如有必要）

---

## 修改歷程

| 日期       | 版本  | 更新者       | 變更內容                                                             |
| ---------- | ----- | ------------ | -------------------------------------------------------------------- |
| 2026-04-21 | 1.11.0 | Daniel Chung | 新增 Agent 建立指南（11章）；完善 shared/tools/ 與 shared/orchestration/ 框架文件 |
| 2026-04-21 | 1.10.0 | Daniel Chung | 新增 shared/tools/ 標準工具編排框架；新增 shared/orchestration/ 標準工作編排框架（LangGraph StateMachine） |
| 2026-04-19 | 1.9.0 | Daniel Chung | 新增 Service Architecture 原則，定義獨立服務與統一入口，規範 Port 分配；新增 ArangoDB PATCH vs PUT 安全操作規範（避免文件替換導致資料遺失） |
| 2026-03-27 | 1.5.0 | Daniel Chung | 新增 Temporary Files Management 規範，禁止在根目錄放置臨時檔案，統一使用 `.tmp/` 目錄 |
| 2026-03-25 | 1.4.1 | Daniel Chung | 新增資料庫資料修改必須事先確認規則                                    |
| 2026-03-19 | 1.4.0 | Daniel Chung | 新增 Safe Operation Rules，破壞性操作必須事先取得同意                |
| 2026-03-18 | 1.3.0 | Daniel Chung | 新增 Tauri Desktop 桌面殼開發規範                                    |
| 2026-03-18 | 1.2.0 | Daniel Chung | 新增 API 開發規範章節，強制要求遵循 API Specification                |
| 2026-03-18 | 1.1.0 | Daniel Chung | 新增 Python mypy/ruff 規範、Module Size Guidelines、測試文件放置規範 |
| 2026-03-17 | 1.0.0 | Daniel Chung | 初始版本，新增開發規範、檔頭標準、重複檢查、刪除流程                 |
