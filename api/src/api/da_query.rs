//! Data Agent Query & Health API Routes
//!
//! # Description
//! DA 的查詢執行、健康檢查與同步 endpoints
//! 使用 DuckDB 連線工廠模式（每次查詢建立獨立連線）避免 mutex poison 問題。
//! /nl2sql proxy 轉發到 Python data_agent 服務。
//!
//! # Last Update: 2026-03-23 22:20:13
//! # Author: Daniel Chung
//! # Version: 1.2.0

use crate::config::CONFIG;
use crate::db::get_db;
use crate::duckdb_conn::create_connection;
use axum::{
    extract::{Path, Query},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use duckdb::arrow::array::{
    Array, BooleanArray, Float32Array, Float64Array, Int8Array, Int16Array, Int32Array, Int64Array,
    StringArray, UInt8Array, UInt16Array, UInt32Array, UInt64Array,
};
use serde_json::{Map, Value};
use std::time::Instant;
use uuid::Uuid;

pub fn create_da_query_router() -> Router {
    Router::new()
        .route("/api/v1/da/query", post(execute_da_query))
        .route("/api/v1/da/query/sql", post(execute_direct_sql))
        .route("/api/v1/da/query/nl2sql", post(proxy_nl2sql))
        .route("/api/v1/da/query/tables/{table_name}/preview", get(proxy_table_preview))
        .route("/api/v1/da/health", get(da_health))
        .route("/api/v1/da/sync/status", get(get_sync_status))
        .route("/api/v1/da/sync/trigger", post(trigger_sync))
}

async fn execute_da_query(Json(payload): Json<Value>) -> Response {
    if payload
        .get("query")
        .and_then(|value| value.as_str())
        .filter(|value| !value.trim().is_empty())
        .is_none()
    {
        return StatusCode::BAD_REQUEST.into_response();
    }

    let sql = payload
        .get("sql")
        .and_then(|value| value.as_str())
        .map(str::trim)
        .filter(|value| !value.is_empty());

    if let Some(sql) = sql {
        if !is_select_statement(sql) {
            return only_select_error_response();
        }
        return execute_duckdb_sql_response(sql);
    }

    Json(serde_json::json!({
        "code": 0,
        "data": {
            "sql": Value::Null,
            "results": [],
            "columns": [],
            "metadata": {
                "duration_ms": 0,
                "row_count": 0,
                "truncated": false,
                "trace_id": format!("nl-{}", Uuid::new_v4())
            }
        },
        "intent": {
            "intent_type": "pending",
            "confidence": 0.0
        },
        "cache_hit": false,
        "message": "NL→SQL pipeline not yet connected. Provide 'sql' field for direct execution."
    }))
    .into_response()
}

async fn execute_direct_sql(Json(payload): Json<Value>) -> Response {
    let Some(sql) = payload
        .get("sql")
        .and_then(|value| value.as_str())
        .filter(|value| !value.trim().is_empty())
    else {
        return StatusCode::BAD_REQUEST.into_response();
    };

    let sql = sql.trim();
    if !is_select_statement(sql) {
        return only_select_error_response();
    }

    execute_duckdb_sql_response(sql)
}

async fn da_health() -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let timestamp = chrono::Utc::now().to_rfc3339();

    let mut errors: Vec<String> = Vec::new();

    let arangodb_connected = match db.aql_str::<Value>("RETURN 1").await {
        Ok(_) => true,
        Err(error) => {
            errors.push(format!("ArangoDB error: {error}"));
            false
        }
    };

    let (has_da_table_info, has_da_field_info, has_da_table_relation, has_da_intents) =
        if arangodb_connected {
            let collections = db
                .accessible_collections()
                .await
                .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
            let has_collection = |name: &str| collections.iter().any(|col| col.name == name);
            (
                has_collection("da_table_info"),
                has_collection("da_field_info"),
                has_collection("da_table_relation"),
                has_collection("da_intents"),
            )
        } else {
            (false, false, false, false)
        };

    let duckdb_connected = match create_connection() {
        Ok(conn) => match conn.execute_batch("SELECT 1;") {
            Ok(_) => true,
            Err(error) => {
                errors.push(format!("DuckDB error: {error}"));
                false
            }
        },
        Err(error) => {
            errors.push(format!("DuckDB error: {error}"));
            false
        }
    };

    let status = if arangodb_connected
        && duckdb_connected
        && has_da_table_info
        && has_da_field_info
        && has_da_table_relation
        && has_da_intents
    {
        "healthy"
    } else {
        "degraded"
    };

    let mut data = serde_json::json!({
        "status": status,
        "arangodb": if arangodb_connected { "connected" } else { "disconnected" },
        "duckdb": if duckdb_connected { "connected" } else { "disconnected" },
        "collections": {
            "da_table_info": has_da_table_info,
            "da_field_info": has_da_field_info,
            "da_table_relation": has_da_table_relation,
            "da_intents": has_da_intents
        },
        "timestamp": timestamp
    });

    if !errors.is_empty() {
        data["error"] = Value::String(errors.join("; "));
    }

    Ok(Json(serde_json::json!({
        "code": 0,
        "data": data
    })))
}

