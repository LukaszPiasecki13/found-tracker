---
id: kb-python314-except
status: current
last_reviewed: 2026-10-01
type: fact
scope: backend/python-314-syntax
applies_to:
  - backend/app/infrastructure/market_data/yahoo.py
---

# Python 3.14: `except A, B:` bez nawiasów to poprawna składnia

**Data:** 2026-10-01
**Źródło:** `ast.parse` pod CPython **3.14.3** oraz `ruff check` i `mypy app` przechodzące na [`yahoo.py`](../../../backend/app/infrastructure/market_data/yahoo.py)

```python
except InvalidOperation, ValueError:
    return None
```

Wygląda jak Python 2 (`except Exception, e:`, gdzie przecinek wiązał zmienną), ale od **3.14** (PEP 758) jest listą typów wyjątków. Nie zgłaszaj tego jako błędu składni.

Sprawdzenie: `python -c "import ast; ast.parse('try:\n  pass\nexcept A, B:\n  pass')"`.

**Ograniczenie:** przy wiązaniu do nazwy nawiasy są nadal obowiązkowe: `except (A, B) as err:`.
