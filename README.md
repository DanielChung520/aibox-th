---
lastUpdate: 2026-03-25 23:16:31
author: Daniel Chung
version: 1.3.0
---

# ABC Desktop 管理系统

跨平台桌面管理应用，基于 Tauri + React + Ant Design 构建，后端采用 Rust Axum + ArangoDB。

**AI Agent 系统扩展**: 支持 AI 聊天、数据查询、知识库管理、MCP 工具和 BPA 流程自动化。

## 功能特点

- 用户认证与权限管理
- 角色与权限分配
- 系统参数动态配置
- 深色/浅色主题切换
- 动态菜单加载
- AI Agent 功能 (开发中)
  - AI 聊天 (SSE/WebSocket)
  - 自然语言数据查询
  - 知识库管理 (RAG)
  - MCP 工具集成
  - BPA 流程自动化

## 技术栈

| 层级 | 技术 |
|------|------|
| 桌面壳 | Tauri 2.x (Rust) |
| 前端 | React 18 + TypeScript + Vite |
| UI | Ant Design 6.x |
| 后端 | Rust Axum |
| AI 服务 | Python FastAPI |
| 数据库 | ArangoDB |
| LLM | Ollama / LM Studio |

## 项目结构

```
aibox/
├── api/                        # Rust Axum API Gateway
│   ├── src/
│   │   ├── main.rs            # 入口
│   │   ├── lib.rs             # 库导出
│   │   ├── error.rs           # 错误类型
│   │   ├── config.rs          # 配置模组
│   │   ├── auth/              # JWT 认证
│   │   ├── middleware/        # 中间件
│   │   │   ├── auth.rs        # JWT 验证
│   │   │   ├── logging.rs     # 请求日志
│   │   │   └── rate_limit.rs  # 速率限制
│   │   ├── api/               # API 路由
│   │   │   ├── mod.rs
│   │   │   ├── sse.rs        # SSE 接口
│   │   │   ├── ws.rs         # WebSocket 接口
│   │   │   ├── ai.rs         # AI 路由
│   │   │   ├── billing.rs    # 计费接口
│   │   │   ├── services.rs   # 服务管理
│   │   │   └── health.rs     # 健康检查
│   │   ├── services/          # 业务服务
│   │   ├── models/           # 数据模型
│   │   └── db/               # 数据库
│   ├── Cargo.toml
│   └── .env
├── ai-services/               # Python AI Services
│   ├── aitask/               # AI Task 服務 (port 8001)
│   ├── data_agent/           # Data Agent 服務 (port 8003) — 意圖 RAG + NL→SQL
│   ├── mcp_tools/            # MCP Tools 服務 (port 8004)
│   ├── bpa/mm_agent/         # BPA 物料管理 Agent (port 8005)
│   ├── knowledge_agent/      # Knowledge Agent 服務 (port 8007)
│   ├── datalake/             # 資料湖種子資料與 Schema 工具
│   └── requirements.txt
├── src/                       # React 前端源码
├── src-tauri/                 # Tauri 桌面应用壳
├── .docs/                     # 规格书
│   └── Spec/
│       └── AIBox AI Agent 系统规格书.md
├── start.sh                  # 服务管理脚本
├── install.sh                # 一键安装脚本
└── README.md
```

## 快速开始

### 开发环境

#### 1. 启动 ArangoDB

```bash
docker run -d \
  --name arangodb \
  -p 8529:8529 \
  -e ARANGO_ROOT_PASSWORD=abc_desktop_2026 \
  arangodb:latest
```

#### 2. 配置 API 服务器

创建 `api/.env` 文件：

```env
DATABASE_URL=http://localhost:8529
DATABASE_NAME=abc_desktop
DATABASE_USER=root
DATABASE_PASSWORD=abc_desktop_2026
JWT_SECRET=your-secret-key-here
```

#### 3. 启动服务

```bash
# 方式一：使用 start.sh 管理脚本（推荐）
./start.sh start    # 启动 API 服务器
./start.sh stop     # 停止 API 服务器
./start.sh restart  # 重启 API 服务器
./start.sh status   # 查看运行状态

# 方式二：手动启动 Rust API Gateway
cd api && cargo run --release

# 方式三：开发模式 (带热重载)
cd api && cargo watch -x run
```

