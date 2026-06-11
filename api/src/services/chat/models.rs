//! Chat 資料模型模組
//!
//! # Description
//! 定義聊天服務拆分後共用的請求與回應資料結構
//!
//! # Last Update: 2026-04-11 02:38:22
//! # Author: AI Agent
//! # Version: 1.0.0

use std::convert::Infallible;
use std::pin::Pin;

use crate::db::{ChatMessage, ChatSession};
use axum::response::sse::{Event, Sse};
use serde::{Deserialize, Serialize};

pub type ChatEventStream =
    Pin<Box<dyn tokio_stream::Stream<Item = Result<Event, Infallible>> + Send>>;
pub type ChatSse = Sse<ChatEventStream>;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionWithMessages {
    pub session: ChatSession,
    pub messages: Vec<ChatMessage>,
}

#[derive(Debug, Clone)]
pub struct ChatDefaults {
    pub default_provider: String,
    pub default_model: String,
    pub temperature: f64,
    pub max_tokens: i32,
    pub system_prompt: String,
    pub max_history_messages: usize,
}

#[derive(Debug, Clone, Deserialize)]
pub struct FileStatusWebhookPayload {
    pub file_key: String,
    pub vector_status: Option<String>,
    pub graph_status: Option<String>,
    pub failed_reason: Option<String>,
    pub graph_stats: Option<serde_json::Value>,
}
