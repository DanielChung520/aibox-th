---
lastUpdate: 2026-04-05 12:00:00
author: Daniel Chung
version: 1.0.0
---

# HybridRAG 系統規格書

**文檔版本**: v1.0.0  
**創建日期**: 2026-04-05  
**最後修改日期**: 2026-04-05  
**維護人**: Daniel Chung  

---

## 1. 概述

### 1.1 文檔目的

本文檔定義 AIBox HybridRAG（混合檢索增強生成）系統的完整架構、API 介面、數據模型、開發規範及實作細節。

### 1.2 背景與動機

現有 AIBox 知識管理系統存在以下缺口：

| 缺口 | 現有狀態 | 問題 |
|------|----------|------|
| 向量檢索與圖譜檢索分離 | Vector RAG + Graph RAG 分開儲存/查詢 | 查詢結果無融合，語義完整性不足 |
| 無動態權重配置 | 查詢使用固定策略 | 無法根據查詢類型優化檢索 |
| 無查詢類型檢測 | 所有查詢同等處理 | 結構化查詢與語義查詢需求不同 |
| 意圖目錄無 Knowledge Scope | 仅有 `data_agent` / `orchestrator` | Knowledge Agent 無法參與意圖路由 |

### 1.3 目標

實作完整的 HybridRAG 系統，實現：
- **混合檢索**：同時支援向量檢索（Qdrant）與圖譜檢索（ArangoDB）
- **動態權重**：根據查詢類型自動調整 vector/graph 權重
- **查詢分類**：自動識別 structure_query / entity_query / semantic_query
- **結果融合**：使用 RRF（Reciprocal Rank Fusion）演算法融合多通道結果
- **意圖整合**：新增 `knowledge` 意圖 scope，完善三層意圖路由

---

## 2. 系統架構

### 2.1 架構圖

```
┌─────────────────────────────────────────────────────────────────┐
│                        用戶查詢                                   │
│                     (Natural Language Query)                      │
└──────────────────────────┬────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                 HybridRAGQueryClassifier                          │
│           查詢類型檢測：structure / entity / semantic            │
└──────────────────────────┬────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                 HybridRAGConfigService                            │
│           權重配置：三層級（system → tenant → user）              │
│           根據 query_type 返回對應權重                            │
└──────────────────────────┬────────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
         ┌──────────────┐  ┌──────────────┐
         │   Vector     │  │    Graph     │
         │   Search    │  │    Search    │
         │  (Qdrant)   │  │ (ArangoDB)   │
         │             │  │              │
         │ - 語義相似度 │  │ - 實體關係   │
         │ - Top-K    │  │ - 圖遍歷     │
         │ - 分數     │  │ - 分數       │
         └──────┬──────┘  └──────┬──────┘
                │                  │
                └────────┬─────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  HybridRAGFusionEngine                           │
│  1. 根據權重調整各通道分數                                        │
│  2. RRF (Reciprocal Rank Fusion) 融合                           │
│  3. 去重 + 排序                                                  │
│  4. 返回 Top-K 結果                                               │
└──────────────────────────┬────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     融合後結果                                    │
│  - content: 文檔內容                                              │
│  - source: "vector" | "graph" | "fusion"                        │
│  - score: 融合後相關度分數                                        │
│  - metadata: 額外元數據                                            │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 組件列表

| 組件 | 檔案位置 | 職責 |
|------|----------|------|
| `HybridRAGQueryClassifier` | `knowledge_agent/hybrid_rag/classifier.py` | 查詢類型檢測 |
| `HybridRAGConfigService` | `knowledge_agent/hybrid_rag/config_service.py` | 權重配置管理 |
| `HybridRAGFusionEngine` | `knowledge_agent/hybrid_rag/fusion_engine.py` | 結果融合引擎 |
| `HybridRAGService` | `knowledge_agent/hybrid_rag/service.py` | 主服務整合 |
| `KnowledgeIntentRouter` | `knowledge_agent/knowledge_intent_rag/router.py` | Knowledge 意圖路由 |
| Seed Script | `datalake/seed_knowledge_intents.py` | 意圖目錄初始化 |

### 2.3 依賴服務

| 服務 | 地址 | 用途 |
|------|------|------|
| Qdrant | `http://localhost:6333` | 向量儲存與檢索 |
| ArangoDB | `http://localhost:8529` | 圖譜儲存與查詢 |
| Ollama | `http://localhost:11434` | Embedding 生成 |

