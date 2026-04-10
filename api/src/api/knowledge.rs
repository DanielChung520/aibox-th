//! Knowledge Base API
//!
//! # Last Update: 2026-04-07 11:18:19
//! # Author: Daniel Chung
//! # Version: 5.0.0

use arangors::client::reqwest::ReqwestClient;
use arangors::Database;
use crate::auth::verify_jwt;
use crate::db::{
    get_db,
    knowledge::{KnowledgeFile, KnowledgeRoot},
};
use axum::{
    extract::{DefaultBodyLimit, Path, Query},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    routing::post,
    Json, Router,
};
use futures::StreamExt;
use serde_json::json;
use std::collections::HashMap;
use uuid::Uuid;

pub async fn list_roots(
    Query(params): Query<HashMap<String, String>>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let (query, bind_vars) = if let Some(search) = params.get("search").filter(|s| !s.is_empty()) {
        let lower = search.to_lowercase();
        (
            "FOR r IN knowledge_roots FILTER CONTAINS(LOWER(r.name), @search) || CONTAINS(LOWER(r.description), @search) SORT r.created_at DESC RETURN r".to_string(),
            [("search", json!(lower))].into(),
        )
    } else {
        (
            "FOR r IN knowledge_roots SORT r.created_at DESC RETURN r".to_string(),
            HashMap::new(),
        )
    };

    let roots: Vec<KnowledgeRoot> = db
        .aql_bind_vars(&query, bind_vars)
        .await
        .map_err(|_| err_500())?;

    Ok(Json(json!({ "code": 200, "data": roots })))
}

pub async fn get_root(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();
    let mut roots: Vec<KnowledgeRoot> = db
        .aql_bind_vars(
            "FOR r IN knowledge_roots FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", json!(key))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    let root = roots.pop().ok_or_else(|| err_404("knowledge root"))?;
    Ok(Json(json!({ "code": 200, "data": root })))
}

