//! PDCA Controller
//!
//! # Description
//! PDCA 控制器 — 透過 Ollama 對 todo/step 進行 Plan/Check 審查
//!
//! # LastUpdate: 2026-05-11 00:00:00
//! # Author: AI Agent
//! # Version: 1.0.0

use crate::db::get_db;
use crate::error::ApiError;
use serde_json::{json, Value};

pub enum PdcaVerdict {
    Approved,
    Rejected(String),
    Clarify(String),
    Escalate(String),
}

impl PdcaVerdict {
    pub fn to_json(&self) -> Value {
        match self {
            PdcaVerdict::Approved => json!({"verdict": "approved"}),
            PdcaVerdict::Rejected(reason) => json!({"verdict": "rejected", "reason": reason}),
            PdcaVerdict::Clarify(question) => json!({"verdict": "clarify", "question": question}),
            PdcaVerdict::Escalate(reason) => json!({"verdict": "escalate", "reason": reason}),
        }
    }
}

pub struct PDCAController;

impl PDCAController {
    pub async fn plan(todo_key: &str) -> Result<PdcaVerdict, ApiError> {
        let db = get_db();
        let docs: Vec<Value> = db
            .aql_bind_vars(
                "FOR t IN todos FILTER t._key == @key LIMIT 1 RETURN t",
                [("key", json!(todo_key))].into(),
            )
            .await
            .map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;
        let todo = docs
            .into_iter()
            .next()
            .ok_or_else(|| ApiError::not_found("Todo"))?;

        let title = todo.get("title").and_then(|v| v.as_str()).unwrap_or("");
        let desc = todo.get("description").and_then(|v| v.as_str()).unwrap_or("");

        let prompt = format!(
            r#"You are a PDCA Plan reviewer. Review the following todo plan:

Title: {title}
Description: {desc}

Respond with exactly one of:
APPROVED
REJECTED: <reason>
CLARIFY: <question>
ESCALATE: <reason>"#,
            title = title,
            desc = desc,
        );

        let response = Self::call_llm(&prompt).await?;
        Ok(Self::parse_verdict(&response))
    }

    pub async fn check(todo_key: &str, step_index: i32) -> Result<PdcaVerdict, ApiError> {
        let db = get_db();

        let docs: Vec<Value> = db
            .aql_bind_vars(
                "FOR t IN todos FILTER t._key == @key LIMIT 1 RETURN t",
                [("key", json!(todo_key))].into(),
            )
            .await
            .map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;
        let todo = docs
            .into_iter()
            .next()
            .ok_or_else(|| ApiError::not_found("Todo"))?;

        let steps: Vec<Value> = db
            .aql_bind_vars(
                "FOR s IN todo_steps FILTER s.todo_key == @key AND s.step_index == @idx LIMIT 1 RETURN s",
                [("key", json!(todo_key)), ("idx", json!(step_index))].into(),
            )
            .await
            .map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;
        let step = steps
            .into_iter()
            .next()
            .ok_or_else(|| ApiError::not_found("Step"))?;

        let title = todo.get("title").and_then(|v| v.as_str()).unwrap_or("");
        let step_title = step
            .get("step_title")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let step_result = step
            .get("result")
            .map(|v| v.to_string())
            .unwrap_or_default();

        let prompt = format!(
            r#"You are a PDCA Check reviewer. Review the following step result:

Todo: {title}
Step: {step_title}
Result: {step_result}

Respond with exactly one of:
APPROVED
REJECTED: <reason>
CLARIFY: <question>
ESCALATE: <reason>"#,
            title = title,
            step_title = step_title,
            step_result = step_result,
        );

        let response = Self::call_llm(&prompt).await?;
        Ok(Self::parse_verdict(&response))
    }

    fn parse_verdict(response: &str) -> PdcaVerdict {
        let trimmed = response.trim();
        if trimmed.starts_with("APPROVED") {
            PdcaVerdict::Approved
        } else if let Some(reason) = trimmed.strip_prefix("REJECTED:") {
            PdcaVerdict::Rejected(reason.trim().to_string())
        } else if let Some(question) = trimmed.strip_prefix("CLARIFY:") {
            PdcaVerdict::Clarify(question.trim().to_string())
        } else if let Some(reason) = trimmed.strip_prefix("ESCALATE:") {
            PdcaVerdict::Escalate(reason.trim().to_string())
        } else {
            PdcaVerdict::Clarify(format!("Could not parse verdict: {response}"))
        }
    }

    async fn call_llm(prompt: &str) -> Result<String, ApiError> {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(60))
            .build()
            .map_err(|e| ApiError::internal_error(&format!("Client build failed: {e}")))?;

        let resp = client
            .post("http://localhost:11434/api/chat")
            .json(&json!({
                "model": "llama3.2:latest",
                "messages": [{"role": "user", "content": prompt}],
                "stream": false,
                "options": {"temperature": 0.3, "num_predict": 512}
            }))
            .send()
            .await
            .map_err(|e| ApiError::internal_error(&format!("Ollama call failed: {e}")))?
            .json::<Value>()
            .await
            .map_err(|e| ApiError::internal_error(&format!("Parse failed: {e}")))?;

        resp["message"]["content"]
            .as_str()
            .map(String::from)
            .ok_or_else(|| ApiError::internal_error("Empty LLM response"))
    }
}
