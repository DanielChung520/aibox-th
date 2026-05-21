# Agent Orchestrator 優化計畫

> 基於 Corrected2.drawio.xml 為核心架構，逐步補足 Corrected1 的安全審計與監督機制。
> 核心哲學：Harness Engineering — 裕度光譜 + PDCA 品質循環。

---

## 設計理念與架構確認（2026-05-09 討論總結）

### 核心哲學：Harness Engineering + 裕度光譜

```
LLM 自由對話    ─── 最高裕度，最低精度（開放式聊天）
     │
Tools 調用      ─── 中度裕度（LLM 可選工具+決定參數）
     │               但 Data Agent 限定資料範圍
     │
Skills 執行     ─── 中度偏低（結構化步驟，每步指定 executor）
     │               步驟間變數傳遞，PDCA 稽核
     │
ActionScript    ─── 最低裕度，最高精度（Code 強制執行）
                    適用於需要精準調用資料的邏輯運算
```

### 元件定義

| 元件 | 定義 | 裕度 | 對應主流 |
|------|------|------|---------|
| **Agent** | 有狀態、可多輪、可編排的工作單元，擁有 2~3 個 Skills | 中 | Anthropic Agent / OpenAI GPTs |
| **Skill** | 結構化步驟序列，每步指定調用哪個元件，步驟間可傳遞變數 | 中低 | ORCA YAML DAG / CrewAI Flows |
| **Tool** | 單次無狀態執行單元（MCP / DA / KA / Builtin） | 中 | MCP / Function Calling |
| **ActionScript** | 零裕度業務邏輯單元，Code 強制執行 | ❌ 零 | 無對應（自有設計） |
| **PDCA** | 步驟稽核者，可通過 / 擋下 / 澄清 / 升級 | — | SafeHarness / BAL |

### Agent 運作流程

```
進入路徑（雙軌）：
  ├─ 結構化（LINE Menu / 表單）→ 直接建立 taskSession → 綁定 Skill
  └─ 自然語言 → Intent Classification → SkillsRAG /match → 匹配 Skill

Agent 啟動後：
  Skill 步驟 1 → 執行 → PDCA Check → 通過 → 步驟 2 → ...
                                      ├─ 擋下 → 通知
                                      ├─ 澄清 → 詢問用戶
                                      └─ 升級 → 通知管理員
  執行期間不插入 LLM 廢話，只有 Check 時 LLM 判斷。
  用戶可多輪對話，但同一 Skill 內不亂跳。
```

### 裕度設計原則

| 工作類型 | 適用元件 | 說明 |
|---------|---------|------|
| 自由發想、探索 | LLM Chat | 不經 SkillsRAG，Mermaid/表格渲染即可 |
| 查詢類（多變） | Tool: DA/KA | LLM 決定查法，但限定資料範圍 |
| 流程類（固定） | ActionScript | Code 強制，零裕度 |
| 判斷類（模糊） | LLM inside step | 例：比對照片 vs ERP 資料 |
| 異常類（少發） | PDCA → HITL | 升級給人處理 |

### 案例：進倉入庫小幫手

```
Agent: 進倉入庫小幫手（管理原料入庫）

  Skill 1: 入庫照片登錄 ─── ActionScript（高精度）
    步驟:
      1. LINE 工具 → 取得照片+標記（裕度：❌ 固定調用）
      2. 多媒體解析 → 辨識食材成分（裕度：✅ LLM）
      3. 上傳 Ragic 暫存（裕度：❌ 精準寫入）
      ─── PDCA Check: 暫存成功？
      4. 讀取 ERP 進貨明細 → Data Agent（裕度：✅ 有範圍）
      5. 照片勾稽比對（裕度：✅ LLM 判斷匹配）
      ─── PDCA Check: 匹配 / 不匹配 / 部分匹配（→澄清）
      6. 回單確認（裕度：❌ 零裕度）
      ─── PDCA Act: 完成→回饋 / 失敗→升級

  Skill 2: 入庫記錄更新（含 HITL）
  Skill 3: 入庫記錄刪除（零裕度 + guardrail）
  Skill 4: 入庫資料查詢（Tool: DA，中裕度）
    用戶可直接問「今天進哪些料號？」→ Intent → SkillsRAG → Skill 4
```

### 與主流 Harness Engineering 比較

| 面向 | 主流 HE | 你的設計 | 差異 |
|------|---------|---------|------|
| 控制方式 | 全有全無 bounded/unbounded | **光譜式**裕度，依工作類型動態變化 | ✅ 更細緻 |
| Skills 本質 | 被動上下文（Anthropic SKILL.md） | **主動步驟 DAG**，可編排其他元件 | ✅ 更結構化 |
| PDCA 角色 | 無對應 | 稽核者：通過/擋下/澄清/升級 | ✅ 自有設計 |
| 進入路徑 | 純自然語言 | 結構化（Menu）+ 自然語言雙軌 | ✅ 更務實 |
| ActionScript | 無對應 | 零裕度 Code 強制執行 | ✅ 自有設計 |
| 裕度控制粒度 | 粗 | 細（Tools/KA/DA/ActionScript 各自不同） | ✅ 更精準 |

### 結論

你的設計不是偏離主流，而是主流 HE 尚未抵達的下一階段。主流 HE 2026 還在解決「怎麼把 governance 寫進 code」，你已經在解決「不同類型的工作需要不同程度的 governance」。

