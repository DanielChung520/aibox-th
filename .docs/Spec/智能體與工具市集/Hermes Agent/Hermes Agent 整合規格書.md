---
lastUpdate: 2026-04-11 23:30:00
author: Daniel Chung
version: 1.0.0
---

# Hermes Agent 效率工具整合規格書

## 1. 目標與定位

將 **Hermes Agent**（Nous Research）整合進 AIBox，作為一個**可被其他 AI Agent 調用的效率工具**。

**不做的**：獨立 UI 對話介面（用戶直接點擊 Hermes 聊天）。
**做的**：Hermes 作為後端 Agent 能力，被 AITask、Data Agent 等服務在處理複雜任務時呼叫。

### 1.1 整合價值

| 價值點 | 說明 |
|--------|------|
| 自我改進學習循環 | 任務完成後自動生成可重用技能，隨使用累積能力 |
| 持久化跨 Session 記憶 | MEMORY.md / USER.md / FTS5 session search |
| 技能自動積累 | 從成功經驗中提取技能，下次相似問題自動套用 |
| 研究導向 | RL 軌跡生成可用於未來模型訓練 |

### 1.2 Hermes 記憶存放位置

```
~/.hermes/                          # Hermes 主目錄（可透過 HERMES_HOME 自訂）
├── memories/
│   ├── MEMORY.md                   # Agent 個人筆記 (~2,200 chars, ~800 tokens)
│   └── USER.md                     # 用戶 profile (~1,375 chars, ~500 tokens)
├── SOUL.md                         # Agent 人格定義
├── skills/                         # 自動生成的技能文件
├── config.yaml                     # 主要設定
├── .env                            # API keys / secrets
├── state.db                        # SQLite + FTS5（所有對話歷史，無上限）
├── sessions/                       # Gateway 對話 session
└── logs/                           # 錯誤日誌、Gateway 日誌
```

---

## 2. 系統架構

### 2.1 整合架構圖

```
┌─────────────────────────────────────────────────────────────┐
│               Hermes Agent Tool Layer                       │
│               (ai-services/tools/hermes/)                   │
│  - REST API 適配                                            │
│  - 任務轉發 (hermes mcp serve 或 hermes chat)              │
│  - 回應格式化                                               │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │  AITask    │ │ Data Agent │ │ Knowledge  │
   │  (8001)    │ │  (8003)    │ │  Agent     │
   │            │ │            │ │  (8007)    │
   └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
         │               │               │
         │   複雜任務 ────┼───────────────┘
         │               │                │
         ▼               ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│               Hermes Agent Proxy Layer                      │
│               (ai-services/hermes/)                   │
│  - REST API 適配                                            │
│  - 任務轉發 (hermes mcp serve 或 hermes chat)              │
│  - 回應格式化                                               │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Hermes Agent         │
              │  (~/.hermes/)         │
              │                       │
              │  ├── 47 內建工具      │
              │  ├── 自我改進技能系統  │
              │  ├── 跨 Session 記憶   │
              │  └── MCP Client       │
              └───────────────────────┘
```

### 2.2 兩種運行模式

| 模式 | 說明 | 適用場景 |
|------|------|----------|
| **CLI Mode** | `hermes chat` 互動對話 | 複雜多輪任務、學習循環 |
| **MCP Mode** | `hermes mcp serve` 提供工具 | 當作工具集被調用 |

**本整合採用 CLI Mode**，因為 Hermes 的核心價值在於它的**學習循環和跨 Session 記憶**，這需要 Agent 完整運行，不能只是工具調用。

---

## 3. Hermes Agent Proxy Service

### 3.1 服務定位

在 `ai-services/hermes/` 建立 proxy 服務，作為 AIBox 與 Hermes Agent 之間的橋樑。

**為什麼需要 Proxy？**

1. Hermes CLI 是交互式終端，不適合直接 API 調用
2. 需要格式轉換（AIBox 內部格式 ↔ Hermes 格式）
3. 需要生命週期管理（啟動、停止、健康檢查）
4. 需要認證轉發（AIBox JWT → Hermes session）

### 3.2 目錄結構

```
ai-services/tools/
└── hermes/                        # Hermes Agent Tool (新增)
    ├── __init__.py
    ├── main.py                     # FastAPI 入口
    ├── proxy.py                    # Hermes CLI 進程管理
    ├── models.py                   # Pydantic 請求/回應模型
    ├── router.py                   # API 路由
    ├── auth.py                     # JWT 轉換為 Hermes session
    └── config.py                   # 設定（HERMES_HOME 等）
```

### 3.3 API 端點設計

| 方法 | 路徑 | 說明 |
|------|------|------|
| `POST` | `/hermes/query` | 發送查詢到 Hermes |
| `GET` | `/hermes/status` | Hermes 運行狀態 |
| `POST` | `/hermes/start` | 啟動 Hermes 進程 |
| `POST` | `/hermes/stop` | 停止 Hermes 進程 |
| `GET` | `/hermes/skills` | 列出 Hermes 已學習的技能 |
| `GET` | `/hermes/memory` | 查詢 MEMORY.md 內容 |
| `POST` | `/hermes/session-search` | FTS5 對話歷史搜索 |
| `GET` | `/health` | 健康檢查 |

