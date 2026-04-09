# AI-Box 記憶系統規格書

> **文件名**: AI-Box 記憶系統規格書
> **版本**: 1.0.0
> **創建日期**: 2026-04-06
> **作者**: Daniel Chung
> **最後更新**: 2026-04-06 11:20:10

---

## 1. 概述

### 1.1 設計目標

AI-Box 記憶系統旨在實現一個**類人記憶的 AI 增強系統**，模擬人類記憶的層次性、主動性和選擇性。系統不僅儲存知識，更要讓 AI 具備運用知識達成目標的**智慧**。

### 1.2 設計原則

| 原則 | 說明 |
|------|------|
| **關注點分離** | 即時交互與異步學習分離，低延遲與深度分析分離 |
| **封閉類型系統** | 明確定義「可記憶」與「不可記憶」的邊界 |
| **安全第一** | 敏感資訊雙層防護，路徑安全雙重驗證 |
| **可演化** | 支援定期整理與模型持續優化 |

### 1.3 參考文獻

- [Claude-Code-記憶系統深度分析](./Claude-Code-記憶系統深度分析.md)
- [AI-Box-AAM-長短記憶架構技術白皮書](./AI-Box-AAM-長短記憶架構技術白皮書.md)
- [AAM-AI-Augmented-Memory-設計理念與意識演化框架](./AAM-AI-Augmented-Memory-設計理念與意識演化框架.md)

---

## 2. 架構總覽

AI-Box 記憶系統採用**五層架構**：

```
┌─────────────────────────────────────────────────────────────────┐
│  第5層：離線整理層（Offline Consolidation Layer）                  │
│  定期整理 │ KAIROS 日誌 │ 模型微調                              │
├─────────────────────────────────────────────────────────────────┤
│  第4層：團隊共享層（Team Memory Layer）                           │
│  跨用戶同步 │ 秘密掃描 │ 路徑安全                               │
├─────────────────────────────────────────────────────────────────┤
│  第3層：長期記憶層（Persistent Memory Layer）                      │
│  四種類型 │ MEMORY.md 索引 │ Vector DB │ Graph DB               │
├─────────────────────────────────────────────────────────────────┤
│  第2層：工作記憶層（Working Memory Layer）                         │
│  任務進度 │ 狀態追蹤 │ MCP 響應緩存                            │
├─────────────────────────────────────────────────────────────────┤
│  第1層：會話記憶層（Session Memory Layer）                        │
│  上下文窗口 │ 漸進式摘要 │ 壓縮觸發                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 五層職責對照

| 層級 | 持久性 | 作用域 | 核心功能 |
|------|--------|--------|----------|
| 會話記憶 | 臨時 | 當前會話 | 對話歷史、即時上下文 |
| 工作記憶 | 臨時 | 當前任務 | 任務進度、狀態追蹤 |
| 長期記憶 | 永久 | 跨會話、跨項目 | 知識沉澱、偏好記憶 |
| 團隊共享 | 永久 | 團隊成員 | 協作上下文、安全共享 |
| 離線整理 | 週期性 | 全局 | 整理、合併、進化 |

---

## 3. 第1層：會話記憶層（Session Memory Layer）

### 3.1 功能描述

會話記憶層負責維護**當前對話的完整上下文**，是 AI 即時推理的基礎。

### 3.2 組成元件

#### 3.2.1 上下文窗口（Context Window）

- **職責**：保存當前會話的完整對話歷史
- **特性**：未壓縮，完整保留每條消息
- **限制**：受限於 LLM 上下文窗口大小

#### 3.2.2 漸進式摘要（Progressive Summary）

> **靈感來源**：Claude Code Session Memory

- **職責**：在長對話過程中，持續維護一份會話摘要
- **觸發條件**：
  - 上下文 token 數達到 `minimumMessageTokensToInit`（預設 10,000）
  - 自上次更新以來增長 `minimumTokensBetweenUpdate`（預設 5,000）tokens
  - 或至少 `toolCallsBetweenUpdates`（預設 3）次工具調用

- **模板結構**（10 個固定章節）：

```markdown
# Session Memory

## Session Title
_簡短描述此會話的主題_

## Current State
_當前工作狀態_

## Task specification
_當前任務的詳細需求_

## Files and Functions
_涉及的關鍵文件和函數_

## Workflow
_正在遵循的工作流程_