pub async fn create_root(
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();
    let col = db.collection("knowledge_roots").await.map_err(|_| err_500())?;

    let now = chrono::Utc::now().to_rfc3339();
    let key = format!("kb_{}", chrono::Utc::now().timestamp_millis());

    let root = KnowledgeRoot {
        _key: Some(key.clone()),
        name: payload.get("name").and_then(|v| v.as_str()).unwrap_or("未命名知識庫").to_string(),
        description: payload.get("description").and_then(|v| v.as_str()).map(String::from),
        ontology_domain: payload.get("ontology_domain").and_then(|v| v.as_str()).unwrap_or("Unknown").to_string(),
        ontology_majors: payload
            .get("ontology_majors")
            .and_then(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
            .unwrap_or_default(),
        source_count: 0,
        vector_status: "pending".into(),
        graph_status: "pending".into(),
        is_favorite: false,
        created_at: now.clone(),
        updated_at: now,
    };

    col.create_document(root, Default::default())
        .await
        .map_err(|_| err_500())?;

    Ok((
        StatusCode::CREATED,
        Json(json!({ "code": 201, "data": { "_key": key } })),
    ))
}

pub async fn update_root(
    Path(key): Path<String>,
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let existing: Vec<KnowledgeRoot> = db
        .aql_bind_vars(
            "FOR r IN knowledge_roots FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", json!(key.clone()))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    if existing.is_empty() {
        return Err(err_404("knowledge root"));
    }

    let mut data = payload;
    if let Some(obj) = data.as_object_mut() {
        obj.remove("_key");
        obj.remove("_id");
        obj.remove("created_at");
        obj.insert("updated_at".to_string(), json!(chrono::Utc::now().to_rfc3339()));
    }

    let _: Vec<KnowledgeRoot> = db
        .aql_bind_vars(
            "FOR r IN knowledge_roots FILTER r._key == @key UPDATE r WITH @data IN knowledge_roots RETURN NEW",
            [("key", json!(key)), ("data", data)].into(),
        )
        .await
        .map_err(|_| err_500())?;

    Ok(Json(json!({ "code": 200, "message": "updated" })))
}

pub async fn delete_root(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let existing: Vec<KnowledgeRoot> = db
        .aql_bind_vars(
            "FOR r IN knowledge_roots FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", json!(key.clone()))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    if existing.is_empty() {
        return Err(err_404("knowledge root"));
    }

    let _: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR f IN knowledge_files FILTER f.knowledge_root_id == @key REMOVE f IN knowledge_files",
            [("key", json!(key.clone()))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    let _: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "REMOVE @key IN knowledge_roots",
            [("key", json!(key))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    Ok(Json(json!({ "code": 200, "message": "deleted" })))
}

pub async fn copy_root(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let mut roots: Vec<KnowledgeRoot> = db
        .aql_bind_vars(
            "FOR r IN knowledge_roots FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", json!(key.clone()))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    let source = roots.pop().ok_or_else(|| err_404("knowledge root"))?;
    let now = chrono::Utc::now().to_rfc3339();
    let new_key = format!("kb_copy_{}", chrono::Utc::now().timestamp_millis());

    let copy = KnowledgeRoot {
        _key: Some(new_key.clone()),
        name: format!("{} - 副本", source.name),
        description: source.description,
        ontology_domain: source.ontology_domain,
        ontology_majors: source.ontology_majors,
        source_count: 0,
        vector_status: "pending".into(),
        graph_status: "pending".into(),
        is_favorite: false,
        created_at: now.clone(),
        updated_at: now,
    };

    let col = db.collection("knowledge_roots").await.map_err(|_| err_500())?;
    col.create_document(copy, Default::default())
        .await
        .map_err(|_| err_500())?;

    Ok((
        StatusCode::CREATED,
        Json(json!({ "code": 201, "data": { "_key": new_key } })),
    ))
}

pub async fn toggle_favorite(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let mut roots: Vec<KnowledgeRoot> = db
        .aql_bind_vars(
            "FOR r IN knowledge_roots FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", json!(key.clone()))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    let root = roots.pop().ok_or_else(|| err_404("knowledge root"))?;
    let new_fav = !root.is_favorite;

    let col = db.collection("knowledge_roots").await.map_err(|_| err_500())?;
    col.update_document(
        &key,
        json!({
            "is_favorite": new_fav,
            "updated_at": chrono::Utc::now().to_rfc3339()
        }),
        Default::default(),
    )
    .await
    .map_err(|_| err_500())?;

    Ok(Json(json!({ "code": 200, "data": { "is_favorite": new_fav } })))
}

pub async fn list_files(
    Path(root_id): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let files: Vec<KnowledgeFile> = db
        .aql_bind_vars(
            "FOR f IN knowledge_files FILTER f.knowledge_root_id == @root_id SORT f.upload_time DESC RETURN f",
            [("root_id", json!(root_id))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    Ok(Json(json!({ "code": 200, "data": files })))
}

pub async fn get_file(
    Path(file_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let mut files: Vec<KnowledgeFile> = db
        .aql_bind_vars(
            "FOR f IN knowledge_files FILTER f._key == @key LIMIT 1 RETURN f",
            [("key", json!(file_key))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    let file = files.pop().ok_or_else(|| err_404("knowledge file"))?;
    Ok(Json(json!({ "code": 200, "data": file })))
}

pub async fn delete_file(
    Path(file_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let files: Vec<KnowledgeFile> = db
        .aql_bind_vars(
            "FOR f IN knowledge_files FILTER f._key == @key LIMIT 1 RETURN f",
            [("key", json!(file_key.clone()))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    if files.is_empty() {
        return Err(err_404("knowledge file"));
    }

    let root_id = files[0].knowledge_root_id.clone();

    // Pipeline cleanup MUST complete before ArangoDB removal,
    // otherwise Python cannot resolve root_id → Qdrant collection.
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());
    let client = reqwest::Client::new();
    let pipeline_ok = client
        .post(format!("{}/pipeline/delete?file_id={}", agent_url, file_key))
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
        .map(|r| r.status().is_success())
        .unwrap_or(false);

    if !pipeline_ok {
        eprintln!("WARNING: pipeline/delete failed for file_id={}, proceeding with DB removal", file_key);
    }

    let _: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "REMOVE @key IN knowledge_files OPTIONS { ignoreErrors: true }",
            [("key", json!(file_key))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    let _: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR r IN knowledge_roots FILTER r._key == @key UPDATE r WITH { source_count: MAX([0, r.source_count - 1]), updated_at: @now } IN knowledge_roots RETURN 1",
            [("key", json!(root_id)), ("now", json!(chrono::Utc::now().to_rfc3339()))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    Ok(Json(json!({ "code": 200, "message": "deleted" })))
}

pub async fn upload_file(
    Path(root_id): Path<String>,
    headers: HeaderMap,
    mut multipart: axum::extract::Multipart,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    // Verify root exists
    let roots: Vec<KnowledgeRoot> = db
        .aql_bind_vars(
            "FOR r IN knowledge_roots FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", json!(&root_id))].into(),
        )
        .await
        .map_err(|_| err_500())?;
    if roots.is_empty() {
        return Err(err_400("knowledge root not found"));
    }

    // Extract file from multipart
    let field = multipart.next_field().await.map_err(|_| err_400("no file provided"))?;
    let field = field.ok_or_else(|| err_400("no file provided"))?;

    let filename = field.file_name().unwrap_or("unknown").to_string();
    let content_type = field.content_type().unwrap_or("application/octet-stream").to_string();

    // Determine user tier and max upload size
    let tier = extract_user_tier(&headers, db).await;
    let max_size = get_upload_max_size(db, &tier).await;
    let tier_display = if tier == "vip" { "VIP" } else { "一般用户" };

    // Generate unique file key and local path
    let file_key = Uuid::new_v4().to_string();
    let ext = std::path::Path::new(&filename)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("bin");
    let local_dir = std::env::current_dir()
        .unwrap_or_else(|_| std::path::PathBuf::from("."))
        .join("data/uploads")
        .join(&root_id);
    let local_path = local_dir.join(format!("{}.{}", file_key, ext));

    // Create upload directory
    tokio::fs::create_dir_all(&local_dir).await.map_err(|e| {
        (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({ "code": 500, "message": e.to_string() })))
    })?;

    // Stream file using StreamExt next() (avoids chunk() internal buffer limits)
    let mut file = tokio::fs::File::create(&local_path).await.map_err(|e| {
        (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({ "code": 500, "message": e.to_string() })))
    })?;
    let mut total_bytes: usize = 0;
    let mut stream = field;

    loop {
        match stream.next().await {
            Some(Ok(chunk)) => {
                total_bytes += chunk.len();
                if total_bytes > max_size {
                    drop(file);
                    let _ = tokio::fs::remove_file(&local_path).await;
                    return Err((
                        StatusCode::PAYLOAD_TOO_LARGE,
                        Json(json!({
                            "success": false,
                            "error": "FILE_TOO_LARGE",
                            "message": format!(
                                "上傳檔案大小（{} bytes）超過會員「{}」限制（{} bytes）。請升級至更高會員等級。",
                                total_bytes, tier_display, max_size
                            ),
                            "tier": tier,
                            "max_size_bytes": max_size,
                        })),
                    ));
                }
                if let Err(e) = tokio::io::AsyncWriteExt::write_all(&mut file, &chunk).await {
                    let _ = tokio::fs::remove_file(&local_path).await;
                    return Err((
                        StatusCode::INTERNAL_SERVER_ERROR,
                        Json(json!({ "code": 500, "message": e.to_string() })),
                    ));
                }
            }
            Some(Err(e)) => {
                let _ = tokio::fs::remove_file(&local_path).await;
                return Err((StatusCode::BAD_REQUEST, Json(json!({ "code": 400, "message": format!("failed to read upload stream: {}", e) }))));
            }
            None => break,
        }
    }
    drop(file);

    let bytes_to_upload = match tokio::fs::read(&local_path).await {
        Ok(bytes) => bytes,
        Err(e) => {
            let _ = tokio::fs::remove_file(&local_path).await;
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "code": 500, "message": e.to_string() })),
            ));
        }
    };

    let s3_path = format!("bucket-aibox-assets/{}/{}.{}", root_id, file_key, ext);

    // Upload to SeaweedFS ai-box cluster (backup / long-term storage)
    let seaweed_user = std::env::var("SEAWEED_USER").unwrap_or_else(|_| "admin".to_string());
    let seaweed_pass = std::env::var("SEAWEED_PASS").unwrap_or_else(|_| "admin123".to_string());
    let seaweed_base = std::env::var("SEAWEED_AIBOX_URL").unwrap_or_else(|_| "http://localhost:8888".to_string());
    let seaweed_url = format!("{}/{}", seaweed_base, s3_path);
    let client = reqwest::Client::new();
    let _ = client
        .put(&seaweed_url)
        .basic_auth(&seaweed_user, Some(&seaweed_pass))
        .body(bytes_to_upload.clone())
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await;

    // Create ArangoDB record
    let now = chrono::Utc::now().to_rfc3339();
    let doc: serde_json::Value = json!({
        "_key": file_key,
        "filename": filename,
        "file_size": total_bytes as i64,
        "file_type": content_type,
        "upload_time": now,
        "vector_status": "pending",
        "graph_status": "pending",
        "knowledge_root_id": root_id,
        "local_path": local_path,
        "s3_path": s3_path,
    });

    let col = db.collection("knowledge_files").await.map_err(|_| err_500())?;
    col.create_document(doc.clone(), Default::default())
        .await
        .map_err(|_| err_500())?;

    // Update root source_count
    let _: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR r IN knowledge_roots FILTER r._key == @key UPDATE r WITH { source_count: r.source_count + 1, updated_at: @now } IN knowledge_roots",
            [("key", json!(&root_id)), ("now", json!(&now))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    // Trigger Celery task via knowledge_agent
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL").unwrap_or_else(|_| "http://localhost:8007".to_string());
    let trigger_url = format!("{}/pipeline/trigger", agent_url);
    let payload = serde_json::json!({
        "task": "process_file",
        "file_id": file_key,
        "local_path": local_path,
        "root_id": root_id,
    });
    let _ = client
        .post(&trigger_url)
        .json(&payload)
        .timeout(std::time::Duration::from_secs(5))
        .send()
        .await;

    let file_id = file_key;
    Ok(Json(json!({ "code": 0, "data": { "fileId": file_id } })))
}

/// Extract user tier from optional JWT token.
/// Falls back to "general" if no token or user not found.
async fn extract_user_tier(headers: &HeaderMap, db: &Database<ReqwestClient>) -> String {
    let token = headers
        .get(axum::http::header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "));

    let Some(token) = token else {
        return "general".to_string();
    };

    let Ok(token_data) = verify_jwt(token) else {
        return "general".to_string();
    };

    let username = &token_data.claims.username;
    let users: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR u IN users FILTER u.username == @username LIMIT 1 RETURN u",
            [("username", json!(username))].into(),
        )
        .await
        .unwrap_or_default();

    if let Some(user) = users.first() {
        user.get("tier")
            .and_then(|v: &serde_json::Value| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_else(|| "general".to_string())
    } else {
        "general".to_string()
    }
}

/// Look up max upload size for the given tier from system_params.
/// Falls back to DEFAULT_MAX_SIZE if not found.
async fn get_upload_max_size(
    db: &Database<ReqwestClient>,
    tier: &str,
) -> usize {
    let param_key = format!("upload_max_size_{}", tier);
    let params: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR p IN system_params FILTER p.param_key == @k LIMIT 1 RETURN p",
            [("k", json!(&param_key))].into(),
        )
        .await
        .unwrap_or_default();

    params
        .first()
        .and_then(|p: &serde_json::Value| p.get("param_value"))
        .and_then(|v: &serde_json::Value| v.as_str())
        .and_then(|s: &str| s.parse::<usize>().ok())
        .unwrap_or_else(|| {
            if tier == "vip" {
                52428800 // 50 MB for vip
            } else {
                5242880 // 5 MB for general
            }
        })
}

pub fn create_upload_router() -> Router {
    Router::new()
        .route("/api/v1/knowledge/roots/{root_id}/files/upload", post(upload_file))
        // Override Axum's internal 2MB multipart body limit to 100MB
        .layer(DefaultBodyLimit::max(100 * 1024 * 1024))
}

pub async fn list_jobs(
    Query(params): Query<std::collections::HashMap<String, String>>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    let filter = match params.get("status").map(|s| s.as_str()) {
        Some("failed") => {
            let jobs: Vec<KnowledgeFile> = db
                .aql_bind_vars(
                    "FOR f IN knowledge_files \
                     FILTER f.vector_status == 'failed' OR f.graph_status == 'failed' \
                     SORT f.upload_time DESC LIMIT 50 RETURN f",
                    [].into(),
                )
                .await
                .map_err(|_| err_500())?;
            return Ok(Json(json!({ "code": 200, "data": jobs })));
        }
        Some("completed") => {
            let jobs: Vec<KnowledgeFile> = db
                .aql_bind_vars(
                    "FOR f IN knowledge_files \
                     FILTER f.vector_status == 'completed' AND f.graph_status == 'completed' \
                     SORT f.upload_time DESC LIMIT 50 RETURN f",
                    [].into(),
                )
                .await
                .map_err(|_| err_500())?;
            return Ok(Json(json!({ "code": 200, "data": jobs })));
        }
        _ => "(f.vector_status IN ['pending', 'processing', 'queued'] \
              OR f.graph_status IN ['pending', 'processing', 'queued']) \
              AND f.vector_status != 'failed' AND f.graph_status != 'failed'",
    };

    let query = format!(
        "FOR f IN knowledge_files FILTER {} SORT f.upload_time DESC LIMIT 50 RETURN f",
        filter
    );

    let jobs: Vec<KnowledgeFile> = db
        .aql_str(&query)
        .await
        .map_err(|_| err_500())?;

    Ok(Json(json!({ "code": 200, "data": jobs })))
}

pub async fn clear_jobs(
    Query(params): Query<std::collections::HashMap<String, String>>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();
    let status = params.get("status").map(|s| s.as_str()).unwrap_or("failed");

    let filter = match status {
        "completed" => {
            "f.vector_status == 'completed' AND f.graph_status == 'completed'"
        }
        _ => {
            "f.vector_status == 'failed' OR f.graph_status == 'failed'"
        }
    };

    let query = format!(
        "FOR f IN knowledge_files FILTER {} SORT f.upload_time DESC LIMIT 200 REMOVE f IN knowledge_files RETURN f",
        filter
    );

    let deleted: Vec<KnowledgeFile> = db
        .aql_str(&query)
        .await
        .map_err(|_| err_500())?;

    let keys: Vec<&str> = deleted
        .iter()
        .filter_map(|f| f._key.as_deref())
        .collect();
    if !keys.is_empty() {
        let log_filter = keys
            .iter()
            .map(|k| format!("'{}'", k))
            .collect::<Vec<_>>()
            .join(",");
        let log_query = format!(
            "FOR log IN job_logs FILTER log.file_id IN [{}] REMOVE log IN job_logs RETURN log",
            log_filter
        );
        let _logs: Vec<serde_json::Value> = db
            .aql_str(&log_query)
            .await
            .unwrap_or_default();
    }

    Ok(Json(json!({ "code": 200, "message": format!("已清除 {} 筆記錄", deleted.len()) })))
}

/// List stuck jobs: processing in DB but no active Celery task backing them.
/// A job is stuck if vector_status or graph_status is "processing" for > STUCK_TIMEOUT_SECS
/// without a corresponding active Celery task.
#[allow(dead_code)]
const STUCK_TIMEOUT_SECS: i64 = 600; // 10 minutes

pub async fn list_jobs_stuck() -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();

    // Get all processing jobs
    let processing: Vec<serde_json::Value> = db
        .aql_str(
            "FOR f IN knowledge_files \
             FILTER f.vector_status == 'processing' OR f.graph_status == 'processing' \
             RETURN { _key: f._key, filename: f.filename, vector_status: f.vector_status, \
             graph_status: f.graph_status, vector_task_id: f.vector_task_id, \
             graph_task_id: f.graph_task_id, failed_reason: f.failed_reason }",
        )
        .await
        .map_err(|_| err_500())?;

    if processing.is_empty() {
        return Ok(Json(json!({ "code": 200, "data": [] })));
    }

    // Call knowledge agent to get active Celery tasks
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .unwrap_or_else(|_| reqwest::Client::new());

    let active_tasks_url = format!("{}/pipeline/active-tasks", agent_url);
    let agent_active: Vec<String> = match client.get(&active_tasks_url).send().await {
        Ok(resp) => resp.json().await.unwrap_or_default(),
        Err(_) => Vec::new(),
    };

    let stuck: Vec<serde_json::Value> = processing
        .into_iter()
        .filter(|job| {
            let vt_id = job
                .get("vector_task_id")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let gt_id = job
                .get("graph_task_id")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            // Stuck if neither task ID is in active tasks
            let vt_active = agent_active.iter().any(|t| t == vt_id);
            let gt_active = agent_active.iter().any(|t| t == gt_id);
            !vt_active && !gt_active
        })
        .collect();

    Ok(Json(json!({ "code": 200, "data": stuck })))
}

fn err_400(msg: &str) -> (StatusCode, Json<serde_json::Value>) {
    (
        StatusCode::BAD_REQUEST,
        Json(json!({ "code": 400, "message": msg })),
    )
}

/// Revoke Celery tasks via knowledge agent (which has Celery SDK access).
async fn revoke_celery_tasks(
    file_key: &str,
    vector_task_id: Option<&str>,
    graph_task_id: Option<&str>,
) -> (Vec<String>, bool) {
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .unwrap_or_else(|_| reqwest::Client::new());

    let mut revoked = Vec::new();
    let mut any_success = false;

    for task_id in vector_task_id.into_iter().chain(graph_task_id.into_iter()) {
        if task_id.is_empty() {
            continue;
        }
        // Call knowledge agent's abort endpoint for each task
        let url = format!("{}/pipeline/abort?file_id={}", agent_url, file_key);
        if let Ok(resp) = client.post(&url).send().await {
            if resp.status().is_success() {
                revoked.push(task_id.to_string());
                any_success = true;
            }
        }
    }
    (revoked, any_success)
}

pub async fn abort_job(
    Path(file_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let db = get_db();
    let col = db
        .collection("knowledge_files")
        .await
        .map_err(|_| err_500())?;

    // Read current doc to get task IDs
    let doc_url = format!(
        "{}/_db/{}/_api/document/knowledge_files/{}",
        std::env::var("DATABASE_URL").unwrap_or_else(|_| "http://localhost:8529".to_string()),
        std::env::var("DATABASE_NAME").unwrap_or_else(|_| "abc_desktop".to_string()),
        file_key
    );
    let arango_user = std::env::var("DATABASE_USER").unwrap_or_else(|_| "root".to_string());
    let arango_pass = std::env::var("DATABASE_PASSWORD").unwrap_or_else(|_| "abc_desktop_2026".to_string());

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(5))
        .build()
        .unwrap_or_else(|_| reqwest::Client::new());

    let (vector_task_id, graph_task_id): (Option<String>, Option<String>) = match client
        .get(&doc_url)
        .basic_auth(&arango_user, Some(&arango_pass))
        .send()
        .await
    {
        Ok(resp) => {
            if resp.status().is_success() {
                if let Ok(doc) = resp.json::<serde_json::Value>().await {
                    let vt = doc
                        .get("vector_task_id")
                        .and_then(|v| v.as_str())
                        .filter(|s| !s.is_empty())
                        .map(String::from);
                    let gt = doc
                        .get("graph_task_id")
                        .and_then(|v| v.as_str())
                        .filter(|s| !s.is_empty())
                        .map(String::from);
                    (vt, gt)
                } else {
                    (None, None)
                }
            } else {
                (None, None)
            }
        }
        Err(_) => (None, None),
    };

    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());
    let agent_abort_url = format!("{}/pipeline/abort?file_id={}", agent_url, file_key);
    let agent_result: serde_json::Value = match client.post(&agent_abort_url).send().await {
        Ok(resp) => resp.json().await.unwrap_or_default(),
        Err(_) => serde_json::Value::Null,
    };

    let (revoked, _) = revoke_celery_tasks(
        &file_key,
        vector_task_id.as_deref(),
        graph_task_id.as_deref(),
    )
    .await;

    // Reset DB status to pending so job can be retried
    let patch = serde_json::json!({
        "vector_status": "pending",
        "graph_status": "pending",
        "failed_reason": serde_json::Value::Null,
    });
    let _ = col
        .update_document(&file_key, patch, Default::default())
        .await;

    Ok(Json(json!({
        "code": 200,
        "data": {
            "file_id": file_key,
            "agent_abort": agent_result,
            "revoked_tasks": revoked,
        }
    })))
}

pub async fn job_logs(
    Path(file_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());
    let url = format!("{}/pipeline/logs?file_id={}", agent_url, file_key);

    let client = reqwest::Client::new();
    match client
        .get(&url)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await
    {
        Ok(resp) => {
            let body: serde_json::Value = resp.json().await.unwrap_or_default();
            Ok(Json(json!({ "code": 200, "data": body })))
        }
        Err(e) => Err((
            StatusCode::BAD_GATEWAY,
            Json(json!({ "code": 502, "message": format!("failed to fetch logs: {}", e) })),
        )),
    }
}

pub async fn get_vectors(
    Path(file_key): Path<String>,
    Query(params): Query<std::collections::HashMap<String, String>>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());
    let limit = params.get("limit").and_then(|s| s.parse::<usize>().ok()).unwrap_or(50);
    let offset = params.get("offset").and_then(|s| s.parse::<usize>().ok()).unwrap_or(0);
    let url = format!(
        "{}/pipeline/vectors?file_id={}&limit={}&offset={}",
        agent_url, file_key, limit, offset
    );

    let client = reqwest::Client::new();
    match client
        .get(&url)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await
    {
        Ok(resp) => {
            let body: serde_json::Value = resp.json().await.unwrap_or_default();
            Ok(Json(json!({ "code": 200, "data": body })))
        }
        Err(e) => Err((
            StatusCode::BAD_GATEWAY,
            Json(json!({ "code": 502, "message": format!("failed to get vectors: {}", e) })),
        )),
    }
}

pub async fn get_graph(
    Path(file_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());
    let url = format!("{}/pipeline/graph?file_id={}", agent_url, file_key);

    let client = reqwest::Client::new();
    match client
        .get(&url)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await
    {
        Ok(resp) => {
            let body: serde_json::Value = resp.json().await.unwrap_or_default();
            Ok(Json(json!({ "code": 200, "data": body })))
        }
        Err(e) => Err((
            StatusCode::BAD_GATEWAY,
            Json(json!({ "code": 502, "message": format!("failed to get graph: {}", e) })),
        )),
    }
}

pub async fn preview_file(
    Path(file_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());
    let url = format!("{}/pipeline/preview?file_id={}", agent_url, file_key);

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
            Json(json!({ "code": 502, "message": format!("failed to preview file: {}", e) })),
        )),
    }
}

