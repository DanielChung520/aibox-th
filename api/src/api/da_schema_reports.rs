//! Data Agent Schema Reports API Routes
//!
//! # Description
//! Schema 智慧報表 CRUD endpoints，操作 ArangoDB schema_reports 集合。
//! 支援同步/非同步兩種產生模式：
//!   - 同步：report_url 必填，直接寫入完成狀態
//!   - 非同步：report_url 可為空，status="generating"，後續由 Celery worker PATCH 更新
//!
//! # Last Update: 2026-05-01 03:00:00
//! # Author: Daniel Chung / Sisyphus
//! # Version: 1.1.0

use crate::db::get_db;
use crate::models::ApiResponse;
use axum::{
    extract::{Path, Query},
    http::StatusCode,
    response::IntoResponse,
    routing::{delete, get, patch, post},
    Json, Router,
};
use serde_json::Value;
use std::collections::HashMap;

const COLLECTION: &str = "schema_reports";

pub fn create_schema_reports_router() -> Router {
    Router::new()
        .route("/api/v1/da/schema-reports", get(list_reports).post(create_report))
        .route("/api/v1/da/schema-reports/{key}", delete(delete_report).patch(update_report))
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
    let table_id = payload
        .get("table_id")
        .and_then(|v| v.as_str())
        .filter(|v| !v.trim().is_empty())
        .ok_or(StatusCode::BAD_REQUEST)?
        .to_string();

    let _report_name = payload
        .get("report_name")
        .and_then(|v| v.as_str())
        .filter(|v| !v.trim().is_empty())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let db = get_db();

    let mut doc = payload;
    if let Some(obj) = doc.as_object_mut() {
        if !obj.contains_key("_key") {
            let key = format!("rpt_{}_{}", table_id, chrono::Utc::now().timestamp());
            obj.insert("_key".into(), serde_json::json!(key));
        }
        let now = chrono::Utc::now().to_rfc3339();
        obj.entry("created_at").or_insert(serde_json::json!(now));
        obj.entry("updated_at").or_insert(serde_json::json!(now));
        obj.entry("status").or_insert(serde_json::json!("generating"));
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

// ---------------------------------------------------------------------------
// PATCH a report — update status / report_url / error_message（非同步流程用）
// 使用 ArangoDB PATCH 語法，只更新指定欄位，不覆蓋整份文件
// ---------------------------------------------------------------------------

async fn update_report(
    Path(key): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let aql = "FOR r IN schema_reports \
               FILTER r._key == @key \
               UPDATE r WITH @payload IN schema_reports \
               RETURN NEW";

    let mut results: Vec<Value> = db
        .aql_bind_vars(
            aql,
            [
                ("key", serde_json::json!(key)),
                ("payload", serde_json::json!({
                    "status": payload.get("status"),
                    "report_url": payload.get("report_url"),
                    "error_message": payload.get("error_message"),
                    "chart_type": payload.get("chart_type"),
                    "analysis_summary": payload.get("analysis_summary"),
                    "size_bytes": payload.get("size_bytes"),
                    "filename": payload.get("filename"),
                    "updated_at": chrono::Utc::now().to_rfc3339(),
                })),
            ]
            .into(),
        )
        .await
        .map_err(|e| {
            eprintln!("schema_reports update error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let report = results.pop().ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(ApiResponse::success(report)))
}
