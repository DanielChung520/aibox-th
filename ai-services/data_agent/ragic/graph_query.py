"""
@file        graph_query.py
@description Query cross-table relation graph from ArangoDB (BFS traversal + path finding).
@lastUpdate  2026-04-11 17:12:44
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import logging
import os
from collections import deque

import httpx

from data_agent.ragic.models_phase9 import (
    GraphQueryResult,
    GraphRelation,
    TableRelationEdge,
)

logger = logging.getLogger(__name__)

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "abc_desktop_2026")

_COLLECTION = "da_table_relation_ragic"
_LIMIT = 1000


def _parse_relation_doc(doc: dict[str, object]) -> TableRelationEdge:
    left = str(doc.get("left_table", ""))
    right = str(doc.get("right_table", ""))
    left_name = left.split("_", 1)[-1] if "_" in left else left
    right_name = right.split("_", 1)[-1] if "_" in right else right
    join_type = str(doc.get("join_type", "LEFT"))
    rel_type = "link" if join_type != "load" else "load"
    return TableRelationEdge(
        from_table=left_name,
        from_field=str(doc.get("left_field", "")),
        to_table=right_name,
        to_field=str(doc.get("right_field", "")),
        relation_type=rel_type,
        sync_mode=str(doc.get("sync_mode", "")) or None,
    )


class RagicGraphQuery:

    def __init__(
        self,
        arango_url: str | None = None,
        arango_db: str | None = None,
        arango_user: str | None = None,
        arango_password: str | None = None,
    ) -> None:
        self._url = arango_url or ARANGO_URL
        self._db = arango_db or ARANGO_DB
        self._user = arango_user or ARANGO_USER
        self._password = arango_password or ARANGO_PASSWORD

    @property
    def _base(self) -> str:
        return f"{self._url}/_db/{self._db}"

    @property
    def _auth(self) -> tuple[str, str]:
        return (self._user, self._password)

    async def get_related_tables(
        self, table_name: str, account: str, depth: int = 1
    ) -> GraphQueryResult:
        table_id = f"{account}_{table_name}"
        visited: set[str] = {table_name}
        all_relations: list[GraphRelation] = []
        frontier: set[str] = {table_id}

        for current_depth in range(depth):
            if not frontier:
                break
            docs = await self._fetch_relations_for_ids(list(frontier), account)
            next_frontier: set[str] = set()
            for doc in docs:
                left = str(doc.get("left_table", ""))
                right = str(doc.get("right_table", ""))
                left_name = left.split("_", 1)[-1] if "_" in left else left
                right_name = right.split("_", 1)[-1] if "_" in right else right
                left_field = str(doc.get("left_field", ""))
                right_field = str(doc.get("right_field", ""))

                if left in frontier:
                    all_relations.append(GraphRelation(
                        target_table=right_name,
                        target_field=right_field,
                        source_field=left_field,
                        relation_type="link",
                        direction="outgoing",
                    ))
                    if right_name not in visited:
                        visited.add(right_name)
                        next_frontier.add(right)
                if right in frontier:
                    all_relations.append(GraphRelation(
                        target_table=left_name,
                        target_field=left_field,
                        source_field=right_field,
                        relation_type="link",
                        direction="incoming",
                    ))
                    if left_name not in visited:
                        visited.add(left_name)
                        next_frontier.add(left)
            frontier = next_frontier

        return GraphQueryResult(
            table=table_name,
            relations=all_relations,
            depth=depth,
        )

    async def find_path(
        self,
        from_table: str,
        to_table: str,
        account: str,
        max_depth: int = 4,
    ) -> list[TableRelationEdge] | None:
        all_rels = await self.get_all_relations(account)
        adj: dict[str, list[tuple[str, TableRelationEdge]]] = {}
        for rel in all_rels:
            adj.setdefault(rel.from_table, []).append((rel.to_table, rel))
            adj.setdefault(rel.to_table, []).append((rel.from_table, rel))

        visited: set[str] = {from_table}
        queue: deque[tuple[str, list[TableRelationEdge]]] = deque()
        queue.append((from_table, []))

        while queue:
            current, path = queue.popleft()
            if len(path) >= max_depth:
                continue
            for neighbor, edge in adj.get(current, []):
                if neighbor == to_table:
                    return path + [edge]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [edge]))
        return None

    async def get_all_relations(self, account: str) -> list[TableRelationEdge]:
        aql = (
            f"FOR r IN {_COLLECTION} "
            "FILTER r.account == @account "
            f"LIMIT {_LIMIT} "
            "RETURN r"
        )
        docs = await self._execute_aql(aql, {"account": account})
        return [_parse_relation_doc(d) for d in docs]

    async def _fetch_relations_for_ids(
        self, table_ids: list[str], account: str
    ) -> list[dict[str, object]]:
        aql = (
            f"FOR r IN {_COLLECTION} "
            "FILTER r.account == @account "
            "AND (r.left_table IN @ids OR r.right_table IN @ids) "
            f"LIMIT {_LIMIT} "
            "RETURN r"
        )
        return await self._execute_aql(aql, {"account": account, "ids": table_ids})

    async def _execute_aql(
        self, aql: str, bind_vars: dict[str, object]
    ) -> list[dict[str, object]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base}/_api/cursor",
                json={"query": aql, "bindVars": bind_vars},
                auth=self._auth,
            )
            if resp.status_code not in (200, 201):
                logger.error("AQL failed: %d %s", resp.status_code, resp.text[:200])
                return []
            result: list[dict[str, object]] = resp.json().get("result", [])
            return result
