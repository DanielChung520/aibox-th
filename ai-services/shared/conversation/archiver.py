"""
Archive job for cold tier (S3/SeaweedFS) storage.

Moves old messages from ArangoDB (hot) to S3 Parquet (cold) based on TTL.
Designed to run as a scheduled job (e.g., daily at 2 AM).
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .models import ArchiveConfig


class Archiver:
    """
    Archives old messages from ArangoDB to S3/SeaweedFS Parquet.

    Uses DuckDB to read from S3 and write Parquet files partitioned by platform.
    """

    def __init__(self, config: ArchiveConfig | None = None):
        self.config = config or ArchiveConfig()
        self._arango_url = os.getenv("ARANGO_URL", "http://localhost:8529")
        self._arango_db = os.getenv("ARANGODB_DATABASE", "abc_desktop")
        self._arango_user = os.getenv("ARANGO_USER", "root")
        self._arango_password = os.getenv("ARANGO_PASSWORD", "")
        self._collection = "bot_chat_sessions"
        # SeaweedFS / S3 configuration
        self._s3_url = os.getenv("SEAWEEDFS_URL", "http://localhost:8888")
        self._archive_path = self.config.archive_path

    def _auth(self) -> tuple[str, str]:
        return (self._arango_user, self._arango_password)

    async def run(self, dry_run: bool = True) -> dict[str, Any]:
        """
        Run the archive job.

        Args:
            dry_run: If True, only count messages without archiving.

        Returns:
            Summary of the archive operation.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.hot_ttl_days)
        summary: dict[str, Any] = {
            "dry_run": dry_run,
            "cutoff": cutoff.isoformat(),
            "hot_ttl_days": self.config.hot_ttl_days,
            "platforms": {},
        }

        platforms = ["line", "whatsapp", "wecom", "dingtalk", "bot"]

        for platform in platforms:
            count = await self._count_old_messages(platform, cutoff)
            if count == 0:
                continue

            summary["platforms"][platform] = {
                "messages_to_archive": count,
            }

            if not dry_run:
                await self._archive_platform(platform, cutoff)
                await self._delete_old_messages(platform, cutoff)
                summary["platforms"][platform]["archived"] = True

        summary["total_messages"] = sum(
            p.get("messages_to_archive", 0) for p in summary["platforms"].values()
        )

        return summary

    async def _count_old_messages(self, platform: str, cutoff: datetime) -> int:
        """Count messages older than cutoff for a platform."""
        aql = """
        FOR doc IN {collection}
        FILTER doc.platform == @platform
        AND doc.created_at < @cutoff
        RETURN COUNT(doc)
        """.format(collection=self._collection)

        bind_vars = {"platform": platform, "cutoff": cutoff.isoformat()}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._arango_url}/_db/{self._arango_db}/_api/cursor",
                json={"query": aql, "bindVars": bind_vars},
                auth=self._auth(),
            )
            resp.raise_for_status()
            data = resp.json()
            return data["result"][0] if data.get("result") else 0

    async def _fetch_old_messages(
        self, platform: str, cutoff: datetime, batch_size: int = 1000
    ) -> list[dict[str, Any]]:
        """
        Fetch old messages for a platform in batches.

        Returns up to `batch_size` messages.
        """
        aql = """
        FOR doc IN {collection}
        FILTER doc.platform == @platform
        AND doc.created_at < @cutoff
        SORT doc.created_at ASC
        LIMIT @batch_size
        RETURN doc
        """.format(collection=self._collection)

        bind_vars = {
            "platform": platform,
            "cutoff": cutoff.isoformat(),
            "batch_size": batch_size,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._arango_url}/_db/{self._arango_db}/_api/cursor",
                json={"query": aql, "bindVars": bind_vars},
                auth=self._auth(),
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", [])

    async def _archive_platform(self, platform: str, cutoff: datetime) -> None:
        """
        Archive messages for a platform to S3 Parquet.

        Uses DuckDB to write Parquet files partitioned by date.
        """
        # Fetch messages in batches
        all_messages: list[dict[str, Any]] = []
        batch_size = 1000

        while True:
            batch = await self._fetch_old_messages(platform, cutoff, batch_size)
            if not batch:
                break
            all_messages.extend(batch)

        if not all_messages:
            return

        # Build parquet data using DuckDB
        await self._write_parquet(platform, all_messages)

    async def _write_parquet(self, platform: str, messages: list[dict[str, Any]]) -> None:
        """
        Write messages to S3 as Parquet file using DuckDB.

        This is a placeholder - actual implementation would use:
        1. duckdb.connect() with S3 credentials
        2. CREATE TABLE FROM messages
        3. COPY TO S3 Parquet format

        For now, we'll use a simpler approach with SeaweedFS direct upload.
        """
        import json
        from datetime import datetime

        # Create archive directory structure: {archive_path}/{platform}/{date}/
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dir_path = f"{self._archive_path}/{platform}/{date_str}"

        # Ensure directory exists (SeaweedFS creates on write)
        # Convert messages to JSON lines format for storage
        file_name = f"{platform}_{date_str}_{len(messages)}.jsonl"
        full_path = f"{dir_path}/{file_name}"

        jsonl_content = "\n".join(json.dumps(msg) for msg in messages)

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Upload as JSON Lines (simpler than Parquet for now)
            resp = await client.post(
                f"{self._s3_url}{full_path}",
                content=jsonl_content.encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()

    async def _delete_old_messages(self, platform: str, cutoff: datetime) -> int:
        """
        Delete archived messages from ArangoDB.

        Returns:
            Number of deleted messages.
        """
        aql = """
        FOR doc IN {collection}
        FILTER doc.platform == @platform
        AND doc.created_at < @cutoff
        REMOVE doc IN {collection}
        RETURN doc._key
        """.format(collection=self._collection)

        bind_vars = {"platform": platform, "cutoff": cutoff.isoformat()}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._arango_url}/_db/{self._arango_db}/_api/cursor",
                json={"query": aql, "bindVars": bind_vars},
                auth=self._auth(),
            )
            resp.raise_for_status()
            data = resp.json()
            return len(data.get("result", []))


async def run_archive_job(dry_run: bool = True) -> dict[str, Any]:
    """
    Convenience function to run the archive job.

    Usage:
        from shared.conversation.archiver import run_archive_job
        result = await run_archive_job(dry_run=False)
    """
    archiver = Archiver()
    return await archiver.run(dry_run=dry_run)


if __name__ == "__main__":
    # CLI entry point
    import sys

    dry_run = "--no-dry-run" not in sys.argv

    result = asyncio.run(run_archive_job(dry_run=dry_run))
    print(f"Archive job result: {result}")
