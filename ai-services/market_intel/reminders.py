"""
@file        market_intel/reminders.py
@description 每日提醒：行程提醒 + 久未聯絡提醒
@lastUpdate  2026-06-14
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

ARANGO_URL = "http://localhost:8529"
ARANGO_DB = "abc_desktop"
ARANGO_USER = "root"
ARANGO_PASSWORD = "abc_desktop_2026"


async def _aql(query: str, bind: dict | None = None) -> list[dict]:
    import httpx, base64
    auth = base64.b64encode(f"{ARANGO_USER}:{ARANGO_PASSWORD}".encode()).decode()
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": query, "bindVars": bind or {}},
            headers={"Authorization": f"Basic {auth}"},
        )
        if resp.status_code not in (200, 201):
            return []
        return resp.json().get("result", [])


async def send_line_message(token: str, user_id: str, text: str) -> bool:
    """透過 LINE API 發送文字訊息"""
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.line.me/v2/bot/message/push",
            json={"to": user_id, "messages": [{"type": "text", "text": text}]},
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.status_code == 200


async def send_visit_reminders() -> dict[str, Any]:
    """檢查今天有行程的業務員，發送 LINE 提醒"""
    today = date.today().isoformat()
    sent = 0

    # 查今天有行程的 visit_plans + 對應頻道
    plans = await _aql(
        """FOR v IN visit_plans
           FILTER v.visit_date == @d AND v.status == 'planned'
           FOR c IN channels
             FILTER c.business_user_key == v.created_by AND c.status == 'active'
             RETURN {plan: v, channel: c}""",
        {"d": today},
    )

    for p in plans:
        plan = p.get("plan", {})
        ch = p.get("channel", {})
        config = ch.get("config", {})
        token = config.get("access_token", "")
        owner_line = ch.get("owner_line_id", "")
        if not token or not owner_line:
            continue

        customer = plan.get("customer_name", "客戶")
        location = plan.get("location", "")
        notes = plan.get("notes", "")

        text = (
            f"📅 今日行程提醒\n\n"
            f"👤 客戶：{customer}\n"
            f"📍 地點：{location or '未設定'}\n"
            f"{'📝 備註：' + notes if notes else ''}\n\n"
            f"開車前別忘了打開地圖導航！"
        )
        try:
            ok = await send_line_message(token, owner_line, text)
            if ok:
                sent += 1
        except Exception as e:
            logger.warning("Visit reminder push failed: %s", e)

    return {"type": "visit_reminder", "sent": sent, "total": len(plans)}


async def send_follow_up_reminders(days_threshold: int = 7) -> dict[str, Any]:
    """檢查超過 N 天未聯絡的客戶，提醒業務員跟進"""
    sent = 0
    now = datetime.now(timezone.utc).isoformat()[:10]

    # 查各業務員的客戶最近一次 LINE 互動時間
    reminders_data = await _aql(
        """FOR c IN crm_contacts
           FILTER c.status == 'active' AND c.last_contacted_at != null
           LET days_since = DATE_DIFF(c.last_contacted_at, @now, 'day')
           FILTER days_since >= @threshold
           FOR ch IN channels
             FILTER ch.business_user_key == c.owner_key AND ch.status == 'active'
             RETURN {contact_name: c.name, days: days_since, channel: ch}""",
        {"now": now, "threshold": days_threshold},
    )

    # 依頻道分組
    by_channel: dict[str, dict[str, Any]] = {}
    for r in reminders_data:
        ch = r.get("channel", {})
        ch_key = ch.get("_key", "")
        if ch_key not in by_channel:
            config = ch.get("config", {})
            by_channel[ch_key] = {
                "token": config.get("access_token", ""),
                "owner_line": ch.get("owner_line_id", ""),
                "contacts": [],
            }
        by_channel[ch_key]["contacts"].append({
            "name": r.get("contact_name", "?"),
            "days": r.get("days", 0),
        })

    for ch_key, info in by_channel.items():
        token = info["token"]
        owner_line = info["owner_line"]
        contacts = info["contacts"]
        if not token or not owner_line or not contacts:
            continue

        # 最多列出 5 位
        top = contacts[:5]
        lines = "\n".join(f"  👤 {c['name']}（{c['days']} 天未聯繫）" for c in top)
        more = f"\n  ...及其他 {len(contacts) - 5} 位" if len(contacts) > 5 else ""

        text = (
            f"🔔 客戶跟進提醒\n\n"
            f"以下客戶已超過 {days_threshold} 天未聯繫：\n\n"
            f"{lines}{more}\n\n"
            f"建議今天抽空關心一下！"
        )
        try:
            ok = await send_line_message(token, owner_line, text)
            if ok:
                sent += 1
        except Exception as e:
            logger.warning("Follow-up reminder push failed for %s: %s", ch_key, e)

    total_contacts = sum(len(v["contacts"]) for v in by_channel.values())
    return {"type": "follow_up_reminder", "channels_sent": sent, "total_contacts": total_contacts}


async def run_all_reminders() -> dict[str, Any]:
    """執行所有提醒（供排程呼叫）"""
    visit = await send_visit_reminders()
    follow = await send_follow_up_reminders()
    return {"visit_reminder": visit, "follow_up_reminder": follow}
