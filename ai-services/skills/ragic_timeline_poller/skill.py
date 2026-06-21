"""
@file        ragic_timeline_poller/skill.py
@description 輪巡 Ragic 表單 → 比對客戶 → 寫入 customer_timelines
              reusable skill，不受特定 agent 綁定
@lastUpdate  2026-06-14
@author      Daniel Chung
@version     1.0.0

# Skill 規範

## 用途
定時或手動輪巡 Ragic 業務表單（報價、訂單、銷貨、退貨、折讓），
提取客戶活動摘要，寫入 customer_timelines 集合。

## 輸入
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| table_configs | array | ❌ | 預設使用 6 張標準表（見下方 TABLE_CONFIGS） |
| interval_minutes | number | ❌ | 排程間隔（預設 15） |
| mode | enum | ❌ | poll_all / poll_table / manual_sync |

## 輸出
| 屬性 | 類型 | 說明 |
|------|------|------|
| synced_count | number | 本次寫入筆數 |
| table_results | array | 各表輪巡結果 |
| errors | array | 錯誤記錄 |

## 依賴
- data_agent.ragic.client.RagicAPIClient
- ArangoDB collections: customer_timelines, crm_contacts, system_params
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ─── 預設輪巡表設定 ─────────────────────────────────────────────

TABLE_CONFIGS: list[dict[str, Any]] = [
    {
        "tab_path": "order-operation",
        "sheet_index": 11,
        "event_type": "quote_analysis",
        "date_field": "訂購單日期",
        "customer_field": "客戶全稱",
        "ref_field": "訂購單編號",
        "summary_template": "報價#{訂購單編號} {客戶全稱} — {狀態}",
    },
    {
        "tab_path": "order-operation",
        "sheet_index": 4,
        "event_type": "order_placed",
        "date_field": "訂購日期",
        "customer_field": "客戶全稱",
        "ref_field": "單據號碼",
        "summary_template": "訂單#{單據號碼} {客戶全稱} — {業務人員} ${未稅合計}",
    },
    {
        "tab_path": "inventory-management",
        "sheet_index": 2,
        "event_type": "shipment_delivered",
        "date_field": "銷貨日期",
        "customer_field": "客戶全稱",
        "ref_field": "單據號碼",
        "summary_template": "銷貨#{單據號碼} {客戶全稱} — {車牌號碼}",
    },
    {
        "tab_path": "inventory-management",
        "sheet_index": 4,
        "event_type": "return_processed",
        "date_field": "退回日期",
        "customer_field": "(客戶全稱)",
        "ref_field": "單據號碼",
        "summary_template": "退貨#{單據號碼} {客戶全稱} ${未稅合計} — {備註}",
    },
    {
        "tab_path": "inventory-management",
        "sheet_index": 6,
        "event_type": "credit_note_issued",
        "date_field": "折讓日期",
        "customer_field": "(客戶全稱)",
        "ref_field": "單據號碼",
        "summary_template": "折讓#{單據號碼} {客戶全稱} — 原銷貨#{原銷貨單}",
    },
    {
        "tab_path": "order-operation",
        "sheet_index": 32,
        "event_type": "inquiry_sent",
        "date_field": "請購日期",
        "customer_field": None,
        "ref_field": "請購單號",
        "summary_template": "詢價#{請購單號} — {請購人員} ({單況})",
    },
]


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    """Skill 統一進入點。

    Args:
        params: 見上方 Skill 規範輸入表

    Returns:
        見上方 Skill 規範輸出表
    """
    mode = params.get("mode", "poll_all")
    table_configs = params.get("table_configs", TABLE_CONFIGS)
    interval_minutes = params.get("interval_minutes", 15)

    if mode == "poll_all":
        return await _poll_all(table_configs)
    elif mode == "poll_table":
        return await _poll_single_table(params.get("table_config", table_configs[0]))
    elif mode == "manual_sync":
        return await _manual_sync(params.get("customer_name", ""), table_configs)
    else:
        return {"synced_count": 0, "errors": [f"Unknown mode: {mode}"]}


async def _poll_all(table_configs: list[dict[str, Any]]) -> dict[str, Any]:
    """輪巡所有設定表單。"""
    total = 0
    results = []
    errors = []

    for cfg in table_configs:
        try:
            result = await _poll_single_table(cfg)
            results.append({
                "table": f"{cfg['tab_path']}/{cfg['sheet_index']}",
                "synced": result["synced_count"],
            })
            total += result["synced_count"]
        except Exception as e:
            errors.append({
                "table": f"{cfg['tab_path']}/{cfg['sheet_index']}",
                "error": str(e),
            })
            logger.warning("Poll table %s/%s failed: %s",
                           cfg['tab_path'], cfg['sheet_index'], e)

    return {
        "synced_count": total,
        "table_results": results,
        "errors": errors,
    }


async def _poll_single_table(cfg: dict[str, Any]) -> dict[str, Any]:
    """輪巡單一表單，比對客戶，寫入 timeline。"""
    from data_agent.ragic.client import RagicAPIClient
    from data_agent.ragic.config_loader import RagicConfigLoader
    from data_agent.ragic.models import RagicQueryParams

    # 1. 建立 Ragic client
    loader = RagicConfigLoader()
    conn = await loader.get_connection("2026carhouse")
    if not conn:
        raise ConnectionError("Ragic connection '2026carhouse' not configured")
    client = RagicAPIClient(conn)

    # 2. 查詢最近 N 天的記錄
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    params = RagicQueryParams(
        limit=500,
        order_field=cfg["date_field"],
        order_direction="DESC",
        naming="EID",
    )
    result = await client.get_records(
        tab_path=cfg["tab_path"],
        sheet_index=cfg["sheet_index"],
        params=params,
    )

    if not result.records:
        return {"synced_count": 0}

    # 3. 比對客戶 + 寫入
    synced = 0
    for record in result.records:
        success = await _process_record(record.fields, cfg)
        if success:
            synced += 1

    return {"synced_count": synced}


async def _process_record(
    fields: dict[str, Any],
    cfg: dict[str, Any],
) -> bool:
    """處理單筆 Ragic 記錄：比對客戶 → 寫入 timeline。"""

    customer_field = cfg.get("customer_field")
    ref_field = cfg.get("ref_field", "")
    event_type = cfg["event_type"]

    # 取得客戶名稱
    customer_name = ""
    if customer_field:
        customer_name = str(fields.get(customer_field, "")).strip()

    # 無客戶名稱則跳過（詢價憑單等無客戶欄位的表）
    if not customer_name and event_type == "inquiry_sent":
        return False

    ref_key = str(fields.get(ref_field, "")).strip()
    timestamp = str(fields.get(cfg["date_field"], ""))

    # 比對 crm_contacts
    customer_id = None
    if customer_name:
        customer_id = await _match_customer(customer_name)

    # 無匹配客戶則跳過
    if not customer_id:
        return False

    # 檢查 ref_key 是否已存在（去重）
    if ref_key:
        exists = await _check_duplicate(customer_id, ref_key)
        if exists:
            return False

    # 產生摘要
    summary = _build_summary(fields, cfg)

    # 寫入 timeline
    await _write_timeline(
        customer_id=customer_id,
        customer_name=customer_name,
        event_type=event_type,
        summary=summary,
        timestamp=timestamp,
        ref_key=ref_key,
    )

    return True


async def _match_customer(customer_name: str) -> str | None:
    """客戶名稱模糊比對 crm_contacts，回傳 customer_id。"""
    from data_agent.config_reader import get_db

    db = get_db()
    result = await db.aql_bind_vars(
        "FOR c IN crm_contacts FILTER CONTAINS(c.name, @name) LIMIT 1 RETURN c._key",
        [("name", customer_name)],
    )
    return result[0] if result else None


async def _check_duplicate(customer_id: str, ref_key: str) -> bool:
    """檢查 customer_timelines 是否已有此 ref_key。"""
    from data_agent.config_reader import get_db

    db = get_db()
    result = await db.aql_bind_vars(
        """FOR t IN customer_timelines
           FILTER t.customer_id == @cid
           FOR e IN t.events
           FILTER e.ref_key == @rk
           LIMIT 1 RETURN 1""",
        [("cid", customer_id), ("rk", ref_key)],
    )
    return len(result) > 0


def _build_summary(fields: dict[str, Any], cfg: dict[str, Any]) -> str:
    """根據 template 產生摘要字串。"""
    template = cfg["summary_template"]
    try:
        return template.format(**fields)
    except KeyError:
        # 有欄位缺漏時 fallback
        event_type = cfg["event_type"]
        ref_val = str(fields.get(cfg.get("ref_field", ""), "?"))
        cust_val = str(fields.get(cfg.get("customer_field", ""), ""))
        return f"[{event_type}] {ref_val} {cust_val}"


async def _write_timeline(
    customer_id: str,
    customer_name: str,
    event_type: str,
    summary: str,
    timestamp: str,
    ref_key: str,
) -> None:
    """寫入 customer_timelines events 陣列。"""
    from data_agent.config_reader import get_db
    from datetime import datetime

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    event = {
        "event_id": f"{event_type}_{ref_key}" if ref_key else f"{event_type}_{now}",
        "event_type": event_type,
        "summary": summary,
        "timestamp": timestamp or now,
        "source": "erp",
        "detail_level": "full",
        "ref_key": ref_key or "",
        "metadata": {},
    }

    # UPSERT: 若 customer_timelines 已存在則 append，否則 create
    await db.aql_bind_vars(
        """FOR t IN customer_timelines
           FILTER t.customer_id == @cid
           UPDATE t WITH { events: APPEND(t.events, [@event]), last_updated: @now } IN customer_timelines""",
        [
            ("cid", customer_id),
            ("event", json.dumps(event)),
            ("now", now),
        ],
    )

    # 若無該客戶的 timeline document，建立新的
    await db.aql_bind_vars(
        """LET exists = LENGTH(FOR t IN customer_timelines FILTER t.customer_id == @cid LIMIT 1 RETURN 1)
           FILTER exists == 0
           INSERT { _key: CONCAT("tl_", @cid), customer_id: @cid, customer_name: @name, events: [@event], last_updated: @now } INTO customer_timelines""",
        [
            ("cid", customer_id),
            ("name", customer_name),
            ("event", json.dumps(event)),
            ("now", now),
        ],
    )


async def _manual_sync(
    customer_name: str,
    table_configs: list[dict[str, Any]],
) -> dict[str, Any]:
    """手動同步單一客戶的所有活動。"""
    if not customer_name:
        return {"synced_count": 0, "errors": ["customer_name required"]}
    return await _poll_all(table_configs)
