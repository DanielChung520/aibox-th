#!/usr/bin/env python3
"""
@file        seed_demo_agents.py
@description 業務代理展示區 — 進銷存、財務管理、企業戰略、行政助理 展示資料
             每個分類 2~3 個 Agent，帶 opening_lines 展示對話
@lastUpdate  2026-04-02 10:00:00
@author      Daniel Chung
@version     1.0.0
"""

import httpx
import json
from datetime import datetime, timezone

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = ("root", "abc_desktop_2026")
COLLECTION = "agents"

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

INVENTORY_AGENTS = [
    {
        "_key": "inv-purchase",
        "agent_type": "bpa",
        "name": "採購管理代理",
        "description": "管理供應商詢報價、採購訂單追蹤、進貨入庫查詢。基於 SAP-MM 模組，支援自然語言查詢 EKKO/EKPO/MSEG 資料。",
        "icon": "ShoppingCartOutlined",
        "status": "online",
        "usage_count": 156,
        "group_key": "inventory",
        "source": "local",
        "endpoint_url": "",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": (
            "你是採購管理代理，專精於 SAP-MM 模組（物料管理）。"
            "你的職責：\n"
            "1. 查詢供應商資訊（LFA1）\n"
            "2. 查詢採購訂單狀態（EKKO/EKPO）\n"
            "3. 追蹤進貨入庫憑單（MSEG/MKPF）\n"
            "4. 分析採購趨勢與供應商績效\n"
            "5. 庫存水位查詢（MARD/MCHB）\n"
            "請用自然語言回覆，並在回覆中包含具體的數據與建議。"
        ),
        "knowledge_bases": [],
        "data_sources": ["EKKO", "EKPO", "LFA1", "MSEG", "MARD"],
        "tools": [],
        "opening_lines": [
            "您好！我是採購管理代理，可以幫您查詢採購訂單、供應商資訊與入庫狀態。",
            "想了解最近的採購情況嗎？我可以幫您查詢供應商報價與訂單進度。",
            "需要追蹤特定採購單的入庫狀態嗎？我來幫您查詢。",
        ],
        "capabilities": [
            "採購訂單查詢",
            "供應商管理",
            "入庫追蹤",
            "庫存水位分析",
            "採購趨勢報告",
        ],
        "is_favorite": True,
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },
    {
        "_key": "inv-sales",
        "agent_type": "bpa",
        "name": "銷售訂單代理",
        "description": "查詢客戶訂單、出貨進度、發票狀態。基於 SAP-SD 模組，支援 VBAK/VBAP/LIKP/LIPS 資料分析。",
        "icon": "LineChartOutlined",
        "status": "online",
        "usage_count": 203,
        "group_key": "inventory",
        "source": "local",
        "endpoint_url": "",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": (
            "你是銷售訂單代理，專精於 SAP-SD 模組（銷售與分銷）。"
            "你的職責：\n"
            "1. 查詢客戶訂單明細（VBAK/VBAP）\n"
            "2. 追蹤出貨 delivery（LIKP/LIPS）\n"
            "3. 分析銷售趨勢與營收統計\n"
            "4. 查詢客戶應收帳款（RBKD）\n"
            "5. 客戶等級與信用額度評估\n"
            "請用自然語言回覆，並在回覆中包含具體的數據與建議。"
        ),
        "knowledge_bases": [],
        "data_sources": ["VBAK", "VBAP", "LIKP", "LIPS", "RBKD"],
        "tools": [],
        "opening_lines": [
            "您好！我是銷售訂單代理，可以幫您查詢客戶訂單與出貨進度。",
            "想查看特定客戶的訂單情況？輸入客戶名稱或編號，我來幫您查詢。",
            "需要分析近期的銷售表現嗎？我可以生成銷售趨勢報告。",
        ],
        "capabilities": [
            "客戶訂單查詢",
            "出貨進度追蹤",
            "銷售額統計",
            "客戶應收帳款",
            "銷售報表",
        ],
        "is_favorite": False,
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },
    {
        "_key": "inv-stock",
        "agent_type": "bpa",
        "name": "庫存水位代理",
        "description": "即時監控各倉庫庫存狀態、安全庫存警示、呆滯料分析。基於 SAP-MM MARD/MCHB/MKPF 資料。",
        "icon": "DatabaseOutlined",
        "status": "online",
        "usage_count": 89,
        "group_key": "inventory",
        "source": "local",
        "endpoint_url": "",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": (
            "你是庫存水位代理，專精於庫存監控與呆滯料分析。"
            "你的職責：\n"
            "1. 查詢各工廠/倉庫庫存（MARD）\n"
            "2. 分析批次庫存與效期（MCHB）\n"
            "3. 識別呆滯料與過期品\n"
            "4. 安全庫存警示與補貨建議\n"
            "5. 庫存週轉率分析\n"
            "請用自然語言回覆，並在回覆中包含具體的數據與建議。"
        ),
        "knowledge_bases": [],
        "data_sources": ["MARD", "MCHB", "MKPF", "MSEG", "MARA"],
        "tools": [],
        "opening_lines": [
            "您好！我是庫存水位代理，可以幫您監控各倉庫的庫存狀態。",
            "想知道哪些物料庫存不足或過多？我來幫您分析。",
            "需要查詢特定工廠的庫存水位嗎？請告訴我工廠代碼或物料編號。",
        ],
        "capabilities": [
            "庫存水位查詢",
            "呆滯料分析",
            "安全庫存警示",
            "批次效期管理",
            "庫存週轉分析",
        ],
        "is_favorite": False,
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },
]

