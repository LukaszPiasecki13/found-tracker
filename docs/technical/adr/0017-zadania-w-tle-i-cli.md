---
id: adr-0017-background-jobs-cli
status: Proposed
type: decision
scope: backend/cli-jobs
last_reviewed: 2026-10-02
---

# Zadania w tle to polecenia `python -m app.cli <zadanie>` wołające wyłącznie `entrypoints.py`, uruchamiane harmonogramem systemowym

`app/cli.py` jest driverem ([ADR-0002](0002-sesja-poza-zadaniem-entrypointy-i-wiring.md), R8): parsuje argumenty, woła funkcję z `entrypoints.py`, drukuje wynik, ustala kod wyjścia. Harmonogram jest poza kodem aplikacji. Brak Celery/Redis.

**Rozstrzyga:** D8 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E0.6, E0.8, E1.4, E2.0, E4.5, E5.1, E5.6, E9.6.

## Kontekst

- Brak `entrypoints.py` i `cli.py`; kursy i ceny odświeża żądanie `GET /portfolios/positions` (`backend/app/modules/portfolios/services/positions.py:37-39`) — E1.4 to usuwa.
- Test R8 (`backend/app/core/tests/test_architecture.py:295`) zakazuje w driverze tylko importów `services|repositories|wiring`; nie obejmuje `models`/`schemas`/`api` ani `BackgroundTasks` w `api/`.
- `click` jest w `requirements.txt:11` tylko przechodnio.

## Decyzja

**1. Driver.** `backend/app/cli.py`, `argparse` **[propozycja]**, uruchomienie w `.venv`. Rejestr `COMMANDS: dict[str, Callable]` mapuje nazwę na funkcję z `entrypoints.py`.

**2. Polecenia** (jedna funkcja entrypointu każde; entrypoint przyjmuje `scope: SessionScope = session_scope`):

| Polecenie | Entrypoint | Krok |
|---|---|---|
| `refresh-prices` | `assets.refresh_prices` | E1.4 |
| `refresh-fx` | `assets.refresh_fx_rates` (wypełnia `fx_rate_tax IS NULL`, [ADR-0015](0015-historia-cen-i-kursow.md)) | E1.4 |
| `backfill` | `portfolios.backfill_history` | E1.4 |
| `rebuild-dirty` | `portfolios.rebuild_dirty` ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)) | E2.5 |
| `rebuild-all` | `portfolios.rebuild_all`; `--check` drukuje różnice, kod 1, bez zapisu **[propozycja]** | E2.0 |
| `create-user`, `set-owner` | `core_data.create_user`, `core_data.set_owner`; hasło z `getpass`/env, nigdy z argumentu | E0.6 |
| `report-suspect-data` | `portfolios.report_suspect_data` (tylko odczyt) | E0.8 |
| `evaluate-alerts` | `notifications.evaluate_alerts` | E10.1 |
| `load-limits`, `load-bond-rates` | `portfolios.load_limits`, `assets.load_bond_rates` | E5.6, E5.1 |
| `generate-recurring` | `planning.generate_recurring` (idempotentne przez `external_ref`) | E9.6 |
| `export-all` / `import-all` | `<moduł>.export_data` / `import_data` po kolei, bez zależności między modułami | E4.5, E11.3 |

**3. Polityka błędów** (R7). *Domenowa* w entrypoincie: błąd jednej waluty/waloru nie przerywa reszty (wzorzec: `assets/services/market_data.py:131`, `:142`), wynik zwraca liczniki `ok`/`failed`. *Procesowa* w driverze, kod wyjścia: `0` ok, `1` błąd niedomenowy lub `--check` z różnicami, `2` błędne argumenty, `3` częściowe niepowodzenia **[propozycja]**.

**4. Harmonogram.** Repo dostarcza przykłady (cron, timer systemd, kontener), nie kod. Kolejność dnia: `refresh-fx` po tabeli A NBP → `refresh-prices` po sesji → `rebuild-dirty` → `evaluate-alerts`. Nakładanie przebiegów blokuje `flock -n` (`rebuild-*` biorą blokady wierszy).

**5. Egzekwowanie** (`test_architecture.py`, z testem detektora): driver i funkcje w `BackgroundTasks` importują z `app.modules.*` wyłącznie `…entrypoints`; `test_cli` — każda wartość `COMMANDS` pochodzi z `…entrypoints` i zwraca kod z pkt 3. R5 (`:273`) obowiązuje dalej.

**6. Wyjątek: ręczne odświeżenie ceny.** `POST /assets/refresh-prices` zwraca `202` i rejestruje w `BackgroundTasks` wyłącznie `assets.entrypoints.refresh_prices`; żądanie nie woła dostawcy synchronicznie.

**7. APScheduler** w `lifespan`: dopuszczalny, nie domyślny — duplikaty przy wielu workerach `uvicorn`, nowa zależność. Tylko przy jednym procesie.

## Rozpatrywane alternatywy

- Celery/Redis — broker i procesy dla jednego użytkownika.
- `click`/`typer` — `click` niedeklarowany, `typer` to nowa zależność.
- Zadania przez endpoint HTTP — druga sesja w żądaniu, auth dla crona.

## Konsekwencje

- (+) Jedno wejście dla zadań; te same funkcje służą CLI, `BackgroundTasks` i testom.
- (−) Harmonogram wymaga konfiguracji poza repo (łagodzi flaga `stale`, E1.7); kody `1`/`3` i `--check` są robocze.

## Otwarte

- Środowisko docelowe (cron / systemd / kontener) wybiera właściciel.
