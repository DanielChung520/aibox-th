//! WebSocket 即时通信模块
//!
//! 提供聊天与监控 WebSocket 连接，支持心跳、订阅与消息推送
//!
//! # Last Update: 2026-03-18 10:35:00
//! # Author: Daniel Chung
//! # Version: 1.2.0

use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        ConnectInfo,
    },
    response::IntoResponse,
    routing::get,
    Router,
};
use futures::{sink::SinkExt, stream::StreamExt};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::broadcast;

pub struct WsState {
    pub chat_tx: broadcast::Sender<ChatMessage>,
    pub monitor_tx: broadcast::Sender<MonitorData>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub message: String,
    pub context_id: Option<String>,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MonitorData {
    pub service: String,
    pub status: String,
    pub cpu: f32,
    pub memory: f32,
    pub timestamp: String,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type")]
enum WsClientMessage {
    Chat {
        message: String,
        context_id: Option<String>,
    },
    Heartbeat,
    Subscribe {
        channel: String,
    },
    Unsubscribe {
        channel: String,
    },
}

#[derive(Debug, Serialize)]
#[serde(tag = "type")]
enum WsServerMessage {
    ChatResponse {
        response: String,
        context_id: String,
        tokens: u32,
    },
    ChatChunk {
        chunk: String,
    },
    HeartbeatAck,
    Notification {
        title: String,
        body: String,
    },
    #[allow(dead_code)]
    Error {
        code: String,
        message: String,
    },
    MonitorUpdate {
        data: MonitorData,
    },
}

pub fn create_ws_router() -> Router {
    Router::new()
        .route("/api/v1/ws/chat", get(ws_chat))
        .route("/api/v1/ws/monitor", get(ws_monitor))
        .with_state(create_ws_state())
}

fn create_ws_state() -> Arc<WsState> {
    Arc::new(WsState {
        chat_tx: broadcast::channel(100).0,
        monitor_tx: broadcast::channel(100).0,
    })
}

pub async fn ws_chat(
    ws: WebSocketUpgrade,
    ConnectInfo(addr): ConnectInfo<std::net::SocketAddr>,
) -> impl IntoResponse {
    let state = create_ws_state();
    tracing::info!("WebSocket chat connection from: {}", addr);
    ws.on_upgrade(move |socket| handle_chat_socket(socket, addr, state))
}

async fn handle_chat_socket(socket: WebSocket, addr: std::net::SocketAddr, state: Arc<WsState>) {
    let (mut sender, mut receiver) = socket.split();
    let mut rx = state.chat_tx.subscribe();

    let welcome = WsServerMessage::Notification {
        title: "Connected".to_string(),
        body: "Welcome to AI Chat".to_string(),
    };
    let _ = sender.send(Message::Text(serde_json::to_string(&welcome).unwrap().into())).await;

    let heartbeat_tx = state.chat_tx.clone();
    let heartbeat_handle = tokio::spawn(async move {
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
            let _ = heartbeat_tx.send(ChatMessage {
                message: "heartbeat".to_string(),
                context_id: None,
                timestamp: chrono::Utc::now().to_rfc3339(),
            });
        }
    });

    loop {
        tokio::select! {
            msg = receiver.next() => {
                match msg {
                    Some(Ok(Message::Text(text))) => {
                        if let Ok(client_msg) = serde_json::from_str::<WsClientMessage>(&text) {
                            match client_msg {
                                WsClientMessage::Chat { message, context_id } => {
                                    tracing::info!("Chat message from {}: {}", addr, message);
                                    
                                    let responses = [
                                        "好的，我来帮你处理这个问题。",
                                        "让我分析一下...",
                                        "根据我的理解，你可以尝试以下方案：",
                                        "1. 首先检查配置是否正确",
                                        "2. 然后验证输入数据",
                                        "3. 最后执行操作",
                                        "希望这能帮助你！如有其他问题，请随时告诉我。"
                                    ];
                                    
                                    for (i, chunk) in responses.iter().enumerate() {
                                        let chat_chunk = WsServerMessage::ChatChunk {
                                            chunk: chunk.to_string(),
                                        };
                                        let _ = sender.send(Message::Text(serde_json::to_string(&chat_chunk).unwrap().into())).await;
                                        tokio::time::sleep(tokio::time::Duration::from_millis(100 * i as u64)).await;
                                    }
                                    
                                    let response = WsServerMessage::ChatResponse {
                                        response: "处理完成".to_string(),
                                        context_id: context_id.unwrap_or_default(),
                                        tokens: responses.iter().map(|s| s.len() as u32).sum(),
                                    };
                                    let _ = sender.send(Message::Text(serde_json::to_string(&response).unwrap().into())).await;
                                }
                                WsClientMessage::Heartbeat => {
                                    let ack = WsServerMessage::HeartbeatAck;
                                    let _ = sender.send(Message::Text(serde_json::to_string(&ack).unwrap().into())).await;
                                }
                                WsClientMessage::Subscribe { channel } => {
                                    tracing::info!("Client subscribed to channel: {}", channel);
                                    let notif = WsServerMessage::Notification {
                                        title: "Subscribed".to_string(),
                                        body: format!("Successfully subscribed to {}", channel),
                                    };
                                    let _ = sender.send(Message::Text(serde_json::to_string(&notif).unwrap().into())).await;
                                }
                                WsClientMessage::Unsubscribe { channel } => {
                                    tracing::info!("Client unsubscribed from channel: {}", channel);
                                }
                            }
                        }
                    }
                    Some(Ok(Message::Close(_))) | None => {
                        tracing::info!("WebSocket chat connection closed: {}", addr);
                        break;
                    }
                    Some(Ok(Message::Ping(data))) => {
                        let _ = sender.send(Message::Pong(data)).await;
                    }
                    _ => {}
                }
            }
            broadcast_msg = rx.recv() => {
                if let Ok(msg) = broadcast_msg {
                    if msg.message == "heartbeat" {
                        let ack = WsServerMessage::HeartbeatAck;
                        let _ = sender.send(Message::Text(serde_json::to_string(&ack).unwrap().into())).await;
                    }
                }
            }
        }
    }

    heartbeat_handle.abort();
    tracing::info!("WebSocket chat handler finished for: {}", addr);
}

pub async fn ws_monitor(
    ws: WebSocketUpgrade,
    ConnectInfo(addr): ConnectInfo<std::net::SocketAddr>,
) -> impl IntoResponse {
    let state = create_ws_state();
    tracing::info!("WebSocket monitor connection from: {}", addr);
    ws.on_upgrade(move |socket| handle_monitor_socket(socket, addr, state))
}

async fn handle_monitor_socket(socket: WebSocket, addr: std::net::SocketAddr, state: Arc<WsState>) {
    let (mut sender, mut receiver) = socket.split();
    let mut rx = state.monitor_tx.subscribe();

    let welcome = WsServerMessage::Notification {
        title: "Monitor Connected".to_string(),
        body: "Monitoring service status".to_string(),
    };
    let _ = sender.send(Message::Text(serde_json::to_string(&welcome).unwrap().into())).await;

    let monitor_tx = state.monitor_tx.clone();
    let monitor_handle = tokio::spawn(async move {
        let services = vec!["AITask", "DataQuery", "KnowledgeAssets", "MCPTools", "BPA"];
        
        for _ in 0..100 {
            for service in &services {
                let data = MonitorData {
                    service: service.to_string(),
                    status: if rand_simple() > 0.1 { "healthy".to_string() } else { "warning".to_string() },
                    cpu: rand_simple() * 100.0,
                    memory: rand_simple() * 100.0,
                    timestamp: chrono::Utc::now().to_rfc3339(),
                };
                let _ = monitor_tx.send(data);
                tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
            }
        }
    });

    loop {
        tokio::select! {
            msg = receiver.next() => {
                match msg {
                    Some(Ok(Message::Text(text))) => {
                        if let Ok(WsClientMessage::Heartbeat) = serde_json::from_str::<WsClientMessage>(&text) {
                            let ack = WsServerMessage::HeartbeatAck;
                            let _ = sender.send(Message::Text(serde_json::to_string(&ack).unwrap().into())).await;
                        }
                    }
                    Some(Ok(Message::Close(_))) | None => {
                        tracing::info!("WebSocket monitor connection closed: {}", addr);
                        break;
                    }
                    Some(Ok(Message::Ping(data))) => {
                        let _ = sender.send(Message::Pong(data)).await;
                    }
                    _ => {}
                }
            }
            broadcast_msg = rx.recv() => {
                if let Ok(data) = broadcast_msg {
                    let update = WsServerMessage::MonitorUpdate { data };
                    let _ = sender.send(Message::Text(serde_json::to_string(&update).unwrap().into())).await;
                }
            }
        }
    }

    monitor_handle.abort();
    tracing::info!("WebSocket monitor handler finished for: {}", addr);
}

fn rand_simple() -> f32 {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .subsec_nanos();
    (nanos % 1000) as f32 / 1000.0
}
