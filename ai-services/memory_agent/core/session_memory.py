"""
Session memory module - progressive summary for conversations.
"""

import os
from datetime import datetime
from typing import Optional

from memory_agent.core.models import SessionMemory


SESSION_MEMORY_DIR = os.getenv("AIBOX_SESSION_MEMORY_DIR", "~/.aibox/sessions")
SESSION_MEMORY_TEMPLATE = """# Session Memory

## Session Title
{title}

## Current State
{current_state}

## Task specification
{task_spec}

## Files and Functions
{files_and_functions}

## Workflow
{workflow}

## Errors & Corrections
{errors_and_corrections}

## Codebase and System Documentation
{codebase_docs}

## Learnings
{learnings}

## Key results
{key_results}

## Worklog
{worklog}
"""


class SessionMemoryStore:
    def __init__(self):
        self._store: dict[str, SessionMemory] = {}

    def get(self, session_id: str) -> Optional[SessionMemory]:
        return self._store.get(session_id)

    def set(self, memory: SessionMemory) -> None:
        self._store[memory.session_id] = memory

    def delete(self, session_id: str) -> None:
        if session_id in self._store:
            del self._store[session_id]

    def list_all(self) -> list[SessionMemory]:
        return list(self._store.values())


_session_memory_store = SessionMemoryStore()


def get_session_memory(session_id: str) -> Optional[SessionMemory]:
    return _session_memory_store.get(session_id)


def create_session_memory(session_id: str) -> SessionMemory:
    now = datetime.now()
    memory = SessionMemory(
        session_id=session_id,
        title="",
        current_state="",
        task_spec="",
        files_and_functions=[],
        workflow="",
        errors_and_corrections=[],
        learnings=[],
        key_results=[],
        worklog=[],
        created_at=now,
        updated_at=now,
    )
    _session_memory_store.set(memory)
    return memory


def update_session_memory(
    session_id: str,
    title: Optional[str] = None,
    current_state: Optional[str] = None,
    task_spec: Optional[str] = None,
    files_and_functions: Optional[list[str]] = None,
    workflow: Optional[str] = None,
    errors_and_corrections: Optional[list[str]] = None,
    learnings: Optional[list[str]] = None,
    key_results: Optional[list[str]] = None,
    worklog: Optional[list[dict]] = None,
) -> Optional[SessionMemory]:
    memory = _session_memory_store.get(session_id)
    if not memory:
        memory = create_session_memory(session_id)
    if title is not None:
        memory.title = title
    if current_state is not None:
        memory.current_state = current_state
    if task_spec is not None:
        memory.task_spec = task_spec
    if files_and_functions is not None:
        memory.files_and_functions = files_and_functions
    if workflow is not None:
        memory.workflow = workflow
    if errors_and_corrections is not None:
        memory.errors_and_corrections = errors_and_corrections
    if learnings is not None:
        memory.learnings = learnings
    if key_results is not None:
        memory.key_results = key_results
    if worklog is not None:
        memory.worklog = worklog
    memory.updated_at = datetime.now()
    _session_memory_store.set(memory)
    return memory


def delete_session_memory(session_id: str) -> None:
    _session_memory_store.delete(session_id)


def render_session_memory(session_id: str) -> str:
    memory = _session_memory_store.get(session_id)
    if not memory:
        return ""
    return SESSION_MEMORY_TEMPLATE.format(
        title=memory.title or "_No title yet_",
        current_state=memory.current_state or "_No current state_",
        task_spec=memory.task_spec or "_No task specification_",
        files_and_functions="\n".join([f"- {f}" for f in memory.files_and_functions])
        or "_None_",
        workflow=memory.workflow or "_No workflow defined_",
        errors_and_corrections="\n".join(
            [f"- {e}" for e in memory.errors_and_corrections]
        )
        or "_None_",
        codebase_docs="_No documentation yet_",
        learnings="\n".join([f"- {item}" for item in memory.learnings]) or "_None_",
        key_results="\n".join([f"- {r}" for r in memory.key_results]) or "_None_",
        worklog="\n".join(
            [
                f"- [{w.get('timestamp', '')}] {w.get('action', '')}: {w.get('result', '')}"
                for w in memory.worklog
            ]
        )
        or "_None_",
    )
