---
lastUpdate: 2026-04-18 00:05:39
author: Daniel Chung
version: 2.0.0
---

# HybridRAG 細部規格書 v2

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-18 | 2.0.0 | Daniel Chung | 重新定義 HybridRAG：從混合檢索系統升級為有界探查與證據組裝層 |

---

## 1. 文件定位

本文件是 HybridRAG 的**細部規格**，用於承接：

- `.docs/Spec/知識庫管理/知識管理優化規格書-v6.md`
- `.docs/Spec/知識庫管理/知識管理優化規格書-v6-導引版.md`
- `.docs/Spec/艾企助手/05-意圖形成與收斂規格綱要-v2.md`
- `.docs/Spec/智能體/艾企未來架構/艾企未來架構原則草案-v0.1.md`

本文件不再把 HybridRAG 定義為：

> vector search + graph search + RRF

而是定義為：

> **在知識邊界內，將意圖假設轉化為有界探查計畫，蒐集、篩選、組裝並交付可稽核證據包的系統。**

---

## 2. HybridRAG 在新架構中的角色

### 2.1 它是什麼

HybridRAG 是：

- 有界探查層（Bounded Inquiry Layer）
- 證據組裝層（Evidence Assembly Layer）
- 連接意圖形成與後續回答/決策的中介層

### 2.2 它不是什麼

HybridRAG 不是：

- 更強的搜尋器
- 純演算法融合器
- 記憶產品本身
- 最終回答生成器
- 只追求召回率的 RAG pipeline

### 2.3 North Star

HybridRAG 的最高目標不是「找到最多資料」，而是：

> **在有限邊界、有限成本、有限時間內，組裝出最小但足以支持或反駁當前假設的證據集合。**

---

## 3. 核心設計原則

### 3.1 邊界優先於召回

在企業 AI 中，越界使用知識比低召回更危險。

因此 HybridRAG 必須遵守：

1. 所有候選來源先過 boundary check
2. 不允許 LLM 自行決定是否跨知識庫、跨權限、跨版本
3. 若邊界不明，輸出「需澄清 / 不可繼續」，而非擴大搜尋

### 3.2 證據優先於答案

HybridRAG 的一級輸出是：

- EvidenceSet
- Hypothesis support / contradiction summary
- NextStep recommendation

而不是 final answer。

### 3.3 停止條件優先於持續搜尋

HybridRAG 必須是一個可停止的系統。

它必須能夠明確回應：

- 證據已足夠
- 還缺少哪一類關鍵證據
- 邊界不允許繼續
- 成本預算已到上限

### 3.4 對立證據不可被抹平

若不同通道（vector / graph / raw / prior）之間出現矛盾，HybridRAG 必須：

- 保留分歧
- 標示來源
- 輸出追加蒐證建議

不得為了生成流暢回答而把矛盾合併掉。

---

## 4. HybridRAG 的最小輸入輸出契約

## 4.1 輸入物件

HybridRAG 需至少接受以下輸入：

### 4.1.1 Boundary

```json
{
  "root_id": "kb_xxx",
  "role_scope": ["knowledge_reader"],
  "ontology_scope": {
    "domain": ["quality", "supply_chain"],
    "major": ["inspection", "supplier"]
  },
  "lifecycle_scope": ["active"],
  "usage_scope": ["knowledge_answer", "intent_support"],
  "max_hops": 2,
  "max_top_k": 10,
  "time_budget_ms": 2000
}
```

### 4.1.2 Hypothesis

```json
{
  "hypothesis_id": "ih_xxx",
  "statement": "使用者可能正在追查退貨批次的上游供應與生產關聯",
  "candidate_anchors": ["batch_id", "item_id", "supplier_id"],
  "required_evidence_types": ["graph_relation", "source_chunk", "table_context"],
  "falsifiable_by": ["找不到批號對應", "關聯跨越知識邊界"]
}
```

### 4.1.3 InquiryPlan

```json
{
  "plan_id": "ip_xxx",
  "strategy": "hybrid",
  "sub_questions": [
    "哪個 anchor 最可能是當前查詢中心？",
    "有哪些結構化關係可支持這個假設？",
    "有哪些語義片段能補足上下文？"
  ],
  "allowed_channels": ["vector", "graph", "raw"],
  "stop_when": ["evidence_sufficient", "boundary_unclear", "budget_exhausted"]
}
```

