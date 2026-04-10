//! Chat 資料存取模組
//!
//! # Description
//! 集中管理聊天服務的 JWT 使用者解析與資料庫查詢邏輯
//!
//! # Last Update: 2026-04-11 02:38:22
//! # Author: AI Agent
//! # Version: 1.0.0

use arangors::client::reqwest::ReqwestClient;
use arangors::Database;
use axum::http::{HeaderMap, StatusCode};

use crate::auth::{verify_jwt, Claims};
use crate::db::{ChatMessage, ChatSession, SystemParam, UpdateSessionRequest};

use super::models::{ChatDefaults, SessionWithMessages};

pub fn extract_user_key_from_headers(headers: &HeaderMap) -> String {
    let claims: Option<Claims> = headers
        .get(axum::http::header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .and_then(|token| verify_jwt(token).ok())
        .map(|data| data.claims);

    claims
        .map(|claims| claims.sub)
        .unwrap_or_else(|| "anonymous".to_string())
}

pub async fn list_sessions_for_user(
    db: &Database<ReqwestClient>,
    user_key: &str,
) -> Result<Vec<ChatSession>, StatusCode> {
    db.aql_bind_vars(
        "FOR s IN chat_sessions FILTER s.user_key == @user_key SORT s.updated_at DESC RETURN s",
        [("user_key", serde_json::json!(user_key))].into(),
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)
}

pub async fn get_session_with_messages(
    db: &Database<ReqwestClient>,
    key: &str,
    user_key: &str,
) -> Result<SessionWithMessages, StatusCode> {
    let mut sessions: Vec<ChatSession> = db
        .aql_bind_vars(
            "FOR s IN chat_sessions FILTER s._key == @key AND s.user_key == @user_key LIMIT 1 RETURN s",
            [("key", serde_json::json!(key)), ("user_key", serde_json::json!(user_key))].into(),
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

    Ok(SessionWithMessages { session, messages })
}

pub async fn create_session_doc(
    db: &Database<ReqwestClient>,
    session: ChatSession,
) -> Result<(), StatusCode> {
    let col = db
        .collection("chat_sessions")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(session, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(())
}

pub async fn update_session_doc(
    db: &Database<ReqwestClient>,
    key: &str,
    payload: UpdateSessionRequest,
) -> Result<ChatSession, StatusCode> {
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

    col.update_document(key, serde_json::Value::Object(patch), Default::default())
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;

    let mut sessions: Vec<ChatSession> = db
        .aql_bind_vars(
            "FOR s IN chat_sessions FILTER s._key == @key LIMIT 1 RETURN s",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    sessions.pop().ok_or(StatusCode::NOT_FOUND)
}

pub async fn insert_message(
    db: &Database<ReqwestClient>,
    msg: ChatMessage,
) -> Result<(), StatusCode> {
    let msg_col = db
        .collection("chat_messages")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    msg_col
        .create_document(msg, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(())
}

pub async fn get_message_history(
    db: &Database<ReqwestClient>,
    session_key: &str,
) -> Result<Vec<ChatMessage>, StatusCode> {
    db.aql_bind_vars(
        "FOR m IN chat_messages FILTER m.session_key == @key SORT m.created_at ASC RETURN m",
        [("key", serde_json::json!(session_key))].into(),
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)
}

pub async fn get_system_param(
    db: &Database<ReqwestClient>,
    param_key: &str,
) -> Option<String> {
    let params: Vec<SystemParam> = db
        .aql_bind_vars(
            "FOR p IN system_params FILTER p.param_key == @key LIMIT 1 RETURN p",
            [("key", serde_json::json!(param_key))].into(),
        )
        .await
        .ok()?;
    params.into_iter().next().map(|p| p.param_value)
}

pub async fn load_chat_defaults(
    db: &Database<ReqwestClient>,
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

    let default_provider =
        get_value("task_chat.default_provider").unwrap_or_else(|| "ollama".to_string());
    let default_model =
        get_value("task_chat.default_model").unwrap_or_else(|| "llama3.2:latest".to_string());
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
