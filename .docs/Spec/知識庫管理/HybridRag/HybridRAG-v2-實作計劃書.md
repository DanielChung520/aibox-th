---
lastUpdate: 2026-04-18 00:43:35
author: Daniel Chung
version: 1.0.0
---

# HybridRAG v2 實作計劃書

## 文件定位

本計劃書依據 `.docs/Spec/知識庫管理/HybridRag/HybridRAG-細部規格書-v2.md` 制定，
用於追蹤 HybridRAG 從 v1（混合檢索）升級為 v2（有界探查與證據組裝層）的實作進度。

---

## 實作目標摘要

將 HybridRAG 從「vector + graph + RRF 混合搜尋」升級為「Bounded Evidence Assembly」系統：

> 在有限邊界、有限成本、有限時間內，組裝出最小但足以支持或反駁當前假設的證據集合。

---

## Phase 架構

```
Phase 1 ─── 輸入輸出契約重構（新增 v2 API）
Phase 2 ─── Boundary Governance（邊界檢查）
Phase 3 ─── Inquiry Decomposition（Hypothesis → InquiryPlan）
Phase 4 ─── Contradiction Preservation + Gap Detection
Phase 5 ─── 狀態機整合 + Stop Logic
```

每個 Phase 皆為獨立的遞交單位，完成一個 Phase 才進下一個。

---

## Phase 1：輸入輸出契約重構

### 目標

- 新增 v2 API：`POST /hybrid/evidence`
- 讓 HybridRAG 接受 `Boundary + Hypothesis + InquiryPlan + ContextSignals` 輸入
- 輸出 `EvidenceSet + AuditRecord`，而非 `HybridSearchResponse`
- 現有 v1 `/hybrid/search` API 保持向後相容

### 新增檔案

```
ai-services/knowledge_agent/hybrid_rag/
├── models/
│   ├── __init__.py
│   ├── evidence.py           # EvidenceUnit, EvidenceSet, AuditRecord dataclass
│   └── inquiry.py            # Boundary, Hypothesis, InquiryPlan, ContextSignals dataclass
```

### 現有檔案改動

| 檔案 | 改動內容 |
|------|---------|
| `hybrid_rag/service.py` | 新增 `evidence_search()` 方法（Phase 1 核心） |
| `hybrid_rag/router.py`  | 新增 `/hybrid/evidence` 路由 |

### 驗收標準

- [ ] `POST /hybrid/evidence` 接受新輸入格式
- [ ] 回傳 `EvidenceSet` 含 `evidences[]`、`boundary_status`、`sufficiency`、`gaps[]`、`next_step`
- [ ] 回傳 `AuditRecord` 含 `channels_used[]`、`discarded_candidates`、`stop_reason`
- [ ] 現有 `/hybrid/search` 不受影響
- [ ] 單元測試通過

### 詳細任務

- [ ] Task 1.1：建立 `models/evidence.py` — `EvidenceUnit`、`EvidenceSet`、`AuditRecord` dataclass
- [ ] Task 1.2：建立 `models/inquiry.py` — `Boundary`、`Hypothesis`、`InquiryPlan`、`ContextSignals` dataclass
- [ ] Task 1.3：重構 `HybridRAGService` — 新增 `evidence_search()` 方法，封裝 Hypothesis → Inquiry → Retrieval → Assembly → EvidenceSet 流程
- [ ] Task 1.4：新增 `/hybrid/evidence` API 路由
- [ ] Task 1.5：單元測試

---

## Phase 2：Boundary Governance

### 目標

在 retrieval 前執行完整邊界檢查，確保所有候選來源符合 `root_id / role / ontology / lifecycle / usage` 約束。

### 新增檔案

| 檔案 | 說明 |
|------|------|
| `hybrid_rag/boundary_checker.py` | 邊界檢查器 |

### Boundary 檢查項目

