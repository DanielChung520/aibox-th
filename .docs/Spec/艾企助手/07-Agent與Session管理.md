---
lastUpdate: 2026-06-15 22:00:00
author: Daniel Chung
version: 1.0.0
status: 初版
---

# 07 — Agent 與 Session 管理

> 艾企助手的 Agent 切換、Session 列表、自訂頭像與辨識色系統

---

## TL;DR

艾企助手目前為「單一對話體」，本規格將其升級為**多 Agent 架構**：

- **Agent 選擇**：右鍵浮動按鈕 → 快速切換不同 Agent
- **Session 管理**：點擊時鐘按鈕 → 列出/切換對話 Session
- **自訂識別**：每個 Agent 可設定自訂頭像 + 辨識色
- **Session → Agent 綁定**：每個 Session 綁定一個 Agent，切換 Agent 時只顯示對應 Sessions

---

## 1. 核心架構

### 1.1 Agent → Session 綁定關係

```
Agent (agentApi.list)
├── _key, name, icon, color, llm_model
│
└── Sessions (aiqChatStore.sessions filtered by agent_key)
    ├── Session A: { agent_key: "ai-assistant", title: "需求分析", ... }
    ├── Session B: { agent_key: "ai-assistant", title: "資料查詢", ... }
    └── Session C: { agent_key: "data-agent",  title: "SQL 優化", ... }
```

### 1.2 資料流

```
右鍵 FAB → Agent 選單 → 選 Agent
                          ├── 切換 activeAgent 狀態
                          ├── 更新 Drawer Header（頭像 + 顏色 + 名稱）
                          └── 載入該 Agent 的 Sessions

點擊時鐘按鈕 → Session 列表
                  ├── 顯示當前 Agent 的所有 Sessions
                  ├── 點擊 Session → loadSessionMessages(key)
                  └── [+ 新對話] → createSession({ agent_key })

發送訊息 → aiqChatStore.sendMessage()
             ├── 從 activeAgent.llm_model 解析 provider:model
             └── Session 自動綁定當前 agent_key
```

---

## 2. Agent 選擇（右鍵浮動按鈕）

### 2.1 觸發方式
- **左鍵**點擊：切換 Drawer（維持現有）
- **右鍵**點擊：彈出 Agent 選單（`onContextMenu`）
- 選單外點擊：關閉

### 2.2 Agent 選單 UI
```
┌─────────────────────────────┐
│  切換 AI 助手                │
│                             │
│  ● AI 助理         🤖 公用  │ ← 高亮 + 勾選
│  ○ 業務小秘        🛠️ 公用  │
│  ○ 數據分析師      📊 公用  │
│  ─────────────────────────  │
│  ○ 我的客製化 Agent 🔒 私有 │
│                             │
│  [⚙️ 管理 Agent]            │
└─────────────────────────────┘
```

### 2.3 實作
- FAB 新增 `onContextMenu` handler
- Portal 方式渲染 AgentMenu 跟隨按鈕位置
- Agent 資料來自 `agentApi.list()`

---

## 3. Session 列表（時鐘按鈕）

### 3.1 Header 按鈕
```
┌──────────────────────────────────────────────┐
│ [🤖] AI 助理    [🕐] [+ 新對話] [管理] [✕]  │
│                    ↑                         │
│              時鐘按鈕 — 點擊展開 Session 列表    │
└──────────────────────────────────────────────┘
```

### 3.2 Session 列表 UI（Dropdown 面板）
```
┌─────────────────────────────────────┐
│ 📋 對話歷史                    [+ 新對話] │
│─────────────────────────────────────│
│ 今日                                  │
│ ├ 需求分析與報價              10:32   │
│ ├ 客戶資料查詢                09:15   │
│ 昨天                                  │
│ ├ 系統參數配置                16:20   │
│ 更早                                  │
│ ├ 資料庫 Schema 設計         6/12    │
└─────────────────────────────────────┘
```

### 3.3 Session 操作
- 點擊 Session → `loadSessionMessages(key)`
- [+ 新對話] → `createSession({ agent_key })`
- 右鍵/長按 → 重新命名 / 刪除

---

## 4. 架構變更

### 4.1 Session 新增 agent_key
```typescript
interface ChatSession {
  _key: string;
  title: string | null;
  agent_key?: string;        // ← 新增
  provider: string;
  model: string;
  // ...
}
```

### 4.2 AIAssistantDrawer State
```typescript
const [agents, setAgents] = useState<Agent[]>([]);
const [activeAgent, setActiveAgent] = useState<Agent | null>(null);
const [showAgentMenu, setShowAgentMenu] = useState(false);
const [showSessionList, setShowSessionList] = useState(false);
```

### 4.3 Header 動態顯示
- `activeAgent = null` → `[🤖] 艾企 AI 助手`
- `activeAgent = {...}` → `[{icon}] {name}` + 辨識色條

---

## 5. 辨識色系統

```typescript
const AGENT_COLORS = ['#3b82f6','#10b981','#8b5cf6','#f59e0b','#ef4444','#06b6d4','#ec4899','#84cc16'];

function getAgentColor(agent: Agent): string {
  if (agent.color) return agent.color;
  const hash = agent.name.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  return AGENT_COLORS[hash % AGENT_COLORS.length];
}
```

應用位置：右鍵選單左側色條、Header Avatar 外圈色環、Session title 色點、FAB 外圈色暈。

---

## 6. 向後相容

- Agent API 不可用或空陣列 → 降級為現有單一模式
- Session 無 `agent_key` → 歸類為 `default`，在所有 Agent 切換時都顯示

---

## 7. 檔案變更清單

| 檔案 | 動作 |
|------|------|
| `src/components/FloatingAssistantButton.tsx` | 修改 — 新增 onContextMenu |
| `src/components/AIAssistantDrawer.tsx` | 修改 — 時鐘按鈕 + agent-aware header |
| `src/components/AIAssistantDrawer.css` | 修改 — 新元件樣式 |
| `src/components/AIAssistantDrawer/AgentMenu.tsx` | **新增** |
| `src/components/AIAssistantDrawer/SessionListPanel.tsx` | **新增** |
| `src/services/api.ts` | 修改 — ChatSession agent_key |
| `src/stores/chatStore.ts` | 修改 — createSession 接受 agentKey |
| `src/services/agentColor.ts` | **新增** — 辨識色工具 |

---

## 8. 實作順序

| 階段 | 任務 |
|------|------|
| **P0** | Agent 右鍵選單 |
| **P0** | 時鐘按鈕 + Session 列表面板 |
| **P1** | Session → Agent 綁定 |
| **P1** | Header 動態顯示 |
| **P2** | 辨識色系統 |
| **P2** | Session 時間分組 |
| **P3** | Session 重新命名/刪除 |
| **P3** | 降級相容 |
