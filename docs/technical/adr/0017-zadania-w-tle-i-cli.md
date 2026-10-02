---
id: adr-0017-background-jobs-cli
status: Proposed
type: decision
scope: backend/cli-jobs
last_reviewed: 2026-10-02
---

# Zadania w tle to polecenia `python -m app.cli <zadanie>` wołające wyłącznie `entrypoints.py`, uruchamiane harmonogramem systemowym

`app/cli.py` jest driverem ([ADR-0002](0002-sesja-poza-zadaniem-entrypointy-i-wiring.md), R8): parsuje argumenty, woła funkcję z `entrypoints.py` modułu, drukuje wynik i ustala kod wyjścia. Nie importuje serwisów, repozytoriów ani `wiring`. Harmonogram (cron, timer systemd, kontener) jest poza kodem aplikacji; repo dokumentuje, jak go ustawić. Brak Celery/Redis.

**Rozstrzyga:** D8 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E0.6 (`create-user`, `set-owner`), E0.8, E1.4, E2.0 (`rebuild-all`), E4.5, E5.1, E5.6, E9.6.

## Kontekst

- Dziś żaden moduł nie ma `entrypoints.py`, a `cli.py` nie istnieje; `main.py` ma tylko `lifespan` bez zadań (`backend/app/main.py:24`). Odświeżanie kursów i cen odbywa się w żądaniu `GET /portfolios/positions` (`backend/app/modules/portfolios/services/positions.py:37-39`) — E1.4 to usuwa.
- Test architektury R8 sprawdza `main.py` i `cli.py`, gdy istnieje (`backend/app/core/tests/test_architecture.py:295`), ale zakazuje tylko importów `services|repositories|wiring` (`_MODULE_SERVICES_RE`) i wywołań otwierających sesję. **Luki:** driver mógłby importować `models`/`schemas`/`api` modułu; test nie obejmuje `BackgroundTasks` w `api/` (ADR-0002 R8 wymienia je jako drivery).
- `click` jest w `requirements.txt:11`, ale `app/` ani `seed/` go nie importują (zależność przechodnia); instalacja nowych zależności wymaga zgody.
- Konfiguracja harmonogramu to eksploatacja, nie kod; dokumentuje ją [`06_wiring_i_entrypointy.md` §5](../backend/06_wiring_i_entrypointy.md) (drivery).

## Decyzja

**1. Driver.** `backend/app/cli.py`, `argparse` (biblioteka standardowa, bez nowej zależności) **[propozycja]**; uruchomienie `python -m app.cli <polecenie> [opcje]` w `.venv`. Rejestr `COMMANDS: dict[str, Callable]` mapuje nazwę na funkcję z `entrypoints.py`.

**2. Polecenia** (każde = jedna funkcja entrypointu; entrypoint przyjmuje `scope: SessionScope = session_scope`):

| Polecenie | Entrypoint | Krok | Zachowanie |
|---|---|---|---|
| `refresh-prices` | `assets.entrypoints.refresh_prices` | E1.4 | zamknięcia dzienne; idempotentne (drugi przebieg = 0 zapisów dla zamknięć) |
| `refresh-fx` | `assets.entrypoints.refresh_fx_rates` | E1.4 | kursy NBP/Yahoo; wypełnia `fx_rate_tax IS NULL` ([ADR-0015](0015-historia-cen-i-kursow.md)) |
| `backfill` | `portfolios.entrypoints.backfill_history` | E1.4 | zna okresy posiadania, prosi `assets` o zakres dat |
| `rebuild-dirty` | `portfolios.entrypoints.rebuild_dirty` | E2.5 | synchronizuje zmiany rynku i przebudowuje Portfele z `dirty_from` ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)) |
| `rebuild-all` | `portfolios.entrypoints.rebuild_all` | E2.0 | pozycje, salda, partie, snapshoty z Operacji; `--check` drukuje różnice i zwraca 1 bez zapisu **[propozycja]** |
| `create-user` | `core_data.entrypoints.create_user` | E0.6 | hasło z `getpass`/zmiennej środowiskowej, nigdy z argumentu |
| `report-suspect-data` | `portfolios.entrypoints.report_suspect_data` | E0.8 | raport tylko do odczytu (waluta waloru = waluta Portfela przy giełdzie zagranicznej; `fx_rate` = 1 przy różnych walutach) |
| `evaluate-alerts` | `notifications.entrypoints.evaluate_alerts` | E10.1 | po `refresh-prices`; moduł [ADR-0013](0013-kierunki-zaleznosci-nowych-modulow.md) |
| `set-owner` (albo `create-user --owner`) | `core_data.entrypoints.set_owner` | E0.6 | ustawia `is_owner` wskazanemu kontu ([ADR-0007 biz.](../../business/adr/0007-dane-referencyjne-i-usuwanie.md)) |
| `load-limits` | `portfolios.entrypoints.load_limits` | E5.6 | limity IKE/IKZE z pliku konfiguracji (`source_ref`, etykieta [niezweryfikowane]) |
| `load-bond-rates` | `assets.entrypoints.load_bond_rates` | E5.1 | serie i okresy odsetkowe obligacji z pliku |
| `generate-recurring` | `planning.entrypoints.generate_recurring` | E9.6 | szkice Operacji z szablonów cyklicznych (idempotentne przez `external_ref`) |
| `export-all` / `import-all` | kolejno `<moduł>.entrypoints.export_data` / `import_data` | E4.5, E11.3 | pełna kopia i restore instancji; driver woła `entrypoints` modułów po kolei, więc moduły nie zależą od siebie |

