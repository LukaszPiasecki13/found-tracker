---
paths: ["**/*.py"]
description: Python 3.12+ coding standards - Ruff, mypy strict, FastAPI patterns, pytest. Auto-loaded for Python files.
---

# Python Coding Standards

Python 3.12+ with FastAPI or Django REST. Toolchain: Ruff, mypy strict, pytest.

## Comment and Identifier Language

Code, identifiers, and code comments/docstrings are always written in English, regardless of
what language the project's documentation (README, `docs/`, ADRs) uses. This keeps source
readable for tooling, linters, and any contributor who doesn't share the docs' language.
User-facing strings (API messages shown to end users, UI labels) follow the product's target
language instead — that's a product decision, not a code-comment one.

## Package Management

Follow the package manager the project already uses — never introduce a second one.

| Project state | Use | Lockfile |
|---------------|-----|----------|
| New project, free choice | `uv` | commit `uv.lock` |
| Existing `uv.lock` | `uv` | commit `uv.lock` |
| Existing `requirements.txt` / `pyproject.toml` with pip | `pip` inside the project `.venv` | commit pinned `requirements*.txt` |
| Existing `poetry.lock` | `poetry` | commit `poetry.lock` |

Invariants regardless of tool:

- Never install into the system interpreter. Always the project's virtual environment
  (`uv run` / `.venv/bin/python` / `.venv\Scripts\python.exe`).
- Never commit `.venv/`.
- Adding or upgrading a dependency is a decision, not a side effect: propose it and get
  approval before installing.

## Formatting Rules (Ruff)

- Line length: 88 characters
- Indent: 4 spaces
- Quotes: double (`"`)
- Imports: stdlib, then third-party, then local (isort-compatible)

## Type Safety (mypy strict)

All functions must have full type annotations.

Exception - FastAPI route handlers: the response contract is `response_model=` on the
decorator, so a missing return annotation on a handler that declares it is not a review finding.
`mypy --strict` still reports `no-untyped-def` for it, so silence it with a per-module override
for the `api` packages rather than line-by-line ignores. Everything below the router (services,
repositories, helpers) is annotated with no exceptions.
A project that cannot enable `strict` yet records the gap and a plan in an ADR instead of
silently setting `strict = false`.

```python
# Use | for unions (Python 3.10+)
def get_user(user_id: str) -> User | None: ...

# Type aliases
from typing import TypeAlias
ReportMap: TypeAlias = dict[str, list[ReportResponse]]

# Protocol for structural typing
from typing import Protocol
class Repository(Protocol):
    async def get(self, id: str) -> dict | None: ...
    async def save(self, data: dict) -> str: ...
```

## FastAPI Patterns

### Router structure

Examples below use `async`; a project on a synchronous SQLAlchemy session uses plain `def`
handlers and services throughout. Follow what the project already does - do not mix.

```python
from fastapi import APIRouter, Depends, status
from app.schemas.report import ReportCreate, ReportResponse
from app.services.report_service import ReportService
from app.dependencies import get_current_user, get_report_service

router = APIRouter(prefix="/reports", tags=["reports"])

@router.post("/", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    data: ReportCreate,
    service: ReportService = Depends(get_report_service),
    current_user: User = Depends(get_current_user),
) -> ReportResponse:
    return await service.create(data, current_user.id)
```

### Pydantic schemas
```python
from pydantic import BaseModel, Field, ConfigDict

class ReportBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    year: int = Field(ge=2020, le=2030)

class ReportCreate(ReportBase):
    """What the client sends."""

class ReportResponse(ReportBase):
    """What the server returns."""
    id: str
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

### Configuration (pydantic-settings)
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    debug: bool = False
    allowed_origins: list[str] = []
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
```

### Query Parameters — Always Use Schema
Query parameters must **always** use a Pydantic schema with `Depends()`, even for a single parameter. Never scatter individual parameters in function arguments.

```python
# schemas/report.py
class ListReportsQuery(BaseModel):
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)
    status: str | None = None

# api/reports.py
@router.get("/", response_model=PaginatedResponse[ReportResponse])
def list_reports(
    query: ListReportsQuery = Depends(),
    service: ReportService = Depends(get_report_service),
) -> PaginatedResponse[ReportResponse]:
    reports, total = service.list_reports(query.skip, query.limit, query.status)
    return PaginatedResponse(items=reports, total=total, skip=query.skip, limit=query.limit)
```

**Why:** Centralizes validation, defaults, and documentation. Reusable across endpoints. Consistent signatures.

