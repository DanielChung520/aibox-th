//! Agent Chat Proxy
//!
//! # Description
//! 通用 Agent 聊天代理路由。讀取 Agent 記錄的 endpoint_url，動態代理請求到該端點。
//! 前端一律透過 POST /api/v1/agents/{key}/chat 呼叫，不需硬編碼任何 Agent 路徑。
//!
//! # Last Update: 2026-04-28 15:30:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use axum::{
    extract::Path,
    http::{header::AUTHORIZATION, HeaderMap, StatusCode},
    response::IntoResponse,
    routing::post,
    Json, Router,
};
use once_cell::sync::Lazy;
use serde_json::Value;

use crate::{auth::verify_jwt, config::CONFIG, db::get_db};

static HTTP_CLIENT: Lazy<reqwest::Client> = Lazy::new(reqwest::Client::new);

fn extract_user_key(headers: &HeaderMap) -> Result<String, StatusCode> {
    let token = headers
        .get(AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;
    let claims = verify_jwt(token).map_err(|_| StatusCode::UNAUTHORIZED)?;
    Ok(claims.claims.sub)
}

pub fn create_agent_chat_router() -> Router {
    Router::new().route("/api/v1/agents/{key}/chat", post(proxy_agent_chat))
}

async fn proxy_agent_chat(
    headers: HeaderMap,
    Path(key): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let user_key = extract_user_key(&headers)?;

    let db = get_db();
    let agents: Vec<Value> = db
        .aql_bind_vars(
            "FOR a IN agents FILTER a._key == @key LIMIT 1 RETURN a",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let agent = agents.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let endpoint_url = agent
        .get("endpoint_url")
        .and_then(|v| v.as_str())
        .filter(|s| !s.is_empty())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let mut body = payload;
    if let Some(obj) = body.as_object_mut() {
        if !obj.contains_key("user_id") || obj.get("user_id").and_then(|v| v.as_str()).map_or(true, |s| s.is_empty() || s == "anonymous") {
            obj.insert("user_id".to_string(), serde_json::json!(user_key));
        }
        if !obj.contains_key("agent_key") {
            obj.insert("agent_key".to_string(), serde_json::json!(&key));
        }
    }

    let response = HTTP_CLIENT
        .post(endpoint_url)
        .header("X-User-Key", &user_key)
        .header("X-Internal-Token", &CONFIG.ai_services.internal_token)
        .json(&body)
        .send()
        .await
        .map_err(|error| {
            tracing::error!(url = %endpoint_url, error = %error, "Agent chat proxy error");
            StatusCode::BAD_GATEWAY
        })?;

    let status = StatusCode::from_u16(response.status().as_u16())
        .unwrap_or(StatusCode::INTERNAL_SERVER_ERROR);
    let resp_body: Value = response.json().await.map_err(|error| {
        tracing::error!(url = %endpoint_url, error = %error, "Agent chat proxy response parse error");
        StatusCode::BAD_GATEWAY
    })?;

    Ok((status, Json(resp_body)))
}
