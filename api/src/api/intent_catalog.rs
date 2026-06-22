//! Unified Intent Catalog API Routes
//!
//! # Description
//! 統一意圖目錄 CRUD endpoints，操作 ArangoDB intent_catalog 集合。
//! 以 agent_scope 欄位區分不同 Agent 的意圖（orchestrator / data_agent / …）
//! sync-qdrant / models 路由依 scope 代理轉發到對應 Python 服務
//!
//! # Last Update: 2026-04-16 20:34:33
//! # Author: Daniel Chung
//! # Version: 1.3.0

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

const COLLECTION: &str = "intent_catalog";

pub fn create_intent_catalog_router() -> Router {
    Router::new()
        // CRUD
        .route(
            "/api/v1/intents/catalog",
            get(list_catalog).post(create_intent),
        )
        .route(
            "/api/v1/intents/catalog/{intent_id}",
            put(update_intent).delete(delete_intent),
        )
        // Feedback (append nl_examples)
        .route(
            "/api/v1/intents/catalog/{intent_id}/feedback",
            post(feedback_intent),
        )
        // Proxy: scope-aware sync-qdrant
        .route(
            "/api/v1/intents/sync-qdrant",
            post(proxy_sync_qdrant),
        )
        // Proxy: scope-aware list models
        .route(
            "/api/v1/intents/models",
            get(proxy_list_models),
        )
}

