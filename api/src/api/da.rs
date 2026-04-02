//! Data Agent Schema API Routes
//!
//! # Description
//! DA 的 Schema CRUD endpoints (tables, fields, relations)
//! 支援雙資料源 (SAP + Ragic)
//!
//! # Last Update: 2026-04-02 17:45:00
//! # Author: Daniel Chung
//! # Version: 2.0.0

use crate::db::get_db;
use crate::models::ApiResponse;
use axum::{
    extract::{Path, Query},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, put},
    Json, Router,
};
use serde_json::Value;
use std::collections::HashMap;

fn resolve_collection_name(base: &str, data_source: &str) -> String {
    match (base, data_source) {
        // SAP uses legacy collection names (no suffix)
        ("table_info", "sap") => "da_table_info".to_string(),
        ("field_info", "sap") => "da_field_info".to_string(),
        ("relation", "sap") => "da_table_relation".to_string(),
        // Ragic uses _ragic suffix
        ("table_info", "ragic") => "da_table_info_ragic".to_string(),
        ("field_info", "ragic") => "da_field_info_ragic".to_string(),
        ("relation", "ragic") => "da_table_relation_ragic".to_string(),
        _ => format!("da_{}_{}", base, data_source),
    }
}

pub fn create_da_router() -> Router {
    Router::new()
        .route(
            "/api/v1/da/schema/tables",
            get(list_tables).post(create_table),
        )
        .route(
            "/api/v1/da/schema/tables/{table_id}",
            get(get_table).put(update_table).delete(delete_table),
        )
        .route(
            "/api/v1/da/schema/tables/{table_id}/fields",
            get(list_fields).post(create_field),
        )
        .route(
            "/api/v1/da/schema/tables/{table_id}/fields/{field_id}",
            put(update_field).delete(delete_field),
        )
        .route(
            "/api/v1/da/schema/relations",
            get(list_relations).post(create_relation),
        )
        .route(
            "/api/v1/da/schema/relations/{relation_id}",
            put(update_relation).delete(delete_relation),
        )
}

