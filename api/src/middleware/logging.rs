//! 日誌中間件
//!
//! # Description
//! 實現請求日誌記錄，按照規格書 11.2 日誌格式記錄請求資訊
//!
//! # Last Update: 2026-03-18 02:20:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use axum::{
    extract::Request,
    middleware::Next,
    response::Response,
};
use chrono::Utc;
use serde::Serialize;
use std::time::Instant;

#[derive(Debug, Serialize)]
pub struct RequestLog {
    pub timestamp: String,
    pub level: String,
    pub service: String,
    pub action: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_key: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub latency_ms: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tokens: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cost: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status_code: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

impl RequestLog {
    pub fn new(action: &str) -> Self {
        Self {
            timestamp: Utc::now().to_rfc3339(),
            level: "info".to_string(),
            service: "gateway".to_string(),
            action: action.to_string(),
            user_key: None,
            latency_ms: None,
            tokens: None,
            cost: None,
            status_code: None,
            error: None,
        }
    }

    pub fn with_user(mut self, user_key: &str) -> Self {
        self.user_key = Some(user_key.to_string());
        self
    }

    pub fn with_latency(mut self, latency_ms: u64) -> Self {
        self.latency_ms = Some(latency_ms);
        self
    }

    pub fn with_status(mut self, status: u16) -> Self {
        self.status_code = Some(status);
        if status >= 400 {
            self.level = "error".to_string();
        }
        self
    }

    pub fn with_error(mut self, error: &str) -> Self {
        self.error = Some(error.to_string());
        self.level = "error".to_string();
        self
    }

    pub fn log(&self) {
        if let Ok(json) = serde_json::to_string(self) {
            println!("{}", json);
        }
    }
}

pub async fn logging_middleware(
    req: Request,
    next: Next,
) -> Response {
    let start = Instant::now();
    let method = req.method().clone();
    let path = req.uri().path().to_string();
    let action = format!("{} {}", method, path);

    let user_key = req
        .extensions()
        .get::<crate::auth::Claims>()
        .map(|c| c.sub.clone());

    let response = next.run(req).await;
    let latency_ms = start.elapsed().as_millis() as u64;
    let status = response.status().as_u16();

    let mut log_entry = RequestLog::new(&action);
    log_entry = log_entry.with_latency(latency_ms).with_status(status);

    if let Some(key) = user_key {
        log_entry = log_entry.with_user(&key);
    }

    log_entry.log();

    response
}
