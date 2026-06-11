"""
@file        base_engine.py
@description Abstract base engine for the data trace system.
             Defines the interface all scenario-specific engines must implement.
@lastUpdate  2026-05-17
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from data_agent.ragic.config_loader import RagicConfigLoader
from data_agent.ragic.record_tracer import RecordTracer
from data_agent.trace_engine.config import TraceEngineConfig, load_config
from data_agent.trace_engine.models import TraceRequest, TraceResult


class BaseTraceEngine(ABC):
    """Abstract base for scenario-specific trace engines.

    Every concrete engine receives a shared ``RecordTracer`` and
    ``RagicConfigLoader`` at construction time.  The public API is a
    single async ``trace()`` method.
    """

    def __init__(
        self,
        tracer: RecordTracer,
        config_loader: RagicConfigLoader,
    ) -> None:
        self._tracer = tracer
        self._config_loader = config_loader
        self._config: TraceEngineConfig = load_config()

    @abstractmethod
    async def trace(self, request: TraceRequest, account: str) -> TraceResult:
        """Execute a trace scenario and return the result.

        Args:
            request: Parameters describing what to trace.
            account: The Ragic account identifier.

        Returns:
            A fully populated ``TraceResult``.
        """
        ...
