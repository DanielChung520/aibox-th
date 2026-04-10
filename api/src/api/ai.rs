//! AI Router
//!
//! # Description
//! AI 聊天、查詢、知識庫等路由
//!
//! # Last Update: 2026-03-18 03:00:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use crate::error::ApiError;
use axum::{
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};

pub fn create_ai_router() -> Router {
    Router::new()
        .route("/api/v1/ai/chat", post(chat))
        .route("/api/v1/ai/chat/stream", get(chat_stream))
        .route("/api/v1/ai/query", post(query))
        .route("/api/v1/ai/knowledge", post(knowledge))
}

#[derive(Debug, Deserialize)]
pub struct ChatRequest {
    pub message: String,
    pub context_id: Option<String>,
    pub model: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct ChatResponse {
    pub message: String,
    pub context_id: String,
    pub tokens: u32,
}

#[derive(Debug, Deserialize)]
pub struct QueryRequest {
    pub natural_language: String,
    pub collection: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct QueryResponse {
    pub sql: String,
    pub results: Vec<serde_json::Value>,
}

#[derive(Debug, Deserialize)]
pub struct KnowledgeRequest {
    pub query: String,
    pub collection: Option<String>,
    pub limit: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct KnowledgeResponse {
    pub results: Vec<KnowledgeResult>,
}

#[derive(Debug, Serialize)]
pub struct KnowledgeResult {
    pub content: String,
    pub score: f32,
}

async fn chat(Json(req): Json<ChatRequest>) -> Result<impl IntoResponse, ApiError> {
    if req.message.trim().is_empty() {
        return Err(ApiError::bad_request("Message cannot be empty"));
    }

    let context_id = req.context_id.unwrap_or_else(|| "default".to_string());
    
    let response = ChatResponse {
        message: format!("Echo: {}", req.message),
        context_id,
        tokens: req.message.len() as u32 / 4,
    };

    Ok(Json(response))
}

async fn chat_stream() -> Result<axum::response::Response, ApiError> {
    Ok(ApiError::service_unavailable("SSE streaming not implemented yet").into_response())
}

async fn query(Json(req): Json<QueryRequest>) -> Result<impl IntoResponse, ApiError> {
    if req.natural_language.trim().is_empty() {
        return Err(ApiError::bad_request("Query cannot be empty"));
    }

    let response = QueryResponse {
        sql: format!("-- Converted from: {}\nSELECT * FROM users LIMIT 10", req.natural_language),
        results: vec![],
    };

    Ok(Json(response))
}

async fn knowledge(Json(req): Json<KnowledgeRequest>) -> Result<impl IntoResponse, ApiError> {
    if req.query.trim().is_empty() {
        return Err(ApiError::bad_request("Query cannot be empty"));
    }

    let response = KnowledgeResponse {
        results: vec![KnowledgeResult {
            content: format!("Sample knowledge: {}", req.query),
            score: 0.95,
        }],
    };

    Ok(Json(response))
}
