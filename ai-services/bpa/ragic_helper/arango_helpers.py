"""
ArangoDB helper utilities shared across services.
"""

import os
from typing import Any

import httpx


ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGODB_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")


def arango_auth() -> tuple[str, str]:
    return (ARANGO_USER, ARANGO_PASSWORD)


async def get_doc(collection: str, key: str) -> dict[str, Any] | None:
    aql = f"FOR doc IN {collection} FILTER doc._key == @key LIMIT 1 RETURN doc"
    bind_vars = {"key": key}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": aql, "bindVars": bind_vars},
            auth=arango_auth(),
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            results = data.get("result", [])
            if results:
                return results[0]
    return None


async def query_one(
    collection: str, filter_aql: str, bind_vars: dict[str, Any]
) -> dict[str, Any] | None:
    aql = f"FOR doc IN {collection} FILTER {filter_aql} LIMIT 1 RETURN doc"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": aql, "bindVars": bind_vars},
            auth=arango_auth(),
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            results = data.get("result", [])
            if results:
                return results[0]
    return None
