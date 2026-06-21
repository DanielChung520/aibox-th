#!/usr/bin/env python3
"""
@file        seed_welfare_secretary.py
@description 業務平台助手 — Agent 紀錄與新集合初始化
@lastUpdate  2026-06-19
@author      Sisyphus
@version     1.0.0
"""

import httpx
import json
from datetime import datetime, timezone

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = ("root", "abc_desktop_2026")
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def ensure_collections():
    """確保 customer_timelines 和 pending_contacts 集合存在"""
    async with httpx.AsyncClient(auth=AUTH) as client:
        for col in ["customer_timelines", "pending_contacts", "broadcast_logs", "greeting_templates"]:
            resp = await client.post(
                f"{ARANGO_URL}/_db/{DB}/_api/collection",
                json={"name": col},
            )
            if resp.status_code in (200, 201):
                print(f"  ✅ Collection '{col}' created")
            elif resp.status_code == 409:
                print(f"  ℹ️  Collection '{col}' already exists")
            else:
                print(f"  ❌ Failed to create '{col}': {resp.status_code} {resp.text}")


async def seed_agent():
    """建立業務平台助手 Agent 紀錄"""
    agent = {
        "_key": "welfare_secretary",
        "agent_type": "bpa",
        "name": "業務平台助手",
        "description": "通訊平台客服助理：管理 LINE/WeCom/DingTalk 客戶互動，支援名片 OCR、日常問候、FAQ 回答、意圖記錄轉達等功能。",
        "icon": "RobotOutlined",
        "status": "online",
        "usage_count": 0,
        "group_key": "bpa",
        "source": "local",
        "endpoint_url": "http://localhost:8011/welfare-secretary/chat",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "qwen3:latest",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": (
            "你是一個專業親切的「業務平台助手」AI 助手，服務於台灣福祉股份有限公司。\n\n"
            "【角色定位】\n"
            "- 你是公司派駐的客服與業務助理，協助客戶與業務人員\n"
            "- 語氣溫暖禮貌，用繁體中文回覆\n\n"
            "【客戶端規則】\n"
            "- L0（公開資訊）：可直接回覆\n"
            "- L1（FAQ）：可回覆\n"
            "- L2（互動摘要）：僅摘要，不含明細\n"
            "- L3（機密明細：金額、成本、合約）：婉轉拒答\n"
            "- L4（內部操作：下單、改單）：婉轉拒答\n\n"
            "【內部助理規則】\n"
            "- 可查詢 ERP/CRM 完整資料\n"
            "- 對於群發等操作，先要求確認"
        ),
        "knowledge_bases": [],
        "data_sources": ["customer_timelines", "crm_contacts", "crm_customers"],
        "tools": [],
        "opening_lines": [
            "您好！我是業務平台助手，可以協助您查詢產品資訊、互動記錄，或轉達給業務人員。",
            "早安！有什麼我可以幫您的嗎？",
        ],
        "capabilities": [
            "客戶問候回應",
            "產品 FAQ 回答",
            "Timeline 互動記錄查詢",
            "名片 OCR 收藏",
            "ERP/CRM 查詢（內部）",
            "代理客戶問候（內部）",
            "群發訊息（內部）",
        ],
        "created_at": NOW,
        "updated_at": NOW,
    }

    async with httpx.AsyncClient(auth=AUTH) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{DB}/_api/document/agents",
            json=agent,
        )
        if resp.status_code in (200, 201, 202):
            print(f"  ✅ Agent 'welfare_secretary' created/updated")
        elif resp.status_code == 409:
            # 已存在，改用 PUT 更新
            resp = await client.put(
                f"{ARANGO_URL}/_db/{DB}/_api/document/agents/welfare_secretary",
                json=agent,
            )
            if resp.status_code in (200, 201, 202):
                print(f"  ✅ Agent 'welfare_secretary' updated")
            else:
                print(f"  ❌ Failed to update agent: {resp.status_code} {resp.text}")
        else:
            print(f"  ❌ Failed to create agent: {resp.status_code} {resp.text}")


async def main():
    print("=== 業務平台助手 DB 初始化 ===\n")
    
    print("1. 確保集合存在...")
    await ensure_collections()
    
    print("\n2. 建立 Agent 紀錄...")
    await seed_agent()
    
    print("\n=== 完成 ===")


async def seed_crm_assistant():
    """建立 CRM 助理 Agent 紀錄（Agent 卡片）"""
    agent = {
        "_key": "crm_assistant",
        "agent_type": "bpa",
        "name": "CRM 助理",
        "description": "業務 CRM 操作助手：查詢客戶資料、互動記錄、排程管理、知識庫 FAQ。協助業務人員在艾企助手中處理日常 CRM 作業。",
        "icon": "TeamOutlined",
        "status": "online",
        "usage_count": 0,
        "group_key": "sales",
        "source": "local",
        "endpoint_url": "",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "qwen3:latest",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": (
            "你是 CRM 助理，協助業務人員查詢客戶資料與互動記錄。\n\n"
            "【核心能力】\n"
            "1. 客戶資料查詢（crm_query skill）\n"
            "2. 互動記錄查詢（timeline_engine skill）\n"
            "3. 知識庫 FAQ 檢索（knowledge_agent skill）\n"
            "4. 行程安排與管理（visit_plan skill）\n"
            "5. 發送訊息排程管理（greeting_settings skill）\n\n"
            "請用專業有效率的語氣回覆，並以結構化方式呈現查詢結果。"
        ),
        "knowledge_bases": [],
        "data_sources": ["crm_contacts", "crm_customers", "customer_timelines"],
        "tools": [],
        "opening_lines": [
            "您好！我是 CRM 助理，可以幫您查詢客戶資料、互動記錄或管理行程。",
            "想查詢哪位客戶的資料？請提供客戶名稱或關鍵字。",
        ],
        "capabilities": [
            "客戶資料查詢",
            "互動記錄查詢",
            "知識庫 FAQ",
            "行程安排",
            "訊息排程管理",
        ],
        "created_at": NOW,
        "updated_at": NOW,
    }
    async with httpx.AsyncClient(auth=AUTH) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{DB}/_api/document/agents",
            json=agent,
        )
        if resp.status_code in (200, 201, 202):
            print(f"  ✅ Agent 'crm_assistant' created")
        elif resp.status_code == 409:
            resp = await client.put(
                f"{ARANGO_URL}/_db/{DB}/_api/document/agents/crm_assistant",
                json=agent,
            )
            if resp.status_code in (200, 201, 202):
                print(f"  ✅ Agent 'crm_assistant' updated")
            else:
                print(f"  ❌ Failed to update crm_assistant: {resp.status_code}")
        else:
            print(f"  ❌ Failed to create crm_assistant: {resp.status_code}")


async def main():
    print("=== 業務平台助手 DB 初始化 ===\n")
    
    print("1. 確保集合存在...")
    await ensure_collections()
    
    print("\n2. 建立 Agent 紀錄...")
    await seed_agent()
    
    print("\n3. 建立 CRM 助理 Agent 卡片...")
    await seed_crm_assistant()
    
    print("\n=== 完成 ===")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
