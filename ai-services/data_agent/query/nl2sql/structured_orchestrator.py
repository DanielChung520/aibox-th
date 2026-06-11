"""
Structured Query Orchestrator — 結構化查詢 pipeline。

流程：SQL 生成 → 驗證 → 執行（含 fallback 重試）。
艾企 Agent 傳入 StructuredQueryRequest，回傳 StructuredQueryResult。

# Last Update: 2026-04-16 19:52:01
# Author: Daniel Chung
# Version: 1.1.0
"""

import logging
import time

from data_agent.query.nl2sql.exceptions import ExecutionError, SQLGenerationError
from data_agent.query.nl2sql.executor import execute_on_server_cache, fetch_table_schema
from data_agent.query.nl2sql.models import (
    FieldSchema,
    PipelineConfig,
    SchemaContext,
    StructuredQueryRequest,
    StructuredQueryResult,
    TableSchema,
    ValidationResult,
)
from data_agent.query.nl2sql.structured_sql_generator import generate_structured_sql
from data_agent.query.nl2sql.validator import validate_sql

logger = logging.getLogger(__name__)


def _build_lightweight_schema(request: StructuredQueryRequest) -> SchemaContext:
    tables = [TableSchema(table_name=request.table)]
    fields = [
        FieldSchema(table_name=request.table, field_name=f)
        for f in request.fields
    ]
    return SchemaContext(tables=tables, fields=fields)


def _build_minimal_config() -> PipelineConfig:
    return PipelineConfig()


async def run_structured_pipeline(
    request: StructuredQueryRequest,
) -> StructuredQueryResult:
    start_ms = time.time() * 1000
    attempts = 0

    try:
        table_columns = await fetch_table_schema(request.table)
        sql, model_used = await generate_structured_sql(
            request, table_columns=table_columns,
        )
        attempts = 1
    except SQLGenerationError as e:
        return StructuredQueryResult(
            success=False,
            error=str(e),
            attempts=1,
            total_time_ms=round(time.time() * 1000 - start_ms, 2),
        )

    schema = _build_lightweight_schema(request)
    config = _build_minimal_config()

    validation: ValidationResult = await validate_sql(
        sql, schema, config, run_semantic_check=False,
    )

    if not validation.is_valid:
        logger.warning("Structured SQL validation failed: %s", validation.errors)
        try:
            error_msg = "; ".join(e.message for e in validation.errors)
            sql, model_used = await generate_structured_sql(
                request, previous_error=error_msg,
                table_columns=table_columns,
            )
            attempts += 1

            validation = await validate_sql(
                sql, schema, config, run_semantic_check=False,
            )
            if not validation.is_valid:
                error_msgs = "; ".join(e.message for e in validation.errors)
                return StructuredQueryResult(
                    success=False,
                    generated_sql=sql,
                    model_used=model_used,
                    attempts=attempts,
                    error=f"Validation failed after retry: {error_msgs}",
                    total_time_ms=round(time.time() * 1000 - start_ms, 2),
                )
        except SQLGenerationError as e:
            return StructuredQueryResult(
                success=False,
                generated_sql=sql,
                model_used=model_used,
                attempts=attempts,
                error=str(e),
                total_time_ms=round(time.time() * 1000 - start_ms, 2),
            )

    try:
        execution_result = await execute_on_server_cache(sql)
    except ExecutionError as e:
        return StructuredQueryResult(
            success=False,
            generated_sql=sql,
            model_used=model_used,
            attempts=attempts,
            error=str(e),
            total_time_ms=round(time.time() * 1000 - start_ms, 2),
        )

    return StructuredQueryResult(
        success=True,
        generated_sql=sql,
        execution_result=execution_result,
        model_used=model_used,
        attempts=attempts,
        total_time_ms=round(time.time() * 1000 - start_ms, 2),
    )