## Errors & Corrections
_遇到的錯誤及解決方式_

## Codebase and System Documentation
_重要的代碼庫模式和約定_

## Learnings
_此會話中獲得的洞察_

## Key results
_重要的輸出、測量結果或成就_

## Worklog
_按時間順序的操作日誌_
```

- **大小限制**：
  - 每章節最大：2,000 tokens
  - 整個文件最大：12,000 tokens

### 3.3 接口定義

```typescript
interface SessionMemory {
  sessionId: string;
  createdAt: Date;
  updatedAt: Date;
  title: string;
  currentState: string;
  taskSpec: string;
  filesAndFunctions: string[];
  workflow: string;
  errorsAndCorrections: string[];
  learnings: string[];
  keyResults: string[];
  worklog: WorklogEntry[];
  rawMessages: Message[];  // 原始消息（未壓縮）
}

interface WorklogEntry {
  timestamp: Date;
  action: string;
  result: string;
}
```

### 3.4 觸發條件配置

```typescript
const SESSION_MEMORY_CONFIG = {
  minimumMessageTokensToInit: 10_000,
  minimumTokensBetweenUpdate: 5_000,
  toolCallsBetweenUpdates: 3,
  maxSectionLength: 2_000,      // tokens per section
  maxTotalSessionMemory: 12_000, // tokens total
};
```

---

## 4. 第2層：工作記憶層（Working Memory Layer）

### 4.1 功能描述

工作記憶層負責追蹤**當前任務的即時狀態**，區別於長期的知識記憶。

### 4.2 核心職責

| 職責 | 說明 | 示例 |
|------|------|------|
| 任務進度 | 記錄工作推進到了哪個階段 | "已完成用戶認證，正在處理訂單" |
| 偏移量 | 保存執行過程中的位置或數據偏移 | "當前處理到第 23 條記錄" |
| 機器響應狀態 | 記錄系統或工具的即時回饋 | "API 返回 404，資源不存在" |
| MCP 響應緩存 | 緩存 MCP 工具的響應結果 | 避免重複調用 |

### 4.3 接口定義

```typescript
interface WorkingMemory {
  taskId: string;
  sessionId: string;
  taskProgress: TaskProgress;
  offsets: Map<string, number>;
  machineStates: Map<string, MachineState>;
  mcpResponseCache: Map<string, CachedResponse>;
  lastUpdated: Date;
}

interface TaskProgress {
  stage: 'init' | 'processing' | 'validating' | 'completed' | 'failed';
  description: string;
  completedSteps: string[];
  pendingSteps: string[];
  currentStep: string;
}

interface MachineState {
  machineId: string;
  status: 'idle' | 'busy' | 'error';
  lastResponse: any;
  errorMessage?: string;
}

interface CachedResponse {
  key: string;
  response: any;
  ttl: number;        // milliseconds
  createdAt: Date;
}
```

### 4.4 與其他層級的區別

| 維度 | 會話記憶 | 工作記憶 | 長期記憶 |
|------|----------|----------|----------|
| 內容 | 對話歷史 | 任務狀態 | 跨會話知識 |
| 更新頻率 | 每輪對話 | 每個操作 | 對話後提取 |
| 持久性 | 會話結束清除 | 任務結束清除 | 永久 |
| 用途 | 上下文推理 | 任務追蹤 | 知識沉澱 |

---

## 5. 第3層：長期記憶層（Persistent Memory Layer）

### 5.1 功能描述

長期記憶層是**記憶系統的核心**，負責跨會話的知識沉澱和用戶偏好保持。

### 5.2 四種類型封閉系統

> **靈感來源**：Claude Code 的 MEMORY_TYPES

系統嚴格定義**四種封閉類型**，明確邊界：

```typescript
const MEMORY_TYPES = ['user', 'feedback', 'project', 'reference'] as const;
type MemoryType = typeof MEMORY_TYPES[number];
```

#### 5.2.1 User 類型

- **用途**：用戶角色、目標、知識背景
- **保存時機**：了解到用戶身份信息時
- **作用域**：始終私有
- **示例**：
```markdown
---
name: 用戶畫像-深度Go經驗
description: 用戶有深度 Go 經驗，但 React 是新手
type: user
---
用戶是後端開發者，擅長 Go。解釋前端概念時應用後端類比。
```

#### 5.2.2 Feedback 類型

- **用途**：用戶對工作方式的指導
- **保存時機**：用戶糾正或確認做法時
- **作用域**：默認私有
- **重要設計**：**同時記錄「做對了」和「做錯了」**

| 反饋類型 | 原因 |
|----------|------|
| 負面反饋（做錯了） | 防止重蹈覆轍 |
| 正面反饋（做對了） | 防止過度保守，明確正確行為 |

**示例**：
```markdown
---
name: 反饋-不要總結
description: 用戶不希望在回復末尾加總結
type: feedback
---
不要在回復末尾總結剛做了什麼，用戶能看到 diff。

