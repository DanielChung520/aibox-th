//! DuckDB Connection Factory Module
//!
//! # Description
//! 提供 DuckDB file-backed 連線工廠，連線至 table_cache.duckdb。
//! 每次查詢建立獨立連線，避免 singleton 模式下 Mutex poisoned 問題。
//!
//! # Last Update: 2026-04-16 18:10:00
//! # Author: Daniel Chung
//! # Version: 2.0.0

use once_cell::sync::OnceCell;

static DB_PATH: OnceCell<String> = OnceCell::new();

/// Initialize DuckDB connection factory with the table_cache.duckdb path.
pub fn init() -> Result<(), String> {
    let db_path = std::env::var("TABLE_CACHE_PATH")
        .unwrap_or_else(|_| "./data/table_cache.duckdb".to_string());

    if let Some(parent) = std::path::Path::new(&db_path).parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("Cannot create data dir: {e}"))?;
    }

    let conn =
        duckdb::Connection::open(&db_path).map_err(|e| format!("DuckDB open failed: {e}"))?;
    conn.execute_batch("SELECT 1;")
        .map_err(|e| format!("DuckDB health check failed: {e}"))?;

    DB_PATH
        .set(db_path)
        .map_err(|_| "DuckDB path already initialized".to_string())
}

/// Create a fresh DuckDB connection to the file-backed table_cache.duckdb.
/// Each call returns an independent connection — no shared state, no mutex.
pub fn create_connection() -> Result<duckdb::Connection, String> {
    let db_path = DB_PATH
        .get()
        .ok_or_else(|| "DuckDB not initialized (call init first)".to_string())?;

    let conn = duckdb::Connection::open(db_path).map_err(|e| format!("DuckDB open failed: {e}"))?;

    Ok(conn)
}
