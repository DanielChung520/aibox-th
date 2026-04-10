#![allow(dead_code, unused_imports)]
#![allow(clippy::single_component_path_imports)]

//! Main entry point
//!
//! # Description
//! ABC Desktop API 服務入口
//!
//! # Last Update: 2026-03-17 15:00:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

mod api;
mod auth;
mod db;
mod models;

mod error;
mod config;
mod middleware;
mod services;
mod duckdb_conn;

use api::create_router;
use std::net::SocketAddr;

#[tokio::main]
async fn main() {
    dotenvy::dotenv().ok();

    if let Err(e) = db::init().await {
        eprintln!("Failed to initialize ArangoDB: {e}");
        std::process::exit(1);
    }
    println!("ArangoDB initialized");

    if let Err(e) = duckdb_conn::init() {
        eprintln!("Failed to initialize DuckDB: {e}");
        std::process::exit(1);
    }
    println!("DuckDB initialized (in-memory + S3)");

    let app = create_router();
    let port: u16 = std::env::var("PORT")
        .unwrap_or_else(|_| "3001".into())
        .parse()
        .unwrap_or(3001);
    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    println!("API server running on http://{addr}");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
