"""
NL→SQL Pipeline - Orchestrator

Main pipeline entry point that coordinates all phases:
Clarification → Intent Classification → Reranking → Schema → Plan
→ SQL → Validation → Execution → Error Explanation (on failure)

# Last Update: 2026-03-24 20:10:43
# Author: Daniel Chung
# Version: 1.5.0
"""

import logging
import os
import time

from data_agent.config_reader import get_param
from data_agent.query.nl2sql.error_explainer import explain_error
from data_agent.query.nl2sql.exceptions import PipelineError
from data_agent.query.nl2sql.executor import execute_aql, execute_sql
from data_agent.query.nl2sql.intent_classifier import (
    classify_intent,
    classify_intent_candidates,
)
from data_agent.query.nl2sql.models import (
    GenerationStrategy,
    IntentMatch,
    PipelineConfig,
    PipelinePhaseResult,
    PipelineResult,
)
from data_agent.query.nl2sql.plan_generator import generate_query_plan
from data_agent.query.nl2sql.query_clarifier import check_query_clarity
from data_agent.query.nl2sql.reranker import RERANK_THRESHOLD, rerank_candidates
from data_agent.query.nl2sql.schema_retriever import retrieve_schema
from data_agent.query.nl2sql.sql_generator import generate_sql
from data_agent.query.nl2sql.validator import validate_sql

logger = logging.getLogger(__name__)


async def _build_config() -> PipelineConfig:
    """Build pipeline config from ArangoDB system_params."""
    raw_threshold = await get_param("intent.matching_threshold")
    try:
        match_threshold = float(raw_threshold) if raw_threshold is not None and raw_threshold != "" else 0.45
    except (ValueError, TypeError):
        logger.warning("Invalid intent.matching_threshold value %r, using default 0.45", raw_threshold)
        match_threshold = 0.45

    return PipelineConfig(
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        small_model=await get_param("da.small_llm_model"),
        large_model=await get_param("da.large_llm_model"),
        embedding_model=await get_param("da.embedding_model"),
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "data_agent_intents"),
        arango_url=os.getenv("ARANGO_URL", "http://localhost:8529"),
        arango_db=os.getenv("ARANGO_DATABASE", "abc_desktop"),
        arango_user=os.getenv("ARANGO_USER", "root"),
        arango_password=os.getenv("ARANGO_PASSWORD", ""),
        s3_endpoint=os.getenv("S3_ENDPOINT", "http://localhost:8334"),
        s3_bucket=os.getenv("S3_BUCKET", "sap"),
        data_source=await get_param("da.data_source"),
        s3_access_key=os.getenv("S3_ACCESS_KEY", ""),
        s3_secret_key=os.getenv("S3_SECRET_KEY", ""),
        match_threshold=match_threshold,
        max_retries=int(os.getenv("NL2SQL_MAX_RETRIES", "2")),
        generate_timeout=float(os.getenv("NL2SQL_GENERATE_TIMEOUT", "60")),
    )


async def _classify_with_reranking(
    query: str, config: PipelineConfig, phases: list[PipelinePhaseResult],
) -> tuple[IntentMatch, float]:
    """Classify intent, applying LLM reranking when top-1 score is ambiguous."""
    t0 = time.time() * 1000
    intent = await classify_intent(query, config)
    classify_ms = round(time.time() * 1000 - t0, 2)
    phases.append(PipelinePhaseResult(phase="intent_classification", duration_ms=classify_ms))

    if intent.score < RERANK_THRESHOLD and intent.generation_strategy != GenerationStrategy.TEMPLATE:
        t0 = time.time() * 1000
        candidates = await classify_intent_candidates(query, config, limit=3)
        if len(candidates) > 1:
            intent = await rerank_candidates(query, candidates, config)
            phases.append(PipelinePhaseResult(
                phase="reranking", duration_ms=round(time.time() * 1000 - t0, 2),
            ))
            logger.info("Reranked: %s (score=%.3f)", intent.intent_id, intent.score)

    logger.info("Intent: %s (score=%.3f, strategy=%s)",
                intent.intent_id, intent.score, intent.generation_strategy.value)
    if intent.intent_id.startswith("rgc_"):
        config.data_source = "ragic"
        logger.info("Ragic intent matched, data_source=ragic")
    return intent, classify_ms


