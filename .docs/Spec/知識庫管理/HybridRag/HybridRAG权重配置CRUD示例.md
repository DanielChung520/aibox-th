# HybridRAG 權重配置 CRUD 示例

**創建日期**: 2026-01-05
**創建人**: Daniel Chung
**最後修改日期**: 2026-01-05

---

## 📋 概述

本文檔提供 HybridRAG 權重配置的完整 CRUD 操作示例代碼。

---

## 🔧 完整 CRUD 示例代碼

### 1. 導入模塊

```python
from genai.workflows.rag.hybrid_rag_config import HybridRAGConfigService
```

### 2. 創建配置服務實例

```python
# 創建配置服務（使用默認 ConfigStoreService）
config_service = HybridRAGConfigService()

# 或者傳入自定義的 ConfigStoreService
from services.api.services.config_store_service import ConfigStoreService
custom_config_service = ConfigStoreService()
rag_config_service = HybridRAGConfigService(config_service=custom_config_service)
```

### 3. 初始化默認配置（Create）

```python
# 初始化系統級默認配置
config_id = config_service.initialize_default_config(
    force=False,  # 如果為 True，強制覆蓋現有配置
    changed_by="system"  # 變更者（用戶 ID）
)

print(f"配置 ID: {config_id}")
```

**默認配置內容**：
```json
{
  "default": {"vector_weight": 0.6, "graph_weight": 0.4},
  "structure_query": {"vector_weight": 0.4, "graph_weight": 0.6},
  "semantic_query": {"vector_weight": 0.7, "graph_weight": 0.3},
  "entity_query": {"vector_weight": 0.3, "graph_weight": 0.7}
}
```

### 4. 讀取配置（Read）

#### 4.1 獲取權重（根據查詢類型動態調整）

```python
# 獲取系統級權重（結構化查詢）
weights = config_service.get_weights(query="結構化的AI需求分析框架步驟")
print(f"權重: {weights}")  # {"vector_weight": 0.4, "graph_weight": 0.6}

# 獲取系統級權重（實體查詢）
weights = config_service.get_weights(query="X與Y的關係是什麼")
print(f"權重: {weights}")  # {"vector_weight": 0.3, "graph_weight": 0.7}

# 獲取系統級權重（語義查詢）
weights = config_service.get_weights(query="解釋一下AI需求分析")
print(f"權重: {weights}")  # {"vector_weight": 0.7, "graph_weight": 0.3}

# 獲取系統級權重（默認）
weights = config_service.get_weights(query="一般查詢")
print(f"權重: {weights}")  # {"vector_weight": 0.6, "graph_weight": 0.4}
```

#### 4.2 獲取租戶級權重

```python
# 獲取租戶級權重
weights = config_service.get_weights(
    query="AI需求分析框架步驟",
    tenant_id="tenant_001"
)
```

#### 4.3 獲取用戶級權重

```python
# 獲取用戶級權重
weights = config_service.get_weights(
    query="AI需求分析框架步驟",
    tenant_id="tenant_001",
    user_id="user_001"
)
```

#### 4.4 獲取完整配置模型

```python
# 獲取系統級配置
config = config_service.get_config_model()
if config:
    print(f"配置 Scope: {config.scope}")
    print(f"配置數據: {config.config_data}")
    print(f"是否啟用: {config.is_active}")
    print(f"創建時間: {config.created_at}")
    print(f"更新時間: {config.updated_at}")

# 獲取租戶級配置
config = config_service.get_config_model(tenant_id="tenant_001")

# 獲取用戶級配置
config = config_service.get_config_model(
    tenant_id="tenant_001",
    user_id="user_001"
)
```

### 5. 創建/更新配置（Create/Update）

#### 5.1 創建系統級配置

```python
# 定義權重配置
weights = {
    "default": {"vector_weight": 0.6, "graph_weight": 0.4},
    "structure_query": {"vector_weight": 0.4, "graph_weight": 0.6},
    "semantic_query": {"vector_weight": 0.7, "graph_weight": 0.3},
    "entity_query": {"vector_weight": 0.3, "graph_weight": 0.7},
}

# 保存配置（創建或更新）
config_id = config_service.save_weights(
    weights=weights,
    changed_by="admin_user"
)

print(f"配置 ID: {config_id}")
```

#### 5.2 創建租戶級配置

```python
# 定義租戶級權重配置
tenant_weights = {
    "default": {"vector_weight": 0.5, "graph_weight": 0.5},
    "structure_query": {"vector_weight": 0.3, "graph_weight": 0.7},
}

# 保存租戶級配置
config_id = config_service.save_weights(
    weights=tenant_weights,
    tenant_id="tenant_001",
    changed_by="tenant_admin"
)
```

#### 5.3 創建用戶級配置

```python
# 定義用戶級權重配置
user_weights = {
    "default": {"vector_weight": 0.5, "graph_weight": 0.5},
}

# 保存用戶級配置
config_id = config_service.save_weights(
    weights=user_weights,
    tenant_id="tenant_001",
    user_id="user_001",
    changed_by="user_001"
)
```

### 6. 更新配置（Update - 部分更新）

```python
# 部分更新（只更新 structure_query 的權重）
updated_weights = {
    "structure_query": {"vector_weight": 0.5, "graph_weight": 0.5}
}

# 更新配置（會合併現有配置）
config_id = config_service.update_weights(
    weights=updated_weights,
    changed_by="admin_user"
)

# 更新租戶級配置
config_id = config_service.update_weights(
    weights=updated_weights,
    tenant_id="tenant_001",
    changed_by="tenant_admin"
)

# 更新用戶級配置
config_id = config_service.update_weights(
    weights=updated_weights,
    tenant_id="tenant_001",
    user_id="user_001",
    changed_by="user_001"
)
```

