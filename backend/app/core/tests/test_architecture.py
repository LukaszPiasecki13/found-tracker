"""Architecture invariants of ADR-0002 (`wiring.py`/`entrypoints.py`/`session_scope`):
R1, R4, R5, R8, and where `Session(...)`/`sessionmaker(...)`/`session_scope` may be
used at all. Plus the layer rules of `01_backend-architecture.md` §2 that every
module now meets (refactor plan R-09): `api/` imports no repositories and no ORM
models (except `User` for `get_current_user` typing), no `HTTPException` outside
`dependencies.py` (ADR-0007), nothing from Django / `backend-old/` (ADR-0009),
and `yfinance` only in `infrastructure/` (the market-data adapter). The purity of
a module's `domain/` is checked by that module's own `test_domain_purity.py`.

AST-based, anchored on this file's own path - pytest runs from `backend/`, where a
cwd-relative `Path("backend/app")` would resolve to nothing and these tests would
pass without scanning a single file. `backend/seed/` is deliberately out of scope:
standalone scripts call `session_scope()` directly rather than through a module's
`entrypoints.py`.

Lives in `core/tests/` (cross-cutting, not owned by one business module - see
`test_provide.py` in this same directory): `pyproject.toml`'s
`testpaths = ["app"]` never collects a `backend/tests/` directory.
"""

import ast
import re
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
BACKEND_OLD_ROOT = APP_ROOT.parents[1] / "backend-old"

_SESSION_OPENING_CALLS = {"Session", "sessionmaker", "session_scope"}
_MODULE_DEPENDENCIES_RE = re.compile(r"^app\.modules\.[^.]+\.dependencies(\.|$)")
_MODULE_SERVICES_RE = re.compile(
    r"^app\.modules\.[^.]+\.(services|repositories|wiring)(\.|$)"
)
_MODULE_REPOSITORIES_RE = re.compile(r"^app\.modules\.[^.]+\.repositories(\.|$)")
_MODULE_REPOSITORIES_OR_MODELS_RE = re.compile(
    r"^app\.modules\.[^.]+\.(repositories|models)(\.|$)"
)
# `api/` may type `get_current_user`'s result with the `User` ORM model.
_API_ALLOWED_MODEL_IMPORTS_RE = re.compile(r"^app\.modules\.core_data\.models(\.|$)")
# Top-level packages of the Django application; `backend-old/` itself is not
# importable (hyphen), only its apps are, through a `sys.path` change.
_DJANGO_PACKAGES = frozenset({"django", "rest_framework"})


# Files not yet migrated to the target architecture (refactor plan R-04...R-07).
# Each entry is a debt, not a licence: the list only shrinks. A stale entry (the
# file no longer violates) fails `test_legacy_allowlist_has_no_stale_entries`.
_LEGACY_R1_FASTAPI_IMPORTS: frozenset[str] = frozenset()


def _relative(path: Path) -> str:
    return path.relative_to(APP_ROOT).as_posix()


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _iter_py_files(root: Path) -> list[Path]:
    return [
        p
        for p in root.rglob("*.py")
        if "tests" not in p.parts and p.name != "conftest.py"
    ]


def _module_dirs() -> list[Path]:
    modules_root = APP_ROOT / "modules"
    return [p for p in modules_root.iterdir() if p.is_dir() and p.name != "__pycache__"]


def _imported_names(tree: ast.Module) -> set[str]:
    """Every fully-qualified name reachable via import in this module, at any
    nesting (including under `if TYPE_CHECKING:`): both the imported module
    path and, for `from x import y`, `x.y` — matches by prefix elsewhere, not
    equality, so `from app.modules import assets` is not missed.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue  # relative import: cannot reach another module
            names.add(node.module)
            for alias in node.names:
                names.add(f"{node.module}.{alias.name}")
    return names


def _calls_opening_a_session(tree: ast.Module) -> list[int]:
    """Line numbers of calls to `Session(...)`, `sessionmaker(...)` or
    `session_scope()` by that literal name, bare or as an attribute
    (`orm.Session(...)`) — not through a locally-bound parameter, e.g.
    `entrypoints.py`'s `scope()`."""
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id in _SESSION_OPENING_CALLS)
            or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in _SESSION_OPENING_CALLS
            )
        )
    ]


