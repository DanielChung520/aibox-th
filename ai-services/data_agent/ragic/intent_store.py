"""
@file        intent_store.py
@description Qdrant-backed vector store for data query intents.
             Supports upsert, search (by vector similarity), list, and delete.
@lastUpdate  2026-04-13 01:43:49
@author      Daniel Chung
@version     1.2.0
"""

import hashlib
import logging
import os

import httpx

from data_agent.ragic.models import RagicIntent

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
COLLECTION_NAME = "data_agent_intents"


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


def _intent_to_embed_text(intent: RagicIntent) -> str:
    """Combine nl_patterns + description into searchable text for embedding."""
    parts = list(intent.nl_patterns)
    if intent.description:
        parts.append(intent.description)
    parts.append(intent.intent_id.replace("_", " "))
    return " ".join(parts)


def _deterministic_point_id(seed: str) -> int:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return int(digest[:15], 16)


class IntentVectorStore:
    """CRUD operations for Ragic query intents in Qdrant."""

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

    async def upsert(self, intents: list[RagicIntent]) -> int:
        if not intents:
            return 0

        await self.ensure_collection()

        points: list[dict[str, object]] = []
        for intent in intents:
            embed_text = _intent_to_embed_text(intent)
            vector = await _embed_text(embed_text)
            if not vector:
                logger.warning(
                    "Empty embedding for %s, skipping", intent.intent_id
                )
                continue

            point_id = _deterministic_point_id(intent.point_id_seed)

            filter_payload: dict[str, str] | None = None
            if intent.filter_template:
                filter_payload = {
                    "field_id": intent.filter_template.field_id,
                    "operator": intent.filter_template.operator.value,
                    "value": intent.filter_template.value,
                }

            payload: dict[str, object] = {
                "account": intent.account,
                "agent_scope": intent.agent_scope,
                "intent_id": intent.intent_id,
                "name": intent.name,
                "nl_patterns": intent.nl_patterns,
                "nl_examples": intent.nl_examples,
                "description": intent.description,
                "action": intent.action,
                "table_key": intent.table_key,
                "table_id": intent.table_id,
                "sheet_key": intent.sheet_key,
                "tables": intent.tables,
                "group": intent.group,
                "core_fields": intent.core_fields,
                "filter_template": filter_payload,
                "api_template": intent.api_template,
                "query_type": intent.query_type,
                "tool_schema": intent.tool_schema,
                "involved_tables": intent.involved_tables,
                "join_keys": [jk.model_dump() for jk in intent.join_keys],
                "generation_strategy": intent.generation_strategy,
            }

            points.append({
                "id": point_id,
                "vector": vector,
                "payload": payload,
            })

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

        logger.info("Upserted %d intents into '%s'", len(points), self._collection)
        return len(points)

    async def search(
        self,
        query: str,
        account: str | None = None,
        top_k: int = 5,
        score_threshold: float = 0.3,
    ) -> list[dict[str, object]]:
        vector = await _embed_text(query)
        if not vector:
            return []

        body: dict[str, object] = {
            "vector": vector,
            "limit": top_k,
            "with_payload": True,
        }

        if account:
            body["filter"] = {
                "must": [{"key": "account", "match": {"value": account}}]
            }

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
            if score < score_threshold:
                continue
            filtered.append(hit)
        return filtered

    async def list_all(
        self, account: str | None = None, limit: int = 100
    ) -> list[dict[str, object]]:
        body: dict[str, object] = {
            "limit": limit,
            "with_payload": True,
        }
        if account:
            body["filter"] = {
                "must": [{"key": "account", "match": {"value": account}}]
            }

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
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                f"{self._url}/collections/{self._collection}/points/delete",
                json={
                    "filter": {
                        "must": [{"key": "account", "match": {"value": account}}]
                    }
                },
            )
        logger.info("Deleted intents for account '%s'", account)

    async def delete_by_intent_id(self, account: str, intent_id: str) -> None:
        point_id = _deterministic_point_id(f"{account}_intent_{intent_id}")
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(
                f"{self._url}/collections/{self._collection}/points/delete",
                json={"points": [point_id]},
            )

    async def count(self) -> int:
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

    @staticmethod
    def payload_to_intent(payload: dict[str, object]) -> RagicIntent:
        from data_agent.ragic.models import JoinKeyMapping, RagicFilterTemplate, RagicOperator

        filter_raw = payload.get("filter_template")
        filter_tpl: RagicFilterTemplate | None = None
        if isinstance(filter_raw, dict):
            op_str = str(filter_raw.get("operator", "eq"))
            try:
                op = RagicOperator(op_str)
            except ValueError:
                op = RagicOperator.EQ
            filter_tpl = RagicFilterTemplate(
                field_id=str(filter_raw.get("field_id", "")),
                operator=op,
                value=str(filter_raw.get("value", "")),
            )

        nl_raw = payload.get("nl_patterns", [])
        nl_patterns: list[str] = [str(p) for p in nl_raw] if isinstance(nl_raw, list) else []

        nl_ex_raw = payload.get("nl_examples", [])
        nl_examples: list[str] = [str(p) for p in nl_ex_raw] if isinstance(nl_ex_raw, list) else []

        tables_raw = payload.get("tables", [])
        tables: list[str] = [str(t) for t in tables_raw] if isinstance(tables_raw, list) else []

        core_raw = payload.get("core_fields", [])
        core_fields: list[str] = [str(f) for f in core_raw] if isinstance(core_raw, list) else []

        involved_raw = payload.get("involved_tables", [])
        involved: list[str] = [str(t) for t in involved_raw] if isinstance(involved_raw, list) else []

        join_keys_raw = payload.get("join_keys", [])
        join_keys: list[JoinKeyMapping] = []
        if isinstance(join_keys_raw, list):
            for jk in join_keys_raw:
                if isinstance(jk, dict):
                    join_keys.append(JoinKeyMapping(
                        source_table=str(jk.get("source_table", "")),
                        source_field=str(jk.get("source_field", "")),
                        target_table=str(jk.get("target_table", "")),
                        target_field=str(jk.get("target_field", "")),
                    ))

        tool_schema_raw = payload.get("tool_schema")
        tool_schema: dict[str, object] | None = (
            dict(tool_schema_raw) if isinstance(tool_schema_raw, dict) else None
        )

        return RagicIntent(
            intent_id=str(payload.get("intent_id", "")),
            agent_scope=str(payload.get("agent_scope", "data_agent")),
            account=str(payload.get("account", "")),
            name=str(payload.get("name", "")),
            nl_patterns=nl_patterns,
            nl_examples=nl_examples,
            description=str(payload.get("description", "")),
            action=str(payload.get("action", "list")),
            table_key=str(payload.get("table_key", "")),
            table_id=str(payload.get("table_id", "")),
            sheet_key=str(payload.get("sheet_key", "")),
            tables=tables,
            group=str(payload.get("group", "")),
            core_fields=core_fields,
            filter_template=filter_tpl,
            api_template=str(payload.get("api_template", "")),
            query_type=str(payload.get("query_type", "simple_filter")),
            tool_schema=tool_schema,
            involved_tables=involved,
            join_keys=join_keys,
            generation_strategy=str(payload.get("generation_strategy", "")),
        )
