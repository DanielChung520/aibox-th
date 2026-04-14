//! Database Module
//!
//! # Description
//! ArangoDB 數據庫連接與操作
//!
//! # Last Update: 2026-03-28 10:22:08
//! # Author: Daniel Chung
//! # Version: 1.1.0

use arangors::client::reqwest::ReqwestClient;
use arangors::{Connection as ArangoConnection, Database};
use chrono::Utc;
use once_cell::sync::OnceCell;
use serde::{Deserialize, Serialize};

static ARANGO_URL: OnceCell<String> = OnceCell::new();
static ARANGO_CREDS: OnceCell<(String, String)> = OnceCell::new();

pub mod knowledge;
pub mod ontology;
pub mod themes;

static DB: OnceCell<Database<ReqwestClient>> = OnceCell::new();

pub async fn init() -> Result<(), String> {
    let url = std::env::var("ARANGODB_URL").unwrap_or_else(|_| "http://localhost:8529".into());
    let username = std::env::var("ARANGODB_USERNAME").unwrap_or_else(|_| "root".into());
    let password = std::env::var("ARANGODB_PASSWORD").unwrap_or_default();
    let db_name = std::env::var("ARANGODB_DATABASE").unwrap_or_else(|_| "abc_desktop".into());

    ARANGO_URL.set(url.clone()).ok();
    ARANGO_CREDS.set((username.clone(), password.clone())).ok();

    let conn = ArangoConnection::establish_jwt(&url, &username, &password)
        .await
        .map_err(|e| format!("ArangoDB connection failed: {e}"))?;

    ensure_database(&conn, &db_name).await?;

    let db = conn
        .db(&db_name)
        .await
        .map_err(|e| format!("Cannot access database '{db_name}': {e}"))?;

    ensure_collections(&db).await?;
    ensure_indexes(&db).await?;
    seed_defaults(&db).await?;

    DB.set(db).map_err(|_| "DB already initialized".to_string())
}

pub fn get_db() -> &'static Database<ReqwestClient> {
    DB.get().expect("Database not initialized")
}

async fn ensure_database(conn: &ArangoConnection, name: &str) -> Result<(), String> {
    let databases = conn
        .accessible_databases()
        .await
        .map_err(|e| format!("Cannot list databases: {e}"))?;
    if !databases.contains_key(name) {
        conn.create_database(name)
            .await
            .map_err(|e| format!("Cannot create database '{name}': {e}"))?;
    }
    Ok(())
}

async fn ensure_collections(db: &Database<ReqwestClient>) -> Result<(), String> {
    let existing: Vec<String> = db
        .accessible_collections()
        .await
        .map_err(|e| format!("Cannot list collections: {e}"))?
        .into_iter()
        .filter(|c| !c.name.starts_with('_'))
        .map(|c| c.name)
        .collect();

    let docs = ["users", "roles", "system_params", "functions", "role_functions", "agents", "tools", "tool_logs", "model_providers", "theme_templates", "knowledge_roots", "knowledge_files", "ontologies", "job_logs", "knowledge_graphs", "knowledge_graph_edges", "chat_sessions", "chat_messages", "orch_intents", "intent_catalog", "leads", "da_tables", "da_expressions"];
    for name in docs {
        if !existing.contains(&name.to_string()) {
            db.create_collection(name)
                .await
                .map_err(|e| format!("Cannot create collection '{name}': {e}"))?;
        }
    }

    // chat_session_files: Edge collection binding session ↔ uploaded files
    let edge_collections = ["chat_session_files"];
    for name in edge_collections {
        if !existing.contains(&name.to_string()) {
            db.create_collection(name)
                .await
                .map_err(|e| format!("Cannot create edge collection '{name}': {e}"))?;
        }
    }

    Ok(())
}

