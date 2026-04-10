---
lastUpdate: 2026-04-10 22:35:00
author: Daniel Chung
version: 1.7.0
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

#### 硬編碼避免清單

| 類型     | 正確做法                                 |
| -------- | ---------------------------------------- |
| API URL  | 存放於環境變數或配置檔                   |
| 功能開關 | 存放於資料庫 `system_params`           |
| 權限配置 | 存放於資料庫 `roles` / `permissions` |
| 菜單配置 | 存放於資料庫 `functions`               |
| 常數配置 | 存放於 `src/config/` 或環境變數        |

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
.venv/bin/python -m uvicorn aitask.main:app --port 8001 --host 0.0.0.0

# Data Agent (port 8003) - NL→SQL 查詢
.venv/bin/python -m uvicorn data_agent.main:app --port 8003 --host 0.0.0.0

# MCP Tools (port 8004) - MCP 工具執行
.venv/bin/python -m uvicorn mcp_tools.main:app --port 8004 --host 0.0.0.0

# BPA MM Agent (port 8005) - 物料管理流程
.venv/bin/python -m uvicorn bpa.mm_agent.main:app --port 8005 --host 0.0.0.0

# Knowledge Agent (port 8007) - 知識庫 RAG
.venv/bin/python -m uvicorn knowledge_agent.main:app --port 8007 --host 0.0.0.0

# Memory Agent (port 8008) - AI 增強記憶
.venv/bin/python -m uvicorn memory_agent.main:app --port 8008 --host 0.0.0.0

# Backup Agent (port 8010)
.venv/bin/python -m uvicorn backup_agent.main:app --port 8010 --host 0.0.0.0
```

#### 快速重啟單一服務

```bash
# 找到並 kill 舊进程
pkill -f "uvicorn aitask.main:app"

# 使用 .venv 重啟
cd ai-services
nohup .venv/bin/python -m uvicorn aitask.main:app --port 8001 --host 0.0.0.0 > .tmp/aitask.log 2>&1 &
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
HOST=0.0.0.0

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

## 修改歷程

| 日期       | 版本  | 更新者       | 變更內容                                                             |
| ---------- | ----- | ------------ | -------------------------------------------------------------------- |
| 2026-03-27 | 1.5.0 | Daniel Chung | 新增 Temporary Files Management 規範，禁止在根目錄放置臨時檔案，統一使用 `.tmp/` 目錄 |
| 2026-03-25 | 1.4.1 | Daniel Chung | 新增資料庫資料修改必須事先確認規則                                    |
| 2026-03-19 | 1.4.0 | Daniel Chung | 新增 Safe Operation Rules，破壞性操作必須事先取得同意                |
| 2026-03-18 | 1.3.0 | Daniel Chung | 新增 Tauri Desktop 桌面殼開發規範                                    |
| 2026-03-18 | 1.2.0 | Daniel Chung | 新增 API 開發規範章節，強制要求遵循 API Specification                |
| 2026-03-18 | 1.1.0 | Daniel Chung | 新增 Python mypy/ruff 規範、Module Size Guidelines、測試文件放置規範 |
| 2026-03-17 | 1.0.0 | Daniel Chung | 初始版本，新增開發規範、檔頭標準、重複檢查、刪除流程                 |
