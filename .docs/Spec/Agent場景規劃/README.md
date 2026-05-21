---
lastUpdate: 2026-05-07 16:30:00
author: Sisyphus
version: 1.1.0
---

# AIBox Agent 場景規劃 — 進銷存 + 人資

> 基於 Ragic ERP，針對 LINE 業務協作場景，設計職責單一（2~3 個工作）的 AI Agent。

## 設計原則

1. **單一職責**：每個 Agent 頂多 2~3 個意圖/工作流程，不包山包海
2. **LINE First**：大部分互動來自 LINE Bot，需考慮群組 @mention 與個人聊天兩種模式
3. **複用現有框架**：`shared/orchestration/`（編排）、`shared/conversation/`（對話歷史）、`shared/tools/`（工具框架）、`shared/llm_resolver.py`（LLM 解析）
4. **動態路由**：Agent 記錄存在 `agents` 集合，LINE Channel 透過 `linked_agent_key` 綁定
5. **資料查詢優先走 Data Agent**：複雜跨表查詢（NL→SQL / Pandas）由 `/da/*` 處理，Agent 只負責意圖判斷與結果呈現

## 文件索引

| # | Agent | 檔案 | 寫入操作 | 確認機制 | 身份綁定 |
|---|-------|------|---------|---------|---------|
| 01 | **訂單小幫手** ✅ | [01-訂單小幫手.md](./01-訂單小幫手.md) | 建立預購單 | ✅ 摘要→確認→執行 | 選用 |
| 02 | **採購小幫手** | [02-採購小幫手.md](./02-採購小幫手.md) | 無（純讀取） | - | 否 |
| 03 | **庫存小幫手** | [03-庫存小幫手.md](./03-庫存小幫手.md) | 無（純讀取） | - | 否 |
| 04 | **進貨小幫手** | [04-進貨小幫手.md](./04-進貨小幫手.md) | 異常回報 | ✅ 摘要→確認→寫入 | 選用 |
| 05 | **詢價小幫手** | [05-詢價小幫手.md](./05-詢價小幫手.md) | 無（純讀取） | - | 否 |
| 06 | **出貨小幫手** | [06-出貨小幫手.md](./06-出貨小幫手.md) | 無（純讀取） | - | 否 |
| 07 | **物料需求小幫手** | [07-物料需求小幫手.md](./07-物料需求小幫手.md) | 無（純讀取） | - | 否 |
| 08 | **請假小幫手** | [08-請假小幫手.md](./08-請假小幫手.md) | 請假申請 | ✅ 摘要→確認→寫入 | ✅ 必要 |
| 09 | **員工資料小幫手** | [09-員工資料小幫手.md](./09-員工資料小幫手.md) | 無（純讀取） | - | 選用 |
| 10 | **出勤小幫手** | [10-出勤小幫手.md](./10-出勤小幫手.md) | 加班申請 | ✅ 摘要→確認→寫入 | ✅ 必要 |

---

## 採購流程 vs Agent 對照

以下以前端 `RagicLogisticProcess.tsx` 的 G6 採購流程圖為基礎，將每個流程節點對應到負責的 Agent：

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  請購單   │    │  詢價單   │    │  採購單   │    │  收貨單   │    │退貨/異常  │
│   (PR)   │───→│  (RFQ)   │───→│   (PO)   │───→│   (GR)   │───→│  (Return)│
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
    └─ 採購小幫手 ─┘ └─詢價小幫手─┘ └─ 採購小幫手 ─┘ └─ 進貨小幫手 ──┘

┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 報價憑證  │    │  訂購單   │    │ 生產需求  │    │ 物料需求  │
│          │───→│   (SO)   │───→│   (PRD)  │───→│  (MRP)   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
└─ 詢價小幫手 ─┘ └─訂單小幫手─┘   └──────────┬───────────┘
                                              │
                                     ┌────────▼────────┐    ┌──────────┐
                                     │  採購預算表      │    │ 生產製令  │
                                     │  (Budget)       │───→│  (MO)    │
                                     └────────┬────────┘    └────┬─────┘
                                              │                  │
                                     ┌────────▼────────┐    ┌────▼─────┐
                                     │ 物料需求小幫手   │    │ 製令→領料 │
                                     └─────────────────┘    │ →派工→入庫│
                                                             └──────────┘
