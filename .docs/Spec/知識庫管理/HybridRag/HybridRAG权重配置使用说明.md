# HybridRAG 權重配置使用說明

**創建日期**: 2026-01-05
**創建人**: Daniel Chung
**最後修改日期**: 2026-01-05

---

## 📋 概述

HybridRAG 權重配置服務提供靈活的權重管理機制，允許在 ArangoDB 中存儲和管理不同查詢類型的權重配置，支持系統/租戶/用戶三層配置。

---

## 🎯 設計目標

1. **配置化權重**：權重配置存儲在 ArangoDB，無需修改代碼即可調整
2. **多層級支持**：支持系統級、租戶級、用戶級配置，優先級：User > Tenant > System
3. **動態調整**：根據查詢類型自動調整權重（結構化查詢、實體查詢、語義查詢）
4. **完整 CRUD**：提供完整的創建、讀取、更新、刪除操作

---

## 📦 配置結構

### 配置 Scope

- **Scope**: `rag.hybrid_weights`
- **Collection**: `system_configs` / `tenant_configs` / `user_configs`

### 配置數據結構

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

### 查詢類型

| 查詢類型 | 關鍵詞 | 默認權重 | 說明 |
|---------|--------|---------|------|
| `structure_query` | 框架、步驟、流程、階段、順序、架構、設計 | 向量 0.4，圖 0.6 | 結構化查詢（如"AI需求分析框架步驟"） |
| `entity_query` | 是什麼、關係、連接、包含、屬於 | 向量 0.3，圖 0.7 | 實體查詢（如"X與Y的關係是什麼"） |
| `semantic_query` | 其他 | 向量 0.7，圖 0.3 | 語義查詢（如"解釋一下..."） |
| `default` | - | 向量 0.6，圖 0.4 | 默認權重（當無法匹配查詢類型時使用） |

---

## 🔧 使用方法

### 1. 初始化配置

```python
from genai.workflows.rag.hybrid_rag_config import HybridRAGConfigService

# 創建配置服務
config_service = HybridRAGConfigService()

# 初始化默認配置（系統級）
config_id = config_service.initialize_default_config(force=False, changed_by="system")
```

### 2. 獲取權重配置

```python
# 獲取系統級權重（根據查詢類型動態調整）
weights = config_service.get_weights(query="結構化的AI需求分析框架步驟")
# 返回: {"vector_weight": 0.4, "graph_weight": 0.6}

# 獲取租戶級權重
weights = config_service.get_weights(
    query="AI需求分析框架",
    tenant_id="tenant_001"
)

# 獲取用戶級權重
weights = config_service.get_weights(
    query="AI需求分析框架",
    tenant_id="tenant_001",
    user_id="user_001"
)
```

### 3. 保存權重配置

```python
# 保存系統級配置
weights = {
    "default": {"vector_weight": 0.6, "graph_weight": 0.4},
    "structure_query": {"vector_weight": 0.4, "graph_weight": 0.6},
    "semantic_query": {"vector_weight": 0.7, "graph_weight": 0.3},
    "entity_query": {"vector_weight": 0.3, "graph_weight": 0.7},
}

config_id = config_service.save_weights(
    weights=weights,
    changed_by="admin_user"
)

# 保存租戶級配置
config_id = config_service.save_weights(
    weights=weights,
    tenant_id="tenant_001",
    changed_by="tenant_admin"
)

# 保存用戶級配置
config_id = config_service.save_weights(
    weights=weights,
    tenant_id="tenant_001",
    user_id="user_001",
    changed_by="user_001"
)
```

### 4. 更新權重配置

```python
# 部分更新（只更新 structure_query 的權重）
updated_weights = {
    "structure_query": {"vector_weight": 0.5, "graph_weight": 0.5}
}

config_id = config_service.update_weights(
    weights=updated_weights,
    changed_by="admin_user"
)
```

### 5. 獲取完整配置模型

```python
# 獲取系統級配置
config = config_service.get_config_model()

# 獲取租戶級配置
config = config_service.get_config_model(tenant_id="tenant_001")

# 獲取用戶級配置
config = config_service.get_config_model(
    tenant_id="tenant_001",
    user_id="user_001"
)
```

---

## 💻 在 HybridRAGService 中使用

### 自動從配置讀取權重（推薦）

