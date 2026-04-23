# Ragic Schema 變更更新規範與腳本

> **最後更新**：2026-04-18
> **用途**：當 Ragic 資料庫 Schema 變更時，執行本文件中的腳本進行全面同步。

---

## 觸發時機

當 Ragic 資料庫發生以下變更時，必須執行本規範中的腳本：

| 變更類型 | 說明 | 緊急性 |
|----------|------|--------|
| 新增 Sheet | 在 Ragic 新增表單 | ⚡ 高 |
| 刪除 Sheet | 刪除既有表單 | ⚡ 高 |
| 新增欄位 | 在既有 Sheet 新增欄位 | 🟡 中 |
| 刪除欄位 | 刪除既有欄位 | 🟡 中 |
| 欄位類型變更 | 文字→數字、單選→多選等 | 🟡 中 |
| 連結/載入欄位變更 | 新增跨表連結、修改載入邏輯 | ⚡ 高 |
| 子公司 Schema 變更 | dawnlink、2025shianyong 等 | ⚡ 高 |

---

## 更新腳本總覽

```
ai-services/datalake/
│
├── ⭐ 01_sync_ragic_schema.sh          # 主腳本：一步到位同步所有
├── ⭐ 02_sync_ragic_intents.sh        # 主腳本：同步 Intents
│
├── seed_ragic_schema.py               # Phase 1 核心 Schema 播種（寫入 ArangoDB）
├── seed_ragic_schema_full.py           # 完整 Schema 播種（所有 Sheets）
├── seed_ragic_intents.py              # Intent 播種（寫入 ArangoDB）
├── seed_intent_catalog_ragic.py       # Intent Catalog 播種
│
├── ragic_field_mapping.py             # ⚠️ 手動維護：Field ID → 中文欄位名
│
└── generate_ragic_fake_data.py        # 測試資料生成（視需要）
```

---

## ⭐ 推薦流程：一步到位腳本

### 腳本 1：同步 Schema + Intents（最完整）

```bash
# 位置：ai-services/datalake/01_sync_ragic_schema.sh
# 用法：bash 01_sync_ragic_schema.sh <account_name>
# 範例：bash 01_sync_ragic_schema.sh dawnlink

#!/bin/bash
set -e

ACCOUNT=${1:-dawnlink}
echo "============================================"
echo "Ragic Schema Sync for: $ACCOUNT"
echo "============================================"

# 1. Sync Schema to Qdrant (via API)
echo "[1/4] Syncing Schema to Qdrant..."
curl -X POST "http://localhost:8003/ragic/schema/sync" \
  -H "Content-Type: application/json" \
  -d "{\"connection_name\": \"$ACCOUNT\"}"

# 2. Sync Intents to Qdrant
echo "[2/4] Syncing Intents to Qdrant..."
curl -X POST "http://localhost:8003/ragic/intent/sync" \
  -H "Content-Type: application/json" \
  -d "{\"connection_name\": \"$ACCOUNT\"}"

# 3. Reload Config
echo "[3/4] Reloading Config..."
curl -X POST "http://localhost:8003/ragic/config/reload"

# 4. Verify
echo "[4/4] Verifying..."
curl "http://localhost:8003/ragic/health"

echo "============================================"
echo "Done! Schema sync completed for $ACCOUNT"
echo "============================================"
```

### 腳本 2：同步 Intents

```bash
# 位置：ai-services/datalake/02_sync_ragic_intents.sh
# 用法：bash 02_sync_ragic_intents.sh <account_name>

#!/bin/bash
set -e

ACCOUNT=${1:-dawnlink}
echo "Syncing Intents for: $ACCOUNT"
curl -X POST "http://localhost:8003/ragic/intent/sync" \
  -H "Content-Type: application/json" \
  -d "{\"connection_name\": \"$ACCOUNT\"}"
```

---

## 📋 完整更新檢查清單

### Step 1：更新 API 文件（文件層）

當 Ragic Schema 變更時，首先重新從 Ragic 匯出 API 文件：

