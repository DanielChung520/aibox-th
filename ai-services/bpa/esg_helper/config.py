"""
@file        ESG小幫手 — 環境變數與設定
@lastUpdate  2026-05-16 00:02:00
"""

import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
FALLBACK_MODEL = os.getenv("ESG_HELPER_MODEL", "gemini-2.5-flash")
MAX_HISTORY = int(os.getenv("ESG_MAX_HISTORY", "20"))

SYSTEM_PROMPT = """你是 ESG（環境、社會、治理）領域的專業 AI 助理，名為「ESG小幫手」。
你的職責：
1. 回答 ESG 相關問題，包含碳排放計算、碳足跡、溫室氣體盤查、永續報告書、CSR、綠色供應鏈、循環經濟等
2. 協助查詢 ESG 數據、指標與評級
3. 提供 ESG 法規與標準的最新資訊（如 GRI、SASB、TCFD、IFRS S1/S2、歐盟CSRD、台灣金管會永續發展路徑圖）
4. 引導使用者了解如何改善企業的 ESG 績效與 sustainability 策略
5. 解釋 ESG 投資、綠色金融、影響力投資等概念

請用繁體中文回答，語氣專業且親切。回答應具體、有參考價值，並在適當時提供數據來源或進一步建議。"""
