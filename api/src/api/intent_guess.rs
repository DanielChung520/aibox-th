//! Intent Guess 模組
//!
//! # Description
//! 接收前端 ActionTrail 上下文，透過小 LLM (Ollama) 生成意圖猜測。
//!
//! # Last Update: 2026-04-16 11:43:44
//! # Author: Daniel Chung
//! # Version: 1.0.0

use axum::{
    http::StatusCode,
    response::IntoResponse,
    routing::post,
    Json, Router,
};
use once_cell::sync::Lazy;
use serde::{Deserialize, Serialize};

use crate::config::CONFIG;
use crate::models::ApiResponse;

static HTTP_CLIENT: Lazy<reqwest::Client> = Lazy::new(reqwest::Client::new);

const INTENT_MODEL: &str = "qwen3.5:0.8b";

#[derive(Debug, Deserialize)]
struct IntentGuessRequest {
    trigger: String,
    table_name: Option<String>,
    field_name: Option<String>,
    cell_value: Option<String>,
    page_name: Option<String>,
    page_description: Option<String>,
    recent_actions: Option<Vec<serde_json::Value>>,
}

#[derive(Debug, Serialize, Clone)]
struct IntentGuess {
    text: String,
    confidence: f64,
    source: String,
}

#[derive(Debug, Serialize)]
struct IntentGuessResponse {
    guesses: Vec<IntentGuess>,
}

fn build_prompt(req: &IntentGuessRequest) -> String {
    let mut prompt = String::from(
        "你是企業 ERP 系統的意圖推斷助手。根據用戶的操作上下文，生成用戶最可能想問的問題。\n\
         回覆格式：每行一個問題，格式為 `置信度|問題`，置信度為 0.0-1.0 的小數。\n\
         不要加編號、不要加其他文字。\n\n"
    );

    match req.trigger.as_str() {
        "table_open" => {
            let name = req.table_name.as_deref().unwrap_or("未知表");
            prompt.push_str(&format!(
                "用戶剛打開「{}」資料表。請生成 5-6 個可能的問題。\n\
                 第一個必須是詢問這張表的意思與用途（置信度 0.95）。\n",
                name
            ));
        }
        "cell_click" | "field_click" => {
            let table = req.table_name.as_deref().unwrap_or("未知表");
            let field = req.field_name.as_deref().unwrap_or("未知欄位");
            prompt.push_str(&format!(
                "用戶在「{}」表中點擊了「{}」欄位",
                table, field
            ));
            if let Some(val) = &req.cell_value {
                if !val.is_empty() {
                    prompt.push_str(&format!("，看到的值是「{}」", val));
                }
            }
            prompt.push_str(
                "。\n請生成 3 個可能的問題。\n\
                 第一個必須是詢問這個欄位的含義（置信度 0.90）。\n",
            );
        }
        "page_view" => {
            let page = req.page_name.as_deref().unwrap_or("目前頁面");
            let desc = req.page_description.as_deref().unwrap_or("");
            prompt.push_str(&format!(
                "用戶進入了「{}」頁面（{}）。請生成 3-5 個可能的問題。\n\
                 第一個必須是詢問此功能的操作說明（置信度 0.95）。\n\
                 其餘問題應與此頁面的功能和常見任務相關。\n",
                page, desc
            ));
        }
        _ => {
            prompt.push_str("用戶正在操作系統。請根據以下最近操作，生成 3 個可能的問題。\n");
        }
    }

    if let Some(actions) = &req.recent_actions {
        if !actions.is_empty() {
            prompt.push_str("\n最近操作軌跡：\n");
            for (i, action) in actions.iter().take(10).enumerate() {
                let action_type = action.get("type").and_then(|v| v.as_str()).unwrap_or("unknown");
                let meta_str = action.get("meta").map(|m| m.to_string()).unwrap_or_default();
                prompt.push_str(&format!("{}. {} {}\n", i + 1, action_type, meta_str));
            }
        }
    }

    prompt
}

