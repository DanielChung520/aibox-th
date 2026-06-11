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

from data_agent.ragic.config_loader import RagicConfigLoader
from data_agent.ragic.graph_query import RagicGraphQuery

logger = logging.getLogger(__name__)

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:6500")

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

        table_name = await self._get_table_name(account, table_key)

        # Load FK field map for this table
        fk_field_map = await self._load_fk_field_map(account, table_key)

        # Fetch root record via Rust proxy API (more reliable than direct Ragic call)
        root_fields = await self._fetch_record_via_proxy(table_key, record_id)
        if root_fields is None:
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
                fields=root_fields,
                depth=0,
            )
        )

        # BFS traversal queue
        pending_work: list[tuple[str, str, int, dict[str, Any]]] = []

        relations_for_table = await self._get_relations_for_table(account, table_key)

        await self._collect_fk_records(
            account=account,
            table_key=table_key,
            record_id=record_id,
            record_fields=root_fields,
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

    # ------------------------------------------------------------------ 
    # Progressive expansion — step-by-step FK edge traversal
    # ------------------------------------------------------------------

    async def fk_preview(
        self,
        table_key: str,
        record_id: str,
        account: str,
    ) -> dict[str, Any]:
        """Get a record's data + list of expandable FK edges (no traversal).

        Returns everything the frontend needs to show the record node
        and its ghost edges, WITHOUT fetching target record data.
        """
        table_name = await self._get_table_name(account, table_key)
        record = await self._fetch_record_via_proxy(table_key, record_id)
        if record is None:
            return {"record": None, "table_name": table_name, "fk_edges": []}

        relations = await self._get_relations_for_table(account, table_key)
        fk_field_map = await self._load_fk_field_map(account, table_key)

        fk_edges: list[dict[str, Any]] = []
        for from_tk, from_field_id, to_tk, to_field_name_or_id, rel_type in relations:
            if from_tk != table_key:
                continue
            fk_value = self._get_field_value(record, from_field_id)
            if fk_value is None or str(fk_value).strip() == "":
                continue

            target_table_name = await self._get_table_name(account, to_tk)
            via_field_name = fk_field_map.get(from_field_id, {}).get(
                "via_field_name", from_field_id
            )

            fk_edges.append({
                "from_field_id": from_field_id,
                "from_field_name": via_field_name,
                "from_field_value": str(fk_value).strip(),
                "target_table_key": to_tk,
                "target_table_name": target_table_name,
                "relation_type": rel_type,
            })

        return {
            "record": record,
            "table_name": table_name,
            "fk_edges": fk_edges,
        }

    async def expand_fk_edge(
        self,
        table_key: str,
        record_id: str,
        field_id: str,
        field_value: str,
        account: str,
        via_field_name: str = "",
    ) -> dict[str, Any]:
        """Expand ONE FK edge: fetch target records + their FK previews.

        Returns target records (as nodes) and their own expandable FK edges,
        so the frontend can immediately show ghost nodes for the next level.
        """
        relations = await self._get_relations_for_table(account, table_key)
        target_rel = None
        for from_tk, from_fid, to_tk, to_fname, rel_type in relations:
            if from_tk == table_key and from_fid == field_id:
                target_rel = (to_tk, to_fname, rel_type)
                break

        if target_rel is None:
            return {"nodes": [], "fk_previews": {}, "via_field_name": via_field_name}

        to_tk, to_field_name_or_id, rel_type = target_rel

        to_field_id = await self._resolve_field_id(account, to_tk, to_field_name_or_id)
        target_records = await self._fetch_records_by_field_value(
            to_tk, to_field_id, field_value,
        )

        nodes: list[dict[str, Any]] = []
        fk_previews: dict[str, list[dict[str, Any]]] = {}

        for rec in target_records:
            rid = str(rec.get("_ragicId", ""))
            if not rid:
                continue

            target_table_name = await self._get_table_name(account, to_tk)
            nodes.append({
                "table_key": to_tk,
                "table_name": target_table_name,
                "ragic_id": rid,
                "fields": rec,
            })

            target_relations = await self._get_relations_for_table(account, to_tk)
            target_fk_map = await self._load_fk_field_map(account, to_tk)
            preview_edges: list[dict[str, Any]] = []
            for fr_tk, fr_fid, to_tk2, to_fn2, rel2 in target_relations:
                if fr_tk != to_tk:
                    continue
                val = self._get_field_value(rec, fr_fid)
                if val is None or str(val).strip() == "":
                    continue
                tname2 = await self._get_table_name(account, to_tk2)
                vname2 = target_fk_map.get(fr_fid, {}).get(
                    "via_field_name", fr_fid
                )
                preview_edges.append({
                    "from_field_id": fr_fid,
                    "from_field_name": vname2,
                    "from_field_value": str(val).strip(),
                    "target_table_key": to_tk2,
                    "target_table_name": tname2,
                    "relation_type": rel2,
                })
            fk_previews[rid] = preview_edges

        return {
            "nodes": nodes,
            "fk_previews": fk_previews,
            "relation_type": rel_type,
            "via_field_name": via_field_name or field_id,
        }

    async def _collect_fk_records(
        self,
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
        for from_tk, from_field_id, to_tk, to_field_name_or_id, rel_type in relations:
            if from_tk != table_key:
                continue

            # Resolve target field name to field ID (if needed)
            to_field_id = await self._resolve_field_id(account, to_tk, to_field_name_or_id)

            # This relation is from our table to another table
            # Check if the FK field has a value in the current record
            fk_value = self._get_field_value(record_fields, from_field_id)
            if fk_value is None or str(fk_value).strip() == "":
                continue

            # Fetch the target record(s) via FK field value search
            target_table_name = await self._get_table_name(account, to_tk)

            try:
                target_records = await self._fetch_records_by_field_value(
                    to_tk, to_field_id, str(fk_value).strip(),
                )
            except (ValueError, TypeError):
                continue

            if not target_records:
                continue

            seen_target_rids: set[str] = set()
            for target_fields in target_records:
                target_rid = str(target_fields.get("_ragicId", ""))
                if not target_rid or target_rid in seen_target_rids:
                    continue
                seen_target_rids.add(target_rid)
                if (to_tk, target_rid) in visited:
                    continue
                visited.add((to_tk, target_rid))

                # Add edge
                via_field_name = fk_field_map.get(from_field_id, {}).get("via_field_name", from_field_id)
                edges.append(RecordEdge(
                    from_ragic_id=record_id,
                    from_table_key=table_key,
                    to_ragic_id=target_rid,
                    to_table_key=to_tk,
                    via_field_id=from_field_id,
                    via_field_name=via_field_name,
                    relation_type=rel_type,
                ))

                # Add node
                nodes.append(
                    RecordNode(
                        table_key=to_tk,
                        table_name=target_table_name,
                        ragic_id=target_rid,
                        fields=target_fields,
                        depth=depth + 1,
                    )
                )

                # Queue for further traversal
                pending_work.append(
                    (to_tk, target_rid, depth + 1, target_fields)
                )

    async def _get_relations_for_table(
        self,
        account: str,
        table_key: str,
    ) -> list[tuple[str, str, str, str, str]]:
        """Get outgoing relations for a table from da_table_relation_ragic.

        Returns list of (from_table_key, from_field_id, to_table_key, to_field_id, rel_type).
        """
        _REL_COLLECTION = "da_table_relation_ragic"
        aql = (
            f"FOR r IN {_REL_COLLECTION} "
            "FILTER r.data_source == 'ragic' "
            "AND r.source_table == @table_key "
            "AND (r.status == null OR r.status == 'enabled') "
            "RETURN {"
            "  from_table: r.source_table,"
            "  from_field: r.source_field,"
            "  to_table: r.target_table,"
            "  to_field: r.target_field,"
            "  relation_type: r.relation_type"
            "}"
        )
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.post(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                    json={"query": aql, "bindVars": {"table_key": table_key}},
                    auth=(ARANGO_USER, ARANGO_PASSWORD),
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to fetch relations for %s: %s", table_key, exc)
            return []

        results = resp.json().get("result", [])
        relations: list[tuple[str, str, str, str, str]] = []
        for doc in results:
            relations.append((
                str(doc.get("from_table", "")),
                str(doc.get("from_field", "")),
                str(doc.get("to_table", "")),
                str(doc.get("to_field", "")),
                str(doc.get("relation_type", "link")),
            ))
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
        _REL_COLLECTION = "da_table_relation_ragic"
        aql = (
            f"FOR r IN {_REL_COLLECTION} "
            "FILTER r.data_source == 'ragic' "
            "AND r.source_table == @table_key "
            "AND (r.status == null OR r.status == 'enabled') "
            "RETURN {"
            "  field_id: r.source_field,"
            "  target_table: r.target_table,"
            "  target_field: r.target_field,"
            "  description: r.description"
            "}"
        )
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.post(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                    json={"query": aql, "bindVars": {"table_key": table_key}},
                    auth=(ARANGO_USER, ARANGO_PASSWORD),
                )
                resp.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to load FK field map for %s: %s", table_key, exc)
            return {}

        result_map: dict[str, dict[str, str]] = {}
        for doc in resp.json().get("result", []):
            field_id = str(doc.get("field_id", ""))
            via_field_name = str(doc.get("description", field_id))
            result_map[field_id] = {
                "target_table": str(doc.get("target_table", "")),
                "target_field": str(doc.get("target_field", "")),
                "via_field_name": via_field_name,
            }
        return result_map

    async def _resolve_ragic_path(
        self, account: str, table_id: str,
    ) -> tuple[str, int]:
        """Resolve table_id (e.g. 'FORM_36') to (tab_path, sheet_index).

        Queries da_table_info_ragic for the tab and sheet_key fields,
        falling back to _parse_table_key if the DB query fails.
        """
        aql = (
            f"FOR d IN {_TABLE_COLLECTION} "
            "FILTER d._key == @table_id AND d.account == @account "
            "LIMIT 1 "
            "RETURN {{tab: d.tab, sheet_key: d.sheet_key}}"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.post(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                    json={"query": aql, "bindVars": {
                        "account": account, "table_id": table_id,
                    }},
                    auth=(ARANGO_USER, ARANGO_PASSWORD),
                )
                resp.raise_for_status()
                result = resp.json().get("result", [])
                if result:
                    tab = str(result[0].get("tab", ""))
                    sheet_key = str(result[0].get("sheet_key", "0"))
                    return tab, int(sheet_key)
        except Exception as exc:
            logger.warning("Failed to resolve Ragic path for %s: %s", table_id, exc)

        return self._parse_table_key(table_id)

    async def _resolve_field_id(
        self, account: str, table_key: str, field_name_or_id: str,
    ) -> str:
        """Resolve a field name to a field ID by querying da_field_info_ragic.

        If field_name_or_id is already numeric (looks like an ID), returns as-is.
        """
        if field_name_or_id.isdigit() or field_name_or_id.startswith("10"):
            return field_name_or_id
        aql = (
            "FOR d IN da_field_info_ragic "
            "FILTER d.table_id == @table_key "
            "AND (d.field_name == @name OR d.field_id == @name) "
            "LIMIT 1 "
            "RETURN d.field_id"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.post(
                    f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
                    json={"query": aql, "bindVars": {
                        "table_key": table_key, "name": field_name_or_id,
                    }},
                    auth=(ARANGO_USER, ARANGO_PASSWORD),
                )
                resp.raise_for_status()
                result = resp.json().get("result", [])
                if result:
                    return str(result[0])
        except Exception as exc:
            logger.warning("Failed to resolve field %s/%s: %s", table_key, field_name_or_id, exc)
        return field_name_or_id

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

    async def _fetch_records_by_field_value(
        self, table_key: str, field_id: str, value: str,
    ) -> list[dict[str, Any]]:
        """Fetch records from a table where a field matches the given value.

        Uses the Rust proxy API to page through records.
        """
        matches: list[dict[str, Any]] = []
        page_size = 200
        offset = 0
        while offset < 10000:
            url = (
                f"{GATEWAY_URL}/api/v1/da/ragic/proxy/{table_key}/data"
                f"?offset={offset}&limit={page_size}"
            )
            try:
                async with httpx.AsyncClient(timeout=30.0) as http:
                    resp = await http.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    rows = data.get("rows", [])
                    for row in rows:
                        row_val = row.get(field_id)
                        if row_val is not None and str(row_val).strip() == value.strip():
                            matches.append({
                                k: v for k, v in row.items()
                                if k != "_ragicRecordUrl"
                            })
                    if len(rows) < page_size:
                        break
                    offset += page_size
            except Exception as exc:
                logger.warning(
                    "Failed to search records in %s: %s", table_key, exc,
                )
                break
        return matches

    async def _fetch_record_via_proxy(
        self, table_key: str, record_id: str,
    ) -> dict[str, Any] | None:
        """Fetch a single record's field data via the Rust proxy API.

        Uses the same proxy that the frontend uses (/api/v1/da/ragic/proxy/...)
        to reliably get all field values. Searches page-by-page for the record.
        """
        page_size = 200
        offset = 0
        while offset < 10000:
            url = (
                f"{GATEWAY_URL}/api/v1/da/ragic/proxy/{table_key}/data"
                f"?offset={offset}&limit={page_size}"
            )
            try:
                async with httpx.AsyncClient(timeout=30.0) as http:
                    resp = await http.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    rows = data.get("rows", [])
                    for row in rows:
                        rid = row.get("_ragicId")
                        if rid is not None and str(rid) == str(record_id).strip():
                            return {k: v for k, v in row.items() if k != "_ragicRecordUrl"}
                    if len(rows) < page_size:
                        break
                    offset += page_size
            except Exception as exc:
                logger.warning("Failed to fetch record %s/%s: %s", table_key, record_id, exc)
                return None

        logger.warning("Record not found via proxy: %s/%s", table_key, record_id)
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
