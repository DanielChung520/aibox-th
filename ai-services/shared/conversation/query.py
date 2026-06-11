"""
Query engine for platform-agnostic conversation storage.

Provides unified query interface that merges hot (ArangoDB) and cold (S3) data.
"""

import os
from datetime import datetime
from typing import Any

import httpx

from .models import Platform


class QueryEngine:
    """
    Query engine that transparently merges hot (ArangoDB) and cold (S3) data.

    Currently queries ArangoDB only. S3 integration is planned for cold tier.
    """

    def __init__(self):
        self._arango_url = os.getenv("ARANGO_URL", "http://localhost:8529")
        self._arango_db = os.getenv("ARANGO_DATABASE", "abc_desktop")
        self._arango_user = os.getenv("ARANGO_USER", "root")
        self._arango_password = os.getenv("ARANGO_PASSWORD", "")
        self._collection = "bot_chat_sessions"

    def _auth(self) -> tuple[str, str]:
        return (self._arango_user, self._arango_password)

    async def get_history(
        self,
        session_id: str,
        limit: int = 20,
        include_metadata: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Get conversation history for a session.

        Args:
            session_id: The session identifier.
            limit: Maximum number of messages to return.
            include_metadata: Whether to include metadata in results.

        Returns:
            List of messages in chronological order (oldest first).
            Each message has "role" and "content" keys (OpenAI-compatible).
        """
        # Support both exact session_id and channel_id prefix match
        # session_id format: "line:{channel_id}:{user_id}"
        # For channel-level history, also match all sessions for that channel_id
        has_colon = ":" in session_id
        bind_vars = {"session_id": session_id, "limit": limit}

        if not has_colon:
            # Channel-level query: match all sessions for this channel
            aql = f"""
            FOR doc IN {self._collection}
            FILTER doc.session_id LIKE @session_pattern
            SORT doc.created_at ASC
            LIMIT @limit
            RETURN doc
            """
            bind_vars = {"session_pattern": f"%{session_id}%", "limit": limit}
        else:
            # Exact session match
            aql = """
            FOR doc IN {collection}
            FILTER doc.session_id == @session_id
            SORT doc.created_at ASC
            LIMIT @limit
            RETURN doc
            """.format(collection=self._collection)

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._arango_url}/_db/{self._arango_db}/_api/cursor",
                json={"query": aql, "bindVars": bind_vars},
                auth=self._auth(),
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("result", [])

            messages = []
            for m in results:
                stored_role = m.get("role", "assistant")
                msg = {
                    "role": stored_role,
                    "content": m.get("message", ""),
                }
                if include_metadata:
                    msg["metadata"] = m.get("metadata", {})
                    msg["created_at"] = m.get("created_at")
                messages.append(msg)

            return messages

    async def get_history_by_platform(
        self,
        platform: str | Platform,
        channel_id: str | None = None,
        limit: int = 100,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get conversation history filtered by platform.

        Args:
            platform: Messaging platform (line, whatsapp, etc.).
            channel_id: Optional channel identifier to filter by.
            limit: Maximum number of messages to return.
            since: Optional start time filter.

        Returns:
            List of messages in reverse chronological order.
        """
        if isinstance(platform, Platform):
            platform = platform.value

        # Build AQL query
        aql = """
        FOR doc IN {collection}
        FILTER doc.platform == @platform
        """.format(collection=self._collection)

        bind_vars: dict[str, Any] = {"platform": platform, "limit": limit}

        if channel_id:
            aql += """
        AND doc.session_id LIKE @channel_pattern
            """
            bind_vars["channel_pattern"] = f"%{channel_id}%"

        if since:
            aql += """
        AND doc.created_at >= @since
            """
            bind_vars["since"] = since.isoformat()

        aql += """
        SORT doc.created_at DESC
        LIMIT @limit
        RETURN doc
        """

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._arango_url}/_db/{self._arango_db}/_api/cursor",
                json={"query": aql, "bindVars": bind_vars},
                auth=self._auth(),
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", [])

    async def get_sessions_by_platform(
        self,
        platform: str | Platform,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get all sessions for a platform with their message counts.

        Args:
            platform: Messaging platform.
            limit: Maximum number of sessions to return.

        Returns:
            List of session summaries.
        """
        if isinstance(platform, Platform):
            platform = platform.value

        aql = """
        FOR doc IN {collection}
        FILTER doc.platform == @platform
        COLLECT session_id = doc.session_id
        AGGREGATE message_count = LENGTH(doc), first_msg = MIN(doc.created_at), last_msg = MAX(doc.created_at)
        SORT last_msg DESC
        LIMIT @limit
        RETURN {{
            "session_id": session_id,
            "platform": @platform,
            "message_count": message_count,
            "first_message_at": first_msg,
            "last_message_at": last_msg
        }}
        """.format(collection=self._collection)

        bind_vars = {"platform": platform, "limit": limit}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._arango_url}/_db/{self._arango_db}/_api/cursor",
                json={"query": aql, "bindVars": bind_vars},
                auth=self._auth(),
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", [])

    async def count_messages(
        self,
        session_id: str | None = None,
        platform: str | None = None,
        older_than: datetime | None = None,
    ) -> int:
        """
        Count messages matching the given filters.

        Args:
            session_id: Optional session filter.
            platform: Optional platform filter.
            older_than: Optional timestamp filter (for archiving).

        Returns:
            Number of matching messages.
        """
        aql = "RETURN COUNT(FOR doc IN {collection}".format(collection=self._collection)
        bind_vars: dict[str, Any] = {}

        conditions = []

        if session_id:
            conditions.append("doc.session_id == @session_id")
            bind_vars["session_id"] = session_id

        if platform:
            conditions.append("doc.platform == @platform")
            bind_vars["platform"] = platform

        if older_than:
            conditions.append("doc.created_at < @older_than")
            bind_vars["older_than"] = older_than.isoformat()

        if conditions:
            aql += " FILTER " + " AND ".join(conditions)

        aql += " RETURN 1)"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._arango_url}/_db/{self._arango_db}/_api/cursor",
                json={"query": aql, "bindVars": bind_vars},
                auth=self._auth(),
            )
            resp.raise_for_status()
            data = resp.json()
            return data["result"][0] if data.get("result") else 0
