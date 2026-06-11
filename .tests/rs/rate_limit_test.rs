//! Rate limit test

use abc_api::middleware::rate_limit::{RateLimitConfig, RateLimiter};

#[tokio::test]
async fn test_rate_limiter_allows_requests_under_limit() {
    let config = RateLimitConfig {
        max_requests: 5,
        window_secs: 60,
    };
    let limiter = RateLimiter::new(config);

    for _ in 0..5 {
        let result = limiter.check_rate_limit("test_key").await;
        assert!(result.is_ok());
    }
}

#[tokio::test]
async fn test_rate_limiter_blocks_requests_over_limit() {
    let config = RateLimitConfig {
        max_requests: 3,
        window_secs: 60,
    };
    let limiter = RateLimiter::new(config);

    for _ in 0..3 {
        limiter.check_rate_limit("test_key").await.unwrap();
    }

    let result = limiter.check_rate_limit("test_key").await;
    assert!(result.is_err());
    let err = result.unwrap_err();
    assert_eq!(err.code, 429);
}

#[tokio::test]
async fn test_rate_limiter_different_keys() {
    let config = RateLimitConfig {
        max_requests: 2,
        window_secs: 60,
    };
    let limiter = RateLimiter::new(config);

    assert!(limiter.check_rate_limit("key1").await.is_ok());
    assert!(limiter.check_rate_limit("key2").await.is_ok());
    assert!(limiter.check_rate_limit("key1").await.is_ok());
    assert!(limiter.check_rate_limit("key2").await.is_ok());
    
    assert!(limiter.check_rate_limit("key1").await.is_err());
    assert!(limiter.check_rate_limit("key2").await.is_err());
}

#[test]
fn test_rate_limit_config_default() {
    let config = RateLimitConfig::default();
    assert_eq!(config.max_requests, 100);
    assert_eq!(config.window_secs, 60);
}

#[test]
fn test_rate_limit_config_custom() {
    let config = RateLimitConfig {
        max_requests: 200,
        window_secs: 120,
    };
    assert_eq!(config.max_requests, 200);
    assert_eq!(config.window_secs, 120);
}
