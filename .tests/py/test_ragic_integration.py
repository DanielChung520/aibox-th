"""
@file        test_ragic_integration.py
@description Integration tests for Ragic Phase 9-11: import pipeline + multi-step.
             Requires running Qdrant (localhost:6333) and ArangoDB (localhost:8529).
@lastUpdate  2026-04-11 18:18:34
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import pytest

from data_agent.ragic.arango_writer import RagicArangoWriter
from data_agent.ragic.graph_query import RagicGraphQuery
from data_agent.ragic.import_orchestrator import RagicImportOrchestrator
from data_agent.ragic.intent_store import RagicIntentStore
from data_agent.ragic.models_phase9 import (
    GraphQueryResult,
    MultiStepQuery,
)
from data_agent.ragic.multi_step_orchestrator import MultiStepOrchestrator
from data_agent.ragic.result_merger import ResultMerger
from data_agent.ragic.schema_store import RagicSchemaStore

_TEST_ACCOUNT = "__test_integration__"

_SMALL_MD = """## 頁籤： 測試頁籤

### 表單: 客戶資料
- 表單網址: https://ap15.ragic.com/__test__/database/1
- API 網址: https://ap15.ragic.com/__test__/database/1?api
- 主表單Key: 1000001

| Field Name | Field ID | Type | Writable | Write Format | Memo |
|---|---|---|---|---|---|
| 客戶名稱 | 1001 | 文字 | 可寫入 | 任意文字 | |
| 聯絡電話 | 1002 | 文字 | 可寫入 | 任意文字 | |
| 地址 | 1003 | 文字 | 可寫入 | 任意文字 | |

### 表單: 訂單
- 表單網址: https://ap15.ragic.com/__test__/database/2
- API 網址: https://ap15.ragic.com/__test__/database/2?api
- 主表單Key: 1000002

| Field Name | Field ID | Type | Writable | Write Format | Memo |
|---|---|---|---|---|---|
| 訂單編號 | 2001 | 文字 | 可寫入 | 任意文字 | |
| 客戶 | 2002 | 連結欄位 | 可寫入 | 目標資料的顯示值 | 連結到客戶資料表單上的客戶名稱 |
| 金額 | 2003 | 數字 | 可寫入 | 整數 | |

### 表單: 出貨單
- 表單網址: https://ap15.ragic.com/__test__/database/3
- API 網址: https://ap15.ragic.com/__test__/database/3?api
- 主表單Key: 1000003

