---
lastUpdate: 2026-04-22 00:00:00
author: Daniel Chung
version: 1.0.0
---

# Agent 需求管理系統規格書

## 1. 概述

### 1.1 目的

本規格書定義 Agent 需求管理系統的功能需求、狀態機設計、資料結構、API 介面及 UI 流程。

此系統讓非技術用戶能夠通过艾企引導提交結構化需求，團隊依此開發，雙方有明確的驗收基準。

### 1.2 背景與問題

市場上大多數 AI Agent 平台宣稱「每個人都能寫智能體」，但：
- 用戶知道怎麼描述需求嗎？
- 沒有受過需求訪談訓練的人，會漏掉很多重要的假設
- 做出來的 Agent 好壞，取決於用戶的「描述能力」，而不是「需求本身」

本系統提出「AI 需求訪談」模式，在用戶填寫需求表的過程中，AI 被動陪伴、主動補漏，最終產出結構化需求文件。

### 1.3 設計原則

| 原則 | 說明 |
|------|------|
| **被動感知** | 艾企感知用戶正在填寫需求表，但不主動打斷 |
| **預測提示** | 根據當前欄位、填寫內容，AI 預測用戶可能需要的提示 |
| **環境專家** | 像一個安靜站在旁邊的顧問，你知道他在，可以隨時問 |
| **隱私保護** | 企業敏感資訊默認本地處理，外部模型調用需用戶同意 |
| **可追溯** | 所有需求狀態變更有完整時間記錄 |

---

## 2. 狀態機設計

### 2.1 完整狀態流程圖

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  【沒有需求】                                                     │
│     │                                                            │
│     │ 點「提交需求」                                              │
│     ↓                                                            │
│  【需求 vX 草稿】  ←── 用戶填寫需求，AI 陪伴引導                │
│     │                                                            │
│     │ 點「提交」                                                 │
│     ↓                                                            │
│  【已提交】    ←── 等待團隊處理                                  │
│     │                               ┌─────────────┐             │
│     │                               │ AI 工時預估  │             │
│     │                               │ 預估：3-5天  │             │
│     │                               └─────────────┘             │
│     ├─ 團隊「接受」 ──→ 【開發中】                             │
│     │                                                            │
│     └─ 用戶「取消」 ──→ 【已取消】 ──→ 可刪除或重新提交         │
│                                                                  │
│  【開發中】    ←── 團隊正在開發                                  │
│     │                                                            │
│     │ 團隊完成 → 「提交驗收」                                    │
│     ↓                                                            │
│  【待驗收】    ←── 用戶測試中                                    │
│     │                                                            │
│     ├─ 驗收不通過 ─→ 【開發中】（附打回原因）──→ 重新驗收       │
│     │                                                            │
│     └─ 驗收通過 ─────────────────────→ 【已上線】──────────→    │
│                                              ↓                    │
│                                        按「需求變更」              │
│                                              ↓                    │
│                                    回到【需求 vX+1 草稿】         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 狀態說明

| 狀態 | 說明 | 可執行操作 |
|------|------|-----------|
| `none` | 尚無需求 | 提交需求 |
| `draft` | 草稿，用戶正在填寫 | 提交 / 取消 |
| `submitted` | 已提交，等待團隊處理 | 取消（用戶） / 接受（團隊） |
| `in_development` | 開發中 | 提交驗收（團隊） |
| `pending_acceptance` | 待驗收 | 驗收通過 / 驗收不通過 |
| `online` | 已上線 / 確立版本 | 需求變更 |
| `cancelled` | 已取消 | 刪除 / 重新提交 |

### 2.3 特殊行為

- **驗收不通過**：停留在 `in_development`，附帶 `rejection_reason`，供團隊查看
- **需求變更**：從 `online` 回到 `draft`（新版本），按鈕改為「需求變更」
- **取消**：從 `submitted` 可取消，需求不會消失但狀態改 `cancelled`
- **多版本共存**：歷史版本可查閱，當前 active 需求只有一個

---

## 3. 資料模型

### 3.1 Demand 資料結構

