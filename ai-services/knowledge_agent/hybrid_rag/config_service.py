"""
HybridRAG Config Service - Weight configuration management.

Provides dynamic weight configuration for hybrid retrieval with support
for three-level override: system → tenant → user.

Configuration is stored in ArangoDB system_params collection.

@lastUpdate: 2026-04-05 12:00:00
@author: Daniel Chung
@version: 1.0.0
"""

from __future__ import annotations

import os
import time
from typing import Final

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RRF_K: Final[int] = 60
DEFAULT_TOP_K: Final[int] = 10
DEFAULT_MIN_RELEVANCE: Final[float] = 0.0
CONFIG_CACHE_TTL: int = int(os.getenv("HYBRID_RAG_CONFIG_CACHE_TTL", "300"))

# Default weights by query type
DEFAULT_WEIGHTS: Final[dict[str, dict[str, float]]] = {
    "default": {"vector_weight": 0.6, "graph_weight": 0.4},
    "structure_query": {"vector_weight": 0.4, "graph_weight": 0.6},
    "semantic_query": {"vector_weight": 0.7, "graph_weight": 0.3},
    "entity_query": {"vector_weight": 0.3, "graph_weight": 0.7},
}

# ArangoDB connection
ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class Weights:
    """Weight configuration for vector and graph retrieval."""

    __slots__ = ("vector_weight", "graph_weight")

    def __init__(self, vector_weight: float, graph_weight: float) -> None:
        if not 0.0 <= vector_weight <= 1.0:
            raise ValueError("vector_weight must be between 0.0 and 1.0")
        if not 0.0 <= graph_weight <= 1.0:
            raise ValueError("graph_weight must be between 0.0 and 1.0")
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight

    def __repr__(self) -> str:
        return f"Weights(vector={self.vector_weight}, graph={self.graph_weight})"

    def to_dict(self) -> dict[str, float]:
        return {"vector_weight": self.vector_weight, "graph_weight": self.graph_weight}

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> Weights:
        return cls(
            vector_weight=float(data.get("vector_weight", 0.6)),
            graph_weight=float(data.get("graph_weight", 0.4)),
        )


class HybridRAGConfig:
    """Complete HybridRAG configuration for all query types."""

    def __init__(
        self,
        default: Weights,
        structure_query: Weights,
        semantic_query: Weights,
        entity_query: Weights,
    ) -> None:
        self.default = default
        self.structure_query = structure_query
        self.semantic_query = semantic_query
        self.entity_query = entity_query

    def get_weights(self, query_type: str) -> Weights:
        """Get weights for a specific query type.

        Args:
            query_type: Query type string.

        Returns:
            Weights for the given query type.
        """
        return getattr(self, query_type, self.default)

    def to_dict(self) -> dict[str, dict[str, float]]:
        return {
            "default": self.default.to_dict(),
            "structure_query": self.structure_query.to_dict(),
            "semantic_query": self.semantic_query.to_dict(),
            "entity_query": self.entity_query.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, dict[str, float]]) -> HybridRAGConfig:
        return cls(
            default=Weights.from_dict(data.get("default", {})),
            structure_query=Weights.from_dict(data.get("structure_query", {})),
            semantic_query=Weights.from_dict(data.get("semantic_query", {})),
            entity_query=Weights.from_dict(data.get("entity_query", {})),
        )

    @classmethod
    def default_config(cls) -> HybridRAGConfig:
        """Create default configuration."""
        return cls(
            default=Weights.from_dict(DEFAULT_WEIGHTS["default"]),
            structure_query=Weights.from_dict(DEFAULT_WEIGHTS["structure_query"]),
            semantic_query=Weights.from_dict(DEFAULT_WEIGHTS["semantic_query"]),
            entity_query=Weights.from_dict(DEFAULT_WEIGHTS["entity_query"]),
        )


# ---------------------------------------------------------------------------
# Config Service Implementation
# ---------------------------------------------------------------------------

_config_cache: dict[str, tuple[HybridRAGConfig, float]] = {}