**Why:** 用戶明確要求過"stop summarizing what you just did"
**How to apply:** 所有回復結束時，直接結束，不加回顧性總結。
```

#### 5.2.3 Project 類型

- **用途**：項目進展、目標、事件
- **保存時機**：了解到工作計劃、截止日期時
- **作用域**：偏向團隊
- **重要設計**：**相對日期必須轉為絕對日期**

**示例**：
```markdown
---
name: 項目-發布凍結
description: 3月5日起移動端發布凍結
type: project
---
原訂 "下週五發布" 已改為絕對日期 2026-03-05。

**Why:** 相對日期會隨時間失去意義
**How to apply:** 檢查任何日期相關記憶時，必須使用絕對日期。
```

#### 5.2.4 Reference 類型

- **用途**：外部系統的靜態指針
- **保存時機**：了解到 Linear/Grafana/Slack 等資源時
- **作用域**：通常團隊

**示例**：
```markdown
---
name: 引用-OnCall面板
description: Grafana OnCall 面板連結
type: reference
---
用於查看生產環境報警：https://grafana.example.com/oncall
```

### 5.3 明確不保存的內容

> **靈感來源**：Claude Code 的 6 類排除項

系統**硬編碼以下 6 類排除項**，即使用戶明確要求也不保存：

| 排除類型 | 原因 | 權威來源 |
|----------|------|----------|
| 代碼模式、架構、文件路徑 | 可從代碼推導 | 代碼本身 |
| Git 歷史、最近變更 | `git log`/`git blame` 是權威 | Git |
| 調試方案或修復步驟 | 修復在代碼中 | 代碼 + commit message |
| CLAUDE.md 中已有的內容 | 不重複 | CLAUDE.md |
| 臨時任務細節 | 進行中的工作、當前對話 | 上下文 |
| 可從系統直接查詢的資訊 | API/工具可實時獲取 | 系統狀態 |

### 5.4 存儲架構

#### 5.4.1 雙層存儲

```
┌─────────────────────────────────────────┐
│  第1層：MEMORY.md 索引文件               │
│  - 純 Markdown，無 frontmatter           │
│  - 每行最多 150 字元                     │
│  - 最多 200 行                          │
│  - 格式：[name](filename.md) — description │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  第2層：具體記憶文件（.md）             │
│  - 每個記憶一個文件                      │
│  - 標準 YAML frontmatter                 │
│  - 自由格式內容                          │
└─────────────────────────────────────────┘
```

#### 5.4.2 目錄結構

```
~/.aibox/
  memory/
    INDEX.md                    # 全局索引（200行限制）
    user/
      user_profile.md
      user_preferences.md
    feedback/
      feedback_concise.md
      feedback_testing.md
    project/
      project_deadline.md
    reference/
      reference_linear.md
    team/                      # 團隊共享（可選）
      INDEX.md
      team_project.md
    logs/                     # KAIROS 日誌
      2026/
        03/
          2026-03-31.md
```

#### 5.4.3 Vector DB 存儲（擴展）

> **AIBox 特有**：結合向量檢索增強召回

```typescript
interface VectorMemory {
  memoryId: string;
  type: MemoryType;
  content: string;           // 原始內容
  embedding: number[];        // 向量表示
  metadata: {
    userId: string;
    projectId?: string;
    createdAt: Date;
    updatedAt: Date;
    usageCount: number;
    freshness: number;        // 0-1, 1=最新
  };
}
```

#### 5.4.4 Graph DB 存儲（擴展）

> **AIBox 特有**：知識圖譜增強推理

```typescript
interface KnowledgeGraphNode {
  id: string;
  type: 'user' | 'feedback' | 'project' | 'reference' | 'entity';
  properties: {
    name: string;
    description: string;
    [key: string]: any;
  };
  memoryId?: string;         // 關聯記憶
}

