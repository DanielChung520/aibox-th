//! Chat API 模組
//!
//! # Description
//! 聊天 Session CRUD、SSE 串流代理、5W1H 非同步標記
//!
//! # Last Update: 2026-04-11 02:46:07
//! # Author: AI Agent
//! # Version: 1.4.0

use axum::extract::{Multipart, Path};
use axum::http::{HeaderMap, StatusCode};
use axum::routing::{get, post};
use axum::{Json, Router};

use crate::db::{get_db, ChatSession, CreateSessionRequest, UpdateSessionRequest};
use crate::models::ApiResponse;
use crate::services::chat::{clients, files, orchestrator, *};

pub fn create_chat_router() -> Router {
    Router::new()
        .route("/api/v1/chat/sessions", post(create_session).get(list_sessions))
        .route("/api/v1/chat/sessions/{key}", get(get_session).put(update_session).delete(delete_session))
        .route("/api/v1/chat/sessions/{key}/messages", post(send_message))
        .route("/api/v1/chat/sessions/{key}/files", post(upload_session_file).get(list_session_files).delete(delete_session_file))
        .route("/api/v1/chat/sessions/{key}/files/status-webhook", post(file_status_webhook))
}

async fn create_session(headers: HeaderMap, Json(payload): Json<CreateSessionRequest>) -> Result<Json<ApiResponse<ChatSession>>, StatusCode> {
    let db = get_db();
    let defaults = load_chat_defaults(db).await?;
    let now = chrono::Utc::now().to_rfc3339();
    let session = ChatSession {
        _key: Some(uuid::Uuid::new_v4().to_string()),
        title: None,
        provider: payload
            .provider
            .unwrap_or_else(|| defaults.default_provider.clone()),
        model: payload.model.unwrap_or_else(|| defaults.default_model.clone()),
        status: "active".to_string(),
        tags_5w1h: None,
        user_key: extract_user_key_from_headers(&headers),
        created_at: now.clone(),
        updated_at: now,
    };
    create_session_doc(db, session.clone()).await?;
    Ok(Json(ApiResponse::success(session)))
}

async fn list_sessions(headers: HeaderMap) -> Result<Json<ApiResponse<Vec<ChatSession>>>, StatusCode> {
    let db = get_db();
    Ok(Json(ApiResponse::success(list_sessions_for_user(db, &extract_user_key_from_headers(&headers)).await?)))
}

async fn get_session(headers: HeaderMap, Path(key): Path<String>) -> Result<Json<ApiResponse<SessionWithMessages>>, StatusCode> {
    let db = get_db();
    Ok(Json(ApiResponse::success(get_session_with_messages(db, &key, &extract_user_key_from_headers(&headers)).await?)))
}

async fn update_session(Path(key): Path<String>, Json(payload): Json<UpdateSessionRequest>) -> Result<Json<ApiResponse<ChatSession>>, StatusCode> {
    Ok(Json(ApiResponse::success(update_session_doc(get_db(), &key, payload).await?)))
}

async fn delete_session(headers: HeaderMap, Path(key): Path<String>) -> Result<Json<ApiResponse<String>>, StatusCode> {
    let db = get_db();
    let user_key = extract_user_key_from_headers(&headers);
    let sessions: Vec<ChatSession> = db
        .aql_bind_vars(
            "FOR s IN chat_sessions FILTER s._key == @key AND s.user_key == @user_key RETURN s",
            [("key", serde_json::json!(key.clone())), ("user_key", serde_json::json!(user_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    if sessions.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    let file_keys: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR e IN chat_session_files FILTER e.session_key == @key RETURN e.file_key",
            [("key", serde_json::json!(key.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    for file in &file_keys {
        if let Some(file_key) = file.as_str().filter(|value| !value.is_empty()) {
            let _ = clients::call_knowledge_delete(file_key).await;
        }
    }

    let _: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR e IN chat_session_files FILTER e.session_key == @key REMOVE e IN chat_session_files",
            [("key", serde_json::json!(key.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let _: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR m IN chat_messages FILTER m.session_key == @key REMOVE m IN chat_messages",
            [("key", serde_json::json!(key.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let _ = clients::call_qdrant_delete_collection(&key).await;
    let _ = clients::call_seaweedfs_delete_session(&key).await;
    let _ = tokio::fs::remove_dir_all(std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from(".")).join("data/uploads/sessions").join(&key)).await;

    db.collection("chat_sessions")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .remove_document::<serde_json::Value>(&key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;

    Ok(Json(ApiResponse::success("Session deleted".to_string())))
}

async fn send_message(headers: HeaderMap, Path(session_key): Path<String>, Json(payload): Json<crate::db::SendMessageRequest>) -> Result<ChatSse, StatusCode> {
    orchestrator::handle_send_message(headers, session_key, payload).await
}

async fn upload_session_file(Path(session_key): Path<String>, multipart: Multipart) -> Result<Json<ApiResponse<serde_json::Value>>, StatusCode> {
    files::handle_upload_session_file(session_key, multipart).await
}

async fn list_session_files(Path(session_key): Path<String>) -> Result<Json<ApiResponse<Vec<serde_json::Value>>>, StatusCode> {
    files::handle_list_session_files(session_key).await
}

async fn delete_session_file(Path((session_key, file_key)): Path<(String, String)>) -> Result<Json<ApiResponse<String>>, StatusCode> {
    files::handle_delete_session_file(session_key, file_key).await
}

async fn file_status_webhook(Path(session_key): Path<String>, Json(payload): Json<FileStatusWebhookPayload>) -> Result<Json<ApiResponse<serde_json::Value>>, StatusCode> {
    files::handle_file_status_webhook(session_key, payload).await
}
