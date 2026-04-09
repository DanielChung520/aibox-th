"""
HybridRAG Query Classifier - Query type detection for hybrid retrieval.

Classifies natural language queries into structure_query, entity_query, or semantic_query
to enable dynamic weight adjustment in hybrid retrieval.

@lastUpdate: 2026-04-05 12:00:00
@author: Daniel Chung
@version: 1.0.0
"""

from __future__ import annotations

from enum import Enum
from typing import Final

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Keywords for structure query detection (流程、步驟、框架等)
STRUCTURE_KEYWORDS: Final[set[str]] = {
    "框架",
    "步驟",
    "流程",
    "階段",
    "順序",
    "架構",
    "設計",
    "結構",
    "流程圖",
    "流程說明",
    "步驟說明",
    "階段說明",
    "包含哪些階段",
    "流程是什麼",
    "幾個步驟",
    "先後順序",
}

# Keywords for entity query detection (關係、連接、包含等)
ENTITY_KEYWORDS: Final[set[str]] = {
    "是什麼",
    "關係",
    "連接",
    "包含",
    "屬於",
    "之間",
    "差異",
    "不同",
    "對比",
    "比較",
    "包含哪些",
    "由什麼組成",
    "與什麼關係",
    "什麼關係",
}

# Keywords that strongly indicate semantic query
SEMANTIC_INDICATOR_KEYWORDS: Final[set[str]] = {
    "解釋",
    "說明",
    "關於",
    "什麼是",
    "定義",
    "意思",
    "總結",
    "摘要",
    "相關",
}


# ---------------------------------------------------------------------------
# Query Type Enum
# ---------------------------------------------------------------------------


class QueryType(str, Enum):
    """HybridRAG query type classification."""

    STRUCTURE_QUERY = "structure_query"
    SEMANTIC_QUERY = "semantic_query"
    ENTITY_QUERY = "entity_query"

    def __str__(self) -> str:
        return self.value


# ---------------------------------------------------------------------------
# Classifier Implementation
# ---------------------------------------------------------------------------


def detect_query_type(query: str) -> QueryType:
    """Detect query type based on keyword matching.

    Detection priority:
    1. structure_query - if any structure keyword found
    2. entity_query - if any entity keyword found
    3. semantic_query - default

    Args:
        query: Natural language query string.

    Returns:
        Detected QueryType.
    """
    query_lower = query.lower()

    # Priority 1: Check for structure keywords
    if _contains_any(query_lower, STRUCTURE_KEYWORDS):
        return QueryType.STRUCTURE_QUERY

    # Priority 2: Check for entity keywords
    if _contains_any(query_lower, ENTITY_KEYWORDS):
        return QueryType.ENTITY_QUERY

    # Default: semantic query
    return QueryType.SEMANTIC_QUERY


def _contains_any(text: str, keywords: set[str]) -> bool:
    """Check if text contains any of the keywords.

    Args:
        text: Lowercased text to search.
        keywords: Set of keyword strings.

    Returns:
        True if any keyword is found in text.
    """
    return any(kw in text for kw in keywords)


class HybridRAGQueryClassifier:
    """Query classifier for HybridRAG with keyword-based detection.

    This classifier analyzes natural language queries and determines
    which retrieval strategy should be prioritized.

    Usage:
        classifier = HybridRAGQueryClassifier()
        query_type = classifier.classify("AI需求分析的步驟是什麼？")
        # Returns: QueryType.STRUCTURE_QUERY
    """

    def __init__(
        self,
        structure_keywords: set[str] | None = None,
        entity_keywords: set[str] | None = None,
    ) -> None:
        """Initialize classifier with optional custom keywords.

        Args:
            structure_keywords: Custom structure keywords (optional).
            entity_keywords: Custom entity keywords (optional).
        """
        self._structure_keywords = structure_keywords or STRUCTURE_KEYWORDS
        self._entity_keywords = entity_keywords or ENTITY_KEYWORDS

    @property
    def structure_keywords(self) -> set[str]:
        """Get structure keywords set."""
        return self._structure_keywords

    @property
    def entity_keywords(self) -> set[str]:
        """Get entity keywords set."""
        return self._entity_keywords

    def classify(self, query: str) -> QueryType:
        """Classify a query into its type.

        Args:
            query: Natural language query string.

        Returns:
            Detected QueryType.
        """
        query_lower = query.lower()

        if _contains_any(query_lower, self._structure_keywords):
            return QueryType.STRUCTURE_QUERY

        if _contains_any(query_lower, self._entity_keywords):
            return QueryType.ENTITY_QUERY

        return QueryType.SEMANTIC_QUERY

    def classify_with_confidence(
        self, query: str
    ) -> tuple[QueryType, float]:
        """Classify query with confidence score.

        Args:
            query: Natural language query string.

        Returns:
            Tuple of (QueryType, confidence_score).
            Confidence is based on keyword match density.
        """
        query_lower = query.lower()
        query_len = len(query)

        # Count matches
        structure_matches = sum(1 for kw in self._structure_keywords if kw in query_lower)
        entity_matches = sum(1 for kw in self._entity_keywords if kw in query_lower)

        # Normalize by query length
        structure_density = structure_matches / max(query_len / 10, 1)
        entity_density = entity_matches / max(query_len / 10, 1)

        # Determine type and confidence
        if structure_matches > 0:
            confidence = min(0.5 + structure_density * 0.5, 0.95)
            return QueryType.STRUCTURE_QUERY, confidence

        if entity_matches > 0:
            confidence = min(0.5 + entity_density * 0.5, 0.95)
            return QueryType.ENTITY_QUERY, confidence

        # Semantic query - lower confidence as it's the default
        return QueryType.SEMANTIC_QUERY, 0.6

    def add_structure_keyword(self, keyword: str) -> None:
        """Add a keyword to the structure keywords set.

        Args:
            keyword: Keyword to add.
        """
        self._structure_keywords.add(keyword)

    def add_entity_keyword(self, keyword: str) -> None:
        """Add a keyword to the entity keywords set.

        Args:
            keyword: Keyword to add.
        """
        self._entity_keywords.add(keyword)