```

## Agent 總覽

| 領域 | Agent | 工作流程 (Intents) | 優先級 | LINE 適用性 | 前端流程對應 |
|------|-------|-------------------|--------|------------|------------|
| 進銷存 | **訂單小幫手** ✅ 現有 | 3 | P0 | ⭐⭐⭐ | 訂購單(SO)、預購單 |
| 進銷存 | **庫存小幫手** | 2 | P0 | ⭐⭐⭐ | 庫存表(STOCK_16/17) |
| 進銷存 | **採購小幫手** 🆕 含請購 | 3 | P0 | ⭐⭐⭐ | 請購單(PR)→採購單(PO) |
| 進銷存 | **進貨小幫手** ⬆ P2→P1 | 2 | P1 | ⭐⭐ | 收貨單(GR)→退貨異常 |
| 進銷存 | **詢價小幫手** 🆕 NEW | 2 | P1 | ⭐⭐ | 詢價單(RFQ)+報價憑證 |
| 進銷存 | **出貨小幫手** | 2 | P1 | ⭐⭐ | 銷貨單+銷退 |
| 進銷存 | **物料需求小幫手** 🆕 NEW | 2 | P2 | ⭐ | 物料需求單(MRP)+採購預算表 |
| 人資 | **請假小幫手** | 3 | P0 | ⭐⭐⭐ | — |
| 人資 | **員工資料小幫手** | 2 | P1 | ⭐⭐⭐ | — |
| 人資 | **出勤小幫手** | 2 | P2 | ⭐⭐ | — |

---

## 進銷存 Agents

### 1. 訂單小幫手 ✅（已存在）

> **Agent Key**: `order_secretary`
> **路徑**: `ai-services/bpa/order_secretary/`（已實作）
> **Ragic 關聯表單**: ERP_14（訂購單）、ERP_59（報價憑證）
> **前端對應**: BrowseAgent 的「預訂購」按鈕 + PreorderBoard 看板

| 工作流程 | 意圖 | 說明 |
|---------|------|------|
| 接單/預購 | `order_text` | 接收 LINE 文字/圖片 → LLM 提取訂購品項 → 寫入 `order_preorders` |
| 訂單查詢 | `order_track` | 查詢該用戶的預購單狀態（開立/處理中/已完成） |
| 產品列表 | `product_list` | 查詢可預購品項/庫存列表，讓客戶挑選（走 `STOCK_16` Ragic sheet） |

**現狀**：Phase 1 已上線，支援 LINE 文字 + 圖片/檔案上傳建立預購單。意圖分類使用 `intent_catalog`。

**既有技能/API**：
- `POST /order-secretary/skills/order_preorder_collect` — 預購單收集統一技能（text/image/file/structured）
- `query_preorder_items` (SKL-2618-002) — 查詢 `STOCK_16` 庫存品項
- `order_preorders` / `order_preorder_items` — ArangoDB 預購單主表明細集合

---

### 2. 採購小幫手 🆕 含請購單

> **Agent Key**: `purchase_assistant`
> **建議路徑**: `ai-services/bpa/purchase_assistant/`
> **Ragic 關聯表單**: ERP_13（採購單）、CONFIGURATIONFILE_10（供應商）、請購單（PR，需確認 Ragic Sheet ID）
> **前端對應**: RagicLogisticProcess 流程圖中的「請購單」→「採購單」

| 工作流程 | 意圖觸發 | 說明 |
|---------|---------|------|
| 請購查詢 | `pr_query` | 查詢請購單狀態（已提出/已轉採購/已結案） |
| 採購單查詢 | `po_query` | 依單號/日期/供應商查詢採購單狀態（開立/待核簽/已簽核/轉收貨） |
| 供應商查詢 | `vendor_query` | 查詢供應商基本資訊、聯絡方式、付款條件、歷史交易（CONFIGURATIONFILE_10） |

**典型 LINE 對話**：
```
User: PR-202605001 這張請購單核准了嗎？
Agent: 請購單 PR-202605001（申請部門：生產部）：
  - 品項：A001 原料 x 1000 KG
  - 狀態：已轉採購 → PO-202605003
  - 申請人：王小明

