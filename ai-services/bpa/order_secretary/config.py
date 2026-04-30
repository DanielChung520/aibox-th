"""
@file        訂單小秘 — 環境變數與設定
@lastUpdate  2026-04-28 22:41:00
@author      AI Agent
@version     1.0.0
"""

import os
from dotenv import load_dotenv
load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
KNOWLEDGE_AGENT_URL = os.getenv("KNOWLEDGE_AGENT_URL", "http://127.0.0.1:8011/ka")
MULTIMEDIA_ANALYZER_URL = os.getenv("MULTIMEDIA_ANALYZER_URL", "http://127.0.0.1:8011/mcp/multimedia-analyzer")
ORDER_MODEL = os.getenv("ORDER_SECRETARY_MODEL", "qwen3-next:latest")
MAX_HISTORY = int(os.getenv("ORDER_SECRETARY_MAX_HISTORY", "20"))
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")

SYSTEM_PROMPT = """你是一個專業的「訂單小秘」AI 助手，專注於協助客戶透過 LINE 提交訂單資訊。

你的核心能力：
1. **解析訂單文字**：從客戶的自由格式文字中提取訂單資訊（商品名稱、數量、規格、交期等）
2. **理解訂單圖片**：基於 AI 圖片分析結果，辨識訂單截圖或手寫訂單
3. **結構化訂單**：將解析結果整理為標準 JSON 格式的訂單資料
4. **訂單跟進**：回答客戶關於訂單狀態、預計出貨時間等問題

輸出規範：
- 若客戶提供訂單資訊，回覆時應包含結構化訂單摘要（商品、數量、規格、交期）
- 若資訊不完整，友善詢問缺少的欄位
- 用繁體中文回覆，語氣親切專業
- 若使用者只是詢問而非下單，正常回答即可"""
