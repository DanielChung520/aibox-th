//! Todos Engine API
//!
//! # Description
//! Todo CRUD + 執行狀態管理 API
//!
//! # LastUpdate: 2026-05-11 00:00:00
//! # Author: AI Agent
//! # Version: 1.0.0

use axum::{
    extract::{Path, Query},
    response::IntoResponse,
    Json, Router,
    routing::{get, post},
};
use serde_json::{json, Value};
use std::collections::HashMap;

use crate::db::{get_db, TodoItem, TodoLog};
use crate::error::ApiError;
use crate::models::ApiResponse;
use crate::services::{PDCAController, PdcaVerdict, TodosEngine};

pub fn create_todos_router() -> Router {
    Router::new()
        .route("/api/v1/todos", get(list_todos).post(create_todo))
        .route("/api/v1/todos/{key}", get(get_todo).patch(update_todo).delete(delete_todo))
        .route("/api/v1/todos/{key}/start", post(start_todo))
        .route("/api/v1/todos/{key}/pause", post(pause_todo))
        .route("/api/v1/todos/{key}/restart", post(restart_todo))
        .route("/api/v1/todos/{key}/step/{step_index}/complete", post(complete_step))
        .route("/api/v1/todos/{key}/step/{step_index}/fail", post(fail_step))
        .route("/api/v1/todos/{key}/step/{step_index}/skip", post(skip_step))
        .route("/api/v1/todos/{key}/step/{step_index}/retry", post(retry_step))
        .route("/api/v1/todos/{key}/step/{step_index}/plan", post(step_plan))
        .route("/api/v1/todos/{key}/step/{step_index}/check", post(step_check))
        .route("/api/v1/todos/{key}/step/{step_index}/clarify", post(clarify_step))
        .route("/api/v1/todos/{key}/revise", post(revise_plan))
        .route("/api/v1/todos/{key}/logs", get(get_todo_logs))
}

async fn list_todos(Query(params): Query<HashMap<String, String>>) -> Result<impl IntoResponse, ApiError> {
    let db = get_db();
    let mut filter_parts: Vec<String> = Vec::new();
    let mut bind_keys: Vec<String> = Vec::new();
    let mut bind_vals: Vec<Value> = Vec::new();

    let filter_keys = ["status", "priority", "assigned_to"];
    for key in &filter_keys {
        if let Some(val) = params.get(*key) {
            let bind_key = format!("f_{}", key);
            filter_parts.push(format!("t.{} == @{}", key, bind_key));
            bind_keys.push(bind_key);
            bind_vals.push(json!(val));
        }
    }

    let filter_clause = if filter_parts.is_empty() {
        String::new()
    } else {
        format!("FILTER {}", filter_parts.join(" && "))
    };

    let query = format!("FOR t IN todos {} SORT t.created_at DESC RETURN t", filter_clause);
    let bind_map: HashMap<&str, Value> = bind_keys.iter().zip(bind_vals.into_iter())
        .map(|(k, v)| (k.as_str(), v))
        .collect();

    let todos: Vec<TodoItem> = db.aql_bind_vars(&query, bind_map)
        .await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;

    Ok(Json(ApiResponse::success(todos)))
}

async fn create_todo(Json(payload): Json<Value>) -> Result<impl IntoResponse, ApiError> {
    if payload.as_object().map(|o| o.is_empty()).unwrap_or(true) {
        return Err(ApiError::bad_request("Empty payload"));
    }
    let db = get_db();

    let now = chrono::Utc::now();
    let date_str = now.format("%y%m%d").to_string();
    let prefix = format!("TODO-{}", date_str);
    let count: f64 = db.aql_bind_vars(
        "FOR t IN todos FILTER t.todo_no LIKE @prefix RETURN 1",
        [("prefix", json!(format!("{}%", prefix)))].into(),
    ).await.ok().map(|v: Vec<Value>| v.len() as f64).unwrap_or(0.0);

    let todo_no = format!("{}-{:03}", prefix, count as i32 + 1);
    let now_str = now.to_rfc3339();

    let steps = payload.get("steps")
        .and_then(|s| s.as_array())
        .map(|arr| arr.to_vec())
        .unwrap_or_default();
    let total_steps = steps.len() as i32;

    let mut doc = payload;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert("_key".to_string(), json!(todo_no));
        obj.insert("todo_no".to_string(), json!(todo_no));
        obj.insert("status".to_string(), json!("pending"));
        obj.insert("current_step_index".to_string(), json!(0));
        obj.insert("total_steps".to_string(), json!(total_steps));
        obj.insert("progress".to_string(), json!(0));
        obj.insert("pdca_verdict".to_string(), json!("pending"));
        obj.insert("tags".to_string(), json!([]));
        obj.insert("created_at".to_string(), json!(now_str));
        obj.insert("updated_at".to_string(), json!(now_str));
        obj.remove("steps");
    }

    let col = db.collection("todos")
        .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
    col.create_document(doc, Default::default())
        .await.map_err(|e| ApiError::internal_error(&format!("Create failed: {e}")))?;

    let step_col = db.collection("todo_steps")
        .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;

    for (i, step) in steps.iter().enumerate() {
        let mut step_doc = step.clone();
        if let Some(obj) = step_doc.as_object_mut() {
            obj.insert("todo_key".to_string(), json!(todo_no));
            obj.insert("step_index".to_string(), json!(i));
            obj.insert("status".to_string(), json!("pending"));
            obj.insert("created_at".to_string(), json!(now_str));
        }
        step_col.create_document(step_doc, Default::default())
            .await.map_err(|e| ApiError::internal_error(&format!("Create step failed: {e}")))?;
    }

    Ok(Json(ApiResponse::success(json!({
        "_key": todo_no,
        "todo_no": todo_no,
        "status": "pending",
        "total_steps": total_steps,
    }))))
}