pub async fn download_file_proxy(
    Path(file_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());
    let url = format!("{}/pipeline/download?file_id={}", agent_url, file_key);

    let client = reqwest::Client::new();
    match client
        .get(&url)
        .timeout(std::time::Duration::from_secs(120))
        .send()
        .await
    {
        Ok(resp) => {
            if !resp.status().is_success() {
                return Err((
                    StatusCode::BAD_GATEWAY,
                    Json(json!({ "code": 502, "message": "failed to download file from upstream" })),
                ));
            }

            let mut response_builder = axum::response::Response::builder()
                .status(StatusCode::OK);

            if let Some(v) = resp.headers().get("content-type").and_then(|v| v.to_str().ok()) {
                response_builder = response_builder.header("content-type", v);
            }
            if let Some(v) = resp.headers().get("content-disposition").and_then(|v| v.to_str().ok()) {
                response_builder = response_builder.header("content-disposition", v);
            }
            if let Some(v) = resp.headers().get("content-length").and_then(|v| v.to_str().ok()) {
                response_builder = response_builder.header("content-length", v);
            }

            let stream = resp.bytes_stream();
            let body = axum::body::Body::from_stream(stream);

            Ok(response_builder.body(body).unwrap())
        }
        Err(e) => Err((
            StatusCode::BAD_GATEWAY,
            Json(json!({ "code": 502, "message": format!("failed to download file: {}", e) })),
        )),
    }
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

pub async fn regenerate_vector(
    Path(file_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());
    let url = format!("{}/pipeline/vector?file_id={}", agent_url, file_key);

    let client = reqwest::Client::new();
    match client
        .post(&url)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await
    {
        Ok(resp) => {
            let body: serde_json::Value = resp.json().await.unwrap_or_default();
            Ok(Json(json!({ "code": 200, "data": body })))
        }
        Err(e) => Err((
            StatusCode::BAD_GATEWAY,
            Json(json!({ "code": 502, "message": format!("failed to regenerate vector: {}", e) })),
        )),
    }
}

pub async fn regenerate_graph(
    Path(file_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());
    let url = format!("{}/pipeline/graph?file_id={}", agent_url, file_key);

    let client = reqwest::Client::new();
    match client
        .post(&url)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await
    {
        Ok(resp) => {
            let body: serde_json::Value = resp.json().await.unwrap_or_default();
            Ok(Json(json!({ "code": 200, "data": body })))
        }
        Err(e) => Err((
            StatusCode::BAD_GATEWAY,
            Json(json!({ "code": 502, "message": format!("failed to regenerate graph: {}", e) })),
        )),
    }
}

pub async fn get_similar_chunks(
    Path(file_key): Path<String>,
    Query(params): Query<std::collections::HashMap<String, String>>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());
    let chunk_id = params.get("chunk_id").cloned().unwrap_or_default();
    let top_k = params.get("top_k").and_then(|s| s.parse::<usize>().ok()).unwrap_or(10);
    let url = format!(
        "{}/pipeline/similar?file_id={}&chunk_id={}&top_k={}",
        agent_url, file_key, chunk_id, top_k
    );

    let client = reqwest::Client::new();
    match client
        .get(&url)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await
    {
        Ok(resp) => {
            let body: serde_json::Value = resp.json().await.unwrap_or_default();
            Ok(Json(json!({ "code": 200, "data": body })))
        }
        Err(e) => Err((
            StatusCode::BAD_GATEWAY,
            Json(json!({ "code": 502, "message": format!("failed to get similar: {}", e) })),
        )),
    }
}

