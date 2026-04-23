# HybridRAG 權重配置測試說明

**創建日期**: 2026-01-05
**創建人**: Daniel Chung
**最後修改日期**: 2026-01-05

---

## 📋 測試狀態

### ✅ 可以測試的部分

1. **配置 CRUD 操作**（可以立即測試）
   - ✅ 初始化默認配置
   - ✅ 讀取權重配置
   - ✅ 保存/更新配置
   - ✅ 查詢類型檢測

2. **權重配置邏輯**（可以立即測試）
   - ✅ 根據查詢類型動態調整權重
   - ✅ 多層級配置讀取（System/Tenant/User）
   - ✅ 權重驗證

### ⚠️ 需要完整環境的部分

1. **完整 HybridRAG 檢索**（需要運行環境）
   - ⚠️ 需要 ArangoDB 服務運行
   - ⚠️ 需要 ChromaDB 服務運行
   - ⚠️ 需要已上傳文檔並構建知識圖譜
   - ⚠️ 需要 AAMManager 實例
   - ⚠️ 需要 NER 服務和 KGBuilder 服務

---

## 🔧 測試配置功能

### 快速測試腳本

```python
from genai.workflows.rag.hybrid_rag_config import HybridRAGConfigService

# 創建配置服務
config_service = HybridRAGConfigService()

# 1. 初始化默認配置
config_id = config_service.initialize_default_config(force=False, changed_by="system")
print(f"配置 ID: {config_id}")

# 2. 測試查詢權重
query = "請說明中国预制菜产业市场规模与增长趋势"
weights = config_service.get_weights(query=query)
print(f"查詢: {query}")
print(f"權重: 向量 {weights['vector_weight']:.1f}, 圖 {weights['graph_weight']:.1f}")
```

### 執行測試

```bash
cd /Users/daniel/GitHub/AI-Box

# 初始化配置
python scripts/init_hybrid_rag_config.py

# 測試權重配置
python -c "
from genai.workflows.rag.hybrid_rag_config import HybridRAGConfigService
service = HybridRAGConfigService()
query = '請說明中国预制菜产业市场规模与增长趋势'
weights = service.get_weights(query=query)
print(f'查詢: {query}')
print(f'權重: 向量 {weights[\"vector_weight\"]:.1f}, 圖 {weights[\"graph_weight\"]:.1f}')
"
```

---

## 🎯 測試查詢：中国预制菜产业市场规模与增长趋势

### 查詢分析

**用戶查詢**: "請說明中国预制菜产业市场规模与增长趋势"

**查詢類型檢測**:
- 關鍵詞："規模"、"趨勢"、"說明"
- 檢測結果：`semantic_query`（語義查詢）
- 使用的權重：**向量 0.7，圖 0.3**

**權重配置邏輯**:
1. 查詢中包含"說明"（語義查詢關鍵詞）
2. 不包含結構化關鍵詞（框架、步驟、流程等）
3. 不包含實體查詢關鍵詞（是什麼、關係等）
4. 因此歸類為 `semantic_query`
5. 使用語義查詢權重：向量 70%，圖 30%

---

## ✅ 測試結果

### 配置初始化測試

```bash
$ python scripts/init_hybrid_rag_config.py
================================================================================
HybridRAG 權重配置初始化
================================================================================

✅ 配置初始化成功！
配置 ID: rag.hybrid_weights
配置 Scope: rag.hybrid_weights

配置內容:
  default:
    向量權重: 0.6
    圖權重: 0.4
  structure_query:
    向量權重: 0.4
    圖權重: 0.6
  semantic_query:
    向量權重: 0.7
    圖權重: 0.3
  entity_query:
    向量權重: 0.3
    圖權重: 0.7

================================================================================
初始化完成！
================================================================================
```

### 查詢權重測試

**查詢**: "請說明中国预制菜产业市场规模与增长趋势"

**權重配置**:
- **查詢類型**: `semantic_query`（語義查詢）
- **向量權重**: 0.7 (70%)
- **圖權重**: 0.3 (30%)