def _imports_fastapi(names: set[str]) -> bool:
    return any(name == "fastapi" or name.startswith("fastapi.") for name in names)


def _all_app_files() -> list[Path]:
    """Every `.py` under `backend/app/`, tests included."""
    return [p for p in APP_ROOT.rglob("*.py") if "__pycache__" not in p.parts]


def _api_files() -> list[Path]:
    return [
        py_file
        for module_dir in _module_dirs()
        if (module_dir / "api").is_dir()
        for py_file in _iter_py_files(module_dir / "api")
    ]


def _forbidden_api_imports(names: set[str]) -> list[str]:
    return sorted(
        name
        for name in names
        if _MODULE_REPOSITORIES_OR_MODELS_RE.match(name)
        and not _API_ALLOWED_MODEL_IMPORTS_RE.match(name)
    )


def _http_exception_lines(tree: ast.Module) -> list[int]:
    """Lines that import or use `HTTPException` (bare name, attribute, alias)."""

    def mentions(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id == "HTTPException"
        if isinstance(node, ast.Attribute):
            return node.attr == "HTTPException"
        if isinstance(node, ast.ImportFrom):
            return any(alias.name == "HTTPException" for alias in node.names)
        return False

    return sorted(
        {getattr(node, "lineno", 0) for node in ast.walk(tree) if mentions(node)}
    )


def _backend_old_packages() -> frozenset[str]:
    """The Django apps of `backend-old/` (empty once it is deleted, R-13)."""
    if not BACKEND_OLD_ROOT.is_dir():
        return frozenset()
    return frozenset(
        p.name
        for p in BACKEND_OLD_ROOT.iterdir()
        if p.is_dir() and (p / "__init__.py").is_file()
    )


def _legacy_imports(names: set[str], forbidden_top_levels: frozenset[str]) -> list[str]:
    return sorted(name for name in names if name.split(".")[0] in forbidden_top_levels)


def _imports_yfinance(names: set[str]) -> bool:
    return any(name == "yfinance" or name.startswith("yfinance.") for name in names)


def test_app_root_is_correctly_anchored() -> None:
    assert APP_ROOT.name == "app", APP_ROOT
    assert (APP_ROOT / "main.py").is_file()


def test_the_detectors_catch_every_form() -> None:
    """Guards the two checkers above: a silent false negative here would let
    the real tests below pass vacuously."""
    dependencies_import = ast.parse(
        "from app.modules.security.dependencies import get_x"
    )
    assert any(
        _MODULE_DEPENDENCIES_RE.match(name)
        for name in _imported_names(dependencies_import)
    )
    core_dependencies_import = ast.parse(
        "from app.core.dependencies import session_scope"
    )
    assert not any(
        _MODULE_DEPENDENCIES_RE.match(name)
        for name in _imported_names(core_dependencies_import)
    )

    services_import = ast.parse("import app.modules.assets.services.assets as x")
    assert any(
        _MODULE_SERVICES_RE.match(name) for name in _imported_names(services_import)
    )
    api_import = ast.parse("from app.modules.assets import api")
    assert not any(
        _MODULE_SERVICES_RE.match(name) for name in _imported_names(api_import)
    )

    fastapi_import = ast.parse("from fastapi import Depends")
    assert _imports_fastapi(_imported_names(fastapi_import))
    unrelated_import = ast.parse("from fastapi_events import x")
    assert not _imports_fastapi(_imported_names(unrelated_import))

    raw_session = ast.parse("with Session(engine) as session: pass")
    assert _calls_opening_a_session(raw_session)
    via_scope_param = ast.parse("with scope() as session: pass")
    assert not _calls_opening_a_session(via_scope_param)


def test_r1_services_and_repositories_do_not_open_sessions_or_import_fastapi() -> None:
    violations: list[str] = []
    files_scanned = 0

    for module_dir in _module_dirs():
        for subpackage in ("services", "repositories"):
            package_dir = module_dir / subpackage
            if not package_dir.is_dir():
                continue
            for py_file in _iter_py_files(package_dir):
                files_scanned += 1
                tree = _parse(py_file)
                if (
                    _imports_fastapi(_imported_names(tree))
                    and _relative(py_file) not in _LEGACY_R1_FASTAPI_IMPORTS
                ):
                    violations.append(f"{py_file}: imports fastapi")
                violations.extend(
                    f"{py_file}:{lineno}: opens a session"
                    for lineno in _calls_opening_a_session(tree)
                )

    assert files_scanned > 0, (
        f"No .py files found under {APP_ROOT}/modules/*/services|repositories"
    )
    assert not violations, "R1 violated:\n" + "\n".join(violations)


def test_r4_wiring_entrypoints_and_services_do_not_import_any_dependencies_py() -> None:
    violations: list[str] = []
    files_scanned = 0

    for module_dir in _module_dirs():
        targets = [
            f
            for f in (module_dir / "wiring.py", module_dir / "entrypoints.py")
            if f.is_file()
        ]
        services_dir = module_dir / "services"
        if services_dir.is_dir():
            targets.extend(_iter_py_files(services_dir))

        for py_file in targets:
            files_scanned += 1
            tree = _parse(py_file)
            violations.extend(
                f"{py_file}: imports {name}"
                for name in _imported_names(tree)
                if _MODULE_DEPENDENCIES_RE.match(name)
            )

    assert files_scanned > 0, (
        f"No wiring.py/entrypoints.py/services found under {APP_ROOT}/modules"
    )
    assert not violations, "R4 violated:\n" + "\n".join(violations)


def test_r5_entrypoints_do_not_import_repositories_or_fastapi() -> None:
    violations: list[str] = []

    for module_dir in _module_dirs():
        entrypoints_file = module_dir / "entrypoints.py"
        if not entrypoints_file.is_file():
            continue
        tree = _parse(entrypoints_file)
        names = _imported_names(tree)
        if _imports_fastapi(names):
            violations.append(f"{entrypoints_file}: imports fastapi")
        violations.extend(
            f"{entrypoints_file}: imports {name}"
            for name in names
            if _MODULE_REPOSITORIES_RE.match(name)
        )

    # `entrypoints.py` exists only in a module with a non-HTTP operation, so
    # scanning zero files is legitimate until the first one appears.
    assert not violations, "R5 violated:\n" + "\n".join(violations)


def test_r8_drivers_call_only_entrypoints() -> None:
    # `cli.py` is optional: it does not exist until the first CLI command does.
    drivers = [d for d in (APP_ROOT / "main.py", APP_ROOT / "cli.py") if d.is_file()]
    violations: list[str] = []
    files_scanned = 0

    for driver in drivers:
        files_scanned += 1
        tree = _parse(driver)
        violations.extend(
            f"{driver}: imports {name}"
            for name in _imported_names(tree)
            if _MODULE_SERVICES_RE.match(name)
        )
        violations.extend(
            f"{driver}:{lineno}: opens a session directly"
            for lineno in _calls_opening_a_session(tree)
        )

    assert files_scanned >= 1
    assert not violations, "R8 violated:\n" + "\n".join(violations)


def test_session_scope_and_raw_session_are_confined() -> None:
    """`Session(...)`/`sessionmaker(...)`/`session_scope()` appear, under
    `backend/app/`, only in `core/`, `infrastructure/` or a module's
    `entrypoints.py` — never in tests-excluded business-module code."""
    allowed_dirs = (APP_ROOT / "core", APP_ROOT / "infrastructure")
    violations: list[str] = []
    files_scanned = 0

    for py_file in APP_ROOT.rglob("*.py"):
        if "tests" in py_file.parts or py_file.name == "conftest.py":
            continue
        if any(py_file.is_relative_to(d) for d in allowed_dirs):
            continue
        if py_file.name == "entrypoints.py":
            continue
        files_scanned += 1
        tree = _parse(py_file)
        violations.extend(
            f"{py_file}:{lineno}" for lineno in _calls_opening_a_session(tree)
        )

    assert files_scanned > 0, f"No .py files found under {APP_ROOT}"
    assert not violations, (
        "Session opened outside core/infrastructure/entrypoints.py:\n"
        + "\n".join(violations)
    )


def test_the_layer_detectors_catch_every_form() -> None:
    """Guards the checkers of the layer rules below against false negatives."""

    def names(source: str) -> set[str]:
        return _imported_names(ast.parse(source))

    for source in (
        "from app.modules.assets.repositories.assets import AssetRepository",
        "from app.modules.assets import repositories",
        "import app.modules.portfolios.repositories.operations as ops",
        "from app.modules.portfolios.models import Portfolio",
        "from app.modules.assets.models.assets import Asset",
    ):
        assert _forbidden_api_imports(names(source)), source
    for source in (
        "from app.modules.core_data.models.user import User",
        "from app.modules.portfolios.schemas.portfolios import PortfolioResponse",
        "from app.modules.portfolios.services.portfolios import PortfolioService",
    ):
        assert not _forbidden_api_imports(names(source)), source

    for source in (
        "from fastapi import HTTPException",
        "from starlette.exceptions import HTTPException as StarletteError",
        "import fastapi\nraise fastapi.HTTPException(404)",
        "def f(e=HTTPException): pass",
    ):
        assert _http_exception_lines(ast.parse(source)), source
    assert not _http_exception_lines(ast.parse("raise NotFoundError('x')"))

    old_apps = frozenset({"portfolios", "authentication"})
    assert _legacy_imports(names("from portfolios.models import Pocket"), old_apps)
    assert _legacy_imports(names("import authentication.models"), old_apps)
    assert _legacy_imports(names("from django.db import models"), _DJANGO_PACKAGES)
    assert _legacy_imports(names("import rest_framework"), _DJANGO_PACKAGES)
    assert not _legacy_imports(
        names("from app.modules.portfolios.models import Portfolio"), old_apps
    )

    assert _imports_yfinance(names("import yfinance as yf"))
    assert _imports_yfinance(names("from yfinance import Ticker"))
    assert not _imports_yfinance(names("import yfinance_cache"))


def test_api_does_not_import_repositories_or_models() -> None:
    """API -> Services only (§2.2, ADR-0006); `User` for `get_current_user`
    typing is the one accepted ORM import."""
    violations: list[str] = []
    files = _api_files()

    for py_file in files:
        violations.extend(
            f"{py_file}: imports {name}"
            for name in _forbidden_api_imports(_imported_names(_parse(py_file)))
        )

    assert files, f"No api/ files found under {APP_ROOT}/modules"
    assert not violations, "API imports repositories/models:\n" + "\n".join(violations)


def test_http_exception_only_in_dependencies() -> None:
    """Errors leave modules as `APIError` with a `code` (ADR-0007); only an HTTP
    adapter (`dependencies.py`) could have a reason for `HTTPException`."""
    violations: list[str] = []
    files_scanned = 0

    for module_dir in _module_dirs():
        for py_file in _iter_py_files(module_dir):
            if py_file.name == "dependencies.py":
                continue
            files_scanned += 1
            violations.extend(
                f"{py_file}:{lineno}"
                for lineno in _http_exception_lines(_parse(py_file))
            )

    assert files_scanned > 0
    assert not violations, "HTTPException outside dependencies.py:\n" + "\n".join(
        violations
    )


def test_nothing_imports_django_or_backend_old() -> None:
    """`backend-old/` is a reference to read, never code to import (ADR-0009)."""
    forbidden = _DJANGO_PACKAGES | _backend_old_packages()
    if BACKEND_OLD_ROOT.is_dir():
        assert "portfolios" in forbidden, "backend-old/ apps not detected"
    violations: list[str] = []
    files = _all_app_files()

    for py_file in files:
        violations.extend(
            f"{py_file}: imports {name}"
            for name in _legacy_imports(_imported_names(_parse(py_file)), forbidden)
        )

    assert files
    assert not violations, "Imports from Django/backend-old:\n" + "\n".join(violations)


def test_yfinance_is_imported_only_in_infrastructure() -> None:
    """Market data goes through the `core/market_data.py` port; the Yahoo Finance
    adapter in `infrastructure/market_data/` is the only `yfinance` user."""
    allowed_root = APP_ROOT / "infrastructure"
    violations = [
        str(py_file)
        for py_file in _all_app_files()
        if not py_file.is_relative_to(allowed_root)
        and _imports_yfinance(_imported_names(_parse(py_file)))
    ]

    assert not violations, "yfinance imported outside infrastructure/:\n" + "\n".join(
        violations
    )


def test_legacy_allowlist_has_no_stale_entries() -> None:
    stale = [
        entry
        for entry in _LEGACY_R1_FASTAPI_IMPORTS
        if not (APP_ROOT / entry).is_file()
        or not _imports_fastapi(_imported_names(_parse(APP_ROOT / entry)))
    ]

    assert not stale, f"Remove migrated files from the legacy allowlist: {stale}"


# --- ADR-0006 (cross-module only through services) and ADR-0001 (commit boundary) ---

_CROSS_MODULE_RE = re.compile(r"^app\.modules\.([^.]+)\.(\w+)(?:\.(\w+))?")


def _cross_module_violations(
    names: set[str], own_module: str, *, allow_models: bool
) -> list[str]:
    """Imports of another module's repositories/api, of a submodule of its
    `domain/` (only `domain/__init__.py` is public, DOM-5) and - unless
    `allow_models` - of its ORM models. Services and wiring of another module are
    the sanctioned way in."""
    violations: set[str] = set()
    for name in names:
        match = _CROSS_MODULE_RE.match(name)
        if match is None or match.group(1) == own_module:
            continue
        layer, sub = match.group(2), match.group(3)
        # `from ...domain import Thing` yields `...domain.Thing`: a capitalized
        # name is a public export, a lowercase one is a submodule (DOM-5).
        is_domain_submodule = layer == "domain" and sub is not None and sub[0].islower()
        if (
            layer in {"repositories", "api"}
            or is_domain_submodule
            or (layer == "models" and not allow_models)
        ):
            violations.add(name)
    return sorted(violations)


def test_cross_module_detector_catches_every_form() -> None:
    def violations(source: str, *, allow_models: bool = False) -> list[str]:
        return _cross_module_violations(
            _imported_names(ast.parse(source)), "portfolios", allow_models=allow_models
        )

    assert violations("from app.modules.assets.repositories.assets import X")
    assert violations("import app.modules.assets.repositories.assets as x")
    assert violations("from app.modules.assets.domain.ledger import X")
    assert violations("from app.modules.assets.models.assets import Asset")
    assert not violations(
        "from app.modules.assets.models.assets import Asset", allow_models=True
    )
    assert not violations("from app.modules.assets.services.assets import AssetService")
    assert not violations("from app.modules.assets import wiring as assets_wiring")
    assert not violations("from app.modules.assets.domain import Thing")
    assert not violations("from app.modules.portfolios.repositories.positions import X")


def test_services_and_repositories_reach_other_modules_only_through_services() -> None:
    """ADR-0006: a service or repository never reaches into another module's
    repositories or `api/`, nor into a submodule of its `domain/`; another
    module's services are the way in. Its ORM models may be imported (typing a
    returned entity, JOIN / eager load in a repository)."""
    violations: list[str] = []
    files_scanned = 0
    for module_dir in _module_dirs():
        for subpackage, allow_models in (("services", True), ("repositories", True)):
            package_dir = module_dir / subpackage
            if not package_dir.is_dir():
                continue
            for py_file in _iter_py_files(package_dir):
                files_scanned += 1
                violations.extend(
                    f"{_relative(py_file)}: imports {name}"
                    for name in _cross_module_violations(
                        _imported_names(_parse(py_file)),
                        module_dir.name,
                        allow_models=allow_models,
                    )
                )

    assert files_scanned > 0
    assert not violations, "ADR-0006 violated:\n" + "\n".join(violations)


def test_wiring_does_not_import_fastapi() -> None:
    violations = [
        _relative(wiring)
        for module_dir in _module_dirs()
        if (wiring := module_dir / "wiring.py").is_file()
        and _imports_fastapi(_imported_names(_parse(wiring)))
    ]

    assert not violations, f"wiring.py must not import fastapi: {violations}"


def _commit_or_rollback_lines(tree: ast.Module) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"commit", "rollback"}
    ]


