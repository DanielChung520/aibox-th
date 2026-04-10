//! Ontology API
//!
//! # Last Update: 2026-03-25 11:53:22
//! # Author: Daniel Chung
//! # Version: 1.0.0

use crate::db::{get_db, ontology::Ontology};
use axum::{
    extract::{Path, Query},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde_json::json;
use std::collections::HashMap;

pub async fn list_ontologies(
    Query(params): Query<HashMap<String, String>>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let (query, bind_vars) = if let Some(ont_type) = params.get("type").filter(|s| !s.is_empty()) {
        (
            "FOR o IN ontologies FILTER o.type == @type SORT o.name ASC RETURN o".to_string(),
            [("type", json!(ont_type))].into(),
        )
    } else {
        (
            "FOR o IN ontologies SORT o.type ASC, o.name ASC RETURN o".to_string(),
            HashMap::new(),
        )
    };

    let ontologies: Vec<Ontology> = db
        .aql_bind_vars(&query, bind_vars)
        .await
        .map_err(|_| err_500())?;

    Ok(Json(json!({ "code": 200, "data": ontologies })))
}

pub async fn get_ontology(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();
    let mut results: Vec<Ontology> = db
        .aql_bind_vars(
            "FOR o IN ontologies FILTER o._key == @key LIMIT 1 RETURN o",
            [("key", json!(key))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    let ont = results.pop().ok_or_else(|| err_404("ontology"))?;
    Ok(Json(json!({ "code": 200, "data": ont })))
}

pub async fn create_ontology(
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();
    let col = db.collection("ontologies").await.map_err(|_| err_500())?;

    let ont_type = payload.get("type").and_then(|v| v.as_str()).unwrap_or("domain");
    let name = payload.get("name").and_then(|v| v.as_str()).unwrap_or("Unnamed");
    let key = format!("{}_{}", ont_type, chrono::Utc::now().timestamp_millis());

    let ont = Ontology {
        _key: Some(key.clone()),
        ontology_type: ont_type.to_string(),
        name: name.to_string(),
        version: payload.get("version").and_then(|v| v.as_str()).unwrap_or("1.0").to_string(),
        default_version: payload.get("default_version").and_then(|v| v.as_bool()).unwrap_or(true),
        ontology_name: payload.get("ontology_name").and_then(|v| v.as_str()).unwrap_or(name).to_string(),
        description: payload.get("description").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        author: payload.get("author").and_then(|v| v.as_str()).unwrap_or("System").to_string(),
        last_modified: chrono::Utc::now().format("%Y-%m-%d").to_string(),
        inherits_from: extract_string_array(&payload, "inherits_from"),
        compatible_domains: payload.get("compatible_domains").and_then(|v| v.as_array()).map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect()),
        tags: extract_string_array(&payload, "tags"),
        use_cases: extract_string_array(&payload, "use_cases"),
        entity_classes: serde_json::from_value(payload.get("entity_classes").cloned().unwrap_or(json!([]))).unwrap_or_default(),
        object_properties: serde_json::from_value(payload.get("object_properties").cloned().unwrap_or(json!([]))).unwrap_or_default(),
        metadata: serde_json::from_value(payload.get("metadata").cloned().unwrap_or(json!({}))).unwrap_or(crate::db::ontology::OntologyMetadata {
            domain_owner: None,
            domain: None,
            major_owner: None,
            data_classification: None,
            intended_usage: None,
        }),
        status: payload.get("status").and_then(|v| v.as_str()).map(String::from).or(Some("enabled".into())),
    };

    col.create_document(ont, Default::default())
        .await
        .map_err(|_| err_500())?;

    Ok((
        StatusCode::CREATED,
        Json(json!({ "code": 201, "data": { "_key": key } })),
    ))
}

pub async fn import_ontology(
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    create_ontology(Json(payload)).await
}

pub async fn update_ontology(
    Path(key): Path<String>,
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let existing: Vec<Ontology> = db
        .aql_bind_vars(
            "FOR o IN ontologies FILTER o._key == @key LIMIT 1 RETURN o",
            [("key", json!(key.clone()))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    if existing.is_empty() {
        return Err(err_404("ontology"));
    }

    let mut data = payload;
    if let Some(obj) = data.as_object_mut() {
        obj.remove("_key");
        obj.remove("_id");
        obj.insert("last_modified".to_string(), json!(chrono::Utc::now().format("%Y-%m-%d").to_string()));
    }

    let _: Vec<Ontology> = db
        .aql_bind_vars(
            "FOR o IN ontologies FILTER o._key == @key UPDATE o WITH @data IN ontologies RETURN NEW",
            [("key", json!(key)), ("data", data)].into(),
        )
        .await
        .map_err(|_| err_500())?;

    Ok(Json(json!({ "code": 200, "message": "updated" })))
}

pub async fn delete_ontology(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let mut results: Vec<Ontology> = db
        .aql_bind_vars(
            "FOR o IN ontologies FILTER o._key == @key LIMIT 1 RETURN o",
            [("key", json!(key.clone()))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    let ont = results.pop().ok_or_else(|| err_404("ontology"))?;

    if ont.ontology_type == "domain" {
        let children: Vec<serde_json::Value> = db
            .aql_bind_vars(
                "FOR o IN ontologies FILTER o.type == 'major' AND (@domain_name IN o.inherits_from OR o.metadata.domain == @name) LIMIT 1 RETURN o._key",
                [
                    ("domain_name", json!(ont.ontology_name)),
                    ("name", json!(ont.name)),
                ]
                .into(),
            )
            .await
            .map_err(|_| err_500())?;

        if !children.is_empty() {
            return Err((
                StatusCode::CONFLICT,
                Json(json!({
                    "code": 409,
                    "message": "無法刪除：此 Domain 下仍有 Major Ontology，請先刪除子項目。"
                })),
            ));
        }
    }

    let _: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "REMOVE @key IN ontologies",
            [("key", json!(key))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    Ok(Json(json!({ "code": 200, "message": "deleted" })))
}

fn extract_string_array(payload: &serde_json::Value, field: &str) -> Vec<String> {
    payload
        .get(field)
        .and_then(|v| v.as_array())
        .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
        .unwrap_or_default()
}

fn err_500() -> (StatusCode, Json<serde_json::Value>) {
    (
        StatusCode::INTERNAL_SERVER_ERROR,
        Json(json!({ "code": 500, "message": "internal server error" })),
    )
}

fn err_404(resource: &str) -> (StatusCode, Json<serde_json::Value>) {
    (
        StatusCode::NOT_FOUND,
        Json(json!({ "code": 404, "message": format!("{} not found", resource) })),
    )
}
