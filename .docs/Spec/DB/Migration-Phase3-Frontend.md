---
lastUpdate: 2026-04-02 12:00:00
author: Daniel Chung
version: 1.1.0
---

# Migration Phase 3: 前端頁面更新

## §1 Phase 3 概述

本階段任務是更新前端 Schema 管理頁面與 Query Playground，使其能夠同時支援 SAP 與 Ragic 兩種資料來源。

**核心範圍**：
- 前端 API Types 與介面更新（T3-1）。
- Schema 管理頁面（SchemaPage.tsx）的新增資料來源過濾與 Tab Filter（T3-2 ~ T3-5）。
- 新增資料表 Modal 支援 Ragic 專屬欄位（T3-6）。
- Query Playground 範例更新（T3-8）。

---

## §2 前端架構調整藍圖

前端 Schema 管理頁需同時支援 SAP 與 Ragic 兩種資料來源，以 Tab Filter 區分。

**調整後的 UI 結構**：
```
┌────────────────────────────────────────────────────────────┐
│  資料來源篩選                                               │
│  [全部] [SAP] [Ragic]   ← Tab Filter                     │
├────────────────────────────────────────────────────────────┤
│  模組 篩選                                               │
│  [全部] [BASE] [MFG] [PUR] [INV] [SAL] [CRM] ...       │
│  （依資料來源動態切換模組清單）                              │
├────────────────────────────────────────────────────────────┤
│  統計卡片                                                  │
│  總資料表 | BASE | MFG | PUR | INV | SAL | ...           │
│  （依 data_source + module 統計）                         │
├────────────────────────────────────────────────────────────┤
│  資料表列表                                                │
│  Table ID | Table Name | Module | Tab | Sheet# | S3 Path  │
│            + Status | Actions                             │
├────────────────────────────────────────────────────────────┤
│  欄位列表（選擇資料表後）                                    │
│  Field ID | Field Name | Type | Writable | PK | FK       │
│  （Ragic 模式下顯示 Writable 標記）                        │
└────────────────────────────────────────────────────────────┘
```

---

## §3 詳細任務卡片 (T3-1 ~ T3-8)

### T3-1：更新 API Types

**檔案**：`src/services/dataAgentApi.ts`

**工作內容**：
1. `TableInfo` interface 新增：`tab`, `sheet_key`, `data_source` 欄位。
2. 擴充 `module` 類型，加入 Ragic 的模組分類（BASE, PLM, MFG, PUR, INV, QA, FORM, SAL, CRM, FIN, HR, MES, ADMIN, AI）。

```typescript
export interface TableInfo {
  // ... 現有欄位 ...
  tab?: string;           // Ragic Tab 名稱
  sheet_key?: string;    // Ragic Sheet Key
  data_source: 'sap' | 'ragic';  // 資料來源
  module: string; // 支援 SAP 與 Ragic 兩套模組
}
```

### T3-2：更新 SchemaPage.tsx — 資料來源過濾

**工作內容**：
1. 新增 `dataSourceFilter` state。
2. 更新 `filteredTables` 邏輯，同時依據 `dataSourceFilter` 與 `moduleFilter` 進行篩選。

### T3-3：更新 SchemaPage.tsx — Tab Filter UI

**工作內容**：
1. 在 Statistic Cards 上方新增 `Segmented` 控制項，讓使用者切換 [全部] [SAP] [Ragic]。

### T3-4：更新 SchemaPage.tsx — Module Select 動態化

**工作內容**：
1. 建立 `sapModules` 與 `ragicModules` 清單。
2. 讓 `Select` 的 `options` 根據 `dataSourceFilter` 動態改變。

### T3-5：更新 SchemaPage.tsx — 資料表列表新增欄位

**工作內容**：
1. `tableColumns` 新增 `data_source` Tag 顯示。
2. 新增 `tab` 與 `sheet_key` 欄位。
3. 調整 `module` 欄位的顏色標記邏輯。

### T3-6：更新 SchemaPage.tsx — 新增資料表 Modal

**工作內容**：
1. Form 中新增 `data_source`（必填，下拉選單）、`tab`、`sheet_key` 欄位。
2. 更新 `module` 的下拉選項，包含所有的 SAP 與 Ragic 模組。
3. `s3_path` 的 `placeholder` 根據 `data_source` 動態切換。

### T3-7：更新 SchemaPage.tsx — 欄位 Modal 新增 Writable 標記

**工作內容**：
1. `fieldColumns` 新增 `writable` 欄位顯示（綠色 Tag）。
2. `fieldModalVisible` 的 Form 中新增 `writable` 勾選框。

### T3-8：更新 QueryPlayground.tsx

**檔案**：`src/pages/data-agent/QueryPlayground.tsx`

**工作內容**：
1. 更新預設範例查詢，加入 Ragic 相關業務場景。
2. 驗證 `s3://ragic/` 路徑在 Query Playground 中能被正確解析與顯示。

---

## §4 Ragic 模組分類參考

| Module | 中文 | 代表 Sheets |
|--------|------|-------------|
| `BASE` | 基礎資料 | 編碼原則、組織部門、倉儲位、員工、品項、交易對象 |
| `PLM` | 研發/PLM | 產品主檔、BOM 主檔、物料清單、製程碼 |
| `MFG` | 製造 | 工序管理、BOM、生產製令單、派工單 |
| `PUR` | 採購 | 詢價單、報價單、採購單、進貨單 |
| `INV` | 庫存/倉儲 | 庫存表、盤點單、調撥紀錄、領料單 |
| `SAL` | 銷售 | 銷貨單、銷貨退回、訂購單 |
| `FIN` | 財務/會計 | 收款憑單、付款憑單、發票、應收帳款 |
| `HR` | 人力資源 | 內部教育訓練、訪客登記、人員資料 |