interface KnowledgeGraphEdge {
  id: string;
  source: string;
  target: string;
  relation: string;          // e.g., 'related_to', 'conflicts_with'
  weight: number;
}
```

### 5.5 記憶召回流程

#### 5.5.1 AI 驅動的召回

> **靈感來源**：Claude Code findRelevantMemories

```
用戶消息
    ↓
scanMemoryFiles()           // 掃描所有 .md 文件
    ↓
解析 frontmatter           // 提取 description + type
    ↓
按 mtime 排序              // 最多 200 個文件
    ↓
過濾已展示的記憶           // alreadySurfaced
    ↓
selectRelevantMemories()    // AI 驅動選擇
    ↓ sideQuery → 輕量模型（如 Sonnet）
    ↓ 結構化輸出：{ selected_memories: string[] }
    ↓ max_tokens: 256
    ↓
返回最多 5 條 RelevantMemory
    ↓
標注記憶新鮮度              // "47 days ago" 自然語言
    ↓
返回給用戶 + 附帶驗證警告   // 超過 1 天需驗證
```

#### 5.5.2 召回約束

| 約束 | 說明 |
|------|------|
| 數量限制 | 最多返回 5 條 |
| 去重過濾 | 已展示過的記憶自動過濾 |
| 防止污染 | 降低最近使用的工具文檔優先級 |
| 驗證要求 | 超過 1 天的記憶，使用前必須驗證 |

### 5.6 接口定義

```typescript
interface PersistentMemory {
  memoryId: string;
  name: string;
  description: string;
  type: MemoryType;
  content: string;
  createdAt: Date;
  updatedAt: Date;
  createdBy: 'user' | 'system';  // 用戶創建或系統提取
  scope: 'private' | 'team';
  metadata: {
    projectId?: string;
    confidence?: number;
    sourceConversationId?: string;
  };
}

interface MemoryIndex {
  entries: MemoryIndexEntry[];
  totalLines: number;
  lastUpdated: Date;
}

interface MemoryIndexEntry {
  memoryId: string;
  filename: string;
  description: string;     // 最多 150 字元
  line: number;
}
```

---

## 6. 第4層：團隊共享層（Team Memory Layer）

### 6.1 功能描述

團隊共享層負責**跨用戶的記憶同步**，在提供協作能力的同時確保安全。

### 6.2 前置條件

| 條件 | 說明 |
|------|------|
| 用戶已認證 | 有效的 OAuth 令牌 |
| 倉庫權限 | 對目標 Git 倉庫有讀寫權限 |
| 團隊模式開啟 | `TEAM_MEMORY_ENABLED` 配置 |

### 6.3 API 端點

```
基礎 URL: {apiBaseUrl}/api/v1/memory/team?repo={owner/repo}
```

| 方法 | 參數 | 用途 |
|------|------|------|
| GET | `repo={slug}` | 拉取全部團隊記憶 |
| GET | `repo={slug}&view=hashes` | 僅拉取哈希（輕量探測） |
| PUT | `repo={slug}` | 上傳記憶條目（upsert） |
| DELETE | `repo={slug}&key={key}` | 刪除記憶條目 |

### 6.4 同步協議

#### 6.4.1 拉取（Pull）

```
1. GET 請求，攜帶 If-None-Match: {etag}（條件請求）
2. 304 = 未變化，跳過
3. 200 = 有更新：
   a. 對每個條目驗證路徑（防遍歷攻擊）
   b. 跳過 >250KB 的文件
   c. 跳過本地內容已匹配的文件
   d. 並行寫入本地文件系統
   e. 刷新本地校驗和
```

#### 6.4.2 推送（Push）

```
1. 遍歷本地 team/ 目錄
   → 每個文件掃描秘密（30種規則）
   → 跳過 >250KB 的文件
   → 計算 SHA-256 哈希

2. 計算 delta：僅上傳哈希變化的條目

3. 分批上傳：貪心裝箱，每批 ≤ 200KB

4. 每批攜帶 If-Match 頭（樂觀鎖）

5. 衝突處理：
   412 Conflict → 重試（最多 2 次）
   413 Too Many → 截斷後重試

