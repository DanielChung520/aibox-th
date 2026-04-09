//! API Routes Module
//!
//! # Description
//! API 路由定義
//!
//! # Last Update: 2026-03-28 10:22:08
//! # Author: Daniel Chung
//! # Version: 1.1.0

use reqwest;
use crate::auth::verify_jwt;
use crate::middleware::auth::jwt_auth_middleware;
use crate::db::{
    get_db, CreateAgentRequest, CreateRoleRequest, CreateToolRequest, CreateUserRequest, Function, FunctionRoleAuth, Role, RoleFunction, SystemParam, UpdateParamRequest, UpdateRoleRequest, User, Agent, Tool, ToolLog, ModelProvider, LLMModel,
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
pub mod knowledge;
pub mod ontology;
pub mod themes;
pub mod web_search;
pub mod weather;
pub mod intent;
pub mod orch_intents;
pub mod intent_catalog;
pub mod leads;

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
        .route("/api/v1/tools", get(list_tools).post(create_tool))
        .route("/api/v1/tools/{key}", get(get_tool).put(update_tool).delete(delete_tool))
        .route("/api/v1/tools/{key}/intents", post(sync_tool_intents))
        .route("/api/v1/agents/{key}/favorite", patch(toggle_agent_favorite))
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
        .merge(backup::create_backup_router())
        .merge(da_query::create_da_query_router())
        .merge(web_search::create_web_search_router())
        .merge(weather::create_weather_router())
        .merge(orch_intents::create_orch_intents_router())
        .merge(intent_catalog::create_intent_catalog_router())
        .merge(leads::create_leads_router())
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
    let params: Vec<SystemParam> = db
        .aql_str("FOR p IN system_params RETURN p")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
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

    col.update_document(
        &key,
        serde_json::json!({
            "param_value": new_value,
            "updated_at": chrono::Utc::now().to_rfc3339(),
        }),
        Default::default(),
    )
    .await
    .map_err(|_| StatusCode::NOT_FOUND)?;

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

    let filtered: Vec<Agent> = match (&user_key, &user_roles) {
        (Some(uk), Some(roles)) => all_agents
            .into_iter()
            .filter(|a| {
                match a.visibility.as_deref().unwrap_or("public") {
                    "public" => true,
                    "private" => a.created_by.as_ref() == Some(uk),
                    "role" => {
                    let agent_roles = a.visibility_roles.as_deref().unwrap_or(&[]);
                        roles.iter().any(|r| agent_roles.contains(r))
                    }
                    _ => true,
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
        "FOR t IN tools FILTER (t.visibility == null || t.visibility == 'public' || t.visibility == 'role' || t.visibility == 'account'){} SORT t.created_at DESC RETURN t",
        tool_filter
    );
    let all_tools: Vec<Tool> = db.aql_str(&query).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let filtered: Vec<Tool> = match (&user_key, &user_roles) {
        (Some(uk), Some(roles)) => all_tools
            .into_iter()
            .filter(|t| {
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
                    _ => true,
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
    let p = providers.into_iter().next().ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(p)))
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