---

## 3. 查詢類型分類

### 3.1 三種查詢類型

| 類型 | 關鍵詞 | 特徵 | 預設權重 (Vector/Graph) |
|------|--------|------|-------------------------|
| `structure_query` | 框架、步驟、流程、階段、順序、架構、設計 | 結構化內容、組織層次 | 0.4 / 0.6 |
| `entity_query` | 是什麼、關係、連接、包含、屬於 | 實體間關係查詢 | 0.3 / 0.7 |
| `semantic_query` | 解釋、說明、關於、關鍵、相關 | 語義相似性查詢 | 0.7 / 0.3 |

### 3.2 分類演算法

```python
def detect_query_type(query: str) -> QueryType:
    """根據關鍵詞檢測查詢類型"""
    query_lower = query.lower()
    
    # 優先檢測 structure_query
    structure_keywords = ["框架", "步驟", "流程", "階段", "順序", "架構", "設計", "結構"]
    if any(kw in query_lower for kw in structure_keywords):
        return QueryType.STRUCTURE_QUERY
    
    # 檢測 entity_query
    entity_keywords = ["是什麼", "關係", "連接", "包含", "屬於", "之間", "差異", "不同"]
    if any(kw in query_lower for kw in entity_keywords):
        return QueryType.ENTITY_QUERY
    
    # 預設 semantic_query
    return QueryType.SEMANTIC_QUERY
```

---

## 4. 權重配置系統

### 4.1 三層級配置

權重配置支援三層級覆蓋，優先順序：**user > tenant > system**

```python
# 配置優先順序
def get_weights(
    query_type: str,
    tenant_id: str | None = None,
    user_id: str | None = None
) -> dict[str, float]:
    # 1. 先嘗試 user 級配置
    # 2. 再嘗試 tenant 級配置
    # 3. 最後使用 system 級配置
```

### 4.2 預設權重

```json
{
  "default": {
    "vector_weight": 0.6,
    "graph_weight": 0.4
  },
  "structure_query": {
    "vector_weight": 0.4,
    "graph_weight": 0.6
  },
  "semantic_query": {
    "vector_weight": 0.7,
    "graph_weight": 0.3
  },
  "entity_query": {
    "vector_weight": 0.3,
    "graph_weight": 0.7
  }
}
```

### 4.3 儲存位置

權重配置儲存於 ArangoDB `system_params` 集合：

| Key | 說明 |
|-----|------|
| `hybridrag.vector_weight.default` | 預設向量權重 |
| `hybridrag.graph_weight.default` | 預設圖譜權重 |
| `hybridrag.vector_weight.structure_query` | 結構化查詢向量權重 |
| `hybridrag.graph_weight.structure_query` | 結構化查詢圖譜權重 |
| `hybridrag.vector_weight.semantic_query` | 語義查詢向量權重 |
| `hybridrag.graph_weight.semantic_query` | 語義查詢圖譜權重 |
| `hybridrag.vector_weight.entity_query` | 實體查詢向量權重 |
| `hybridrag.graph_weight.entity_query` | 實體查詢圖譜權重 |

---

## 5. 融合引擎

### 5.1 RRF (Reciprocal Rank Fusion)

RRF 是一種無參數的結果融合演算法，公式如下：

```
RRF_score(doc) = Σ 1 / (k + rank_i(doc))
```

其中：
- `k`: 常數（預設 60）
- `rank_i(doc)`: 文檔在第 i 個通道中的排名

### 5.2 融合流程

```python
def fuse_results(
    vector_results: list[RetrievalResult],
    graph_results: list[RetrievalResult],
    vector_weight: float,
    graph_weight: float,
    k: int = 60,
    top_k: int = 10
) -> list[FusionResult]:
    # 1. 根據權重調整分數
    # 2. 計算 RRF 分數
    # 3. 合併去重（以 content hash 或 doc_id 為準）
    # 4. 排序
    # 5. 返回 Top-K
```

### 5.3 去重策略

