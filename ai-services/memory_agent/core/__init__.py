"""
Memory core module exports.
"""

from memory_agent.core.models import (
    MemoryType,
    MEMORY_TYPES,
    Memory,
    MemoryCreate,
    MemoryIndex,
    WorkingMemory,
    SessionMemory,
    RecallResult,
    ConsolidationResult,
    SecretDetectionResult,
    PathValidationResult,
)
from memory_agent.core.storage import (
    create_memory,
    get_memory,
    get_all_memories,
    update_memory,
    delete_memory,
    read_index,
    should_save_content,
    validate_memory_type,
)
from memory_agent.core.security import (
    scan_content,
    scan_file,
    validate_path_safety,
    validate_symlink_safety,
    compute_checksum,
)
from memory_agent.core.recall import (
    recall_memories,
    calculate_freshness,
    needs_verification,
    generate_system_prompt,
)
from memory_agent.core.working_memory import (
    get_working_memory,
    set_working_memory,
    clear_working_memory,
)
from memory_agent.core.session_memory import (
    get_session_memory,
    create_session_memory,
    update_session_memory,
    delete_session_memory,
    render_session_memory,
)
from memory_agent.core.consolidation import (
    consolidate_memories,
    should_run_consolidation,
    count_new_memories,
)

__all__ = [
    "MemoryType",
    "MEMORY_TYPES",
    "Memory",
    "MemoryCreate",
    "MemoryIndex",
    "WorkingMemory",
    "SessionMemory",
    "RecallResult",
    "ConsolidationResult",
    "SecretDetectionResult",
    "PathValidationResult",
    "create_memory",
    "get_memory",
    "get_all_memories",
    "update_memory",
    "delete_memory",
    "read_index",
    "should_save_content",
    "validate_memory_type",
    "scan_content",
    "scan_file",
    "validate_path_safety",
    "validate_symlink_safety",
    "compute_checksum",
    "recall_memories",
    "calculate_freshness",
    "needs_verification",
    "generate_system_prompt",
    "get_working_memory",
    "set_working_memory",
    "clear_working_memory",
    "get_session_memory",
    "create_session_memory",
    "update_session_memory",
    "delete_session_memory",
    "render_session_memory",
    "consolidate_memories",
    "should_run_consolidation",
    "count_new_memories",
]