User: PO-202605003 現在到哪了？
Agent: 採購單 PO-202605003（供應商：XX食品）：
  - 品項：A001 原料 x 1000 KG
  - 狀態：已簽核／部分收貨（已收 600 KG / 總計 1000 KG）
  - 預計交期：2026-05-10
  - 收貨單：GR-202605001 (600 KG, 05/06)
```

**實作要點**：
- 請購(PR) + 採購(PO) 放在同一個 Agent 是因為請購→採購是連續流程，USER 經常混著問
- 供應商查詢直接走 Ragic Proxy API（CONFIGURATIONFILE_10 已有完整 field ID mapping）
- 採購單跨表查詢（含供應商名稱）走 Data Agent NL→SQL
- 若現有 Data Agent 採購意圖（`rgc_c01`~`rgc_c03`）已涵蓋，優先複用

---

### 3. 庫存小幫手

> **Agent Key**: `inventory_assistant`
> **建議路徑**: `ai-services/bpa/inventory_assistant/`
> **Ragic 關聯表單**: STOCK_16（庫存表）、STOCK_17（倉儲庫存表）、盤點單、調撥紀錄
> **前端對應**: QueryPlayground 的庫存查詢範例、Data Agent Schema 分類

| 工作流程 | 意圖觸發 | 說明 |
|---------|---------|------|
| 庫存查詢 | `inv_query` | 查詢特定品項的即時庫存量、倉儲位置。走 Data Agent (`/da/query/nl`) |
| 庫存異動記錄 | `inv_movement` | 查詢某品項的調撥/入庫/出庫歷史記錄 |

**典型 LINE 對話**：
```
User: 請問A001原料目前庫存多少？
Agent: A001（XX原料）目前庫存 1,500 KG，存放於 倉庫A-01-03 儲位。

User: 這批貨最近有進出記錄嗎？
Agent: A001 最近 7 天異動：
  - 05/05 入庫 +500 KG（採購單 PO-202605001）
  - 05/04 出庫 -200 KG（領料單 MO-202605003）
```

**實作要點**：
- 庫存查詢走 Data Agent NL→SQL（`/da/query/nl`），不走 KA HybridRAG
- 庫存異動查詢走 Data Agent Pandas 引擎
- 既有 `query_preorder_items` skill 的 `STOCK_16` 快取(`shared/ragic_cache.py`)可直接複用

---

### 4. 進貨小幫手 ⬆ 提升優先級(P2→P1)

> **Agent Key**: `receiving_assistant`
> **建議路徑**: `ai-services/bpa/receiving_assistant/`
> **Ragic 關聯表單**: ERP_15（收貨單）、ERP_48/ERP_16（進貨/退貨異常）
> **前端對應**: RagicLogisticProcess 流程圖中的「收貨單」→「退貨/進貨異常」節點

| 工作流程 | 意圖觸發 | 說明 |
|---------|---------|------|
| 收貨查詢 | `gr_query` | 查詢收貨單狀態（待收/已收/部分收）、品項數量、檢驗結果 |
| 退貨/異常追蹤 | `gr_return` | 查詢退貨處理狀態、異常原因、後續處理進度 |

**典型 LINE 對話**：
```
User: PO-202605003 這批貨收貨了嗎？
Agent: 採購單 PO-202605003（供應商：XX食品）：
  - 收貨狀態：已收 600 KG / 總計 1000 KG
  - 收貨單 GR-202605001（2026-05-06）
  - IQC 結果：待檢驗

User: 那批退貨處理好了嗎？
Agent: 退貨單 RET-202605001（原採購單 PO-202605003）：
  - 退貨品項：A001 原料 x 200 KG
  - 原因：規格不符
  - 狀態：已退回供應商（2026-05-07）
```

**提升優先級原因**：前端流程圖明確顯示「收貨→退貨異常」是閉環流程，且退貨異常直接影響採購單狀態，業務上為高頻操作。

---

### 5. 詢價小幫手 🆕 NEW

> **Agent Key**: `quotation_assistant`
> **建議路徑**: `ai-services/bpa/quotation_assistant/`
> **Ragic 關聯表單**: ERP_59（詢價單／報價憑證）、CONFIGURATIONFILE_10（供應商）
> **前端對應**: RagicLogisticProcess 流程圖中的「詢價單」+「報價憑證」節點

| 工作流程 | 意圖觸發 | 說明 |
|---------|---------|------|
| 詢價查詢 | `rfq_query` | 查詢詢價單狀態、供應商報價狀況、比價結果 |
| 報價查詢 | `quote_query` | 查詢報價憑證（歷史報價、產品別報價、客戶別報價） |

**典型 LINE 對話**：
```
User: RFQ-202605001 有幾家報價了？
Agent: 詢價單 RFQ-202605001（品項：A001 原料 x 1000 KG）：
  - 已報價：3 家 / 發出 5 家
  - 最低價：XX食品 $15.5/KG
  - 截止報價日：2026-05-10