6. 衝突策略：本地優先（local-wins）
```

### 6.5 安全防護

#### 6.5.1 雙層秘密掃描

> **靈感來源**：Claude Code secretScanner

| 層 | 時機 | 行為 |
|----|------|------|
| 寫入時 | FileWrite/FileEdit 調用 | 阻止寫入，返回錯誤 |
| 上傳前 | pushTeamMemory 讀取本地文件 | 跳過該文件，不上傳 |

#### 6.5.2 秘密模式清單

```typescript
const SECRET_PATTERNS = [
  // 雲端服務商
  { pattern: /^AKIA[A-Z0-9]{16}$/, name: 'AWS Access Key' },
  { pattern: /^AIza[-Za-z0-9_-]{35}$/, name: 'GCP API Key' },
  
  // AI API
  { pattern: /^sk-ant-api03-[A-Za-z0-9_-]{80,}$/, name: 'Anthropic API Key' },
  { pattern: /^sk-proj-[A-Za-z0-9_-]{80,}$/, name: 'OpenAI API Key' },
  
  // 版本控制
  { pattern: /^gh[pousr]_[A-Za-z0-9_]{36,}$/, name: 'GitHub Token' },
  { pattern: /^glpat-[A-Za-z0-9_-]{20}$/, name: 'GitLab PAT' },
  
  // 通訊平台
  { pattern: /^xox[baprs]-[A-Za-z0-9-]{10,}$/, name: 'Slack Token' },
  
  // 密碼學
  { pattern: /^-----BEGIN PRIVATE KEY-----/, name: 'PEM Private Key' },
  
  // ... 共 30 種模式
];
```

#### 6.5.3 路徑安全雙重驗證

> **靈感來源**：Claude Code teamMemPaths

```
第1遍：字串級驗證
  1. Null 位元組檢查
  2. URL 編碼遍歷檢測（%2e%2e%2f → ../）
  3. Unicode 規範化攻擊（全角字元）
  4. 反斜杠檢查（Windows 路徑遍歷）
  5. path.resolve() 解析後 startsWith(teamDir) 驗證

第2遍：符號連結級驗證
  6. realpathDeepestExisting() 解析實際路徑
  7. isRealPathWithinTeamDir() 驗證
  8. 檢測懸掛符號連結

通過 → 返回解析後的安全路徑
失敗 → 拋出 PathTraversalError
```

### 6.6 接口定義

```typescript
interface TeamMemory {
  teamId: string;
  repoSlug: string;
  memories: TeamMemoryEntry[];
  serverChecksums: Map<string, string>;  // key -> sha256
  lastSyncedAt: Date;
  syncStatus: 'idle' | 'syncing' | 'error';
}

interface TeamMemoryEntry {
  key: string;           // 文件路徑（相對）
  content: string;
  checksum: string;       // SHA-256
  updatedAt: Date;
  updatedBy: string;      // userId
  memoryType: MemoryType;
}
```

---

## 7. 第5層：離線整理層（Offline Consolidation Layer）

### 7.1 功能描述

離線整理層負責**全局記憶的定期維護**，類似人類的「睡眠整理」過程。

### 7.2 Auto Consolidation 機制

> **靈感來源**：Claude Code Auto Dream

#### 7.2.1 觸發條件（雙重門控）

```typescript
const CONSOLIDATION_CONFIG = {
  minIntervalHours: 24,         // 距離上次整合至少 24 小時
  minNewMemories: 5,           // 至少 5 個新記憶
  lockTimeoutMs: 30 * 60 * 1000, // 鎖超時 30 分鐘
};
```

#### 7.2.2 四階段整理流程

| 階段 | 名稱 | 職責 |
|------|------|------|
| 1 | Orient（定向探索） | 瀏覽記憶目錄，尋找重複或近似主題 |
| 2 | Gather（資訊收集） | 查看日誌，檢查舊記憶是否與現狀矛盾 |
| 3 | Consolidate（整合） | 合併到主題文件，相對日期→絕對日期，被推翻事實**直接刪除** |
| 4 | Prune and Index（修剪） | 確保索引 ≤ 200 行，≤ 150 字元/行 |

#### 7.2.3 鎖機制

```typescript
interface ConsolidationLock {
  lockFilePath: string;
  pid: number;           // 持有進程 ID
  lockedAt: Date;
  expiresAt: Date;       // 防死鎖
}

