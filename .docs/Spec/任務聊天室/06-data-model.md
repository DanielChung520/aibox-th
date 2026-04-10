---
lastUpdate: 2026-04-10 21:15:31
author: Daniel Chung
version: 1.1.0
status: 正式版
parent: 00-index.md
---

# 06 — 資料模型與 ArangoDB Checkpointer

> **前置閱讀**: [00-index.md](./00-index.md)、[01-architecture.md](./01-architecture.md)  
> **本文件涵蓋**: 5 個 ArangoDB Collections 設計、Schema 定義、LangGraph Checkpointer 適配器、記憶持久化策略、會話恢復流程

---

## 6.1 ArangoDB Collections 設計

任務聊天室需要以下 ArangoDB 集合：

| 集合名稱 | 類型 | 用途 | 索引 |
|---------|------|------|------|
| `chat_sessions` | Document | 會話元資料 | `user_key` (hash), `status` (hash), `created_at` (skiplist desc) |
| `chat_messages` | Document | 對話訊息 | `session_key` (hash), `created_at` (skiplist), `session_key+created_at` (compound) |
| `chat_checkpoints` | Document | LangGraph 狀態快照 | `thread_id` (hash), `thread_id+checkpoint_id` (compound unique) |
| `chat_checkpoint_writes` | Document | LangGraph 寫入記錄 | `thread_id+task_id+idx` (compound unique) |
| `tool_executions` | Document | 工具調用記錄 | `session_key` (hash), `tool_name` (hash) |

---

## 6.2 Schema 定義

### chat_sessions

```json
{
  "_key": "ses_uuid_v4",
  "user_key": "admin",
  "title": "物料查詢 — 2026-03-27",
  "provider": "ollama",
  "model": "llama3.2:latest",
  "status": "active",
  
  "tags_5w1h": {
    "what": "查詢內容描述",
    "who": "使用者、助理",
    "when": "時間",
    "where": "地點",
    "why": "原因",
    "how": "方法"
  },
  
  "created_at": "2026-03-27T10:00:00Z",
  "updated_at": "2026-03-27T10:30:00Z"
}
```

> **重要**: 
> - 使用 `user_key` 而非 `user_id`（從 JWT claims.sub 提取）
> - `provider` + `model` 用於記錄該 session 使用的 AI 模型
> - 工作區隔離：所有 API 查詢都需透過 `user_key` 過濾

### chat_messages

```json
{
  "_key": "msg_uuid_v4",
  "session_key": "ses_uuid_v4",
  "role": "user | assistant",
  "content": "Markdown 格式的訊息內容",
  "thinking": "AI 思考過程（可選）",
  "tokens": 1650,
  "created_at": "2026-03-27T10:05:00Z"
}
```

### chat_checkpoints（LangGraph Checkpointer）

```json
{
  "_key": "chk_uuid",
  "thread_id": "ses_uuid_v4",
  "checkpoint_ns": "",
  "checkpoint_id": "1ef...uuid",
  "parent_checkpoint_id": "1ef...parent_uuid",
  
  "checkpoint": {
    "v": 1,
    "id": "1ef...uuid",
    "ts": "2026-03-27T10:05:00.000000+00:00",
    "channel_values": {
      "messages": ["...serialized HumanMessage / AIMessage list..."],
      "session_id": "ses_uuid_v4",
      "user_id": "admin",
      "mode": "open_chat",
      "intent": "data_query",
      "entities": {},
      "tool_results": [],
      "memory_summary": "..."
    },
    "channel_versions": {
      "messages": "3",
      "session_id": "1"
    },
    "versions_seen": {}
  },
  
  "metadata": {
    "source": "loop",
    "step": 5,
    "writes": {
      "chat_responder": {
        "messages": ["AIMessage(content='...')"]
      }
    }
  },
  
  "created_at": "2026-03-27T10:05:00Z"
}
```

### chat_checkpoint_writes

```json
{
  "_key": "chkw_thread_task_idx",
  "thread_id": "ses_uuid_v4",
  "checkpoint_ns": "",
  "checkpoint_id": "1ef...uuid",
  "task_id": "task_uuid",
  "idx": 0,
  "channel": "messages",
  "type": "list",
  "value": "...serialized message...",
  "created_at": "2026-03-27T10:05:00Z"
}
```

---

## 6.3 ArangoDB LangGraph Checkpointer 適配器

LangGraph 原生支援 `AsyncPostgresSaver`，本專案需自訂 ArangoDB 適配器：

