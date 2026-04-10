//! Billing Service
//!
//! # Description
//! 計費服務，負責記錄使用量、檢查配額、計算費用
//!
//! # Last Update: 2026-03-18 03:25:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use crate::error::ApiError;

pub struct BillingService {
    free_tokens_per_month: u64,
    price_per_1k_tokens: f64,
}

impl BillingService {
    pub fn new(free_tokens: u64, price_per_1k: f64) -> Self {
        Self {
            free_tokens_per_month: free_tokens,
            price_per_1k_tokens: price_per_1k,
        }
    }

    pub fn check_quota(&self, _user_key: &str, tokens_used: u64) -> Result<u64, ApiError> {
        let remaining = self.free_tokens_per_month.saturating_sub(tokens_used);

        if remaining == 0 {
            return Err(ApiError::quota_exceeded());
        }

        Ok(remaining)
    }

    pub fn calculate_cost(&self, tokens: u64) -> f64 {
        (tokens as f64 / 1000.0) * self.price_per_1k_tokens
    }

    pub fn record_usage(
        &self,
        user_key: &str,
        tokens: u64,
        request_type: &str,
    ) -> Result<(), ApiError> {
        tracing::info!(
            "Usage recorded: user={}, tokens={}, type={}",
            user_key,
            tokens,
            request_type
        );

        let cost = self.calculate_cost(tokens);
        tracing::info!("Cost calculated: ${:.4}", cost);

        Ok(())
    }

    pub fn get_usage(&self, user_key: &str, month: &str) -> UsageInfo {
        UsageInfo {
            user_key: user_key.to_string(),
            month: month.to_string(),
            tokens_used: 0,
            requests_count: 0,
            cost: 0.0,
        }
    }
}

impl Default for BillingService {
    fn default() -> Self {
        Self::new(10000, 0.001)
    }
}

#[derive(Debug, Clone)]
pub struct UsageInfo {
    pub user_key: String,
    pub month: String,
    pub tokens_used: u64,
    pub requests_count: u64,
    pub cost: f64,
}
