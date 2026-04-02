"""
NL→SQL Pipeline - 3-Layer SQL Validator

Validates generated SQL with three layers:
1. Regex blocklist (dangerous keywords, multi-statement)
2. AST parsing via sqlglot (table/column validation)
3. LLM semantic check (optional, for large_llm tier only)

# Last Update: 2026-03-23 18:40:25
# Author: Daniel Chung
# Version: 1.0.0
"""

import re
from typing import Optional

import httpx

from data_agent.query.nl2sql.models import (
    PipelineConfig,
    SchemaContext,
    ValidationError,
    ValidationResult,
)

DANGEROUS_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
]

BLOCKED_PATTERNS = [
    r"--",                      # Single-line comment
    r"(?<!['\w/])/\*(?![.])",   # Multi-line comment open (skip /*.parquet paths)
    r"\*/(?!['\w])",            # Multi-line comment close (skip path context)
    r";\s*\S",                  # Multi-statement (semicolon followed by content)
]


async def validate_sql(
    sql: str,
    schema: SchemaContext,
    config: PipelineConfig,
    run_semantic_check: bool = False,
) -> ValidationResult:
    """Validate SQL through 3 layers.

    Args:
        sql: Generated SQL string.
        schema: Pruned schema context for table/column validation.
        config: Pipeline configuration.
        run_semantic_check: Whether to run LLM semantic check (Layer 3).

    Returns:
        ValidationResult with is_valid flag and errors/warnings.
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    # Ragic AQL bypass — AQL is not SQL, skip Layer 1 & 2 validation
    if config.data_source == "ragic":
        return ValidationResult(
            is_valid=True, errors=[], warnings=[],
        )

    # Layer 1: Regex blocklist
    l1_errors = _validate_regex(sql)
    errors.extend(l1_errors)

    if l1_errors:
        return ValidationResult(
            is_valid=False, errors=errors, warnings=warnings
        )

    # Layer 2: AST parsing (sqlglot)
    l2_errors, l2_warnings = _validate_ast(sql, schema)
    errors.extend(l2_errors)
    warnings.extend(l2_warnings)

    if l2_errors:
        return ValidationResult(
            is_valid=False, errors=errors, warnings=warnings
        )

    # Layer 3: LLM semantic check (optional)
    if run_semantic_check:
        l3_result = await _validate_semantic(sql, config)
        if l3_result:
            warnings.append(l3_result)

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def _validate_regex(sql: str) -> list[ValidationError]:
    """Layer 1: Regex blocklist validation."""
    errors: list[ValidationError] = []
    sql_upper = sql.upper().strip()

    if not sql_upper.startswith("SELECT"):
        errors.append(
            ValidationError(
                layer=1,
                message="SQL must start with SELECT",
                severity="error",
            )
        )

    for keyword in DANGEROUS_KEYWORDS:
        # Check for standalone keyword (not part of another word)
        pattern = rf"\b{keyword}\b"
        if re.search(pattern, sql_upper):
            errors.append(
                ValidationError(
                    layer=1,
                    message=f"Blocked keyword detected: {keyword}",
                    severity="error",
                )
            )

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, sql):
            errors.append(
                ValidationError(
                    layer=1,
                    message=f"Blocked pattern detected: {pattern}",
                    severity="error",
                )
            )

    return errors


def _validate_ast(
    sql: str, schema: SchemaContext
) -> tuple[list[ValidationError], list[ValidationError]]:
    """Layer 2: AST parsing via sqlglot."""
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    try:
        import sqlglot
        parsed = sqlglot.parse_one(sql, dialect="duckdb")

        # Extract referenced tables
        referenced_tables: set[str] = set()
        for table in parsed.find_all(sqlglot.exp.Table):
            table_name = table.name.upper()
            # Skip read_parquet pseudo-tables
            if "READ_PARQUET" in table_name or "PARQUET" in table_name:
                continue
            referenced_tables.add(table_name)

        # Validate tables against schema (skip if using read_parquet)
        schema_tables = {t.table_name.upper() for t in schema.tables}
        if referenced_tables and schema_tables:
            unknown = referenced_tables - schema_tables
            for t in unknown:
                warnings.append(
                    ValidationError(
                        layer=2,
                        message=f"Table '{t}' not in schema context",
                        severity="warning",
                    )
                )

    except ImportError:
        warnings.append(
            ValidationError(
                layer=2,
                message="sqlglot not installed, skipping AST validation",
                severity="warning",
            )
        )
    except Exception as e:
        errors.append(
            ValidationError(
                layer=2,
                message=f"SQL parse error: {str(e)}",
                severity="error",
            )
        )

    return errors, warnings


async def _validate_semantic(
    sql: str, config: PipelineConfig
) -> Optional[ValidationError]:
    """Layer 3: LLM semantic check (optional)."""
    try:
        prompt = (
            f"Does this SQL query look correct and safe? "
            f"Reply YES or NO with a brief reason.\n\n"
            f"SQL: {sql}"
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{config.ollama_base_url}/api/chat",
                json={
                    "model": config.small_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = str(data.get("message", {}).get("content", ""))

        if "NO" in content.upper().split(".")[0]:
            return ValidationError(
                layer=3,
                message=f"LLM semantic check warning: {content[:200]}",
                severity="warning",
            )

        return None

    except Exception:
        # Semantic check is optional — don't fail pipeline
        return None
