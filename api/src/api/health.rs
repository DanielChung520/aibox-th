//! Health Router
//!
//! # Description
//! 健康檢查 API
//!
//! # Last Update: 2026-03-19 10:50:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use crate::db::get_db;
use crate::error::ApiError;
use axum::{
    response::IntoResponse,
    routing::get,
    Json, Router,
};
use serde::Serialize;
use std::time::{SystemTime, UNIX_EPOCH};

pub fn create_health_router() -> Router {
    Router::new()
        .route("/health", get(health_check))
        .route("/health/live", get(liveness))
        .route("/health/ready", get(readiness))
}

#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
    pub uptime: u64,
    pub services: HealthServices,
}

#[derive(Debug, Serialize)]
pub struct HealthServices {
    pub main_api: bool,
    pub chat_api: bool,
    pub arangodb: bool,
    pub qdrant: bool,
}

async fn health_check() -> Result<impl IntoResponse, ApiError> {
    let uptime = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);

    // Check ArangoDB
    let arangodb_ok = match get_db().aql_str::<serde_json::Value>("RETURN 1").await {
        Ok(_) => true,
        Err(e) => {
            eprintln!("ArangoDB health check failed: {}", e);
            false
        }
    };

    // Check Chat API (ai-task service on port 8001)
    let chat_api_ok = check_tcp_port("127.0.0.1:8001").await;

    // Check Qdrant (port 6333)
    let qdrant_ok = check_tcp_port("127.0.0.1:6333").await;

    // Main API is always ok if this handler runs
    let main_api_ok = true;

    let all_ok = main_api_ok && chat_api_ok && arangodb_ok && qdrant_ok;
    let status = if all_ok { "healthy" } else { "degraded" };

    let response = HealthResponse {
        status: status.to_string(),
        version: "1.0.0".to_string(),
        uptime,
        services: HealthServices {
            main_api: main_api_ok,
            chat_api: chat_api_ok,
            arangodb: arangodb_ok,
            qdrant: qdrant_ok,
        },
    };
    Ok(Json(response))
}

async fn check_tcp_port(addr: &str) -> bool {
    match tokio::net::TcpStream::connect(addr).await {
        Ok(_) => true,
        Err(e) => {
            eprintln!("TCP check {} failed: {}", addr, e);
            false
        }
    }
}

async fn liveness() -> Result<impl IntoResponse, ApiError> {
    Ok(Json(serde_json::json!({ "status": "alive" })))
}

async fn readiness() -> Result<impl IntoResponse, ApiError> {
    Ok(Json(serde_json::json!({ "status": "ready" })))
}