```bash
# 启动 Python AI Services (分开终端)
cd ai-services && source .venv/bin/activate
uvicorn aitask.main:app --port 8001 --reload
uvicorn data_agent.main:app --port 8003 --reload
uvicorn mcp_tools.main:app --port 8004 --reload
uvicorn bpa.mm_agent.main:app --port 8005 --reload
uvicorn knowledge_agent.main:app --port 8007 --reload
```

```bash
# 终端 2: 启动前端开发服务器
npm run dev
```

#### 4. 访问应用

- 前端: http://localhost:1420
- API: http://localhost:6500

### 生产构建

```bash
# 构建前端
npm run build

# 构建 Tauri 应用 (macOS)
npm run tauri build

# 构建 DMG 安装包
# 输出: src-tauri/target/release/bundle/dmg/*.dmg
```

### 一键安装 (macOS)

```bash
curl -sL https://raw.githubusercontent.com/your-repo/main/install.sh | bash
```

## 服务管理

使用 `start.sh` 管理 API 服务：

```bash
./start.sh start    # 启动服务
./start.sh stop     # 停止服务
./start.sh restart  # 重启服务
./start.sh status   # 查看状态
```

## API 端点

### 认证
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | /api/v1/auth/login | 登录 |
| POST | /api/v1/auth/logout | 登出 |
| GET | /api/v1/auth/me | 当前用户 |

### 用户管理
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /api/v1/users | 用户列表 |
| POST | /api/v1/users | 创建用户 |
| GET | /api/v1/users/{key} | 获取用户 |
| POST | /api/v1/users/{key} | 更新用户 |
| DELETE | /api/v1/users/{key} | 删除用户 |

### 角色管理
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /api/v1/roles | 角色列表 |
| POST | /api/v1/roles | 创建角色 |

### AI (需要认证)
| 方法 | 端点 | 说明 |
|------|------|------|
| POST | /api/v1/ai/chat | AI 对话 |
| GET | /api/v1/ai/chat/stream | SSE 流式对话 |
| POST | /api/v1/ai/query | 数据查询 |

### SSE / WebSocket
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /api/v1/sse/chat/:context_id | SSE 聊天流 |
| GET | /api/v1/sse/events | SSE 事件流 |
| GET | /api/v1/sse/notifications | SSE 通知 |
| WS | /api/v1/ws/chat | WebSocket 聊天 |
| WS | /api/v1/ws/monitor | WebSocket 监控 |

### 计费 (需要认证)
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /api/v1/billing/usage | 使用量查询 |
| GET | /api/v1/billing/quota | 配额查询 |
| GET | /api/v1/billing/api-keys | API Key 列表 |
| POST | /api/v1/billing/api-keys | 创建 API Key |

### 服务管理
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /api/v1/services | 服务列表 |
| GET | /api/v1/services/{name} | 服务状态 |
| POST | /api/v1/services/{name}/start | 启动服务 |
| POST | /api/v1/services/{name}/stop | 停止服务 |

### 健康检查
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /health | 健康检查 |

## 配置说明

### 端口配置

| 服务 | 端口 | Dashboard | 说明 |
|------|------|-----------|------|
| API Gateway | 6500 | — | Rust Axum |
| AITask | 8001 | — | Python FastAPI |
| Data Agent | 8003 | — | Python FastAPI (意圖 RAG + NL→SQL) |
| MCP Tools | 8004 | — | Python FastAPI |
| BPA MM Agent | 8005 | — | Python FastAPI (物料管理) |
| Knowledge Agent | 8007 | — | Python FastAPI (知識庫 RAG) |
| Frontend (dev) | 1420 | — | Vite dev server |
| Frontend (preview) | 6000 | — | Vite preview |
| ArangoDB | 8529 | :8529 | 資料庫 |
| Qdrant | 6333 | :6333/dashboard | 向量檢索 |
| SeaweedFS Filer | 8888 | :8888 | 統一檔案備份儲存 |
| SeaweedFS Master | 9333 | :9333 | SeaweedFS 叢集協調 |
| Ollama | 11434 | — | LLM |
| LM Studio | 1234 | — | LLM |

### 生产环境

| 服务 | 地址 |
|------|------|
| API | https://abcapi.k84.org |
| 前端 | 內嵌於 Tauri 桌面應用 (dist/) |
| 產品頁 | https://abc.k84.org |

