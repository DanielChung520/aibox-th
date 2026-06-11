//! Ragic Table Cache Module (DuckDB persistent)
//!
//! # Description
//! 將 Ragic 資料 cache 到本地 DuckDB 檔案，透過 worker thread 避免
//! DuckDB Connection 非 Send/Sync 的限制。
//! 設計為獨立模組，未來可拆為 library crate 供 PyO3 包裝。
//!
//! # Last Update: 2026-04-16 10:35:20
//! # Author: Daniel Chung
//! # Version: 1.0.0

mod worker;

use once_cell::sync::OnceCell;
use serde::{Deserialize, Serialize};
use tokio::sync::{mpsc, oneshot};

static CACHE: OnceCell<TableCacheHandle> = OnceCell::new();

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheMeta {
    pub table_id: String,
    pub row_count: i64,
    pub cached_at: String,
}

pub(crate) enum CacheCmd {
    Store {
        table_id: String,
        rows_json: String,
        reply: oneshot::Sender<Result<CacheMeta, String>>,
    },
    Query {
        table_id: String,
        offset: i64,
        limit: i64,
        reply: oneshot::Sender<Result<(Vec<serde_json::Value>, i64), String>>,
    },
    HasTable {
        table_id: String,
        reply: oneshot::Sender<bool>,
    },
    Drop {
        table_id: String,
        reply: oneshot::Sender<Result<(), String>>,
    },
}

#[derive(Clone)]
pub struct TableCacheHandle {
    tx: mpsc::Sender<CacheCmd>,
}

impl TableCacheHandle {
    pub async fn store(
        &self,
        table_id: &str,
        rows: &[serde_json::Value],
    ) -> Result<CacheMeta, String> {
        let rows_json =
            serde_json::to_string(rows).map_err(|e| format!("JSON serialize: {e}"))?;
        let (reply, rx) = oneshot::channel();
        self.tx
            .send(CacheCmd::Store {
                table_id: table_id.to_string(),
                rows_json,
                reply,
            })
            .await
            .map_err(|_| "cache worker gone".to_string())?;
        rx.await.map_err(|_| "cache reply dropped".to_string())?
    }

    pub async fn query(
        &self,
        table_id: &str,
        offset: i64,
        limit: i64,
    ) -> Result<(Vec<serde_json::Value>, i64), String> {
        let (reply, rx) = oneshot::channel();
        self.tx
            .send(CacheCmd::Query {
                table_id: table_id.to_string(),
                offset,
                limit,
                reply,
            })
            .await
            .map_err(|_| "cache worker gone".to_string())?;
        rx.await.map_err(|_| "cache reply dropped".to_string())?
    }

    pub async fn has_table(&self, table_id: &str) -> bool {
        let (reply, rx) = oneshot::channel();
        let _ = self
            .tx
            .send(CacheCmd::HasTable {
                table_id: table_id.to_string(),
                reply,
            })
            .await;
        rx.await.unwrap_or(false)
    }

    pub async fn drop_table(&self, table_id: &str) -> Result<(), String> {
        let (reply, rx) = oneshot::channel();
        self.tx
            .send(CacheCmd::Drop {
                table_id: table_id.to_string(),
                reply,
            })
            .await
            .map_err(|_| "cache worker gone".to_string())?;
        rx.await.map_err(|_| "cache reply dropped".to_string())?
    }
}

pub fn init() -> Result<(), String> {
    let db_path = std::env::var("TABLE_CACHE_PATH")
        .unwrap_or_else(|_| "./data/table_cache.duckdb".to_string());

    if let Some(parent) = std::path::Path::new(&db_path).parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Cannot create data dir: {e}"))?;
    }

    let (tx, rx) = mpsc::channel::<CacheCmd>(256);
    let handle = TableCacheHandle { tx };

    std::thread::spawn(move || {
        worker::run(db_path, rx);
    });

    CACHE
        .set(handle)
        .map_err(|_| "TableCache already initialized".to_string())?;

    println!("TableCache initialized (DuckDB file-based)");
    Ok(())
}

pub fn get_cache() -> &'static TableCacheHandle {
    CACHE.get().expect("TableCache not initialized")
}
