# FundTracker — backend

FastAPI + SQLAlchemy + Alembic. Architecture: [`docs/technical/backend/01_backend-architecture.md`](../docs/technical/backend/01_backend-architecture.md).

## Setup

```
python -m venv ../.venv && ../.venv/Scripts/activate   # Python 3.14
pip install -r requirements.txt
cp .env.example .env                                   # fill in; never commit .env
alembic upgrade head
python -m seed.seed                                    # demo data; refuses staging/production
uvicorn app.main:app --reload
```

## Tests

Integration tests write to the database (inside a rolled-back transaction), so they
need a disposable database:

```
TEST_DATABASE_URL=postgresql://user:pw@localhost:5432/found_tracker_test pytest
pytest -m "not integration"      # no database needed
```

`app/conftest.py` aborts the run if the target is not local and `TEST_DATABASE_URL` is unset.
Prepare the test database with `alembic upgrade head` and `python -m seed.seed` using that URL.

## Quality gates

`ruff check .`, `ruff format --check .`, `mypy app`, `alembic check`, `pytest`.
Migrations: only `alembic revision --autogenerate -m "..."`, never edited by hand.
