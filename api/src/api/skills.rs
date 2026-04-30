//! Skill Specs API
//!
//! # Description
//! 技能規格 CRUD — 技能看板 backend。狀態流程：draft → spec → developing → testing → live → deprecated
//!
//! # Last Update: 2026-04-29 14:00:00
//! # Author: AI Agent
//! # Version: 1.0.0

use axum::{
    extract::Path,
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post, put, delete},
    Json, Router,
};
use chrono::Datelike;
use serde_json::Value;

use crate::{db::get_db, models::ApiResponse};

pub fn create_skill_router() -> Router {
    Router::new()
        .route("/api/v1/skills", get(list_skills).post(create_skill))
        .route("/api/v1/skills/{id}", get(get_skill).put(update_skill).delete(delete_skill))
        .route("/api/v1/skills/by-no/{skill_no}", get(get_skill_by_no))
        .route("/api/v1/skills/{id}/analyze", post(analyze_skill))
}

async fn generate_skill_no() -> String {
    let db = get_db();
    let now = chrono::Utc::now();
    let week_str = format!("{:02}", now.iso_week().week());
    let year_str = format!("{:02}", now.year() % 100);
    let prefix = format!("SKL-{}{}", year_str, week_str);
    let pattern = format!("{}%", prefix);
    let count: f64 = db
        .aql_bind_vars(
            "FOR s IN skill_specs FILTER s.skill_no LIKE @pattern RETURN 1",
            [("pattern", serde_json::json!(pattern))].into(),
        )
        .await
        .ok()
        .map(|v: Vec<Value>| v.len() as f64)
        .unwrap_or(0.0);
    format!("{}-{:03}", prefix, count as i32 + 1)
}

async fn list_skills() -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<Value> = db
        .aql_str("FOR s IN skill_specs SORT s.created_at DESC RETURN s")
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(docs)))
}

async fn create_skill(
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    if payload.as_object().map(|o| o.is_empty()).unwrap_or(true) {
        return Err(StatusCode::BAD_REQUEST);
    }
    let db = get_db();
    let col = db.collection("skill_specs").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let skill_no = generate_skill_no().await;
    let now = chrono::Utc::now().to_rfc3339();
    let mut doc = payload.clone();
    if let Some(obj) = doc.as_object_mut() {
        obj.insert("skill_no".to_string(), serde_json::json!(skill_no));
        obj.insert("status".to_string(), serde_json::json!("draft"));
        obj.insert("version".to_string(), serde_json::json!("v0.1"));
        obj.insert("created_at".to_string(), serde_json::json!(now));
        obj.insert("updated_at".to_string(), serde_json::json!(now));
    }
    col.create_document(doc, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(serde_json::json!({
        "skill_no": skill_no,
        "status": "draft"
    }))))
}

async fn get_skill(
    Path(id): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<Value> = db
        .aql_bind_vars(
            "FOR s IN skill_specs FILTER s._key == @key LIMIT 1 RETURN s",
            [("key", serde_json::json!(id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc = docs.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(doc)))
}

async fn update_skill(
    Path(id): Path<String>,
    Json(payload): Json<Value>,
) -> Result<impl IntoResponse, StatusCode> {
    if payload.is_null() || payload.as_object().map(|o| o.is_empty()).unwrap_or(true) {
        return Err(StatusCode::BAD_REQUEST);
    }
    let db = get_db();
    let col = db.collection("skill_specs").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let mut update_data = payload.clone();
    if let Some(obj) = update_data.as_object_mut() {
        obj.insert("updated_at".to_string(), serde_json::json!(chrono::Utc::now().to_rfc3339()));
    }
    col.update_document(&id, update_data, Default::default())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ApiResponse::success(serde_json::json!({"status": "updated", "key": id}))))
}

async fn delete_skill(
    Path(id): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let col = db.collection("skill_specs").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.remove_document::<Value>(&id, Default::default(), None)
        .await
        .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success("Skill deleted")))
}