### 3.4 請求 / 回應格式

**POST /hermes/query**

```json
// Request
{
  "query": "分析這段程式碼的效能瓶頸並提出優化建議",
  "context": {
    "code": "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)",
    "language": "python"
  },
  "mode": "advisory",
  "user_id": "user123"
}

// Response
{
  "code": 0,
  "data": {
    "response": "## 分析\n效能瓶頸在於指數級遞迴...",
    "session_id": "sess_abc123",
    "skills_created": 1,
    "skill_name": "fibonacci_optimization",
    "memory_updated": true,
    "model_used": "qwen2.5-coder:14b",
    "latency_ms": 3200
  }
}
```

### 3.5 Hermes 進程管理

```python
# hermes/proxy.py
import asyncio
import subprocess
import signal
from pathlib import Path

class HermesProcessManager:
    def __init__(self, hermes_home: str = "~/.hermes"):
        self.hermes_home = Path(hermes_home).expanduser()
        self.process: subprocess.Popen | None = None

    def start(self, mode: str = "chat") -> bool:
        """啟動 Hermes CLI 或 MCP server"""
        cmd = ["hermes", mode]
        self.process = subprocess.Popen(
            cmd,
            cwd=self.hermes_home,
            env={**os.environ, "HERMES_HOME": str(self.hermes_home)},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return self.process.poll() is None

    def send_query(self, query: str) -> str:
        """發送查詢並取得回應（簡易版）"""
        self.process.stdin.write(f"{query}\n".encode())
        self.process.stdin.flush()
        return self._read_response()

    def stop(self):
        """優雅停止 Hermes"""
        self.process.send_signal(signal.SIGTERM)
        self.process.wait(timeout=10)
```

---

## 4. Rust API Gateway 整合

### 4.1 路由設計

在 Rust API Gateway 新增 Hermes 相關端點：

```rust
// api/src/api/hermes.rs
pub fn configure_hermes_routes(cfg: &mut Router) {
    cfg
        .route("/hermes/query", post(hermes_query))
        .route("/hermes/status", get(hermes_status))
        .route("/hermes/skills", get(hermes_skills))
        .route("/hermes/memory", get(hermes_memory))
        .route("/hermes/session-search", post(hermes_session_search))
}
```

### 4.2 轉發流程

```
[前端/Agent]
    │ POST /api/v1/hermes/query
    ▼
[Rust API Gateway]
    │ 讀取 JWT，驗證身份
    │ 附加 X-User-ID, X-Session-ID header
    ▼
[Python hermes (8009)]
    │ 轉發給 Hermes CLI
    ▼
[Hermes Agent]
    │ 執行任務，自動學習
    ▼
[Python hermes]
    │ 格式化回應
    ▼
[Rust API Gateway]
    │ 附加用量到 billiing
    ▼
[前端/Agent]
```

---

## 5. 與現有 Agent 的整合

### 5.1 AITask 調用 Hermes

Hermes 適合處理的任務：

| 任務類型 | 說明 | 觸發條件 |
|----------|------|----------|
| 複雜程式重構 | 涉及多檔案、跨架構的改動 | 任務標記 `complexity: high` |
| 效能分析 | 需要深入 profiling 和優化建議 | 任務標記 `domain: performance` |
| 自動化腳本生成 | 需要跨平台兼容性處理 | 任務標記 `domain: automation` |
| 複雜 Debug | 跨多個系統的錯誤追蹤 | 任務標記 `domain: debug` |

### 5.2 調用流程

```python
# ai-services/aitask/graph/nodes/hermes_call.py

async def call_hermes(context: AgentContext, task: Task) -> TaskResult:
    """當 AITask 判斷任務適合 Hermes 時呼叫"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{HERMES_URL}/hermes/query",
            json={
                "query": task.description,
                "context": task.context,
                "mode": task.hermes_mode or "advisory",
                "user_id": context.user_id,
            },
            headers={"Authorization": f"Bearer {context.token}"},
        )
        result = response.json()
        return TaskResult(
            content=result["data"]["response"],
            skills_created=result["data"].get("skills_created", 0),
            memory_updated=result["data"].get("memory_updated", False),
        )
```

---

## 6. Herme s記憶管理介面

### 6.1 記憶查詢端點

透過 API 暴露 Hermes 的記憶能力，讓其他 Agent 可以查询：

```
GET /hermes/memory          → 讀取 MEMORY.md 當前內容
GET /hermes/skills          → 列出所有已學習的技能
POST /hermes/session-search → 搜索過往對話
```

### 6.2 技能系統

Hermes 自動生成的技能存放在 `~/.hermes/skills/`：