**3. Podział polityk błędów** (R7): *domenowa* w entrypoincie — błąd jednej waluty/waloru nie przerywa reszty (wzorzec już w `MarketDataService`, `backend/app/modules/assets/services/market_data.py:131`, `:142`), wynik zwraca liczniki `ok`/`failed`; *procesowa* w driverze — kod wyjścia: `0` wszystko zrobione, `1` błąd niedomenowy lub `--check` z różnicami, `2` błędne argumenty (argparse), `3` zadanie ukończone z częściowymi niepowodzeniami **[propozycja]**. Logi przez `configure_logging` (jak `backend/app/main.py:19`).

**4. Harmonogram — dokumentacja uruchomienia.** Repo dostarcza przykłady (cron, timer systemd, osobny kontener z tym samym obrazem), nie kod harmonogramu. Kolejność dnia: `refresh-fx` po publikacji tabeli A NBP (okno: [dane PL §1.2](../../research/03_rynek_pl_dane_i_obligacje.md)) → `refresh-prices` po sesji → `rebuild-dirty` → `evaluate-alerts`. Nakładanie się przebiegów blokuje `flock -n` w linii harmonogramu (zadania są idempotentne, ale `rebuild-*` biorą blokady wierszy, [ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)).

**5. Egzekwowanie** (rozszerzenie `test_architecture.py`, każdy z testem detektora):
- Driver (`main.py`, `cli.py`) i funkcje rejestrowane w `BackgroundTasks` w `api/` importują z `app.modules.*` **wyłącznie** `…entrypoints`; każdy inny import modułu → błąd (domyka lukę `models`/`schemas`/`api`).
- `test_cli`: każda wartość `COMMANDS` pochodzi z modułu `…entrypoints` (`__module__`), a polecenie zwraca kod z pkt 3.
- Obowiązuje dalej R5 (`test_architecture.py:273`): entrypoint bez repozytoriów, `fastapi` i `dependencies.py`.

**6. Wyjątek: ręczne odświeżenie ceny.** `POST /assets/refresh-prices` (przycisk w UI) zwraca `202` i rejestruje w `BackgroundTasks` **wyłącznie** `assets.entrypoints.refresh_prices`; żądanie HTTP nie woła dostawcy synchronicznie. Kryterium E1.4 dostaje ten wyjątek.

**7. Opcjonalnie APScheduler** w `lifespan` drivera `main.py`: dopuszczalny (woła entrypointy), ale uruchamiałby zadania w każdym workerze `uvicorn` i wymaga zgody na nową zależność. Nie jest domyślny; rozważyć tylko przy jednym procesie.

## Rozpatrywane alternatywy

- **Celery/Redis.** Dodatkowe procesy i broker dla jednego użytkownika (D8). Odrzucone.
- **`click`/`typer`.** `click` jest przechodnią zależnością niedeklarowaną; `typer` to nowa zależność. Odrzucone na rzecz `argparse`.
- **Zadania wywoływane endpointem HTTP.** Otwierałyby drugą sesję w żądaniu (zakaz w `06_wiring_i_entrypointy.md` §4) i wymagały auth dla crona. Odrzucone.
- **Harmonogram w aplikacji domyślnie.** Duplikaty przy wielu workerach. Odrzucone (pkt 7).

## Konsekwencje

**Pozytywne**
- Jedno miejsce wejścia dla zadań; żądania HTTP nie wołają dostawcy synchronicznie (kryterium E1.4; jedyny wyjątek: pkt 6, 202 w tle); polecenia są testowalne przez parametr `scope`.
- Te same funkcje służą CLI, `BackgroundTasks` i testom.

**Negatywne**
- Harmonogram wymaga konfiguracji poza repo; błąd w niej oznacza nieodświeżone ceny (łagodzi flaga `stale`, E1.7).
- Kody wyjścia `1`/`3` i `--check` są robocze.

## Otwarte

- Środowisko docelowe (cron / systemd / kontener) — wybiera właściciel; ADR tego nie zakłada.
