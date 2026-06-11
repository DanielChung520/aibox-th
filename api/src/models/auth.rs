//! 認證模型
//!
//! # Description
//! 定義認證相關的數據結構，包括 JWT Claims、ApiKey、用戶權限等
//!
//! # Last Update: 2026-03-18 02:10:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,
    pub username: String,
    pub role: String,
    pub permissions: Vec<String>,
    pub exp: u64,
    pub iat: u64,
}

impl Claims {
    pub fn new(
        user_key: &str,
        username: &str,
        role: &str,
        permissions: Vec<String>,
        exp: u64,
        iat: u64,
    ) -> Self {
        Self {
            sub: user_key.to_string(),
            username: username.to_string(),
            role: role.to_string(),
            permissions,
            exp,
            iat,
        }
    }

    pub fn is_expired(&self) -> bool {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        self.exp < now
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKey {
    pub key: String,
    pub user_key: String,
    pub name: String,
    pub rate_limit: u32,
    pub monthly_quota: u64,
    pub scopes: Vec<String>,
    pub expires_at: Option<DateTime<Utc>>,
    pub created_at: DateTime<Utc>,
    pub last_used_at: Option<DateTime<Utc>>,
    pub status: ApiKeyStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ApiKeyStatus {
    Active,
    Revoked,
    Expired,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateApiKeyRequest {
    pub name: String,
    pub rate_limit: Option<u32>,
    pub monthly_quota: Option<u64>,
    pub scopes: Vec<String>,
    pub expires_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateApiKeyResponse {
    pub key: String,
    pub name: String,
    pub expires_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Permission {
    pub resource: String,
    pub actions: Vec<String>,
}

pub const SCOPE_AI_CHAT: &str = "ai.chat";
pub const SCOPE_AI_QUERY: &str = "ai.query";
pub const SCOPE_AI_KNOWLEDGE: &str = "ai.knowledge";
pub const SCOPE_AI_MCP: &str = "ai.mcp";
pub const SCOPE_AI_BPA: &str = "ai.bpa";
pub const SCOPE_BILLING: &str = "billing";
pub const SCOPE_ADMIN: &str = "admin";
