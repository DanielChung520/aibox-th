"""
Memory core module - types, models, and interfaces.
"""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"


MEMORY_TYPES = tuple(m.value for m in MemoryType)


MEMORY_TYPE_DESCRIPTIONS = {
    MemoryType.USER: "用戶畫像、角色、目標、知識背景",
    MemoryType.FEEDBACK: "工作方式指導（糾正和確認）",
    MemoryType.PROJECT: "項目進展、目標、截止日期",
    MemoryType.REFERENCE: "外部系統指針",
}


MEMORY_TYPE_SCOPES = {
    MemoryType.USER: "always private",
    MemoryType.FEEDBACK: "default private",
    MemoryType.PROJECT: "strongly bias toward team",
    MemoryType.REFERENCE: "usually team",
}


FORBIDDEN_PATTERNS = [
    r"代碼模式[:\s]",
    r"架構[:\s]",
    r"文件路徑[:\s]",
    r"Git 歷史[:\s]",
    r"git log",
    r"git blame",
    r"調試方案[:\s]",
    r"調試步驟[:\s]",
    r"CLAUDE\.md 中已有",
    r"臨時任務",
    r"當前對話上下文",
]


class MemoryBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: str = Field(..., max_length=150)
    type: MemoryType
    content: str = Field(..., min_length=1)


class MemoryCreate(MemoryBase):
    scope: str = "private"
    project_id: Optional[str] = None


class Memory(MemoryBase):
    memory_id: str
    scope: str = "private"
    created_at: datetime
    updated_at: datetime
    created_by: str = "system"
    project_id: Optional[str] = None
    file_path: Optional[str] = None


class MemoryIndexEntry(BaseModel):
    memory_id: str
    filename: str
    description: str
    type: MemoryType
    line: int


class MemoryIndex(BaseModel):
    entries: list[MemoryIndexEntry]
    total_lines: int
    last_updated: datetime


class WorkingMemory(BaseModel):
    task_id: str
    session_id: str
    task_progress: str
    offsets: dict[str, int] = Field(default_factory=dict)
    machine_states: dict[str, dict] = Field(default_factory=dict)
    last_updated: datetime


class SessionMemory(BaseModel):
    session_id: str
    title: str = ""
    current_state: str = ""
    task_spec: str = ""
    files_and_functions: list[str] = Field(default_factory=list)
    workflow: str = ""
    errors_and_corrections: list[str] = Field(default_factory=list)
    learnings: list[str] = Field(default_factory=list)
    key_results: list[str] = Field(default_factory=list)
    worklog: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    token_count: int = 0


class RecallResult(BaseModel):
    memory: Memory
    relevance_score: float
    freshness: str
    needs_verification: bool = False


class ConsolidationStats(BaseModel):
    memories_scanned: int = 0
    memories_merged: int = 0
    memories_pruned: int = 0
    duration_ms: int = 0


class ConsolidationResult(BaseModel):
    success: bool
    stats: ConsolidationStats
    errors: list[str] = Field(default_factory=list)


class SecretDetectionResult(BaseModel):
    has_secrets: bool
    detected_patterns: list[str] = Field(default_factory=list)
    blocked_content: Optional[str] = None


class PathValidationResult(BaseModel):
    is_valid: bool
    sanitized_path: Optional[str] = None
    error: Optional[str] = None
