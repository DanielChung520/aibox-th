/**
 * @file        schedules.rs
 * @description 排程訊息 CRUD — 問候/促銷/公告 的排程管理
 * @lastUpdate  2026-06-20
 * @author      Sisyphus
 * @version     1.0.0
 */

use crate::auth::verify_jwt;
use crate::db::get_db;
use axum::{
    extract::{Path, Query},
    http::{header::AUTHORIZATION, HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{get, post, patch, delete},
    Extension, Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::sync::Arc;

pub fn create_schedules_router() -> Router {
    Router::new()
        .route("/api/v1/crm/schedules", get(list_schedules).post(create_schedule))
        .route("/api/v1/crm/schedules/{key}", patch(update_schedule).delete(delete_schedule))
}

#[derive(Debug, Deserialize)]
pub struct ListSchedulesQuery {
    pub business_user_key: Option<String>,
    pub message_type: Option<String>,
    pub is_active: Option<bool>,
}

#[derive(Debug, Deserialize)]
pub struct CreateSchedulePayload {
    pub business_user_key: String,
    pub name: Option<String>,
    pub message_type: Option<String>,
    pub template_text: Option<String>,
    pub schedule_time: Option<String>,
    pub schedule_type: Option<String>,
    pub target_type: Option<String>,
    pub target_config: Option<Value>,
    pub content_mode: Option<String>,
    pub ai_prompt: Option<String>,
    pub is_active: Option<bool>,
}

#[derive(Debug, Deserialize)]
pub struct UpdateSchedulePayload {
    pub name: Option<String>,
    pub message_type: Option<String>,
    pub template_text: Option<String>,
    pub schedule_time: Option<String>,
    pub schedule_type: Option<String>,
    pub target_type: Option<String>,
    pub target_config: Option<Value>,
    pub content_mode: Option<String>,
    pub ai_prompt: Option<String>,
    pub is_active: Option<bool>,
}

fn now_iso() -> String {
    chrono::Utc::now().to_rfc3339()
}

async fn list_schedules(
    Query(params): Query<ListSchedulesQuery>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let mut filters = Vec::new();
    let mut bind_vars: Vec<(&str, Value)> = Vec::new();

    if let Some(ref buk) = params.business_user_key {
        if !buk.is_empty() {
            filters.push("s.business_user_key == @business_user_key");
            bind_vars.push(("business_user_key", json!(buk)));
        }
    }
    if let Some(ref mt) = params.message_type {
        if !mt.is_empty() {
            filters.push("s.message_type == @message_type");
            bind_vars.push(("message_type", json!(mt)));
        }
    }
    if let Some(active) = params.is_active {
        filters.push("s.is_active == @is_active");
        bind_vars.push(("is_active", json!(active)));
    }

    let where_clause = if filters.is_empty() {
        String::new()
    } else {
        format!("FILTER {}", filters.join(" && "))
    };

    let aql = format!(
        r#"
        FOR s IN message_schedules {}
            SORT s.created_at DESC
            RETURN s
        "#, where_clause
    );
    let bind = bind_vars.iter().map(|(k, v)| (*k, v.clone())).collect();
    let results: Vec<Value> = db.aql_bind_vars(&aql, bind).await.map_err(|e| {
        eprintln!("schedules list error: {}", e);
        (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({"code": 500, "message": "internal error"})))
    })?;

    Ok(Json(json!({"code": 200, "data": results})))
}

async fn create_schedule(
    headers: HeaderMap,
    Json(payload): Json<CreateSchedulePayload>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col = db.collection("message_schedules").await.map_err(|_| {
        (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({"code": 500, "message": "collection not found"})))
    })?;

    let token = headers.get(AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .and_then(|t| verify_jwt(t).ok());
    let user_key = token.map(|t| t.claims.username).unwrap_or_default();
    let now = now_iso();
    let key = uuid::Uuid::new_v4().to_string();

    let mut doc = serde_json::Map::new();
    doc.insert("_key".into(), json!(key));
    doc.insert("business_user_key".into(), json!(payload.business_user_key));
    doc.insert("message_type".into(), json!(payload.message_type.unwrap_or_else(|| "greeting".into())));
    doc.insert("schedule_type".into(), json!(payload.schedule_type.unwrap_or_else(|| "recurring".into())));
    doc.insert("target_type".into(), json!(payload.target_type.unwrap_or_else(|| "all".into())));
    doc.insert("content_mode".into(), json!(payload.content_mode.unwrap_or_else(|| "template".into())));
    doc.insert("is_active".into(), json!(payload.is_active.unwrap_or(true)));
    doc.insert("sent_count".into(), json!(0));
    doc.insert("created_at".into(), json!(now.clone()));
    doc.insert("updated_at".into(), json!(now));
    doc.insert("created_by".into(), json!(user_key));

    if let Some(v) = payload.name { doc.insert("name".into(), json!(v)); }
    if let Some(v) = payload.template_text { doc.insert("template_text".into(), json!(v)); }
    if let Some(v) = payload.schedule_time { doc.insert("schedule_time".into(), json!(v)); }
    if let Some(v) = payload.target_config { doc.insert("target_config".into(), v); }
    if let Some(v) = payload.ai_prompt { doc.insert("ai_prompt".into(), json!(v)); }

    let doc_val = Value::Object(doc);
    col.create_document(doc_val.clone(), Default::default()).await.map_err(|e| {
        eprintln!("schedules create error: {}", e);
        (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({"code": 500, "message": "create failed"})))
    })?;

    Ok(Json(json!({"code": 200, "message": "created", "data": doc_val})))
}

