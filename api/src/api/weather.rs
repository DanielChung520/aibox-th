//! Weather API endpoint - provides config to Python services
//!
//! # Last Update: 2026-03-27 18:00:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use axum::{routing::get, Json, Router};

use crate::db::get_db;

async fn get_weather_config() -> Json<serde_json::Value> {
    let db = get_db();

    let rows: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR p IN system_params FILTER STARTS_WITH(p.param_key, 'weather.') RETURN p",
            [].into(),
        )
        .await
        .unwrap_or_default();

    let mut config = serde_json::json!({});
    for row in rows {
        let key = row
            .get("param_key")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let value = row
            .get("param_value")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if let Some(short_key) = key.strip_prefix("weather.") {
            if short_key.ends_with("_enabled") {
                config[short_key] = serde_json::json!(value == "true");
            } else {
                config[short_key] = serde_json::json!(value);
            }
        }
    }

    Json(serde_json::json!({ "code": 200, "data": config }))
}

pub fn create_weather_router() -> Router {
    Router::new().route("/api/v1/weather/config", get(get_weather_config))
}