| 檔案 | 說明 | 更新頻率 |
|------|------|----------|
| `.docs/Ragic/dawnlink202604.md` | 道霖 Ragic API 文件 | Schema 變更時 |
| `.docs/Ragic/2025shianyong.md` | 鮮湧 Ragic API 文件 | Schema 變更時 |
| `.docs/Ragic/twbraun.md` | 道霖標準版 API 文件 | Schema 變更時 |
| `.docs/Spec/DB/RagicTableSchema.md` | 標準版 Schema（twbraun） | Schema 變更時 |

**匯出方式**：
1. 登入 Ragic 後台
2. 進入每個 Sheet 的 API 設定頁面
3. 複製 API 文件（Markdown 格式）
4. 替換對應的 `.md` 檔案

### Step 2：更新 Field Mapping（程式層）

```bash
# 位置：ai-services/datalake/ragic_field_mapping.py
```

**何時需要更新**：
- 新增欄位時 → 在對應的 `*_MAP` dict 中加入新 mapping
- 欄位名稱變更時 → 更新對應的 value

**格式**：
```python
# CFG9 = 品項管理
CFG9_MAP: dict[str, str] = {
    "1015220": "品項代碼(短)",      # 新增欄位
    "1015221": "啟用狀態",
    "1015223": "品項說明",          # 現有欄位
    # ... 
}
```

**影響範圍**：
- `ragic_field_mapping.py` 被以下腳本使用：
  - `generate_ragic_fake_data.py`
  - `generate_ragic_tx_data.py`
  - `migrate_ragic_data_to_chinese.py`

### Step 3：同步 Schema 到 Qdrant（系統層）

```bash
# 方式 1：透過 API（推薦）
curl -X POST "http://localhost:8003/ragic/schema/sync" \
  -H "Content-Type: application/json" \
  -d '{"connection_name": "dawnlink"}'

# 方式 2：直接執行 Python 腳本
cd ai-services/datalake
python seed_ragic_schema.py        # Phase 1 核心 Schema
python seed_ragic_schema_full.py    # 完整 Schema
```

**同步內容**：
- Table 名稱、Key、Path
- 欄位 ID、Name、Type
- 子表格結構
- 連結/載入欄位

**儲存位置**：
- Qdrant Collection: `ragic_schemas`

### Step 4：同步 Intents（AI 理解層）

```bash
# 方式 1：透過 API（推薦）
curl -X POST "http://localhost:8003/ragic/intent/sync" \
  -H "Content-Type: application/json" \
  -d '{"connection_name": "dawnlink"}'

# 方式 2：直接執行 Python 腳本
cd ai-services/datalake
python seed_ragic_intents.py
python seed_intent_catalog_ragic.py
```

**同步內容**：
- Intent Pattern（自然語言範例）
- Filter Template（篩選條件範本）
- API Template（API 呼叫範本）

**儲存位置**：
- Qdrant Collection: `ragic_intents`

### Step 5：更新 Ontology（本體知識庫）

當 Ragic Schema 變更涉及**新的業務概念**時，需要更新本體：

| 檔案 | 用途 |
|------|------|
| `.docs/Spec/知識庫管理/EEA-AIBox-Major-Onology.json` | 主要本體（通用） |
| `.docs/Spec/知識庫管理/mm-agent-major.json` | 物料管理本體 |
| `.docs/Spec/知識庫管理/ka-agent-domain.json` | 知識管理本體 |
| `.docs/Spec/知識庫管理/sd-domain.json` | 系統設計本體 |

**更新原則**：
- 新增 Table → 檢查是否需要新增本體節點
- 新增業務術語 → 新增同義詞映射
- 跨 Table 關聯 → 更新本體關係

### Step 6：更新系統參數（如有需要）

當新增子公司或變更連線設定時，更新 Ragic 系統管理模組：

```bash
# Ragic 路徑：ragic-setup/6

# 或透過 API
curl -X GET "http://localhost:8003/ragic/config/connections"
```

**需要更新的內容**：
- 新增子公司 → 在 `ragic-setup/6` 新增一筆設定
- API Key 變更 → 更新對應的 `api_key` 欄位
- 快取 TTL 調整 → 更新 `schema_cache_ttl_hours`

---

## 🔄 標準執行流程

