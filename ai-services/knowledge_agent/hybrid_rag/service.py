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

from knowledge_agent.hybrid_rag.models.evidence import (
    AuditRecord,
    BoundaryStatus,
    EvidenceProvenance,
    EvidenceSearchResponse,
    EvidenceSet,
    EvidenceUnit,
    NextStep,
    SourceType,
    Sufficiency,
)
from knowledge_agent.hybrid_rag.models.inquiry import (
    EvidenceSearchRequest,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3:latest")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class HybridSearchRequest(TypedDict, total=False):
    """Request model for hybrid search."""

    query: str
    collection: str
    top_k: int
    strategy: str
    min_relevance: float
    tenant_id: str | None
    user_id: str | None
    root_id: str | None
    user_role: str | None


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
    _boundary_checker: object | None = field(default=None)
    _inquiry_decomposer: object | None = field(default=None)
    _evidence_analyzer: object | None = field(default=None)

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

    @property
    def boundary_checker(self):
        """Get boundary checker (lazy loaded)."""
        if self._boundary_checker is None:
            from knowledge_agent.hybrid_rag.boundary_checker import get_boundary_checker
            self._boundary_checker = get_boundary_checker()
        return self._boundary_checker

    @property
    def evidence_analyzer(self):
        if self._evidence_analyzer is None:
            from knowledge_agent.hybrid_rag.evidence_analyzer import get_evidence_analyzer
            self._evidence_analyzer = get_evidence_analyzer()
        return self._evidence_analyzer

    @property
    def inquiry_decomposer(self):
        """Get inquiry decomposer (lazy loaded)."""
        if self._inquiry_decomposer is None:
            from knowledge_agent.hybrid_rag.inquiry_decomposer import get_inquiry_decomposer
            self._inquiry_decomposer = get_inquiry_decomposer()
        return self._inquiry_decomposer

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
        llm_provider: str = "ollama",
        user_role: str | None = None,
    ) -> HybridSearchResponse:
        start_time = time.time()

        self.config_service.assert_llm_provider_allowed(llm_provider)

        if root_id and collection == "knowledge_default":
            collection = f"knowledge_{root_id}"

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
    # Evidence Search (v2)
    # -------------------------------------------------------------------------

    async def evidence_search(
        self,
        request: EvidenceSearchRequest,
        llm_provider: str = "ollama",
    ) -> EvidenceSearchResponse:
        import time

        start_time = time.time()
        self.config_service.assert_llm_provider_allowed(llm_provider)
        hypothesis = request.hypothesis
        boundary = request.boundary

        if not hypothesis.statement and not request.query:
            evidence_set = EvidenceSet(
                hypothesis_id="",
                boundary_status=BoundaryStatus.WITHIN_BOUNDARY,
                sufficiency=Sufficiency.INSUFFICIENT,
                evidences=[],
                contradictions=[],
                gaps=["No hypothesis and no query provided"],
                next_step=NextStep.ASK_FOR_CLARIFICATION,
            )
            audit = AuditRecord(
                query=request.query,
                hypothesis_id=None,
                boundary_checked=True,
                channels_used=[],
                stop_reason="no_hypothesis",
                total_time_ms=int((time.time() - start_time) * 1000),
            )
            return EvidenceSearchResponse(evidence_set=evidence_set, audit=audit)

        decomposer = self.inquiry_decomposer
        if not hypothesis.statement and request.query:
            hypothesis = decomposer.create_implicit_hypothesis(
                request.query, boundary, request.context_signals
            )
        elif request.inquiry_plan is None:
            request.inquiry_plan = decomposer.decompose(hypothesis, boundary, request.query)
        query = request.query or hypothesis.statement

        boundary_result = self.boundary_checker.check(boundary, hypothesis, user_role=request.user_role)
        if boundary_result.is_out_of_boundary:
            evidence_set = EvidenceSet(
                hypothesis_id=hypothesis.hypothesis_id or "",
                boundary_status=BoundaryStatus.OUT_OF_BOUNDARY,
                sufficiency=Sufficiency.INSUFFICIENT,
                evidences=[],
                contradictions=[],
                gaps=[],
                next_step=NextStep.STOP,
            )
            audit = AuditRecord(
                query=query,
                hypothesis_id=hypothesis.hypothesis_id,
                boundary_checked=True,
                channels_used=[],
                discarded_candidates=0,
                discard_reasons=[boundary_result.reason or "out_of_boundary"],
                stop_reason="out_of_boundary",
                fusion_strategy="rrf_v2",
                total_time_ms=int((time.time() - start_time) * 1000),
            )
            return EvidenceSearchResponse(evidence_set=evidence_set, audit=audit)

        if boundary_result.is_boundary_unclear:
            evidence_set = EvidenceSet(
                hypothesis_id=hypothesis.hypothesis_id or "",
                boundary_status=BoundaryStatus.BOUNDARY_UNCLEAR,
                sufficiency=Sufficiency.INSUFFICIENT,
                evidences=[],
                contradictions=[],
                gaps=[boundary_result.reason or "boundary_unclear"],
                next_step=NextStep.ASK_FOR_CLARIFICATION,
            )
            audit = AuditRecord(
                query=query,
                hypothesis_id=hypothesis.hypothesis_id,
                boundary_checked=True,
                channels_used=[],
                discarded_candidates=0,
                discard_reasons=[boundary_result.reason or "boundary_unclear"],
                stop_reason="boundary_unclear",
                fusion_strategy="rrf_v2",
                total_time_ms=int((time.time() - start_time) * 1000),
            )
            return EvidenceSearchResponse(evidence_set=evidence_set, audit=audit)

        channels_used: list[str] = []
        discarded = 0
        discard_reasons: list[str] = []

        top_k = boundary.max_top_k
        actual_plan = request.inquiry_plan
        allowed = actual_plan.allowed_channels if actual_plan else ["vector", "graph"]

        vector_results: list[dict] = []
        graph_results: list[dict] = []
        total_vector = 0
        total_graph = 0

        if "vector" in allowed:
            channels_used.append("vector")
            collection = f"knowledge_{boundary.root_id}" if boundary.root_id else "knowledge_default"
            query_emb = await self._get_embedding(query)
            vector_results, total_vector = await self._vector_search(
                query_emb, collection, top_k * 2
            )

        if "graph" in allowed:
            channels_used.append("graph")
            graph_results, total_graph = await self._graph_search(
                query, boundary.root_id, top_k * 2
            )

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
                score=1.0,
                metadata={
                    "file_id": r.get("file_id", ""),
                    "entity_type": r.get("entity_type", ""),
                },
            )
            for r in graph_results
        ]

        weights, _ = self.config_service.get_weights_for_query(query, None, None)
        fused = self.fusion_engine.fuse(
            vector_results=vector_retrieval,
            graph_results=graph_retrieval,
            vector_weight=weights.vector_weight,
            graph_weight=weights.graph_weight,
            top_k=top_k,
        )

        evidence_units: list[EvidenceUnit] = []
        for fr in fused:
            src_type = SourceType.FUSION
            if fr.source == RetrievalSource.VECTOR:
                src_type = SourceType.VECTOR
            elif fr.source == RetrievalSource.GRAPH:
                src_type = SourceType.GRAPH

            evidence_units.append(
                EvidenceUnit(
                    source_type=src_type,
                    root_id=fr.metadata.get("root_id"),
                    file_id=fr.metadata.get("file_id"),
                    content=fr.content,
                    normalized_score=fr.score,
                    extraction_confidence=0.8,
                    supports=[hypothesis.hypothesis_id or ""],
                    contradicts=[],
                    provenance=EvidenceProvenance(
                        lifecycle_status="active",
                    ),
                )
            )

        evidence_set, gaps = self.evidence_analyzer.analyze(
            evidence_units, hypothesis, request.inquiry_plan
        )
        evidence_set.boundary_status = BoundaryStatus.WITHIN_BOUNDARY

        audit = AuditRecord(
            query=query,
            hypothesis_id=hypothesis.hypothesis_id,
            boundary_checked=True,
            channels_used=channels_used,
            discarded_candidates=discarded,
            discard_reasons=discard_reasons,
            stop_reason=evidence_set.next_step.value if evidence_set.next_step else None,
            fusion_strategy="rrf_v2",
            total_time_ms=int((time.time() - start_time) * 1000),
        )

        from knowledge_agent.hybrid_rag.state_machine import compute_next_state
        final_state = compute_next_state(
            boundary_status=evidence_set.boundary_status.value if evidence_set.boundary_status else None,
            sufficiency=evidence_set.sufficiency.value if evidence_set.sufficiency else None,
            next_step=evidence_set.next_step.value if evidence_set.next_step else None,
            has_hypothesis=bool(hypothesis.statement),
        )
        audit.stop_reason = final_state.value

        return EvidenceSearchResponse(
            evidence_set=evidence_set,
            audit=audit,
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
