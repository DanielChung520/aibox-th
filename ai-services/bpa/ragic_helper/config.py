import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

INTENT_RAG_URL = os.getenv("INTENT_RAG_URL", "http://localhost:8011/da/intent-rag")
HYBRID_RAG_URL = os.getenv("HYBRID_RAG_URL", "http://localhost:8011/ka/hybrid")
MEMORY_SESSION_URL = os.getenv("MEMORY_SESSION_URL", "http://localhost:8011/memory/session")


async def get_agent_config(agent_key: str) -> dict | None:
    from arango_helpers import get_doc

    return await get_doc("agents", agent_key)


async def get_agent_llm_config(agent_key: str) -> dict:
    agent = await get_agent_config(agent_key)
    if not agent:
        return {
            "model": DEFAULT_MODEL,
            "temperature": 0.7,
            "max_tokens": 2000,
            "system_prompt": "你是 Ragic 系統的 AI 助理，專門回答關於 Ragic 操作的問題。",
        }

    return {
        "model": agent.get("llm_model") or DEFAULT_MODEL,
        "temperature": agent.get("temperature", 0.7),
        "max_tokens": agent.get("max_tokens", 2000),
        "system_prompt": agent.get("system_prompt") or "你是 Ragic 系統的 AI 助理，專門回答關於 Ragic 操作的問題。",
        "knowledge_bases": agent.get("knowledge_bases", []),
        "data_sources": agent.get("data_sources", []),
        "tools": agent.get("tools", []),
    }


async def get_conversation_history(session_id: str, limit: int = 10) -> list[dict]:
    from shared.conversation import QueryEngine

    engine = QueryEngine()
    return await engine.get_history(session_id, limit=limit)


async def save_message(session_id: str, role: str, message: str, platform: str = "line") -> None:
    from shared.conversation import ConversationStorage

    storage = ConversationStorage()
    await storage.save_message(
        session_id=session_id,
        platform=platform,
        role=role,
        message=message,
    )
