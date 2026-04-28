//! API Routes Module
//!
//! # Description
//! API 路由定義
//!
//! # Last Update: 2026-03-28 10:22:08
//! # Author: Daniel Chung
//! # Version: 1.1.0

use crate::auth::verify_jwt;
use crate::config::CONFIG;
use crate::middleware::auth::jwt_auth_middleware;
use crate::middleware::logging::logging_middleware;
use crate::db::{
    get_db, CreateAgentRequest, CreateRoleRequest, CreateToolRequest, CreateUserRequest, Function, FunctionRoleAuth, Role, RoleFunction, SystemParam, UpdateParamRequest, UpdateRoleRequest, User, Agent, Tool, ModelProvider, LLMModel,
};
use crate::models::*;
use axum::{
    extract::{Path, Query},
    http::{header::AUTHORIZATION, HeaderMap, Method, StatusCode},
    response::IntoResponse,
    routing::{get, post, put, patch, delete},
    Json, Router,
    middleware,
};
use tower_http::cors::{Any, CorsLayer};

pub mod sse;
pub mod ws;
pub mod ai;
pub mod chat;
pub mod billing;
pub mod services;
pub mod health;
pub mod da;
pub mod da_intents;
pub mod backup;
pub mod da_query;
pub mod da_tables;
pub mod da_expressions;
pub mod knowledge;
pub mod ontology;
pub mod themes;
pub mod web_search;
pub mod weather;
pub mod intent;
pub mod orch_intents;
pub mod intent_catalog;
pub mod leads;
pub mod action_trail;
pub mod aiq;
pub mod intent_guess;

use once_cell::sync::Lazy;
use reqwest::Client;

static HTTP_CLIENT: Lazy<Client> = Lazy::new(Client::new);
pub mod intent_logs;
pub mod platforms;
pub mod agent_chat;
pub mod ragic;