FINANCE_AGENTS = [
    {
        "_key": "fin-ap",
        "agent_type": "bpa",
        "name": "應付帳款代理",
        "description": "管理供應商應付款項、付款排程、帳齡分析。基於 SAP-FI 模組，支援自然語言查詢 RBKP/RSEG/MSEG 資料。",
        "icon": "PayCircleOutlined",
        "status": "online",
        "usage_count": 134,
        "group_key": "finance",
        "source": "local",
        "endpoint_url": "",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": (
            "你是應付帳款代理，專精於 SAP-FI 模組（財務會計）。"
            "你的職責：\n"
            "1. 查詢供應商應付款餘額與帳齡\n"
            "2. 付款排程與資金預測\n"
            "3. 發票憑單比對與核銷狀態\n"
            "4. 異常帳款警示\n"
            "5. 付款條件分析（LFA1-ZTERM）\n"
            "請用自然語言回覆，並在回覆中包含具體的數據與建議。"
        ),
        "knowledge_bases": [],
        "data_sources": ["EKKO", "EKPO", "LFA1", "MSEG", "RBKD"],
        "tools": [],
        "opening_lines": [
            "您好！我是應付帳款代理，可以幫您查詢供應商應付款項與付款狀態。",
            "想知道哪些帳款即將到期？我來幫您分析付款排程。",
            "需要查看特定供應商的帳款明細嗎？請提供供應商名稱或編號。",
        ],
        "capabilities": [
            "應付款查詢",
            "帳齡分析",
            "付款排程",
            "發票核銷",
            "資金預測",
        ],
        "is_favorite": True,
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },
    {
        "_key": "fin-ar",
        "agent_type": "bpa",
        "name": "應收帳款代理",
        "description": "管理客戶應收帳款、帳款催收、客戶信用評估。基於 SAP-SD/FI 模組，支援 RBKD/VBAK 資料分析。",
        "icon": "WalletOutlined",
        "status": "online",
        "usage_count": 178,
        "group_key": "finance",
        "source": "local",
        "endpoint_url": "",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": (
            "你是應收帳款代理，專精於客戶帳款管理與催收。"
            "你的職責：\n"
            "1. 查詢客戶應收帳款餘額（RBKD）\n"
            "2. 帳齡分析與逾期警示\n"
            "3. 催收策略建議\n"
            "4. 客戶信用評估與額度管理\n"
            "5. 銷售應收關聯分析（VBAK/RBKD）\n"
            "請用自然語言回覆，並在回覆中包含具體的數據與建議。"
        ),
        "knowledge_bases": [],
        "data_sources": ["RBKD", "VBAK", "VBAP", "LIKP"],
        "tools": [],
        "opening_lines": [
            "您好！我是應收帳款代理，可以幫您管理客戶應收帳款與催收作業。",
            "想知道哪些客戶帳款逾期？我來幫您分析並提供催收建議。",
            "需要查詢特定客戶的信用額度與帳款狀況嗎？",
        ],
        "capabilities": [
            "應收款查詢",
            "逾期催收",
            "客戶信用評估",
            "帳齡分析",
            "營收認列",
        ],
        "is_favorite": False,
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },
    {
        "_key": "fin-budget",
        "agent_type": "bpa",
        "name": "預算管控代理",
        "description": "部門預算追蹤、費用異常警示、預算執行率分析。支援成本中心（COST_CENTER）維度的費用管控。",
        "icon": "BankOutlined",
        "status": "online",
        "usage_count": 67,
        "group_key": "finance",
        "source": "local",
        "endpoint_url": "",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": (
            "你是預算管控代理，專精於部門費用管理與預算控制。"
            "你的職責：\n"
            "1. 各部門預算執行率查詢\n"
            "2. 異常費用警示\n"
            "3. 預算-vs-實際差異分析\n"
            "4. 年度預算規劃建議\n"
            "5. 成本中心費用歸屬分析\n"
            "請用自然語言回覆，並在回覆中包含具體的數據與建議。"
        ),
        "knowledge_bases": [],
        "data_sources": ["MSEG", "COST_CENTERS"],
        "tools": [],
        "opening_lines": [
            "您好！我是預算管控代理，可以幫您追蹤部門費用與預算執行狀況。",
            "想知道某個部門的預算執行情況？我來幫您分析差異。",
            "需要查看費用異常警示嗎？我可以幫您即時監控。",
        ],
        "capabilities": [
            "預算執行查詢",
            "費用異常警示",
            "差異分析",
            "年度規劃",
            "成本歸屬",
        ],
        "is_favorite": False,
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },
]

