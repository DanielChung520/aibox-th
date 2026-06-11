//! 速率限制中間件
//!
//! # Description
//! 實現滑動窗口算法的速率限制，防止請求頻率過高
//!
//! # Last Update: 2026-03-18 02:25:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use crate::error::ApiError;
use axum::{
    extract::Request,
    http::header::AUTHORIZATION,
    middleware::Next,
    response::Response,
};
use std::{
    collections::HashMap,
    sync::Arc,
    time::{Duration, Instant},
};
use tokio::sync::RwLock;

#[derive(Clone)]
pub struct RateLimitConfig {
    pub max_requests: u32,
    pub window_secs: u64,
}

impl Default for RateLimitConfig {
    fn default() -> Self {
        Self {
            max_requests: 100,
            window_secs: 60,
        }
    }
}

#[derive(Clone)]
pub struct RateLimiter {
    requests: Arc<RwLock<HashMap<String, Vec<Instant>>>>,
    config: RateLimitConfig,
}

impl RateLimiter {
    pub fn new(config: RateLimitConfig) -> Self {
        Self {
            requests: Arc::new(RwLock::new(HashMap::new())),
            config,
        }
    }

    pub async fn check_rate_limit(&self, key: &str) -> Result<(), ApiError> {
        let mut requests = self.requests.write().await;
        let now = Instant::now();
        let window = Duration::from_secs(self.config.window_secs);

        let entry = requests.entry(key.to_string()).or_insert_with(Vec::new);
        
        entry.retain(|&instant| now.duration_since(instant) < window);

        if entry.len() >= self.config.max_requests as usize {
            let retry_after = entry
                .first()
                .map(|first| {
                    let elapsed = now.duration_since(*first);
                    self.config.window_secs.saturating_sub(elapsed.as_secs())
                })
                .unwrap_or(0);

            return Err(ApiError::rate_limited(
                self.config.max_requests,
                self.config.window_secs,
                retry_after,
            ));
        }

        entry.push(now);
        Ok(())
    }
}

pub async fn rate_limit_middleware(
    req: Request,
    next: Next,
) -> Result<Response, ApiError> {
    let rate_limiter = req
        .extensions()
        .get::<RateLimiter>()
        .cloned()
        .unwrap_or_else(|| RateLimiter::new(RateLimitConfig::default()));

    let key = req
        .headers()
        .get(AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .map(|v| v.to_string())
        .unwrap_or_else(|| {
            req.headers()
                .get("x-forwarded-for")
                .and_then(|v| v.to_str().ok())
                .unwrap_or("anonymous")
                .to_string()
        });

    rate_limiter.check_rate_limit(&key).await?;

    Ok(next.run(req).await)
}