async fn get_skill_by_no(
    Path(skill_no): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let docs: Vec<Value> = db
        .aql_bind_vars(
            "FOR s IN skill_specs FILTER s.skill_no == @no LIMIT 1 RETURN s",
            [("no", serde_json::json!(skill_no))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc = docs.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(ApiResponse::success(doc)))
}

async fn analyze_skill(
    Path(id): Path<String>,
    payload: Option<Json<Value>>,
) -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    let revision = payload.as_ref().and_then(|p| p.get("revision")).and_then(|v| v.as_str()).unwrap_or("");

    let docs: Vec<Value> = db
        .aql_bind_vars(
            "FOR s IN skill_specs FILTER s._key == @key LIMIT 1 RETURN s",
            [("key", serde_json::json!(id))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let doc = docs.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    let title = doc.get("title").and_then(|v| v.as_str()).unwrap_or("");
    let desc = doc.get("description").and_then(|v| v.as_str()).unwrap_or("");
    let skill_type = doc.get("skill_type").and_then(|v| v.as_str()).unwrap_or("data");
    let steps_arr = doc.get("steps").and_then(|v| v.as_array()).map(|a| a.iter().filter_map(|v| v.as_str()).collect::<Vec<_>>().join("\n")).unwrap_or_default();
    let guardrails_arr = doc.get("guardrails").and_then(|v| v.as_array()).map(|a| a.iter().filter_map(|v| v.as_str()).collect::<Vec<_>>().join("\n")).unwrap_or_default();
    let tags_arr = doc.get("tags").and_then(|v| v.as_array()).map(|a| a.iter().filter_map(|v| v.as_str()).collect::<Vec<_>>().join(", ")).unwrap_or_default();
    let linked_intents = doc.get("linked_intents").and_then(|v| v.as_array()).map(|a| a.iter().filter_map(|v| v.as_str()).collect::<Vec<_>>().join(", ")).unwrap_or_default();

    let revision_hint = if revision.is_empty() {
        String::new()
    } else {
        format!("\n\n⚠️ 修改指示：請根據以下反饋調整規格書內容：\n{revision}\n")
    };

    // 先讀取 model 配置（provider 查詢需要用到）
    let model: String = db
        .aql_bind_vars(
            "FOR p IN system_params FILTER p.param_key == @key LIMIT 1 RETURN p.param_value",
            [("key", serde_json::json!("dev.requirement_spec_model"))].into(),
        )
        .await
        .ok()
        .and_then(|mut v: Vec<String>| v.pop())
        .unwrap_or_else(|| "qwen3-coder:30b".to_string());

    // 讀取 max_tokens 配置
    let max_tokens: usize = db
        .aql_bind_vars(
            "FOR p IN system_params FILTER p.param_key == @key LIMIT 1 RETURN p.param_value",
            [("key", serde_json::json!("dev.requirement_spec_max_tokens"))].into(),
        )
        .await
        .ok()
        .and_then(|mut v: Vec<String>| v.pop())
        .and_then(|s| s.parse().ok())
        .unwrap_or(4000);

    // 從 model_providers 查詢 model 對應的 base_url 與 api_key
    let mut api_base = std::env::var("OLLAMA_BASE_URL").unwrap_or_else(|_| "http://localhost:11434".to_string());
    let mut api_key = String::new();

    let providers: Vec<Value> = db
        .aql_bind_vars(
            "FOR p IN model_providers FILTER p.status == 'enabled' RETURN p",
            [].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    'provider_loop: for p in &providers {
        if let Some(models) = p.get("models").and_then(|v| v.as_array()) {
            for m in models {
                if let Some(mid) = m.get("model_id").and_then(|v| v.as_str()) {
                    if mid == model {
                        if let Some(url) = p.get("base_url").and_then(|v| v.as_str()) {
                            api_base = url.trim_end_matches('/').to_string();
                        }
                        if let Some(k) = p.get("api_key").and_then(|v| v.as_str()) {
                            api_key = k.to_string();
                        }
                        break 'provider_loop;
                    }
                }
            }
        }
    }

    let mut model_for_url = model.clone();
    let is_ollama = api_base.contains("localhost") || api_base.contains("127.0.0.1");
    if !is_ollama {
        model_for_url = model.split(':').next().unwrap_or(&model).to_string();
    }

    // 讀取系統規格索引（dev.spec_context）作為參考上下文
    let spec_index: String = db
        .aql_bind_vars(
            "FOR p IN system_params FILTER p.param_key == @key LIMIT 1 RETURN p.param_value",
            [("key", serde_json::json!("dev.spec_context"))].into(),
        )
        .await
        .ok()
        .and_then(|mut v: Vec<String>| v.pop())
        .unwrap_or_default();

    let spec_section = if spec_index.is_empty() {
        String::new()
    } else {
        format!("\n## 系統規格索引（參考文件）\n請閱讀以下文件索引，理解系統架構與開發規範後再產出規格書：\n\n{spec_index}\n")
    };

    // AGENTS.md 關鍵架構規則摘要
    let agents_core = r#"
## 系統架構強制規則（必須遵守）

### 服務架構
- 所有前端請求必須透過 Rust API Gateway (port 6500) 轉發，嚴禁前端直接呼叫 Python 服務
- Python 服務統一入口：unified_agents (port 8011)
- 服務間通訊路徑：Frontend → Rust API (6500) → Python Services (8011/8004/8007)

### 目錄規範
- Python 技能程式碼放置路徑格式：ai-services/bpa/{agent_name}/skills/{skill_name}.py
- 測試檔案放置路徑格式：.tests/py/test_{skill_name}.py
- 模組大小限制：Python 單檔上限 400 行，建議 250 行

### ToolRegistry 框架（shared/tools/）
- 所有技能必須使用 shared/tools/ 框架註冊與執行，不可自行實作工具調用
- 註冊方式：ToolRegistry.register(SkillDefinition(name=..., ...))
- 工具來源：MCP / DATA_AGENT / KNOWLEDGE / BUILTIN
- ToolResult 格式：{{ success: bool, result: any, error: str?, duration_ms: int }}

### 配置原則
- 所有配置性內容（API URL、模型、功能開關）必須存放於 ArangoDB system_params
- 嚴禁在程式碼中 hardcode 任何配置
- 讀取方式：透過 Rust API GET /api/v1/system-params/{key}
"#;

    let prompt = format!(
        r#"你是 AIBox / ABC Desktop 系統的資深開發架構師。請根據以下技能需求與系統規格索引，產生一份**緊密對應需求**的技能開發規格書（JSON 格式）。

## ⚠️ 關鍵規則：每項輸出都必須直接從下方的「預想執行步驟」推導而來，不可填寫通用內容。

## 技能需求
標題：{title}
描述：{desc}
技能類型：{skill_type}
標籤：{tags_arr}
關聯意圖：{linked_intents}

## 預想執行步驟（以下為顧問提出的步驟，你的輸出必須基於這些步驟逐一對應）
{steps_arr}

## 護欄規則
{guardrails_arr}

{revision_hint}
{agents_core}
{spec_section}

## 約束
- 技術棧必須在本系統範圍內：Python FastAPI / Tauri / Rust / React / TypeScript / ArangoDB / Qdrant / Ollama
- 技能必須定義為無狀態的 SkillDefinition，可被任何 Agent 調用
- 資料存取必須嚴格遵守 data_scope 定義的允許/禁止欄位
- LLM 在技能中僅用於格式化輸出，不可用於決策
- 護欄規則必須在執行時被強制執行，不可由 LLM 覆寫
- 技能必須可單元測試

## 系統可用能力（AI 開發時可使用的服務與端點）
以下是系統中已存在的服務，開發技能時可直接呼叫，**不需要從零實作**：

### 多媒體解析
- 端點：`POST /mcp/multimedia-analyzer/analyze`
- 功能：分析圖片內容，回傳文字描述；可用於解析訂單截圖、產品圖片
- 輸入：`{{ content: base64, media_type: "image", filename: string }}`

### LINE 平台
- Webhook：`unified_agents/platforms/line/webhook.py`
- 功能：接收 LINE 訊息、解析 user_id、群組管理、回覆訊息
- 可取得：使用者名稱、群組名稱、session_id

### Data Agent（Ragic 資料查詢）
- NL 查詢：`POST /da/ragic/query` — 自然語言查 Ragic
- 直接查詢：`POST /da/ragic/query/records` — 指定 table + where
- 可用的 Ragic 表格：STOCK_16（庫存表）、ERP_52（採購單）、ERP_2（訂購單）

### Knowledge Agent（知識庫 RAG）
- 端點：`POST /ka/hybrid/search`
- 功能：全文 + 向量雙軌檢索，適合回答操作問題

### ToolRegistry（工具註冊）
- 框架：`shared/tools/registry.py`
- 註冊方式：`ToolRegistry.register(SkillDefinition(...))`
- 已有內建工具：`current_time`、`multimedia_analyzer`、`da_query`、`ka_search`

### ArangoDB 集合（直接存取）
- `product_cache`：產品快取資料（key: `stock_16_products`，含品名、庫存、單位）
- `order_preorders`：預購單（含 items、status 等欄位）
- `bot_chat_sessions`：對話歷史

### 技能參考實作
- 參考 `ai-services/bpa/ragic_agent/router.py` — 完整的 Agent router 模式
- 技能目錄建議：`ai-services/bpa/{{agent_name}}/skills/{{skill_name}}.py`

## 重要規範（務必遵守以下對應規則）
1. **程式名稱**：根據技能標題產生英文代號（snake_case），例如「庫存品項查詢」→ `query_stock`
2. **mermaid_flow**：必須是**使用者視角的業務流程圖**，展示請求如何被處理、判斷與回應。每個節點對應一個「預想執行步驟」。**不可**畫資料驗證或欄位檢查作為主要流程節點。**務必按照以下範例的結構輸出**：

   ```mermaid
   flowchart TD
       A[使用者輸入訂購資訊] --> B{{判斷輸入類型}}
       B -->|文字| C[直接提取訂購文字]
       B -->|圖片| D[呼叫多媒體解析器]
       B -->|PDF| E[呼叫 PDF 解析器（dummy）]
       B -->|Excel| F[呼叫 Excel 解析器（dummy）]
       C --> G{{檢查訂購完整性<br/>（品名、數量、單位）}}
       D --> G
       E --> G
       F --> G
       G -->|完整| H[寫入預購單 order_preorders]
       G -->|不完整| I[回傳錯誤：缺少欄位]
       H --> J[回傳：已完成]
       I --> J
   ```
3. **error_handling**：每個錯誤情境必須對應到「預想執行步驟」中可能失敗的步驟，不可憑空編造
4. **data_flow**：必須描述資料從接收到輸出的完整路徑，對應到預想步驟
5. **hour_breakdown**：根據預想步驟的複雜度合理估算
6. **risks**：必須直接從預想步驟和護欄規則中分析可能的風險
7. **三階段流程不可遺漏：解析→檢驗→寫入**。若需求包含訂單/預購單建立，mermaid_flow 必須包含以下三個階段，缺一不可：
   - **解析階段**：接收輸入，呼叫多媒體解析器（若為非文字），提取訂單資訊（品名、數量、規格）
   - **檢驗階段**：檢查提取的資訊是否完整（必填欄位是否齊全）。若不完整，必須有回問使用者的循環節點
   - **寫入階段**：將完整訂單資訊寫入 `order_preorders`（ArangoDB 集合），回覆使用者已建立預購單；若寫入失敗則回傳錯誤
8. **output_schema 不可包含價格相關欄位**：若護欄規則禁止顯示價格，`implementation.output_schema` 中**絕對不可出現** `price`、`cost`、`單價`、`金額` 等欄位。違者視為護欄失效
9. **input_schema 必須包含 session_id 與 user_id**：若需求涉及聊天平台，必須包含這兩個欄位

## 輸出 JSON（雙層結構 — 同時滿足人類閱讀與 AI 開發）
{{
  "business": {{
    "summary": "技能摘要（一段話，必須提及原始需求標題）",
    "user_flow": "Mermaid flowchart，使用者視角的業務流程，包含所有預想步驟",
    "component_relations": "Mermaid graph，展示與現有系統組件的關係",
    "data_flow": "資料從接收到輸出的完整路徑描述"
  }},
  "implementation": {{
    "name": "程式名稱（snake_case）",
    "tech_stack": ["選擇的技術"],
    "file_path": "程式碼放置路徑，例如 ai-services/bpa/order_secretary/skills/query_stock.py",
    "class_name": "類別名稱，例如 QueryStockSkill",
    "base_class": "繼承的基礎類別，例如 BaseSkill",
    "input_schema": {{ "param1": "型別與說明" }},
    "output_schema": {{ "field1": "型別與說明" }},
    "data_access": [
      {{ "type": "arangodb|ragic|cache", "name": "資料源名稱", "collection": "集合名稱", "key": "查詢鍵", "method": "get|aql|query" }}
    ],
    "registration": "註冊方式，例如 SkillRegistry.register(name)",
    "test_file": "測試檔案路徑，例如 .tests/py/test_query_stock.py",
    "hour_breakdown": {{
      "design": 設計（整數小時）,
      "development": 開發（整數小時）,
      "testing": 測試（整數小時）,
      "review": 審查（整數小時）
    }}
  }},
  "error_handling": [
    {{ "scenario": "對應步驟的錯誤情境", "response": "預期回應", "code": "錯誤碼" }}
  ],
  "risks": ["從預想步驟和護欄規則分析的風險"],
  "suggestions": ["從預想步驟和護欄規則提出的開發建議"]
}}"#,
        title = title,
        desc = desc,
        skill_type = skill_type,
        tags_arr = tags_arr,
        linked_intents = linked_intents,
        steps_arr = steps_arr,
        guardrails_arr = guardrails_arr,
        revision_hint = revision_hint,
        agents_core = agents_core,
        spec_section = spec_section,
    );

    let mut spec_json = serde_json::json!({
        "business": {
            "summary": "分析中...",
            "user_flow": "",
            "component_relations": "",
            "data_flow": ""
        },
        "implementation": {
            "name": "",
            "tech_stack": [],
            "file_path": "",
            "class_name": "",
            "base_class": "",
            "input_schema": {},
            "output_schema": {},
            "data_access": [],
            "registration": "",
            "test_file": "",
            "hour_breakdown": {"design": 0, "development": 0, "testing": 0, "review": 0}
        },
        "error_handling": [],
        "risks": [],
        "suggestions": [],
    });

    if let Ok(client) = reqwest::Client::builder().timeout(std::time::Duration::from_secs(120)).build() {
        let llm_req = if is_ollama {
            client
                .post(format!("{api_base}/api/chat"))
                .json(&serde_json::json!({
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": false,
                    "format": "json",
                    "options": {"num_predict": max_tokens as i32},
                }))
        } else {
            let mut req = client
                .post(format!("{api_base}/chat/completions"))
                .json(&serde_json::json!({
                    "model": model_for_url,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": false,
                    "max_tokens": max_tokens,
                }));
            if !api_key.is_empty() {
                req = req.header("Authorization", format!("Bearer {}", api_key));
            }
            req
        };

        if let Ok(resp) = llm_req.send().await {
            if resp.status().is_success() {
                let body: Value = resp.json().await.unwrap_or_default();
                let content = if is_ollama {
                    body.get("message").and_then(|m| m.get("content")).and_then(|c| c.as_str()).map(|s| s.to_string())
                } else {
                    body.get("choices").and_then(|c| c.get(0)).and_then(|c| c.get("message")).and_then(|m| m.get("content")).and_then(|c| c.as_str()).map(|s| s.to_string())
                };
                if let Some(content) = content {
                    if let Ok(parsed) = serde_json::from_str::<Value>(&content) {
                        spec_json = parsed;
                    } else if let Some(start) = content.find('{') {
                        if let Some(end) = content.rfind('}') {
                            if let Ok(parsed) = serde_json::from_str::<Value>(&content[start..=end]) {
                                spec_json = parsed;
                            }
                        }
                    }
                }
            }
        }
    }

    let gen_name = spec_json
        .get("implementation").and_then(|i| i.get("name")).and_then(|v| v.as_str())
        .or_else(|| spec_json.get("name").and_then(|v| v.as_str()))
        .unwrap_or("");
    let col = db.collection("skill_specs").await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    col.update_document(
        &id,
        serde_json::json!({
            "status": "spec",
            "name": gen_name,
            "version": "v0.2",
            "dev_spec": spec_json,
            "analyzed_at": chrono::Utc::now().to_rfc3339(),
            "updated_at": chrono::Utc::now().to_rfc3339(),
        }),
        Default::default(),
    )
    .await
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(ApiResponse::success("spec_generated")))
}