| 策略 | 說明 | 適用場景 |
|------|------|----------|
| `exact_match` | 內容完全相同 | 測試環境 |
| `fuzzy_match` | 相似度 > 0.9 | 生產環境（推薦） |
| `source_priority` | vector 結果優先 | 語義查詢為主 |

---

## 6. API 介面

### 6.1 Hybrid Search 端點

#### POST `/api/v1/ai/hybrid-search`

**說明**：執行 HybridRAG 混合檢索

**認證**：是（JWT Token）

**請求**：
```json
{
  "query": "AI需求分析的步驟是什麼？",
  "collection": "knowledge_default",
  "top_k": 10,
  "strategy": "hybrid",
  "min_relevance": 0.5,
  "tenant_id": "optional",
  "user_id": "optional"
}
```

| 欄位 | 類型 | 必填 | 預設值 | 說明 |
|------|------|------|--------|------|
| `query` | string | 是 | - | 查詢內容 |
| `collection` | string | 否 | knowledge_default | Qdrant collection 名稱 |
| `top_k` | integer | 否 | 10 | 返回結果數量 |
| `strategy` | string | 否 | hybrid | 檢索策略：hybrid / vector_first / graph_first |
| `min_relevance` | float | 否 | 0.0 | 最低相關度閾值 |
| `tenant_id` | string | 否 | null | 租戶 ID（用於多租戶權重） |
| `user_id` | string | 否 | null | 用戶 ID（用於用戶級權重） |

**回應**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "query": "AI需求分析的步驟是什麼？",
    "query_type": "structure_query",
    "strategy": "hybrid",
    "weights_used": {
      "vector_weight": 0.4,
      "graph_weight": 0.6
    },
    "results": [
      {
        "content": "AI需求分析框架步驟如下：\n1. 需求收集\n2. 需求整理\n3. 需求驗證",
        "source": "graph",
        "score": 0.85,
        "metadata": {
          "file_id": "file_123",
          "chunk_index": 5,
          "entity_type": "Process",
          "relation": "has_step"
        }
      },
      {
        "content": "AI需求分析是系統開發的重要階段...",
        "source": "vector",
        "score": 0.72,
        "metadata": {
          "file_id": "file_456",
          "chunk_index": 12
        }
      }
    ],
    "total_vector_hits": 25,
    "total_graph_hits": 8,
    "fusion_time_ms": 45
  }
}
```

### 6.2 權重配置端點

#### GET `/api/v1/ai/hybrid-config`

**說明**：取得當前 HybridRAG 權重配置

**認證**：是

**回應**：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "weights": {
      "default": {"vector_weight": 0.6, "graph_weight": 0.4},
      "structure_query": {"vector_weight": 0.4, "graph_weight": 0.6},
      "semantic_query": {"vector_weight": 0.7, "graph_weight": 0.3},
      "entity_query": {"vector_weight": 0.3, "graph_weight": 0.7}
    },
    "scope": "system",
    "updated_at": "2026-04-05T10:00:00Z"
  }
}
```

#### PUT `/api/v1/ai/hybrid-config`

**說明**：更新 HybridRAG 權重配置

**認證**：是（需要 admin 權限）

**請求**：
```json
{
  "query_type": "structure_query",
  "vector_weight": 0.45,
  "graph_weight": 0.55,
  "scope": "system"
}
```

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `query_type` | string | 是 | 查詢類型：default / structure_query / semantic_query / entity_query |
| `vector_weight` | float | 是 | 向量權重（0.0 ~ 1.0） |
| `graph_weight` | float | 是 | 圖譜權重（0.0 ~ 1.0） |
| `scope` | string | 否 | 配置範圍：system / tenant / user |

### 6.3 Knowledge 意圖路由端點

#### POST `/api/v1/intents/knowledge/intent/match`

**說明**：匹配 Knowledge 領域意圖

**認證**：是

**請求**：
```json
{
  "query": "查詢知識庫中關於系統架構的內容",
  "top_k": 3
}
```

**回應**：
```json
{
  "query": "查詢知識庫中關於系統架構的內容",
  "matches": [
    {
      "intent_id": "knowledge.structured_query",
      "score": 0.82,
      "intent_data": {
        "name": "結構化知識查詢",
        "description": "查詢知識庫中的流程、步驟、框架",
        "query_type": "structure_query"
      }
    }
  ],
  "best_match": {...}
}
```

