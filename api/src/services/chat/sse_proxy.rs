//! Chat SSE 代理模組
//!
//! # Description
//! 封裝 AITask 上游串流解析、事件轉發、訊息累積持久化與 5W1H 後處理
//!
//! # Last Update: 2026-04-24 01:53:38
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

fn done_event() -> Result<Event, std::convert::Infallible> {
    Ok(Event::default().event("chat_done").data(serde_json::json!({ "done": true }).to_string()))
}

fn parse_sse_block(block: &str) -> Option<(String, String)> {
    let mut event_name = None;
    let mut data_lines = Vec::new();

    for line in block.lines() {
        let line = line.trim_end_matches('\r');
        if let Some(value) = line.strip_prefix("event:") {
            event_name = Some(value.trim().to_string());
        } else if let Some(value) = line.strip_prefix("data:") {
            data_lines.push(value.trim().to_string());
        }
    }

    match (event_name, data_lines.is_empty()) {
        (Some(event), false) => Some((event, data_lines.join("\n"))),
        _ => None,
    }
}

fn next_sse_block(buffer: &mut String) -> Option<String> {
    let pos = buffer.find("\n\n").or_else(|| buffer.find("\r\n\r\n"))?;
    let step = if buffer[pos..].starts_with("\r\n\r\n") { 4 } else { 2 };
    let raw = buffer[..pos].to_string();
    buffer.drain(..pos + step);
    Some(raw)
}

fn next_sse_block_bytes(buffer: &mut Vec<u8>) -> Option<Vec<u8>> {
    let lf_pos = buffer.windows(2).position(|window| window == b"\n\n");
    let crlf_pos = buffer.windows(4).position(|window| window == b"\r\n\r\n");

    let (pos, step) = match (lf_pos, crlf_pos) {
        (Some(lf), Some(crlf)) if crlf < lf => (crlf, 4),
        (Some(lf), _) => (lf, 2),
        (None, Some(crlf)) => (crlf, 4),
        (None, None) => return None,
    };

    let raw = buffer[..pos].to_vec();
    buffer.drain(..pos + step);
    Some(raw)
}

fn extract_reasoning_delta(json: &serde_json::Value) -> Option<String> {
    let reasoning_content = json
        .get("choices")
        .and_then(|choices| choices.get(0))
        .and_then(|choice| choice.get("delta"))
        .and_then(|delta| delta.get("reasoning_content"))
        .and_then(|value| value.as_str())
        .filter(|value| !value.is_empty())
        .map(str::to_string);

    let reasoning_details = json
        .get("choices")
        .and_then(|choices| choices.get(0))
        .and_then(|choice| choice.get("delta"))
        .and_then(|delta| delta.get("reasoning_details"))
        .and_then(|value| value.as_array())
        .map(|details| {
            details
                .iter()
                .filter_map(|detail| detail.get("text").and_then(|value| value.as_str()))
                .collect::<String>()
        })
        .filter(|value| !value.is_empty());

    reasoning_content.or(reasoning_details)
}

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
        let mut buffer = Vec::new();
        let mut body = response.bytes_stream();

        while let Some(chunk_result) = body.next().await {
            match chunk_result {
                Ok(chunk) => {
                    buffer.extend_from_slice(&chunk);

                    while let Some(raw_event_bytes) = next_sse_block_bytes(&mut buffer) {
                        let raw_event = String::from_utf8_lossy(&raw_event_bytes).into_owned();

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
                                if let Some(reasoning) = extract_reasoning_delta(&json) {
                                    let payload = serde_json::json!({
                                        "message": { "thinking": reasoning }
                                    });
                                    let _ = event_tx.send(Ok(
                                        Event::default().event("thinking_chunk").data(payload.to_string()),
                                    ));
                                }

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
                                    let _ = event_tx.send(Ok(Event::default().event("chat_chunk").data(data)));
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

pub async fn stream_langgraph_response(response: reqwest::Response, session_key: String) -> ChatSse {
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
        let mut buffer = Vec::new();
        let mut body = response.bytes_stream();

        while let Some(chunk_result) = body.next().await {
            match chunk_result {
                Ok(chunk) => {
                    buffer.extend_from_slice(&chunk);

                    while let Some(raw_event_bytes) = next_sse_block_bytes(&mut buffer) {
                        let raw_event = String::from_utf8_lossy(&raw_event_bytes).into_owned();
                        let Some((event_name, data)) = parse_sse_block(&raw_event) else {
                            continue;
                        };

                        match event_name.as_str() {
                            "chat_chunk" => {
                                let Ok(json) = serde_json::from_str::<serde_json::Value>(&data) else {
                                    continue;
                                };
                                let Some(chunk_text) = json.get("chunk").and_then(|value| value.as_str()) else {
                                    continue;
                                };
                                if chunk_text.is_empty() {
                                    continue;
                                }

                                let _ = content_tx.send(chunk_text.to_string());
                                let payload = serde_json::json!({
                                    "message": { "content": chunk_text }
                                });
                                let _ = event_tx.send(Ok(
                                    Event::default().event("chat_chunk").data(payload.to_string()),
                                ));
                            }
                            "chat_complete" => {
                                let _ = event_tx.send(done_event());
                                return;
                            }
                            "error" => {
                                let _ = event_tx.send(Ok(Event::default().event("chat_error").data(data)));
                                let _ = event_tx.send(done_event());
                                return;
                            }
                            "intent_detected"
                            | "tool_call_start"
                            | "tool_call_result"
                            | "da_query_start"
                            | "da_query_result"
                            | "ka_search_result"
                            | "bpa_step_start" => {
                                let _ = event_tx.send(Ok(Event::default().event(event_name).data(data)));
                            }
                            "heartbeat" => {}
                            _ => {}
                        }
                    }
                }
                Err(_) => {
                    let _ = event_tx.send(Ok(
                        Event::default()
                            .event("chat_error")
                            .data(serde_json::json!({ "error": "upstream_stream_error" }).to_string()),
                    ));
                    let _ = event_tx.send(done_event());
                    return;
                }
            }
        }

        let _ = event_tx.send(done_event());
    });

    let sse_stream: ChatEventStream = Box::pin(UnboundedReceiverStream::new(event_rx));
    Sse::new(sse_stream)
}
