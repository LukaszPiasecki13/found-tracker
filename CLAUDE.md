# FundTracker (found-tracker)

Osobista aplikacja do śledzenia inwestycji finansowych (akcje, fundusze, obligacje) — zakupy,
sprzedaże, wpłaty/wypłaty, przeliczanie metryk portfela, wykresy w czasie.

**Backend jest w trakcie migracji z Django (`backend-old/`) na FastAPI (`backend/`).**
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
| Install | `pip install -r requirements.txt` |
| Run (dev) | `uvicorn app.main:app --reload` |
| Test | `pytest` — wymaga prawdziwego `DATABASE_URL` (Postgres, `psycopg2`); brak fallbacku na sqlite |
| Lint | `ruff check .` (verified) |
| Format check | `ruff format --check .` (verified) |
| Typecheck | `mypy app` — konfiguracja (`strict`, py3.14) jest w `pyproject.toml`, ale **`mypy` nie jest jeszcze zainstalowany w `.venv`** — doinstaluj przed użyciem |
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
  [ADR-0005](docs/technical/adr/0005-warstwa-domeny.md) — dziś planowany dla `portfolios`) i
  `entrypoints.py` (operacje spoza HTTP). **Migracja w toku** — `assets` jest już rozbity na
  podfoldery, `core_data`, `security` i `portfolios` wciąż mają płaskie pliki. Nie mieszaj
  stylów w jednym module podczas edycji — jeśli dotykasz modułu, doprowadź go do docelowej
  struktury.
- `backend/app/infrastructure/sql/` — silnik SQLAlchemy, fabryka sesji, rejestr modeli.
- `backend/app/core/` — konfiguracja (`pydantic-settings`, `.env`), zależności współdzielone.
- `backend/alembic/` — migracje.
- `backend-old/` — **stara aplikacja Django**, referencja logiki biznesowej na czas migracji.
  Nie importuj z niej i nie dodawaj tam nowych funkcji — zostanie usunięta po zakończeniu
  przepisywania.
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

> **Stan vs cel.** Opisane wyżej reguły są **celem**; kod jest w połowie drogi (brak
> `core/errors.py`, `transaction()`, `session_scope`, `wiring.py`). Nie zakładaj, że istnieją —
> sprawdź tabelę w [§10 architektury](docs/technical/backend/01_backend-architecture.md#10-stan-kodu-vs-cel)
> i [plan refaktoryzacji](docs/plans/01_refaktoryzacja_do_wzorca_waterworks.md). Do czasu
> akceptacji ADR-ów nie przepisuj istniejącego kodu „przy okazji".

**Migracje tylko przez `alembic revision --autogenerate -m "..."`.** Nigdy nie edytuj pliku
migracji ręcznie — desynchronizuje łańcuch i psuje upgrade.

**`backend-old/` to referencja, nie kod produkcyjny.** Czytaj go, żeby zrozumieć obecne
zachowanie (np. logikę w `portfolios/services/`, `portfolios/analytics/`), ale całą nową
logikę pisz w `backend/app/`.

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
python <ai-tools>/scripts/install.py --target . --only error-handling-patterns,python-coding-standards,security-checklist,typescript-coding-standards
```

Reguły `architecture-decisions` i `knowledge-base` (obecne w waterworks) nie są jeszcze
zainstalowane — krok R-11 planu; do tego czasu ADR-y i dokumenty piszemy według
`.claude/skills/knowledge-base/` (szablony, `METADATA.md`). Walidator dokumentów:
`.venv/Scripts/python.exe .claude/skills/knowledge-base/scripts/kb_validate.py --root . --strict`
(dodaj `--exclude "backend-old/**"`).

Agenty, skille i hooki (m.in. `code-reviewer`, `explorer`, `commit`, `fastapi-endpoint`,
`react-patterns`) pochodzą z pluginu ai-tools — zainstaluj go raz, globalnie:

```
/plugin marketplace add lukaszpiasecki13/ai-tools
/plugin install ai-tools@ai-tools
```
