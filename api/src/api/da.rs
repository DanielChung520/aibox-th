//! Data Agent Schema API Routes
//!
//! # Description
//! DA 的 Schema CRUD endpoints (tables, fields, relations)
//! 支援雙資料源 (SAP + Ragic) + Ragic API Proxy
//!
//! # Last Update: 2026-04-11 17:45:24
//! # Author: Daniel Chung
//! # Version: 2.1.0

use crate::config::CONFIG;
use crate::db::get_db;
use crate::models::ApiResponse;
use crate::table_cache;
use axum::{
    extract::{Path, Query},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post, put},
    Json, Router,
};
use serde_json::{Value, json};
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
        .route(
            "/api/v1/da/schema/modules",
            get(list_modules),
        )
        .route(
            "/api/v1/da/ragic/proxy/{table_id}/data",
            get(ragic_proxy_data),
        )
        .route(
            "/api/v1/da/ragic/cache/{table_id}/refresh",
            post(ragic_cache_refresh),
        )
        .route(
            "/api/v1/da/ragic/cache/{table_id}/meta",
            get(ragic_cache_meta),
        )
        .route(
            "/api/v1/da/ragic/graph/related-tables",
            get(ragic_graph_related_tables),
        )
        .route(
            "/api/v1/da/ragic/graph/path",
            get(ragic_graph_path),
        )
        .route(
            "/api/v1/da/ragic/graph/all-relations",
            get(ragic_graph_all_relations),
        )
}

async fn list_modules() -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let modules: Vec<Value> = db
        .aql_str(
            r#"
            LET sap_modules = (FOR d IN da_table_info FILTER d.module != null RETURN {key: d.module, label: d.module, source: "sap"})
            LET rag_modules = (FOR d IN da_table_info_ragic FILTER d.module != null RETURN {key: d.module, label: d.module, source: "ragic"})
            FOR m IN UNION_DISTINCT(sap_modules, rag_modules) SORT m.label ASC RETURN m
            "#,
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(modules)))
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

