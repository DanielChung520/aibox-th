"""
@file        greeting_settings/skill.py
@description 問候設定管理 Skill：接受業務自然語言指令，管理問候排程與模板
@lastUpdate  2026-06-20
@author      Sisyphus
@version     1.0.0

# Skill 規範

## 用途
業務人員可透過自然語言設定問候排程與模板，技能自動解析指令並更新設定。

## 輸入
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| business_user_key | string | ✅ | 業務人員 ID |
| instruction | string | ❌ | 自然語言指令（如「每天早上9點發早安問候」） |
| action | string | ❌ | 動作覆蓋：get_status / set_schedule / set_template / send_now / toggle |
| greeting_type | string | ❌ | 問候類型：morning / holiday / birthday / event |
| settings | dict | ❌ | 結構化設定（跳過 LLM 解析） |

## 輸出
| 屬性 | 類型 | 說明 |
|------|------|------|
| success | boolean | 操作是否成功 |
| message | string | 使用者面向的確認訊息 |
| settings | dict | 更新後的設定內容 |
"""

from __future__ import annotations

import json
import logging
import base64
import httpx
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

def _get_arango_config() -> dict:
    from bpa.welfare_secretary.config import ARANGO_URL, ARANGO_DB, ARANGO_USER, ARANGO_PASSWORD
    return {
        "url": ARANGO_URL,
        "db": ARANGO_DB,
        "user": ARANGO_USER,
        "password": ARANGO_PASSWORD,
    }

def _arango_headers(cfg: dict) -> dict:
    auth = base64.b64encode(f"{cfg['user']}:{cfg['password']}".encode()).decode()
    return {
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth}",
    }

PARSE_SYSTEM_PROMPT = "你是一個CRM業務設定解析器。嚴格按照使用者要求的JSON格式回傳。"

PARSE_PROMPT_TEMPLATE = """你是CRM設定解析助理。請將業務人員的指令解析為結構化JSON。

指令：{instruction}

可設定的問候類型：morning（早安）、holiday（節日）、birthday（生日）、event（活動）
可用動作：get_status（查看設定）、set_schedule（設定排程）、set_template（設定模板）、send_now（立即發送）、toggle（啟用/停用）

回傳格式（嚴格JSON，不要其他文字）：
{{
  "action": "get_status | set_schedule | set_template | send_now | toggle",
  "greeting_type": "morning | holiday | birthday | event | null",
  "settings": {{
    "schedule_time": "HH:MM 或 null",
    "template_text": "模板文字（用{{customer_name}}代替客戶名稱）或 null",
    "is_active": true | false | null,
    "target": "all | segment:xxx 或 null"
  }},
  "summary": "對指令的簡短中文說明"
}}
"""


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    """Skill 統一進入點。"""
    business_user_key = params.get("business_user_key", "")
    instruction = params.get("instruction", "")
    action = params.get("action", "")
    greeting_type = params.get("greeting_type")
    settings_update = params.get("settings", {})
    dry_run = params.get("dry_run", False)

    if not business_user_key:
        return {"success": False, "message": "business_user_key is required", "settings": {}}

    summary = ""
    if not action and instruction:
        parsed = await _parse_instruction(instruction)
        action = parsed.get("action", "get_status")
        settings_update = parsed.get("settings", {})
        greeting_type = parsed.get("greeting_type") or greeting_type
        summary = parsed.get("summary", "")
    elif not action:
        action = "get_status"

    cfg = _get_arango_config()

    if action == "get_status":
        return await _handle_get_status(cfg, business_user_key)

    elif action in ("set_schedule", "set_template", "toggle"):
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "message": f"即將{summary}，請確認是否執行？",
                "preview": summary,
                "settings": settings_update,
                "action": action,
                "greeting_type": greeting_type,
            }
        return await _handle_update(cfg, business_user_key, action, greeting_type, settings_update, summary)

    elif action == "send_now":
        return await _handle_send_now(business_user_key, greeting_type, settings_update)

    return {"success": False, "message": f"未知動作: {action}", "settings": {}}


