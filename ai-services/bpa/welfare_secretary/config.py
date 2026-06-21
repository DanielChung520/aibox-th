"""
@file        業務平台助手 — 配置管理
@description 從 ArangoDB system_params 讀取所有配置，禁止 hardcode
@lastUpdate  2026-06-19
@author      Sisyphus
@version     1.0.0
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ---- 環境變數 fallback ----
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")

DEFAULT_MODEL = os.getenv("WELFARE_SECRETARY_MODEL", "qwen3:latest")
DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

# ---- 預設 System Prompt（被 system_params 覆蓋） ----

SYSTEM_PROMPT_CUSTOMER = """你是一個專業親切的「業務平台助手」AI 助手，服務於台灣福祉股份有限公司的客戶。

【角色定位】
- 你是公司派駐在 LINE 上的客服助手，協助客戶解答問題
- 語氣溫暖禮貌，用繁體中文回覆
- 若客戶詢問你無法確認的資訊，誠實告知並建議聯繫業務人員

【核心能力】
1. 日常問候回應：早安、節日祝賀、天氣提醒等
2. 產品/服務 FAQ 回答：根據知識庫內容回覆
3. 互動歷史摘要：查詢客戶與公司的互動記錄（僅回傳摘要，不含金額明細）
4. 名片收藏：收到名片圖片時進行 OCR 處理

【資訊安全規則 — 嚴格遵守】
- L0（公開資訊）：產品介紹、服務項目、營業時間 → 可直接回覆
- L1（FAQ）：常見問題、使用說明 → 可回覆
- L2（互動摘要）：Timeline 時間/類型/摘要 → 僅回傳摘要，不含明細
- L3（機密明細）：報價金額、訂單成本、合約條款 → 婉轉拒答「已轉達業務，將由業務直接回覆」
- L4（內部操作）：下單、改單、取消訂單 → 婉轉拒答「已轉達業務，將由業務直接回覆」

【禁止行為】
- 嚴禁自行編造產品資訊、價格、庫存資料
- 嚴禁透露任何客戶的個人資料給其他客戶
- 不可執行任何訂單操作"""

SYSTEM_PROMPT_INTERNAL = """你是一個專業的「業務平台助手」AI 助手，協助業務人員處理日常工作。

【角色定位】
- 你是業務人員的個人工作助理，協助查詢 ERP/CRM 資料
- 語氣專業有效率，用繁體中文回覆
- 你的使用者是公司內部業務人員，擁有完整資訊權限

【核心能力】
1. ERP 查詢：查詢報價、訂單、出貨狀態（透過 Data Agent）
2. CRM 查詢：查詢客戶詳情、聯絡人資訊
3. 代理客戶問候：代替業務傳送問候/節日祝福給客戶
4. 群發訊息：文字公告、產品宣傳
5. 名片掃描：OCR → CRM 寫入
6. 行程安排：記錄拜訪日期/地點/客戶
7. Timeline 整理：彙整客戶互動記錄

【輸出規範】
- 資訊查詢結果應以結構化方式呈現（表格/列表）
- 若資訊不足，明確告知缺少什麼
- 對於需要確認的操作（如群發），務必先要求使用者確認"""

# ---- 快取 ----
_config_cache: dict | None = None


async def load_config() -> dict:
    """從 system_params 載入業務平台助手的配置，含快取。

    快取 key: "welfare_secretary_config"（5 分鐘 TTL），由排程或寫入時更新。
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    import base64
    import httpx

    auth_cred = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(auth_cred.encode()).decode()}",
    }
    aql = """FOR p IN system_params
             FILTER p._key IN ["welfare_secretary", "llm_config", "greeting.honorific_map"]
             RETURN p"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": aql},
                headers=headers,
            )
            if resp.status_code in (200, 201):
                results = resp.json().get("result", [])
                config: dict = {}
                for p in results:
                    config[p["_key"]] = p.get("value", p)
                _config_cache = config
                logger.info(f"[Config] Loaded {len(results)} params from system_params")
                return config
    except Exception as e:
        logger.warning(f"[Config] Failed to load from system_params: {e}")

    _config_cache = {}
    return _config_cache


async def get_model_config(agent_key: str = "welfare_secretary") -> tuple[str, str, str, str]:
    """從 agents + model_providers 集合解析 LLM 設定。

    Returns:
        (model_id, api_base, api_key, system_prompt)
    """
    import base64
    import httpx

    model = DEFAULT_MODEL
    api_base = DEFAULT_OLLAMA_URL
    api_key = ""
    system_prompt = SYSTEM_PROMPT_CUSTOMER

    auth_cred = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(auth_cred.encode()).decode()}",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 查 agent 紀錄
            resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": "FOR a IN agents FILTER a._key == @key LIMIT 1 RETURN a", "bindVars": {"key": agent_key}},
                headers=headers,
            )
            if resp.status_code in (200, 201):
                agents = resp.json().get("result", [])
                if agents:
                    agent = agents[0]
                    if agent.get("llm_model"):
                        model = agent["llm_model"]
                    if agent.get("system_prompt"):
                        system_prompt = agent["system_prompt"]

            # 查 model_providers
            resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": "FOR p IN model_providers FILTER p.status == 'enabled' RETURN p"},
                headers=headers,
            )
            if resp.status_code in (200, 201):
                providers = resp.json().get("result", [])
                for p in providers:
                    p_models = p.get("models") or []
                    for m in p_models:
                        if isinstance(m, dict) and m.get("model_id") == model:
                            api_base = (p.get("base_url") or "").rstrip("/")
                            api_key = p.get("api_key") or ""
                            break
                    if api_base != DEFAULT_OLLAMA_URL:
                        break
    except Exception as e:
        logger.warning(f"[Config] Model config resolution failed: {e}")

    return model, api_base, api_key, system_prompt
