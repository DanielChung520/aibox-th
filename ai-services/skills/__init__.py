"""
@file        skills/__init__.py
@description Skills 統一目錄 — 所有可複用技能集中管理
@lastUpdate  2026-06-14
@author      Daniel Chung
@version     1.0.0

# Skills 目錄結構

skills/
├── skills.json                 # 技能登記與發現
├── __init__.py                 # 此檔案
├── ragic_timeline_poller/      # Ragic 表輪巡 → Timeline 寫入
│   └── skill.py
├── customer_intent_recorder/   # 客戶意圖記錄：分析+記錄+轉告業務
│   └── skill.py
├── confidential_handler/       # 機密資訊查詢分流（業務本人→subagent，其他→記錄+通知）
│   └── skill.py
├── image_processor/            # 圖片分類 + 名片 OCR + 摘要
│   └── skill.py
├── timeline_engine/            # Timeline 讀寫（含 level 過濾）
│   └── skill.py
├── push_engine/                # 排程推播（LINE Push 逐筆發送）
│   └── skill.py
├── greeting_engine/            # CRM 尊稱查詢 + LLM 問候生成
│   └── skill.py
├── greeting_settings/          # 問候設定管理：接受業務自然語言指令
│   └── skill.py
├── customer_safe_reply/        # 客戶安全回覆（L0-L4 防 jailbreak）
│   └── skill.py
├── business_notification/      # L3/L4 機密攔截時通知業務
│   └── skill.py
├── crm_query/                  # CRM 客戶/聯絡人查詢
│   └── skill.py
├── visit_plan/                 # 行程安排與估程
│   └── skill.py
└── knowledge_agent/            # 知識庫 FAQ 檢索
    └── skill.py

## 呼叫方式

所有 skill 統一 interface：

    from skills.<name>.skill import execute
    result = execute(params)
"""
