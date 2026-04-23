//! 庫導出模組
//!
//! # Description
//! 導出所有模組，包含錯誤處理、配置、認證、中間件、API、數據庫等
//!
//! # Last Update: 2026-03-18 02:30:00
//! # Author: Daniel Chung
//! # Version: 1.0.0
//!
//! ## History
//! - 2026-03-18 02:30:00 | Daniel Chung | 1.0.0 | 初始版本，實現庫導出模組

pub mod api;
pub mod auth;
pub mod config;
pub mod db;
pub mod duckdb_conn;
pub mod table_cache;
pub mod error;
pub mod middleware;
pub mod models;
pub mod services;

pub use api::create_router;
pub use config::Config;
pub use error::{ApiError, Result};
