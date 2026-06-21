#!/usr/bin/env python3
"""
@file        seed_welfare_secretary_intents.py
@description 業務平台助手 — 18 個宣告意圖（Declared Intents）初始化
@lastUpdate  2026-06-20
@author      Sisyphus
@version     1.0.0
"""

import httpx
import json
import uuid
from datetime import datetime, timezone

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = ("root", "abc_desktop_2026")
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
AGENT_KEY = "welfare_secretary"
AGENT_UUID = None  # 從 agents 集合查詢實際 _key

# ── 場景一：客戶端 LINE Bot（7 個意圖） ──

CUSTOMER_INTENTS = [
    {
        "name": "greeting",
        "description": "客戶發送日常問候（早安、晚安、你好等）",
        "keywords": ["早安", "午安", "晚安", "你好", "嗨", "哈囉", "您好", "hello", "hi"],
        "nl_patterns": ["早安", "晚上好", "哈囉", "您好", "你好"],
        "scope": "customer",
        "scene": "customer",
        "routing": {"target_type": "skill", "target": "greeting_engine", "parallel": False},
        "confidence": {"auto_route": 0.9, "verify": 0.6},
        "auth": {"trust_level": "T3"},
        "priority": 90,
        "status": "enabled",
    },
    {
        "name": "greeting_image",
        "description": "客戶傳送問候圖片（節日賀卡、早安圖）",
        "keywords": [],
        "nl_patterns": [],
        "scope": "customer",
        "scene": "customer",
        "routing": {"target_type": "skill", "target": "image_processor", "parallel": False},
        "confidence": {"auto_route": 0.85, "verify": 0.5},
        "auth": {"trust_level": "T3"},
        "priority": 85,
        "status": "enabled",
    },
    {
        "name": "faq_question",
        "description": "客戶詢問產品/服務的常見問題",
        "keywords": ["產品", "服務", "規格", "型號", "多少錢", "保固", "怎麼使用", "申請"],
        "nl_patterns": ["你們的輪椅有哪些型號", "保固多久", "如何申請補助", "產品規格"],
        "scope": "customer",
        "scene": "customer",
        "routing": {"target_type": "skill", "target": "knowledge_agent", "parallel": False},
        "confidence": {"auto_route": 0.8, "verify": 0.5},
        "auth": {"trust_level": "T3"},
        "priority": 80,
        "status": "enabled",
    },
    {
        "name": "timeline_query",
        "description": "客戶查詢自己的互動記錄摘要",
        "keywords": ["訂單", "進度", "查詢", "記錄", "狀態", "互動", "歷程"],
        "nl_patterns": ["我的訂單到哪了", "查詢我的記錄", "我的互動紀錄"],
        "scope": "customer",
        "scene": "customer",
        "routing": {"target_type": "skill", "target": "timeline_engine", "parallel": False},
        "confidence": {"auto_route": 0.8, "verify": 0.5},
        "auth": {"trust_level": "T2"},
        "priority": 80,
        "status": "enabled",
    },
    {
        "name": "confidential_q",
        "description": "客戶詢問機密資訊（報價、金額、合約等）",
        "keywords": ["報價", "金額", "成本", "合約", "價格", "費用", "底價", "利潤", "折扣"],
        "nl_patterns": ["這個多少錢", "一台多少", "報價多少", "價格是多少"],
        "scope": "customer",
        "scene": "customer",
        "routing": {"target_type": "skill", "target": "customer_safe_reply", "parallel": False},
        "confidence": {"auto_route": 0.95, "verify": 0.8},
        "auth": {"trust_level": "T4"},
        "priority": 95,
        "status": "enabled",
    },
    {
        "name": "business_card",
        "description": "客戶傳送名片圖片進行 OCR",
        "keywords": [],
        "nl_patterns": [],
        "scope": "customer",
        "scene": "customer",
        "routing": {"target_type": "skill", "target": "image_processor", "parallel": False},
        "confidence": {"auto_route": 0.9, "verify": 0.6},
        "auth": {"trust_level": "T2"},
        "priority": 90,
        "status": "enabled",
    },
    {
        "name": "unclear",
        "description": "無法明確分類的客戶訊息，以安全回覆模式處理",
        "keywords": [],
        "nl_patterns": [],
        "scope": "customer",
        "scene": "customer",
        "routing": {"target_type": "skill", "target": "customer_safe_reply", "parallel": False},
        "confidence": {"auto_route": 0.0, "verify": 0.0},
        "auth": {"trust_level": "T3"},
        "priority": 0,
        "status": "enabled",
    },
]

# ── 場景二：內部工作助理（11 個意圖） ──