User: A001 原料上次跟哪家買？多少錢？
Agent: A001 原料歷史採購記錄：
  - 最近一次：XX食品 $15.5/KG（2026-04-15）
  - 前次：YY原料 $16.0/KG（2026-03-20）
```

**為何獨立成一個 Agent**：
- 詢價/報價的業務流程與採購(PO)不同——它屬於前置作業，關注的是比價、供應商選擇
- 如果合併到採購小幫手會超過 3 個工作（已有請購/採購/供應商）
- 前端流程圖中「詢價單」和「報價憑證」是獨立節點，有明確的業務邊界

---

### 6. 出貨小幫手

> **Agent Key**: `shipping_assistant`
> **建議路徑**: `ai-services/bpa/shipping_assistant/`
> **Ragic 關聯表單**: ERP_26（銷貨單）、銷貨退回單、配貨揀貨單
> **前端對應**: 未在採購流程圖中（屬下游銷售），從 Data Agent Schema 分類歸入「進銷存」

| 工作流程 | 意圖觸發 | 說明 |
|---------|---------|------|
| 銷貨查詢 | `so_query` | 查詢銷貨單狀態、出貨進度 |
| 銷退處理 | `so_return` | 查詢銷貨退回單狀態 |

**典型 LINE 對話**：
```
User: 銷貨單 SO-202605008 出貨了嗎？
Agent: 銷貨單 SO-202605008（客戶：OO食品）：
  - 品項：B002 成品 x 200 箱
  - 出貨狀態：已出貨（2026-05-06）
  - 配送方式：貨運
```

---

### 7. 物料需求小幫手 🆕 NEW

> **Agent Key**: `mrp_assistant`
> **建議路徑**: `ai-services/bpa/mrp_assistant/`
> **Ragic 關聯表單**: ERP_42（物料需求單）、ERP_41（採購預算表）
> **前端對應**: RagicLogisticProcess 流程圖中的「物料需求單(MRP)」→「採購預算表」

| 工作流程 | 意圖觸發 | 說明 |
|---------|---------|------|
| 物料需求查詢 | `mrp_query` | 查詢物料需求單狀態、料況缺口、建議採購量 |
| 採購預算查詢 | `budget_query` | 查詢採購預算使用狀況、剩餘額度 |

**典型 LINE 對話**：
```
User: 這個月的物料需求出來了嗎？
Agent: 本月物料需求單 MRP-202605：
  - A001 原料：需求 5,000 KG，庫存 1,500 KG，缺口 3,500 KG
  - B002 包材：需求 10,000 個，庫存 3,000 個，缺口 7,000 個
  - 建議採購總金額：約 $85,000

User: 採購預算還有多少？
Agent: 本月採購預算：
  - 總預算：$500,000
  - 已使用：$320,000（含 PO-202605001~005）
  - 剩餘：$180,000
```

**實作要點**：
- MRP 計算邏輯較複雜（BOM 展開、庫存扣抵），建議走 Data Agent Pandas 引擎
- LINE 適用性較低（⭐），因物料需求偏向規劃性質，非即時查詢

---

## 人資 Agents

### 8. 請假小幫手

> **Agent Key**: `leave_assistant`
> **建議路徑**: `ai-services/bpa/leave_assistant/`
> **Ragic 關聯表單**: 員工管理（含假別/剩餘時數）、假單（需確認 Ragic Sheet ID 或自建）

| 工作流程 | 意圖觸發 | 說明 |
|---------|---------|------|
| 假別/餘額查詢 | `leave_balance` | 查詢個人剩餘特休、病假、事假時數 |
| 請假申請 | `leave_apply` | 提交請假申請（日期、假別、原因）→ 寫入 Ragic 假單或 `leave_requests` 集合 |
| 請假紀錄 | `leave_history` | 查詢個人請假歷史紀錄 |

**典型 LINE 對話**：
```
User: 我還有幾天特休？
Agent: 您目前剩餘假別：
  - 特休：7.5 天
  - 事假：3 天
  - 病假：已使用 2 天（全年度）

