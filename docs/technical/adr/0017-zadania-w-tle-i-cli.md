---
id: adr-0017-background-jobs-cli
status: Proposed
type: decision
scope: backend/cli-jobs
last_reviewed: 2026-10-03
---

# Zadania w tle to polecenia `python -m app.cli <zadanie>` wołające wyłącznie `entrypoints.py`, uzupełniane nadrabianiem zaległości po wybudzeniu

`app/cli.py` jest driverem ([ADR-0002](0002-sesja-poza-zadaniem-entrypointy-i-wiring.md), R8): parsuje argumenty, woła funkcję z `entrypoints.py`, drukuje wynik, ustala kod wyjścia. Backend usypia się (Render), więc zaległości nadrabia pierwsze żądanie dnia. Brak Celery/Redis.

**Rozstrzyga:** D8 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E0.6, E0.8, E1.4, E2.0, E4.5.

## Kontekst

- Brak `entrypoints.py` i `cli.py`; kursy i ceny odświeża żądanie `GET /portfolios/positions` (`backend/app/modules/portfolios/services/positions.py:37-39`) — E1.4 to usuwa.
- Test R8 (`backend/app/core/tests/test_architecture.py:295`) zakazuje w driverze tylko importów `services|repositories|wiring`; nie obejmuje `models`/`schemas`/`api` ani `BackgroundTasks` w `api/`.
- Pooler transakcyjny Supabase wyklucza blokady sesyjne; `SELECT … FOR UPDATE` w transakcji działa.

## Decyzja

**1. Driver.** `backend/app/cli.py`, `argparse` **[propozycja]**, uruchomienie w `.venv`. Rejestr `COMMANDS: dict[str, Callable]` mapuje nazwę na funkcję z `entrypoints.py`.

**2. Polecenia** (jedna funkcja entrypointu każde; entrypoint przyjmuje `scope: SessionScope = session_scope`):

| Polecenie | Entrypoint | Krok |
|---|---|---|
| `refresh-prices` | `assets.refresh_prices` | E1.4 |
| `refresh-fx` | `assets.refresh_fx_rates` | E1.4 |
| `backfill` | `portfolios.backfill_history` | E1.4 |
| `rebuild-dirty` | `portfolios.rebuild_dirty` ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)) | E2.5 |
| `rebuild-all` | `portfolios.rebuild_all` | E2.0 |
| `create-user`, `set-owner` | `core_data.create_user`, `core_data.set_owner`; hasło z `getpass`/env, nigdy z argumentu | E0.6 |
| `report-suspect-data` | `portfolios.report_suspect_data` (tylko odczyt) | E0.8 |

**3. Polityka błędów** (R7). *Domenowa* w entrypoincie: błąd jednej waluty/waloru nie przerywa reszty (wzorzec: `assets/services/market_data.py:131`, `:142`), wynik zwraca liczniki `ok`/`failed`. *Procesowa* w driverze, kod wyjścia: `0` ok, `1` błąd niedomenowy, `2` błędne argumenty, `3` częściowe niepowodzenia **[propozycja]**.

**4. Nadrabianie po wybudzeniu i blokada.**
- Pierwsze żądanie dnia (stan z tabeli `job_run`, nie z pamięci procesu) rejestruje w `BackgroundTasks` wyłącznie `refresh_fx_rates`, `refresh_prices` i `rebuild_dirty`. Zadania są idempotentne.
- Równoległy przebieg blokuje tabela `job_run` (`job` PK, `last_started_at`, `last_finished_at`, `status`): przebieg w transakcji robi `SELECT … FOR UPDATE SKIP LOCKED` wiersza swojego zadania; zajęty → pomija. To samo dla CLI i `BackgroundTasks`. Nie `flock`, nie blokady sesyjne. **[propozycja]**

**5. Egzekwowanie** (`test_architecture.py`, z testem detektora): driver i funkcje w `BackgroundTasks` importują z `app.modules.*` wyłącznie `…entrypoints`; `test_cli` — każda wartość `COMMANDS` pochodzi z `…entrypoints` i zwraca kod z pkt 3. R5 (`:273`) obowiązuje dalej.

**6. Wyjątek: ręczne odświeżenie ceny.** `POST /assets/refresh-prices` zwraca `202` i rejestruje w `BackgroundTasks` wyłącznie `assets.entrypoints.refresh_prices`; żądanie nie woła dostawcy synchronicznie.

**7. Harmonogram zewnętrzny opcjonalny:** jedna linia crona wołająca `python -m app.cli refresh-fx && … refresh-prices && … rebuild-dirty` (kursy NBP przed cenami, potem przebudowa). APScheduler w `lifespan` odrzucony — proces się usypia.

## Rozpatrywane alternatywy

- Celery/Redis — broker i procesy dla jednego użytkownika.
- `click`/`typer` — `click` niedeklarowany (tylko przechodnio), `typer` to nowa zależność.
- Zadania przez endpoint HTTP — druga sesja w żądaniu, auth dla crona.
- `flock` — nie działa między instancjami; blokady sesyjne nie działają przez pooler.

## Konsekwencje

- (+) Jedno wejście dla zadań; te same funkcje służą CLI, `BackgroundTasks` i testom; działa bez harmonogramu.
- (−) Pierwsze żądanie po przerwie wybudza też zadania; tabela `job_run` i kody `1`/`3` są robocze.