async def _generate_and_execute(
    query: str, intent: IntentMatch, config: PipelineConfig,
    phases: list[PipelinePhaseResult], start_time: float,
) -> PipelineResult:
    """Run phases 2-6: Schema → Plan → SQL → Validate → Execute (with retry)."""

    t0 = time.time() * 1000
    schema = await retrieve_schema(intent.tables, config)
    phases.append(PipelinePhaseResult(phase="schema_retrieval",
                                      duration_ms=round(time.time() * 1000 - t0, 2)))

    t0 = time.time() * 1000
    plan = await generate_query_plan(query, intent, schema, config)
    phases.append(PipelinePhaseResult(phase="plan_generation",
                                      duration_ms=round(time.time() * 1000 - t0, 2)))

    generated_sql = ""
    validation = None
    last_error = ""
    for attempt in range(config.max_retries + 1):
        t0 = time.time() * 1000
        generated_sql = await generate_sql(query, plan, intent, schema, config, last_error)
        phases.append(PipelinePhaseResult(
            phase=f"sql_generation_attempt_{attempt + 1}",
            duration_ms=round(time.time() * 1000 - t0, 2),
        ))

        t0 = time.time() * 1000
        run_semantic = intent.generation_strategy == GenerationStrategy.LARGE_LLM
        validation = await validate_sql(generated_sql, schema, config, run_semantic_check=run_semantic)
        phases.append(PipelinePhaseResult(
            phase=f"sql_validation_attempt_{attempt + 1}",
            duration_ms=round(time.time() * 1000 - t0, 2), success=validation.is_valid,
        ))

        if not validation.is_valid:
            last_error = str([e.message for e in validation.errors])
            if attempt < config.max_retries:
                continue
            err_msg = "SQL validation failed after retries"
            explanation = await explain_error(query, err_msg, "sql_validation", config)
            return PipelineResult(success=False, query=query, matched_intent=intent,
                                  query_plan=plan, generated_sql=generated_sql,
                                  validation=validation, error=err_msg,
                                  error_explanation=explanation,
                                  phases=phases, total_time_ms=round(time.time() * 1000 - start_time, 2))

        t0 = time.time() * 1000
        try:
            if getattr(config, "data_source", "sap") == "ragic":
                result = await execute_aql(generated_sql, config)
            else:
                result = await execute_sql(generated_sql, config)
            phases.append(PipelinePhaseResult(phase="execution",
                                              duration_ms=round(time.time() * 1000 - t0, 2)))
            return PipelineResult(success=True, query=query, matched_intent=intent,
                                  query_plan=plan, generated_sql=generated_sql,
                                  validation=validation, execution_result=result,
                                  phases=phases, total_time_ms=round(time.time() * 1000 - start_time, 2))
        except PipelineError as exec_err:
            phases.append(PipelinePhaseResult(
                phase=f"execution_attempt_{attempt + 1}",
                duration_ms=round(time.time() * 1000 - t0, 2), success=False, error=str(exec_err),
            ))
            last_error = str(exec_err)
            if attempt < config.max_retries:
                continue
            err_msg = f"[execution] {last_error}"
            explanation = await explain_error(query, last_error, "execution", config)
            return PipelineResult(success=False, query=query, matched_intent=intent,
                                  query_plan=plan, generated_sql=generated_sql,
                                  validation=validation, error=err_msg,
                                  error_explanation=explanation,
                                  phases=phases, total_time_ms=round(time.time() * 1000 - start_time, 2))

    explanation = await explain_error(query, last_error, "pipeline_exhausted", config)
    return PipelineResult(success=False, query=query, matched_intent=intent,
                          query_plan=plan, generated_sql=generated_sql,
                          validation=validation, error=f"Pipeline exhausted retries: {last_error}",
                          error_explanation=explanation,
                          phases=phases, total_time_ms=round(time.time() * 1000 - start_time, 2))


async def run_nl2sql_pipeline(
    query: str, config: PipelineConfig | None = None,
) -> PipelineResult:
    """Run the full NL→SQL pipeline with pre-query clarification and error explanation."""
    if config is None:
        config = await _build_config()

    start_time = time.time() * 1000
    phases: list[PipelinePhaseResult] = []

    t0 = time.time() * 1000
    clarification = await check_query_clarity(query, config)
    phases.append(PipelinePhaseResult(
        phase="clarification_check", duration_ms=round(time.time() * 1000 - t0, 2),
    ))

    if clarification.needs_clarification:
        return PipelineResult(
            success=False, query=query, clarification=clarification,
            error="Query needs clarification before processing",
            phases=phases, total_time_ms=round(time.time() * 1000 - start_time, 2),
        )

    try:
        intent, _ = await _classify_with_reranking(query, config, phases)
        return await _generate_and_execute(query, intent, config, phases, start_time)
    except PipelineError as e:
        logger.error("Pipeline error at %s: %s", e.phase, str(e))
        phases.append(PipelinePhaseResult(phase=e.phase, duration_ms=0, success=False, error=str(e)))
        explanation = await explain_error(query, str(e), e.phase, config)
        return PipelineResult(success=False, query=query, error=f"[{e.phase}] {str(e)}",
                              error_explanation=explanation,
                              phases=phases, total_time_ms=round(time.time() * 1000 - start_time, 2))
    except Exception as e:
        logger.error("Unexpected pipeline error: %s", str(e))
        explanation = await explain_error(query, str(e), "unknown", config)
        return PipelineResult(success=False, query=query, error=f"Unexpected error: {str(e)}",
                              error_explanation=explanation,
                              phases=phases, total_time_ms=round(time.time() * 1000 - start_time, 2))
