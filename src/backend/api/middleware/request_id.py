"""Request ID tracing middleware for end-to-end request logging and debugging."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Iterable
from contextvars import ContextVar

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger(__name__)

#: Shown in log lines emitted outside a request (startup, workers).
NO_REQUEST_ID = "-"
#: A client-supplied ID is only trusted if it is a short token.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._\-]{1,128}$")


class RequestIdFilter(logging.Filter):
    """Logging filter that attaches the current request ID to all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get(None) or NO_REQUEST_ID
        return True


class RequestIdMiddleware:
    """
    Pure-ASGI middleware that:
    1. Uses the caller's ``X-Request-ID`` if it is a safe token, else generates a UUID
    2. Attaches it to the request context (``get_current_request_id``) and to
       ``request.state.request_id``
    3. Adds it to the response headers
    4. Logs request start, end, duration, and status code
    5. Logs unhandled exceptions with the request ID

    It was a ``BaseHTTPMiddleware``, which wraps every request and response in
    extra tasks and streams, a measurable cost on a middleware that runs for
    every call. Being plain ASGI also avoids that class's known problems with
    background tasks and cancellation.
    """

    HEADER_NAME = "X-Request-ID"

    def __init__(self, app: ASGIApp, quiet_paths: Iterable[str] = ("/health", "/ping")):
        """
        Args:
            app: ASGI application
            quiet_paths: Exact paths whose start/end lines are not logged (health
                probes would otherwise dominate the log). They still get an ID.
        """
        self.app = app
        self.quiet_paths = frozenset(quiet_paths)
        self._configure_logging()

    def _configure_logging(self) -> None:
        """Make log lines carry the request ID. Idempotent."""
        for handler in logging.getLogger().handlers:
            if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
                handler.addFilter(RequestIdFilter())

            formatter = handler.formatter
            fmt = getattr(formatter, "_fmt", None)
            # Only rewrite a plain %-style Formatter. Replacing any other
            # formatter (JSON, colour, ``{``-style) with a bare Formatter dropped
            # its behaviour and date format; those can use %(request_id)s through
            # the filter above.
            if (
                type(formatter) is logging.Formatter
                and isinstance(formatter._style, logging.PercentStyle)
                and isinstance(fmt, str)
                and "%(request_id)s" not in fmt
                and "%(levelname)s" in fmt
            ):
                handler.setFormatter(
                    logging.Formatter(
                        fmt.replace("%(levelname)s", "%(levelname)s [%(request_id)s]"),
                        datefmt=formatter.datefmt,
                    )
                )

    def _resolve_request_id(self, scope: Scope) -> str:
        incoming = Headers(scope=scope).get(self.HEADER_NAME)
        # The raw header used to be trusted: CR/LF forged log lines and an
        # arbitrarily long value was echoed into every log line and response.
        if incoming and _VALID_REQUEST_ID.match(incoming):
            return incoming
        return str(uuid.uuid4())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request_id = self._resolve_request_id(scope)
        token = request_id_context.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id

        if scope["type"] == "websocket":
            try:
                await self.app(scope, receive, send)
            finally:
                request_id_context.reset(token)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        client = scope.get("client")
        remote = client[0] if client else None
        quiet = path in self.quiet_paths
        status_code = 500  # what the client sees if the app raises before responding
        start_time = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[self.HEADER_NAME] = request_id
            await send(message)

        try:
            if not quiet:
                logger.info(
                    "Request started: %s %s from %s",
                    method,
                    path,
                    remote or "unknown",
                    extra={
                        "request_method": method,
                        "request_path": path,
                        "remote_addr": remote,
                    },
                )
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            # The old code set ``exc.request_id = ...``, which raises
            # AttributeError (masking the real error) on exceptions that use
            # __slots__. The ID is already on the log record via the filter.
            logger.exception("Request failed with exception")
            raise
        finally:
            duration = time.perf_counter() - start_time
            if not quiet or status_code >= 500:
                logger.log(
                    logging.WARNING if status_code >= 500 else logging.INFO,
                    "Request completed: %s %s - %d (%.3fms)",
                    method,
                    path,
                    status_code,
                    duration * 1000,
                    extra={
                        "request_method": method,
                        "request_path": path,
                        "status_code": status_code,
                        "duration_ms": round(duration * 1000, 3),
                    },
                )
            request_id_context.reset(token)


def get_current_request_id() -> str | None:
    """Get the request ID for the current request context."""
    return request_id_context.get()
