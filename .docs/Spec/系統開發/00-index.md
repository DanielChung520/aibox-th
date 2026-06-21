---
lastUpdate: 2026-06-14 16:30:00
author: Daniel Chung
version: 2.0.0
---

# 系統開發區 — 規格索引

## 概述
系統開發區涵蓋從使用者提交 AI Agent 需求、AI 審查、開發者接單、到規格書產出的完整流程。需求支援**版本迭代**（變更需求建立新版），並具備**開發中阻擋撤銷**的安全機制。

## 文件清單

| 文件 | 說明 |
|------|------|
| [01-需求提交與審查](./01-需求提交與審查.md) | AgentFormModal → DemandTab → AI 審查 → 提交流程 → 版本變更 → 撤銷 |
| [02-需求看板](./02-需求看板.md) | RequirementBoard：列表、接單、分析、狀態流轉、版次顯示 |
| [03-規格產出](./03-規格產出.md) | AI 規格書生成、重新產生、Mermaid、工時明細 |
| [04-排程推播系統](./04-排程推播系統.md) | Scheduled Push Engine：以 Push 逐筆遍歷取代 Broadcast，含排程、個人化、送達追蹤 |
| [05-客戶 Timeline 活動整理](./05-客戶timeline-活動整理.md) | Ragic 6 張表的輪巡與 Timeline 摘要腳本：客戶比對、event_type、摘要模板 |

## 核心概念

### 兩層狀態機（Two-Level State Machine）

需求生命週期分為兩個層級：

**Level 1 — Demand 狀態機（需求文件生命週期）**

```
draft → submitted → qualified → online
                        ↓
                    cancelled / superseded
```

| 狀態 | 意義 | 看板顯示？ |
|------|------|-----------|
| `draft` | 草稿編輯中 | ❌ |
| `submitted` | 提交等待 AI 審查判定 | ❌ |
| `qualified` | **需求成立**，可開發 | ✅ 顯示為待接單 |
| `online` | 已上線 | ✅ |
| `cancelled` | 已撤銷（開發前） | ❌ |
| `superseded` | 被新版取代 | ❌ |

**Level 2 — Kanban 狀態機（開發執行追蹤）**

```
pending_accept → accepted → analyzing → spec_ready → in_development → completed
                    ↓                          ↑
              analyze_failed ─── retry ────┘
```

Level 2 的啟動時機：當 Level 1 達到 `qualified` 時，自動建立 Level 2 看板記錄。

### 版本管理

- 需求可變更（change），每次變更建立新版（v1.0 → v2.0 → v3.0...）
- 新版透過 `supersedes` 欄位記錄來源
- 舊版在新版 `qualified` 時自動標為 `superseded`
- 看板只顯示當前活躍（非 superseded）版本

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
| `agent_demands` | 原始需求（含版本管理、變更溯源） |
| `agent_requirements` | 需求看板紀錄（接單、分析、規格產出） |
| `demand_logs` | 需求狀態變更 Audit Trail（每次轉移紀錄） |
| `system_params` | 開發相關配置（dev.* 分類） |

### agent_demands 新增欄位（v2.0）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `version` | string | 語意版本號（v1.0, v2.0…） |
| `supersedes` | string? | 從哪個 demand 版本變更來的 |
| `superseded_by` | string? | 被哪個 demand 版本取代 |
| `change_reason` | string? | 變更原因 |
| `change_history` | ChangeEntry[] | 完整變更軌跡 |

## API 端點

| 方法 | 路徑 | 說明 | 狀態變更 |
|------|------|------|---------|
| GET | `/api/v1/agent-requirements` | 需求列表 | — |
| POST | `/api/v1/agent-requirements` | 建立需求紀錄 | — |
| GET | `/api/v1/agent-requirements/{key}` | 需求詳情 | — |
| PATCH | `/api/v1/agent-requirements/{key}/accept` | 接單 | Level 2 |
| POST | `/api/v1/agent-requirements/{key}/analyze` | 啟動分析/重新產生規格 | Level 2 |
| POST | `/api/v1/demands/review` | AI 審查需求 | — |
| POST | `/api/v1/demands/{key}/submit` | 提交需求（含 AI 審查） | draft → submitted |
| POST | `/api/v1/demands/{key}/qualify` | 系統判定合格 | submitted → qualified ⚡自動建立看板 |
| POST | `/api/v1/demands/{key}/withdraw` | 撤銷需求（含開發檢查） | submitted/qualified → cancelled |
| POST | `/api/v1/demands/{key}/change` | 變更需求（建立新版） | 建立 v2.0 draft，舊版不變 |
| POST | `/api/v1/demands/{key}/reactivate` | 重新開啟 | cancelled → draft |
| GET | `/api/v1/demands/{key}/history` | 取得版本變更歷史 | — |

## 修改歷程
| 日期 | 版本 | 作者 | 變更 |
|------|------|------|------|
| 2026-06-14 | 2.0.0 | Daniel Chung | 重新設計狀態機：兩層分離（Demand + Kanban）、版本管理（變更/撤銷/取代）、Audit Trail、supersedes 連結 |
| 2026-04-27 | 1.0.0 | AI Agent | 初始版本 |
