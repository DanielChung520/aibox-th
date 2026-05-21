"""Perception Engine — Rule-based signal processing."""

from __future__ import annotations

import os
import threading
import time

from aiq_agent.perception.models import (
    Anchor,
    PageContext,
    SignalEvent,
    UserPrior,
    WorkingContext,
)

PAGE_TYPE_MAP: dict[str, str] = {
    "/app/welcome": "welcome",
    "/app/home": "welcome",
    "/app/users": "system_management",
    "/app/roles": "system_management",
    "/app/system-params": "system_management",
    "/app/params": "system_management",
    "/app/functions": "system_management",
    "/app/lead-management": "business_management",
    "/app/browse-agent": "browse",
    "/app/browse-tools": "browse",
    "/app/task-session/chat": "chat",
    "/app/task-session/history": "history",
    "/app/task-session/scheduled": "task_management",
    "/app/data-agent": "data_query",
    "/app/data-agent/schema": "data_query",
    "/app/data-agent/playground": "data_query",
    "/app/data-agent/datalake": "data_query",
    "/app/knowledge": "knowledge_management",
    "/app/knowledge/ontology": "knowledge_management",
    "/app/knowledge/management": "knowledge_management",
    "/app/intent-orchestration": "system_management",
    "/app/requirements": "business_management",
    "/app/action-board": "business_management",
    "/app/preorder": "business_management",
    "/app/knowledge/todos": "task_management",
    "/app/todo-board": "task_management",
    "/app/platforms": "platform",
    "/app/mermaid-verification": "development",
    "/app/knowledge/skills": "knowledge_management",
}


MAX_CONTEXTS = int(os.environ.get("AIQ_MAX_CONTEXTS", "500"))
CONTEXT_TTL_SECONDS = int(os.environ.get("AIQ_CONTEXT_TTL_SECONDS", "3600"))


class PerceptionEngine:
    """Rule-based perception engine for building working context."""

    def __init__(self) -> None:
        """Initialize in-memory working context storage."""
        self._contexts: dict[str, WorkingContext] = {}
        self._timestamps: dict[str, float] = {}
        self._lock = threading.Lock()

    def process_signals(
        self,
        user_key: str,
        signals: list[SignalEvent],
    ) -> WorkingContext:
        """Process a batch of signals and return the updated working context."""
        with self._lock:
            self._evict_stale()
            context = self._contexts.get(user_key, _create_default_context())

            if not signals:
                self._contexts[user_key] = context
                self._timestamps[user_key] = time.monotonic()
                return context.model_copy(deep=True)

            latest_page_signal = _latest_signal_by_type(signals, "page_navigate")
            if latest_page_signal is not None:
                context.page_context = _build_page_context(
                    latest_page_signal,
                    current_context=context,
                )

            recent_actions = context.behavior_snapshot.recent_actions + signals
            context.behavior_snapshot.recent_actions = recent_actions[-50:]

            anchor_changed = False
            batch_confidence = 0.0
            for signal in signals:
                anchor = _anchor_from_signal(signal)
                if anchor is None:
                    continue

                if signal.type == "table_focus":
                    context.page_context.table_name = _meta_string(signal.meta, "table_name")
                if signal.type == "page_navigate":
                    context.page_context.path = signal.page

                anchor_changed = _upsert_anchor(context, anchor) or anchor_changed
                batch_confidence = max(batch_confidence, anchor.confidence)

            # Track click counts per page
            for signal in signals:
                if signal.type == "click" or signal.type == "cell_click":
                    page_path = signal.page
                    context.behavior_snapshot.click_counts[page_path] = \
                        context.behavior_snapshot.click_counts.get(page_path, 0) + 1

                # Track recent searches
                if signal.type == "global_search":
                    keyword = _meta_string(signal.meta, "keyword")
                    if keyword and keyword not in context.behavior_snapshot.recent_searches:
                        context.behavior_snapshot.recent_searches.append(keyword)
                        context.behavior_snapshot.recent_searches = \
                            context.behavior_snapshot.recent_searches[-10:]  # Keep last 10

                # Track filter patterns
                if signal.type == "filter_apply":
                    filters = signal.meta.get("filters")
                    if filters and isinstance(filters, dict):
                        pattern = ",".join(f"{k}={v}" for k, v in filters.items())
                        if pattern not in context.behavior_snapshot.filter_patterns:
                            context.behavior_snapshot.filter_patterns.append(pattern)
                            context.behavior_snapshot.filter_patterns = \
                                context.behavior_snapshot.filter_patterns[-10:]

            context.signal_accumulation.total_signals += len(signals)
            if anchor_changed:
                context.signal_accumulation.last_anchor_change = signals[-1].timestamp

            confidence_trend = context.signal_accumulation.confidence_trend + [batch_confidence]
            context.signal_accumulation.confidence_trend = confidence_trend[-5:]

            self._contexts[user_key] = context
            self._timestamps[user_key] = time.monotonic()
            return context.model_copy(deep=True)

    def get_context(self, user_key: str) -> WorkingContext:
        """Return the current working context for a user."""
        with self._lock:
            context = self._contexts.get(user_key, _create_default_context())
            if user_key not in self._contexts:
                self._contexts[user_key] = context
                self._timestamps[user_key] = time.monotonic()
            return context.model_copy(deep=True)

    def set_user_prior(self, user_key: str, prior: UserPrior) -> None:
        """Inject user prior from the learning layer into the working context."""
        with self._lock:
            context = self._contexts.get(user_key)
            if context is not None:
                context.user_prior = prior
                self._timestamps[user_key] = time.monotonic()

    def _evict_stale(self) -> None:
        """Remove expired contexts and cap total count."""
        now = time.monotonic()
        stale = [k for k, ts in self._timestamps.items() if now - ts > CONTEXT_TTL_SECONDS]
        for k in stale:
            self._contexts.pop(k, None)
            self._timestamps.pop(k, None)
        if len(self._contexts) > MAX_CONTEXTS:
            oldest = sorted(self._timestamps, key=self._timestamps.get)  # type: ignore[arg-type]
            for k in oldest[: len(self._contexts) - MAX_CONTEXTS]:
                self._contexts.pop(k, None)
                self._timestamps.pop(k, None)


