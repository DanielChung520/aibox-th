//! 艾企助手 L3 意圖形成系統 API — Proxy to Python aiq_agent
//!
//! # Description
//! 所有 AIQ 端點透過 reqwest 轉發到 Python aiq_agent 服務 (port 8009)。
//! JWT 驗證在 Rust 層完成，萃取 user_key 後注入 X-User-Key header。
//!
//! # Last Update: 2026-04-18 20:14:17
//! # Author: Daniel Chung
//! # Version: 3.0.0

use axum::{
    http::{header::AUTHORIZATION, HeaderMap, StatusCode},
    response::{
        sse::{Event, Sse},
        IntoResponse,
    },
    routing::{get, post},
    Json, Router,
};
use chrono::Utc;
use futures::{stream, Stream, StreamExt};
use once_cell::sync::Lazy;
use serde_json::Value;
use std::convert::Infallible;

use crate::{auth::verify_jwt, config::CONFIG};

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

fn proxy_url(path: &str) -> String {
    let base = CONFIG.ai_services.aiq_agent_url.trim_end_matches('/');
    format!("{base}/{path}")
}

fn map_status(status: reqwest::StatusCode) -> StatusCode {
    StatusCode::from_u16(status.as_u16()).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR)
}

async fn proxy_get(url: String, user_key: &str) -> Result<(StatusCode, Json<Value>), StatusCode> {
    let response = HTTP_CLIENT
        .get(&url)
        .header("X-User-Key", user_key)
        .header("X-Internal-Token", &CONFIG.ai_services.internal_token)
        .send()
        .await
        .map_err(|error| {
            tracing::error!(url = %url, error = %error, "AIQ proxy GET error");
            StatusCode::BAD_GATEWAY
        })?;

    let status = map_status(response.status());
    let body = response.json::<Value>().await.map_err(|error| {
        tracing::error!(url = %url, error = %error, "AIQ proxy GET response parse error");
        StatusCode::BAD_GATEWAY
    })?;

    Ok((status, Json(body)))
}

async fn proxy_post(
    url: String,
    user_key: &str,
    payload: &Value,
) -> Result<(StatusCode, Json<Value>), StatusCode> {
    let response = HTTP_CLIENT
        .post(&url)
        .header("X-User-Key", user_key)
        .header("X-Internal-Token", &CONFIG.ai_services.internal_token)
        .json(payload)
        .send()
        .await
        .map_err(|error| {
            tracing::error!(url = %url, error = %error, "AIQ proxy POST error");
            StatusCode::BAD_GATEWAY
        })?;

    let status = map_status(response.status());
    let body = response.json::<Value>().await.map_err(|error| {
        tracing::error!(url = %url, error = %error, "AIQ proxy POST response parse error");
        StatusCode::BAD_GATEWAY
    })?;

    Ok((status, Json(body)))
}

async fn proxy_put(
    url: String,
    user_key: &str,
    payload: &Value,
) -> Result<(StatusCode, Json<Value>), StatusCode> {
    let response = HTTP_CLIENT
        .put(&url)
        .header("X-User-Key", user_key)
        .header("X-Internal-Token", &CONFIG.ai_services.internal_token)
        .json(payload)
        .send()
        .await
        .map_err(|error| {
            tracing::error!(url = %url, error = %error, "AIQ proxy PUT error");
            StatusCode::BAD_GATEWAY
        })?;

    let status = map_status(response.status());
    let body = response.json::<Value>().await.map_err(|error| {
        tracing::error!(url = %url, error = %error, "AIQ proxy PUT response parse error");
        StatusCode::BAD_GATEWAY
    })?;

    Ok((status, Json(body)))
}

async fn push_signals(
    headers: HeaderMap,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let user_key = extract_user_key(&headers)?;
    proxy_post(proxy_url("signals/push"), &user_key, &payload).await
}

async fn get_intent_state(headers: HeaderMap) -> Result<impl IntoResponse, StatusCode> {
    let user_key = extract_user_key(&headers)?;
    proxy_get(proxy_url("intent-state"), &user_key).await
}

async fn commit_intent(
    headers: HeaderMap,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let user_key = extract_user_key(&headers)?;
    proxy_post(proxy_url("intent-state/commit"), &user_key, &payload).await
}

async fn inquiry_analyze(
    headers: HeaderMap,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let user_key = extract_user_key(&headers)?;
    proxy_post(proxy_url("inquiry/analyze"), &user_key, &payload).await
}

async fn inquiry_state(headers: HeaderMap) -> Result<impl IntoResponse, StatusCode> {
    let user_key = extract_user_key(&headers)?;
    proxy_get(proxy_url("inquiry/state"), &user_key).await
}

async fn inquiry_reset(
    headers: HeaderMap,
) -> Result<impl IntoResponse, StatusCode> {
    let user_key = extract_user_key(&headers)?;
    proxy_post(proxy_url("inquiry/reset"), &user_key, &serde_json::json!({})).await
}

async fn learning_turn_complete(
    headers: HeaderMap,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let user_key = extract_user_key(&headers)?;
    proxy_post(proxy_url("learning/turn-complete"), &user_key, &payload).await
}

async fn get_user_profile(headers: HeaderMap) -> Result<impl IntoResponse, StatusCode> {
    let user_key = extract_user_key(&headers)?;
    proxy_get(proxy_url("user-profile"), &user_key).await
}

async fn update_user_profile(
    headers: HeaderMap,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let user_key = extract_user_key(&headers)?;
    proxy_put(proxy_url("user-profile"), &user_key, &payload).await
}

async fn intent_state_stream(
    headers: HeaderMap,
) -> Result<Sse<impl Stream<Item = Result<Event, Infallible>>>, StatusCode> {
    let user_key = extract_user_key(&headers)?;

    let initial_stream = stream::iter(vec![Ok(
        Event::default().event("connected").data(
            serde_json::json!({
                "user_key": user_key,
                "timestamp": Utc::now().to_rfc3339(),
                "message": "Subscribed to AIQ intent state stream"
            })
            .to_string(),
        ),
    )]);

    let heartbeat_stream = stream::unfold((), |_| async {
        tokio::time::sleep(tokio::time::Duration::from_secs(15)).await;

        Some((
            Ok(Event::default().event("heartbeat").data(
                serde_json::json!({
                    "timestamp": Utc::now().to_rfc3339()
                })
                .to_string(),
            )),
            (),
        ))
    });

    Ok(Sse::new(initial_stream.chain(heartbeat_stream)))
}

pub fn create_aiq_router() -> Router {
    Router::new()
        .route("/api/v1/aiq/signals/push", post(push_signals))
        .route("/api/v1/aiq/intent-state", get(get_intent_state))
        .route("/api/v1/aiq/intent-state/commit", post(commit_intent))
        .route("/api/v1/aiq/intent-state/stream", get(intent_state_stream))
        .route("/api/v1/aiq/inquiry/analyze", post(inquiry_analyze))
        .route("/api/v1/aiq/inquiry/state", get(inquiry_state))
        .route("/api/v1/aiq/inquiry/reset", post(inquiry_reset))
        .route("/api/v1/aiq/learning/turn-complete", post(learning_turn_complete))
        .route("/api/v1/aiq/user-profile", get(get_user_profile).put(update_user_profile))
}
