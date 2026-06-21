/**
 * @file        crm.rs
 * @description EEA-CRM API — customers CRUD, map markers, import endpoints
 * @lastUpdate  2026-06-13 13:00:00
 * @author      Daniel Chung
 * @version     1.0.0
 */

use crate::auth::verify_jwt;
use crate::db::get_db;
use crate::middleware::auth::AuthState;
use arangors::Collection;
use axum::{
    extract::{Path, Query},
    http::{header::AUTHORIZATION, HeaderMap, StatusCode},
    response::IntoResponse,
    routing::{get, patch, post, put, delete},
    Extension, Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::Arc;

pub fn create_crm_router() -> Router {
    Router::new()
        .route("/api/v1/crm/customers", get(list_customers))
        .route("/api/v1/crm/customers/map", get(map_customers))
        .route("/api/v1/crm/customers/{key}", patch(update_customer))
        .route("/api/v1/crm/customers/merge", post(merge_customers))
        .route("/api/v1/crm/customers/import/business-kindom", post(import_business_kindom))
        .route("/api/v1/crm/customers/import/mohw", post(import_mohw))
        .route("/api/v1/crm/permissions/{customer_key}", get(get_permission))
        .route("/api/v1/crm/permissions/{customer_key}", put(upsert_permission))
        .route("/api/v1/crm/permissions/{customer_key}", delete(delete_permission))
        .route("/api/v1/crm/users-and-roles", get(list_users_and_roles))
        // --- Contacts routes ---
        .route("/api/v1/crm/contacts", get(list_contacts).post(create_contact))
        .route("/api/v1/crm/contacts/{key}", get(get_contact).patch(update_contact).delete(delete_contact))
        .route("/api/v1/crm/contacts/by-customer/{customer_key}", get(list_contacts_by_customer))
        .route("/api/v1/crm/contacts/assign", post(assign_contact))
        .route("/api/v1/crm/contacts/{key}/set-primary", post(set_primary_contact))
}

#[derive(Debug, Deserialize)]
pub struct ListCustomersQuery {
    pub q: Option<String>,
    pub source: Option<String>,
    pub status: Option<String>,
    pub city: Option<String>,
    pub district: Option<String>,
    pub abc_grade: Option<String>,
    pub page: Option<usize>,
    pub page_size: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct CustomerListResponse {
    pub data: Vec<Value>,
    pub pagination: PaginationMeta,
    pub summary: SummaryMeta,
}

#[derive(Debug, Serialize)]
pub struct PaginationMeta {
    pub page: usize,
    pub page_size: usize,
    pub total: usize,
    pub total_pages: usize,
}

#[derive(Debug, Serialize)]
pub struct SummaryMeta {
    pub total: usize,
    pub by_source: HashMap<String, usize>,
    pub by_status: HashMap<String, usize>,
}

#[derive(Debug, Deserialize)]
pub struct MapCustomersQuery {
    pub bbox: Option<String>,
    pub source: Option<String>,
    pub status: Option<String>,
    pub abc_grade: Option<String>,
    pub city: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct MapMarkersResponse {
    pub markers: Vec<Value>,
    pub summary: MapSummaryMeta,
}

#[derive(Debug, Serialize)]
pub struct MapSummaryMeta {
    pub total: usize,
    pub in_viewport: usize,
    pub by_source: HashMap<String, usize>,
}

#[derive(Debug, Deserialize)]
pub struct UpdateCustomerPayload {
    pub status: Option<String>,
    pub abc_grade: Option<String>,
    pub sales_rep: Option<String>,
    pub tags: Option<Vec<String>>,
    pub last_contact_at: Option<String>,
    pub last_contact_note: Option<String>,
    pub name: Option<String>,
    pub phone: Option<String>,
    pub email: Option<String>,
    pub address: Option<String>,
    pub category: Option<Vec<String>>,
    pub org_tags: Option<Vec<String>>,
}

#[derive(Debug, Deserialize)]
pub struct MergeCustomersPayload {
    pub primary_key: String,
    pub merge_keys: Vec<String>,
    pub reason: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ImportResult {
    pub imported: usize,
    pub updated: usize,
    pub skipped: usize,
    pub errors: Vec<String>,
    pub batch_id: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CustomerPermission {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub customer_key: String,
    #[serde(default)]
    pub assigned_users: Vec<String>,
    #[serde(default)]
    pub assigned_roles: Vec<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Deserialize)]
pub struct UpsertPermissionPayload {
    #[serde(default)]
    pub assigned_users: Vec<String>,
    #[serde(default)]
    pub assigned_roles: Vec<String>,
}

#[derive(Debug, Serialize)]
pub struct UsersAndRolesResponse {
    pub users: Vec<Value>,
    pub roles: Vec<Value>,
}

async fn resolve_auth(headers: &HeaderMap) -> (Option<String>, Option<Vec<String>>) {
    let token = headers
        .get(AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "));
    let Some(token) = token else { return (None, None); };
    let Ok(token_data) = verify_jwt(token) else { return (None, None); };
    let db = get_db();
    let raw_users: Vec<Value> = db
        .aql_bind_vars(
            "FOR u IN users FILTER u.username == @username LIMIT 1 RETURN u",
            [("username", json!(token_data.claims.username))].into(),
        )
        .await
        .unwrap_or_default();
    let raw_user = match raw_users.into_iter().next() {
        Some(u) => u,
        None => return (None, None),
    };
    let uk = match raw_user.get("_key").and_then(|v| v.as_str()) {
        Some(k) => k.to_string(),
        None => return (None, None),
    };
    let role_keys = raw_user
        .get("role_keys")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    (Some(uk), Some(role_keys))
}

fn err_500() -> (StatusCode, Json<Value>) {
    (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({ "code": 500, "message": "internal server error" })))
}

fn err_404() -> (StatusCode, Json<Value>) {
    (StatusCode::NOT_FOUND, Json(json!({ "code": 404, "message": "customer not found" })))
}

fn err_400(msg: &str) -> (StatusCode, Json<Value>) {
    (StatusCode::BAD_REQUEST, Json(json!({ "code": 400, "message": msg })))
}

fn now_iso() -> String {
    chrono::Utc::now().to_rfc3339()
}

async fn list_customers(
    headers: HeaderMap,
    Query(params): Query<ListCustomersQuery>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let page = params.page.unwrap_or(1).max(1);
    let page_size = params.page_size.unwrap_or(50).min(200);
    let skip = (page - 1) * page_size;

    let (user_key, user_roles) = resolve_auth(&headers).await;

    let mut filters: Vec<String> = Vec::new();
    let mut bind_vars: Vec<(&str, Value)> = vec![
        ("skip", json!(skip)),
        ("limit", json!(page_size)),
    ];

    if let Some(ref q) = params.q {
        if !q.is_empty() {
            filters.push("(c.name LIKE @q || c.phone LIKE @q || c.address LIKE @q)".to_string());
            bind_vars.push(("q", json!(format!("%{}%", q))));
        }
    }
    if let Some(ref source) = params.source {
        if !source.is_empty() {
            filters.push("c.source == @source".to_string());
            bind_vars.push(("source", json!(source)));
        }
    }
    if let Some(ref status) = params.status {
        if !status.is_empty() {
            filters.push("c.status == @status".to_string());
            bind_vars.push(("status", json!(status)));
        }
    }
    if let Some(ref city) = params.city {
        if !city.is_empty() {
            filters.push("c.city == @city".to_string());
            bind_vars.push(("city", json!(city)));
        }
    }
    if let Some(ref district) = params.district {
        if !district.is_empty() {
            filters.push("c.district == @district".to_string());
            bind_vars.push(("district", json!(district)));
        }
    }
    if let Some(ref abc) = params.abc_grade {
        if !abc.is_empty() {
            filters.push("c.abc_grade == @abc_grade".to_string());
            bind_vars.push(("abc_grade", json!(abc)));
        }
    }

    let uk = user_key.clone().unwrap_or_default();
    let roles = user_roles.clone().unwrap_or_default();
    let roles_json: Value = serde_json::to_value(&roles).unwrap_or_default();
    bind_vars.push(("user_key", json!(uk)));
    bind_vars.push(("user_roles", roles_json));

    let where_clause = if filters.is_empty() {
        String::new()
    } else {
        format!("FILTER {}", filters.join(" && "))
    };

    let aql = format!(
        r#"
        LET total = (FOR c IN crm_customers {} COLLECT WITH COUNT INTO cnt RETURN cnt)[0]
        LET rows = (
            FOR c IN crm_customers {}
                LET perm = FIRST(
                    FOR p IN crm_customer_permissions FILTER p.customer_key == c._key RETURN p
                )
                LET _perm_assigned = perm != null
                LET _perm_authorized = !_perm_assigned
                    || @user_key IN (perm.assigned_users  ?: [])
                    || LENGTH(
                        (FOR r IN (perm.assigned_roles ?: []) FILTER r IN @user_roles RETURN 1)
                       ) > 0
                SORT c.created_at DESC
                LIMIT @skip, @limit
                RETURN MERGE(c, {{_perm_assigned, _perm_authorized}})
        )
        LET by_source = (FOR c IN crm_customers {} COLLECT src = c.source WITH COUNT INTO cnt RETURN {{source: src, count: cnt}})
        LET by_status = (FOR c IN crm_customers {} COLLECT st = c.status WITH COUNT INTO cnt RETURN {{status: st, count: cnt}})
        RETURN {{total, rows, by_source, by_status}}
        "#,
        where_clause, where_clause, where_clause, where_clause
    );

    let bind = bind_vars.iter().map(|(k, v)| (*k, v.clone())).collect();
    let mut results: Vec<Value> = db.aql_bind_vars(&aql, bind).await.map_err(|e| {
        eprintln!("crm list query error: {}", e);
        err_500()
    })?;

    if results.is_empty() {
        return Ok(Json(json!(CustomerListResponse {
            data: vec![],
            pagination: PaginationMeta { page, page_size, total: 0, total_pages: 0 },
            summary: SummaryMeta {
                total: 0,
                by_source: HashMap::new(),
                by_status: HashMap::new(),
            },
        })));
    }

    let row = results.remove(0);
    let total = row.get("total").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
    let data = row.get("rows").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let total_pages = if page_size > 0 { (total + page_size - 1) / page_size } else { 0 };

    let mut by_source = HashMap::new();
    if let Some(arr) = row.get("by_source").and_then(|v| v.as_array()) {
        for entry in arr {
            let src = entry.get("source").and_then(|v| v.as_str()).unwrap_or("unknown").to_string();
            let count = entry.get("count").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
            by_source.insert(src, count);
        }
    }
    let mut by_status = HashMap::new();
    if let Some(arr) = row.get("by_status").and_then(|v| v.as_array()) {
        for entry in arr {
            let st = entry.get("status").and_then(|v| v.as_str()).unwrap_or("unknown").to_string();
            let count = entry.get("count").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
            by_status.insert(st, count);
        }
    }

    Ok(Json(json!(CustomerListResponse {
        data,
        pagination: PaginationMeta { page, page_size, total, total_pages },
        summary: SummaryMeta { total, by_source, by_status },
    })))
}

async fn map_customers(
    Query(params): Query<MapCustomersQuery>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();

    let mut filters: Vec<String> = vec!["c.lat != null && c.lng != null".to_string()];
    let mut bind_vars: Vec<(&str, Value)> = Vec::new();

    if let Some(ref bbox) = params.bbox {
        let parts: Vec<&str> = bbox.split(',').collect();
        if parts.len() == 4 {
            let sw_lat = parts[0].parse::<f64>().unwrap_or(-90.0);
            let sw_lng = parts[1].parse::<f64>().unwrap_or(-180.0);
            let ne_lat = parts[2].parse::<f64>().unwrap_or(90.0);
            let ne_lng = parts[3].parse::<f64>().unwrap_or(180.0);
            filters.push("c.lat >= @sw_lat && c.lat <= @ne_lat && c.lng >= @sw_lng && c.lng <= @ne_lng".to_string());
            bind_vars.extend([
                ("sw_lat", json!(sw_lat)),
                ("sw_lng", json!(sw_lng)),
                ("ne_lat", json!(ne_lat)),
                ("ne_lng", json!(ne_lng)),
            ]);
        }
    }

    if let Some(ref source) = params.source {
        if !source.is_empty() {
            filters.push("c.source == @source".to_string());
            bind_vars.push(("source", json!(source)));
        }
    }
    if let Some(ref status) = params.status {
        if !status.is_empty() {
            filters.push("c.status == @status".to_string());
            bind_vars.push(("status", json!(status)));
        }
    }
    if let Some(ref abc) = params.abc_grade {
        if !abc.is_empty() {
            filters.push("c.abc_grade == @abc_grade".to_string());
            bind_vars.push(("abc_grade", json!(abc)));
        }
    }
    if let Some(ref city) = params.city {
        if !city.is_empty() {
            filters.push("c.city == @city".to_string());
            bind_vars.push(("city", json!(city)));
        }
    }

    let where_clause = format!("FILTER {}", filters.join(" && "));

    let aql = format!(
        r#"
        LET total = (FOR c IN crm_customers {} COLLECT WITH COUNT INTO cnt RETURN cnt)[0]
        LET markers = (FOR c IN crm_customers {} SORT c.name RETURN {{
            id: c._key,
            source: c.source,
            status: c.status,
            name: c.name,
            lat: c.lat,
            lng: c.lng,
            abc_grade: c.abc_grade,
            phone: c.phone,
            address: c.address,
            city: c.city,
            district: c.district,
            sales_rep: c.sales_rep,
            category: c.category,
            org_tags: c.org_tags
        }})
        LET by_source = (FOR c IN crm_customers {} COLLECT src = c.source WITH COUNT INTO cnt RETURN {{source: src, count: cnt}})
        RETURN {{total, markers, by_source}}
        "#,
        where_clause, where_clause, where_clause
    );

    let bind = bind_vars.iter().map(|(k, v)| (*k, v.clone())).collect();
    let mut results: Vec<Value> = db.aql_bind_vars(&aql, bind).await.map_err(|e| {
        eprintln!("crm map query error: {}", e);
        err_500()
    })?;

    if results.is_empty() {
        return Ok(Json(json!(MapMarkersResponse {
            markers: vec![],
            summary: MapSummaryMeta {
                total: 0,
                in_viewport: 0,
                by_source: HashMap::new(),
            },
        })));
    }

    let row = results.remove(0);
    let total = row.get("total").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
    let markers = row.get("markers").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let in_viewport = markers.len();

    let mut by_source = HashMap::new();
    if let Some(arr) = row.get("by_source").and_then(|v| v.as_array()) {
        for entry in arr {
            let src = entry.get("source").and_then(|v| v.as_str()).unwrap_or("unknown").to_string();
            let count = entry.get("count").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
            by_source.insert(src, count);
        }
    }

    Ok(Json(json!(MapMarkersResponse {
        markers,
        summary: MapSummaryMeta { total, in_viewport, by_source },
    })))
}

async fn update_customer(
    Path(key): Path<String>,
    Json(payload): Json<UpdateCustomerPayload>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col: Collection<_> = db.collection("crm_customers").await.map_err(|_| err_500())?;

    let mut patch = serde_json::Map::new();

    if let Some(v) = payload.status { patch.insert("status".into(), json!(v)); }
    if let Some(v) = payload.abc_grade { patch.insert("abc_grade".into(), json!(v)); }
    if let Some(v) = payload.sales_rep { patch.insert("sales_rep".into(), json!(v)); }
    if let Some(v) = payload.tags { patch.insert("tags".into(), json!(v)); }
    if let Some(v) = payload.last_contact_at { patch.insert("last_contact_at".into(), json!(v)); }
    if let Some(v) = payload.last_contact_note { patch.insert("last_contact_note".into(), json!(v)); }
    if let Some(v) = payload.name { patch.insert("name".into(), json!(v)); }
    if let Some(v) = payload.phone { patch.insert("phone".into(), json!(v)); }
    if let Some(v) = payload.email { patch.insert("email".into(), json!(v)); }
    if let Some(v) = payload.address { patch.insert("address".into(), json!(v)); }
    if let Some(v) = payload.category { patch.insert("category".into(), json!(v)); }
    if let Some(v) = payload.org_tags { patch.insert("org_tags".into(), json!(v)); }

    if patch.is_empty() {
        return Err(err_400("no fields to update"));
    }

    patch.insert("updated_at".into(), json!(now_iso()));

    col.update_document(&key, Value::Object(patch), Default::default())
        .await
        .map_err(|_| err_404())?;

    let mut updated: Vec<Value> = db
        .aql_bind_vars(
            "FOR c IN crm_customers FILTER c._key == @key LIMIT 1 RETURN c",
            [("key", json!(key))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    let customer = updated.pop().ok_or_else(err_404)?;
    Ok(Json(json!({ "code": 200, "message": "updated", "data": customer })))
}

async fn merge_customers(
    Json(payload): Json<MergeCustomersPayload>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col: Collection<_> = db.collection("crm_customers").await.map_err(|_| err_500())?;

    let primary_exists: Vec<Value> = db
        .aql_bind_vars(
            "FOR c IN crm_customers FILTER c._key == @key LIMIT 1 RETURN c._key",
            [("key", json!(&payload.primary_key))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    if primary_exists.is_empty() {
        return Err(err_400(&format!("primary key {} not found", payload.primary_key)));
    }

    let now = now_iso();
    let mut merged_count = 0usize;

    for merge_key in &payload.merge_keys {
        let update_result = col
            .update_document(
                merge_key,
                json!({
                    "merge_status": "merged",
                    "merged_into": &payload.primary_key,
                    "updated_at": now,
                }),
                Default::default(),
            )
            .await;

        if update_result.is_ok() {
            merged_count += 1;
        }
    }

    Ok(Json(json!({
        "code": 200,
        "message": format!("merged {} records into {}", merged_count, payload.primary_key),
        "data": {
            "primary_key": payload.primary_key,
            "merged_count": merged_count,
        }
    })))
}

async fn import_business_kindom(
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let records = payload.get("records").and_then(|v| v.as_array()).ok_or_else(|| {
        err_400("missing 'records' array in request body")
    })?;

    let db = get_db();
    let col: Collection<_> = db.collection("crm_customers").await.map_err(|_| err_500())?;
    let now = now_iso();
    let batch_id = format!("bk_import_{}", chrono::Utc::now().format("%Y%m%d_%H%M%S"));

    let mut imported = 0usize;
    let mut updated = 0usize;
    let mut skipped = 0usize;
    let mut errors: Vec<String> = Vec::new();

    for record in records {
        let biz_id = record.get("流水號")
            .or_else(|| record.get("business_kindom_id"))
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());

        let name = record.get("客戶名稱")
            .or_else(|| record.get("name"))
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        if name.is_empty() {
            skipped += 1;
            continue;
        }

        let store_name = record.get("總店名稱").and_then(|v| v.as_str()).unwrap_or("");
        let branch_name = record.get("分店名稱").and_then(|v| v.as_str()).unwrap_or("");
        let full_name = if branch_name.is_empty() { name.clone() } else { format!("{}_{}", store_name, branch_name) };

        let address = record.get("分店地址").or_else(|| record.get("address")).and_then(|v| v.as_str()).unwrap_or("");
        let phone = record.get("客戶電話").or_else(|| record.get("phone")).and_then(|v| v.as_str()).unwrap_or("");
        let sales_rep = record.get("執行人員").or_else(|| record.get("sales_rep")).and_then(|v| v.as_str()).unwrap_or("");
        let abc_grade = record.get("階級").or_else(|| record.get("abc_grade")).and_then(|v| v.as_str()).unwrap_or("");
        let category = record.get("分店分類").or_else(|| record.get("category")).and_then(|v| v.as_str()).unwrap_or("");
        let lat = record.get("latitude").or_else(|| record.get("lat")).and_then(|v| v.as_str()).and_then(|s| s.parse::<f64>().ok());
        let lng = record.get("longitude").or_else(|| record.get("lng")).and_then(|v| v.as_str()).and_then(|s| s.parse::<f64>().ok());

        if let Some(ref bid) = biz_id {
            let tags_val: Vec<String> = if category.is_empty() { vec![] } else { vec![category.to_string()] };
            let update_result: Result<Vec<Value>, _> = db.aql_bind_vars(
                r#"
                FOR c IN crm_customers
                    FILTER c.business_kindom_id == @id
                    UPDATE c WITH {
                        name: @name,
                        name_raw: @name_raw,
                        phone: @phone,
                        address: @address,
                        sales_rep: @sales_rep,
                        abc_grade: @abc_grade,
                        category: @category,
                        lat: @lat,
                        lng: @lng,
                        import_batch: @batch_id,
                        updated_at: @now
                    } IN crm_customers
                    RETURN OLD._key
                "#,
                std::collections::HashMap::from([
                    ("id", json!(bid)),
                    ("name", json!(full_name)),
                    ("name_raw", json!(name)),
                    ("phone", json!(phone)),
                    ("address", json!(address)),
                    ("sales_rep", json!(sales_rep)),
                    ("abc_grade", json!(abc_grade)),
                    ("category", json!(tags_val)),
                    ("lat", json!(lat)),
                    ("lng", json!(lng)),
                    ("batch_id", json!(batch_id)),
                    ("now", json!(now)),
                ]),
            ).await;

            if let Ok(update_result) = update_result {
                if !update_result.is_empty() {
                    updated += 1;
                    continue;
                }
            }
        }

        let key = uuid::Uuid::new_v4().to_string();
        let tags: Vec<String> = if category.is_empty() { vec![] } else { vec![category.to_string()] };

        let doc = json!({
            "_key": key,
            "source": "business_kindom",
            "status": "lead",
            "name": full_name,
            "name_raw": name,
            "phone": phone,
            "address": address,
            "sales_rep": sales_rep,
            "abc_grade": abc_grade,
            "category": tags,
            "business_kindom_id": biz_id,
            "lat": lat,
            "lng": lng,
            "created_at": now,
            "updated_at": now,
            "synced_at": now,
            "import_batch": batch_id,
        });

        col.create_document(doc, Default::default()).await.map_err(|e| {
            errors.push(format!("insert error: {}", e));
        }).ok();
        imported += 1;
    }

    Ok(Json(json!(ImportResult {
        imported,
        updated,
        skipped,
        errors,
        batch_id,
    })))
}

async fn import_mohw() -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    Ok(Json(json!({
        "code": 200,
        "message": "MOHW import triggered — stub endpoint, actual CSV fetch+parse to be implemented in Python job runner",
        "data": { "status": "stub" }
    })))
}

async fn get_permission(
    Path(customer_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let results: Vec<Value> = db
        .aql_bind_vars(
            "FOR p IN crm_customer_permissions FILTER p.customer_key == @key LIMIT 1 RETURN p",
            [("key", json!(customer_key))].into(),
        )
        .await
        .map_err(|_| err_500())?;
    if let Some(perm) = results.into_iter().next() {
        Ok(Json(json!({ "code": 200, "data": perm })))
    } else {
        Ok(Json(json!({ "code": 200, "data": null })))
    }
}

async fn upsert_permission(
    Path(customer_key): Path<String>,
    Json(payload): Json<UpsertPermissionPayload>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let now = now_iso();
    let existing: Vec<Value> = db
        .aql_bind_vars(
            "FOR p IN crm_customer_permissions FILTER p.customer_key == @key LIMIT 1 RETURN p._key",
            [("key", json!(&customer_key))].into(),
        )
        .await
        .map_err(|_| err_500())?;
    if let Some(existing_key) = existing.into_iter().next().and_then(|v| v.as_str().map(String::from)) {
        let patch = json!({
            "assigned_users": payload.assigned_users,
            "assigned_roles": payload.assigned_roles,
            "updated_at": now,
        });
        let _: Vec<Value> = db.aql_bind_vars(
            "UPDATE @key WITH @patch IN crm_customer_permissions RETURN NEW",
            Into::<HashMap<&str, Value>>::into([("key", json!(existing_key)), ("patch", patch)]),
        )
        .await
        .map_err(|_| err_500())?;
    } else {
        let doc = json!({
            "customer_key": customer_key,
            "assigned_users": payload.assigned_users,
            "assigned_roles": payload.assigned_roles,
            "created_at": now,
            "updated_at": now,
        });
        let _: Vec<Value> = db.aql_bind_vars(
            "INSERT @doc INTO crm_customer_permissions RETURN NEW",
            [("doc", doc)].into(),
        )
        .await
        .map_err(|_| err_500())?;
    }
    Ok(Json(json!({ "code": 200, "message": "permission updated" })))
}

async fn delete_permission(
    Path(customer_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let _: Vec<Value> = db.aql_bind_vars(
        "FOR p IN crm_customer_permissions FILTER p.customer_key == @key REMOVE p IN crm_customer_permissions",
        [("key", json!(customer_key))].into(),
    )
    .await
    .map_err(|_| err_500())?;
    Ok(Json(json!({ "code": 200, "message": "permission removed" })))
}

async fn list_users_and_roles() -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let users: Vec<Value> = db
        .aql_str(" \
            FOR u IN users \
            FILTER u.status == 'enabled' \
            LET keys = u.role_keys != null ? u.role_keys : (u.role_key != null ? [u.role_key] : []) \
            LET role_names = ( \
                FOR r IN roles \
                FILTER r._key IN keys \
                RETURN r.name \
            ) \
            RETURN { \
                _key: u._key, \
                name: u.name, \
                username: u.username, \
                role_keys: keys, \
                role_names: role_names, \
                status: u.status \
            } \
        ")
        .await
        .map_err(|_| err_500())?;
    let roles: Vec<Value> = db
        .aql_str("FOR r IN roles RETURN { _key: r._key, name: r.name }")
        .await
        .map_err(|_| err_500())?;
    Ok(Json(json!({ "code": 200, "data": { "users": users, "roles": roles } })))
}

// =====================================================================
// Contacts CRUD
// =====================================================================

#[derive(Debug, Deserialize)]
pub struct ListContactsQuery {
    pub q: Option<String>,
    pub source: Option<String>,
    pub line_status: Option<String>,
    pub customer_key: Option<String>,
    pub owner_key: Option<String>,
    pub is_primary: Option<bool>,
    pub page: Option<usize>,
    pub page_size: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct ContactListResponse {
    pub code: u16,
    pub data: Vec<Value>,
    pub pagination: ContactPaginationMeta,
}

#[derive(Debug, Serialize)]
pub struct ContactPaginationMeta {
    pub page: usize,
    pub page_size: usize,
    pub total: usize,
    pub total_pages: usize,
}

#[derive(Debug, Deserialize)]
pub struct CreateContactPayload {
    pub name_cn: Option<String>,
    pub name_en: Option<String>,
    pub customer_key: Option<String>,
    pub titles: Option<Value>,
    pub phones: Option<Value>,
    pub emails: Option<Value>,
    pub social_accounts: Option<Value>,
    pub organizations: Option<Value>,
    pub notes: Option<String>,
    pub card_images: Option<Value>,
    pub source: Option<String>,
    pub line_status: Option<String>,
    pub is_primary: Option<bool>,
    pub owner_key: Option<String>,
    pub channel_key: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct UpdateContactPayload {
    pub name_cn: Option<String>,
    pub name_en: Option<String>,
    pub customer_key: Option<String>,
    pub titles: Option<Value>,
    pub phones: Option<Value>,
    pub emails: Option<Value>,
    pub social_accounts: Option<Value>,
    pub organizations: Option<Value>,
    pub notes: Option<String>,
    pub card_images: Option<Value>,
    pub source: Option<String>,
    pub line_status: Option<String>,
    pub is_primary: Option<bool>,
    pub owner_key: Option<String>,
    pub channel_key: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct AssignContactPayload {
    pub key: String,
    pub owner_key: String,
}

async fn list_contacts(
    headers: HeaderMap,
    Query(params): Query<ListContactsQuery>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let page = params.page.unwrap_or(1).max(1);
    let page_size = params.page_size.unwrap_or(20).min(100);
    let skip = (page - 1) * page_size;

    let (current_user_key, _user_roles) = resolve_auth(&headers).await;
    let effective_owner = params.owner_key.clone()
        .or_else(|| current_user_key.clone())
        .unwrap_or_default();

    let mut filters: Vec<String> = Vec::new();
    let mut bind_vars: Vec<(&str, Value)> = vec![
        ("skip", json!(skip)),
        ("limit", json!(page_size)),
    ];

    // 權限過濾：一般用戶只看自己的聯絡人
    // (管理員可指定 owner_key 參數查看其他人)
    filters.push("c.owner_key == @owner_key".to_string());
    bind_vars.push(("owner_key", json!(effective_owner)));

    if let Some(ref q) = params.q {
        if !q.is_empty() {
            filters.push("(c.name_cn LIKE @q || c.name_en LIKE @q || c.notes LIKE @q)".to_string());
            bind_vars.push(("q", json!(format!("%{}%", q))));
        }
    }
    if let Some(ref source) = params.source {
        if !source.is_empty() {
            filters.push("c.source == @source".to_string());
            bind_vars.push(("source", json!(source)));
        }
    }
    if let Some(ref ls) = params.line_status {
        if !ls.is_empty() {
            filters.push("c.line_status == @line_status".to_string());
            bind_vars.push(("line_status", json!(ls)));
        }
    }
    if let Some(ref ck) = params.customer_key {
        if !ck.is_empty() {
            filters.push("c.customer_key == @customer_key".to_string());
            bind_vars.push(("customer_key", json!(ck)));
        }
    }
    if let Some(primary) = params.is_primary {
        filters.push("c.is_primary == @is_primary".to_string());
        bind_vars.push(("is_primary", json!(primary)));
    }

    let where_clause = if filters.is_empty() {
        String::new()
    } else {
        format!("FILTER {}", filters.join(" && "))
    };

    let aql = format!(
        r#"
        LET total = (FOR c IN crm_contacts {} COLLECT WITH COUNT INTO cnt RETURN cnt)[0]
        LET rows = (
            FOR c IN crm_contacts {}
                LET customer_name = FIRST(
                    FOR cust IN crm_customers FILTER cust._key == c.customer_key LIMIT 1 RETURN cust.name
                )
                SORT c.created_at DESC
                LIMIT @skip, @limit
                RETURN MERGE(c, {{customer_name}})
        )
        RETURN {{total, rows}}
        "#,
        where_clause, where_clause
    );

    let bind = bind_vars.iter().map(|(k, v)| (*k, v.clone())).collect();
    let mut results: Vec<Value> = db.aql_bind_vars(&aql, bind).await.map_err(|e| {
        eprintln!("crm contacts list error: {}", e);
        err_500()
    })?;

    if results.is_empty() {
        return Ok(Json(json!(ContactListResponse {
            code: 200,
            data: vec![],
            pagination: ContactPaginationMeta { page, page_size, total: 0, total_pages: 0 },
        })));
    }

    let row = results.remove(0);
    let total = row.get("total").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
    let data = row.get("rows").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let total_pages = if page_size > 0 { (total + page_size - 1) / page_size } else { 0 };

    Ok(Json(json!(ContactListResponse {
        code: 200,
        data,
        pagination: ContactPaginationMeta { page, page_size, total, total_pages },
    })))
}

async fn create_contact(
    headers: HeaderMap,
    Json(payload): Json<CreateContactPayload>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col: Collection<_> = db.collection("crm_contacts").await.map_err(|_| err_500())?;
    let (_user_key, _user_roles) = resolve_auth(&headers).await;
    let now = now_iso();
    let key = uuid::Uuid::new_v4().to_string();

    let owner = payload.owner_key.clone().or_else(|| _user_key.clone()).unwrap_or_default();

    let mut doc_map = serde_json::Map::new();
    doc_map.insert("_key".into(), json!(key));
    doc_map.insert("customer_key".into(), json!(payload.customer_key));
    doc_map.insert("source".into(), json!(payload.source.unwrap_or_else(|| "manual".to_string())));
    doc_map.insert("line_status".into(), json!(payload.line_status.unwrap_or_else(|| "none".to_string())));
    doc_map.insert("is_primary".into(), json!(payload.is_primary.unwrap_or(false)));
    doc_map.insert("owner_key".into(), json!(owner));
    doc_map.insert("created_at".into(), json!(now.clone()));
    doc_map.insert("updated_at".into(), json!(now));
    doc_map.insert("created_by".into(), json!(_user_key.unwrap_or_default()));

    if let Some(v) = payload.name_cn { doc_map.insert("name_cn".into(), json!(v)); }
    if let Some(v) = payload.name_en { doc_map.insert("name_en".into(), json!(v)); }
    if let Some(v) = payload.titles { doc_map.insert("titles".into(), v); }
    if let Some(v) = payload.phones { doc_map.insert("phones".into(), v); }
    if let Some(v) = payload.emails { doc_map.insert("emails".into(), v); }
    if let Some(v) = payload.social_accounts { doc_map.insert("social_accounts".into(), v); }
    if let Some(v) = payload.organizations { doc_map.insert("organizations".into(), v); }
    if let Some(v) = payload.notes { doc_map.insert("notes".into(), json!(v)); }
    if let Some(v) = payload.card_images { doc_map.insert("card_images".into(), v); }
    if let Some(v) = payload.channel_key { doc_map.insert("channel_key".into(), json!(v)); }

    let doc = Value::Object(doc_map);

    col.create_document(doc.clone(), Default::default()).await.map_err(|e| {
        eprintln!("crm create contact error: {}", e);
        err_500()
    })?;

    Ok(Json(json!({ "code": 200, "message": "created", "data": doc })))
}

async fn get_contact(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let mut results: Vec<Value> = db.aql_bind_vars(
        r#"
        FOR c IN crm_contacts FILTER c._key == @key LIMIT 1
            LET customer_name = FIRST(
                FOR cust IN crm_customers FILTER cust._key == c.customer_key LIMIT 1 RETURN cust.name
            )
            RETURN MERGE(c, {customer_name})
        "#,
        [("key", json!(key))].into(),
    ).await.map_err(|e| {
        eprintln!("crm get contact error: {}", e);
        err_500()
    })?;

    let contact = results.pop().ok_or_else(err_404)?;
    Ok(Json(json!({ "code": 200, "data": contact })))
}

async fn update_contact(
    Path(key): Path<String>,
    Json(payload): Json<UpdateContactPayload>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col: Collection<_> = db.collection("crm_contacts").await.map_err(|_| err_500())?;

    let mut patch = serde_json::Map::new();
    if let Some(v) = payload.name_cn { patch.insert("name_cn".into(), json!(v)); }
    if let Some(v) = payload.name_en { patch.insert("name_en".into(), json!(v)); }
    if let Some(v) = payload.customer_key { patch.insert("customer_key".into(), json!(v)); }
    if let Some(v) = payload.titles { patch.insert("titles".into(), v); }
    if let Some(v) = payload.phones { patch.insert("phones".into(), v); }
    if let Some(v) = payload.emails { patch.insert("emails".into(), v); }
    if let Some(v) = payload.social_accounts { patch.insert("social_accounts".into(), v); }
    if let Some(v) = payload.organizations { patch.insert("organizations".into(), v); }
    if let Some(v) = payload.notes { patch.insert("notes".into(), json!(v)); }
    if let Some(v) = payload.card_images { patch.insert("card_images".into(), v); }
    if let Some(v) = payload.channel_key { patch.insert("channel_key".into(), json!(v)); }
    if let Some(v) = payload.source { patch.insert("source".into(), json!(v)); }
    if let Some(v) = payload.line_status { patch.insert("line_status".into(), json!(v)); }
    if let Some(v) = payload.is_primary { patch.insert("is_primary".into(), json!(v)); }
    if let Some(v) = payload.owner_key { patch.insert("owner_key".into(), json!(v)); }

    if patch.is_empty() {
        return Err(err_400("no fields to update"));
    }
    patch.insert("updated_at".into(), json!(now_iso()));

    col.update_document(&key, Value::Object(patch), Default::default())
        .await
        .map_err(|_| err_404())?;

    let mut updated: Vec<Value> = db
        .aql_bind_vars(
            "FOR c IN crm_contacts FILTER c._key == @key LIMIT 1 RETURN c",
            [("key", json!(key))].into(),
        )
        .await
        .map_err(|_| err_500())?;

    let contact = updated.pop().ok_or_else(err_404)?;
    Ok(Json(json!({ "code": 200, "message": "updated", "data": contact })))
}

async fn delete_contact(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col: Collection<_> = db.collection("crm_contacts").await.map_err(|_| err_500())?;
    col.remove_document::<Value>(&key, Default::default(), None)
        .await
        .map_err(|_| err_404())?;
    Ok(Json(json!({ "code": 200, "message": "deleted" })))
}

async fn list_contacts_by_customer(
    Path(customer_key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let results: Vec<Value> = db.aql_bind_vars(
        r#"
        FOR c IN crm_contacts FILTER c.customer_key == @customer_key
            SORT c.is_primary DESC, c.created_at DESC
            RETURN MERGE(c, {customer_name: FIRST(
                FOR cust IN crm_customers FILTER cust._key == c.customer_key LIMIT 1 RETURN cust.name
            )})
        "#,
        [("customer_key", json!(customer_key))].into(),
    ).await.map_err(|e| {
        eprintln!("crm list contacts by customer error: {}", e);
        err_500()
    })?;

    Ok(Json(json!({ "code": 200, "data": results })))
}

async fn assign_contact(
    Json(payload): Json<AssignContactPayload>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col: Collection<_> = db.collection("crm_contacts").await.map_err(|_| err_500())?;
    let now = now_iso();

    col.update_document(&payload.key, json!({
        "owner_key": payload.owner_key,
        "source": "assignment",
        "assigned_by": payload.owner_key,
        "assigned_at": now.clone(),
        "updated_at": now,
    }), Default::default()).await.map_err(|_| err_404())?;

    Ok(Json(json!({ "code": 200, "message": "assigned" })))
}

async fn set_primary_contact(
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, Json<Value>)> {
    let db = get_db();
    let col: Collection<_> = db.collection("crm_contacts").await.map_err(|_| err_500())?;
    let now = now_iso();

    // 先查到此聯絡人的 customer_key
    let contact_result: Vec<Value> = db.aql_bind_vars(
        "FOR c IN crm_contacts FILTER c._key == @key LIMIT 1 RETURN c.customer_key",
        [("key", json!(&key))].into(),
    ).await.map_err(|_| err_500())?;

    let customer_key = contact_result.into_iter().next()
        .and_then(|v| v.as_str().map(String::from))
        .ok_or_else(|| err_400("contact not found or has no customer_key"))?;

    // 清除該機構所有聯絡人的 is_primary
    let _: Vec<Value> = db.aql_bind_vars(
        r#"
        FOR c IN crm_contacts FILTER c.customer_key == @customer_key
            UPDATE c WITH {is_primary: false, updated_at: @now} IN crm_contacts
        "#,
        Into::<std::collections::HashMap<&str, Value>>::into([
            ("customer_key", json!(customer_key)),
            ("now", json!(now.clone())),
        ]),
    ).await.map_err(|_| err_500())?;

    // 設指定的聯絡人為 primary
    col.update_document(&key, json!({
        "is_primary": true,
        "updated_at": now,
    }), Default::default()).await.map_err(|_| err_404())?;

    Ok(Json(json!({ "code": 200, "message": "set as primary contact" })))
}