async fn ragic_proxy_data(
    Path(table_id): Path<String>,
    Query(params): Query<HashMap<String, String>>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let cache = table_cache::get_cache();

    let offset: i64 = params
        .get("offset")
        .and_then(|v| v.parse().ok())
        .unwrap_or(0);
    let limit: i64 = params
        .get("limit")
        .and_then(|v| v.parse().ok())
        .unwrap_or(20);

    let fields: Vec<Value> = db
        .aql_bind_vars(
            "FOR d IN da_field_info_ragic FILTER d.table_id == @table_id RETURN d",
            [("table_id", serde_json::json!(&table_id))].into(),
        )
        .await
        .map_err(|e| {
            eprintln!("ragic_proxy_data: fields query error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let table_name = get_table_name(db, &table_id).await;

    if cache.has_table(&table_id).await {
        match cache.query(&table_id, offset, limit).await {
            Ok((rows, total)) => {
                let result = serde_json::json!({
                    "code": 0,
                    "table_id": table_id,
                    "table_name": table_name,
                    "fields": fields,
                    "rows": rows,
                    "total": total,
                    "offset": offset,
                    "limit": limit,
                    "source": "cache",
                });
                return Ok(Json(result));
            }
            Err(e) => {
                eprintln!("ragic_proxy_data: cache query failed, falling back to Ragic: {e}");
            }
        }
    }

    let (server_prefix, ragic_database, api_key) = get_ragic_config(db).await?;

    let mut table_infos: Vec<Value> = db
        .aql_bind_vars(
            "FOR d IN da_table_info_ragic FILTER d.table_id == @table_id LIMIT 1 RETURN d",
            [("table_id", serde_json::json!(&table_id))].into(),
        )
        .await
        .map_err(|e| {
            eprintln!("ragic_proxy_data: DB query error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let table_info = table_infos.pop().ok_or_else(|| {
        eprintln!("ragic_proxy_data: table_id={} not found", table_id);
        StatusCode::NOT_FOUND
    })?;

    let tab = table_info
        .get("tab")
        .and_then(|v| v.as_str())
        .ok_or_else(|| {
            eprintln!("ragic_proxy_data: table_id={} has no tab", table_id);
            StatusCode::BAD_REQUEST
        })?;
    let sheet_number = table_info
        .get("sheet_key")
        .and_then(|v| v.as_str())
        .ok_or_else(|| {
            eprintln!("ragic_proxy_data: table_id={} has no sheet_key", table_id);
            StatusCode::BAD_REQUEST
        })?;

    let ragic_url = format!(
        "https://{}.ragic.com/{}/{}/{}?api&naming=EID&limit={},{}",
        server_prefix, ragic_database, tab, sheet_number, offset, limit
    );

    let rows = fetch_ragic(&ragic_url, &api_key, &table_id, offset, limit).await?;

    let row_count = rows.len() as i64;
    let total = if row_count < limit {
        offset + row_count
    } else {
        offset + row_count + 1
    };

    let result = serde_json::json!({
        "code": 0,
        "table_id": table_id,
        "table_name": table_name,
        "fields": fields,
        "rows": rows,
        "total": total,
        "offset": offset,
        "limit": limit,
        "source": "ragic",
    });

    Ok(Json(result))
}

async fn ragic_cache_refresh(
    Path(table_id): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let cache = table_cache::get_cache();

    let (server_prefix, ragic_database, api_key) = get_ragic_config(db).await?;

    let mut table_infos: Vec<Value> = db
        .aql_bind_vars(
            "FOR d IN da_table_info_ragic FILTER d.table_id == @table_id LIMIT 1 RETURN d",
            [("table_id", serde_json::json!(&table_id))].into(),
        )
        .await
        .map_err(|e| {
            eprintln!("ragic_cache_refresh: DB query error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let table_info = table_infos.pop().ok_or_else(|| {
        eprintln!("ragic_cache_refresh: table_id={} not found", table_id);
        StatusCode::NOT_FOUND
    })?;

    let tab = table_info.get("tab").and_then(|v| v.as_str()).ok_or(StatusCode::BAD_REQUEST)?;
    let sheet_number = table_info.get("sheet_key").and_then(|v| v.as_str()).ok_or(StatusCode::BAD_REQUEST)?;

    let mut all_rows: Vec<Value> = Vec::new();
    let batch_size: i64 = 1000;
    let mut offset: i64 = 0;

    loop {
        let ragic_url = format!(
            "https://{}.ragic.com/{}/{}/{}?api&naming=EID&limit={},{}",
            server_prefix, ragic_database, tab, sheet_number, offset, batch_size
        );

        let batch = fetch_ragic(&ragic_url, &api_key, &table_id, offset, batch_size).await?;
        let batch_len = batch.len() as i64;
        all_rows.extend(batch);

        if batch_len < batch_size {
            break;
        }
        offset += batch_size;
    }

    let meta = cache
        .store(&table_id, &all_rows)
        .await
        .map_err(|e| {
            eprintln!("ragic_cache_refresh: cache store failed: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let db_meta = serde_json::json!({
        "_key": table_id,
        "table_id": table_id,
        "row_count": meta.row_count,
        "cached_at": meta.cached_at,
    });
    let _ = upsert_cache_meta(db, &table_id, &db_meta).await;

    Ok(Json(ApiResponse::success(serde_json::json!({
        "table_id": table_id,
        "row_count": meta.row_count,
        "cached_at": meta.cached_at,
    }))))
}

async fn ragic_cache_meta(
    Path(table_id): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let mut metas: Vec<Value> = db
        .aql_bind_vars(
            "FOR d IN ragic_cache_meta FILTER d.table_id == @table_id LIMIT 1 RETURN d",
            [("table_id", serde_json::json!(&table_id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    match metas.pop() {
        Some(meta) => Ok(Json(ApiResponse::success(meta))),
        None => Ok(Json(ApiResponse::success(serde_json::json!(null)))),
    }
}

async fn get_ragic_config(
    db: &arangors::Database<arangors::client::reqwest::ReqwestClient>,
) -> Result<(String, String, String), StatusCode> {
    let ragic_params: Vec<Value> = db
        .aql_str(
            "FOR d IN system_params FILTER d.category == 'ragic' RETURN { key: d.param_key, value: d.param_value }",
        )
        .await
        .map_err(|e| {
            eprintln!("get_ragic_config: query error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let mut server_prefix = String::new();
    let mut ragic_database = String::new();
    let mut api_key = String::new();
    for p in &ragic_params {
        let key = p.get("key").and_then(|v| v.as_str()).unwrap_or("");
        let val = p.get("value").and_then(|v| v.as_str()).unwrap_or("");
        match key {
            "ragic.server_prefix" => server_prefix = val.to_string(),
            "ragic.database" => ragic_database = val.to_string(),
            "ragic.api_key" => api_key = val.to_string(),
            _ => {}
        }
    }

    if api_key.is_empty() || server_prefix.is_empty() || ragic_database.is_empty() {
        eprintln!("get_ragic_config: incomplete");
        return Err(StatusCode::INTERNAL_SERVER_ERROR);
    }

    Ok((server_prefix, ragic_database, api_key))
}

async fn get_table_name(
    db: &arangors::Database<arangors::client::reqwest::ReqwestClient>,
    table_id: &str,
) -> String {
    let names: Vec<String> = db
        .aql_bind_vars(
            "FOR d IN da_table_info_ragic FILTER d.table_id == @table_id LIMIT 1 RETURN d.table_name",
            [("table_id", serde_json::json!(table_id))].into(),
        )
        .await
        .unwrap_or_default();
    names.into_iter().next().unwrap_or_default()
}

async fn fetch_ragic(
    url: &str,
    api_key: &str,
    table_id: &str,
    offset: i64,
    limit: i64,
) -> Result<Vec<Value>, StatusCode> {
    let client = reqwest::Client::new();
    let ragic_resp = client
        .get(url)
        .header("Authorization", format!("Basic {}", api_key))
        .send()
        .await
        .map_err(|e| {
            eprintln!("fetch_ragic: HTTP error: {}", e);
            StatusCode::BAD_GATEWAY
        })?;

    if !ragic_resp.status().is_success() {
        let status = ragic_resp.status();
        let body = ragic_resp.text().await.unwrap_or_default();
        eprintln!("fetch_ragic: Ragic returned {}: {}", status, body);
        return Err(StatusCode::BAD_GATEWAY);
    }

    let ragic_data: Value = ragic_resp.json().await.map_err(|e| {
        eprintln!("fetch_ragic: JSON parse error: {}", e);
        StatusCode::BAD_GATEWAY
    })?;

    if let Some(status) = ragic_data.get("status").and_then(|v| v.as_str()) {
        if status == "ERROR" {
            let msg = ragic_data.get("msg").and_then(|v| v.as_str()).unwrap_or("Unknown");
            eprintln!("fetch_ragic: Ragic API error for {}: {}", table_id, msg);
            return Err(StatusCode::BAD_GATEWAY);
        }
    }

    let rows: Vec<Value> = if let Some(obj) = ragic_data.as_object() {
        obj.values().cloned().collect()
    } else {
        vec![]
    };

    Ok(rows)
}

async fn upsert_cache_meta(
    db: &arangors::Database<arangors::client::reqwest::ReqwestClient>,
    table_id: &str,
    meta: &Value,
) -> Result<(), String> {
    let existing: Vec<Value> = db
        .aql_bind_vars(
            "FOR d IN ragic_cache_meta FILTER d.table_id == @table_id LIMIT 1 RETURN d._key",
            [("table_id", serde_json::json!(table_id))].into(),
        )
        .await
        .map_err(|e| format!("upsert meta query: {e}"))?;

    let col = db
        .collection("ragic_cache_meta")
        .await
        .map_err(|e| format!("ragic_cache_meta collection: {e}"))?;

    if let Some(key_val) = existing.into_iter().next() {
        if let Some(key) = key_val.as_str() {
            col.update_document(key, meta.clone(), Default::default())
                .await
                .map_err(|e| format!("update meta: {e}"))?;
        }
    } else {
        col.create_document(meta.clone(), Default::default())
            .await
            .map_err(|e| format!("create meta: {e}"))?;
    }

    Ok(())
}

pub async fn ragic_graph_related_tables(
    Query(params): Query<HashMap<String, String>>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let table_name = params.get("table_name").ok_or_else(|| (StatusCode::BAD_REQUEST, Json(json!({"code": 400, "message": "table_name is required"}))))?;
    let account = params.get("account").ok_or_else(|| (StatusCode::BAD_REQUEST, Json(json!({"code": 400, "message": "account is required"}))))?;
    let depth = params.get("depth").map(|d| d.as_str()).unwrap_or("1");

    let url = format!(
        "{}/da/ragic/graph/related-tables?table_name={}&account={}&depth={}",
        CONFIG.ai_services.unified_agents_url,
        urlencoding::encode(table_name),
        urlencoding::encode(account),
        urlencoding::encode(depth)
    );

    let client = reqwest::Client::new();
    match client
        .get(&url)
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
    {
        Ok(resp) => {
            let body: serde_json::Value = resp.json().await.unwrap_or_default();
            Ok(Json(json!({ "code": 200, "data": body })))
        }
        Err(e) => Err((
            StatusCode::BAD_GATEWAY,
            Json(json!({ "code": 502, "message": format!("failed to get related tables: {}", e) })),
        )),
    }
}

pub async fn ragic_graph_path(
    Query(params): Query<HashMap<String, String>>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let from_table = params.get("from_table").ok_or_else(|| (StatusCode::BAD_REQUEST, Json(json!({"code": 400, "message": "from_table is required"}))))?;
    let to_table = params.get("to_table").ok_or_else(|| (StatusCode::BAD_REQUEST, Json(json!({"code": 400, "message": "to_table is required"}))))?;
    let account = params.get("account").ok_or_else(|| (StatusCode::BAD_REQUEST, Json(json!({"code": 400, "message": "account is required"}))))?;

    let url = format!(
        "{}/da/ragic/graph/path?from_table={}&to_table={}&account={}",
        CONFIG.ai_services.unified_agents_url,
        urlencoding::encode(from_table),
        urlencoding::encode(to_table),
        urlencoding::encode(account)
    );

    let client = reqwest::Client::new();
    match client
        .get(&url)
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
    {
        Ok(resp) => {
            let body: serde_json::Value = resp.json().await.unwrap_or_default();
            Ok(Json(json!({ "code": 200, "data": body })))
        }
        Err(e) => Err((
            StatusCode::BAD_GATEWAY,
            Json(json!({ "code": 502, "message": format!("failed to get graph path: {}", e) })),
        )),
    }
}

pub async fn ragic_graph_all_relations(
    Query(params): Query<HashMap<String, String>>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let account = params.get("account").ok_or_else(|| (StatusCode::BAD_REQUEST, Json(json!({"code": 400, "message": "account is required"}))))?;

    let url = format!(
        "{}/da/ragic/graph/all-relations?account={}",
        CONFIG.ai_services.unified_agents_url,
        urlencoding::encode(account)
    );

    let client = reqwest::Client::new();
    match client
        .get(&url)
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
    {
        Ok(resp) => {
            let body: serde_json::Value = resp.json().await.unwrap_or_default();
            Ok(Json(json!({ "code": 200, "data": body })))
        }
        Err(e) => Err((
            StatusCode::BAD_GATEWAY,
            Json(json!({ "code": 502, "message": format!("failed to get all relations: {}", e) })),
        )),
    }
}
