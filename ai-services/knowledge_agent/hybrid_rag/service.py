"""
HybridRAG Service - Main service integrating all HybridRAG components.

Orchestrates query classification, weight configuration, vector search,
graph search, and result fusion into a unified hybrid retrieval API.

@lastUpdate: 2026-04-05 12:00:00
@author: Daniel Chung
@version: 1.0.0
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import TypedDict

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3:latest")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class HybridSearchRequest(TypedDict, total=False):
    """Request model for hybrid search."""

    query: str
    collection: str
    top_k: int
    strategy: str  # "hybrid" | "vector_first" | "graph_first"
    min_relevance: float
    tenant_id: str | None
    user_id: str | None
    root_id: str | None


class HybridSearchMetadata(TypedDict, total=False):
    """Metadata in search result."""

    file_id: str
    chunk_index: int | None
    entity_type: str | None
    relation: str | None
    root_id: str | None


class HybridSearchResult(TypedDict):
    """Single search result."""

    content: str
    source: str
    score: float
    metadata: HybridSearchMetadata


class HybridSearchResponse(TypedDict):
    """Response model for hybrid search."""

    query: str
    query_type: str
    strategy: str
    weights_used: dict[str, float]
    results: list[HybridSearchResult]
    total_vector_hits: int
    total_graph_hits: int
    fusion_time_ms: int


@dataclass
class HybridRAGService:
    """Main HybridRAG service integrating all components.

    Provides unified hybrid search API combining vector (Qdrant)
    and graph (ArangoDB) retrieval with RRF fusion.

    Usage:
        service = HybridRAGService()
        result = await service.hybrid_search(
            query="AI需求分析的步驟是什麼？",
            collection="knowledge_default",
            top_k=10,
        )
    """

    _ollama_url: str = field(default=OLLAMA_BASE_URL)
    _qdrant_url: str = field(default=QDRANT_URL)
    _arango_url: str = field(default=ARANGO_URL)
    _arango_db: str = field(default=ARANGO_DB)
    _arango_auth: tuple[str, str] = field(default_factory=lambda: (ARANGO_USER, ARANGO_PASSWORD))
    _embedding_model: str = field(default=OLLAMA_EMBEDDING_MODEL)

    def __init__(
        self,
        ollama_url: str | None = None,
        qdrant_url: str | None = None,
        arango_url: str | None = None,
        arango_db: str | None = None,
        arango_user: str | None = None,
        arango_password: str | None = None,
        embedding_model: str | None = None,
    ) -> None:
        """Initialize HybridRAG service.

        Args:
            ollama_url: Ollama base URL.
            qdrant_url: Qdrant URL.
            arango_url: ArangoDB URL.
            arango_db: ArangoDB database name.
            arango_user: ArangoDB username.
            arango_password: ArangoDB password.
            embedding_model: Ollama embedding model.
        """
        self._ollama_url = ollama_url or OLLAMA_BASE_URL
        self._qdrant_url = qdrant_url or QDRANT_URL
        self._arango_url = arango_url or ARANGO_URL
        self._arango_db = arango_db or ARANGO_DB
        self._arango_auth = (
            arango_user or ARANGO_USER,
            arango_password or ARANGO_PASSWORD,
        )
        self._embedding_model = embedding_model or OLLAMA_EMBEDDING_MODEL

        # Lazy imports to avoid circular dependencies
        self._classifier: object | None = None
        self._config_service: object | None = None
        self._fusion_engine: object | None = None

    @property
    def classifier(self):
        """Get query classifier (lazy loaded)."""
        if self._classifier is None:
            from knowledge_agent.hybrid_rag.classifier import HybridRAGQueryClassifier
            self._classifier = HybridRAGQueryClassifier()
        return self._classifier

    @property
    def config_service(self):
        """Get config service (lazy loaded)."""
        if self._config_service is None:
            from knowledge_agent.hybrid_rag.config_service import get_config_service
            self._config_service = get_config_service()
        return self._config_service

    @property
    def fusion_engine(self):
        """Get fusion engine (lazy loaded)."""
        if self._fusion_engine is None:
            from knowledge_agent.hybrid_rag.fusion_engine import HybridRAGFusionEngine
            self._fusion_engine = HybridRAGFusionEngine()
        return self._fusion_engine

    # -------------------------------------------------------------------------
    # Embedding
    # -------------------------------------------------------------------------

    async def _get_embedding(self, text: str) -> list[float]:
        """Get embedding vector for text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._ollama_url}/api/embed",
                json={"model": self._embedding_model, "input": text},
            )
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings", [])
            if embeddings and len(embeddings) > 0:
                return list(embeddings[0])
            return []

    # -------------------------------------------------------------------------
    # Vector Search
    # -------------------------------------------------------------------------

    async def _vector_search(
        self,
        query_embedding: list[float],
        collection: str,
        top_k: int,
    ) -> tuple[list[dict], int]:
        """Search vector store (Qdrant).

        Args:
            query_embedding: Query embedding vector.
            collection: Qdrant collection name.
            top_k: Number of results.

        Returns:
            Tuple of (results, total_count).
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._qdrant_url}/collections/{collection}/points/search",
                    json={
                        "vector": query_embedding,
                        "limit": top_k,
                        "with_payload": True,
                    },
                )
                response.raise_for_status()
                data = response.json()
                results = data.get("result", [])
                return results, len(results)
        except Exception:
            return [], 0

    # -------------------------------------------------------------------------
    # Graph Search
    # -------------------------------------------------------------------------

    async def _graph_search(
        self,
        query: str,
        root_id: str | None = None,
        top_k: int = 10,
    ) -> tuple[list[dict], int]:
        """Search knowledge graph (ArangoDB).

        Args:
            query: Natural language query.
            root_id: Optional root ID to filter by knowledge base.
            top_k: Number of results.

        Returns:
            Tuple of (results, total_count).
        """
        # Extract keywords from query for matching
        keywords = self._extract_keywords(query)

        # Build AQL query
        filter_conditions = []
        bind_vars: dict[str, object] = {"top_k": top_k}

        if keywords:
            keyword_conditions = " || ".join(
                f'LIKE(d.entity, CONCAT("%", @kw{i}, "%"), true)'
                for i, kw in enumerate(keywords)
            )
            filter_conditions.append(f"({keyword_conditions})")
            for i, kw in enumerate(keywords):
                bind_vars[f"kw{i}"] = kw

        if root_id:
            filter_conditions.append("d.root_id == @root_id")
            bind_vars["root_id"] = root_id

        filter_clause = (
            f" FILTER {' && '.join(filter_conditions)}" if filter_conditions else ""
        )

        aql = f"""
        FOR d IN knowledge_graphs
        {filter_clause}
        SORT BM25(d) DESC
        LIMIT @top_k
        RETURN d
        """

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/cursor",
                    json={"query": aql, "bindVars": bind_vars},
                    auth=self._arango_auth,
                )
                if response.status_code in (200, 201):
                    data = response.json()
                    results = data.get("result", [])
                    return results, len(results)
        except Exception:
            pass

        return [], 0

    def _extract_keywords(self, query: str) -> list[str]:
        """Extract keywords from query for graph matching.

        Args:
            query: Query string.

        Returns:
            List of significant keywords.
        """
        # Simple keyword extraction - remove common words and extract significant terms
        stop_words = {
            "什麼", "是", "的", "了", "和", "與", "這", "那", "有",
            "沒有", "如何", "怎麼", "為什麼", "可以", "嗎", "呢",
        }

        words = query.replace("？", " ").replace("?", " ").replace("，", " ").split()
        keywords = [w for w in words if len(w) >= 2 and w not in stop_words]

        # Return longer keywords first (more specific)
        keywords.sort(key=len, reverse=True)
        return keywords[:10]  # Limit to top 10

    def _build_graph_result_content(self, entity: dict, relations: list[dict]) -> str:
        """Build content string from graph entity and relations.

        Args:
            entity: Entity document.
            relations: Related entities.

        Returns:
            Content string for fusion.
        """
        entity_name = entity.get("entity", "")
        entity_type = entity.get("entity_type", "")
        description = entity.get("description", "")

        parts = [f"{entity_name}（{entity_type}）"]
        if description:
            parts.append(description)

        # Add relation info
        for rel in relations[:3]:
            rel_type = rel.get("relation", "")
            target = rel.get("target", "")
            if rel_type and target:
                parts.append(f"{rel_type}: {target}")

        return " | ".join(parts)

    # -------------------------------------------------------------------------
    # Hybrid Search
    # -------------------------------------------------------------------------

    async def hybrid_search(
        self,
        query: str,
        collection: str = "knowledge_default",
        top_k: int = 10,
        strategy: str = "hybrid",
        min_relevance: float = 0.0,
        tenant_id: str | None = None,
        user_id: str | None = None,
        root_id: str | None = None,
    ) -> HybridSearchResponse:
        """Execute hybrid search combining vector and graph retrieval.

        Args:
            query: Natural language query.
            collection: Qdrant collection name.
            top_k: Number of results to return.
            strategy: Search strategy - "hybrid", "vector_first", or "graph_first".
            min_relevance: Minimum relevance score threshold.
            tenant_id: Optional tenant ID for config.
            user_id: Optional user ID for config.
            root_id: Optional root ID to filter graph search.

        Returns:
            HybridSearchResponse with fused results.
        """
        start_time = time.time()

        # Step 1: Detect query type
        query_type = self.classifier.classify(query)

        # Step 2: Get weights for query type
        weights, _ = self.config_service.get_weights_for_query(
            query, tenant_id, user_id
        )

        # Step 3: Get query embedding
        query_embedding = await self._get_embedding(query)

        # Step 4: Execute searches based on strategy
        vector_weight = weights.vector_weight
        graph_weight = weights.graph_weight

        vector_results: list[dict] = []
        graph_results: list[dict] = []
        total_vector = 0
        total_graph = 0

        if strategy in ("hybrid", "vector_first"):
            vector_results, total_vector = await self._vector_search(
                query_embedding, collection, top_k * 2
            )

        if strategy in ("hybrid", "graph_first"):
            graph_results, total_graph = await self._graph_search(
                query, root_id, top_k * 2
            )

        # Step 5: Convert to RetrievalResult format
        from knowledge_agent.hybrid_rag.fusion_engine import (
            RetrievalResult,
            RetrievalSource,
        )

        vector_retrieval = [
            RetrievalResult(
                content=r.get("payload", {}).get("text_full", r.get("payload", {}).get("text", "")),
                source=RetrievalSource.VECTOR,
                score=float(r.get("score", 0.0)),
                metadata={
                    "file_id": r.get("payload", {}).get("file_id", ""),
                    "chunk_index": r.get("payload", {}).get("chunk_index"),
                    "root_id": r.get("payload", {}).get("root_id", ""),
                },
            )
            for r in vector_results
        ]

        graph_retrieval = [
            RetrievalResult(
                content=self._build_graph_result_content(r, []),
                source=RetrievalSource.GRAPH,
                score=1.0,  # Graph results don't have scores in same scale
                metadata={
                    "file_id": r.get("file_id", ""),
                    "entity_type": r.get("entity_type", ""),
                },
            )
            for r in graph_results
        ]

        # Step 6: Fuse results
        fused = self.fusion_engine.fuse(
            vector_results=vector_retrieval,
            graph_results=graph_retrieval,
            vector_weight=vector_weight,
            graph_weight=graph_weight,
            top_k=top_k,
            min_relevance=min_relevance,
        )

        # Step 7: Build response
        fusion_time_ms = int((time.time() - start_time) * 1000)

        results: list[HybridSearchResult] = []
        for fr in fused:
            results.append(
                HybridSearchResult(
                    content=fr.content,
                    source=fr.source,
                    score=round(fr.score, 4),
                    metadata=HybridSearchMetadata(
                        file_id=fr.metadata.get("file_id", ""),
                        chunk_index=fr.metadata.get("chunk_index"),
                        entity_type=fr.metadata.get("entity_type"),
                        root_id=fr.metadata.get("root_id"),
                    ),
                )
            )

        return HybridSearchResponse(
            query=query,
            query_type=query_type.value,
            strategy=strategy,
            weights_used={
                "vector_weight": round(vector_weight, 2),
                "graph_weight": round(graph_weight, 2),
            },
            results=results,
            total_vector_hits=total_vector,
            total_graph_hits=total_graph,
            fusion_time_ms=fusion_time_ms,
        )

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    async def health_check(self) -> dict:
        """Check service health.

        Returns:
            Health status dict.
        """
        status: dict[str, str] = {
            "status": "ok",
            "ollama": "unknown",
            "qdrant": "unknown",
            "arangodb": "unknown",
        }

        # Check Ollama
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._ollama_url}/api/tags")
                status["ollama"] = "ok" if resp.status_code == 200 else "error"
        except Exception:
            status["ollama"] = "error"

        # Check Qdrant
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._qdrant_url}/collections")
                status["qdrant"] = "ok" if resp.status_code == 200 else "error"
        except Exception:
            status["qdrant"] = "error"

        # Check ArangoDB
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/collection",
                    auth=self._arango_auth,
                )
                status["arangodb"] = "ok" if resp.status_code == 200 else "error"
        except Exception:
            status["arangodb"] = "error"

        status["status"] = "ok" if all(
            v == "ok" for k, v in status.items() if k != "status"
        ) else "degraded"

        return status


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_hybrid_rag_service: HybridRAGService | None = None


def get_hybrid_rag_service() -> HybridRAGService:
    """Get singleton HybridRAG service instance.

    Returns:
        HybridRAGService instance.
    """
    global _hybrid_rag_service
    if _hybrid_rag_service is None:
        _hybrid_rag_service = HybridRAGService()
    return _hybrid_rag_service