// CAS 競爭檢測
async function acquireLock(): Promise<boolean> {
  // 1. 嘗試創建鎖文件
  // 2. 寫入當前 PID
  // 3. 驗證文件內容是否為自己
  // 4. 若被搶占，退讓
}
```

### 7.3 KAIROS 日誌模式

> **靈感來源**：Claude Code KAIROS mode

當 AI 助手長時間運行時：

```
普通模式：寫獨立文件 + 更新 MEMORY.md 索引
KAIROS 模式：追加到 logs/YYYY/MM/YYYY-MM-DD.md 日誌文件
```

- **只追加，不編輯**：確保歷史完整性
- **每日一個文件**：便於追蹤和回溯
- **由離線整理統一維護索引**：避免實時衝突

### 7.4 整理觸發 API

```typescript
// POST /api/v1/memory/consolidate
interface ConsolidateRequest {
  force: boolean;  // 強制執行（忽略門控）
}

interface ConsolidateResponse {
  success: boolean;
  stats: {
    memoriesScanned: number;
    memoriesMerged: number;
    memoriesPruned: number;
    duration: number;  // milliseconds
  };
  errors: string[];
}
```

---

## 8. 記憶寫入流程

### 8.1 觸發時機

```
用戶消息 → 模型響應 → 工具執行 → 循環...
    ↓
模型最終響應（無工具調用）
    ↓
Stop Hooks 執行
    ↓
extractMemories()  ← 即發即忘，非阻塞
```

### 8.2 前置條件

```typescript
const EXTRACT_MEMORIES_CONFIG = {
  featureFlag: 'EXTRACT_MEMORIES',
  growthBookFlag: 'aibox_auto_memory_enabled',
  requireAuth: true,
  excludeSubagents: true,    // 子代理不執行提取
  excludeBareMode: true,
};
```

### 8.3 提取器權限白名單

```typescript
const EXTRACT_AGENT_TOOLS = {
  allowed: ['FileRead', 'Grep', 'Glob', 'Bash-readonly'],
  denied: ['Bash-write', 'MCP', 'Agent', 'FileWrite', 'FileEdit'],
  pathRestriction: 'memoryDir',  // 只能寫入記憶目錄
};
```

### 8.4 提取後通知

成功提取後，系統消息追加到主對話：

```json
{
  "type": "system",
  "content": "已保存 3 條記憶到長期記憶",
  "memoryIds": ["mem_001", "mem_002", "mem_003"]
}
```

---

## 9. 系統提示詞注入

### 9.1 注入時機

| 時機 | 內容 |
|------|------|
| 會話開始 | loadMemoryPrompt() → 讀取 MEMORY.md |
| 每輪對話 | findRelevantMemories() → 召回相關記憶 |
| 會話結束 | drainPendingExtraction() → 等待提取完成 |

### 9.2 注入模板

```markdown
# Memory System

你有一個持久化的基於文件的記憶系統，位於 `<memoryDir>`。
該目錄已存在——使用 Write 工具直接寫入。

## Types of Memory
- **user**: 用戶畫像、角色、目標、知識背景
- **feedback**: 工作方式指導（糾正和確認）
- **project**: 項目進展、目標、截止日期
- **reference**: 外部系統指針

## What NOT to Save
- 代碼模式、架構、文件路徑（可從代碼推導）
- Git 歷史（git log 是權威來源）
- 調試方案（修復在代碼中）
- CLAUDE.md 已有的內容
- 臨時任務細節

## How to Save
1. 寫入文件（帶 frontmatter）
2. 在 MEMORY.md 中添加索引行

## When to Access
- 看起来相關時
- 用戶明確要求時（必須訪問）
- 用戶說"忽略記憶"時，假裝 MEMORY.md 為空

## Before Using a Memory
- 提到文件路徑 → 檢查文件是否存在
- 提到函數/標誌 → grep 搜索
- 用戶要行動 → 先驗證

## Memory freshness
記憶新鮮度用自然語言："today", "yesterday", "47 days ago"
超過 1 天的記憶，在使用前必須驗證。
```

---

## 10. 配置參數

### 10.1 環境變數

```bash
# 記憶系統開關
AIBOX_MEMORY_ENABLED=true

# 目錄配置
AIBOX_MEMORY_DIR=~/.aibox/memory
AIBOX_TEAM_MEMORY_ENABLED=false

