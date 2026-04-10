//! Chat SSE 代理模組
//!
//! # Description
//! 封裝 AITask 上游串流解析、事件轉發、訊息累積持久化與 5W1H 後處理
//!
//! # Last Update: 2026-04-11 02:46:07
//! # Author: AI Agent
//! # Version: 1.0.0

use axum::response::sse::{Event, Sse};
use futures::StreamExt;
use tokio::sync::mpsc;
use tokio_stream::wrappers::UnboundedReceiverStream;

use crate::db::{get_db, ChatMessage};

use super::models::{ChatEventStream, ChatSse};
use super::orchestrator::spawn_5w1h_tagging;
use super::repo::insert_message;

pub async fn stream_aitask_response(response: reqwest::Response, session_key: String) -> ChatSse {
    let (content_tx, mut content_rx) = mpsc::unbounded_channel::<String>();
    let session_key_for_persist = session_key.clone();

    tokio::spawn(async move {
        let mut full_content = String::new();
        while let Some(chunk) = content_rx.recv().await {
            full_content.push_str(&chunk);
        }

        if full_content.is_empty() {
            return;
        }

        let db = get_db();
        let msg = ChatMessage {
            _key: Some(uuid::Uuid::new_v4().to_string()),
            session_key: session_key_for_persist.clone(),
            role: "assistant".to_string(),
            content: full_content,
            tokens: None,
            created_at: chrono::Utc::now().to_rfc3339(),
        };

        if insert_message(db, msg).await.is_ok() {
            spawn_5w1h_tagging(session_key_for_persist).await;
        }
    });

    let (event_tx, event_rx) = mpsc::unbounded_channel::<Result<Event, std::convert::Infallible>>();

    tokio::spawn(async move {
        let mut buffer = String::new();
        let mut body = response.bytes_stream();

        while let Some(chunk_result) = body.next().await {
            match chunk_result {
                Ok(chunk) => {
                    let text = String::from_utf8_lossy(&chunk);
                    buffer.push_str(&text);

                    while let Some(pos) = buffer.find("\n\n") {
                        let raw_event = buffer[..pos].to_string();
                        buffer.drain(..pos + 2);

                        for line in raw_event.lines() {
                            let Some(data) = line
                                .strip_prefix("data:")
                                .map(str::trim)
                                .filter(|value| !value.is_empty())
                            else {
                                continue;
                            };

                            if data == "[DONE]" {
                                let _ = event_tx.send(Ok(
                                    Event::default()
                                        .event("chat_done")
                                        .data(serde_json::json!({ "done": true }).to_string()),
                                ));
                                return;
                            }

                            if let Ok(json) = serde_json::from_str::<serde_json::Value>(data) {
                                let delta = json
                                    .get("message")
                                    .and_then(|message| message.get("content"))
                                    .and_then(|value| value.as_str())
                                    .or_else(|| {
                                        json.get("choices")
                                            .and_then(|choices| choices.get(0))
                                            .and_then(|choice| choice.get("delta"))
                                            .and_then(|delta| delta.get("content"))
                                            .and_then(|value| value.as_str())
                                    });

                                if let Some(delta) = delta.filter(|value| !value.is_empty()) {
                                    let _ = content_tx.send(delta.to_string());
                                }

                                let is_done =
                                    json.get("done").and_then(|value| value.as_bool()) == Some(true);
                                let is_finish = json
                                    .get("choices")
                                    .and_then(|choices| choices.get(0))
                                    .and_then(|choice| choice.get("finish_reason"))
                                    .and_then(|value| value.as_str())
                                    == Some("stop");

                                if is_done || is_finish {
                                    let _ = event_tx.send(Ok(
                                        Event::default()
                                            .event("chat_done")
                                            .data(serde_json::json!({ "done": true }).to_string()),
                                    ));
                                    return;
                                }

                                let _ = event_tx.send(Ok(Event::default().event("chat_chunk").data(data)));
                            }
                        }
                    }
                }
                Err(_) => {
                    let _ = event_tx.send(Ok(
                        Event::default()
                            .event("chat_error")
                            .data(serde_json::json!({ "error": "upstream_stream_error" }).to_string()),
                    ));
                    let _ = event_tx.send(Ok(
                        Event::default()
                            .event("chat_done")
                            .data(serde_json::json!({ "done": true }).to_string()),
                    ));
                    return;
                }
            }
        }

        let _ = event_tx.send(Ok(
            Event::default()
                .event("chat_done")
                .data(serde_json::json!({ "done": true }).to_string()),
        ));
    });

    let sse_stream: ChatEventStream = Box::pin(UnboundedReceiverStream::new(event_rx));
    Sse::new(sse_stream)
}
