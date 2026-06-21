# 福祉ISO 文件 — 知識圖譜整合實施計劃

## 概述

將福祉 ISO 品質管理系統文件（1,353 份/639MB）整合至 AIBox 知識庫，建構 Ontology 驅動的 RAG + 知識圖譜，支援 AI 推斷與決策輔助。

## 技術棧

- **資料庫**: ArangoDB（文件 + 圖譜雙模態）
- **向量庫**: Qdrant
- **AI 服務**: knowledge_agent（port 8007）
- **本體系統**: ontologies collection（三層：Basic → Domain → Major）
- **LLM**: Ollama（qwen3-embedding, qwen3-coder 等）

---

## Phase 1: Ontology 匯入

### 1.1 匯入 Domain Ontology

**檔案**: `domain_iso_quality_management.json`
- `_key`: domain_iso_quality_mgmt
- `type`: domain
- `name`: ISO_Quality_Management
- Entity Classes: 22 個（QMS_Framework, QMS_Document, Level1~4, Form_Template/Instance, Document_Code/Version/Status, Factory_Unit, ERP_Module, Quality_Record, Nonconformity, Corrective_Action, Internal_Audit, Management_Review, Document_Change_Log, Continual_Improvement）
- Object Properties: 14 個（has_document_level, has_version, defines_form, references_document, governed_by_procedure, maps_to_erp_module 等）

### 1.2 匯入 Major Ontology

**檔案**: `major_manufacturing_management_process.json`
- `_key`: major_manufacturing_mgmt_process
- `type`: major
- `name`: Manufacturing_Management_Process
- Entity Classes: 63 個（涵蓋 14 大業務領域）
- Object Properties: 46 個
- `inherits_from`: ["5W1H_Base_Ontology_OWL", "ISO_Quality_Management_Domain_Ontology"]

**匯入方式**（擇一）：
```bash
# REST API
curl -X POST http://localhost:8529/_db/aibox/_api/document/ontologies \
  -H "Content-Type: application/json" \
  -u root:abc_desktop_2026 \
  -d @domain_iso_quality_management.json

# arangosh
var domain = cat('domain_iso_quality_management.json');
db.ontologies.save(JSON.parse(domain));
```

---

## Phase 2: 建立 Knowledge Root

透過 API 建立知識庫根節點：

```json
{
  "_key": "kb_welfare_iso",
  "name": "福祉 ISO 品質管理系統",
  "description": "福祉車輛改裝製造業 ISO 9001 品質管理系統文件集，涵蓋文件四階層、儀器設備管理、製程檢驗與法規符合性。",
  "ontology_domain": "ISO_Quality_Management",
  "ontology_majors": ["Manufacturing_Management_Process"],
  "source_count": 0,
  "vector_status": "pending",
  "graph_status": "pending",
  "is_favorite": true
}
```

---

## Phase 3: 建立文件體系總覽（結構錨點）

製作一份結構化 Markdown 文件 `福祉ISO文件體系總覽.md`，用自然語言描述：

- 文件四階層的完整結構與編號規則
- 各管理辦法（QP）定義的表單（TB）對應關係
- 兩廠區（樹八/土城）的儀器設備清單
- 各文件之間的引用與從屬關係
- 產品與車型平台的分類

**目的**：上傳後 LLM graph extraction 會從中萃取出跨檔案的結構性圖譜（文件層級、引用關係、模板-實例關係），作為整個知識庫的骨架。

---

## Phase 4: 分批上傳文件

### 批次規劃

| 批次 | 內容 | 檔案數 | Entity Class |
|------|------|--------|-------------|
| 4.1 | 品質手冊（QM） | ~2 | Level1_QualityManual |
| 4.2 | 管理辦法（QP） | ~30 | Level2_ManagementProcedure |
| 4.3 | 作業規範（W/WP/WO/WC） | ~30 | Level3_WorkInstruction |
| 4.4 | 業務表單（TB-Pxx） | ~10 | Form_Template |
| 4.5 | 服務表單（TB-Sxx） | ~30 | Form_Template |
| 4.6 | 技術表單（TB-Txx） | ~30 | Form_Template |
| 4.7 | 儀器履歷實例（樹八廠 SMxx） | ~40 | Form_Instance |
| 4.8 | 儀器履歷實例（土城廠 TMxx） | ~50 | Form_Instance |
| 4.9 | 設備點檢紀錄（E001~E029） | ~60 | Form_Instance |
| 4.10 | 儀器履歷 PDF 掃描檔 | ~200+ | Form_Instance |
| 4.11 | 未入 ISO 表單（HR/行政） | ~30 | Form_Template |

### 上傳流程

每個檔案上傳時呼叫 `/pipeline/trigger`，自動啟動：
1. `vectorize_task` → 向量化存入 Qdrant
2. `graph_task` → LLM 圖譜萃取存入 ArangoDB

上傳參數範例：
```json
{
  "task": "auto",
  "file_id": "sm01_caliper",
  "local_path": "/data/福祉ISO/.../樹SM01.pdf",
  "root_id": "kb_welfare_iso",
  "metadata": {
    "hierarchy_level": "4",
    "document_code": "SM01",
    "form_type": "instance",
    "factory": "樹八廠",
    "instrument_type": "游標卡尺",
    "parent_form": "TB-T17"
  }
}
```

