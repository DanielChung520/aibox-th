"""
HybridRAG Fusion Engine - Result fusion using RRF algorithm.

Implements Reciprocal Rank Fusion (RRF) for combining vector and graph
retrieval results with configurable weights.

@lastUpdate: 2026-04-05 12:00:00
@author: Daniel Chung
@version: 1.0.0
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Final, TypedDict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RRF_K: Final[int] = int(os.getenv("HYBRID_RAG_K", "60"))

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class RetrievalSource(str):
    """Source of retrieval result."""

    VECTOR = "vector"
    GRAPH = "graph"
    FUSION = "fusion"


class RetrievalMetadata(TypedDict, total=False):
    """Metadata for a retrieval result."""

    file_id: str
    chunk_index: int | None
    entity_type: str | None
    relation: str | None
    root_id: str | None
    text: str | None


@dataclass
class RetrievalResult:
    """Single retrieval result from vector or graph search.

    Attributes:
        content: Text content of the result.
        source: Source channel (vector/graph).
        score: Original relevance score from search.
        metadata: Additional metadata about the result.
    """

    content: str
    source: RetrievalSource
    score: float
    metadata: RetrievalMetadata = field(default_factory=dict)

    @property
    def doc_key(self) -> str:
        """Generate unique key for deduplication.

        Uses content hash + file_id for uniqueness.
        """
        content_hash = hashlib.md5(self.content[:200].encode()).hexdigest()[:12]
        file_id = self.metadata.get("file_id", "")
        return f"{file_id}:{content_hash}" if file_id else content_hash

    def with_adjusted_score(self, weight: float) -> RetrievalResult:
        """Return a copy with score adjusted by weight.

        Args:
            weight: Weight multiplier.

        Returns:
            New RetrievalResult with adjusted score.
        """
        return RetrievalResult(
            content=self.content,
            source=self.source,
            score=self.score * weight,
            metadata=self.metadata,
        )


@dataclass
class FusionResult:
    """Fused retrieval result with combined score.

    Attributes:
        content: Text content.
        source: Primary source channel.
        score: Fused relevance score.
        original_scores: Scores from each channel.
        metadata: Combined metadata.
    """

    content: str
    source: str
    score: float
    original_scores: dict[str, float] = field(default_factory=dict)
    metadata: RetrievalMetadata = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "content": self.content,
            "source": self.source,
            "score": round(self.score, 4),
            "original_scores": {k: round(v, 4) for k, v in self.original_scores.items()},
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# RRF Implementation
# ---------------------------------------------------------------------------


def reciprocal_rank_fusion(
    vector_results: list[RetrievalResult],
    graph_results: list[RetrievalResult],
    vector_weight: float,
    graph_weight: float,
    k: int = DEFAULT_RRF_K,
) -> dict[str, tuple[float, RetrievalResult]]:
    """Apply Reciprocal Rank Fusion to combine results.

    RRF formula: RRF_score(doc) = Σ 1 / (k + rank_i(doc))

    Args:
        vector_results: Results from vector search.
        graph_results: Results from graph search.
        vector_weight: Weight multiplier for vector channel.
        graph_weight: Weight multiplier for graph channel.
        k: RRF constant (default 60). Higher = more weight to lower ranks.

    Returns:
        Dict mapping doc_key to (fused_score, best_result).
    """
    rrf_scores: dict[str, tuple[float, RetrievalResult]] = {}

    # Process vector results
    sorted_vector = sorted(
        vector_results, key=lambda r: r.score, reverse=True
    )
    for rank, result in enumerate(sorted_vector):
        doc_key = result.doc_key
        rrf_score = vector_weight * (1.0 / (k + rank + 1))

        if doc_key in rrf_scores:
            existing_score, _ = rrf_scores[doc_key]
            rrf_scores[doc_key] = (existing_score + rrf_score, result)
        else:
            rrf_scores[doc_key] = (rrf_score, result)

    # Process graph results
    sorted_graph = sorted(graph_results, key=lambda r: r.score, reverse=True)
    for rank, result in enumerate(sorted_graph):
        doc_key = result.doc_key
        rrf_score = graph_weight * (1.0 / (k + rank + 1))

        if doc_key in rrf_scores:
            existing_score, existing_result = rrf_scores[doc_key]
            # Keep the result with higher original score as primary
            if result.score > existing_result.score:
                rrf_scores[doc_key] = (existing_score + rrf_score, result)
            else:
                rrf_scores[doc_key] = (existing_score + rrf_score, existing_result)
        else:
            rrf_scores[doc_key] = (rrf_score, result)

    return rrf_scores


# ---------------------------------------------------------------------------
# Fusion Engine
# ---------------------------------------------------------------------------


class HybridRAGFusionEngine:
    """Fusion engine for combining vector and graph retrieval results.

    Implements RRF-based fusion with support for deduplication,
    weighting, and flexible result combination.

    Usage:
        engine = HybridRAGFusionEngine()
        results = engine.fuse(
            vector_results=vector_hits,
            graph_results=graph_hits,
            vector_weight=0.4,
            graph_weight=0.6,
            top_k=10,
        )
    """

    def __init__(self, rrf_k: int = DEFAULT_RRF_K) -> None:
        """Initialize fusion engine.

        Args:
            rrf_k: RRF constant for ranking. Higher values give more
                   weight to lower-ranked results.
        """
        self._rrf_k = rrf_k

    @property
    def rrf_k(self) -> int:
        """Get RRF k constant."""
        return self._rrf_k

    def fuse(
        self,
        vector_results: list[RetrievalResult],
        graph_results: list[RetrievalResult],
        vector_weight: float,
        graph_weight: float,
        top_k: int = 10,
        min_relevance: float = 0.0,
    ) -> list[FusionResult]:
        """Fuse vector and graph results using RRF.

        Args:
            vector_results: Results from vector search.
            graph_results: Results from graph search.
            vector_weight: Weight for vector channel.
            graph_weight: Weight for graph channel.
            top_k: Maximum number of results to return.
            min_relevance: Minimum relevance score threshold.

        Returns:
            List of fused results sorted by score descending.
        """
        if not vector_results and not graph_results:
            return []

        # Apply RRF fusion
        fused = reciprocal_rank_fusion(
            vector_results=vector_results,
            graph_results=graph_results,
            vector_weight=vector_weight,
            graph_weight=graph_weight,
            k=self._rrf_k,
        )

        # Convert to FusionResult and sort
        fusion_results: list[FusionResult] = []
        seen_doc_keys: set[str] = set()

        for doc_key, (rrf_score, result) in fused.items():
            # Skip if below minimum relevance
            if rrf_score < min_relevance:
                continue

            # Deduplication
            if doc_key in seen_doc_keys:
                continue
            seen_doc_keys.add(doc_key)

            # Collect original scores
            original_scores: dict[str, float] = {"fused": rrf_score}
            if result.source == RetrievalSource.VECTOR:
                original_scores["vector"] = result.score
            elif result.source == RetrievalSource.GRAPH:
                original_scores["graph"] = result.score

            # Determine primary source
            primary_source = (
                RetrievalSource.VECTOR.value
                if result.source == RetrievalSource.VECTOR
                else RetrievalSource.GRAPH.value
            )

            fusion_results.append(
                FusionResult(
                    content=result.content,
                    source=primary_source,
                    score=rrf_score,
                    original_scores=original_scores,
                    metadata=result.metadata,
                )
            )

        # Sort by fused score descending
        fusion_results.sort(key=lambda x: x.score, reverse=True)

        return fusion_results[:top_k]

    def fuse_weighted(
        self,
        vector_results: list[RetrievalResult],
        graph_results: list[RetrievalResult],
        weights: dict[str, float],
        top_k: int = 10,
        min_relevance: float = 0.0,
    ) -> list[FusionResult]:
        """Fuse results using weights from config.

        Args:
            vector_results: Results from vector search.
            graph_results: Results from graph search.
            weights: Dict with 'vector_weight' and 'graph_weight'.
            top_k: Maximum results to return.
            min_relevance: Minimum relevance threshold.

        Returns:
            List of fused results.
        """
        return self.fuse(
            vector_results=vector_results,
            graph_results=graph_results,
            vector_weight=weights.get("vector_weight", 0.6),
            graph_weight=weights.get("graph_weight", 0.4),
            top_k=top_k,
            min_relevance=min_relevance,
        )
