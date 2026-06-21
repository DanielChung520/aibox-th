---
lastUpdate: 2026-06-18
author: Sisyphus
version: 1.0.0
---

# 互動 Timeline 規格

## 1. 概述

客戶互動 Timeline 彙整 ERP 交易記錄、LINE 對話、業務拜訪等事件，提供統一的時間軸查詢介面。支援摘要級（場景一客戶端）與完整級（場景二內部）兩種檢視權限。

## 2. 資料來源

| 來源 | 事件類型 | 更新時機 |
|------|---------|---------|
| Ragic ERP（6 張表） | quote_analysis, order_placed, shipment_delivered, return_processed, credit_note_issued, inquiry_sent | 定時輪巡（每 15 分） |
| LINE Bot（場景一） | greeting_sent, faq_answered, business_card_received, confidential_blocked | 即時寫入 |
| 內部助理（場景二） | greeting_customer, broadcast_sent, visit_completed | 即時寫入 |
| CRM | contact_created, contact_updated | 即時寫入 |

## 3. 資料模型

### Collection: customer_timelines

```json
{
  "_key": "uuid",
  "customer_id": "crm_contact_key",
  "customer_name": "陳先生",
  "events": [
    {
      "event_id": "uuid",
      "event_type": "quote_analysis | order_placed | shipment_delivered | return_processed | credit_note_issued | inquiry_sent | greeting_sent | faq_answered | visit_completed | broadcast_sent | business_card_received | confidential_blocked | image_shared",
      "summary": "2026/06/10 報價#Q-2026-0089 輪椅輔具一批",
      "timestamp": "2026-06-10T14:30:00Z",
      "source": "erp | line_bot | internal_assistant | crm",
      "detail_level": "summary | full",
      "ref_key": "單據號碼 or LINE_msg_key",
      "metadata": {}
    }
  ],
  "last_updated": "2026-06-14T10:00:00Z"
}
```

## 4. API 端點

### GET /api/v1/customer/{customer_id}/timeline

```
level?   string  — summary | full（預設 full）
from?    string  — ISO datetime 起始
to?      string  — ISO datetime 結束
limit?   number  — 預設 50
```

### POST /api/v1/customer/{customer_id}/timeline/event

寫入新事件（由各功能呼叫）。

## 5. Skill 實作

| Skill | 路徑 | 說明 |
|-------|------|------|
| TimelineWriteSkill | ai-services/skills/timeline_engine/skill.py | 寫入事件（含 ref_key 去重） |
| TimelineQuerySkill | ai-services/skills/timeline_engine/skill.py | 查詢（支援 level 過濾） |
| RagicPollSkill | ai-services/skills/ragic_timeline_poller/skill.py | 輪巡 Ragic 6 張表，比對客戶後寫入 |

## 6. 前端實作

| 檔案 | 說明 |
|------|------|
| src/pages/eea-crm/TimelinePage.tsx | Timeline 頁面（目前 mock data） |
| src/pages/eea-crm/LineAssistantPage.tsx | LINE 助手內嵌 Timeline tab（mock） |

## 7. 實作狀態

| 項目 | 狀態 |
|------|:----:|
| customer_timelines collection | ✅ 實作 |
| Timeline Engine skill（讀寫） | ✅ 實作 |
| Ragic 6 表輪巡 poller | ✅ 實作 |
| level 過濾（summary/full） | ✅ 實作 |
| Timeline 前端頁面 | ⏳ mock |
| LINE 助手 Timeline tab | ⏳ mock |