**說明**:
- 這是一個語義查詢（解釋、說明類），系統會優先使用向量檢索
- 向量檢索更適合語義相似性匹配
- 圖檢索作為補充，提供結構化關係信息

---

## 🚀 完整 HybridRAG 檢索測試

要測試完整的 HybridRAG 檢索功能，需要：

### 前置條件

1. **服務運行**:
   ```bash
   # 確保 ArangoDB 運行
   docker ps | grep arangodb
   
   # 確保 ChromaDB 運行
   docker ps | grep chromadb
   ```

2. **文檔上傳**:
   - 已上傳相關文檔（如"东方伊厨-预制菜发展策略报告20250902.pdf"）
   - 已構建向量索引（ChromaDB）
   - 已構建知識圖譜（ArangoDB）

3. **服務初始化**:
   ```python
   from agents.infra.memory.aam.aam_core import AAMManager
   from genai.workflows.rag.hybrid_rag import HybridRAGService
   
   # 創建 AAMManager（需要實際配置）
   aam_manager = AAMManager(...)
   
   # 創建 HybridRAGService（自動從配置讀取權重）
   hybrid_rag_service = HybridRAGService(
       aam_manager=aam_manager,
       tenant_id="tenant_001",  # 可選
       user_id="user_001",      # 可選
   )
   
   # 執行檢索
   query = "請說明中国预制菜产业市场规模与增长趋势"
   results = hybrid_rag_service.retrieve(query=query, top_k=10)
   
   # 查看結果
   for i, result in enumerate(results, 1):
       print(f"[{i}] 相關度: {result['score']:.3f}")
       print(f"    內容: {result['content'][:100]}...")
       print(f"    來源: {result['metadata'].get('source', 'unknown')}")
   ```

---

## 📊 預期行為

### 對於查詢"請說明中国预制菜产业市场规模与增长趋势"

1. **權重配置**:
   - 查詢類型：`semantic_query`
   - 向量權重：0.7 (70%)
   - 圖權重：0.3 (30%)

2. **檢索流程**:
   - **向量檢索**（70% 權重）：
     - 在 ChromaDB 中搜索語義相似的文檔片段
     - 找到與"中國預製菜產業市場規模與增長趨勢"相關的內容
     - 返回 top_k 個最相關的文檔片段

   - **圖檢索**（30% 權重）：
     - 使用 NER 提取實體（如"中國"、"預製菜"、"市場規模"等）
     - 在 ArangoDB 知識圖譜中查找相關實體和關係
     - 返回相關的圖譜數據

3. **結果融合**:
   - 應用權重：向量結果 × 0.7，圖結果 × 0.3
   - 去重並按相關度排序
   - 返回最終結果

4. **預期結果**:
   - 主要來自向量檢索（70%）
   - 包含語義相似的文檔片段
   - 可能包含圖檢索的結構化關係（30%）

---

## ⚠️ 注意事項

1. **配置初始化**：
   - 首次使用前，需要運行 `scripts/init_hybrid_rag_config.py` 初始化配置
   - 如果配置已存在，不會覆蓋（除非使用 `force=True`）

2. **權重驗證**：
   - 權重必須在 0.0 到 1.0 之間
   - `vector_weight + graph_weight` 必須等於 1.0（允許 1% 誤差）

3. **查詢類型檢測**：
   - 系統會根據查詢中的關鍵詞自動檢測查詢類型
   - 可以手動調整權重配置以優化特定查詢類型

4. **多層級配置**：
   - 配置優先級：User > Tenant > System
   - 如果用戶級配置存在，會優先使用用戶級配置

---

## 🔗 相關文檔

- [HybridRAG 權重配置使用說明](./HybridRAG权重配置使用说明.md)
- [HybridRAG 權重配置 CRUD 示例](./HybridRAG权重配置CRUD示例.md)
- [HybridRAG 查詢邏輯說明](./系统设计文档/核心组件/文件上傳向量圖譜/向量與圖檢索混合查詢邏輯.md)

---

**最後更新日期**: 2026-01-05
**維護人**: Daniel Chung

