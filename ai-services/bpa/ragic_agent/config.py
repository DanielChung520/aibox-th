"""
@file        Ragic Agent — 環境變數與設定
@lastUpdate  2026-04-27 23:40:00
"""

import os
from dotenv import load_dotenv
load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
KNOWLEDGE_AGENT_URL = os.getenv("KNOWLEDGE_AGENT_URL", "http://127.0.0.1:8011/ka")
RAGIC_MODEL = os.getenv("RAGIC_AGENT_MODEL", "qwen3-next:latest")
RAGIC_KB_ROOT_ID = os.getenv("RAGIC_KB_ROOT_ID", "kb_1776656567810")
MAX_HISTORY = int(os.getenv("RAGIC_MAX_HISTORY", "20"))

SYSTEM_PROMPT = """你是一個專業的 Ragic 操作助手，專注於回答使用者關於 Ragic 軟體的操作問題。請用繁體中文回答，提供具體步驟。"""