| Field Name | Field ID | Type | Writable | Write Format | Memo |
|---|---|---|---|---|---|
| 出貨編號 | 3001 | 文字 | 可寫入 | 任意文字 | |
| 訂單 | 3002 | 連結欄位 | 可寫入 | 目標資料的顯示值 | 連結到訂單表單上的訂單編號 |
| 出貨日期 | 3003 | 日期 | 可寫入 | | |
"""


@pytest.fixture
def schema_store() -> RagicSchemaStore:
    return RagicSchemaStore()


@pytest.fixture
def intent_store() -> RagicIntentStore:
    return RagicIntentStore()


@pytest.fixture
def arango_writer() -> RagicArangoWriter:
    return RagicArangoWriter()


@pytest.fixture
def orchestrator(schema_store: RagicSchemaStore) -> RagicImportOrchestrator:
    return RagicImportOrchestrator(
        schema_store=schema_store,
        intent_store=RagicIntentStore(),
        arango_writer=RagicArangoWriter(),
    )


@pytest.fixture
def graph_query() -> RagicGraphQuery:
    return RagicGraphQuery()


async def _cleanup_test_data(
    arango_writer: RagicArangoWriter,
    schema_store: RagicSchemaStore,
) -> None:
    await arango_writer.clear_collections(_TEST_ACCOUNT)
    try:
        await schema_store.delete_by_account(_TEST_ACCOUNT)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_import_small_md(
    orchestrator: RagicImportOrchestrator,
    arango_writer: RagicArangoWriter,
    schema_store: RagicSchemaStore,
) -> None:
    await _cleanup_test_data(arango_writer, schema_store)
    try:
        result = await orchestrator.run_import(_SMALL_MD, _TEST_ACCOUNT)
        assert result.tables_parsed == 3
        assert result.arango_tables_written >= 3
        assert result.arango_fields_written >= 7
        assert result.intents_generated >= 3
        assert result.duration_ms > 0
        assert len(result.errors) == 0
    finally:
        await _cleanup_test_data(arango_writer, schema_store)


@pytest.mark.asyncio
async def test_import_idempotent(
    orchestrator: RagicImportOrchestrator,
    arango_writer: RagicArangoWriter,
    schema_store: RagicSchemaStore,
) -> None:
    await _cleanup_test_data(arango_writer, schema_store)
    try:
        r1 = await orchestrator.run_import(_SMALL_MD, _TEST_ACCOUNT)
        r2 = await orchestrator.run_import(_SMALL_MD, _TEST_ACCOUNT)
        assert r1.tables_parsed == r2.tables_parsed
        assert r2.arango_tables_written >= 3
    finally:
        await _cleanup_test_data(arango_writer, schema_store)


@pytest.mark.asyncio
async def test_import_with_relations(
    orchestrator: RagicImportOrchestrator,
    arango_writer: RagicArangoWriter,
    schema_store: RagicSchemaStore,
    graph_query: RagicGraphQuery,
) -> None:
    await _cleanup_test_data(arango_writer, schema_store)
    try:
        result = await orchestrator.run_import(_SMALL_MD, _TEST_ACCOUNT)
        assert result.relations_extracted >= 2
        assert result.arango_relations_written >= 2

        gq_result = await graph_query.get_related_tables(
            "訂單", _TEST_ACCOUNT
        )
        assert isinstance(gq_result, GraphQueryResult)
        assert len(gq_result.relations) >= 1
    finally:
        await _cleanup_test_data(arango_writer, schema_store)


@pytest.mark.asyncio
async def test_multi_step_timeout() -> None:
    from unittest.mock import AsyncMock, MagicMock

    mock_graph = MagicMock()
    mock_executor = MagicMock()
    mock_merger = MagicMock()
    mock_executor.execute = AsyncMock(
        side_effect=TimeoutError("Timeout")
    )
    mock_graph.get_related_tables = AsyncMock(
        return_value=GraphQueryResult(table="x", relations=[])
    )

    orch = MultiStepOrchestrator(
        graph_query=mock_graph,
        step_executor=mock_executor,
        result_merger=mock_merger,
    )
    query = MultiStepQuery(
        query="timeout test", account="test", total_timeout_s=0.001
    )
    result = await orch.execute(query)
    assert result.partial_failure is True
    assert len(result.errors) > 0


@pytest.mark.asyncio
async def test_multi_step_single_table() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from data_agent.ragic.models_phase9 import StepResult

    mock_graph = MagicMock()
    mock_executor = MagicMock()
    mock_merger = ResultMerger()
    mock_graph.get_related_tables = AsyncMock(
        return_value=GraphQueryResult(table="A", relations=[])
    )
    mock_executor.execute = AsyncMock(
        return_value=StepResult(
            step_index=0, table_name="A", record_count=5
        )
    )
    orch = MultiStepOrchestrator(
        graph_query=mock_graph,
        step_executor=mock_executor,
        result_merger=mock_merger,
    )
    query = MultiStepQuery(query="列出A", account="test")
    result = await orch.execute(query)
    assert result.total_steps == 1
    assert result.partial_failure is False


@pytest.mark.slow
@pytest.mark.asyncio
async def test_import_real_document(
    orchestrator: RagicImportOrchestrator,
    arango_writer: RagicArangoWriter,
    schema_store: RagicSchemaStore,
) -> None:
    import os
    md_path = os.path.join(
        os.path.dirname(__file__),
        "../../.docs/Spec/效能工具代理/2025shianyong.md",
    )
    if not os.path.exists(md_path):
        pytest.skip("Real schema file not found")

    real_account = "__test_real_import__"
    try:
        with open(md_path, encoding="utf-8") as f:
            content = f.read()
        result = await orchestrator.run_import(content, real_account)
        assert result.tables_parsed >= 250
        assert result.relations_extracted >= 2000
    finally:
        await arango_writer.clear_collections(real_account)
        try:
            await schema_store.delete_by_account(real_account)
        except Exception:
            pass