def test_commit_detector_catches_attribute_calls() -> None:
    assert _commit_or_rollback_lines(ast.parse("self.session.commit()"))
    assert _commit_or_rollback_lines(ast.parse("repo.rollback()"))
    assert not _commit_or_rollback_lines(ast.parse("repo.transaction()"))


def test_commit_and_rollback_stay_in_the_transaction_boundary() -> None:
    """ADR-0001: only `SQLRepository` (and the session lifecycle in
    `infrastructure/`) commits or rolls back; modules call `repo.transaction()`."""
    violations: list[str] = []
    for module_dir in _module_dirs():
        for py_file in _iter_py_files(module_dir):
            violations.extend(
                f"{_relative(py_file)}:{lineno}"
                for lineno in _commit_or_rollback_lines(_parse(py_file))
            )

    assert not violations, "commit/rollback outside infrastructure/:\n" + "\n".join(
        violations
    )


# --- No cycles between modules (01_backend-architecture.md §2.4) ---

# `wiring.py` tolerates a cycle (a module import), and the HTTP adapter files
# (`api/`, `dependencies.py`) are left out: `core_data/api` still imports
# `security.dependencies.get_current_user` while `security` depends on
# `core_data` - a known HTTP-level cycle, to be removed by moving the user
# endpoints (`/auth/register`, `/auth/me`) into `security/api`.
_CYCLE_CHECKED_LAYERS = frozenset(
    {"services", "repositories", "models", "schemas", "domain"}
)
_MODULE_IMPORT_RE = re.compile(r"^app\.modules\.([^.]+)(\.|$)")