INTERNAL_INTENTS = [
    {
        "name": "erp_query",
        "description": "業務人員查詢 ERP 報價單/訂單/庫存資料",
        "keywords": ["ERP", "報價單", "訂單", "銷貨", "庫存", "詢價", "出貨"],
        "nl_patterns": ["查詢客戶陳先生的報價單", "上個月的訂單有哪些", "庫存查詢"],
        "scope": "internal",
        "scene": "internal",
        "routing": {"target_type": "subagent", "target": "data_agent", "parallel": False},
        "confidence": {"auto_route": 0.85, "verify": 0.6},
        "auth": {"trust_level": "T3"},
        "priority": 85,
        "status": "enabled",
    },
    {
        "name": "crm_query",
        "description": "業務人員查詢客戶聯絡人資訊",
        "keywords": ["客戶", "聯絡人", "電話", "地址", "公司", "CRM", "客戶資料"],
        "nl_patterns": ["查詢陳先生的聯絡方式", "找王小姐的地址", "客戶資料"],
        "scope": "internal",
        "scene": "internal",
        "routing": {"target_type": "skill", "target": "crm_query", "parallel": False},
        "confidence": {"auto_route": 0.85, "verify": 0.6},
        "auth": {"trust_level": "T3"},
        "priority": 85,
        "status": "enabled",
    },
    {
        "name": "greeting_customer",
        "description": "業務人員代理發送問候給客戶",
        "keywords": ["代發", "問候", "節日", "祝福", "賀詞", "早安"],
        "nl_patterns": ["幫我發早安問候給所有客戶", "發送節日祝福", "代發問候"],
        "scope": "internal",
        "scene": "internal",
        "routing": {"target_type": "skill", "target": "greeting_engine", "parallel": False},
        "confidence": {"auto_route": 0.85, "verify": 0.6},
        "auth": {"trust_level": "T3"},
        "priority": 85,
        "status": "enabled",
    },
    {
        "name": "broadcast",
        "description": "業務人員群發公告/促銷訊息給客戶",
        "keywords": ["群發", "公告", "宣傳", "推播", "促銷", "發送給"],
        "nl_patterns": ["群發下週促銷活動給 VIP 客戶", "發送公告", "群發訊息"],
        "scope": "internal",
        "scene": "internal",
        "routing": {"target_type": "skill", "target": "push_engine", "parallel": False},
        "confidence": {"auto_route": 0.85, "verify": 0.6},
        "auth": {"trust_level": "T3"},
        "priority": 85,
        "status": "enabled",
    },
    {
        "name": "send_card_intro",
        "description": "業務人員將客戶名片/聯絡人分享給其他業務",
        "keywords": ["名片", "介紹", "分享聯絡人", "推薦", "轉發"],
        "nl_patterns": ["幫我把陳總的名片發給林業務", "分享張經理的聯絡方式", "轉發名片"],
        "scope": "internal",
        "scene": "internal",
        "routing": {"target_type": "skill", "target": "contact_share", "parallel": False},
        "confidence": {"auto_route": 0.8, "verify": 0.5},
        "auth": {"trust_level": "T2"},
        "priority": 80,
        "status": "enabled",
    },
    {
        "name": "card_to_contact",
        "description": "業務人員將名片 OCR 結果直接建檔到 CRM",
        "keywords": ["整理", "名片轉聯絡人", "建檔", "OCR", "掃描"],
        "nl_patterns": ["把這張名片建檔到 CRM", "掃描名片", "名片建檔"],
        "scope": "internal",
        "scene": "internal",
        "routing": {"target_type": "skill", "target": "image_processor", "parallel": False},
        "confidence": {"auto_route": 0.85, "verify": 0.6},
        "auth": {"trust_level": "T2"},
        "priority": 85,
        "status": "enabled",
    },
    {
        "name": "market_subscribe",
        "description": "業務人員訂閱市場產業快報",
        "keywords": ["市場快報", "訂閱", "產業新聞", "快訊", "市場"],
        "nl_patterns": ["訂閱輔具市場每週快報", "我要看市場新聞", "市場快報"],
        "scope": "internal",
        "scene": "internal",
        "routing": {"target_type": "handoff", "target": "market_intel", "parallel": False},
        "confidence": {"auto_route": 0.8, "verify": 0.5},
        "auth": {"trust_level": "T2"},
        "priority": 80,
        "status": "enabled",
    },
    {
        "name": "schedule_visit",
        "description": "業務人員安排客戶拜訪行程",
        "keywords": ["拜訪", "行程", "安排", "約時間", "拜會", "預約"],
        "nl_patterns": ["下週三下午拜訪台北陳先生", "安排明天去新竹", "預約拜訪"],
        "scope": "internal",
        "scene": "internal",
        "routing": {"target_type": "skill", "target": "visit_plan", "parallel": False},
        "confidence": {"auto_route": 0.85, "verify": 0.6},
        "auth": {"trust_level": "T2"},
        "priority": 85,
        "status": "enabled",
    },
    {
        "name": "timeline_full",
        "description": "業務人員查詢客戶完整互動記錄",
        "keywords": ["完整記錄", "互動歷史", "所有事件", "全部記錄"],
        "nl_patterns": ["顯示陳先生的所有互動記錄", "查詢完整歷程", "全部記錄"],
        "scope": "internal",
        "scene": "internal",
        "routing": {"target_type": "skill", "target": "timeline_engine", "parallel": False},
        "confidence": {"auto_route": 0.9, "verify": 0.6},
        "auth": {"trust_level": "T3"},
        "priority": 90,
        "status": "enabled",
    },
    {
        "name": "timeline_write",
        "description": "各功能自動寫入互動記錄到 Timeline（非使用者手動觸發）",
        "keywords": [],
        "nl_patterns": [],
        "scope": "internal",
        "scene": "internal",
        "routing": {"target_type": "skill", "target": "timeline_engine", "parallel": False},
        "confidence": {"auto_route": 0.0, "verify": 0.0},
        "auth": {"trust_level": "T3"},
        "priority": 0,
        "status": "enabled",
    },
    {
        "name": "ragic_sync",
        "description": "業務人員手動觸發 Ragic ERP 同步",
        "keywords": ["同步", "Ragic", "更新ERP", "手動同步"],
        "nl_patterns": ["手動同步陳先生的 ERP 資料", "更新 timeline", "Ragic 同步"],
        "scope": "internal",
        "scene": "internal",
        "routing": {"target_type": "skill", "target": "ragic_timeline_poller", "parallel": False},
        "confidence": {"auto_route": 0.85, "verify": 0.6},
        "auth": {"trust_level": "T3"},
        "priority": 85,
        "status": "enabled",
    },
]

