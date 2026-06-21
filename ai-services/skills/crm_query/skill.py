"""
@file        crm_query/skill.py
@description CRM 查詢 Skill：查詢客戶詳情、聯絡人資訊
@lastUpdate  2026-06-20
@author      Sisyphus
@version     1.0.0

# Skill 規範
## 用途
查詢 crm_customers 與 crm_contacts 集合，回傳客戶基本資料與聯絡人資訊。
"""

from __future__ import annotations
import logging
import base64
from typing import Any

logger = logging.getLogger(__name__)

ARANGO_URL = "http://localhost:8529"
ARANGO_DB = "abc_desktop"
ARANGO_USER = "root"
ARANGO_PASSWORD = ""


async def _query(aql: str, bind_vars: dict | None = None) -> list[dict]:
    import httpx
    auth_cred = f"{ARANGO_USER}:{ARANGO_PASSWORD}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(auth_cred.encode()).decode()}",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": aql, "bindVars": bind_vars or {}},
                headers=headers,
            )
            if resp.status_code in (200, 201):
                return resp.json().get("result", [])
    except Exception as e:
        logger.warning(f"[CRMQuery] AQL failed: {e}")
    return []


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    query = params.get("query", "")
    customer_id = params.get("customer_id", "")

    results = []
    if customer_id:
        results = await _query(
            "FOR c IN crm_customers FILTER c._key == @key RETURN c",
            {"key": customer_id},
        )
    elif query:
        results = await _query(
            """FOR c IN crm_customers
               FILTER CONTAINS(LOWER(c.name || c.company || c.phone), @q)
               LIMIT 10
               RETURN c""",
            {"q": query.lower()},
        )

    contacts = []
    if customer_id:
        contacts = await _query(
            "FOR ct IN crm_contacts FILTER ct.customer_id == @cid RETURN ct",
            {"cid": customer_id},
        )

    return {
        "results": results,
        "contacts": contacts,
        "total": len(results),
    }