def _module_dependency_graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for module_dir in _module_dirs():
        dependencies = graph.setdefault(module_dir.name, set())
        for path in _iter_py_files(module_dir):
            relative = path.relative_to(module_dir)
            if relative.parts[0] not in _CYCLE_CHECKED_LAYERS:
                continue
            for name in _imported_names(_parse(path)):
                match = _MODULE_IMPORT_RE.match(name)
                if match and match.group(1) != module_dir.name:
                    dependencies.add(match.group(1))
    return graph


def _find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    def visit(node: str, path: list[str]) -> list[str] | None:
        if node in path:
            return [*path[path.index(node) :], node]
        for neighbour in sorted(graph.get(node, ())):
            cycle = visit(neighbour, [*path, node])
            if cycle:
                return cycle
        return None

    for start in sorted(graph):
        cycle = visit(start, [])
        if cycle:
            return cycle
    return None


def test_cycle_detector_finds_a_cycle() -> None:
    assert _find_cycle({"a": {"b"}, "b": {"c"}, "c": {"a"}}) == ["a", "b", "c", "a"]
    assert _find_cycle({"a": {"b"}, "b": set(), "c": {"b"}}) is None


def test_modules_do_not_depend_on_each_other_in_a_cycle() -> None:
    cycle = _find_cycle(_module_dependency_graph())

    assert cycle is None, "module dependency cycle: " + " -> ".join(cycle or [])


