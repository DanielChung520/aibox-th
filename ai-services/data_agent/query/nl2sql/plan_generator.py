"""
NL→SQL Pipeline - JSON Query Plan Generator

Generates a structured JSON Query Plan as intermediate representation
between natural language and SQL. Supports 3-tier strategy routing:
template (no LLM), small_llm, large_llm.

# Last Update: 2026-03-23 18:40:25
# Author: Daniel Chung
# Version: 1.0.0
"""

import json
import re

import httpx

from data_agent.query.nl2sql.exceptions import QueryPlanError
from data_agent.query.nl2sql.models import (
    GenerationStrategy,
    IntentMatch,
    PipelineConfig,
    QueryPlan,
    QueryPlanFilter,
    QueryPlanJoin,
    QueryPlanOrderBy,
    SchemaContext,
)

PLAN_SYSTEM_PROMPT = """You are a database query planner. Given a natural language \
query, matched intent, and database schema, generate a JSON Query Plan.

Output ONLY valid JSON with this structure:
{
  "intent_type": "filter|aggregation|join|lookup",
  "primary_table": "TABLE_NAME",
  "tables": ["TABLE1", "TABLE2"],
  "joins": [{"from_ref": "T1.FIELD", "to_ref": "T2.FIELD", "join_type": "INNER"}],
  "filters": [{"field": "TABLE.FIELD", "operator": ">=", "value": "2025-01-01"}],
  "select_fields": ["TABLE.FIELD1", "TABLE.FIELD2"],
  "aggregations": ["COUNT(*)", "SUM(TABLE.FIELD)"],
  "group_by": ["TABLE.FIELD"],
  "order_by": [{"field": "TABLE.FIELD", "direction": "DESC"}],
  "limit": 100
}

Rules:
1. Use ONLY tables and fields from the provided schema
2. Infer filter values from the natural language query
3. Use appropriate join types based on schema relations
4. Default limit is 100 unless specified
5. Output ONLY JSON, no explanation"""


async def generate_query_plan(
    query: str,
    intent: IntentMatch,
    schema: SchemaContext,
    config: PipelineConfig,
) -> QueryPlan:
    """Generate a JSON Query Plan from NL query + intent + schema.

    Strategy routing:
    - template: Derive plan from sql_template structure (no LLM)
    - small_llm: Use small model for plan generation
    - large_llm: Use large model with detailed prompting

    Args:
        query: Natural language query.
        intent: Matched intent with strategy and template.
        schema: Pruned schema context.
        config: Pipeline configuration.

    Returns:
        QueryPlan as structured intermediate representation.

    Raises:
        QueryPlanError: When plan generation fails.
    """
    if intent.generation_strategy == GenerationStrategy.TEMPLATE:
        return _derive_plan_from_template(intent)

    model = (
        config.small_model
        if intent.generation_strategy == GenerationStrategy.SMALL_LLM
        else config.large_model
    )

    return await _generate_plan_with_llm(query, intent, schema, config, model)


def _derive_plan_from_template(intent: IntentMatch) -> QueryPlan:
    """Derive a query plan from the intent's SQL template (no LLM needed)."""
    return QueryPlan(
        intent_type=intent.intent_type,
        primary_table=intent.tables[0] if intent.tables else "",
        tables=intent.tables,
        select_fields=intent.core_fields,
        limit=100,
    )


async def _generate_plan_with_llm(
    query: str,
    intent: IntentMatch,
    schema: SchemaContext,
    config: PipelineConfig,
    model: str,
) -> QueryPlan:
    """Generate query plan using LLM (Ollama)."""
    schema_desc = _format_schema_for_prompt(schema)
    user_prompt = (
        f"Natural language query: {query}\n\n"
        f"Matched intent: {intent.intent_id} ({intent.description})\n"
        f"Intent type: {intent.intent_type}\n"
        f"Tables: {', '.join(intent.tables)}\n\n"
        f"Database Schema:\n{schema_desc}\n\n"
        f"Generate the JSON Query Plan."
    )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{config.ollama_base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": PLAN_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "temperature": 0.2,
                    "format": "json",
                },
            )
            response.raise_for_status()
            data = response.json()
            content = str(data.get("message", {}).get("content", ""))

        return _parse_plan_json(content)

    except httpx.HTTPError as e:
        raise QueryPlanError(f"LLM service unavailable: {str(e)}")


def _parse_plan_json(content: str) -> QueryPlan:
    """Parse LLM output into QueryPlan, with fallback for markdown blocks."""
    try:
        plan_data = json.loads(content)
    except json.JSONDecodeError:
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if json_match:
            try:
                plan_data = json.loads(json_match.group(1))
            except json.JSONDecodeError as e:
                raise QueryPlanError(f"Failed to parse plan JSON: {str(e)}")
        else:
            raise QueryPlanError(f"No valid JSON in LLM response: {content[:200]}")

    return QueryPlan(
        intent_type=str(plan_data.get("intent_type", "")),
        primary_table=str(plan_data.get("primary_table", "")),
        tables=[str(t) for t in plan_data.get("tables", [])],
        joins=[
            QueryPlanJoin(
                from_ref=str(j.get("from_ref", "")),
                to_ref=str(j.get("to_ref", "")),
                join_type=str(j.get("join_type", "INNER")),
            )
            for j in plan_data.get("joins", [])
        ],
        filters=[
            QueryPlanFilter(
                field=str(f.get("field", "")),
                operator=str(f.get("operator", "=")),
                value=str(f.get("value", "")),
            )
            for f in plan_data.get("filters", [])
        ],
        select_fields=[str(s) for s in plan_data.get("select_fields", [])],
        aggregations=[str(a) for a in plan_data.get("aggregations", [])],
        group_by=[str(g) for g in plan_data.get("group_by", [])],
        order_by=[
            QueryPlanOrderBy(
                field=str(o.get("field", "")),
                direction=str(o.get("direction", "ASC")),
            )
            for o in plan_data.get("order_by", [])
        ],
        limit=int(plan_data.get("limit", 100)),
    )


def _format_schema_for_prompt(schema: SchemaContext) -> str:
    """Format pruned schema context for LLM prompt consumption."""
    lines: list[str] = []
    for tbl in schema.tables:
        lines.append(f"Table: {tbl.table_name} - {tbl.description}")
        tbl_fields = [f for f in schema.fields if f.table_name == tbl.table_name]
        for fld in tbl_fields:
            key_marker = " [PK]" if fld.is_key else ""
            lines.append(
                f"  {fld.field_name} ({fld.data_type}){key_marker}"
                f" - {fld.description}"
            )

    if schema.relations:
        lines.append("\nRelations:")
        for rel in schema.relations:
            lines.append(
                f"  {rel.from_table}.{rel.from_field} → "
                f"{rel.to_table}.{rel.to_field} ({rel.relation_type})"
            )

    return "\n".join(lines)
