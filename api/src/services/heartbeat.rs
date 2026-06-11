//! Heartbeat Service
//!
//! # Description
//! 心跳檢測服務，定時檢查 AI 服務健康狀態
//!
//! # Last Update: 2026-03-18 03:30:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use reqwest::Client;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;

pub struct HeartbeatService {
    client: Client,
    services: Arc<RwLock<Vec<ServiceHeartbeat>>>,
    interval_secs: u64,
}

#[derive(Debug, Clone)]
pub struct ServiceHeartbeat {
    pub name: String,
    pub url: String,
    pub healthy: bool,
    pub last_check: String,
    pub latency_ms: Option<u64>,
}

impl HeartbeatService {
    pub fn new(interval_secs: u64) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .unwrap_or_else(|_| Client::new());
        
        Self {
            client,
            services: Arc::new(RwLock::new(Vec::new())),
            interval_secs,
        }
    }

    pub async fn add_service(&self, name: &str, url: &str) {
        let mut services = self.services.write().await;
        services.push(ServiceHeartbeat {
            name: name.to_string(),
            url: url.to_string(),
            healthy: false,
            last_check: "never".to_string(),
            latency_ms: None,
        });
    }

    pub async fn check_all(&self) -> Vec<ServiceHeartbeat> {
        let mut services = self.services.write().await;
        let mut results = Vec::new();

        for service in services.iter_mut() {
            let start = std::time::Instant::now();
            let response = self.client.get(&service.url).send().await;
            let elapsed = start.elapsed().as_millis() as u64;

            service.latency_ms = Some(elapsed);
            service.last_check = chrono::Utc::now().to_rfc3339();

            match response {
                Ok(resp) if resp.status().is_success() => {
                    service.healthy = true;
                }
                _ => {
                    service.healthy = false;
                }
            }

            results.push(service.clone());
        }

        results
    }

    pub async fn get_status(&self) -> Vec<ServiceHeartbeat> {
        let services = self.services.read().await;
        services.clone()
    }

    pub async fn start_monitoring(&self) {
        let services = Arc::clone(&self.services);
        let interval_secs = self.interval_secs;

        tokio::spawn(async move {
            let mut ticker = tokio::time::interval(Duration::from_secs(interval_secs));
            let client = Client::builder()
                .timeout(Duration::from_secs(5))
                .build()
                .unwrap_or_else(|_| Client::new());
            
            loop {
                ticker.tick().await;
                
                let mut services_guard = services.write().await;

                for service in services_guard.iter_mut() {
                    let start = std::time::Instant::now();
                    let result = client.get(&service.url).send().await;
                    let elapsed = start.elapsed().as_millis() as u64;

                    service.latency_ms = Some(elapsed);
                    service.last_check = chrono::Utc::now().to_rfc3339();

                    match result {
                        Ok(resp) if resp.status().is_success() => {
                            service.healthy = true;
                        }
                        _ => {
                            service.healthy = false;
                        }
                    }
                }
            }
        });
    }
}

impl Default for HeartbeatService {
    fn default() -> Self {
        Self::new(30)
    }
}
