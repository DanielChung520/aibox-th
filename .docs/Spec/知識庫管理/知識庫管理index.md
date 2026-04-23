---
lastUpdate: 2026-04-18 02:00:00
author: Daniel Chung
version: 1.0.0
---

# 知識庫管理 規格索引

本目錄為 AIBox 知識庫管理系統的規格文件集中地。

---

## 核心規格文件

### 知識管理系統 v6（最新）

| 文件 | 版本 | 說明 |
|------|------|------|
| `知識管理優化規格書-v6.md` | 6.0.0 | 知識管理中心全面升級：從文件處理管線 → 知識邊界治理與有界證據組裝系統 |

**閱讀順序建議：** 先讀本 index → 再讀 v6 規格書 → 再依賴深入各子系統規格

### HybridRAG v2（最新）

| 文件 | 版本 | 說明 |
|------|------|------|
| `HybridRag/HybridRAG-v2-實作計劃書.md` | 1.0.0 | HybridRAG v1 → v2 升級實作追蹤（Phase 1-4 進度） |
| `HybridRag/HybridRAG-細部規格書-v2.md` | 2.0.0 | HybridRAG v2 詳細技術規格：邊界檢查、查詢分解、矛盾保留、缺口檢測 |

**閱讀順序：** v6 規格書（宏觀） → HybridRAG-細部規格書-v2.md（微觀） → HybridRAG-v2-實作計劃書.md（實作追蹤）

---

## 實作進度摘要

### Phase 1 — LLM Whitelist + role_scope ✅
- **內容：** LLM Provider 白名單、邊界 role_scope 機制
- **實作：** `hybrid_rag/boundary_checker.py`、`service.py`

### Phase 2 — KnowledgeManagementService 整合 ✅
- **內容：** KMS 統一封裝、所有 pipeline 端點 + hybrid 端點加入權限檢查
- **實作：** `knowledge_agent/service.py`、`pipeline.py`、`hybrid.py`

### Phase 3 — Allowed Roles Schema Migration ✅
- **內容：** `role_scope` → `allowed_roles` 欄位遷移（ArangoDB + Python + Rust）
- **實作：** 6 個 knowledge_roots 全部遷移完畢

### Phase 4 — Rust API Gateway JWT Role Injection ✅
- **內容：** Rust API Gateway 所有 proxy 呼叫注入 `X-User-Role` header
- **實作：** `api/src/api/knowledge.rs`、`pipeline.py` 14 個端點支援 header fallback

---

## 技術架構總覽

```
┌─────────────────────────────────────────────────────────────┐
│                    Rust API Gateway                         │
│  (api/src/api/knowledge.rs)                                │
│  - JWT 驗證 + Role 注入                                      │
│  - X-User-Role header → Python KMS                         │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP (with X-User-Role)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               Python Knowledge Agent (port 8007)             │
│                                                             │
│  ┌─────────────────┐    ┌────────────────────────────────┐ │
│  │ KnowledgeMgmt  │    │   HybridRAG v2                  │ │
│  │ Service         │    │   Boundary Checker              │ │
│  │ (kms.check_     │    │   (allowed_roles, llm_whitelist)│ │
│  │  access)        │    │   Inquiry Decomposition         │ │
│  └────────┬────────┘    └────────────────────────────────┘ │
│           │                                                  │
│  ┌────────▼────────┐    ┌────────────────────────────────┐ │
│  │ Pipeline Router  │    │   Hybrid Router                │ │
│  │ /pipeline/*     │    │   /search, /evidence           │ │
│  └─────────────────┘    └────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     ┌─────────┐  ┌─────────┐  ┌─────────┐
     │ ArangoDB│  │ Qdrant  │  │ SeaweedFS│
     │(meta)   │  │(vector) │  │(file)   │
     └─────────┘  └─────────┘  └─────────┘
```

---

## 安全性模型

| 層面 | 機制 | 位置 |
|------|------|------|
| LLM 白名單 | `knowledge.allowed_llm_providers` system param | `service.py` |
| Role 門控 | `allowed_roles` list（空 = 無限制） | `service.py` + `boundary_checker.py` |
| JWT Role 注入 | Rust `extract_user_role()` → `X-User-Role` header | `knowledge.rs` |
| KMS 統一檢查 | `KnowledgeManagementService.check_access()` | `service.py` |

---

## 歸檔文件（`.archived/知識庫管理/`）

以下為已被取代的歷史版本：

| 原檔案 | 取代版本 |
|--------|----------|
| `上傳的功能架構說明-v4.0.md` | `知識管理優化規格書-v6.md` |
| `上傳的功能架構說明-v5.0.md` | `知識管理優化規格書-v6.md` |
| `知識管理優化規格書-v6-導引版.md` | `知識管理優化規格書-v6.md` |
| `HybridRag/HybridRAG-系統規格書.md` | `HybridRag/HybridRAG-細部規格書-v2.md` |
| `HybridRag/HybridRAG-完整配置與使用指南.md` | `HybridRag/HybridRAG-v2-實作計劃書.md` |
| `HybridRag/HybridRAG查詢處理示例.md` | `HybridRag/HybridRAG-v2-實作計劃書.md` |
| `HybridRag/HybridRAG查詢测试说明.md` | `HybridRag/HybridRAG-v2-實作計劃書.md` |
| `HybridRag/HybridRAG問題定位與解決方案.md` | `HybridRag/HybridRAG-v2-實作計劃書.md` |
| `HybridRag/HybridRAG权重配置*.md` | `HybridRag/HybridRAG-v2-實作計劃書.md` |

---

## 外部參考

- [API Specification](../API%20Specification.md) — API 端點與錯誤碼定義
- `ai-services/knowledge_agent/service.py` — KMS 實作
- `ai-services/knowledge_agent/routers/pipeline.py` — Pipeline 端點
- `ai-services/knowledge_agent/routers/hybrid.py` — HybridRAG 端點
- `api/src/api/knowledge.rs` — Rust API Gateway 知識代理

---

## 修改歷程

| 日期 | 版本 | 更新者 | 變更內容 |
|------|------|--------|----------|
| 2026-04-18 | 1.0.0 | Daniel Chung | 初始版本：建立規格索引，整合 Phase 1-4 實作進度 |