async fn ensure_indexes(_db: &Database<ReqwestClient>) -> Result<(), String> {
    let idx_specs: &[(&str, &[&str])] = &[
        ("chat_messages", &["session_key", "created_at"]),
        ("knowledge_files", &["session_key"]),
        ("job_logs", &["session_key"]),
        ("knowledge_graphs", &["file_id"]),
        ("knowledge_graph_edges", &["file_id"]),
    ];

    let base_url = ARANGO_URL.get().ok_or("ARANGO_URL not set")?;
    let (user, pass) = ARANGO_CREDS.get().ok_or("ARANGO_CREDS not set")?;
    let db_name = std::env::var("ARANGODB_DATABASE").unwrap_or_else(|_| "abc_desktop".into());

    for (col_name, fields) in idx_specs {
        let idx_body = serde_json::json!({
            "type": "persistent",
            "fields": fields,
            "unique": false,
            "sparse": false
        });

        let url = format!("{}/_db/{}/_api/index?collection={}", base_url, db_name, col_name);
        let client = reqwest::Client::new();
        let resp = client
            .post(&url)
            .basic_auth(user, Some(pass))
            .json(&idx_body)
            .send()
            .await
            .map_err(|e| format!("Index HTTP error on '{col_name}': {e}"))?;

        if resp.status().is_success() || resp.status().as_u16() == 409 {
            // 409 = index already exists, OK
        } else {
            let body = resp.text().await.unwrap_or_default();
            return Err(format!("Index creation failed on '{col_name}': {body}"));
        }
    }

    Ok(())
}

async fn ensure_agent_defaults(db: &Database<ReqwestClient>) -> Result<(), String> {
    let _: Vec<serde_json::Value> = db
        .aql_str(
            "FOR a IN agents FILTER a.visibility == null UPDATE a WITH { visibility: 'public', visibility_roles: [], created_by: 'admin' } IN agents OPTIONS { waitForSync: true } RETURN a",
        )
        .await
        .map_err(|e| format!("AQL error: {e}"))?;
    Ok(())
}

async fn ensure_websearch_params(db: &Database<ReqwestClient>) -> Result<(), String> {
    let col = db
        .collection("system_params")
        .await
        .map_err(|e| format!("system_params collection: {e}"))?;

    let defaults: &[(&str, &str, &str)] = &[
        ("web_search.serper_enabled", "false", "boolean"),
        ("web_search.serper_api_key", "", "string"),
        ("web_search.serpapi_enabled", "false", "boolean"),
        ("web_search.serpapi_api_key", "", "string"),
        ("web_search.scraper_enabled", "false", "boolean"),
        ("web_search.scraper_api_key", "", "string"),
        ("web_search.google_cse_enabled", "false", "boolean"),
        ("web_search.google_cse_api_key", "", "string"),
        ("web_search.google_cse_cx", "", "string"),
    ];

    let now = Utc::now().to_rfc3339();
    for (key, value, param_type) in defaults {
        let existing: Vec<serde_json::Value> = db
            .aql_bind_vars(
                "FOR p IN system_params FILTER p.param_key == @k LIMIT 1 RETURN p",
                [("k", serde_json::json!(key))].into(),
            )
            .await
            .map_err(|e| format!("AQL error on '{key}': {e}"))?;

        if existing.is_empty() {
            col.create_document(
                SystemParam {
                    _key: Some(key.to_string()),
                    param_key: key.to_string(),
                    param_value: value.to_string(),
                    param_type: param_type.to_string(),
                    require_restart: false,
                    category: "web_search".to_string(),
                    updated_at: now.clone(),
                },
                Default::default(),
            )
            .await
            .map_err(|e| format!("Seed web_search param '{key}' failed: {e}"))?;
        }
    }
    Ok(())
}

