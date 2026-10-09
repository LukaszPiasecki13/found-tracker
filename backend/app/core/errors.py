"""Global error handling and custom exceptions."""

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.headers = headers
        super().__init__(message)


class BadRequestError(APIError):
    """Invalid operation or malformed domain request."""


class NotFoundError(APIError):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found", code: str | None = None):
        super().__init__(message, status.HTTP_404_NOT_FOUND, code)


class ConflictError(APIError):
    """Resource conflict (e.g., unique constraint violation)."""

    def __init__(self, message: str = "Resource conflict", code: str | None = None):
        super().__init__(message, status.HTTP_409_CONFLICT, code)


class AuthenticationError(APIError):
    """Authentication failed."""

    def __init__(
        self,
        message: str = "Authentication failed",
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED, code, headers)


class ForbiddenError(APIError):
    """Permission denied."""

    def __init__(self, message: str = "Permission denied", code: str | None = None):
        super().__init__(message, status.HTTP_403_FORBIDDEN, code)


class ValidationException(APIError):  # noqa: N818
    """Validation error."""

    def __init__(self, message: str = "Validation error", code: str | None = None):
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_CONTENT, code)


class GoneError(APIError):
    """Resource is gone (expired challenge, etc)."""

    def __init__(self, message: str = "Resource is gone", code: str | None = None):
        super().__init__(message, status.HTTP_410_GONE, code)


class BondTermsNotFoundError(NotFoundError):
    """Bond series parameters not found."""

    def __init__(self, message: str = "Bond series not found"):
        super().__init__(message, code="BOND_TERMS_NOT_FOUND")


class BondDataUnavailableError(APIError):
    """Bond data provider is unavailable (network error, format error, etc)."""

    def __init__(self, message: str = "Bond data provider is unavailable"):
        super().__init__(message, status.HTTP_502_BAD_GATEWAY, "BOND_DATA_UNAVAILABLE")


class BondAccrualFailedError(BadRequestError):
    """Bond accrual calculation failed (e.g., date before issue or after maturity)."""

    def __init__(self, message: str = "Bond accrual calculation failed"):
        super().__init__(message, code="BOND_ACCRUAL_FAILED")


# Fallback `code` by status for errors raised without one (error-handling
# patterns: every error carries a stable code).
_GENERIC_CODES = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_410_GONE: "GONE",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "VALIDATION_ERROR",
    status.HTTP_502_BAD_GATEWAY: "BAD_GATEWAY",
}


def _error_response(
    status_code: int,
    detail: object,
    code: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    content: dict[str, object] = {"detail": detail}
    code = code or _GENERIC_CODES.get(status_code)
    if code is not None:
        content["code"] = code
    return JSONResponse(status_code=status_code, content=content, headers=headers)


def _public_error(error: Mapping[str, Any]) -> dict[str, Any]:
    """One validation error as the client sees it: where, what and the type.
    `input` is dropped (it would echo what the user typed, passwords included)
    and so is `ctx` (it may hold exception objects, not JSON)."""
    return {key: error[key] for key in ("type", "loc", "msg") if key in error}


def register_error_handlers(app: FastAPI) -> None:
    """Register global error handlers."""

    @app.exception_handler(APIError)
    async def api_exception_handler(request: Request, exc: APIError) -> JSONResponse:
        if exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            logger.error(
                "API error on %s %s: %s",
                request.method,
                request.url.path,
                exc.message,
            )
        else:
            logger.info(
                "API error on %s %s: %s (%s)",
                request.method,
                request.url.path,
                exc.message,
                exc.status_code,
            )
        return _error_response(exc.status_code, exc.message, exc.code, exc.headers)

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError | ValidationError
    ) -> JSONResponse:
        logger.info("Validation error on %s %s", request.method, request.url.path)
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            [_public_error(error) for error in exc.errors()],
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # Never leak internals to the client, but always keep the traceback.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Internal server error",
        )
