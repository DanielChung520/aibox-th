//! Theme Templates API
//!
//! # Last Update: 2026-03-25 15:07:58
//! # Author: Daniel Chung
//! # Version: 1.1.0

use crate::db::{get_db, themes::ThemeTemplate};
use axum::{extract::Path, http::StatusCode, response::IntoResponse, Json};
use serde_json::json;

pub async fn list_theme_templates(
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();
    let templates: Vec<ThemeTemplate> = db
        .aql_str("FOR t IN theme_templates SORT t.template_type, t.name RETURN t")
        .await
        .map_err(|_| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "code": 500, "message": "internal server error" })),
            )
        })?;

    Ok(Json(json!({ "code": 200, "data": templates })))
}

pub async fn get_theme_template(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();
    let mut templates: Vec<ThemeTemplate> = db
        .aql_bind_vars(
            "FOR t IN theme_templates FILTER t._key == @key RETURN t",
            [("key", json!(key))].into(),
        )
        .await
        .map_err(|_| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "code": 500, "message": "internal server error" })),
            )
        })?;

    let template = templates.pop().ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(json!({ "code": 404, "message": "not found" })),
        )
    })?;

    Ok(Json(json!({ "code": 200, "data": template })))
}

pub async fn create_theme_template(
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();
    let col = db.collection("theme_templates").await.map_err(|_| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "code": 500, "message": "internal server error" })),
        )
    })?;

    let now = chrono::Utc::now().to_rfc3339();
    let mut template = payload;
    if let Some(obj) = template.as_object_mut() {
        obj.insert("created_at".to_string(), json!(now.clone()));
        obj.insert("updated_at".to_string(), json!(now));
    } else {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(json!({ "code": 400, "message": "invalid payload" })),
        ));
    }

    col.create_document(template, Default::default())
        .await
        .map_err(|_| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "code": 500, "message": "internal server error" })),
            )
        })?;

    Ok((
        StatusCode::CREATED,
        Json(json!({ "code": 201, "message": "created" })),
    ))
}

pub async fn update_theme_template(
    Path(key): Path<String>,
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let mut data = payload;
    if let Some(obj) = data.as_object_mut() {
        obj.insert("updated_at".to_string(), json!(chrono::Utc::now().to_rfc3339()));
    } else {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(json!({ "code": 400, "message": "invalid payload" })),
        ));
    }

    let updated: Vec<ThemeTemplate> = db
        .aql_bind_vars(
            "FOR t IN theme_templates FILTER t._key == @key UPDATE t WITH @data IN theme_templates RETURN NEW",
            [
                ("key", json!(key)),
                ("data", data),
            ]
            .into(),
        )
        .await
        .map_err(|_| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "code": 500, "message": "internal server error" })),
            )
        })?;

    if updated.is_empty() {
        return Err((
            StatusCode::NOT_FOUND,
            Json(json!({ "code": 404, "message": "not found" })),
        ));
    }

    Ok(Json(json!({ "code": 200, "message": "updated" })))
}

pub async fn delete_theme_template(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let existing: Vec<ThemeTemplate> = db
        .aql_bind_vars(
            "FOR t IN theme_templates FILTER t._key == @key LIMIT 1 RETURN t",
            [("key", json!(key.clone()))].into(),
        )
        .await
        .map_err(|_| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "code": 500, "message": "internal server error" })),
            )
        })?;

    let template = existing.into_iter().next().ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(json!({ "code": 404, "message": "not found" })),
        )
    })?;

    if template.is_default {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(json!({ "code": 400, "message": "cannot delete default template" })),
        ));
    }

    let _: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "REMOVE @key IN theme_templates",
            [("key", json!(key))].into(),
        )
        .await
        .map_err(|_| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "code": 500, "message": "internal server error" })),
            )
        })?;

    Ok(Json(json!({ "code": 200, "message": "deleted" })))
}

pub async fn activate_theme_template(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let mut templates: Vec<ThemeTemplate> = db
        .aql_bind_vars(
            "FOR t IN theme_templates FILTER t._key == @key LIMIT 1 RETURN t",
            [("key", json!(key.clone()))].into(),
        )
        .await
        .map_err(|_| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "code": 500, "message": "internal server error" })),
            )
        })?;

    let template = templates.pop().ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(json!({ "code": 404, "message": "not found" })),
        )
    })?;

    if template.template_type == "shell" {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(json!({ "code": 400, "message": "cannot activate shell template" })),
        ));
    }

    let _: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR t IN theme_templates FILTER t.template_type == @type UPDATE t WITH { is_default: false } IN theme_templates",
            [("type", json!(template.template_type.clone()))].into(),
        )
        .await
        .map_err(|_| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "code": 500, "message": "internal server error" })),
            )
        })?;

    let _: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "UPDATE @key WITH { is_default: true } IN theme_templates",
            [("key", json!(key))].into(),
        )
        .await
        .map_err(|_| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "code": 500, "message": "internal server error" })),
            )
        })?;

    Ok(Json(json!({ "code": 200, "message": "activated" })))
}