async fn get_todo(Path(key): Path<String>, Query(params): Query<HashMap<String, String>>) -> Result<impl IntoResponse, ApiError> {
    let db = get_db();
    let docs: Vec<Value> = db.aql_bind_vars(
        "FOR t IN todos FILTER t._key == @key LIMIT 1 RETURN t",
        [("key", json!(key))].into(),
    ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;

    let doc = docs.into_iter().next().ok_or_else(|| ApiError::not_found("Todo"))?;
    let include_steps = params.get("steps").map(|s| s == "true").unwrap_or(false);

    if include_steps {
        let steps: Vec<Value> = db.aql_bind_vars(
            "FOR s IN todo_steps FILTER s.todo_key == @key SORT s.step_index ASC RETURN s",
            [("key", json!(key))].into(),
        ).await.map_err(|e| ApiError::internal_error(&format!("Query steps failed: {e}")))?;

        return Ok(Json(ApiResponse::success(json!({"todo": doc, "steps": steps}))));
    }

    Ok(Json(ApiResponse::success(doc)))
}

async fn update_todo(Path(key): Path<String>, Json(payload): Json<Value>) -> Result<impl IntoResponse, ApiError> {
    if payload.is_null() || payload.as_object().map(|o| o.is_empty()).unwrap_or(true) {
        return Err(ApiError::bad_request("Empty payload"));
    }

    let db = get_db();
    let mut update_data = payload;
    if let Some(obj) = update_data.as_object_mut() {
        obj.remove("_key");
        obj.remove("_id");
        obj.remove("_rev");
        obj.remove("steps");
        obj.remove("todo_no");
        obj.remove("created_at");
        obj.insert("updated_at".to_string(), json!(chrono::Utc::now().to_rfc3339()));
    }

    let col = db.collection("todos")
        .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
    col.update_document(&key, update_data, Default::default())
        .await.map_err(|e| ApiError::internal_error(&format!("Update failed: {e}")))?;

    let docs: Vec<Value> = db.aql_bind_vars(
        "FOR t IN todos FILTER t._key == @key LIMIT 1 RETURN t",
        [("key", json!(key))].into(),
    ).await.map_err(|e| ApiError::internal_error(&format!("Query failed: {e}")))?;

    let doc = docs.into_iter().next().ok_or_else(|| ApiError::not_found("Todo"))?;
    Ok(Json(ApiResponse::success(doc)))
}

async fn delete_todo(Path(key): Path<String>) -> Result<impl IntoResponse, ApiError> {
    let db = get_db();
    let todo_col = db.collection("todos")
        .await.map_err(|e| ApiError::internal_error(&format!("Collection error: {e}")))?;
    todo_col.remove_document::<Value>(&key, Default::default(), None)
        .await.map_err(|e| ApiError::internal_error(&format!("Remove todo failed: {e}")))?;

    let _: Vec<Value> = db.aql_bind_vars(
        "FOR s IN todo_steps FILTER s.todo_key == @key REMOVE s IN todo_steps",
        [("key", json!(key))].into(),
    ).await.map_err(|e| ApiError::internal_error(&format!("Remove steps failed: {e}")))?;

    let _: Vec<Value> = db.aql_bind_vars(
        "FOR l IN todo_logs FILTER l.todo_key == @key REMOVE l IN todo_logs",
        [("key", json!(key))].into(),
    ).await.map_err(|e| ApiError::internal_error(&format!("Remove logs failed: {e}")))?;

    Ok(Json(ApiResponse::success("Todo deleted")))
}

async fn start_todo(Path(key): Path<String>) -> Result<impl IntoResponse, ApiError> {
    TodosEngine::start(&key).await?;
    Ok(Json(ApiResponse::success("Todo started")))
}

async fn pause_todo(Path(key): Path<String>) -> Result<impl IntoResponse, ApiError> {
    TodosEngine::pause(&key).await?;
    Ok(Json(ApiResponse::success("Todo paused")))
}

async fn restart_todo(Path(key): Path<String>) -> Result<impl IntoResponse, ApiError> {
    TodosEngine::restart(&key).await?;
    Ok(Json(ApiResponse::success("Todo restarted")))
}

async fn complete_step(Path((key, step_index)): Path<(String, i32)>, Json(payload): Json<Value>) -> Result<impl IntoResponse, ApiError> {
    let result = if payload.is_null() || payload.as_object().map(|o| o.is_empty()).unwrap_or(true) {
        None
    } else {
        Some(payload)
    };
    TodosEngine::complete_step(&key, step_index, result).await?;
    Ok(Json(ApiResponse::success("Step completed")))
}

async fn fail_step(Path((key, step_index)): Path<(String, i32)>, Json(payload): Json<Value>) -> Result<impl IntoResponse, ApiError> {
    let error_msg = payload.get("error").and_then(|v| v.as_str()).unwrap_or("Unknown error");
    TodosEngine::fail_step(&key, step_index, error_msg).await?;
    Ok(Json(ApiResponse::success("Step failed")))
}

async fn skip_step(Path((key, step_index)): Path<(String, i32)>) -> Result<impl IntoResponse, ApiError> {
    TodosEngine::skip_step(&key, step_index).await?;
    Ok(Json(ApiResponse::success("Step skipped")))
}

async fn retry_step(Path((key, step_index)): Path<(String, i32)>) -> Result<impl IntoResponse, ApiError> {
    TodosEngine::retry_step(&key, step_index).await?;
    Ok(Json(ApiResponse::success("Step retry started")))
}

async fn step_plan(Path((key, _step_index)): Path<(String, i32)>) -> Result<impl IntoResponse, ApiError> {
    let verdict = PDCAController::plan(&key).await?;
    match &verdict {
        PdcaVerdict::Approved => {
            TodosEngine::add_log(&key, None, "pdca_plan_approved", "Plan approved", Some(verdict.to_json())).await?;
        }
        PdcaVerdict::Rejected(reason) => {
            TodosEngine::pause_for_pdca(&key, "rejected", reason, Some(verdict.to_json())).await?;
        }
        PdcaVerdict::Clarify(question) => {
            TodosEngine::pause_for_pdca(&key, "clarify", question, Some(verdict.to_json())).await?;
        }
        PdcaVerdict::Escalate(reason) => {
            TodosEngine::pause_for_pdca(&key, "escalated", reason, Some(verdict.to_json())).await?;
        }
    }
    Ok(Json(ApiResponse::success(verdict.to_json())))
}

async fn step_check(Path((key, step_index)): Path<(String, i32)>) -> Result<impl IntoResponse, ApiError> {
    let verdict = PDCAController::check(&key, step_index).await?;
    match &verdict {
        PdcaVerdict::Approved => {
            TodosEngine::add_log(&key, Some(step_index), "pdca_check_approved", &format!("Step {} check approved", step_index), Some(verdict.to_json())).await?;
        }
        PdcaVerdict::Rejected(reason) => {
            TodosEngine::pause_for_pdca(&key, "rejected", reason, Some(verdict.to_json())).await?;
        }
        PdcaVerdict::Clarify(question) => {
            TodosEngine::pause_for_pdca(&key, "clarify", question, Some(verdict.to_json())).await?;
        }
        PdcaVerdict::Escalate(reason) => {
            TodosEngine::pause_for_pdca(&key, "escalated", reason, Some(verdict.to_json())).await?;
        }
    }
    Ok(Json(ApiResponse::success(verdict.to_json())))
}

async fn clarify_step(Path((key, _step_index)): Path<(String, i32)>, Json(payload): Json<Value>) -> Result<impl IntoResponse, ApiError> {
    let response = payload.get("response").and_then(|v| v.as_str()).ok_or_else(|| ApiError::bad_request("Missing 'response' field"))?;
    TodosEngine::resume_from_clarify(&key, response).await?;
    Ok(Json(ApiResponse::success("Clarification submitted, todo resumed")))
}

async fn revise_plan(Path(key): Path<String>, Json(payload): Json<Value>) -> Result<impl IntoResponse, ApiError> {
    let new_plan = payload.get("plan").and_then(|v| v.as_str()).ok_or_else(|| ApiError::bad_request("Missing 'plan' field"))?;
    TodosEngine::resume_from_clarify(&key, new_plan).await?;
    Ok(Json(ApiResponse::success("Plan revised, todo resumed")))
}

async fn get_todo_logs(Path(key): Path<String>) -> Result<impl IntoResponse, ApiError> {
    let db = get_db();
    let logs: Vec<TodoLog> = db.aql_bind_vars(
        "FOR l IN todo_logs FILTER l.todo_key == @key SORT l.created_at ASC RETURN l",
        [("key", json!(key))].into(),
    ).await.map_err(|e| ApiError::internal_error(&format!("Query logs failed: {e}")))?;

    Ok(Json(ApiResponse::success(logs)))
}


