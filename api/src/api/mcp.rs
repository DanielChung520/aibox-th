//! MCP Tools Execute API
//!
//! # Description
//! 工具市集工具執行端點，轉發到 unified_agents (8011) /mcp/execute
//!
//! # Last Update: 2026-04-30 02:00:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::post,
    Json, Router,
};
use serde_json::{json, Value};

use crate::config::CONFIG;

/// MCP 工具執行請求
#[derive(serde::Deserialize)]
pub struct MCPExecuteRequest {
    pub tool: String,
    pub parameters: Value,
}

/// 轉發 /mcp/execute 到 unified_agents
async fn mcp_execute(Json(req): Json<MCPExecuteRequest>) -> Response {
    let url = format!("{}/mcp/execute", CONFIG.ai_services.unified_agents_url);

    let client = reqwest::Client::new();
    match client
        .post(&url)
        .json(&json!({
            "tool": req.tool,
            "parameters": req.parameters,
        }))
        .timeout(std::time::Duration::from_secs(300))
        .send()
        .await
    {
        Ok(resp) => {
            let status = StatusCode::from_u16(resp.status().as_u16())
                .unwrap_or(StatusCode::BAD_GATEWAY);
            let body: Value = resp.json().await.unwrap_or_else(|_| {
                json!({ "code": status.as_u16(), "message": "invalid JSON response from unified_agents" })
            });
            (status, Json(body)).into_response()
        }
        Err(e) => (
            StatusCode::BAD_GATEWAY,
            Json(json!({
                "code": 502,
                "message": format!("mcp execute failed: {}", e),
                "success": false,
                "error": e.to_string()
            })),
        )
            .into_response(),
    }
}

/// Async variant — submits to Celery and returns immediately
async fn mcp_execute_async(Json(req): Json<MCPExecuteRequest>) -> Response {
    let url = format!("{}/mcp/execute-async", CONFIG.ai_services.unified_agents_url);

    let client = reqwest::Client::new();
    match client
        .post(&url)
        .json(&json!({
            "tool": req.tool,
            "parameters": req.parameters,
        }))
        .timeout(std::time::Duration::from_secs(15))
        .send()
        .await
    {
        Ok(resp) => {
            let status = StatusCode::from_u16(resp.status().as_u16())
                .unwrap_or(StatusCode::BAD_GATEWAY);
            let body: Value = resp.json().await.unwrap_or_else(|_| {
                json!({ "code": status.as_u16(), "message": "invalid JSON response" })
            });
            (status, Json(body)).into_response()
        }
        Err(e) => (
            StatusCode::BAD_GATEWAY,
            Json(json!({
                "code": 502,
                "message": format!("mcp execute-async failed: {}", e),
                "success": false,
                "error": e.to_string()
            })),
        )
            .into_response(),
    }
}

pub fn create_mcp_router() -> Router {
    Router::new()
        .route("/api/v1/mcp/execute", post(mcp_execute))
        .route("/api/v1/mcp/execute-async", post(mcp_execute_async))
}