pub async fn delete_job(
    Path(file_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());
    let url = format!("{}/pipeline/delete?file_id={}", agent_url, file_key);

    let client = reqwest::Client::new();
    let agent_result: serde_json::Value = match client
        .post(&url)
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await
    {
        Ok(resp) => resp.json().await.unwrap_or_default(),
        Err(e) => {
            return Err((
                StatusCode::BAD_GATEWAY,
                Json(json!({ "code": 502, "message": format!("failed to delete job: {}", e) })),
            ));
        }
    };

    let db = get_db();
    let col = db
        .collection("knowledge_files")
        .await
        .map_err(|_| err_500())?;
    let _removed = col
        .remove_document::<serde_json::Value>(&file_key, Default::default(), None)
        .await
        .ok();

    Ok(Json(json!({
        "code": 200,
        "data": {
            "agent": agent_result,
            "arangodb_removed": true
        }
    })))
}

pub async fn retry_job(
    Path(file_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let agent_url = std::env::var("KNOWLEDGE_AGENT_URL")
        .unwrap_or_else(|_| "http://localhost:8007".to_string());
    let url = format!("{}/pipeline/retry?file_id={}", agent_url, file_key);

    let client = reqwest::Client::new();
    match client
        .post(&url)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .await
    {
        Ok(resp) => {
            let body: serde_json::Value = resp.json().await.unwrap_or_default();
            Ok(Json(json!({ "code": 200, "data": body })))
        }
        Err(e) => Err((
            StatusCode::BAD_GATEWAY,
            Json(json!({ "code": 502, "message": format!("failed to retry job: {}", e) })),
        )),
    }
}
