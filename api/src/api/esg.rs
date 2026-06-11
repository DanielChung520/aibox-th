use axum::{
    extract::Path,
    http::StatusCode,
    response::IntoResponse,
    routing::{delete, get, post, put},
    Json, Router,
};
use serde_json::Value;

use crate::db::get_db;
use crate::models::ApiResponse;

async fn list_factors() -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<Value> = db
        .aql_str("FOR f IN esg_emission_factors SORT f.source_type, f.source_name RETURN f")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(docs)))
}

async fn create_factor(Json(payload): Json<Value>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("esg_emission_factors").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let now = chrono::Utc::now().to_rfc3339();
    let mut doc = payload;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert("created_at".to_string(), Value::String(now.clone()));
        obj.insert("updated_at".to_string(), Value::String(now));
    }
    col.create_document(doc, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success("created")))
}

async fn update_factor(
    Path(key): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("esg_emission_factors").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let now = chrono::Utc::now().to_rfc3339();
    let mut doc = payload;
    if let Some(obj) = doc.as_object_mut() {
        obj.insert("updated_at".to_string(), Value::String(now));
    }
    col.update_document(&key, doc, Default::default())
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(key)))
}

async fn delete_factor(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("esg_emission_factors").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<Value>(&key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(key)))
}

async fn list_records() -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<Value> = db
        .aql_str("FOR r IN esg_carbon_records SORT r.submitted_at DESC RETURN r")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(docs)))
}

async fn get_record(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let mut docs: Vec<Value> = db
        .aql_bind_vars(
            "FOR r IN esg_carbon_records FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", Value::String(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc = docs.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(doc)))
}

pub fn create_esg_router() -> Router {
    Router::new()
        .route("/api/v1/esg/factors", get(list_factors).post(create_factor))
        .route("/api/v1/esg/factors/{key}", put(update_factor).delete(delete_factor))
        .route("/api/v1/esg/records", get(list_records))
        .route("/api/v1/esg/records/{key}", get(get_record))
}
