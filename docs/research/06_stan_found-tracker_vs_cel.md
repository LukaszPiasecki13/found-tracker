---
id: research-fundtracker-gap-analysis
status: current
type: mixed
scope: research/gap-analysis
last_reviewed: 2026-10-02
---

# Co FundTracker potrafi dziś i czego mu brakuje do poziomu myfund?

> **Dokument L4 (dowód).** Stan na 2026-10-01/02. Nienormatywny — rekomendacje stąd stają się obowiązujące dopiero przez ADR lub plan. Append-only: nie poprawiamy, dopisujemy nowe badanie i link do następcy.

Migawka kodu z 2026-10-01 (HEAD `9eda5fe`). Stan systemu opisuje L2 i kod — ten dokument jest dowodem do roadmapy, nie kontraktem.

**Metoda:** czytanie kodu i dokumentacji (read-only). Testów, lintów ani serwerów nie uruchamiano. Defekty z §7 i luki
oznaczone jako defekt ponownie zweryfikowano 2026-10-02, otwierając wskazane `plik:linia`. Ścieżki `app/...` = `backend/app/...`.
Słownictwo wg [CONTEXT.md](../business/CONTEXT.md); architektura wg
[01_backend-architecture.md](../technical/backend/01_backend-architecture.md).

## 0. TL;DR

- **Zakres dziś:** pięć typów Operacji (`buy/sell/deposit/withdrawal/dividend`); jedna pula gotówki na Portfel w jego
  Walucie bazowej; Pozycje w średniej ważonej (weighted average); ceny na żywo z Yahoo (`yfinance`); wektory wykresów
  liczone od zera przy każdym żądaniu; brak zapisu historii cen; brak harmonogramu.
- **Architektura dojrzała:** warstwowy monolit modułowy, czysta `domain/`, porty/adaptery dla danych rynkowych, testy
  architektury (AST), CI z Postgresem, mypy strict, ruff. Każda nowa funkcja musi ją respektować (§9).
- **Największe luki wobec myfund:** brak historii cen i kursów, brak TWR/MWR/XIRR, brak zrealizowanego zysku, brak
  partii zakupu (lotów podatkowych) i FIFO (PIT-38), brak obligacji skarbowych (EDO/COI…), brak zdarzeń korporacyjnych,
  brak importu CSV/z brokera, brak benchmarku (stub we frontendzie zwraca `null`). Wielowalutowość jest w praktyce
  zepsuta (F1).
- **Defekty poprawności (§7):** F1 wycena FX względem USD, F2 wektory ignorują FX i dywidendy, F3 „Całkowita wartość"
  na dashboardzie sumuje tylko gotówkę, F4 dialog kupna podpowiada kurs USD, F5 Walor tworzony po tickerze dostaje
  Walutę Portfela.

## 1. Model danych

Wszystkie modele dziedziczą z `Base` (`app/infrastructure/sql/base.py:5-8`), rejestr: `app/infrastructure/sql/models_registry.py`.
Kwoty, ilości i kursy: `Numeric` → `Decimal` (ADR-0010).

