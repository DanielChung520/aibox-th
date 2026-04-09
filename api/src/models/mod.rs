//! Models Module
//!
//! # Description
//! 數據模型
//!
//! # Last Update: 2026-03-17 15:00:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

pub mod auth;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoginRequest {
    pub username: String,
    pub password: String,
    pub remember: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoginResponse {
    pub token: String,
    pub user: UserInfo,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserInfo {
    pub _key: String,
    pub username: String,
    pub name: String,
    pub role_keys: Vec<String>,
    pub role_names: Vec<String>,
    pub tier: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiResponse<T> {
    pub code: i32,
    pub message: String,
    pub data: Option<T>,
}

impl<T> ApiResponse<T> {
    pub fn success(data: T) -> Self {
        Self {
            code: 200,
            message: "success".to_string(),
            data: Some(data),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateUserRequest {
    pub name: Option<String>,
    pub role_keys: Option<Vec<String>>,
    pub status: Option<String>,
    pub tier: Option<String>,
    pub password_hash: Option<String>,
}
