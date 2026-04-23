//! Chat 協調流程模組
//!
//! # Description
//! 負責送出訊息主流程、意圖路由、LLM fallback 與 5W1H 標記協調
//!
//! # Last Update: 2026-04-11 08:42:17
//! # Author: AI Agent
//! # Version: 1.0.0

use axum::http::{HeaderMap, StatusCode};
use std::fmt::Write as _;

#[allow(deprecated)]
use crate::api::intent::{route_tool_intent, sse_text_to_stream, summarize_text, ToolIntentResult};
use crate::config::CONFIG;
use crate::db::{
    get_db, AssistantContextFocus, AssistantContextIntentHint, AssistantContextPayload,
    AssistantContextRecentAction, ChatMessage, ModelProvider, SendMessageRequest,
};

use super::clients::{call_aitask_chat, call_aitask_graph_chat, call_aitask_tagging};
use super::models::ChatSse;
use super::repo::{extract_user_key_from_headers, get_message_history, get_session_with_messages, get_system_param, insert_message, load_chat_defaults};
use super::sse_proxy::{stream_aitask_response, stream_langgraph_response};

fn push_focus_block(lines: &mut Vec<String>, title: &str, focus: &AssistantContextFocus) {
    let mut parts: Vec<String> = Vec::new();
    if let Some(component) = &focus.component {
        parts.push(format!("組件={component}"));
    }
    if let Some(component_name) = &focus.component_name {
        parts.push(format!("組件名稱={component_name}"));
    }
    if let Some(entity) = &focus.entity {
        parts.push(format!("實體={entity}"));
    }
    if let Some(entity_type) = &focus.entity_type {
        parts.push(format!("實體類型={entity_type}"));
    }
    if let Some(action) = &focus.action {
        parts.push(format!("動作={action}"));
    }
    if let Some(data_summary) = &focus.data_summary {
        parts.push(format!("摘要={data_summary}"));
    }

    if !parts.is_empty() {
        lines.push(format!("- {title}：{}", parts.join("；")));
    }
}

fn format_intent_hints(intent_hints: &[AssistantContextIntentHint]) -> Option<String> {
    if intent_hints.is_empty() {
        return None;
    }

    let mut line = String::new();
    for (index, hint) in intent_hints.iter().enumerate() {
        if index > 0 {
            line.push_str(" ｜ ");
        }
        let _ = write!(
            line,
            "{}（{:.0}%/{}{}）",
            hint.text,
            hint.confidence * 100.0,
            hint.source,
            hint.strategy
                .as_ref()
                .map(|strategy| format!("/{strategy}"))
                .unwrap_or_default()
        );
    }
    Some(line)
}

fn format_recent_actions(recent_actions: &[AssistantContextRecentAction]) -> Option<String> {
    if recent_actions.is_empty() {
        return None;
    }

    let parts: Vec<String> = recent_actions
        .iter()
        .map(|action| {
            action
                .summary
                .clone()
                .unwrap_or_else(|| format!("{} @ {}", action.event_type, action.page))
        })
        .collect();
    Some(parts.join(" ｜ "))
}

fn build_assistant_context_prompt(context: &AssistantContextPayload) -> String {
    let mut lines = vec![
        "以下是使用者當前所在頁面的即時上下文，請優先用它理解『這個頁面 / 這筆資料 / 這個視窗』指的是什麼。若上下文不足，再主動澄清。".to_string(),
        format!(
            "- 當前頁面：{}（{}）",
            context.page.name, context.page.pathname
        ),
    ];

    if let Some(description) = &context.page.description {
        lines.push(format!("- 頁面說明：{description}"));
    }
    if let Some(page_types) = &context.page.page_types {
        if !page_types.is_empty() {
            lines.push(format!("- 頁面類型：{}", page_types.join("、")));
        }
    }
    if let Some(focus) = &context.focus {
        push_focus_block(&mut lines, "當前焦點", focus);
    }
    if let Some(entity) = &context.entity {
        push_focus_block(&mut lines, "當前實體", entity);
    }
    if let Some(modal) = &context.modal {
        let mut modal_line = format!("- 開啟視窗：{}", modal.modal);
        if let Some(mode) = &modal.mode {
            let _ = write!(modal_line, "（模式：{mode}）");
        }
        if let Some(summary) = &modal.summary {
            let _ = write!(modal_line, "；摘要={summary}");
        }
        lines.push(modal_line);
    }
    if let Some(intent_hints) = &context.intent_hints {
        if let Some(line) = format_intent_hints(intent_hints) {
            lines.push(format!("- 意圖線索：{line}"));
        }
    }
    if let Some(recent_actions) = &context.recent_actions {
        if let Some(line) = format_recent_actions(recent_actions) {
            lines.push(format!("- 最近操作：{line}"));
        }
    }

    lines.join("\n")
}