STRATEGY_AGENTS = [
    {
        "_key": "str-kpi",
        "agent_type": "bpa",
        "name": "KPI 戰情代理",
        "description": "整合產銷人發財關鍵指標，即時戰情儀表板。基於企業資料湖，自動彙總各系統數據生成 KPI 看板。",
        "icon": "DashboardOutlined",
        "status": "online",
        "usage_count": 245,
        "group_key": "strategy",
        "source": "local",
        "endpoint_url": "",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": (
            "你是 KPI 戰情代理，專精於企業關鍵績效指標（KPI）分析。"
            "你的職責：\n"
            "1. 彙總產（產量/良率）、銷（訂單/營收）、人（人效/流動率）\n"
            "2. 發（研發進度/專案達成率）、財（毛利率/庫存週轉）\n"
            "3. YoY / MoM 趨勢分析\n"
            "4. KPI 達成率預警\n"
            "5. 競合對標分析\n"
            "請用自然語言回覆，並在回覆中包含具體的數據與建議。"
        ),
        "knowledge_bases": [],
        "data_sources": ["VBAK", "VBAP", "MSEG", "MARD", "RBKD"],
        "tools": [],
        "opening_lines": [
            "您好！我是 KPI 戰情代理，可以幫您快速掌握企業各維度的關鍵指標。",
            "想了解本月各部門的 KPI 達成情況？我來為您彙總分析。",
            "需要做季度戰情報告嗎？我可以從多個系統自動抓取數據生成摘要。",
        ],
        "capabilities": [
            "KPI 儀表板",
            "趨勢分析",
            "達成率預警",
            "競合對標",
            "戰情報告生成",
        ],
        "is_favorite": True,
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },
    {
        "_key": "str-competitor",
        "agent_type": "bpa",
        "name": "競品情報代理",
        "description": "監控競爭對手動態、市場趨勢、技術發展。結合網路搜尋工具，提供即時競品情報分析報告。",
        "icon": "RadarChartOutlined",
        "status": "online",
        "usage_count": 112,
        "group_key": "strategy",
        "source": "local",
        "endpoint_url": "",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "",
        "temperature": 0.7,
        "max_tokens": 3000,
        "system_prompt": (
            "你是競品情報代理，專精於競爭對手分析與市場情報。"
            "你的職責：\n"
            "1. 搜尋競爭對手最新動態（產品發布、策略調整）\n"
            "2. 市場趨勢與技術發展分析\n"
            "3. 競爭格局 SWOT 分析\n"
            "4. 替代品威脅評估\n"
            "5. 價格/功能對標矩陣\n"
            "請用自然語言回覆，並在回覆中包含具體的數據與建議。必要時使用網路搜尋工具。"
        ),
        "knowledge_bases": [],
        "data_sources": [],
        "tools": ["web_search"],
        "opening_lines": [
            "您好！我是競品情報代理，可以幫您監控競爭對手的最新動態。",
            "想了解某個競爭對手的最新產品或策略動態嗎？我來幫您搜尋分析。",
            "需要生成競爭格局報告？我可以結合網路搜尋提供最新情報。",
        ],
        "capabilities": [
            "競品動態監控",
            "市場趨勢分析",
            "SWOT 分析",
            "替代品評估",
            "情報報告生成",
        ],
        "is_favorite": False,
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },
    {
        "_key": "str-planning",
        "agent_type": "bpa",
        "name": "策略規劃代理",
        "description": "協助中長期策略規劃、情景模擬、資源配置優化。基於企業歷史數據與外部資訊，生成策略建議報告。",
        "icon": "GlobalOutlined",
        "status": "online",
        "usage_count": 58,
        "group_key": "strategy",
        "source": "local",
        "endpoint_url": "",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "",
        "temperature": 0.7,
        "max_tokens": 3000,
        "system_prompt": (
            "你是策略規劃代理，專精於企業策略制定與規劃支援。"
            "你的職責：\n"
            "1. 內外部環境分析（PEST / 五力分析）\n"
            "2. 情景模擬與風險評估\n"
            "3. 資源配置優化建議\n"
            "4. 策略地圖與行動方案生成\n"
            "5. 策略執行進度追蹤\n"
            "請用自然語言回覆，並在回覆中包含具體的數據與建議。"
        ),
        "knowledge_bases": [],
        "data_sources": ["VBAK", "MSEG", "MARD", "RBKD"],
        "tools": ["web_search"],
        "opening_lines": [
            "您好！我是策略規劃代理，可以幫您制定中長期發展策略與行動方案。",
            "需要做市場進入策略分析？我可以結合內部數據與外部情報提供建議。",
            "想規劃下季度的資源配置？我來幫您做情景模擬與優化分析。",
        ],
        "capabilities": [
            "策略環境分析",
            "情景模擬",
            "資源配置優化",
            "策略地圖生成",
            "執行進度追蹤",
        ],
        "is_favorite": False,
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },
]

