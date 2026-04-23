use crate::config::CONFIG;
use axum::{
    extract::{Path, State},
    http::{StatusCode},
    response::IntoResponse,
    routing::get,
    Json, Router,
};
use reqwest::Client;
use serde_json::Value;
use std::time::Duration;

#[derive(Clone)]
struct RagicAppState {
    client: Client,
}

pub fn create_ragic_router() -> Router {
    let state = RagicAppState {
        client: Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .unwrap(),
    };

    Router::new()
        .route(
            "/api/v1/ragic/session/{session_id}/history",
            get(get_session_history),
        )
        .with_state(state)
}

fn ragic_base_url() -> String {
    format!("{}/ragic", CONFIG.ai_services.unified_agents_url)
}

async fn get_session_history(
    State(state): State<RagicAppState>,
    Path(session_id): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let url = format!("{}/session/{}/history", ragic_base_url(), session_id);

    let resp = state
        .client
        .get(&url)
        .send()
        .await
        .map_err(|e| {
            eprintln!("ragic session history error: {}", e);
            StatusCode::BAD_GATEWAY
        })?;

    let status = resp.status();
    let body: Value = resp.json().await.map_err(|e| {
        eprintln!("ragic session history parse error: {}", e);
        StatusCode::BAD_GATEWAY
    })?;

    if status.is_success() {
        Ok(Json(body))
    } else {
        eprintln!("ragic session history failed: {} - {:?}", status, body);
        Err(StatusCode::from_u16(status.as_u16()).unwrap_or(StatusCode::BAD_GATEWAY))
    }
}
