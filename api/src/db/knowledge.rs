//! Knowledge Base Module
//!
//! # Last Update: 2026-03-25 11:47:06
//! # Author: Daniel Chung
//! # Version: 1.0.0

use arangors::client::reqwest::ReqwestClient;
use arangors::Database;
use chrono::Utc;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KnowledgeRoot {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub name: String,
    pub description: Option<String>,
    pub ontology_domain: String,
    pub ontology_majors: Vec<String>,
    pub source_count: i32,
    pub vector_status: String,
    pub graph_status: String,
    pub is_favorite: bool,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KnowledgeFile {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub filename: String,
    pub file_size: i64,
    pub file_type: String,
    pub upload_time: String,
    pub vector_status: String,
    pub graph_status: String,
    pub knowledge_root_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub failed_reason: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vector_task_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub graph_task_id: Option<String>,
}

pub async fn seed_knowledge(db: &Database<ReqwestClient>) -> Result<(), String> {
    let count: serde_json::Value = db
        .aql_str("RETURN LENGTH(knowledge_roots)")
        .await
        .map_err(|e| format!("AQL error: {e}"))?
        .into_iter()
        .next()
        .unwrap_or(serde_json::Value::Number(0.into()));

    if count.as_u64().unwrap_or(0) > 0 {
        return Ok(());
    }

    let root_col = db
        .collection("knowledge_roots")
        .await
        .map_err(|e| format!("knowledge_roots collection: {e}"))?;
    let file_col = db
        .collection("knowledge_files")
        .await
        .map_err(|e| format!("knowledge_files collection: {e}"))?;
    let _job_logs_col = db
        .collection("job_logs")
        .await
        .map_err(|_| ());

    let now = Utc::now().to_rfc3339();

    let roots = vec![
        KnowledgeRoot {
            _key: Some("kb1".into()),
            name: "MM-Agent 知識庫".into(),
            description: Some("物料管理規範與流程文件集".into()),
            ontology_domain: "Material_Management".into(),
            ontology_majors: vec!["Inventory_Control".into(), "Quality_Management".into()],
            source_count: 3,
            vector_status: "completed".into(),
            graph_status: "completed".into(),
            is_favorite: true,
            created_at: "2026-03-01T10:00:00Z".into(),
            updated_at: now.clone(),
        },
        KnowledgeRoot {
            _key: Some("kb2".into()),
            name: "KA-Agent 知識庫".into(),
            description: Some("核心知識對齊與語義標準化".into()),
            ontology_domain: "Knowledge_Alignment".into(),
            ontology_majors: vec!["Semantic_Mapping".into()],
            source_count: 4,
            vector_status: "processing".into(),
            graph_status: "pending".into(),
            is_favorite: false,
            created_at: "2026-03-10T14:30:00Z".into(),
            updated_at: now.clone(),
        },
        KnowledgeRoot {
            _key: Some("kb3".into()),
            name: "財務規範 2026".into(),
            description: Some("預算編列準則與財務流程".into()),
            ontology_domain: "Financial_Standards".into(),
            ontology_majors: vec!["Budget_Control".into()],
            source_count: 2,
            vector_status: "completed".into(),
            graph_status: "completed".into(),
            is_favorite: false,
            created_at: "2026-02-15T09:00:00Z".into(),
            updated_at: now.clone(),
        },
        KnowledgeRoot {
            _key: Some("kb4".into()),
            name: "醫療知識庫".into(),
            description: Some("臨床數據與醫療照護知識".into()),
            ontology_domain: "Medical_Healthcare".into(),
            ontology_majors: vec!["Clinical_Data_Management".into()],
            source_count: 3,
            vector_status: "failed".into(),
            graph_status: "pending".into(),
            is_favorite: true,
            created_at: "2026-03-20T16:45:00Z".into(),
            updated_at: now.clone(),
        },
    ];

    for root in &roots {
        root_col
            .create_document(root.clone(), Default::default())
            .await
            .map_err(|e| format!("Seed knowledge root '{}' failed: {e}", root.name))?;
    }

    let files = vec![
        // kb1 files
        KnowledgeFile { failed_reason: None, vector_task_id: None, graph_task_id: None,
            _key: Some("kf_mm_001".into()),
            filename: "物料管理作業規範_v3.2.pdf".into(),
            file_size: 2_457_600,
            file_type: "pdf".into(),
            upload_time: "2026-03-01T10:05:00Z".into(),
            vector_status: "completed".into(),
            graph_status: "completed".into(),
            knowledge_root_id: "kb1".into(),
        },
        KnowledgeFile { failed_reason: None, vector_task_id: None, graph_task_id: None,
            _key: Some("kf_mm_002".into()),
            filename: "庫存盤點流程.docx".into(),
            file_size: 845_000,
            file_type: "docx".into(),
            upload_time: "2026-03-02T09:30:00Z".into(),
            vector_status: "completed".into(),
            graph_status: "completed".into(),
            knowledge_root_id: "kb1".into(),
        },
        KnowledgeFile { failed_reason: None, vector_task_id: None, graph_task_id: None,
            _key: Some("kf_mm_003".into()),
            filename: "品質管理手冊_2026.pdf".into(),
            file_size: 3_200_000,
            file_type: "pdf".into(),
            upload_time: "2026-03-03T14:00:00Z".into(),
            vector_status: "completed".into(),
            graph_status: "completed".into(),
            knowledge_root_id: "kb1".into(),
        },
        // kb2 files
        KnowledgeFile { failed_reason: None, vector_task_id: None, graph_task_id: None,
            _key: Some("kf_ka_001".into()),
            filename: "語義對齊規範說明.pdf".into(),
            file_size: 1_120_000,
            file_type: "pdf".into(),
            upload_time: "2026-03-10T15:00:00Z".into(),
            vector_status: "completed".into(),
            graph_status: "pending".into(),
            knowledge_root_id: "kb2".into(),
        },
        KnowledgeFile { failed_reason: None, vector_task_id: None, graph_task_id: None,
            _key: Some("kf_ka_002".into()),
            filename: "知識分類體系_v2.xlsx".into(),
            file_size: 567_000,
            file_type: "xlsx".into(),
            upload_time: "2026-03-11T10:00:00Z".into(),
            vector_status: "processing".into(),
            graph_status: "pending".into(),
            knowledge_root_id: "kb2".into(),
        },
        KnowledgeFile { failed_reason: None, vector_task_id: None, graph_task_id: None,
            _key: Some("kf_ka_003".into()),
            filename: "Ontology_Mapping_Guide.md".into(),
            file_size: 234_000,
            file_type: "md".into(),
            upload_time: "2026-03-12T08:30:00Z".into(),
            vector_status: "processing".into(),
            graph_status: "pending".into(),
            knowledge_root_id: "kb2".into(),
        },
        KnowledgeFile { failed_reason: None, vector_task_id: None, graph_task_id: None,
            _key: Some("kf_ka_004".into()),
            filename: "實體關係定義表.csv".into(),
            file_size: 89_000,
            file_type: "csv".into(),
            upload_time: "2026-03-13T11:20:00Z".into(),
            vector_status: "pending".into(),
            graph_status: "pending".into(),
            knowledge_root_id: "kb2".into(),
        },
        // kb3 files
        KnowledgeFile { failed_reason: None, vector_task_id: None, graph_task_id: None,
            _key: Some("kf_fin_001".into()),
            filename: "2026年度預算編列準則.pdf".into(),
            file_size: 1_890_000,
            file_type: "pdf".into(),
            upload_time: "2026-02-15T09:15:00Z".into(),
            vector_status: "completed".into(),
            graph_status: "completed".into(),
            knowledge_root_id: "kb3".into(),
        },
        KnowledgeFile { failed_reason: None, vector_task_id: None, graph_task_id: None,
            _key: Some("kf_fin_002".into()),
            filename: "財務審核流程圖.pdf".into(),
            file_size: 456_000,
            file_type: "pdf".into(),
            upload_time: "2026-02-16T14:00:00Z".into(),
            vector_status: "completed".into(),
            graph_status: "completed".into(),
            knowledge_root_id: "kb3".into(),
        },
        // kb4 files
        KnowledgeFile { failed_reason: None, vector_task_id: None, graph_task_id: None,
            _key: Some("kf_med_001".into()),
            filename: "臨床數據管理標準作業程序.pdf".into(),
            file_size: 4_500_000,
            file_type: "pdf".into(),
            upload_time: "2026-03-20T17:00:00Z".into(),
            vector_status: "failed".into(),
            graph_status: "pending".into(),
            knowledge_root_id: "kb4".into(),
        },
        KnowledgeFile { failed_reason: None, vector_task_id: None, graph_task_id: None,
            _key: Some("kf_med_002".into()),
            filename: "病患資料隱私規範.docx".into(),
            file_size: 678_000,
            file_type: "docx".into(),
            upload_time: "2026-03-21T09:00:00Z".into(),
            vector_status: "pending".into(),
            graph_status: "pending".into(),
            knowledge_root_id: "kb4".into(),
        },
        KnowledgeFile { failed_reason: None, vector_task_id: None, graph_task_id: None,
            _key: Some("kf_med_003".into()),
            filename: "醫療照護知識圖譜設計.pptx".into(),
            file_size: 2_100_000,
            file_type: "pptx".into(),
            upload_time: "2026-03-21T15:30:00Z".into(),
            vector_status: "pending".into(),
            graph_status: "pending".into(),
            knowledge_root_id: "kb4".into(),
        },
    ];

    for file in &files {
        file_col
            .create_document(file.clone(), Default::default())
            .await
            .map_err(|e| format!("Seed knowledge file '{}' failed: {e}", file.filename))?;
    }

    Ok(())
}
