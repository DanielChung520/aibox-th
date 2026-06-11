"""
Memory storage module - file-based storage with MEMORY.md index.
"""

import os
import re
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from memory_agent.core.models import (
    Memory,
    MemoryCreate,
    MemoryType,
    MemoryIndex,
    MemoryIndexEntry,
    FORBIDDEN_PATTERNS,
)


MEMORY_DIR = os.getenv("AIBOX_TH_MEMORY_DIR", "~/.aibox-th/memory")
MAX_INDEX_LINES = 200
MAX_LINE_CHARS = 150
INDEX_FILENAME = "INDEX.md"


class MemoryStorageError(Exception):
    pass


class MemoryNotFoundError(MemoryStorageError):
    pass


class MemoryTypeInvalidError(MemoryStorageError):
    pass


class ForbiddenContentError(MemoryStorageError):
    pass


class IndexSizeExceededError(MemoryStorageError):
    pass


def get_memory_dir() -> Path:
    return Path(os.path.expanduser(MEMORY_DIR))


def get_memory_dir_for_project(project_id: str) -> Path:
    safe_id = hashlib.md5(project_id.encode()).hexdigest()[:12]
    return get_memory_dir() / f"project_{safe_id}"


def ensure_memory_dir(project_id: Optional[str] = None) -> Path:
    if project_id:
        base_dir = get_memory_dir_for_project(project_id)
    else:
        base_dir = get_memory_dir()
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "user").mkdir(exist_ok=True)
    (base_dir / "feedback").mkdir(exist_ok=True)
    (base_dir / "project").mkdir(exist_ok=True)
    (base_dir / "reference").mkdir(exist_ok=True)
    return base_dir


def get_index_path(base_dir: Path) -> Path:
    return base_dir / INDEX_FILENAME


def get_memory_file_path(
    base_dir: Path, memory_id: str, memory_type: MemoryType
) -> Path:
    type_dir = base_dir / memory_type.value
    return type_dir / f"{memory_id}.md"


def generate_memory_id() -> str:
    return f"mem_{uuid.uuid4().hex[:12]}"


def should_save_content(content: str) -> bool:
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return False
    return True


def validate_memory_type(memory_type: str) -> MemoryType:
    try:
        return MemoryType(memory_type)
    except ValueError:
        raise MemoryTypeInvalidError(f"Invalid memory type: {memory_type}")


def parse_memory_file(file_path: Path) -> Optional[Memory]:
    if not file_path.exists():
        return None
    try:
        content = file_path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        frontmatter = parts[1]
        body = parts[2].strip()
        metadata = {}
        for line in frontmatter.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()
        name = metadata.get("name", "")
        description = metadata.get("description", "")
        memory_type_str = metadata.get("type", "user")
        memory_type = validate_memory_type(memory_type_str)
        memory_id = file_path.stem
        created_at_str = metadata.get("created_at", datetime.now().isoformat())
        updated_at_str = metadata.get("updated_at", datetime.now().isoformat())
        try:
            created_at = datetime.fromisoformat(created_at_str)
        except ValueError:
            created_at = datetime.now()
        try:
            updated_at = datetime.fromisoformat(updated_at_str)
        except ValueError:
            updated_at = datetime.now()
        return Memory(
            memory_id=memory_id,
            name=name,
            description=description,
            type=memory_type,
            content=body,
            created_at=created_at,
            updated_at=updated_at,
            scope=metadata.get("scope", "private"),
            created_by=metadata.get("created_by", "system"),
            file_path=str(file_path),
        )
    except Exception:
        return None


def read_index(base_dir: Path) -> MemoryIndex:
    index_path = get_index_path(base_dir)
    if not index_path.exists():
        return MemoryIndex(entries=[], total_lines=0, last_updated=datetime.now())
    try:
        lines = index_path.read_text(encoding="utf-8").split("\n")
        entries = []
        total_lines = len(lines)
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"- \[(.+?)\]\((.+?)\)\.?\s*—?\s*(.*)", line)
            if match:
                _name = match.group(1)
                filename = match.group(2)
                description = match.group(3).strip()
                type_from_name = guess_type_from_filename(filename)
                entries.append(
                    MemoryIndexEntry(
                        memory_id=filename.replace(".md", ""),
                        filename=filename,
                        description=description[:MAX_LINE_CHARS],
                        type=type_from_name,
                        line=i + 1,
                    )
                )
        return MemoryIndex(
            entries=entries,
            total_lines=total_lines,
            last_updated=datetime.now(),
        )
    except Exception:
        return MemoryIndex(entries=[], total_lines=0, last_updated=datetime.now())


