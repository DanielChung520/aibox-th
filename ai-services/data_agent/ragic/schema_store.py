"""
@file        schema_store.py
@description Qdrant-backed store for Ragic table schemas.
             Supports upsert, search (by vector similarity), list, and delete.
@lastUpdate  2026-04-11 17:12:44
@author      Daniel Chung
@version     1.1.0
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import TYPE_CHECKING

import httpx

from data_agent.ragic.models import RagicFieldSchema, RagicTableSchema

if TYPE_CHECKING:
    from data_agent.ragic.models_phase9 import ParsedTable

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
COLLECTION_NAME = "ragic_schemas"


async def _get_embedding_model() -> str:
    from data_agent.config_reader import get_param

    return await get_param("da.embedding_model")


async def _get_embedding_dim() -> int:
    from data_agent.config_reader import get_param

    raw = await get_param("da.embedding_dimension")
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 1024


async def _embed_text(text: str) -> list[float]:
    model = await _get_embedding_model()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": model, "input": text},
        )
        resp.raise_for_status()
        embeddings = resp.json().get("embeddings", [])
        if embeddings and len(embeddings) > 0:
            return list(embeddings[0])
        return []


def _schema_to_embed_text(schema: RagicTableSchema) -> str:
    """Build a searchable text representation of a table schema."""
    parts = [schema.table_name, schema.description]
    for field_id, field in schema.fields.items():
        parts.append(f"{field.name}({field_id})")
        if field.description:
            parts.append(field.description)
        for alias in field.business_aliases:
            parts.append(alias)
    return " ".join(p for p in parts if p)


def _deterministic_point_id(seed: str) -> int:
    """Produce a stable positive int64 from a string seed (for Qdrant point id)."""
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return int(digest[:15], 16)


class RagicSchemaStore:
    """CRUD operations for Ragic table schemas in Qdrant."""

    def __init__(
        self,
        qdrant_url: str | None = None,
        collection: str = COLLECTION_NAME,
    ) -> None:
        self._url = qdrant_url or QDRANT_URL
        self._collection = collection

    async def ensure_collection(self) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self._url}/collections/{self._collection}"
            )
            if resp.status_code == 200:
                return
            dim = await _get_embedding_dim()
            await client.put(
                f"{self._url}/collections/{self._collection}",
                json={
                    "vectors": {"size": dim, "distance": "Cosine"},
                    "optimizers_config": {"indexing_threshold": 10000},
                },
            )
            logger.info(
                "Created Qdrant collection '%s' (dim=%d)",
                self._collection,
                dim,
            )

    async def upsert(self, schemas: list[RagicTableSchema]) -> int:
        """Embed and upsert schemas into Qdrant. Returns count of upserted."""
        if not schemas:
            return 0
        await self.ensure_collection()
        points: list[dict[str, object]] = []
        for schema in schemas:
            embed_text = _schema_to_embed_text(schema)
            vector = await _embed_text(embed_text)
            if not vector:
                logger.warning("Empty embedding for %s, skipping", schema.table_key)
                continue
            point_id = _deterministic_point_id(schema.point_id_seed)
            fields_payload: dict[str, object] = {
                fid: fschema.model_dump() for fid, fschema in schema.fields.items()
            }
            payload: dict[str, object] = {
                "account": schema.account,
                "table_key": schema.table_key,
                "table_name": schema.table_name,
                "tab_path": schema.tab_path,
                "sheet_index": schema.sheet_index,
                "description": schema.description,
                "module": schema.module,
                "version": schema.version,
                "fields": fields_payload,
                "subtables": schema.subtables,
            }
            points.append({"id": point_id, "vector": vector, "payload": payload})

        if not points:
            return 0

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.put(
                f"{self._url}/collections/{self._collection}/points",
                json={"points": points},
            )
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Qdrant upsert failed: {resp.status_code} {resp.text}"
                )

        logger.info("Upserted %d schemas into '%s'", len(points), self._collection)
        return len(points)

    async def search(
        self,
        query: str,
        account: str | None = None,
        top_k: int = 5,
        score_threshold: float = 0.3,
    ) -> list[dict[str, object]]:
        """Vector-search schemas by natural language query."""
        vector = await _embed_text(query)
        if not vector:
            return []
        body: dict[str, object] = {"vector": vector, "limit": top_k, "with_payload": True}
        if account:
            body["filter"] = {"must": [{"key": "account", "match": {"value": account}}]}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._url}/collections/{self._collection}/points/search",
                json=body,
            )
            resp.raise_for_status()
        raw_results: list[dict[str, object]] = resp.json().get("result", [])
        filtered: list[dict[str, object]] = []
        for hit in raw_results:
            raw_score = hit.get("score", 0.0)
            score = float(raw_score) if isinstance(raw_score, (int, float)) else 0.0
            if score >= score_threshold:
                filtered.append(hit)
        return filtered

    async def list_all(
        self, account: str | None = None, limit: int = 100
    ) -> list[dict[str, object]]:
        """List all schemas (optionally filtered by account)."""
        body: dict[str, object] = {"limit": limit, "with_payload": True}
        if account:
            body["filter"] = {"must": [{"key": "account", "match": {"value": account}}]}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._url}/collections/{self._collection}/points/scroll",
                json=body,
            )
            if resp.status_code >= 400:
                return []
        result: dict[str, object] = resp.json().get("result", {})
        if isinstance(result, dict):
            points = result.get("points", [])
            if isinstance(points, list):
                return points
        return []

    async def delete_by_account(self, account: str) -> None:
        """Delete all schema points for a given account."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                f"{self._url}/collections/{self._collection}/points/delete",
                json={
                    "filter": {
                        "must": [{"key": "account", "match": {"value": account}}]
                    }
                },
            )
        logger.info("Deleted schemas for account '%s'", account)

    async def delete_by_table_key(self, account: str, table_key: str) -> None:
        """Delete a specific schema point by account + table_key."""
        point_id = _deterministic_point_id(
            f"{account}_{table_key.replace('/', '_')}"
        )
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(
                f"{self._url}/collections/{self._collection}/points/delete",
                json={"points": [point_id]},
            )

    async def count(self) -> int:
        """Return total number of schema points in the collection."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._url}/collections/{self._collection}/points/count",
                json={},
            )
            if resp.status_code == 200:
                result: dict[str, object] = resp.json().get("result", {})
                raw_count = result.get("count", 0)
                if isinstance(raw_count, (int, float)):
                    return int(raw_count)
        return 0

    async def bulk_upsert_from_parsed(
        self,
        tables: list[ParsedTable],
        account: str,
        batch_size: int = 20,
    ) -> int:
        """Convert ParsedTable list to RagicTableSchema and upsert in batches."""
        from data_agent.ragic.schema_converter import convert_parsed_tables

        schemas = convert_parsed_tables(tables, account)
        if not schemas:
            return 0

        total = 0
        for i in range(0, len(schemas), batch_size):
            batch = schemas[i : i + batch_size]
            count = await self.upsert(batch)
            total += count
        return total

    @staticmethod
    def payload_to_schema(payload: dict[str, object]) -> RagicTableSchema:
        """Reconstruct RagicTableSchema from Qdrant payload dict."""
        fields_raw = payload.get("fields", {})
        fields: dict[str, RagicFieldSchema] = {}
        if isinstance(fields_raw, dict):
            for fid, fdata in fields_raw.items():
                if isinstance(fdata, dict):
                    fields[fid] = RagicFieldSchema(**fdata)
        subtables_raw = payload.get("subtables", {})
        subtables: dict[str, str] = (
            {k: str(v) for k, v in subtables_raw.items()}
            if isinstance(subtables_raw, dict) else {}
        )
        sheet_raw = payload.get("sheet_index", 0)
        sheet_idx = int(sheet_raw) if isinstance(sheet_raw, (int, float)) else 0
        return RagicTableSchema(
            account=str(payload.get("account", "")),
            table_key=str(payload.get("table_key", "")),
            table_name=str(payload.get("table_name", "")),
            tab_path=str(payload.get("tab_path", "")),
            sheet_index=sheet_idx,
            description=str(payload.get("description", "")),
            module=str(payload.get("module", "")),
            version=str(payload.get("version", "")),
            fields=fields,
            subtables=subtables,
        )
