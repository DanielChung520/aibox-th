//! Web Search API 端點
//!
//! 提供 web search API key 配置，供 Python AI Service 讀取
//!
//! # Last Update: 2026-03-27 17:00:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use axum::{routing::get, Json, Router};
use crate::db::get_db;

async fn get_web_search_config() -> Json<serde_json::Value> {
    let db = get_db();

    let rows: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR p IN system_params FILTER STARTS_WITH(p.param_key, 'web_search.') RETURN p",
            [].into(),
        )
        .await
        .unwrap_or_default();

    let mut config = serde_json::json!({});
    for row in rows {
        let key = row.get("param_key")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let value = row.get("param_value")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if let Some(short_key) = key.strip_prefix("web_search.") {
            if short_key.ends_with("_enabled") {
                config[short_key] = serde_json::json!(value == "true");
            } else {
                config[short_key] = serde_json::json!(value);
            }
        }
    }

    Json(serde_json::json!({ "code": 200, "data": config }))
}

pub fn create_web_search_router() -> Router {
    Router::new()
        .route("/api/v1/web-search/config", get(get_web_search_config))
}