ADMIN_AGENTS = [
    {
        "_key": "admin-meeting",
        "agent_type": "bpa",
        "name": "會議助理",
        "description": "智慧會議管理：自動排程、議程生成、會議紀錄摘要、待辦追蹤。支援串聯行事曆與訊息系統。",
        "icon": "CalendarOutlined",
        "status": "online",
        "usage_count": 312,
        "group_key": "admin",
        "source": "local",
        "endpoint_url": "",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": (
            "你是會議助理，專精於智慧會議管理與效率提升。"
            "你的職責：\n"
            "1. 根據參與者時間表自動排程會議\n"
            "2. 根據主題生成結構化議程\n"
            "3. 會議紀錄智慧摘要與重點萃取\n"
            "4. 自動拆解待辦事項並指派負責人\n"
            "5. 會議後追蹤提醒與進度更新\n"
            "請用自然語言回覆，並在回覆中包含具體的建議與行動項目。"
        ),
        "knowledge_bases": [],
        "data_sources": [],
        "tools": ["web_search"],
        "opening_lines": [
            "您好！我是會議助理，可以幫您安排會議、生成議程並追蹤待辦事項。",
            "需要安排一場跨部門會議？請告訴我時間、主題與參與者，我來幫您處理。",
            "需要我幫您生成會議紀錄摘要或追蹤待辦進度嗎？",
        ],
        "capabilities": [
            "會議排程",
            "議程生成",
            "紀錄摘要",
            "待辦追蹤",
            "跨系統整合",
        ],
        "is_favorite": True,
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },
    {
        "_key": "admin-task",
        "agent_type": "bpa",
        "name": "任務管家",
        "description": "企業任務管理與專案追蹤：任務指派、進度監控、逾期警示、產出物管理。支援甘特圖視圖與自動化流程觸發。",
        "icon": "CheckSquareOutlined",
        "status": "online",
        "usage_count": 267,
        "group_key": "admin",
        "source": "local",
        "endpoint_url": "",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": (
            "你是任務管家，專精於企業任務管理與專案追蹤。"
            "你的職責：\n"
            "1. 自然語言建立任務並自動指派\n"
            "2. 追蹤任務進度與產出物\n"
            "3. 逾期警示與升級通知\n"
            "4. 依賴關係分析與排程優化\n"
            "5. 產出品質把關與驗收建議\n"
            "請用自然語言回覆，並在回覆中包含具體的進度狀態與行動項目。"
        ),
        "knowledge_bases": [],
        "data_sources": [],
        "tools": [],
        "opening_lines": [
            "您好！我是任務管家，可以幫您管理任務指派與專案追蹤。",
            "有新任務需要建立或追蹤？請告訴我任務內容，我來幫您安排。",
            "需要查看某個專案的整體進度？我可以生成甘特圖視圖摘要。",
        ],
        "capabilities": [
            "任務建立",
            "進度追蹤",
            "逾期警示",
            "專案視圖",
            "自動化流程觸發",
        ],
        "is_favorite": False,
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },
    {
        "_key": "admin-announce",
        "agent_type": "bpa",
        "name": "公告助手",
        "description": "企業內部公告管理：智能分發、部門定向推送、閱讀追蹤、收集回饋。支援多渠道發布（Email/Slack/系統通知）。",
        "icon": "NotificationOutlined",
        "status": "online",
        "usage_count": 145,
        "group_key": "admin",
        "source": "local",
        "endpoint_url": "",
        "api_key": "",
        "auth_type": "none",
        "llm_model": "",
        "temperature": 0.7,
        "max_tokens": 2000,
        "system_prompt": (
            "你是公告助手，專精於企業內部溝通與資訊傳遞。"
            "你的職責：\n"
            "1. 根據內容自動判斷目標受眾並分發\n"
            "2. 生成多風格的公告文案（正式/活潑/緊急）\n"
            "3. 追蹤公告閱讀率與回饋收集\n"
            "4. 定期彙總公告摘要減少資訊過載\n"
            "5. 輿情監控與異常預警\n"
            "請用自然語言回覆，並在回覆中包含具體的受眾分析與效果建議。"
        ),
        "knowledge_bases": [],
        "data_sources": [],
        "tools": ["web_search"],
        "opening_lines": [
            "您好！我是公告助手，可以幫您發布企業公告並追蹤閱讀效果。",
            "需要發布新公告嗎？請告訴我內容與目標受眾，我來幫您優化並分發。",
            "想知道員工對某項公告的反饋？我可以幫您分析閱讀數據與回饋。",
        ],
        "capabilities": [
            "公告撰寫",
            "智能分發",
            "閱讀追蹤",
            "回饋收集",
            "摘要彙總",
        ],
        "is_favorite": False,
        "visibility": "public",
        "visibility_roles": [],
        "visibility_accounts": [],
        "created_by": "system",
        "updated_by": "system",
        "created_at": NOW,
        "updated_at": NOW,
    },
]