# Vector DB 配置
AIBOX_VECTOR_DB_URL=http://localhost:6333
AIBOX_VECTOR_COLLECTION=memories

# Graph DB 配置
AIBOX_GRAPH_DB_URL=http://localhost:8529
AIBOX_GRAPH_DB_NAME=aibox_memory

# 整理配置
AIBOX_CONSOLIDATION_ENABLED=true
AIBOX_CONSOLIDATION_INTERVAL_HOURS=24

# 安全配置
AIBOX_SECRET_SCAN_ENABLED=true
AIBOX_PATH_VALIDATION_ENABLED=true
```

### 10.2 Feature Flags

```typescript
const MEMORY_FEATURE_FLAGS = {
  autoMemoryEnabled: 'aibox_auto_memory',       // 自動記憶提取
  extractModeActive: 'aibox_extract_mode',      // 提取模式
  teamMemoryEnabled: 'aibox_team_memory',        // 團隊記憶
  consolidationEnabled: 'aibox_consolidation',  // 離線整理
  vectorRecallEnabled: 'aibox_vector_recall',    // 向量召回
  graphRecallEnabled: 'aibox_graph_recall',     // 圖召回
};
```

---

## 11. API 端點

### 11.1 記憶管理

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/v1/memory` | 獲取用戶所有記憶 |
| GET | `/api/v1/memory/:id` | 獲取指定記憶 |
| POST | `/api/v1/memory` | 創建記憶 |
| PUT | `/api/v1/memory/:id` | 更新記憶 |
| DELETE | `/api/v1/memory/:id` | 刪除記憶 |
| GET | `/api/v1/memory/index` | 獲取 MEMORY.md 內容 |

### 11.2 召回

| 方法 | 端點 | 說明 |
|------|------|------|
| POST | `/api/v1/memory/recall` | AI 驅動召回相關記憶 |
| GET | `/api/v1/memory/search` | 關鍵詞搜索記憶 |

### 11.3 團隊記憶

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/v1/memory/team` | 獲取團隊記憶 |
| PUT | `/api/v1/memory/team` | 上傳團隊記憶 |
| DELETE | `/api/v1/memory/team/:key` | 刪除團隊記憶 |
| POST | `/api/v1/memory/team/sync` | 觸發同步 |

### 11.4 整理

| 方法 | 端點 | 說明 |
|------|------|------|
| POST | `/api/v1/memory/consolidate` | 觸發離線整理 |
| GET | `/api/v1/memory/consolidate/status` | 獲取整理狀態 |

---

## 12. 實現狀態

### 12.1 已實現 ✅

| 功能 | 說明 |
|------|------|
| 四種類型定義 | user/feedback/project/reference |
| 明確不保存清單 | 6 類排除項 |
| MEMORY.md 索引 | 200 行限制、150 字元限制 |
| 記憶文件格式 | YAML frontmatter + Markdown |
| 秘密掃描 | 雙層防護 |
| 路徑安全 | 字串級 + 符號連結級 |

### 12.2 規劃中 🔄

| 功能 | 優先級 | 預計時間 |
|------|--------|----------|
| AI 驅動召回 | 高 | 1-2 月 |
| 向量 DB 集成 | 高 | 1-2 月 |
| 圖 DB 集成 | 中 | 2-3 月 |
| 工作記憶建模 | 中 | 1-2 月 |
| 漸進式摘要 | 中 | 2-3 月 |
| 團隊記憶同步 | 低 | 3+ 月 |
| 離線整理 | 低 | 3+ 月 |

---

## 13. 測試策略

### 13.1 單元測試

```typescript
// 記憶類型驗證
test('四種類型封閉系統', () => {
  expect(() => createMemory({ type: 'invalid' })).toThrow();
  MEMORY_TYPES.forEach(type => {
    expect(() => createMemory({ type })).not.toThrow();
  });
});

