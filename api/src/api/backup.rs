//! Backup Agent Router
//!
//! # Description
//! Proxy backup/restore requests to backup_agent:8010
//!
//! # Last Update: 2026-04-04
//! # Author: Daniel Chung
//! # Version: 1.0.0

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{delete, get, post},
    Json, Router,
};
use reqwest::Client;
use serde_json::Value;
use std::time::Duration;

#[derive(Clone)]
struct BackupAppState {
    client: Client,
}

pub fn create_backup_router() -> Router {
    let state = BackupAppState {
        client: Client::builder()
            .timeout(Duration::from_secs(600))
            .build()
            .unwrap(),
    };

    Router::new()
        .route("/api/v1/backup/arangodb", post(proxy_arangodb_backup))
        .route("/api/v1/backup/arangodb/history", get(proxy_arangodb_history))
        .route(
            "/api/v1/backup/arangodb/restore",
            post(proxy_arangodb_restore),
        )
        .route(
            "/api/v1/backup/arangodb/disk-usage",
            get(proxy_arangodb_disk),
        )
        .route(
            "/api/v1/backup/arangodb/{backup_id}",
            delete(delete_arangodb_backup),
        )
        .route("/api/v1/backup/qdrant", post(proxy_qdrant_backup))
        .route("/api/v1/backup/qdrant/history", get(proxy_qdrant_history))
        .route("/api/v1/backup/qdrant/restore", post(proxy_qdrant_restore))
        .route("/api/v1/backup/qdrant/disk-usage", get(proxy_qdrant_disk))
        .route(
            "/api/v1/backup/qdrant/{backup_id}",
            delete(delete_qdrant_backup),
        )
        .route("/api/v1/backup/status", get(proxy_backup_status))
        .with_state(state)
}

fn backup_base_url() -> String {
    std::env::var("BACKUP_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8010".to_string())
}

fn reqwest_to_axum_status(reqwest_status: reqwest::StatusCode) -> StatusCode {
    match reqwest_status.as_u16() {
        200 => StatusCode::OK,
        201 => StatusCode::CREATED,
        400 => StatusCode::BAD_REQUEST,
        404 => StatusCode::NOT_FOUND,
        500 => StatusCode::INTERNAL_SERVER_ERROR,
        502 => StatusCode::BAD_GATEWAY,
        _ => StatusCode::from_u16(reqwest_status.as_u16()).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

async fn proxy_to_backup(
    client: &Client,
    method: &str,
    path: &str,
    body: Option<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let url = format!("{}{}", backup_base_url(), path);

    let mut req = match method {
        "GET" => client.get(&url),
        "POST" => client.post(&url),
        "DELETE" => client.delete(&url),
        _ => return Err(StatusCode::METHOD_NOT_ALLOWED),
    };

    if let Some(payload) = body {
        req = req.json(&payload);
    }

    let resp = req.send().await.map_err(|e| {
        eprintln!("backup proxy error: {e}");
        StatusCode::BAD_GATEWAY
    })?;

    let status = resp.status();
    let body: Value = resp.json().await.unwrap_or(Value::Null);

    if status.is_success() || status.as_u16() >= 400 {
        Ok((reqwest_to_axum_status(status), Json(body)))
    } else {
        Err(StatusCode::BAD_GATEWAY)
    }
}

async fn proxy_arangodb_backup(
    State(state): State<BackupAppState>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    proxy_to_backup(&state.client, "POST", "/backup/arangodb", Some(payload)).await
}

async fn proxy_arangodb_history(
    State(state): State<BackupAppState>,
) -> Result<impl IntoResponse, StatusCode> {
    proxy_to_backup(&state.client, "GET", "/backup/arangodb/history", None).await
}

async fn proxy_arangodb_restore(
    State(state): State<BackupAppState>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    proxy_to_backup(&state.client, "POST", "/backup/arangodb/restore", Some(payload)).await
}

async fn proxy_arangodb_disk(
    State(state): State<BackupAppState>,
) -> Result<impl IntoResponse, StatusCode> {
    proxy_to_backup(&state.client, "GET", "/backup/arangodb/disk-usage", None).await
}

async fn delete_arangodb_backup(
    State(state): State<BackupAppState>,
    Path(backup_id): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let path = format!("/backup/arangodb/{}", backup_id);
    proxy_to_backup(&state.client, "DELETE", &path, None).await
}

async fn proxy_qdrant_backup(
    State(state): State<BackupAppState>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    proxy_to_backup(&state.client, "POST", "/backup/qdrant", Some(payload)).await
}

async fn proxy_qdrant_history(
    State(state): State<BackupAppState>,
) -> Result<impl IntoResponse, StatusCode> {
    proxy_to_backup(&state.client, "GET", "/backup/qdrant/history", None).await
}

async fn proxy_qdrant_restore(
    State(state): State<BackupAppState>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    proxy_to_backup(&state.client, "POST", "/backup/qdrant/restore", Some(payload)).await
}

async fn proxy_qdrant_disk(State(state): State<BackupAppState>) -> Result<impl IntoResponse, StatusCode> {
    proxy_to_backup(&state.client, "GET", "/backup/qdrant/disk-usage", None).await
}

async fn delete_qdrant_backup(
    State(state): State<BackupAppState>,
    Path(backup_id): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let path = format!("/backup/qdrant/{}", backup_id);
    proxy_to_backup(&state.client, "DELETE", &path, None).await
}

async fn proxy_backup_status(
    State(state): State<BackupAppState>,
) -> Result<impl IntoResponse, StatusCode> {
    proxy_to_backup(&state.client, "GET", "/backup/status", None).await
}
