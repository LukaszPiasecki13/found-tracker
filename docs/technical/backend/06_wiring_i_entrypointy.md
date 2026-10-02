---
id: be-wiring-entrypoints
status: current
last_reviewed: 2026-10-01
type: mixed
scope: backend/wiring-entrypoints
applies_to:
  - backend/app/infrastructure/sql/factory.py
  - backend/app/core/dependencies.py
  - backend/app/modules/*/dependencies.py
  - backend/app/modules/*/wiring.py
  - backend/app/modules/*/entrypoints.py
  - backend/app/main.py
---

# Składanie obiektów i wejścia modułu spoza HTTP — `wiring.py`, `entrypoints.py`

Jak moduł backendu składa serwisy (`wiring.py`), jak FastAPI z tego korzysta (`dependencies.py`) i jak moduł przyjmuje wywołania, które nie są żądaniem HTTP: start aplikacji, polecenie CLI, zadanie w tle (`entrypoints.py`). Decyzja i odrzucone alternatywy: [ADR-0002](../adr/0002-sesja-poza-zadaniem-entrypointy-i-wiring.md). Miejsce w warstwach: [`01_backend-architecture.md` §1–§2](./01_backend-architecture.md#2-zasady-architektury).

> **Stan kodu:** `session_scope` i `provide` istnieją; `wiring.py` + `dependencies.py` (adapter `provide`) mają wszystkie moduły (`core_data`, `security`, `assets`, `portfolios` — ten ostatni buduje też komponenty `domain/`: `build_portfolio_ledger`, `build_portfolio_valuator`). Żaden moduł nie ma jeszcze `entrypoints.py` — sekcje §4–§5 opisują **cel** dla pierwszej operacji spoza HTTP (np. odświeżanie kursów walut, dziś wołane synchronicznie w `POST /portfolios/positions/refresh`).

## 1. Dwa przepływy: składanie i praca

```
Składanie (raz, na początku obsługi):   sesja ──▶ build_<x>(sesja) ──▶ serwis z repozytoriami w środku
Praca (w trakcie obsługi):               api/ | entrypoints.py ──▶ serwis ──▶ repozytorium ──▶ baza
```

Warstwami wywołań są tylko `api/` → serwis → repozytorium. `wiring.py` działa wyłącznie w przepływie składania. `entrypoints.py` jest drugim wejściem obok `api/`, a nie warstwą między nim a serwisem.

| Element | Odpowiada za | Nie wie o |
|---|---|---|
| serwis (`services/`) | logika, granica transakcji (`repo.transaction()`) | sesji, FastAPI, tym, kto go wywołał |
| repozytorium (`repositories/`) | zapytania na sesji, którą dostało | logice biznesowej |
| `wiring.py` | składa serwis z repozytoriami na jednej sesji | skąd przyszła sesja i kto woła |
| `dependencies.py` | wystawia buildery jako zależności FastAPI + zależności tylko-HTTP (bieżący użytkownik) | kodzie spoza HTTP |
| `entrypoints.py` | otwiera sesję poza żądaniem, woła serwis, stosuje domenową politykę błędów | repozytoriach, commicie, FastAPI |
| driver (`main.py`, `cli.py`, `BackgroundTasks` w `api/`) | uruchomienie procesu, komunikaty, kod wyjścia | sesji, serwisach, repozytoriach |

```
HTTP:  api/operations.py ─▶ get_operation_service ─▶ get_db ──────▶ build_operation_service(s) ─▶ serwis ─▶ repozytoria
tło:   main.py (lifespan) ─▶ entrypoints.refresh_currency_rates ─▶ session_scope ─▶ build_...(s) ─▶ serwis ─▶ repozytoria
```

## 2. `wiring.py` — jedyne miejsce składania

Czyste funkcje `build_<x>(session) -> X`: bez FastAPI, bez I/O, bez commitu. Cały graf powstaje na **jednej** sesji — dlatego wszystkie repozytoria jednej operacji dzielą sesję, a `transaction()` z dowolnego z nich domyka całość ([ADR-0001](../adr/0001-jedna-sesja-na-request.md)).

```python
# portfolios/wiring.py
from app.modules.assets import wiring as assets_wiring


def build_operation_service(session: Session) -> OperationService:
    return OperationService(
        PortfolioRepository(session),
        PositionRepository(session),
        OperationRepository(session),
        assets_wiring.build_asset_service(session),
        PortfolioLedger(),                     # komponent z portfolios/domain/ (DOM-10)
    )
```

**Zasady:**
- Builder przyjmuje `Session` i tylko to, co naprawdę zmienne między wywołaniami; konfigurację czyta z `core.config.get_settings()`.
- Builder cudzego modułu wołaj przez import modułu (`from app.modules.x import wiring as x_wiring`), nie przez `from ... import build_y` — to toleruje cykl między `wiring.py`.
- Nigdy nie importuj `fastapi` ani żadnego `dependencies.py`.
- Builder powstaje dla **każdego** serwisu, także takiego, którego dziś używa tylko HTTP.
- Serwis bez sesji (np. `TokenService`, `PasswordService` — zależne tylko od konfiguracji) też ma builder; `wiring.py` czyta konfigurację.

## 3. `dependencies.py` — adapter FastAPI

Wystawia buildery jako zależności FastAPI; sam niczego nie składa. Poza tym zawiera tylko zależności istniejące wyłącznie w HTTP: `get_current_user`, schemat OAuth2.

```python
# portfolios/dependencies.py
from app.core.dependencies import provide
from app.modules.portfolios.wiring import build_operation_service, build_portfolio_service

get_portfolio_service = provide(build_portfolio_service)
get_operation_service = provide(build_operation_service)
```

`provide` (w `core/dependencies.py`) opakowuje builder w zależność `session=Depends(get_db)`. Wynik przypisuj do nazwy `get_<x>` na poziomie modułu — to klucz `dependency_overrides` w testach.

## 4. Wejście spoza HTTP — `entrypoints.py`

Odpowiednik `api/` dla wywołań bez żądania HTTP: start aplikacji, CLI, zadanie w tle. Jedyne miejsce w module, które otwiera sesję poza żądaniem. Powstaje tylko gdy moduł ma taką operację. Przykładowi kandydaci we FundTrackerze: odświeżanie kursów walut i cen walorów (`assets`), przebudowa pozycji portfela z historii operacji (`portfolios`), utworzenie konta administracyjnego (`core_data`).

```python
# assets/entrypoints.py
def refresh_currency_rates(*, scope: SessionScope = session_scope) -> int:
    with scope() as session:
        service = build_market_data_service(session)
        return service.update_currency_rates()
```

Buduj serwis na osobnej linii (`service = build_<x>(session)`), a wywołanie metody na kolejnej.

**Zasady:**
- **Nie commituje** i nie dotyka repozytoriów; granica transakcji należy do serwisu.
- **Zwraca dane** (dataclass, enum, liczba, `None`), nie encje ORM — po wyjściu z `with` sesja jest zamknięta.
- **Przyjmuje `scope: SessionScope = session_scope`** jako argument tylko-nazwany — testy podają sesję testu.
- **Polityka błędów — kto decyduje:**

  | Rodzaj polityki | Gdzie | Przykład |
  |---|---|---|
  | domenowa: wynika z wiedzy modułu | entrypoint | „błąd pobrania kursu jednej waluty nie przerywa odświeżania pozostałych” |
  | procesowa: wynika z rodzaju procesu | driver | kod wyjścia CLI, „aplikacja nie startuje” |
  | brak szczególnej | — | entrypoint przepuszcza wyjątek; `session_scope` zrobił rollback |

- Entrypointu **nie wołaj** z serwisu ani z wnętrza żądania HTTP (otworzyłby drugą sesję). Wyjątek: rejestracja `BackgroundTasks`.
- **Skrypty pod `backend/seed/`** nie są wejściem modułu — wołają `session_scope()` wprost i składają serwisy przez `wiring.py`. Test architektury skanuje wyłącznie `backend/app/`.

## 5. Drivery

Driver uruchamia proces albo przyjmuje wywołanie z zewnątrz. Zna tylko entrypointy; nie importuje serwisów, repozytoriów, `wiring` ani `session_scope`.

| Driver | Woła | Odpowiada za |
|---|---|---|
| `main.py` `lifespan` | entrypointy startowe (gdy powstaną) | co zatrzymuje start |
| `cli.py` (gdy powstanie) | entrypointy modułów | argumenty, komunikat, kod wyjścia |
| handler w `api/` z `BackgroundTasks` | entrypoint zadania w tle | tylko rejestracja zadania |

## 6. Gdzie co dopisać

| Chcę dodać… | Gdzie |
|---|---|
| regułę biznesową | serwis (`services/`), a gdy czysta — `domain/` |
| zapytanie do bazy | repozytorium |
| zależność serwisu | builder w `wiring.py` — jedna edycja |
| endpoint HTTP | `api/` + `get_<x> = provide(build_<x>)` w `dependencies.py` |
| operację przy starcie / z CLI / w tle | metoda serwisu + funkcja w `entrypoints.py` + cienki driver |
| decyzję „ten błąd nie jest fatalny, bo…” | `entrypoints.py` modułu |
| decyzję „proces kończy się kodem 1” | driver |

## 7. Testy entrypointów i wiringu

Testy integracyjne działają na **jednej** sesji testu:

- **Serwis składamy tym samym builderem co produkcja**, na sesji testu: `build_operation_service(session)`.
- **Entrypoint dostaje sesję testu przez parametr `scope`**, zamiast patchowania ścieżek modułów:

```python
@pytest.fixture
def shared_scope(session: Session) -> SessionScope:
    @contextmanager
    def scope() -> Iterator[Session]:
        yield session
    return scope
```

- Sam `session_scope` testujemy jednostkowo w `infrastructure/tests/unit/`: rollback przy wyjątku (także `SystemExit`), błąd rollbacku nie przykrywa oryginału, `close()` zawsze.
- Drivery testujemy cienko (mock entrypointu); logikę testujemy w serwisie.

**Egzekwowanie:** test architektury `core/tests/test_architecture.py` (AST) — serwisy i repozytoria nie otwierają sesji i nie importują `fastapi`; `wiring.py`, `entrypoints.py` i serwisy nie importują `dependencies.py`; entrypoint nie importuje repozytoriów; drivery wołają tylko entrypointy.
