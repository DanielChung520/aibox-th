---
lastUpdate: 2026-04-27 17:00:00
author: AI Agent
version: 1.0.0
---

# AI Agent / Tool 開發指引（@dev）

當使用者輸入 `@dev {需求編號}` 時，AI Coder 應按照本指引進行開發工作。

## 觸發條件

使用者訊息包含 `@dev` 關鍵字，後接需求編號（格式：`A01-2617-001`）。

## 執行步驟

### Step 1：提取需求編號

從使用者輸入中解析需求編號，格式為 `A{tab}-{YYWW}-{seq}` 或 `T{tab}-{YYWW}-{seq}`。

### Step 2：調用 API 取得需求與規格

```
GET http://localhost:3001/api/v1/agent-requirements/by-req-no/{req_no}
```

回應包含完整需求資訊：`agent_name`, `goal`, `expected_effect`, `problem_description`, `dev_spec`, `ai_review`。

### Step 3：複製規格書到工作區

將規格書內容寫入專案工作目錄：

```
.sisyphus/plans/{req_no}-spec.md
```

或若使用 OpenCode：
```
.opencode/plans/{req_no}-spec.md
```

### Step 4：解析並確認

AI Coder 必須先完成以下分析，再開始寫程式碼：

1. **需求理解**：用自己的話重述需求目標與預期效果
2. **技術棧確認**：確認建議的技術都在本系統範圍內
3. **模組拆解**：列出需要建立/修改的檔案
4. **依賴檢查**：確認是否有未滿足的前置條件
5. **向使用者確認**：以上分析完成後，請使用者確認是否開始開發

### Step 5：開始開發

使用者確認後，按照 AGENTS.md 的開發規範進行實作。

## API 參考

| 端點 | 用途 |
|------|------|
| `GET /api/v1/agent-requirements/by-req-no/{no}` | 依編號查詢需求 |
| `GET /api/v1/agent-requirements/{key}` | 依 key 查詢需求 |
| `GET /api/v1/agent-requirements/{key}/spec.md` | 下載規格書 Markdown |

## 開發規範參考

- 系統開發基準：`dev.spec_context` 系統參數（於 `/app/params` 查看）
- 完整開發規範：`AGENTS.md`
- 系統規格索引：`.docs/Spec/系統開發/00-index.md`

## 範例

使用者輸入：
```
@dev A01-2617-001 請開始開發 Ragic 小幫手
```

AI Coder 應：
1. 解析 `A01-2617-001`
2. 調用 `GET /api/v1/agent-requirements/by-req-no/A01-2617-001`
3. 取得規格書，寫入 `.opencode/plans/A01-2617-001-spec.md`
4. 分析規格書，列出開發計畫
5. 向使用者確認後開始開發

## 修改歷程
| 日期 | 版本 | 作者 | 變更 |
|------|------|------|------|
| 2026-04-27 | 1.0.0 | AI Agent | 初始版本 |
