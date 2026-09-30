"""Architecture invariants of ADR-0002 (`wiring.py`/`entrypoints.py`/`session_scope`):
R1, R4, R5, R8, and where `Session(...)`/`sessionmaker(...)`/`session_scope` may be
used at all.

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
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]

_SESSION_OPENING_CALLS = {"Session", "sessionmaker", "session_scope"}
_MODULE_DEPENDENCIES_RE = re.compile(r"^app\.modules\.[^.]+\.dependencies(\.|$)")
_MODULE_SERVICES_RE = re.compile(
    r"^app\.modules\.[^.]+\.(services|repositories|wiring)(\.|$)"
)
_MODULE_REPOSITORIES_RE = re.compile(r"^app\.modules\.[^.]+\.repositories(\.|$)")


# Files not yet migrated to the target architecture (refactor plan R-04...R-07).
# Each entry is a debt, not a licence: the list only shrinks. A stale entry (the
# file no longer violates) fails `test_legacy_allowlist_has_no_stale_entries`.
_LEGACY_R1_FASTAPI_IMPORTS = frozenset(
    {
        "modules/security/services/auth.py",  # HTTPException -> R-06
    }
)


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
    """Line numbers of calls whose callee is a bare Name in
    `_SESSION_OPENING_CALLS` (`Session(...)`, `sessionmaker(...)`,
    `session_scope()`, called by that literal name — not through a
    locally-bound parameter, e.g. `entrypoints.py`'s `scope()`)."""
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _SESSION_OPENING_CALLS
    ]


def _imports_fastapi(names: set[str]) -> bool:
    return any(name == "fastapi" or name.startswith("fastapi.") for name in names)


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


def test_legacy_allowlist_has_no_stale_entries() -> None:
    stale = [
        entry
        for entry in _LEGACY_R1_FASTAPI_IMPORTS
        if not (APP_ROOT / entry).is_file()
        or not _imports_fastapi(_imported_names(_parse(APP_ROOT / entry)))
    ]

    assert not stale, f"Remove migrated files from the legacy allowlist: {stale}"