```
┌─────────────────────────────────────────────────────────────┐
│  觸發：Ragic Schema 變更                                    │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 匯出並更新 API 文件                                  │
│  → .docs/Ragic/<account>.md                                │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 分析差異                                           │
│  → 找出新增/刪除/變更的 Sheets 和 欄位                      │
│  → 判斷影響範圍                                            │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 更新 Field Mapping（如有新增欄位）                    │
│  → ai-services/datalake/ragic_field_mapping.py              │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 執行一步到位腳本                                    │
│  → bash ai-services/datalake/01_sync_ragic_schema.sh       │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 更新 Ontology（如有新增業務概念）                    │
│  → .docs/Spec/知識庫管理/*.json                            │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 6: 更新系統參數（如有變更連線設定）                      │
│  → Ragic ragic-setup/6 或 API                            │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  完成！                                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚠️ 注意事項

### 1. Schema 與 Intent 的依賴關係

```
Schema 變更 → Intent 可能需要調整 → 但 Intent 不會自動刪除

原則：
- 新增 Schema → Intents 會自動支援（向量檢索）
- 刪除 Schema → Intents 需要手動清理
- 欄位變更 → Intents 可能需要更新 Template
```

### 2. 測試環境 vs 生產環境

```bash
# 測試環境（建議先在測試環境執行）
export RAGIC_ACCOUNT="dawnlink_test"
bash 01_sync_ragic_schema.sh dawnlink_test

# 確認無誤後再執行生產環境
export RAGIC_ACCOUNT="dawnlink"
bash 01_sync_ragic_schema.sh dawnlink
```

### 3. 快取問題

執行同步後，Config 會自動清除快取。如需手動清除：

```bash
curl -X POST "http://localhost:8003/ragic/config/reload"
```

---

## 📁 關鍵檔案索引

### Schema 相關

| 檔案 | 位置 | 用途 |
|------|------|------|
| `RagicTableSchema.md` | `.docs/Spec/DB/` | 標準版 Schema 定義 |
| `dawnlink202604.md` | `.docs/Ragic/` | 道霖完整 API 文件 |
| `ragic_schema.py` | `ai-services/datalake/` | Phase 1 Schema 定義 |
| `schema_sync.py` | `ai-services/data_agent/ragic/` | Qdrant Schema 同步 |
| `schema_store.py` | `ai-services/data_agent/ragic/` | Qdrant 儲存操作 |

### Intent 相關

| 檔案 | 位置 | 用途 |
|------|------|------|
| `seed_ragic_intents.py` | `ai-services/datalake/` | Intent 播種腳本 |
| `seed_intent_catalog_ragic.py` | `ai-services/datalake/` | Intent Catalog |
| `intent_store.py` | `ai-services/data_agent/ragic/` | Intent 儲存操作 |
| `intent_rag/` | `ai-services/data_agent/` | Intent RAG 模組 |

### Field Mapping

| 檔案 | 位置 | 用途 |
|------|------|------|
| `ragic_field_mapping.py` | `ai-services/datalake/` | Field ID → 中文 |

### Ontology

| 檔案 | 位置 | 用途 |
|------|------|------|
| `EEA-AIBox-Major-Onology.json` | `.docs/Spec/知識庫管理/` | 主要本體 |
| `mm-agent-major.json` | `.docs/Spec/知識庫管理/` | 物料管理本體 |
| `ka-agent-domain.json` | `.docs/Spec/知識庫管理/` | 知識管理本體 |

---

## 🆘 疑難排解

### Q1: Schema 同步成功但 AI 查不到資料

**檢查**：
1. Qdrant 中是否有該 Table 的 Schema？
   ```bash
   curl "http://localhost:6333/collections/ragic_schemas/points/404" 
   ```
2. Intent 是否正確匹配？
   ```bash
   curl -X POST "http://localhost:8003/ragic/query" \
     -d '{"query": "測試查詢", "connection_name": "dawnlink"}'
   ```

### Q2: Field Mapping 正確但翻譯錯誤

**原因**：可能有多個相同名稱的欄位在不同 Table

**解決**：使用完整的 Table + Field 路徑進行對照

### Q3: API 文件與實際 Schema 不符

**原因**：Ragic API 文件不會自動更新

**解決**：手動從 Ragic 後台重新匯出

---

## 📝 維護記錄

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-18 | 1.0.0 | Daniel | 初始版本 |
