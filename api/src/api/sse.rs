//! SSE (Server-Sent Events) 即时推送模块
//!
//! 提供 SSE 接口用于实时推送 AI 响应、通知和事件
//!
//! # Last Update: 2026-03-18 10:00:00
//! # Author: Daniel Chung
//! # Version: 1.0.0

use axum::{
    extract::Path,
    response::sse::{Event, Sse},
    routing::get,
    Router,
};
use chrono::Utc;
use futures::{stream, Stream, StreamExt};
use std::{collections::HashMap, convert::Infallible, sync::Arc};
use tokio::sync::broadcast;

/// SSE 事件结构
#[derive(Debug, Clone, serde::Serialize)]
pub struct SseEvent {
    /// 事件类型: chat_chunk, chat_done, notification, heartbeat, error
    pub event: String,
    /// JSON 数据
    pub data: String,
    /// 事件 ID (用于断点重连)
    pub id: Option<String>,
    /// 重连间隔 (毫秒)
    pub retry: Option<u64>,
}

// 全局广播通道 (用于演示，實際應從外部注入)
lazy_static::lazy_static! {
    static ref BROADCAST_TX: Arc<broadcast::Sender<SseEvent>> = {
        let (tx, _) = broadcast::channel(100);
        Arc::new(tx)
    };
}

// Session-scoped broadcast channels for file status events
lazy_static::lazy_static! {
    static ref FILE_BROADCAST_TXS: Arc<std::sync::Mutex<HashMap<String, broadcast::Sender<SseEvent>>>> = {
        Arc::new(std::sync::Mutex::new(HashMap::new()))
    };
}

const FILE_BROADCAST_CAPACITY: usize = 50;

/// Get or create a broadcast sender for a session's file events
pub fn get_or_create_file_broadcast_tx(session_key: &str) -> broadcast::Sender<SseEvent> {
    let mut txs = FILE_BROADCAST_TXS.lock().unwrap();
    if let Some(tx) = txs.get(session_key) {
        return tx.clone();
    }
    let (tx, _) = broadcast::channel(FILE_BROADCAST_CAPACITY);
    txs.insert(session_key.to_string(), tx.clone());
    tx
}

/// 创建 SSE 路由
pub fn create_sse_router() -> Router {
    Router::new()
        .route("/api/v1/sse/chat/{context_id}", get(sse_chat))
        .route("/api/v1/sse/events", get(sse_events))
        .route("/api/v1/sse/notifications", get(sse_notifications))
        .route("/api/v1/sse/session-files/{session_key}", get(sse_session_files))
}

/// SSE Chat 流 - 对应指定 context_id 的对话流
/// GET /api/v1/sse/chat/{context_id}
pub async fn sse_chat(
    Path(context_id): Path<String>,
) -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
    let rx = BROADCAST_TX.subscribe();

    let mut initial_events: Vec<Result<Event, Infallible>> = vec![Ok(
        Event::default().event("connected").data(
            serde_json::json!({
                "context_id": context_id.clone(),
                "timestamp": Utc::now().to_rfc3339(),
                "message": "Connected to chat stream"
            })
            .to_string(),
        ),
    )];

    for (i, chunk) in ["你好", "，我是", "AI 助手", "。有什么", "可以帮助", "你的吗？"]
        .iter()
        .enumerate()
    {
        initial_events.push(Ok(
            Event::default()
                .event("chat_chunk")
                .id(format!("{}-{}", context_id, i))
                .data(
                    serde_json::json!({
                        "chunk": chunk,
                        "context_id": context_id,
                        "index": i
                    })
                    .to_string(),
                ),
        ));
    }

    initial_events.push(Ok(
        Event::default().event("chat_done").data(
            serde_json::json!({
                "context_id": context_id,
                "timestamp": Utc::now().to_rfc3339()
            })
            .to_string(),
        ),
    ));

    let initial_stream = stream::iter(initial_events);
    let heartbeat_stream = stream::unfold(rx, |mut rx| async move {
        tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;

        let event = if let Ok(event) = rx.try_recv() {
            Event::default().event(event.event).data(event.data)
        } else {
            Event::default().event("heartbeat").data(
                serde_json::json!({
                    "timestamp": Utc::now().to_rfc3339()
                })
                .to_string(),
            )
        };

        Some((Ok(event), rx))
    });

    Sse::new(initial_stream.chain(heartbeat_stream))
}