# --- Import parsers (ADR-0018): port in core/, adapters in infrastructure/ ---

_IMPORT_PARSERS_DIR = APP_ROOT / "infrastructure" / "import_parsers"
_IMPORT_PORT = APP_ROOT / "core" / "import_parser.py"
# What an import adapter may use: the standard library, `openpyxl`, `app.core`.
_ADAPTER_THIRD_PARTY = frozenset({"openpyxl"})


def _top_level_imports(names: set[str]) -> set[str]:
    return {name.split(".")[0] for name in names}


def _disallowed_adapter_imports(names: set[str]) -> list[str]:
    """Imports an import adapter must not have: anything that is neither the
    standard library, `openpyxl`, `app.core` nor its own package."""
    return sorted(
        name
        for name in names
        if name.split(".")[0] not in sys.stdlib_module_names | _ADAPTER_THIRD_PARTY
        and name != "app"
        and not name.startswith(("app.core", "app.infrastructure.import_parsers"))
    )


def _imports_openpyxl(names: set[str]) -> bool:
    return "openpyxl" in _top_level_imports(names)


def test_the_import_adapter_detectors_catch_every_form() -> None:
    def names(source: str) -> set[str]:
        return _imported_names(ast.parse(source))

    assert _disallowed_adapter_imports(
        names("from app.modules.assets.services import AssetService")
    )
    assert _disallowed_adapter_imports(names("import requests"))
    assert _disallowed_adapter_imports(names("from sqlalchemy import select"))
    assert not _disallowed_adapter_imports(
        names(
            "from app.core.import_parser import ParsedRow\nfrom zipfile import ZipFile"
        )
    )
    assert not _disallowed_adapter_imports(names("from openpyxl import load_workbook"))
    assert _imports_openpyxl(names("from openpyxl.utils import get_column_letter"))
    assert not _imports_openpyxl(names("import openpyxl_stubs_not_it"))


