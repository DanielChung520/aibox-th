//! Billing Router
//!
//! # Description
//! 計費相關 API，包含使用量、配額、API Key 管理
//!
//! # Last Update: 2026-03-18 03:05:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use crate::error::ApiError;
use axum::{
    extract::Path,
    response::IntoResponse,
    routing::{delete, get},
    Json, Router,
};
use serde::{Deserialize, Serialize};

pub fn create_billing_router() -> Router {
    Router::new()
        .route("/api/v1/billing/usage", get(get_usage))
        .route("/api/v1/billing/quota", get(get_quota))
        .route("/api/v1/billing/api-keys", get(list_api_keys).post(create_api_key))
        .route("/api/v1/billing/api-keys/{key}", delete(revoke_api_key))
}

#[derive(Debug, Serialize)]
pub struct UsageResponse {
    pub user_key: String,
    pub month: String,
    pub tokens_used: u64,
    pub requests_count: u64,
    pub cost: f64,
}

#[derive(Debug, Serialize)]
pub struct QuotaResponse {
    pub user_key: String,
    pub month: String,
    pub quota: u64,
    pub used: u64,
    pub remaining: u64,
}

#[derive(Debug, Serialize)]
pub struct ApiKeyResponse {
    pub key: String,
    pub name: String,
    pub created_at: String,
    pub expires_at: Option<String>,
    pub status: String,
}

#[derive(Debug, Deserialize)]
pub struct CreateApiKeyRequest {
    pub name: String,
    pub expires_at: Option<String>,
}

async fn get_usage() -> Result<impl IntoResponse, ApiError> {
    let response = UsageResponse {
        user_key: "user123".to_string(),
        month: "2026-03".to_string(),
        tokens_used: 1500,
        requests_count: 100,
        cost: 0.0015,
    };
    Ok(Json(response))
}

async fn get_quota() -> Result<impl IntoResponse, ApiError> {
    let response = QuotaResponse {
        user_key: "user123".to_string(),
        month: "2026-03".to_string(),
        quota: 10000,
        used: 1500,
        remaining: 8500,
    };
    Ok(Json(response))
}

async fn list_api_keys() -> Result<impl IntoResponse, ApiError> {
    let response = vec![ApiKeyResponse {
        key: "ak_xxxxx".to_string(),
        name: "My API Key".to_string(),
        created_at: "2026-03-01T00:00:00Z".to_string(),
        expires_at: None,
        status: "active".to_string(),
    }];
    Ok(Json(response))
}

async fn create_api_key(Json(req): Json<CreateApiKeyRequest>) -> Result<impl IntoResponse, ApiError> {
    let response = ApiKeyResponse {
        key: format!("ak_{}", uuid::Uuid::new_v4()),
        name: req.name,
        created_at: chrono::Utc::now().to_rfc3339(),
        expires_at: req.expires_at,
        status: "active".to_string(),
    };
    Ok(Json(response))
}

async fn revoke_api_key(Path(key): Path<String>) -> Result<impl IntoResponse, ApiError> {
    Ok(Json(serde_json::json!({ "success": true, "key": key })))
}
