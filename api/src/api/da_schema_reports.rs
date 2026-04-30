//! Data Agent Schema Reports API Routes
//!
//! # Description
//! Schema 智慧報表 CRUD endpoints，操作 ArangoDB schema_reports 集合。
//! 報告產生後寫入此集合，SchemaReportModal 從此集合讀取報告列表。
//!
//! # Last Update: 2026-04-30 11:30:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use crate::db::get_db;
use crate::models::ApiResponse;
use axum::{
    extract::{Path, Query},
    http::StatusCode,
    response::IntoResponse,
    routing::{delete, get, post},
    Json, Router,
};
use serde_json::Value;
use std::collections::HashMap;

const COLLECTION: &str = "schema_reports";

pub fn create_schema_reports_router() -> Router {
    Router::new()
        .route("/api/v1/da/schema-reports", get(list_reports).post(create_report))
        .route("/api/v1/da/schema-reports/{key}", delete(delete_report))
}

// ---------------------------------------------------------------------------
// LIST reports by table_id
// ---------------------------------------------------------------------------

async fn list_reports(
    Query(params): Query<HashMap<String, String>>,
) -> Result<impl IntoResponse, StatusCode> {
    let table_id = params
        .get("table_id")
        .and_then(|v: &String| {
            let s = v.trim();
            if s.is_empty() { None } else { Some(s) }
        })
        .ok_or(StatusCode::BAD_REQUEST)?;

    let db = get_db();

    let query = "FOR r IN schema_reports \
                 FILTER r.table_id == @table_id \
                 SORT r.created_at DESC \
                 LIMIT 50 \
                 RETURN r";

    let reports: Vec<Value> = db
        .aql_bind_vars(query, [("table_id", serde_json::json!(table_id))].into())
        .await
        .map_err(|e| {
            eprintln!("schema_reports list error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(serde_json::json!({
        "code": 0,
        "data": reports
    })))
}

// ---------------------------------------------------------------------------
// CREATE a new report record
// ---------------------------------------------------------------------------

async fn create_report(Json(payload): Json<Value>) -> Result<impl IntoResponse, StatusCode> {
    // Validate required fields
    let _ = payload
        .get("table_id")
        .and_then(|v| v.as_str())
        .filter(|v| !v.trim().is_empty())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let _ = payload
        .get("report_name")
        .and_then(|v| v.as_str())
        .filter(|v| !v.trim().is_empty())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let _ = payload
        .get("report_url")
        .and_then(|v| v.as_str())
        .filter(|v| !v.trim().is_empty())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let db = get_db();

    let mut doc = payload;
    if let Some(obj) = doc.as_object_mut() {
        // Auto-generate _key if not provided
        if !obj.contains_key("_key") {
            let key = format!(
                "rpt_{}_{}",
                obj.get("table_id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("unknown"),
                chrono::Utc::now().timestamp()
            );
            obj.insert("_key".into(), serde_json::json!(key));
        }
        obj.insert(
            "created_at".into(),
            serde_json::json!(chrono::Utc::now().to_rfc3339()),
        );
    }

    let col = db
        .collection(COLLECTION)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    col.create_document(doc.clone(), Default::default())
        .await
        .map_err(|e| {
            eprintln!("schema_reports create error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // Return created document
    let key = doc
        .get("_key")
        .and_then(|v| v.as_str())
        .unwrap_or("");

    let mut created: Vec<Value> = db
        .aql_bind_vars(
            "FOR r IN schema_reports FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let report = created.pop().ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(report)))
}

// ---------------------------------------------------------------------------
// DELETE a report by _key
// ---------------------------------------------------------------------------

async fn delete_report(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db
        .collection(COLLECTION)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    col.remove_document::<Value>(&key, Default::default(), None)
        .await
        .map_err(|e| {
            eprintln!("schema_reports delete error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(ApiResponse::success(serde_json::json!({ "_key": key }))))
}
