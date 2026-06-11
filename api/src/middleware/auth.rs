//! JWT 認證中間件
//!
//! # Description
//! 實現 JWT 驗證中間件，從請求頭提取並驗證 JWT Token，提取用戶信息
//!
//! # Last Update: 2026-03-18 02:15:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use crate::auth::verify_jwt;
use crate::error::ApiError;
use crate::auth::Claims;
use axum::{
    extract::Request,
    http::header::AUTHORIZATION,
    middleware::Next,
    response::Response,
};
use std::sync::Arc;

#[derive(Clone)]
pub struct AuthState {
    pub claims: Claims,
}

pub async fn jwt_auth_middleware(
    mut req: Request,
    next: Next,
) -> Result<Response, ApiError> {
    let token = req
        .headers()
        .get(AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or_else(|| ApiError::unauthorized("Missing or invalid Authorization header"))?;

    let token_data = verify_jwt(token).map_err(|e| ApiError::unauthorized(&e))?;

    let claims = token_data.claims;
    if claims.is_expired() {
        return Err(ApiError::unauthorized("Token expired"));
    }

    req.extensions_mut().insert(Arc::new(AuthState { claims }));
    
    Ok(next.run(req).await)
}

pub fn extract_claims(req: &Request) -> Result<Arc<AuthState>, ApiError> {
    req.extensions()
        .get::<Arc<AuthState>>()
        .cloned()
        .ok_or_else(|| ApiError::unauthorized("No authentication context"))
}
