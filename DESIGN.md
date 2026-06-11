# ABC Desktop Design System

## Visual Theme & Atmosphere

**Mood**: 專業企業級管理系統，深色外殼提供沉浸式工作體驗，淺色內容區確保長時間閱讀舒適度。

**Density**: 中等密度，資訊豐富但不擁擠，適合 enterprise 應用場景。

**Design Philosophy**: 
- 外殼固定深色，內容區支援亮/暗主題切換
- 雙層架構：Shell (固定) + Content (可切換)
- 使用 Ant Design 6.x 作為 UI 框架基礎

---

## Color Palette & Roles

### Brand Colors (內容主題色)

| Name | Hex | Role |
|------|-----|------|
| Primary | `#3b82f6` | 主要按鈕、連結、選中狀態 (Dark) / `#1e40af` (Light) |
| Success | `#22c55e` | 成功狀態、反饋 |
| Warning | `#f59e0b` | 警告狀態 |
| Error | `#ef4444` (Dark) / `#dc2626` (Light) | 錯誤狀態 |
| Info | `#3b82f6` | 資訊提示 |

### Content Background Colors

| Name | Dark Mode | Light Mode | Role |
|------|-----------|------------|------|
| Page Background | `#0a0f1a` | `#e8eaed` | 頁面底層背景 |
| Content Background | `#0f172a` | `#ffffff` | 內容頁容器背景 |
| Container Background | `#1e293b` | `#ffffff` | Table/Card/Tabs 容器 |
| Text Primary | `#f1f5f9` | `#030213` | 主文字顏色 |
| Text Secondary | `#8892a0` | `#64748b` | 次要文字 |

### Shell Colors (外殼 - 固定深色)

| Name | Hex | Role |
|------|-----|------|
| Sider Background | `#1e293b` | 側邊欄背景 |
| Header Background | `#0f172a` | 頂部列背景 |
| Menu Item Color | `#94a3b8` | 選單項目預設文字 |
| Menu Item Hover | `#334155` | 選單項目懸停背景 |
| Menu Item Selected | `#3b82f6` | 選單項目選中背景 |
| Menu Selected Text | `#ffffff` | 選單項目選中文字 |
| Logo Color | `#ffffff` | Logo 顏色 |
| Sider Border | `#334155` | 側邊欄邊框 |

### Chat Interface Colors

| Name | Dark Mode | Light Mode | Role |
|------|-----------|------------|------|
| Chat Input BG | `#1e293b` | `#f1f5f9` | 輸入框背景 |
| User Bubble | `#1e3a8a` | `#dbeafe` | 使用者訊息氣泡 |
| Assistant Bubble | `#1e293b` | `#e2e8f0` | 助理訊息氣泡 |

### Component Colors

| Name | Dark Mode | Light Mode | Role |
|------|-----------|------------|------|
| Table Header BG | `#1a2235` | `#f0f4ff` | 表格標題背景 |
| Table Row Hover | `#1a2744` | `#e6f0ff` | 表格列懸停 |
| Table Expanded Row | `#0a1120` | `#f0f4ff` | 表格展開列 |
| Icon Default | `#8892a0` | `#64748b` | 圖示預設顏色 |
| Icon Hover | `#ffffff` | `#1e40af` | 圖示懸停顏色 |

---

## Typography Rules

**Font Family**:
```
-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif
```

**Hierarchy**:
| Element | Size | Weight | Line Height |
|---------|------|--------|-------------|
| Page Title | 20px | 600 | 1.4 |
| Section Title | 16px | 600 | 1.4 |
| Body Text | 14px | 400 | 1.5 |
| Secondary Text | 12px | 400 | 1.4 |
| Small Text | 12px | 400 | 1.4 |

---

## Component Stylings

### Buttons

**Primary Button** (Send/Confirm):
- Dark: Background `#3b82f6`, Hover `#2563eb`, Text `#ffffff`
- Light: Background `#1e40af`, Hover `#1e3a8a`, Text `#ffffff`

**Clear Button**:
- Background `#f59e0b`, Hover `#d97706`, Text `#030213`

**Link Button**:
- Color `#3b82f6`, Hover underline

### Cards

**Border Radius**: `10px`

**Shadows**:
```
Default: 0 6px 24px rgba(100, 80, 220, 0.35)
Hover:   0 12px 40px rgba(100, 80, 220, 0.50)
```

### Tables

**Header**:
- Background: `#1a2235` (Dark) / `#f0f4ff` (Light)
- Text: Bold, `#f1f5f9` (Dark) / `#030213` (Light)

**Row Hover**:
- Background: `#1a2744` (Dark) / `#e6f0ff` (Light)

### Form Inputs

- Background: `#1e293b` (Dark) / `#f1f5f9` (Light)
- Border: `#334155` (Dark) / `#d1d5db` (Light)
- Focus Border: `#3b82f6`
- Border Radius: `10px`

### Tooltips

- Background: `#1e293b`
- Text: `#f1f5f9`
- Opacity: 88%
- Border Radius: `6px`

---

## Layout Principles

### Shell Layout (Fixed Dark)