User: 我要請假 5/10 特休一天
Agent: 已為您建立請假申請（假別：特休，日期：2026-05-10，共 1 天），
       待主管審核中。申請單號：LV-202605001。
```

**實作要點**：
- 假別查詢：讀取 Ragic `員工管理` 表單中的假別欄位
- 請假申請：視 Ragic 是否有假單 Sheet，無則自建 `leave_requests` 集合（參考 `order_preorders` 模式）
- 需要員工身份驗證（LINE user_id 對應 Ragic 員工編號）
- **身份綁定**：需建立 LINE user_id ↔ 員工編號 的映射（`user_bindings` 集合）

---

### 9. 員工資料小幫手

> **Agent Key**: `employee_directory`
> **建議路徑**: `ai-services/bpa/employee_directory/`
> **Ragic 關聯表單**: 員工管理（CONFIGURATIONFILE_7）、組織部門（CONFIGURATIONFILE_2）

| 工作流程 | 意圖觸發 | 說明 |
|---------|---------|------|
| 員工查詢 | `emp_query` | 查詢員工基本資料（部門、職稱、分機） |
| 組織架構 | `org_chart` | 查詢部門組織與成員列表 |

**典型 LINE 對話**：
```
User: 王小明是哪個部門的？
Agent: 王小明（員工編號 EMP-00042）
  - 部門：生產部 - 製造課
  - 職稱：課長
  - 分機：#231

User: 生產部有哪些人？
Agent: 生產部（主管：陳經理）共 15 人：
  - 製造課：王小明(課長)、李大同、...
  - 品管課：張小花(課長)、...
```

**實作要點**：
- 查詢直接走 Ragic Proxy API（簡單單表查詢，不需 Data Agent）
- 組織架構需要遞迴查詢（部門→子部門→員工），可在 Agent 內實作
- 員工照片可考慮透過 LINE 多媒體訊息回傳

---

### 10. 出勤小幫手

> **Agent Key**: `attendance_assistant`
> **建議路徑**: `ai-services/bpa/attendance_assistant/`
> **Ragic 關聯表單**: 員工管理（班別）、工序報工單（MES）、打卡紀錄（可能有對應 Ragic Sheet 或外掛系統）

| 工作流程 | 意圖觸發 | 說明 |
|---------|---------|------|
| 出勤查詢 | `attn_query` | 查詢個人出勤/打卡紀錄 |
| 加班申請 | `ot_apply` | 提交加班申請 |

**實作要點**：
- 出勤資料若不在 Ragic 而在外部系統（如門禁打卡機），需先確認資料來源
- 此 Agent 優先級最低，建議先完成前 9 個再評估

---

## 共用技術方案

### 身份綁定（跨 Agent 共用）

所有需要「知道是誰」的 Agent（請假、出勤、訂單查詢、員工查詢）都需要 LINE user_id → Ragic 員工編號的映射。

```
集合: user_bindings
{
  "_key": "line:{channel_key}:{line_user_id}",
  "platform": "line",
  "channel_key": "...",
  "line_user_id": "...",
  "employee_id": "EMP-00042",
  "employee_name": "王小明",
  "department": "生產部",
  "bound_at": "2026-05-01T10:00:00Z",
  "bound_by": "admin"  // HR 管理員於後台綁定
}
```

**建議放在 `shared/` 層級**，作為共用能力提供給所有 Agent。

### Agent 目錄模板

每個 Agent 遵循以下結構（以 `leave_assistant` 為例）：

```
ai-services/bpa/leave_assistant/
├── __init__.py
├── main.py              # FastAPI 入口（獨立啟動用）
├── router.py            # ★ API Router → `/chat` 端點
├── agent.py             # Agent 核心邏輯（意圖分類 + 執行）
├── config.py            # 環境變數
├── skills/              # Agent 專用技能（非共用）
│   └── ragic_leave.py   # Ragic 請假相關操作
└── graph/               # LangGraph 節點（選用）
    ├── state.py
    └── builder.py