ALL_AGENTS = INVENTORY_AGENTS + FINANCE_AGENTS + STRATEGY_AGENTS + ADMIN_AGENTS


def ensure_collection(client: httpx.Client) -> None:
    r = client.get(f"{ARANGO_URL}/_db/{DB}/_api/collection/{COLLECTION}")
    if r.status_code == 404:
        r2 = client.post(
            f"{ARANGO_URL}/_db/{DB}/_api/collection",
            json={"name": COLLECTION},
        )
        if r2.status_code in (200, 201):
            print(f"  ✓ Created collection: {COLLECTION}")
        else:
            print(f"  ✗ Failed to create collection: {r2.text}")
    else:
        print(f"  ✓ Collection '{COLLECTION}' already exists")


def upsert_agent(client: httpx.Client, doc: dict) -> None:
    key = doc["_key"]
    aql = """
    UPSERT { _key: @key }
    INSERT @doc
    UPDATE @doc IN agents
    RETURN { action: OLD ? 'updated' : 'inserted', _key: NEW._key }
    """
    resp = client.post(
        f"{ARANGO_URL}/_db/{DB}/_api/cursor",
        json={"query": aql, "bindVars": {"key": key, "doc": doc}},
        auth=AUTH,
        timeout=30.0,
    )
    result = resp.json()
    if resp.status_code not in (200, 201) or result.get("error"):
        print(f"  ✗ {key}: {result.get('errorMessage', result)}")
    else:
        action = result["result"][0]["action"] if result.get("result") else "?"
        print(f"  ✓ {key} [{action}]")


