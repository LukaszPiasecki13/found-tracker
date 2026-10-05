"""Prepare the schema the integration tests run in (`TEST_SCHEMA`, e.g. `dev1`).

A shared database may hold a test schema next to the production one; the tests pin
`search_path` to it (see `app/conftest.py`). This creates the tables there from the
current models (`Base.metadata`, which carry no schema) and loads the reference data
the tests need (currencies, an asset class, assets - the demo seed). Idempotent: run
it again after the models change; existing tables are left as they are, so drop the
schema first (`DROP SCHEMA <name> CASCADE`) to pick up a changed column.

    python -m seed.test_schema

It refuses `public`, `PRODUCTION_SCHEMA` and a staging/production environment.
The Alembic baseline pins `schema='public'`, so `alembic -x db_schema=...` cannot
build another schema from scratch; this is the supported way for a test schema.
"""

import logging
import os
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    os.chdir(backend_root)

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _test_schema() -> str:
    schema = (os.environ.get("TEST_SCHEMA") or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
        raise SystemExit("Set TEST_SCHEMA to a valid schema name (e.g. dev1)")
    production = (os.environ.get("PRODUCTION_SCHEMA") or "public").strip()
    if schema.lower() in {"public", production.lower()}:
        raise SystemExit(f"TEST_SCHEMA={schema!r} is the production schema; refusing")
    return schema


def main() -> int:
    load_dotenv()
    schema = _test_schema()
    # Settings read the environment at import time: pin the schema first, so the
    # seed (which uses `settings.database_schema`) writes to the test schema too.
    os.environ["DATABASE_SCHEMA"] = schema

    from sqlalchemy import create_engine

    import app.infrastructure.sql.models_registry  # noqa: F401
    from app.core.config import get_settings
    from app.infrastructure.sql.base import Base
    from seed import seed

    settings = get_settings()
    if settings.is_production:
        logger.error("Refusing to prepare a test schema in staging/production")
        return 1

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    engine = create_engine(settings.database_url)
    try:
        with engine.begin() as connection:
            quoted = engine.dialect.identifier_preparer.quote(schema)
            connection.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {quoted}")
            # Only the test schema, no fallback to `public`: unqualified tables
            # (and the existence checks) must land in it.
            connection.exec_driver_sql(f"SET LOCAL search_path TO {quoted}")
            Base.metadata.create_all(connection)
        logger.info("Tables of the models are in schema %s", schema)
    finally:
        engine.dispose()
    return seed.main([])


if __name__ == "__main__":
    raise SystemExit(main())