/// SSE Events - 通用事件流
/// GET /api/v1/sse/events
pub async fn sse_events() -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
    let initial_stream = stream::iter(vec![Ok(
        Event::default().event("init").data(
            serde_json::json!({
                "timestamp": Utc::now().to_rfc3339(),
                "message": "SSE connection established"
            })
            .to_string(),
        ),
    )]);
    let heartbeat_stream = stream::unfold((), |_| async {
        tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;

        Some((
            Ok(Event::default().event("heartbeat").data(
                serde_json::json!({
                    "timestamp": Utc::now().to_rfc3339()
                })
                .to_string(),
            )),
            (),
        ))
    });

    Sse::new(initial_stream.chain(heartbeat_stream))
}

/// SSE Notifications - 系统通知流
/// GET /api/v1/sse/notifications
pub async fn sse_notifications() -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
    let initial_stream = stream::iter(vec![Ok(
        Event::default().event("notification").data(
            serde_json::json!({
                "title": "Connected",
                "body": "Successfully subscribed to notifications",
                "timestamp": Utc::now().to_rfc3339(),
                "level": "info"
            })
            .to_string(),
        ),
    )]);
    let heartbeat_stream = stream::unfold((), |_| async {
        tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;

        Some((
            Ok(Event::default().event("heartbeat").data(
                serde_json::json!({
                    "timestamp": Utc::now().to_rfc3339()
                })
                .to_string(),
            )),
            (),
        ))
    });

    Sse::new(initial_stream.chain(heartbeat_stream))
}

/// 广播 SSE 事件到所有订阅者
pub fn broadcast_sse_event(event: SseEvent) {
    let _ = BROADCAST_TX.send(event);
}

/// Broadcast a file_status event to the session's broadcast channel
pub fn broadcast_file_status_event(session_key: &str, payload: serde_json::Value) {
    let tx = get_or_create_file_broadcast_tx(session_key);
    let event = SseEvent {
        event: "file_status".to_string(),
        data: payload.to_string(),
        id: None,
        retry: Some(5000),
    };
    let _ = tx.send(event);
}

/// SSE stream for session file status events
pub async fn sse_session_files(
    Path(session_key): Path<String>,
) -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
    let tx = get_or_create_file_broadcast_tx(&session_key);
    let rx = tx.subscribe();

    let initial_stream = stream::iter(vec![Ok(
        Event::default().event("connected").data(
            serde_json::json!({
                "session_key": session_key,
                "timestamp": Utc::now().to_rfc3339(),
                "message": "Subscribed to file status events"
            })
            .to_string(),
        ),
    )]);

    let event_stream = stream::unfold(rx, move |mut rx| async move {
        match rx.recv().await {
            Ok(event) => Some((
                Ok(Event::default().event(&event.event).data(&event.data)),
                rx,
            )),
            Err(broadcast::error::RecvError::Lagged(n)) => {
                Some((
                    Ok(Event::default()
                        .event("heartbeat")
                        .data(format!(r#"{{"lagged_events":{}}}"#, n))),
                    rx,
                ))
            }
            Err(broadcast::error::RecvError::Closed) => None,
        }
    });

    let heartbeat_stream = stream::unfold((), |_| async {
        tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
        Some((
            Ok(Event::default()
                .event("heartbeat")
                .data(serde_json::json!({ "timestamp": Utc::now().to_rfc3339() }).to_string())),
            (),
        ))
    });

    Sse::new(
        initial_stream
            .chain(event_stream)
            .chain(heartbeat_stream),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sse_event_serialization() {
        let event = SseEvent {
            event: "chat_chunk".to_string(),
            data: r#"{"chunk": "Hello"}"#.to_string(),
            id: Some("1".to_string()),
            retry: Some(5000),
        };

        let json = serde_json::to_string(&event).unwrap();
        assert!(json.contains("chat_chunk"));
        assert!(json.contains("Hello"));
    }
}