---

## Phase 5: 驗證與測試

### 5.1 驗證 Ontology
```aql
FOR o IN ontologies FILTER o.name == "ISO_Quality_Management" OR o.name == "Manufacturing_Management_Process"
RETURN { name: o.name, classes: LENGTH(o.entity_classes), props: LENGTH(o.object_properties) }
```

### 5.2 驗證 Knowledge Root
```aql
FOR kr IN knowledge_roots FILTER kr._key == "kb_welfare_iso"
RETURN kr
```

### 5.3 測試 Hybrid Search
```bash
curl -X POST http://localhost:8007/hybrid/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "游標卡尺的校正週期是多久？",
    "collection": "knowledge_kb_welfare_iso",
    "strategy": "hybrid",
    "root_id": "kb_welfare_iso"
  }'
```

### 5.4 驗證圖譜
```bash
curl "http://localhost:8007/pipeline/graph?file_id=sm01_caliper"
```

---

## Phase 6: 跨檔案圖譜整合（新增 ⭐）

### 問題意識

福祉 ISO 四階文件體系是一個**有機整體**，但當前 Pipeline 對每個檔案**獨立**做圖譜萃取：

```
QM-P01 → node("QP-S01", file_id=A)    ← 同一實體名稱
QP-S01 → node("QP-S01", file_id=B)    ← 但不同 file_id，沒有合併
```
- ❌ 無跨檔案實體解析（同名的實體在 ArangoDB 中各自獨立）
- ❌ 無跨檔案邊（QM-P01 ──governs──→ QP-S01 無法自動產生）
- ❌ 搜尋時無法做圖遍歷（`GRAPH_TRAVERSAL` / `SHORTEST_PATH` 無跨檔案路徑）

### 三層解決方案

```
L1. 結構錨點（Phase 3）── 上傳「福祉ISO文件體系總覽.md」建立跨檔案關係骨架
L2. Metadata Linker  ──── 基於 document_code + hierarchy_level 的 AQL 規則合併
L3. Batch Merge Pipeline ── 專用 Celery 任務進行模糊匹配與邊推理
```

### 6.1 Metadata Linker（建議立即實作）

利用上傳時附加的 metadata，透過純 AQL 規則進行跨檔案整合：

```aql
// Step A: 跨檔案同名實體合併
FOR n IN knowledge_graphs
  FILTER n.root_id == "kb_welfare_iso"
  COLLECT entity_name = n.entity INTO groups
  FILTER LENGTH(groups) > 1
  INSERT {
    entity: entity_name,
    root_id: "kb_welfare_iso",
    is_merged: true,
    source_files: groups[*].file_id,
    description: CONCAT_SEPARATOR("; ", groups[*].description)
  } INTO knowledge_graph_merged

// Step B: 根據 document_code 前綴建立階層邊
// QM-P01 ──governs──→ QP-*
// QP-*   ──defines──→ TB-*
// TB-T17 ──filled_by──→ SM01/TM01 (表單模板→實例)
```

### 6.2 Batch Graph Merge Pipeline（後續增強）

新增專用 Celery 任務：

```
merge_graph_task(root_id="kb_welfare_iso")
  → 1. 載入 Ontology entity_classes + object_properties
  → 2. 掃描所有 knowledge_graphs 節點
  → 3. 同類實體名稱模糊匹配 (fuzzy matching)
  → 4. 根據 ontology domain/range 推理跨檔案邊
  → 5. 存入 knowledge_graph_merged collection
  → 6. 更新 HybridRAG 搜尋納入 merged graph
```

---

## 風險與注意事項

| 風險 | 影響 | 對策 |
|------|------|------|
| 639MB 上傳耗時 | 長時間等待 | 分批上傳，優先核心文件 |
| LLM 圖譜萃取品質不穩 | 關係抽取不完整 | 先手動驗證幾份，必要時調整 prompt |
| 跨檔案關聯遺失 | 文件層級關係中斷 | 先上傳文件體系總覽建立結構骨架；加上 Phase 6 merge |
| PDF 掃描檔 OCR 需求 | 文字無法直接萃取 | 需要先 OCR 處理或僅上傳 docx 版本 |
| 空白表單 vs 填寫實例混淆 | 向量搜尋精準度下降 | 透過 metadata 分類，搜尋時可過濾 |

---

## Timeline（預估）

| Phase | 內容 | 預估時間 |
|-------|------|----------|
| 1 | Ontology 匯入 | 5 分鐘 |
| 2 | Knowledge Root 建立 | 2 分鐘 |
| 3 | 文件體系總覽製作 | 30 分鐘 |
| 4.1~4.3 | 核心文件上傳（QM/QP/W） | 1 小時 |
| 4.4~4.7 | 表單模板上傳 | 1 小時 |
| 4.8~4.14 | 實例文件上傳（含PDF） | 2~3 小時 |
| 5 | 驗證測試 | 30 分鐘 |
| 6.1 | Metadata Linker 實作 | 2 小時 |
| 6.2 | Batch Merge Pipeline | 1 天 |
| **總計** | | **6~8 小時 + 1 天開發** |
