//! Data Agent Tables API Routes
//!
//! # Description
//! Data Agent 表管理 CRUD endpoints，操作 ArangoDB da_tables 集合。
//! 提供表的列表（含分頁、篩選、搜尋）、取得單筆、新增、更新、刪除功能。
//!
//! # Last Update: 2026-04-13 05:31:39
//! # Author: Daniel Chung
//! # Version: 1.0.0

use crate::db::get_db;
use crate::models::ApiResponse;
use axum::{
    extract::{Path, Query},
    http::StatusCode,
    response::IntoResponse,
    routing::get,
    Json, Router,
};
use serde_json::Value;
use std::collections::HashMap;

const COLLECTION: &str = "da_tables";

pub fn create_da_tables_router() -> Router {
    Router::new()
        .route("/api/v1/da/tables", get(list_tables).post(create_table))
        .route(
            "/api/v1/da/tables/{key}",
            get(get_table).put(update_table).delete(delete_table),
        )
}

// ---------------------------------------------------------------------------
// LIST (paginated, filterable by domain / status / search)
// ---------------------------------------------------------------------------

async fn list_tables(
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

    if let Some(domain) = params.get("domain").filter(|v| !v.trim().is_empty()) {
        filters.push("d.domain == @domain".into());
        bind_entries.push(("domain".into(), serde_json::json!(domain)));
    }

    if let Some(status) = params.get("status").filter(|v| !v.trim().is_empty()) {
        filters.push("d.status == @status".into());
        bind_entries.push(("status".into(), serde_json::json!(status)));
    }

    if let Some(search) = params.get("search").filter(|v| !v.trim().is_empty()) {
        filters.push(
            "(LIKE(d.display_name, CONCAT('%', @search, '%'), true) \
             || LIKE(d.description, CONCAT('%', @search, '%'), true) \
             || LIKE(d._key, CONCAT('%', @search, '%'), true))"
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
            eprintln!("da_tables count error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    let total_count = total_result.into_iter().next().unwrap_or(0);

    // ── paginated records ──
    bind_entries.push(("offset".into(), serde_json::json!(offset)));
    bind_entries.push(("page_size".into(), serde_json::json!(page_size)));

    let records_query = format!(
        "FOR d IN {COLLECTION}{filter_clause} \
         SORT d.domain ASC, d.display_name ASC \
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
            eprintln!("da_tables records error: {e}");
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
// GET single table by _key
// ---------------------------------------------------------------------------

async fn get_table(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let mut results: Vec<Value> = db
        .aql_bind_vars(
            &format!("FOR d IN {COLLECTION} FILTER d._key == @key LIMIT 1 RETURN d"),
            [("key", serde_json::json!(&key))].into(),
        )
        .await
        .map_err(|e| {
            eprintln!("da_tables get error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let table = results.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(table)))
}

// ---------------------------------------------------------------------------
// CREATE
// ---------------------------------------------------------------------------

async fn create_table(Json(payload): Json<Value>) -> Result<impl IntoResponse, StatusCode> {
    let key = payload
        .get("_key")
        .and_then(|v| v.as_str())
        .map(String::from)
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
            eprintln!("da_tables dup check error: {e}");
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
            eprintln!("da_tables create error: {e}");
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
    let table = created.pop().ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(table)))
}

// ---------------------------------------------------------------------------
// UPDATE
// ---------------------------------------------------------------------------

async fn update_table(
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
            eprintln!("da_tables update error: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let mut updated: Vec<Value> = db
        .aql_bind_vars(
            &format!("FOR d IN {COLLECTION} FILTER d._key == @key LIMIT 1 RETURN d"),
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let table = updated.pop().ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(ApiResponse::success(table)))
}

// ---------------------------------------------------------------------------
// DELETE
// ---------------------------------------------------------------------------

async fn delete_table(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let col = db
        .collection(COLLECTION)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<Value>(&key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;

    Ok(Json(ApiResponse::success(
        "Table deleted".to_string(),
    )))
}
