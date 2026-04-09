use crate::db::get_db;
use arangors::Collection;
use axum::{
    extract::{Path, Query},
    http::StatusCode,
    response::IntoResponse,
    routing::{delete, get, post, put},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Lead {
    #[serde(rename = "_key", skip_serializing_if = "Option::is_none")]
    pub key: Option<String>,
    pub name: String,
    pub company: String,
    pub email: String,
    pub phone: Option<String>,
    pub budget: Option<String>,
    pub message: Option<String>,
    pub github: Option<String>,
    pub status: String,
    pub note: Option<String>,
    pub can_download: bool,
    pub open_github: bool,
    pub created_at: String,
    pub updated_at: Option<String>,
    pub approved_at: Option<String>,
    pub approved_by: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct CreateLeadRequest {
    pub name: String,
    pub company: String,
    pub email: String,
    pub phone: Option<String>,
    pub budget: Option<String>,
    pub message: Option<String>,
    pub github: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct UpdateLeadRequest {
    pub status: Option<String>,
    pub note: Option<String>,
    pub can_download: Option<bool>,
    pub open_github: Option<bool>,
}

#[derive(Debug, Deserialize)]
pub struct ApproveLeadRequest {
    pub note: Option<String>,
    pub can_download: Option<bool>,
    pub open_github: Option<bool>,
}

#[derive(Debug, Deserialize)]
pub struct ListLeadsQuery {
    pub status: Option<String>,
    pub page: Option<usize>,
    pub page_size: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct LeadListResponse {
    pub leads: Vec<Lead>,
    pub total: usize,
    pub page: usize,
    pub page_size: usize,
}

#[derive(Debug, Serialize)]
pub struct CheckLeadResponse {
    pub approved: bool,
    pub can_download: bool,
    pub open_github: bool,
}

pub fn create_leads_router() -> Router {
    Router::new()
        .route("/api/v1/leads", post(create_lead))
        .route("/api/v1/leads/check", get(check_lead))
        .route("/api/v1/leads/admin/list", get(list_leads))
        .route("/api/v1/leads/admin/{key}", get(get_lead))
        .route("/api/v1/leads/admin/{key}", put(update_lead))
        .route("/api/v1/leads/admin/{key}/approve", put(approve_lead))
        .route("/api/v1/leads/admin/{key}/reject", put(reject_lead))
        .route("/api/v1/leads/admin/{key}", delete(delete_lead))
}

fn err_500() -> (StatusCode, Json<Value>) {
    (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({ "code": 500, "message": "internal server error" })))
}

fn err_404(resource: &str) -> (StatusCode, Json<Value>) {
    (StatusCode::NOT_FOUND, Json(json!({ "code": 404, "message": format!("{resource} not found") })))
}

async fn create_lead(Json(payload): Json<CreateLeadRequest>) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col: Collection<_> = db.collection("leads").await.map_err(|_| err_500())?;

    let existing: Vec<Value> = db
        .aql_bind_vars(
            "FOR l IN leads FILTER l.email == @email LIMIT 1 RETURN l._key",
            [("email", json!(payload.email))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    if !existing.is_empty() {
        return Err((StatusCode::CONFLICT, Json(json!({ "code": 409, "message": "此 email 已被註冊" }))));
    }

    let key = uuid_v4();
    let now = chrono::Utc::now().to_rfc3339();
    let doc = json!({
        "_key": key,
        "name": payload.name,
        "company": payload.company,
        "email": payload.email,
        "phone": payload.phone,
        "budget": payload.budget,
        "message": payload.message,
        "github": payload.github,
        "status": "pending",
        "note": null,
        "can_download": false,
        "open_github": false,
        "created_at": now,
        "updated_at": null,
        "approved_at": null,
        "approved_by": null,
    });

    col.create_document(doc, Default::default())
        .await
        .map_err(|_| err_500())?;

    Ok(Json(json!({ "code": 201, "message": "申請已收到，我們將盡快與您聯繫", "data": { "key": key } })))
}

async fn check_lead(Query(params): Query<HashMap<String, String>>) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let email = params.get("email").ok_or((StatusCode::BAD_REQUEST, Json(json!({ "message": "email required" }))))?;

    let db = get_db();
    let results: Vec<Value> = db
        .aql_bind_vars(
            "FOR l IN leads FILTER l.email == @email LIMIT 1 RETURN {status: l.status, can_download: l.can_download, open_github: l.open_github}",
            [("email", json!(email))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    let row = results.first();
    let approved = row.and_then(|v| v.get("status").and_then(|s| s.as_str())).map(|s| s == "approved").unwrap_or(false);
    let can_download = row.and_then(|v| v.get("can_download").and_then(|v| v.as_bool())).unwrap_or(false);
    let open_github = row.and_then(|v| v.get("open_github").and_then(|v| v.as_bool())).unwrap_or(false);

    Ok(Json(CheckLeadResponse { approved, can_download, open_github }))
}

async fn list_leads(Query(params): Query<ListLeadsQuery>) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let status_filter = params.status.as_deref();
    let page = params.page.unwrap_or(1).max(1);
    let page_size = params.page_size.unwrap_or(20).min(100);
    let skip = (page - 1) * page_size;

    let (query, bind_vars) = if let Some(s) = status_filter {
        (
            "LET total = (FOR l IN leads FILTER l.status == @status COLLECT WITH COUNT INTO c RETURN c)[0] LET rows = (FOR l IN leads FILTER l.status == @status SORT l.created_at DESC LIMIT @skip, @limit RETURN l) RETURN {leads: rows, total}".to_string(),
            [("status", json!(s)), ("skip", json!(skip)), ("limit", json!(page_size))].into(),
        )
    } else {
        (
            "LET total = (FOR l IN leads COLLECT WITH COUNT INTO c RETURN c)[0] LET rows = (FOR l IN leads SORT l.created_at DESC LIMIT @skip, @limit RETURN l) RETURN {leads: rows, total}".to_string(),
            [("skip", json!(skip)), ("limit", json!(page_size))].into(),
        )
    };

    let results: Vec<Value> = db
        .aql_bind_vars(&query, bind_vars)
        .await
        .map_err(|_| err_500())?;

    let (leads_arr, total) = if let Some(row) = results.first() {
        let arr = row.get("leads").and_then(|v| v.as_array()).cloned().unwrap_or_default();
        let n = row.get("total").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
        (arr, n)
    } else {
        (vec![], 0)
    };

    let leads: Vec<Lead> = leads_arr.into_iter().filter_map(|v| serde_json::from_value(v).ok()).collect();

    Ok(Json(json!({ "code": 200, "message": "success", "data": { "leads": leads, "total": total, "page": page, "page_size": page_size } })))
}

async fn get_lead(Path(key): Path<String>) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let mut results: Vec<Lead> = db
        .aql_bind_vars(
            "FOR l IN leads FILTER l._key == @key LIMIT 1 RETURN l",
            [("key", json!(key))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    let lead = results.pop().ok_or_else(|| err_404("lead"))?;

    Ok(Json(json!({ "code": 200, "message": "success", "data": lead })))
}

async fn update_lead(Path(key): Path<String>, Json(payload): Json<UpdateLeadRequest>) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col: Collection<_> = db.collection("leads").await.map_err(|_| err_500())?;

    let mut patch = serde_json::Map::new();
    patch.insert("updated_at".to_string(), json!(chrono::Utc::now().to_rfc3339()));

    if let Some(s) = payload.status {
        patch.insert("status".to_string(), json!(s));
    }
    if let Some(n) = payload.note {
        patch.insert("note".to_string(), json!(n));
    }
    if let Some(v) = payload.can_download {
        patch.insert("can_download".to_string(), json!(v));
    }
    if let Some(v) = payload.open_github {
        patch.insert("open_github".to_string(), json!(v));
    }

    col.update_document(&key, patch, Default::default())
        .await
        .map_err(|_| err_404("lead"))?;

    Ok(Json(json!({ "code": 200, "message": "updated", "data": null })))
}

async fn approve_lead(Path(key): Path<String>, Json(payload): Json<ApproveLeadRequest>) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col: Collection<_> = db.collection("leads").await.map_err(|_| err_500())?;
    let now = chrono::Utc::now().to_rfc3339();

    let mut patch = serde_json::Map::new();
    patch.insert("status".to_string(), json!("approved"));
    patch.insert("approved_at".to_string(), json!(now));
    patch.insert("updated_at".to_string(), json!(now));
    if let Some(n) = payload.note {
        patch.insert("note".to_string(), json!(n));
    }
    if let Some(v) = payload.can_download {
        patch.insert("can_download".to_string(), json!(v));
    }
    if let Some(v) = payload.open_github {
        patch.insert("open_github".to_string(), json!(v));
    }

    col.update_document(&key, patch, Default::default())
        .await
        .map_err(|_| err_404("lead"))?;

    Ok(Json(json!({ "code": 200, "message": "approved", "data": null })))
}

async fn reject_lead(Path(key): Path<String>, Json(payload): Json<ApproveLeadRequest>) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col: Collection<_> = db.collection("leads").await.map_err(|_| err_500())?;
    let now = chrono::Utc::now().to_rfc3339();

    let mut patch = serde_json::Map::new();
    patch.insert("status".to_string(), json!("rejected"));
    patch.insert("updated_at".to_string(), json!(now));
    if let Some(n) = payload.note {
        patch.insert("note".to_string(), json!(n));
    }

    col.update_document(&key, patch, Default::default())
        .await
        .map_err(|_| err_404("lead"))?;

    Ok(Json(json!({ "code": 200, "message": "rejected", "data": null })))
}

async fn delete_lead(Path(key): Path<String>) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col: Collection<_> = db.collection("leads").await.map_err(|_| err_500())?;

    col.remove_document::<Value>(&key, Default::default(), None)
        .await
        .map_err(|_| err_404("lead"))?;

    Ok(Json(json!({ "code": 200, "message": "deleted", "data": null })))
}

fn uuid_v4() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap();
    let ns = now.as_nanos();
    let random: u64 = (ns & 0xFFFFFFFFFFFFFFFF) as u64;
    format!("{:x}-{:x}", ns, random)
}
