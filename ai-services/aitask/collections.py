"""
ArangoDB collection bootstrap for LangGraph checkpointer and tool executions.

# Last Update: 2026-04-11 02:57:52
# Author: AI Agent
# Version: 1.0.0
"""

import asyncio
import logging
from typing import NamedTuple

from arango.database import StandardDatabase

logger = logging.getLogger("aitask.collections")


class IndexSpec(NamedTuple):
    fields: list[str]
    unique: bool


_COLLECTION_INDEXES: dict[str, list[IndexSpec]] = {
    "chat_checkpoints": [
        IndexSpec(fields=["thread_id"], unique=False),
        IndexSpec(fields=["thread_id", "checkpoint_id"], unique=True),
    ],
    "chat_checkpoint_writes": [
        IndexSpec(fields=["thread_id", "task_id", "idx"], unique=True),
    ],
    "tool_executions": [
        IndexSpec(fields=["session_key"], unique=False),
        IndexSpec(fields=["tool_name"], unique=False),
    ],
}


def _ensure_collections_sync(db: StandardDatabase) -> None:
    for col_name, indexes in _COLLECTION_INDEXES.items():
        if not db.has_collection(col_name):
            db.create_collection(col_name)
            logger.info("Created collection: %s", col_name)

        col = db.collection(col_name)
        for spec in indexes:
            col.add_index({
                "type": "persistent",
                "fields": spec.fields,
                "unique": spec.unique,
            })


async def ensure_collections(db: StandardDatabase) -> None:
    """Async wrapper — python-arango is sync, so we bridge via asyncio.to_thread."""
    await asyncio.to_thread(_ensure_collections_sync, db)
