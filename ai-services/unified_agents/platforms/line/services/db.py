import base64
import os
from datetime import datetime
from typing import Any

import httpx

ARANGO_URL = os.getenv("ARANGODB_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DB", "abc_desktop")
ARANGO_USER = os.getenv("ARANGODB_USERNAME", "root")
ARANGO_PASSWORD = os.getenv("ARANGODB_PASSWORD", "abc_desktop_2026")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://eeaapi.ent4i.com")


async def _arango_headers() -> dict[str, str]:
    credentials = base64.b64encode(f"{ARANGO_USER}:{ARANGO_PASSWORD}".encode()).decode()
    return {
        "Content-Type": "application/json",
        "Authorization": f"Basic {credentials}",
    }


async def _get_collection(name: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/collection/{name}"
        resp = await client.get(url, headers=await _arango_headers())
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


async def _create_collection(name: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/collection"
        resp = await client.post(
            url,
            headers=await _arango_headers(),
            json={"name": name},
        )
        resp.raise_for_status()
        return resp.json()


async def ensure_collections() -> None:
    for col in ["platforms_line_official_accounts", "platforms_line_channels"]:
        existing = await _get_collection(col)
        if not existing:
            await _create_collection(col)


async def list_official_accounts() -> list[dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor"
        resp = await client.post(
            url,
            headers=await _arango_headers(),
            json={
                "query": "FOR o IN platforms_line_official_accounts SORT o.created_at DESC RETURN o"
            },
        )
        resp.raise_for_status()
        result = resp.json()
        return result.get("result", [])


async def get_official_account(key: str) -> dict[str, Any] | None:
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/platforms_line_official_accounts/{key}"
        resp = await client.get(url, headers=await _arango_headers())
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


async def create_official_account(data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()
    doc = {
        **data,
        "created_at": now,
        "updated_at": now,
        "status": "active",
    }
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/platforms_line_official_accounts"
        resp = await client.post(url, headers=await _arango_headers(), json=doc)
        resp.raise_for_status()
        result = resp.json()
        return result.get("new", {})


async def update_official_account(key: str, data: dict[str, Any]) -> dict[str, Any] | None:
    patch = {**data, "updated_at": datetime.utcnow().isoformat()}
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/platforms_line_official_accounts/{key}"
        resp = await client.patch(url, headers=await _arango_headers(), json=patch)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


async def delete_official_account(key: str) -> bool:
    await delete_channels_by_account(key)
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/platforms_line_official_accounts/{key}"
        resp = await client.delete(url, headers=await _arango_headers())
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True


async def list_channels(official_account_key: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor"
        resp = await client.post(
            url,
            headers=await _arango_headers(),
            json={
                "query": "FOR c IN platforms_line_channels FILTER c.official_account_key == @key SORT c.created_at DESC RETURN c",
                "bindVars": {"key": official_account_key},
            },
        )
        resp.raise_for_status()
        result = resp.json()
        return result.get("result", [])


async def get_channel(key: str) -> dict[str, Any] | None:
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/channels/{key}"
        resp = await client.get(url, headers=await _arango_headers())
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        raw = resp.json()
        # Map from unified channels schema to legacy field names
        config = raw.get("config") or {}
        return {
            "_key": raw.get("_key", key),
            "channel_id": config.get("channel_id", ""),
            "channel_secret": config.get("channel_secret", ""),
            "channel_access_token": config.get("access_token", ""),
            "channel_name": raw.get("business_user_name", ""),
            "webhook_enabled": raw.get("status") == "active",
            "linked_agent_key": raw.get("linked_agent_key", "welfare_secretary"),
            "platform": raw.get("platform", "line"),
        }


async def create_channel(data: dict[str, Any]) -> dict[str, Any]:
    doc = {
        **data,
        "created_at": datetime.utcnow().isoformat(),
        "webhook_url": f"{PUBLIC_BASE_URL}/api/v1/webhook/line/{data.get('_key', 'unknown')}",
        "webhook_enabled": False,
        "publication_status": "unpublished",
    }
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/platforms_line_channels"
        resp = await client.post(url, headers=await _arango_headers(), json=doc)
        resp.raise_for_status()
        result = resp.json()
        return result.get("new", {})


async def update_channel(key: str, data: dict[str, Any]) -> dict[str, Any] | None:
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/platforms_line_channels/{key}"
        resp = await client.patch(url, headers=await _arango_headers(), json=data)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


async def delete_channel(key: str) -> bool:
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/platforms_line_channels/{key}"
        resp = await client.delete(url, headers=await _arango_headers())
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True


async def get_agent(key: str) -> dict[str, Any] | None:
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/agents/{key}"
        resp = await client.get(url, headers=await _arango_headers())
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


async def delete_channels_by_account(official_account_key: str) -> None:
    async with httpx.AsyncClient() as client:
        url = f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor"
        resp = await client.post(
            url,
            headers=await _arango_headers(),
            json={
                "query": "FOR c IN platforms_line_channels FILTER c.official_account_key == @key REMOVE c IN platforms_line_channels",
                "bindVars": {"key": official_account_key},
            },
        )
        resp.raise_for_status()