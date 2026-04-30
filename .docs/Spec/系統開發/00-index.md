---
lastUpdate: 2026-04-27 16:00:00
author: AI Agent
version: 1.0.0
---

# 系統開發區 — 規格索引

## 概述
系統開發區涵蓋從使用者提交 AI Agent 需求、AI 審查、開發者接單、到規格書產出的完整流程。

## 文件清單

| 文件 | 說明 |
|------|------|
| [01-需求提交與審查](./01-需求提交與審查.md) | AgentFormModal → DemandTab → AI 審查 → 提交流程 |
| [02-需求看板](./02-需求看板.md) | RequirementBoard：列表、接單、分析、狀態流轉 |
| [03-規格產出](./03-規格產出.md) | AI 規格書生成、重新產生、Mermaid、工時明細 |

## 系統參數

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `dev.requirement_spec_model` | `qwen3-coder:30b` | 規格產出使用模型 |
| `dev.spec_context` | （系統規格索引） | AI 生成規格書的參考文件索引 |

## 角色

| 角色 | 權限 |
|------|------|
| `developer` | 需求看板（接單、分析、規格書） |
| `admin` | 全部功能 |

## 資料集合

| 集合 | 用途 |
|------|------|
| `agent_demands` | 原始需求（AI 審查、輸入/輸出規格） |
| `agent_requirements` | 需求看板紀錄（接單、分析、規格產出） |
| `system_params` | 開發相關配置（dev.* 分類） |

## API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/v1/agent-requirements` | 需求列表 |
| POST | `/api/v1/agent-requirements` | 建立需求紀錄 |
| GET | `/api/v1/agent-requirements/{key}` | 需求詳情 |
| PATCH | `/api/v1/agent-requirements/{key}/accept` | 接單 |
| POST | `/api/v1/agent-requirements/{key}/analyze` | 啟動分析/重新產生規格 |
| POST | `/api/v1/demands/review` | AI 審查需求 |
| POST | `/api/v1/demands/estimate-hours` | 工時估算 |

## 修改歷程
| 日期 | 版本 | 作者 | 變更 |
|------|------|------|------|
| 2026-04-27 | 1.0.0 | AI Agent | 初始版本 |
