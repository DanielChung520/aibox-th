//! Ontology Module
//!
//! # Description
//! 知識本體 (Ontology) 資料模型與種子資料
//! 支援三層結構: Basic (5W1H) / Domain (知識領域) / Major (知識專業)
//!
//! # Last Update: 2026-03-25 11:53:22
//! # Author: Daniel Chung
//! # Version: 1.0.0

use arangors::client::reqwest::ReqwestClient;
use arangors::Database;
use serde::{Deserialize, Serialize};
use serde_json::json;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntityClass {
    pub name: String,
    pub base_class: String,
    pub description: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ObjectProperty {
    pub name: String,
    pub description: String,
    pub domain: Vec<String>,
    pub range: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OntologyMetadata {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub domain_owner: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub domain: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub major_owner: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data_classification: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub intended_usage: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Ontology {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    #[serde(rename = "type")]
    pub ontology_type: String,
    pub name: String,
    pub version: String,
    pub default_version: bool,
    pub ontology_name: String,
    pub description: String,
    pub author: String,
    pub last_modified: String,
    pub inherits_from: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub compatible_domains: Option<Vec<String>>,
    pub tags: Vec<String>,
    pub use_cases: Vec<String>,
    pub entity_classes: Vec<EntityClass>,
    pub object_properties: Vec<ObjectProperty>,
    pub metadata: OntologyMetadata,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status: Option<String>,
}

pub async fn seed_ontologies(db: &Database<ReqwestClient>) -> Result<(), String> {
    let count: serde_json::Value = db
        .aql_str("RETURN LENGTH(ontologies)")
        .await
        .map_err(|e| format!("AQL error: {e}"))?
        .into_iter()
        .next()
        .unwrap_or(json!(0));

    if count.as_u64().unwrap_or(0) > 0 {
        return Ok(());
    }

    let col = db
        .collection("ontologies")
        .await
        .map_err(|e| format!("ontologies collection: {e}"))?;

    // --- Basic (5W1H) ---
    let basic = Ontology {
        _key: Some("basic_5w1h".into()),
        ontology_type: "basic".into(),
        name: "5W1H_Base".into(),
        version: "1.0".into(),
        default_version: true,
        ontology_name: "5W1H_Base_Ontology_OWL".into(),
        description: "基礎 5W1H 知識本體，定義 Who/What/When/Where/Why/How 六大維度的抽取意圖。".into(),
        author: "System".into(),
        last_modified: "2026-01-01".into(),
        inherits_from: vec![],
        compatible_domains: None,
        tags: vec!["5W1H".into(), "Base".into(), "Extraction".into()],
        use_cases: vec![
            "知識抽取意圖定義".into(),
            "問答維度分類".into(),
            "RAG 查詢路由".into(),
        ],
        entity_classes: vec![
            EntityClass { name: "Who".into(), base_class: "Dimension".into(), description: "人物維度 — 識別與事件相關的人員、角色、組織。".into() },
            EntityClass { name: "What".into(), base_class: "Dimension".into(), description: "事物維度 — 識別核心主題、物件、概念。".into() },
            EntityClass { name: "When".into(), base_class: "Dimension".into(), description: "時間維度 — 識別時間點、時段、頻率。".into() },
            EntityClass { name: "Where".into(), base_class: "Dimension".into(), description: "地點維度 — 識別地理位置、場所、區域。".into() },
            EntityClass { name: "Why".into(), base_class: "Dimension".into(), description: "原因維度 — 識別因果關係、動機、目的。".into() },
            EntityClass { name: "How".into(), base_class: "Dimension".into(), description: "方法維度 — 識別流程、手段、方式。".into() },
        ],
        object_properties: vec![],
        metadata: OntologyMetadata {
            domain_owner: Some("System".into()),
            domain: None,
            major_owner: None,
            data_classification: Some("PUBLIC".into()),
            intended_usage: Some(vec!["知識抽取維度分類".into()]),
        },
        status: Some("enabled".into()),
    };

    // --- Domain (Material_Management) ---
    let domain = Ontology {
        _key: Some("domain_material_mgmt".into()),
        ontology_type: "domain".into(),
        name: "Material_Management".into(),
        version: "1.0".into(),
        default_version: true,
        ontology_name: "Material_Management_Domain_Ontology".into(),
        description: "物料管理知識領域本體論，定義物料主檔、庫存、採購、入出庫、批次、供應商與審計等核心概念。適用於企業物料管理系統、ERP 知識上架、RAG 檢索與決策支援場景。".into(),
        author: "Daniel Chung".into(),
        last_modified: "2026-01-25".into(),
        inherits_from: vec!["5W1H_Base_Ontology_OWL".into()],
        compatible_domains: Some(vec!["Knowledge_Assets".into(), "Business_Process".into()]),
        tags: vec!["MaterialManagement".into(), "Inventory".into(), "Procurement".into(), "ERP".into(), "KA".into()],
        use_cases: vec![
            "物料主檔知識管理".into(),
            "庫存與批次追蹤".into(),
            "採購與供應商知識檢索".into(),
            "物料異動審計".into(),
            "RAG 輔助物料決策".into(),
        ],
        entity_classes: vec![
            EntityClass { name: "Material".into(), base_class: "Concept".into(), description: "物料主體，包含原料、半成品、成品、備品、耗材等。".into() },
            EntityClass { name: "Material_Master_Data".into(), base_class: "Document".into(), description: "物料主檔資料，定義料號、規格、單位、分類、有效狀態等。".into() },
            EntityClass { name: "Inventory_Record".into(), base_class: "Concept".into(), description: "庫存紀錄，描述物料在特定時間與地點的數量與狀態。".into() },
            EntityClass { name: "Batch_Lot".into(), base_class: "Concept".into(), description: "批次或批號，用於追蹤物料來源、效期與品質。".into() },
            EntityClass { name: "Warehouse_Location".into(), base_class: "Concept".into(), description: "倉庫或庫位位置，用於物料存放與盤點。".into() },
            EntityClass { name: "Supplier".into(), base_class: "Agent".into(), description: "供應商實體，提供物料或相關服務。".into() },
            EntityClass { name: "Purchase_Record".into(), base_class: "Document".into(), description: "採購紀錄，包含採購單、到貨紀錄與驗收資訊。".into() },
            EntityClass { name: "Material_Movement".into(), base_class: "Event".into(), description: "物料異動事件，如入庫、出庫、調撥、報廢。".into() },
            EntityClass { name: "Material_Classification".into(), base_class: "Concept".into(), description: "物料分類體系，如原料類、製程類、備品類等。".into() },
            EntityClass { name: "Material_Metadata".into(), base_class: "Metadata".into(), description: "物料知識的元數據，包含 Domain、Major、料號、批次、版本、來源等。".into() },
            EntityClass { name: "Material_KNW_Code".into(), base_class: "Concept".into(), description: "物料知識專用 KNW-Code，用於唯一識別物料相關知識資產。".into() },
            EntityClass { name: "Material_Security_Policy".into(), base_class: "Concept".into(), description: "物料知識存取的安全與權限策略。".into() },
            EntityClass { name: "Material_Audit_Log".into(), base_class: "Document".into(), description: "物料相關操作與異動的審計日誌。".into() },
        ],
        object_properties: vec![
            ObjectProperty { name: "has_master_data".into(), description: "物料對應的主檔資料。".into(), domain: vec!["Material".into()], range: vec!["Material_Master_Data".into()] },
            ObjectProperty { name: "classified_as".into(), description: "物料所屬的分類。".into(), domain: vec!["Material".into()], range: vec!["Material_Classification".into()] },
            ObjectProperty { name: "stored_at".into(), description: "物料存放的位置。".into(), domain: vec!["Inventory_Record".into()], range: vec!["Warehouse_Location".into()] },
            ObjectProperty { name: "tracked_by_batch".into(), description: "物料以批次方式追蹤。".into(), domain: vec!["Material".into(), "Inventory_Record".into()], range: vec!["Batch_Lot".into()] },
            ObjectProperty { name: "supplied_by".into(), description: "物料的供應商。".into(), domain: vec!["Material".into(), "Purchase_Record".into()], range: vec!["Supplier".into()] },
            ObjectProperty { name: "records_inventory".into(), description: "庫存紀錄對應的物料。".into(), domain: vec!["Inventory_Record".into()], range: vec!["Material".into()] },
            ObjectProperty { name: "records_movement".into(), description: "記錄物料異動事件。".into(), domain: vec!["Material_Movement".into()], range: vec!["Material".into()] },
            ObjectProperty { name: "generates_metadata".into(), description: "為物料知識生成 Metadata。".into(), domain: vec!["Material".into(), "Material_Master_Data".into()], range: vec!["Material_Metadata".into()] },
            ObjectProperty { name: "identified_by_knw_code".into(), description: "物料知識的唯一識別碼。".into(), domain: vec!["Material".into(), "Material_Metadata".into()], range: vec!["Material_KNW_Code".into()] },
            ObjectProperty { name: "applies_security_policy".into(), description: "套用物料知識的安全策略。".into(), domain: vec!["Material".into(), "Material_Master_Data".into()], range: vec!["Material_Security_Policy".into()] },
            ObjectProperty { name: "records_audit".into(), description: "記錄物料相關操作的審計日誌。".into(), domain: vec!["Material".into(), "Material_Movement".into()], range: vec!["Material_Audit_Log".into()] },
        ],
        metadata: OntologyMetadata {
            domain_owner: Some("KA-Agent".into()),
            domain: None,
            major_owner: None,
            data_classification: Some("INTERNAL".into()),
            intended_usage: None,
        },
        status: Some("enabled".into()),
    };

    // --- Major (Material_Inventory_Control) ---
    let major = Ontology {
        _key: Some("major_inventory_ctrl".into()),
        ontology_type: "major".into(),
        name: "Material_Inventory_Control".into(),
        version: "1.0".into(),
        default_version: true,
        ontology_name: "Material_Inventory_Control_Major_Ontology".into(),
        description: "物料庫存與控管專業本體論，定義庫存狀態、異動規則、盤點、批次、效期與安全庫存等專業概念。適用於庫存分析、異動追蹤、RAG 查詢與決策推斷。".into(),
        author: "Daniel Chung".into(),
        last_modified: "2026-01-25".into(),
        inherits_from: vec![
            "5W1H_Base_Ontology_OWL".into(),
            "Material_Management_Domain_Ontology".into(),
        ],
        compatible_domains: None,
        tags: vec!["Inventory".into(), "MaterialControl".into(), "Stock".into(), "KA".into()],
        use_cases: vec![
            "庫存狀態查詢".into(),
            "安全庫存與補貨判斷".into(),
            "物料異動原因分析".into(),
            "批次與效期追蹤".into(),
            "盤點差異分析".into(),
        ],
        entity_classes: vec![
            EntityClass { name: "Stock_Level".into(), base_class: "Concept".into(), description: "庫存水位，描述物料在特定時間點的數量狀態。".into() },
            EntityClass { name: "Stock_Status".into(), base_class: "Concept".into(), description: "庫存狀態，如可用、保留、凍結、報廢。".into() },
            EntityClass { name: "Safety_Stock".into(), base_class: "Concept".into(), description: "安全庫存量，用於避免供應中斷。".into() },
            EntityClass { name: "Reorder_Point".into(), base_class: "Concept".into(), description: "再訂購點，當庫存低於此值時需觸發補貨。".into() },
            EntityClass { name: "Stock_Movement_Type".into(), base_class: "Concept".into(), description: "庫存異動類型，如入庫、出庫、調撥、盤點調整。".into() },
            EntityClass { name: "Stock_Movement_Reason".into(), base_class: "Concept".into(), description: "庫存異動原因，如生產領料、銷售出貨、報廢。".into() },
            EntityClass { name: "Inventory_Check".into(), base_class: "Event".into(), description: "盤點事件，用於核對實體庫存與系統紀錄。".into() },
            EntityClass { name: "Inventory_Discrepancy".into(), base_class: "Concept".into(), description: "盤點差異，描述實際庫存與帳面庫存的落差。".into() },
            EntityClass { name: "Expiration_Date".into(), base_class: "Concept".into(), description: "效期，用於管理有保存期限的物料。".into() },
            EntityClass { name: "Batch_Trace_Record".into(), base_class: "Document".into(), description: "批次追蹤紀錄，串聯來源、庫存與去向。".into() },
        ],
        object_properties: vec![
            ObjectProperty { name: "has_stock_level".into(), description: "物料目前的庫存水位。".into(), domain: vec!["Material".into()], range: vec!["Stock_Level".into()] },
            ObjectProperty { name: "has_stock_status".into(), description: "物料目前的庫存狀態。".into(), domain: vec!["Inventory_Record".into()], range: vec!["Stock_Status".into()] },
            ObjectProperty { name: "defined_by_safety_stock".into(), description: "物料所設定的安全庫存。".into(), domain: vec!["Material".into()], range: vec!["Safety_Stock".into()] },
            ObjectProperty { name: "triggers_reorder_point".into(), description: "庫存低於再訂購點。".into(), domain: vec!["Stock_Level".into()], range: vec!["Reorder_Point".into()] },
            ObjectProperty { name: "has_movement_type".into(), description: "庫存異動的類型。".into(), domain: vec!["Material_Movement".into()], range: vec!["Stock_Movement_Type".into()] },
            ObjectProperty { name: "has_movement_reason".into(), description: "庫存異動的原因。".into(), domain: vec!["Material_Movement".into()], range: vec!["Stock_Movement_Reason".into()] },
            ObjectProperty { name: "results_in_discrepancy".into(), description: "盤點導致的差異。".into(), domain: vec!["Inventory_Check".into()], range: vec!["Inventory_Discrepancy".into()] },
            ObjectProperty { name: "tracked_with_expiration".into(), description: "物料受效期管理。".into(), domain: vec!["Material".into(), "Batch_Lot".into()], range: vec!["Expiration_Date".into()] },
            ObjectProperty { name: "has_batch_trace".into(), description: "批次追蹤紀錄。".into(), domain: vec!["Batch_Lot".into()], range: vec!["Batch_Trace_Record".into()] },
        ],
        metadata: OntologyMetadata {
            domain_owner: None,
            domain: Some("Material_Management".into()),
            major_owner: Some("KA-Agent".into()),
            data_classification: Some("INTERNAL".into()),
            intended_usage: Some(vec![
                "RAG 檢索重排序".into(),
                "KG 三元組抽取".into(),
                "庫存推斷與決策輔助".into(),
            ]),
        },
        status: Some("enabled".into()),
    };

    for ont in &[basic, domain, major] {
        col.create_document(ont.clone(), Default::default())
            .await
            .map_err(|e| format!("Seed ontology '{}' failed: {e}", ont.name))?;
    }

    Ok(())
}
