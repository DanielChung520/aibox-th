"""
@file        record_tracer.py
@description Record-level data lineage tracer.
              Given a table_key + record_id, traverses FK relationships
              through the schema graph and returns a data graph (nodes + edges).
@lastUpdate  2026-05-01
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from data_agent.ragic.client import RagicAPIClient
from data_agent.ragic.config_loader import RagicConfigLoader
from data_agent.ragic.graph_query import RagicGraphQuery

logger = logging.getLogger(__name__)

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")

_FIELD_COLLECTION = "da_field_info_ragic"
_TABLE_COLLECTION = "da_table_info_ragic"
_MAX_FAN_OUT = 10


# ---------------------------------------------------------------------------
# Data graph models
# ---------------------------------------------------------------------------


class RecordNode:
    """A single record node in the data graph."""

    def __init__(
        self,
        table_key: str,
        table_name: str,
        ragic_id: str,
        fields: dict[str, Any],
        depth: int,
    ) -> None:
        self.table_key = table_key
        self.table_name = table_name
        self.ragic_id = ragic_id
        self.fields = fields
        self.depth = depth

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_key": self.table_key,
            "table_name": self.table_name,
            "ragic_id": self.ragic_id,
            "fields": self.fields,
            "depth": self.depth,
        }


class RecordEdge:
    """A directed edge between two records in the data graph."""

    def __init__(
        self,
        from_ragic_id: str,
        from_table_key: str,
        to_ragic_id: str,
        to_table_key: str,
        via_field_id: str,
        via_field_name: str,
        relation_type: str,
    ) -> None:
        self.from_ragic_id = from_ragic_id
        self.from_table_key = from_table_key
        self.to_ragic_id = to_ragic_id
        self.to_table_key = to_table_key
        self.via_field_id = via_field_id
        self.via_field_name = via_field_name
        self.relation_type = relation_type

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_ragic_id": self.from_ragic_id,
            "from_table_key": self.from_table_key,
            "to_ragic_id": self.to_ragic_id,
            "to_table_key": self.to_table_key,
            "via_field_id": self.via_field_id,
            "via_field_name": self.via_field_name,
            "relation_type": self.relation_type,
        }


class DataGraph:
    """Complete data graph result."""

    def __init__(
        self,
        nodes: list[RecordNode],
        edges: list[RecordEdge],
        root_ragic_id: str,
        root_table_key: str,
        total_records: int,
        total_time_ms: float,
    ) -> None:
        self.nodes = nodes
        self.edges = edges
        self.root_ragic_id = root_ragic_id
        self.root_table_key = root_table_key
        self.total_records = total_records
        self.total_time_ms = total_time_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "root_ragic_id": self.root_ragic_id,
            "root_table_key": self.root_table_key,
            "total_records": self.total_records,
            "total_time_ms": round(self.total_time_ms, 2),
        }


# ---------------------------------------------------------------------------
# Record Tracer
# ---------------------------------------------------------------------------


class RecordTracer:
    """Trace a single record through FK relationships in the schema graph.

    Given a table_key + record_id (Ragic row ID), this tracer:
    1. Fetches the starting record from Ragic API
    2. Loads field schema to identify FK fields (linked_to / loaded_from)
    3. Uses RagicGraphQuery to discover related tables
    4. For each related table, extracts FK values from the record
       and fetches the related records (up to max_fan_out per edge)
    5. Recursively traces until depth limit or no more FK values
    6. Returns a DataGraph with RecordNodes and RecordEdges
    """

    def __init__(
        self,
        graph_query: RagicGraphQuery,
        config_loader: RagicConfigLoader,
    ) -> None:
        self._graph = graph_query
        self._config_loader = config_loader

    async def trace(
        self,
        table_key: str,
        record_id: str,
        account: str,
        depth: int = 3,
        max_fan_out: int = _MAX_FAN_OUT,
    ) -> DataGraph:
        """Trace a record through FK relationships.

        Args:
            table_key: Ragic table key (e.g. "进仓单/3").
            record_id: Ragic row ID of the starting record.
            account: Ragic account name.
            depth: Max traversal depth (default 3).
            max_fan_out: Max records to fetch per FK edge (default 10).

        Returns:
            DataGraph with all traced nodes and edges.
        """
        start_time = time.monotonic()

        # Setup
        conn = await self._config_loader.get_connection(account)
        if conn is None:
            logger.error("No Ragic connection for account: %s", account)
            return DataGraph([], [], record_id, table_key, 0, 0)

        client = RagicAPIClient(conn)
        tab_path, sheet_index = self._parse_table_key(table_key)
        table_name = await self._get_table_name(account, table_key)

        # Load FK field map for this table
        fk_field_map = await self._load_fk_field_map(account, table_key)
        # fk_field_map: field_id -> {target_table_key, target_field_id}

        # Fetch root record
        root_record = await client.get_record(tab_path, sheet_index, int(record_id))
        if root_record is None:
            logger.warning("Record not found: %s/%s", table_key, record_id)
            return DataGraph([], [], record_id, table_key, 0, 0)

        # Build graph using BFS
        nodes: list[RecordNode] = []
        edges: list[RecordEdge] = []
        visited: set[tuple[str, str]] = {(table_key, record_id)}

        # Add root node
        nodes.append(
            RecordNode(
                table_key=table_key,
                table_name=table_name,
                ragic_id=record_id,
                fields=dict(root_record.fields),
                depth=0,
            )
        )

        # BFS traversal queue
        pending_work: list[tuple[str, str, int, dict[str, Any]]] = []

        relations_for_table = await self._get_relations_for_table(account, table_key)
        # relations_for_table: list of (from_table_key, from_field_id, to_table_key, to_field_id, rel_type)

        await self._collect_fk_records(
            client=client,
            account=account,
            table_key=table_key,
            record_id=record_id,
            record_fields=dict(root_record.fields),
            relations=relations_for_table,
            fk_field_map=fk_field_map,
            depth=0,
            max_depth=depth,
            max_fan_out=max_fan_out,
            visited=visited,
            nodes=nodes,
            edges=edges,
            pending_work=pending_work,
        )

        # Process pending work (BFS)
        while pending_work:
            cur_table_key, cur_record_id, cur_depth, cur_fields = pending_work.pop(0)

            if cur_depth >= depth:
                continue

            # Get relations for this table
            cur_relations = await self._get_relations_for_table(account, cur_table_key)
            cur_fk_map = await self._load_fk_field_map(account, cur_table_key)

            await self._collect_fk_records(
                client=client,
                account=account,
                table_key=cur_table_key,
                record_id=cur_record_id,
                record_fields=cur_fields,
                relations=cur_relations,
                fk_field_map=cur_fk_map,
                depth=cur_depth,
                max_depth=depth,
                max_fan_out=max_fan_out,
                visited=visited,
                nodes=nodes,
                edges=edges,
                pending_work=pending_work,
            )

        elapsed_ms = (time.monotonic() - start_time) * 1000
        return DataGraph(
            nodes=nodes,
            edges=edges,
            root_ragic_id=record_id,
            root_table_key=table_key,
            total_records=len(nodes),
            total_time_ms=elapsed_ms,
        )

    async def _collect_fk_records(
        self,
        client: RagicAPIClient,
        account: str,
        table_key: str,
        record_id: str,
        record_fields: dict[str, Any],
        relations: list[tuple[str, str, str, str, str]],
        fk_field_map: dict[str, dict[str, str]],
        depth: int,
        max_depth: int,
        max_fan_out: int,
        visited: set[tuple[str, str]],
        nodes: list[RecordNode],
        edges: list[RecordEdge],
        pending_work: list[tuple[str, str, int, dict[str, Any]]],
    ) -> None:
        """Collect records reachable via FK edges from a single record."""
        for from_tk, from_field_id, to_tk, to_field_id, rel_type in relations:
            if from_tk != table_key:
                continue

            # This relation is from our table to another table
            # Check if the FK field has a value in the current record
            fk_value = self._get_field_value(record_fields, from_field_id)
            if fk_value is None or str(fk_value).strip() == "":
                continue

            # Fetch the target record(s)
            target_tab_path, target_sheet_index = self._parse_table_key(to_tk)
            target_table_name = await self._get_table_name(account, to_tk)

            try:
                target_record = await client.get_record(
                    target_tab_path,
                    target_sheet_index,
                    int(str(fk_value).strip()),
                )
            except (ValueError, TypeError):
                continue

            if target_record is None:
                continue

            target_id = target_record.ragic_id
            if (to_tk, target_id) in visited:
                continue
            visited.add((to_tk, target_id))

            # Add edge
            via_field_name = fk_field_map.get(from_field_id, {}).get(
                "via_field_name", from_field_id
            )
            edges.append(
                RecordEdge(
                    from_ragic_id=record_id,
                    from_table_key=table_key,
                    to_ragic_id=target_id,
                    to_table_key=to_tk,
                    via_field_id=from_field_id,
                    via_field_name=via_field_name,
                    relation_type=rel_type,
                )
            )

            # Add node
            nodes.append(
                RecordNode(
                    table_key=to_tk,
                    table_name=target_table_name,
                    ragic_id=target_id,
                    fields=dict(target_record.fields),
                    depth=depth + 1,
                )
            )

            # Queue for further traversal
            pending_work.append(
                (to_tk, target_id, depth + 1, dict(target_record.fields))
            )

    async def _get_relations_for_table(
        self,
        account: str,
        table_key: str,
    ) -> list[tuple[str, str, str, str, str]]:
        """Get outgoing relations for a table from ArangoDB.

        Returns list of (from_table_key, from_field_id, to_table_key, to_field_id, rel_type).
        """
        tab_path, _ = self._parse_table_key(table_key)
        aql = (
            f"FOR r IN {_FIELD_COLLECTION} "
            "FILTER r.account == @account "
            "AND r.table_id == @table_id "
            "AND r.linked_to != null "
            "RETURN {"
            "  field_id: r.field_id,"
            "  linked_to: r.linked_to,"
            "  loaded_from: r.loaded_from"
            "}"
        )
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.post(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                    json={
                        "query": aql,
                        "bindVars": {
                            "account": account,
                            "table_id": table_key,
                        },
                    },
                    auth=(ARANGO_USER, ARANGO_PASSWORD),
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to fetch relations for %s: %s", table_key, exc)
            return []

        results = resp.json().get("result", [])
        relations: list[tuple[str, str, str, str, str]] = []

        for doc in results:
            linked_to = doc.get("linked_to")
            if not isinstance(linked_to, dict):
                continue

            target_form = str(linked_to.get("target_form", ""))
            target_field = str(linked_to.get("target_field", ""))

            # Resolve target_form -> table_key via da_table_info_ragic
            target_table_key = await self._resolve_table_key(account, target_form)
            if not target_table_key:
                continue

            relations.append(
                (
                    table_key,
                    str(doc.get("field_id", "")),
                    target_table_key,
                    target_field,
                    "link",
                )
            )

        return relations

    async def _resolve_table_key(self, account: str, table_name: str) -> str | None:
        """Resolve a human-readable table name to a table_key (table_id in ArangoDB)."""
        aql = (
            f"FOR d IN {_TABLE_COLLECTION} "
            "FILTER d.account == @account "
            "AND (d.table_name == @tname OR d.tab == @tname) "
            "LIMIT 1 "
            "RETURN d._key"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.post(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                    json={
                        "query": aql,
                        "bindVars": {
                            "account": account,
                            "tname": table_name,
                        },
                    },
                    auth=(ARANGO_USER, ARANGO_PASSWORD),
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to resolve table name %s: %s", table_name, exc)
            return None

        result = resp.json().get("result", [])
        return str(result[0]) if result else None

    async def _load_fk_field_map(
        self,
        account: str,
        table_key: str,
    ) -> dict[str, dict[str, str]]:
        """Load FK field metadata (field_id -> {target_table_key, target_field_id, via_field_name})."""
        aql = (
            f"FOR r IN {_FIELD_COLLECTION} "
            "FILTER r.account == @account "
            "AND r.table_id == @table_id "
            "AND r.linked_to != null "
            "RETURN {"
            "  field_id: r.field_id,"
            "  field_name: r.field_name,"
            "  linked_to: r.linked_to"
            "}"
        )
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.post(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                    json={
                        "query": aql,
                        "bindVars": {
                            "account": account,
                            "table_id": table_key,
                        },
                    },
                    auth=(ARANGO_USER, ARANGO_PASSWORD),
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to load FK field map for %s: %s", table_key, exc)
            return {}

        result_map: dict[str, dict[str, str]] = {}
        for doc in resp.json().get("result", []):
            linked_to = doc.get("linked_to")
            if not isinstance(linked_to, dict):
                continue
            field_id = str(doc.get("field_id", ""))
            result_map[field_id] = {
                "target_form": str(linked_to.get("target_form", "")),
                "target_field": str(linked_to.get("target_field", "")),
                "via_field_name": str(doc.get("field_name", field_id)),
            }
        return result_map

    async def _get_table_name(self, account: str, table_key: str) -> str:
        """Get human-readable table name from table_key."""
        aql = (
            f"FOR d IN {_TABLE_COLLECTION} "
            "FILTER d._key == @table_key "
            "LIMIT 1 "
            "RETURN d.table_name"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.post(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                    json={"query": aql, "bindVars": {"table_key": table_key}},
                    auth=(ARANGO_USER, ARANGO_PASSWORD),
                )
                resp.raise_for_status()
        except Exception:
            return table_key

        result = resp.json().get("result", [])
        return str(result[0]) if result else table_key

    @staticmethod
    def _get_field_value(fields: dict[str, Any], field_id: str) -> Any:
        """Get field value from record fields dict, handling Ragic's nested EID format."""
        # Ragic returns fields like: "1000001": "value" (EID-based)
        # Or: "供应商": "value" (name-based when naming="" param)
        # We look up by field_id (EID string)
        if field_id in fields:
            return fields[field_id]
        # Fallback: try lowercase
        lower = field_id.lower()
        for k, v in fields.items():
            if k.lower() == lower:
                return v
        return None

    @staticmethod
    def _parse_table_key(table_key: str) -> tuple[str, int]:
        """Parse table_key like '进仓单/3' -> ('进仓单', 3)."""
        parts = table_key.rsplit("/", 1)
        if len(parts) == 2:
            try:
                return parts[0], int(parts[1])
            except ValueError:
                pass
        return table_key, 0