### 6.4 錯誤碼

| HTTP 狀態碼 | 錯誤碼 | 說明 |
|-------------|--------|------|
| 400 | `INVALID_QUERY` | 查詢內容無效 |
| 400 | `INVALID_WEIGHTS` | 權重配置無效（和不等於 1） |
| 404 | `COLLECTION_NOT_FOUND` | Qdrant collection 不存在 |
| 500 | `EMBEDDING_FAILED` | Embedding 生成失敗 |
| 500 | `RETRIEVAL_FAILED` | 檢索服務錯誤 |
| 500 | `FUSION_FAILED` | 結果融合失敗 |

---

## 7. 數據模型

### 7.1 HybridRAG 檢索結果

```typescript
interface HybridRetrievalResult {
  content: string;           // 文檔內容
  source: "vector" | "graph" | "fusion";  // 來源通道
  score: number;            // 融合後分數
  original_score?: number;   // 原始分數
  metadata: {
    file_id: string;         // 來源文件 ID
    chunk_index?: number;    // Chunk 索引（vector）
    entity_type?: string;     // 實體類型（graph）
    relation?: string;       // 關係類型（graph）
    root_id?: string;        // 知識庫根 ID
  };
}
```

### 7.2 HybridRAG 配置模型

```typescript
interface HybridRAGWeights {
  vector_weight: number;     // 向量權重
  graph_weight: number;      // 圖譜權重
}

interface HybridRAGConfig {
  default: HybridRAGWeights;
  structure_query: HybridRAGWeights;
  semantic_query: HybridRAGWeights;
  entity_query: HybridRAGWeights;
}
```

### 7.3 Knowledge 意圖模型

```typescript
interface KnowledgeIntent {
  intent_id: string;         // 意圖 ID（如 "knowledge.structured_query"）
  agent_scope: "knowledge";   // 固定為 "knowledge"
  name: string;               // 意圖名稱
  description: string;        // 意圖描述
  intent_type: "query";      // 意圖類型
  query_type: QueryType;      // 對應的查詢類型
  nl_examples: string[];      // 自然語言範例
  status: "enabled";          // 狀態
  priority: number;          // 優先級
}
```

---

## 8. 檔案結構

```
ai-services/
├── knowledge_agent/
│   ├── main.py                      # [修改] 整合 HybridRAG
│   ├── hybrid_rag/                  # [新增] HybridRAG 核心模組
│   │   ├── __init__.py
│   │   ├── classifier.py            # [新增] 查詢類型檢測
│   │   ├── config_service.py        # [新增] 權重配置服務
│   │   ├── fusion_engine.py         # [新增] 結果融合引擎
│   │   └── service.py               # [新增] HybridRAG 主服務
│   └── knowledge_intent_rag/         # [新增] Knowledge 意圖路由
│       ├── __init__.py
│       └── router.py                # [新增] 意圖匹配路由
├── datalake/
│   └── seed_knowledge_intents.py     # [新增] Knowledge 意圖 seed
```

---

## 9. 實作細節

### 9.1 向量檢索（Vector Search）

```python
# 使用現有 QdrantStore.search()
def vector_search(
    query_embedding: list[float],
    collection: str,
    top_k: int
) -> list[RetrievalResult]:
    results = qdrant_store.search(
        collection=collection,
        vector=query_embedding,
        limit=top_k
    )
    return [
        RetrievalResult(
            content=r["text_full"],
            source="vector",
            score=r["score"],
            metadata={"file_id": r["file_id"], ...}
        )
        for r in results
    ]
```

### 9.2 圖譜檢索（Graph Search）

```python
# 使用 ArangoDB 圖遍歷查詢
def graph_search(
    query: str,
    file_ids: list[str] | None,
    top_k: int
) -> list[RetrievalResult]:
    # 1. 提取查詢關鍵詞
    keywords = extract_keywords(query)
    
    # 2. 查詢相關實體
    entities = find_matching_entities(keywords, file_ids)
    
    # 3. 查詢實體關係
    relations = find_relations(entities)
    
    # 4. 建構結果
    return build_graph_results(entities, relations, top_k)
```

