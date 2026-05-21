# 資料深度追蹤系統 (Data Depth Tracker)

> **文件版本**: 1.0.0  
> **最後更新**: 2026-05-17  
> **作者**: Atlas (Master Orchestrator)  
> **狀態**: 規劃完成，待執行

---

## 1. 概述

### 1.1 核心目標

為 ABC Desktop 建立「資料深度追蹤」功能，支援製造企業 8 大追溯場景，讓使用者能透過固定頁面操作 + 自然語言輔助查詢，快速掌握批次資料的完整關聯鏈路。

### 1.2 系統定位

- **所屬功能群組**: EEA-ERP
- **主要資料源**: Ragic ERP（第一版）
- **基礎設施**: 基於現有 RecordTracer + G6 graph 擴展
- **AI 整合**: 關鍵字比對式自然語言輔助（非 LLM）

### 1.3 技術棧

| 層級 | 技術 | 說明 |
|------|------|------|
| 後端引擎 | Python FastAPI | `ai-services/data_agent/trace_engine/` |
| API Gateway | Rust Axum | `api/src/api/da.rs` Proxy |
| 前端頁面 | React + TypeScript + Ant Design 6 | `src/pages/DataDepthTracking/` |
| 圖譜視覺化 | G6 (AntV) | 沿用現有元件 |
| 資料庫 | ArangoDB | `trace_reports` collection |
| 自然語言 | Regex/Keyword 比對 | `nl_trace.py` |

---

## 2. 八大追蹤場景

### 2.1 場景定義

| # | 場景名稱 | ID | 入口 | 方向 | 預設深度 |
|---|----------|-----|------|------|---------|
| 1 | 出貨批號追蹤 | `shipment_batch` | 銷貨單/出貨單批號 | 雙向 | 3 |
| 2 | 進料批號追蹤 | `incoming_batch` | 進貨單批號 | 順流 | 3 |
| 3 | 成品批號全履歷 | `product_full_history` | 成品批號 | 雙向 | 5 |
| 4 | 工單追溯 | `work_order` | 製令單號 | 雙向 | 3 |
| 5 | 客訴/召回追溯 | `complaint_recall` | 成品批號 | 雙向(衝擊) | 3 |
| 6 | 效期追蹤 | `expiry_tracking` | 日期範圍 | 順流 | 3 |
| 7 | 品質異常追溯 | `quality_issue` | QC 批號 | 雙向 | 3 |
| 8 | 供應商追溯 | `supplier_trace` | 供應商代碼 + 日期 | 順流 | 3 |

### 2.2 場景詳細路徑

#### 場景 1：出貨批號追蹤
```
輸入: 出貨批號
路徑: 銷貨單(批號) → 成品庫存(批號) → 
      ├─ 客戶(出貨對象)
      ├─ 庫存餘量(同批)
      └─ 原料批號 → 其他成品(同原料)
輸出: 客戶清單 + 庫存狀況 + 同原料其他成品
```

#### 場景 2：進料批號追蹤
```
輸入: 進貨批號
路徑: 進貨單(批號) → 領料單 → 製令工單 → 成品入庫
輸出: 該原料生產的所有成品批號
```

#### 場景 3：成品批號全履歷
```
輸入: 成品批號
路徑: 成品批號 →
      上游: 製令工單 → 領料單 → 原料批號
      中游: QC 檢驗記錄
      下游: 庫存 → 銷貨單 → 客戶
輸出: 完整原料→生產→QC→庫存→出貨鏈條
```

#### 場景 4：工單追溯
```
輸入: 工單號
路徑: 製令工單 →
      用料: 領料單 → 原料批號
      產出: 成品入庫 → 成品批號
      關聯: 生產需求 → 銷售單 → 客戶
輸出: 用料清單 + 產出成品 + 訂單關聯
```

#### 場景 5：客訴/召回追溯
```
輸入: 客訴成品批號
路徑: 成品批號 →
      下游影響: 銷貨單 → 客戶(哪些客戶收到)
      上游影響: 原料批號 → 供應商
      橫向影響: 同原料 → 其他成品批號
輸出: 影響範圍報告(客戶數、批號數、成品數)
```

#### 場景 6：效期追蹤
```
輸入: 日期區間 + 選擇性物料代碼
路徑: 批次庫存(效期) → 篩選即將到期 →
      成品批號 → 銷貨單 → 客戶
輸出: 即將到期批號清單 + 持有客戶
```