async fn list_tables(
    Query(params): Query<HashMap<String, String>>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let data_source = params.get("data_source").cloned();

    let tables: Vec<Value> = match data_source.as_deref() {
        Some("sap") => db
            .aql_str(
                r#"FOR d IN da_table_info RETURN MERGE(d, {data_source: "sap"})"#,
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?,
        Some("ragic") => db
            .aql_str(
                r#"FOR d IN da_table_info_ragic RETURN MERGE(d, {data_source: "ragic"})"#,
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?,
        _ => db
            .aql_str(
                r#"
                LET sap = (FOR d IN da_table_info RETURN MERGE(d, {data_source: "sap"}))
                LET rag = (FOR d IN da_table_info_ragic RETURN MERGE(d, {data_source: "ragic"}))
                FOR d IN UNION(sap, rag) RETURN d
                "#,
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?,
    };

    Ok(Json(ApiResponse::success(tables)))
}

async fn get_table(Path(table_id): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let mut tables: Vec<Value> = db
        .aql_bind_vars(
            r#"
            LET sap = (FOR d IN da_table_info FILTER d.table_id == @table_id RETURN MERGE(d, {data_source: "sap"}))
            LET rag = (FOR d IN da_table_info_ragic FILTER d.table_id == @table_id RETURN MERGE(d, {data_source: "ragic"}))
            FOR d IN UNION(sap, rag) LIMIT 1 RETURN d
            "#,
            [("table_id", serde_json::json!(table_id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let table = tables.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(table)))
}

async fn create_table(Json(payload): Json<Value>) -> Result<impl IntoResponse, StatusCode> {
    let table_id = payload
        .get("table_id")
        .and_then(|v| v.as_str())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let data_source = payload
        .get("data_source")
        .and_then(|v| v.as_str())
        .unwrap_or("sap")
        .to_string();

    if data_source != "sap" && data_source != "ragic" {
        return Err(StatusCode::BAD_REQUEST);
    }

    let collection_name = resolve_collection_name("table_info", &data_source);

    let db = get_db();
    let existing: Vec<Value> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {} FILTER d.table_id == @table_id LIMIT 1 RETURN d._key",
                collection_name
            ),
            [("table_id", serde_json::json!(table_id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if !existing.is_empty() {
        return Err(StatusCode::CONFLICT);
    }

    let col = db
        .collection(&collection_name)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(payload.clone(), Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut created: Vec<Value> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {} FILTER d.table_id == @table_id LIMIT 1 RETURN MERGE(d, {{data_source: @data_source}})",
                collection_name
            ),
            [
                ("table_id", serde_json::json!(table_id)),
                ("data_source", serde_json::json!(data_source)),
            ]
            .into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let table = created.pop().ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(table)))
}

async fn update_table(
    Path(table_id): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let mut found_in: Option<String> = None;
    let mut doc_key: Option<String> = None;

    for source in ["sap", "ragic"] {
        let collection_name = resolve_collection_name("table_info", source);
        let keys: Vec<String> = db
            .aql_bind_vars(
                &format!(
                    "FOR d IN {} FILTER d.table_id == @table_id LIMIT 1 RETURN d._key",
                    collection_name
                ),
                [("table_id", serde_json::json!(table_id.clone()))].into(),
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

        if let Some(key) = keys.into_iter().next() {
            found_in = Some(collection_name);
            doc_key = Some(key);
            break;
        }
    }

    let collection_name = found_in.ok_or(StatusCode::NOT_FOUND)?;
    let doc_key = doc_key.ok_or(StatusCode::NOT_FOUND)?;

    let col = db
        .collection(&collection_name)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(&doc_key, payload, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let data_source = if collection_name == "da_table_info" {
        "sap"
    } else {
        collection_name.strip_prefix("da_table_info_").unwrap()
    };
    let mut updated: Vec<Value> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {} FILTER d._key == @key LIMIT 1 RETURN MERGE(d, {{data_source: @data_source}})",
                collection_name
            ),
            [
                ("key", serde_json::json!(doc_key)),
                ("data_source", serde_json::json!(data_source)),
            ]
            .into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let table = updated.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(table)))
}

async fn delete_table(Path(table_id): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let mut found_in: Option<String> = None;
    let mut doc_key: Option<String> = None;

    for source in ["sap", "ragic"] {
        let collection_name = resolve_collection_name("table_info", source);
        let keys: Vec<String> = db
            .aql_bind_vars(
                &format!(
                    "FOR d IN {} FILTER d.table_id == @table_id LIMIT 1 RETURN d._key",
                    collection_name
                ),
                [("table_id", serde_json::json!(table_id.clone()))].into(),
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

        if let Some(key) = keys.into_iter().next() {
            found_in = Some(collection_name);
            doc_key = Some(key);
            break;
        }
    }

    let collection_name = found_in.ok_or(StatusCode::NOT_FOUND)?;
    let doc_key = doc_key.ok_or(StatusCode::NOT_FOUND)?;

    let col = db
        .collection(&collection_name)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<Value>(&doc_key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success("Table deleted".to_string())))
}

async fn list_fields(Path(table_id): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let fields: Vec<Value> = db
        .aql_bind_vars(
            r#"
            LET sap = (FOR d IN da_field_info FILTER d.table_id == @table_id RETURN MERGE(d, {data_source: "sap"}))
            LET rag = (FOR d IN da_field_info_ragic FILTER d.table_id == @table_id RETURN MERGE(d, {data_source: "ragic"}))
            FOR d IN UNION(sap, rag) RETURN d
            "#,
            [("table_id", serde_json::json!(table_id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(fields)))
}

async fn create_field(
    Path(table_id): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let field_id = payload
        .get("field_id")
        .and_then(|v| v.as_str())
        .map(str::to_string)
        .ok_or(StatusCode::BAD_REQUEST)?;

    let data_source = payload
        .get("data_source")
        .and_then(|v| v.as_str())
        .unwrap_or("sap")
        .to_string();

    if data_source != "sap" && data_source != "ragic" {
        return Err(StatusCode::BAD_REQUEST);
    }

    let mut doc = payload;
    let obj = doc.as_object_mut().ok_or(StatusCode::BAD_REQUEST)?;
    obj.insert("table_id".to_string(), serde_json::json!(table_id.clone()));

    let collection_name = format!("da_field_info_{}", data_source);

    let db = get_db();
    let existing: Vec<String> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {} FILTER d.table_id == @table_id && d.field_id == @field_id LIMIT 1 RETURN d._key",
                collection_name
            ),
            [
                ("table_id", serde_json::json!(table_id.clone())),
                ("field_id", serde_json::json!(field_id.clone())),
            ]
            .into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    if !existing.is_empty() {
        return Err(StatusCode::CONFLICT);
    }

    let col = db
        .collection(&collection_name)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(doc, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut created: Vec<Value> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {} FILTER d.table_id == @table_id && d.field_id == @field_id LIMIT 1 RETURN MERGE(d, {{data_source: @data_source}})",
                collection_name
            ),
            [
                ("table_id", serde_json::json!(table_id)),
                ("field_id", serde_json::json!(field_id)),
                ("data_source", serde_json::json!(data_source)),
            ]
            .into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let field = created.pop().ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(field)))
}

async fn update_field(
    Path((table_id, field_id)): Path<(String, String)>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let mut found_in: Option<String> = None;
    let mut doc_key: Option<String> = None;

    for source in ["sap", "ragic"] {
        let collection_name = format!("da_field_info_{}", source);
        let keys: Vec<String> = db
            .aql_bind_vars(
                &format!(
                    "FOR d IN {} FILTER d.table_id == @table_id && d.field_id == @field_id LIMIT 1 RETURN d._key",
                    collection_name
                ),
                [
                    ("table_id", serde_json::json!(table_id.clone())),
                    ("field_id", serde_json::json!(field_id.clone())),
                ]
                .into(),
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

        if let Some(key) = keys.into_iter().next() {
            found_in = Some(collection_name);
            doc_key = Some(key);
            break;
        }
    }

    let collection_name = found_in.ok_or(StatusCode::NOT_FOUND)?;
    let doc_key = doc_key.ok_or(StatusCode::NOT_FOUND)?;

    let col = db
        .collection(&collection_name)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(&doc_key, payload, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let data_source = collection_name.strip_prefix("da_field_info_").unwrap();
    let mut updated: Vec<Value> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {} FILTER d._key == @key LIMIT 1 RETURN MERGE(d, {{data_source: @data_source}})",
                collection_name
            ),
            [
                ("key", serde_json::json!(doc_key)),
                ("data_source", serde_json::json!(data_source)),
            ]
            .into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let field = updated.pop().ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(ApiResponse::success(field)))
}

async fn delete_field(
    Path((table_id, field_id)): Path<(String, String)>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let mut found_in: Option<String> = None;
    let mut doc_key: Option<String> = None;

    for source in ["sap", "ragic"] {
        let collection_name = format!("da_field_info_{}", source);
        let keys: Vec<String> = db
            .aql_bind_vars(
                &format!(
                    "FOR d IN {} FILTER d.table_id == @table_id && d.field_id == @field_id LIMIT 1 RETURN d._key",
                    collection_name
                ),
                [
                    ("table_id", serde_json::json!(table_id.clone())),
                    ("field_id", serde_json::json!(field_id.clone())),
                ]
                .into(),
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

        if let Some(key) = keys.into_iter().next() {
            found_in = Some(collection_name);
            doc_key = Some(key);
            break;
        }
    }

    let collection_name = found_in.ok_or(StatusCode::NOT_FOUND)?;
    let doc_key = doc_key.ok_or(StatusCode::NOT_FOUND)?;

    let col = db
        .collection(&collection_name)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<Value>(&doc_key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success("Field deleted".to_string())))
}

async fn list_relations(
    Query(params): Query<HashMap<String, String>>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let data_source = params.get("data_source").cloned();

    let relations: Vec<Value> = match data_source.as_deref() {
        Some("sap") => db
            .aql_str(
                r#"FOR d IN da_table_relation RETURN MERGE(d, {data_source: "sap"})"#,
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?,
        Some("ragic") => db
            .aql_str(
                r#"FOR d IN da_table_relation_ragic RETURN MERGE(d, {data_source: "ragic"})"#,
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?,
        _ => db
            .aql_str(
                r#"
                LET sap = (FOR d IN da_table_relation RETURN MERGE(d, {data_source: "sap"}))
                LET rag = (FOR d IN da_table_relation_ragic RETURN MERGE(d, {data_source: "ragic"}))
                FOR d IN UNION(sap, rag) RETURN d
                "#,
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?,
    };

    Ok(Json(ApiResponse::success(relations)))
}

async fn create_relation(Json(payload): Json<Value>) -> Result<impl IntoResponse, StatusCode> {
    let relation_id = payload
        .get("relation_id")
        .and_then(|v| v.as_str())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let data_source = payload
        .get("data_source")
        .and_then(|v| v.as_str())
        .unwrap_or("sap")
        .to_string();

    if data_source != "sap" && data_source != "ragic" {
        return Err(StatusCode::BAD_REQUEST);
    }

    let collection_name = resolve_collection_name("relation", &data_source);

    let db = get_db();
    let existing: Vec<Value> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {} FILTER d.relation_id == @relation_id LIMIT 1 RETURN d._key",
                collection_name
            ),
            [("relation_id", serde_json::json!(relation_id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    if !existing.is_empty() {
        return Err(StatusCode::CONFLICT);
    }

    let col = db
        .collection(&collection_name)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(payload.clone(), Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut created: Vec<Value> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {} FILTER d.relation_id == @relation_id LIMIT 1 RETURN MERGE(d, {{data_source: @data_source}})",
                collection_name
            ),
            [
                ("relation_id", serde_json::json!(relation_id)),
                ("data_source", serde_json::json!(data_source)),
            ]
            .into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let relation = created.pop().ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(relation)))
}

async fn update_relation(
    Path(relation_id): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let mut found_in: Option<String> = None;
    let mut doc_key: Option<String> = None;

    for source in ["sap", "ragic"] {
        let collection_name = resolve_collection_name("relation", source);
        let keys: Vec<String> = db
            .aql_bind_vars(
                &format!(
                    "FOR d IN {} FILTER d.relation_id == @relation_id LIMIT 1 RETURN d._key",
                    collection_name
                ),
                [("relation_id", serde_json::json!(relation_id.clone()))].into(),
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

        if let Some(key) = keys.into_iter().next() {
            found_in = Some(collection_name);
            doc_key = Some(key);
            break;
        }
    }

    let collection_name = found_in.ok_or(StatusCode::NOT_FOUND)?;
    let doc_key = doc_key.ok_or(StatusCode::NOT_FOUND)?;

    let col = db
        .collection(&collection_name)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(&doc_key, payload, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let data_source = if collection_name == "da_table_relation" {
        "sap"
    } else {
        collection_name.strip_prefix("da_table_relation_").unwrap()
    };
    let mut updated: Vec<Value> = db
        .aql_bind_vars(
            &format!(
                "FOR d IN {} FILTER d._key == @key LIMIT 1 RETURN MERGE(d, {{data_source: @data_source}})",
                collection_name
            ),
            [
                ("key", serde_json::json!(doc_key)),
                ("data_source", serde_json::json!(data_source)),
            ]
            .into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let relation = updated.pop().ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(ApiResponse::success(relation)))
}

async fn delete_relation(Path(relation_id): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let mut found_in: Option<String> = None;
    let mut doc_key: Option<String> = None;

    for source in ["sap", "ragic"] {
        let collection_name = resolve_collection_name("relation", source);
        let keys: Vec<String> = db
            .aql_bind_vars(
                &format!(
                    "FOR d IN {} FILTER d.relation_id == @relation_id LIMIT 1 RETURN d._key",
                    collection_name
                ),
                [("relation_id", serde_json::json!(relation_id.clone()))].into(),
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

        if let Some(key) = keys.into_iter().next() {
            found_in = Some(collection_name);
            doc_key = Some(key);
            break;
        }
    }

    let collection_name = found_in.ok_or(StatusCode::NOT_FOUND)?;
    let doc_key = doc_key.ok_or(StatusCode::NOT_FOUND)?;

    let col = db
        .collection(&collection_name)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<Value>(&doc_key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success("Relation deleted".to_string())))
}