async fn get_sync_status() -> Result<impl IntoResponse, StatusCode> {
    Ok(Json(serde_json::json!({
        "code": 0,
        "data": {
            "status": "idle",
            "last_sync": Value::Null,
            "message": "Sync service not yet implemented"
        }
    })))
}

async fn trigger_sync() -> Result<impl IntoResponse, StatusCode> {
    Ok(Json(serde_json::json!({
        "code": 0,
        "data": {
            "status": "accepted",
            "message": "Sync trigger not yet implemented"
        }
    })))
}

/// Proxy POST /api/v1/da/query/nl2sql → data_agent:8003/query/nl2sql
async fn proxy_nl2sql(Json(payload): Json<Value>) -> Result<impl IntoResponse, StatusCode> {
    let url = format!("{}/query/nl2sql", CONFIG.ai_services.data_agent_url);

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
            eprintln!("proxy_nl2sql error: {e}");
            StatusCode::BAD_GATEWAY
        })?;

    let body: Value = resp.json().await.map_err(|_| StatusCode::BAD_GATEWAY)?;
    Ok(Json(body))
}

#[derive(serde::Deserialize)]
struct PreviewQuery {
    offset: Option<usize>,
    limit: Option<usize>,
}

async fn proxy_table_preview(
    Path(table_name): Path<String>,
    Query(params): Query<PreviewQuery>,
) -> Result<impl IntoResponse, StatusCode> {
    let offset = params.offset.unwrap_or(0);
    let limit = params.limit.unwrap_or(20);
    let url = format!(
        "{}/query/tables/{}/preview?offset={}&limit={}",
        CONFIG.ai_services.data_agent_url, table_name, offset, limit
    );

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let resp = client
        .get(&url)
        .send()
        .await
        .map_err(|e| {
            eprintln!("proxy_table_preview error: {e}");
            StatusCode::BAD_GATEWAY
        })?;

    let body: Value = resp.json().await.map_err(|_| StatusCode::BAD_GATEWAY)?;
    Ok(Json(body))
}

fn is_select_statement(sql: &str) -> bool {
    sql.trim_start().to_ascii_uppercase().starts_with("SELECT")
}

fn only_select_error_response() -> Response {
    (
        StatusCode::BAD_REQUEST,
        Json(serde_json::json!({
            "code": 1,
            "message": "Only SELECT statements are allowed"
        })),
    )
        .into_response()
}

fn execute_duckdb_sql_response(sql: &str) -> Response {
    match run_duckdb_query(sql) {
        Ok((results, columns, duration_ms, truncated)) => Json(serde_json::json!({
            "code": 0,
            "data": {
                "sql": sql,
                "results": results,
                "columns": columns,
                "metadata": {
                    "duration_ms": duration_ms,
                    "row_count": results.len(),
                    "truncated": truncated,
                    "trace_id": format!("duckdb-{}", Uuid::new_v4())
                }
            },
            "intent": {
                "intent_type": "direct_sql",
                "confidence": 1.0
            },
            "cache_hit": false,
            "message": "OK"
        }))
        .into_response(),
        Err(error) => Json(serde_json::json!({
            "code": 1,
            "message": format!("DuckDB error: {error}"),
            "data": Value::Null
        }))
        .into_response(),
    }
}