### 4.1.4 Context Signals（可選）

包含：

- recent actionTrail window
- active page / table / row / field
- current working set
- candidate anchors from intent layer

---

## 4.2 輸出物件

HybridRAG 的最小輸出不是 search hits，而是：

### 4.2.1 EvidenceUnit

```json
{
  "evidence_id": "ev_xxx",
  "source_type": "vector|graph|raw|fusion",
  "root_id": "kb_xxx",
  "file_id": "file_xxx",
  "chunk_index": 12,
  "entity_id": "kg_xxx",
  "content": "...",
  "normalized_score": 0.83,
  "extraction_confidence": 0.88,
  "supports": ["ih_xxx"],
  "contradicts": [],
  "provenance": {
    "text_span": {"start": 1200, "end": 1450},
    "ontology_version": "v1.2.0",
    "lifecycle_status": "active"
  }
}
```

### 4.2.2 EvidenceSet

```json
{
  "hypothesis_id": "ih_xxx",
  "boundary_status": "within_boundary|boundary_unclear|out_of_boundary",
  "sufficiency": "sufficient|insufficient|conflicted",
  "evidences": ["ev_1", "ev_2", "ev_3"],
  "contradictions": ["ev_9"],
  "gaps": ["缺少明確 batch_id 對應來源"],
  "next_step": "ask_for_clarification|expand_graph|stop|handoff_to_human"
}
```

### 4.2.3 Audit Record

```json
{
  "query": "...",
  "hypothesis_id": "ih_xxx",
  "boundary_checked": true,
  "channels_used": ["vector", "graph"],
  "discarded_candidates": 14,
  "discard_reasons": ["out_of_boundary", "stale_version"],
  "stop_reason": "evidence_sufficient",
  "fusion_strategy": "rrf_v2"
}
```

---

## 5. HybridRAG 狀態機

HybridRAG 流程必須可表示為以下狀態機：

```
Receive Request
    ↓
Boundary Check
    ↓
Hypothesis Intake
    ↓
Inquiry Decomposition
    ↓
Channel Retrieval
    ↓
Evidence Assembly
    ↓
Conflict / Gap Evaluation
    ↓
Stop / Clarify / Expand / Handoff
```

### 5.1 狀態定義

| 狀態 | 說明 |
|------|------|
| `boundary_checking` | 驗證 root / role / ontology / lifecycle |
| `planning` | 把 hypothesis 轉為 inquiry plan |
| `retrieving` | 依 channel 取得候選資料 |
| `assembling` | 將候選轉為 evidence units / set |
| `evaluating` | 檢查 sufficiency / conflict / gap |
| `stopped` | 已足夠或不能再繼續 |
| `clarify_required` | 需向 user 追問 |
| `handoff_required` | 需交由人類判斷 |

---

## 6. Channel Contract（通道契約）

### 6.1 Vector Channel

責任：

- 找回語義相關候選 chunk / evidence
- 提供相似案例或說法補全

限制：

- 不可單獨構成最終結論
- 必須附帶 provenance
- 必須受 root / lifecycle / usage scope 約束

### 6.2 Graph Channel

責任：

- 找回結構化實體與關係
- 進行受限 path expansion
- 提供 anchor-aware 的結構證據

限制：

- 不可將可連接誤視為可推論
- path expansion 必須受 hop / budget 限制

### 6.3 Raw Channel

責任：

- 在 provenance 必要時回取原始 chunk / span
- 用於人工審核與 evidence verification

限制：

- 不直接參與大規模召回
- 主要用於驗證與補充

### 6.4 Prior / Intent Support Channel（保留接口）

責任：

- 接收上游 intent system 的 candidate anchors / intent hypothesis / current attention zone

限制：

- 不直接當作證據
- 只能作為 inquiry plan 的優先序調整來源

---

## 7. Boundary Governance Contract

### 7.1 必檢項目

HybridRAG 在進 retrieval 前，必須檢查：

1. `root_id` 是否存在且允許
2. role / auth 是否允許
3. ontology scope 是否匹配
4. lifecycle status 是否可用
5. usage scope 是否允許本次用途