```typescript
interface Demand {
  // 識別
  _key: string;                    // 文件唯一識別
  agent_key: string;               // 所屬 Agent 的 _key
  version: string;                 // 版本號（v1.0, v2.0...）
  status: DemandStatus;

  // 需求內容
  goal: string;                    // 需求目標
  expected_effect: string;         // 預期效果
  problem_description: string;     // 要解決的問題
  target_users?: string;           // 目標用戶（選填）
  scope?: string;                 // 服務範圍（選填）
  excluded_scope?: string;         // 不包含的範圍（選填）

  // 工時預估
  estimated_hours: number | null; // AI 估算工時（小時）
  estimated_confidence: 'low' | 'medium' | 'high';  // AI 估算信心度
  final_hours: number | null;     // 最終確認工時

  // 對話風格（選填）
  conversation_style?: string;      // 如：繁體中文、禮貌親切、專業但不冷淡

  // 驗收記錄
  rejection_history: RejectionRecord[];  // 被打回記錄列表
  accepted_at?: string;            // 驗收通過時間
  online_at?: string;              // 上線時間

  // 時間戳
  created_at: string;
  updated_at: string;
  submitted_at?: string;           // 提交時間
  accepted_at?: string;            // 團隊接受時間
  cancelled_at?: string;           // 取消時間
}

interface RejectionRecord {
  rejected_at: string;
  reason: string;                 // 打回原因
  by_user?: string;               // 驗收人（可選）
}
```

### 3.2 Agent 擴展欄位

在現有 `agents` collection 新增以下欄位：

```typescript
interface Agent {
  // ... 現有欄位 ...

  // 需求相關
  current_demand_key: string | null;   // 當前 active 需求 _key
  demand_version: string;               // 下一個版本號（遞增）
  has_active_demand: boolean;          // 是否有 active 需求
}
```

---

## 4. 需求表單設計

### 4.1 表單欄位

| 欄位名 | 必填 | 說明 | 範例 |
|--------|------|------|------|
| **需求目標** | ✅ | 這個 Agent 要做什麼 | 「做一個內部 IT 客服，幫員工快速解決 IT 問題」 |
| **預期效果** | ✅ | 達到什麼樣的效果 | 「員工問題能在 5 分鐘內得到回覆，80% 問題能自動回答」 |
| **問題描述** | ✅ | 現有什麼問題需要解決 | 「員工經常問重複的 IT 問題，IT 人員時間被佔用」 |
| **目標用戶** | ❌ | 誰會用到這個 Agent | 「公司內部員工（約 200 人）」 |
| **服務範圍** | ❌ | 明確包含哪些場景 | 「密碼重設、軟體安裝、網路問題」 |
| **不包含範圍** | ❌ | 明確排除哪些場景 | 「不處理財務系統問題、不執行刪除動作」 |
| **對話風格** | ❌ | 性格、語氣、語言 | 「繁體中文、禮貌親切、專業但不冷淡」 |
| **參考文件** | ❌ | 相關文件連結或附件 | 「IT 手冊.pdf、Ragic 官方文件」 |

### 4.2 對話範例（重要）

用戶需提供「理想對話範例」和「不接受範例」，幫助 AI 理解預期行為：

```markdown
【理想對話 1】
用戶：請問如何設定自動化通知？
助手：當然可以！請問您是想設定「記錄異動通知」還是「時限提醒」呢？

【理想對話 2】
用戶：系統壞了，沒辦法登入
助手：抱歉聽到這個問題！請問是什麼畫面無法操作？或者有錯誤訊息嗎？

【不接受對話】
用戶：幫我刪除這個客戶資料
助手：抱歉，我沒有刪除資料的權限。如需刪除，請聯繫管理員處理。
```

### 4.3 AI 工時預估

當用戶填寫過程中，AI 分析需求內容自動估算：

```
┌─────────────────────────────────────────────┐
│  💡 AI 工時預估                             │
│                                             │
│  根據您填寫的需求：                         │
│  - 目標用戶：內部員工 200 人               │
│  - 服務範圍：密碼、軟體、網路（共 3 類）  │
│  - 需要串接外部系統：IT 管理系統           │
│                                             │
│  我建議開發工時為：**3-5 天**              │
│  信心度：中等（建議與團隊確認）             │
│                                             │
│  可調整：[-] 3-5 天 [+]                    │
└─────────────────────────────────────────────┘
```

---

## 5. UI 流程設計

### 5.1 Agent 編輯頁佈局

