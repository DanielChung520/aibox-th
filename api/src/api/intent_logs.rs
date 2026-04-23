//! Intent Logs API Routes
//!
//! # Description
//! 意圖日誌 CRUD endpoints，記錄使用者與意圖猜測的互動。
//!
//! # Last Update: 2026-04-16 20:34:33
//! # Author: Daniel Chung
//! # Version: 1.0.0

use crate::db::get_db;
use crate::models::ApiResponse;
use axum::{
    extract::Query,
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use serde_json::Value;
use std::collections::HashMap;

const COLLECTION: &str = "intent_logs";

pub fn create_intent_logs_router() -> Router {
    Router::new()
        .route("/api/v1/intent-logs", post(create_log).get(list_logs))
        .route("/api/v1/intent-logs/stats", get(get_stats))
}

async fn create_log(Json(payload): Json<Value>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let mut doc = payload;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "created_at".into(),
            serde_json::json!(chrono::Utc::now().to_rfc3339()),
        );
        if !obj.contains_key("_key") {
            obj.insert(
                "_key".into(),
                serde_json::json!(uuid::Uuid::new_v4().to_string()),
            );
        }
    }

    let col = db
        .collection(COLLECTION)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(doc, Default::default())
        .await
        .map_err(|e| {
            eprintln!("intent_logs create error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(ApiResponse::success("logged")))
}

async fn list_logs(
    Query(params): Query<HashMap<String, String>>,
) -> Result<impl IntoResponse, StatusCode> {
    let page = params
        .get("page")
        .and_then(|v| v.parse::<usize>().ok())
        .filter(|v| *v > 0)
        .unwrap_or(1);
    let page_size = params
        .get("page_size")
        .and_then(|v| v.parse::<usize>().ok())
        .filter(|v| *v > 0)
        .unwrap_or(20);
    let offset = (page - 1) * page_size;

    let mut filters: Vec<String> = Vec::new();
    let mut bind_entries: Vec<(String, Value)> = Vec::new();

    if let Some(intent_id) = params.get("intent_id").filter(|v| !v.trim().is_empty()) {
        filters.push("d.intent_id == @intent_id".into());
        bind_entries.push(("intent_id".into(), serde_json::json!(intent_id)));
    }
    if let Some(user_id) = params.get("user_id").filter(|v| !v.trim().is_empty()) {
        filters.push("d.user_id == @user_id".into());
        bind_entries.push(("user_id".into(), serde_json::json!(user_id)));
    }
    if let Some(action) = params.get("action").filter(|v| !v.trim().is_empty()) {
        filters.push("d.action == @action".into());
        bind_entries.push(("action".into(), serde_json::json!(action)));
    }
    if let Some(page_type) = params.get("page_type").filter(|v| !v.trim().is_empty()) {
        filters.push("d.page_type == @page_type".into());
        bind_entries.push(("page_type".into(), serde_json::json!(page_type)));
    }

    let filter_clause = if filters.is_empty() {
        String::new()
    } else {
        format!(" FILTER {}", filters.join(" && "))
    };

    let db = get_db();

    let count_query = format!(
        "FOR d IN {COLLECTION}{filter_clause} COLLECT WITH COUNT INTO length RETURN length"
    );
    let count_bind: HashMap<&str, Value> = bind_entries
        .iter()
        .map(|(k, v)| (k.as_str(), v.clone()))
        .collect();
    let total_result: Vec<u64> = db
        .aql_bind_vars(&count_query, count_bind)
        .await
        .map_err(|e| {
            eprintln!("intent_logs count error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    let total_count = total_result.into_iter().next().unwrap_or(0);

    bind_entries.push(("offset".into(), serde_json::json!(offset)));
    bind_entries.push(("page_size".into(), serde_json::json!(page_size)));

    let records_query = format!(
        "FOR d IN {COLLECTION}{filter_clause} \
         SORT d.created_at DESC \
         LIMIT @offset, @page_size RETURN d"
    );
    let records_bind: HashMap<&str, Value> = bind_entries
        .iter()
        .map(|(k, v)| (k.as_str(), v.clone()))
        .collect();
    let records: Vec<Value> = db
        .aql_bind_vars(&records_query, records_bind)
        .await
        .map_err(|e| {
            eprintln!("intent_logs records error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(serde_json::json!({
        "code": 0,
        "data": {
            "records": records,
            "total": total_count,
            "page": page,
            "page_size": page_size
        }
    })))
}

async fn get_stats(
    Query(params): Query<HashMap<String, String>>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let mut filters: Vec<String> = Vec::new();
    let mut bind_entries: Vec<(String, Value)> = Vec::new();

    if let Some(intent_id) = params.get("intent_id").filter(|v| !v.trim().is_empty()) {
        filters.push("d.intent_id == @intent_id".into());
        bind_entries.push(("intent_id".into(), serde_json::json!(intent_id)));
    }

    let filter_clause = if filters.is_empty() {
        String::new()
    } else {
        format!(" FILTER {}", filters.join(" && "))
    };

    let query = format!(
        "FOR d IN {COLLECTION}{filter_clause} \
         COLLECT action = d.action WITH COUNT INTO cnt \
         RETURN {{ action, count: cnt }}"
    );
    let bind: HashMap<&str, Value> = bind_entries
        .iter()
        .map(|(k, v)| (k.as_str(), v.clone()))
        .collect();
    let stats: Vec<Value> = db
        .aql_bind_vars(&query, bind)
        .await
        .map_err(|e| {
            eprintln!("intent_logs stats error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(ApiResponse::success(stats)))
}
