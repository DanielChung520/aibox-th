"""
NL→SQL Pipeline - 3-Tier Hybrid SQL Generator

# Last Update: 2026-03-24 19:27:14
# Author: Daniel Chung
# Version: 1.4.0
"""

import asyncio
import re

import httpx

from data_agent.query.nl2sql.date_utils import compute_date_range
from data_agent.query.nl2sql.exceptions import SQLGenerationError
from data_agent.query.nl2sql.models import (
    GenerationStrategy,
    IntentMatch,
    PipelineConfig,
    QueryPlan,
    SchemaContext,
)

SQL_SYSTEM_PROMPT = """You are a DuckDB SQL expert. Generate a SELECT query.

MANDATORY: Tables are Parquet on S3. ALWAYS use read_parquet('s3://...') AS alias.
The exact read_parquet paths are provided in the schema. Copy them exactly.

DuckDB date syntax (IMPORTANT — date columns are VARCHAR in 'YYYYMMDD' format):
- strftime(strptime(col, '%Y%m%d'), '%Y-%m') for date formatting
- strptime(col, '%Y%m%d') to parse VARCHAR date to TIMESTAMP
- CURRENT_DATE, INTERVAL '1 month'

Rules:
1. ONLY SELECT statements (no INSERT/UPDATE/DELETE/DROP/ALTER)
2. Use exact UPPERCASE field names from schema
3. Use read_parquet() with JOIN on both sides
4. Output ONLY valid SQL, no explanation"""

SQL_LARGE_PROMPT = """You are a senior DuckDB SQL expert. Generate a precise SELECT query.

MANDATORY: Tables are Parquet on S3. ALWAYS use read_parquet('s3://...') in FROM/JOIN.
The exact read_parquet paths are provided in the schema. Copy them exactly.

DuckDB date syntax (IMPORTANT — date columns are VARCHAR in 'YYYYMMDD' format):
- strftime(strptime(col, '%Y%m%d'), '%Y-%m') for date formatting
- strptime(col, '%Y%m%d') to parse VARCHAR date to TIMESTAMP
- CURRENT_DATE, INTERVAL '1 month'
- BETWEEN '20260201' AND '20260228' for date range filtering (lexicographic)
- ILIKE for case-insensitive, || for concat
- COUNT(*), SUM(), AVG(), GROUP BY ALL

Rules:
1. ONLY SELECT — never INSERT/UPDATE/DELETE/DROP/ALTER
2. Use exact UPPERCASE field names from the provided schema
3. Ensure JOIN conditions match schema relations
4. Apply all filters from the query plan
5. Output ONLY valid SQL, no explanation or markdown"""


async def generate_sql(
    query: str,
    plan: QueryPlan,
    intent: IntentMatch,
    schema: SchemaContext,
    config: PipelineConfig,
    previous_error: str = "",
) -> str:
    if intent.generation_strategy == GenerationStrategy.TEMPLATE:
        return _fill_template(query, plan, intent, config)

    model = (
        config.small_model
        if intent.generation_strategy == GenerationStrategy.SMALL_LLM
        else config.large_model
    )

    system_prompt = (
        SQL_LARGE_PROMPT
        if intent.generation_strategy == GenerationStrategy.LARGE_LLM
        else SQL_SYSTEM_PROMPT
    )

    return await _generate_sql_with_llm(
        query, plan, intent, schema, config, model, system_prompt, previous_error
    )


def _fill_template(
    query: str, plan: QueryPlan, intent: IntentMatch, config: PipelineConfig
) -> str:
    template = intent.sql_template
    if not template:
        raise SQLGenerationError("No sql_template found for template-tier intent")

    template = template.replace("{time_range}", "*")
    template = template.replace("{po_number}", _extract_placeholder(plan, "po_number"))
    template = template.replace("{vendor_list}", _extract_placeholder(plan, "vendor_list"))

    if "read_parquet" not in intent.sql_template and config.data_source != "ragic":
        for table in plan.tables:
            module = table.split("_")[0].lower() if "_" in table else "mm"
            tbl_name = table.split("_")[-1].lower() if "_" in table else table.lower()
            parquet_ref = (
                f"read_parquet('s3://{config.s3_bucket}/{module}/{tbl_name}/*.parquet')"
            )
            template = re.sub(
                rf"\b{re.escape(table)}\b",
                parquet_ref,
                template,
                count=1,
            )

    if plan.filters:
        conditions = " AND ".join(
            f"{f.field} {f.operator} '{f.value}'" for f in plan.filters
        )
        template = template.replace("{conditions}", conditions)
    else:
        template = template.replace("WHERE {conditions}", "")
        template = template.replace("{conditions}", "1=1")

    template = template.replace("{limit}", str(plan.limit))
    start_date, end_date = compute_date_range(query)
    template = template.replace("{start_date}", start_date)
    template = template.replace("{end_date}", end_date)

    return template.strip()


