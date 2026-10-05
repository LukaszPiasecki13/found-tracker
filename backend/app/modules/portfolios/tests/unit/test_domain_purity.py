"""Architecture invariant: `portfolios/domain/` is pure, layered and narrowly
reachable (ADR-0005, DOM-1/DOM-2/DOM-3/DOM-9/DOM-11). Adapted from waterworks'
`alarms/tests/unit/test_domain_purity.py`.

No ORM, no `Session`, no `fastapi`/`pydantic`, no `app.core`/`app.infrastructure`,
no third-party library (ADR-0005 variant (a): no `numpy` either - the vector
metrics live in `services/metrics.py`), no clock. `repositories/` never imports
`domain/`. Files within `domain/` are layered (DOM-9): dictionary (0) ->
ORM-boundary views (1) -> components (2); imports go only downward or within a
level, never in a cycle. Consumers outside `domain/` (`services/`, `models/`,
`schemas/`, `wiring.py`) import only from `domain/__init__.py` (DOM-11).
"""

import ast
from pathlib import Path

ALLOWED_MODULES = {
    "collections",
    "collections.abc",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "types",
    "typing",
}
ALLOWED_PREFIX = "app.modules.portfolios.domain"
FORBIDDEN_CLOCK_CALLS = ("now", "utcnow", "today")

# DOM-9: layer of each domain submodule.
DOMAIN_LAYERS = {
    "enums": 0,
    "errors": 0,
    "protocols": 1,
    "ledger": 2,
    "snapshots": 2,
    "valuation": 2,
}


def _module_dir() -> Path:
    # This file lives at portfolios/tests/unit/; parents[2] is `portfolios`.
    portfolios_dir = Path(__file__).resolve().parents[2]
    assert portfolios_dir.name == "portfolios", portfolios_dir
    return portfolios_dir


