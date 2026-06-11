"""
ArangoDBSaver integration-style unit tests.

# Last Update: 2026-04-11 02:57:52
# Author: AI Agent
# Version: 1.0.0
"""

# pyright: reportMissingImports=false

import uuid

import pytest
from arango import ArangoClient  # type: ignore[attr-defined]
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import empty_checkpoint

from aitask.checkpointer.arango_saver import ArangoDBSaver


def _config(thread_id: str, checkpoint_id: str | None = None) -> dict[str, dict[str, str]]:
    configurable = {"thread_id": thread_id, "checkpoint_ns": "tests"}
    if checkpoint_id is not None:
        configurable["checkpoint_id"] = checkpoint_id
    return {"configurable": configurable}


@pytest.fixture
async def saver() -> ArangoDBSaver:
    instance = ArangoDBSaver(
        db_url="http://localhost:8529",
        db_name="abc_desktop",
        username="root",
        password="abc_desktop_2026",
    )
    await instance.setup()
    yield instance
    client = ArangoClient(hosts="http://localhost:8529")
    db = client.db("abc_desktop", username="root", password="abc_desktop_2026")
    prefix = "test-arango-saver-"
    for name in ("chat_checkpoint_writes", "chat_checkpoints"):
        db.aql.execute(
            f"FOR doc IN {name} FILTER STARTS_WITH(doc.thread_id, @prefix) REMOVE doc IN {name}",
            bind_vars={"prefix": prefix},
        )


@pytest.mark.asyncio
async def test_aget_tuple_nonexistent(saver: ArangoDBSaver) -> None:
    result = await saver.aget_tuple(_config(f"test-arango-saver-{uuid.uuid4()}"))
    assert result is None


@pytest.mark.asyncio
async def test_aput_and_aget_roundtrip(saver: ArangoDBSaver) -> None:
    thread_id = f"test-arango-saver-{uuid.uuid4()}"
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {"value": "ok"}
    metadata = {"source": "roundtrip"}
    saved_config = await saver.aput(_config(thread_id), checkpoint, metadata, {})
    loaded = await saver.aget_tuple(saved_config)
    assert loaded is not None
    assert loaded.checkpoint == checkpoint
    assert loaded.metadata["source"] == "roundtrip"
    assert loaded.config["configurable"]["checkpoint_id"] == checkpoint["id"]


@pytest.mark.asyncio
async def test_aput_writes(saver: ArangoDBSaver) -> None:
    thread_id = f"test-arango-saver-{uuid.uuid4()}"
    checkpoint = empty_checkpoint()
    saved_config = await saver.aput(_config(thread_id), checkpoint, {"source": "writes"}, {})
    await saver.aput_writes(saved_config, [("messages", {"text": "hello"})], task_id="task-1")
    loaded = await saver.aget_tuple(saved_config)
    assert loaded is not None
    assert loaded.pending_writes == [("task-1", "messages", {"text": "hello"})]


@pytest.mark.asyncio
async def test_alist_multiple(saver: ArangoDBSaver) -> None:
    thread_id = f"test-arango-saver-{uuid.uuid4()}"
    first = empty_checkpoint()
    second = empty_checkpoint()
    await saver.aput(_config(thread_id), first, {"order": 1}, {})
    await saver.aput(_config(thread_id, first["id"]), second, {"order": 2}, {})
    items = [item async for item in saver.alist(_config(thread_id))]
    assert [item.checkpoint["id"] for item in items] == [second["id"], first["id"]]
    assert items[0].parent_config == _config(thread_id, first["id"])


@pytest.mark.asyncio
async def test_serialization_roundtrip(saver: ArangoDBSaver) -> None:
    thread_id = f"test-arango-saver-{uuid.uuid4()}"
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {"messages": [HumanMessage(content="你好")]}
    saved_config = await saver.aput(_config(thread_id), checkpoint, {"source": "messages"}, {})
    loaded = await saver.aget_tuple(saved_config)
    assert loaded is not None
    messages = loaded.checkpoint["channel_values"]["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "你好"