def _extract_placeholder(plan: QueryPlan, key: str) -> str:
    for f in plan.filters:
        if key in f.field.lower() or key in f.value.lower():
            return f.value
    return ""


async def _generate_sql_with_llm(
    query: str,
    plan: QueryPlan,
    intent: IntentMatch,
    schema: SchemaContext,
    config: PipelineConfig,
    model: str,
    system_prompt: str,
    previous_error: str = "",
) -> str:
    schema_desc = _format_schema_brief(schema, config)
    plan_json = plan.model_dump_json(indent=2)
    few_shot_block = _build_few_shot_block(intent)

    error_context = ""
    if previous_error:
        error_context = (
            f"\n\nPREVIOUS ATTEMPT FAILED with error:\n{previous_error}\n"
            f"Fix the error and generate corrected SQL.\n"
        )

    user_prompt = (
        f"Natural language query: {query}\n\n"
        f"Query Plan:\n{plan_json}\n\n"
        f"Available tables (use EXACTLY these FROM clauses):\n"
        f"{schema_desc}\n\n"
        f"{few_shot_block}"
        f"CRITICAL: Do NOT use bare table names. "
        f"You MUST use read_parquet('s3://...') as shown above.\n"
        f"ONLY use column names listed in the schema above."
        f"{error_context}\n\n"
        f"Generate the DuckDB SQL query."
    )

    try:
        async with httpx.AsyncClient(timeout=config.generate_timeout + 5.0) as client:
            response = await asyncio.wait_for(
                client.post(
                    f"{config.ollama_base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "stream": False,
                        "temperature": 0.1,
                    },
                ),
                timeout=config.generate_timeout,
            )
            response.raise_for_status()
            data = response.json()
            content = str(data.get("message", {}).get("content", ""))

        return _extract_sql(content)

    except asyncio.TimeoutError:
        raise SQLGenerationError(f"LLM generation timed out after {config.generate_timeout}s")
    except httpx.HTTPError as e:
        raise SQLGenerationError(f"LLM service unavailable: {str(e)}")


def _extract_sql(content: str) -> str:
    sql_match = re.search(r"```(?:sql)?\s*([\s\S]*?)```", content)
    if sql_match:
        return sql_match.group(1).strip()

    cleaned = content.strip()
    if cleaned.upper().startswith("SELECT"):
        return cleaned

    raise SQLGenerationError(f"No valid SQL in LLM response: {content[:200]}")


def _build_few_shot_block(intent: IntentMatch) -> str:
    pairs: list[tuple[str, str]] = []

    if intent.example_sqls:
        for i, sql in enumerate(intent.example_sqls[:3]):
            nl = intent.nl_examples[i] if i < len(intent.nl_examples) else ""
            if nl and sql:
                pairs.append((nl, sql))
    elif intent.nl_examples and intent.sql_template:
        pairs.append((intent.nl_examples[0], intent.sql_template))

    if not pairs:
        return ""

    lines = ["Reference examples for this query type:\n"]
    for idx, (nl, sql) in enumerate(pairs, 1):
        lines.append(f"Example {idx}:")
        lines.append(f"  Question: {nl}")
        lines.append(f"  SQL: {sql}\n")
    lines.append("")

    return "\n".join(lines)


def _format_schema_brief(schema: SchemaContext, config: PipelineConfig) -> str:
    lines: list[str] = []
    alias_map: dict[str, str] = {}
    master_tables = {"mara", "lfa1", "mard", "mchb", "t024", "t001", "t024e"}
    for tbl in schema.tables:
        fields = [f for f in schema.fields if f.table_name == tbl.table_name]
        field_strs = [f"{f.field_name}({f.data_type})" for f in fields]
        module = tbl.module.lower() if tbl.module else "mm"
        tbl_lower = tbl.table_name.lower()
        suffix = "all.parquet" if tbl_lower in master_tables else "*.parquet"
        pq = f"read_parquet('s3://{config.s3_bucket}/{module}/{tbl_lower}/{suffix}')"
        alias = tbl_lower[0]
        if alias in alias_map.values():
            alias = tbl_lower[:2]
        alias_map[tbl.table_name] = alias
        lines.append(f"-- {tbl.table_name}: FROM {pq} AS {alias}\n"
                     f"--   Columns: {', '.join(field_strs)}")
    if schema.relations:
        rels = [f"{r.from_table}.{r.from_field}→{r.to_table}.{r.to_field}"
                for r in schema.relations]
        lines.append(f"-- Relations: {'; '.join(rels)}")
    return "\n".join(lines)
