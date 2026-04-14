# da_expressions 場景新增進度管制表

## 總覽

| 階段 | 模組 | 表格數 | 表達式數 | 狀態 |
|------|------|--------|----------|------|
| Phase 1 | Sales | 43 | 130 | ✅ 已完成 |
| Phase 2 | Manufacturing | 61 | 233 | ✅ 已完成 |
| Phase 3 | Quality | 65 | 216 | ✅ 已完成 |
| Phase 4 | Trade | 42 | 155 | ✅ 已完成 |
| Phase 5 | Base | 32 | 108 | ✅ 已完成 |
| Phase 6 | Management | 19 | 68 | ✅ 已完成 |

**總計**：910 表達式（Phase 1-6 新增 773 表達式）

---

## Phase 1: Sales 模組

- **Core Tables（13 表）**：已擴展為 4+ 表達式
- **Basic Tables（29 表）**：已擴展為 4 表達式（89 表達式）
- **RAGICSALES_17**：17 表達式（含 TEST 場景）
- **注意**：RAGICSALES_17 表達式 domain="inventory"（非 "sales"）

### 表達式分布

| Domain | 表達式數 | 說明 |
|--------|----------|------|
| sales | 113 | 標準 Sales 表達式 |
| inventory | 17 | RAGICSALES_17 表達式 |
| crm | 17 | CRM 相關 |
| finance | 5 | 財務相關 |
| contract | 5 | 合約相關 |
| marketing | 5 | 行銷相關 |

---

## Phase 2: Manufacturing 模組

### Core Tables（45 表，5 表達式）

45 個 Core Tables（aggregate=true）已擴展各 4 表達式（filter/search/list/aggregate）

| 表格 | 名稱 |
|------|------|
| MES_10, MES_11, MES_12, MES_14 | 原材料/添加物/重製品/報廢表 |
| MES_2~MES_9 | 各類原材料驗收紀錄表 |
| MES_20~MES_30 | 重製品/報廢相關 |
| MES2_1, MES2_2, MES2_3 | 生產需求/物料需求/托工單 |
| MES2_5, MES2_6, MES2_8 | 派工/製令/添加劑領用 |
| MES2_11, MES2_12 | 物料需求單預扣明細 |
| WORKREPORTINGAREA_1~13 | 工序報工單 |

### Basic Tables（16 表，3 表達式）

16 個 Basic Tables 已擴展各 3 表達式（filter/search/list）

| 表格 | 名稱 |
|------|------|
| MES_1, MES_19 | 原料化學性快篩檢驗 |
| MES_13, MES_31 | 成品留樣保存 |
| MES_15~17, MES_33~35 | 溫度壓力 |
| MES_18, MES_36 | 機聯到MES |
| MES2_4 | 領料單 |
| MES2_7 | 食品添加物領用與投料複核 |
| MES2_9 | 採購預算表 |
| MES2_10 | 自主管理通知單 |

---

## Phase 3-6: 已完成

| 模組 | 表格數 | 表達式數 | 狀態 |
|------|--------|----------|------|
| Quality | 65 | 216 | ✅ 已完成 |
| Trade | 42 | 155 | ✅ 已完成 |
| Base | 32 | 108 | ✅ 已完成 |
| Management | 19 | 68 | ✅ 已完成 |

---

## 已知問題

### 1. Domain 不一致
- RAGICSALES_17 表達式 domain="inventory"，但 da_tables.domain="sales"
- **影響**：意圖路由可能匹配錯誤 domain

### 2. Null Domain 表達式
- 248 個表達式 domain=NULL（需要處理）

### 3. 向量匹配效果
- nomic-embed-text 對中文語意理解不足
- 建議更換為 qwen3-embedding:latest（4096 維，需重建 collection）

---

## 執行記錄

| 日期 | 操作 | 表達式數 |
|------|------|----------|
| 2026-04-13 | 建立 RAGICSALES_17 TEST 場景 | +12 |
| 2026-04-13 | 修復 schema_linker 支援 list 格式 | - |
| 2026-04-13 | 新增 da.llm_model 等 system_params | - |
| 2026-04-13 | 同步所有表達式到 Qdrant（含 intent_id 修復）| 413 |
| 2026-04-13 | 擴展 Manufacturing Basic Tables | +48 |
| 2026-04-13 | 同步 Manufacturing 表達式到 Qdrant | +233 |
| 2026-04-13 | 擴展 Quality 表達式 | +216 |
| 2026-04-13 | 同步 Quality 表達式到 Qdrant | +210 |
| 2026-04-13 | 擴展 Trade 表達式 | +155 |
| 2026-04-13 | 同步 Trade 表達式到 Qdrant | +155 |
| 2026-04-13 | 擴展 Base 表達式 | +108 |
| 2026-04-13 | 同步 Base 表達式到 Qdrant | +108 |
| 2026-04-13 | 擴展 Management 表達式 | +68 |
| 2026-04-13 | 同步 Management 表達式到 Qdrant | +68 |
