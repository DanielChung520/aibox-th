# ISO 品質管理系統 Ontology 設計文件

## 設計架構

```
Basic: 5W1H_Base (既有)
  └── Domain: ISO_Quality_Management (ISO 品質管理系統領域)
        └── Major: Manufacturing_Management_Process (製造管理流程專業)
```

## 涵蓋範圍

本 Ontology 完整對應福祉 ISO 文件系統（1,353 份文件），涵蓋：

### Domain 層：ISO_Quality_Management（22 Entity Classes, 14 Object Properties）

定義 ISO 9001 文件化管理體系的框架概念：
- **文件四階層**：一階品質手冊 → 二階管理辦法 → 三階作業規範 → 四階表單
- **文件生命週期**：版本、狀態、變更紀錄
- **品質管理要素**：內部稽核、管理審查、矯正措施、持續改善
- **ERP 對應**：各文件對應的 ERP 功能模組

### Major 層：Manufacturing_Management_Process（63 Entity Classes, 46 Object Properties）

定義福祉車輛改裝製造的具體營運概念，分為 14 大類：

| 分類 | Entity Classes | 對應文件 |
|------|---------------|----------|
| 📋 訂單與客戶 | Customer_Order, Sales_Project, Customer, Customer_Complaint, After_Sales_Service | QP-P01~P05, TB-Pxx |
| 🚗 產品與平台 | Product, Vehicle_Platform, Vehicle_Modification_Type, Key_Component | WP-Txx, TB-T20 |
| ⚙️ 製程與生產 | Production_Process, Work_Station_Operation, Labor_Hour_Segment, Welding_Specification, Risk_Assessment | WP-Txx, WO-T01, TB-T58 |
| 📦 物料與供應鏈 | Material, Incoming_Material, Supplier, Purchase_Order, Outsourcing_Process | QP-S04~S06,S08,S09, TB-T10,T31 |
| 🏭 庫存與儲位 | Inventory_Record, Warehouse_Location, Product_Traceability | QP-S04, QP-S08 |
| 🔬 品質檢驗 | Quality_Inspection, Inspection_Type, Self_Inspection, Quality_Check_Record, Key_Component_Check_Record | QP-T05, TB-T04, TB-T05 |
| ⚠️ 不符合與矯正 | Nonconformity_Handling_Record, Special_Acceptance | QP-T04, QP-S15, TB-T02, TB-T08, TB-S27 |
| 📐 儀器管理 | Instrument, Instrument_Type, Calibration_Record, Calibration_Status, Calibration_Plan, Internal_Calibration, External_Calibration, Instrument_Master_List | QP-T07, TB-T16, TB-T17, TB-T18, TB-T19 |
| 🔧 設備管理 | Equipment, Equipment_Master_List, Equipment_Log, Maintenance_Record, Maintenance_Type, Equipment_Status | QP-T06, TB-T12, TB-T13 |
| 🛠 工具治具 | Tool, Jig_Fixture | TB-T14, TB-T15, TB-T55 |
| 🆕 新產品開發 | New_Product_Development, NPD_Phase, Engineering_Change, FMEA | QP-T08, QP-T09, TB-T50~T67 |
| 📜 法規檢驗 | Vehicle_Safety_Regulation, Compliance_Inspection_Record | TB-T21~T25, T30, T32~T34 |
| 👥 人力資源 | Employee, Training_Record, Skill_Certification, Customer_Property | QP-S03, TB-S05~S08, TB-S29, TB-S30 |
| 📑 文件管理 | Drawing, Document_Overall_List | QP-T01, TB-S01, TB-S04, TB-T01 |

## 匯入 ArangoDB 方式

### 方式一：透過 ArangoDB REST API

```bash
# Domain
curl -X POST http://localhost:8529/_db/abc_desktop/_api/document/ontologies \
  -H "Content-Type: application/json" \
  -u root:abc_desktop_2026 \
  -d @domain_iso_quality_management.json

# Major
curl -X POST http://localhost:8529/_db/abc_desktop/_api/document/ontologies \
  -H "Content-Type: application/json" \
  -u root:abc_desktop_2026 \
  -d @major_manufacturing_management_process.json
```

### 方式二：透過 arangosh

```javascript
var domain = cat('domain_iso_quality_management.json');
db.ontologies.save(JSON.parse(domain));

var major = cat('major_manufacturing_management_process.json');
db.ontologies.save(JSON.parse(major));
```

### 方式三：寫入 Rust seed 函數

比照 `api/src/db/ontology.rs` 中的 `seed_ontologies()` 模式，新增兩個 Ontology 實例。

## 上傳策略建議

### Phase 1：建立 Knowledge Root
在系統中建立一個 Knowledge Root：
- 名稱：`福祉 ISO 品質管理系統`
- Ontology Domain：`ISO_Quality_Management`
- Ontology Majors：`["Manufacturing_Management_Process"]`

### Phase 2：上傳文件體系總覽（結構錨點）
先製作並上傳一份結構化 markdown，描述文件全貌與關聯：
- `福祉ISO文件體系總覽.md` → 圖譜萃取後建立結構骨架

### Phase 3：分批上傳個別文件
依層級分批上傳，每份檔案附加 metadata：
- `hierarchy_level`: "1" | "2" | "3" | "4"
- `document_code`: "QM-P01" | "QP-S01" | ...
- `factory`: "樹八廠" | "土城廠" (若適用)
- `form_type`: "template" | "instance" (四階文件)

### Phase 4：跨檔案關聯（未來增強）
在 pipeline 中加入後處理步驟，根據 metadata 和 ontology 定義，自動在 `knowledge_graph_edges` 中建立跨檔案的關係邊。
