#!/usr/bin/env python3
"""
Migrate line_chat_sessions to bot_chat_sessions.

Usage:
    python -m shared.conversation.migrate --dry-run  # Preview
    python -m shared.conversation.migrate --execute  # Execute migration
"""

import argparse
import asyncio
import os
import sys

import httpx

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGODB_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")

OLD_COLLECTION = "line_chat_sessions"
NEW_COLLECTION = "bot_chat_sessions"


def auth():
    return (ARANGO_USER, ARANGO_PASSWORD)


async def collection_exists(name: str) -> bool:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/collection/{name}",
            auth=auth(),
        )
        return resp.status_code == 200


async def create_collection(name: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/collection",
            json={"name": name},
            auth=auth(),
        )
        resp.raise_for_status()


async def create_indexes(name: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        base = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/index/{name}"
        await client.post(base, json={"type": "persistent", "fields": ["session_id", "created_at"]}, auth=auth())
        await client.post(base, json={"type": "persistent", "fields": ["platform"]}, auth=auth())


async def count_documents(collection: str) -> int:
    aql = f"RETURN COUNT(FOR doc IN {collection} RETURN 1)"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": aql},
            auth=auth(),
        )
        resp.raise_for_status()
        data = resp.json()
        return data["result"][0] if data.get("result") else 0


async def copy_documents(batch_size: int = 1000) -> int:
    copied = 0
    offset = 0

    while True:
        aql = f"""
        FOR doc IN {OLD_COLLECTION}
        LIMIT @offset, @batch_size
        RETURN doc
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                json={"query": aql, "bindVars": {"offset": offset, "batch_size": batch_size}},
                auth=auth(),
            )
            resp.raise_for_status()
            data = resp.json()
            docs = data.get("result", [])

            if not docs:
                break

            insert_resp = await client.post(
                f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/{NEW_COLLECTION}",
                json=docs,
                auth=auth(),
            )
            insert_resp.raise_for_status()
            copied += len(docs)
            offset += batch_size

            if len(docs) < batch_size:
                break

    return copied


async def delete_collection(name: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.delete(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/collection/{name}",
            auth=auth(),
        )
        resp.raise_for_status()


async def main(dry_run: bool = True) -> None:
    print(f"=== Migration: {OLD_COLLECTION} -> {NEW_COLLECTION} ===")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}\n")

    old_exists = await collection_exists(OLD_COLLECTION)
    new_exists = await collection_exists(NEW_COLLECTION)

    print(f"Old collection '{OLD_COLLECTION}' exists: {old_exists}")
    print(f"New collection '{NEW_COLLECTION}' exists: {new_exists}")

    if not old_exists:
        print(f"\n❌ Old collection '{OLD_COLLECTION}' does not exist. Nothing to migrate.")
        return

    old_count = await count_documents(OLD_COLLECTION)
    print(f"Documents in old collection: {old_count}")

    if new_exists:
        new_count = await count_documents(NEW_COLLECTION)
        print(f"Documents in new collection: {new_count}")
    else:
        print("New collection does not exist yet.")

    if dry_run:
        print(f"\n🔍 [DRY RUN] Would copy {old_count} documents to '{NEW_COLLECTION}'")
        print("           Would delete old collection after verification")
    else:
        print("\n🚀 Starting migration...")

        if not new_exists:
            print(f"1. Creating collection '{NEW_COLLECTION}'...")
            await create_collection(NEW_COLLECTION)
            print("   Creating indexes...")
            await create_indexes(NEW_COLLECTION)
            print("   ✅ Collection created")
        else:
            print(f"1. Collection '{NEW_COLLECTION}' already exists, skipping creation")

        print("2. Copying documents...")
        copied = await copy_documents()
        print(f"   ✅ Copied {copied} documents")

        new_count = await count_documents(NEW_COLLECTION)
        print(f"3. Verification: {new_count} documents in new collection")

        if new_count >= old_count:
            print(f"4. Deleting old collection '{OLD_COLLECTION}'...")
            await delete_collection(OLD_COLLECTION)
            print("   ✅ Old collection deleted")
        else:
            print(f"⚠️  Verification failed: expected {old_count}, got {new_count}")
            print("   Keeping old collection for manual inspection")
            sys.exit(1)

    print("\n✅ Migration complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate conversation storage")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview only")
    parser.add_argument("--execute", action="store_true", help="Execute migration")
    args = parser.parse_args()

    if args.execute:
        asyncio.run(main(dry_run=False))
    else:
        asyncio.run(main(dry_run=True))