async fn ensure_weather_params(db: &Database<ReqwestClient>) -> Result<(), String> {
    let col = db
        .collection("system_params")
        .await
        .map_err(|e| format!("system_params collection: {e}"))?;

    let defaults: &[(&str, &str, &str)] = &[
        ("weather.openweathermap_enabled", "true", "boolean"),
        ("weather.openweathermap_api_key", "", "string"),
    ];

    let now = Utc::now().to_rfc3339();
    for (key, value, param_type) in defaults {
        let existing: Vec<serde_json::Value> = db
            .aql_bind_vars(
                "FOR p IN system_params FILTER p.param_key == @k LIMIT 1 RETURN p",
                [("k", serde_json::json!(key))].into(),
            )
            .await
            .map_err(|e| format!("AQL error on '{key}': {e}"))?;

        if existing.is_empty() {
            col.create_document(
                SystemParam {
                    _key: Some(key.to_string()),
                    param_key: key.to_string(),
                    param_value: value.to_string(),
                    param_type: param_type.to_string(),
                    require_restart: false,
                    category: "weather".to_string(),
                    updated_at: now.clone(),
                },
                Default::default(),
            )
            .await
            .map_err(|e| format!("Seed weather param '{key}' failed: {e}"))?;
        }
    }
    Ok(())
}

async fn ensure_upload_params(db: &Database<ReqwestClient>) -> Result<(), String> {
    let col = db
        .collection("system_params")
        .await
        .map_err(|e| format!("system_params collection: {e}"))?;

    let defaults: &[(&str, &str, &str)] = &[
        // v5.0 上傳分級限制（bytes）
        ("upload_max_size_general", "5242880", "number"),      // 5 MB
        ("upload_max_size_vip", "52428800", "number"),         // 50 MB
        ("upload_max_size_super_vip", "524288000", "number"),  // 500 MB（系統硬上限）
    ];

    let now = Utc::now().to_rfc3339();
    for (key, value, param_type) in defaults {
        let existing: Vec<serde_json::Value> = db
            .aql_bind_vars(
                "FOR p IN system_params FILTER p.param_key == @k LIMIT 1 RETURN p",
                [("k", serde_json::json!(key))].into(),
            )
            .await
            .map_err(|e| format!("AQL error on '{key}': {e}"))?;

        if existing.is_empty() {
            col.create_document(
                SystemParam {
                    _key: Some(key.to_string()),
                    param_key: key.to_string(),
                    param_value: value.to_string(),
                    param_type: param_type.to_string(),
                    require_restart: false,
                    category: "upload".to_string(),
                    updated_at: now.clone(),
                },
                Default::default(),
            )
            .await
            .map_err(|e| format!("Seed upload param '{key}' failed: {e}"))?;
        }
    }
    Ok(())
}

async fn seed_defaults(db: &Database<ReqwestClient>) -> Result<(), String> {
    seed_roles(db).await?;
    seed_users(db).await?;
    seed_params(db).await?;
    seed_functions(db).await?;
    seed_model_providers(db).await?;
    themes::seed_theme_templates(db).await?;
    knowledge::seed_knowledge(db).await?;
    ontology::seed_ontologies(db).await?;
    ensure_agent_defaults(db).await?;
    ensure_websearch_params(db).await?;
    ensure_weather_params(db).await?;
    ensure_upload_params(db).await?;
    Ok(())
}

async fn seed_roles(db: &Database<ReqwestClient>) -> Result<(), String> {
    let count: serde_json::Value = db
        .aql_str("RETURN LENGTH(roles)")
        .await
        .map_err(|e| format!("AQL error: {e}"))?
        .into_iter()
        .next()
        .unwrap_or(serde_json::Value::Number(0.into()));

    if count.as_u64().unwrap_or(0) > 0 {
        return Ok(());
    }

    let now = Utc::now().to_rfc3339();
    let col = db
        .collection("roles")
        .await
        .map_err(|e| format!("roles collection: {e}"))?;
    col.create_document(
        Role {
            _key: Some("admin".into()),
            name: "系统管理员".into(),
            description: "拥有所有权限".into(),
            created_at: now,
        },
        Default::default(),
    )
    .await
    .map_err(|e| format!("Seed role failed: {e}"))?;
    Ok(())
}

