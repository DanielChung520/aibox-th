"""
NL→SQL Pipeline - Schema Retriever

Retrieves pruned schema context from ArangoDB for the tables
identified by intent classification. Never sends full schema to LLM.

# Last Update: 2026-03-23 23:24:21
# Author: Daniel Chung
# Version: 1.0.0
"""

import httpx

from data_agent.query.nl2sql.exceptions import SchemaError
from data_agent.query.nl2sql.models import (
    FieldSchema,
    JoinPath,
    PipelineConfig,
    SchemaContext,
    TableRelation,
    TableSchema,
)


async def retrieve_schema(
    tables: list[str], config: PipelineConfig
) -> SchemaContext:
    """Retrieve pruned schema for specified tables from ArangoDB.

    Only fetches metadata for the requested tables, not the full schema.
    Collection routing is controlled by config.data_source ('sap' or 'ragic').

    Args:
        tables: List of table names to retrieve schema for.
        config: Pipeline configuration with ArangoDB credentials and data_source.

    Returns:
        SchemaContext with tables, fields, relations, and join graph.

    Raises:
        SchemaError: When ArangoDB is unreachable or query fails.
    """
    if not tables:
        raise SchemaError("No tables specified for schema retrieval")

    try:
        table_schemas = await _fetch_tables(tables, config)
        table_id_map = {ts.table_name: ts.module + "_" + ts.table_name
                        for ts in table_schemas}
        table_ids = list(table_id_map.values())

        field_schemas = await _fetch_fields(table_ids, table_id_map, config)
        relations = await _fetch_relations(table_ids, config)
        join_graph = _build_join_graph(relations)

        return SchemaContext(
            tables=table_schemas,
            fields=field_schemas,
            relations=relations,
            join_graph=join_graph,
        )

    except httpx.HTTPError as e:
        raise SchemaError(f"ArangoDB unavailable: {str(e)}")


async def _fetch_tables(
    tables: list[str], config: PipelineConfig
) -> list[TableSchema]:
    ds = getattr(config, "data_source", "sap")
    collection = f"da_table_info_{ds}"
    table_list = ", ".join(f'"{t}"' for t in tables)
    aql = (
        f"FOR t IN {collection} "
        f"FILTER t.table_name IN [{table_list}] "
        f"RETURN t"
    )

    results = await _execute_aql(aql, config)
    return [
        TableSchema(
            table_name=str(r.get("table_name", "")),
            description=str(r.get("description", "")),
            row_count=int(r.get("row_count_estimate", 0)),
            module=str(r.get("module", "")),
            tab=str(r.get("tab", "")),
            sheet_key=str(r.get("sheet_key", "")),
            s3_path=str(r.get("s3_path", "")),
        )
        for r in results
    ]


async def _fetch_fields(
    table_ids: list[str],
    table_id_map: dict[str, str],
    config: PipelineConfig,
) -> list[FieldSchema]:
    ds = getattr(config, "data_source", "sap")
    collection = f"da_field_info_{ds}"
    id_list = ", ".join(f'"{tid}"' for tid in table_ids)
    aql = (
        f"FOR f IN {collection} "
        f"FILTER f.table_id IN [{id_list}] "
        f"RETURN f"
    )

    reverse_map = {v: k for k, v in table_id_map.items()}
    results = await _execute_aql(aql, config)
    return [
        FieldSchema(
            table_name=reverse_map.get(
                str(r.get("table_id", "")),
                str(r.get("table_id", "")).split("_", 1)[-1],
            ),
            field_name=str(r.get("field_name", "")),
            data_type=str(r.get("field_type", "")),
            description=str(r.get("description", "")),
            is_key=bool(r.get("is_pk", False)),
            field_id=str(r.get("field_id", "")),
            writable=bool(r.get("writable", True)),
            is_subtable_field=bool(r.get("is_subtable", False)),
            subtable_key=str(r.get("subtable_key", "")),
        )
        for r in results
    ]


async def _fetch_relations(
    table_ids: list[str], config: PipelineConfig
) -> list[TableRelation]:
    ds = getattr(config, "data_source", "sap")
    collection = f"da_table_relation_{ds}"
    id_list = ", ".join(f'"{tid}"' for tid in table_ids)
    aql = (
        f"FOR r IN {collection} "
        f"FILTER r.left_table IN [{id_list}] "
        f"OR r.right_table IN [{id_list}] "
        f"RETURN r"
    )

    results = await _execute_aql(aql, config)
    return [
        TableRelation(
            from_table=str(r.get("left_table", "")).split("_", 1)[-1],
            from_field=str(r.get("left_field", "")),
            to_table=str(r.get("right_table", "")).split("_", 1)[-1],
            to_field=str(r.get("right_field", "")),
            relation_type=str(r.get("join_type", "INNER")),
        )
        for r in results
    ]


def _build_join_graph(
    relations: list[TableRelation],
) -> dict[str, list[JoinPath]]:
    """Build a join graph from table relations for quick lookup."""
    graph: dict[str, list[JoinPath]] = {}

    for rel in relations:
        if rel.from_table not in graph:
            graph[rel.from_table] = []
        graph[rel.from_table].append(
            JoinPath(
                target_table=rel.to_table,
                from_field=rel.from_field,
                to_field=rel.to_field,
                join_type=rel.relation_type,
            )
        )

        # Bidirectional: also add reverse
        if rel.to_table not in graph:
            graph[rel.to_table] = []
        graph[rel.to_table].append(
            JoinPath(
                target_table=rel.from_table,
                from_field=rel.to_field,
                to_field=rel.from_field,
                join_type=rel.relation_type,
            )
        )

    return graph


async def _execute_aql(
    aql: str, config: PipelineConfig
) -> list[dict[str, object]]:
    """Execute an AQL query and return results."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{config.arango_url}/_db/{config.arango_db}/_api/cursor",
            json={"query": aql},
            auth=(config.arango_user, config.arango_password),
        )
        response.raise_for_status()
        data = response.json()
        result: list[dict[str, object]] = data.get("result", [])
        return result
