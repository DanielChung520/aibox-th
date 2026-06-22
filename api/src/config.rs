//! 配置模組
//!
//! # Description
//! 定義所有環境變數配置，包含資料庫、JWT、AI服務、速率限制、計費等配置
//!
//! # Last Update: 2026-03-23 18:55:00
//! # Author: Daniel Chung
//! # Version: 1.1.0

use once_cell::sync::Lazy;
use serde::Deserialize;
use std::env;

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    pub database: DatabaseConfig,
    pub jwt: JwtConfig,
    pub ai_services: AiServicesConfig,
    pub rate_limit: RateLimitConfig,
    pub billing: BillingConfig,
    pub server: ServerConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct DatabaseConfig {
    pub url: String,
    pub name: String,
    pub user: String,
    pub password: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct JwtConfig {
    pub secret: String,
    pub expiration_hours: i64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct AiServicesConfig {
    pub aitask_url: String,
    pub data_agent_url: String,
    pub knowledge_agent_url: String,
    pub mcp_tools_url: String,
    pub bpa_mm_agent_url: String,
    pub unified_agents_url: String,
    pub aiq_agent_url: String,
    pub ollama_base_url: String,
    pub lm_studio_url: String,
    pub qdrant_url: String,
    pub seaweed_aibox_url: String,
    pub seaweed_user: String,
    pub seaweed_pass: String,
    pub internal_token: String,
    pub intent_router_enabled: bool,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RateLimitConfig {
    pub max_requests: u32,
    pub window_seconds: u64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct BillingConfig {
    pub free_tokens_per_month: u64,
    pub price_per_1k_tokens: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ServerConfig {
    pub port: u16,
    pub host: String,
    pub external_url: String,
}

impl Config {
    pub fn from_env() -> Self {
        Self {
            database: DatabaseConfig {
                url: env::var("ARANGODB_URL")
                    .unwrap_or_else(|_| "http://localhost:8529".to_string()),
                name: env::var("ARANGODB_DATABASE").unwrap_or_else(|_| "abc_desktop".to_string()),
                user: env::var("ARANGODB_USERNAME").unwrap_or_else(|_| "root".to_string()),
                password: env::var("ARANGODB_PASSWORD").expect("ARANGODB_PASSWORD must be set"),
            },
            jwt: JwtConfig {
                secret: env::var("JWT_SECRET").expect("JWT_SECRET is required"),
                expiration_hours: env::var("JWT_EXPIRATION_HOURS")
                    .unwrap_or_else(|_| "24".to_string())
                    .parse()
                    .unwrap_or(24),
            },
            ai_services: AiServicesConfig {
                aitask_url: env::var("AITASK_URL")
                    .unwrap_or_else(|_| "http://localhost:8001".to_string()),
                data_agent_url: env::var("DATA_AGENT_URL")
                    .unwrap_or_else(|_| "http://localhost:8003".to_string()),
                knowledge_agent_url: env::var("KNOWLEDGE_AGENT_URL")
                    .unwrap_or_else(|_| "http://localhost:8007".to_string()),
                mcp_tools_url: env::var("MCP_TOOLS_URL")
                    .unwrap_or_else(|_| "http://localhost:8004".to_string()),
                bpa_mm_agent_url: env::var("BPA_MM_AGENT_URL")
                    .unwrap_or_else(|_| "http://localhost:8005".to_string()),
                unified_agents_url: env::var("UNIFIED_AGENTS_URL")
                    .unwrap_or_else(|_| "http://localhost:8011".to_string()),
                aiq_agent_url: env::var("AIQ_AGENT_URL")
                    .unwrap_or_else(|_| "http://localhost:8009".to_string()),
                ollama_base_url: env::var("OLLAMA_BASE_URL")
                    .unwrap_or_else(|_| "http://localhost:11434".to_string()),
                lm_studio_url: env::var("LM_STUDIO_URL")
                    .unwrap_or_else(|_| "http://localhost:1234".to_string()),
                qdrant_url: env::var("QDRANT_URL")
                    .unwrap_or_else(|_| "http://localhost:6333".to_string()),
                seaweed_aibox_url: env::var("SEAWEED_AIBOX_URL")
                    .unwrap_or_else(|_| "http://localhost:8888".to_string()),
                seaweed_user: env::var("SEAWEED_USER").unwrap_or_default(),
                seaweed_pass: env::var("SEAWEED_PASS").unwrap_or_default(),
                internal_token: env::var("INTERNAL_SERVICE_TOKEN").unwrap_or_default(),
                intent_router_enabled: env::var("INTENT_ROUTER_ENABLED")
                    .unwrap_or_else(|_| "true".to_string())
                    .parse()
                    .unwrap_or(true),
            },
            rate_limit: RateLimitConfig {
                max_requests: env::var("RATE_LIMIT_MAX_REQUESTS")
                    .unwrap_or_else(|_| "100".to_string())
                    .parse()
                    .unwrap_or(100),
                window_seconds: env::var("RATE_LIMIT_WINDOW_SECONDS")
                    .unwrap_or_else(|_| "60".to_string())
                    .parse()
                    .unwrap_or(60),
            },
            billing: BillingConfig {
                free_tokens_per_month: env::var("BILLING_FREE_TOKENS_PER_MONTH")
                    .unwrap_or_else(|_| "10000".to_string())
                    .parse()
                    .unwrap_or(10000),
                price_per_1k_tokens: env::var("BILLING_PRICE_PER_1K_TOKENS")
                    .unwrap_or_else(|_| "0.001".to_string())
                    .parse()
                    .unwrap_or(0.001),
            },
            server: ServerConfig {
                port: env::var("PORT")
                    .unwrap_or_else(|_| "6500".to_string())
                    .parse()
                    .unwrap_or(6500),
                host: env::var("HOST").unwrap_or_else(|_| "127.0.0.1".to_string()),
                external_url: env::var("EXTERNAL_URL").unwrap_or_else(|_| "https://eeaapi.ent4i.com".to_string()),
            },
        }
    }
}

pub static CONFIG: Lazy<Config> = Lazy::new(Config::from_env);
