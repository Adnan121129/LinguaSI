"""Application error hierarchy and FastAPI exception handlers.

Every error response has the same JSON shape so web and mobile clients can show
meaningful, user-friendly messages:

    {"error": {"code": "ai_unavailable", "message": "...", "details": {...}, "request_id": "..."}}
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("linguasi.errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"
    message = "Something went wrong with this request."

    def __init__(self, message: str | None = None, *, code: str | None = None, details: Any = None) -> None:
        self.message = message or self.message
        if code:
            self.code = code
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "The requested resource was not found."


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Please sign in to continue."


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "You do not have permission to do that."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "This conflicts with existing data."


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Some of the submitted data is invalid."


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"
    message = "Too many requests. Please slow down and try again shortly."


class AIUnavailableError(AppError):
    """Raised when an AI-backed step cannot complete. User data has already been saved."""

    status_code = 503
    code = "ai_unavailable"
    message = "AI analysis is temporarily unavailable. Your work has been saved and can be analyzed again."


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "This service is temporarily unavailable. Please try again in a moment."


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _payload(request: Request, code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message, "request_id": _request_id(request)}
    if details is not None:
        body["details"] = details
    return {"error": body}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        headers = {"Retry-After": "30"} if isinstance(exc, RateLimitedError) else None
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(request, exc.code, exc.message, exc.details),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = []
        for err in exc.errors():
            loc = [str(part) for part in err.get("loc", []) if part not in ("body", "query", "path")]
            msg = str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
            fields.append({"field": ".".join(loc) or None, "message": msg})
        first = fields[0]["message"] if fields else "Invalid request."
        field_name = fields[0]["field"] if fields else None
        message = f"{field_name}: {first}" if field_name else first
        return JSONResponse(status_code=422, content=_payload(request, "validation_error", message, {"fields": fields}))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(status_code=exc.status_code, content=_payload(request, code, message))

    @app.exception_handler(OperationalError)
    async def _db_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
        logger.exception("Database operational error", extra={"request_id": _request_id(request)})
        return JSONResponse(
            status_code=503,
            content=_payload(
                request,
                "database_unavailable",
                "The database is temporarily unavailable. Please try again in a moment.",
            ),
        )

    @app.exception_handler(DBAPIError)
    async def _db_error(request: Request, exc: DBAPIError) -> JSONResponse:
        logger.exception("Database error", extra={"request_id": _request_id(request)})
        _record_system_log("error", "database", str(exc.orig)[:500] if exc.orig else str(exc)[:500], request)
        return JSONResponse(
            status_code=500,
            content=_payload(request, "database_error", "We could not save or load your data. Please try again."),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", extra={"request_id": _request_id(request)})
        _record_system_log("error", "unhandled", f"{type(exc).__name__}: {exc}"[:500], request)
        return JSONResponse(
            status_code=500,
            content=_payload(request, "internal_error", "An unexpected error occurred. Our team has been notified."),
        )


def _record_system_log(level: str, source: str, message: str, request: Request | None = None) -> None:
    """Best-effort persistence of server errors for the admin panel. Never raises."""
    try:
        from app.services.system_log import record_system_log

        context = {}
        if request is not None:
            context = {"path": request.url.path, "method": request.method, "request_id": _request_id(request)}
        record_system_log(level, source, message, context)
    except Exception:  # pragma: no cover - logging must never break error handling
        logger.warning("Could not persist system log entry", exc_info=True)
