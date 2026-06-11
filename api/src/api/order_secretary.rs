use crate::config::CONFIG;
use axum::{
    body::Bytes,
    extract::{Path as AxumPath, State},
    http::{HeaderMap, Method, StatusCode, Uri},
    response::IntoResponse,
    routing::any,
    Router,
};
use reqwest::Client;
use std::time::Duration;

pub fn create_order_secretary_router() -> Router {
    let client = Client::builder()
        .timeout(Duration::from_secs(60))
        .build()
        .unwrap();

    Router::new()
        .route("/order-secretary/{*path}", any(proxy_handler))
        .with_state(client)
}

async fn proxy_handler(
    State(client): State<Client>,
    method: Method,
    uri: Uri,
    AxumPath(path): AxumPath<String>,
    headers: HeaderMap,
    body: Bytes,
) -> Result<impl IntoResponse, StatusCode> {
    let query = uri.query().map(|q| format!("?{}", q)).unwrap_or_default();
    let upstream_url = format!(
        "{}/order-secretary/{}",
        CONFIG.ai_services.unified_agents_url.trim_end_matches('/'),
        path,
    );
    let upstream_url = if query.is_empty() {
        upstream_url
    } else {
        format!("{}{}", upstream_url, query)
    };

    let req_method = match method.as_str() {
        "GET" => reqwest::Method::GET,
        "POST" => reqwest::Method::POST,
        "PUT" => reqwest::Method::PUT,
        "PATCH" => reqwest::Method::PATCH,
        "DELETE" => reqwest::Method::DELETE,
        _ => return Err(StatusCode::METHOD_NOT_ALLOWED),
    };

    let mut proxy_req = client.request(req_method, &upstream_url);

    for (key, value) in headers.iter() {
        let key_str = key.as_str().to_lowercase();
        if key_str == "host" || key_str == "connection" || key_str == "content-length" {
            continue;
        }
        if let Ok(v) = value.to_str() {
            proxy_req = proxy_req.header(key.as_str(), v);
        }
    }

    if !body.is_empty() {
        proxy_req = proxy_req.body(body.to_vec());
    }

    let resp = proxy_req.send().await.map_err(|e| {
        eprintln!("order_secretary proxy error: {} -> {}", upstream_url, e);
        StatusCode::BAD_GATEWAY
    })?;

    let status = resp.status();
    let resp_headers = resp.headers().clone();
    let resp_body = resp.bytes().await.map_err(|_| StatusCode::BAD_GATEWAY)?;

    let mut response = axum::response::Response::builder().status(status.as_u16());
    for (key, value) in resp_headers.iter() {
        let key_str = key.as_str();
        if matches!(
            key_str.to_lowercase().as_str(),
            "connection" | "keep-alive" | "transfer-encoding" | "upgrade"
        ) {
            continue;
        }
        if let Ok(v) = value.to_str() {
            response = response.header(key_str, v);
        }
    }

    response
        .body(axum::body::Body::from(resp_body))
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)
}