fn parse_llm_response(text: &str, req: &IntentGuessRequest) -> Vec<IntentGuess> {
    let mut guesses: Vec<IntentGuess> = text
        .lines()
        .filter(|line| !line.trim().is_empty())
        .filter_map(|line| {
            let line = line.trim().trim_start_matches(|c: char| c.is_ascii_digit() || c == '.' || c == ' ');
            if let Some((conf_str, question)) = line.split_once('|') {
                let confidence = conf_str.trim().parse::<f64>().unwrap_or(0.5);
                let text = question.trim().to_string();
                if !text.is_empty() {
                    return Some(IntentGuess {
                        text,
                        confidence: confidence.clamp(0.0, 1.0),
                        source: "llm".to_string(),
                    });
                }
            }
            None
        })
        .collect();

    if guesses.is_empty() {
        guesses = build_fallback_guesses(req);
    }

    guesses.sort_by(|a, b| b.confidence.partial_cmp(&a.confidence).unwrap_or(std::cmp::Ordering::Equal));
    guesses
}

fn build_fallback_guesses(req: &IntentGuessRequest) -> Vec<IntentGuess> {
    let mut guesses = Vec::new();
    match req.trigger.as_str() {
        "table_open" => {
            let name = req.table_name.as_deref().unwrap_or("這張表");
            guesses.push(IntentGuess { text: format!("告訴我「{}」的意思與用途", name), confidence: 0.95, source: "fixed".to_string() });
            guesses.push(IntentGuess { text: format!("{}目前有多少筆記錄？", name), confidence: 0.70, source: "fixed".to_string() });
            guesses.push(IntentGuess { text: format!("{}有哪些欄位？", name), confidence: 0.65, source: "fixed".to_string() });
            guesses.push(IntentGuess { text: format!("{}最近有什麼變動？", name), confidence: 0.55, source: "fixed".to_string() });
            guesses.push(IntentGuess { text: format!("幫我分析{}的數據趨勢", name), confidence: 0.50, source: "fixed".to_string() });
        }
        "cell_click" | "field_click" => {
            let field = req.field_name.as_deref().unwrap_or("這個欄位");
            guesses.push(IntentGuess { text: format!("告訴我「{}」欄位的含義", field), confidence: 0.90, source: "fixed".to_string() });
            guesses.push(IntentGuess { text: format!("{}的分布統計？", field), confidence: 0.60, source: "fixed".to_string() });
            guesses.push(IntentGuess { text: format!("{}的唯一值有哪些？", field), confidence: 0.55, source: "fixed".to_string() });
        }
        "page_view" => {
            let page = req.page_name.as_deref().unwrap_or("目前頁面");
            guesses.push(IntentGuess { text: format!("告訴我「{}」的操作說明", page), confidence: 0.95, source: "fixed".to_string() });
            guesses.push(IntentGuess { text: format!("{}有哪些主要功能？", page), confidence: 0.70, source: "fixed".to_string() });
            guesses.push(IntentGuess { text: format!("如何在{}中完成常見任務？", page), confidence: 0.60, source: "fixed".to_string() });
        }
        _ => {
            guesses.push(IntentGuess { text: "幫我整理目前的操作摘要".to_string(), confidence: 0.50, source: "fixed".to_string() });
        }
    }
    guesses
}

async fn intent_guess(
    Json(payload): Json<IntentGuessRequest>,
) -> Result<impl IntoResponse, StatusCode> {
    let prompt = build_prompt(&payload);

    let ollama_body = serde_json::json!({
        "model": INTENT_MODEL,
        "prompt": prompt,
        "stream": false,
        "options": {
            "temperature": 0.7,
            "num_predict": 256,
            "top_p": 0.9,
        }
    });

    let result = HTTP_CLIENT
        .post(format!("{}/api/generate", CONFIG.ai_services.ollama_base_url))
        .json(&ollama_body)
        .timeout(std::time::Duration::from_secs(12))
        .send()
        .await;

    let guesses = match result {
        Ok(resp) if resp.status().is_success() => {
            let body: serde_json::Value = resp.json().await.unwrap_or_default();
            let response_text = body.get("response").and_then(|v| v.as_str()).unwrap_or("");
            parse_llm_response(response_text, &payload)
        }
        _ => build_fallback_guesses(&payload),
    };

    Ok(Json(ApiResponse::success(IntentGuessResponse { guesses })))
}

pub fn create_intent_guess_router() -> Router {
    Router::new()
        .route("/api/v1/ai/intent-guess", post(intent_guess))
}
