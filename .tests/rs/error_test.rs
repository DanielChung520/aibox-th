//! Error types test

use abc_api::error::ApiError;
use axum::http::StatusCode;

#[test]
fn test_api_error_creation() {
    let err = ApiError::new(StatusCode::BAD_REQUEST, "BAD_REQUEST", "Invalid request");
    assert_eq!(err.code, 400);
    assert_eq!(err.error, "BAD_REQUEST");
    assert_eq!(err.message, "Invalid request");
    assert!(err.details.is_none());
}

#[test]
fn test_bad_request() {
    let err = ApiError::bad_request("Missing parameter");
    assert_eq!(err.code, 400);
    assert_eq!(err.error, "BAD_REQUEST");
    assert_eq!(err.message, "Missing parameter");
}

#[test]
fn test_unauthorized() {
    let err = ApiError::unauthorized("Invalid token");
    assert_eq!(err.code, 401);
    assert_eq!(err.error, "UNAUTHORIZED");
}

#[test]
fn test_forbidden() {
    let err = ApiError::forbidden("Access denied");
    assert_eq!(err.code, 403);
    assert_eq!(err.error, "FORBIDDEN");
}

#[test]
fn test_rate_limited() {
    let err = ApiError::rate_limited(100, 60, 30);
    assert_eq!(err.code, 429);
    assert_eq!(err.error, "RATE_LIMITED");
    assert!(err.details.is_some());
    let details = err.details.unwrap();
    assert_eq!(details["limit"], 100);
    assert_eq!(details["window"], 60);
    assert_eq!(details["retry_after"], 30);
}

#[test]
fn test_quota_exceeded() {
    let err = ApiError::quota_exceeded();
    assert_eq!(err.code, 401);
    assert_eq!(err.error, "QUOTA_EXCEEDED");
}

#[test]
fn test_bad_gateway() {
    let err = ApiError::bad_gateway("Upstream error");
    assert_eq!(err.code, 502);
    assert_eq!(err.error, "BAD_GATEWAY");
}

#[test]
fn test_service_unavailable() {
    let err = ApiError::service_unavailable("Service down");
    assert_eq!(err.code, 503);
    assert_eq!(err.error, "SERVICE_UNAVAILABLE");
}

#[test]
fn test_not_found() {
    let err = ApiError::not_found("User");
    assert_eq!(err.code, 404);
    assert_eq!(err.message, "User 不存在");
}

#[test]
fn test_internal_error() {
    let err = ApiError::internal_error("Unexpected error");
    assert_eq!(err.code, 500);
    assert_eq!(err.error, "INTERNAL_ERROR");
}

#[test]
fn test_with_details() {
    let err = ApiError::bad_request("Error").with_details(serde_json::json!({"field": "value"}));
    assert!(err.details.is_some());
}