#### 場景 7：品質異常追溯
```
輸入: QC 檢驗記錄 ID
路徑: QC記錄 →
      上游: 進貨單 → 原料批號 → 供應商
      下游: 原料 → 領料單 → 製令 → 成品
輸出: 原料來源 + 所有受影響成品
```

#### 場景 8：供應商追溯
```
輸入: 供應商代碼 + 日期區間
路徑: 供應商 → 進貨單(期間內) →
      原料批號 → 領料單 → 製令 → 成品
輸出: 該供應商原料用於哪些成品
```

---

## 3. 系統架構

### 3.1 模組結構

```
ai-services/data_agent/trace_engine/
├── __init__.py
├── models.py              # Pydantic 資料模型
├── config.py              # 配置載入 + 場景設定
├── base_engine.py         # 抽象基礎引擎
├── forward_engine.py      # 正向追蹤引擎 (場景 1-4)
├── reverse_engine.py      # 反向/衝擊追蹤引擎 (場景 5-8)
├── nl_trace.py            # 自然語言解析
├── report_store.py        # 報告 CRUD (ArangoDB)
├── router.py              # API 端點定義
└── batch_fields_config.json  # 批次欄位映射配置

src/pages/DataDepthTracking/
├── index.tsx              # 頁面入口
├── DataDepthTracking.tsx  # 主要容器
├── scenarioConfig.ts      # 場景定義配置
└── components/
    ├── ScenarioSelector.tsx    # 場景選擇卡
    ├── TraceInputForm.tsx      # 追蹤輸入表單
    ├── TraceGraphView.tsx      # G6 圖譜視覺化
    ├── TraceResultTable.tsx    # 結果表格
    ├── ResultSummary.tsx       # 結果摘要面板
    ├── ReportSaveModal.tsx     # 報告儲存對話框
    └── ReportListPanel.tsx     # 報告列表
```

### 3.2 API 端點

| 方法 | 端點 | 說明 | Timeout |
|------|------|------|---------|
| POST | `/da/trace-engine/scenario/{id}` | 執行指定場景追蹤 | 120s |
| POST | `/da/trace-engine/nl-parse` | NL 查詢解析 | 15s |
| POST | `/da/trace-engine/report/save` | 儲存追蹤報告 | 30s |
| GET | `/da/trace-engine/report/{id}` | 取得單一報告 | 30s |
| GET | `/da/trace-engine/reports` | 報告列表(分頁) | 30s |
| DELETE | `/da/trace-engine/report/{id}` | 刪除報告 | 30s |

### 3.3 資料流

```
使用者 → ScenarioSelector → TraceInputForm → API Call → 
  trace_engine → RecordTracer → Ragic API → DataGraph →
  
  前端接收 TraceResult →
    TraceGraphView (G6 渲染 nodes + edges)
    TraceResultTable (表格渲染)
    ResultSummary (統計摘要)
    ReportSaveModal (可選儲存)
```

---

## 4. 執行計劃

### 4.1 任務分波

| 波次 | 任務 | 依賴 | 並行 |
|------|------|------|------|
| Wave 0 | T0: 批次欄位盤點 | — | — |
| Wave 1 | T1: 模組基礎建設 | — | ✅ 全部並行 |
| | T2: 前端頁面骨架 | — | ✅ |
| | T3: 報告持久層 | T1 | ✅ |
| | T4: 場景配置定義 | T0 | ✅ |
| Wave 2 | T5: 正向引擎 (S1-4) | T1, T4 | ✅ 全部並行 |
| | T6: 反向引擎 (S5-8) | T1, T4 | ✅ |
| | T7: NL 查詢 | T4 | ✅ |
| Wave 3 | T8: 場景選擇器+表單 | T2 | ✅ 全部並行 |
| | T9: 圖譜視覺化 | T2 | ✅ |
| | T10: 表格+明細 | T2 | ✅ |
| | T11: 報告 UI | T2 | ✅ |
| | T12: API 端點 | T3, T5, T6 | ✅ |
| Wave 4 | T13: 前後端整合 | T7, T8-12 | — |
| | T14: 選單+路由註冊 | T13 | — |

### 4.2 依賴矩陣