async fn seed_users(db: &Database<ReqwestClient>) -> Result<(), String> {
    let count: serde_json::Value = db
        .aql_str("RETURN LENGTH(users)")
        .await
        .map_err(|e| format!("AQL error: {e}"))?
        .into_iter()
        .next()
        .unwrap_or(serde_json::Value::Number(0.into()));

    if count.as_u64().unwrap_or(0) > 0 {
        return Ok(());
    }

    let col = db
        .collection("users")
        .await
        .map_err(|e| format!("users collection: {e}"))?;
    col.create_document(
        User {
            _key: Some("admin".into()),
            username: "admin".into(),
            password_hash: "$2b$10$Qte4lSw901/2KP3oLhmyiewedoNaHF.2R9AdBmQ24/rKUhj4UO9Ei".into(),
            name: "管理员".into(),
            role_keys: vec!["admin".into()],
            status: "enabled".into(),
            tier: Some("vip".into()),
            created_at: Utc::now().to_rfc3339(),
        },
        Default::default(),
    )
    .await
    .map_err(|e| format!("Seed user failed: {e}"))?;
    Ok(())
}

async fn seed_params(db: &Database<ReqwestClient>) -> Result<(), String> {
    let count: serde_json::Value = db
        .aql_str("RETURN LENGTH(system_params)")
        .await
        .map_err(|e| format!("AQL error: {e}"))?
        .into_iter()
        .next()
        .unwrap_or(serde_json::Value::Number(0.into()));

    if count.as_u64().unwrap_or(0) > 0 {
        return Ok(());
    }

    let col = db
        .collection("system_params")
        .await
        .map_err(|e| format!("system_params collection: {e}"))?;

    // NOTE: theme.mode and theme.primaryColor params have been migrated to the
    // theme_templates collection (see db/themes.rs). Theme configuration is now
    // DB-driven and managed through the ThemeTemplate struct with active template
    // activation via PUT /api/v1/theme-templates/{key}/activate.
    let defaults: &[(&str, &str, &str, bool, &str)] = &[
        ("app.name", "管理系统", "string", true, "basic"),
        ("app.logo", "", "string", true, "basic"),
        ("app.version", "1.0.0", "string", false, "basic"),
        ("app.copyright", "© 2026", "string", true, "basic"),
        ("window.width", "1200", "number", true, "window"),
        ("window.height", "800", "number", true, "window"),
        ("window.minWidth", "800", "number", true, "window"),
        ("window.minHeight", "600", "number", true, "window"),
        ("autoJump.enabled", "true", "boolean", false, "behavior"),
        ("autoJump.delay", "3", "number", false, "behavior"),
        ("autoLogin.enabled", "true", "boolean", false, "behavior"),
        ("autoLogin.days", "2", "number", false, "behavior"),
        ("knowledge.embedding_model", "qwen3-embedding:latest", "string", false, "knowledge"),
        ("knowledge.embedding_dimension", "1024", "number", false, "knowledge"),
        ("knowledge.graph_model", "qwen3-coder:30b", "string", false, "knowledge"),
        ("knowledge.graph_num_predict", "9600", "number", false, "knowledge"),
        ("task_chat.default_provider", "ollama", "string", false, "task_chat"),
        ("task_chat.default_model", "llama3.2:latest", "string", false, "task_chat"),
        ("task_chat.temperature", "0.7", "number", false, "task_chat"),
        ("task_chat.max_tokens", "4096", "number", false, "task_chat"),
        ("task_chat.max_history_messages", "20", "number", false, "task_chat"),
        ("task_chat.greeting_message", "你好！我是你的 AI 工作助理，有什麼可以幫你的嗎？", "string", false, "task_chat"),
        ("task_chat.system_prompt", "你是一個綜合工作協作者，可以天南地北無所不談，協助使用者完成各種工作任務。", "string", false, "task_chat"),
        ("ragic.default_graph_modules", "TRADE", "string", false, "ragic"),
    ];

    let now = Utc::now().to_rfc3339();
    for (key, value, param_type, require_restart, category) in defaults {
        col.create_document(
            SystemParam {
                _key: Some(key.to_string()),
                param_key: key.to_string(),
                param_value: value.to_string(),
                param_type: param_type.to_string(),
                require_restart: *require_restart,
                category: category.to_string(),
                updated_at: now.clone(),
            },
            Default::default(),
        )
        .await
        .map_err(|e| format!("Seed param '{key}' failed: {e}"))?;
    }
    Ok(())
}

