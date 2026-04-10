"""
ArangoDB-backed LangGraph checkpoint saver.

# Last Update: 2026-04-11 02:57:52
# Author: AI Agent
# Version: 1.0.0
"""

# pyright: reportMissingImports=false

import asyncio
import base64
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import AsyncIterator, Protocol, Sequence, TypeAlias, cast, runtime_checkable

from arango import ArangoClient  # type: ignore[attr-defined]
from arango.database import StandardDatabase
from arango.typings import DataTypes
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    PendingWrite,
    get_checkpoint_metadata,
)

from aitask.collections import ensure_collections

JsonValue: TypeAlias = DataTypes


@runtime_checkable
class _ByteSerde(Protocol):
    def dumps(self, obj: object) -> bytes: ...
    def loads(self, data: bytes) -> object: ...


class ArangoDBSaver(BaseCheckpointSaver[str]):
    def __init__(self, db_url: str, db_name: str, username: str, password: str) -> None:
        super().__init__()
        client = ArangoClient(hosts=db_url)
        self._db: StandardDatabase = client.db(db_name, username=username, password=password)

    async def setup(self) -> None:
        await ensure_collections(self._db)

    def _parts(self, config: RunnableConfig) -> tuple[str, str, str | None]:
        data = config["configurable"]
        return str(data["thread_id"]), str(data.get("checkpoint_ns", "")), cast(str | None, data.get("checkpoint_id"))

    def _config(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> RunnableConfig:
        return {"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": checkpoint_id}}

    def _checkpoint_key(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        return f"{thread_id}_{checkpoint_ns}_{checkpoint_id}"

    def _write_key(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str, task_id: str, idx: int) -> str:
        return f"{thread_id}_{checkpoint_ns}_{checkpoint_id}_{task_id}_{idx}"

    def _encode(self, value: object) -> tuple[str, str]:
        if isinstance(self.serde, _ByteSerde):
            return "bytes", base64.b64encode(self.serde.dumps(value)).decode("utf-8")
        value_type, payload = self.serde.dumps_typed(value)
        return value_type, base64.b64encode(payload).decode("utf-8")

    def _decode(self, value_type: str, payload: str) -> object:
        raw = base64.b64decode(payload.encode("utf-8"))
        if value_type == "bytes" and isinstance(self.serde, _ByteSerde):
            return self.serde.loads(raw)
        return self.serde.loads_typed((value_type, raw))

    async def _fetch_all(self, query: str, bind_vars: dict[str, JsonValue]) -> list[dict[str, object]]:
        def run() -> list[dict[str, object]]:
            cursor = cast(Iterable[object], self._db.aql.execute(query, bind_vars=bind_vars))
            return [cast(dict[str, object], doc) for doc in cursor]

        return await asyncio.to_thread(run)

    async def _fetch_one(self, query: str, bind_vars: dict[str, JsonValue]) -> dict[str, object] | None:
        docs = await self._fetch_all(query, bind_vars)
        return docs[0] if docs else None

    async def _upsert_many(self, collection: str, docs: Sequence[dict[str, JsonValue]]) -> None:
        def run() -> None:
            for doc in docs:
                self._db.aql.execute(
                    f"UPSERT {{ _key: @doc._key }} INSERT @doc UPDATE @doc IN {collection}",
                    bind_vars={"doc": doc},
                )

        await asyncio.to_thread(run)

    async def _pending_writes(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> list[PendingWrite]:
        docs = await self._fetch_all(
            "FOR doc IN chat_checkpoint_writes FILTER doc.thread_id == @thread_id FILTER doc.checkpoint_ns == @checkpoint_ns FILTER doc.checkpoint_id == @checkpoint_id SORT doc.idx ASC RETURN doc",
            {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": checkpoint_id},
        )
        return [
            (
                cast(str, doc["task_id"]),
                cast(str, doc["channel"]),
                self._decode(cast(str, doc["value_type"]), cast(str, doc["value_payload"])),
            )
            for doc in docs
        ]

    async def _tuple(self, doc: dict[str, object]) -> CheckpointTuple:
        thread_id = cast(str, doc["thread_id"])
        checkpoint_ns = cast(str, doc["checkpoint_ns"])
        checkpoint_id = cast(str, doc["checkpoint_id"])
        parent_id = cast(str | None, doc.get("parent_checkpoint_id"))
        return CheckpointTuple(
            config=self._config(thread_id, checkpoint_ns, checkpoint_id),
            checkpoint=cast(Checkpoint, self._decode(cast(str, doc["checkpoint_type"]), cast(str, doc["checkpoint_payload"]))),
            metadata=cast(CheckpointMetadata, self._decode(cast(str, doc["metadata_type"]), cast(str, doc["metadata_payload"]))),
            parent_config=self._config(thread_id, checkpoint_ns, parent_id) if parent_id else None,
            pending_writes=await self._pending_writes(thread_id, checkpoint_ns, checkpoint_id),
        )

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id, checkpoint_ns, checkpoint_id = self._parts(config)
        if checkpoint_id:
            doc = await self._fetch_one(
                "FOR doc IN chat_checkpoints FILTER doc.thread_id == @thread_id FILTER doc.checkpoint_ns == @checkpoint_ns FILTER doc.checkpoint_id == @checkpoint_id LIMIT 1 RETURN doc",
                {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": checkpoint_id},
            )
        else:
            doc = await self._fetch_one(
                "FOR doc IN chat_checkpoints FILTER doc.thread_id == @thread_id FILTER doc.checkpoint_ns == @checkpoint_ns SORT doc.created_at DESC LIMIT 1 RETURN doc",
                {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns},
            )
        return None if doc is None else await self._tuple(doc)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, object] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        bind_vars: dict[str, JsonValue] = {}
        filters: list[str] = []
        if config:
            thread_id, checkpoint_ns, checkpoint_id = self._parts(config)
            bind_vars.update({"thread_id": thread_id, "checkpoint_ns": checkpoint_ns})
            filters.extend(["doc.thread_id == @thread_id", "doc.checkpoint_ns == @checkpoint_ns"])
            if checkpoint_id:
                bind_vars["checkpoint_id"] = checkpoint_id
                filters.append("doc.checkpoint_id == @checkpoint_id")
        if before and (before_tuple := await self.aget_tuple(before)) is not None:
            bind_vars["before_created_at"] = before_tuple.checkpoint["ts"]
            filters.append("doc.created_at < @before_created_at")
        where_clause = " ".join(f"FILTER {item}" for item in filters)
        docs = await self._fetch_all(
            f"FOR doc IN chat_checkpoints {where_clause} SORT doc.created_at DESC RETURN doc",
            bind_vars,
        )
        yielded = 0
        for doc in docs:
            item = await self._tuple(doc)
            metadata_filter = cast(CheckpointMetadata | None, filter)
            if metadata_filter and any(item.metadata.get(key) != value for key, value in metadata_filter.items()):
                continue
            yield item
            yielded += 1
            if limit is not None and yielded >= limit:
                return

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        del new_versions
        thread_id, checkpoint_ns, parent_id = self._parts(config)
        checkpoint_id = checkpoint["id"]
        checkpoint_type, checkpoint_payload = self._encode(checkpoint)
        metadata_type, metadata_payload = self._encode(get_checkpoint_metadata(config, metadata))
        await self._upsert_many(
            "chat_checkpoints",
            [{
                "_key": self._checkpoint_key(thread_id, checkpoint_ns, checkpoint_id),
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "parent_checkpoint_id": parent_id,
                "created_at": checkpoint.get("ts", datetime.now(UTC).isoformat()),
                "checkpoint_type": checkpoint_type,
                "checkpoint_payload": checkpoint_payload,
                "metadata_type": metadata_type,
                "metadata_payload": metadata_payload,
            }],
        )
        return self._config(thread_id, checkpoint_ns, checkpoint_id)

    async def aput_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, object]], task_id: str, task_path: str = "") -> None:
        thread_id, checkpoint_ns, checkpoint_id = self._parts(config)
        if checkpoint_id is None:
            return
        docs: list[dict[str, JsonValue]] = []
        for idx, (channel, value) in enumerate(writes):
            write_idx = WRITES_IDX_MAP.get(channel, idx)
            value_type, value_payload = self._encode(value)
            docs.append(
                {
                    "_key": self._write_key(thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx),
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                    "task_id": task_id,
                    "task_path": task_path,
                    "idx": cast(JsonValue, write_idx),
                    "channel": channel,
                    "value_type": value_type,
                    "value_payload": value_payload,
                }
            )
        await self._upsert_many("chat_checkpoint_writes", docs)