```
T0 ─→ T4 ─→ T5 ─→ T12 ─→ T13 ─→ T14 → F1-F4
              ↘
T1 ─→ T5, T6 ─→ T12 ─→ T13 ─→ T14 → F1-F4
      T6 ──→ T12 ↗
T2 ─→ T8, T9, T10, T11 ─→ T13 ↗
T3 ─→ T12 ↗
T7 ─→ T13 ↗
```

---

## 5. 邊界與限制

### 5.1 In Scope
- ✅ Ragic ERP 資料深度追蹤（8 場景）
- ✅ 固定頁面操作 + 自然語言輔助輸入
- ✅ 圖譜 + 表格雙視圖（G6）
- ✅ 追蹤結果可儲存為報告
- ✅ EEA-ERP 選單群組

### 5.2 Out of Scope (v1)
- ❌ SAP Parquet 資料湖追蹤（v2）
- ❌ MES 即時串接
- ❌ MRP 計算
- ❌ LLM 驅動的意圖分類
- ❌ PDF/Excel 匯出（v2）
- ❌ 推播通知（v2）
- ❌ 圖譜互動編輯（唯讀視覺化）
- ❌ 多使用者報告分享

### 5.3 非功能性要求

| 項目 | 標準 |
|------|------|
| 單 hop 追蹤 | < 2s |
| 多 hop (depth=3) | < 15s |
| 完整場景 (depth=5) | < 60s |
| 圖譜渲染 (100 nodes) | < 1s |
| 圖譜渲染 (500 nodes) | < 3s |
| 每 hop fan-out 上限 | 50 筆（超過標記 has_more） |

---

## 6. 資料模型

### 6.1 TraceRequest
```json
{
  "scenario": "incoming_batch",
  "entry_table": "ERP_48",
  "entry_batch": "B001",
  "depth": 3,
  "max_fan_out": 50,
  "options": {
    "from_date": "2026-01-01",
    "to_date": "2026-12-31"
  }
}
```

### 6.2 TraceResult
```json
{
  "nodes": [{ "table_key": "...", "ragic_id": "...", "fields": {...}, "depth": 0 }],
  "edges": [{ "from": "...", "to": "...", "via_field": "...", "relation_type": "..." }],
  "summary": { "node_count": 42, "edge_count": 56, "max_depth": 3 },
  "errors": [{ "hop": "production_order", "error": "timeout", "partial": true }],
  "has_results": true,
  "total_time_ms": 2340
}
```

### 6.3 TraceReport (ArangoDB document)
```json
{
  "_key": "report_001",
  "name": "進料批號 B001 追蹤報告",
  "scenario": "incoming_batch",
  "entry_table": "ERP_48",
  "entry_batch": "B001",
  "trace_result": { "...": "full DataGraph" },
  "summary": { "node_count": 42, "edge_count": 56, "max_depth": 3 },
  "tags": ["進料", "緊急"],
  "created_by": "user_key",
  "created_at": "2026-05-17T10:30:00Z"
}
```

---

## 7. 錯誤處理策略

| 情境 | 處理方式 |
|------|----------|
| 批次號碼不存在 | 回傳 `has_results: false`，無 nodes/edges |
| 單 hop Ragic timeout | 回傳部分結果 + `errors[]` 標記該 hop 失敗 |
| 迴圈偵測 | 沿用 RecordTracer `visited` set，自動跳過 |
| 批次號碼格式不一致 | 自動 `.strip().lower()` 正規化 |
| 大 fan-out | 取前 50 筆，標記 `has_more: true` |
| NL 無法解析 | 回傳 `parsed: false` + 提示訊息 |

---

## 8. 相關文件

| 文件 | 說明 |
|------|------|
| [執行計劃](../../../../.sisyphus/plans/data-depth-tracking.md) | 完整任務清單與 QA Scenarios |
| [RecordTracer](../../../../ai-services/data_agent/ragic/record_tracer.py) | 底層 FK 遍歷追蹤器 |
| [RecordLineageGraphModal](../../../../src/pages/data-agent/RecordLineageGraphModal.tsx) | 現有圖譜視覺化元件 |
| [schemaGraphUtils](../../../../src/pages/data-agent/schemaGraphUtils.ts) | G6 圖譜工具函式 |
| [RagicDataAgent規格書](../Ragic/RagicDataAgent規格書.md) | Ragic Data Agent 架構說明 |

---

## 修改歷程

| 日期 | 版本 | 作者 | 變更內容 |
|------|------|------|----------|
| 2026-05-17 | 1.0.0 | Atlas | 初始規格書，從訪談/計劃彙整 |