```
┌─────────────────────────────────────────────────────────────────┐
│  編輯 Agent — Ragic 小幫手                    [提交需求] [×]   │
├─────────────────────────────────────────────────────────────────┤
│  [基本資訊] [分類] [來源] │ [權限] [模型] [對話] [意圖表]     │
│                                                    [需求]        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                    （Tab 內容區）                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**說明**：
- 「提交需求」按鈕在 Modal 右上角
- 「需求」Tab 一開始不存在，點「提交需求」後才出現
- Tab 出現時自動切換到該 Tab

### 5.2 需求 Tab 內容（不同狀態顯示不同內容）

#### 狀態：草稿（draft）

```
┌─────────────────────────────────────────────────────────────────┐
│  需求 v1.0                                        [草稿]        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  需求目標 *                    [________________________]      │
│                                                                 │
│  預期效果 *                    [________________________]        │
│                                                                 │
│  問題描述 *                    [________________________]        │
│                                                                 │
│  目標用戶                      [________________________]        │
│                                                                 │
│  服務範圍                      [________________________]        │
│                                                                 │
│  不包含範圍                    [________________________]        │
│                                                                 │
│  對話風格                      [________________________]        │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 💬 艾企正在陪伴您填寫需求                               │   │
│  │    「我看到您填寫了『服務範圍』，可以更具體說明        │   │
│  │      哪些情況是不處理的嗎？這樣可以避免未來误会。」      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│                              [取消]              [提交需求]       │
└─────────────────────────────────────────────────────────────────┘
```

#### 狀態：已提交（submitted）

```
┌─────────────────────────────────────────────────────────────────┐
│  需求 v1.0                                        [已提交]  ✓  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 📋 需求摘要                                             │   │
│  │                                                         │   │
│  │ 目標：內部 IT 客服                                       │   │
│  │ 效果：員工問題能在 5 分鐘內得到回覆                      │   │
│  │ 問題：公司約 200 人，重複 IT 問題佔用 IT 人員時間        │   │
│  │ 工時預估：3-5 天（AI 估算，信心度：中）                  │   │
│  │ 提交時間：2026-04-22 10:30                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  💬 艾企                                                    │
│  「需求已提交，等待團隊審核。通常 1-2 個工作天會有回覆，        │
│    有任何問題隨時可以詢問我。」                                 │
│                                                                 │
│  [撤回需求]                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 狀態：開發中（in_development）

```
┌─────────────────────────────────────────────────────────────────┐
│  需求 v1.0                                    [開發中] 🔧       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 📋 需求摘要                                   [展開]     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  💬 艾企                                                    │
│  「團隊已開始開發，預計完成時間 3 天。如有緊急變更              │
│    可以直接告訴我，我會協助更新需求。」                          │
│                                                                 │
│  上次溝通：2026-04-22 14:00                                    │
└─────────────────────────────────────────────────────────────────┘
```

#### 狀態：待驗收（pending_acceptance）

```
┌─────────────────────────────────────────────────────────────────┐
│  需求 v1.0                                    [待驗收] ⏳     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  團隊已完成開發，請進行驗收：                                    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 預計功能：                                              │   │
│  │ □ 密碼重設自動化回覆                                    │   │
│  │ □ 軟體安裝指引                                          │   │
│  │ □ 網路問題初步診斷                                      │   │
│  │ □ 常见问题知识库检索                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  測試反饋：________________________                            │
│                                                                 │
│                    [驗收不通過]            [驗收通過 ✓]         │
└─────────────────────────────────────────────────────────────────┘
```

#### 狀態：已上線（online）

```
┌─────────────────────────────────────────────────────────────────┐
│  需求 v1.0                                          [已上線] 🎉│
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🎉 此功能已於 2026-04-25 上線                                 │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 📋 功能描述                                   [展開]     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  💬 艾企                                                    │
│  「功能已上線，如需調整或有新需求，可以點擊『需求變更』。」       │
│                                                                 │
│                                        [需求變更]               │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 需求 Tab 按鈕邏輯

| 狀態 | 左側按鈕 | 右側按鈕 |
|------|----------|----------|
| `draft` | 取消 | **提交需求**（primary） |
| `submitted` | **撤回需求** | — |
| `in_development` | — | —（被動狀態） |
| `pending_acceptance` | **驗收不通過** | **驗收通過** |
| `online` | — | **需求變更** |
| `cancelled` | **刪除需求** | **重新提交** |

---

## 6. API 規格

### 6.1 需求 CRUD

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/v1/agents/{key}/demands` | 取得所有需求（支援分頁、狀態過濾） |
| GET | `/api/v1/agents/{key}/demands/{demandKey}` | 取得單一需求 |
| POST | `/api/v1/agents/{key}/demands` | 建立新需求（草稿） |
| PUT | `/api/v1/agents/{key}/demands/{demandKey}` | 更新需求（草稿階段） |
| PATCH | `/api/v1/agents/{key}/demands/{demandKey}/status` | 更新需求狀態 |
| DELETE | `/api/v1/agents/{key}/demands/{demandKey}` | 刪除需求 |