| 檢查 | 說明 |
|------|------|
| `root_id` | 知識庫是否存在且允許 |
| `role_scope` | 使用者角色是否有權限 |
| `ontology_scope` | 領域是否在允許範圍內 |
| `lifecycle_scope` | 知識狀態是否可用（active） |
| `usage_scope` | 用途是否允許本次操作 |

### 邊界結果處理

| 結果 | 狀態 | 後續動作 |
|------|------|---------|
| `within_boundary` | 可正常檢索 | 進入 retrieval |
| `boundary_unclear` | 資訊不足 | `clarify_required` |
| `out_of_boundary` | 明確越界 | `stop` / reject |

### 驗收標準

- [ ] retrieval 前所有候選經過 boundary check
- [ ] `out_of_boundary` 的結果被標記並排除（不进 fusion）
- [ ] `boundary_unclear` 時 API 回傳 `clarify_required` 狀態
- [ ] 邊界檢查結果寫入 AuditRecord

### 詳細任務

- [ ] Task 2.1：建立 `boundary_checker.py` — 實作 5 項邊界檢查
- [ ] Task 2.2：整合進 `evidence_search()` — retrieval 前呼叫
- [ ] Task 2.3：邊界失敗時的 early return 邏輯
- [ ] Task 2.4：單元測試

---

## Phase 3：Inquiry Decomposition

### 目標

廢除「沒有 hypothesis 就直接全量 hybrid search」，實作 Hypothesis → InquiryPlan 轉換。

### 新增檔案

| 檔案 | 說明 |
|------|------|
| `hybrid_rag/inquiry_decomposer.py` | Hypothesis 轉 InquiryPlan |

### Inquiry Decomposition 職責

- 分析 Hypothesis 的 `statement` 和 `candidate_anchors`
- 產生 `sub_questions[]`（分解後的子問題）
- 決定 `allowed_channels[]`（vector / graph / raw / prior）
- 分配 `cost_budget`（hop count、top_k、time_budget_ms）
- 設定 `stop_conditions[]`

### 處理無 Hypothesis 的查詢

若 API 收到純 `query` 而無 `hypothesis_id`，自動包裝為隱性 Hypothesis：
- `statement` = query 本身
- `required_evidence_types` = 由 QueryClassifier 推斷
- 仍走完整流程，不允許直接全量 hybrid search

### 驗收標準

- [ ] 所有查詢都經過 InquiryPlan 轉換
- [ ] `InquiryPlan` 的 `sub_questions` 決定了 retrieval 策略
- [ ] channel 配置影響實際呼叫哪個檢索器
- [ ] 隱性 Hypothesis 機制運作正常

### 詳細任務

- [ ] Task 3.1：建立 `inquiry_decomposer.py`
- [ ] Task 3.2：整合進 `evidence_search()` — 每次呼叫前都做 decomposition
- [ ] Task 3.3：隱性 Hypothesis 自動生成邏輯
- [ ] Task 3.4：單元測試

---

## Phase 4：Contradiction Preservation + Gap Detection

### 目標

廢除「矛盾被 RRF 抹平」，實作對立證據保留與缺口檢測。

### 新增檔案

| 檔案 | 說明 |
|------|------|
| `hybrid_rag/evidence_analyzer.py` | 矛盾檢測 + 缺口分析 |

### 核心邏輯

**矛盾檢測**：
- 同一 Hypothesis 下，evidence 分 `supports[]` 和 `contradicts[]` 兩組
- 矛盾不抹平，都寫入 `EvidenceSet.contradictions[]`

**缺口檢測**：
- 比對 `Hypothesis.required_evidence_types` vs 實際蒐集到的類型
- 缺口寫入 `EvidenceSet.gaps[]`
- 建議下一步：`ask_for_clarification | expand_graph | stop | handoff_to_human`

### 驗收標準

- [ ] 對立證據同時存在於 `EvidenceSet.evidences[]` 和 `EvidenceSet.contradictions[]`
- [ ] 缺口被正確識別並寫入 `gaps[]`
- [ ] `next_step` 給出具體下一步建議