// 排除項驗證
test('明確不保存的內容被拒絕', () => {
  const forbiddenContent = [
    '代碼模式：const x = 1',
    'Git 歷史：commit abc123',
    '調試方案：fix by updating deps',
  ];
  forbiddenContent.forEach(content => {
    expect(shouldSaveToMemory(content)).toBe(false);
  });
});
```

### 13.2 集成測試

```typescript
test('記憶召回流程', async () => {
  // 1. 創建測試記憶
  await createMemory({ type: 'user', name: '測試用戶' });
  
  // 2. 觸發召回
  const memories = await recallMemories('用戶偏好');
  
  // 3. 驗證結果
  expect(memories.length).toBeLessThanOrEqual(5);
  memories.forEach(m => expect(m.type).toBeDefined());
});
```

---

## 14. 遷移策略

### 14.1 從現有 AAM 遷移

現有 AAM 架構中的組件需要重新整合：

| 現有組件 | 遷移目標 |
|----------|----------|
| ChromaDB | Vector DB（長期記憶層） |
| ArangoDB | Graph DB（長期記憶層） |
| Short-Term Memory | 會話記憶層 |
| AAM Agentic | 離線整理層 |

### 14.2 兼容性

```typescript
// 保持向後兼容
interface LegacyMemory {
  id: string;
  content: string;
  vector?: number[];
  metadata: Record<string, any>;
}

// 轉換為新格式
function convertLegacyMemory(legacy: LegacyMemory): PersistentMemory {
  return {
    memoryId: legacy.id,
    name: extractName(legacy.content),
    description: extractDescription(legacy.content),
    type: inferType(legacy.metadata),
    content: legacy.content,
    // ...
  };
}
```

---

## 15. 監控與日誌

### 15.1 關鍵指標

| 指標 | 說明 | 警報閾值 |
|------|------|----------|
| memory_operations_total | 記憶操作總數 | - |
| memory_size_bytes | 記憶總大小 | > 100MB |
| recall_latency_ms | 召回延遲 | > 500ms |
| consolidation_duration_ms | 整理耗時 | > 5min |
| secret_blocks_total | 秘密攔截總數 | > 0 |
| path_validation_fails_total | 路徑驗證失敗 | > 0 |

### 15.2 日誌格式

```json
{
  "timestamp": "2026-04-06T11:20:10Z",
  "level": "info",
  "event": "memory_recall",
  "userId": "user_123",
  "memoriesReturned": 3,
  "latencyMs": 45
}
```

---

## 16. 安全性考量

### 16.1 數據隔離

| 層級 | 隔離策略 |
|------|----------|
| 用戶私有記憶 | 加密存儲，僅用戶可訪問 |
| 團隊記憶 | 成員級別訪問控制 |
| 系統記憶 | 管理員可配置，用戶不可見 |

### 16.2 審計日誌

```typescript
interface AuditLog {
  timestamp: Date;
  userId: string;
  action: 'create' | 'read' | 'update' | 'delete';
  memoryId: string;
  memoryType: MemoryType;
  ipAddress: string;
  userAgent: string;
}
```

---

## 17. 性能優化

### 17.1 緩存策略

| 緩存層 | TTL | 策略 |
|--------|-----|------|
| MEMORY.md | 會話內 | LRU |
| 記憶文件內容 | 5 分鐘 | lazy load |
| 召回結果 | 1 分鐘 | 相同 query 共享 |

### 17.2 異步處理

```typescript
// 記憶提取：即發即忘
async function extractMemoriesAsync(conversation: Message[]): Promise<void> {
  // 不阻塞主流程
  backgroundQueue.enqueue(() => doExtractMemories(conversation));
}

// 離線整理：低峰期執行
scheduleConsolidation({
  preferHours: [2, 3, 4],  // 凌晨時段
  maxDuration: 30 * 60 * 1000,
});
```

---

## 18. 錯誤處理

### 18.1 錯誤類型

```typescript
enum MemoryErrorCode {
  MEMORY_NOT_FOUND = 'MEMORY_001',
  MEMORY_TYPE_INVALID = 'MEMORY_002',
  MEMORY_CONTENT_FORBIDDEN = 'MEMORY_003',  // 包含敏感內容
  INDEX_SIZE_EXCEEDED = 'MEMORY_004',
  PATH_TRAVERSAL_DETECTED = 'MEMORY_005',
  CONSOLIDATION_LOCKED = 'MEMORY_006',
  TEAM_SYNC_CONFLICT = 'MEMORY_007',
}
```

### 18.2 重試策略

| 錯誤類型 | 重試次數 | 退避策略 |
|----------|----------|----------|
| 網路錯誤 | 3 | 指數退避 |
| 衝突錯誤 | 2 | 樂觀鎖重試 |
| 鎖超時 | 1 | 等待後重試 |

---

*最後更新：2026-04-06 11:20:10*