```

### LINE 整合模式

所有 Agent 共用現有 LINE Webhook 架構，無需修改 `unified_agents/platforms/line/webhook.py`：

```
LINE Channel → 設定 linked_agent_key → webhook 讀取 agent.endpoint_url → POST /chat
```

前端 `ragicChatStore`（`src/stores/chatStore.ts`）已提供採購流程 AI 問答面板，新 Agent 可考慮複用此模式。

### Agent 註冊資料範例

```json
{
  "_key": "leave_assistant",
  "name": "請假小幫手",
  "agent_type": "bpa",
  "endpoint_url": "http://localhost:8011/leave-assistant/chat",
  "llm_model": "deepseek:DeepSeek-V4-Flash",
  "source": "local",
  "tools": ["line_bot_key"],
  "visibility": "public",
  "system_prompt": "你是一個專業的請假小幫手，協助員工透過 LINE 查詢假別餘額、提交請假申請...",
  "status": "enabled"
}
```

### 既有可複用基礎建設

| 元件 | 位置 | 用途 |
|------|------|------|
| Ragic 資料快取 | `shared/ragic_cache.py` | 快取 263 張 Ragic 表，TTL 可配置 |
| Data Agent NL→SQL | `data_agent/ragic/` → `/da/query/nl` | 自然語言查詢 Ragic 資料 |
| Data Agent 採購意圖 | `datalake/seed_intent_catalog_ragic.py` (rgc_c01~c03) | 進貨單/供應商採購統計 |
| 對話歷史 | `shared/conversation/` | `bot_chat_sessions` 持久化 |
| LLM 解析 | `shared/llm_resolver.py` | Provider → base_url + api_key |
| 預購單 CRUD | `bpa/order_secretary/preorder.py` | `order_preorders` + `order_preorder_items` |

---

## 實施路徑建議

| Phase | Agent | 依賴 | 預估工時 | 備註 |
|-------|-------|------|---------|------|
| **P0 - 核心** | 訂單小幫手 ✅ (已完成) | - | - | LINE 已上線 |
| **P0 - 核心** | 採購小幫手 | Data Agent 採購 NL→SQL + Ragic Proxy | 3-5 天 | 含請購單(PR)+採購單(PO)+供應商 |
| **P0 - 核心** | 庫存小幫手 | Data Agent NL→SQL + 複用 STOCK_16 快取 | 3-5 天 | 可複用現有 `query_preorder_items` skill |
| **P0 - 核心** | 請假小幫手 | `shared/user_binding.py` 共用模組 | 5-7 天 | 需先確認 Ragic 假單 Sheet 或自建 |
| **P1 - 重要** | 進貨小幫手 | Data Agent + Ragic Proxy | 2-3 天 | 含收貨(GR) + 退貨異常 |
| **P1 - 重要** | 員工資料小幫手 | `shared/user_binding.py` + Ragic Proxy | 3-5 天 | 組織遞迴查詢較複雜 |
| **P1 - 重要** | 詢價小幫手 | Ragic Proxy (ERP_59) | 2-3 天 | 流程圖中的獨立節點 |
| **P2 - 次要** | 出貨小幫手 | Data Agent | 2-3 天 | — |
| **P2 - 次要** | 物料需求小幫手 | Data Agent Pandas 引擎 | 3-5 天 | MRP 計算邏輯較複雜，LINE 適用性低 |
| **P2 - 次要** | 出勤小幫手 | 需先確認資料來源 | 3-5 天 | 門禁打卡資料可能不在 Ragic |

### 共用基礎建設先決條件

1. **`shared/user_binding.py`** — LINE user_id ↔ 員工編號 映射（所有需要身份識別的 Agent 共用）
2. **Data Agent 進銷存場景調校** — 請購(PR)、採購(PO)、收貨(GR)、庫存(STOCK) 的 NL→SQL 語意覆蓋率需先補齊
3. **Ragic Proxy API 唯讀查詢封裝** — 簡單單表查詢（供應商、員工）不走 Data Agent，封裝在 `shared/ragic_proxy.py`

---

## 各 Agent Intent Catalog 規劃

每個 Agent 的意圖註冊在 `intent_catalog` 集合中，透過 `agent_key` 關聯：

### purchase_assistant (採購小幫手)

| name | nl_patterns | 說明 |
|------|------------|------|
| `pr_query` | 請購, PR-, 請購單, 請購進度, 請購什麼 | 查詢請購單狀態 |
| `po_query` | 採購單, PO-, 採購進度, 採購什麼, 採購到哪 | 查詢採購單狀態 |
| `vendor_query` | 供應商, 廠商, 供應商資料, vendor, 交易對象 | 查詢供應商資訊 |

### inventory_assistant (庫存小幫手)

| name | nl_patterns | 說明 |
|------|------------|------|
| `inv_query` | 庫存, 還有多少, 庫存量, 庫存查詢, 剩多少, stock | 查詢品項即時庫存 |
| `inv_movement` | 異動記錄, 進出記錄, 調撥紀錄, 最近進出 | 查詢庫存異動歷史 |

### receiving_assistant (進貨小幫手)

| name | nl_patterns | 說明 |
|------|------------|------|
| `gr_query` | 收貨, 進貨, 收貨單, GR-, 收貨進度, 到貨 | 查詢收貨/進貨單狀態 |
| `gr_return` | 退貨, 異常, 退貨單, RET-, 退貨進度, 不合格 | 查詢退貨/異常處理狀態 |

### quotation_assistant (詢價小幫手)

| name | nl_patterns | 說明 |
|------|------------|------|
| `rfq_query` | 詢價, RFQ-, 詢價單, 比價, 報價狀況 | 查詢詢價單與比價狀況 |
| `quote_query` | 報價, 報價單, 歷史報價, 上次買多少 | 查詢歷史報價/報價憑證 |

### shipping_assistant (出貨小幫手)

| name | nl_patterns | 說明 |
|------|------------|------|
| `so_query` | 銷貨, 出貨, 銷貨單, SO-, 出貨進度 | 查詢銷貨單狀態 |
| `so_return` | 銷退, 銷貨退回, 退貨單 | 查詢銷貨退回單狀態 |

### mrp_assistant (物料需求小幫手)

| name | nl_patterns | 說明 |
|------|------------|------|
| `mrp_query` | 物料需求, MRP, 料況, 需求單, 缺口 | 查詢物料需求單狀態 |
| `budget_query` | 預算, 採購預算, 預算表, 還剩多少錢 | 查詢採購預算使用狀況 |

### leave_assistant (請假小幫手)

| name | nl_patterns | 說明 |
|------|------------|------|
| `leave_balance` | 特休, 剩餘假, 還有幾天假, 假別, 休假額度 | 查詢假別餘額 |
| `leave_apply` | 請假, 我要休假, 申請休假, 請休 | 提交請假申請 |
| `leave_history` | 請假紀錄, 休過哪些假, 假單查詢, 歷史請假 | 查詢個人請假歷史 |

### employee_directory (員工資料小幫手)

| name | nl_patterns | 說明 |
|------|------------|------|
| `emp_query` | 在哪個部門, 分機, 員工資料, 誰是, 同事 | 查詢員工基本資料 |
| `org_chart` | 組織, 部門有哪些人, 部門成員, 組織架構 | 查詢部門組織 |

---

## 相關文件

- [Ragic小幫手規格書](../智能體/Ragic小幫手.md) — 現有 Ragic Agent 實作參考
- [Data Agent 規格書](../智能體/數據處理智能體（Data Agent）/Data-Agent 規格書.md) — NL→SQL 底層能力
- [BPA 物料管理規格書](../後台/BPA/material-management-bpa-spec.md) — SAP MM 採購工作流規格
- [智能體通用 Orchestrator 規格書](../智能體/智能體通用Orchestrator規格書.md) — 編排框架
- [LINE 設置規格書](../基礎工具/通信工具/LINE設置規格書.md) — LINE Bot 整合
- [DB Ragic Schema](../DB/RagicTableSchema.md) — Ragic 表單對照
- [AGENTS.md](../../../AGENTS.md) — 專案開發規範

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-05-07 | 1.1.0 | Sisyphus | 加入前端採購流程對照；新增詢價小幫手、物料需求小幫手；採購小幫手擴充含請購單；進貨小幫手提升到 P1 |
| 2026-05-07 | 1.0.0 | Sisyphus | 初始版本：進銷存 5 Agent + 人資 3 Agent 場景規劃 |