pub async fn handle_send_message(headers: HeaderMap, session_key: String, payload: SendMessageRequest) -> Result<ChatSse, StatusCode> {
    if payload.content.trim().is_empty() {
        return Err(StatusCode::BAD_REQUEST);
    }

    let db = get_db();
    let user_key = extract_user_key_from_headers(&headers);
    let session_data = get_session_with_messages(db, &session_key, &user_key).await?;
    let defaults = load_chat_defaults(db).await?;

    let provider = payload
        .provider
        .clone()
        .unwrap_or_else(|| session_data.session.provider.clone());
    let model = payload
        .model
        .clone()
        .unwrap_or_else(|| session_data.session.model.clone());
    let temperature = payload.temperature.unwrap_or(defaults.temperature);
    let max_tokens = payload.max_tokens.unwrap_or(defaults.max_tokens);

    if provider != session_data.session.provider || model != session_data.session.model {
        let _ = db
            .aql_bind_vars::<serde_json::Value>(
                "UPDATE @key WITH { provider: @provider, model: @model, updated_at: @now } IN chat_sessions",
                [
                    ("key", serde_json::json!(session_key.clone())),
                    ("provider", serde_json::json!(provider.clone())),
                    ("model", serde_json::json!(model.clone())),
                    ("now", serde_json::json!(chrono::Utc::now().to_rfc3339())),
                ]
                .into(),
            )
            .await;
    }

    let providers_raw: Vec<serde_json::Value> = db
        .aql_bind_vars(
            "FOR p IN model_providers FILTER p.code == @code LIMIT 1 RETURN p",
            [("code", serde_json::json!(provider.clone()))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let provider_info = providers_raw
        .into_iter()
        .filter_map(|value| serde_json::from_value::<ModelProvider>(value).ok())
        .next()
        .ok_or(StatusCode::BAD_REQUEST)?;

    let user_msg = ChatMessage {
        _key: Some(uuid::Uuid::new_v4().to_string()),
        session_key: session_key.clone(),
        role: "user".to_string(),
        content: payload.content.clone(),
        tokens: None,
        created_at: chrono::Utc::now().to_rfc3339(),
    };
    insert_message(db, user_msg).await?;

    let history_all = get_message_history(db, &session_key).await?;
    let history_len = history_all.len();
    let history: Vec<ChatMessage> = if history_len > defaults.max_history_messages {
        history_all
            .into_iter()
            .skip(history_len.saturating_sub(defaults.max_history_messages))
            .collect()
    } else {
        history_all
    };

    let context_prompt = payload
        .assistant_context
        .as_ref()
        .map(build_assistant_context_prompt)
        .filter(|prompt| !prompt.is_empty());

    let mut system_prompt = defaults.system_prompt.clone();
    if let Some(context_prompt) = &context_prompt {
        system_prompt.push_str("\n\n[PAGE_AWARE_CONTEXT]\n");
        system_prompt.push_str(context_prompt);
    }

    let mut messages: Vec<serde_json::Value> = vec![serde_json::json!({
        "role": "system",
        "content": system_prompt,
    })];

    let history_for_intent: Vec<serde_json::Value> = history
        .iter()
        .map(|message| serde_json::json!({ "role": message.role, "content": message.content }))
        .collect();

    for message in &history {
        messages.push(serde_json::json!({
            "role": message.role,
            "content": message.content,
        }));
    }

    let orchestrator_mode = get_system_param(db, "task_chat.orchestrator_mode").await.unwrap_or_else(|| "legacy".to_string());

    if orchestrator_mode == "langgraph" {
        let graph_body = serde_json::json!({
            "session_id": session_key,
            "user_id": user_key,
            "message": payload.content,
            "mode": "chat",
            "assistant_context_prompt": context_prompt,
        });
        let response = call_aitask_graph_chat(graph_body).await?;
        return Ok(stream_langgraph_response(response, session_key).await);
    }

    let client = reqwest::Client::new();

    if CONFIG.ai_services.intent_router_enabled {
        let ollama_base_url = if provider == "ollama" {
            provider_info.base_url.clone()
        } else {
            CONFIG.ai_services.ollama_base_url.clone()
        };

        let intent_model = get_system_param(db, "intent.extraction_model")
                .await
                .unwrap_or_else(|| "deepseek-v3.1:671b-cloud".to_string());
        let intent_threshold = get_system_param(db, "intent.match_threshold")
                .await
                .and_then(|v| v.parse::<f64>().ok())
                .unwrap_or(0.45);

        eprintln!(
            "[chat] intent router: threshold={:.4} model={}",
            intent_threshold, intent_model
        );

        let tool_result = route_tool_intent(
            &client,
            &CONFIG.ai_services.data_agent_url,
            &CONFIG.ai_services.mcp_tools_url,
            &ollama_base_url,
            &intent_model,
            &payload.content,
            &history_for_intent,
            intent_threshold,
        )
        .await;

        match &tool_result {
            Ok(Some(result)) => eprintln!(
                "[chat] intent router matched: tool={} score={:.4}",
                result.tool_name, result.score
            ),
            Ok(None) => eprintln!("[chat] intent router: no tool match, falling back to LLM"),
            Err(error) => eprintln!("[chat] intent router error: {:?}, falling back to LLM", error),
        }

        if let Ok(Some(ToolIntentResult {
            tool_name,
            result: tool_data,
            ..
        })) = tool_result
        {
            let sse_text_result = summarize_text(
                &client,
                &ollama_base_url,
                &intent_model,
                &payload.content,
                &tool_name,
                &tool_data,
                &history_for_intent,
            )
            .await;

            match sse_text_result {
                Ok(sse_text) => {
                    let stream_text = sse_text.clone();
                    let persist_text = sse_text;
                    let session_key_for_persist = session_key.clone();
                    tokio::spawn(async move {
                        let db = get_db();
                        let mut full_content = String::new();
                        for line in persist_text.lines() {
                            if let Ok(data) = serde_json::from_str::<serde_json::Value>(line) {
                                if let Some(content) =
                                    data.get("response").and_then(|value| value.as_str())
                                {
                                    full_content.push_str(content);
                                }
                            }
                        }

                        if full_content.is_empty() {
                            return;
                        }

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

                    return Ok(axum::response::sse::Sse::new(sse_text_to_stream(stream_text)));
                }
                Err(error) => {
                    eprintln!("[chat] summarize_text failed: {:?}, falling back to LLM", error);
                }
            }
        }
    }

    let aitask_body = serde_json::json!({
        "messages": messages,
        "model": model,
        "stream": true,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "provider": provider,
        "provider_base_url": provider_info.base_url,
        "api_key": provider_info.api_key,
    });

    let response = call_aitask_chat(aitask_body).await?;
    Ok(stream_aitask_response(response, session_key).await)
}

pub async fn spawn_5w1h_tagging(session_key: String) {
    let db = get_db();

    let defaults = match load_chat_defaults(db).await {
        Ok(defaults) => defaults,
        Err(_) => return,
    };

    let tagging_model = get_system_param(db, "task_chat.tagging_model")
        .await
        .unwrap_or_else(|| "qwen3-coder:30b".to_string());

    let messages = match get_message_history(db, &session_key).await {
        Ok(messages) => messages,
        Err(_) => return,
    };

    if messages.is_empty() {
        return;
    }

    let capped: Vec<&ChatMessage> = if messages.len() > defaults.max_history_messages {
        messages[messages.len().saturating_sub(defaults.max_history_messages)..]
            .iter()
            .collect()
    } else {
        messages.iter().collect()
    };

    let msg_payload: Vec<serde_json::Value> = capped
        .iter()
        .map(|message| serde_json::json!({ "role": message.role, "content": message.content }))
        .collect();

    let body = serde_json::json!({
        "session_key": session_key,
        "messages": msg_payload,
        "model": tagging_model,
    });

    let resp_json = match call_aitask_tagging(body).await {
        Ok(resp_json) => resp_json,
        Err(_) => return,
    };

    let Some(tags) = resp_json.get("tags").cloned() else {
        return;
    };

    let patch = serde_json::json!({
        "tags_5w1h": tags,
        "updated_at": chrono::Utc::now().to_rfc3339(),
    });

    if let Ok(col) = db.collection("chat_sessions").await {
        let _ = col
            .update_document(&session_key, patch, Default::default())
            .await;
    }
}
