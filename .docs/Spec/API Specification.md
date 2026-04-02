# ABC Desktop API 開發規範與使用說明

## 概述

ABC Desktop API 基於 Rust Axum 框架構建，提供 RESTful API 服務。支援 JWT 認證、ArangoDB 資料庫操作、以及 AI 服務代理。

**Base URL**: `http://localhost:6500`

**預設帳號**:
- 使用者名稱: `admin`
- 密碼: `admin123`

---

## 目錄

1. [認證 (Authentication)](#認證-authentication)
2. [API 端點 (Endpoints)](#api-端點-endpoints)
3. [請求與回應格式](#請求與回應格式)
4. [錯誤處理](#錯誤處理)
5. [開發範例](#開發範例)
6. [新增 API 流程](#新增-api-流程)

---

## 認證 (Authentication)

### JWT Token

API 使用 JWT (JSON Web Token) 進行身份驗證。

**取得 Token**:
```bash
curl -X POST http://localhost:6500/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

**回應**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "token": "eyJ0eXAi...",
    "user": {
      "_key": "admin",
      "username": "admin",
      "name": "管理員",
      "role_key": "admin",
      "role_name": "系統管理員"
    }
  }
}
```

**使用 Token**:
```bash
curl http://localhost:6500/api/v1/users \
  -H "Authorization: Bearer <your_token>"
```

### 需要認證的端點

以下端點需要有效的 JWT Token：

- `GET /api/v1/users`
- `POST /api/v1/users`
- `GET /api/v1/users/{key}`
- `PUT /api/v1/users/{key}`
- `DELETE /api/v1/users/{key}`
- `POST /api/v1/users/{key}/reset-password`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/ai/*` (所有 AI 相關端點)

---

## API 端點 (Endpoints)

### 健康檢查

| 方法 | 端點 | 說明 | 認證 |
|------|------|------|------|
| GET | `/health` | 服務健康檢查 | 否 |

**回應範例**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 3600,
  "services": {
    "database": true,
    "ai_task": true,
    "data_query": true,
    "knowledge_assets": true,
    "mcp_tools": true,
    "bpa": true
  }
}
```

---

### 認證 (Auth)

| 方法 | 端點 | 說明 | 認證 |
|------|------|------|------|
| POST | `/api/v1/auth/login` | 使用者登入 | 否 |
| POST | `/api/v1/auth/logout` | 使用者登出 | 是 |
| GET | `/api/v1/auth/me` | 取得當前使用者資訊 | 是 |

#### POST /api/v1/auth/login

**請求**:
```json
{
  "username": "admin",
  "password": "admin123",
  "remember": true
}
```

**回應**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "token": "eyJ0eXAi...",
    "user": {
      "_key": "admin",
      "username": "admin",
      "name": "管理員",
      "role_key": "admin",
      "role_name": "系統管理員"
    }
  }
}
```

#### GET /api/v1/auth/me

**Headers**: `Authorization: Bearer <token>`

**回應**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "_key": "admin",
    "username": "admin",
    "name": "管理員",
    "role_key": "admin",
    "role_name": "系統管理員"
  }
}
```

---

### 使用者管理 (Users)

| 方法 | 端點 | 說明 | 認證 |
|------|------|------|------|
| GET | `/api/v1/users` | 取得所有使用者 | 是 |
| POST | `/api/v1/users` | 建立新使用者 | 是 |
| GET | `/api/v1/users/{key}` | 取得特定使用者 | 是 |
| PUT | `/api/v1/users/{key}` | 更新使用者 | 是 |
| DELETE | `/api/v1/users/{key}` | 刪除使用者 | 是 |
| POST | `/api/v1/users/{key}/reset-password` | 重設密碼 | 是 |

#### GET /api/v1/users

**回應**:
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "_key": "admin",
      "username": "admin",
      "name": "管理員",
      "role_key": "admin",
      "status": "enabled",
      "created_at": "2026-03-18T10:00:00Z"
    }
  ]
}
```

#### POST /api/v1/users

**請求**:
```json
{
  "username": "newuser",
  "password_hash": "newpassword",
  "name": "新使用者",
  "role_key": "user",
  "status": "enabled"
}
```

---

### 角色管理 (Roles)

| 方法 | 端點 | 說明 | 認證 |
|------|------|------|------|
| GET | `/api/v1/roles` | 取得所有角色 | 否 |
| POST | `/api/v1/roles` | 建立新角色 | 是 |
| GET | `/api/v1/roles/{key}` | 取得特定角色 | 是 |
| PUT | `/api/v1/roles/{key}` | 更新角色 | 是 |
| DELETE | `/api/v1/roles/{key}` | 刪除角色 | 是 |

---

### 系統參數 (System Params)

| 方法 | 端點 | 說明 | 認證 |
|------|------|------|------|
| GET | `/api/v1/system-params` | 取得所有參數 | 否 |
| GET | `/api/v1/system-params/{key}` | 取得特定參數 | 否 |
| PUT | `/api/v1/system-params/{key}` | 更新參數 | 是 |

#### GET /api/v1/system-params

**回應**:
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "_key": "app.name",
      "param_key": "app.name",
      "param_value": "管理系統",
      "param_type": "string",
      "require_restart": true,
      "category": "basic",
      "updated_at": "2026-03-18T10:00:00Z"
    }
  ]
}
```

**常見 DA 系統參數**：

| 參數 Key | 類型 | 說明 |
|----------|------|------|
| `da.data_source` | string | 預設資料源：`sap` 或 `ragic` |
| `da.llm_model` | string | SQL 生成 LLM 模型 |
| `da.vector_threshold` | number | Qdrant 向量匹配門檻（預設 0.85） |

> **注意**：`da.data_source` 為 Pipeline 預設值，查詢時可透過 `data_source` 請求參數或意圖前綴（`sap_`/`rgc_`）動態覆寫。

---

### 功能管理 (Functions)

| 方法 | 端點 | 說明 | 認證 |
|------|------|------|------|
| GET | `/api/v1/functions` | 取得所有功能 | 否 |
| POST | `/api/v1/functions` | 建立新功能 | 是 |
| GET | `/api/v1/functions/{key}` | 取得特定功能 | 是 |
| PUT | `/api/v1/functions/{key}` | 更新功能 | 是 |
| DELETE | `/api/v1/functions/{key}` | 刪除功能 | 是 |
| GET | `/api/v1/functions/{key}/roles` | 取得功能權限 | 是 |
| PUT | `/api/v1/functions/{key}/roles` | 設定功能權限 | 是 |

---

### AI 服務 (AI)

| 方法 | 端點 | 說明 | 認證 |
|------|------|------|------|
| POST | `/api/v1/ai/chat` | AI 對話 | 是 |
| GET | `/api/v1/ai/chat/stream` | SSE 流式對話 | 是 |
| POST | `/api/v1/ai/query` | 自然語言查詢 | 是 |
| POST | `/api/v1/ai/knowledge` | 知識庫搜尋 | 是 |

#### POST /api/v1/ai/chat

**請求**:
```json
{
  "message": "你好，請問今天天氣如何？",
  "model": "llama3.2:latest",
  "stream": false
}
```

**回應**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "response": "你好！我是 AI 助手...",
    "model": "llama3.2:latest",
    "tokens": 150
  }
}
```

---

### Data Agent 自然語言查詢 (NL→SQL)

Data Agent 服務（Python FastAPI，port 8003）透過 API Gateway 的 `/api/v1/ai/query` 端點提供自然語言轉 SQL 查詢功能。

> **雙資料源架構**：Data Agent 支援 SAP + Ragic 兩種資料源，透過 `data_source` 參數或意圖前綴動態路由：
> - `sap_` 前綴 → `da_table_info_sap` 等 collections（`s3://sap/` 路徑）
> - `rgc_` 前綴 → `da_table_info_ragic` 等 collections（`s3://ragic/` 路徑）
>
> 完整 Pipeline 規格見 [data-agent-spec-v2.md](./Spec/後台/DA/data-agent-spec-v2.md)。

#### POST /api/v1/ai/query

**請求**:
```json
{
  "message": "查詢所有員工",
  "data_source": "ragic",
  "user_context": {
    "user_id": "admin",
    "roles": ["admin"]
  }
}
```

**回應**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "sql": "SELECT * FROM read_parquet('s3://ragic/configuration-file/7/*.parquet') LIMIT 100",
    "intent": {
      "intent_id": "rgc_employee_list",
      "data_source": "ragic",
      "table_id": "CFG7_EMPLOYEE"
    },
    "binding": {
      "table_id": "CFG7_EMPLOYEE",
      "fields": ["1015428", "1015429", "1015495"]
    },
    "execution": {
      "duration_ms": 234,
      "row_count": 42
    }
  }
}
```

**請求欄位說明**：

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `message` | String | 是 | 自然語言查詢 |
| `data_source` | String | 否 | 資料源：`sap` 或 `ragic`（預設由意圖前綴推斷） |
| `user_context` | Object | 是 | 使用者上下文（JWT 解碼） |

**錯誤碼**：

| 狀態碼 | 說明 | 常見原因 |
|--------|------|----------|
| 400 | 無效查詢 | 無法識別意圖 |
| 404 | Schema 未找到 | 指定的 table 不存在 |
| 422 | SQL 生成失敗 | LLM 無法生成有效 SQL |
| 500 | 執行錯誤 | DuckDB/S3 連線失敗 |

> **ETL 說明**：Data Agent 的 ETL（SAP/Ragic → S3 Parquet）屬於獨立專案，不在本系統範圍內。

---

### SSE 即時推送 (Server-Sent Events)

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/v1/sse/chat/{context_id}` | SSE 聊天流 |
| GET | `/api/v1/sse/events` | SSE 事件流 |
| GET | `/api/v1/sse/notifications` | SSE 通知流 |

**使用範例**:
```javascript
const eventSource = new EventSource('http://localhost:6500/api/v1/sse/chat/123');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
```

---

### WebSocket 即時通訊

| 方法 | 端點 | 說明 |
|------|------|------|
| WS | `/api/v1/ws/chat` | WebSocket 聊天 |
| WS | `/api/v1/ws/monitor` | WebSocket 監控 |

---

### 計費 (Billing)

| 方法 | 端點 | 說明 | 認證 |
|------|------|------|------|
| GET | `/api/v1/billing/usage` | 取得使用量 | 是 |
| GET | `/api/v1/billing/quota` | 取得配額 | 是 |
| GET | `/api/v1/billing/api-keys` | 取得 API Keys | 是 |
| POST | `/api/v1/billing/api-keys` | 建立 API Key | 是 |

---

### 服務管理 (Services)

| 方法 | 端點 | 說明 | 認證 |
|------|------|------|------|
| GET | `/api/v1/services` | 取得所有服務 | 否 |
| GET | `/api/v1/services/{name}` | 取得服務狀態 | 否 |
| POST | `/api/v1/services/{name}/start` | 啟動服務 | 是 |
| POST | `/api/v1/services/{name}/stop` | 停止服務 | 是 |

---

## 請求與回應格式

### 通用回應格式

所有 API 回應都遵循以下格式：

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

### 錯誤回應格式

```json
{
  "code": 404,
  "message": "Not Found",
  "data": null
}
```

### 常見狀態碼

| 狀態碼 | 說明 |
|--------|------|
| 200 | 成功 |
| 400 | 請求參數錯誤 |
| 401 | 未授權 (JWT 無效或過期) |
| 403 | 權限不足 |
| 404 | 資源不存在 |
| 409 | 衝突 (如使用者名稱已存在) |
| 429 | 請求過多 (Rate Limit) |
| 500 | 伺服器內部錯誤 |
| 502 | 閘道錯誤 (AI 服務無回應) |
| 503 | 服務不可用 |

---

## 錯誤處理

### 錯誤類型 (Error.rs)

在 `api/src/error.rs` 中定義：

```rust
pub enum ApiError {
    BadRequest(String),
    Unauthorized(String),
    Forbidden(String),
    NotFound(String),
    Conflict(String),
    RateLimited(u32, u64, u64),
    QuotaExceeded,
    BadGateway(String),
    ServiceUnavailable(String),
    InternalError(String),
}
```

### 使用方式

```rust
use crate::error::ApiError;

async fn handler() -> Result<impl IntoResponse, ApiError> {
    // 400 Bad Request
    Err(ApiError::BadRequest("Invalid input".to_string()))
    
    // 401 Unauthorized
    Err(ApiError::Unauthorized("Invalid token".to_string()))
    
    // 404 Not Found
    Err(ApiError::NotFound("User not found".to_string()))
    
    // 500 Internal Error
    Err(ApiError::InternalError("Database error".to_string()))
}
```

---

## 開發範例

### 新增一個簡單的 API 端點

**步驟 1**: 在 `api/src/api/mod.rs` 中新增路由

```rust
// 新增路由
.route("/api/v1/hello", get(hello_world))
```

**步驟 2**: 實作處理函數

```rust
use axum::{
    extract::Path,
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde::{Deserialize, Serialize};

// 定義請求/回應結構
#[derive(Debug, Deserialize)]
pub struct HelloRequest {
    name: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct HelloResponse {
    message: String,
}

// 實作處理函數
async fn hello_world(
    Query(params): Query<HelloRequest>,
) -> Result<impl IntoResponse, StatusCode> {
    let name = params.name.unwrap_or_else(|| "World".to_string());
    
    Ok(Json(ApiResponse::success(HelloResponse {
        message: format!("Hello, {}!", name),
    })))
}
```

### 新增一個需要認證的端點

```rust
use axum::{
    extract::Path,
    http::{header::AUTHORIZATION, HeaderMap, StatusCode},
    Json,
};

async fn get_user_profile(
    headers: HeaderMap,
    Path(user_key): Path<String>,
) -> Result<impl IntoResponse, StatusCode> {
    // 驗證 JWT Token
    let token = headers
        .get(AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;
    
    // 驗證 token
    let claims = crate::auth::verify_jwt(token)
        .map_err(|_| StatusCode::UNAUTHORIZED)?;
    
    // 從資料庫取得資料
    let db = crate::db::get_db();
    let users: Vec<User> = db
        .aql_bind_vars(
            "FOR u IN users FILTER u._key == @key LIMIT 1 RETURN u",
            [("key", serde_json::json!(user_key))].into(),
        )
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    
    let user = users.pop().ok_or(StatusCode::NOT_FOUND)?;
    
    Ok(Json(ApiResponse::success(user)))
}
```

### 新增一個 SSE 端點

```rust
use axum::{
    extract::Path,
    response::sse::{Event, Sse},
    routing::get,
    Router,
};
use futures::stream::{self, StreamExt};
use std::convert::Infallible;

pub fn create_router() -> Router {
    Router::new()
        .route("/api/v1/sse/stream/{id}", get(sse_stream))
}

pub async fn sse_stream(
    Path(id): Path<String>,
) -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
    let stream = stream::iter(vec![
        Ok(Event::default()
            .event("connect")
            .data(serde_json::json!({ "id": id }).to_string())),
        Ok(Event::default()
            .event("data")
            .data("Hello from SSE!")),
    ]);

    Sse::new(stream)
}
```

### 新增資料庫操作

```rust
use crate::db::{get_db, User};

// 新增使用者
async fn create_user(user: User) -> Result<User, ApiError> {
    let db = get_db();
    let col = db
        .collection("users")
        .await
        .map_err(|_| ApiError::InternalError("DB error".to_string()))?;
    
    col.create_document(user, Default::default())
        .await
        .map_err(|_| ApiError::InternalError("Failed to create user".to_string()))
}

// 查詢使用者
async fn get_user(key: &str) -> Result<User, ApiError> {
    let db = get_db();
    let users: Vec<User> = db
        .aql_bind_vars(
            "FOR u IN users FILTER u._key == @key LIMIT 1 RETURN u",
            [("key", serde_json::json!(key))].into(),
        )
        .await
        .map_err(|_| ApiError::InternalError("DB error".to_string()))?;
    
    users.pop().ok_or(ApiError::NotFound("User not found".to_string()))
}

// 更新使用者
async fn update_user(key: &str, patch: serde_json::Value) -> Result<User, ApiError> {
    let db = get_db();
    let col = db
        .collection("users")
        .await
        .map_err(|_| ApiError::InternalError("DB error".to_string()))?;
    
    col.update_document(key, patch, Default::default())
        .await
        .map_err(|_| ApiError::NotFound("User not found".to_string()))
}

// 刪除使用者
async fn delete_user(key: &str) -> Result<(), ApiError> {
    let db = get_db();
    let col = db
        .collection("users")
        .await
        .map_err(|_| ApiError::InternalError("DB error".to_string()))?;
    
    col.remove_document::<serde_json::Value>(key, Default::default(), None)
        .await
        .map_err(|_| ApiError::NotFound("User not found".to_string()))
}
```

---

## 新增 API 流程

### 1. 定義資料模型

在 `api/src/db/mod.rs` 或 `api/src/models/mod.rs` 中新增結構體：

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewModel {
    pub field1: String,
    pub field2: i32,
}
```

### 2. 新增 API 路由

在 `api/src/api/mod.rs` 中：

```rust
// 新增路由
.route("/api/v1/new-resource", get(list_new_resources).post(create_new_resource))
.route("/api/v1/new-resource/{key}", get(get_new_resource).put(update_new_resource).delete(delete_new_resource))
```

### 3. 實作處理函數

```rust
async fn list_new_resources() -> Result<impl IntoResponse, StatusCode> {
    let db = get_db();
    // 查詢邏輯
    Ok(Json(ApiResponse::success(data)))
}

async fn create_new_resource(Json(payload): Json<NewModel>) -> Result<impl IntoResponse, StatusCode> {
    // 建立邏輯
    Ok(Json(ApiResponse::success(created)))
}
```

### 4. 新增單元測試

在 `.tests/rs/` 目錄中新增測試檔案：

```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_model_serialization() {
        let model = NewModel {
            field1: "test".to_string(),
            field2: 42,
        };
        let json = serde_json::to_string(&model).unwrap();
        assert!(json.contains("test"));
    }
}
```

### 5. 新增整合測試

在 `.tests/py/test_integration.py` 中新增測試：

```python
def test_new_resource():
    status, body = make_request("GET", "/api/v1/new-resource")
    assert status == 200
```

---

## 測試

### 執行單元測試

```bash
cd api
cargo test
```

### 執行整合測試

```bash
python3 .tests/py/test_integration.py
```

### 程式碼檢查

```bash
cd api
cargo check
cargo clippy -- -D warnings
```

---

## Agent 管理 (Agents)

### 數據模型

```json
{
  "_key": "agent-001",
  "name": "文檔處理助手",
  "description": "專業文檔解析助手，支持 PDF、Word、PPT 等格式文件的智能解讀與內容提取",
  "icon": "FileTextOutlined",
  "status": "online",
  "usage_count": 1250,
  "group_key": "productivity",
  "agent_type": "tool",
  "source": "local",
  "endpoint_url": "http://localhost:8000",
  "api_key": null,
  "auth_type": "none",
  "llm_model": "gpt-4",
  "temperature": 0.7,
  "max_tokens": 2000,
  "system_prompt": null,
  "knowledge_bases": ["kb-001", "kb-002"],
  "data_sources": ["db-sales"],
  "tools": ["tool-web-search"],
  "opening_lines": ["你好，我是文檔處理助手"],
  "capabilities": ["PDF解析", "Word解析"],
  "is_favorite": false,
  "created_by": "admin",
  "updated_by": "admin",
  "created_at": "2026-03-18T08:00:00Z",
  "updated_at": "2026-03-18T08:00:00Z"
}
```

### 字段說明

| 字段 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `_key` | String | 是 | UUID，唯一識別符 |
| `name` | String | 是 | Agent 顯示名稱 |
| `description` | String | 否 | Agent 描述 |
| `icon` | String | 否 | 圖標名稱 (Ant Design Icons) |
| `status` | Enum | 是 | 狀態: online/maintenance/deprecated/registering |
| `usage_count` | Integer | 否 | 使用次數，預設 0 |
| `group_key` | String | 是 | 分組 Key |
| `agent_type` | Enum | 否 | 類型: knowledge/data/bpa/tool |
| `source` | Enum | 否 | 來源: local/third_party，預設 local |
| `endpoint_url` | String | 否 | Endpoint URL |
| `api_key` | String | 否 | API Key (第三方代理用) |
| `auth_type` | Enum | 否 | 認證方式: none/bearer/basic/oauth2 |
| `llm_model` | String | 否 | LLM 模型名稱 |
| `temperature` | Float | 否 | Temperature (0-2) |
| `max_tokens` | Integer | 否 | 最大 Tokens |
| `system_prompt` | String | 否 | System Prompt |
| `knowledge_bases` | Array | 否 | 知識庫權限列表 |
| `data_sources` | Array | 否 | 資料權限列表 |
| `tools` | Array | 否 | 工具權限列表 |
| `opening_lines` | Array | 否 | 開場白列表 |
| `capabilities` | Array | 否 | 能力描述列表 |
| `is_favorite` | Boolean | 否 | 是否收藏 |
| `created_by` | String | 系統 | 創建者 |
| `updated_by` | String | 系統 | 更新者 |
| `created_at` | DateTime | 系統 | 創建時間 |
| `updated_at` | DateTime | 系統 | 更新時間 |

### API 端點

| 方法 | 路徑 | 說明 | 認證 |
|------|------|------|------|
| GET | /api/v1/agents | 取得所有 Agents | 是 |
| GET | /api/v1/agents/:key | 取得單一 Agent | 是 |
| POST | /api/v1/agents | 建立 Agent | 是 |
| PUT | /api/v1/agents/:key | 更新 Agent | 是 |
| DELETE | /api/v1/agents/:key | 刪除 Agent | 是 |
| PATCH | /api/v1/agents/:key/favorite | 切換收藏狀態 | 是 |

### API 範例

#### 取得所有 Agents

```bash
curl -X GET http://localhost:6500/api/v1/agents \
  -H "Authorization: Bearer <token>"
```

**回應**:
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "_key": "agent-001",
      "name": "文檔處理助手",
      "description": "專業文檔解析助手",
      "icon": "FileTextOutlined",
      "status": "online",
      "usage_count": 1250,
      "group_key": "productivity"
    }
  ]
}
```

#### 建立 Agent

```bash
curl -X POST http://localhost:6500/api/v1/agents \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "文檔處理助手",
    "description": "專業文檔解析助手",
    "icon": "FileTextOutlined",
    "status": "online",
    "group_key": "productivity",
    "agent_type": "tool",
    "source": "local",
    "endpoint_url": "http://localhost:8000"
  }'
```

#### 更新 Agent

```bash
curl -X PUT http://localhost:6500/api/v1/agents/agent-001 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "文檔處理助手 (新版)",
    "status": "maintenance"
  }'
```

#### 刪除 Agent

```bash
curl -X DELETE http://localhost:6500/api/v1/agents/agent-001 \
  -H "Authorization: Bearer <token>"
```

#### 切換收藏狀態

```bash
curl -X PATCH http://localhost:6500/api/v1/agents/agent-001/favorite \
  -H "Authorization: Bearer <token>"
```

---

## 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `PORT` | 6500 | API 伺服器端口 |
| `ARANGODB_URL` | http://localhost:8529 | ArangoDB URL |
| `ARANGODB_DATABASE` | abc_desktop | 資料庫名稱 |
| `ARANGODB_USER` | root | 資料庫使用者 |
| `ARANGODB_PASSWORD` | abc_desktop_2026 | 資料庫密碼 |
| `OLLAMA_BASE_URL` | http://localhost:11434 | Ollama URL |
| `RATE_LIMIT_MAX_REQUESTS` | 100 | Rate limit 請求數 |
| `RATE_LIMIT_WINDOW_SECONDS` | 60 | Rate limit 時間窗口 |

---

## 參考資源

- [Axum 文件](https://docs.rs/axum/)
- [ArangoDB Rust Driver](https://github.com/ArangoDB-Community/arangors)
- [JWT Rust](https://github.com/Keats/jsonwebtoken)
- [BCrypt](https://github.com/Keats/bcrypt-rs)

---

## 更新記錄

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-03-18 | 1.0.0 | Daniel Chung | 初始版本 |