def _domain_dir() -> Path:
    return _module_dir() / "domain"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imported_names(tree: ast.Module) -> set[str]:
    """Every name a module import or `from ... import ...` could reach; for an
    internal `app.` source, `module.name` too - `name` may be a submodule
    disguising the real target (`from app.modules import portfolios`)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            if node.module == "app" or node.module.startswith("app."):
                names |= {f"{node.module}.{alias.name}" for alias in node.names}
    return names


def _is_allowed(name: str) -> bool:
    if name in ALLOWED_MODULES:
        return True
    return name == ALLOWED_PREFIX or name.startswith(ALLOWED_PREFIX + ".")


def _clock_calls(source: str) -> list[str]:
    return [
        attribute
        for attribute in FORBIDDEN_CLOCK_CALLS
        if f"datetime.{attribute}(" in source
        or f"date.{attribute}(" in source
        or f"time.{attribute}(" in source
    ]


def _domain_submodule_imports(tree: ast.Module) -> set[str]:
    prefix = ALLOWED_PREFIX + "."
    return {
        node.module[len(prefix) :].split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith(prefix)
    }


def _direct_submodule_imports(tree: ast.Module) -> list[str]:
    return [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith(ALLOWED_PREFIX + ".")
    ]


def test_the_detectors_catch_every_form() -> None:
    """Guards the checkers themselves against a silent false negative."""
    caught = [
        "import sqlalchemy",
        "from sqlalchemy.orm import Session",
        "from app.core.errors import BadRequestError",
        "from app.infrastructure.sql.repository import SQLRepository",
        "import fastapi",
        "from pydantic import BaseModel",
        "import numpy as np",
        "from app.modules.portfolios.models import Portfolio",
    ]
    for source in caught:
        names = _imported_names(ast.parse(source))
        assert any(not _is_allowed(n) for n in names), source

    not_caught = [
        "from dataclasses import dataclass, replace",
        "from decimal import Decimal",
        "from collections.abc import Iterable",
        "from typing import Protocol",
        "from app.modules.portfolios.domain.enums import OperationType",
        "from app.modules.portfolios.domain import errors",
    ]
    for source in not_caught:
        names = _imported_names(ast.parse(source))
        assert all(_is_allowed(n) for n in names), source
    disguised = _imported_names(ast.parse("from app.modules import portfolios"))
    assert any(not _is_allowed(n) for n in disguised)

    assert _clock_calls("x = datetime.now(UTC)") == ["now"]
    assert _clock_calls("x = date.today()") == ["today"]
    assert _clock_calls("x = make_date(1)") == []

    submodule = ast.parse("from app.modules.portfolios.domain.ledger import X")
    assert _domain_submodule_imports(submodule) == {"ledger"}
    assert _direct_submodule_imports(submodule) == [
        "app.modules.portfolios.domain.ledger"
    ]
    public = ast.parse("from app.modules.portfolios.domain import PortfolioLedger")
    assert _direct_submodule_imports(public) == []


def test_domain_package_imports_nothing_but_stdlib_and_itself() -> None:
    files = sorted(_domain_dir().glob("*.py"))
    assert files, f"No .py files found under {_domain_dir()}"

    violations = [
        f"{py_file.name}: {name}"
        for py_file in files
        for name in _imported_names(_parse(py_file))
        if not _is_allowed(name)
    ]

    assert not violations, "portfolios/domain imports outside stdlib/self:\n" + (
        "\n".join(violations)
    )


def test_domain_package_does_not_call_the_clock() -> None:
    files = sorted(_domain_dir().glob("*.py"))
    assert files

    violations = [
        f"{py_file.name}: {call}()"
        for py_file in files
        for call in _clock_calls(py_file.read_text(encoding="utf-8"))
    ]

    assert not violations, "portfolios/domain reads the clock:\n" + "\n".join(
        violations
    )


def test_repositories_do_not_import_domain() -> None:
    """DOM-3: `repositories/` never imports `domain/`."""
    checked = sorted((_module_dir() / "repositories").glob("*.py"))
    assert checked

    violations = [
        f"{py_file.name}: {name}"
        for py_file in checked
        for name in _imported_names(_parse(py_file))
        if name == ALLOWED_PREFIX or name.startswith(ALLOWED_PREFIX + ".")
    ]

    assert not violations, "repositories/ import the domain:\n" + "\n".join(violations)


def test_domain_files_are_layered_without_cycles() -> None:
    """DOM-9: a domain file imports another domain submodule only at the same
    or a lower level, and the import graph has no cycles."""
    graph: dict[str, set[str]] = {}
    for py_file in sorted(_domain_dir().glob("*.py")):
        if py_file.stem == "__init__":
            continue
        assert py_file.stem in DOMAIN_LAYERS, (
            f"{py_file.name} has no assigned layer in DOMAIN_LAYERS"
        )
        graph[py_file.stem] = _domain_submodule_imports(_parse(py_file))

    upward = [
        f"{module} (level {DOMAIN_LAYERS[module]}) imports "
        f"{imported} (level {DOMAIN_LAYERS[imported]})"
        for module, imports in graph.items()
        for imported in imports
        if DOMAIN_LAYERS[imported] > DOMAIN_LAYERS[module]
    ]
    assert not upward, "domain imports point upward:\n" + "\n".join(upward)

    visiting: set[str] = set()
    visited: set[str] = set()
    cycle: list[str] = []

    def _visit(node: str, path: list[str]) -> bool:
        if node in visiting:
            cycle.extend([*path, node])
            return True
        if node in visited:
            return False
        visiting.add(node)
        for neighbor in graph.get(node, ()):
            if _visit(neighbor, [*path, node]):
                return True
        visiting.discard(node)
        visited.add(node)
        return False

    for module in graph:
        if module not in visited and _visit(module, []):
            break

    assert not cycle, "cycle in domain imports: " + " -> ".join(cycle)


def test_consumers_import_domain_only_from_its_public_init() -> None:
    """DOM-11: `services/`, `models/`, `schemas/`, `api/` and `wiring.py`
    import only `app.modules.portfolios.domain` itself, never a submodule."""
    module_dir = _module_dir()
    checked = [
        *sorted((module_dir / "services").glob("*.py")),
        *sorted((module_dir / "models").glob("*.py")),
        *sorted((module_dir / "schemas").glob("*.py")),
        *sorted((module_dir / "api").glob("*.py")),
        module_dir / "wiring.py",
    ]

    violations = [
        f"{py_file.name}: {module}"
        for py_file in checked
        for module in _direct_submodule_imports(_parse(py_file))
    ]

    assert not violations, (
        "import app.modules.portfolios.domain.<submodule> directly, bypassing "
        "domain/__init__.py's public API:\n" + "\n".join(violations)
    )


def test_api_does_not_import_domain() -> None:
    """DOM-3: `api/` reaches the domain only through a service."""
    violations = [
        f"{py_file.name}: {name}"
        for py_file in sorted((_module_dir() / "api").glob("*.py"))
        for name in _imported_names(_parse(py_file))
        if name == ALLOWED_PREFIX or name.startswith(ALLOWED_PREFIX + ".")
    ]

    assert not violations, "api/ imports the domain:\n" + "\n".join(violations)