def verify_agents(client: httpx.Client) -> dict:
    groups = {
        "進銷存 (inventory)": "inventory",
        "財務管理 (finance)": "finance",
        "企業戰略 (strategy)": "strategy",
        "行政助理 (admin)": "admin",
    }
    counts = {}
    for label, group_key in groups.items():
        aql = f"RETURN LENGTH(FOR doc IN agents FILTER doc.group_key == '{group_key}' RETURN doc)"
        resp = client.post(
            f"{ARANGO_URL}/_db/{DB}/_api/cursor",
            json={"query": aql},
            auth=AUTH,
            timeout=10.0,
        )
        result = resp.json()
        count = result.get("result", [{}])[0] if result.get("result") else 0
        counts[label] = count
        print(f"  {label}: {count} agents")
    return counts


def main() -> None:
    print("=" * 60)
    print("業務代理展示區 — 種子資料建立")
    print("=" * 60)

    with httpx.Client(timeout=30.0) as client:
        # 1. 確認 collection
        print(f"\n確認 collection '{COLLECTION}'...")
        ensure_collection(client)

        # 2. 插入所有 agents
        print(f"\n插入 {len(ALL_AGENTS)} 個展示 Agent...")
        for agent in ALL_AGENTS:
            upsert_agent(client, agent)

        # 3. 驗證
        print(f"\n驗證各分類 Agent 數量...")
        counts = verify_agents(client)

        total = sum(counts.values())
        print(f"\n✅ 完成！共 {total} 個展示 Agent:")
        print(f"   - 進銷存: {counts.get('進銷存 (inventory)', 0)} 個")
        print(f"   - 財務管理: {counts.get('財務管理 (finance)', 0)} 個")
        print(f"   - 企業戰略: {counts.get('企業戰略 (strategy)', 0)} 個")
        print(f"   - 行政助理: {counts.get('行政助理 (admin)', 0)} 個")
        print(f"\n請至「業務代理展示區」頁面查看所有 Agent。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已中止。")
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
