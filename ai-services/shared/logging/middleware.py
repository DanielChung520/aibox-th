import logging
import sys
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        import json

        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "extra_fields"):
            log_obj.update(record.extra_fields)

        return json.dumps(log_obj)


def setup_logging(service_name: str, log_level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.error").handlers = []


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, service_name: str):
        super().__init__(app)
        self.service_name = service_name
        self.logger = logging.getLogger(f"{service_name}.middleware")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        t0 = time.time()
        method = request.method
        path = request.url.path
        query = str(request.url.query)[:100] if request.url.query else ""

        self.logger.info(
            "request_start | request_id=%s | method=%s | path=%s | query=%s",
            request_id,
            method,
            path,
            query,
        )

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            status_code = 500
            elapsed_ms = int((time.time() - t0) * 1000)
            self.logger.error(
                "request_error | request_id=%s | method=%s | path=%s | error=%s | latency_ms=%d",
                request_id,
                method,
                path,
                str(exc),
                elapsed_ms,
            )
            raise

        elapsed_ms = int((time.time() - t0) * 1000)
        level = (
            "info"
            if status_code < 400
            else ("warning" if status_code < 500 else "error")
        )

        getattr(self.logger, level)(
            "request_end | request_id=%s | method=%s | path=%s | status=%d | latency_ms=%d",
            request_id,
            method,
            path,
            status_code,
            elapsed_ms,
        )

        return response
