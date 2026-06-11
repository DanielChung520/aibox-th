"""
NL→SQL Pipeline - Custom Exceptions

Defines pipeline-specific exception hierarchy for structured error handling.

# Last Update: 2026-03-23 18:40:25
# Author: Daniel Chung
# Version: 1.0.0
"""


class PipelineError(Exception):
    """Base exception for NL→SQL pipeline errors."""

    def __init__(self, message: str, phase: str = "unknown") -> None:
        self.phase = phase
        super().__init__(message)


class IntentNotFoundError(PipelineError):
    """No matching intent found for the query."""

    def __init__(self, message: str = "No matching intent found") -> None:
        super().__init__(message, phase="intent_classification")


class SchemaError(PipelineError):
    """Schema retrieval or validation failed."""

    def __init__(self, message: str = "Schema retrieval failed") -> None:
        super().__init__(message, phase="schema_retrieval")


class QueryPlanError(PipelineError):
    """Query plan generation failed."""

    def __init__(self, message: str = "Query plan generation failed") -> None:
        super().__init__(message, phase="plan_generation")


class SQLGenerationError(PipelineError):
    """SQL generation failed."""

    def __init__(self, message: str = "SQL generation failed") -> None:
        super().__init__(message, phase="sql_generation")


class SQLValidationError(PipelineError):
    """SQL validation failed."""

    def __init__(self, message: str = "SQL validation failed") -> None:
        super().__init__(message, phase="sql_validation")


class ExecutionError(PipelineError):
    """DuckDB execution failed."""

    def __init__(self, message: str = "SQL execution failed") -> None:
        super().__init__(message, phase="execution")