### 环境变量 (api/.env)

```env
# ===================
# Database
# ===================
DATABASE_URL=http://localhost:8529
DATABASE_NAME=aibox
DATABASE_USER=root
DATABASE_PASSWORD=abc_desktop_2026

# ===================
# JWT
# ===================
JWT_SECRET=your-256-bit-secret-key
JWT_EXPIRATION_HOURS=24

# ===================
# AI Services
# ===================
AITASK_URL=http://localhost:8001
DATA_AGENT_URL=http://localhost:8003
MCP_TOOLS_URL=http://localhost:8004
BPA_MM_AGENT_URL=http://localhost:8005
KNOWLEDGE_AGENT_URL=http://localhost:8007

# ===================
# External AI
# ===================
OLLAMA_BASE_URL=http://localhost:11434
LM_STUDIO_URL=http://localhost:1234

# ===================
# Rate Limiting
# ===================
RATE_LIMIT_MAX_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# ===================
# Billing
# ===================
BILLING_FREE_TOKENS_PER_MONTH=10000
BILLING_PRICE_PER_1K_TOKENS=0.001

# ===================
# Server
# ===================
PORT=6500
HOST=127.0.0.1
```

## 默认账户

- 用户名: `admin`
- 密码: `admin123`

首次登录后建议修改密码。

## 功能模块

### 系统维护
- 系统参数配置
- 日志管理
- 数据备份与恢复

### 账户管理
- 用户 CRUD
- 密码重置
- 状态管理

### 角色管理
- 角色 CRUD
- 权限分配

### AI Agent
- **AI 聊天**: SSE 流式响应 / WebSocket 实时对话
- **数据查询**: 自然语言转 SQL 查询
- **知识库**: RAG 向量检索
- **MCP 工具**: 外部工具集成
- **BPA**: 业务流程自动化

## 界面预览

### 欢迎页
- Logo 动画效果
- 自动跳转 (3秒)
- 版本信息显示

### 登录页
- 支持记住密码
- 错误提示
- 主题适配

### 主界面
- 侧边栏菜单 (可折叠)
- 动态主题切换
- 响应式布局

## 常见问题

### 端口冲突

如果端口 6500 被占用:
```bash
# macOS 查看占用
lsof -i :6500
```

### 构建失败

确保已安装:
- Node.js 18+
- Rust 1.70+
- Python 3.10+ (for AI services)
- Xcode (macOS)
- Xcode Command Line Tools

### 数据库连接失败

检查:
1. ArangoDB 是否运行: `docker ps`
2. 凭据是否正确
3. 数据库是否存在

### AI 服务启动

```bash
# 启动 AI 服务 (需要先启动 Rust API Gateway)
cd ai-services && source .venv/bin/activate
uvicorn aitask.main:app --port 8001
uvicorn data_agent.main:app --port 8003
uvicorn mcp_tools.main:app --port 8004
uvicorn bpa.mm_agent.main:app --port 8005
uvicorn knowledge_agent.main:app --port 8007
```

### 运行测试

```bash
# Rust API 测试
cd api && cargo test

# 前端测试
npm run test
```

## 文档

- [规格书](./.docs/SPEC.md)
- [AI Agent 系统规格书](./.docs/Spec/AIBox AI Agent 系统规格书.md)
- [Tauri 文档](https://tauri.app/)
- [Ant Design](https://ant.design/)
- [Axum 文档](https://docs.rs/axum/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)

## License

© 2026 ABC Desktop. All rights reserved.

---

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-03-25 | 1.3.0 | Daniel Chung | 新增 JobMonitor（Cloud icon + Tab）、任務中止、job_logs 失敗追蹤；新增 SeaweedFS 備份、Celery 非同步 pipeline、kb_pipeline Python 套件；新增知識庫向量化與圖譜抽取端點 |
| 2026-03-23 | 1.2.0 | Daniel Chung | 重構 AI Services 架構：data_agent(8003), knowledge_agent(8007), bpa/mm_agent(8005), datalake |
| 2026-03-18 | 1.1.0 | Daniel Chung | 新增 AI Agent 系統架構、Python AI Services、單元測試 |
| 2026-03-17 | 1.0.0 | Daniel Chung | 初始版本，完整專案文檔 |
