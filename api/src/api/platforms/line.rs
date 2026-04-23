use crate::config::CONFIG;
use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{delete, get, post},
    Json, Router,
};
use reqwest::Client;
use serde_json::Value;
use std::time::Duration;

#[derive(Clone)]
struct LineAppState {
    client: Client,
}

pub fn create_line_router() -> Router {
    let state = LineAppState {
        client: Client::builder()
            .timeout(Duration::from_secs(60))
            .build()
            .unwrap(),
    };

    Router::new()
        .route(
            "/api/v1/platforms/line/official-accounts",
            get(list_official_accounts).post(create_official_account),
        )
        .route(
            "/api/v1/platforms/line/official-accounts/{key}",
            get(get_official_account).put(update_official_account).delete(delete_official_account),
        )
        .route(
            "/api/v1/platforms/line/official-accounts/{key}/channels",
            post(create_channel),
        )
        .route(
            "/api/v1/platforms/line/channels/{channel_key}",
            get(get_channel).put(update_channel).delete(delete_channel),
        )
        .route(
            "/api/v1/platforms/line/channels/{channel_key}/test-connection",
            post(test_connection),
        )
        .route(
            "/api/v1/platforms/line/channels/{channel_key}/publish",
            post(publish_channel).delete(unpublish_channel),
        )
        .route(
            "/api/v1/webhook/line/{channel_key}",
            get(line_webhook_get).post(line_webhook),
        )
        .with_state(state)
}

fn line_base_url() -> String {
    format!("{}/platforms/line", CONFIG.ai_services.unified_agents_url)
}

fn reqwest_to_axum_status(reqwest_status: reqwest::StatusCode) -> StatusCode {
    match reqwest_status.as_u16() {
        200 => StatusCode::OK,
        201 => StatusCode::CREATED,
        400 => StatusCode::BAD_REQUEST,
        404 => StatusCode::NOT_FOUND,
        500 => StatusCode::INTERNAL_SERVER_ERROR,
        _ => StatusCode::from_u16(reqwest_status.as_u16()).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

async fn proxy(
    client: &Client,
    method: &str,
    path: &str,
    body: Option<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let url = format!("{}{}", line_base_url(), path);

    let mut req = match method {
        "GET" => client.get(&url),
        "POST" => client.post(&url),
        "DELETE" => client.delete(&url),
        "PUT" => client.put(&url),
        _ => return Err(StatusCode::METHOD_NOT_ALLOWED),
    };

    if let Some(payload) = body {
        req = req.json(&payload);
    }

    let resp = req.send().await.map_err(|e| {
        eprintln!("line proxy error: {e}");
        StatusCode::BAD_GATEWAY
    })?;

    let status = resp.status();
    let body: Value = resp.json().await.unwrap_or(Value::Null);

    if status.is_success() || status.as_u16() >= 400 {
        Ok((reqwest_to_axum_status(status), Json(body)))
    } else {
        Err(StatusCode::BAD_GATEWAY)
    }
}

async fn list_official_accounts(
    State(state): State<LineAppState>,
) -> Result<impl IntoResponse, StatusCode> {
    proxy(&state.client, "GET", "/official-accounts", None).await
}

async fn create_official_account(
    State(state): State<LineAppState>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    proxy(&state.client, "POST", "/official-accounts", Some(payload)).await
}

async fn get_official_account(
    State(state): State<LineAppState>,
    Path(key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let path = format!("/official-accounts/{}", key);
    proxy(&state.client, "GET", &path, None).await
}

async fn update_official_account(
    State(state): State<LineAppState>,
    Path(key): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let path = format!("/official-accounts/{}", key);
    proxy(&state.client, "PUT", &path, Some(payload)).await
}

async fn delete_official_account(
    State(state): State<LineAppState>,
    Path(key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let path = format!("/official-accounts/{}", key);
    proxy(&state.client, "DELETE", &path, None).await
}

async fn create_channel(
    State(state): State<LineAppState>,
    Path(key): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let path = format!("/official-accounts/{}/channels", key);
    proxy(&state.client, "POST", &path, Some(payload)).await
}

async fn get_channel(
    State(state): State<LineAppState>,
    Path(channel_key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let path = format!("/channels/{}", channel_key);
    proxy(&state.client, "GET", &path, None).await
}

async fn update_channel(
    State(state): State<LineAppState>,
    Path(channel_key): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let path = format!("/channels/{}", channel_key);
    proxy(&state.client, "PUT", &path, Some(payload)).await
}

async fn delete_channel(
    State(state): State<LineAppState>,
    Path(channel_key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let path = format!("/channels/{}", channel_key);
    proxy(&state.client, "DELETE", &path, None).await
}

async fn test_connection(
    State(state): State<LineAppState>,
    Path(channel_key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let path = format!("/channels/{}/test-connection", channel_key);
    proxy(&state.client, "POST", &path, None).await
}

async fn publish_channel(
    State(state): State<LineAppState>,
    Path(channel_key): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let path = format!("/channels/{}/publish", channel_key);
    proxy(&state.client, "POST", &path, Some(payload)).await
}

async fn unpublish_channel(
    State(state): State<LineAppState>,
    Path(channel_key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let path = format!("/channels/{}/publish", channel_key);
    proxy(&state.client, "DELETE", &path, None).await
}

async fn line_webhook(
    State(state): State<LineAppState>,
    Path(channel_key): Path<String>,
    headers: HeaderMap,
    body: String,
) -> Result<impl IntoResponse, StatusCode> {
    let url = format!(
        "{}/webhook/line/{}",
        CONFIG.ai_services.unified_agents_url,
        channel_key
    );

    let mut req_builder = state.client.post(&url).body(body);

    if let Some(sig) = headers.get("x-line-signature") {
        req_builder = req_builder.header("x-line-signature", sig.to_str().unwrap_or(""));
    }

    let resp = req_builder.send().await.map_err(|e| {
        eprintln!("line webhook proxy error: {e}");
        StatusCode::BAD_GATEWAY
    })?;

    let status = resp.status();
    let body_bytes = resp.bytes().await.unwrap_or_default();

    Ok((reqwest_to_axum_status(status), body_bytes))
}

async fn line_webhook_get(
    State(state): State<LineAppState>,
    Path(channel_key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let url = format!(
        "{}/webhook/line/{}",
        CONFIG.ai_services.unified_agents_url,
        channel_key
    );

    let resp = state.client.get(&url).send().await.map_err(|e| {
        eprintln!("line webhook get error: {e}");
        StatusCode::BAD_GATEWAY
    })?;

    let status = resp.status();
    let body_bytes = resp.bytes().await.unwrap_or_default();

    Ok((reqwest_to_axum_status(status), body_bytes))
}