### 6.2 狀態更新 API

```
PATCH /api/v1/agents/{key}/demands/{demandKey}/status
```

Request Body：

```json
{
  "status": "in_development",
  "reason": "",
  "estimated_hours": 40
}
```

```json
{
  "status": "pending_acceptance",
  "reason": "",
  "final_hours": 36
}
```

```json
{
  "status": "in_development",
  "reason": "驗收不通過：密碼重設功能無法正常發送郵件"
}
```

```json
{
  "status": "online",
  "reason": ""
}
```

### 6.3 AI 工時預估 API

```
POST /api/v1/demands/estimate-hours
```

Request Body：

```json
{
  "goal": "內部 IT 客服，幫員工快速解決 IT 問題",
  "expected_effect": "員工問題能在 5 分鐘內得到回覆",
  "problem_description": "員工經常問重複的 IT 問題",
  "target_users": "公司內部員工約 200 人",
  "scope": "密碼重設、軟體安裝、網路問題",
  "systems_to_integrate": ["IT 管理系統", "公司通訊軟體"]
}
```

Response：

```json
{
  "code": 0,
  "data": {
    "estimated_hours": 40,
    "range_min": 32,
    "range_max": 48,
    "confidence": "medium",
    "reasoning": "需求涉及 3 個主要領域（密碼、軟體、網路），需要串接 2 個外部系統，複雜度中等。"
  }
}
```

---

## 7. 艾企整合設計

### 7.1 FormContext 擴展

```typescript
interface FormContext {
  // ... 現有欄位 ...
  page: 'agent-demand-form';
  field: 'goal' | 'expected_effect' | 'problem_description' | 'target_users' | 'scope' | 'excluded_scope' | 'conversation_style';
  formValues: {
    goal?: string;
    expected_effect?: string;
    problem_description?: string;
    target_users?: string;
    scope?: string;
    excluded_scope?: string;
    conversation_style?: string;
  };
  demandStatus?: DemandStatus;
  demandVersion?: string;
}
```

### 7.2 艾企被動提示觸發時機

| 觸發條件 | 艾企行為 |
|----------|----------|
| 用戶 focus `goal` 欄位 | 顯示「這個欄位可以更具體描述目標」 |
| 用戶在 `goal` 停頓 >10 秒 | 顯示「需要幫您列舉一些常見目標嗎？」 |
| 用戶填寫 `scope` 但沒填 `excluded_scope` | 顯示「建議也說明哪些是不處理的，可以減少誤解」 |
| 用戶即將提交但 scope 模糊 | 顯示「我注意到服務範圍描述較模糊，可能影響開發，確定要提交嗎？」 |
| 提交後 | 自動整理摘要，詢問是否需要調整 |

### 7.3 艾企主動提供工時估算

當用戶填寫的內容足夠完整時（`goal` + `expected_effect` + `scope` 都已填），艾企自動在右側顯示：

```
┌──────────────────────────────┐
│ 💡 我可以幫您估算工時          │
│                              │
│  根據您填寫的內容，           │
│  預估需要 3-5 天              │
│                              │
│  [詳細估算]                   │
└──────────────────────────────┘
```

---

## 8. 數據庫 Schema

### 8.1 ArangoDB Collection

Collection 名稱：`agent_demands`