### Dependencies
```python
from collections.abc import AsyncGenerator

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

### Composing Services Outside HTTP Requests

Startup code, a CLI command, or a background task needs a session too, and it must not
hand-roll its own open → commit → rollback → close. Give the project one context manager that
opens a session, rolls back on **any** exception (including `SystemExit`), always closes, and
**never commits** — the transaction boundary stays with the service, exactly like in a request.
Expose it next to the request-scoped session dependency (`get_db`).

Split *composing* an object graph from the two ways of *calling* it, one file each per module:

| File | Role | Must not know about |
|------|------|----------------------|
| `wiring.py` | The only place that assembles services: `build_<x>(session) -> X`, pure functions, no I/O, no commit | FastAPI, `dependencies.py` |
| `dependencies.py` | Adapts builders to FastAPI: `get_<x> = provide(build_<x>)`, plus dependencies that exist only in HTTP (current user, permissions) | Composing object graphs itself |
| `entrypoints.py` | The non-HTTP counterpart to a router: `with scope() as session: service = build_<x>(session); service.method(...)`, applies domain error policy. Exists only in a module that has such an operation | Committing, returning ORM entities, `dependencies.py` |

Rules:
- A builder takes the session and only what genuinely varies between calls; it reads
  configuration itself (`get_settings()`). The calling actor (for an audit trail, etc.) is a
  method argument on the service, not a builder argument — it depends on the call, not on
  composition.
- Call another module's builder through a module import (`from app.x import wiring as
  x_wiring`, then `x_wiring.build_y(session)` inside a function body) rather than importing the
  function by name. A module-level `from x import wiring as x_wiring` doesn't execute anything,
  so it tolerates a cycle between two modules' `wiring.py` files that each need a service from
  the other — importing a specific function by name does not.
- `dependencies.py` never composes; it only wraps a builder as a FastAPI dependency via a
  `provide(builder)` helper that supplies `session=Depends(get_db)`. Assign the result to a
  module-level `get_<x>` name — that name is the key tests use for `dependency_overrides`.
- Code that isn't part of an HTTP request (`wiring.py`, `entrypoints.py`, services) never
  imports any module's `dependencies.py` — that would tie non-HTTP code to FastAPI.
- Only `entrypoints.py` opens a session outside a request. It never commits or touches
  repositories directly, and returns plain data (dataclass, enum, `None`), not ORM entities.
- Error policy has an owner: *domain* policy ("this failure is non-fatal because...") belongs
  in the entrypoint; *process* policy (exit code, "the app doesn't start") belongs in the thin
  driver (CLI command, `lifespan`, background-task registration) that calls the entrypoint and
  nothing else — no service, repository, or session import in the driver itself.

## Code Quality Rules

| Rule | Limit |
|------|-------|
| Cyclomatic complexity | max 10 |
| Function length | ~50 lines |
| File length | ~300 lines |

### Prefer
- f-strings over `.format()`
- `pathlib.Path` over `os.path`
- Structural pattern matching (`match`/`case`) for multi-branch logic
- Dependency injection over global mutable state

### Avoid
```python
# Mutable default arguments - BUG
def bad(items: list = []):  ...
def good(items: list | None = None):
    items = items or []

# Bare except - NEVER
try: ...
except:  ...
# Instead:
except (ValueError, KeyError) as e:
    logger.error(f"Processing failed: {e}")
```

## Testing (pytest)

Configure in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # no @pytest.mark.asyncio needed per test
```

```python
@pytest.fixture
def mock_service() -> AsyncMock:
    service = AsyncMock(spec=ReportService)
    service.get.return_value = ReportResponse(id="1", title="Test", ...)
    return service

async def test_create_report_success(client: AsyncClient, mock_service: AsyncMock):
    response = await client.post("/api/v1/reports", json={"title": "New", "year": 2024})
    assert response.status_code == 201

@pytest.mark.parametrize("invalid_year", [-1, 2019, 2031])
async def test_create_report_invalid_year(client: AsyncClient, invalid_year: int):
    response = await client.post("/api/v1/reports", json={"title": "X", "year": invalid_year})
    assert response.status_code == 422
```

## Docstrings

Add only to: public API functions, complex business logic, non-obvious algorithms.
Skip for: private helpers, simple CRUD, test functions.
Format: Google style with `Args`/`Returns`/`Raises` sections.

---

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|----------|
| Module/file | snake_case | `report_service.py` |
| Class | PascalCase | `ReportService` |
| Function/method | snake_case | `get_by_company()` |
| Variable | snake_case | `report_count` |
| Constant (module-level) | UPPER_SNAKE | `MAX_RETRY_COUNT` |
| Private | leading underscore | `_validate_input()` |
| Type alias | PascalCase | `ReportMap` |
| Pydantic schema | PascalCase + suffix | `ReportCreate`, `ReportResponse` |
| FastAPI router | snake_case | `report_router` |
| Test function | `test_` + descriptive | `test_create_report_with_invalid_year()` |
| Fixture | snake_case, noun | `mock_service`, `db_session` |
| Repository instance (var/attr/param) | `<domain>_repo` | `alarms_repo`, `measurement_points_repo` |

- Boolean variables/params: `is_`, `has_`, `can_` prefix (`is_active`, `has_permission`)
- Async functions: no special naming (`async` keyword is sufficient)
- Abbreviations allowed: `db`, `id`, `url`, `api` - avoid all others

## API and Database Naming

| Element | Convention | Example |
|---------|-----------|----------|
| URL path | kebab-case, plural | `/api/v1/data-points` |
| Query param | snake_case | `?company_id=abc&page_size=20` |
| JSON field | snake_case | `created_at`, `company_id` |
| DB table | snake_case, plural | `reports`, `data_points` |
| DB column | snake_case | `created_at`, `company_id` |
| DB index | `idx_` + table + columns | `idx_reports_company_status` |