```python
# ai-services/aitask/checkpointer/arango_saver.py

from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata
from typing import AsyncIterator, Optional, Sequence
from arango import ArangoClient

class ArangoDBSaver(BaseCheckpointSaver):
    """
    ArangoDB-based checkpointer for LangGraph.
    
    實作 BaseCheckpointSaver 介面，將 LangGraph 狀態持久化到 ArangoDB。
    使用 python-arango 驅動，支援異步操作。
    
    Collections required:
    - chat_checkpoints: 狀態快照
    - chat_checkpoint_writes: 寫入記錄
    """
    
    def __init__(self, db_url: str, db_name: str, username: str, password: str):
        super().__init__()
        # 初始化 ArangoDB 連線
    
    async def aget_tuple(self, config: dict) -> Optional[CheckpointTuple]:
        """
        根據 thread_id 取得最新 checkpoint。
        AQL: FOR c IN chat_checkpoints
             FILTER c.thread_id == @thread_id
             SORT c.created_at DESC LIMIT 1
             RETURN c
        """
    
    async def alist(self, config: dict, *, 
                    filter: Optional[dict] = None,
                    before: Optional[dict] = None,
                    limit: Optional[int] = None) -> AsyncIterator[CheckpointTuple]:
        """
        列出指定 thread 的所有 checkpoints。
        支援分頁和過濾。
        """
    
    async def aput(self, config: dict, checkpoint: Checkpoint, 
                   metadata: CheckpointMetadata,
                   new_versions: dict) -> dict:
        """
        寫入新的 checkpoint。
        使用 ArangoDB 交易確保原子性。
        """
    
    async def aput_writes(self, config: dict, 
                          writes: Sequence[tuple[str, Any]], 
                          task_id: str) -> None:
        """
        寫入 checkpoint_writes 記錄。
        使用 UPSERT 確保冪等性。
        """
    
    async def setup(self) -> None:
        """
        建立所需 collections 和索引。
        應在應用啟動時呼叫。
        """
```

### 關鍵實作注意事項

1. **序列化**：LangGraph 的 `channel_values` 包含 `BaseMessage` 物件，需使用 `langgraph.checkpoint.serde.jsonplus` 進行 JSON 序列化/反序列化
2. **交易安全**：`aput` 必須在 ArangoDB Transaction 中執行（同時寫入 checkpoints + checkpoint_writes）
3. **索引策略**：`thread_id + checkpoint_id` 複合唯一索引確保不重複
4. **清理策略**：保留最近 N 個 checkpoints（建議 N=50，從 `system_params.chat.checkpoint_retention_count` 讀取），定期清理舊記錄

---

## 6.4 對話記憶管理（Memory Persistence）

### 短期記憶（Session Scope）

存放在 LangGraph State 的 `messages` 欄位，隨 checkpoint 一起持久化：

```python
# 滑動窗口策略
MAX_MESSAGES_IN_CONTEXT = 20  # 配置於 system_params

def sliding_window_trim(messages: list[BaseMessage]) -> list[BaseMessage]:
    """保留最近 N 條訊息，超出部分摘要化"""
    if len(messages) <= MAX_MESSAGES_IN_CONTEXT:
        return messages
    
    # 前面的訊息做摘要
    old_messages = messages[:-MAX_MESSAGES_IN_CONTEXT]
    recent_messages = messages[-MAX_MESSAGES_IN_CONTEXT:]
    
    summary = summarize_messages(old_messages)  # 調用 LLM 摘要
    
    return [SystemMessage(content=f"[對話摘要] {summary}")] + recent_messages
```

### 長期記憶（Cross-Session）

未來擴展，目前不在本規格範疇。預留 `user_memory` collection 結構：

```json
{
  "_key": "mem_uuid",
  "user_id": "users/admin_key",
  "memory_type": "preference | fact | context",
  "content": "使用者偏好使用倉庫 A 作為預設查詢範圍",
  "source_session_id": "ses_uuid",
  "relevance_score": 0.85,
  "created_at": "2026-03-27T10:00:00Z",
  "expires_at": null
}
```

> **AAM 記憶管理框架**：若採用 AAM 架構（見 `.docs/Spec/記憶管理/`），此處可擴展為 4 層記憶結構。目前 v1.0 先以滑動窗口 + 摘要化為基礎。

---

## 6.5 會話恢復流程

```
使用者點擊歷史會話 → loadSession(sessionId)
  │
  ├── 1. 從 chat_sessions 讀取元資料
  │      → 確認 status === 'active'
  │
  ├── 2. 從 chat_messages 讀取訊息列表
  │      → AQL: FOR m IN chat_messages
  │               FILTER m.session_id == @sid
  │               SORT m.created_at ASC
  │               RETURN m
  │
  ├── 3. 從 chat_checkpoints 讀取最新 LangGraph 狀態
  │      → 恢復 TopState（包含 entities、intent 等上下文）
  │
  ├── 4. 恢復前端狀態
  │      → mode = session.mode
  │      → messages = loaded messages
  │      → 若 mode === 'bpa_workflow' 且 bpa_context.final_status 為 null
  │        → 嘗試重連 SSE（BPA 可能仍在執行）
  │
  └── 5. 就緒
```

---

> **API 端點（會話管理）**：見 [08-api-endpoints.md](./08-api-endpoints.md) §8.2.1–8.2.3。  
> **前端 ChatStore.loadSession**：見 [05-frontend-orchestrator.md](./05-frontend-orchestrator.md) §5.7。
