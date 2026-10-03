# FundTracker (found-tracker)

Osobista aplikacja do śledzenia inwestycji finansowych (akcje, fundusze, obligacje) — zakupy,
sprzedaże, wpłaty/wypłaty, przeliczanie metryk portfela, wykresy w czasie.

**Backend (FastAPI, `backend/`) zastąpił dawną aplikację Django; `backend-old/` usunięto 2026-10-01.**
Docelowa architektura: Layered Modular Monolith wzorowany na projekcie
`waterworks-monitoring-platform` (źródło prawdy dla wzorca), opisana w
[`docs/technical/backend/01_backend-architecture.md`](docs/technical/backend/01_backend-architecture.md).

**Zanim zaczniesz czegokolwiek szukać w `docs/`, przeczytaj
[`docs/00_KNOWLEDGE-MAP.md`](docs/00_KNOWLEDGE-MAP.md)** — jedyny punkt wejścia do bazy wiedzy
(słownik, architektura, ADR-y, plan). Przed refaktoryzacją modułu przeczytaj jego dokument w
`docs/technical/backend/` (tabela „Stan vs cel") i
[plan refaktoryzacji](docs/plans/01_refaktoryzacja_do_wzorca_waterworks.md).

## Commands

**Backend** (`cd backend`, wymaga aktywnego `.venv` z korzenia repo):

| Task | Command |
|------|---------|
| Install | `pip install -r requirements-dev.txt` (dev/CI: with ruff, mypy, pytest); `pip install -r requirements.txt` (production only) |
| Run (dev) | `uvicorn app.main:app --reload` |
| Test | `pytest` — wymaga jednorazowej bazy Postgres w `TEST_DATABASE_URL` (albo lokalnego `DATABASE_URL`); `conftest.py` odmawia startu na nielokalnej bazie. Bez bazy: `pytest -m "not integration"` |
| Lint | `ruff check .` (verified) |
| Format check | `ruff format --check .` (verified) |
| Typecheck | `mypy app` — konfiguracja (`strict`, py3.14) w `pyproject.toml`; `mypy==2.3.0` w `requirements-dev.txt` |
| Migration status | `alembic current` |
| Migration apply | `alembic upgrade head` |
| Migration create | `alembic revision --autogenerate -m "..."` |

**Frontend** (`cd frontend`):

| Task | Command |
|------|---------|
| Install | `npm install` |
| Run (dev) | `npm run dev` |
| Build (+ typecheck) | `npm run build` (`tsc -b && vite build`) |
| Lint | `npm run lint` |

## Layout

- `backend/app/modules/{security,core_data,assets,portfolios}/` — moduły domenowe. Docelowo
  każdy ma `api/`, `services/`, `repositories/`, `schemas/`, `models/`, `dependencies.py`,
  `wiring.py`, `tests/{unit,integration}/`; opcjonalnie `domain/` (logika bez ORM/sesji/zegara,
  [ADR-0005](docs/technical/adr/0005-warstwa-domeny.md) — dziś ma go `portfolios`) i
  `entrypoints.py` (operacje spoza HTTP). Wszystkie cztery moduły mają już strukturę docelową
  (R-04…R-08); nowy kod pisz w tym samym stylu.
- `backend/app/infrastructure/sql/` — silnik SQLAlchemy, fabryka sesji, rejestr modeli.
- `backend/app/infrastructure/market_data/` — adapter Yahoo Finance (`yfinance` importowany
  tylko tutaj); port `MarketDataProvider` w `core/market_data.py`, wybór adaptera w
  `assets/wiring.py`.
- `backend/app/core/` — konfiguracja (`pydantic-settings`, `.env`), zależności współdzielone,
  `errors.py`, `schemas.py` (`DecimalNumber`), porty współdzielone.
- `backend/alembic/` — migracje.
- `frontend/src/` — React (Vite, MUI, TanStack Query/Table, Recharts) — nieruszany podczas
  migracji backendu, konsumuje REST API.

## Constraints

**Git.** Nie wykonuj `commit`, `push`, `rebase`, `merge`, `reset` bez wyraźnej zgody w
rozmowie.

**Python environment.** Cały Python przechodzi przez `.venv` w katalogu głównym repo, nigdy
przez interpreter systemowy. Instalacja zależności wymaga zgody.

**Granice modułów** (z [`01_backend-architecture.md` §2](docs/technical/backend/01_backend-architecture.md#2-zasady-architektury)):
API może zależeć od services/errors/core; services od repositories/domain/serwisów innych
modułów/errors/core; domain tylko od biblioteki standardowej; repositories od
infrastructure/errors/core; infrastructure tylko od core/errors. Zakaz: logiki biznesowej w
routerach, importów API → repositories, serwisu trzymającego cudze repozytorium, cykli między
modułami ([ADR-0006](docs/technical/adr/0006-cross-module-wylacznie-przez-serwisy.md)).

**Transakcje i sesje.** Repozytorium nie commituje; granicę commitu wyznacza serwis przez
`repo.transaction()` ([ADR-0001](docs/technical/adr/0001-jedna-sesja-na-request.md)). Serwis nie
zna `Session`. Obiekty składa tylko `wiring.py`; sesję poza żądaniem HTTP otwiera tylko
`entrypoints.py` przez `session_scope()`
([ADR-0002](docs/technical/adr/0002-sesja-poza-zadaniem-entrypointy-i-wiring.md),
[`06_wiring_i_entrypointy.md`](docs/technical/backend/06_wiring_i_entrypointy.md)).

**Błędy.** Serwisy rzucają wyjątki z `core/errors.py` (`APIError` z `code`), nigdy
`HTTPException` ani goły `ValueError` do routera
([ADR-0007](docs/technical/adr/0007-kontrakt-bledow-z-code.md)). Kwoty, ceny, ilości i kursy
to `Decimal`, nie `float` ([ADR-0010](docs/technical/adr/0010-decimal-i-precyzja-pieniedzy.md)).

**Schematy Pydantic żądań na granicy modułu** używają `extra="forbid"`.

**ADR-y** w `docs/technical/adr/` (techniczne) i `docs/business/adr/` (biznesowe), numeracja od
`0001`, status `Proposed` dopóki człowiek nie zaakceptuje — agent nie przełącza sam na
`Accepted`. Nowy dokument → wpis w [`docs/00_KNOWLEDGE-MAP.md`](docs/00_KNOWLEDGE-MAP.md).

> **Stan vs cel.** Moduły realizują opisane wyżej reguły (egzekwuje je
> `core/tests/test_architecture.py`); otwarte kroki to m.in. `mypy` (R-10), reguły ai-tools
> (R-11), CI (R-12) — sprawdź tabelę w [§10 architektury](docs/technical/backend/01_backend-architecture.md#10-stan-kodu-vs-cel)
> i [plan refaktoryzacji](docs/plans/01_refaktoryzacja_do_wzorca_waterworks.md). ADR-y wciąż
> mają status `Proposed` — do ich akceptacji nie przepisuj istniejącego kodu „przy okazji".

**Migracje tylko przez `alembic revision --autogenerate -m "..."`.** Nigdy nie edytuj pliku
migracji ręcznie — desynchronizuje łańcuch i psuje upgrade.

**Django (`backend-old/`) usunięto** (ADR-0009, usunięty razem z katalogiem).
Katalog nie był w git, więc nie ma go w historii; zgodność reguł z Django chronią testy
parytetu w `portfolios/tests/unit/test_ledger_parity.py`. Test architektury zabrania importów
z Django.

**`python-jose`** — `backend/requirements.txt` wymaga `>=3.4.0` (próg z `security-checklist`,
CVE-2024-33663/33664/29370); w HEAD było `3.3.0`, poprawka jest w niezacommitowanym drzewie
roboczym. Jeśli dotykasz auth/JWT, sprawdź wersję zainstalowaną w `.venv`. Świadome odstępstwa
od checklisty (HS256, `localStorage`, stateless refresh):
[ADR-0012](docs/technical/adr/0012-jwt-odstepstwa-od-checklisty.md).

## Domain vocabulary

| Term | Meaning |
|------|---------|
| Portfolio (`portfolios_portfolio`) | Portfel inwestycyjny użytkownika (w Django: `Pocket`) |
| Position (`portfolios_position`) | Pozycja — stan posiadania danego waloru w portfelu |
| Operation (`portfolios_operation`) | Zdarzenie: kupno, sprzedaż, wpłata, wypłata, dywidenda |
| Asset / AssetClass | Walor (akcja, fundusz, obligacja) i jego klasa |
| Currency | Waluta rozliczeniowa operacji/waloru |

Pełny słownik z listą „unikać": [`docs/business/CONTEXT.md`](docs/business/CONTEXT.md).

## AI Tools Integration

Reguły (`python-coding-standards`, `typescript-coding-standards`, `error-handling-patterns`,
`security-checklist`) w `.claude/rules/ai-tools/` są **kopiami** z
[ai-tools](https://github.com/lukaszpiasecki13/ai-tools) (single source of truth). Zmiany w
`ai-tools/rules/` nie propagują się automatycznie — po aktualizacji uruchom ręcznie:

```
python <ai-tools>/scripts/install.py --target . --only error-handling-patterns,python-coding-standards,security-checklist,typescript-coding-standards,architecture-decisions,knowledge-base
```

Reguły `architecture-decisions` i `knowledge-base` są zainstalowane (R-11); szablony ADR i
dokumentów oraz `METADATA.md` — `.claude/skills/knowledge-base/`. Walidator dokumentów:
`.venv/Scripts/python.exe .claude/skills/knowledge-base/scripts/kb_validate.py --root . --strict`. Uwaga: reguła `architecture-decisions` wskazuje
`docs/business/bdr/` dla decyzji biznesowych, a ten projekt trzyma je w `docs/business/adr/`
(konwencja projektu wygrywa).

Agenty, skille i hooki (m.in. `code-reviewer`, `explorer`, `commit`, `fastapi-endpoint`,
`react-patterns`) pochodzą z pluginu ai-tools — zainstaluj go raz, globalnie:

```
/plugin marketplace add lukaszpiasecki13/ai-tools
/plugin install ai-tools@ai-tools
```
