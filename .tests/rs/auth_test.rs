//! Auth test

use abc_api::auth::{create_jwt, verify_jwt};

#[test]
fn test_create_jwt() {
    let token = create_jwt("user123", "testuser", "admin").unwrap();
    assert!(!token.is_empty());
}

#[test]
fn test_verify_valid_jwt() {
    let token = create_jwt("user123", "testuser", "admin").unwrap();
    let result = verify_jwt(&token);
    assert!(result.is_ok());
    let claims = result.unwrap().claims;
    assert_eq!(claims.sub, "user123");
    assert_eq!(claims.username, "testuser");
    assert_eq!(claims.role, "admin");
}

#[test]
fn test_verify_invalid_jwt() {
    let result = verify_jwt("invalid.token.here");
    assert!(result.is_err());
}

#[test]
fn test_verify_empty_token() {
    let result = verify_jwt("");
    assert!(result.is_err());
}

#[test]
fn test_jwt_contains_all_fields() {
    let token = create_jwt("user_key", "username", "role").unwrap();
    let result = verify_jwt(&token).unwrap();
    let claims = result.claims;
    
    assert_eq!(claims.sub, "user_key");
    assert_eq!(claims.username, "username");
    assert_eq!(claims.role, "role");
}
