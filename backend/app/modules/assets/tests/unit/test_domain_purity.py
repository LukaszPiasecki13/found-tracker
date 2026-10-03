"""Architecture invariant: `assets/domain/` is pure (ADR-0005): standard library
only, no `app.*` import other than its own package, no clock."""

import ast
from pathlib import Path

ALLOWED_MODULES = {
    "collections",
    "collections.abc",
    "datetime",
    "decimal",
    "re",
    "typing",
}
ALLOWED_PREFIX = "app.modules.assets.domain"
FORBIDDEN_CLOCK_CALLS = ("now", "utcnow", "today")


def _domain_dir() -> Path:
    # This file lives at assets/tests/unit/; parents[2] is `assets`.
    assets_dir = Path(__file__).resolve().parents[2]
    assert assets_dir.name == "assets", assets_dir
    return assets_dir / "domain"


def _files() -> list[Path]:
    files = sorted(_domain_dir().glob("*.py"))
    assert files, "assets/domain/ has no files - the test would pass vacuously"
    return files


def test_domain_imports_only_the_standard_library_and_itself() -> None:
    offenders = []
    for path in _files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            offenders += [
                f"{path.name}: {name}"
                for name in names
                if name not in ALLOWED_MODULES and not name.startswith(ALLOWED_PREFIX)
            ]
    assert offenders == []


def test_domain_does_not_read_the_clock() -> None:
    offenders = []
    for path in _files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in FORBIDDEN_CLOCK_CALLS
            ):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []
