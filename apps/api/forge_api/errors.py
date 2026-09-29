"""HTTP-facing errors and the handlers that render every failure as `{"error": {...}}`."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ai.errors import (
    AIError,
    DependencyMissingError,
    IncompatibleLoraError,
    InvalidLoraError,
    UnsupportedModelError,
)

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class UnprocessableError(AppError):
    status_code = 422
    code = "validation_error"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


_AI_ERROR_STATUS: dict[type[AIError], int] = {
    InvalidLoraError: 422,
    IncompatibleLoraError: 422,
    UnsupportedModelError: 422,
    DependencyMissingError: 503,
}


def error_body(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, **extra}}


def _field_name(loc: tuple[Any, ...]) -> str:
    # Drop the "body"/"query" prefix so the frontend can map errors straight onto form fields.
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts) or "request"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status_code)

    @app.exception_handler(AIError)
    async def _ai_error(_: Request, exc: AIError) -> JSONResponse:
        status = next((s for t, s in _AI_ERROR_STATUS.items() if isinstance(exc, t)), 500)
        return JSONResponse(error_body(exc.code, exc.message), status_code=status)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"field": _field_name(tuple(err["loc"])), "message": str(err["msg"])}
            for err in exc.errors()
        ]
        return JSONResponse(
            error_body("validation_error", "Some fields are invalid.", fields=fields),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(error_body("http_error", str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Full trace goes to logs only; users get a generic message.
        logger.exception("unhandled_error", extra={"path": request.url.path})
        return JSONResponse(
            error_body("internal_error", "Something went wrong on the server."), status_code=500
        )
