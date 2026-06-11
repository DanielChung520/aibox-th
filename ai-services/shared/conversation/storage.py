"""
Conversation storage layer.

Handles writing messages to the hot tier (ArangoDB) and provides
a unified interface for all platforms.
"""

import os
from datetime import datetime, timezone
from typing import Any

import httpx

from .models import ArchiveConfig, ConversationMessage, Platform


class ConversationStorage:
    """
    Platform-agnostic conversation storage.

    Writes to ArangoDB (hot tier). Cold tier (S3) is handled by the Archiver.
    """

    def __init__(self, config: ArchiveConfig | None = None):
        self.config = config or ArchiveConfig()
        self._arango_url = os.getenv("ARANGO_URL", "http://localhost:8529")
        self._arango_db = os.getenv("ARANGODB_DATABASE", "abc_desktop")
        self._arango_user = os.getenv("ARANGO_USER", "root")
        self._arango_password = os.getenv("ARANGO_PASSWORD", "")
        self._collection = "bot_chat_sessions"

    def _auth(self) -> tuple[str, str]:
        return (self._arango_user, self._arango_password)

    async def upsert_session_group_name(
        self,
        session_id: str,
        group_name: str,
        platform: str = "line",
    ) -> None:
        doc_key = self._session_meta_key(session_id)
        doc = {
            "_key": doc_key,
            "session_id": session_id,
            "platform": platform,
            "group_name": group_name,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                r = await client.patch(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/document/bot_session_metadata/{doc_key}",
                    json=doc,
                    auth=self._auth(),
                )
                if r.status_code == 404:
                    r = await client.post(
                        f"{self._arango_url}/_db/{self._arango_db}/_api/document/bot_session_metadata",
                        json=doc,
                        auth=self._auth(),
                    )
            except Exception:
                pass

    async def get_session_group_name(self, session_id: str) -> str | None:
        """
        Get cached session group_name if refreshed within 24 hours.
        Returns None if no cached name or cache is stale.
        """
        doc_key = self._session_meta_key(session_id)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/document/bot_session_metadata/{doc_key}",
                    auth=self._auth(),
                )
                if resp.status_code != 200:
                    return None
                doc = resp.json()
                refreshed_str = doc.get("refreshed_at", "")
                if not refreshed_str:
                    return None
                refreshed = datetime.fromisoformat(refreshed_str.replace("Z", "+00:00"))
                age_hours = (datetime.now(timezone.utc) - refreshed).total_seconds() / 3600
                if age_hours > 24:
                    return None
                name = doc.get("group_name", "")
                return name if name and name != doc.get("session_id", "") else None
            except Exception:
                return None

    async def get_greeting_responded_at(self, session_id: str) -> str | None:
        doc_key = self._session_meta_key(session_id)
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/document/bot_session_metadata/{doc_key}",
                    auth=self._auth(),
                )
                if resp.status_code != 200:
                    return None
                return resp.json().get("greeting_responded_at")
            except Exception:
                return None

    async def set_greeting_responded_at(self, session_id: str, date_str: str) -> None:
        doc_key = self._session_meta_key(session_id)
        doc = {
            "_key": doc_key,
            "session_id": session_id,
            "greeting_responded_at": date_str,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                r = await client.patch(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/document/bot_session_metadata/{doc_key}",
                    json=doc,
                    auth=self._auth(),
                )
                if r.status_code == 404:
                    await client.post(
                        f"{self._arango_url}/_db/{self._arango_db}/_api/document/bot_session_metadata",
                        json=doc,
                        auth=self._auth(),
                    )
            except Exception:
                pass

    @staticmethod
    def _session_meta_key(session_id: str) -> str:
        import hashlib
        return hashlib.sha256(session_id.encode()).hexdigest()[:32]

    async def save_message(
        self,
        session_id: str,
        platform: str | Platform,
        role: str,
        message: str,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> str:
        """
        Save a single message to the hot tier (ArangoDB).

        Args:
            session_id: Unique session identifier.
            platform: Messaging platform.
            role: Sender role ("user" or "assistant").
            message: Message content.
            metadata: Optional platform-specific metadata.
            created_at: Override creation time (default: now).

        Returns:
            The document key of the saved message.
        """
        if isinstance(platform, Platform):
            platform = platform.value

        doc = {
            "session_id": session_id,
            "platform": platform,
            "role": role,
            "message": message,
            "metadata": metadata or {},
            "created_at": (created_at or datetime.now(timezone.utc)).isoformat(),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._arango_url}/_db/{self._arango_db}/_api/document/{self._collection}",
                json=doc,
                auth=self._auth(),
            )
            resp.raise_for_status()
            result = resp.json()
            return result["_key"]

    async def save_messages_batch(self, messages: list[ConversationMessage]) -> list[str]:
        """
        Save multiple messages in a single request.

        Args:
            messages: List of ConversationMessage objects.

        Returns:
            List of document keys for the saved messages.
        """
        docs = [
            {
                "session_id": msg.session_id,
                "platform": msg.platform.value if isinstance(msg.platform, Platform) else msg.platform,
                "role": msg.role,
                "message": msg.message,
                "metadata": msg.metadata,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ]

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._arango_url}/_db/{self._arango_db}/_api/document/{self._collection}",
                json=docs,
                auth=self._auth(),
            )
            resp.raise_for_status()
            results = resp.json()
            return [r["_key"] for r in results]

    async def ensure_collection(self) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._arango_url}/_db/{self._arango_db}/_api/collection/{self._collection}",
                auth=self._auth(),
            )
            if resp.status_code == 200:
                return

            if resp.status_code == 404:
                create_resp = await client.post(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/collection",
                    json={"name": self._collection},
                    auth=self._auth(),
                )
                create_resp.raise_for_status()

                collection_url = f"{self._arango_url}/_db/{self._arango_db}/_api/index/{self._collection}"
                await client.post(
                    collection_url,
                    json={"type": "persistent", "fields": ["session_id", "created_at"]},
                    auth=self._auth(),
                )
                await client.post(
                    collection_url,
                    json={"type": "persistent", "fields": ["platform"]},
                    auth=self._auth(),
                )
                return

            resp.raise_for_status()

    async def ensure_session_metadata_collection(self) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._arango_url}/_db/{self._arango_db}/_api/collection/bot_session_metadata",
                auth=self._auth(),
            )
            if resp.status_code == 200:
                return

            if resp.status_code == 404:
                create_resp = await client.post(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/collection",
                    json={"name": "bot_session_metadata"},
                    auth=self._auth(),
                )
                create_resp.raise_for_status()
                idx_url = f"{self._arango_url}/_db/{self._arango_db}/_api/index/bot_session_metadata"
                await client.post(
                    idx_url,
                    json={"type": "persistent", "fields": ["session_id"]},
                    auth=self._auth(),
                )
                return

            resp.raise_for_status()