async fn seed_functions(db: &Database<ReqwestClient>) -> Result<(), String> {
    let count: serde_json::Value = db
        .aql_str("RETURN LENGTH(functions)")
        .await
        .map_err(|e| format!("AQL error: {e}"))?
        .into_iter()
        .next()
        .unwrap_or(serde_json::Value::Number(0.into()));

    if count.as_u64().unwrap_or(0) > 0 {
        return Ok(());
    }

    let col = db
        .collection("functions")
        .await
        .map_err(|e| format!("functions collection: {e}"))?;

    type FuncRow = (&'static str, &'static str, &'static str, Option<&'static str>, Option<&'static str>, Option<&'static str>, Option<&'static str>, i32);
    let rows: &[FuncRow] = &[
        ("system", "系统设置", "group", None, None, None, None, 1),
        ("system.functions", "功能维护", "sub_function", Some("system"), Some("/app/functions"), Some("ToolOutlined"), None, 1),
        ("system.users", "账户管理", "sub_function", Some("system"), Some("/app/users"), Some("UserOutlined"), None, 2),
        ("system.roles", "角色管理", "sub_function", Some("system"), Some("/app/roles"), Some("TeamOutlined"), None, 3),
        ("system.params", "系统参数", "sub_function", Some("system"), Some("/app/params"), Some("SettingOutlined"), None, 4),
        ("system.functions.list", "功能列表", "tab", Some("system.functions"), None, None, None, 1),
        ("system.functions.create", "新增功能", "tab", Some("system.functions"), None, None, None, 2),
        ("system.users.list", "用户列表", "tab", Some("system.users"), None, None, None, 1),
        ("system.users.create", "新增用户", "tab", Some("system.users"), None, None, None, 2),
        ("system.roles.list", "角色列表", "tab", Some("system.roles"), None, None, None, 1),
        ("system.roles.create", "新增角色", "tab", Some("system.roles"), None, None, None, 2),
        ("system.roles.permissions", "权限分配", "tab", Some("system.roles"), None, None, None, 3),
        ("knowledge", "知识管理", "group", None, None, Some("BookOutlined"), None, 2),
        ("knowledge.ontology", "知识本体列表", "sub_function", Some("knowledge"), Some("/app/knowledge/ontology"), Some("ApartmentOutlined"), None, 1),
        ("knowledge.management", "知识库管理", "sub_function", Some("knowledge"), Some("/app/knowledge/management"), Some("DatabaseOutlined"), None, 2),
    ];

    let now = Utc::now().to_rfc3339();
    for (code, name, ft, pk, path, icon, desc, so) in rows {
        col.create_document(
            Function {
                _key: Some((*code).to_string()),
                code: (*code).to_string(),
                name: (*name).to_string(),
                description: desc.map(|s| s.to_string()),
                function_type: (*ft).to_string(),
                parent_key: pk.map(|s| s.to_string()),
                path: path.map(|s| s.to_string()),
                icon: icon.map(|s| s.to_string()),
                sort_order: *so,
                status: "enabled".to_string(),
                created_at: now.clone(),
            },
            Default::default(),
        )
        .await
        .map_err(|e| format!("Seed function '{code}' failed: {e}"))?;
    }
    Ok(())
}

async fn seed_model_providers(db: &Database<ReqwestClient>) -> Result<(), String> {
    let count: serde_json::Value = db
        .aql_str("RETURN LENGTH(model_providers)")
        .await
        .map_err(|e| format!("AQL error: {e}"))?
        .into_iter()
        .next()
        .unwrap_or(serde_json::Value::Number(0.into()));

    if count.as_u64().unwrap_or(0) > 0 {
        return Ok(());
    }

    let col = db
        .collection("model_providers")
        .await
        .map_err(|e| format!("model_providers collection: {e}"))?;

    let providers: &[ModelProvider] = &[
        ModelProvider {
            _key: Some("ollama".to_string()),
            code: "ollama".to_string(),
            name: "Ollama Local".to_string(),
            description: Some("本地部署的 Ollama LLM".to_string()),
            icon: Some("CloudServerOutlined".to_string()),
            base_url: "http://localhost:11434".to_string(),
            api_key: None,
            status: "enabled".to_string(),
            sort_order: 1,
            models: vec![
                LLMModel { model_id: "llama3.2:latest".to_string(), name: "llama3.2:latest".to_string(), display_name: Some("Llama 3.2".to_string()), context_window: Some(128000), input_cost_per_1k: None, output_cost_per_1k: None, supports_vision: Some(false), temperature: Some(0.7), status: "enabled".to_string() },
            ],
            created_at: Some(Utc::now().to_rfc3339()),
            updated_at: Some(Utc::now().to_rfc3339()),
        },
        ModelProvider {
            _key: Some("openai".to_string()),
            code: "openai".to_string(),
            name: "OpenAI".to_string(),
            description: Some("OpenAI GPT 系列模型".to_string()),
            icon: Some("RobotOutlined".to_string()),
            base_url: "https://api.openai.com/v1".to_string(),
            api_key: None,
            status: "disabled".to_string(),
            sort_order: 2,
            models: vec![
                LLMModel { model_id: "gpt-4o".to_string(), name: "gpt-4o".to_string(), display_name: Some("GPT-4o".to_string()), context_window: Some(128000), input_cost_per_1k: Some(0.005), output_cost_per_1k: Some(0.015), supports_vision: Some(true), temperature: Some(0.7), status: "enabled".to_string() },
                LLMModel { model_id: "gpt-4-turbo".to_string(), name: "gpt-4-turbo".to_string(), display_name: Some("GPT-4 Turbo".to_string()), context_window: Some(128000), input_cost_per_1k: Some(0.01), output_cost_per_1k: Some(0.03), supports_vision: Some(true), temperature: Some(0.7), status: "enabled".to_string() },
                LLMModel { model_id: "gpt-3.5-turbo".to_string(), name: "gpt-3.5-turbo".to_string(), display_name: Some("GPT-3.5 Turbo".to_string()), context_window: Some(16385), input_cost_per_1k: Some(0.0005), output_cost_per_1k: Some(0.0015), supports_vision: Some(false), temperature: Some(0.7), status: "enabled".to_string() },
            ],
            created_at: Some(Utc::now().to_rfc3339()),
            updated_at: Some(Utc::now().to_rfc3339()),
        },
        ModelProvider {
            _key: Some("anthropic".to_string()),
            code: "anthropic".to_string(),
            name: "Anthropic".to_string(),
            description: Some("Anthropic Claude 系列模型".to_string()),
            icon: Some("RobotOutlined".to_string()),
            base_url: "https://api.anthropic.com/v1".to_string(),
            api_key: None,
            status: "disabled".to_string(),
            sort_order: 3,
            models: vec![
                LLMModel { model_id: "claude-3-5-sonnet".to_string(), name: "claude-3-5-sonnet".to_string(), display_name: Some("Claude 3.5 Sonnet".to_string()), context_window: Some(200000), input_cost_per_1k: Some(0.003), output_cost_per_1k: Some(0.015), supports_vision: Some(true), temperature: Some(0.7), status: "enabled".to_string() },
                LLMModel { model_id: "claude-3-opus".to_string(), name: "claude-3-opus".to_string(), display_name: Some("Claude 3 Opus".to_string()), context_window: Some(200000), input_cost_per_1k: Some(0.015), output_cost_per_1k: Some(0.075), supports_vision: Some(true), temperature: Some(0.7), status: "enabled".to_string() },
            ],
            created_at: Some(Utc::now().to_rfc3339()),
            updated_at: Some(Utc::now().to_rfc3339()),
        },
    ];

    for p in providers {
        col.create_document(p.clone(), Default::default())
            .await
            .map_err(|e| format!("Seed provider '{}' failed: {e}", p.code))?;
    }
    Ok(())
}

// ============= Data Models =============

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub username: String,
    pub password_hash: String,
    pub name: String,
    pub role_keys: Vec<String>,
    pub status: String,
    pub tier: Option<String>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Role {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub name: String,
    pub description: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemParam {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub param_key: String,
    pub param_value: String,
    #[serde(default)]
    pub param_type: String,
    #[serde(default)]
    pub require_restart: bool,
    pub category: String,
    #[serde(default)]
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Function {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub code: String,
    pub name: String,
    pub description: Option<String>,
    pub function_type: String,
    pub parent_key: Option<String>,
    pub path: Option<String>,
    pub icon: Option<String>,
    pub sort_order: i32,
    pub status: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoleFunction {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub function_key: String,
    pub role_key: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FunctionRoleAuth {
    pub function_key: String,
    pub role_keys: Vec<String>,
    pub inherited_role_keys: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateParamRequest {
    pub value: Option<String>,
    pub param_value: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateRoleRequest {
    pub name: String,
    pub description: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateRoleRequest {
    pub name: Option<String>,
    pub description: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateFunctionRequest {
    pub code: String,
    pub name: String,
    pub description: String,
    pub function_type: String,
    pub parent_key: Option<String>,
    pub path: Option<String>,
    pub icon: Option<String>,
    pub status: String,
    pub sort_order: Option<i32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateUserRequest {
    pub username: String,
    pub password_hash: String,
    pub name: String,
    pub role_keys: Vec<String>,
    #[serde(default = "default_status")]
    pub status: String,
    #[serde(default = "default_tier")]
    pub tier: String,
}

fn default_status() -> String {
    "enabled".to_string()
}

fn default_tier() -> String {
    "general".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Agent {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub name: String,
    pub description: Option<String>,
    pub icon: Option<String>,
    pub status: String,
    pub usage_count: i32,
    pub group_key: String,
    pub agent_type: Option<String>,
    pub source: Option<String>,
    pub endpoint_url: Option<String>,
    pub api_key: Option<String>,
    pub auth_type: Option<String>,
    pub llm_model: Option<String>,
    pub temperature: Option<f64>,
    pub max_tokens: Option<i32>,
    pub system_prompt: Option<String>,
    pub knowledge_bases: Option<Vec<String>>,
    pub data_sources: Option<Vec<String>>,
    pub tools: Option<Vec<String>>,
    pub opening_lines: Option<Vec<String>>,
    pub capabilities: Option<Vec<String>>,
    pub is_favorite: Option<bool>,
    pub visibility: Option<String>,
    pub visibility_roles: Option<Vec<String>>,
    pub created_by: Option<String>,
    pub updated_by: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateAgentRequest {
    pub name: String,
    pub description: Option<String>,
    pub icon: Option<String>,
    pub status: Option<String>,
    pub group_key: Option<String>,
    pub agent_type: Option<String>,
    pub source: Option<String>,
    pub endpoint_url: Option<String>,
    pub api_key: Option<String>,
    pub auth_type: Option<String>,
    pub llm_model: Option<String>,
    pub temperature: Option<f64>,
    pub max_tokens: Option<i32>,
    pub system_prompt: Option<String>,
    pub knowledge_bases: Option<Vec<String>>,
    pub data_sources: Option<Vec<String>>,
    pub tools: Option<Vec<String>>,
    pub opening_lines: Option<Vec<String>>,
    pub capabilities: Option<Vec<String>>,
    pub visibility: Option<String>,
    pub visibility_roles: Option<Vec<String>>,
    pub created_by: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Tool {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub code: String,
    pub name: String,
    pub description: Option<String>,
    pub tool_type: Option<String>,
    pub icon: Option<String>,
    pub status: String,
    pub usage_count: i32,
    pub group_key: Option<String>,
    pub intent_tags: Option<Vec<String>>,
    pub nl_examples: Option<Vec<String>>,
    pub endpoint_url: Option<String>,
    pub input_schema: Option<serde_json::Value>,
    pub output_schema: Option<serde_json::Value>,
    pub timeout_ms: Option<i32>,
    pub llm_model: Option<String>,
    pub temperature: Option<f64>,
    pub max_tokens: Option<i32>,
    pub auth_config: Option<serde_json::Value>,
    pub visibility: Option<String>,
    pub visibility_roles: Option<Vec<String>>,
    pub visibility_accounts: Option<Vec<String>>,
    pub created_by: Option<String>,
    pub updated_by: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateToolRequest {
    pub code: String,
    pub name: String,
    pub description: Option<String>,
    pub tool_type: Option<String>,
    pub icon: Option<String>,
    pub status: Option<String>,
    pub group_key: Option<String>,
    pub intent_tags: Option<Vec<String>>,
    pub nl_examples: Option<Vec<String>>,
    pub endpoint_url: Option<String>,
    pub input_schema: Option<serde_json::Value>,
    pub output_schema: Option<serde_json::Value>,
    pub timeout_ms: Option<i32>,
    pub llm_model: Option<String>,
    pub temperature: Option<f64>,
    pub max_tokens: Option<i32>,
    pub auth_config: Option<serde_json::Value>,
    pub visibility: Option<String>,
    pub visibility_roles: Option<Vec<String>>,
    pub visibility_accounts: Option<Vec<String>>,
    pub created_by: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolLog {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub tool_key: String,
    pub caller: Option<String>,
    pub input_params: Option<serde_json::Value>,
    pub output_result: Option<serde_json::Value>,
    pub success: bool,
    pub error_message: Option<String>,
    pub duration_ms: Option<i64>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LLMModel {
    pub model_id: String,
    pub name: String,
    pub display_name: Option<String>,
    pub context_window: Option<i32>,
    pub input_cost_per_1k: Option<f64>,
    pub output_cost_per_1k: Option<f64>,
    pub supports_vision: Option<bool>,
    pub temperature: Option<f64>,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelProvider {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub code: String,
    pub name: String,
    pub description: Option<String>,
    pub icon: Option<String>,
    pub base_url: String,
    pub api_key: Option<String>,
    pub status: String,
    pub sort_order: i32,
    pub models: Vec<LLMModel>,
    #[serde(default)]
    pub created_at: Option<String>,
    #[serde(default)]
    pub updated_at: Option<String>,
}

// ============= Chat Data Models =============

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatSession {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub title: Option<String>,
    pub provider: String,
    pub model: String,
    pub status: String,           // "active", "archived"
    pub tags_5w1h: Option<serde_json::Value>,
    pub user_key: String,          // owner user key
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    #[serde(rename = "_key")]
    pub _key: Option<String>,
    pub session_key: String,
    pub role: String,             // "user", "assistant", "system"
    pub content: String,
    pub tokens: Option<i32>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateSessionRequest {
    pub provider: Option<String>,
    pub model: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateSessionRequest {
    pub title: Option<String>,
    pub status: Option<String>,
    pub tags_5w1h: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SendMessageRequest {
    pub content: String,
    pub provider: Option<String>,
    pub model: Option<String>,
    pub temperature: Option<f64>,
    pub max_tokens: Option<i32>,
}
