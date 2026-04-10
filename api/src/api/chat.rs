//! Chat API 模組
//!
//! # Description
//! 聊天 Session CRUD、SSE 串流代理、5W1H 非同步標記
//!
//! # Last Update: 2026-03-27 15:50:00
//! # Author: Daniel Chung
//! # Version: 1.1.0

use std::collections::VecDeque;
use std::convert::Infallible;
use std::pin::Pin;
use std::sync::Arc;

use axum::extract::{Multipart, Path};
use axum::http::{HeaderMap, StatusCode};
use axum::response::sse::{Event, Sse};
use axum::routing::{get, post};
use axum::{Json, Router};
use futures::{Stream, StreamExt};
use tokio::sync::mpsc;

use crate::db::{
    get_db, ChatMessage, ChatSession, CreateSessionRequest, ModelProvider, SendMessageRequest,
    SystemParam, UpdateSessionRequest,
};
use crate::models::ApiResponse;
use crate::auth::{verify_jwt, Claims};
use crate::api::sse::broadcast_file_status_event;
use crate::api::intent::{
    route_tool_intent, sse_text_to_stream, summarize_text, ToolIntentResult,
};

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
struct SessionWithMessages {
    session: ChatSession,
    messages: Vec<ChatMessage>,
}

#[derive(Debug, Clone)]
struct ChatDefaults {
    default_provider: String,
    default_model: String,
    temperature: f64,
    max_tokens: i32,
    system_prompt: String,
    max_history_messages: usize,
}

fn extract_user_key_from_headers(headers: &HeaderMap) -> String {
    headers
        .get(axum::http::header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .and_then(|token| verify_jwt(token).ok())
        .map(|data| data.claims.sub)
        .unwrap_or_else(|| "anonymous".to_string())
}

pub fn create_chat_router() -> Router {
    Router::new()
        .route("/api/v1/chat/sessions", post(create_session).get(list_sessions))
        .route(
            "/api/v1/chat/sessions/{key}",
            get(get_session).put(update_session).delete(delete_session),
        )
        .route(
            "/api/v1/chat/sessions/{key}/messages",
            post(send_message),
        )
        .route(
            "/api/v1/chat/sessions/{key}/files",
            post(upload_session_file).get(list_session_files).delete(delete_session_file),
        )
        .route(
            "/api/v1/chat/sessions/{key}/files/status-webhook",
            post(file_status_webhook),
        )
}

async fn create_session(
    headers: HeaderMap,
    Json(payload): Json<CreateSessionRequest>,
) -> Result<Json<ApiResponse<ChatSession>>, StatusCode> {
    let db = get_db();
    let defaults = load_chat_defaults(db).await?;
    let key = uuid::Uuid::new_v4().to_string();
    let now = chrono::Utc::now().to_rfc3339();

    let user_key = extract_user_key_from_headers(&headers);

    let session = ChatSession {
        _key: Some(key),
        title: None,
        provider: payload
            .provider
            .unwrap_or_else(|| defaults.default_provider.clone()),
        model: payload.model.unwrap_or_else(|| defaults.default_model.clone()),
        status: "active".to_string(),
        tags_5w1h: None,
        user_key,
        created_at: now.clone(),
        updated_at: now,
    };

    let col = db
        .collection("chat_sessions")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(session.clone(), Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(session)))
}

