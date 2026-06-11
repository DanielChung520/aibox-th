"""
@file        預購品項查詢技能
@description 查詢 Ragic STOCK_16 預購品項，支援快取讀寫與結構化輸出
              技能編號：SKL-2618-002
@lastUpdate  2026-04-30 01:50:00
@author      Daniel Chung
@version     1.0.0

# Skill 規範

## 用途
查詢預購可用之品項（品名、規格、庫存數量、單位），用於前置詢價或建立預購單。

## 輸入
| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| session_id | string | ✅ | 對話 session 識別碼 |
| user_id | string | ✅ | 使用者識別碼 |
| filter_term | string | ❌ | 篩選關鍵字（品名含該字才回傳） |

## 輸出
| 欄位 | 類型 | 說明 |
|------|------|------|
| success | boolean | 是否成功 |
| data | array | 品項清單陣列 |
| total_count | int | 總品項數 |

## data 陣列每項結構
| 欄位 | 類型 | 說明 |
|------|------|------|
| item_name | string | 品項名稱 |
| spec | string | 規格 |
| stock_qty | int | 庫存數量 |
| unit | string | 單位 |

## 路由
- Skills Framework: `ToolRegistry.execute("query_preorder_items", params)`
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from shared.ragic_cache import RagicCache

logger = logging.getLogger(__name__)

# STOCK_16 必備欄位（品名、規格、庫存數量、單位）
FIELD_ITEM_NAME = "品項名稱"
FIELD_SPEC = "規格"
FIELD_STOCK_QTY = "即時庫存(入庫數量)"
FIELD_UNIT = "入庫單位"
CACHE_TABLE_ID = "STOCK_16"


class QueryPreorderItemsInput(BaseModel):
    session_id: str
    user_id: str
    filter_term: str = ""


class ItemEntry(BaseModel):
    item_name: str
    spec: str
    stock_qty: int
    unit: str


class QueryPreorderItemsOutput(BaseModel):
    success: bool
    data: list[ItemEntry]
    total_count: int


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    try:
        input_data = QueryPreorderItemsInput(
            session_id=params.get("session_id", ""),
            user_id=params.get("user_id", ""),
            filter_term=params.get("filter_term", ""),
        )
    except Exception as e:
        return {"success": False, "data": [], "total_count": 0, "error": str(e)}

    cache = RagicCache()
    cached = await cache.read_or_refresh(CACHE_TABLE_ID)
    if cached is None:
        return {"success": False, "data": [], "total_count": 0, "error": "無法取得品項資料"}

    items: list[ItemEntry] = []
    for row in cached.get("rows", []):
        if not isinstance(row, dict):
            continue
        item_name = str(row.get(FIELD_ITEM_NAME, "")).strip()
        if not item_name:
            continue
        if input_data.filter_term and input_data.filter_term.lower() not in item_name.lower():
            continue

        try:
            stock_qty = int(str(row.get(FIELD_STOCK_QTY, 0)).replace(",", "").strip())
        except (ValueError, TypeError):
            stock_qty = 0

        items.append(ItemEntry(
            item_name=item_name,
            spec=str(row.get(FIELD_SPEC, "")).strip(),
            stock_qty=stock_qty,
            unit=str(row.get(FIELD_UNIT, "")).strip(),
        ))

    return {
        "success": True,
        "data": [i.model_dump() for i in items],
        "total_count": len(items),
    }