| Tabela / model | Pola (typ, ograniczenia) | Uwagi |
|---|---|---|
| `users` / `User` (`core_data/models/user.py:7-13`) | id; email String(254) unique; password_hash; is_active | brak ustawień użytkownika (Waluta wyświetlania, locale), brak znaczników czasu |
| `assets_assetclass` / `AssetClass` | id; name String(20) unique | — |
| `assets_currency` / `Currency` (`assets/models/currencies.py:13-31`) | id; code String(3) unique; exchange_rate Numeric(18,9) default 1; base_currency_id FK self, nullable | **exchange_rate = jednostki USD za 1 jednostkę** (§4, F1); `base_currency_id` nieużywane przez logikę |
| `assets_asset` / `Asset` (`assets/models/assets.py:15-42`) | ticker String(20) unique (`strip().upper()`); name; asset_class_id; currency_id; current_price Numeric(18,9); exchange; sector; updated_at | **jedyna cena, bez historii**; brak ISIN, symbolu dostawcy, kuponu, zapadalności, nominału |
| `portfolios_portfolio` / `Portfolio` (`portfolios/models/portfolio.py:26-67`) | owner_id; name (unique per owner); base_currency_id; cash_balance Numeric(18,3); total_deposited Numeric(18,3); is_active; created_at/updated_at | **jedna pula gotówki w Walucie bazowej**; kaskada tylko w ORM, w FK bazy brak `ON DELETE CASCADE` |
| `portfolios_position` / `Position` (`portfolios/models/position.py:23-70`) | portfolio_id+asset_id unique; quantity; average_buy_price (w Walucie Waloru, **z prowizją**); average_fx_rate (ważony ilością); total_fees; total_dividends; opened_at/updated_at | stan pochodny, przebudowywany z Operacji; wiersz usuwany przy ilości 0; brak partii zakupu (CONTEXT: „nie modelujemy lotów") |
| `portfolios_operation` / `Operation` (`portfolios/models/operation.py:24-69`) | portfolio_id; asset_id nullable; operation_type String(20) (**bez CHECK w bazie**); quantity, price; amount Numeric(18,2) nullable; fee; fx_rate default 1; notes; operation_date (tz, index); created_at | indeks `(portfolio_id, operation_date)`; `OperationType` w `portfolios/domain/enums.py:9-14` |

**Migracje** (`backend/alembic/versions/`): `78e899c115c6` (initial, 6 tabel) i `74834345f4d0` (wyłącznie zmiana nazw
indeksów). CI uruchamia `alembic check` (wykrywanie dryfu).

**Seed** (`backend/seed/seed_data.py`): użytkownik `admin@foundtracker.com`/`admin` (l.64-65); Waluty z kursami
względem USD — USD 1.0, EUR 1.08, PLN 0.25, GBP, JPY, CHF (l.67-74) — co potwierdza semantykę „USD za jednostkę";
Walory GPW jako `CDR`, `PKO`, `PKN` (l.132-150) bez sufiksu `.WA`, podczas gdy niemieckie mają `SAP.DE`, `SIE.DE`
(l.159-168). **[niezweryfikowane]** że Yahoo wymaga `.WA` dla GPW i odświeżenie tych tickerów zawodzi.

## 2. Endpointy

Routery montowane w `app/main.py`; wszystko poza `/`, `/health` i `/auth/*` wymaga `get_current_user`. Błędy:
`{"detail", "code"}` (`app/core/errors.py:80-112`; `code` jest opcjonalny w `APIError`).

| Grupa | Metoda + ścieżka | Co robi / uwagi |
|---|---|---|
| infra | GET `/`, GET `/health` | `/health` robi `SELECT 1`, 503 gdy baza nie odpowiada |
| auth | POST `/auth/register` | rejestracja **otwarta**; hasło ≥8; 409 `EMAIL_ALREADY_REGISTERED` |
| auth | GET `/auth/me`, POST `/auth/login`, POST `/auth/token/refresh` | JWT HS256, access 30 min, refresh 1 dzień, refresh bezstanowy (ADR-0012) |
| assets | GET/POST/PUT/PATCH/DELETE `/assets/asset-classes[/{id}]` | DELETE → 409 `ASSET_CLASS_IN_USE` |
| assets | GET/POST/PUT/PATCH/DELETE `/assets/currencies[/{id}]` | kurs można ustawić ręcznie |
| assets | GET `/assets/?search=`, POST `/assets/` | ręczny Walor, cena ustawiana ręcznie |
| assets | GET `/assets/search-yahoo?q=` | **dokładny ticker**, nie wyszukiwanie po nazwie (`assets/services/market_data.py:49-68`) |
| assets | POST `/assets/create-from-yahoo` | Klasa Waloru z `quoteType`, Waluta z notowania; tworzy brakujące |
| assets | GET/PUT/PATCH/DELETE `/assets/{id}` | PUT/PATCH = **jedyna droga ręcznej wyceny**; DELETE → 409 `ASSET_IN_USE` |
| portfolios | GET `/portfolios/?name=` | podsumowanie wycenione po **zapisanych** cenach, bez odświeżania |
| portfolios | POST/GET/PUT/PATCH/DELETE `/portfolios/[{id}]` | zmiana `base_currency_id` **nie przelicza** gotówki ani historii |
| portfolios | GET `/portfolios/positions?portfolio_name=` | **synchronicznie odświeża wszystkie kursy i ceny Pozycji z Yahoo**, potem wycenia (`portfolios/services/positions.py:37-39`) |
| portfolios | GET `/portfolios/operations?portfolio_name=` | najnowsze pierwsze, **bez paginacji** |
| portfolios | POST `/portfolios/operations` | stosowana do **bieżącego** stanu niezależnie od `operation_date` (`portfolios/services/operations.py:99-126`) |
| portfolios | PUT/PATCH/DELETE `/portfolios/operations/{id}` | potem pełna przebudowa historii |
| portfolios | GET `/portfolios/portfolio-vectors?...&interval=1d&vectors=[json]` | bez `portfolioName` miesza wszystkie Portfele niezależnie od Waluty |

Kwoty w odpowiedziach: `DecimalNumber` (w JSON jako float, `app/core/schemas.py`); zaokrąglenie raz na granicy
(wartości 3 miejsca, % 4, prowizje 2, `ROUND_HALF_EVEN`).

## 3. Logika domenowa

Szczegóły modułu: [05_portfolios_module.md](../technical/backend/05_portfolios_module.md).

### 3.1 Księga (`app/modules/portfolios/domain/ledger.py`)

Czysta biblioteka standardowa (`Decimal`, zamrożone dataclassy), bez zaokrągleń. Walidacja `validate` (l.272-292):
buy/sell — Walor, ilość>0, cena>0, prowizja≥0, fx>0; deposit/withdrawal — amount>0, bez Waloru; dividend — Walor, amount>0, fx>0.

| Operacja | Gotówka | Pozycja | total_deposited | Linie |
|---|---|---|---|---|
| buy | `-= (q·p + fee)·fx`; musi się zmieścić, inaczej `InsufficientCashError` | nowa: `avg=(q·p+fee)/q`, `avg_fx=fx`; istniejąca: `avg=(q0·avg0+q·p+fee)/(q0+q)`, `avg_fx=(q0·fx0+q·fx)/(q0+q)`; `total_fees += fee` | – | 167-201 |
| sell | `+= (q·p − fee)·fx` | wymaga Pozycji i q ≤ posiadane; **średnie bez zmian** (nie FIFO); `total_fees += fee`; wiersz usuwany przy 0; **brak zrealizowanego zysku** | – | 204-225 |
| deposit | `+= amount − fee` | – | `+= amount` | 228-234 |
| withdrawal | `-= amount + fee` (musi się zmieścić) | – | `-= amount` | 237-246 |
| dividend | `+= (amount − fee)·fx` | wymaga otwartej Pozycji; `total_dividends += amount` (Waluta Waloru) | – | 249-261 |

- `fx_rate` Operacji wpisuje użytkownik; nie ma wyszukiwania kursu historycznego.
- Prowizja wchodzi do średniej ceny zakupu **i** do `total_fees`.
- `rebuild()` (l.311) składa całą historię od pustego stanu; kolejność `operation_date, created_at, id`.
- Edycja/usunięcie: zmiana wiersza → przebudowa → nadpisanie gotówki i Pozycji; naruszenie reguły → 400 i rollback.
- POST z datą wsteczną nie jest odtwarzany na historii — późniejsza przebudowa może go odrzucić (otwarte w 05_portfolios_module).
- Błędy domeny: `PortfolioDomainError(ValueError)` z `code`, tłumaczone w serwisie na `OperationRejectedError` (400).

### 3.2 Wycena (`app/modules/portfolios/domain/valuation.py`)

| Wielkość | Wzór | Linia |
|---|---|---|
| cost_basis | `q · avg_buy_price` (Waluta Waloru) | 53 |
| cost_in_portfolio | `cost_basis · avg_fx_rate` | 54 |
| market_value | `q · asset.current_price`, × `asset.currency.exchange_rate` gdy Waluta Waloru ≠ bazowa Portfela | 55-57 |
| unrealized / return_pct | `market_value − cost_in_portfolio`; `/cost_in_portfolio·100` | 58-64 |
| positions_value / total_value | `Σ market_value`; `cash + positions_value` | 81-82 |
| total_profit_loss / total_return_pct | `total_value − total_deposited`; `/total_deposited·100` (prosty zwrot od wpłat netto, nie TWR) | 83, 88 |
| total_fees | `Σ position.total_fees` — bez prowizji od wpłat/wypłat | 89 |
| wagi | względem `total_value` (z gotówką) | 91 |

Dzielenie przez zero zwraca 0.

### 3.3 Wektory metryk (`app/modules/portfolios/services/metrics.py`, numpy, ADR-0005 wariant (a))

- Port `PriceHistoryProvider{close_history, current_price}` realizowany przez `assets.MarketDataService`.
- Oś dat: każdy dzień kalendarzowy `start..end`; Operacja trafia na indeks dnia; sumy narastające w `Decimal`, zapis jako float.
- **Notowania pobierane z Yahoo przy każdym żądaniu** (l.172), raz na ticker; luki wypełniane w przód, potem wstecz;
  ostatni dzień roboczy bierze bieżącą cenę (l.177-180). Interwał tylko `1d`.

| Wektor | Definicja | Linia |
|---|---|---|
| `assets` / `asset_classes` | ilość × zamknięcie, per ticker / per klasa | 185-187 |
| `net_deposits_vector` | narastające deposit − withdrawal | 226-237 |
| `transaction_cost_vector` | buy `+q·p+fee`, sell `−(q·p−fee)`, pozostałe `+fee` | 108-116, 239-244 |
| `profit_vector` | Σ wartość Walorów − transaction_cost | 246-247 |
| `free_cash_vector` | net_deposits − transaction_cost | 249-250 |
| `portfolio_value_vector` / `pocket_value_vector` | free_cash + Σ wartość Walorów | 252-253 |

Wektor, który się nie policzy, zwraca zera, a błąd idzie do logu (l.347-356).

**Nieścisłości (zweryfikowane czytaniem):**
1. `_transaction_cost_change` (l.108-116) ignoruje `fx_rate`; wartości Walorów (l.185-187) nie są przeliczane na Walutę Portfela → wektory wielowalutowe mieszają Waluty.
2. Kwota dywidendy nie wchodzi do gotówki ani zysku (dla `dividend` liczona jest tylko prowizja jako koszt, l.116) → `free_cash_vector` rozjeżdża się z `cash_balance` księgi po każdej dywidendzie.
3. Brak TWR/IRR; „zysk" = wartość − koszt.
4. Obsługa weekendów zakłada handel pn–pt (`_SATURDAY = 5`, l.53); święta giełdowe nieobsługiwane.

### 3.4 Decimal i numpy

`Decimal` od domeny po kolumny; dane dostawcy przez `Decimal(str(x))` (`app/infrastructure/market_data/yahoo.py`).
`float` tylko w wektorach i serializacji JSON. numpy tylko w `services/metrics.py`; czystość `domain/` pilnuje
`portfolios/tests/unit/test_domain_purity.py`.

## 4. Dane rynkowe

Szczegóły modułu: [04_assets_module.md](../technical/backend/04_assets_module.md).

| Element | Stan | Plik |
|---|---|---|
| Port | `Quote{symbol,name,exchange,quote_type,currency,sector,current_price,regular_market_price,previous_close}`; `MarketDataProvider`: `fetch_quote`, `fetch_fx_rate(from,to)`, `fetch_close_history(ticker,start,end)` (end wyłączny); `MarketDataUnavailableError` → 502 | `app/core/market_data.py` |
| Adapter Yahoo (jedyny import `yfinance`) | `Ticker(t).info`; kurs `"{FROM}{TO}=X"` (bid → regularMarketPrice → previousClose); `.history(interval="1d")["Close"]`; każdy wyjątek → `MarketDataUnavailableError`; brak retry, timeoutów, limitów, cache | `app/infrastructure/market_data/yahoo.py` |
| Inne źródła | brak (Stooq, NBP, GPW, analizy.pl — żadnego adaptera) | — |
| `search` | dokładny ticker; awaria dostawcy → `[]` | `assets/services/market_data.py:49-68` |
| `refresh_asset_prices` | best-effort per Walor, pobranie przed transakcją | `assets/services/market_data.py:87-107` |
| `refresh_currency_rates(base_code=DEFAULT_CURRENCY_CODE)` | ustawia każdej Walucie kurs „jednostki `base_code` za 1"; domyślnie USD | `assets/services/market_data.py:109-129`; `assets/constants.py:4` |
| Historia | **brak tabel cen i kursów**; nadpisywane tylko `Asset.current_price` i `Currency.exchange_rate` | §1 |
| Harmonogram | **brak**; odświeżanie tylko synchronicznie w `GET /portfolios/positions`; w `backend/app` nie ma żadnego `entrypoints.py` ani `cli.py` (`find`) | `portfolios/services/positions.py:37-39` |
| Obsługa awarii | refresh loguje i pomija; search → pusto; `create-from-yahoo` → 502; wektory → zera | — |

## 5. Frontend (`frontend/src/`, React 19 + Vite + MUI 7 + TanStack Query/Table + Recharts 3)

| Trasa (`App.tsx:26-97`) | Strona | API |
|---|---|---|
| `/login`, `/register` | `LoginPage`, `RegisterPage` | `/auth/login`, `/auth/register`, `/auth/me` |
| `/` | `DashboardPage` + `PortfolioOverview` + `PocketsList` | `GET /portfolios/` |
| `/pockets/:slug` (slug = nazwa Portfela) | 4 karty, `PositionsTable`, dialogi Kup/Sprzedaj/Gotówka | `/portfolios/?name=`, `/portfolios/positions`, `/portfolios/{id}` |
| `/pockets/:slug/history` | `OperationsTable` (tylko usuwanie) | `GET/DELETE /portfolios/operations` |
| `/pockets/:slug/charts` | 5 liniowych, 1 kołowy, 2 warstwowe, wartość vs wpłaty; zakres dat (domyślnie rok) | `/portfolios/portfolio-vectors` + Pozycje |
| `/compare` | do 4 Portfeli (4 zaszyte hooki), wartość znormalizowana (start=100) — wpłaty zniekształcają porównanie % | vectors ×4 |
| `/operations` | `OperationsTable` wszystkich Portfeli | `GET /portfolios/operations` |
| `*` | przekierowanie na `/` | — |

**Dialogi:** `BuyAssetDialog` (wyszukiwanie z debounce → `create-from-yahoo` → POST Operacji); `SellAssetDialog`
(`amount = q·p − fee`); `CashOperationDialog` (tylko deposit/withdrawal, `fee: 0` na sztywno, l.42); `AddPocketDialog`.
Daty wysyłane jako `YYYY-MM-DD` (bez godziny).

**Zaszyte, atrapy, zepsute:**

| Element | Dowód |
|---|---|
| „Całkowita wartość" = suma samego `cash_balance`; `positionsCount` dostaje liczbę Portfeli; sumy bez przeliczenia Walut (F3) | `frontend/src/pages/DashboardPage.tsx:14`, `:36` |
| `PortfolioOverview` zawsze formatuje w PLN; wpłaty podpisane „Kapitał początkowy" | `frontend/src/components/portfolio-overview.tsx:27`, `:116` |
| `benchmarkService.getSP500Data()` zwraca `null` (TODO); **nigdzie nieimportowany** (grep); brak endpointu benchmarku w backendzie | `frontend/src/services/benchmarkService.ts:29-37` |
| Zakładki „Portfele" i „Analizy" bez linku; menu linkuje do `/settings`, którego nie ma w `App.tsx`; indeks zakładek zna `/analytics` i `/alerts` (nie istnieją) | `frontend/src/components/dashboard-header.tsx:52-53, 77, 79, 94` |
| `MiniLineChart` nieimportowany nigdzie (grep) | `frontend/src/components/charts/MiniLineChart.tsx` |
| Brak UI dla istniejącego API: edycja Operacji (`operationService` nie ma update), dywidenda (żaden dialog; `OperationsTable.tsx:54` tylko etykieta), zarządzanie Walorami/Walutami/Klasami, zmiana nazwy Portfela | grep |
| Auth: JWT w `localStorage` (ADR-0012), retry refresh przy 401, odświeżanie co 14 min | `frontend/src/lib/api.ts`, `contexts/AuthContext.tsx` |
| Nazewnictwo „Pocket" w typach i trasach | `frontend/src/types/api.ts` |

## 6. Testy

pytest, `testpaths=["app"]`; markery `unit`/`integration` nadawane wg katalogu (`app/conftest.py`). `-m "not integration"`
pomija testy z bazą, ale `conftest` nadal wymaga `TEST_DATABASE_URL` lub lokalnego `DATABASE_URL`. Izolacja integracyjna:
zewnętrzna transakcja z rollbackiem + savepointy.

| Obszar | Pliki (liczba testów wg materiału wejściowego) |
|---|---|
| Architektura | `core/tests/test_architecture.py` (18): warstwy, sesje, brak repo w API, `HTTPException` tylko w `dependencies.py`, zakaz Django, `yfinance` tylko w infrastructure, cross-module przez serwisy, commit tylko w `transaction()` |
| Core / infrastruktura | config, errors, market_data, provide, schemas; sql_factory, session_scope, sql_repository, yahoo_provider (mock) |
| assets | unit: serwisy, API, repozytoria, wiring; integracja: assets_flow, reference_data_flow; fake dostawcy `assets/tests/fakes.py` |
| core_data / security | unit + integracja |
| portfolios | unit: ledger (28), **ledger_parity (7)**, valuation (6), metrics_service (13), serwisy, API, domain_purity, wiring; integracja: portfolio_flow, repozytoria |

Testy parytetu (`portfolios/tests/unit/test_ledger_parity.py`) odtwarzają scenariusze dawnego Django (losowe, ziarno
stałe). **Niepokryte:** poprawność FX w wycenie, wektory wielowalutowe, dywidendy w wektorach, cały frontend (brak
runnera testów w `frontend/package.json`).

## 7. Defekty poprawności

Zweryfikowane 2026-10-02 czytaniem kodu (nie uruchomieniem). Każdy wymaga testu odtwarzającego przed poprawką.

| # | Defekt | Dowód (`plik:linia`) | Skutek |
|---|---|---|---|
| F1 | **Wycena FX względem USD.** `refresh_currency_rates` ustawia kursy jako „USD za jednostkę" (domyślne `base_code = DEFAULT_CURRENCY_CODE = "USD"`), wywoływane bez argumentu; seed też w USD. `_value_holding` mnoży wartość rynkową przez `asset.currency.exchange_rate`, gdy Waluta Waloru ≠ bazowa Portfela, bez względu na to, jaka jest Waluta bazowa | `app/modules/assets/services/market_data.py:109`; `app/modules/assets/constants.py:4`; `app/modules/portfolios/services/positions.py:37`; `app/modules/portfolios/domain/valuation.py:55-57`; `backend/seed/seed_data.py:67-74` | Portfel PLN + akcja USD: wartość zostaje w USD (×1); Portfel PLN + akcja EUR: wynik w USD (×1.08). Poprawne tylko dla Portfela w USD. Koszt liczony po `average_fx_rate` Operacji (l.54), więc niezrealizowany zysk miesza jednostki |
| F2 | **Wektory metryk ignorują FX i dywidendy.** Koszt bez `fx_rate`; wartości Walorów nieprzeliczane; dywidenda liczona tylko jako koszt prowizji | `app/modules/portfolios/services/metrics.py:108-116`, `:185-187` | Wykresy Portfeli wielowalutowych błędne; `free_cash_vector` ≠ `cash_balance` po dywidendzie; zysk na wykresie zaniżony o dywidendy |
| F3 | **„Całkowita wartość" na dashboardzie = sama gotówka**; `positionsCount` = liczba Portfeli; sumowanie różnych Walut bez przeliczenia | `frontend/src/pages/DashboardPage.tsx:14`, `:36` | Główna liczba aplikacji pomija wartość Pozycji |
| F4 | **Dialog kupna podpowiada `fx_rate` z kursu względem USD** (`selectedAsset.currency.exchange_rate`) | `frontend/src/components/dialogs/BuyAssetDialog.tsx:55-69` (kurs l.63) | Dla Portfela nie-USD domyślny kurs Operacji jest błędny i trafia do `average_fx_rate` |
| F5 | **Walor tworzony po tickerze w POST Operacji dostaje Walutę bazową Portfela** (`currency_id=portfolio.base_currency_id`) | `app/modules/portfolios/services/operations.py:176-180` | Zagraniczna akcja kupiona w Portfelu PLN zapisana jako Walor w PLN — wycena i FX trwale błędne |
| F6 | **Zmiana Waluty bazowej Portfela** ustawia pole bez przeliczenia gotówki, `total_deposited` i historii | `app/modules/portfolios/services/portfolios.py:150-153` | Ta sama liczba gotówki cicho zmienia Walutę |

## 8. Luki funkcjonalne

| # | Luka | Dowód |
|---|---|---|
| G1 | Brak zapisu historii cen i kursów; każdy wykres pyta Yahoo | §1; `portfolios/services/metrics.py:172` |
| G2 | Brak harmonogramu / odświeżania w tle; brak `entrypoints.py`/`cli.py` | `find`; 04_assets_module (tabela „Stan vs cel") |
| G3 | Brak TWR / MWR / XIRR, Sharpe, zmienności, obsunięcia (drawdown); zwrot = (wartość − wpłaty netto)/wpłaty netto | `portfolios/domain/valuation.py:83, 88` |
| G4 | Brak zrealizowanego zysku przy sprzedaży | `portfolios/domain/ledger.py:204-225` |
| G5 | Brak partii zakupu (lotów podatkowych) / FIFO (PIT-38) i śledzenia podatku Belki; tylko średnia ważona | `ledger.py:184-196`; CONTEXT.md |
| G6 | Brak zdarzeń korporacyjnych (split, spin-off, prawa poboru, zmiana tickera) i typów Operacji: odsetki, podatek, sama opłata, przeniesienie między Portfelami, wymiana Walut | `portfolios/domain/enums.py:9-14` |
| G7 | Jedna pula gotówki w Walucie bazowej; brak gotówki wielowalutowej | `portfolios/models/portfolio.py:38-43` |
| G8 | Defekt wyceny FX | F1 |
| G9 | Brak historycznych kursów FX; `fx_rate` wpisywany ręcznie; brak NBP (do PIT potrzebny kurs NBP z dnia poprzedzającego **[niezweryfikowane]** — reguła podatkowa nie sprawdzona w tym badaniu) | `ledger.py:170` |
| G10 | Wektory ignorują FX i dywidendy | F2 |
| G11 | Brak obligacji skarbowych (EDO/COI/ROR…, naliczanie wg wzoru inflacyjnego), lokat, Walorów wycenianych ręcznie (nieruchomości) poza statycznym `current_price` | `assets/models/assets.py:15-42` |
| G12 | Brak źródła danych dla GPW/Polski; tylko Yahoo, wyszukiwanie po dokładnym tickerze, domyślna Waluta USD; tickery GPW w seedzie bez `.WA` (**[niezweryfikowane]** zachowanie Yahoo) | `assets/services/market_data.py:49-68`; `assets/constants.py:4` |
| G13 | Brak importu/eksportu (CSV, wyciągi XTB/mBank/Bossa, eksport myfund) | brak kodu (grep) |
| G14 | Brak benchmarku w backendzie; stub nieużywany we frontendzie | `frontend/src/services/benchmarkService.ts:29-37` |
| G15 | Operacje z datą wsteczną nie są walidowane na historii w POST | `portfolios/services/operations.py:99-126` |
| G16 | Brak agregacji między Portfelami we wspólnej Walucie | `portfolios/services/metrics.py:328-330`; F3 |
| G17 | Zmiana Waluty bazowej Portfela reinterpretuje gotówkę i historię | F6 |
| G18 | Brak audytu i soft-delete (ADR-0011 świadomie odłożony) | `docs/technical/adr/0011-audyt-odlozony.md` |
| G19 | Brak paginacji i filtrowania list | `portfolios/repositories/operations.py:32-45` |
| G20 | Dane referencyjne globalne: każdy zarejestrowany użytkownik edytuje Walory, Waluty i ceny, a rejestracja jest otwarta | `assets/api/*.py` (brak sprawdzania właściciela) |
| G21 | Brak ustawień użytkownika (Waluta wyświetlania, locale); `/settings` martwy | `core_data/models/user.py:7-13`; `dashboard-header.tsx:94` |
| G22 | Frontend: brak edycji Operacji, wpisu dywidendy, prowizji przy wpłacie/wypłacie, zarządzania Walorami/Walutami, alokacji wg klasy/sektora/Waluty/kraju, wykresu wartości na dashboardzie | §5 |
| G23 | Operacje z UI mają tylko datę; kolejność w ciągu dnia wg `created_at` | `BuyAssetDialog.tsx`; `portfolios/repositories/operations.py:53-57` |
| G24 | Wycena nieaktualna w `/portfolios/` i `/portfolios/{id}` (zapisane ceny); odświeża tylko lista Pozycji | `portfolios/services/portfolios.py:63-64` vs `positions.py:37-39` |
| G25 | Brak kalendarza/prognozy dywidend, alertów, listy obserwowanych, celów, typów kont IKE/IKZE | modele i enumy; `dashboard-header.tsx:53` |

## 9. Ograniczenia architektoniczne, które każda nowa funkcja musi respektować

Źródła: `CLAUDE.md` (Constraints), [01_backend-architecture.md](../technical/backend/01_backend-architecture.md)
(§2, §5, §9), ADR-y w `docs/technical/adr/` — wszystkie `Proposed`.

1. **Warstwy:** API → Services → Repositories → Infrastructure; `domain/` pod serwisami, tylko biblioteka standardowa;
   infrastructure tylko od core/errors; drivery (main, cli, zadania w tle) wołają wyłącznie `entrypoints.py`.
   Egzekwuje `core/tests/test_architecture.py`.
2. **Cross-module wyłącznie przez serwisy** (ADR-0006): serwis nie trzyma cudzego repozytorium; odczyt cudzego modelu
   ORM w JOIN dozwolony; cudze `domain/` tylko przez `__init__`; bez cykli — odwrócenie przez port Protocol (jak
   `PriceHistoryProvider`).
3. **Kompozycja:** obiekty składa tylko `wiring.py` (`build_x(session)`); `dependencies.py` = `get_x = provide(build_x)`
   (ADR-0002); adapter zewnętrzny wybierany w wiring (`assets/wiring.py`).
4. **Transakcje:** jedna sesja na żądanie, repozytorium nie commituje (ADR-0001); granica `with repo.transaction():` w
   serwisie; zapisy wielomodułowe przez rdzenie bez commitu (np. `AssetService.get_or_create_by_ticker`), transakcję
   trzyma orkiestrator (ADR-0008); poza HTTP sesję otwiera tylko `entrypoints.py` przez `session_scope()` (ADR-0002) —
   **tu musi się podpiąć harmonogram cen/kursów**.
5. **Błędy:** serwisy rzucają podklasy `APIError` z `code`, nigdy `HTTPException` ani goły `ValueError` (ADR-0007);
   błędy domeny = `ValueError` z `code`, tłumaczone w serwisie.
6. **Pieniądze:** kwoty, ceny, ilości, kursy jako `Decimal`; `Numeric` zaokrągla przy zapisie; `float` tylko w wektorach
   wykresów (ADR-0010); dane dostawcy przez `Decimal(str(x))`.
7. **Schematy:** żądania na granicy modułu `extra="forbid"`, tylko kształt; reguły biznesowe w serwisie/domenie;
   odpowiedzi `DecimalNumber`.
8. **Zwroty i nazewnictwo:** serwisy CRUD zwracają encje ORM, serwisy read-model — DTO (ADR-0003); repozytorium:
   `find_*` → `None`, `get_*` rzuca (ADR-0004).
9. **Warstwa domeny:** opcjonalna, czysta (bez zegara i I/O), komponenty wstrzykiwane przez wiring (DOM-1…DOM-11,
   ADR-0005); numpy poza `domain/` (wariant (a)); czystość testuje `test_domain_purity.py`.
10. **Migracje:** wyłącznie `alembic revision --autogenerate -m "..."`, nigdy ręczna edycja; nowy model w
    `infrastructure/sql/models_registry.py`; zmiany addytywne; CI uruchamia `alembic check`.
11. **`yfinance`** tylko w `app/infrastructure/` (test architektury); każde nowe źródło danych = adapter portu w `core/`.
12. **Proces:** ADR zostaje `Proposed`, dopóki człowiek nie zaakceptuje; nowy dokument → wpis w
    `docs/00_KNOWLEDGE-MAP.md`; bez przepisywania kodu „przy okazji" przed akceptacją ADR-ów; bez `commit`/`push` bez
    zgody; Python tylko przez `.venv` w korzeniu, instalacja zależności za zgodą.
13. **Słownik:** Portfel, Pozycja, Operacja, Walor, Waluta; unikać „lot", „transakcja" ([CONTEXT.md](../business/CONTEXT.md)).
    Funkcja FIFO / partii zakupu wymaga biznesowego ADR i zmiany słownika; biznesowe ADR-y w `docs/business/adr/`
    (dziś tylko `README.md`).

## 10. Narzędzia

| Narzędzie | Stan | Dowód |
|---|---|---|
| Python | 3.14 (ruff `py314`, mypy 3.14, CI 3.14) | `backend/pyproject.toml`; `.github/workflows/backend.yml` |
| ruff | `ruff==0.15.14`; E,F,W,I,N,UP,SIM,RET,RSE,RUF,B,ISC,Q; alembic wyłączony | `backend/pyproject.toml`; `backend/requirements.txt:61` |
| mypy | `mypy==2.3.0`, `strict=true`; testy/sqlalchemy/alembic `ignore_errors` | `backend/requirements.txt:33` |
| pytest | `8.3.4` | `backend/requirements.txt:51` |
| CI backend | ruff check + format --check, `mypy app`, `alembic upgrade head`, `alembic check`, seed, `pytest` na postgres:16 | `.github/workflows/backend.yml` |
| CI frontend | `npm ci`, `npm run lint`, `npm run build` (Node 22); bez testów | `.github/workflows/frontend.yml` |
| CI security | gitleaks; pip-audit i npm audit (nieblokujące) | `.github/workflows/security.yml` |
| pre-commit | ruff, eslint, tsc, `kb-validate` z ai-tools | `.pre-commit-config.yaml` |
| Zależności | `python-jose==3.5.0` (≥3.4.0 spełnione), `numpy==2.4.6`, `pandas==3.0.3`, `yfinance==1.3.0`; `passlib==1.7.4` na liście, w `backend/app` nieużywany (grep) | `backend/requirements.txt:35-73` |

Uruchomienie (z `backend/`, `.venv` z korzenia): `pip install -r requirements.txt`, `alembic upgrade head`,
`python -m seed.seed`, `pytest` (z `TEST_DATABASE_URL`) lub `pytest -m "not integration"`; frontend: `npm install`,
`npm run dev`, `npm run build` (wymaga `VITE_API_URL`).

## 11. Niespójności dokumentacji

| # | Niespójność | Dowód |
|---|---|---|
| N1 | `CLAUDE.md` („Stan vs cel") wymienia jako otwarte `mypy` (R-10), reguły ai-tools (R-11), CI (R-12); mapa wiedzy mówi, że R-01…R-13 wykonane, a architektura oznacza R-10 jako domknięty; workflowy CI istnieją | `CLAUDE.md:93-94`; `docs/00_KNOWLEDGE-MAP.md:96`; `01_backend-architecture.md:399`; `.github/workflows/` |
| N2 | `05_portfolios_module.md` w tabeli „Stan vs cel" nadal: `mypy` „nieuruchamiany" | `docs/technical/backend/05_portfolios_module.md:164` |
| N3 | `CLAUDE.md` twierdzi, że w HEAD `python-jose` było `3.3.0`, a poprawka jest w niezacommitowanym drzewie; HEAD `9eda5fe` ma `python-jose==3.5.0`, `git status` czysty | `CLAUDE.md` (sekcja `python-jose`); `git show HEAD:backend/requirements.txt` |

Odrzucone przy weryfikacji: teza, że `docs/technical/frontend/frontend-architecture.md:35` („część endpointów zwraca
same `detail`") jest nieaktualna — `code` w `APIError` jest opcjonalny (`app/core/errors.py:36-89`), więc zdanie może
nadal być prawdziwe.

## Źródła

Badanie wyłącznie wewnętrzne — brak źródeł zewnętrznych (URL). Dowody: kod i dokumentacja repozytorium
`found-tracker` w commicie `9eda5fe`, dostęp 2026-10-01/02; ścieżki i linie podane przy każdym twierdzeniu.

## Luki i niepewności

- Nic nie było uruchamiane (testy, serwer, Yahoo) — defekty F1–F6 potwierdzone czytaniem, nie wykonaniem.
- Zachowanie Yahoo dla tickerów GPW bez `.WA` — **[niezweryfikowane]**.
- Reguła kursu NBP z dnia poprzedzającego dla PIT-38 — **[niezweryfikowane]** w tym badaniu.
- Liczby testów w §6 przejęte z materiału wejściowego, nie przeliczone ponownie.
- Numery linii poza §7 i §11 przejęte z materiału wejściowego; wyrywkowo sprawdzone (ledger, valuation, metrics, seed,
  frontend), reszta może dryfować.
