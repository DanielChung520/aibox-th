//! Data Agent Intents Catalog API Routes
//!
//! # Description
//! DA 的 Intents Catalog CRUD endpoints + proxy to unified_agents
//! Catalog 路由直接操作 ArangoDB da_intents 集合
//! sync-qdrant / models 路由代理轉發到 unified_agents /da/intent-rag/*
//!
//! # Last Update: 2026-03-24 13:16:23
//! # Author: Daniel Chung
//! # Version: 2.1.0

use crate::config::CONFIG;
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

pub fn create_da_intents_router() -> Router {
    Router::new()
        // Catalog CRUD
        .route(
            "/api/v1/da/intents/catalog",
            get(list_catalog).post(create_intent),
        )
        .route(
            "/api/v1/da/intents/catalog/{intent_id}",
            put(update_intent).delete(delete_intent),
        )
        // Feedback (append nl_examples)
        .route(
            "/api/v1/da/intents/catalog/{intent_id}/feedback",
            post(feedback_intent),
        )
        // Proxy to unified_agents
        .route(
            "/api/v1/da/intents/sync-qdrant",
            post(proxy_sync_qdrant),
        )
        .route(
            "/api/v1/da/intents/models",
            get(proxy_list_models),
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

    if let Some(group) = params.get("group").filter(|v| !v.trim().is_empty()) {
        filters.push("d.group == @group".to_string());
        bind_entries.push(("group".to_string(), serde_json::json!(group)));
    }

    if let Some(strategy) = params.get("generation_strategy").filter(|v| !v.trim().is_empty()) {
        filters.push("d.generation_strategy == @generation_strategy".to_string());
        bind_entries.push(("generation_strategy".to_string(), serde_json::json!(strategy)));
    }

    if let Some(table_key) = params.get("table_key").filter(|v| !v.trim().is_empty()) {
        filters.push("d.table_key == @table_key".to_string());
        bind_entries.push(("table_key".to_string(), serde_json::json!(table_key)));
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

    // Count query
    let count_query = format!(
        "FOR d IN da_intents{} COLLECT WITH COUNT INTO length RETURN length",
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

    // Records query with pagination
    bind_entries.push(("offset".to_string(), serde_json::json!(offset)));
    bind_entries.push(("page_size".to_string(), serde_json::json!(page_size)));

    let records_query = format!(
        "FOR d IN da_intents{} SORT d.group ASC, d.intent_id ASC LIMIT @offset, @page_size RETURN d",
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

    // Check for duplicates
    let existing: Vec<Value> = db
        .aql_bind_vars(
            "FOR d IN da_intents FILTER d.intent_id == @intent_id LIMIT 1 RETURN d._key",
            [("intent_id", serde_json::json!(intent_id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    if !existing.is_empty() {
        return Err(StatusCode::CONFLICT);
    }

    let mut doc = payload;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert("is_template".to_string(), serde_json::json!(true));
        obj.insert(
            "created_at".to_string(),
            serde_json::json!(chrono::Utc::now().to_rfc3339()),
        );
    }

    let col = db
        .collection("da_intents")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(doc, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut created: Vec<Value> = db
        .aql_bind_vars(
            "FOR d IN da_intents FILTER d.intent_id == @intent_id LIMIT 1 RETURN d",
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
            "FOR d IN da_intents FILTER d.intent_id == @intent_id LIMIT 1 RETURN d._key",
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
        // Prevent changing intent_id
        obj.remove("_key");
        obj.remove("_id");
    }

    let col = db
        .collection("da_intents")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(&doc_key, update_data, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut updated: Vec<Value> = db
        .aql_bind_vars(
            "FOR d IN da_intents FILTER d._key == @key LIMIT 1 RETURN d",
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
            "FOR d IN da_intents FILTER d.intent_id == @intent_id LIMIT 1 RETURN d._key",
            [("intent_id", serde_json::json!(intent_id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc_key = keys.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let col = db
        .collection("da_intents")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<Value>(&doc_key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success("Intent deleted".to_string())))
}

async fn feedback_intent(
    Path(intent_id): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let action = payload
        .get("action")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let nl_query = payload
        .get("nl_query")
        .and_then(|v| v.as_str())
        .unwrap_or("");

    if action != "thumbs_up" || nl_query.is_empty() {
        return Ok(Json(serde_json::json!({
            "code": 0,
            "data": { "action": action, "intent_id": intent_id, "applied": false }
        })));
    }

    let db = get_db();
    let keys: Vec<String> = db
        .aql_bind_vars(
            "FOR d IN da_intents FILTER d.intent_id == @intent_id LIMIT 1 RETURN d._key",
            [("intent_id", serde_json::json!(intent_id.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc_key = keys.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let update_doc = serde_json::json!({
        "updated_at": chrono::Utc::now().to_rfc3339(),
    });
    let col = db
        .collection("da_intents")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(&doc_key, update_doc, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    db.aql_bind_vars::<Value>(
        "FOR d IN da_intents FILTER d._key == @key UPDATE d WITH { nl_examples: APPEND(d.nl_examples, @nl) } IN da_intents",
        [
            ("key", serde_json::json!(doc_key)),
            ("nl", serde_json::json!(nl_query)),
        ]
        .into(),
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(serde_json::json!({
        "code": 0,
        "data": { "action": "thumbs_up", "intent_id": intent_id, "applied": true, "nl_added": nl_query }
    })))
}

/// Proxy POST /api/v1/da/intents/sync-qdrant → unified_agents/da/intent-rag/embed-sync
async fn proxy_sync_qdrant(Json(payload): Json<Value>) -> Result<impl IntoResponse, StatusCode> {
    let url = format!("{}/da/intent-rag/data_agent/embed-sync", CONFIG.ai_services.unified_agents_url);

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let resp = client
        .post(&url)
        .json(&payload)
        .send()
        .await
        .map_err(|e| {
            eprintln!("proxy_sync_qdrant error: {e}");
            StatusCode::BAD_GATEWAY
        })?;

    let status = resp.status();
    let body: Value = resp.json().await.map_err(|_| StatusCode::BAD_GATEWAY)?;

    if status.is_success() {
        Ok(Json(body))
    } else {
        Err(StatusCode::BAD_GATEWAY)
    }
}

/// Proxy GET /api/v1/da/intents/models → unified_agents/da/intent-rag/models
async fn proxy_list_models() -> Result<impl IntoResponse, StatusCode> {
    let url = format!("{}/da/intent-rag/models", CONFIG.ai_services.unified_agents_url);

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let resp = client.get(&url).send().await.map_err(|e| {
        eprintln!("proxy_list_models error: {e}");
        StatusCode::BAD_GATEWAY
    })?;

    let body: Value = resp.json().await.map_err(|_| StatusCode::BAD_GATEWAY)?;
    Ok(Json(body))
}
