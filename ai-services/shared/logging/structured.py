import logging
import time
import uuid
from typing import Any


class StructuredLogger:
    def __init__(self, service: str, operation: str):
        self.logger = logging.getLogger(f"{service}.{operation}")
        self.service = service
        self.operation = operation
        self.request_id = str(uuid.uuid4())[:8]

    def log(
        self,
        level: str,
        action: str,
        **kwargs: Any,
    ) -> None:
        log_data = {
            "service": self.service,
            "operation": self.operation,
            "action": action,
            "request_id": self.request_id,
            **kwargs,
        }
        getattr(self.logger, level)(
            "%s | %s",
            action,
            " | ".join(f"{k}={v}" for k, v in log_data.items() if v is not None),
        )

    def info(self, action: str, **kwargs: Any) -> None:
        self.log("info", action, **kwargs)

    def warning(self, action: str, **kwargs: Any) -> None:
        self.log("warning", action, **kwargs)

    def error(self, action: str, **kwargs: Any) -> None:
        self.log("error", action, **kwargs)

    def debug(self, action: str, **kwargs: Any) -> None:
        self.log("debug", action, **kwargs)


class Timer:
    def __init__(self, logger: StructuredLogger, action: str):
        self.logger = logger
        self.action = action
        self.start = time.time()

    def stop(self, **kwargs: Any) -> int:
        elapsed_ms = int((time.time() - self.start) * 1000)
        self.logger.info(f"{self.action}_done", duration_ms=elapsed_ms, **kwargs)
        return elapsed_ms


def get_structured_logger(service: str, operation: str) -> StructuredLogger:
    return StructuredLogger(service, operation)


def log_hybrid_rag_request(
    logger: StructuredLogger,
    query: str,
    strategy: str,
    top_k: int,
    user_id: str | None = None,
    root_id: str | None = None,
) -> Timer:
    logger.info(
        "hybrid_rag_request",
        query_length=len(query),
        strategy=strategy,
        top_k=top_k,
        user_id=user_id,
        root_id=root_id,
    )
    return Timer(logger, "hybrid_rag_search")


def log_nl_sql_request(
    logger: StructuredLogger,
    query: str,
    intent_type: str,
    user_id: str | None = None,
) -> Timer:
    logger.info(
        "nl_sql_request",
        query_length=len(query),
        intent_type=intent_type,
        user_id=user_id,
    )
    return Timer(logger, "nl_sql_pipeline")


def log_tool_execution(
    logger: StructuredLogger,
    tool_name: str,
    user_id: str | None = None,
    session_id: str | None = None,
) -> Timer:
    logger.info(
        "tool_execution_start",
        tool_name=tool_name,
        user_id=user_id,
        session_id=session_id,
    )
    return Timer(logger, "tool_execution")


def log_knowledge_retrieval(
    logger: StructuredLogger,
    query: str,
    collection: str,
    top_k: int,
    hits: int,
    user_id: str | None = None,
) -> None:
    logger.info(
        "knowledge_retrieval_done",
        query_length=len(query),
        collection=collection,
        top_k=top_k,
        actual_hits=hits,
        user_id=user_id,
    )
