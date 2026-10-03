"""Error contract (ADR-0007): `{"detail", "code"}` and no leaked internals."""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import (
    APIError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    GoneError,
    NotFoundError,
    ValidationException,
    register_error_handlers,
)


class _Payload(BaseModel):
    value: int


def _client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/not-found")
    def not_found() -> None:
        raise NotFoundError("Portfolio 1 not found", code="PORTFOLIO_NOT_FOUND")

    @app.get("/no-code")
    def no_code() -> None:
        raise ConflictError("Already there")

    @app.get("/unauthorized")
    def unauthorized() -> None:
        raise AuthenticationError(
            "Bad token", code="TOKEN_INVALID", headers={"WWW-Authenticate": "Bearer"}
        )

    @app.get("/pydantic")
    def pydantic_error() -> None:
        _Payload.model_validate({"value": "abc"})

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    return TestClient(app, raise_server_exceptions=False)


def test_api_error_renders_detail_and_code() -> None:
    response = _client().get("/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Portfolio 1 not found",
        "code": "PORTFOLIO_NOT_FOUND",
    }


def test_a_generic_code_by_status_is_used_when_none_is_given() -> None:
    response = _client().get("/no-code")

    assert response.status_code == 409
    assert response.json() == {"detail": "Already there", "code": "CONFLICT"}


def test_api_error_headers_are_forwarded() -> None:
    response = _client().get("/unauthorized")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_pydantic_validation_error_is_422_with_a_list() -> None:
    response = _client().get("/pydantic")

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_unhandled_exception_never_leaks_internals(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="app.core.errors"):
        response = _client().get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret internal detail" not in response.text
    assert "secret internal detail" in caplog.text  # traceback stays in the log


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (BadRequestError("x"), 400),
        (AuthenticationError(), 401),
        (ForbiddenError(), 403),
        (NotFoundError(), 404),
        (ConflictError(), 409),
        (GoneError(), 410),
        (ValidationException(), 422),
    ],
)
def test_subclasses_map_to_their_status(error: APIError, status_code: int) -> None:
    assert error.status_code == status_code


def test_request_validation_errors_use_the_envelope_and_do_not_echo_input() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.post("/login")
    def login(body: dict[str, str]) -> None: ...

    response = TestClient(app).post("/login", json=["secret-password"])

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert set(body["detail"][0]) <= {"type", "loc", "msg"}
    assert "secret-password" not in response.text
