"""
Unified Agents Service - Single entry point for all AI agents.

This module provides a unified FastAPI app that combines:
- data_agent (NL→SQL, Intent RAG, Ragic)
- knowledge_agent (HybridRAG, Knowledge retrieval)
- memory_agent (AI-augmented memory)
- backup_agent (ArangoDB & Qdrant backup/restore)
- mcp_tools (Calculator, Web Search, Weather, Code Executor)

Each agent is mounted under a prefix:
- /da/*     → data_agent (intent-rag, query, ragic)
- /ka/*     → knowledge_agent (future)
- /memory/* → memory_agent (future)
- /backup/* → backup_agent
- /mcp/*    → mcp_tools

# Last Update: 2026-04-14
# Author: Daniel Chung
# Version: 1.0.0
"""

__version__ = "1.0.0"