### 7. 刪除配置（Delete）

**注意**：當前 `ConfigStoreService` 沒有提供刪除方法，但可以通過設置 `is_active=False` 來禁用配置。

如果需要刪除，可以直接使用 `ConfigStoreService`：

```python
from services.api.services.config_store_service import ConfigStoreService
from genai.workflows.rag.hybrid_rag_config import HYBRID_RAG_CONFIG_SCOPE

config_store_service = ConfigStoreService()

# 獲取配置
config = config_store_service.get_config(scope=HYBRID_RAG_CONFIG_SCOPE)
if config:
    # 設置 is_active=False 來禁用配置
    from services.api.models.config import ConfigUpdate
    config_update = ConfigUpdate(is_active=False)
    # 然後使用 save_config 更新配置
    # ...（需要實現禁用邏輯）
```

---

## 🔍 完整示例代碼

```python
"""
HybridRAG 權重配置完整 CRUD 示例
"""

from genai.workflows.rag.hybrid_rag_config import HybridRAGConfigService

def main():
    # 1. 創建配置服務
    config_service = HybridRAGConfigService()

    # 2. 初始化默認配置（如果不存在）
    try:
        config_id = config_service.initialize_default_config(force=False, changed_by="system")
        print(f"✅ 配置初始化成功，配置 ID: {config_id}")
    except Exception as e:
        print(f"⚠️ 配置可能已存在: {e}")

    # 3. 讀取權重（根據查詢類型）
    test_queries = [
        "結構化的AI需求分析框架步驟",  # structure_query
        "X與Y的關係是什麼",              # entity_query
        "解釋一下AI需求分析",             # semantic_query
        "一般查詢",                      # default
    ]

    print("\n【權重讀取測試】")
    for query in test_queries:
        weights = config_service.get_weights(query=query)
        print(f"查詢: {query}")
        print(f"  權重: {weights}")

    # 4. 獲取完整配置
    print("\n【完整配置讀取】")
    config = config_service.get_config_model()
    if config:
        print(f"配置 Scope: {config.scope}")
        print(f"配置數據:")
        for query_type, weights in config.config_data.items():
            print(f"  {query_type}: {weights}")

    # 5. 更新配置（部分更新）
    print("\n【配置更新測試】")
    updated_weights = {
        "structure_query": {"vector_weight": 0.5, "graph_weight": 0.5}
    }
    try:
        config_id = config_service.update_weights(
            weights=updated_weights,
            changed_by="admin_user"
        )
        print(f"✅ 配置更新成功，配置 ID: {config_id}")

        # 驗證更新
        weights = config_service.get_weights(query="結構化的AI需求分析框架步驟")
        print(f"更新後的權重: {weights}")
    except Exception as e:
        print(f"❌ 配置更新失敗: {e}")

    # 6. 創建租戶級配置
    print("\n【租戶級配置創建】")
    tenant_weights = {
        "default": {"vector_weight": 0.5, "graph_weight": 0.5},
        "structure_query": {"vector_weight": 0.3, "graph_weight": 0.7},
    }
    try:
        config_id = config_service.save_weights(
            weights=tenant_weights,
            tenant_id="tenant_001",
            changed_by="tenant_admin"
        )
        print(f"✅ 租戶級配置創建成功，配置 ID: {config_id}")

        # 驗證租戶級配置
        weights = config_service.get_weights(
            query="結構化的AI需求分析框架步驟",
            tenant_id="tenant_001"
        )
        print(f"租戶級權重: {weights}")
    except Exception as e:
        print(f"❌ 租戶級配置創建失敗: {e}")


if __name__ == "__main__":
    main()
```

---

## ⚠️ 注意事項

### 權重驗證

權重配置必須滿足以下條件：

1. **權重範圍**：`vector_weight` 和 `graph_weight` 必須在 0.0 到 1.0 之間
2. **權重和**：`vector_weight + graph_weight` 必須等於 1.0（允許 1% 誤差）
3. **數據類型**：權重必須是數值類型（int 或 float）

如果權重配置無效，會拋出 `ValueError` 異常。

### 配置優先級

配置合併順序：**System → Tenant → User**（優先級由低到高）

- **System 級配置**：默認配置，適用於所有租戶和用戶
- **Tenant 級配置**：覆蓋 System 級配置，適用於特定租戶的所有用戶
- **User 級配置**：覆蓋 System 和 Tenant 級配置，適用於特定用戶

### 查詢類型檢測

系統會根據查詢中的關鍵詞自動檢測查詢類型：

- **結構化查詢**（structure_query）：框架、步驟、流程、階段、順序、架構、設計
- **實體查詢**（entity_query）：是什麼、關係、連接、包含、屬於
- **語義查詢**（semantic_query）：其他查詢（默認）
- **默認**（default）：當無法匹配查詢類型時使用

---

## 🔗 相關文檔

- [HybridRAG 權重配置使用說明](./HybridRAG权重配置使用说明.md)
- [ConfigStoreService 使用說明](../系统设计文档/tools/System-Config-存储位置说明.md)

---

**最後更新日期**: 2026-01-05
**維護人**: Daniel Chung

