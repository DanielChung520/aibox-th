# HybridRAG 問題定位與解決方案

**創建日期**: 2026-01-05
**創建人**: Daniel Chung
**最後修改日期**: 2026-01-05

---

## 📋 問題定位總結

經過系統性檢查，已確認以下問題：

### ✅ 已確認的狀態

1. **向量數據狀態**：
   - ChromaDB 連接成功，有 122 個集合
   - 找到相關集合：`f347352c-a30e-4598-b0e8-60811b949751` 和 `file_f347352c-a30e-4598-b0e8-60811b949751`
   - 文件已上傳並完成向量化

2. **圖譜數據狀態**：
   - ArangoDB 連接成功，有 1080 個實體，794 個關係
   - 找到 13 個相關實體（预制菜、市场、规模、增长、趋势、产业）
   - 包括「日本预制菜企业」、「台湾市场」、「市场价值估算」等

### ❌ 發現的問題

#### 問題 1: 向量維度不匹配（關鍵問題）

**錯誤信息**:

```
Collection expecting embedding with dimension of 768, got 384
```

**問題分析**:

- **集合期望的向量維度**: 768
- **查詢生成的向量維度**: 384（使用 `nomic-embed-text` 模型）
- **影響**: 向量檢索返回 0 個結果

**根本原因**:

- 向量化時使用的 embedding 模型與查詢時使用的模型不一致
- 文件向量化時可能使用了 768 維的模型（如 `bge-large-zh-v1.5` 或類似模型）
- 查詢時使用了 384 維的模型（`nomic-embed-text`）

**解決方案**:

1. **方案 A（推薦）**: 確保查詢時使用與向量化時相同的 embedding 模型
   - 檢查向量化時使用的模型配置
   - 設置 `OLLAMA_EMBEDDING_MODEL` 環境變數為相同的模型
   - 或修改 `EmbeddingService` 使用相同的模型

2. **方案 B**: 重新向量化文件使用當前模型
   - 使用 `nomic-embed-text`（384 維）重新向量化文件
   - 確保所有文件使用統一的 embedding 模型

#### 問題 2: 圖檢索實體匹配返回 0 個結果

**問題分析**:

- NER 成功提取了實體（中国、预制菜、产业、规模、增长趋势）
- 圖譜中存在相關實體（13 個相關實體）
- 但匹配邏輯返回 0 個結果

**可能的原因**:

1. 實體名稱不完全匹配（如「中国预制菜产业」無法匹配「日本预制菜企业」）
2. 關鍵詞匹配雖然已實施，但可能仍有問題
3. `cursor count not enabled` 錯誤已修復，但可能影響了結果返回

**解決方案**:

1. 檢查關鍵詞匹配邏輯是否正常工作
2. 優化實體匹配策略（已實施混合策略）
3. 檢查實體匹配的返回邏輯

---

## 🔧 解決方案實施

### 步驟 1: 修復向量維度不匹配

**檢查向量化時使用的模型**:

```bash
# 檢查環境變數
grep EMBEDDING .env

# 檢查配置文件
cat config/config.json | grep -i embedding
```

**修復方法**:

1. 確認向量化時使用的 embedding 模型
2. 設置查詢時使用相同的模型
3. 或重新向量化文件使用統一的模型

### 步驟 2: 優化圖檢索實體匹配

**已實施的改進**:

- ✅ 混合策略（文字比對 + 關鍵詞匹配）
- ✅ 關鍵詞提取邏輯改進
- ✅ `cursor count not enabled` 錯誤處理

**待優化**:

- 檢查關鍵詞匹配是否正常工作
- 優化實體匹配的返回邏輯
- 確保找到的實體能正確返回

---

## 📊 測試結果

### 向量檢索測試

**測試結果**:

- ❌ 向量檢索返回 0 個結果
- **原因**: 向量維度不匹配（768 vs 384）

### 圖檢索測試

**測試結果**:

- ✅ 找到 13 個相關實體
- ❌ 但匹配邏輯返回 0 個結果
- **原因**: 需要進一步檢查匹配邏輯

---

## 🎯 實施狀態

### ✅ 已完成的修復

