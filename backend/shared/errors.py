"""Centralized API error types and FastAPI exception handlers."""

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class AppError(Exception):
    """Domain error mapped to a stable API contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        detail: Any | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


def error_payload(code: str, message: str, detail: Any | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if detail is not None:
        body["detail"] = detail
    return {"error": body}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            error_payload(exc.code, exc.message, exc.detail),
            status_code=exc.status_code,
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            return JSONResponse(detail, status_code=exc.status_code)
        message = detail if isinstance(detail, str) else "Request failed"
        return JSONResponse(
            error_payload("HTTP_ERROR", message, detail if not isinstance(detail, str) else None),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            error_payload("VALIDATION_ERROR", "Request validation failed", exc.errors()),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            error_payload("INTERNAL_ERROR", "An unexpected error occurred", str(exc)),
            status_code=500,
        )
