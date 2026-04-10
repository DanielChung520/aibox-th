"""
AITask Service Configuration — centralised env var reads.

# Last Update: 2026-04-11 02:57:52
# Author: AI Agent
# Version: 1.0.0
"""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderConfig:

    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    openai_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )
    anthropic_base_url: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    )
    gemini_base_url: str = field(
        default_factory=lambda: os.getenv(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
        )
    )
    minimax_base_url: str = field(
        default_factory=lambda: os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
    )

    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    minimax_api_key: str = field(default_factory=lambda: os.getenv("MINIMAX_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))


@dataclass(frozen=True)
class ArangoConfig:

    url: str = field(default_factory=lambda: os.getenv("ARANGO_URL", "http://localhost:8529"))
    db_name: str = field(default_factory=lambda: os.getenv("ARANGO_DB", "abc_desktop"))
    username: str = field(default_factory=lambda: os.getenv("ARANGO_USER", "root"))
    password: str = field(
        default_factory=lambda: os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")
    )


@dataclass(frozen=True)
class ServiceConfig:

    data_agent_url: str = field(
        default_factory=lambda: os.getenv("DATA_AGENT_URL", "http://localhost:8003")
    )
    knowledge_agent_url: str = field(
        default_factory=lambda: os.getenv("KNOWLEDGE_AGENT_URL", "http://localhost:8007")
    )
    mcp_tools_url: str = field(
        default_factory=lambda: os.getenv("MCP_TOOLS_URL", "http://localhost:8004")
    )
    bpa_mm_agent_url: str = field(
        default_factory=lambda: os.getenv("BPA_MM_AGENT_URL", "http://localhost:8005")
    )
    qdrant_url: str = field(
        default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333")
    )


@dataclass(frozen=True)
class AITaskSettings:

    provider: ProviderConfig = field(default_factory=ProviderConfig)
    arango: ArangoConfig = field(default_factory=ArangoConfig)
    services: ServiceConfig = field(default_factory=ServiceConfig)
    default_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.2:latest")
    )
    tagging_model: str = field(
        default_factory=lambda: os.getenv("TAGGING_MODEL", "qwen3-coder:30b")
    )
    orchestrator_mode_default: str = "legacy"


settings = AITaskSettings()