```python
from genai.workflows.rag.hybrid_rag import HybridRAGService
from agents.infra.memory.aam.aam_core import AAMManager

# 創建 HybridRAGService（不指定權重，將自動從配置讀取）
aam_manager = AAMManager(...)
hybrid_rag_service = HybridRAGService(
    aam_manager=aam_manager,
    # vector_weight 和 graph_weight 不指定，將從配置讀取
    tenant_id="tenant_001",  # 可選
    user_id="user_001",      # 可選
)

# 檢索時自動使用配置權重（根據查詢類型動態調整）
results = hybrid_rag_service.retrieve(
    query="結構化的AI需求分析框架步驟",
    top_k=10
)
```

### 手動指定權重（不推薦，除非有特殊需求）

```python
# 手動指定權重（不使用配置）
hybrid_rag_service = HybridRAGService(
    aam_manager=aam_manager,
    vector_weight=0.6,  # 手動指定
    graph_weight=0.4,   # 手動指定
)
```

---

## 🚀 初始化腳本

使用初始化腳本創建默認配置：

```bash
cd /Users/daniel/GitHub/AI-Box
python scripts/init_hybrid_rag_config.py
```

---

## 📊 配置優先級

配置合併順序：**System → Tenant → User**（優先級由低到高）

1. **System 級配置**：默認配置，適用於所有租戶和用戶
2. **Tenant 級配置**：覆蓋 System 級配置，適用於特定租戶的所有用戶
3. **User 級配置**：覆蓋 System 和 Tenant 級配置，適用於特定用戶

---

## ⚠️ 注意事項

### 權重驗證

1. **權重範圍**：`vector_weight` 和 `graph_weight` 必須在 0.0 到 1.0 之間
2. **權重和**：`vector_weight + graph_weight` 必須等於 1.0（允許 1% 誤差）
3. **數據類型**：權重必須是數值類型（int 或 float）

### 配置讀取

1. **首次讀取**：如果配置不存在，將使用硬編碼的默認值
2. **配置失效**：如果配置無效（驗證失敗），將使用硬編碼的默認值
3. **動態調整**：每次檢索時都會根據查詢類型動態調整權重

---

## 🔍 查詢類型檢測邏輯

### 結構化查詢（structure_query）

**關鍵詞**：框架、步驟、流程、階段、順序、架構、設計

**示例**：
- "結構化的AI需求分析框架步驟"
- "系統架構設計流程"
- "需求分析階段順序"

### 實體查詢（entity_query）

**關鍵詞**：是什麼、關係、連接、包含、屬於

**示例**：
- "X與Y的關係是什麼"
- "A包含哪些B"
- "C屬於哪個D"

### 語義查詢（semantic_query）

**默認類型**：不匹配結構化查詢和實體查詢的查詢

**示例**：
- "解釋一下AI需求分析"
- "如何進行需求分析"
- "什麼是AI需求分析"

---

## 📝 完整 CRUD 示例

```python
from genai.workflows.rag.hybrid_rag_config import HybridRAGConfigService

# 創建配置服務
config_service = HybridRAGConfigService()

# 1. 初始化默認配置
config_id = config_service.initialize_default_config(force=False, changed_by="system")
print(f"配置 ID: {config_id}")

# 2. 獲取權重
weights = config_service.get_weights(query="AI需求分析框架步驟")
print(f"權重: {weights}")  # {"vector_weight": 0.4, "graph_weight": 0.6}

# 3. 保存自定義配置
custom_weights = {
    "default": {"vector_weight": 0.5, "graph_weight": 0.5},
    "structure_query": {"vector_weight": 0.3, "graph_weight": 0.7},
}
config_id = config_service.save_weights(
    weights=custom_weights,
    changed_by="admin_user"
)

# 4. 更新配置（部分更新）
updated_weights = {
    "structure_query": {"vector_weight": 0.4, "graph_weight": 0.6}
}
config_id = config_service.update_weights(
    weights=updated_weights,
    changed_by="admin_user"
)

# 5. 獲取完整配置
config = config_service.get_config_model()
print(f"配置內容: {config.config_data}")
```

---

## 🔗 相關文檔

- [ConfigStoreService 使用說明](../系统设计文档/tools/System-Config-存储位置说明.md)
- [HybridRAG 查詢邏輯說明](./系统设计文档/核心组件/文件上傳向量圖譜/向量與圖檢索混合查詢邏輯.md)

---

**最後更新日期**: 2026-01-05
**維護人**: Daniel Chung