ALL_INTENTS = CUSTOMER_INTENTS + INTERNAL_INTENTS


async def lookup_agent_uuid() -> str:
    """從 agents 集合查詢業務平台助手的實際 _key (UUID)"""
    async with httpx.AsyncClient(auth=AUTH, timeout=10.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{DB}/_api/cursor",
            json={
                "query": "FOR a IN agents FILTER a.name == @name LIMIT 1 RETURN a._key",
                "bindVars": {"name": "業務平台助手"},
            },
        )
        if resp.status_code in (200, 201):
            keys = resp.json().get("result", [])
            if keys:
                return str(keys[0])
    return ""


async def seed_intents():
    """批次寫入所有宣告意圖到 intent_catalog（upsert by name）"""
    global AGENT_UUID
    AGENT_UUID = await lookup_agent_uuid()
    if not AGENT_UUID:
        print("  ❌ 找不到業務平台助手的 Agent 文件，請先執行 seed_welfare_secretary.py")
        return 0, 0
    print(f"  Agent UUID: {AGENT_UUID}")

    async with httpx.AsyncClient(auth=AUTH, timeout=15.0) as client:
        # 查詢現有 welfare_secretary 的 intent（by name 做 upsert）
        resp = await client.post(
            f"{ARANGO_URL}/_db/{DB}/_api/cursor",
            json={
                "query": "FOR i IN intent_catalog FILTER i.agent_key == @key RETURN i",
                "bindVars": {"key": AGENT_KEY},
            },
        )
        existing = {}
        if resp.status_code in (200, 201):
            for doc in resp.json().get("result", []):
                existing[doc.get("name", "")] = doc.get("_key", "")

        created = 0
        updated = 0

        for intent in ALL_INTENTS:
            doc = {
                "_key": str(uuid.uuid4()),
                "agent_key": AGENT_UUID,         # agents 集合的實際 _key (UUID)，供前端 API 查詢
                "agent_key_name": AGENT_KEY,     # 硬編碼名稱 "welfare_secretary"，供 BPA router 查詢
                **intent,
                "created_at": NOW,
                "updated_at": NOW,
            }

            existing_key = existing.get(intent["name"])
            if existing_key:
                doc.pop("_key", None)
                doc.pop("created_at", None)
                resp = await client.patch(
                    f"{ARANGO_URL}/_db/{DB}/_api/document/intent_catalog/{existing_key}",
                    json=doc,
                )
                if resp.status_code in (200, 201, 202):
                    updated += 1
                    print(f"  🔄 Updated: {intent['name']}")
                else:
                    print(f"  ❌ Failed to update {intent['name']}: {resp.status_code}")
            else:
                resp = await client.post(
                    f"{ARANGO_URL}/_db/{DB}/_api/document/intent_catalog",
                    json=doc,
                )
                if resp.status_code in (200, 201, 202):
                    created += 1
                    print(f"  ✅ Created: {intent['name']} ({intent['scene']})")
                else:
                    print(f"  ❌ Failed to create {intent['name']}: {resp.status_code} {resp.text[:200]}")

    return created, updated


async def main():
    print("=== 業務平台助手 — 宣告意圖初始化 ===\n")

    print(f"Agent Key: {AGENT_KEY}")
    print(f"Total intents: {len(ALL_INTENTS)}")
    print(f"  Customer: {len(CUSTOMER_INTENTS)}")
    print(f"  Internal: {len(INTERNAL_INTENTS)}\n")

    print("寫入 intent_catalog...")
    c, u = await seed_intents()

    print(f"\n=== 完成: 新增 {c} / 更新 {u} / 總計 {len(ALL_INTENTS)} ===")
    print("請到前端 Agent 編輯頁面 → 宣告意圖 Tab 確認資料。")
    print("或執行同步到 Qdrant：POST /api/v1/agents/welfare_secretary/intents/sync")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
