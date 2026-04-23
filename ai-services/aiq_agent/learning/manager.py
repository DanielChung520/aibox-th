"""
@file        Learning Layer Manager
@description 管理 AIQ Learning Layer 的 UserProfileSummary 讀寫與 turn-complete 更新流程。
@lastUpdate  2026-04-18 20:12:44
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import os
import re
import threading
import time

import httpx

from aiq_agent.learning.models import Pattern, QueryPatterns, TurnCompleteRequest, UserProfileSummary

USER_PROFILES_COLLECTION = "user_profiles"
MAX_PATTERN_COUNT = 50
MAX_FREQUENT_INTENTS = 10
_USER_KEY_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


class LearningManager:
    """Manage AIQ user learning summaries backed by ArangoDB."""

    def __init__(self) -> None:
        """Initialize ArangoDB client configuration for the learning layer."""
        self._arango_url = os.environ.get("ARANGO_URL", "http://localhost:8529").rstrip("/")
        self._arango_db = os.environ.get("ARANGO_DB", "abc_desktop")
        self._arango_user = os.environ.get("ARANGO_USER", "root")
        self._arango_password = os.environ.get("ARANGO_PASSWORD", "")
        self._client: httpx.AsyncClient | None = None
        self._client_lock = threading.Lock()

    async def get_profile(self, user_key: str) -> UserProfileSummary:
        """Return the persisted profile for a user, or an empty profile if absent."""
        _validate_user_key(user_key)
        response = await self._get_client().get(self._document_path(user_key))
        if response.status_code == httpx.codes.NOT_FOUND:
            return _empty_profile(user_key)

        response.raise_for_status()
        payload = _extract_profile_payload(response, user_key)
        return UserProfileSummary.model_validate(payload)

    async def update_profile(
        self,
        user_key: str,
        profile: UserProfileSummary,
    ) -> UserProfileSummary:
        """Upsert a user profile into ArangoDB and return the stored summary."""
        _validate_user_key(user_key)
        profile_to_store = profile.model_copy(update={"user_key": user_key}, deep=True)
        payload = _profile_to_document(profile_to_store)
        response = await self._get_client().put(
            self._document_path(user_key),
            params={"overwrite": "true"},
            json=payload,
        )
        response.raise_for_status()
        return profile_to_store

    async def process_turn_complete(
        self,
        user_key: str,
        request: TurnCompleteRequest,
    ) -> UserProfileSummary:
        """Update profile statistics based on a completed AIQ turn."""
        profile = await self.get_profile(user_key)
        updated_profile = profile.model_copy(deep=True)

        updated_profile.last_updated = int(time.time())
        updated_profile.total_turns = updated_profile.total_turns + 1

        updated_profile.domain_counts = _update_domain_counts(
            updated_profile.domain_counts,
            request.domain,
        )
        updated_profile.domain_distribution = _normalize_distribution(
            updated_profile.domain_counts,
        )
        updated_profile.query_patterns = _update_query_patterns(
            updated_profile.query_patterns,
            request.execution_path,
            request.clarification_rounds,
            updated_profile.total_turns - 1,
        )

        is_success = request.outcome == "success"
        target_patterns = (
            updated_profile.success_patterns if is_success else updated_profile.failure_patterns
        )
        updated_patterns = _update_patterns(
            target_patterns,
            context_signature=request.context_signature,
            execution_path=request.execution_path,
            success_observation=1.0 if is_success else 0.0,
        )

        if is_success:
            updated_profile.success_patterns = updated_patterns
        else:
            updated_profile.failure_patterns = updated_patterns

        return await self.update_profile(user_key, updated_profile)

    async def close(self) -> None:
        """Close the shared httpx client if it has been initialized."""
        client = self._client
        self._client = None
        if client is not None:
            await client.aclose()

    def _get_client(self) -> httpx.AsyncClient:
        """Lazily build the shared AsyncClient used for ArangoDB requests."""
        client = self._client
        if client is not None:
            return client

        with self._client_lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    base_url=f"{self._arango_url}/_db/{self._arango_db}/_api",
                    auth=httpx.BasicAuth(self._arango_user, self._arango_password),
                    timeout=10.0,
                )
            return self._client

    def _document_path(self, user_key: str) -> str:
        """Return the ArangoDB document API path for the target user profile."""
        return f"/document/{USER_PROFILES_COLLECTION}/{user_key}"


def _empty_profile(user_key: str) -> UserProfileSummary:
    return UserProfileSummary(
        user_key=user_key,
        last_updated=int(time.time()),
    )


def _extract_profile_payload(response: httpx.Response, user_key: str) -> dict[str, object]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("ArangoDB user profile response must be a JSON object.")

    document = {str(key): value for key, value in payload.items()}
    document.pop("_id", None)
    document.pop("_rev", None)
    document.pop("_oldRev", None)
    document["user_key"] = user_key
    return document


def _profile_to_document(profile: UserProfileSummary) -> dict[str, object]:
    return {
        "_key": profile.user_key,
        "user_key": profile.user_key,
        "last_updated": profile.last_updated,
        "total_turns": profile.total_turns,
        "domain_counts": dict(profile.domain_counts),
        "domain_distribution": dict(profile.domain_distribution),
        "query_patterns": {
            "frequent_intents": list(profile.query_patterns.frequent_intents),
            "avg_clarification_rounds": profile.query_patterns.avg_clarification_rounds,
            "preferred_response_depth": profile.query_patterns.preferred_response_depth,
        },
        "success_patterns": [_pattern_to_document(pattern) for pattern in profile.success_patterns],
        "failure_patterns": [_pattern_to_document(pattern) for pattern in profile.failure_patterns],
    }


def _pattern_to_document(pattern: Pattern) -> dict[str, object]:
    return {
        "context_signature": pattern.context_signature,
        "execution_path": pattern.execution_path,
        "success_rate": pattern.success_rate,
        "sample_count": pattern.sample_count,
    }


def _validate_user_key(user_key: str) -> None:
    """Validate user_key format to prevent ArangoDB path injection."""
    if not _USER_KEY_RE.match(user_key):
        raise ValueError(f"Invalid user_key format: {user_key!r}")


def _update_domain_counts(
    domain_counts: dict[str, int],
    domain: str,
) -> dict[str, int]:
    """Increment the raw count for the given domain."""
    if not domain:
        return dict(domain_counts)
    counts = dict(domain_counts)
    counts[domain] = counts.get(domain, 0) + 1
    return counts


def _normalize_distribution(
    domain_counts: dict[str, int],
) -> dict[str, float]:
    """Normalize raw domain counts into a probability distribution."""
    total = sum(domain_counts.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in domain_counts.items()}


def _update_query_patterns(
    query_patterns: QueryPatterns,
    execution_path: str,
    clarification_rounds: int,
    total_turns: int,
) -> QueryPatterns:
    frequent_intents = [
        intent
        for intent in query_patterns.frequent_intents
        if intent != execution_path
    ]
    if execution_path:
        frequent_intents.insert(0, execution_path)
    frequent_intents = frequent_intents[:MAX_FREQUENT_INTENTS]

    next_turn_count = total_turns + 1
    avg_clarification_rounds = (
        (query_patterns.avg_clarification_rounds * total_turns) + clarification_rounds
    ) / next_turn_count

    return QueryPatterns(
        frequent_intents=frequent_intents,
        avg_clarification_rounds=avg_clarification_rounds,
        preferred_response_depth=query_patterns.preferred_response_depth,
    )


def _update_patterns(
    patterns: list[Pattern],
    *,
    context_signature: str,
    execution_path: str,
    success_observation: float,
) -> list[Pattern]:
    updated_patterns = [pattern.model_copy(deep=True) for pattern in patterns]

    for index, pattern in enumerate(updated_patterns):
        if (
            pattern.context_signature == context_signature
            and pattern.execution_path == execution_path
        ):
            next_sample_count = pattern.sample_count + 1
            next_success_rate = (
                (pattern.success_rate * pattern.sample_count) + success_observation
            ) / next_sample_count
            updated_patterns[index] = pattern.model_copy(
                update={
                    "sample_count": next_sample_count,
                    "success_rate": next_success_rate,
                }
            )
            break
    else:
        updated_patterns.append(
            Pattern(
                context_signature=context_signature,
                execution_path=execution_path,
                success_rate=success_observation,
                sample_count=1,
            )
        )

    ranked_patterns = sorted(
        updated_patterns,
        key=lambda pattern: (pattern.sample_count, pattern.success_rate),
        reverse=True,
    )
    return ranked_patterns[:MAX_PATTERN_COUNT]



