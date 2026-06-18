"""
@file        market_intel/pusher.py
@description 市場快報 LINE 推播 — 每天早上定時發送
@lastUpdate  2026-06-14
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

ARANGO_URL = "http://localhost:8529"
ARANGO_DB = "abc_desktop"
ARANGO_USER = "root"
ARANGO_PASSWORD = "abc_desktop_2026"


async def _aql(query: str, bind: dict | None = None) -> list[dict]:
    import httpx
    import base64
    auth = base64.b64encode(f"{ARANGO_USER}:{ARANGO_PASSWORD}".encode()).decode()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": query, "bindVars": bind or {}},
            headers={"Authorization": f"Basic {auth}"},
        )
        if resp.status_code not in (200, 201):
            raise Exception(f"AQL error: {resp.text}")
        return resp.json().get("result", [])


async def push_daily_report_to_all() -> dict[str, Any]:
    """產生今日快報並推播給所有業務員的 LINE"""
    today = date.today().isoformat()

    # 1. 取得今日快報
    reports = await _aql(
        "FOR r IN market_intel_reports FILTER r.date == @d LIMIT 1 RETURN r",
        {"d": today},
    )
    if not reports:
        return {"status": "skipped", "reason": "no_report_for_today"}

    report = reports[0]
    items = report.get("items", [])
    daily_focus = report.get("daily_focus", "")
    high_count = sum(1 for i in items if i.get("relevance") == "high")

    # 2. 取得所有啟用的 LINE 頻道（有綁定業務員的）
    channels = await _aql(
        "FOR c IN channels FILTER c.status == 'active' AND c.platform == 'line' RETURN c",
    )
    if not channels:
        return {"status": "skipped", "reason": "no_active_channels"}

    # 3. 對每個頻道發送
    success = 0
    failed = 0
    for ch in channels:
        try:
            await _push_to_channel(ch, report, daily_focus, high_count)
            success += 1
        except Exception as e:
            logger.warning("Push to channel %s failed: %s", ch.get("_key"), e)
            failed += 1

    return {"status": "ok", "pushed": success, "failed": failed, "date": today}


async def _push_to_channel(channel: dict, report: dict, focus: str, high_count: int) -> None:
    """推播到單一頻道"""
    from unified_agents.platforms.line.services.line_api import push_message

    config = channel.get("config", {})
    token = config.get("access_token", "")
    # 取得該業務員的 LINE 用戶 ID（存在 user_profile 或 channels 擴充欄位）
    # 此處假設頻道有對應的業務員個人 LINE ID
    # 若無則跳過
    owner_line_id = channel.get("owner_line_id", "")
    if not token or not owner_line_id:
        logger.info("Channel %s missing token or owner_line_id, skipping", channel.get("_key"))
        return

    items = report.get("items", [])
    # 取前 4 筆高/中關聯
    top_items = [i for i in items if i.get("relevance") in ("high", "medium")][:4]

    flex_contents = []
    for item in top_items:
        rel = item.get("relevance", "medium")
        emoji = "🔴" if rel == "high" else "🟡"
        flex_contents.append({
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": f"{emoji} {item['title']}", "weight": "bold", "size": "sm", "wrap": True},
                {"type": "text", "text": item.get("summary", "")[:80], "size": "xs", "color": "#666666", "wrap": True, "margin": "sm"},
            ],
            "margin": "md",
        })

    if not flex_contents:
        flex_contents.append({
            "type": "text", "text": "今日無重大市場資訊", "size": "sm", "color": "#888888",
        })

    # 建立 Flex Message
    flex_msg = {
        "type": "flex",
        "altText": f"📡 市場快報 {report.get('date', today)}",
        "contents": {
            "type": "bubble",
            "hero": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "📡 今日市場快報", "weight": "bold", "size": "lg", "color": "#ffffff"},
                    {"type": "text", "text": report.get("date", today), "size": "xs", "color": "#aaaaaa", "margin": "sm"},
                ],
                "paddingAll": "16px",
                "backgroundColor": "#1a365d",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": focus or "市場資訊整理完成", "size": "sm", "wrap": True, "color": "#333333"},
                    {"type": "separator", "margin": "md"},
                    *flex_contents,
                ],
                "paddingAll": "16px",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "uri",
                            "label": "📋 查看完整報告",
                            "uri": f"https://eea.ent4i.com/app/eea-crm/market-intel",
                        },
                        "style": "primary",
                        "color": "#1a365d",
                    }
                ],
                "paddingAll": "12px",
            },
        },
    }

    await push_message(token, owner_line_id, [flex_msg])
    logger.info("Pushed market intel to %s", channel.get("_key"))
