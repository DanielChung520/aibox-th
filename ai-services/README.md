---
lastUpdate: 2026-04-24 10:07:45
author: Daniel Chung
version: 2.1.0
---

# AI Services

TWHC Python FastAPI 微服務集群，提供 AI Agent 系統的後端能力。

## 服務架構

| 服務 | 端口 | 模組路徑 | 說明 |
|------|------|----------|------|
| AITask | 8001 | `aitask/` | AI 任務調度服務 |
| unified_agents | 8011 | `unified_agents/` | 統一入口，承載 Data Agent `/da/*`、Knowledge `/ka/*`、BPA 等路由 |
| MCP Tools | 8004 | `mcp_tools/` | MCP 工具集成服務 |
| Knowledge Agent | 8007 | `knowledge_agent/` | 知識庫 RAG 管理服務 |
| Memory Agent | 8008 | `memory_agent/` | AI 增強記憶系統 |

## 目錄結構

```text
ai-services/
├── requirements.txt          # 共用 Python 依賴
├── aitask/                   # AI Task 服務 (port 8001)
│   └── main.py
├── data_agent/               # Data Agent 實作模組（由 unified_agents 掛載 /da/*）
│   ├── __init__.py
│   ├── main.py               # FastAPI 入口，掛載子路由
│   ├── intent_rag/           # 資料查詢意圖 RAG 子模組
│   │   ├── __init__.py
│   │   └── router.py         # /intent-rag/* 路由 (Qdrant + Ollama)
│   └── query/                # NL→SQL 查詢子模組
│       ├── __init__.py
│       ├── router.py          # /query/* 路由
│       └── nl2sql/            # 3-tier NL→SQL Pipeline
│           ├── __init__.py
│           ├── models.py      # Pydantic 資料模型
│           ├── exceptions.py  # 自訂例外
│           ├── orchestrator.py # Pipeline 調度器
│           ├── intent_classifier.py  # 意圖分類 (template/small/large)
│           ├── schema_retriever.py   # Schema 向量檢索
│           ├── plan_generator.py     # JSON Query Plan 生成
│           ├── sql_generator.py      # SQL 生成 (3-tier hybrid)
│           ├── validator.py          # SQL 安全驗證 + sqlglot
│           └── executor.py           # DuckDB 執行引擎
├── knowledge_agent/          # Knowledge Agent 服務 (port 8007)
│   ├── __init__.py
│   └── main.py
├── memory_agent/             # Memory Agent 服務 (port 8008)
│   ├── __init__.py
│   ├── main.py
│   └── core/                 # 核心模組
│       ├── __init__.py
│       ├── models.py          # 類型定義
│       ├── storage.py         # 文件存儲
│       ├── security.py       # 安全模組
│       ├── recall.py          # 召回模組
│       ├── working_memory.py  # 工作記憶
│       ├── session_memory.py  # 會話記憶
│       └── consolidation.py   # 離線整理
├── bpa/                      # BPA 服務群組
│   └── mm_agent/             # 物料管理 Agent (port 8005)
│       ├── __init__.py
│       └── main.py
├── mcp_tools/                # MCP Tools 服務 (port 8004)
│   └── main.py
└── datalake/                 # 資料湖種子資料與 Schema 工具
    ├── __init__.py
    ├── seed_schema.py         # ArangoDB Schema 初始化
    ├── seed_inventory_tables.py  # 庫存相關表結構
    ├── generate_sap_data.py      # SAP 模擬數據生成
    └── generate_inventory_data.py # 庫存模擬數據生成
```

## NL→SQL Pipeline 架構

Data Agent 實現 3-tier 混合 SQL 生成策略：

| 層級 | 策略 | 適用場景 | LLM |
|------|------|----------|-----|
| Template | SQL 模板替換 | 簡單查詢（單表、固定模式） | 無 |
| Small LLM | 聚焦 Schema + LLM | 中等複雜度查詢 | `qwen2.5-coder:7b` |
| Large LLM | 完整推理 | 複雜多表 JOIN | `qwen3:32b` |

Pipeline 流程：
```
Intent Classifier → Schema Retriever → Plan Generator → SQL Generator → Validator → Executor
```

## 本地啟動

```bash
# 建立虛擬環境
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 啟動各服務
uvicorn unified_agents.main:app --port 8011 --reload
uvicorn knowledge_agent.main:app --port 8007 --reload
uvicorn bpa.mm_agent.main:app --port 8005 --reload
uvicorn aitask.main:app --port 8001 --reload
uvicorn mcp_tools.main:app --port 8004 --reload
```

或使用專案根目錄的 `start.sh`：

```bash
./start.sh start    # 啟動所有服務（含 Rust API Gateway）
./start.sh status   # 查看服務狀態
./start.sh stop     # 停止所有服務
```

## 外部依賴

| 依賴 | 用途 | 預設地址 |
|------|------|----------|
| ArangoDB | Schema 存儲、意圖目錄 | `http://localhost:8529` |
| Qdrant | 向量檢索 | `http://localhost:6333` |
| Ollama | LLM 推理 + Embedding | `http://localhost:11434` |
| SeaweedFS | 統一檔案備份儲存 | `http://localhost:8888` |
| DuckDB | SQL-on-Parquet 查詢引擎 | 內嵌 (in-process) |

## 環境變數

各服務透過環境變數配置，預設使用 localhost。詳見 `api/.env`。

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `ARANGO_URL` | ArangoDB 連線 | `http://localhost:8529` |
| `ARANGO_DB` | 資料庫名稱 | `abc_desktop` |
| `QDRANT_URL` | Qdrant 連線 | `http://localhost:6333` |
| `OLLAMA_BASE_URL` | Ollama API | `http://localhost:11434` |
| `SEAWEED_URL` | SeaweedFS Filer | `http://localhost:8888` |

## 程式碼品質

```bash
# Lint 檢查
ruff check ai-services/

# 格式檢查
ruff format --check ai-services/

# 類型檢查
mypy ai-services/ --ignore-missing-imports
```

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-24 | 2.1.0 | Daniel Chung | 補充 unified_agents(8011) 為 Data Agent 對外整合入口，釐清 data_agent/ 為實作模組 |
| 2026-03-23 | 2.0.0 | Daniel Chung | 重構目錄：data_agent(8003), knowledge_agent(8007), bpa/mm_agent(8005), datalake; 新增 NL→SQL Pipeline |
| 2026-03-18 | 1.0.0 | Daniel Chung | 初始化 ai-services FastAPI 模板與服務目錄 |