class HybridRAGConfigService:
    """Configuration service for HybridRAG weights.

    Supports three-level configuration override:
    - system: Default weights for all users
    - tenant: Tenant-specific weights
    - user: User-specific weights

    Configuration is cached with TTL to reduce database queries.

    Usage:
        service = HybridRAGConfigService()
        weights = service.get_weights("structure_query", tenant_id="tenant_001")
    """

    def __init__(
        self,
        arango_url: str | None = None,
        arango_db: str | None = None,
        arango_user: str | None = None,
        arango_password: str | None = None,
    ) -> None:
        self._arango_url = arango_url or ARANGO_URL
        self._arango_db = arango_db or ARANGO_DB
        self._arango_user = arango_user or ARANGO_USER
        self._arango_password = arango_password or ARANGO_PASSWORD
        self._cache_ttl = CONFIG_CACHE_TTL

    def _get_cache_key(
        self, scope: str, tenant_id: str | None, user_id: str | None
    ) -> str:
        """Generate cache key for configuration."""
        return f"{scope}:{tenant_id}:{user_id}"

    def _is_cache_valid(self, cached: tuple[HybridRAGConfig, float]) -> bool:
        """Check if cache entry is still valid."""
        _, timestamp = cached
        return time.time() - timestamp < self._cache_ttl

    def _fetch_from_db(
        self, param_key: str
    ) -> dict[str, float] | None:
        """Fetch configuration from ArangoDB system_params.

        Args:
            param_key: Parameter key (e.g., "hybridrag.vector_weight.default").

        Returns:
            Configuration dict or None if not found.
        """
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/document/"
                    f"system_params/{param_key}",
                    auth=(self._arango_user, self._arango_password),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "vector_weight": float(data.get("vector_weight", 0.6)),
                        "graph_weight": float(data.get("graph_weight", 0.4)),
                    }
        except Exception:
            pass
        return None

    def _load_config(self) -> HybridRAGConfig:
        """Load full configuration from database or defaults.

        Returns:
            HybridRAGConfig instance.
        """
        # Try to load each query type config from DB
        config_data: dict[str, dict[str, float]] = {}

        query_types = ["default", "structure_query", "semantic_query", "entity_query"]

        for qt in query_types:
            vec_key = f"hybridrag.vector_weight.{qt}"
            gra_key = f"hybridrag.graph_weight.{qt}"

            vec_val = self._fetch_from_db(vec_key)
            gra_val = self._fetch_from_db(gra_key)

            if vec_val and gra_val:
                config_data[qt] = {
                    "vector_weight": vec_val["vector_weight"],
                    "graph_weight": gra_val["graph_weight"],
                }
            elif qt in DEFAULT_WEIGHTS:
                config_data[qt] = DEFAULT_WEIGHTS[qt]

        if not config_data:
            return HybridRAGConfig.default_config()

        # Fill missing with defaults
        for qt in query_types:
            if qt not in config_data:
                config_data[qt] = DEFAULT_WEIGHTS.get(qt, DEFAULT_WEIGHTS["default"])

        return HybridRAGConfig.from_dict(config_data)

    def get_config(self, force_reload: bool = False) -> HybridRAGConfig:
        """Get full HybridRAG configuration.

        Args:
            force_reload: If True, bypass cache.

        Returns:
            HybridRAGConfig instance.
        """
        cache_key = self._get_cache_key("system", None, None)

        if not force_reload and cache_key in _config_cache:
            cached_config, cached_time = _config_cache[cache_key]
            if self._is_cache_valid((cached_config, cached_time)):
                return cached_config

        config = self._load_config()
        _config_cache[cache_key] = (config, time.time())
        return config

    def get_weights(
        self,
        query_type: str,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> Weights:
        """Get weights for a specific query type.

        Args:
            query_type: Query type (default/structure_query/semantic_query/entity_query).
            tenant_id: Optional tenant ID for tenant-level override.
            user_id: Optional user ID for user-level override.

        Returns:
            Weights instance for the query type.
        """
        config = self.get_config()
        return config.get_weights(query_type)

    def get_weights_for_query(
        self, query: str, tenant_id: str | None = None, user_id: str | None = None
    ) -> tuple[Weights, str]:
        """Get weights for a query, automatically detecting query type.

        Args:
            query: Natural language query.
            tenant_id: Optional tenant ID.
            user_id: Optional user ID.

        Returns:
            Tuple of (Weights, detected_query_type).
        """
        from knowledge_agent.hybrid_rag.classifier import detect_query_type

        query_type = detect_query_type(query)
        weights = self.get_weights(query_type.value, tenant_id, user_id)
        return weights, query_type.value

    def save_weights(
        self,
        query_type: str,
        vector_weight: float,
        graph_weight: float,
        changed_by: str = "system",
    ) -> bool:
        """Save weight configuration to database.

        Args:
            query_type: Query type to update.
            vector_weight: Vector weight (0.0-1.0).
            graph_weight: Graph weight (0.0-1.0).
            changed_by: Who made the change.

        Returns:
            True if successful, False otherwise.
        """
        # Validate weights sum to 1.0 (with small tolerance)
        total = vector_weight + graph_weight
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Weights must sum to 1.0, got {vector_weight} + {graph_weight} = {total}"
            )

        vec_key = f"hybridrag.vector_weight.{query_type}"
        gra_key = f"hybridrag.graph_weight.{query_type}"

        try:
            with httpx.Client(timeout=10.0) as client:
                # Update vector weight
                client.patch(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/document/"
                    f"system_params/{vec_key}",
                    json={
                        "param_value": str(vector_weight),
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "updated_by": changed_by,
                    },
                    auth=(self._arango_user, self._arango_password),
                )

                # Update graph weight
                client.patch(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/document/"
                    f"system_params/{gra_key}",
                    json={
                        "param_value": str(graph_weight),
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "updated_by": changed_by,
                    },
                    auth=(self._arango_user, self._arango_password),
                )

            # Invalidate cache
            cache_key = self._get_cache_key("system", None, None)
            _config_cache.pop(cache_key, None)
            return True

        except Exception:
            return False

    def validate_weights(self, vector_weight: float, graph_weight: float) -> bool:
        """Validate that weights are valid.

        Args:
            vector_weight: Vector weight.
            graph_weight: Graph weight.

        Returns:
            True if valid, False otherwise.
        """
        if not (0.0 <= vector_weight <= 1.0):
            return False
        if not (0.0 <= graph_weight <= 1.0):
            return False
        if abs(vector_weight + graph_weight - 1.0) > 0.01:
            return False
        return True


# ---------------------------------------------------------------------------
# Singleton Access
# ---------------------------------------------------------------------------

_config_service: HybridRAGConfigService | None = None


def get_config_service() -> HybridRAGConfigService:
    """Get singleton config service instance.

    Returns:
        HybridRAGConfigService instance.
    """
    global _config_service
    if _config_service is None:
        _config_service = HybridRAGConfigService()
    return _config_service