### 7.2 邊界結果

| 狀態 | 說明 | 後續動作 |
|------|------|----------|
| `within_boundary` | 可正常檢索 | 進入 retrieval |
| `boundary_unclear` | 邊界資訊不足 | 進入 clarify_required |
| `out_of_boundary` | 明確越界 | stop / reject |

---

## 8. Inquiry Decomposition Contract

HybridRAG 不是直接拿 query 檢索，而應先把 query/hypothesis 轉成 inquiry plan。

### 8.1 分解必須產生

- target hypothesis
- required evidence types
- preferred channels
- anchor candidates
- cost budget
- stop conditions

### 8.2 不允許的做法

- 沒有 hypothesis 就直接全量 hybrid search
- 不經 plan 就直接擴大 top_k
- 用 query text 直接替代所有結構訊號

---

## 9. Evidence Assembly Contract

### 9.1 組裝必須完成的工作

1. 候選轉 EvidenceUnit
2. Canonical link 對齊（file/chunk/entity/vector）
3. 去重
4. 標註支持/反對假設
5. 標註缺口與不足
6. 產出 EvidenceSet

### 9.2 去重原則

v1 以 `content hash + file_id` 為主，v2 起必須逐步升級為：

- canonical entity / chunk linkage 優先
- content hash 作為 fallback

### 9.3 分歧原則

若同一 hypothesis 存在對立證據，必須：

- 在 EvidenceSet 中同時保留
- 顯示 contradiction 列表
- 輸出下一步蒐證或澄清方向

---

## 10. 停止與升級契約

### 10.1 停止條件

系統應在以下條件之一成立時停止：

- evidence sufficient
- boundary unclear
- out of boundary
- budget exhausted
- contradictory evidence unresolved

### 10.2 升級條件

應升級到 clarify / human handoff 的情況：

- 需要跨知識庫
- 需要跨權限資料
- 高風險問題（策略、法務、財務責任）
- 證據矛盾且無法在 budget 內解決

---

## 11. 與現行實作的對齊與差距

### 11.1 現行已有能力

- Query classifier
- Config-based weights
- Vector retrieval（Qdrant）
- Graph retrieval（Arango keyword/BM25）
- Fusion engine（RRF）
- `/hybrid/search` API

### 11.2 現行不足

- 現行輸入仍以 query 為中心，沒有明確 Hypothesis / Boundary / InquiryPlan
- 現行 graph retrieval 仍偏 keyword-like，未明確支持受限 path expansion
- 現行 result 仍是 search hit，而不是 EvidenceSet
- 現行 metadata 缺少完整 provenance / boundary / usable scope / contradiction 標記
- 現行沒有明確 stop / clarify / handoff 輸出

---

## 12. 對後續資料模型與 API 細規的要求

### 12.1 後續資料模型細規必須回答

- EvidenceUnit / EvidenceSet / AuditRecord 的完整欄位
- canonical id 與 linkage 模型
- channel-specific metadata schema

### 12.2 後續 API 細規必須回答

- request 中如何輸入 boundary / hypothesis / inquiry plan
- response 中如何輸出 evidence set / next step / audit info
- clarify / handoff 狀態如何表示

### 12.3 後續 UI 細規必須回答

- 如何展示 evidence set
- 如何展示 contradiction / gap / boundary status
- 如何回查 provenance 原文

---

## 13. 明確拒絕的舊假設

1. HybridRAG 的目標是把檢索排名做到最好
2. 召回越多越好
3. 向量 + 圖譜 + RRF 就等於 HybridRAG 完成
4. HybridRAG 的一級輸出是最終答案
5. query text 足以代表完整上下文

---

## 14. 驗收導向

HybridRAG 細規的驗收，不應只看：

- latency
- recall
- top-k relevance

還必須看：

- boundary correctness
- provenance completeness
- evidence sufficiency
- contradiction preservation
- stop / clarify correctness

---

## 15. 本文件結論

HybridRAG v2 的關鍵，不是把「混合檢索」做得更花，而是讓它真正成為：

> **艾企在知識邊界內，將意圖假設轉化為有界探查計畫，再把多通道資料組裝成可稽核證據包的核心中介層。**

它是 bounded inquiry 的執行核心，不是另一個搜尋器。
