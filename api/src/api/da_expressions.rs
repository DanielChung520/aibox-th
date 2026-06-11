use crate::config::CONFIG;
use crate::db::get_db;
use crate::models::ApiResponse;
use axum::{
    extract::{Path, Query},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use serde_json::Value;
use std::collections::HashMap;

const COLLECTION: &str = "da_expressions";

pub fn create_da_expressions_router() -> Router {
    Router::new()
        .route(
            "/api/v1/da/expressions",
            get(list_expressions).post(create_expression),
        )
        .route(
            "/api/v1/da/expressions/{key}",
            get(get_expression)
                .put(update_expression)
                .delete(delete_expression),
        )
        .route(
            "/api/v1/da/expressions/sync-qdrant",
            post(proxy_sync_da_expressions),
        )
}

fn get_data_agent_url() -> String {
    format!("{}/da/intent-rag", CONFIG.ai_services.unified_agents_url)
}

async fn sync_expression_to_qdrant(key: &str) -> Result<(), StatusCode> {
    let url = format!(
        "{}/data_agent/upsert-expression/{}",
        get_data_agent_url(),
        key
    );
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(60))
        .build()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    client
        .post(&url)
        .send()
        .await
        .map_err(|e| {
            eprintln!("sync_expression_to_qdrant error: {e}");
            StatusCode::BAD_GATEWAY
        })?;

    Ok(())
}

async fn delete_expression_from_qdrant(key: &str) -> Result<(), StatusCode> {
    let url = format!(
        "{}/data_agent/delete-expression/{}",
        get_data_agent_url(),
        key
    );
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let _ = client
        .delete(&url)
        .send()
        .await
        .map_err(|e| {
            eprintln!("delete_expression_from_qdrant error: {e}");
            StatusCode::BAD_GATEWAY
        })?;

    Ok(())
}

// ---------------------------------------------------------------------------
// LIST (paginated, filterable by table_key / status / search)
// ---------------------------------------------------------------------------

async fn list_expressions(
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

    if let Some(table_key) = params.get("table_key").filter(|v| !v.trim().is_empty()) {
        filters.push("d.table_key == @table_key".into());
        bind_entries.push(("table_key".into(), serde_json::json!(table_key)));
    }

    if let Some(status) = params.get("status").filter(|v| !v.trim().is_empty()) {
        filters.push("d.status == @status".into());
        bind_entries.push(("status".into(), serde_json::json!(status)));
    }

    if let Some(search) = params.get("search").filter(|v| !v.trim().is_empty()) {
        filters.push(
            "(LIKE(d.name, CONCAT('%', @search, '%'), true) \
             || LIKE(d.description, CONCAT('%', @search, '%'), true) \
             || LIKE(d.table_key, CONCAT('%', @search, '%'), true))"
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
            eprintln!("da_expressions count error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    let total_count = total_result.into_iter().next().unwrap_or(0);

    // ── paginated records ──
    bind_entries.push(("offset".into(), serde_json::json!(offset)));
    bind_entries.push(("page_size".into(), serde_json::json!(page_size)));

    let records_query = format!(
        "FOR d IN {COLLECTION}{filter_clause} \
         SORT d.table_key ASC, d.angle ASC \
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
            eprintln!("da_expressions records error: {e}");
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
// GET single expression by _key
// ---------------------------------------------------------------------------

async fn get_expression(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let mut results: Vec<Value> = db
        .aql_bind_vars(
            &format!("FOR d IN {COLLECTION} FILTER d._key == @key LIMIT 1 RETURN d"),
            [("key", serde_json::json!(&key))].into(),
        )
        .await
        .map_err(|e| {
            eprintln!("da_expressions get error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let expression = results.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(expression)))
}

// ---------------------------------------------------------------------------
// CREATE
// ---------------------------------------------------------------------------

async fn create_expression(Json(payload): Json<Value>) -> Result<impl IntoResponse, StatusCode> {
    let key = payload
        .get("_key")
        .and_then(|v| v.as_str())
        .map(String::from)
        .ok_or(StatusCode::BAD_REQUEST)?;

    // table_key is required
    let _table_key = payload
        .get("table_key")
        .and_then(|v| v.as_str())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let db = get_db();

    // Duplicate check by _key
    let existing: Vec<Value> = db
        .aql_bind_vars(
            &format!("FOR d IN {COLLECTION} FILTER d._key == @key LIMIT 1 RETURN d._key"),
            [("key", serde_json::json!(&key))].into(),
        )
        .await
        .map_err(|e| {
            eprintln!("da_expressions dup check error: {e}");
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
        obj.entry("status".to_string())
            .or_insert(serde_json::json!("enabled"));
    }

    let col = db
        .collection(COLLECTION)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(doc, Default::default())
        .await
        .map_err(|e| {
            eprintln!("da_expressions create error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // Return created document
    let mut created: Vec<Value> = db
        .aql_bind_vars(
            &format!("FOR d IN {COLLECTION} FILTER d._key == @key LIMIT 1 RETURN d"),
            [("key", serde_json::json!(&key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let expression = created.pop().ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    let _ = sync_expression_to_qdrant(&key).await;

    Ok(Json(ApiResponse::success(expression)))
}

// ---------------------------------------------------------------------------
// UPDATE
// ---------------------------------------------------------------------------

async fn update_expression(
    Path(key): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    // Verify document exists
    let existing: Vec<Value> = db
        .aql_bind_vars(
            &format!("FOR d IN {COLLECTION} FILTER d._key == @key LIMIT 1 RETURN d._key"),
            [("key", serde_json::json!(&key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    if existing.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    let mut update_data = payload;
    if let Some(obj) = update_data.as_object_mut() {
        obj.insert(
            "updated_at".into(),
            serde_json::json!(chrono::Utc::now().to_rfc3339()),
        );
        obj.remove("_key");
        obj.remove("_id");
        obj.remove("_rev");
    }

    let col = db
        .collection(COLLECTION)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(&key, update_data, Default::default())
        .await
        .map_err(|e| {
            eprintln!("da_expressions update error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let mut updated: Vec<Value> = db
        .aql_bind_vars(
            &format!("FOR d IN {COLLECTION} FILTER d._key == @key LIMIT 1 RETURN d"),
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let expression = updated.pop().ok_or(StatusCode::NOT_FOUND)?;

    let _ = sync_expression_to_qdrant(&key).await;

    Ok(Json(ApiResponse::success(expression)))
}

// ---------------------------------------------------------------------------
// DELETE
// ---------------------------------------------------------------------------

async fn delete_expression(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let col = db
        .collection(COLLECTION)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<Value>(&key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;

    let _ = delete_expression_from_qdrant(&key).await;

    Ok(Json(ApiResponse::success(
        "Expression deleted".to_string(),
    )))
}

// ---------------------------------------------------------------------------
// PROXY: sync da_expressions to Qdrant via unified_agents
// ---------------------------------------------------------------------------

async fn proxy_sync_da_expressions(
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let base_url = format!("{}/da/intent-rag", CONFIG.ai_services.unified_agents_url);
    let url = format!("{base_url}/data_agent/sync-da-expressions");

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(300))
        .build()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let resp = client
        .post(&url)
        .json(&payload)
        .send()
        .await
        .map_err(|e| {
            eprintln!("proxy_sync_da_expressions error: {e}");
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
