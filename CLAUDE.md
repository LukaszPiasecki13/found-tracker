# FundTracker (found-tracker)

Osobista aplikacja do śledzenia inwestycji finansowych (akcje, fundusze, obligacje) — zakupy,
sprzedaże, wpłaty/wypłaty, przeliczanie metryk portfela, wykresy w czasie.

**Backend jest w trakcie migracji z Django (`backend-old/`) na FastAPI (`backend/`).**
Docelowa architektura: Layered Modular Monolith, opisana w
[`docs/backend-architecture-plan.md`](docs/backend-architecture-plan.md) — przeczytaj ten
dokument przed refaktoryzacją dowolnego modułu backendu.

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
  każdy ma `api/`, `services/`, `repositories/`, `schemas/`, `models/`, `dependencies.py`
  (patrz plan architektury). **Migracja w toku** — `assets` jest już rozbity na podfoldery,
  `core_data` i `security` wciąż mają płaskie pliki (`api.py`, `models.py`, ...). Nie mieszaj
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

**Granice modułów** (z [`docs/backend-architecture-plan.md`](docs/backend-architecture-plan.md)):
API może zależeć od services/errors/core; services od repositories/kontraktów innych modułów/
errors/core; repositories od infrastructure/errors/core; infrastructure tylko od core/errors.
Zakaz: logiki biznesowej w routerach, bezpośrednich importów API → repositories, cykli między
modułami.

**Migracje tylko przez `alembic revision --autogenerate -m "..."`.** Nigdy nie edytuj pliku
migracji ręcznie — desynchronizuje łańcuch i psuje upgrade.

**`backend-old/` to referencja, nie kod produkcyjny.** Czytaj go, żeby zrozumieć obecne
zachowanie (np. logikę w `portfolios/services/`, `portfolios/analytics/`), ale całą nową
logikę pisz w `backend/app/`.

**`python-jose` w `backend/requirements.txt` jest przypięty na `3.3.0`** — poniżej progu
bezpieczeństwa `>=3.4.0` z reguły `security-checklist` (CVE-2024-33663, CVE-2024-33664,
CVE-2024-29370). Jeśli dotykasz auth/JWT, zgłoś to i zaproponuj podbicie wersji zamiast
ignorować.

## Domain vocabulary

| Term | Meaning |
|------|---------|
| Portfolio (`portfolios_portfolio`) | Portfel inwestycyjny użytkownika (w Django: `Pocket`) |
| Position (`portfolios_position`) | Pozycja — stan posiadania danego waloru w portfelu |
| Operation (`portfolios_operation`) | Zdarzenie: kupno, sprzedaż, wpłata, wypłata |
| Asset / AssetClass | Walor (akcja, fundusz, obligacja) i jego klasa |
| Currency | Waluta rozliczeniowa operacji/waloru |

## AI Tools Integration

Reguły (`python-coding-standards`, `typescript-coding-standards`, `error-handling-patterns`,
`security-checklist`) w `.claude/rules/ai-tools/` są **kopiami** z
[ai-tools](https://github.com/lukaszpiasecki13/ai-tools) (single source of truth). Zmiany w
`ai-tools/rules/` nie propagują się automatycznie — po aktualizacji uruchom ręcznie:

```
python <ai-tools>/scripts/install.py --target . --only error-handling-patterns,python-coding-standards,security-checklist,typescript-coding-standards
```

Agenty, skille i hooki (m.in. `code-reviewer`, `explorer`, `commit`, `fastapi-endpoint`,
`react-patterns`) pochodzą z pluginu ai-tools — zainstaluj go raz, globalnie:

```
/plugin marketplace add lukaszpiasecki13/ai-tools
/plugin install ai-tools@ai-tools
```