// ---------------------------------------------------------------------------
// LIST (paginated, filterable)
// ---------------------------------------------------------------------------

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

    let agent_scope = params.get("agent_scope").filter(|v| !v.trim().is_empty());
    let collection = COLLECTION;

    if let Some(ref scope) = agent_scope {
        filters.push("d.agent_scope == @agent_scope".into());
        bind_entries.push(("agent_scope".into(), serde_json::json!(scope)));
    }

    // ── welfare_secretary / BPA agent filter ──
    let agent_key_name = params.get("agent_key_name").filter(|v| !v.trim().is_empty());
    if let Some(ref akn) = agent_key_name {
        filters.push("d.agent_key_name == @agent_key_name".into());
        bind_entries.push(("agent_key_name".into(), serde_json::json!(akn)));
    }

    // ── common filters ──
    if let Some(status) = params.get("status").filter(|v| !v.trim().is_empty()) {
        filters.push("d.status == @status".into());
        bind_entries.push(("status".into(), serde_json::json!(status)));
    }

    if let Some(intent_type) = params.get("intent_type").filter(|v| !v.trim().is_empty()) {
        filters.push("d.intent_type == @intent_type".into());
        bind_entries.push(("intent_type".into(), serde_json::json!(intent_type)));
    }

    // ── orchestrator-specific filters (BPA routing model) ──
    if let Some(bpa_id) = params.get("bpa_id").filter(|v| !v.trim().is_empty()) {
        filters.push("d.bpa_id == @bpa_id".into());
        bind_entries.push(("bpa_id".into(), serde_json::json!(bpa_id)));
    }

    if let Some(domain) = params.get("domain").filter(|v| !v.trim().is_empty()) {
        filters.push("d.domain == @domain".into());
        bind_entries.push(("domain".into(), serde_json::json!(domain)));
    }

    if let Some(tool_name) = params.get("tool_name").filter(|v| !v.trim().is_empty()) {
        filters.push("d.tool_name == @tool_name".into());
        bind_entries.push(("tool_name".into(), serde_json::json!(tool_name)));
    }

    // ── page_action-specific filters ──
    if let Some(page_type) = params.get("page_type").filter(|v| !v.trim().is_empty()) {
        filters.push("d.page_type == @page_type".into());
        bind_entries.push(("page_type".into(), serde_json::json!(page_type)));
    }

    // ── data_agent-specific filters ──
    if let Some(group) = params.get("group").filter(|v| !v.trim().is_empty()) {
        filters.push("d.group == @group".into());
        bind_entries.push(("group".into(), serde_json::json!(group)));
    }

    if let Some(strategy) = params
        .get("generation_strategy")
        .filter(|v| !v.trim().is_empty())
    {
        filters.push("d.generation_strategy == @generation_strategy".into());
        bind_entries.push((
            "generation_strategy".into(),
            serde_json::json!(strategy),
        ));
    }

    // ── full-text search ──
    if let Some(search) = params.get("search").filter(|v| !v.trim().is_empty()) {
        filters.push(
            "(LIKE(d.description, CONCAT('%', @search, '%'), true) \
             || LIKE(d.intent_id, CONCAT('%', @search, '%'), true) \
             || LIKE(d.name, CONCAT('%', @search, '%'), true))"
                .into(),
        );
        bind_entries.push(("search".into(), serde_json::json!(search)));
    }

    let filter_clause = if filters.is_empty() {
        String::new()
    } else {
        format!(" FILTER {}", filters.join(" && "))
    };

    let db = get_db();

    // ── total count ──
    let count_query = format!(
        "FOR d IN {collection}{filter_clause} COLLECT WITH COUNT INTO length RETURN length"
    );
    let count_bind: HashMap<&str, Value> = bind_entries
        .iter()
        .map(|(k, v)| (k.as_str(), v.clone()))
        .collect();
    let total_result: Vec<u64> = db
        .aql_bind_vars(&count_query, count_bind)
        .await
        .map_err(|e| {
            eprintln!("intent_catalog count error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    let total_count = total_result.into_iter().next().unwrap_or(0);

    // ── paginated records ──
    bind_entries.push(("offset".into(), serde_json::json!(offset)));
    bind_entries.push(("page_size".into(), serde_json::json!(page_size)));

    let records_query = format!(
        "FOR d IN {collection}{filter_clause} \
         SORT d.priority DESC, d.intent_id ASC \
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
            eprintln!("intent_catalog records error: {e}");
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

// ---------------------------------------------------------------------------
// CREATE
// ---------------------------------------------------------------------------

async fn create_intent(Json(payload): Json<Value>) -> Result<impl IntoResponse, StatusCode> {
    let intent_id = payload
        .get("intent_id")
        .and_then(|v| v.as_str())
        .map(String::from)
        .ok_or(StatusCode::BAD_REQUEST)?;

    let agent_scope = payload
        .get("agent_scope")
        .and_then(|v| v.as_str())
        .map(String::from)
        .ok_or(StatusCode::BAD_REQUEST)?;

    let db = get_db();

    // Duplicate check: same intent_id within same scope
    let existing: Vec<Value> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {COLLECTION} \
                 FILTER d.intent_id == @intent_id && d.agent_scope == @agent_scope \
                 LIMIT 1 RETURN d._key"
            ),
            [
                ("intent_id", serde_json::json!(&intent_id)),
                ("agent_scope", serde_json::json!(&agent_scope)),
            ]
            .into(),
        )
        .await
        .map_err(|e| {
            eprintln!("intent_catalog dup check error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    if !existing.is_empty() {
        return Err(StatusCode::CONFLICT);
    }

    let mut doc = payload;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert(
            "created_at".into(),
            serde_json::json!(chrono::Utc::now().to_rfc3339()),
        );
        if !obj.contains_key("status") {
            obj.insert("status".into(), serde_json::json!("enabled"));
        }
        if !obj.contains_key("priority") {
            obj.insert("priority".into(), serde_json::json!(0));
        }
    }

    let col = db
        .collection(COLLECTION)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(doc, Default::default())
        .await
        .map_err(|e| {
            eprintln!("intent_catalog create error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // Return created document
    let mut created: Vec<Value> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {COLLECTION} \
                 FILTER d.intent_id == @intent_id && d.agent_scope == @agent_scope \
                 LIMIT 1 RETURN d"
            ),
            [
                ("intent_id", serde_json::json!(&intent_id)),
                ("agent_scope", serde_json::json!(&agent_scope)),
            ]
            .into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let intent = created.pop().ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(intent)))
}

// ---------------------------------------------------------------------------
// UPDATE
// ---------------------------------------------------------------------------

async fn update_intent(
    Path(intent_id): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let keys: Vec<String> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {COLLECTION} \
                 FILTER d.intent_id == @intent_id \
                 LIMIT 1 RETURN d._key"
            ),
            [("intent_id", serde_json::json!(&intent_id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc_key = keys.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let mut update_data = payload;
    if let Some(obj) = update_data.as_object_mut() {
        obj.insert(
            "updated_at".into(),
            serde_json::json!(chrono::Utc::now().to_rfc3339()),
        );
        // Prevent overwriting immutable fields
        obj.remove("_key");
        obj.remove("_id");
        obj.remove("_rev");
    }

    let col = db
        .collection(COLLECTION)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(&doc_key, update_data, Default::default())
        .await
        .map_err(|e| {
            eprintln!("intent_catalog update error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let mut updated: Vec<Value> = db
        .aql_bind_vars(
            &format!("FOR d IN {COLLECTION} FILTER d._key == @key LIMIT 1 RETURN d"),
            [("key", serde_json::json!(doc_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let intent = updated.pop().ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(ApiResponse::success(intent)))
}

// ---------------------------------------------------------------------------
// DELETE
// ---------------------------------------------------------------------------

async fn delete_intent(Path(intent_id): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let keys: Vec<String> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {COLLECTION} \
                 FILTER d.intent_id == @intent_id \
                 LIMIT 1 RETURN d._key"
            ),
            [("intent_id", serde_json::json!(&intent_id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc_key = keys.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let col = db
        .collection(COLLECTION)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<Value>(&doc_key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success("Intent deleted".to_string())))
}

// ---------------------------------------------------------------------------
// FEEDBACK (append nl_examples via thumbs_up)
// ---------------------------------------------------------------------------

async fn feedback_intent(
    Path(intent_id): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let action = payload.get("action").and_then(|v| v.as_str()).unwrap_or("");
    let nl_query = payload.get("nl_query").and_then(|v| v.as_str()).unwrap_or("");

    if action != "thumbs_up" || nl_query.is_empty() {
        return Ok(Json(serde_json::json!({
            "code": 0,
            "data": { "action": action, "intent_id": intent_id, "applied": false }
        })));
    }

    let db = get_db();

    let keys: Vec<String> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {COLLECTION} \
                 FILTER d.intent_id == @intent_id \
                 LIMIT 1 RETURN d._key"
            ),
            [("intent_id", serde_json::json!(&intent_id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc_key = keys.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    // Update timestamp
    let update_doc = serde_json::json!({
        "updated_at": chrono::Utc::now().to_rfc3339(),
    });
    let col = db
        .collection(COLLECTION)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(&doc_key, update_doc, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Append nl_examples
    db.aql_bind_vars::<Value>(
        &format!(
            "FOR d IN {COLLECTION} FILTER d._key == @key \
             UPDATE d WITH {{ nl_examples: APPEND(d.nl_examples, @nl) }} IN {COLLECTION}"
        ),
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
        "data": {
            "action": "thumbs_up",
            "intent_id": intent_id,
            "applied": true,
            "nl_added": nl_query
        }
    })))
}

// ---------------------------------------------------------------------------
// PROXY: scope-aware Qdrant sync
// ---------------------------------------------------------------------------

async fn proxy_sync_qdrant(
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let scope = payload
        .get("agent_scope")
        .and_then(|v| v.as_str())
        .unwrap_or("data_agent");

    let base_url = resolve_intent_rag_base(scope);
    let url = format!("{}/intent-rag/{scope}/embed-sync", base_url);

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let resp = client.post(&url).json(&payload).send().await.map_err(|e| {
        eprintln!("proxy_sync_qdrant ({scope}) error: {e}");
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

// ---------------------------------------------------------------------------
// PROXY: scope-aware list models
// ---------------------------------------------------------------------------

async fn proxy_list_models(
    Query(params): Query<HashMap<String, String>>,
) -> Result<impl IntoResponse, StatusCode> {
    let scope = params
        .get("agent_scope")
        .map(|s| s.as_str())
        .unwrap_or("data_agent");

    let base_url = resolve_intent_rag_base(scope);
    let url = format!("{}/intent-rag/{scope}/models", base_url);

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let resp = client.get(&url).send().await.map_err(|e| {
        eprintln!("proxy_list_models ({scope}) error: {e}");
        StatusCode::BAD_GATEWAY
    })?;

    let body: Value = resp.json().await.map_err(|_| StatusCode::BAD_GATEWAY)?;
    Ok(Json(body))
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

/// Resolve the Python intent-rag base URL for a given scope.
/// Currently all scopes share the data_agent service; can be extended later.
fn resolve_intent_rag_base(scope: &str) -> String {
    match scope {
        "data_agent" | "orchestrator" => CONFIG.ai_services.data_agent_url.clone(),
        _ => CONFIG.ai_services.data_agent_url.clone(),
    }
}
