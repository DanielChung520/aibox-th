"""
@file        訂單小秘 — TWHC 訂單處理 Agent
@description 解析 LINE 平台的訂單文字、圖片、Excel，結構化後存入 Ragic，支援訂單跟進。
             Phase 1：LINE 平台；後續可透過工具市集擴展 WhatsApp/Dingtalk。
@lastUpdate  2026-04-28 22:41:00
@author      AI Agent
@version     1.0.0
"""

from bpa.order_secretary.main import app  # noqa: F401
