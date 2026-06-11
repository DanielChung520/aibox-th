//! Orchestrator Intents Catalog API Routes
//!
//! # Description
//! Orchestrator 意圖決策管理 CRUD endpoints
//! 操作 ArangoDB orch_intents 集合
//! sync-qdrant 路由為 placeholder，Phase 2 再接 Python 服務
//!
//! # Last Update: 2026-03-28 11:24:37
//! # Author: Daniel Chung
//! # Version: 1.0.0

use crate::db::get_db;
use crate::models::ApiResponse;
use axum::{
    extract::{Path, Query},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post, put},
    Json, Router,
};
use serde_json::Value;
use std::collections::HashMap;

pub fn create_orch_intents_router() -> Router {
    Router::new()
        .route(
            "/api/v1/orch/intents/catalog",
            get(list_catalog).post(create_intent),
        )
        .route(
            "/api/v1/orch/intents/catalog/{intent_id}",
            put(update_intent).delete(delete_intent),
        )
        .route(
            "/api/v1/orch/intents/sync-qdrant",
            post(sync_qdrant_placeholder),
        )
}

async fn list_catalog(
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

    if let Some(intent_type) = params.get("intent_type").filter(|v| !v.trim().is_empty()) {
        filters.push("d.intent_type == @intent_type".to_string());
        bind_entries.push(("intent_type".to_string(), serde_json::json!(intent_type)));
    }

    if let Some(status) = params.get("status").filter(|v| !v.trim().is_empty()) {
        filters.push("d.status == @status".to_string());
        bind_entries.push(("status".to_string(), serde_json::json!(status)));
    }

    if let Some(tool_name) = params.get("tool_name").filter(|v| !v.trim().is_empty()) {
        filters.push("d.tool_name == @tool_name".to_string());
        bind_entries.push(("tool_name".to_string(), serde_json::json!(tool_name)));
    }

    if let Some(search) = params.get("search").filter(|v| !v.trim().is_empty()) {
        filters.push(
            "(LIKE(d.description, CONCAT('%', @search, '%'), true) || LIKE(d.intent_id, CONCAT('%', @search, '%'), true) || LIKE(d.name, CONCAT('%', @search, '%'), true))"
                .to_string(),
        );
        bind_entries.push(("search".to_string(), serde_json::json!(search)));
    }

    let filter_clause = if filters.is_empty() {
        String::new()
    } else {
        format!(" FILTER {}", filters.join(" && "))
    };

    let db = get_db();

    let count_query = format!(
        "FOR d IN orch_intents{} COLLECT WITH COUNT INTO length RETURN length",
        filter_clause
    );
    let count_bind: HashMap<&str, Value> = bind_entries
        .iter()
        .map(|(k, v)| (k.as_str(), v.clone()))
        .collect();
    let total_result: Vec<u64> = db
        .aql_bind_vars(&count_query, count_bind)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let total_count = total_result.into_iter().next().unwrap_or(0);

    bind_entries.push(("offset".to_string(), serde_json::json!(offset)));
    bind_entries.push(("page_size".to_string(), serde_json::json!(page_size)));

    let records_query = format!(
        "FOR d IN orch_intents{} SORT d.priority DESC, d.intent_id ASC LIMIT @offset, @page_size RETURN d",
        filter_clause
    );
    let records_bind: HashMap<&str, Value> = bind_entries
        .iter()
        .map(|(k, v)| (k.as_str(), v.clone()))
        .collect();
    let records: Vec<Value> = db
        .aql_bind_vars(&records_query, records_bind)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

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

async fn create_intent(Json(payload): Json<Value>) -> Result<impl IntoResponse, StatusCode> {
    let intent_id = payload
        .get("intent_id")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let db = get_db();

    let existing: Vec<Value> = db
        .aql_bind_vars(
            "FOR d IN orch_intents FILTER d.intent_id == @intent_id LIMIT 1 RETURN d._key",
            [("intent_id", serde_json::json!(intent_id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    if !existing.is_empty() {
        return Err(StatusCode::CONFLICT);
    }

    let mut doc = payload;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "created_at".to_string(),
            serde_json::json!(chrono::Utc::now().to_rfc3339()),
        );
        if !obj.contains_key("status") {
            obj.insert("status".to_string(), serde_json::json!("enabled"));
        }
        if !obj.contains_key("priority") {
            obj.insert("priority".to_string(), serde_json::json!(0));
        }
        if !obj.contains_key("confidence_threshold") {
            obj.insert("confidence_threshold".to_string(), serde_json::json!(0.75));
        }
    }

    let col = db
        .collection("orch_intents")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(doc, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut created: Vec<Value> = db
        .aql_bind_vars(
            "FOR d IN orch_intents FILTER d.intent_id == @intent_id LIMIT 1 RETURN d",
            [("intent_id", serde_json::json!(intent_id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let intent = created.pop().ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(intent)))
}

async fn update_intent(
    Path(intent_id): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let keys: Vec<String> = db
        .aql_bind_vars(
            "FOR d IN orch_intents FILTER d.intent_id == @intent_id LIMIT 1 RETURN d._key",
            [("intent_id", serde_json::json!(intent_id.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc_key = keys.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let mut update_data = payload;
    if let Some(obj) = update_data.as_object_mut() {
        obj.insert(
            "updated_at".to_string(),
            serde_json::json!(chrono::Utc::now().to_rfc3339()),
        );
        obj.remove("_key");
        obj.remove("_id");
    }

    let col = db
        .collection("orch_intents")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(&doc_key, update_data, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut updated: Vec<Value> = db
        .aql_bind_vars(
            "FOR d IN orch_intents FILTER d._key == @key LIMIT 1 RETURN d",
            [("key", serde_json::json!(doc_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let intent = updated.pop().ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(ApiResponse::success(intent)))
}

async fn delete_intent(Path(intent_id): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let keys: Vec<String> = db
        .aql_bind_vars(
            "FOR d IN orch_intents FILTER d.intent_id == @intent_id LIMIT 1 RETURN d._key",
            [("intent_id", serde_json::json!(intent_id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc_key = keys.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let col = db
        .collection("orch_intents")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<Value>(&doc_key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success("Intent deleted".to_string())))
}

async fn sync_qdrant_placeholder(
    Json(_payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    Ok(Json(serde_json::json!({
        "code": 0,
        "message": "Qdrant sync not yet implemented (Phase 2)",
        "data": {
            "synced_count": 0,
            "status": "placeholder"
        }
    })))
}