async def _parse_instruction(instruction: str) -> dict:
    """用 LLM 解析自然語言指令為結構化設定。"""
    from shared.llm_resolver import resolve_and_call

    prompt = PARSE_PROMPT_TEMPLATE.format(instruction=instruction)
    result = await resolve_and_call(
        messages=[
            {"role": "system", "content": PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        model="ollama:gemma4:31b",
        temperature=0.1,
        max_tokens=512,
    )
    content = result.get("content", "{}")
    # 清理 markdown code block 包裝
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"[GreetingSettings] LLM parse failed, raw: {content[:200]}")
        return {"action": "get_status", "settings": {}, "summary": "無法解析指令"}


async def _load_settings(cfg: dict, business_user_key: str) -> dict:
    """從 greeting_templates 載入該業務的問候設定。"""
    headers = _arango_headers(cfg)
    doc_key = f"greeting_settings_{business_user_key}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{cfg['url']}/_db/{cfg['db']}/_api/document/greeting_templates/{doc_key}",
                headers=headers,
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning(f"[GreetingSettings] Load failed: {e}")
    return {
        "_key": doc_key,
        "business_user_key": business_user_key,
        "configs": {},
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


async def _save_settings(cfg: dict, doc: dict) -> bool:
    """寫入或更新 greeting_templates 中的設定文件。"""
    headers = _arango_headers(cfg)
    doc_key = doc.get("_key", "")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            check = await client.get(
                f"{cfg['url']}/_db/{cfg['db']}/_api/document/greeting_templates/{doc_key}",
                headers=headers,
            )
            if check.status_code == 200:
                resp = await client.put(
                    f"{cfg['url']}/_db/{cfg['db']}/_api/document/greeting_templates/{doc_key}",
                    json=doc,
                    headers=headers,
                )
            else:
                resp = await client.post(
                    f"{cfg['url']}/_db/{cfg['db']}/_api/document/greeting_templates",
                    json=doc,
                    headers=headers,
                )
            return resp.status_code in (200, 201, 202)
    except Exception as e:
        logger.warning(f"[GreetingSettings] Save failed: {e}")
        return False


async def _handle_get_status(cfg: dict, business_user_key: str) -> dict:
    """查詢目前問候設定。"""
    doc = await _load_settings(cfg, business_user_key)
    configs = doc.get("configs", {})
    if not configs:
        return {
            "success": True,
            "message": "目前尚未設定任何問候排程。您可以告訴我想要怎麼設定，例如「每天早上9點發早安問候」。",
            "settings": {},
        }
    return {
        "success": True,
        "message": "目前問候設定如下：",
        "settings": configs,
    }


async def _handle_update(
    cfg: dict,
    business_user_key: str,
    action: str,
    greeting_type: str | None,
    settings_update: dict,
    summary: str,
) -> dict:
    """更新問候設定。"""
    doc = await _load_settings(cfg, business_user_key)
    configs = doc.setdefault("configs", {})

    if greeting_type:
        config = configs.setdefault(greeting_type, {})
        if action == "set_schedule":
            if settings_update.get("schedule_time"):
                config["schedule_time"] = settings_update["schedule_time"]
            if settings_update.get("target"):
                config["target"] = settings_update["target"]
            config["is_active"] = settings_update.get("is_active", True)
            message = f"已設定 {greeting_type} 問候排程"
        elif action == "set_template":
            if settings_update.get("template_text"):
                config["template_text"] = settings_update["template_text"]
            message = f"已更新 {greeting_type} 問候模板"
        elif action == "toggle":
            config["is_active"] = settings_update.get("is_active", not config.get("is_active", True))
            status = "啟用" if config["is_active"] else "停用"
            message = f"已{status} {greeting_type} 問候"
        else:
            message = "設定已更新"
    else:
        for gtype, gcfg in settings_update.items():
            if isinstance(gcfg, dict):
                configs[gtype] = {**configs.get(gtype, {}), **gcfg}
        message = summary or "問候設定已更新"

    doc["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    saved = await _save_settings(cfg, doc)

    return {
        "success": saved,
        "message": message if saved else "設定儲存失敗，請稍後再試",
        "settings": configs,
    }


async def _handle_send_now(
    business_user_key: str,
    greeting_type: str | None,
    settings: dict,
) -> dict:
    """立即發送問候（委託 greeting_engine 生成 + push_engine 發送）。"""
    from skills.greeting_engine.skill import execute as greeting_skill

    if not greeting_type:
        greeting_type = "morning"

    result = await greeting_skill({
        "customer_name": settings.get("customer_name", "客戶"),
        "greeting_type": greeting_type,
        "extra_context": settings.get("extra_context", ""),
    })
    greeting_text = result.get("greeting_text", "")

    return {
        "success": True,
        "message": f"已生成 {greeting_type} 問候：\n\n{greeting_text}\n\n請確認後，可使用推播功能發送。",
        "settings": {"greeting_text": greeting_text},
    }
