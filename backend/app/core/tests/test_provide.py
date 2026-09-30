"""`provide(build_x)`: a wiring builder exposed as a FastAPI dependency."""

from collections.abc import Generator
from unittest.mock import MagicMock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, provide


def _app(dependency: object) -> FastAPI:
    app = FastAPI()

    @app.get("/")
    def endpoint(value: str = Depends(dependency)) -> dict[str, str]:  # type: ignore[arg-type]
        return {"value": value}

    return app


def test_builder_receives_the_request_session() -> None:
    request_session = MagicMock(spec=Session)
    received: list[Session] = []

    def build_value(session: Session) -> str:
        received.append(session)
        return "built"

    app = _app(provide(build_value))

    def override_get_db() -> Generator[Session]:
        yield request_session

    app.dependency_overrides[get_db] = override_get_db

    assert TestClient(app).get("/").json() == {"value": "built"}
    assert received == [request_session]


def test_the_provided_dependency_is_an_override_key() -> None:
    get_value = provide(lambda session: "built")
    app = _app(get_value)
    app.dependency_overrides[get_value] = lambda: "overridden"

    assert TestClient(app).get("/").json() == {"value": "overridden"}
