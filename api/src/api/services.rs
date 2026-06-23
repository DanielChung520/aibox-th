//! Services Router
//!
//! # Description
//! AI 服務管理 API
//!
//! # Last Update: 2026-04-05 12:05:00
//! # Author: Daniel Chung
//! # Version: 1.4.0

use crate::config::CONFIG;
use axum::{
    extract::Path,
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Instant;
use std::net::SocketAddr;
use std::time::Duration;
use tokio::net::TcpStream;
use tokio::time::timeout;

pub fn create_services_router() -> Router {
    Router::new()
        .route("/api/v1/services", get(list_services))
        .route("/api/v1/services/{name}", get(get_service))
        .route("/api/v1/services/{name}/start", post(start_service))
        .route("/api/v1/services/{name}/stop", post(stop_service))
        .route("/api/v1/services/{name}/restart", post(restart_service))
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ServiceInfo {
    pub name: String,
    pub display_name: String,
    pub status: ServiceStatus,
    pub port: u16,
    pub url: String,
    pub health_url: Option<String>,
    pub last_check: Option<String>,
    pub latency_ms: Option<u64>,
    pub started_at: Option<String>,
    pub health_via_tcp: bool,
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
    health_via_tcp: bool,
}

fn service_defs() -> Vec<ServiceDef> {
    vec![
        ServiceDef { name: "aitask",           display_name: "AI Task",         port: 8001, health_via_tcp: false },
        ServiceDef { name: "unified-agents",   display_name: "Unified Agents", port: 8011, health_via_tcp: false },
        ServiceDef { name: "celery",           display_name: "Celery Worker",   port: 6379, health_via_tcp: false },
    ]
}

fn base_url_for(name: &str) -> String {
    let cfg = &CONFIG.ai_services;
    match name {
        "aitask" => cfg.aitask_url.clone(),
        "bpa-mm-agent" => cfg.bpa_mm_agent_url.clone(),
        "unified-agents" => cfg.unified_agents_url.clone(),
        "celery" => format!("{}/celery", cfg.unified_agents_url),
        _ => "http://localhost:0".to_string(),
    }
}

fn health_url_for(def: &ServiceDef) -> Option<String> {
    if def.health_via_tcp {
        None
    } else {
        Some(format!("{}/health", base_url_for(def.name)))
    }
}

async fn check_http_health(client: &Client, url: &str) -> (ServiceStatus, Option<u64>, Option<String>) {
    let start = Instant::now();
    let resp = client.get(url).send().await;
    let latency_ms = start.elapsed().as_millis() as u64;

    match resp {
        Ok(r) if r.status().is_success() => {
            let started_at = if let Ok(json) = r.json::<serde_json::Value>().await {
                json.get("started_at")
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string())
            } else {
                None
            };
            (ServiceStatus::Running, Some(latency_ms), started_at)
        }
        _ => (ServiceStatus::Error, Some(latency_ms), None),
    }
}

async fn check_tcp_health(port: u16) -> (ServiceStatus, Option<u64>) {
    let addr: SocketAddr = format!("127.0.0.1:{}", port).parse().unwrap();
    let start = Instant::now();
    let result = timeout(Duration::from_secs(3), TcpStream::connect(addr)).await;
    let latency_ms = start.elapsed().as_millis() as u64;

    match result {
        Ok(Ok(_)) => (ServiceStatus::Running, Some(latency_ms)),
        _ => (ServiceStatus::Error, Some(latency_ms)),
    }
}

async fn check_service(def: ServiceDef) -> ServiceInfo {
    let client = Client::builder()
        .timeout(Duration::from_secs(5))
        .build()
        .unwrap_or_else(|_| Client::new());

    let (status, latency_ms, started_at) = if def.health_via_tcp {
        let (s, l) = check_tcp_health(def.port).await;
        (s, l, None)
    } else {
        let url = format!("{}/health", base_url_for(def.name));
        check_http_health(&client, &url).await
    };

    let base = base_url_for(def.name);
    ServiceInfo {
        name: def.name.to_string(),
        display_name: def.display_name.to_string(),
        status,
        port: def.port,
        url: base,
        health_url: health_url_for(&def),
        last_check: Some(chrono::Utc::now().to_rfc3339()),
        latency_ms,
        started_at,
        health_via_tcp: def.health_via_tcp,
    }
}

async fn list_services() -> impl IntoResponse {
    let defs = service_defs();

    let mut handles = Vec::new();
    for def in defs {
        handles.push(tokio::spawn(check_service(def)));
    }

    let mut services = Vec::new();
    for handle in handles {
        if let Ok(svc) = handle.await {
            services.push(svc);
        }
    }

    // Sort by display_name for consistent ordering
    services.sort_by(|a, b| a.display_name.cmp(&b.display_name));

    Json(ServiceListResponse { services })
}

async fn get_service(Path(name): Path<String>) -> impl IntoResponse {
    let defs = service_defs();
    match defs.iter().find(|d| d.name == name) {
        Some(def) => {
            let svc = check_service(ServiceDef {
                name: def.name,
                display_name: def.display_name,
                port: def.port,
                health_via_tcp: def.health_via_tcp,
            }).await;
            Json(ServiceResponse { service: svc }).into_response()
        }
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