async fn list_sessions(
    headers: HeaderMap,
) -> Result<Json<ApiResponse<Vec<ChatSession>>>, StatusCode> {
    let db = get_db();
    let user_key = extract_user_key_from_headers(&headers);
    let sessions: Vec<ChatSession> = db
        .aql_bind_vars(
            "FOR s IN chat_sessions FILTER s.user_key == @user_key SORT s.updated_at DESC RETURN s",
            [("user_key", serde_json::json!(user_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(sessions)))
}

async fn get_session(
    headers: HeaderMap,
    Path(key): Path<String>,
) -> Result<Json<ApiResponse<SessionWithMessages>>, StatusCode> {
    let db = get_db();
    let user_key = extract_user_key_from_headers(&headers);

    let mut sessions: Vec<ChatSession> = db
        .aql_bind_vars(
            "FOR s IN chat_sessions FILTER s._key == @key AND s.user_key == @user_key LIMIT 1 RETURN s",
            [("key", serde_json::json!(key.clone())), ("user_key", serde_json::json!(user_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let session = sessions.pop().ok_or(StatusCode::NOT_FOUND)?;

    let messages: Vec<ChatMessage> = db
        .aql_bind_vars(
            "FOR m IN chat_messages FILTER m.session_key == @key SORT m.created_at ASC RETURN m",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(SessionWithMessages {
        session,
        messages,
    })))
}

async fn update_session(
    Path(key): Path<String>,
    Json(payload): Json<UpdateSessionRequest>,
) -> Result<Json<ApiResponse<ChatSession>>, StatusCode> {
    let db = get_db();
    let col = db
        .collection("chat_sessions")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut patch = serde_json::Map::new();
    if let Some(title) = payload.title {
        patch.insert("title".to_string(), serde_json::json!(title));
    }
    if let Some(status) = payload.status {
        patch.insert("status".to_string(), serde_json::json!(status));
    }
    if let Some(tags_5w1h) = payload.tags_5w1h {
        patch.insert("tags_5w1h".to_string(), tags_5w1h);
    }
    patch.insert(
        "updated_at".to_string(),
        serde_json::json!(chrono::Utc::now().to_rfc3339()),
    );

    col.update_document(&key, serde_json::Value::Object(patch), Default::default())
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;

    let mut sessions: Vec<ChatSession> = db
        .aql_bind_vars(
            "FOR s IN chat_sessions FILTER s._key == @key LIMIT 1 RETURN s",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let session = sessions.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(session)))
}

async fn delete_session(
    headers: HeaderMap,
    Path(key): Path<String>,
) -> Result<Json<ApiResponse<String>>, StatusCode> {
    let db = get_db();
    let user_key = extract_user_key_from_headers(&headers);
    let client = reqwest::Client::new();

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

    let agent_url =
        std::env::var("KNOWLEDGE_AGENT_URL").unwrap_or_else(|_| "http://localhost:8007".to_string());

    for file in &file_keys {
        let file_key = file.as_str().unwrap_or_default();
        if !file_key.is_empty() {
            let _ = client
                .post(format!("{}/pipeline/delete?file_id={}", agent_url, file_key))
                .timeout(std::time::Duration::from_secs(30))
                .send()
                .await;
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

    let qdrant_url = std::env::var("QDRANT_URL").unwrap_or_else(|_| "http://localhost:6333".to_string());
    let qdrant_collection = format!("knowledge_{}", key);
    let _ = client
        .delete(format!(
            "{}/collections/{}",
            qdrant_url, qdrant_collection
        ))
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;

    let seaweed_user = std::env::var("SEAWEED_USER").unwrap_or_else(|_| "admin".to_string());
    let seaweed_pass = std::env::var("SEAWEED_PASS").unwrap_or_else(|_| "admin123".to_string());
    let seaweed_base = std::env::var("SEAWEED_AIBOX_URL").unwrap_or_else(|_| "http://localhost:8888".to_string());
    let _ = client
        .delete(format!(
            "{}/bucket-aibox-assets/sessions/{}",
            seaweed_base, key
        ))
        .basic_auth(&seaweed_user, Some(&seaweed_pass))
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;

    let local_dir = std::env::current_dir()
        .unwrap_or_else(|_| std::path::PathBuf::from("."))
        .join("data/uploads/sessions")
        .join(&key);
    let _ = tokio::fs::remove_dir_all(&local_dir).await;

    let col = db
        .collection("chat_sessions")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<serde_json::Value>(&key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;

    Ok(Json(ApiResponse::success("Session deleted".to_string())))
}

async fn send_message(
    headers: HeaderMap,
    Path(session_key): Path<String>,
    Json(payload): Json<SendMessageRequest>,
) -> Result<Sse<impl tokio_stream::Stream<Item = Result<Event, Infallible>>>, StatusCode> {
    if payload.content.trim().is_empty() {
        return Err(StatusCode::BAD_REQUEST);
    }

    let db = get_db();
    let user_key = extract_user_key_from_headers(&headers);

    let mut sessions: Vec<ChatSession> = db
        .aql_bind_vars(
            "FOR s IN chat_sessions FILTER s._key == @key AND s.user_key == @user_key LIMIT 1 RETURN s",
            [("key", serde_json::json!(session_key.clone())), ("user_key", serde_json::json!(user_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let session = sessions.pop().ok_or(StatusCode::NOT_FOUND)?;

    let defaults = load_chat_defaults(db).await?;
    let provider = payload
        .provider
        .clone()
        .unwrap_or_else(|| session.provider.clone());
    let model = payload
        .model
        .clone()
        .unwrap_or_else(|| session.model.clone());
    let temperature = payload.temperature.unwrap_or(defaults.temperature);
    let max_tokens = payload.max_tokens.unwrap_or(defaults.max_tokens);

    let providers_raw: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR p IN model_providers FILTER p.code == @code LIMIT 1 RETURN p",
            [("code", serde_json::json!(provider.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let providers: Vec<ModelProvider> = providers_raw
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();
    let provider_info = providers.into_iter().next().ok_or(StatusCode::BAD_REQUEST)?;

    let user_msg = ChatMessage {
        _key: Some(uuid::Uuid::new_v4().to_string()),
        session_key: session_key.clone(),
        role: "user".to_string(),
        content: payload.content.clone(),
        tokens: None,
        created_at: chrono::Utc::now().to_rfc3339(),
    };

    let msg_col = db
        .collection("chat_messages")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    msg_col
        .create_document(user_msg, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let history_all: Vec<ChatMessage> = db
        .aql_bind_vars(
            "FOR m IN chat_messages FILTER m.session_key == @key SORT m.created_at ASC RETURN m",
            [("key", serde_json::json!(session_key.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let history_len = history_all.len();
    let history: Vec<ChatMessage> = if history_len > defaults.max_history_messages {
        history_all
            .into_iter()
            .skip(history_len.saturating_sub(defaults.max_history_messages))
            .collect()
    } else {
        history_all
    };

    let mut messages: Vec<serde_json::Value> = vec![serde_json::json!({
        "role": "system",
        "content": defaults.system_prompt,
    })];

    let history_for_intent: Vec<serde_json::Value> = history
        .iter()
        .map(|m| {
            serde_json::json!({
                "role": m.role,
                "content": m.content,
            })
        })
        .collect();

    for m in &history {
        messages.push(serde_json::json!({
            "role": m.role,
            "content": m.content,
        }));
    }

    let aitask_url =
        std::env::var("AITASK_URL").unwrap_or_else(|_| "http://localhost:8001".to_string());
    let client = reqwest::Client::new();
    let aitask_body = serde_json::json!({
        "messages": messages,
        "model": model,
        "stream": true,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "provider": provider,
        "provider_base_url": provider_info.base_url,
    });

    let response = client
        .post(format!("{}/v1/chat/completions", aitask_url))
        .json(&aitask_body)
        .send()
        .await
        .map_err(|_| StatusCode::BAD_GATEWAY)?;

    if !response.status().is_success() {
        return Err(StatusCode::BAD_GATEWAY);
    }

    let (tx, mut rx) = mpsc::unbounded_channel::<String>();
    let session_key_clone = session_key.clone();

    tokio::spawn(async move {
        let mut full_content = String::new();
        while let Some(chunk) = rx.recv().await {
            full_content.push_str(&chunk);
        }
        if full_content.is_empty() {
            return;
        }

        let db = get_db();
        let msg = ChatMessage {
            _key: Some(uuid::Uuid::new_v4().to_string()),
            session_key: session_key_clone.clone(),
            role: "assistant".to_string(),
            content: full_content,
            tokens: None,
            created_at: chrono::Utc::now().to_rfc3339(),
        };

        if let Ok(col) = db.collection("chat_messages").await {
            let _ = col.create_document(msg, Default::default()).await;
        }

        spawn_5w1h_tagging(session_key_clone).await;
    });

    let enable_intent_router =
        std::env::var("INTENT_ROUTER_ENABLED").unwrap_or_else(|_| "true".into());

    if enable_intent_router == "true" {
        let ollama_base_url = if provider == "ollama" {
            provider_info.base_url.clone()
        } else {
            std::env::var("OLLAMA_BASE_URL").unwrap_or_else(|_| "http://localhost:11434".into())
        };

        let intent_rag_url =
            std::env::var("INTENT_RAG_URL").unwrap_or_else(|_| "http://localhost:8003".into());
        let mcp_tools_url =
            std::env::var("MCP_TOOLS_URL").unwrap_or_else(|_| "http://localhost:8004".into());

        // Get Intent Router specific model (faster model for parameter extraction)
        let intent_model = {
            let params: Vec<SystemParam> = db
                .aql_str("FOR p IN system_params FILTER p.param_key == \"intent.extraction_model\" RETURN p")
                .await
                .unwrap_or_default();
            params.first()
                .map(|p| p.param_value.clone())
                .unwrap_or_else(|| "deepseek-v3.1:671b-cloud".to_string())
        };

        let tool_result = route_tool_intent(
            &client,
            &intent_rag_url,
            &mcp_tools_url,
            &ollama_base_url,
            &intent_model,
            &payload.content,
            &history_for_intent,
        )
        .await;

        if let Ok(Some(ToolIntentResult {
            tool_name,
            result: tool_data,
            ..
        })) = tool_result
        {
            let ollama_url_for_tool = ollama_base_url.clone();
            let model_for_tool = model.clone();
            let user_msg_for_tool = payload.content.clone();
            let sk_for_tool = session_key.clone();

            let sse_text = summarize_text(
                &client,
                &ollama_url_for_tool,
                &model_for_tool,
                &user_msg_for_tool,
                &tool_name,
                &tool_data,
                &history_for_intent,
            )
            .await;

            if let Ok(sse_text) = sse_text {
                let sk_persist = session_key.clone();
                let text_for_persist = sse_text.clone();

                tokio::spawn(async move {
                    let db = get_db();
                    let mut full_content = String::new();
                    for line in text_for_persist.lines() {
                        if let Ok(data) = serde_json::from_str::<serde_json::Value>(line) {
                            if let Some(c) = data.get("response").and_then(|v| v.as_str()) {
                                full_content.push_str(c);
                            }
                        }
                    }
                    if full_content.is_empty() {
                        return;
                    }
                    let msg = ChatMessage {
                        _key: Some(uuid::Uuid::new_v4().to_string()),
                        session_key: sk_persist.clone(),
                        role: "assistant".to_string(),
                        content: full_content.clone(),
                        tokens: None,
                        created_at: chrono::Utc::now().to_rfc3339(),
                    };
                    if let Ok(col) = db.collection("chat_messages").await {
                        let _ = col.create_document(msg, Default::default()).await;
                    }
                    spawn_5w1h_tagging(sk_persist).await;
                });

                let tool_stream = sse_text_to_stream(sse_text);
                return Ok(Sse::new(tool_stream));
            }
        }
    }
    let (event_tx, event_rx) = mpsc::unbounded_channel::<Result<Event, std::convert::Infallible>>();
    let event_tx = Arc::new(event_tx);
    let tx_for_bg = event_tx.clone();
    let rx_for_stream = event_rx;

    tokio::spawn(async move {
        let mut buffer = String::new();
        let mut body = response.bytes_stream();

        use futures::StreamExt;
        while let Some(chunk_result) = body.next().await {
            match chunk_result {
                Ok(chunk) => {
                    let text = String::from_utf8_lossy(&chunk);
                    buffer.push_str(&text);

                    while let Some(pos) = buffer.find("\n\n") {
                        let raw_event = buffer[..pos].to_string();
                        buffer.drain(..pos + 2);

                        for line in raw_event.lines() {
                            let Some(data) = line
                                .strip_prefix("data:")
                                .map(str::trim)
                                .filter(|v| !v.is_empty())
                            else {
                                continue;
                            };

                            if data == "[DONE]" {
                                let _ = tx_for_bg.send(Ok(Event::default()
                                    .event("chat_done")
                                    .data(serde_json::json!({ "done": true }).to_string())));
                                return;
                            }

                            if let Ok(json) = serde_json::from_str::<serde_json::Value>(data) {
                                if let Some(delta) = json
                                    .get("message")
                                    .and_then(|m| m.get("content"))
                                    .and_then(|v| v.as_str())
                                {
                                    let _ = tx.send(delta.to_string());
                                }

                                if json.get("done").and_then(|v| v.as_bool()) == Some(true) {
                                    let _ = tx_for_bg.send(Ok(Event::default()
                                        .event("chat_done")
                                        .data(serde_json::json!({ "done": true }).to_string())));
                                    return;
                                }

                                let _ = tx_for_bg.send(Ok(Event::default()
                                    .event("chat_chunk")
                                    .data(data.to_string())));
                            }
                        }
                    }
                }
                Err(_) => {
                    let _ = tx_for_bg.send(Ok(Event::default()
                        .event("chat_error")
                        .data(serde_json::json!({ "error": "upstream_stream_error" }).to_string())));
                    let _ = tx_for_bg.send(Ok(Event::default()
                        .event("chat_done")
                        .data(serde_json::json!({ "done": true }).to_string())));
                    return;
                }
            }
        }

        let _ = tx_for_bg.send(Ok(Event::default()
            .event("chat_done")
            .data(serde_json::json!({ "done": true }).to_string())));
    });

    let sse_stream = tokio_stream::wrappers::UnboundedReceiverStream::new(rx_for_stream);

    Ok(Sse::new(Box::pin(sse_stream) as Pin<Box<dyn tokio_stream::Stream<Item = Result<Event, Infallible>> + Send>>))
}

async fn load_chat_defaults(
    db: &arangors::Database<arangors::client::reqwest::ReqwestClient>,
) -> Result<ChatDefaults, StatusCode> {
    let params: Vec<SystemParam> = db
        .aql_str("FOR p IN system_params FILTER p.category == \"task_chat\" RETURN p")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let get_value = |key: &str| {
        params
            .iter()
            .find(|p| p.param_key == key)
            .map(|p| p.param_value.clone())
    };

    let default_provider = get_value("task_chat.default_provider")
        .unwrap_or_else(|| "ollama".to_string());
    let default_model = get_value("task_chat.default_model")
        .unwrap_or_else(|| "llama3.2:latest".to_string());
    let temperature = get_value("task_chat.temperature")
        .and_then(|v| v.parse::<f64>().ok())
        .unwrap_or(0.7);
    let max_tokens = get_value("task_chat.max_tokens")
        .and_then(|v| v.parse::<i32>().ok())
        .unwrap_or(4096);
    let system_prompt = get_value("task_chat.system_prompt").unwrap_or_else(|| {
        let base = "你是一個綜合工作協作者，可以天南地北無所不談，協助使用者完成各種工作任務。";
        let mermaid_hint = r#"

【Mermaid 圖表生成須知】
生成 Mermaid 圖表時，請遵守以下規則以確保能正常渲染：
1. 禁止在節點標籤中使用冒號 `:` 或管道符 `|`，如需分隔請用 `/`
2. 禁止使用中文全形括號【】（）《》，請改用英文方括號 `[]` 或尖括號 `<>`
3. 禁止使用中文書名號《》，可用 `<>` 替代
4. 禁止使用中文引號「」或「」，請改用英文單引號 `'` 或雙引號 `"`
5. 節點標籤內如有換行需求，請使用 `<br>`
6. 確保所有 `(` `[` `<` 都有配對的 `)` `]` `>`
7. 不要在 flowchart 的 node ID 中使用中文，請用英文或數字 ID"#;
        format!("{}{}", base, mermaid_hint)
    });
    let max_history_messages = get_value("task_chat.max_history_messages")
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(50);

    Ok(ChatDefaults {
        default_provider,
        default_model,
        temperature,
        max_tokens,
        system_prompt,
        max_history_messages,
    })
}

async fn spawn_5w1h_tagging(session_key: String) {
    let db = get_db();

    let defaults = match load_chat_defaults(db).await {
        Ok(d) => d,
        Err(_) => return,
    };

    let tagging_model: String = {
        let params: Vec<SystemParam> = db
            .aql_str("FOR p IN system_params FILTER p.param_key == \"task_chat.tagging_model\" RETURN p")
            .await
            .unwrap_or_default();
        params
            .into_iter()
            .next()
            .map(|p| p.param_value)
            .unwrap_or_else(|| "qwen3-coder:30b".to_string())
    };

    let messages: Vec<ChatMessage> = match db
        .aql_bind_vars(
            "FOR m IN chat_messages FILTER m.session_key == @key SORT m.created_at ASC RETURN m",
            [("key", serde_json::json!(session_key.clone()))].into(),
        )
        .await
    {
        Ok(msgs) => msgs,
        Err(_) => return,
    };

    if messages.is_empty() {
        return;
    }

    let capped: Vec<&ChatMessage> = if messages.len() > defaults.max_history_messages {
        messages[messages.len().saturating_sub(defaults.max_history_messages)..].iter().collect()
    } else {
        messages.iter().collect()
    };

    let msg_payload: Vec<serde_json::Value> = capped
        .iter()
        .map(|m| serde_json::json!({ "role": m.role, "content": m.content }))
        .collect();

    let aitask_url =
        std::env::var("AITASK_URL").unwrap_or_else(|_| "http://localhost:8001".to_string());

    let client = reqwest::Client::new();
    let body = serde_json::json!({
        "session_key": session_key,
        "messages": msg_payload,
        "model": tagging_model,
    });

    let resp = match client
        .post(format!("{}/v1/chat/tag-5w1h", aitask_url))
        .json(&body)
        .timeout(std::time::Duration::from_secs(120))
        .send()
        .await
    {
        Ok(r) => r,
        Err(_) => return,
    };

    if !resp.status().is_success() {
        return;
    }

    let resp_json: serde_json::Value = match resp.json().await {
        Ok(v) => v,
        Err(_) => return,
    };

    let tags = match resp_json.get("tags") {
        Some(t) => t.clone(),
        None => return,
    };

    let patch = serde_json::json!({
        "tags_5w1h": tags,
        "updated_at": chrono::Utc::now().to_rfc3339(),
    });

    if let Ok(col) = db.collection("chat_sessions").await {
        let _ = col
            .update_document(&session_key, patch, Default::default())
            .await;
    }
}

async fn upload_session_file(
    Path(session_key): Path<String>,
    mut multipart: Multipart,
) -> Result<Json<ApiResponse<serde_json::Value>>, StatusCode> {
    let db = get_db();

    let sessions: Vec<ChatSession> = db
        .aql_bind_vars(
            "FOR s IN chat_sessions FILTER s._key == @key LIMIT 1 RETURN s",
            [("key", serde_json::json!(session_key.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    if sessions.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    let field = multipart
        .next_field()
        .await
        .map_err(|_| StatusCode::BAD_REQUEST)?;
    let field = field.ok_or(StatusCode::BAD_REQUEST)?;

    let filename = field.file_name().unwrap_or("unknown").to_string();
    let bytes = field
        .bytes()
        .await
        .map_err(|_| StatusCode::BAD_REQUEST)?;

    let file_key = uuid::Uuid::new_v4().to_string();
    let ext = std::path::Path::new(&filename)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("bin");

    let local_dir = std::env::current_dir()
        .unwrap_or_else(|_| std::path::PathBuf::from("."))
        .join("data/uploads/sessions")
        .join(&session_key);
    let local_path = local_dir.join(format!("{}.{}", file_key, ext));
    tokio::fs::create_dir_all(&local_dir)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    tokio::fs::write(&local_path, &bytes)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let s3_path = format!(
        "bucket-aibox-assets/sessions/{}/{}.{}",
        session_key, file_key, ext
    );
    let seaweed_user = std::env::var("SEAWEED_USER").unwrap_or_else(|_| "admin".to_string());
    let seaweed_pass = std::env::var("SEAWEED_PASS").unwrap_or_else(|_| "admin123".to_string());
    let seaweed_base =
        std::env::var("SEAWEED_AIBOX_URL").unwrap_or_else(|_| "http://localhost:8888".to_string());
    let seaweed_url = format!("{}/{}", seaweed_base, s3_path);
    let client = reqwest::Client::new();
    let _ = client
        .put(&seaweed_url)
        .basic_auth(&seaweed_user, Some(&seaweed_pass))
        .body(bytes.clone())
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await;

    let now = chrono::Utc::now().to_rfc3339();
    let doc: serde_json::Value = serde_json::json!({
        "_key": file_key,
        "filename": filename,
        "file_size": bytes.len() as i64,
        "file_type": ext,
        "upload_time": now,
        "vector_status": "pending",
        "graph_status": "pending",
        "knowledge_root_id": serde_json::Value::Null,
        "session_key": session_key.clone(),
        "local_path": local_path,
        "s3_path": s3_path,
    });

    let col = db
        .collection("knowledge_files")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(doc, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let edge_key = format!("csf_{}", file_key);
    let edge_doc: serde_json::Value = serde_json::json!({
        "_key": edge_key,
        "_from": format!("chat_sessions/{}", session_key),
        "_to": format!("knowledge_files/{}", file_key),
        "session_key": session_key.clone(),
        "file_key": file_key.clone(),
        "uploaded_at": now,
    });
    let edge_col = db
        .collection("chat_session_files")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    edge_col
        .create_document(edge_doc, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let agent_url =
        std::env::var("KNOWLEDGE_AGENT_URL").unwrap_or_else(|_| "http://localhost:8007".to_string());
    let trigger_url = format!("{}/pipeline/trigger", agent_url);
    let payload = serde_json::json!({
        "task": "vectorize",
        "file_id": file_key,
        "local_path": local_path,
        "root_id": session_key,
        "session_key": session_key,
    });
    let _ = client
        .post(&trigger_url)
        .json(&payload)
        .timeout(std::time::Duration::from_secs(5))
        .send()
        .await;

    Ok(Json(ApiResponse::success(serde_json::json!({
        "file_key": file_key,
        "filename": filename,
        "file_size": bytes.len() as i64,
        "file_type": ext,
        "session_key": session_key,
        "upload_time": now,
        "vector_status": "pending",
        "graph_status": "pending",
    }))))
}

async fn list_session_files(
    Path(session_key): Path<String>,
) -> Result<Json<ApiResponse<Vec<serde_json::Value>>>, StatusCode> {
    let db = get_db();

    let sessions: Vec<ChatSession> = db
        .aql_bind_vars(
            "FOR s IN chat_sessions FILTER s._key == @key LIMIT 1 RETURN s",
            [("key", serde_json::json!(session_key.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    if sessions.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    let files: Vec<serde_json::Value> = db
        .aql_bind_vars(
            r#"
            FOR edge IN chat_session_files
            FILTER edge.session_key == @session_key
            LET file = DOCUMENT("knowledge_files", edge.file_key)
            FILTER file != null
            LET node_count = LENGTH(
                (FOR g IN knowledge_graphs FILTER g.file_id == edge.file_key RETURN 1)
            )
            LET edge_count = LENGTH(
                (FOR e IN knowledge_graph_edges FILTER e.file_id == edge.file_key RETURN 1)
            )
            RETURN {
                "file_key": edge.file_key,
                "filename": file.filename,
                "file_size": file.file_size,
                "file_type": file.file_type,
                "vector_status": file.vector_status,
                "graph_status": file.graph_status,
                "failed_reason": file.failed_reason,
                "upload_time": edge.uploaded_at,
                "graph_stats": {
                    "nodes": node_count,
                    "edges": edge_count
                }
            }
            "#,
            [("session_key", serde_json::json!(session_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(files)))
}

async fn delete_session_file(
    Path((session_key, file_key)): Path<(String, String)>,
) -> Result<Json<ApiResponse<String>>, StatusCode> {
    let db = get_db();

    let sessions: Vec<ChatSession> = db
        .aql_bind_vars(
            "FOR s IN chat_sessions FILTER s._key == @key LIMIT 1 RETURN s",
            [("key", serde_json::json!(session_key.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    if sessions.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    let agent_url =
        std::env::var("KNOWLEDGE_AGENT_URL").unwrap_or_else(|_| "http://localhost:8007".to_string());
    let client = reqwest::Client::new();
    let _ = client
        .post(format!("{}/pipeline/delete?file_id={}", agent_url, file_key))
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await;

    let _: Vec<serde_json::Value> = db
        .aql_bind_vars(
            r#"
            FOR edge IN chat_session_files
            FILTER edge.session_key == @session_key AND edge.file_key == @file_key
            REMOVE edge IN chat_session_files
            "#,
            [
                ("session_key", serde_json::json!(session_key.clone())),
                ("file_key", serde_json::json!(file_key.clone())),
            ]
                .into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let _: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "REMOVE @key IN knowledge_files OPTIONS { ignoreErrors: true }",
            [("key", serde_json::json!(file_key.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let local_dir = std::env::current_dir()
        .unwrap_or_else(|_| std::path::PathBuf::from("."))
        .join("data/uploads/sessions")
        .join(&session_key);
    let _ = tokio::fs::remove_file(local_dir.join(format!("{}.*", file_key))).await;

    let seaweed_user =
        std::env::var("SEAWEED_USER").unwrap_or_else(|_| "admin".to_string());
    let seaweed_pass =
        std::env::var("SEAWEED_PASS").unwrap_or_else(|_| "admin123".to_string());
    let seaweed_base =
        std::env::var("SEAWEED_AIBOX_URL").unwrap_or_else(|_| "http://localhost:8888".to_string());
    let _ = client
        .delete(format!(
            "{}/bucket-aibox-assets/sessions/{}/{}",
            seaweed_base,
            session_key,
            file_key
        ))
        .basic_auth(&seaweed_user, Some(&seaweed_pass))
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await;

    Ok(Json(ApiResponse::success("deleted".to_string())))
}

#[derive(Debug, Clone, serde::Deserialize)]
struct FileStatusWebhookPayload {
    file_key: String,
    vector_status: Option<String>,
    graph_status: Option<String>,
    failed_reason: Option<String>,
    graph_stats: Option<serde_json::Value>,
}

async fn file_status_webhook(
    Path(session_key): Path<String>,
    Json(payload): Json<FileStatusWebhookPayload>,
) -> Result<Json<ApiResponse<serde_json::Value>>, StatusCode> {
    broadcast_file_status_event(
        &session_key,
        serde_json::json!({
            "file_key": payload.file_key,
            "vector_status": payload.vector_status,
            "graph_status": payload.graph_status,
            "failed_reason": payload.failed_reason,
            "graph_stats": payload.graph_stats,
        }),
    );
    Ok(Json(ApiResponse::success(serde_json::json!({ "broadcasted": true }))))
}