async fn sync_tool_intents(
    Path(key): Path<String>,
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("tools").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let intent_tags = payload.get("intent_tags")
        .and_then(|v| v.as_array())
        .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect::<Vec<_>>())
        .unwrap_or_default();
    
    let nl_examples = payload.get("nl_examples")
        .and_then(|v| v.as_array())
        .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect::<Vec<_>>())
        .unwrap_or_default();

    let existing: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR t IN tools FILTER t._key == @key LIMIT 1 RETURN t",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let _old = existing.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let update_data = serde_json::json!({
        "intent_tags": intent_tags,
        "nl_examples": nl_examples,
        "updated_at": chrono::Utc::now().to_rfc3339(),
    });

    col.update_document(&key, update_data, Default::default())
        .await
        .map_err(|e| {
            eprintln!("Sync tool intents error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(ApiResponse::success("已更新工具意圖".to_string())))
}

pub fn create_router() -> Router {
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods([Method::GET, Method::POST, Method::PUT, Method::DELETE, Method::PATCH])
        .allow_headers(Any);

    Router::new()
        .route("/api/v1/auth/login", post(login))
        .route("/api/v1/auth/logout", post(logout))
        .route("/api/v1/auth/me", get(me))
        .route("/api/v1/auth/functions", get(get_auth_functions))
        .route("/api/v1/users", get(list_users).post(create_user))
        .route("/api/v1/users/{key}", get(get_user).put(update_user).delete(delete_user))
        .route("/api/v1/users/{key}/reset-password", post(reset_password))
        .route("/api/v1/roles", get(list_roles).post(create_role))
        .route("/api/v1/roles/{key}", get(get_role).put(update_role).delete(delete_role))
        .route("/api/v1/system-params", get(list_params))
        .route("/api/v1/system-params/{key}", get(get_param).put(update_param))
        .route("/api/v1/functions", get(list_functions).post(create_function))
        .route("/api/v1/functions/{key}", get(get_function).put(update_function).delete(delete_function))
        .route("/api/v1/functions/{key}/roles", get(get_function_roles).put(set_function_roles))
        .route("/api/v1/agents", get(list_agents).post(create_agent))
        .route("/api/v1/agents/{key}", get(get_agent).put(update_agent).delete(delete_agent))
        .route("/api/v1/agents/{key}/intents", get(list_agent_intents).post(create_agent_intent))
        .route("/api/v1/agents/{key}/intents/{intent_key}", put(update_agent_intent).delete(delete_agent_intent))
        .route("/api/v1/agents/{key}/intents/{intent_key}/sync", post(sync_agent_intents_to_qdrant))
        .route("/api/v1/agents/{key}/demands", get(list_agent_demands).post(create_agent_demand))
        .route("/api/v1/agents/{key}/demands/{demand_key}", get(get_agent_demand).put(update_agent_demand).delete(delete_agent_demand))
        .route("/api/v1/agents/{key}/demands/{demand_key}/suggest-intents", post(suggest_intents_for_demand))
        .route("/api/v1/agents/{key}/demands/{demand_key}/status", patch(update_demand_status))
        .route("/api/v1/demands/estimate-hours", post(estimate_demand_hours))
        .route("/api/v1/demands/review", post(review_demand))
        .route("/api/v1/agent-requirements", get(list_all_agent_requirements).post(create_agent_requirement))
        .route("/api/v1/agent-requirements/{req_key}", get(get_agent_requirement))
        .route("/api/v1/agent-requirements/{req_key}/accept", patch(accept_agent_requirement))
        .route("/api/v1/agent-requirements/{req_key}/analyze", post(analyze_agent_requirement))
        .route("/api/v1/agent-requirements/{req_key}/start-dev", post(start_dev_workspace))
        .route("/api/v1/agent-requirements/{req_key}/spec.md", get(get_agent_requirement_spec_md))
        .route("/api/v1/agent-requirements/by-req-no/{req_no}", get(get_agent_requirement_by_no))
        .route("/api/v1/tools", get(list_tools).post(create_tool))
        .route("/api/v1/tools/{key}", get(get_tool).put(update_tool).delete(delete_tool))
        .route("/api/v1/tools/{key}/intents", post(sync_tool_intents))
        .route("/api/v1/agents/{key}/favorite", patch(toggle_agent_favorite))
        .merge(agent_chat::create_agent_chat_router())
        .route("/api/v1/model-providers", get(list_model_providers).post(create_model_provider))
        .route("/api/v1/model-providers/{key}", get(get_model_provider).put(update_model_provider).delete(delete_model_provider))
        .route("/api/v1/model-providers/{key}/sync", post(sync_model_provider))
        .route("/api/v1/theme-templates", get(themes::list_theme_templates))
        .route("/api/v1/theme-templates", 
            post(themes::create_theme_template)
                .route_layer(middleware::from_fn(jwt_auth_middleware))
        )
        .route("/api/v1/theme-templates/{key}", get(themes::get_theme_template))
        .route("/api/v1/theme-templates/{key}", 
            put(themes::update_theme_template)
                .delete(themes::delete_theme_template)
                .route_layer(middleware::from_fn(jwt_auth_middleware))
        )
        .route("/api/v1/theme-templates/{key}/activate", 
            put(themes::activate_theme_template)
                .route_layer(middleware::from_fn(jwt_auth_middleware))
        )
        .route("/api/v1/knowledge/roots", get(knowledge::list_roots).post(knowledge::create_root))
        .route("/api/v1/knowledge/roots/{key}", get(knowledge::get_root).put(knowledge::update_root).delete(knowledge::delete_root))
        .route("/api/v1/knowledge/roots/{key}/copy", post(knowledge::copy_root))
        .route("/api/v1/knowledge/roots/{key}/favorite", patch(knowledge::toggle_favorite))
        .route("/api/v1/knowledge/roots/{root_id}/files", get(knowledge::list_files))
        .route("/api/v1/knowledge/files/{key}", get(knowledge::get_file).delete(knowledge::delete_file))
        .route("/api/v1/knowledge/files/{key}/download", get(knowledge::download_file_proxy))
        .route("/api/v1/knowledge/files/{key}/preview", get(knowledge::preview_file))
.route("/api/v1/knowledge/files/{key}/vectors", get(knowledge::get_vectors))
.route("/api/v1/knowledge/files/{key}/graph", get(knowledge::get_graph))
.route("/api/v1/knowledge/files/{key}/similar", get(knowledge::get_similar_chunks))
.route("/api/v1/knowledge/files/{key}/regenerate-vector", post(knowledge::regenerate_vector))
.route("/api/v1/knowledge/files/{key}/regenerate-graph", post(knowledge::regenerate_graph))
        .route("/api/v1/jobs", get(knowledge::list_jobs))
        .route("/api/v1/jobs/clear", delete(knowledge::clear_jobs))
        .route("/api/v1/jobs/stuck", get(knowledge::list_jobs_stuck))
        .route("/api/v1/jobs/{key}/abort", post(knowledge::abort_job))
        .route("/api/v1/jobs/{key}/delete", post(knowledge::delete_job))
        .route("/api/v1/jobs/{key}/retry", post(knowledge::retry_job))
        .route("/api/v1/jobs/{key}/logs", get(knowledge::job_logs))
        .merge(knowledge::create_upload_router())
        .route("/api/v1/ontologies", get(ontology::list_ontologies).post(ontology::create_ontology))
        .route("/api/v1/ontologies/import", post(ontology::import_ontology))
        .route("/api/v1/ontologies/{key}", get(ontology::get_ontology).put(ontology::update_ontology).delete(ontology::delete_ontology))
        .merge(sse::create_sse_router())
        .merge(ws::create_ws_router())
        .merge(ai::create_ai_router())
        .merge(chat::create_chat_router())
        .merge(billing::create_billing_router())
        .merge(services::create_services_router())
        .merge(health::create_health_router())
        .merge(da::create_da_router())
        .merge(da_intents::create_da_intents_router())
        .merge(da_tables::create_da_tables_router())
        .merge(da_expressions::create_da_expressions_router())
        .merge(backup::create_backup_router())
        .merge(platforms::line::create_line_router())
        .merge(da_query::create_da_query_router())
        .merge(web_search::create_web_search_router())
        .merge(weather::create_weather_router())
        .merge(orch_intents::create_orch_intents_router())
        .merge(intent_catalog::create_intent_catalog_router())
        .merge(leads::create_leads_router())
        .merge(action_trail::create_action_trail_router())
        .merge(intent_guess::create_intent_guess_router())
        .merge(intent_logs::create_intent_logs_router())
        .merge(aiq::create_aiq_router())
        .merge(ragic::create_ragic_router())
        .route("/api/v1/events", post(post_events))
        .layer(middleware::from_fn(logging_middleware))
        .layer(cors)
}

async fn login(Json(payload): Json<LoginRequest>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let raw_users: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR u IN users FILTER u.username == @username LIMIT 1 RETURN u",
            [("username", serde_json::json!(payload.username))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let raw_user = raw_users.into_iter().next().ok_or(StatusCode::UNAUTHORIZED)?;

    let password_hash = raw_user.get("password_hash")
        .and_then(|v| v.as_str())
        .ok_or(StatusCode::UNAUTHORIZED)?;

    if !bcrypt::verify(&payload.password, password_hash).unwrap_or(false) {
        return Err(StatusCode::UNAUTHORIZED);
    }

    let user_key = raw_user.get("_key")
        .and_then(|v| v.as_str())
        .map(String::from)
        .unwrap_or_else(|| payload.username.clone());

    let role_keys: Vec<String> = if let Some(keys) = raw_user.get("role_keys").and_then(|v| v.as_array()) {
        keys.iter().filter_map(|v| v.as_str().map(String::from)).collect()
    } else if let Some(key) = raw_user.get("role_key").and_then(|v| v.as_str()) {
        vec![key.to_string()]
    } else {
        vec![]
    };

    let mut role_names: Vec<String> = Vec::new();
    for role_key in &role_keys {
        let mut roles: Vec<Role> = db
            .aql_bind_vars(
                "FOR r IN roles FILTER r._key == @key LIMIT 1 RETURN r",
                [("key", serde_json::json!(role_key))].into(),
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        if let Some(role) = roles.pop() {
            role_names.push(role.name);
        }
    }

    let primary_role = role_keys.first().cloned().unwrap_or_default();
    let token = crate::auth::create_jwt(&user_key, &payload.username, &primary_role)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let username = raw_user.get("username").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let name = raw_user.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let tier = raw_user.get("tier").and_then(|v| v.as_str()).unwrap_or("general").to_string();

    Ok(Json(ApiResponse::success(LoginResponse {
        token,
        user: UserInfo {
            _key: user_key,
            username,
            name,
            role_keys,
            role_names,
            tier,
        },
    })))
}

async fn logout() -> Result<impl IntoResponse, StatusCode> {
    Ok(Json(ApiResponse::success("Logged out".to_string())))
}

#[derive(Debug, serde::Deserialize)]
struct AnalyticsEvent {
    event: EventData,
    timestamp: u64,
    session_id: String,
    user_key: Option<String>,
}

#[derive(Debug, serde::Deserialize, serde::Serialize)]
#[serde(untagged)]
enum EventData {
    PageView {
        page: String,
        title: Option<String>,
        referrer: Option<String>,
    },
    Track {
        category: String,
        action: String,
        label: Option<String>,
        value: Option<f64>,
        metadata: Option<serde_json::Value>,
    },
}

#[derive(Debug, serde::Serialize)]
struct PostEventsResponse {
    received: usize,
}

async fn post_events(Json(payload): Json<serde_json::Value>) -> Result<impl IntoResponse, StatusCode> {
    let events = payload
        .get("events")
        .and_then(|v| v.as_array())
        .map(|arr| arr.iter().filter_map(|v| serde_json::from_value(v.clone()).ok()).collect::<Vec<AnalyticsEvent>>())
        .unwrap_or_default();

    let count = events.len();

    for event in &events {
        let log_entry = serde_json::json!({
            "type": "analytics",
            "timestamp": event.timestamp,
            "session_id": event.session_id,
            "user_key": event.user_key,
            "event": event.event,
        });
        if let Ok(json) = serde_json::to_string(&log_entry) {
            println!("{}", json);
        }
    }

    Ok(Json(ApiResponse::success(PostEventsResponse { received: count })))
}

async fn me(headers: HeaderMap) -> Result<impl IntoResponse, StatusCode> {
    let token = headers
        .get(AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;

    let claims = verify_jwt(token).map_err(|_| StatusCode::UNAUTHORIZED)?;
    let db = get_db();

    let raw_users: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR u IN users FILTER u.username == @username LIMIT 1 RETURN u",
            [("username", serde_json::json!(claims.claims.username))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let raw_user = raw_users.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let user_key = raw_user.get("_key")
        .and_then(|v| v.as_str())
        .map(String::from)
        .unwrap_or_else(|| claims.claims.username.clone());

    let role_keys: Vec<String> = if let Some(keys) = raw_user.get("role_keys").and_then(|v| v.as_array()) {
        keys.iter().filter_map(|v| v.as_str().map(String::from)).collect()
    } else if let Some(key) = raw_user.get("role_key").and_then(|v| v.as_str()) {
        vec![key.to_string()]
    } else {
        vec![]
    };

    let mut role_names: Vec<String> = Vec::new();
    for role_key in &role_keys {
        let mut roles: Vec<Role> = db
            .aql_bind_vars(
                "FOR r IN roles FILTER r._key == @key LIMIT 1 RETURN r",
                [("key", serde_json::json!(role_key))].into(),
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        if let Some(role) = roles.pop() {
            role_names.push(role.name);
        }
    }

    let username = raw_user.get("username").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let name = raw_user.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let tier = raw_user.get("tier").and_then(|v| v.as_str()).unwrap_or("general").to_string();

    Ok(Json(ApiResponse::success(UserInfo {
        _key: user_key,
        username,
        name,
        role_keys,
        role_names,
        tier,
    })))
}

async fn get_auth_functions(headers: HeaderMap) -> Result<impl IntoResponse, StatusCode> {
    let token = headers
        .get(AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;

    let claims = verify_jwt(token).map_err(|_| StatusCode::UNAUTHORIZED)?;
    let db = get_db();

    let raw_users: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR u IN users FILTER u.username == @username LIMIT 1 RETURN u",
            [("username", serde_json::json!(claims.claims.username))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let raw_user = raw_users.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let role_keys: Vec<String> = if let Some(keys) = raw_user.get("role_keys").and_then(|v| v.as_array()) {
        keys.iter().filter_map(|v| v.as_str().map(String::from)).collect()
    } else if let Some(key) = raw_user.get("role_key").and_then(|v| v.as_str()) {
        vec![key.to_string()]
    } else {
        vec![]
    };

    if role_keys.is_empty() {
        return Ok(Json(ApiResponse::success(Vec::<Function>::new())));
    }

    let role_filters: Vec<String> = role_keys.iter().map(|k| format!("rf.role_key == '{}'", k)).collect();
    let role_filter = role_filters.join(" || ");

    let query = format!(
        "FOR rf IN role_functions FILTER {} FOR f IN functions FILTER f._key == rf.function_key && f.status == 'enabled' SORT f.sort_order ASC RETURN f",
        role_filter
    );

    let raw_functions: Vec<serde_json::Value> = db
        .aql_str(&query)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let functions: Vec<Function> = raw_functions
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();

    Ok(Json(ApiResponse::success(functions)))
}

async fn list_users() -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let raw_users: Vec<serde_json::Value> = db
        .aql_str("FOR u IN users RETURN u")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    
    let users: Vec<User> = raw_users.into_iter().map(|u| {
        let role_keys = if let Some(keys) = u.get("role_keys").and_then(|v| v.as_array()) {
            keys.iter().filter_map(|v| v.as_str().map(String::from)).collect()
        } else if let Some(key) = u.get("role_key").and_then(|v| v.as_str()) {
            vec![key.to_string()]
        } else {
            vec![]
        };
        
        User {
            _key: u.get("_key").and_then(|v| v.as_str()).map(String::from),
            username: u.get("username").and_then(|v| v.as_str()).unwrap_or("").to_string(),
            password_hash: u.get("password_hash").and_then(|v| v.as_str()).unwrap_or("").to_string(),
            name: u.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string(),
            role_keys,
            status: u.get("status").and_then(|v| v.as_str()).unwrap_or("").to_string(),
            tier: u.get("tier").and_then(|v| v.as_str()).map(String::from),
            created_at: u.get("created_at").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        }
    }).collect();
    
    Ok(Json(ApiResponse::success(users)))
}

async fn create_user(Json(payload): Json<CreateUserRequest>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let existing: Vec<User> = db
        .aql_bind_vars(
            "FOR u IN users FILTER u.username == @username LIMIT 1 RETURN u",
            [("username", serde_json::json!(payload.username))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if !existing.is_empty() {
        return Err(StatusCode::CONFLICT);
    }

    let password_hash = bcrypt::hash(&payload.password_hash, 10)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let key = payload.username.clone();
    let user = User {
        _key: Some(key.clone()),
        username: payload.username,
        password_hash,
        name: payload.name,
        role_keys: payload.role_keys,
        status: payload.status,
        tier: Some(payload.tier),
        created_at: chrono::Utc::now().to_rfc3339(),
    };

    let col = db.collection("users").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(user.clone(), Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(user)))
}

async fn get_user(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let raw_users: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR u IN users FILTER u._key == @key LIMIT 1 RETURN u",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    
    if raw_users.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }
    
    let u = &raw_users[0];
    let role_keys = if let Some(keys) = u.get("role_keys").and_then(|v| v.as_array()) {
        keys.iter().filter_map(|v| v.as_str().map(String::from)).collect()
    } else if let Some(key) = u.get("role_key").and_then(|v| v.as_str()) {
        vec![key.to_string()]
    } else {
        vec![]
    };
    
    let user = User {
        _key: u.get("_key").and_then(|v| v.as_str()).map(String::from),
        username: u.get("username").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        password_hash: u.get("password_hash").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        name: u.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        role_keys,
        status: u.get("status").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        tier: u.get("tier").and_then(|v| v.as_str()).map(String::from),
        created_at: u.get("created_at").and_then(|v| v.as_str()).unwrap_or("").to_string(),
    };
    
    Ok(Json(ApiResponse::success(user)))
}

async fn update_user(Path(key): Path<String>, Json(payload): Json<UpdateUserRequest>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("users").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut patch = serde_json::Map::new();
    if let Some(name) = payload.name {
        patch.insert("name".to_string(), serde_json::json!(name));
    }
    if let Some(role_keys) = payload.role_keys {
        patch.insert("role_keys".to_string(), serde_json::json!(role_keys));
    }
    if let Some(status) = payload.status {
        patch.insert("status".to_string(), serde_json::json!(status));
    }
    if let Some(tier) = payload.tier {
        patch.insert("tier".to_string(), serde_json::json!(tier));
    }
    if let Some(password_hash) = payload.password_hash {
        let hashed = bcrypt::hash(&password_hash, 10).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        patch.insert("password_hash".to_string(), serde_json::json!(hashed));
    }

    if patch.is_empty() {
        return Err(StatusCode::BAD_REQUEST);
    }

    col.update_document(&key, patch, Default::default())
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;

    let raw_users: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR u IN users FILTER u._key == @key LIMIT 1 RETURN u",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if raw_users.is_empty() {
        return Err(StatusCode::NOT_FOUND);
    }
    
    let u = &raw_users[0];
    let role_keys = if let Some(keys) = u.get("role_keys").and_then(|v| v.as_array()) {
        keys.iter().filter_map(|v| v.as_str().map(String::from)).collect()
    } else if let Some(key) = u.get("role_key").and_then(|v| v.as_str()) {
        vec![key.to_string()]
    } else {
        vec![]
    };
    
    let user = User {
        _key: u.get("_key").and_then(|v| v.as_str()).map(String::from),
        username: u.get("username").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        password_hash: u.get("password_hash").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        name: u.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        role_keys,
        status: u.get("status").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        tier: u.get("tier").and_then(|v| v.as_str()).map(String::from),
        created_at: u.get("created_at").and_then(|v| v.as_str()).unwrap_or("").to_string(),
    };
    
    Ok(Json(ApiResponse::success(user)))
}

async fn delete_user(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("users").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<serde_json::Value>(&key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success("User deleted".to_string())))
}

async fn reset_password(Path(key): Path<String>, Json(payload): Json<serde_json::Value>) -> Result<impl IntoResponse, StatusCode> {
    let new_password = payload
        .get("password")
        .and_then(|v| v.as_str())
        .ok_or(StatusCode::BAD_REQUEST)?;

    let hash = bcrypt::hash(new_password, 10).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let db = get_db();
    let col = db.collection("users").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    col.update_document(&key, serde_json::json!({ "password_hash": hash }), Default::default())
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;

    Ok(Json(ApiResponse::success("Password reset successfully".to_string())))
}

async fn list_roles() -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let roles: Vec<Role> = db
        .aql_str("FOR r IN roles RETURN r")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(roles)))
}

async fn create_role(Json(payload): Json<CreateRoleRequest>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let key = uuid::Uuid::new_v4().to_string();

    let role = Role {
        _key: Some(key),
        name: payload.name,
        description: payload.description.unwrap_or_default(),
        created_at: chrono::Utc::now().to_rfc3339(),
    };

    let col = db.collection("roles").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(role.clone(), Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(role)))
}

async fn get_role(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let mut roles: Vec<Role> = db
        .aql_bind_vars(
            "FOR r IN roles FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let role = roles.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(role)))
}

async fn update_role(Path(key): Path<String>, Json(payload): Json<UpdateRoleRequest>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("roles").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut patch = serde_json::Map::new();
    if let Some(name) = payload.name {
        patch.insert("name".to_string(), serde_json::json!(name));
    }
    if let Some(description) = payload.description {
        patch.insert("description".to_string(), serde_json::json!(description));
    }

    col.update_document(
        &key,
        serde_json::Value::Object(patch),
        Default::default(),
    )
    .await
    .map_err(|_| StatusCode::NOT_FOUND)?;

    let mut roles: Vec<Role> = db
        .aql_bind_vars(
            "FOR r IN roles FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let role = roles.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(role)))
}

async fn delete_role(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("roles").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<serde_json::Value>(&key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success("Role deleted".to_string())))
}

async fn list_params() -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let raw: Vec<serde_json::Value> = db
        .aql_str("FOR p IN system_params RETURN p")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let params: Vec<SystemParam> = raw
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();
    Ok(Json(ApiResponse::success(params)))
}

async fn get_param(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let mut params: Vec<SystemParam> = db
        .aql_bind_vars(
            "FOR p IN system_params FILTER p._key == @key LIMIT 1 RETURN p",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let param = params.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(param)))
}

async fn update_param(Path(key): Path<String>, Json(payload): Json<UpdateParamRequest>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("system_params").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let new_value = payload.param_value.or(payload.value).ok_or(StatusCode::BAD_REQUEST)?;
    let now = chrono::Utc::now().to_rfc3339();

    let existing: Vec<SystemParam> = db
        .aql_bind_vars(
            "FOR p IN system_params FILTER p._key == @key LIMIT 1 RETURN p",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if existing.is_empty() {
        col.create_document(
            SystemParam {
                _key: Some(key.clone()),
                param_key: key.clone(),
                param_value: new_value.clone(),
                param_type: "string".to_string(),
                require_restart: false,
                category: "data_agent".to_string(),
                updated_at: now,
            },
            Default::default(),
        )
        .await
        .map_err(|e| {
            tracing::error!("Failed to create param {}: {}", key, e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    } else {
        col.update_document(
            &key,
            serde_json::json!({
                "param_value": new_value,
                "updated_at": now,
            }),
            Default::default(),
        )
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;
    }

    let mut params: Vec<SystemParam> = db
        .aql_bind_vars(
            "FOR p IN system_params FILTER p._key == @key LIMIT 1 RETURN p",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let param = params.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(param)))
}

async fn list_functions() -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let result: Result<Vec<serde_json::Value>, _> = db
        .aql_str("FOR f IN functions RETURN f")
        .await;
    
    match result {
        Ok(raw_functions) => {
            let functions: Vec<Function> = raw_functions
                .into_iter()
                .filter_map(|v| serde_json::from_value(v).ok())
                .collect();
            Ok(Json(ApiResponse::success(functions)))
        }
        Err(e) => {
            eprintln!("list_functions query error: {:?}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

async fn create_function(Json(payload): Json<serde_json::Value>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    
    let key = payload.get("_key")
        .and_then(|v| v.as_str())
        .or_else(|| payload.get("code").and_then(|v| v.as_str()))
        .map(|s| s.to_string())
        .unwrap_or_else(|| uuid::Uuid::new_v4().to_string());

    let existing_raw: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR f IN functions FILTER f._key == @key LIMIT 1 RETURN f",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let existing: Vec<Function> = existing_raw
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();

    if !existing.is_empty() {
        return Err(StatusCode::CONFLICT);
    }

    let function = Function {
        _key: Some(key.clone()),
        code: key,
        name: payload.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string(),
        description: payload.get("description").and_then(|v| v.as_str()).map(String::from),
        function_type: payload.get("function_type").and_then(|v| v.as_str()).unwrap_or("sub_function").to_string(),
        parent_key: payload.get("parent_key").and_then(|v| v.as_str()).map(|s| s.to_string()),
        path: payload.get("path").and_then(|v| v.as_str()).map(|s| s.to_string()),
        icon: payload.get("icon").and_then(|v| v.as_str()).map(|s| s.to_string()),
        sort_order: payload.get("sort_order").and_then(|v| v.as_i64()).map(|v| v as i32).unwrap_or(1),
        status: payload.get("status").and_then(|v| v.as_str()).unwrap_or("enabled").to_string(),
        created_at: chrono::Utc::now().to_rfc3339(),
    };

    let col = db.collection("functions").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(function.clone(), Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(function)))
}

async fn get_function(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let raw_functions: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR f IN functions FILTER f._key == @key LIMIT 1 RETURN f",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let functions: Vec<Function> = raw_functions
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();

    let function = functions.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(function)))
}

async fn update_function(Path(key): Path<String>, Json(payload): Json<serde_json::Value>) -> Result<impl IntoResponse, StatusCode> {
    if payload.is_null() || payload.as_object().map(|o| o.is_empty()).unwrap_or(true) {
        return Err(StatusCode::BAD_REQUEST);
    }
    
    let db = get_db();
    let col = db.collection("functions").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    col.update_document(
        &key,
        payload,
        Default::default(),
    )
    .await
    .map_err(|e| {
        eprintln!("Update error: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let raw_functions: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR f IN functions FILTER f._key == @key LIMIT 1 RETURN f",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let functions: Vec<Function> = raw_functions
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();

    let function = functions.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(function)))
}

async fn delete_function(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("functions").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<serde_json::Value>(&key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success("Function deleted".to_string())))
}

async fn get_function_roles(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let role_keys: Vec<String> = db
        .aql_bind_vars(
            "FOR rf IN role_functions FILTER rf.function_key == @key RETURN rf.role_key",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let raw_funcs: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR f IN functions FILTER f._key == @key LIMIT 1 RETURN f",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let functions: Vec<Function> = raw_funcs
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();

    let inherited_role_keys = if let Some(func) = functions.into_iter().next() {
        if let Some(parent_key) = func.parent_key {
            db.aql_bind_vars(
                "FOR rf IN role_functions FILTER rf.function_key == @key RETURN rf.role_key",
                [("key", serde_json::json!(parent_key))].into(),
            )
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        } else {
            vec![]
        }
    } else {
        vec![]
    };

    Ok(Json(ApiResponse::success(FunctionRoleAuth {
        function_key: key,
        role_keys,
        inherited_role_keys,
    })))
}

async fn set_function_roles(Path(key): Path<String>, Json(payload): Json<FunctionRoleAuth>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("role_functions").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let _: Vec<serde_json::Value> = db.aql_bind_vars(
        "FOR rf IN role_functions FILTER rf.function_key == @key REMOVE rf IN role_functions",
        [("key", serde_json::json!(key.clone()))].into(),
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    for role_key in &payload.role_keys {
        let rf_key = format!("{}_{}", role_key, key);
        col.create_document(
            RoleFunction {
                _key: Some(rf_key),
                role_key: role_key.clone(),
                function_key: key.clone(),
                created_at: chrono::Utc::now().to_rfc3339(),
            },
            Default::default(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    }

    let raw_funcs: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR f IN functions FILTER f._key == @key LIMIT 1 RETURN f",
            [("key", serde_json::json!(key.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let funcs: Vec<Function> = raw_funcs
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();

    if let Some(func) = funcs.into_iter().next() {
        if func.function_type == "group" {
            let raw_subs: Vec<serde_json::Value> = db
                .aql_bind_vars(
                    "FOR f IN functions FILTER f.parent_key == @pk && f.function_type != 'group' SORT f.sort_order ASC RETURN f",
                    [("pk", serde_json::json!(key.clone()))].into(),
                )
                .await
                .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
            let subs: Vec<Function> = raw_subs
                .into_iter()
                .filter_map(|v| serde_json::from_value(v).ok())
                .collect();

            for sub in subs {
                let sub_key = sub._key.clone().unwrap_or_default();
                let _: Vec<serde_json::Value> = db.aql_bind_vars(
                    "FOR rf IN role_functions FILTER rf.function_key == @fk REMOVE rf IN role_functions",
                    [("fk", serde_json::json!(sub_key.clone()))].into(),
                )
                .await
                .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

                for role_key in &payload.role_keys {
                    let rf_key = format!("{}_{}", role_key, sub_key);
                    col.create_document(
                        RoleFunction {
                            _key: Some(rf_key),
                            role_key: role_key.clone(),
                            function_key: sub_key.clone(),
                            created_at: chrono::Utc::now().to_rfc3339(),
                        },
                        Default::default(),
                    )
                    .await
                    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
                }
            }
        }
    }

    Ok(Json(ApiResponse::success("Roles updated".to_string())))
}

// Agent CRUD handlers

async fn list_agents(headers: HeaderMap, Query(params): Query<std::collections::HashMap<String, String>>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let agent_type = params.get("agent_type").map(|s| s.as_str());

    let (user_key, user_roles) = if let Some(token) = headers.get(AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
    {
        if let Ok(claims) = verify_jwt(token) {
            let raw_users: Vec<serde_json::Value> = db
                .aql_bind_vars(
                    "FOR u IN users FILTER u.username == @username LIMIT 1 RETURN u",
                    [("username", serde_json::json!(claims.claims.username))].into(),
                )
                .await
                .unwrap_or_default();
            let raw_user = raw_users.into_iter().next();
            let role_keys: Vec<String> = raw_user.as_ref()
                .and_then(|u| u.get("role_keys"))
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect::<Vec<_>>())
                .unwrap_or_default();
            let uk = raw_user.as_ref()
                .and_then(|u| u.get("_key"))
                .and_then(|v| v.as_str())
                .map(String::from)
                .unwrap_or_default();
            (Some(uk), Some(role_keys))
        } else {
            (None, None)
        }
    } else {
        (None, None)
    };

    let agent_filter = if let Some(t) = agent_type {
        format!(" && a.agent_type == '{}'", t)
    } else {
        String::new()
    };
    let query = format!(
        "FOR a IN agents FILTER (a.visibility == null || a.visibility == 'public' || a.visibility == 'private' || a.visibility == 'role'){} SORT a.created_at DESC RETURN a",
        agent_filter
    );
    let all_agents: Vec<Agent> = db.aql_str(&query).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let is_admin = user_roles.as_ref().map(|r| r.contains(&"admin".to_string())).unwrap_or(false);

    let filtered: Vec<Agent> = match (&user_key, &user_roles) {
        (Some(uk), Some(roles)) => all_agents
            .into_iter()
            .filter(|a| {
                if is_admin {
                    return true;
                }
                match a.visibility.as_deref().unwrap_or("public") {
                    "public" => true,
                    "private" => a.created_by.as_ref() == Some(uk),
                    "role" => {
                    let agent_roles = a.visibility_roles.as_deref().unwrap_or(&[]);
                        roles.iter().any(|r| agent_roles.contains(r))
                    }
                    _ => false,
                }
            })
            .collect(),
        _ => all_agents
            .into_iter()
            .filter(|a| matches!(a.visibility.as_deref().unwrap_or("public"), "public"))
            .collect(),
    };

    Ok(Json(ApiResponse::success(filtered)))
}

async fn create_agent(Json(payload): Json<CreateAgentRequest>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    
    let key = uuid::Uuid::new_v4().to_string();
    let now = chrono::Utc::now().to_rfc3339();

    let agent = Agent {
        _key: Some(key.clone()),
        name: payload.name,
        description: payload.description,
        icon: payload.icon,
        status: payload.status.unwrap_or_else(|| "online".to_string()),
        usage_count: 0,
        group_key: payload.group_key.unwrap_or_else(|| "productivity".to_string()),
        agent_type: payload.agent_type,
        source: payload.source.or_else(|| Some("local".to_string())),
        endpoint_url: payload.endpoint_url,
        api_key: payload.api_key,
        auth_type: payload.auth_type.or_else(|| Some("none".to_string())),
        llm_model: payload.llm_model,
        temperature: payload.temperature,
        max_tokens: payload.max_tokens,
        system_prompt: payload.system_prompt,
        knowledge_bases: payload.knowledge_bases,
        data_sources: payload.data_sources,
        tools: payload.tools,
        opening_lines: payload.opening_lines,
        capabilities: payload.capabilities,
        is_favorite: Some(false),
        visibility: payload.visibility.or_else(|| Some("private".to_string())),
        visibility_roles: payload.visibility_roles,
        created_by: payload.created_by,
        updated_by: None,
        created_at: now.clone(),
        updated_at: now,
    };

    let col = db.collection("agents").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(agent.clone(), Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(agent)))
}

async fn get_agent(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let mut agents: Vec<Agent> = db
        .aql_bind_vars(
            "FOR a IN agents FILTER a._key == @key LIMIT 1 RETURN a",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let agent = agents.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(agent)))
}

async fn update_agent(Path(key): Path<String>, Json(payload): Json<serde_json::Value>) -> Result<impl IntoResponse, StatusCode> {
    if payload.is_null() || payload.as_object().map(|o| o.is_empty()).unwrap_or(true) {
        return Err(StatusCode::BAD_REQUEST);
    }
    
    let db = get_db();
    let col = db.collection("agents").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    eprintln!("update_agent: key={} payload={}", key, payload);
    let existing: Vec<serde_json::Value> = db
        .aql_bind_vars("FOR a IN agents FILTER a._key == @key LIMIT 1 RETURN a", [("key", serde_json::json!(key))].into())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let old = existing.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let mut update_data = payload.clone();
    if let Some(obj) = update_data.as_object_mut() {
        if !obj.contains_key("created_by") {
            if let Some(cb) = old.get("created_by") {
                obj.insert("created_by".to_string(), cb.clone());
            }
        }
        obj.insert("updated_at".to_string(), serde_json::json!(chrono::Utc::now().to_rfc3339()));
    }

    col.update_document(&key, update_data, Default::default())
        .await
        .map_err(|e| {
            eprintln!("Update agent error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let mut agents: Vec<Agent> = db
        .aql_bind_vars(
            "FOR a IN agents FILTER a._key == @key LIMIT 1 RETURN a",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let agent = agents.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(agent)))
}

async fn delete_agent(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("agents").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<serde_json::Value>(&key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success("Agent deleted".to_string())))
}

// Agent Intent CRUD

async fn list_agent_intents(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let intents: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR i IN intent_catalog FILTER i.agent_key == @key SORT i.priority DESC RETURN i",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(intents)))
}

#[derive(serde::Deserialize)]
struct CreateIntentRequest {
    name: String,
    description: Option<String>,
    #[serde(default)]
    nl_examples: Vec<String>,
    #[serde(default)]
    nl_patterns: Vec<String>,
    #[serde(default)]
    priority: i32,
    #[serde(default)]
    status: String,
    #[serde(default)]
    action: String,
}

async fn create_agent_intent(
    Path(key): Path<String>,
    Json(payload): Json<CreateIntentRequest>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("intent_catalog").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let intent_key = uuid::Uuid::new_v4().to_string();
    let now = chrono::Utc::now().to_rfc3339();

    let doc = serde_json::json!({
        "_key": intent_key.clone(),
        "agent_key": key,
        "name": payload.name,
        "description": payload.description.unwrap_or_default(),
        "nl_examples": payload.nl_examples,
        "nl_patterns": payload.nl_patterns,
        "priority": payload.priority,
        "status": if payload.status.is_empty() { "enabled" } else { &payload.status },
        "action": payload.action,
        "created_at": now,
        "updated_at": now,
    });

    col.create_document(doc, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let created: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR i IN intent_catalog FILTER i._key == @key LIMIT 1 RETURN i",
            [("key", serde_json::json!(intent_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let intent = created.into_iter().next().ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(intent)))
}

async fn update_agent_intent(
    Path((_key, intent_key)): Path<(String, String)>,
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, StatusCode> {
    if payload.is_null() || payload.as_object().map(|o| o.is_empty()).unwrap_or(true) {
        return Err(StatusCode::BAD_REQUEST);
    }

    let db = get_db();
    let col = db.collection("intent_catalog").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut update_data = payload.clone();
    if let Some(obj) = update_data.as_object_mut() {
        obj.insert("updated_at".to_string(), serde_json::json!(chrono::Utc::now().to_rfc3339()));
    }

    col.update_document(&intent_key, update_data, Default::default())
        .await
        .map_err(|e| {
            eprintln!("Update agent intent error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let updated: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR i IN intent_catalog FILTER i._key == @key LIMIT 1 RETURN i",
            [("key", serde_json::json!(intent_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let intent = updated.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(intent)))
}

async fn delete_agent_intent(Path((_key, intent_key)): Path<(String, String)>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("intent_catalog").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<serde_json::Value>(&intent_key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success("Intent deleted".to_string())))
}

async fn sync_agent_intents_to_qdrant(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    // Determine agent_scope from agent_key
    let agents: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR a IN agents FILTER a._key == @key LIMIT 1 RETURN a",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let agent = agents.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    let agent_type = agent.get("agent_type")
        .and_then(|v| v.as_str())
        .unwrap_or("ragic_helper");

    let scope = match agent_type {
        "data" => "data_agent",
        "bpa" => "orchestrator",
        _ => "ragic_helper",
    };

    let client = reqwest::Client::new();
    let sync_url = format!("http://localhost:8011/da/intent-rag/{}/embed-sync", scope);

    let resp = client.post(&sync_url).send().await.map_err(|e| {
        eprintln!("Sync to Qdrant error: {}", e);
        StatusCode::BAD_GATEWAY
    })?;

    if resp.status().is_success() {
        Ok(Json(ApiResponse::success("Intents synced to Qdrant".to_string())))
    } else {
        Err(StatusCode::BAD_GATEWAY)
    }
}

// ─── Agent Demand CRUD ────────────────────────────────────────────────────────

async fn list_agent_demands(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let demands: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR d IN agent_demands FILTER d.agent_key == @key SORT d.version DESC RETURN d",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(demands)))
}

#[derive(serde::Deserialize)]
struct CreateDemandRequest {
    goal: String,
    expected_effect: String,
    problem_description: String,
    #[serde(default)]
    target_users: Option<String>,
    #[serde(default)]
    scope: Option<String>,
    #[serde(default)]
    excluded_scope: Option<String>,
    #[serde(default)]
    conversation_style: Option<String>,
    #[serde(default)]
    conversation_examples: Vec<serde_json::Value>,
    #[serde(default)]
    estimated_hours: Option<f64>,
    #[serde(default)]
    estimated_confidence: Option<String>,
    #[serde(default)]
    references: Vec<String>,
    #[serde(default)]
    input_description: Option<String>,
    #[serde(default)]
    input_format: Option<String>,
    #[serde(default)]
    example_documents: Vec<UploadedFile>,
    #[serde(default)]
    example_images: Vec<UploadedFile>,
    #[serde(default)]
    output_description: Option<String>,
    #[serde(default)]
    output_format: Option<String>,
    #[serde(default)]
    output_examples: Vec<UploadedFile>,
    #[serde(default)]
    ai_review: Option<AIReview>,
}

#[derive(serde::Deserialize, serde::Serialize, Clone, Default)]
struct HourBreakdown {
    #[serde(default)]
    consulting: i32,
    #[serde(default)]
    development: i32,
    #[serde(default)]
    testing: i32,
    #[serde(default)]
    review: i32,
}

#[derive(serde::Deserialize, serde::Serialize, Clone)]
struct AIReview {
    completeness: String,
    reasonableness: String,
    feasibility: String,
    estimated_hours: i32,
    confidence: String,
    summary: String,
    suggestions: Vec<String>,
    score: i32,
    #[serde(default)]
    hour_breakdown: Option<HourBreakdown>,
}

#[derive(serde::Deserialize, serde::Serialize, Clone)]
struct UploadedFile {
    name: String,
    url: String,
    #[serde(default)]
    size: Option<i64>,
    #[serde(default)]
    mime_type: Option<String>,
}

async fn create_agent_demand(
    Path(key): Path<String>,
    Json(payload): Json<CreateDemandRequest>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("agent_demands").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let demand_key = uuid::Uuid::new_v4().to_string();
    let now = chrono::Utc::now().to_rfc3339();

    // Determine next version
    let existing: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR d IN agent_demands FILTER d.agent_key == @key SORT d.version DESC LIMIT 1 RETURN d",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let version = if let Some(last) = existing.first() {
        let last_ver = last.get("version").and_then(|v| v.as_str()).unwrap_or("v0.0");
        let num: f64 = last_ver.trim_start_matches('v').replace('.', "").parse().unwrap_or(0.0);
        let major = (num / 10.0).floor() as i32;
        let minor = (num % 10.0).floor() as i32 + 1;
        format!("v{}.{}", major, minor)
    } else {
        "v1.0".to_string()
    };

    let doc = serde_json::json!({
        "_key": demand_key.clone(),
        "agent_key": key,
        "version": version,
        "status": "draft",
        "goal": payload.goal,
        "expected_effect": payload.expected_effect,
        "problem_description": payload.problem_description,
        "target_users": payload.target_users.unwrap_or_default(),
        "scope": payload.scope.unwrap_or_default(),
        "excluded_scope": payload.excluded_scope.unwrap_or_default(),
        "conversation_style": payload.conversation_style.unwrap_or_default(),
        "conversation_examples": payload.conversation_examples,
        "estimated_hours": payload.estimated_hours,
        "estimated_confidence": payload.estimated_confidence.unwrap_or_else(|| "medium".to_string()),
        "final_hours": serde_json::Value::Null,
        "rejection_history": serde_json::Value::Array(vec![]),
        "references": payload.references,
        "input_description": payload.input_description.unwrap_or_default(),
        "input_format": payload.input_format.unwrap_or_default(),
        "example_documents": payload.example_documents,
        "example_images": payload.example_images,
        "output_description": payload.output_description.unwrap_or_default(),
        "output_format": payload.output_format.unwrap_or_default(),
        "output_examples": payload.output_examples,
        "ai_review": payload.ai_review,
        "created_at": now,
        "updated_at": now,
        "submitted_at": serde_json::Value::Null,
        "accepted_at": serde_json::Value::Null,
        "cancelled_at": serde_json::Value::Null,
        "online_at": serde_json::Value::Null,
    });

    col.create_document(doc, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let created: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR d IN agent_demands FILTER d._key == @key LIMIT 1 RETURN d",
            [("key", serde_json::json!(demand_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let demand = created.into_iter().next().ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    let _ = db.aql_bind_vars::<serde_json::Value>(
        "FOR a IN agents FILTER a._key == @key UPDATE a WITH { current_demand_key: @dk, demand_version: @ver } IN agents",
        [
            ("key", serde_json::json!(key)),
            ("dk", serde_json::json!(demand_key)),
            ("ver", serde_json::json!(version)),
        ].into(),
    ).await;

    Ok(Json(ApiResponse::success(demand)))
}

async fn get_agent_demand(
    Path((_key, demand_key)): Path<(String, String)>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let demands: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR d IN agent_demands FILTER d._key == @key LIMIT 1 RETURN d",
            [("key", serde_json::json!(demand_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let demand = demands.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(demand)))
}

async fn update_agent_demand(
    Path((_key, demand_key)): Path<(String, String)>,
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, StatusCode> {
    if payload.is_null() || payload.as_object().map(|o| o.is_empty()).unwrap_or(true) {
        return Err(StatusCode::BAD_REQUEST);
    }

    let db = get_db();
    let col = db.collection("agent_demands").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let existing: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR d IN agent_demands FILTER d._key == @key LIMIT 1 RETURN d.status",
            [("key", serde_json::json!(demand_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if let Some(status_val) = existing.first() {
        if let Some(status) = status_val.as_str() {
            if status != "draft" {
                return Err(StatusCode::BAD_REQUEST);
            }
        }
    }

    let mut update_data = payload.clone();
    if let Some(obj) = update_data.as_object_mut() {
        obj.insert("updated_at".to_string(), serde_json::json!(chrono::Utc::now().to_rfc3339()));
    }

    col.update_document(&demand_key, update_data, Default::default())
        .await
        .map_err(|e| {
            eprintln!("Update agent demand error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let updated: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR d IN agent_demands FILTER d._key == @key LIMIT 1 RETURN d",
            [("key", serde_json::json!(demand_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let demand = updated.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(demand)))
}

async fn delete_agent_demand(
    Path((_key, demand_key)): Path<(String, String)>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("agent_demands").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let existing: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR d IN agent_demands FILTER d._key == @key LIMIT 1 RETURN d.status",
            [("key", serde_json::json!(demand_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    if let Some(status_val) = existing.first() {
        if let Some(status) = status_val.as_str() {
            if status != "draft" && status != "cancelled" {
                return Err(StatusCode::BAD_REQUEST);
            }
        }
    }

    col.remove_document::<serde_json::Value>(&demand_key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success("Demand deleted".to_string())))
}

#[derive(serde::Deserialize)]
struct UpdateDemandStatusRequest {
    status: String,
    #[serde(default)]
    reason: Option<String>,
    #[serde(default)]
    estimated_hours: Option<f64>,
    #[serde(default)]
    final_hours: Option<f64>,
    #[serde(default)]
    ai_review: Option<AIReview>,
}

async fn update_demand_status(
    Path((_key, demand_key)): Path<(String, String)>,
    Json(payload): Json<UpdateDemandStatusRequest>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("agent_demands").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let now = chrono::Utc::now().to_rfc3339();

    let existing: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR d IN agent_demands FILTER d._key == @key LIMIT 1 RETURN d",
            [("key", serde_json::json!(demand_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let current = existing.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    let current_status = current.get("status").and_then(|v| v.as_str()).unwrap_or("");

    let valid_transition = match (current_status, payload.status.as_str()) {
        ("draft", "submitted") => true,
        ("submitted", "draft") => true,
        ("submitted", "in_development") => true,
        ("submitted", "cancelled") => true,
        ("in_development", "pending_acceptance") => true,
        ("pending_acceptance", "in_development") => true,
        ("pending_acceptance", "online") => true,
        ("online", "draft") => true,
        _ => false,
    };

    if !valid_transition {
        return Err(StatusCode::BAD_REQUEST);
    }

    let mut update_doc = serde_json::json!({
        "status": payload.status.clone(),
        "updated_at": now,
    });

    match payload.status.as_str() {
        "submitted" => {
            update_doc["submitted_at"] = serde_json::json!(now);
            if let Some(review) = &payload.ai_review {
                update_doc["ai_review"] = serde_json::json!(review);
            }
        }
        "in_development" => {
            if let Some(reason) = &payload.reason {
                if !reason.is_empty() {
                    let rejection = serde_json::json!({
                        "rejected_at": now,
                        "reason": reason,
                    });
                    let mut history = current.get("rejection_history").cloned().unwrap_or(serde_json::json!([]));
                    if let Some(arr) = history.as_array_mut() {
                        arr.push(rejection);
                    }
                    update_doc["rejection_history"] = history;
                    update_doc["status"] = serde_json::json!("in_development");
                }
            }
            if let Some(hours) = payload.estimated_hours {
                update_doc["estimated_hours"] = serde_json::json!(hours);
            }
        }
        "online" => {
            update_doc["online_at"] = serde_json::json!(now);
        }
        "cancelled" => {
            update_doc["cancelled_at"] = serde_json::json!(now);
        }
        _ => {}
    }

    col.update_document(&demand_key, update_doc, Default::default())
        .await
        .map_err(|e| {
            eprintln!("Update demand status error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let updated: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR d IN agent_demands FILTER d._key == @key LIMIT 1 RETURN d",
            [("key", serde_json::json!(demand_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let demand = updated.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(demand)))
}

#[derive(serde::Deserialize)]
struct EstimateHoursRequest {
    goal: String,
    expected_effect: String,
    problem_description: String,
    #[serde(default)]
    target_users: Option<String>,
    #[serde(default)]
    scope: Option<String>,
    #[serde(default)]
    excluded_scope: Option<String>,
    #[serde(default)]
    systems_to_integrate: Vec<String>,
}

async fn estimate_demand_hours(
    Json(payload): Json<EstimateHoursRequest>,
) -> Result<impl IntoResponse, StatusCode> {
    let scope_count = payload.scope
        .as_ref()
        .map(|s| s.split(',').count())
        .unwrap_or(0)
        .max(1);

    let system_count = payload.systems_to_integrate.len();

    let base_hours = scope_count * 8;
    let integration_hours = system_count * 8;

    let complexity_factor = if payload.problem_description.len() > 500 {
        1.5
    } else if payload.problem_description.len() > 200 {
        1.2
    } else {
        1.0
    };

    let total = ((base_hours + integration_hours) as f64 * complexity_factor).round() as i32;
    let range_min = (total as f64 * 0.8).round() as i32;
    let range_max = (total as f64 * 1.3).round() as i32;

    let confidence = if scope_count <= 3 && system_count <= 2 {
        "high"
    } else if scope_count <= 5 && system_count <= 4 {
        "medium"
    } else {
        "low"
    };

    let reasoning = format!(
        "需求涉及 {} 個主要領域，{} 個外部系統串接，複雜度{}。",
        scope_count,
        system_count,
        match confidence {
            "high" => "較低",
            "medium" => "中等",
            _ => "較高",
        }
    );

    Ok(Json(serde_json::json!({
        "code": 0,
        "data": {
            "estimated_hours": total,
            "range_min": range_min,
            "range_max": range_max,
            "confidence": confidence,
            "reasoning": reasoning,
        }
    })))
}

async fn review_demand(
    Json(payload): Json<CreateDemandRequest>,
) -> Result<impl IntoResponse, StatusCode> {
    let ollama_url = CONFIG.ai_services.ollama_base_url.clone();
    let model = "qwen3-coder:30b";

    let prompt = build_review_prompt(&payload);

    let ollama_body = serde_json::json!({
        "model": model,
        "prompt": prompt,
        "stream": false,
        "options": {
            "temperature": 0.3,
            "num_predict": 512,
        }
    });

    let result = HTTP_CLIENT
        .post(format!("{}/api/generate", ollama_url))
        .json(&ollama_body)
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await;

    let review = match result {
        Ok(resp) if resp.status().is_success() => {
            let body: serde_json::Value = resp.json().await.unwrap_or_default();
            let response_text = body.get("response").and_then(|v| v.as_str()).unwrap_or("");
            parse_ai_review_response(response_text)
        }
        _ => {
                AIReview {
                    completeness: "無法完成 AI 審查".to_string(),
                    reasonableness: "無法完成 AI 審查".to_string(),
                    feasibility: "無法完成 AI 審查".to_string(),
                    estimated_hours: 0,
                    confidence: "low".to_string(),
                    summary: "AI 審查服務暫時無法使用".to_string(),
                    suggestions: vec![],
                    score: 0,
                    hour_breakdown: None,
                }
        }
    };

    Ok(Json(ApiResponse::success(review)))
}

fn build_review_prompt(req: &CreateDemandRequest) -> String {
    format!(
        r#"你是一個專業的 AI 需求審查專家。我們已有 AI 對話框架、RAG 檢索、工具系統等基礎建設，只需建立新的 AI Agent 来處理特定領域問題。

請審查以下需求並提供詳細分析：

需求目標：{}
預期效果：{}
問題描述：{}
目標用戶：{}
服務範圍：{}
不包含範圍：{}
對話風格：{}
輸入說明：{}
輸入格式：{}
輸出說明：{}
輸出格式：{}

請以 JSON 格式回覆，包含以下欄位：
- completeness: 需求完整性評估（是否清楚定義了需求目標、範圍、輸入輸出）
- reasonableness: 合理性評估（需求是否合理、是否符合業務邏輯）
- feasibility: 可行性評估（技術上是否可行、是否有明顯障礙）
- estimated_hours: 預估總工時（小時，整數，僅估算建立新 Agent 的增量工作，不含基礎建設）
- hour_breakdown: 工時明細（物件，包含以下欄位，皆為整數小時）：
    - consulting: 顧問訪談與需求釐清
    - development: 核心開發與整合
    - testing: 測試與品質保證
    - review: 審查與上線準備
- confidence: 估計信心（low/medium/high）
- summary: 總結（一句話概括這個需求）
- suggestions: 改進建議（陣列，每項一字元串，若無建議則回空陣列）
- score: 綜合評分（0-100，低於70分不建議開發）

請只回覆 JSON，不要有其他文字："#,
        req.goal,
        req.expected_effect,
        req.problem_description,
        req.target_users.as_deref().unwrap_or("未指定"),
        req.scope.as_deref().unwrap_or("未指定"),
        req.excluded_scope.as_deref().unwrap_or("未指定"),
        req.conversation_style.as_deref().unwrap_or("未指定"),
        req.input_description.as_deref().unwrap_or("未指定"),
        req.input_format.as_deref().unwrap_or("未指定"),
        req.output_description.as_deref().unwrap_or("未指定"),
        req.output_format.as_deref().unwrap_or("未指定"),
    )
}

fn parse_ai_review_response(response: &str) -> AIReview {
    let trimmed = response.trim();

    if let Some(start) = trimmed.find('{') {
        if let Some(end) = trimmed.rfind('}') {
            let json_str = &trimmed[start..=end];
            if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(json_str) {
                return AIReview {
                    completeness: parsed.get("completeness")
                        .and_then(|v| v.as_str())
                        .unwrap_or("無法評估")
                        .to_string(),
                    reasonableness: parsed.get("reasonableness")
                        .and_then(|v| v.as_str())
                        .unwrap_or("無法評估")
                        .to_string(),
                    feasibility: parsed.get("feasibility")
                        .and_then(|v| v.as_str())
                        .unwrap_or("無法評估")
                        .to_string(),
                    estimated_hours: parsed.get("estimated_hours")
                        .and_then(|v| v.as_i64())
                        .unwrap_or(0) as i32,
                    confidence: parsed.get("confidence")
                        .and_then(|v| v.as_str())
                        .unwrap_or("low")
                        .to_string(),
                    summary: parsed.get("summary")
                        .and_then(|v| v.as_str())
                        .unwrap_or("無法生成摘要")
                        .to_string(),
                    suggestions: parsed.get("suggestions")
                        .and_then(|v| v.as_array())
                        .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
                        .unwrap_or_default(),
                    score: parsed.get("score")
                        .and_then(|v| v.as_i64())
                        .unwrap_or(0) as i32,
                    hour_breakdown: parsed.get("hour_breakdown").and_then(|v| {
                        Some(HourBreakdown {
                            consulting: v.get("consulting").and_then(|x| x.as_i64()).unwrap_or(0) as i32,
                            development: v.get("development").and_then(|x| x.as_i64()).unwrap_or(0) as i32,
                            testing: v.get("testing").and_then(|x| x.as_i64()).unwrap_or(0) as i32,
                            review: v.get("review").and_then(|x| x.as_i64()).unwrap_or(0) as i32,
                        })
                    }),
                };
            }
        }
    }

    AIReview {
        completeness: format!("解析失敗：{}", &response[..response.len().min(100)]),
        reasonableness: "無法評估".to_string(),
        feasibility: "無法評估".to_string(),
        estimated_hours: 0,
        confidence: "low".to_string(),
        summary: "AI 回應格式不符預期".to_string(),
        suggestions: vec![],
        score: 0,
        hour_breakdown: None,
    }
}

async fn suggest_intents_for_demand(
    Path((_agent_key, demand_key)): Path<(String, String)>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let demand: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR d IN agent_demands FILTER d._key == @key LIMIT 1 RETURN d",
            [("key", serde_json::json!(demand_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let demand = demand.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let ollama_url = CONFIG.ai_services.ollama_base_url.clone();
    let model = "qwen3-coder:30b";

    let prompt = format!(
        r#"你是一個 AI Agent 意圖設計專家。根據以下需求，設計 3-5 個意圖（Intent）。

需求目標：{}
問題描述：{}
服務範圍：{}
輸入說明：{}
輸出說明：{}

請以 JSON 格式回覆，包含一個 intents 陣列，每個意圖包含：
- name: 意圖名稱（簡短，如「查庫存」、「天氣查詢」）
- description: 意圖描述
- action_type: 動作類型（direct_answer / tool_call / process_orchestration）
- tool_category: 工具類別（web_search / data / knowledge / mcp），若不需要工具則省略
- tool_name: 具體工具名稱，若不需要則省略
- response_strategy: 響應策略（direct_llm / confirm_then_execute / clarify_first / handoff_bpa）

請只回覆 JSON，格式如下：
{{ "intents": [{{"name": "...", "description": "...", "action_type": "...", ...}}] }}"#,
        demand.get("goal").and_then(|v| v.as_str()).unwrap_or("未指定"),
        demand.get("problem_description").and_then(|v| v.as_str()).unwrap_or("未指定"),
        demand.get("scope").and_then(|v| v.as_str()).unwrap_or("未指定"),
        demand.get("input_description").and_then(|v| v.as_str()).unwrap_or("未指定"),
        demand.get("output_description").and_then(|v| v.as_str()).unwrap_or("未指定"),
    );

    let ollama_body = serde_json::json!({
        "model": model,
        "prompt": prompt,
        "stream": false,
        "options": {
            "temperature": 0.3,
            "num_predict": 512,
        }
    });

    let result = HTTP_CLIENT
        .post(format!("{}/api/generate", ollama_url))
        .json(&ollama_body)
        .timeout(std::time::Duration::from_secs(30))
        .send()
        .await;

    let intents = match result {
        Ok(resp) if resp.status().is_success() => {
            let body: serde_json::Value = resp.json().await.unwrap_or_default();
            let response_text = body.get("response").and_then(|v| v.as_str()).unwrap_or("");
            parse_suggested_intents(response_text)
        }
        _ => vec![],
    };

    Ok(Json(ApiResponse::success(intents)))
}

fn parse_suggested_intents(response: &str) -> Vec<serde_json::Value> {
    let trimmed = response.trim();
    if let Some(start) = trimmed.find('{') {
        if let Some(end) = trimmed.rfind('}') {
            let json_str = &trimmed[start..=end];
            if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(json_str) {
                if let Some(intents_array) = parsed.get("intents").and_then(|v| v.as_array()) {
                    return intents_array.iter().map(|v| v.clone()).collect();
                }
            }
        }
    }
    vec![]
}

async fn list_tools(headers: HeaderMap, Query(params): Query<std::collections::HashMap<String, String>>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let tool_type = params.get("tool_type").map(|s| s.as_str());

    let (user_key, user_roles) = if let Some(token) = headers.get(AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
    {
        if let Ok(claims) = verify_jwt(token) {
            let raw_users: Vec<serde_json::Value> = db
                .aql_bind_vars(
                    "FOR u IN users FILTER u.username == @username LIMIT 1 RETURN u",
                    [("username", serde_json::json!(claims.claims.username))].into(),
                )
                .await
                .unwrap_or_default();
            let raw_user = raw_users.into_iter().next();
            let role_keys: Vec<String> = raw_user.as_ref()
                .and_then(|u| u.get("role_keys"))
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect::<Vec<_>>())
                .unwrap_or_default();
            let uk = raw_user.as_ref()
                .and_then(|u| u.get("_key"))
                .and_then(|v| v.as_str())
                .map(String::from)
                .unwrap_or_default();
            (Some(uk), Some(role_keys))
        } else {
            (None, None)
        }
    } else {
        (None, None)
    };

    let tool_filter = if let Some(t) = tool_type {
        format!(" && t.tool_type == '{}'", t)
    } else {
        String::new()
    };
    let query = format!(
        "FOR t IN tools FILTER (t.visibility == null || t.visibility == 'public' || t.visibility == 'role' || t.visibility == 'account' || t.visibility == 'private'){} SORT t.created_at DESC RETURN t",
        tool_filter
    );
    let all_tools: Vec<Tool> = db.aql_str(&query).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let is_admin = user_roles.as_ref().map(|r| r.contains(&"admin".to_string())).unwrap_or(false);

    let filtered: Vec<Tool> = match (&user_key, &user_roles) {
        (Some(uk), Some(roles)) => all_tools
            .into_iter()
            .filter(|t| {
                if is_admin {
                    return true;
                }
                match t.visibility.as_deref().unwrap_or("public") {
                    "public" => true,
                    "role" => {
                        let tool_roles = t.visibility_roles.as_deref().unwrap_or(&[]);
                        roles.iter().any(|r| tool_roles.contains(r))
                    }
                    "account" => {
                        let tool_accounts = t.visibility_accounts.as_deref().unwrap_or(&[]);
                        tool_accounts.contains(uk)
                    }
                    _ => false,
                }
            })
            .collect(),
        _ => all_tools
            .into_iter()
            .filter(|t| matches!(t.visibility.as_deref().unwrap_or("public"), "public"))
            .collect(),
    };

    Ok(Json(ApiResponse::success(filtered)))
}

async fn create_tool(Json(payload): Json<CreateToolRequest>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let key = uuid::Uuid::new_v4().to_string();
    let now = chrono::Utc::now().to_rfc3339();

    let tool = Tool {
        _key: Some(key.clone()),
        code: payload.code,
        name: payload.name,
        description: payload.description,
        tool_type: payload.tool_type,
        icon: payload.icon,
        status: payload.status.unwrap_or_else(|| "online".to_string()),
        usage_count: 0,
        group_key: payload.group_key,
        intent_tags: payload.intent_tags,
        nl_examples: payload.nl_examples,
        endpoint_url: payload.endpoint_url,
        input_schema: payload.input_schema,
        output_schema: payload.output_schema,
        timeout_ms: payload.timeout_ms,
        llm_model: payload.llm_model,
        temperature: payload.temperature,
        max_tokens: payload.max_tokens,
        auth_config: payload.auth_config,
        visibility: payload.visibility.or_else(|| Some("public".to_string())),
        visibility_roles: payload.visibility_roles,
        visibility_accounts: payload.visibility_accounts,
        created_by: payload.created_by,
        updated_by: None,
        created_at: now.clone(),
        updated_at: now,
    };

    let col = db.collection("tools").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.create_document(tool.clone(), Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(tool)))
}

async fn get_tool(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let mut tools: Vec<Tool> = db
        .aql_bind_vars(
            "FOR t IN tools FILTER t._key == @key LIMIT 1 RETURN t",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let tool = tools.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(tool)))
}

async fn update_tool(Path(key): Path<String>, Json(payload): Json<serde_json::Value>) -> Result<impl IntoResponse, StatusCode> {
    if payload.is_null() || payload.as_object().map(|o| o.is_empty()).unwrap_or(true) {
        return Err(StatusCode::BAD_REQUEST);
    }

    let db = get_db();
    let col = db.collection("tools").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    eprintln!("update_tool: key={} payload={}", key, payload);
    let existing: Vec<serde_json::Value> = db
        .aql_bind_vars("FOR t IN tools FILTER t._key == @key LIMIT 1 RETURN t", [("key", serde_json::json!(key))].into())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let old = existing.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let mut update_data = payload.clone();
    if let Some(obj) = update_data.as_object_mut() {
        if !obj.contains_key("created_by") {
            if let Some(cb) = old.get("created_by") {
                obj.insert("created_by".to_string(), cb.clone());
            }
        }
        obj.insert("updated_at".to_string(), serde_json::json!(chrono::Utc::now().to_rfc3339()));
    }

    col.update_document(&key, update_data, Default::default())
        .await
        .map_err(|e| {
            eprintln!("Update tool error: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let mut tools: Vec<Tool> = db
        .aql_bind_vars(
            "FOR t IN tools FILTER t._key == @key LIMIT 1 RETURN t",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let tool = tools.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(tool)))
}

async fn delete_tool(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("tools").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<serde_json::Value>(&key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success("Tool deleted".to_string())))
}

async fn toggle_agent_favorite(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    
    let mut agents: Vec<Agent> = db
        .aql_bind_vars(
            "FOR a IN agents FILTER a._key == @key LIMIT 1 RETURN a",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let agent = agents.pop().ok_or(StatusCode::NOT_FOUND)?;
    let new_favorite = !agent.is_favorite.unwrap_or(false);

    let col = db.collection("agents").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(
        &key,
        serde_json::json!({
            "is_favorite": new_favorite,
            "updated_at": chrono::Utc::now().to_rfc3339()
        }),
        Default::default(),
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut agents: Vec<Agent> = db
        .aql_bind_vars(
            "FOR a IN agents FILTER a._key == @key LIMIT 1 RETURN a",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let agent = agents.pop().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(agent)))
}

// ============= Model Providers =============

async fn list_model_providers() -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let raw: Vec<serde_json::Value> = db
        .aql_str("FOR p IN model_providers SORT p.sort_order ASC RETURN p")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let providers: Vec<ModelProvider> = raw
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();
    Ok(Json(ApiResponse::success(providers)))
}

async fn get_model_provider(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let raw: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR p IN model_providers FILTER p._key == @key LIMIT 1 RETURN p",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let providers: Vec<ModelProvider> = raw
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();
    let provider = providers.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(provider)))
}

async fn create_model_provider(Json(payload): Json<serde_json::Value>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("model_providers").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let code = payload.get("code").and_then(|v| v.as_str()).ok_or(StatusCode::BAD_REQUEST)?;
    let name = payload.get("name").and_then(|v| v.as_str()).ok_or(StatusCode::BAD_REQUEST)?;
    let base_url = payload.get("base_url").and_then(|v| v.as_str()).unwrap_or("");
    let now = chrono::Utc::now().to_rfc3339();

    let doc = serde_json::json!({
        "code": code,
        "name": name,
        "description": payload.get("description").and_then(|v| v.as_str()),
        "icon": payload.get("icon").and_then(|v| v.as_str()),
        "base_url": base_url,
        "api_key": payload.get("api_key").and_then(|v| v.as_str()),
        "status": payload.get("status").and_then(|v| v.as_str()).unwrap_or("disabled"),
        "sort_order": payload.get("sort_order").and_then(|v| v.as_i64()).unwrap_or(99),
        "models": serde_json::Value::Array(vec![]),
        "created_at": now,
        "updated_at": now,
    });

    col.create_document(doc.clone(), Default::default())
        .await
        .map_err(|e| {
            eprintln!("Create provider error: {:?}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let raw: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR p IN model_providers FILTER p.code == @code LIMIT 1 RETURN p",
            [("code", serde_json::json!(code))].into(),
        )
        .await
        .map_err(|e| {
            eprintln!("Fetch new provider error: {:?}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    let providers: Vec<ModelProvider> = raw
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();
    let p = providers.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(p)))
}

// ==================== Agent Requirements ====================

async fn generate_req_no(payload: &serde_json::Value) -> String {
    use chrono::Datelike;
    let db = get_db();

    let now = chrono::Utc::now();
    let iso_week = now.iso_week();
    let week_str = format!("{:02}", iso_week.week());
    let year_str = format!("{:02}", now.year() % 100);

    let agent_type = payload.get("agent_type").and_then(|v| v.as_str()).unwrap_or("A");
    let tab_code = payload.get("tab_code").and_then(|v| v.as_str()).unwrap_or("01");
    let prefix = format!("{}{}-{}{}", agent_type, tab_code, year_str, week_str);

    // Count existing docs with same prefix this week
    let pattern = format!("{}%", prefix);
    let count: f64 = db
        .aql_bind_vars(
            "FOR r IN agent_requirements FILTER r.req_no LIKE @pattern RETURN 1",
            [("pattern", serde_json::json!(pattern))].into(),
        )
        .await
        .ok()
        .map(|v: Vec<serde_json::Value>| v.len() as f64)
        .unwrap_or(0.0);

    format!("{}-{:03}", prefix, count as i32 + 1)
}

async fn list_all_agent_requirements() -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<serde_json::Value> = db
        .aql_str("FOR r IN agent_requirements SORT r.submitted_at DESC RETURN r")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(docs)))
}

async fn create_agent_requirement(
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("agent_requirements").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Auto-increment requirement number
    let req_no = generate_req_no(&payload).await;

    let doc_key = format!(
        "{}_{}",
        payload.get("agent_key").and_then(|v| v.as_str()).unwrap_or("unknown"),
        payload.get("version").and_then(|v| v.as_str()).unwrap_or("v1.0")
    );
    let now = chrono::Utc::now().to_rfc3339();
    let mut doc = payload.clone();
    if let Some(obj) = doc.as_object_mut() {
        obj.insert("_key".to_string(), serde_json::json!(doc_key));
        obj.insert("req_no".to_string(), serde_json::json!(req_no));
        obj.insert("created_at".to_string(), serde_json::json!(now));
        obj.insert("updated_at".to_string(), serde_json::json!(now));
    }
    col.create_document(doc, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(doc_key)))
}

async fn get_agent_requirement(
    Path(req_key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR r IN agent_requirements FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", serde_json::json!(req_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc = docs.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(doc)))
}

async fn accept_agent_requirement(
    Path(req_key): Path<String>,
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("agent_requirements").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let developer = payload.get("developer").and_then(|v| v.as_str()).unwrap_or("unknown");
    col.update_document(
        &req_key,
        serde_json::json!({
            "status": "accepted",
            "developer": developer,
            "accepted_at": chrono::Utc::now().to_rfc3339(),
            "updated_at": chrono::Utc::now().to_rfc3339(),
        }),
        Default::default(),
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success("accepted".to_string())))
}

async fn analyze_agent_requirement(
    Path(req_key): Path<String>,
    Json(payload): Json<serde_json::Value>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR r IN agent_requirements FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", serde_json::json!(req_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc = docs.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let goal = doc.get("goal").and_then(|v| v.as_str()).unwrap_or("");
    let expected = doc.get("expected_effect").and_then(|v| v.as_str()).unwrap_or("");
    let problem = doc.get("problem_description").and_then(|v| v.as_str()).unwrap_or("");
    let agent_name = doc.get("agent_name").and_then(|v| v.as_str()).unwrap_or("");

    let ollama_url = std::env::var("OLLAMA_BASE_URL").unwrap_or_else(|_| "http://localhost:11434".to_string());
    let ollama_url = ollama_url.trim_end_matches('/');

    // Read model from system_params, fallback to qwen3-coder:30b
    let model: String = db
        .aql_bind_vars(
            "FOR p IN system_params FILTER p.param_key == @key LIMIT 1 RETURN p.param_value",
            [("key", serde_json::json!("dev.requirement_spec_model"))].into(),
        )
        .await
        .ok()
        .and_then(|mut v: Vec<String>| v.pop())
        .unwrap_or_else(|| "qwen3-coder:30b".to_string());

    let revision = payload.get("revision").and_then(|v| v.as_str()).unwrap_or("");
    let revision_hint = if revision.is_empty() {
        String::new()
    } else {
        format!("\n\n⚠️ 修改指示：請根據以下反饋調整規格書內容：\n{revision}\n")
    };

    let ai_review = doc.get("ai_review");
    let ref_consulting = ai_review.and_then(|v| v.get("hour_breakdown")).and_then(|v| v.get("consulting")).and_then(|v| v.as_i64()).unwrap_or(0);
    let ref_dev = ai_review.and_then(|v| v.get("hour_breakdown")).and_then(|v| v.get("development")).and_then(|v| v.as_i64()).unwrap_or(0);
    let ref_test = ai_review.and_then(|v| v.get("hour_breakdown")).and_then(|v| v.get("testing")).and_then(|v| v.as_i64()).unwrap_or(0);
    let ref_review = ai_review.and_then(|v| v.get("hour_breakdown")).and_then(|v| v.get("review")).and_then(|v| v.as_i64()).unwrap_or(0);
    let ref_hours = if ref_consulting + ref_dev + ref_test + ref_review > 0 {
        format!("\n\n📊 原始工時參考（請根據修改指示合理調整）：顧問 {ref_consulting}h / 開發 {ref_dev}h / 測試 {ref_test}h / 審查 {ref_review}h")
    } else {
        String::new()
    };

    let spec_index: String = db
        .aql_bind_vars(
            "FOR p IN system_params FILTER p.param_key == @key LIMIT 1 RETURN p.param_value",
            [("key", serde_json::json!("dev.spec_context"))].into(),
        )
        .await
        .ok()
        .and_then(|mut v: Vec<String>| v.pop())
        .unwrap_or_default();

    let prompt = format!(
        r#"你是 AIBox / ABC Desktop 系統的資深開發架構師。請根據以下需求與系統規格，產生一份開發建議規格書（JSON 格式）。

## 系統規格索引（請根據需求主題，參考對應文件的設計模式與慣例）

{spec_index}

## 需求
Agent 名稱：{agent_name}
需求目標：{goal}
預期效果：{expected}
問題描述：{problem}{revision_hint}{ref_hours}

## 約束
- 技術棧必須在本系統範圍內：Tauri/Rust/React/TypeScript/Ant Design 6/Python FastAPI/ArangoDB/Qdrant/Ollama
- 服務間通訊必須透過 Rust API Gateway (port 6500) 轉發
- 新 Agent 應使用 shared/orchestration/ + shared/tools/ 框架
- 配置須存 ArangoDB system_params，禁止 hardcode
- 前端須遵循 AGENTS.md 的 Store 模式與元件結構
- API 格式須符合 .docs/Spec/API Specification.md

## 輸出 JSON（只輸出 JSON）
{{
  "summary": "需求摘要（一段話）",
  "tech_stack": ["基於本系統的具體技術選擇"],
  "modules": [
    {{ "name": "模組名", "description": "功能說明", "priority": "high|medium|low", "depends_on": ["依賴模組"] }}
  ],
  "data_sources": ["ArangoDB 集合或外部 API"],
  "integration_points": ["需整合的內部服務"],
  "hour_breakdown": {{
    "consulting": 顧問訪談與需求釐清（整數小時）,
    "development": Rust/Python/React 開發與整合（整數小時）,
    "testing": 測試與品質保證（整數小時）,
    "review": 審查與上線準備（整數小時）
  }},
  "mermaid_architecture": "Mermaid graph，展示本 Agent 與現有系統組件關係",
  "mermaid_flow": "Mermaid flowchart，展示請求處理流程",
  "risks": ["風險"],
  "suggestions": ["開發建議"]
}}"#,
        spec_index = spec_index,
        agent_name = agent_name,
        goal = goal,
        expected = expected,
        problem = problem,
        revision_hint = revision_hint,
        ref_hours = ref_hours,
    );

    let mut spec_json = serde_json::json!({
        "summary": "LLM 分析中...",
        "tech_stack": [],
        "modules": [],
        "data_sources": [],
        "integration_points": [],
        "risks": [],
        "suggestions": [],
    });

    if let Ok(client) = reqwest::Client::builder().timeout(std::time::Duration::from_secs(120)).build() {
        if let Ok(resp) = client
            .post(format!("{ollama_url}/api/chat"))
            .json(&serde_json::json!({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": false,
                "format": "json",
            }))
            .send()
            .await
        {
            if let Ok(body) = resp.json::<serde_json::Value>().await {
                if let Some(content) = body.get("message").and_then(|m| m.get("content")).and_then(|c| c.as_str()) {
                    if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(content) {
                        spec_json = parsed;
                    } else if let Some(start) = content.find('{') {
                        if let Some(end) = content.rfind('}') {
                            if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(&content[start..=end]) {
                                spec_json = parsed;
                            }
                        }
                    }
                }
            }
        }
    }

    let col = db.collection("agent_requirements").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(
        &req_key,
        serde_json::json!({
            "status": "spec_ready",
            "dev_spec": spec_json,
            "analyzed_at": chrono::Utc::now().to_rfc3339(),
            "updated_at": chrono::Utc::now().to_rfc3339(),
        }),
        Default::default(),
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success("spec_generated".to_string())))
}

async fn start_dev_workspace(
    Path(req_key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR r IN agent_requirements FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", serde_json::json!(req_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc = docs.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let col = db.collection("agent_requirements").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(
        &req_key,
        serde_json::json!({
            "status": "in_development",
            "dev_started_at": chrono::Utc::now().to_rfc3339(),
            "updated_at": chrono::Utc::now().to_rfc3339(),
        }),
        Default::default(),
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success(doc)))
}

async fn get_agent_requirement_by_no(
    Path(req_no): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR r IN agent_requirements FILTER r.req_no == @no LIMIT 1 RETURN r",
            [("no", serde_json::json!(req_no))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc = docs.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(doc)))
}

async fn get_agent_requirement_spec_md(
    Path(req_key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR r IN agent_requirements FILTER r._key == @key LIMIT 1 RETURN r",
            [("key", serde_json::json!(req_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc = docs.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let agent_name = doc.get("agent_name").and_then(|v| v.as_str()).unwrap_or("");
    let goal = doc.get("goal").and_then(|v| v.as_str()).unwrap_or("");
    let expected = doc.get("expected_effect").and_then(|v| v.as_str()).unwrap_or("");
    let problem = doc.get("problem_description").and_then(|v| v.as_str()).unwrap_or("");
    let spec = doc.get("dev_spec");
    let ai_review = doc.get("ai_review");

    let mut md = String::new();
    md.push_str(&format!("# 開發規格書：{agent_name}\n\n"));
    md.push_str("> 本規格書由 AIBox 系統開發區自動生成，可供 AI 開發工具參照。\n\n");
    md.push_str("## 需求概要\n\n");
    md.push_str(&format!("- **目標**：{goal}\n"));
    md.push_str(&format!("- **預期效果**：{expected}\n"));
    md.push_str(&format!("- **問題描述**：{problem}\n\n"));

    if let Some(review) = ai_review {
        md.push_str("## AI 審查\n\n");
        if let Some(s) = review.get("score").and_then(|v| v.as_i64()) { md.push_str(&format!("- 評分：{s}\n")); }
        if let Some(s) = review.get("summary").and_then(|v| v.as_str()) { md.push_str(&format!("- 摘要：{s}\n")); }
        if let Some(bd) = review.get("hour_breakdown") {
            md.push_str("- 工時明細：\n");
            if let Some(v) = bd.get("consulting").and_then(|v| v.as_i64()) { md.push_str(&format!("  - 顧問：{v}h\n")); }
            if let Some(v) = bd.get("development").and_then(|v| v.as_i64()) { md.push_str(&format!("  - 開發：{v}h\n")); }
            if let Some(v) = bd.get("testing").and_then(|v| v.as_i64()) { md.push_str(&format!("  - 測試：{v}h\n")); }
            if let Some(v) = bd.get("review").and_then(|v| v.as_i64()) { md.push_str(&format!("  - 審查：{v}h\n")); }
        }
        md.push_str("\n");
    }

    if let Some(s) = spec {
        if let Some(v) = s.get("summary").and_then(|v| v.as_str()) { md.push_str(&format!("## 摘要\n\n{v}\n\n")); }
        if let Some(arr) = s.get("tech_stack").and_then(|v| v.as_array()) {
            md.push_str("## 技術棧\n\n");
            for t in arr { if let Some(v) = t.as_str() { md.push_str(&format!("- {v}\n")); } }
            md.push_str("\n");
        }
        if let Some(arr) = s.get("modules").and_then(|v| v.as_array()) {
            md.push_str("## 模組規劃\n\n");
            md.push_str("| 模組 | 說明 | 優先級 |\n|------|------|--------|\n");
            for m in arr {
                let name = m.get("name").and_then(|v| v.as_str()).unwrap_or("-");
                let desc = m.get("description").and_then(|v| v.as_str()).unwrap_or("-");
                let pri = m.get("priority").and_then(|v| v.as_str()).unwrap_or("-");
                md.push_str(&format!("| {name} | {desc} | {pri} |\n"));
            }
            md.push_str("\n");
        }
        if let Some(v) = s.get("mermaid_architecture").and_then(|v| v.as_str()) {
            md.push_str("## 系統架構圖\n\n```mermaid\n");
            md.push_str(v);
            md.push_str("\n```\n\n");
        }
        if let Some(v) = s.get("mermaid_flow").and_then(|v| v.as_str()) {
            md.push_str("## 資料流程圖\n\n```mermaid\n");
            md.push_str(v);
            md.push_str("\n```\n\n");
        }
        if let Some(arr) = s.get("risks").and_then(|v| v.as_array()) {
            md.push_str("## 風險\n\n");
            for r in arr { if let Some(v) = r.as_str() { md.push_str(&format!("- {v}\n")); } }
            md.push_str("\n");
        }
        if let Some(arr) = s.get("suggestions").and_then(|v| v.as_array()) {
            md.push_str("## 建議\n\n");
            for sg in arr { if let Some(v) = sg.as_str() { md.push_str(&format!("- {v}\n")); } }
            md.push_str("\n");
        }
    }

    md.push_str("---\n*本規格書由 AIBox 系統自動生成。*\n");

    Ok(axum::response::Response::builder()
        .header("content-type", "text/markdown; charset=utf-8")
        .body(axum::body::Body::from(md))
        .unwrap())
}

async fn update_model_provider(Path(key): Path<String>, Json(payload): Json<serde_json::Value>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("model_providers").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let existing: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR p IN model_providers FILTER p._key == @key LIMIT 1 RETURN p",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let _old = existing.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let mut update = serde_json::Map::new();
    for (k, v) in payload.as_object().unwrap_or(&serde_json::Map::new()) {
        if k != "_key" && k != "_id" && k != "created_at" && k != "code" {
            update.insert(k.clone(), v.clone());
        }
    }
    update.insert("updated_at".to_string(), serde_json::json!(chrono::Utc::now().to_rfc3339()));

    col.update_document(&key, serde_json::Value::Object(update), Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let raw: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR p IN model_providers FILTER p._key == @key LIMIT 1 RETURN p",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let providers: Vec<ModelProvider> = raw
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();
    let p = providers.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(p)))
}

async fn delete_model_provider(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("model_providers").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<serde_json::Value>(&key, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success("Provider deleted".to_string())))
}

async fn sync_model_provider(Path(key): Path<String>) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();

    let raw: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR p IN model_providers FILTER p._key == @key LIMIT 1 RETURN p",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let providers: Vec<ModelProvider> = raw
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();
    let provider = providers.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let mut synced_models: Vec<LLMModel> = Vec::new();

    if provider.code == "ollama" {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(10))
            .build()
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

        let resp = client
            .get(format!("{}/api/tags", provider.base_url))
            .send()
            .await
            .map_err(|_| StatusCode::BAD_GATEWAY)?;

        if resp.status().is_success() {
            let body: serde_json::Value = resp.json().await.map_err(|_| StatusCode::BAD_GATEWAY)?;
            if let Some(models) = body.get("models").and_then(|v| v.as_array()) {
                for m in models {
                    let name = m.get("name").and_then(|v| v.as_str()).unwrap_or("unknown").to_string();
                    synced_models.push(LLMModel {
                        model_id: name.clone(),
                        name: name.clone(),
                        display_name: Some(name.clone()),
                        context_window: None,
                        input_cost_per_1k: None,
                        output_cost_per_1k: None,
                        supports_vision: Some(false),
                        temperature: Some(0.7),
                        status: "enabled".to_string(),
                    });
                }
            }
        }
    }

    let col = db.collection("model_providers").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(
        &key,
        serde_json::json!({
            "models": synced_models,
            "updated_at": chrono::Utc::now().to_rfc3339()
        }),
        Default::default(),
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let raw: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR p IN model_providers FILTER p._key == @key LIMIT 1 RETURN p",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let providers: Vec<ModelProvider> = raw
        .into_iter()
        .filter_map(|v| serde_json::from_value(v).ok())
        .collect();
    let p = providers.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(p)))
}
