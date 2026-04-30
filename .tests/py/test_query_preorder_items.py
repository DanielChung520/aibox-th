"""
@file        test_query_preorder_items.py
@description 單元測試：預購品項查詢技能 SKL-2618-002
@lastUpdate  2026-04-30 01:50:00
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import pytest

from bpa.preorder_agent.skills.query_preorder_items import (
    QueryPreorderItemsInput,
    QueryPreorderItemsOutput,
    execute,
)


class TestQueryPreorderItemsInput:
    def test_valid_input(self):
        inp = QueryPreorderItemsInput(session_id="s001", user_id="u001", filter_term="")
        assert inp.session_id == "s001"
        assert inp.user_id == "u001"
        assert inp.filter_term == ""

    def test_filter_term_optional(self):
        inp = QueryPreorderItemsInput(session_id="s001", user_id="u001")
        assert inp.filter_term == ""

    def test_filter_term_provided(self):
        inp = QueryPreorderItemsInput(session_id="s001", user_id="u001", filter_term="牛肉")
        assert inp.filter_term == "牛肉"


class TestQueryPreorderItemsOutput:
    def test_success_response(self):
        out = QueryPreorderItemsOutput(
            success=True,
            data=[],
            total_count=0,
        )
        assert out.success is True
        assert out.total_count == 0


class TestExecute:
    @pytest.mark.asyncio
    async def test_execute_returns_structure(self):
        result = await execute({"session_id": "test", "user_id": "u001", "filter_term": ""})
        assert "success" in result
        assert "data" in result
        assert "total_count" in result
        assert result["success"] is True
        assert isinstance(result["data"], list)

    @pytest.mark.asyncio
    async def test_filter_reduces_results(self):
        result_all = await execute({"session_id": "test", "user_id": "u001", "filter_term": ""})
        result_filtered = await execute({"session_id": "test", "user_id": "u001", "filter_term": "xyz_nonexistent_item_123"})
        assert result_filtered["total_count"] <= result_all["total_count"]
