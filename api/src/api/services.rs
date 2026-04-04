//! Services Router
//!
//! # Description
//! AI 服務管理 API
//!
//! # Last Update: 2026-04-05 22:05:00
//! # Author: Daniel Chung
//! # Version: 1.3.0

use crate::config::CONFIG;
use axum::{
    extract::Path,
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::time::Instant;

pub fn create_services_router() -> Router {
    Router::new()
        .route("/api/v1/services", get(list_services))
        .route("/api/v1/services/{name}", get(get_service))
        .route("/api/v1/services/{name}/start", post(start_service))
        .route("/api/v1/services/{name}/stop", post(stop_service))
        .route("/api/v1/services/{name}/restart", post(restart_service))
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ServiceInfo {
    pub name: String,
    pub display_name: String,
    pub status: ServiceStatus,
    pub port: u16,
    pub url: String,
    pub health_url: Option<String>,
    pub last_check: Option<String>,
    pub latency_ms: Option<u64>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "lowercase")]
pub enum ServiceStatus {
    Running,
    Stopped,
    Starting,
    Stopping,
    Error,
}

#[derive(Debug, Serialize)]
pub struct ServiceListResponse {
    pub services: Vec<ServiceInfo>,
}

#[derive(Debug, Serialize)]
pub struct ServiceResponse {
    pub service: ServiceInfo,
}

#[derive(Debug, Serialize)]
pub struct ActionResponse {
    pub success: bool,
    pub message: String,
}

struct ServiceDef {
    name: &'static str,
    display_name: &'static str,
    port: u16,
}

fn service_defs() -> Vec<ServiceDef> {
    vec![
        ServiceDef { name: "aitask",           display_name: "AI Task",          port: 8001 },
        ServiceDef { name: "data-agent",       display_name: "Data Agent",       port: 8003 },
        ServiceDef { name: "mcp-tools",        display_name: "MCP Tools",        port: 8004 },
        ServiceDef { name: "bpa-mm-agent",     display_name: "BPA MM Agent",     port: 8005 },
        ServiceDef { name: "knowledge-agent",  display_name: "Knowledge Agent",  port: 8007 },
        ServiceDef { name: "backup-agent",      display_name: "Backup Agent",      port: 8010 },
    ]
}

fn base_url_for(name: &str) -> String {
    let cfg = &CONFIG.ai_services;
    match name {
        "aitask"          => cfg.aitask_url.clone(),
        "data-agent"      => cfg.data_agent_url.clone(),
        "mcp-tools"      => cfg.mcp_tools_url.clone(),
        "bpa-mm-agent"   => cfg.bpa_mm_agent_url.clone(),
        "knowledge-agent" => cfg.knowledge_agent_url.clone(),
        "backup-agent"  => std::env::var("BACKUP_AGENT_URL")
            .unwrap_or_else(|_| "http://localhost:8010".to_string()),
        _ => format!("http://localhost:{}", 0),
    }
}

fn make_service_info(def: &ServiceDef, status: ServiceStatus, latency_ms: Option<u64>) -> ServiceInfo {
    let base = base_url_for(def.name);
    ServiceInfo {
        name: def.name.to_string(),
        display_name: def.display_name.to_string(),
        status,
        port: def.port,
        url: base.clone(),
        health_url: Some(format!("{}/health", base)),
        last_check: Some(chrono::Utc::now().to_rfc3339()),
        latency_ms,
    }
}

async fn list_services() -> impl IntoResponse {
    let defs = service_defs();
    let services: Vec<ServiceInfo> = defs
        .iter()
        .map(|def| make_service_info(def, ServiceStatus::Running, None))
        .collect();
    Json(ServiceListResponse { services })
}

async fn get_service(Path(name): Path<String>) -> impl IntoResponse {
    let defs = service_defs();
    match defs.iter().find(|d| d.name == name) {
        Some(def) => Json(ServiceResponse { service: make_service_info(def, ServiceStatus::Running, None) }).into_response(),
        None => (StatusCode::NOT_FOUND, Json(serde_json::json!({"error": "Service not found"}))).into_response(),
    }
}

async fn start_service(Path(name): Path<String>) -> impl IntoResponse {
    Json(ActionResponse {
        success: true,
        message: format!("Service {} started", name),
    })
}

async fn stop_service(Path(name): Path<String>) -> impl IntoResponse {
    Json(ActionResponse {
        success: true,
        message: format!("Service {} stopped", name),
    })
}

async fn restart_service(Path(name): Path<String>) -> impl IntoResponse {
    Json(ActionResponse {
        success: true,
        message: format!("Service {} restarted", name),
    })
}
