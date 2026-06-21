use axum::{
    extract::{Path, Query},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post, put, delete},
    Json, Router,
};
use crate::db::get_db;
use crate::models::*;
use chrono::Utc;
use std::collections::HashMap;

pub fn create_channel_router() -> Router {
    Router::new()
        .route("/api/v1/channels", get(list_channels).post(create_channel))
        .route("/api/v1/channels/{key}", get(get_channel).put(update_channel).delete(delete_channel))
}

async fn list_channels(
    Query(q): Query<HashMap<String, String>>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let mut filters = Vec::new();
    let mut bind: HashMap<&str, serde_json::Value> = HashMap::new();

    if let Some(p) = q.get("platform") {
        filters.push("c.platform == @platform");
        bind.insert("platform", serde_json::json!(p));
    }
    if let Some(b) = q.get("business_user_key") {
        filters.push("c.business_user_key == @business_user_key");
        bind.insert("business_user_key", serde_json::json!(b));
    }
    if let Some(r) = q.get("role") {
        filters.push("c.role == @role");
        bind.insert("role", serde_json::json!(r));
    }

    let aql = if filters.is_empty() {
        "FOR c IN channels SORT c.updated_at DESC RETURN c".to_string()
    } else {
        format!("FOR c IN channels FILTER {} SORT c.updated_at DESC RETURN c", filters.join(" AND "))
    };

    let docs: Vec<serde_json::Value> = db
        .aql_bind_vars(&aql, bind)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(docs)))
}

async fn get_channel(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR c IN channels FILTER c._key == @key LIMIT 1 RETURN c",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let doc = docs.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(doc)))
}

async fn create_channel(
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("channels").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let key = format!("ch_{}", uuid::Uuid::new_v4().to_string().split('-').next().unwrap_or("x"));
    let now = Utc::now().to_rfc3339();
    let webhook_path = format!("/webhook/{}", &key);

    let mut doc = payload.clone();
    if let Some(obj) = doc.as_object_mut() {
        obj.insert("_key".into(), serde_json::json!(key));
        obj.insert("status".into(), serde_json::json!("active"));
        obj.insert("webhook_path".into(), serde_json::json!(webhook_path));
        obj.insert("created_by".into(), serde_json::json!("admin"));
        obj.insert("created_at".into(), serde_json::json!(now));
        obj.insert("updated_at".into(), serde_json::json!(now));
    }

    col.create_document(doc.clone(), Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(doc)))
}

async fn update_channel(
    Path(key): Path<String>,
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("channels").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut update = serde_json::json!({ "updated_at": Utc::now().to_rfc3339() });
    if let Some(config) = payload.get("config") { update["config"] = config.clone(); }
    if let Some(status) = payload.get("status") { update["status"] = status.clone(); }
    if let Some(avatar) = payload.get("avatar") { update["avatar"] = avatar.clone(); }
    if let Some(role) = payload.get("role") { update["role"] = role.clone(); }
    if let Some(business_user_key) = payload.get("business_user_key") { update["business_user_key"] = business_user_key.clone(); }
    if let Some(business_user_name) = payload.get("business_user_name") { update["business_user_name"] = business_user_name.clone(); }
    if let Some(linked_agent_key) = payload.get("linked_agent_key") { update["linked_agent_key"] = linked_agent_key.clone(); }

    col.update_document(&key, update, Default::default())
        .await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let docs: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR c IN channels FILTER c._key == @key LIMIT 1 RETURN c",
            [("key", serde_json::json!(key))].into(),
        ).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let doc = docs.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(doc)))
}

async fn delete_channel(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("channels").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<serde_json::Value>(&key, Default::default(), None)
        .await.map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success("已刪除".to_string())))
}
