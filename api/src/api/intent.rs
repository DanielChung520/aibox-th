//! Intent Router - 意圖檢測 + 工具路由
//!
//! # Last Update: 2026-04-11 00:39:07
//! # Author: Daniel Chung
//! # Version: 1.2.0

use std::collections::HashMap;
use std::pin::Pin;

use axum::response::sse::Event;
use futures::Stream;
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[allow(dead_code)]
#[derive(Debug)]
pub enum IntentError {
    Reqwest(reqwest::Error),
    Serde(serde_json::Error),
    NoToolMatch,
    ToolExecutionFailed(String),
    OllamaError(String),
}

impl From<reqwest::Error> for IntentError {
    fn from(e: reqwest::Error) -> Self {
        IntentError::Reqwest(e)
    }
}

impl From<serde_json::Error> for IntentError {
    fn from(e: serde_json::Error) -> Self {
        IntentError::Serde(e)
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct IntentMatchResult {
    intent_id: String,
    score: f64,
    #[serde(rename = "intent_data")]
    intent_data: IntentData,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Deserialize)]
struct IntentData {
    #[serde(rename = "intent_type", default)]
    intent_type: String,
    #[serde(rename = "tool_name", default)]
    tool_name: String,
    #[serde(rename = "generation_strategy", default)]
    generation_strategy: String,
    #[serde(rename = "nl_examples", default)]
    nl_examples: Vec<String>,
    #[serde(rename = "description", default)]
    description: String,
}

#[allow(dead_code)]
#[derive(Debug, Clone, Deserialize)]
struct IntentMatchResponse {
    query: String,
    matches: Vec<IntentMatchResult>,
    #[serde(rename = "best_match", default)]
    best_match: Option<IntentMatchResult>,
}

#[derive(Debug, Clone, Serialize)]
struct ToolCall {
    tool: String,
    parameters: HashMap<String, Value>,
}

pub async fn detect_intent(
    client: &reqwest::Client,
    intent_rag_url: &str,
    query: &str,
    threshold: f64,
) -> Result<Option<(IntentMatchResult, String)>, IntentError> {
    let url = format!("{}/intent-rag/orchestrator/intent/match", intent_rag_url);
    let body = serde_json::json!({"query": query, "top_k": 3});

    let resp = client
        .post(&url)
        .json(&body)
        .timeout(std::time::Duration::from_secs(15))
        .send()
        .await?;

    if !resp.status().is_success() {
        eprintln!("[intent] detect_intent HTTP failed: status={}", resp.status());
        return Ok(None);
    }

    let data: IntentMatchResponse = resp.json().await?;

    let best = match data.best_match {
        Some(m) if m.score >= threshold => {
            eprintln!("[intent] matched intent_id={} tool={} score={:.4} (threshold={:.4})",
                m.intent_id, m.intent_data.tool_name, m.score, threshold);
            m
        }
        Some(m) => {
            eprintln!("[intent] below threshold: intent_id={} score={:.4} < {:.4}",
                m.intent_id, m.score, threshold);
            return Ok(None);
        }
        _ => {
            eprintln!("[intent] no best_match returned for query: {}", query);
            return Ok(None);
        }
    };

    if best.intent_data.intent_type != "tool" {
        eprintln!("[intent] intent_type={} (not tool), skipping", best.intent_data.intent_type);
        return Ok(None);
    }

    let tool_name = best.intent_data.tool_name.clone();
    if tool_name.is_empty() {
        eprintln!("[intent] matched intent has empty tool_name");
        return Ok(None);
    }

    Ok(Some((best, tool_name)))
}

pub async fn extract_parameters(
    client: &reqwest::Client,
    ollama_url: &str,
    model: &str,
    user_message: &str,
    tool_name: &str,
) -> Result<HashMap<String, Value>, IntentError> {
    let system_prompt = match tool_name {
        "weather" => {
            r#"You are a parameter extraction assistant. Extract parameters from the user message for the weather tool.
The weather tool accepts:
- city: string (optional, MUST be in English, e.g. "Taipei", "Taichung", "New York")
- lat: float (optional, latitude)
- lon: float (optional, longitude)
- units: string ("metric" for Celsius, "imperial" for Fahrenheit)

IMPORTANT: Always translate city names to English. Examples:
- "台北天氣怎樣" → {"city": "Taipei"}
- "台中今天會下雨嗎" → {"city": "Taichung"}
- "高雄溫度多少" → {"city": "Kaohsiung"}
- "東京天氣" → {"city": "Tokyo"}
- "temperature in New York" → {"city": "New York", "units": "imperial"}
- "今天會下雨嗎" → {}
Output JSON only:"#
        }
        "forecast" => {
            r#"You are a parameter extraction assistant. Extract parameters for the forecast tool.
Accepts: city (MUST be in English), lat, lon, days (1-7, default 3), units.

IMPORTANT: Always translate city names to English. Examples:
- "未來三天天氣" → {"days": 3}
- "一週天氣預報台北" → {"city": "Taipei", "days": 7}
- "高雄五天天氣" → {"city": "Kaohsiung", "days": 5}
- "Tokyo weather forecast" → {"city": "Tokyo", "days": 3}
Output JSON only:"#
        }
        "web_search" => {
            r#"You are a parameter extraction assistant. Extract parameters for the web search tool.
Accepts: query (REQUIRED), num (default 5), location (optional).
Examples:
- "搜尋最新AI新聞" → {"query": "最新AI新聞", "num": 5}
- "search for latest news about climate change" → {"query": "latest news climate change", "num": 5}
- "幫我查一下台北房價" → {"query": "台北房價", "num": 5}
Output JSON only:"#
        }
        _ => r#"Extract parameters as JSON. Output only valid JSON:"#,
    };

    let body = serde_json::json!({
        "model": model,
        "prompt": format!("{}\n\nUser message: {}", system_prompt, user_message),
        "stream": false,
        "options": { "temperature": 0.1, "num_predict": 256 }
    });

    let resp = client
        .post(format!("{}/api/generate", ollama_url))
        .json(&body)
        .timeout(std::time::Duration::from_secs(60))
        .send()
        .await?;

    if !resp.status().is_success() {
        eprintln!("[intent] param extraction failed: status={}", resp.status());
        return Err(IntentError::OllamaError("param extraction failed".into()));
    }

    let data: Value = resp.json().await?;
    let raw_output = data
        .get("response")
        .and_then(|v| v.as_str())
        .unwrap_or("{}")
        .trim();

    let json_str = if raw_output.starts_with("```") {
        raw_output
            .lines()
            .skip_while(|l| !l.starts_with('{'))
            .take_while(|l| !l.starts_with("```"))
            .collect::<Vec<_>>()
            .join("\n")
    } else {
        raw_output.to_string()
    };

    let params: Value =
        serde_json::from_str(&json_str).unwrap_or(Value::Object(serde_json::Map::new()));

    let mut result = HashMap::new();
    if let Some(obj) = params.as_object() {
        for (k, v) in obj {
            result.insert(k.clone(), v.clone());
        }
    }

    if tool_name == "web_search" && !result.contains_key("query") {
        result.insert("query".into(), Value::String(user_message.to_string()));
    }
    if tool_name == "web_search" && !result.contains_key("num") {
        result.insert("num".into(), Value::Number(5.into()));
    }
    if tool_name == "forecast" && !result.contains_key("days") {
        result.insert("days".into(), Value::Number(3.into()));
    }

    Ok(result)
}

pub async fn execute_tool(
    client: &reqwest::Client,
    mcp_tools_url: &str,
    tool_name: &str,
    parameters: HashMap<String, Value>,
) -> Result<Value, IntentError> {
    let url = format!("{}/execute", mcp_tools_url);
    let body = ToolCall {
        tool: tool_name.to_string(),
        parameters,
    };

    let resp = client
        .post(&url)
        .json(&body)
        .timeout(std::time::Duration::from_secs(60))
        .send()
        .await?;

    if !resp.status().is_success() {
        let text = resp.text().await.unwrap_or_default();
        eprintln!("[intent] tool execution failed: tool={} error={}", tool_name, text);
        return Err(IntentError::ToolExecutionFailed(text));
    }

    let result: Value = resp.json().await?;

    if let Some(success) = result.get("success").and_then(|v| v.as_bool()) {
        if !success {
            let error = result
                .get("error")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown");
            return Err(IntentError::ToolExecutionFailed(error.into()));
        }
    }

    Ok(result)
}

pub fn build_summarize_prompt(
    user_message: &str,
    tool_name: &str,
    tool_result: &Value,
    _history: &[Value],
) -> String {
    match tool_name {
        "weather" | "forecast" => build_weather_prompt(user_message, tool_name, tool_result),
        _ => build_web_search_prompt(user_message, tool_result),
    }
}

fn build_weather_prompt(user_message: &str, tool_name: &str, tool_result: &Value) -> String {
    let data_text = serde_json::to_string_pretty(tool_result).unwrap_or_default();
    let tool_label = if tool_name == "forecast" { "天氣預報" } else { "即時天氣" };

    format!(
        r#"用戶詢問了：「{user_message}」

以下是{tool_label}工具回傳的數據：

{data_text}

請根據以上數據，用流暢自然的繁體中文回應用戶。

要求：
- 直接回答問題，不要說「根據數據」或「根據結果」
- 包含溫度、天氣狀況、濕度、風速等關鍵資訊
- 如果用戶問是否適合出行，根據天氣數據給出具體建議
- 用日常對話口吻，不要過於正式
- 在回答末尾附上簡短來源標記：

**參考來源**
[1] {tool_label}數據 ({tool_name} tool)"#
    )
}

fn build_web_search_prompt(user_message: &str, tool_result: &Value) -> String {
    let results_text = if let Some(results) = tool_result
        .get("result")
        .and_then(|r| r.get("results"))
        .and_then(|r| r.as_array())
    {
        results
            .iter()
            .enumerate()
            .filter_map(|(i, item)| {
                let title = item.get("title")?.as_str()?;
                let link = item.get("link")?.as_str()?;
                let snippet = item.get("snippet").and_then(|v| v.as_str()).unwrap_or("");
                Some(format!("[{}] 標題：{}\n    摘要：{}\n    連結：{}", i + 1, title, snippet, link))
            })
            .collect::<Vec<_>>()
            .join("\n\n")
    } else {
        serde_json::to_string_pretty(tool_result).unwrap_or_default()
    };

    format!(
        r#"用戶詢問了：「{user_message}」

以下是網路搜尋結果：

{results_text}

請根據搜尋結果，用流暢自然的繁體中文回應用戶。

格式要求（仿照 Copilot 風格）：
- 在回答正文中，對引用的資訊標註來源編號，例如：負責人為何將謙[1][2]，實收資本額為 100,000 元[1]。
- 回答結束後，附上「參考來源」區塊，格式如下：

**參考來源**
[1] [標題文字](URL)
[2] [標題文字](URL)

- 編號必須與正文引用對應
- 用繁體中文回答
- 直接回答問題，不要說「根據搜尋結果」"#
    )
}

pub async fn summarize_result_stream(
    client: &reqwest::Client,
    ollama_url: &str,
    model: &str,
    user_message: &str,
    tool_name: &str,
    tool_result: &Value,
    history: &[Value],
) -> Result<impl Stream<Item = Result<Event, std::convert::Infallible>>, IntentError> {
    let prompt = build_summarize_prompt(user_message, tool_name, tool_result, history);

    let body = serde_json::json!({
        "model": model,
        "prompt": prompt,
        "stream": true,
        "options": { "temperature": 0.7, "num_predict": 1024 }
    });

    let resp = client
        .post(format!("{}/api/generate", ollama_url))
        .json(&body)
        .timeout(std::time::Duration::from_secs(120))
        .send()
        .await?;

    if !resp.status().is_success() {
        return Err(IntentError::OllamaError("summarize failed".into()));
    }

    let text = resp.text().await.map_err(|_| IntentError::OllamaError("read failed".into()))?;

    let mut events: Vec<Result<Event, std::convert::Infallible>> = Vec::new();
    for line in text.lines() {
        if let Ok(data) = serde_json::from_str::<Value>(line) {
            let content = data.get("response").and_then(|v| v.as_str()).unwrap_or("");
            let done = data.get("done").and_then(|v| v.as_bool()).unwrap_or(false);
            events.push(Ok(Event::default()
                .event(if done { "chat_done" } else { "chat_chunk" })
                .data(serde_json::json!({
                    "message": { "role": "assistant", "content": content },
                    "done": done
                }).to_string())));
        }
    }

    Ok(futures::stream::iter(events))
}

pub fn sse_text_to_stream(
    text: String,
) -> Pin<Box<dyn Stream<Item = Result<Event, std::convert::Infallible>> + Send>> {
    if text.trim().is_empty() {
        return Box::pin(futures::stream::iter(Vec::<Result<Event, std::convert::Infallible>>::new()));
    }

    let events: Vec<_> = text
        .lines()
        .filter_map(|line| {
            if line.trim().is_empty() {
                return None;
            }
            serde_json::from_str::<Value>(line).ok().map(|data| {
                let content = data.get("response").and_then(|v| v.as_str()).unwrap_or("");
                let done = data.get("done").and_then(|v| v.as_bool()).unwrap_or(false);
                Ok(Event::default()
                    .event(if done { "chat_done" } else { "chat_chunk" })
                    .data(serde_json::json!({
                        "message": { "role": "assistant", "content": content },
                        "done": done
                    }).to_string()))
            })
        })
        .collect();

    Box::pin(futures::stream::iter(events))
}

pub async fn summarize_text(
    client: &reqwest::Client,
    ollama_url: &str,
    model: &str,
    user_message: &str,
    tool_name: &str,
    tool_result: &Value,
    history: &[Value],
) -> Result<String, IntentError> {
    eprintln!("[intent] summarize_text: model={} ollama_url={} tool={}", model, ollama_url, tool_name);
    let prompt = build_summarize_prompt(user_message, tool_name, tool_result, history);

    let body = serde_json::json!({
        "model": model,
        "prompt": prompt,
        "stream": true,
        "options": { "temperature": 0.7, "num_predict": 1024 }
    });

    let resp = client
        .post(format!("{}/api/generate", ollama_url))
        .json(&body)
        .timeout(std::time::Duration::from_secs(120))
        .send()
        .await?;

    if !resp.status().is_success() {
        eprintln!("[intent] summarize failed: model={} status={}", model, resp.status());
        return Err(IntentError::OllamaError("summarize failed".into()));
    }

    let text = resp.text().await.map_err(|_| IntentError::OllamaError("read failed".into()))?;
    Ok(text)
}

#[derive(Debug, Clone, Serialize)]
pub struct ToolIntentResult {
    pub tool_name: String,
    pub score: f64,
    pub success: bool,
    pub result: Value,
}

#[allow(clippy::too_many_arguments)]
pub async fn route_tool_intent(
    client: &reqwest::Client,
    intent_rag_url: &str,
    mcp_tools_url: &str,
    ollama_url: &str,
    ollama_model: &str,
    user_message: &str,
    _history: &[Value],
    threshold: f64,
) -> Result<Option<ToolIntentResult>, IntentError> {
    let detect_result = detect_intent(client, intent_rag_url, user_message, threshold).await;
    let Some((intent_match, tool_name)) = detect_result? else {
        return Ok(None);
    };

    eprintln!("[intent] extracting parameters for tool={} model={}", tool_name, ollama_model);
    let params = extract_parameters(client, ollama_url, ollama_model, user_message, &tool_name).await?;
    eprintln!("[intent] executing tool={} params={:?}", tool_name, params.keys().collect::<Vec<_>>());
    let result = execute_tool(client, mcp_tools_url, &tool_name, params).await?;
    eprintln!("[intent] tool={} executed successfully", tool_name);

    Ok(Some(ToolIntentResult {
        tool_name,
        score: intent_match.score,
        success: true,
        result,
    }))
}