async fn update_schedule(
    Path(key): Path<String>,
    Json(payload): Json<UpdateSchedulePayload>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col = db.collection("message_schedules").await.map_err(|_| {
        (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({"code": 500, "message": "collection not found"})))
    })?;

    let mut patch = serde_json::Map::new();
    if let Some(v) = payload.name { patch.insert("name".into(), json!(v)); }
    if let Some(v) = payload.message_type { patch.insert("message_type".into(), json!(v)); }
    if let Some(v) = payload.template_text { patch.insert("template_text".into(), json!(v)); }
    if let Some(v) = payload.schedule_time { patch.insert("schedule_time".into(), json!(v)); }
    if let Some(v) = payload.schedule_type { patch.insert("schedule_type".into(), json!(v)); }
    if let Some(v) = payload.target_type { patch.insert("target_type".into(), json!(v)); }
    if let Some(v) = payload.target_config { patch.insert("target_config".into(), v); }
    if let Some(v) = payload.content_mode { patch.insert("content_mode".into(), json!(v)); }
    if let Some(v) = payload.ai_prompt { patch.insert("ai_prompt".into(), json!(v)); }
    if let Some(v) = payload.is_active { patch.insert("is_active".into(), json!(v)); }

    if patch.is_empty() {
        return Err((StatusCode::BAD_REQUEST, Json(json!({"code": 400, "message": "no fields to update"}))));
    }
    patch.insert("updated_at".into(), json!(now_iso()));

    col.update_document(&key, Value::Object(patch), Default::default()).await.map_err(|_| {
        (StatusCode::NOT_FOUND, Json(json!({"code": 404, "message": "schedule not found"})))
    })?;

    Ok(Json(json!({"code": 200, "message": "updated"})))
}

async fn delete_schedule(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col = db.collection("message_schedules").await.map_err(|_| {
        (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({"code": 500, "message": "collection not found"})))
    })?;

    col.remove_document::<Value>(&key, Default::default(), None).await.map_err(|_| {
        (StatusCode::NOT_FOUND, Json(json!({"code": 404, "message": "schedule not found"})))
    })?;

    Ok(Json(json!({"code": 200, "message": "deleted"})))
}
