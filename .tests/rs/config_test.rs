//! Config test
//!
//! # Last Update: 2026-03-24 19:14:04
//! # Author: Daniel Chung
//! # Version: 1.1.0

use abc_api::config::Config;
use std::env;

fn set_test_env() {
    clear_env();
    env::set_var("JWT_SECRET", "test-secret-key");
    env::set_var("DATABASE_URL", "http://localhost:8529");
    env::set_var("DATABASE_NAME", "test_db");
    env::set_var("DATABASE_USER", "test_user");
    env::set_var("DATABASE_PASSWORD", "test_pass");
    env::set_var("PORT", "3000");
}

fn clear_env() {
    env::remove_var("JWT_SECRET");
    env::remove_var("DATABASE_URL");
    env::remove_var("DATABASE_NAME");
    env::remove_var("DATABASE_USER");
    env::remove_var("DATABASE_PASSWORD");
    env::remove_var("PORT");
    env::remove_var("HOST");
    env::remove_var("RATE_LIMIT_MAX_REQUESTS");
    env::remove_var("RATE_LIMIT_WINDOW_SECONDS");
    env::remove_var("BILLING_FREE_TOKENS_PER_MONTH");
    env::remove_var("BILLING_PRICE_PER_1K_TOKENS");
}

#[test]
fn test_default_config() {
    set_test_env();
    let config = Config::from_env();

    assert_eq!(config.database.url, "http://localhost:8529");
    assert_eq!(config.database.name, "test_db");
    assert_eq!(config.database.user, "test_user");
    assert_eq!(config.jwt.secret, "test-secret-key");
    assert_eq!(config.server.port, 3000);
}

#[test]
fn test_ai_services_default_urls() {
    set_test_env();
    let config = Config::from_env();

    assert_eq!(config.ai_services.aitask_url, "http://localhost:8001");
    assert_eq!(config.ai_services.data_agent_url, "http://localhost:8003");
    assert_eq!(
        config.ai_services.knowledge_agent_url,
        "http://localhost:8007"
    );
    assert_eq!(config.ai_services.mcp_tools_url, "http://localhost:8004");
    assert_eq!(config.ai_services.bpa_mm_agent_url, "http://localhost:8005");
    assert_eq!(config.ai_services.ollama_base_url, "http://localhost:11434");
    assert_eq!(config.ai_services.lm_studio_url, "http://localhost:1234");
}

#[test]
fn test_rate_limit_defaults() {
    set_test_env();
    let config = Config::from_env();

    assert_eq!(config.rate_limit.max_requests, 100);
    assert_eq!(config.rate_limit.window_seconds, 60);
}

#[test]
fn test_billing_defaults() {
    set_test_env();
    let config = Config::from_env();

    assert_eq!(config.billing.free_tokens_per_month, 10000);
    assert_eq!(config.billing.price_per_1k_tokens, 0.001);
}

#[test]
fn test_custom_rate_limit() {
    set_test_env();
    env::set_var("RATE_LIMIT_MAX_REQUESTS", "200");
    env::set_var("RATE_LIMIT_WINDOW_SECONDS", "120");

    let config = Config::from_env();

    assert_eq!(config.rate_limit.max_requests, 200);
    assert_eq!(config.rate_limit.window_seconds, 120);
}

#[test]
fn test_custom_billing() {
    set_test_env();
    env::set_var("BILLING_FREE_TOKENS_PER_MONTH", "50000");
    env::set_var("BILLING_PRICE_PER_1K_TOKENS", "0.002");

    let config = Config::from_env();

    assert_eq!(config.billing.free_tokens_per_month, 50000);
    assert_eq!(config.billing.price_per_1k_tokens, 0.002);
}

#[test]
fn test_server_config() {
    set_test_env();
    env::set_var("HOST", "127.0.0.1");
    env::set_var("PORT", "8080");

    let config = Config::from_env();

    assert_eq!(config.server.host, "127.0.0.1");
    assert_eq!(config.server.port, 8080);
}
