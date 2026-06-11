from fastapi import APIRouter
from typing import Optional

router = APIRouter(prefix="/memory", tags=["Memory Index"])

from memory_agent.core import read_index, generate_system_prompt
from memory_agent.core.storage import ensure_memory_dir

MEMORY_DIR = "~/.aibox-th/memory"


@router.get("/index")
def get_memory_index(project_id: Optional[str] = None) -> dict:
    if project_id:
        base_dir = ensure_memory_dir(project_id)
    else:
        base_dir = ensure_memory_dir()
    index = read_index(base_dir)
    return {
        "total_lines": index.total_lines,
        "last_updated": index.last_updated.isoformat(),
        "entries": [
            {
                "memory_id": e.memory_id,
                "filename": e.filename,
                "description": e.description,
                "type": e.type.value,
                "line": e.line,
            }
            for e in index.entries
        ],
    }


@router.get("/system-prompt")
async def get_system_prompt() -> dict:
    prompt = await generate_system_prompt(MEMORY_DIR)
    return {"prompt": prompt}
