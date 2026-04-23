//! ActionTrail S3 備存模組
//!
//! # Description
//! 接收前端批量操作事件，寫入 SeaweedFS；支援按帳號/日期/頁面/元件調閱。
//!
//! # Last Update: 2026-04-16 11:43:44
//! # Author: Daniel Chung
//! # Version: 1.0.0

use axum::{
    extract::{Path, Query},
    http::{header::AUTHORIZATION, HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use bytes::Bytes;
use once_cell::sync::Lazy;
use serde::{Deserialize, Serialize};

use crate::auth::verify_jwt;
use crate::config::CONFIG;
use crate::models::ApiResponse;

static HTTP_CLIENT: Lazy<reqwest::Client> = Lazy::new(reqwest::Client::new);

#[derive(Debug, Deserialize)]
struct ActionEvent {
    #[serde(rename = "type")]
    event_type: String,
    timestamp: u64,
    page: String,
    meta: serde_json::Value,
}

#[derive(Debug, Deserialize)]
struct BatchRequest {
    events: Vec<ActionEvent>,
}

#[derive(Debug, Deserialize)]
struct TrailQuery {
    date: Option<String>,
    page: Option<String>,
    component: Option<String>,
    from: Option<u64>,
    to: Option<u64>,
}

#[derive(Debug, Serialize)]
struct TrailLine {
    #[serde(rename = "type")]
    event_type: String,
    timestamp: u64,
    page: String,
    meta: serde_json::Value,
}

fn extract_account(headers: &HeaderMap) -> Result<String, StatusCode> {
    let token = headers
        .get(AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;
    let claims = verify_jwt(token).map_err(|_| StatusCode::UNAUTHORIZED)?;
    Ok(claims.claims.sub)
}

fn sanitize_path_segment(s: &str) -> String {
    s.replace(['/', '\\', '\0'], "_")
        .replace("..", "_")
        .chars()
        .filter(|c| c.is_alphanumeric() || *c == '_' || *c == '-' || *c == '.')
        .collect()
}

async fn batch_upload(
    headers: HeaderMap,
    Json(payload): Json<BatchRequest>,
) -> Result<impl IntoResponse, StatusCode> {
    let account = extract_account(&headers)?;

    if payload.events.is_empty() {
        return Ok(Json(ApiResponse::success("no events".to_string())));
    }

    let mut grouped: std::collections::HashMap<String, Vec<String>> =
        std::collections::HashMap::new();

    for event in &payload.events {
        let ts_secs = event.timestamp / 1000;
        let date = chrono::DateTime::from_timestamp(ts_secs as i64, 0)
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_else(|| "unknown".to_string());

        let page_seg = sanitize_path_segment(
            if event.page.is_empty() { "root" } else { &event.page },
        );

        let component = event
            .meta
            .get("component")
            .and_then(|v| v.as_str())
            .unwrap_or("general");
        let comp_seg = sanitize_path_segment(component);

        let s3_key = format!(
            "bucket-aibox-assets/action-trail/{}/{}/{}/{}.jsonl",
            sanitize_path_segment(&account),
            date,
            page_seg,
            comp_seg
        );

        let line = serde_json::to_string(&TrailLine {
            event_type: event.event_type.clone(),
            timestamp: event.timestamp,
            page: event.page.clone(),
            meta: event.meta.clone(),
        })
        .unwrap_or_default();

        grouped.entry(s3_key).or_default().push(line);
    }

    for (s3_key, lines) in grouped {
        let existing = HTTP_CLIENT
            .get(format!("{}/{}", CONFIG.ai_services.seaweed_aibox_url, s3_key))
            .basic_auth(
                &CONFIG.ai_services.seaweed_user,
                Some(&CONFIG.ai_services.seaweed_pass),
            )
            .timeout(std::time::Duration::from_secs(10))
            .send()
            .await
            .ok()
            .and_then(|r| if r.status().is_success() { Some(r) } else { None });

        let mut content = if let Some(resp) = existing {
            resp.text().await.unwrap_or_default()
        } else {
            String::new()
        };

        for line in &lines {
            if !content.is_empty() && !content.ends_with('\n') {
                content.push('\n');
            }
            content.push_str(line);
            content.push('\n');
        }

        let _ = HTTP_CLIENT
            .put(format!("{}/{}", CONFIG.ai_services.seaweed_aibox_url, s3_key))
            .basic_auth(
                &CONFIG.ai_services.seaweed_user,
                Some(&CONFIG.ai_services.seaweed_pass),
            )
            .body(Bytes::from(content))
            .timeout(std::time::Duration::from_secs(30))
            .send()
            .await;
    }

    Ok(Json(ApiResponse::success(format!(
        "flushed {} events",
        payload.events.len()
    ))))
}

async fn query_trail(
    headers: HeaderMap,
    Path(account): Path<String>,
    Query(q): Query<TrailQuery>,
) -> Result<impl IntoResponse, StatusCode> {
    let _ = extract_account(&headers)?;

    let date = q.date.unwrap_or_else(|| {
        chrono::Utc::now().format("%Y-%m-%d").to_string()
    });

    let account_seg = sanitize_path_segment(&account);
    let base = format!(
        "bucket-aibox-assets/action-trail/{}/{}",
        account_seg, date
    );

    let s3_key = match (&q.page, &q.component) {
        (Some(p), Some(c)) => format!(
            "{}/{}/{}.jsonl",
            base,
            sanitize_path_segment(p),
            sanitize_path_segment(c)
        ),
        (Some(p), None) => format!("{}/{}", base, sanitize_path_segment(p)),
        _ => base,
    };

    let resp = HTTP_CLIENT
        .get(format!("{}/{}", CONFIG.ai_services.seaweed_aibox_url, s3_key))
        .basic_auth(
            &CONFIG.ai_services.seaweed_user,
            Some(&CONFIG.ai_services.seaweed_pass),
        )
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
        .map_err(|_| StatusCode::BAD_GATEWAY)?;

    if !resp.status().is_success() {
        return Ok(Json(ApiResponse::success(Vec::<serde_json::Value>::new())));
    }

    let text = resp.text().await.unwrap_or_default();
    let mut events: Vec<serde_json::Value> = text
        .lines()
        .filter(|l| !l.trim().is_empty())
        .filter_map(|l| serde_json::from_str(l).ok())
        .collect();

    if let Some(from_ts) = q.from {
        events.retain(|e| {
            e.get("timestamp")
                .and_then(|v| v.as_u64())
                .map(|ts| ts >= from_ts)
                .unwrap_or(true)
        });
    }
    if let Some(to_ts) = q.to {
        events.retain(|e| {
            e.get("timestamp")
                .and_then(|v| v.as_u64())
                .map(|ts| ts <= to_ts)
                .unwrap_or(true)
        });
    }

    Ok(Json(ApiResponse::success(events)))
}

pub fn create_action_trail_router() -> Router {
    Router::new()
        .route("/api/v1/action-trail/batch", post(batch_upload))
        .route("/api/v1/action-trail/{account}", get(query_trail))
}
