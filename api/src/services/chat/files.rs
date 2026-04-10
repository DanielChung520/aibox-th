//! Chat 檔案處理模組
//!
//! # Description
//! 處理聊天 Session 附件上傳、列表、刪除與檔案狀態 webhook
//!
//! # Last Update: 2026-04-11 02:46:07
//! # Author: AI Agent
//! # Version: 1.0.0

use axum::extract::Multipart;
use axum::http::StatusCode;
use axum::Json;
use serde_json::Value;

use crate::api::sse::broadcast_file_status_event;
use crate::db::{get_db, ChatSession};
use crate::models::ApiResponse;

use super::clients::{
    call_knowledge_delete, call_knowledge_trigger, call_seaweedfs_delete_file,
    call_seaweedfs_upload,
};
use super::models::FileStatusWebhookPayload;

async fn ensure_session_exists(session_key: &str) -> Result<(), StatusCode> {
    let db = get_db();
    let sessions: Vec<ChatSession> = db
        .aql_bind_vars(
            "FOR s IN chat_sessions FILTER s._key == @key LIMIT 1 RETURN s",
            [("key", serde_json::json!(session_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if sessions.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }

    Ok(())
}

pub async fn handle_upload_session_file(
    session_key: String,
    mut multipart: Multipart,
) -> Result<Json<ApiResponse<Value>>, StatusCode> {
    ensure_session_exists(&session_key).await?;
    let db = get_db();

    let field = multipart
        .next_field()
        .await
        .map_err(|_| StatusCode::BAD_REQUEST)?
        .ok_or(StatusCode::BAD_REQUEST)?;

    let filename = field.file_name().unwrap_or("unknown").to_string();
    let bytes = field.bytes().await.map_err(|_| StatusCode::BAD_REQUEST)?;

    let file_key = uuid::Uuid::new_v4().to_string();
    let ext = std::path::Path::new(&filename)
        .extension()
        .and_then(|ext| ext.to_str())
        .unwrap_or("bin");

    let local_dir = std::env::current_dir()
        .unwrap_or_else(|_| std::path::PathBuf::from("."))
        .join("data/uploads/sessions")
        .join(&session_key);
    let local_path = local_dir.join(format!("{}.{}", file_key, ext));
    tokio::fs::create_dir_all(&local_dir)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    tokio::fs::write(&local_path, &bytes)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let s3_path = format!("bucket-aibox-assets/sessions/{}/{}.{}", session_key, file_key, ext);
    let _ = call_seaweedfs_upload(&s3_path, bytes.clone()).await;

    let now = chrono::Utc::now().to_rfc3339();
    let response_session_key = session_key.clone();
    let response_upload_time = now.clone();
    let doc = serde_json::json!({
        "_key": file_key,
        "filename": filename,
        "file_size": bytes.len() as i64,
        "file_type": ext,
        "upload_time": now,
        "vector_status": "pending",
        "graph_status": "pending",
        "knowledge_root_id": serde_json::Value::Null,
        "session_key": session_key.clone(),
        "local_path": local_path,
        "s3_path": s3_path,
    });

    let col = db
        .collection("knowledge_files")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(doc.clone(), Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let edge_doc = serde_json::json!({
        "_key": format!("csf_{}", file_key),
        "_from": format!("chat_sessions/{}", session_key),
        "_to": format!("knowledge_files/{}", file_key),
        "session_key": session_key.clone(),
        "file_key": file_key.clone(),
        "uploaded_at": now,
    });
    let edge_col = db
        .collection("chat_session_files")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    edge_col
        .create_document(edge_doc, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let _ = call_knowledge_trigger(serde_json::json!({
        "task": "vectorize",
        "file_id": file_key,
        "local_path": local_path,
        "root_id": session_key,
        "session_key": session_key,
    }))
    .await;

    Ok(Json(ApiResponse::success(serde_json::json!({
        "file_key": file_key,
        "filename": filename,
        "file_size": bytes.len() as i64,
        "file_type": ext,
        "session_key": response_session_key,
        "upload_time": response_upload_time,
        "vector_status": "pending",
        "graph_status": "pending",
    }))))
}

pub async fn handle_list_session_files(
    session_key: String,
) -> Result<Json<ApiResponse<Vec<Value>>>, StatusCode> {
    ensure_session_exists(&session_key).await?;
    let db = get_db();

    let files: Vec<Value> = db
        .aql_bind_vars(
            r#"
            FOR edge IN chat_session_files
            FILTER edge.session_key == @session_key
            LET file = DOCUMENT("knowledge_files", edge.file_key)
            FILTER file != null
            LET node_count = LENGTH(
                (FOR g IN knowledge_graphs FILTER g.file_id == edge.file_key RETURN 1)
            )
            LET edge_count = LENGTH(
                (FOR e IN knowledge_graph_edges FILTER e.file_id == edge.file_key RETURN 1)
            )
            RETURN {
                "file_key": edge.file_key,
                "filename": file.filename,
                "file_size": file.file_size,
                "file_type": file.file_type,
                "vector_status": file.vector_status,
                "graph_status": file.graph_status,
                "failed_reason": file.failed_reason,
                "upload_time": edge.uploaded_at,
                "graph_stats": {
                    "nodes": node_count,
                    "edges": edge_count
                }
            }
            "#,
            [("session_key", serde_json::json!(session_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(files)))
}

pub async fn handle_delete_session_file(
    session_key: String,
    file_key: String,
) -> Result<Json<ApiResponse<String>>, StatusCode> {
    ensure_session_exists(&session_key).await?;
    let db = get_db();

    let _ = call_knowledge_delete(&file_key).await;

    let _: Vec<Value> = db
        .aql_bind_vars(
            r#"
            FOR edge IN chat_session_files
            FILTER edge.session_key == @session_key AND edge.file_key == @file_key
            REMOVE edge IN chat_session_files
            "#,
            [
                ("session_key", serde_json::json!(session_key.clone())),
                ("file_key", serde_json::json!(file_key.clone())),
            ]
            .into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let _: Vec<Value> = db
        .aql_bind_vars(
            "REMOVE @key IN knowledge_files OPTIONS { ignoreErrors: true }",
            [("key", serde_json::json!(file_key.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let local_dir = std::env::current_dir()
        .unwrap_or_else(|_| std::path::PathBuf::from("."))
        .join("data/uploads/sessions")
        .join(&session_key);
    let _ = tokio::fs::remove_file(local_dir.join(format!("{}.*", file_key))).await;

    let _ = call_seaweedfs_delete_file(&session_key, &file_key).await;

    Ok(Json(ApiResponse::success("deleted".to_string())))
}

pub async fn handle_file_status_webhook(
    session_key: String,
    payload: FileStatusWebhookPayload,
) -> Result<Json<ApiResponse<Value>>, StatusCode> {
    broadcast_file_status_event(
        &session_key,
        serde_json::json!({
            "file_key": payload.file_key,
            "vector_status": payload.vector_status,
            "graph_status": payload.graph_status,
            "failed_reason": payload.failed_reason,
            "graph_stats": payload.graph_stats,
        }),
    );

    Ok(Json(ApiResponse::success(serde_json::json!({ "broadcasted": true }))))
}
