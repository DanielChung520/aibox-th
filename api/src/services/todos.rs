//! Todos Engine — State Machine
//!
//! # Description
//! Todo 狀態機引擎，管理 todo 的生命週期與步驟推進
//!
//! # LastUpdate: 2026-05-11 00:00:00
//! # Author: AI Agent
//! # Version: 1.0.0

use crate::db::{get_db, TodoItem, TodoStep, TodoLog};
use crate::error::ApiError;
use chrono::Utc;
use serde_json::{json, Value};

pub struct TodosEngine;

impl TodosEngine {
    pub async fn start(todo_key: &str) -> Result<(), ApiError> {
        let db = get_db();
        let now = Utc::now().to_rfc3339();

        let todo_col = db.collection("todos")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        todo_col.update_document(todo_key, json!({
            "status": "running",
            "started_at": now,
            "updated_at": Utc::now().to_rfc3339(),
        }), Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Update todo failed: {e}")))?;

        let todos: Vec<TodoItem> = db.aql_bind_vars(
            "FOR t IN todos FILTER t._key == @key LIMIT 1 RETURN t",
            [("key", json!(todo_key))].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;
        let todo = todos.into_iter().next().ok_or_else(|| ApiError::not_found("Todo"))?;

        let step_idx = todo.current_step_index;
        let steps: Vec<TodoStep> = db.aql_bind_vars(
            "FOR s IN todo_steps FILTER s.todo_key == @key AND s.step_index == @idx LIMIT 1 RETURN s",
            [("key", json!(todo_key)), ("idx", json!(step_idx))].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;

        if let Some(step) = steps.into_iter().next() {
            if let Some(step_key) = step._key {
                let step_col = db.collection("todo_steps")
                    .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
                step_col.update_document(&step_key, json!({
                    "status": "running",
                    "started_at": Utc::now().to_rfc3339(),
                }), Default::default())
                    .await.map_err(|e| ApiError::internal_error(&format!("Update step failed: {e}")))?;
            }
        }

        Self::add_log(todo_key, Some(step_idx), "status_change", "Todo started", None).await?;
        Ok(())
    }

    pub async fn pause(todo_key: &str) -> Result<(), ApiError> {
        let db = get_db();
        let todo_col = db.collection("todos")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        todo_col.update_document(todo_key, json!({
            "status": "paused",
            "updated_at": Utc::now().to_rfc3339(),
        }), Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Update todo failed: {e}")))?;

        Self::add_log(todo_key, None, "status_change", "Todo paused", None).await?;
        Ok(())
    }

    pub async fn restart(todo_key: &str) -> Result<(), ApiError> {
        let db = get_db();
        let todo_col = db.collection("todos")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        todo_col.update_document(todo_key, json!({
            "status": "pending",
            "current_step_index": 0,
            "progress": 0,
            "error_message": null,
            "updated_at": Utc::now().to_rfc3339(),
        }), Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Update todo failed: {e}")))?;

        let _: Vec<Value> = db.aql_bind_vars(
            "FOR s IN todo_steps FILTER s.todo_key == @key UPDATE s._key WITH { status: \"pending\", result: null, error: null, duration_ms: null, started_at: null, completed_at: null } IN todo_steps",
            [("key", json!(todo_key))].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Reset steps failed: {e}")))?;

        Self::add_log(todo_key, None, "status_change", "Todo restarted", None).await?;
        Ok(())
    }

    pub async fn complete_step(todo_key: &str, step_index: i32, result: Option<Value>) -> Result<(), ApiError> {
        let db = get_db();
        let steps: Vec<TodoStep> = db.aql_bind_vars(
            "FOR s IN todo_steps FILTER s.todo_key == @key AND s.step_index == @idx LIMIT 1 RETURN s",
            [("key", json!(todo_key)), ("idx", json!(step_index))].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;
        let step = steps.into_iter().next().ok_or_else(|| ApiError::not_found("Step"))?;

        let duration_ms = step.started_at.as_ref()
            .and_then(|s| chrono::DateTime::parse_from_rfc3339(s).ok())
            .map(|start| (Utc::now() - start.with_timezone(&Utc)).num_milliseconds());

        let step_col = db.collection("todo_steps")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        let mut update = json!({
            "status": "completed",
            "completed_at": Utc::now().to_rfc3339(),
            "duration_ms": duration_ms,
        });
        if let Some(r) = result {
            update["result"] = r;
        }
        if let Some(step_key) = step._key {
            step_col.update_document(&step_key, update, Default::default())
                .await.map_err(|e| ApiError::internal_error(&format!("Update step failed: {e}")))?;
        }

        Self::add_log(todo_key, Some(step_index), "step_complete", &format!("Step {} completed", step_index), None).await?;
        Self::advance(todo_key).await?;
        Ok(())
    }

    pub async fn fail_step(todo_key: &str, step_index: i32, error_msg: &str) -> Result<(), ApiError> {
        let db = get_db();
        let steps: Vec<TodoStep> = db.aql_bind_vars(
            "FOR s IN todo_steps FILTER s.todo_key == @key AND s.step_index == @idx LIMIT 1 RETURN s",
            [("key", json!(todo_key)), ("idx", json!(step_index))].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;
        let step = steps.into_iter().next().ok_or_else(|| ApiError::not_found("Step"))?;

        let step_col = db.collection("todo_steps")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        if let Some(step_key) = step._key {
            step_col.update_document(&step_key, json!({
                "status": "failed",
                "error": error_msg,
            }), Default::default())
                .await.map_err(|e| ApiError::internal_error(&format!("Update step failed: {e}")))?;
        }

        let todo_col = db.collection("todos")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        todo_col.update_document(todo_key, json!({
            "status": "failed",
            "error_message": error_msg,
            "updated_at": Utc::now().to_rfc3339(),
        }), Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Update todo failed: {e}")))?;

        Self::add_log(todo_key, Some(step_index), "step_failed", &format!("Step {} failed: {}", step_index, error_msg), None).await?;
        Ok(())
    }

    pub async fn skip_step(todo_key: &str, step_index: i32) -> Result<(), ApiError> {
        let db = get_db();
        let steps: Vec<TodoStep> = db.aql_bind_vars(
            "FOR s IN todo_steps FILTER s.todo_key == @key AND s.step_index == @idx LIMIT 1 RETURN s",
            [("key", json!(todo_key)), ("idx", json!(step_index))].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;
        let step = steps.into_iter().next().ok_or_else(|| ApiError::not_found("Step"))?;

        let step_col = db.collection("todo_steps")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        if let Some(step_key) = step._key {
            step_col.update_document(&step_key, json!({
                "status": "skipped",
            }), Default::default())
                .await.map_err(|e| ApiError::internal_error(&format!("Update step failed: {e}")))?;
        }

        Self::add_log(todo_key, Some(step_index), "step_skipped", &format!("Step {} skipped", step_index), None).await?;
        Self::advance(todo_key).await?;
        Ok(())
    }

    pub async fn retry_step(todo_key: &str, step_index: i32) -> Result<(), ApiError> {
        let db = get_db();
        let steps: Vec<TodoStep> = db.aql_bind_vars(
            "FOR s IN todo_steps FILTER s.todo_key == @key AND s.step_index == @idx LIMIT 1 RETURN s",
            [("key", json!(todo_key)), ("idx", json!(step_index))].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;
        let step = steps.into_iter().next().ok_or_else(|| ApiError::not_found("Step"))?;

        let step_col = db.collection("todo_steps")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        if let Some(step_key) = step._key {
            step_col.update_document(&step_key, json!({
                "status": "pending",
                "error": null,
            }), Default::default())
                .await.map_err(|e| ApiError::internal_error(&format!("Update step failed: {e}")))?;
        }

        let todo_col = db.collection("todos")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        todo_col.update_document(todo_key, json!({
            "status": "running",
            "error_message": null,
            "updated_at": Utc::now().to_rfc3339(),
        }), Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Update todo failed: {e}")))?;

        Self::add_log(todo_key, Some(step_index), "step_retry", &format!("Step {} retry", step_index), None).await?;
        Ok(())
    }

    /// Pause todo when PDCA returns Rejected/Clarify/Escalate
    pub async fn pause_for_pdca(todo_key: &str, verdict: &str, reason: &str, details: Option<Value>) -> Result<(), ApiError> {
        let db = get_db();
        let now = Utc::now().to_rfc3339();
        let todo_col = db.collection("todos")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        todo_col.update_document(todo_key, json!({
            "status": "paused",
            "pdca_verdict": verdict,
            "pdca_summary": reason,
            "updated_at": now,
        }), Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Update todo failed: {e}")))?;

        Self::add_log(todo_key, None, &format!("pdca_{}", verdict), &format!("PDCA {}: {}", verdict, reason), details).await?;
        Ok(())
    }

    /// Resume todo after human clarifies or revises
    pub async fn resume_from_clarify(todo_key: &str, response_text: &str) -> Result<(), ApiError> {
        let db = get_db();
        let now = Utc::now().to_rfc3339();
        let todo_col = db.collection("todos")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        todo_col.update_document(todo_key, json!({
            "status": "running",
            "pdca_verdict": "pending",
            "pdca_summary": null,
            "updated_at": now,
        }), Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Update failed: {e}")))?;

        Self::add_log(todo_key, None, "pdca_clarified", &format!("Human response: {}", response_text), None).await?;
        Ok(())
    }

    async fn advance(todo_key: &str) -> Result<(), ApiError> {
        let db = get_db();
        let todos: Vec<TodoItem> = db.aql_bind_vars(
            "FOR t IN todos FILTER t._key == @key LIMIT 1 RETURN t",
            [("key", json!(todo_key))].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;
        let todo = todos.into_iter().next().ok_or_else(|| ApiError::not_found("Todo"))?;

        let next_idx = todo.current_step_index + 1;

        if next_idx >= todo.total_steps {
            Self::complete_todo(todo_key).await?;
        } else {
            let todo_col = db.collection("todos")
                .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;

            let progress = ((next_idx as f64 / todo.total_steps as f64) * 100.0) as i32;
            todo_col.update_document(todo_key, json!({
                "current_step_index": next_idx,
                "progress": progress.min(99),
                "updated_at": Utc::now().to_rfc3339(),
            }), Default::default())
                .await.map_err(|e| ApiError::internal_error(&format!("Update todo failed: {e}")))?;

            let next_steps: Vec<TodoStep> = db.aql_bind_vars(
                "FOR s IN todo_steps FILTER s.todo_key == @key AND s.step_index == @idx LIMIT 1 RETURN s",
                [("key", json!(todo_key)), ("idx", json!(next_idx))].into(),
            ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;

            if let Some(next_step) = next_steps.into_iter().next() {
                if let Some(step_key) = next_step._key {
                    let step_col = db.collection("todo_steps")
                        .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
                    step_col.update_document(&step_key, json!({
                        "status": "running",
                        "started_at": Utc::now().to_rfc3339(),
                    }), Default::default())
                        .await.map_err(|e| ApiError::internal_error(&format!("Update step failed: {e}")))?;
                }
            }

            Self::add_log(todo_key, Some(next_idx), "step_start", &format!("Step {} started", next_idx), None).await?;
        }

        Ok(())
    }

    async fn complete_todo(todo_key: &str) -> Result<(), ApiError> {
        let db = get_db();
        let now = Utc::now().to_rfc3339();
        let todo_col = db.collection("todos")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
        todo_col.update_document(todo_key, json!({
            "status": "completed", "progress": 100, "completed_at": now, "updated_at": now,
        }), Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Update todo failed: {e}")))?;

        Self::add_log(todo_key, None, "status_change", "Todo completed", None).await?;
        Ok(())
    }

    pub async fn add_log(todo_key: &str, step_index: Option<i32>, log_type: &str, message: &str, details: Option<Value>) -> Result<(), ApiError> {
        let db = get_db();
        let log_col = db.collection("todo_logs")
            .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;

        let log = TodoLog {
            _key: None,
            todo_key: todo_key.to_string(),
            step_index,
            log_type: log_type.to_string(),
            message: message.to_string(),
            details,
            created_at: Utc::now().to_rfc3339(),
        };

        log_col.create_document(log, Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Create log failed: {e}")))?;
        Ok(())
    }
}