```
+------------------+----------------------------------------+
|                  |                                        |
|    SIDEBAR       |              HEADER                    |
|    (256px)       |              (64px height)             |
|                  |----------------------------------------|
|  - Logo          |                                        |
|  - Menu Items    |          CONTENT AREA                  |
|  - Collapse Btn  |          (scrollable)                 |
|                  |                                        |
+------------------+----------------------------------------+
```

### Content Spacing Scale

| Token | Value |
|-------|-------|
| xs | 4px |
| sm | 8px |
| md | 16px |
| lg | 24px |
| xl | 32px |
| 2xl | 48px |

### Grid System

- Content Max Width: `1200px`
- Sidebar Width: `256px` (collapsible to `80px`)
- Header Height: `64px`

---

## Depth & Elevation

### Shadows (Content Layer)

| Level | Dark Mode | Light Mode |
|-------|-----------|------------|
| sm | `0 2px 8px rgba(0, 0, 0, 0.3)` | `0 2px 8px rgba(0, 0, 0, 0.06)` |
| md | `0 6px 24px rgba(100, 80, 220, 0.35)` | `0 6px 24px rgba(30, 64, 175, 0.25)` |
| lg | `0 12px 40px rgba(100, 80, 220, 0.50)` | `0 12px 40px rgba(30, 64, 175, 0.35)` |

### Shell Shadows

| Element | Shadow |
|---------|--------|
| Header | `0 2px 8px rgba(0, 0, 0, 0.4)` |
| Sider | `2px 0 8px rgba(0, 0, 0, 0.3)` |

---

## Do's and Don'ts

### ✅ DO

- 使用 `useTheme()` hook 取得當前主題 tokens
- 使用 `useShellTokens()` 取得外殼樣式（側邊欄、頂部列）
- 使用 `useContentTokens()` 取得內容區樣式
- 使用 Ant Design 的 `theme.useToken()` 獲取框架層級 tokens
- 支援 `ThemeMode: 'light' | 'dark' | 'system'` 三種模式

### ❌ DON'T

- 不要硬編碼顏色值，應使用 tokens
- 不要直接修改 Shell 層的樣式（固定深色）
- 不要假設內容區一定是亮色或暗色
- 不要忽略 `system` 主題偏好設定

---

## Responsive Behavior

### Breakpoints

| Name | Width | Description |
|------|-------|-------------|
| xs | < 576px | Mobile |
| sm | 576px - 768px | Tablet Portrait |
| md | 768px - 992px | Tablet Landscape |
| lg | 992px - 1200px | Desktop |
| xl | > 1200px | Large Desktop |

### Sidebar Behavior

- **Desktop (> 992px)**: 固定顯示，可折疊
- **Tablet (768px - 992px)**: 預設折疊，點擊展開
- **Mobile (< 768px)**: 側滑選單

### Touch Targets

- Minimum: `44px × 44px`
- Button padding: `12px 24px`

---

## Agent Prompt Guide

### Quick Color Reference

```markdown
# ABC Desktop Theme Tokens

## Dark Mode (Default Shell + Dark Content)
Primary: #3b82f6
Background: #0f172a
Text: #f1f5f9
Surface: #1e293b

## Light Mode (Shell + Light Content)
Primary: #1e40af
Background: #ffffff
Text: #030213
Surface: #e8eaed

## Shell (Fixed)
Sider: #1e293b
Header: #0f172a
Menu Selected: #3b82f6
```

### Ready-to-Use Prompts

```
"Build a page for ABC Desktop that displays user management with:
- A data table showing user list (name, role, status)
- Action buttons for edit/delete
- A modal form for creating/editing users
- Use dark shell theme with content area following the current active theme"

"Create a settings panel that:
- Has collapsible sections
- Uses cards for grouping related settings
- Includes form inputs (text, select, switch)
- Follows ABC Desktop's design tokens from DESIGN.md"
```

---

## Technical Implementation

### Theme Provider Stack

```
AppThemeProvider
├── ShellTokensProvider (fixed dark)
└── ContentTokensProvider (switchable light/dark)
```

### Key Files

| File | Purpose |
|------|---------|
| `src/contexts/AppThemeProvider.tsx` | 主題上下文提供者 |
| `src/styles/theme/tokens.ts` | 預設 tokens 定義 |
| `src/components/ThemeTokenEditor.tsx` | Token 編輯表單 |
| `src/pages/ThemeTemplateManagement.tsx` | 樣板管理頁面 |
| `src/services/api.ts` | ThemeTemplate API 定義 |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/theme-templates` | 取得所有樣板 |
| GET | `/api/v1/theme-templates/:key` | 取得單個樣板 |
| POST | `/api/v1/theme-templates` | 建立樣板 |
| PUT | `/api/v1/theme-templates/:key` | 更新樣板 |
| DELETE | `/api/v1/theme-templates/:key` | 刪除樣板 |
| PUT | `/api/v1/theme-templates/:key/activate` | 啟用樣板 |

---

## Preview

### Preview Pages

Each template includes a `preview.html` showing:
- Color swatches with hex values
- Typography scale
- Button states (default, hover, disabled)
- Card components with shadows
- Form inputs
- Table styles

To generate preview:
1. Go to Theme Template Management
2. Select any template
3. Click "Preview" to see visual catalog
