---
id: be-architecture
status: current
last_reviewed: 2026-09-30
type: mixed
scope: backend/architecture
applies_to:
  - backend/app/**
---

# Architektura Backendu — Dokumentacja Techniczna

Wzorzec architektoniczny jest przejęty z projektu **waterworks-monitoring-platform** (źródło prawdy dla wzorca) i dostosowany do FundTrackera: bez audytu, płaszczyzn dostępu per organizacja, urządzeń IoT i telemetrii. Decyzje stojące za wzorcem: [ADR-y techniczne](../adr/). Opis stanu kodu vs celu: [§10](#10-stan-kodu-vs-cel).

## Spis treści

1. [Przegląd architektury](#1-przegląd-architektury)
2. [Zasady architektury](#2-zasady-architektury)
3. [Struktura projektu](#3-struktura-projektu)
4. [Warstwy współdzielone](#4-warstwy-współdzielone)
5. [Template modułu domenowego](#5-template-modułu-domenowego)
6. [Moduły biznesowe](#6-moduły-biznesowe)
7. [Obsługa błędów](#7-obsługa-błędów)
8. [Strategia testowania](#8-strategia-testowania)
9. [Migracje](#9-migracje)
10. [Stan kodu vs cel](#10-stan-kodu-vs-cel)

---

## 1. Przegląd architektury

**Architektura warstwowa (Layered Architecture) zorganizowana jako modularny monolit (Modular Monolith).** Kod dzieli się na poziome warstwy **API → Services → Repositories → Infrastructure**. Każda warstwa zależy wyłącznie od warstwy bezpośrednio poniżej. `core/` i błędy są przekrojowe.

Moduł, którego logika da się wyrazić bez ORM, sesji i zegara, dostaje opcjonalną piątą warstwę **`domain/`** pod Services ([ADR-0005](../adr/0005-warstwa-domeny.md)). W FundTrackerze kandydatem jest `portfolios` (reguły salda i pozycji).

Moduł ma dwa wejścia do serwisów: **API** (żądanie HTTP) i **Entrypoints** (start aplikacji, CLI, zadanie w tle). Oba dostają serwisy złożone przez **Wiring** — jedno miejsce składania obiektów. Wiring nie jest warstwą wywołań: działa raz, przed pracą ([ADR-0002](../adr/0002-sesja-poza-zadaniem-entrypointy-i-wiring.md), [`06_wiring_i_entrypointy.md`](./06_wiring_i_entrypointy.md)).

:::mermaid
flowchart TB
    API["API (HTTP)"]
    ENTRY["Entrypoints (poza HTTP)"]
    WIRING["Wiring"]
    SERVICES["Services"]
    DOMAIN["Domain (opcjonalna)"]
    REPOSITORIES["Repositories"]
    INFRASTRUCTURE["Infrastructure"]
    CORE["Core"]
    ERRORS["Errors"]

    API --> SERVICES
    ENTRY --> SERVICES
    API -. "przez dependencies.py" .-> WIRING
    ENTRY -.-> WIRING
    WIRING -. "składa" .-> SERVICES
    SERVICES --> REPOSITORIES
    SERVICES -. "gdy moduł ma domain/" .-> DOMAIN
    REPOSITORIES --> INFRASTRUCTURE
    API -.-> CORE
    SERVICES -.-> CORE
    REPOSITORIES -.-> CORE
    INFRASTRUCTURE -.-> CORE
    API -.-> ERRORS
    SERVICES -.-> ERRORS
    REPOSITORIES -.-> ERRORS
    INFRASTRUCTURE -.-> ERRORS
:::

**Dlaczego architektura warstwowa, a nie Clean/Hexagonal?** Praktyczny, poziomy podział odpowiedzialności, czytelny dla jednej osoby utrzymującej całość. `domain/` domyka układ (Application → Domain), nie odwraca kierunku zależności.

---

## 2. Zasady architektury

### 2.1. Dozwolone zależności między warstwami

| Warstwa | Może importować z |
|---|---|
| **API** | Services (własny moduł), Core, Errors |
| **Services** | Repositories (własny moduł), Domain (własny moduł, jeśli istnieje), inne Services, Core, Errors |
| **Domain** (opcjonalna) | Nic poza biblioteką standardową i sobą samą ([ADR-0005](../adr/0005-warstwa-domeny.md)) |
| **Repositories** | Infrastructure, Core, Errors |
| **Infrastructure** | Core, Errors |
| **`dependencies.py`** (adapter HTTP) | Wiring (własny moduł), zależności HTTP innych modułów (`get_current_user`), Core |
| **Wiring** (`wiring.py`) | Services i Repositories własnego modułu, Wiring innych modułów, Core — nigdy `fastapi` ani `dependencies.py` |
| **Entrypoints** (`entrypoints.py`) | Wiring (własny moduł), `core.dependencies.session_scope`, Core, Errors — nigdy Repositories, `fastapi` ani `dependencies.py` |
| **Drivery** (`main.py`, `cli.py`, `BackgroundTasks` w `api/`) | Entrypoints dowolnego modułu, Core |

### 2.2. Zakaz przeskakiwania warstw

```
✅  API → Services → Repositories → Infrastructure
✅  Driver → Entrypoint → Services → Repositories → Infrastructure
❌  API → Repositories              (pominięcie Services)
❌  API → Infrastructure
❌  Services → Infrastructure       (pominięcie Repositories)
❌  Driver → Services               (pominięcie Entrypoint)
❌  Entrypoint → Repositories       (granica transakcji należy do serwisu)
```

### 2.3. Komunikacja między modułami

Cross-module odbywa się **wyłącznie przez warstwę serwisów** ([ADR-0006](../adr/0006-cross-module-wylacznie-przez-serwisy.md)):

```python
from app.modules.assets.services.assets import AssetService            # ✅
from app.modules.assets.repositories.assets import AssetRepository    # ❌
```

Doprecyzowanie: serwis nie trzyma repozytorium innego modułu jako zależności; import cudzego modelu ORM w JOIN-ie repozytorium jest dozwolony (tylko do odczytu); cudzą warstwę `domain/` importuje się wyłącznie przez jej `__init__.py`.

### 2.4. Zakaz zależności cyklicznych

Jeśli dwa serwisy wzajemnie się potrzebują: wydziel wspólną logikę do `core/`, odwróć zależność portem (`Protocol`) zdefiniowanym przez moduł nadrzędny, albo zrewiduj podział modułów. Builder cudzego modułu wołaj przez import modułu (`from app.modules.x import wiring as x_wiring`), co toleruje cykl między plikami `wiring.py`.

---

## 3. Struktura projektu

```text
backend/
├─ app/
│  ├─ main.py                    ← driver: aplikacja FastAPI + lifespan
│  ├─ cli.py                     ← driver: polecenia administracyjne (gdy powstaną)
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ dependencies.py         ← get_db, session_scope, provide
│  │  └─ errors.py               ← APIError + handlery (ADR-0007)
│  ├─ infrastructure/
│  │  ├─ sql/
│  │  │  ├─ base.py
│  │  │  ├─ factory.py
│  │  │  ├─ repository.py        ← SQLRepository.transaction()
│  │  │  └─ models_registry.py
│  │  └─ tests/
│  └─ modules/
│     ├─ core_data/              ← użytkownicy
│     ├─ security/               ← logowanie, tokeny, hasła
│     ├─ assets/                 ← waluty, klasy, walory, dane rynkowe
│     └─ portfolios/             ← portfele, pozycje, operacje, metryki
│        ├─ api/  services/  domain/  repositories/  schemas/  models/
│        ├─ dependencies.py  wiring.py  entrypoints.py(opc.)  exceptions.py(opc.)
│        └─ tests/{unit,integration}/
├─ alembic/
├─ seed/                         ← skrypty seedujące (poza zakresem testu architektury)
├─ alembic.ini
├─ pyproject.toml
└─ requirements.txt
```

---

## 4. Warstwy współdzielone

### 4.1. `core/`

Elementy współdzielone przez wszystkie moduły. **Bez logiki biznesowej.**

| Plik | Odpowiedzialność |
|---|---|
| `config.py` | Ustawienia z zmiennych środowiskowych (`pydantic-settings`): baza, JWT, schemat DB |
| `dependencies.py` | Silnik i `sessionmaker`; `get_db` (sesja żądania), `session_scope` + typ `SessionScope` (poza żądaniem), `provide` (builder z `wiring.py` jako zależność FastAPI). Nie importuje żadnego modułu |
| `errors.py` | Hierarchia wyjątków `APIError` z `code` i globalne handlery (§7) |

### 4.2. `infrastructure/sql/`

| Plik | Odpowiedzialność |
|---|---|
| `base.py` | `DeclarativeBase`; wszystkie modele ORM z niej dziedziczą |
| `factory.py` | `SQLConnectionFactory`: cache silników, `sessionmaker` (`expire_on_commit=False`), zależność sesji żądania, `create_session_scope` |
| `repository.py` | `SQLRepository`: baza repozytoriów, `transaction()`, `flush()`, `rollback()` |
| `models_registry.py` | Import wszystkich modeli dla Alembic `autogenerate` — **każdy nowy model musi być tu zarejestrowany** |

**`SQLRepository.transaction()`** zastępuje powtarzany blok `try: ... commit() except: rollback(); raise` i jest jedyną granicą commitu ([ADR-0001](../adr/0001-jedna-sesja-na-request.md)):

```python
@contextmanager
def transaction(self) -> Generator[None]:
    try:
        yield
    except Exception:
        self.rollback()
        raise
    self.commit()
```

Użycie w serwisie: `with self._repo.transaction(): ...`. Repozytorium **nie commituje samo** — metody `create/update/delete` tylko `add`/`flush`.

**Cykl życia sesji** ([ADR-0002](../adr/0002-sesja-poza-zadaniem-entrypointy-i-wiring.md)): jeden szkielet dla sesji żądania (`get_db`) i poza żądaniem (`session_scope`): otwiera, robi rollback przy **dowolnym** wyjątku (także `SystemExit`), zawsze zamyka, **nigdy nie commituje**.

| Mechanizm | Odpowiada za | Czego **nie** robi |
|---|---|---|
| `session_scope()` / `get_db` | otwarcie, rollback przy wyjątku, zamknięcie | nie commituje, nie połyka błędów |
| `repo.transaction()` | granica commitu jednostki pracy | nie otwiera ani nie zamyka sesji |

Konsekwencja: serwis, który zapomni `transaction()`, traci zapis — jedynym sygnałem jest ostrzeżenie w logu przy zamknięciu sesji.

---

## 5. Template modułu domenowego

### 5.1. Struktura katalogów

```text
modules/<domain>/
├─ api/<resource>.py           # Endpointy HTTP
├─ services/<resource>.py      # Logika biznesowa (orkiestracja, I/O)
├─ domain/<pojęcie>.py         # Opcjonalny: logika bez ORM/sesji/zegara
├─ repositories/<resource>.py  # Dostęp do danych
├─ schemas/<resource>.py       # Schematy Pydantic (request/response)
├─ models/<resource>.py        # Modele ORM SQLAlchemy
├─ dependencies.py             # Adapter FastAPI: get_<x> = provide(build_<x>)
├─ wiring.py                   # Jedyne miejsce składania: build_<x>(session)
├─ entrypoints.py              # Wejście spoza HTTP — tylko gdy moduł ma takie operacje
├─ exceptions.py               # Wyjątki domenowe modułu (opcjonalnie)
└─ tests/{unit,integration}/
```

Moduł w toku migracji trzyma **jeden** styl naraz: nie mieszaj płaskich plików (`api.py`, `models.py`) z podfolderami w tym samym module.

### 5.2. Odpowiedzialność każdej warstwy

#### `api/<resource>.py`

- Definiuje endpointy, waliduje wejście schematami Pydantic, ustawia statusy HTTP.
- **Nie zawiera** logiki biznesowej — deleguje do serwisu. **Nie importuje** repozytoriów ani modeli ORM.
- **Nie rzuca `HTTPException`** — błędy idą jako `APIError` z serwisu ([§7](#7-obsługa-błędów)).
- Query params zawsze przez schemat Pydantic z `Depends()`.

```python
@router.post("/", response_model=PortfolioResponse, status_code=201)
def create_portfolio(
    data: PortfolioCreateRequest,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    return service.create(data, owner_id=user.id)  # encja ORM; response_model robi DTO
```

#### `services/<resource>.py`

- Logika biznesowa i przypadki użycia; orkiestruje repozytoria (i `domain/`).
- **Nie importuje** `Request`/`Response`/`fastapi`. **Nie zna sesji** — dostaje repozytoria przez `__init__`.
- **Wyznacza granicę transakcji** (`with self._repo.transaction():`).
- Nie wie, kto go wywołał (HTTP, CLI, test).
- **Zwraca encję ORM, nie DTO** ([ADR-0003](../adr/0003-serwisy-zwracaja-encje-orm.md)); wyjątek: serwisy odczytowe agregujące dane bez encji (np. wektory metryk) zwracają DTO.
- Przyjmuje **typowane argumenty** (schemat Pydantic, `dataclass`, skalary), nie `dict`.
- Kontekst przewlekany przez wywołania to `@dataclass(frozen=True)`, nie słownik.

```python
class PortfolioService:
    def __init__(self, repository: PortfolioRepository) -> None:
        self._repo = repository

    def create(self, data: PortfolioCreateRequest, owner_id: int) -> Portfolio:
        if self._repo.find_by_owner_and_name(owner_id, data.name):
            raise ConflictError("Portfolio already exists", code="PORTFOLIO_ALREADY_EXISTS")
        with self._repo.transaction():
            return self._repo.create(Portfolio(owner_id=owner_id, name=data.name, ...))
```

#### `domain/<pojęcie>.py` (opcjonalny)

Logika bez ORM, `Session` i zegara — czysty kod nad wartościami (`Decimal`, `dataclass`, `StrEnum`). Importuje tylko bibliotekę standardową i inne pliki `domain/` tego modułu. Serwis rozmawia z domeną przez **komponenty** wstrzykiwane w `wiring.py`, nie przez luźne funkcje. Granica z ORM/Pydantic przez `typing.Protocol`. Pełny zestaw reguł DOM-1–DOM-11: [ADR-0005](../adr/0005-warstwa-domeny.md). Przykład w FundTrackerze: `portfolios/domain/` — [`05_portfolios_module.md`](./05_portfolios_module.md).

#### `repositories/<resource>.py`

- Dziedziczy z `SQLRepository`; odczyt i zapis danych, **żadnej logiki biznesowej**.
- Zwraca modele ORM, nigdy kursory.
- Nie commituje (`create/update/delete` = `add` + `flush`); commit robi `transaction()` z serwisu.
- **Konwencja `find_`/`get_`** ([ADR-0004](../adr/0004-repozytoria-get-vs-find.md)): `find_by_<klucz>` zwraca `T | None`; `get_by_<klucz>` zwraca `T` i rzuca `NotFoundError`. Kolekcje: `list_*`.

#### `schemas/<resource>.py`

- Pydantic do walidacji wejścia/wyjścia. Nazwy: `<Resource>CreateRequest`, `<Resource>UpdateRequest`, `<Resource>Response`.
- Schematy żądań na granicy modułu: `extra="forbid"`.
- Tylko walidacja kształtu. Reguły biznesowe (np. „ilość musi być dodatnia”) należą do serwisu/domeny, nie do routera.

#### `models/<resource>.py`

Modele ORM dziedziczące z `Base`. **Wymagana rejestracja** w `infrastructure/sql/models_registry.py`. Kwoty i ilości to `Numeric` mapowane na `Decimal` ([ADR-0010](../adr/0010-decimal-i-precyzja-pieniedzy.md)).

#### `exceptions.py`

Wyjątki domenowe modułu dziedziczące z `core/errors.py`. Własna klasa powstaje, gdy wołający musi ją rozróżnić programowo albo nazwa niesie przyczynę; w pozostałych przypadkach wystarczy klasa z `core/errors.py` z komunikatem i `code`.

### 5.3. Składanie obiektów — `wiring.py` i `dependencies.py`

Serwis składa jedna funkcja `build_<x>(session)` w `wiring.py`, wspólna dla HTTP, entrypointów i testów. `dependencies.py` jest adapterem: `get_<x> = provide(build_<x>)`. Szczegóły: [`06_wiring_i_entrypointy.md`](./06_wiring_i_entrypointy.md).

```python
# portfolios/wiring.py
def build_portfolio_service(session: Session) -> PortfolioService: ...

# portfolios/dependencies.py
get_portfolio_service = provide(build_portfolio_service)
```

**Zabronione wzorce:**

```python
# ❌ API wstrzykuje Repository lub sesję
def get_items(repo: ItemRepository = Depends(get_item_repository)): ...
def get_items(session: Session = Depends(get_db)): ...

# ❌ dependencies.py składa graf samodzielnie, obok buildera
def get_item_service(repo=Depends(get_item_repo)): return ItemService(repo)

# ❌ kod spoza HTTP woła adapter HTTP
from app.modules.security.dependencies import get_user_repo   # w main.py / cli.py

# ✅ API wstrzykuje wyłącznie Service
get_item_service = provide(build_item_service)                       # dependencies.py
def get_items(service: ItemService = Depends(get_item_service)): ... # api/
```

### 5.4. Wejście spoza HTTP — `entrypoints.py`

Odpowiednik `api/` dla wywołań spoza żądania HTTP (start aplikacji, CLI, zadanie w tle — np. odświeżanie kursów walut). Jedyne miejsce w module, które otwiera sesję poza żądaniem: `with scope() as session: service = build_<x>(session); return service.operacja(...)`. Nie commituje, nie dotyka repozytoriów, zwraca dane, nie encje ORM. Plik powstaje tylko w module, który ma taką operację.

---

## 6. Moduły biznesowe

Każdy moduł ma własny dokument; tu tylko granice odpowiedzialności.

| Moduł | Zakres | Dokument |
|---|---|---|
| `core_data` | Użytkownik (konto, e-mail, hash hasła, aktywność) | [`02_core_data_module.md`](./02_core_data_module.md) |
| `security` | Logowanie, JWT access/refresh, hashowanie haseł. **Nie** przechowuje użytkowników (to `core_data`) | [`03_security_module.md`](./03_security_module.md) |
| `assets` | Waluty, klasy waloru, walory, dane rynkowe (Yahoo Finance) | [`04_assets_module.md`](./04_assets_module.md) |
| `portfolios` | Portfele, pozycje, operacje, metryki i wektory | [`05_portfolios_module.md`](./05_portfolios_module.md) |

Kierunek zależności między modułami: `portfolios` → `assets`, `portfolios` → `core_data`; `security` → `core_data`. `assets` i `core_data` nie zależą od `portfolios`.

---

## 7. Obsługa błędów

Kontrakt: [ADR-0007](../adr/0007-kontrakt-bledow-z-code.md).

```
Repository  →  rzuca wyjątek domenowy (np. NotFoundError)
Service     →  przepuszcza lub transformuje; nigdy HTTPException
Handler     →  globalny handler w core/errors.py zamienia na odpowiedź HTTP
Client      ←  {"detail": "...", "code": "..."} z właściwym statusem
```

`APIError(message, status_code, code=None, headers=None)` jest bazą; podklasy: `BadRequestError` 400, `AuthenticationError` 401, `ForbiddenError` 403, `NotFoundError` 404, `ConflictError` 409, `GoneError` 410, `ValidationException` 422. `code` (`UPPER_SNAKE`, np. `PORTFOLIO_NOT_FOUND`) jest kontraktem z klientem; `detail` to fallback.

Globalne handlery (`register_error_handlers`): `APIError` → `{"detail", "code"}` (5xx logowane jako `error`, 4xx jako `info`); `pydantic.ValidationError` → 422; każdy inny wyjątek → 500 ze stałym `"Internal server error"`, traceback tylko w logu. Komunikaty API są w jednym języku (angielski).

**Naruszenie niezmiennika domeny** (ujemna kwota, brak środków) to wyjątek domenowy z `domain/` (podklasa `ValueError`, bez zależności od `app.core`); serwis tłumaczy go na `BadRequestError` z `code`. Nie propaguj gołego `ValueError` do routera.

Poza żądaniem HTTP nie ma globalnego handlera — wyjątek trafia do entrypointu (polityka domenowa) albo drivera (kod wyjścia).

---

## 8. Strategia testowania

| Poziom | Co testujemy | Narzędzia | Izolacja |
|---|---|---|---|
| **Unit** | Serwisy, `domain/` | `pytest`, `MagicMock` | Mock repozytoriów, bez bazy |
| **Integration** | Endpointy + baza | `pytest`, `TestClient`, PostgreSQL | Prawdziwa baza (prefiks danych testowych, sprzątanie) |
| **Architektura** | Zakazy zależności | `pytest` + AST | Skanuje `backend/app/` |

- Testy mieszkają w `<moduł>/tests/unit/` i `<moduł>/tests/integration/`; testy przekrojowe w `core/tests/` (`pyproject.toml` ma `testpaths = ["app"]`).
- Testy integracyjne wymagają prawdziwego `DATABASE_URL` (PostgreSQL); **brak fallbacku na sqlite**.
- Serwis w teście składamy tym samym builderem co produkcja; entrypoint dostaje sesję testu przez parametr `scope` ([`06_wiring_i_entrypointy.md` §7](./06_wiring_i_entrypointy.md#7-testy-entrypointów-i-wiringu)).
- **Test architektury** (`core/tests/test_architecture.py`, AST, ścieżki od `Path(__file__)`) egzekwuje: serwisy/repozytoria nie otwierają sesji i nie importują `fastapi`; `wiring.py`/`entrypoints.py`/serwisy nie importują `dependencies.py`; entrypoint nie importuje repozytoriów; API nie importuje repozytoriów; brak `HTTPException` poza `dependencies.py`.

---

## 9. Migracje

Tylko `alembic revision --autogenerate -m "..."`; pliku migracji nie edytuje się ręcznie (poza poprawą błędnie wygenerowanego, za zgodą). Model musi być zarejestrowany w `models_registry.py`, inaczej `autogenerate` go nie zobaczy. Zmiany schematu są addytywne: nowa kolumna → backfill → przełączenie odczytów.

---

## 10. Stan kodu vs cel

Opis powyżej to **cel**. Stan faktyczny kodu na 2026-09-30 i krok planu, który domyka lukę ([plan refaktoryzacji](../../plans/01_refaktoryzacja_do_wzorca_waterworks.md)):

| Element wzorca | Stan w kodzie | Krok planu |
|---|---|---|
| `core/errors.py`, `APIError` z `code` | Brak. Serwisy i API rzucają `HTTPException` i gołe `ValueError` | R-01 |
| `SQLRepository.transaction()` | Brak. Repozytoria commitują same lub mają `commit: bool` | R-02 |
| `session_scope`, `provide` | Brak. Jest tylko `get_db` | R-03 |
| `wiring.py` + `dependencies.py` jako adapter | Brak `wiring.py`. `dependencies.py` składa graf łańcuchami `Depends` | R-04…R-07 (per moduł) |
| Struktura podfolderów | `assets` — prawie (brak `wiring.py`, serwisy w jednym pliku); `portfolios`, `core_data`, `security` — płaskie pliki | R-04…R-07 |
| `portfolios/domain/` | Brak. Reguły salda w `PortfolioService`/`TransactionService` na `dict`; metryki w `portfolios/analytics/` (numpy/pandas/yfinance) | R-08 |
| Test architektury | Brak | R-09 |
| `mypy` | Skonfigurowany, niezainstalowany; `mypy_path` wskazuje obcy projekt | R-10 |
| Logika w routerach | `portfolios/api.py` (493 linie) zawiera walidację i orkiestrację operacji | R-08 |
| Testy w `unit/` i `integration/` | `infrastructure` — tak; `assets` ma tylko `integration/`; pozostałe moduły płasko | R-04…R-07 |
