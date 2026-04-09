from pydantic import BaseModel
from typing import Optional


class ProcessAdvisorConfig(BaseModel):
    name: str = "process-advisor"
    display_name: str = "流程顧問"
    description: str = "深度流程顧問，專精於複雜系統架構決策與流程優化"
    icon: str = "RobotOutlined"
    group_key: str = "advisor"
    tool_type: str = "oracle"

    llm_model: str = "gemma4:31b"
    temperature: float = 0.7
    max_tokens: int = 32000
    timeout_ms: int = 60000

    visibility: str = "role"
    visibility_roles: list[str] = ["admin", "architect"]