### 詳細任務

- [ ] Task 4.1：建立 `evidence_analyzer.py` — contradiction detection + gap analysis
- [ ] Task 4.2：整合進 `evidence_search()` — assembly 後呼叫
- [ ] Task 4.3：單元測試

---

## Phase 5：狀態機整合 + Stop Logic

### 目標

將整個流程統一為 8 狀態機，明確 stop / clarify / handoff 邏輯。

### 新增檔案

| 檔案 | 說明 |
|------|------|
| `hybrid_rag/state_machine.py` | 狀態機定義 + 轉換邏輯 |

### 狀態機定義

| 狀態 | 說明 |
|------|------|
| `boundary_checking` | 邊界驗證中 |
| `planning` | Hypothesis → InquiryPlan 轉換中 |
| `retrieving` | 各 channel 檢索中 |
| `assembling` | 候選 → EvidenceUnit 組裝中 |
| `evaluating` | 充足性 / 矛盾 / 缺口評估中 |
| `stopped` | 已足夠或不能再繼續 |
| `clarify_required` | 需向 user 追問 |
| `handoff_required` | 需交由人類判斷 |

### Stop Conditions

| 條件 | 動作 |
|------|------|
| `evidence_sufficient` | `stopped` |
| `boundary_unclear` | `clarify_required` |
| `out_of_boundary` | `stopped` |
| `budget_exhausted` | `stopped` |
| `contradictory_unresolved` | `clarify_required` 或 `handoff_required` |

### 升級條件

以下情況應升級至 `handoff_required`：
- 需要跨知識庫
- 需要跨權限資料
- 高風險問題（策略、法務、財務責任）
- 證據矛盾且預算內無法解決

### 驗收標準

- [ ] 狀態機追蹤完整生命週期
- [ ] `AuditRecord` 包含 `stop_reason`
- [ ] 各 stop condition 正確�發
- [ ] `clarify_required` / `handoff_required` 有 API 回應

### 詳細任務

- [ ] Task 5.1：建立 `state_machine.py`
- [ ] Task 5.2：重構 `evidence_search()` — 以狀態機驅動
- [ ] Task 5.3：Stop condition + 升級條件實作
- [ ] Task 5.4：整合測試（端到端）

---

## Phase 依賴關係

```
Phase 1（輸入輸出契約）
  ↓
Phase 2（Boundary Governance）← 需要 Phase 1 的 dataclass
  ↓
Phase 3（Inquiry Decomposition）← 需要 Phase 1 的 dataclass
  ↓
Phase 4（Contradiction + Gap）← 需要 Phase 2, 3
  ↓
Phase 5（狀態機整合）← 需要 Phase 2, 3, 4
```

---

## 向後相容策略

- v1 API (`/hybrid/search`) 完整保留
- v1 內部實作（`_vector_search`、`_graph_search`、`fusion_engine`）不改
- v2 在外層包裝，底層呼叫現有模組
- 兩套 API 同時存在，切換成本為零

---

## 預計產出

| 產出 | 說明 |
|------|------|
| 新 API | `POST /hybrid/evidence` |
| 新 dataclass | `EvidenceUnit`、`EvidenceSet`、`AuditRecord`、`Boundary`、`Hypothesis`、`InquiryPlan` |
| 新模組 | `boundary_checker`、`inquiry_decomposer`、`evidence_analyzer`、`state_machine` |
| 新類型 | `EvidenceSearchResponse`（v2 輸出）|

---

## 拒絕的舊假設

1. ❌ HybridRAG 的目標是把檢索排名做到最好
2. ❌ 召回越多越好
3. ❌ 向量 + 圖譜 + RRF 就等於 HybridRAG 完成
4. ❌ HybridRAG 的一級輸出是最終答案
5. ❌ query text 足以代表完整上下文

