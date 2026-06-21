use axum::{
    extract::Path,
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post, put, delete},
    Json, Router,
};
use crate::db::get_db;
use crate::models::*;
use chrono::Utc;
use serde_json::json;

pub fn create_business_users_router() -> Router {
    Router::new()
        .route("/api/v1/business-users", get(list_business_users).post(create_business_user))
        .route("/api/v1/business-users/{key}", get(get_business_user).put(update_business_user).delete(delete_business_user))
        .route("/api/v1/business-users/{key}/channels", get(get_business_user_channels))
}

async fn list_business_users() -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR u IN business_users SORT u.created_at DESC RETURN u",
            std::collections::HashMap::new(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(docs)))
}

async fn get_business_user(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR u IN business_users FILTER u._key == @key LIMIT 1 RETURN u",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc = docs.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(doc)))
}

async fn create_business_user(
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("business_users").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let key = format!("bu_{}", uuid::Uuid::new_v4().to_string().split('-').next().unwrap_or("x"));
    let now = Utc::now().to_rfc3339();

    let mut doc = payload.clone();
    if let Some(obj) = doc.as_object_mut() {
        obj.insert("_key".into(), serde_json::json!(key));
        obj.insert("status".into(), serde_json::json!("active"));
        obj.insert("created_at".into(), serde_json::json!(now));
        obj.insert("updated_at".into(), serde_json::json!(now));
        if !obj.contains_key("persona_config") {
            obj.insert("persona_config".into(), serde_json::json!({}));
        }
    }

    col.create_document(doc.clone(), Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(doc)))
}

async fn update_business_user(
    Path(key): Path<String>,
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("business_users").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut update = json!({ "updated_at": Utc::now().to_rfc3339() });
    if let Some(name) = payload.get("name") { update["name"] = name.clone(); }
    if let Some(region) = payload.get("region") { update["region"] = region.clone(); }
    if let Some(team) = payload.get("team") { update["team"] = team.clone(); }
    if let Some(role) = payload.get("role") { update["role"] = role.clone(); }
    if let Some(status) = payload.get("status") { update["status"] = status.clone(); }
    if let Some(persona) = payload.get("persona_config") { update["persona_config"] = persona.clone(); }

    col.update_document(&key, update, Default::default())
        .await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let docs: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR u IN business_users FILTER u._key == @key LIMIT 1 RETURN u",
            [("key", serde_json::json!(key))].into(),
        ).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let doc = docs.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(doc)))
}

async fn delete_business_user(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("business_users").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<serde_json::Value>(&key, Default::default(), None)
        .await.map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success("已刪除".to_string())))
}

async fn get_business_user_channels(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR c IN channels FILTER c.business_user_key == @key SORT c.updated_at DESC RETURN c",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(docs)))
}