#### 1. 向量維度不匹配問題修復

**實施內容**:

- ✅ 實現了 `VectorStoreService.get_collection_embedding_dimension()` 方法，用於檢測集合的向量維度
- ✅ 實現了 `EmbeddingService.get_model_for_dimension()` 方法，根據向量維度動態選擇對應的模型
- ✅ 修改了 `VectorStoreService.query_vectors()` 方法，支持動態模型選擇
- ✅ 添加了向量維度緩存機制，避免重複查詢

**技術細節**:

- 使用 Qdrant 的 `get()` 方法查詢第一個向量來檢測維度
- 維護維度到模型的映射表（384維: `nomic-embed-text`, 768維: `bge-large-zh-v1.5`, 1024維: `qwen3-embedding`）
- 支持通過環境變量 `EMBEDDING_DIMENSION_MODEL_MAP` 配置映射

> **v4.1 更新（2026-01-20）**: 新增 `qwen3-embedding:latest` 模型（1024維）推薦配置，支援語言自動檢測和模型選擇。

#### 2. 圖檢索實體匹配問題修復

**實施內容**:

- ✅ 添加了詳細的調試日誌，記錄實體匹配的每個步驟
- ✅ 優化了關鍵詞提取邏輯（`_extract_keywords()`），提高關鍵詞相關性
- ✅ 改進了實體匹配查詢邏輯（`_query_entities_by_text_match()` 和 `_query_entities_by_keywords()`），使用更靈活的匹配策略
- ✅ 實現了實體關係擴展查詢（`_expand_entities_by_relations()`），通過關係擴展檢索範圍
- ✅ 檢查並優化了 `_format_graph_results()` 方法，添加了詳細的日誌記錄

**技術細節**:

- 改進的 AQL 查詢使用前綴、後綴、包含等多種匹配方式
- 關鍵詞提取優先提取長詞語，按長度排序
- 關係擴展查詢實體的鄰居實體，提高檢索覆盖率

#### 3. 調試和測試工具

**實施內容**:

- ✅ 創建了 `scripts/debug_graph_retrieval.py` 調試腳本
- ✅ 創建了 `scripts/test_hybrid_rag_fixes.py` 綜合測試腳本

### 📊 測試結果

**待執行測試**:

- [ ] 運行 `scripts/test_hybrid_rag_fixes.py` 驗證所有修復
- [ ] 運行 `scripts/debug_graph_retrieval.py` 調試圖檢索問題
- [ ] 驗證向量檢索能夠正常工作
- [ ] 驗證圖檢索能夠找到並返回匹配的實體

### 🔧 已知問題和限制

1. **向量維度檢測**:
   - 如果集合為空，無法檢測維度（返回 None，使用默認模型）
   - 如果遇到未知維度，使用默認模型並記錄警告

2. **模型映射（v4.1 更新）**:
   - 新增 `qwen3-embedding:latest` 模型（1024維）支援
   - 推薦使用 MoE 系統的語言感知模型選擇
   - 可以通過環境變量 `MOE_EMBEDDING_MODEL` 配置

3. **性能影響**:
   - 向量維度檢測使用緩存機制，只在首次查詢時檢測
   - 關係擴展可能增加查詢時間，但提高了檢索覆盖率

### 📝 使用說明

#### 配置向量維度到模型的映射

**方法 1: 環境變量（維度映射）**

```bash
export EMBEDDING_DIMENSION_MODEL_MAP='{"384": "nomic-embed-text", "768": "bge-large-zh-v1.5", "1024": "qwen3-embedding"}'
```

**方法 2: MoE 語言感知配置（推薦 v4.1）**

```bash
export MOE_EMBEDDING_MODEL="qwen3-embedding:latest"
```

**方法 3: 修改代碼**
在 `services/api/services/embedding_service.py` 中修改 `LANGUAGE_MODEL_MAP` 字典

#### 運行測試

```bash
# 調試圖檢索
python scripts/debug_graph_retrieval.py

# 測試所有修復
python scripts/test_hybrid_rag_fixes.py
```

---

**最後更新日期: 2026-01-20 (v4.1 更新嵌入模型配置)
**維護人**: Daniel Chung
