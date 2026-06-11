//! Data Agent Schema Report Templates API
//!
//! # Description
//! Schema 智慧報表樣板 CRUD endpoints，操作 ArangoDB schema_report_templates 集合。

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

const COLLECTION: &str = "schema_report_templates";

pub fn create_schema_report_templates_router() -> Router {
    Router::new()
        .route("/api/v1/da/schema-report-templates", get(list_templates).post(create_template))
        .route("/api/v1/da/schema-report-templates/{key}", delete(delete_template))
}

async fn list_templates(
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

    let query = "FOR t IN schema_report_templates \
                 FILTER t.table_id == @table_id \
                 SORT t.created_at DESC \
                 LIMIT 50 \
                 RETURN t";

    let templates: Vec<Value> = db
        .aql_bind_vars(query, [("table_id", serde_json::json!(table_id))].into())
        .await
        .map_err(|e| {
            eprintln!("schema_report_templates list error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(serde_json::json!({
        "code": 0,
        "data": templates
    })))
}

async fn create_template(Json(payload): Json<Value>) -> Result<impl IntoResponse, StatusCode> {
    let table_id = payload
        .get("table_id")
        .and_then(|v| v.as_str())
        .filter(|v| !v.trim().is_empty())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let name = payload
        .get("name")
        .and_then(|v| v.as_str())
        .filter(|v| !v.trim().is_empty())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let db = get_db();

    let key = format!(
        "tpl_{}_{}",
        table_id.replace(['/', '-', '.'], "_"),
        chrono::Utc::now().timestamp()
    );

    let mut doc = serde_json::Map::new();
    doc.insert("_key".into(), serde_json::json!(key));
    doc.insert("table_id".into(), serde_json::json!(table_id));
    doc.insert("name".into(), serde_json::json!(name));

    for field in ["goal", "description", "chart_type", "notes"] {
        if let Some(v) = payload.get(field) {
            doc.insert(field.into(), v.clone());
        }
    }

    doc.insert(
        "created_at".into(),
        serde_json::json!(chrono::Utc::now().to_rfc3339()),
    );

    let col = db
        .collection(COLLECTION)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    col.create_document(Value::Object(doc), Default::default())
        .await
        .map_err(|e| {
            eprintln!("schema_report_templates create error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let created: Vec<Value> = db
        .aql_bind_vars(
            "FOR t IN schema_report_templates FILTER t._key == @key LIMIT 1 RETURN t",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let template = created.into_iter().next().ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(template)))
}

async fn delete_template(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db
        .collection(COLLECTION)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    col.remove_document::<Value>(&key, Default::default(), None)
        .await
        .map_err(|e| {
            eprintln!("schema_report_templates delete error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(ApiResponse::success(serde_json::json!({ "_key": key }))))
}
