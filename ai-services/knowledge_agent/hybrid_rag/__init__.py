"""
HybridRAG - Hybrid Retrieval-Augmented Generation for Knowledge Base.

This module provides hybrid search combining vector (Qdrant) and graph (ArangoDB)
retrieval with configurable weighting and RRF fusion.

@lastUpdate: 2026-04-05 12:00:00
@author: Daniel Chung
@version: 1.0.0
"""

from knowledge_agent.hybrid_rag.classifier import (
    QueryType,
    HybridRAGQueryClassifier,
    detect_query_type,
)
from knowledge_agent.hybrid_rag.config_service import (
    HybridRAGConfigService,
    get_config_service,
)
from knowledge_agent.hybrid_rag.fusion_engine import (
    RetrievalResult,
    FusionResult,
    HybridRAGFusionEngine,
    reciprocal_rank_fusion,
)
from knowledge_agent.hybrid_rag.service import (
    HybridRAGService,
    HybridSearchRequest,
    HybridSearchResponse,
    get_hybrid_rag_service,
)

__all__ = [
    # Classifier
    "QueryType",
    "HybridRAGQueryClassifier",
    "detect_query_type",
    # Config
    "HybridRAGConfigService",
    "get_config_service",
    # Fusion
    "RetrievalResult",
    "FusionResult",
    "HybridRAGFusionEngine",
    "reciprocal_rank_fusion",
    # Service
    "HybridRAGService",
    "HybridSearchRequest",
    "HybridSearchResponse",
    "get_hybrid_rag_service",
]