def guess_type_from_filename(filename: str) -> MemoryType:
    if "feedback" in filename:
        return MemoryType.FEEDBACK
    elif "project" in filename:
        return MemoryType.PROJECT
    elif "reference" in filename:
        return MemoryType.REFERENCE
    return MemoryType.USER


def write_memory(memory: Memory) -> None:
    base_dir = ensure_memory_dir()
    file_path = get_memory_file_path(base_dir, memory.memory_id, memory.type)
    frontmatter = f"""---
name: {memory.name}
description: {memory.description}
type: {memory.type.value}
scope: {memory.scope}
created_at: {memory.created_at.isoformat()}
updated_at: {memory.updated_at.isoformat()}
created_by: {memory.created_by}
---"""
    content = frontmatter + "\n" + memory.content
    file_path.write_text(content, encoding="utf-8")


def add_to_index(memory: Memory) -> None:
    base_dir = ensure_memory_dir()
    index_path = get_index_path(base_dir)
    index = read_index(base_dir)
    if index.total_lines >= MAX_INDEX_LINES:
        raise IndexSizeExceededError(f"Index exceeds {MAX_INDEX_LINES} lines")
    entry_line = f"- [{memory.name}]({memory.memory_id}.md) — {memory.description[: MAX_LINE_CHARS - 10]}"
    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8")
        index_path.write_text(existing + "\n" + entry_line, encoding="utf-8")
    else:
        index_path.write_text(
            "# Memory Index\n\n" + entry_line + "\n", encoding="utf-8"
        )


def create_memory(memory_create: MemoryCreate) -> Memory:
    if not should_save_content(memory_create.content):
        raise ForbiddenContentError("Content matches forbidden patterns")
    memory_id = generate_memory_id()
    now = datetime.now()
    memory = Memory(
        memory_id=memory_id,
        name=memory_create.name,
        description=memory_create.description,
        type=memory_create.type,
        content=memory_create.content,
        scope=memory_create.scope,
        created_at=now,
        updated_at=now,
    )
    write_memory(memory)
    add_to_index(memory)
    return memory


def get_memory(memory_id: str) -> Memory:
    base_dir = get_memory_dir()
    for memory_type in MemoryType:
        file_path = get_memory_file_path(base_dir, memory_id, memory_type)
        memory = parse_memory_file(file_path)
        if memory:
            return memory
    raise MemoryNotFoundError(f"Memory not found: {memory_id}")


def get_all_memories(project_id: Optional[str] = None) -> list[Memory]:
    if project_id:
        base_dir = get_memory_dir_for_project(project_id)
    else:
        base_dir = get_memory_dir()
    memories = []
    for memory_type in MemoryType:
        type_dir = base_dir / memory_type.value
        if type_dir.exists():
            for file_path in type_dir.glob("*.md"):
                memory = parse_memory_file(file_path)
                if memory:
                    memories.append(memory)
    return memories


def update_memory(memory_id: str, updates: dict) -> Memory:
    old_memory = get_memory(memory_id)
    now = datetime.now()
    updated_content = updates.get("content", old_memory.content)
    if not should_save_content(updated_content):
        raise ForbiddenContentError("Updated content matches forbidden patterns")
    new_memory = Memory(
        memory_id=old_memory.memory_id,
        name=updates.get("name", old_memory.name),
        description=updates.get("description", old_memory.description),
        type=old_memory.type,
        content=updated_content,
        scope=updates.get("scope", old_memory.scope),
        created_at=old_memory.created_at,
        updated_at=now,
        created_by=old_memory.created_by,
    )
    write_memory(new_memory)
    return new_memory


def delete_memory(memory_id: str) -> None:
    memory = get_memory(memory_id)
    file_path = Path(memory.file_path) if memory.file_path else None
    if file_path and file_path.exists():
        file_path.unlink()
