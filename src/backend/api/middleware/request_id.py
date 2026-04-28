"""Request ID tracing middleware for end-to-end request logging and debugging."""
from __future__ import annotations

import uuid
import logging
import time
from typing import Callable, Awaitable, Optional
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


request_id_context: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
logger = logging.getLogger(__name__)


class RequestIdFilter(logging.Filter):
    """Logging filter that attaches the current request ID to all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get(None)
        return True


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Generates a unique UUID for every incoming request
    2. Attaches it to the request context
    3. Adds it to all response headers
    4. Logs request start, end, duration, and status code
    5. Includes request ID in all exceptions
    """

    HEADER_NAME = "X-Request-ID"

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._configure_logging()

    def _configure_logging(self) -> None:
        """Configure logging format to include request ID."""
        root_logger = logging.getLogger()

        # Add our filter to all existing handlers
        for handler in root_logger.handlers:
            if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
                handler.addFilter(RequestIdFilter())

            # Update formatter to include request_id if it uses standard format
            if hasattr(handler.formatter, "_fmt"):
                fmt = handler.formatter._fmt
                if "%(request_id)s" not in fmt:
                    # Insert request_id into the format string
                    if "%(levelname)s" in fmt:
                        new_fmt = fmt.replace(
                            "%(levelname)s", "%(levelname)s [%(request_id)s]"
                        )
                        handler.setFormatter(logging.Formatter(new_fmt))

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Generate or extract request ID
        request_id = request.headers.get(self.HEADER_NAME, str(uuid.uuid4()))
        token = request_id_context.set(request_id)

        start_time = time.perf_counter()
        status_code = 500

        try:
            logger.info(
                "Request started: %s %s from %s",
                request.method,
                request.url.path,
                request.client.host if request.client else "unknown",
                extra={
                    "request_method": request.method,
                    "request_path": request.url.path,
                    "remote_addr": request.client.host if request.client else None,
                },
            )

            response = await call_next(request)
            status_code = response.status_code

            # Add request ID to response headers
            response.headers[self.HEADER_NAME] = request_id
            return response

        except Exception as exc:
            # Attach request ID to exception
            setattr(exc, "request_id", request_id)
            logger.exception(
                "Request failed with exception: %s",
                str(exc),
            )
            raise

        finally:
            duration = time.perf_counter() - start_time
            logger.info(
                "Request completed: %s %s - %d (%.3fms)",
                request.method,
                request.url.path,
                status_code,
                duration * 1000,
                extra={
                    "request_method": request.method,
                    "request_path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round(duration * 1000, 3),
                },
            )
            request_id_context.reset(token)


def get_current_request_id() -> Optional[str]:
    """Get the request ID for the current request context."""
    return request_id_context.get()
