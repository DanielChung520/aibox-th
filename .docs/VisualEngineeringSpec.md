---
lastUpdate: 2026-04-16 10:00:00
author: Daniel Chung
version: 1.0.0
---

# 視覺工程規範 (Visual Engineering Specification)

## 概述

本規範定義 ABC Desktop 專案中所有視覺/樣式相關工作的標準流程。

---

## 1. 觸發條件

當任務涉及以下任一項目時，**必須**呼叫 `visual-engineering` agent：

| 條件 | 範例 |
|------|------|
| 新增或修改頁面樣式 | 建立新頁面、修改現有頁面外觀 |
| UI 組件開發 | 按鈕、卡片、表單、表格等視覺組件 |
| 響應式設計 | 適配不同螢幕尺寸、折疊選單 |
| 主題/配色調整 | 修改顏色、陰影、圓角等 Design Tokens |
| CSS 動畫/過渡 | 按鈕 hover 效果、頁面切換動畫 |
| 圖示/插圖整合 | 新增 icon、使用 SVG/圖片 |

---

## 2. 必須參考的檔案

### 2.1 DESIGN.md (設計系統文檔)

位置：`./DESIGN.md`

AI Agent 必須閱讀此檔案以了解：
- 雙層主題架構 (Shell + Content)
- 顏色調色盤與語意化命名
- 字體階層
- 組件樣式規範
- 陰影與深度系統
- 響應式斷點

### 2.2 現有主題程式碼

| 檔案 | 用途 |
|------|------|
| `src/contexts/AppThemeProvider.tsx` | 主題 Provider，定義 `useTheme()`, `useShellTokens()`, `useContentTokens()` |
| `src/styles/theme/tokens.ts` | 預設 Tokens 數值 |
| `src/components/ThemeTokenEditor.tsx` | Token 編輯表單元件 |
| `src/pages/ThemeTemplateManagement.tsx` | 樣板管理頁面 |

---

## 3. 雙層主題架構

### 3.1 Shell 層 (固定深色)

- **用途**：側邊欄、頂部列
- **特點**：固定深色，不可切換
- **取得方式**：`useShellTokens()`

### 3.2 Content 層 (可切換)

- **用途**：頁面內容區域
- **特點**：支援 Light / Dark / System 三種模式
- **取得方式**：`useContentTokens()`

---

## 4. 顏色使用規範

### 4.1 ✅ 正確做法

```tsx
import { useContentTokens } from '../contexts/AppThemeProvider';

function MyComponent() {
  const tokens = useContentTokens();
  
  // 使用 tokens 中的顏色，自動適配當前主題
  const style = {
    backgroundColor: tokens.contentBg,
    color: tokens.colorTextBase,
  };
}
```

### 4.2 ❌ 禁止做法

```tsx
// 禁止：硬編碼顏色值
const style = { backgroundColor: '#3b82f6' };

// 禁止：直接使用 CSS 變數
const style = { backgroundColor: 'var(--primary-color)' };

// 禁止：假設固定主題
const bg = isDark ? '#0f172a' : '#ffffff';
```

---

## 5. UI 組件開發規範

### 5.1 按鈕

**Primary Button**：
- Dark Mode: Background `#3b82f6`, Hover `#2563eb`
- Light Mode: Background `#1e40af`, Hover `#1e3a8a`

**Clear Button**：
- Background `#f59e0b`, Hover `#d97706`

### 5.2 卡片

- Border Radius: `10px`
- Default Shadow: `0 6px 24px rgba(100, 80, 220, 0.35)`
- Hover Shadow: `0 12px 40px rgba(100, 80, 220, 0.50)`

### 5.3 表格

- Header Background: `#1a2235` (Dark) / `#f0f4ff` (Light)
- Row Hover: `#1a2744` (Dark) / `#e6f0ff` (Light)

### 5.4 表單輸入框

- Border Radius: `10px`
- Focus Border: `#3b82f6`

---

## 6. 響應式斷點

| 名稱 | 寬度 | 說明 |
|------|------|------|
| xs | < 576px | Mobile |
| sm | 576px - 768px | Tablet Portrait |
| md | 768px - 992px | Tablet Landscape |
| lg | 992px - 1200px | Desktop |
| xl | > 1200px | Large Desktop |

---

## 7. 執行流程

```
1. 收到視覺/樣式相關任務
2. 立即呼叫 visual-engineering agent，確保傳入：
   - prompt: 任務描述
   - load_skills: ['frontend-ui-ux']
   - 附上 DESIGN.md 內容摘要
3. 由 visual-engineering agent 完成視覺工作
4. 由 build agent 整合到專案中
```

---

## 8. 委派 Prompt 範本

```typescript
task(
  category="visual-engineering",
  load_skills=["frontend-ui-ux"],
  prompt=`任務：{任務描述}

規範文件：
- 設計系統：./DESIGN.md
- UI 框架：Ant Design 6.x
- 主題：雙層架構 (Shell 固定深色 + Content 可切換亮/暗)
- 現有 Token 定義：src/styles/theme/tokens.ts

請 visual-engineering agent：
1. 根據 DESIGN.md 規範設計
2. 使用 useShellTokens() / useContentTokens() 取得主題 tokens
3. 支援亮/暗主題切換
4. 使用 Ant Design 組件
5. 遵循響應式斷點規範
`,
)
```

---

## 9. 常見錯誤避免

| 錯誤 | 正確做法 |
|------|----------|
| 硬編碼顏色 | 使用 `useContentTokens()` 或 `useShellTokens()` |
| 假設固定主題 | 使用 `effectiveTheme` 或 `themeMode` 判斷 |
| 直接修改 Shell 樣式 | Shell 層固定深色，不應修改 |
| 忽略系統主題偏好 | 使用 `ThemeMode.system` 讓使用者設定生效 |

---

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-16 | 1.0.0 | Daniel Chung | 初始版本 |
