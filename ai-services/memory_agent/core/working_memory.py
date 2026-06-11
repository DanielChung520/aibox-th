"""
Working memory module - task state tracking.
"""

from typing import Optional

from memory_agent.core.models import WorkingMemory


class WorkingMemoryStore:
    def __init__(self):
        self._store: dict[str, WorkingMemory] = {}

    def get(self, task_id: str, session_id: str) -> Optional[WorkingMemory]:
        key = f"{session_id}:{task_id}"
        return self._store.get(key)

    def set(self, memory: WorkingMemory) -> None:
        key = f"{memory.session_id}:{memory.task_id}"
        self._store[key] = memory

    def delete(self, task_id: str, session_id: str) -> None:
        key = f"{session_id}:{task_id}"
        if key in self._store:
            del self._store[key]

    def clear_session(self, session_id: str) -> None:
        keys_to_delete = [
            k for k in self._store.keys() if k.startswith(f"{session_id}:")
        ]
        for key in keys_to_delete:
            del self._store[key]


_working_memory_store = WorkingMemoryStore()


def get_working_memory(task_id: str, session_id: str) -> Optional[WorkingMemory]:
    return _working_memory_store.get(task_id, session_id)


def set_working_memory(memory: WorkingMemory) -> None:
    _working_memory_store.set(memory)


def clear_working_memory(task_id: str, session_id: str) -> None:
    _working_memory_store.delete(task_id, session_id)


def clear_session_working_memory(session_id: str) -> None:
    _working_memory_store.clear_session(session_id)