```javascript
{
  "name": "agent_demands",
  "type": 2,
  "schema": {
    "rule": {
      "type": "object",
      "properties": {
        "_key": { "type": "string" },
        "agent_key": { "type": "string" },
        "version": { "type": "string" },
        "status": {
          "type": "string",
          "enum": ["draft", "submitted", "accepted", "in_development", "pending_acceptance", "online", "cancelled"]
        },
        "goal": { "type": "string" },
        "expected_effect": { "type": "string" },
        "problem_description": { "type": "string" },
        "target_users": { "type": "string" },
        "scope": { "type": "string" },
        "excluded_scope": { "type": "string" },
        "conversation_style": { "type": "string" },
        "conversation_examples": { "type": "array", "items": { "type": "object" } },
        "estimated_hours": { "type": ["number", "null"] },
        "estimated_confidence": { "type": "string" },
        "final_hours": { "type": ["number", "null"] },
        "rejection_history": { "type": "array", "items": { "type": "object" } },
        "references": { "type": "array", "items": { "type": "string" } },
        "created_at": { "type": "string" },
        "updated_at": { "type": "string" },
        "submitted_at": { "type": ["string", "null"] },
        "accepted_at": { "type": ["string", "null"] },
        "cancelled_at": { "type": ["string", "null"] },
        "online_at": { "type": ["string", "null"] }
      },
      "required": ["_key", "agent_key", "version", "status", "goal", "expected_effect", "problem_description", "created_at", "updated_at"]
    }
  }
}
```

### 8.2 Index 設計

```javascript
// 主要查詢索引
agent_demands: {
  "agent_key_status": ["agent_key", "status"],
  "agent_key_version": ["agent_key", "version"],
  "status": ["status"],
  "submitted_at": ["submitted_at"]
}
```

---

## 9. 前端元件規劃

### 9.1 新增頁面 / 元件

| 元件 | 路徑 | 說明 |
|------|------|------|
| DemandTab | `src/components/DemandTab.tsx` | 需求 Tab 內容元件，根據狀態 render 不同內容 |
| DemandForm | `src/components/DemandForm.tsx` | 需求填寫表單 |
| DemandSummary | `src/components/DemandSummary.tsx` | 需求摘要顯示（已提交後） |
| AIIteration | `src/components/AIIteration.tsx` | 艾企引導區域 |
| TimeEstimateCard | `src/components/TimeEstimateCard.tsx` | 工時估算卡片 |

### 9.2 現有元件修改

| 檔案 | 修改內容 |
|------|----------|
| `AgentFormModal.tsx` | 新增需求 Tab，新增「提交需求」按鈕 |
| `FloatingAssistant/index.tsx` | 支援 `page='agent-demand-form'` 上下文 |
| `FloatingAssistant/types.ts` | 擴展 `FormContext` 介面 |

---

## 10. 實作階段規劃

### Phase 1：MVP（1-2 sprint）

- [ ] 建立 `agent_demands` collection schema
- [ ] Rust API 新增需求 CRUD 端點
- [ ] 前端新增「提交需求」按鈕
- [ ] 前端新增「需求」Tab（草稿 + 提交）
- [ ] 基本艾企引導（靜態提示）
- [ ] 工時估算 API + 前端顯示

### Phase 2：完整流程（1-2 sprint）

- [ ] 完整狀態機實作（接受、開發中、待驗收等）
- [ ] 驗收不通過流程
- [ ] 需求變更流程
- [ ] 艾企被動提示增強
- [ ] 需求歷史版本查詢

### Phase 3：AI 增強（1 sprint）

- [ ] 艾企動態引導（根據填寫內容實時分析）
- [ ] 對話範例自動生成建議
- [ ] 需求完整性自動檢查

---

## 11. 附錄

### 11.1 狀態轉換矩陣

| 從 \ 到 | draft | submitted | accepted | in_dev | pend_acc | online | cancelled |
|---------|-------|-----------|----------|--------|----------|--------|-----------|
| draft | — | ✅user | — | — | — | — | ✅user |
| submitted | ✅user | — | ✅team | — | — | — | ✅user |
| accepted | — | — | — | ✅team | — | — | — |
| in_dev | — | — | — | — | ✅team | — | — |
| pend_acc | — | — | — | ✅user | — | ✅user | — |
| online | ✅user | — | — | — | — | — | — |
| cancelled | — | — | — | — | — | — | — |

### 11.2 用到的技术栈

| 層級 | 技術 |
|------|------|
| 前端框架 | React 18 + TypeScript |
| UI 組件庫 | Ant Design 6.x |
| 狀態管理 | React Context + Hooks |
| 後端 API | Rust Axum |
| 資料庫 | ArangoDB |
| AI 模型 | Ollama（本地）/ GPT-4（外部，可選） |

---

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-22 | 1.0.0 | Daniel Chung | 初始版本 |
