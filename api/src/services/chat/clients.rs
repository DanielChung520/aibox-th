//! Chat 外部客戶端模組
//!
//! # Description
//! 集中管理聊天模組對 AITask、Knowledge Agent、Qdrant 與 SeaweedFS 的 HTTP 呼叫
//!
//! # Last Update: 2026-04-11 08:42:17
//! # Author: AI Agent
//! # Version: 1.0.0

use axum::http::StatusCode;
use bytes::Bytes;
use once_cell::sync::Lazy;

use crate::config::CONFIG;

static HTTP_CLIENT: Lazy<reqwest::Client> = Lazy::new(reqwest::Client::new);

pub async fn call_aitask_chat(body: serde_json::Value) -> Result<reqwest::Response, StatusCode> {
    let response = HTTP_CLIENT
        .post(format!("{}/v1/chat/completions", CONFIG.ai_services.aitask_url))
        .json(&body)
        .send()
        .await
        .map_err(|_| StatusCode::BAD_GATEWAY)?;

    if !response.status().is_success() {
        return Err(StatusCode::BAD_GATEWAY);
    }

    Ok(response)
}

pub async fn call_aitask_graph_chat(
    body: serde_json::Value,
) -> Result<reqwest::Response, StatusCode> {
    let response = HTTP_CLIENT
        .post(format!("{}/v1/graph/chat", CONFIG.ai_services.aitask_url))
        .json(&body)
        .timeout(std::time::Duration::from_secs(120))
        .send()
        .await
        .map_err(|_| StatusCode::BAD_GATEWAY)?;

    if !response.status().is_success() {
        return Err(StatusCode::BAD_GATEWAY);
    }

    Ok(response)
}

pub async fn call_aitask_tagging(body: serde_json::Value) -> Result<serde_json::Value, ()> {
    let response = HTTP_CLIENT
        .post(format!("{}/v1/chat/tag-5w1h", CONFIG.ai_services.aitask_url))
        .json(&body)
        .timeout(std::time::Duration::from_secs(120))
        .send()
        .await
        .map_err(|_| ())?;

    if !response.status().is_success() {
        return Err(());
    }

    response.json().await.map_err(|_| ())
}

pub async fn call_knowledge_delete(file_key: &str) -> Result<(), ()> {
    HTTP_CLIENT
        .post(format!(
            "{}/pipeline/delete?file_id={}",
            CONFIG.ai_services.knowledge_agent_url, file_key
        ))
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
        .map(|_| ())
        .map_err(|_| ())
}

pub async fn call_qdrant_delete_collection(session_key: &str) -> Result<(), ()> {
    HTTP_CLIENT
        .delete(format!(
            "{}/collections/knowledge_{}",
            CONFIG.ai_services.qdrant_url, session_key
        ))
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await
        .map(|_| ())
        .map_err(|_| ())
}

pub async fn call_seaweedfs_delete_session(session_key: &str) -> Result<(), ()> {
    HTTP_CLIENT
        .delete(format!(
            "{}/bucket-aibox-assets/sessions/{}",
            CONFIG.ai_services.seaweed_aibox_url, session_key
        ))
        .basic_auth(
            &CONFIG.ai_services.seaweed_user,
            Some(&CONFIG.ai_services.seaweed_pass),
        )
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await
        .map(|_| ())
        .map_err(|_| ())
}

pub async fn call_seaweedfs_delete_file(session_key: &str, file_key: &str) -> Result<(), ()> {
    HTTP_CLIENT
        .delete(format!(
            "{}/bucket-aibox-assets/sessions/{}/{}",
            CONFIG.ai_services.seaweed_aibox_url, session_key, file_key
        ))
        .basic_auth(
            &CONFIG.ai_services.seaweed_user,
            Some(&CONFIG.ai_services.seaweed_pass),
        )
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await
        .map(|_| ())
        .map_err(|_| ())
}

pub async fn call_seaweedfs_upload(s3_path: &str, data: Bytes) -> Result<(), ()> {
    HTTP_CLIENT
        .put(format!("{}/{}", CONFIG.ai_services.seaweed_aibox_url, s3_path))
        .basic_auth(
            &CONFIG.ai_services.seaweed_user,
            Some(&CONFIG.ai_services.seaweed_pass),
        )
        .body(data)
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
        .map(|_| ())
        .map_err(|_| ())
}

pub async fn call_knowledge_trigger(payload: serde_json::Value) -> Result<(), ()> {
    HTTP_CLIENT
        .post(format!(
            "{}/pipeline/trigger",
            CONFIG.ai_services.knowledge_agent_url
        ))
        .json(&payload)
        .timeout(std::time::Duration::from_secs(5))
        .send()
        .await
        .map(|_| ())
        .map_err(|_| ())
}
