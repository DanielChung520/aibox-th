//! AI Proxy Service
//!
//! # Description
//! AI 服務代理，負責轉發請求到 Python AI 服務
//!
//! # Last Update: 2026-04-10 22:30:00
//! # Author: Daniel Chung
//! # Version: 1.2.0

use crate::config::CONFIG;
use crate::error::ApiError;
use reqwest::Client;

pub struct AiProxy {
    client: Client,
}

impl AiProxy {
    pub fn new() -> Self {
        Self {
            client: Client::new(),
        }
    }

    pub async fn forward_chat(&self, message: &str) -> Result<String, ApiError> {
        let response = self.client
            .post(format!("{}/chat", CONFIG.ai_services.aitask_url))
            .json(&serde_json::json!({ "message": message }))
            .send()
            .await
            .map_err(|e| ApiError::bad_gateway(&e.to_string()))?;

        if !response.status().is_success() {
            return Err(ApiError::bad_gateway("AITask service error"));
        }

        let body: serde_json::Value = response.json().await
            .map_err(|e| ApiError::internal_error(&e.to_string()))?;

        Ok(body.get("message")
            .and_then(|m| m.as_str())
            .unwrap_or("No response")
            .to_string())
    }

    pub async fn forward_query(&self, query: &str) -> Result<serde_json::Value, ApiError> {
        let response = self.client
            .post(format!("{}/query", CONFIG.ai_services.data_agent_url))
            .json(&serde_json::json!({ "natural_language": query }))
            .send()
            .await
            .map_err(|e| ApiError::bad_gateway(&e.to_string()))?;

        if !response.status().is_success() {
            return Err(ApiError::bad_gateway("DataAgent service error"));
        }

        response.json().await
            .map_err(|e| ApiError::internal_error(&e.to_string()))
    }

    pub async fn forward_knowledge(&self, query: &str) -> Result<serde_json::Value, ApiError> {
        let response = self.client
            .post(format!("{}/ka/search", CONFIG.ai_services.unified_agents_url))
            .json(&serde_json::json!({ "query": query }))
            .send()
            .await
            .map_err(|e| ApiError::bad_gateway(&e.to_string()))?;

        if !response.status().is_success() {
            return Err(ApiError::bad_gateway("KnowledgeAgent service error"));
        }

        response.json().await
            .map_err(|e| ApiError::internal_error(&e.to_string()))
    }

    pub async fn forward_mcp(&self, tool: &str, params: serde_json::Value) -> Result<serde_json::Value, ApiError> {
        let response = self.client
            .post(format!("{}/mcp/execute", CONFIG.ai_services.unified_agents_url))
            .json(&serde_json::json!({
                "tool": tool,
                "parameters": params
            }))
            .send()
            .await
            .map_err(|e| ApiError::bad_gateway(&e.to_string()))?;

        if !response.status().is_success() {
            return Err(ApiError::bad_gateway("MCPTools service error"));
        }

        response.json().await
            .map_err(|e| ApiError::internal_error(&e.to_string()))
    }

    pub async fn forward_bpa(&self, workflow: &str, params: serde_json::Value) -> Result<serde_json::Value, ApiError> {
        let response = self.client
            .post(format!("{}/start", CONFIG.ai_services.bpa_mm_agent_url))
            .json(&serde_json::json!({
                "workflow": workflow,
                "params": params
            }))
            .send()
            .await
            .map_err(|e| ApiError::bad_gateway(&e.to_string()))?;

        if !response.status().is_success() {
            return Err(ApiError::bad_gateway("BPA service error"));
        }

        response.json().await
            .map_err(|e| ApiError::internal_error(&e.to_string()))
    }
}

impl Default for AiProxy {
    fn default() -> Self {
        Self::new()
    }
}