```
~/.hermes/skills/
├── api_error_handling.md   # 從 API 錯誤處理經驗生成
├── sql_query_optimization.md
├── docker_debug_workflow.md
└── ...
```

技能可以被 AITask 或其他 Agent 在執行任務時引用。

---

## 7. Herme s MCP 整合（可選擴展）

Hermes 也支援作為 **MCP Server** 運行，可被其他 MCP Client 工具呼叫：

```bash
# Hermes 啟動為 MCP server
hermes mcp serve
```

在 `~/.hermes/config.yaml` 中設定：

```yaml
mcp_servers:
  aibox:
    url: "http://localhost:8004"  # 連接 AIBox MCP Tools
    enabled: true
```

---

## 8. 部署配置

### 8.1 環境變數

```env
# ai-services/.env 新增
HERMES_HOME=~/.hermes
HERMES_PORT=8009
HERMES_CLI_PATH=hermes  # 或完整路徑
HERMES_DEFAULT_MODEL=qwen2.5-coder:14b
```

### 8.2 Hermes 安裝需求

```bash
# 安裝 Hermes
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# 確認安裝
hermes --version
```

### 8.3 啟動順序

```bash
# 1. 啟動 Hermes Proxy
uvicorn hermes.main:app --port 8009 --reload

# 2. Hermes 進程由 proxy 管理自動啟動
# 或手動啟動：
# hermes chat &
```

---

## 9. 與現有建設計劃的關係

本規格是「效率工具代理」建設計劃（`建設計劃.md`）的**擴展**：

| 現有建設計劃 | 本規格 |
|-------------|--------|
| Oracle Agent（P0）| Hermes 是另一種 Agent 類型 |
| 內部 LLM 顧問 | Hermes 是外部獨立 Agent，有自我學習能力 |
| External Tools（天氣、搜尋）| Hermes 可呼叫這些外部工具擴展能力 |

**差異**：

| 維度 | Oracle Agent | Hermes Agent |
|------|-------------|--------------|
| 類型 | 內部 LLM 推理 | 獨立運行進程 |
| 學習能力 | 無（每次相同）| 有（技能自動積累）|
| 記憶 | 無持久化 | 三層記憶架構 |
| 部署 | 純 API | 需要 CLI 進程管理 |
| 整合複雜度 | 低 | 中 |

---

## 10. 實施計劃

### Phase 1：基礎設施（0.5 天）

- [ ] 確認 Hermes 已安裝於系統
- [ ] 建立 `ai-services/hermes/` 目錄結構
- [ ] 實作 Hermes 進程管理（proxy.py）
- [ ] 實作基本 API 端點（status, start, stop）

### Phase 2：核心整合（1 天）

- [ ] 實作 `/hermes/query` 端點
- [ ] 實作 `/hermes/skills` 端點
- [ ] 實作 `/hermes/memory` 端點
- [ ] 實作 Rust API Gateway 路由轉發
- [ ] 單元測試

### Phase 3：進階整合（1 天）

- [ ] 實作 FTS5 session search
- [ ] AITask → Hermes 調用流程
- [ ] 錯誤處理與重試機制
- [ ] 用量記錄（billing）

### Phase 4：觀察與優化（0.5 天）

- [ ] Hermes 技能積累監控
- [ ] 記憶使用率監控
- [ ] 效能調優

---

## 11. 風險與對策

| 風險 | 機率 | 影響 | 對策 |
|------|------|------|------|
| Hermes CLI 回應格式不稳定 | 中 | 中 | proxy 增加 parsing 容錯層 |
| 進程管理記憶體洩漏 | 低 | 中 | 定期重啟 Hermes 進程 |
| Herm es技能與 AITask 衝突 | 低 | 低 | 透過 intent routing 區分 |
| Hermes 記憶無限增長 | 中 | 低 | 設定定期 consolidation cron |

---

## 12. 附錄

### A. Hermes CLI 常用命令

```bash
hermes chat              # 互動式對話
hermes mcp serve         # 作為 MCP server 運行
hermes skills            # 查看技能列表
hermes skills publish    # 發布技能
hermes update            # 更新版本
hermes doctor            # 診斷問題
```

### B. Hermes 記憶檔案位置

| 檔案 | 路徑 | 用途 |
|------|------|------|
| MEMORY.md | `~/.hermes/memories/MEMORY.md` | Agent 個人筆記 |
| USER.md | `~/.hermes/memories/USER.md` | 用戶 profile |
| SOUL.md | `~/.hermes/SOUL.md` | Agent 人格 |
| skills/ | `~/.hermes/skills/` | 自動生成技能 |
| state.db | `~/.hermes/state.db` | SQLite FTS5 對話歷史 |

### C. Hermes 設定參考

```yaml
# ~/.hermes/config.yaml
memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200
  user_char_limit: 1375

model:
  provider: openrouter
  model: qwen2.5-coder-14b

terminal:
  backend: local  # 或 docker / ssh / singu larity / modal
```