def _create_default_context() -> WorkingContext:
    """Create a default empty working context."""
    return WorkingContext(
        page_context=PageContext(
            path="/app/welcome",
            page_name="Welcome",
            page_type=PAGE_TYPE_MAP["/app/welcome"],
        )
    )


def _latest_signal_by_type(
    signals: list[SignalEvent],
    signal_type: str,
) -> SignalEvent | None:
    """Return the latest signal of the specified type."""
    for signal in reversed(signals):
        if signal.type == signal_type:
            return signal
    return None


def _build_page_context(
    signal: SignalEvent,
    current_context: WorkingContext,
) -> PageContext:
    """Build page context from a page navigation signal."""
    page_name = _meta_string(signal.meta, "page_name") or _page_name_from_path(signal.page)
    domain_name = _meta_string(signal.meta, "domain_name")
    table_name = _meta_string(signal.meta, "table_name") or current_context.page_context.table_name
    record_count = _meta_int(signal.meta, "record_count")
    return PageContext(
        path=signal.page,
        page_name=page_name,
        page_type=_resolve_page_type(signal.page),
        domain_name=domain_name,
        table_name=table_name,
        record_count=record_count,
    )


def _resolve_page_type(page_path: str) -> str:
    """Resolve frontend page path to a normalized page type."""
    if page_path in PAGE_TYPE_MAP:
        return PAGE_TYPE_MAP[page_path]

    for known_path, page_type in PAGE_TYPE_MAP.items():
        if known_path != "/app/welcome" and page_path.startswith(f"{known_path}/"):
            return page_type

    return "unknown"


def _page_name_from_path(page_path: str) -> str:
    """Generate a readable page name from a route path."""
    segment = page_path.rstrip("/").split("/")[-1]
    if not segment:
        return "Welcome"
    return segment.replace("-", " ").replace("_", " ").title()


def _anchor_from_signal(signal: SignalEvent) -> Anchor | None:
    """Build an anchor from a signal when a rule matches."""
    if signal.type == "page_navigate":
        if signal.page.startswith("/data-agent/") or signal.page.startswith("/app/data-agent"):
            return Anchor(
                anchor_type="page",
                value="data_query",
                confidence=0.8,
                source="structure",
                timestamp=signal.timestamp,
            )
        if signal.page.startswith("/knowledge/") or signal.page.startswith("/app/knowledge"):
            return Anchor(
                anchor_type="page",
                value="knowledge",
                confidence=0.8,
                source="structure",
                timestamp=signal.timestamp,
            )

    if signal.type == "query_submit":
        query_text = _meta_string(signal.meta, "query_text")
        if query_text:
            return Anchor(
                anchor_type="query",
                value=query_text,
                confidence=0.9,
                source="language",
                timestamp=signal.timestamp,
            )

    if signal.type == "table_focus":
        table_name = _meta_string(signal.meta, "table_name")
        if table_name:
            return Anchor(
                anchor_type="entity",
                value=table_name,
                confidence=0.75,
                source="behavior",
                timestamp=signal.timestamp,
            )

    if signal.type == "entity_view":
        entity_type = _meta_string(signal.meta, "entity_type") or "unknown"
        return Anchor(
            anchor_type="entity",
            value=entity_type,
            confidence=0.7,
            source="behavior",
            timestamp=signal.timestamp,
        )

    if signal.type == "entity_edit":
        entity_type = _meta_string(signal.meta, "entity_type") or "unknown"
        return Anchor(
            anchor_type="entity",
            value=entity_type,
            confidence=0.85,
            source="behavior",
            timestamp=signal.timestamp,
        )

    if signal.type == "cell_click":
        field_name = _meta_string(signal.meta, "fieldName") or _meta_string(signal.meta, "field") or ""
        return Anchor(
            anchor_type="data_point",
            value=f"cell:{field_name}" if field_name else "cell",
            confidence=0.5,
            source="behavior",
            timestamp=signal.timestamp,
        )

    if signal.type == "global_search":
        keyword = _meta_string(signal.meta, "keyword") or ""
        if keyword:
            return Anchor(
                anchor_type="search_intent",
                value=keyword,
                confidence=0.6,
                source="language",
                timestamp=signal.timestamp,
            )

    return None


def _upsert_anchor(context: WorkingContext, anchor: Anchor) -> bool:
    """Insert or replace an active anchor by anchor type."""
    anchors = [item for item in context.active_anchors if item.anchor_type != anchor.anchor_type]
    previous_anchor = next(
        (item for item in context.active_anchors if item.anchor_type == anchor.anchor_type),
        None,
    )
    anchors.insert(0, anchor)
    context.active_anchors = anchors

    if previous_anchor is None:
        return True

    return (
        previous_anchor.value != anchor.value
        or previous_anchor.confidence != anchor.confidence
        or previous_anchor.source != anchor.source
    )


def _meta_string(meta: dict[str, object], key: str) -> str | None:
    """Extract a string value from signal metadata."""
    value = meta.get(key)
    return value if isinstance(value, str) and value else None


def _meta_int(meta: dict[str, object], key: str) -> int | None:
    """Extract an integer value from signal metadata."""
    value = meta.get(key)
    return value if isinstance(value, int) else None
