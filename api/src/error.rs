//! 錯誤類型定義
//!
//! # Description
//! 定義 API 錯誤類型，包含錯誤碼、錯誤訊息和錯誤處理
//!
//! # Last Update: 2026-03-18 02:00:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct ApiError {
    pub code: u16,
    pub error: String,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub details: Option<serde_json::Value>,
}

impl ApiError {
    pub fn new(status: StatusCode, error: &str, message: &str) -> Self {
        Self {
            code: status.as_u16(),
            error: error.to_string(),
            message: message.to_string(),
            details: None,
        }
    }

    pub fn with_details(mut self, details: serde_json::Value) -> Self {
        self.details = Some(details);
        self
    }

    pub fn bad_request(message: &str) -> Self {
        Self::new(StatusCode::BAD_REQUEST, "BAD_REQUEST", message)
    }

    pub fn unauthorized(message: &str) -> Self {
        Self::new(StatusCode::UNAUTHORIZED, "UNAUTHORIZED", message)
    }

    pub fn forbidden(message: &str) -> Self {
        Self::new(StatusCode::FORBIDDEN, "FORBIDDEN", message)
    }

    pub fn rate_limited(limit: u32, window: u64, retry_after: u64) -> Self {
        Self::new(StatusCode::TOO_MANY_REQUESTS, "RATE_LIMITED", "請求頻率超限，請稍後再試")
            .with_details(serde_json::json!({
                "limit": limit,
                "window": window,
                "retry_after": retry_after
            }))
    }

    pub fn quota_exceeded() -> Self {
        Self::new(
            StatusCode::UNAUTHORIZED,
            "QUOTA_EXCEEDED",
            "超出配額限制，請升級或聯繫管理員",
        )
    }

    pub fn bad_gateway(message: &str) -> Self {
        Self::new(StatusCode::BAD_GATEWAY, "BAD_GATEWAY", message)
    }

    pub fn service_unavailable(message: &str) -> Self {
        Self::new(StatusCode::SERVICE_UNAVAILABLE, "SERVICE_UNAVAILABLE", message)
    }

    pub fn not_found(resource: &str) -> Self {
        Self::new(StatusCode::NOT_FOUND, "NOT_FOUND", &format!("{} 不存在", resource))
    }

    pub fn internal_error(message: &str) -> Self {
        Self::new(StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", message)
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (StatusCode::from_u16(self.code).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR), Json(self)).into_response()
    }
}

pub type Result<T> = std::result::Result<T, ApiError>;
