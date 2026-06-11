"""
@file        query_preorder_items 測試
@description 技能 SKL-2618-002 單元測試：預購品項查詢
@lastUpdate  2026-04-30 02:10:00
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bpa.preorder_agent.skills.query_preorder_items import (
    execute,
    QueryPreorderItemsInput,
    ItemEntry,
    CACHE_TABLE_ID,
    FIELD_ITEM_NAME,
    FIELD_SPEC,
    FIELD_STOCK_QTY,
    FIELD_UNIT,
)


def _make_cache_doc(rows: list[dict]) -> dict:
    return {
        "_key": CACHE_TABLE_ID,
        "table_id": CACHE_TABLE_ID,
        "rows": rows,
        "cached_at": 0.0,
    }


class TestExecute:
    """execute() 整合測試"""

    @pytest.mark.asyncio
    async def test_success_all_items(self):
        """無 filter_term → 回傳全部品項"""
        rows = [
            {"品項名稱": "蒜頭", "規格": "", "即時庫存(入庫數量)": "500", "入庫單位": "公克(g)"},
            {"品項名稱": "薑", "規格": "切片", "即時庫存(入庫數量)": "300", "入庫單位": "公克(g)"},
        ]
        with patch("bpa.preorder_agent.skills.query_preorder_items.RagicCache") as MockCache:
            instance = MockCache.return_value
            instance.read_or_refresh = AsyncMock(return_value={"rows": rows})
            result = await execute({"session_id": "s1", "user_id": "u1", "filter_term": ""})
        assert result["success"] is True
        assert result["total_count"] == 2
        assert result["data"][0]["item_name"] == "蒜頭"
        assert result["data"][1]["stock_qty"] == 300

    @pytest.mark.asyncio
    async def test_filter_term(self):
        """filter_term 只回傳符合的品項"""
        rows = [
            {"品項名稱": "蒜頭", "規格": "", "即時庫存(入庫數量)": "500", "入庫單位": "公克(g)"},
            {"品項名稱": "薑", "規格": "切片", "即時庫存(入庫數量)": "300", "入庫單位": "公克(g)"},
        ]
        with patch("bpa.preorder_agent.skills.query_preorder_items.RagicCache") as MockCache:
            instance = MockCache.return_value
            instance.read_or_refresh = AsyncMock(return_value={"rows": rows})
            result = await execute({"session_id": "s1", "user_id": "u1", "filter_term": "蒜"})
        assert result["success"] is True
        assert result["total_count"] == 1
        assert result["data"][0]["item_name"] == "蒜頭"

    @pytest.mark.asyncio
    async def test_empty_cache(self):
        """快取為 None → 回傳 success: false"""
        with patch("bpa.preorder_agent.skills.query_preorder_items.RagicCache") as MockCache:
            instance = MockCache.return_value
            instance.read_or_refresh = AsyncMock(return_value=None)
            result = await execute({"session_id": "s1", "user_id": "u1"})
        assert result["success"] is False
        assert result["total_count"] == 0
        assert "error" in result

    @pytest.mark.asyncio
    async def test_stock_qty_parsing(self):
        """stock_qty 自動去除千分位逗號"""
        rows = [
            {"品項名稱": "品項A", "規格": "", "即時庫存(入庫數量)": "15,470", "入庫單位": "公克(g)"},
        ]
        with patch("bpa.preorder_agent.skills.query_preorder_items.RagicCache") as MockCache:
            instance = MockCache.return_value
            instance.read_or_refresh = AsyncMock(return_value={"rows": rows})
            result = await execute({"session_id": "s1", "user_id": "u1", "filter_term": ""})
        assert result["success"] is True
        assert result["data"][0]["stock_qty"] == 15470

    @pytest.mark.asyncio
    async def test_missing_fields_default_to_empty(self):
        """缺少欄位 → 使用預設值（空字串 / 0）"""
        rows = [
            {"品項名稱": "品項B"},
            {"品項名稱": "", "規格": "有規格"},  # 空品名會被跳過
        ]
        with patch("bpa.preorder_agent.skills.query_preorder_items.RagicCache") as MockCache:
            instance = MockCache.return_value
            instance.read_or_refresh = AsyncMock(return_value={"rows": rows})
            result = await execute({"session_id": "s1", "user_id": "u1", "filter_term": ""})
        assert result["success"] is True
        assert result["total_count"] == 1
        assert result["data"][0]["spec"] == ""
        assert result["data"][0]["stock_qty"] == 0

    @pytest.mark.asyncio
    async def test_invalid_stock_qty_defaults_to_zero(self):
        """stock_qty 非數字 → 預設為 0"""
        rows = [
            {"品項名稱": "品項C", "規格": "", "即時庫存(入庫數量)": "N/A", "入庫單位": "公克(g)"},
        ]
        with patch("bpa.preorder_agent.skills.query_preorder_items.RagicCache") as MockCache:
            instance = MockCache.return_value
            instance.read_or_refresh = AsyncMock(return_value={"rows": rows})
            result = await execute({"session_id": "s1", "user_id": "u1", "filter_term": ""})
        assert result["success"] is True
        assert result["data"][0]["stock_qty"] == 0

    @pytest.mark.asyncio
    async def test_empty_filter_no_match(self):
        """filter_term 無符合結果 → 回傳空陣列"""
        rows = [
            {"品項名稱": "蒜頭", "規格": "", "即時庫存(入庫數量)": "500", "入庫單位": "公克(g)"},
        ]
        with patch("bpa.preorder_agent.skills.query_preorder_items.RagicCache") as MockCache:
            instance = MockCache.return_value
            instance.read_or_refresh = AsyncMock(return_value={"rows": rows})
            result = await execute({"session_id": "s1", "user_id": "u1", "filter_term": "xyz"})
        assert result["success"] is True
        assert result["total_count"] == 0
        assert result["data"] == []