### 9.3 RRF 融合實現

```python
def reciprocal_rank_fusion(
    vector_results: list[RetrievalResult],
    graph_results: list[RetrievalResult],
    vector_weight: float,
    graph_weight: float,
    k: int = 60
) -> dict[str, float]:
    rrf_scores: dict[str, float] = {}
    
    # 向量通道 RRF
    for rank, r in enumerate(sorted(vector_results, key=lambda x: x.score, reverse=True)):
        doc_key = r.metadata.get("file_id", r.content[:50])
        rrf_scores[doc_key] = rrf_scores.get(doc_key, 0) + vector_weight * (1 / (k + rank + 1))
    
    # 圖譜通道 RRF
    for rank, r in enumerate(sorted(graph_results, key=lambda x: x.score, reverse=True)):
        doc_key = r.metadata.get("file_id", r.content[:50])
        rrf_scores[doc_key] = rrf_scores.get(doc_key, 0) + graph_weight * (1 / (k + rank + 1))
    
    return rrf_scores
```

---

## 10. 測試策略

### 10.1 單元測試

| 測項 | 測試內容 |
|------|----------|
| `test_classifier_structure` | 結構化查詢檢測 |
| `test_classifier_entity` | 實體查詢檢測 |
| `test_classifier_semantic` | 語義查詢檢測 |
| `test_weight_validation` | 權重驗證（和=1） |
| `test_weight_override` | 三層級覆蓋邏輯 |
| `test_rrf_fusion` | RRF 融合正確性 |
| `test_deduplication` | 去重邏輯 |

### 10.2 集成測試

| 測項 | 測試內容 |
|------|----------|
| `test_hybrid_search_end_to_end` | 完整混合檢索流程 |
| `test_vector_only_search` | 僅向量檢索模式 |
| `test_graph_only_search` | 僅圖譜檢索模式 |
| `test_empty_results` | 空結果處理 |

### 10.3 測試資料

```python
TEST_QUERIES = {
    "structure": [
        "AI需求分析的步驟是什麼？",
        "系統架構設計的流程",
        "這個框架包含哪些階段？"
    ],
    "entity": [
        "X和Y之間的關係是什麼？",
        "這個概念包含哪些組成部分？",
        "A與B有什麼差異？"
    ],
    "semantic": [
        "解釋一下知識庫中的某某概念",
        "關於系統安全的相关内容",
        "這份文件主要在說什麼？"
    ]
}
```

---

## 11. 部署與配置

### 11.1 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `HYBRID_RAG_K` | 60 | RRF 常數 k |
| `HYBRID_RAG_DEFAULT_TOP_K` | 10 | 預設返回數量 |
| `HYBRID_RAG_MIN_RELEVANCE` | 0.0 | 最低相關度閾值 |

### 11.2 初始化

```bash
# 1. 初始化 Knowledge 意圖
cd ai-services && python -m datalake.seed_knowledge_intents

# 2. 驗證意圖已寫入
curl -u root:abc_desktop_2026 \
  "http://localhost:8529/_db/abc_desktop/_api/cursor" \
  -d '{"query":"FOR i IN intent_catalog FILTER i.agent_scope == \"knowledge\" RETURN i"}'
```

### 11.3 健康檢查

```bash
# 檢查 HybridRAG 服務狀態
curl http://localhost:8007/hybrid/health
```

---

## 12. 修改歷史

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-05 | 1.0.0 | Daniel Chung | 初始版本，建立 HybridRAG 系統規格書 |

---

## 13. 相關文檔

- [HybridRAG 完整配置與使用指南](./HybridRAG-完整配置與使用指南.md)
- [HybridRAG 問題定位與解決方案](./HybridRAG問題定位與解決方案.md)
- [AI-Box 雙軌 RAG 解析規格書](./AI-Box雙軌RAG解析規格書.md)
- [向量與圖檢索混合查詢邏輯](./向量與圖檢索混合查詢邏輯.md)
- [强化RAG系统](./强化RAG系统.md)
- [API Specification](../API%20Specification.md)
- [意圖目錄](./../EEA/意圖分析.md)