---

## 架構總覽

```
                        ┌─────────────────────┐
                        │   User Input         │
                        └──────────┬──────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │  雙軌進入                     │
                    │  ├─ 結構化（Menu/表單）       │
                    │  └─ 自然語言 → Intent Classify│
                    └──────┬──────────────┬───────┘
                           │              │
                 ┌─────────┴──┐    ┌──────┴──────────┐
                 │ 工作/流程   │    │  探索/自由對話    │
                 │ SkillsRAG  │    │  Unrestricted    │
                 │ → 綁定Skill│    │  Mermaid/表格渲染│
                 └──────┬─────┘    └──────┬──────────┘
                        │                 │
              ┌─────────┴──────┐          │
              │  Skill Steps   │          │
              │  步驟 1: Tool/ │          │
              │  步驟 2: DA/KA │          │
              │  步驟 3: AS   │          │
              │  PDCA Check   │          │
              │  ↻ retry      │          │
              │  ? clarify    │          │
              │  ↑ escalate   │          │
              └─────────┬──────┘          │
                        │                 │
              ┌─────────┴──────┐          │
              │  回饋給用戶     │          │
              └────────────────┘──────────┘
```

---

## 執行階段

### P0（已完成 ✅）

- SkillBoard → ActionBoard 改名
- `aitask/tools/executors.py` 合併至 shared
- system_params 補齊（orchestrator.mode, harness.*）
- ArangoDB 備份

### P1（已完成 ✅）

- SkillsRAG 服務（port 8012）：`/upload`, `/match`, `/skills`
- Qdrant collection: `action_skills`
- 登錄 start.sh

### P2（已完成 ✅）

- ActionBoard UI + API 遷移
- 選單更新
- 路由 `/action-board` + `/api/v1/action-scripts`

### P3：Todos 引擎（待執行）

區分兩種執行模式：

| 模式 | 適用 | 裕度 | 實作方式 |
|------|------|------|---------|
| Tool Dispatch | Tool/DA/KA 調用 | 中 | ToolRegistry（已有） |
| ActionScript 執行 | 精準業務邏輯 | 零 | Code 強制執行（新建） |

### P4：PDCA Agent（待執行）

PDCA 四種行為：

```
Check 結果 → Act:
  ├─ ✅ 符合預期 → 繼續下一步（自動）
  ├─ ❌ 不符合 → 擋下，通知
  ├─ ❓ 模糊 → 發出澄清要求（跟用戶確認）
  └─ ⬆️ 超出範圍 → 升級給管理員
```

### P5：開放式聊天強化（待執行）

- Mermaid prompt 注入
- 數學公式渲染

### P6：安全審計 Dashboard（待執行）

- PDCA session 歷史查詢
- Todo 執行記錄
- 技能使用統計

### P7（新增）：SkillsManagement 前端頁面（待執行）

獨立於 ActionBoard：

```
SkillsManagement
  ├── 技能列表（從 SkillsRAG 讀取）
  ├── 上傳 skill.md → 解析 frontmatter + steps → 索引到 Qdrant
  ├── 編輯步驟（可排序、指定 executor 類型）
  └── 授權綁定（關聯到特定 Agent）
```

### P8（新增）：SkillsRAG 串接 Agent Flow（待執行）

```
Intent → SkillsRAG /match → 取得 skill → 注入 system prompt → Agent 依 skill 執行
```

### P9（新增）：LINE 雙軌入口（待執行）

```
LINE Menu（結構化）→ 直接建立 taskSession → 綁定 Skill
LINE 對話（自然語言）→ Intent → SkillsRAG → 匹配 Skill
```

---

## 執行優先序

| 階段 | 內容 | 預估工時 | 相依性 |
|------|------|---------|--------|
| **P0** | 改名 + 合併 + system_params | ✅ 已完 | 無 |
| **P1** | SkillsRAG 服務 | ✅ 已完 | P0 |
| **P2** | ActionBoard UI/API | ✅ 已完 | P0 |
| **P7** | SkillsManagement 前端頁面 | 2-3 天 | P1 |
| **P3** | Todos 引擎（含 ActionScript 執行器） | 5-7 天 | P7 |
| **P8** | SkillsRAG 串接 Agent Flow | 2-3 天 | P3 + P7 |
| **P4** | PDCA Agent（含澄清/升級） | 3-5 天 | P3 + P8 |
| **P9** | LINE 雙軌入口 | 2-3 天 | P8 |
| **P5** | 開放式聊天強化 | 1-2 天 | 無 |
| **P6** | 安全審計 Dashboard | 2-3 天 | P4 |

---

## 成功標準

| 階段 | Done 的定義 |
|------|------------|
| P0~P2 | ✅ 已完成 |
| P7 | 管理者可上傳 skill.md、編輯步驟、綁定 Agent |
| P3 | Tool dispatch + ActionScript 執行器皆可運作，狀態機完整 |
| P8 | Intent → SkillsRAG → Agent context injection 端到端打通 |
| P4 | PDCA 可稽核步驟結果，支援通過/擋下/澄清/升級 |
| P9 | LINE Menu 可直接啟動 skill，LINE 對話可經意圖匹配 skill |
| P5 | 開放聊天可渲染 Mermaid、數學公式 |
| P6 | 管理者可查詢 PDCA 循環、todo 記錄、技能統計 |