def test_import_adapters_use_only_stdlib_openpyxl_and_core() -> None:
    """An adapter knows no module, repository or ORM: parsing bytes into rows is
    all it does (ADR-0018); mapping to assets is `ImportService`'s job."""
    files = _iter_py_files(_IMPORT_PARSERS_DIR)

    violations = [
        f"{_relative(py_file)}: imports {name}"
        for py_file in files
        for name in _disallowed_adapter_imports(_imported_names(_parse(py_file)))
    ]

    assert files, f"No adapters found under {_IMPORT_PARSERS_DIR}"
    assert not violations, "\n".join(violations)


def test_the_import_port_is_free_of_modules_and_infrastructure() -> None:
    names = _imported_names(_parse(_IMPORT_PORT))

    forbidden = sorted(
        name for name in names if name.startswith(("app.modules", "app.infrastructure"))
    )

    assert not forbidden, f"core/import_parser.py imports {forbidden}"


def test_openpyxl_is_imported_only_by_the_import_adapters() -> None:
    """Production code only: a test may build a workbook to feed a parser."""
    violations = [
        _relative(py_file)
        for py_file in _iter_py_files(APP_ROOT)
        if not py_file.is_relative_to(_IMPORT_PARSERS_DIR)
        and _imports_openpyxl(_imported_names(_parse(py_file)))
    ]

    assert not violations, "openpyxl imported outside import_parsers/:\n" + "\n".join(
        violations
    )