/// Execute SQL via a fresh DuckDB connection (factory pattern).
/// Uses query_arrow to avoid known panic bug in query_map (raw_statement.rs:241).
fn run_duckdb_query(sql: &str) -> Result<(Vec<Value>, Vec<String>, u64, bool), String> {
    let conn = create_connection()?;
    let start = Instant::now();

    let mut stmt = conn.prepare(sql).map_err(|e| e.to_string())?;
    let arrow_iter = stmt.query_arrow([]).map_err(|e| e.to_string())?;

    let mut columns: Vec<String> = Vec::new();
    let mut results: Vec<Value> = Vec::new();
    let mut truncated = false;
    let mut columns_set = false;

    for batch in arrow_iter {
        if !columns_set {
            columns = batch
                .schema()
                .fields()
                .iter()
                .map(|f| f.name().clone())
                .collect();
            columns_set = true;
        }

        let num_rows = batch.num_rows();
        let num_cols = batch.num_columns();

        for row_idx in 0..num_rows {
            if results.len() >= 1000 {
                truncated = true;
                break;
            }
            let mut row_map = Map::new();
            for col_idx in 0..num_cols {
                let col_name = columns.get(col_idx).cloned().unwrap_or_default();
                let col = batch.column(col_idx);
                let value = arrow_value_at(col, row_idx);
                row_map.insert(col_name, value);
            }
            results.push(Value::Object(row_map));
        }

        if truncated {
            break;
        }
    }

    let duration_ms = start.elapsed().as_millis() as u64;
    Ok((results, columns, duration_ms, truncated))
}

/// Extract a JSON Value from an Arrow array at the given row index.
fn arrow_value_at(col: &dyn Array, row: usize) -> Value {
    if col.is_null(row) {
        return Value::Null;
    }
    if let Some(arr) = col.as_any().downcast_ref::<Int64Array>() {
        return Value::Number(arr.value(row).into());
    }
    if let Some(arr) = col.as_any().downcast_ref::<Int32Array>() {
        return Value::Number((arr.value(row) as i64).into());
    }
    if let Some(arr) = col.as_any().downcast_ref::<Int16Array>() {
        return Value::Number((arr.value(row) as i64).into());
    }
    if let Some(arr) = col.as_any().downcast_ref::<Int8Array>() {
        return Value::Number((arr.value(row) as i64).into());
    }
    if let Some(arr) = col.as_any().downcast_ref::<UInt64Array>() {
        return Value::Number(arr.value(row).into());
    }
    if let Some(arr) = col.as_any().downcast_ref::<UInt32Array>() {
        return Value::Number((arr.value(row) as u64).into());
    }
    if let Some(arr) = col.as_any().downcast_ref::<UInt16Array>() {
        return Value::Number((arr.value(row) as u64).into());
    }
    if let Some(arr) = col.as_any().downcast_ref::<UInt8Array>() {
        return Value::Number((arr.value(row) as u64).into());
    }
    if let Some(arr) = col.as_any().downcast_ref::<Float64Array>() {
        let v = arr.value(row);
        return serde_json::Number::from_f64(v)
            .map(Value::Number)
            .unwrap_or(Value::Null);
    }
    if let Some(arr) = col.as_any().downcast_ref::<Float32Array>() {
        let v = arr.value(row) as f64;
        return serde_json::Number::from_f64(v)
            .map(Value::Number)
            .unwrap_or(Value::Null);
    }
    if let Some(arr) = col.as_any().downcast_ref::<StringArray>() {
        return Value::String(arr.value(row).to_string());
    }
    if let Some(arr) = col.as_any().downcast_ref::<BooleanArray>() {
        return Value::Bool(arr.value(row));
    }
    // Fallback: try to format via Display (covers Date, Timestamp, etc.)
    let formatted = duckdb::arrow::util::display::array_value_to_string(col, row);
    match formatted {
        Ok(s) => Value::String(s),
        Err(_) => Value::Null,
    }
}
