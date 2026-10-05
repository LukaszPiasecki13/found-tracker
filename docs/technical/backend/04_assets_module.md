---
id: be-assets-module
status: current
last_reviewed: 2026-10-05
type: mixed
scope: backend/assets
applies_to:
  - backend/app/modules/assets/**
  - backend/app/core/market_data.py
  - backend/app/infrastructure/market_data/**
---

# Moduł `assets`

Walory, klasy waloru, waluty oraz dane rynkowe: historia cen i kursów (źródło: ręczne wpisy i Yahoo Finance). Dane referencyjne, na których buduje [`portfolios`](./05_portfolios_module.md). Słownik: [`CONTEXT.md`](../../business/CONTEXT.md).

## 1. Model danych

| Tabela | Encja | Pola |
|---|---|---|
| `assets_assetclass` | `AssetClass` | `id`, `name` (unikalna, max 20) |
| `assets_currency` | `Currency` | `id`, `code` (unikalny, 3), `exchange_rate` (`Numeric(18,9)`, **cache**), `base_currency_id` |
| `assets_asset` | `Asset` | `id`, `ticker` (unikalny), `name`, `asset_class_id`, `currency_id`, `current_price` (`Numeric(18,9)`, **cache**), `exchange`, `sector`, `isin` (unikalny, nullable), `mic`, `country`, `asset_type` (`String(10)`, domyślnie `stock`), `archived_at`, `updated_at` |
| `assets_price` | `AssetPrice` | `id`, `asset_id`, `price_date`, `close` (`Numeric(18,9)`, `CHECK > 0`), `currency_id`, `source`, `is_synthetic`, `fetched_at`; UNIQUE `(asset_id, price_date, source)` |
| `assets_fx_rate` | `FxRate` | `id`, `from_currency_id`, `to_currency_id` (FK `ON DELETE CASCADE`), `rate_date`, `rate` (`Numeric(18,9)`, `CHECK > 0`), `source`, `is_synthetic`, `fetched_at`; `CHECK from <> to`; UNIQUE `(from, to, rate_date, source)` |

Modele w stylu `Mapped[...]`/`mapped_column`; kwoty i kursy to `Decimal` ([ADR-0010](../adr/0010-decimal-i-precyzja-pieniedzy.md)). `CHECK` tylko w nowych tabelach; walidację pól istniejących tabel robi serwis i schemat.

**Historia jest źródłem prawdy, kolumny `current_price` i `exchange_rate` są cache'em.** Serwis `assets` ustawia je w tej samej transakcji, w której zapisuje wiersz historii (jedyny wyjątek: waluta systemowa ma stałe `exchange_rate = 1`): `current_price` = zamknięcie najnowszego dnia, `exchange_rate` = kurs do USD (waluty systemowej, `DEFAULT_CURRENCY_CODE`) najnowszego dnia — bezpośredni albo odwrotny. `portfolios` czyta cache (`FxMapBuilder`), więc jego wycena się nie zmienia.

**Źródła i pierwszeństwo.** `source` ∈ {`manual`, `yahoo`, …}. Różne źródła tego samego dnia współistnieją; dla dnia wygrywa `manual` (ranga 0), potem znany dostawca (`yahoo`, ranga 1), potem reszta (nieznane, ranga 1000; remis rozstrzyga nazwa źródła). Efektywna cena na dzień D = zwycięzca **najpóźniejszego dnia ≤ D** (nie „najlepsze źródło ze wszystkich dni": starsza cena ręczna nie przykrywa nowszego zamknięcia z dostawcy). Forward-fill liczy się przy odczycie, nigdy nie jest zapisywany. `is_synthetic`: notowanie z `fetch_quote` (może być śródsesyjne) zapisuje się jako syntetyczne i jest nadpisywane zamknięciem z historii dostawcy; wpisy ręczne nie są.

**Typ waloru** (`asset_type`, zbiór zamknięty w `constants.ASSET_TYPES`): `stock` (domyślny) albo `etf` — moduł obsługuje akcje i ETF-y. Walor z dostawcy dostaje `etf` dla `quoteType` `ETF`, w pozostałych przypadkach `stock`. Oś ta jest niezależna od edytowalnej **klasy waloru**. `isin` (ISO 6166, suma kontrolna), `mic` (4 znaki) i `country` (2 litery) są walidowane i zapisywane wielkimi literami; `null` czyści.

**Archiwizacja.** `archived_at` ukrywa walor w wyszukiwarce i listach (`include_archived=true` go pokazuje), blokuje nowe Operacje (`409 ASSET_ARCHIVED` z `portfolios`), ręczne ceny i edycję ceny oraz zatrzymuje odświeżanie. Historia, pozycje i wycena zostają. Odwracalna. Walor z historią (Operacje, Pozycje albo ceny) nie jest usuwany: `409 ASSET_HAS_HISTORY` (zastępuje `ASSET_IN_USE`).

## 2. Endpointy

Wszystkie wymagają zalogowanego użytkownika (`get_current_user`). Zapis danych współdzielonych (`PUT/PATCH/DELETE` walorów, walut, klas; archiwizacja; ręczne ceny i kursy) wymaga administratora (`get_current_admin`, `ADMIN_EMAILS`) — `403 ADMIN_REQUIRED`. Parametry ścieżki mają konwerter `:int`, więc statyczne ścieżki (`/assets/asset-classes`, `/assets/currencies`, `/assets/fx-rates`, `/assets/search-yahoo`, `/assets/data-status`, `/assets/refresh-prices`) nigdy nie trafiają do `/{id}`, niezależnie od kolejności routerów.

| Metoda i ścieżka | Opis |
|---|---|
| `GET/POST /assets/asset-classes`, `PUT/PATCH/DELETE /assets/asset-classes/{id}` | CRUD klas waloru |
| `GET/POST /assets/currencies`, `GET/PUT/PATCH/DELETE /assets/currencies/{id}` | CRUD walut; jawny `exchange_rate` przy `POST`/`PUT`/`PATCH` zapisuje ręczny kurs do USD z dzisiejszą datą (domyślne `1` nie jest kursem i nie trafia do historii) |
| `GET /assets/currencies/rate?from_currency=&to_currency=&date=` | Kurs na dzień (domyślnie dziś): bezpośredni albo odwrotny (`via`), nowsza obserwacja wygrywa, remis → bezpośredni; ta sama waluta → `identity`; brak → `404 RATE_MISSING`. Kursów krzyżowych nie składa — to robi `portfolios` |
| `GET /assets/fx-rates?from_currency=&to_currency=&from=&to=&source=` | Historia skierowanej pary, od najstarszej: `{items: [{rate_date, rate, source, is_synthetic}]}` |
| `PUT /assets/fx-rates` | Ręczny kurs dnia (`source=manual`, upsert), nie z przyszłości |
| `GET /assets/?search=&asset_type=&asset_class_id=&country=&include_archived=` | Lista; `search` po tickerze, nazwie i ISIN |
| `POST /assets/` | Utworzenie; początkowa cena > 0 zapisuje się jako dzisiejszy wpis `manual` (cena 0 = brak ceny) |
| `GET/PUT/PATCH/DELETE /assets/{id}` | Walor (GET zwraca szczegóły z klasą i walutą); `current_price` w `PUT/PATCH` (musi być > 0) zapisuje wpis `manual` z dzisiejszą datą; `isin`/`mic`/`country` przyjmują `null` |
| `POST /assets/{id}/archive`, `/unarchive` | Archiwizacja i jej cofnięcie (idempotentne) |
| `GET /assets/{id}/prices?from=&to=&source=&fill=none\|forward` | Seria zamknięć: zwycięzca dnia albo tylko `source`. `fill=forward` wymaga `from`, zwraca każdy dzień kalendarzowy (do `to`, domyślnie dziś; maks. 3660 dni) z ostatnim zamknięciem; `{day, price_date, close, source, is_synthetic, stale}` — `price_date` < `day` dla przeniesionego dnia |
| `PUT/DELETE /assets/{id}/prices/{price_date}` | Ręczna cena dnia (upsert, `close > 0`, nie z przyszłości, waluta = waluta waloru) / usunięcie ręcznej |
| `GET /assets/data-status?only_problems=` | `{fx: {last_success_at}, assets: [{asset_id, ticker, price_date, stale, source, last_success_at}]}` dla aktywnych walorów |
| `POST /assets/refresh-prices` | `{asset_ids: [1..50]}` → **202** `{accepted: [...]}`; żądanie nie woła dostawcy, wywołuje `assets.entrypoints.refresh_prices` w `BackgroundTasks`; nieznane id → 404, zarchiwizowane są pomijane |
| `GET /assets/search-yahoo?q=` | `{"local": [...], "yahoo": [...]}` — lokalne walory (max 10, bez zarchiwizowanych) + trafienia dostawcy, których jeszcze nie ma lokalnie |
| `POST /assets/create-from-yahoo` | Utworzenie waloru z danych dostawcy (klasa, waluta, typ z notowania; cena → wpis `yahoo`) |

Odpowiedzi waloru niosą `isin`, `mic`, `country`, `asset_type`, `archived_at` oraz stan ceny: `price_date`, `price_source`, `stale` (brak ceny albo starsza niż `STALE_AFTER_DAYS` = 7 dni → `true`). Odpowiedzi: `Decimal` serializowany w JSON jako liczba (`core.schemas.DecimalNumber`). Schematy żądań mają `extra="forbid"`.

## 3. Reguły biznesowe

- **Normalizacja** w serwisie: ticker `strip().upper()`, kod waluty `strip().upper()`; nazwa klasy — dokładne dopasowanie.
- **Unikalność** tickera, ISIN, kodu waluty i nazwy klasy sprawdzana przy tworzeniu i edycji; wyścig rozstrzyga `IntegrityError` tłumaczony na ten sam `ConflictError`.
- **Referencje w treści żądania** (`asset_class_id`, `currency_id`, `base_currency_id`, `from_currency_id`, `to_currency_id`) do nieistniejących wierszy → 400; zasób z adresu URL nie istnieje → 404.
- **Usunięcie**: walor z historią → 409 `ASSET_HAS_HISTORY` (archiwizuj); klasa z walorami / waluta z walorami, portfelami lub walutami → 409 `*_IN_USE`. Kursy waluty znikają razem z nią (`ON DELETE CASCADE`), bo to dane o walucie, nie powód do jej zachowania.
- **Historia jest idempotentna**: ponowny zapis tego samego dnia i źródła nadpisuje wiersz. Odświeżenie pisze pod dzisiejszą datą serwera (`date.today()`), więc dwa uruchomienia w jeden dzień dają jeden wiersz. Wartość od dostawcy, która po zaokrągleniu do 9 miejsc jest zerem albo przepełnia kolumnę, jest pomijana, a błąd zapisu jednego waloru (savepoint) nie cofa pozostałych. Żądania z więcej niż 9 miejscami po przecinku → 422.
- **Daty z przyszłości** w ręcznej cenie i ręcznym kursie → 400 `DATE_IN_FUTURE`; `from` > `to` albo za długi forward-fill → 400 `INVALID_DATE_RANGE`; waluta ceny ≠ waluta waloru → 400 `PRICE_CURRENCY_MISMATCH`.
- **Utworzenie z dostawcy:** klasa z `quoteType` (ETF→„ETF”, CRYPTOCURRENCY/CRYPTO→„Crypto”, MUTUALFUND→„Mutual Fund”, inaczej „Stock”), waluta z notowania (domyślnie USD); obie tworzone, gdy ich brak. Cena = pierwsza niezerowa z `currentPrice`, `regularMarketPrice`, `previousClose`.
- **Dane rynkowe są zależnością zewnętrzną:** błąd pobrania to sytuacja normalna. Wyszukiwanie przy awarii dostawcy zwraca pustą listę. Odświeżanie cen (`refresh_asset_prices`) i kursów (`refresh_currency_rates`, waluta bazowa = 1) jest best-effort per pozycja: błąd jednego tickera/waluty jest logowany i pomijany, nie przerywa reszty. Pobranie następuje przed transakcją.

### Kody błędów

| Status | `code` |
|---|---|
| 404 | `ASSET_NOT_FOUND`, `ASSET_CLASS_NOT_FOUND`, `CURRENCY_NOT_FOUND`, `ASSET_NOT_FOUND_ON_PROVIDER`, `PRICE_NOT_FOUND`, `RATE_MISSING` |
| 400 | `ASSET_CLASS_NOT_FOUND`, `CURRENCY_NOT_FOUND`, `BASE_CURRENCY_NOT_FOUND` (referencja w treści), `INVALID_DATE_RANGE`, `DATE_IN_FUTURE`, `PRICE_CURRENCY_MISMATCH` |
| 403 | `ADMIN_REQUIRED` |
| 409 | `ASSET_ALREADY_EXISTS` (ticker albo ISIN), `ASSET_CLASS_ALREADY_EXISTS`, `CURRENCY_ALREADY_EXISTS`, `ASSET_HAS_HISTORY`, `ASSET_ARCHIVED`, `ASSET_CLASS_IN_USE`, `CURRENCY_IN_USE` |
| 502 | `MARKET_DATA_UNAVAILABLE` (awaria dostawcy przy imporcie) |

## 4. Dane rynkowe — port i adapter

Wzorem waterworks (`core/audit.py` jako port, `infrastructure/storage/` jako adapter):

| Element | Plik | Rola |
|---|---|---|
| Port | `core/market_data.py` | `Quote` (dataclass), `MarketDataProvider` (`Protocol`: `fetch_quote`, `fetch_fx_rate`, `fetch_close_history` — `end` wyłączny), `MarketDataUnavailableError` (502) |
| Adapter | `infrastructure/market_data/yahoo.py` | `YahooFinanceProvider` — jedyne miejsce importu `yfinance`; każdy wyjątek biblioteki/sieci → `MarketDataUnavailableError`; liczby przez `Decimal(str(x))` |
| Wybór adaptera | `assets/wiring.py` → `build_market_data_provider()` | Testy podmieniają tę funkcję (lub wstrzykują fałszywy provider), więc żaden test nie dotyka sieci |

`MarketDataService` zależy wyłącznie od portu. Dla `portfolios` wystawia `close_history(ticker, start, end)` i `current_price(ticker)` (komunikacja między modułami przez serwisy — [ADR-0006](../adr/0006-cross-module-wylacznie-przez-serwisy.md)). Adapter Yahoo wywołuje `history(..., auto_adjust=False)` i **cofa korektę splitów**: `Close` w Yahoo jest dopasowany do splitów nawet przy `auto_adjust=False` (po splicie 10:1 wszystkie wcześniejsze zamknięcia są dziesięć razy niższe niż notowania z tamtego dnia; zweryfikowane na DNP.WA i NVDA, `yfinance` 1.3.0). `fetch_close_history` mnoży każde zamknięcie przez splity późniejsze niż jego dzień (z `Ticker.splits`, a gdy ich brak — z kolumny `Stock Splits` okna), więc zwraca ceny **w jednostkach danego dnia**, zgodnie z ADR-0015 („nieskorygowane”). Takie ceny nie zmieniają się, gdy później dojdzie kolejny split. Dywidendy nie korygują ceny (korekta liczyłaby wypłatę drugi raz obok operacji dywidendy). `backfill_closes(assets, start, end)` zapisuje tę historię w `assets_price` (źródło `yahoo`, `is_synthetic=false`, idempotentnie — ponowny zapis dnia nadpisuje cenę) — używa jej `portfolios` przy budowie dni TWR ([`05_portfolios_module.md` §6.1](./05_portfolios_module.md#61-zwrot-portfela-twr-i-snapshoty-dzienne)). Wiersze zapisane przed tą zmianą mają ceny skorygowane o splity; nadpisuje je kolejna budowa dni portfela, dla zakresu tej budowy. Dokładność danych dostawcy względem giełdy nie jest weryfikowana.

## 5. Serwisy (API publiczne)

| Serwis | Metody |
|---|---|
| `AssetClassService` | `list_asset_classes`, `get_by_id`, `find_by_id`, `create`, `update`, `delete`; rdzeń bez commitu: `get_or_create_by_name` |
| `CurrencyService` | `list_currencies`, `get_by_id`, `find_by_id`, `create`, `update`, `delete`; rdzeń bez commitu: `get_or_create_by_code` |
| `AssetService` | `list_assets`, `list_responses`, `get_by_id`, `get_detail`, `find_by_id`, `find_by_ticker`, `list_by_ids`, `accept_for_refresh`, `search_local_and_provider` (read model), `to_response`, `to_detail`, `create`, `update`, `delete`, `archive`, `unarchive`, `create_from_provider`; rdzeń bez commitu: `get_or_create_by_ticker(ticker, *, asset_class_name, fallback_currency_id)` |
| `PriceService` | `find_close(asset_id, as_of)`, `latest_quotes`, `series`, `set_manual_price`, `delete_manual_price`; rdzenie bez commitu: `record_closes`, `record_manual_price_today`, `sync_current_price` |
| `FxRateService` | `get_rate`, `history`, `set_manual_rate`; rdzenie bez commitu: `record_rate`, `record_manual_rate_to_base`, `sync_cached_rate` |
| `MarketDataService` | `search`, `get_quote`, `current_price`, `close_history`, `refresh_asset_prices`, `backfill_closes`, `refresh_currency_rates`, `data_status` |

Rdzenie bez commitu ([ADR-0008](../adr/0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md)) służą `portfolios` przy rejestrowaniu operacji na nowym tickerze oraz serwisom `assets` między sobą — transakcję trzyma orkiestrator.

## 6. Układ i operacje poza HTTP

```text
assets/
├─ api/{asset_classes,assets,currencies,fx_rates,prices}.py   # __init__.py: wspólny `router` dla main.py
├─ domain/{identifiers,pricing}.py                            # czyste reguły: ISIN/MIC, pierwszeństwo źródeł, świeżość
├─ services/{asset_classes,assets,currencies,fx_rates,prices,market_data}.py
├─ repositories/{asset_classes,assets,currencies,fx_rates,prices}.py
├─ schemas/{asset_classes,assets,currencies,fx_rates,prices}.py
├─ models/{asset_classes,assets,currencies,fx_rates,prices}.py
├─ constants.py  exceptions.py  dependencies.py  wiring.py  entrypoints.py
└─ tests/{unit,integration}/  fakes.py (FakeMarketDataProvider)
```

`domain/` ma wyłącznie bibliotekę standardową i nie czyta zegara (`tests/unit/test_domain_purity.py`).

`entrypoints.py` ([ADR-0002](../adr/0002-sesja-poza-zadaniem-entrypointy-i-wiring.md)) — jedyne miejsce modułu otwierające sesję poza żądaniem; nie commituje. Funkcje przyjmują `SessionScope` (jak w ADR-0017), a błąd jednego waloru lub waluty nie przerywa reszty — liczy się w `failed`:

| Funkcja | Działanie |
|---|---|
| `refresh_prices(asset_ids=None, scope=session_scope)` | dzisiejsza cena z dostawcy dla podanych walorów albo wszystkich aktywnych (zarchiwizowane są pomijane); zwraca `RefreshResult(ok, failed)` |
| `refresh_fx_rates(scope=session_scope)` | dzisiejszy kurs każdej waluty do USD; zwraca `RefreshResult(ok, failed)` |

Harmonogramu ani CLI jeszcze nie ma — `refresh_prices` i `refresh_fx_rates` wołają dziś ręcznie `POST /assets/refresh-prices` i `POST /portfolios/positions/refresh`.

## 7. Stan vs cel

| Element | Stan | Cel | Krok |
|---|---|---|---|
| Struktura, wiring, błędy z `code`, `transaction()`, `find_`/`get_`, testy `unit/` + `integration/` | zgodne z celem | — | R-04 (domknięty) |
| Historia cen i kursów (`assets_price`, `assets_fx_rate`), cache `current_price`/`exchange_rate` | zrobione; `current_price`/`exchange_rate` wciąż czytane przez `portfolios` | `portfolios` czyta cenę i kurs z historii na dzień wyceny (wykresy w czasie) | — |
| Identyfikacja waloru (`isin`, `mic`, `country`, `asset_type`), archiwizacja, `data-status` | zrobione | — | — |
| Odświeżanie w tle | funkcje w `entrypoints.py`; `POST /portfolios/positions/refresh` wciąż woła dostawcę synchronicznie | harmonogram/CLI; usunięcie synchronicznego odświeżania z `portfolios` | — |
| Rejestr dostawców (`assets_listing`, priorytet per walor), NBP, Stooq | brak; jedyny dostawca to Yahoo, ranga stała | tabela `assets_listing` i adaptery | — |
| Dziennik zmian historii (`assets_price_change`), tagi, lista obserwowanych, serie stóp, obligacje, kalendarz sesji | brak | wg planu | — |
| Własność danych referencyjnych | `ADMIN_EMAILS` (`get_current_admin`) | flaga `is_owner` w `users` | — |
| `POST /assets/` i `POST /assets/create-from-yahoo` | otwarte dla każdego zalogowanego | wg decyzji o własności danych | — |

Ograniczenia znane: usunięcie jedynej ceny zostawia w cache ostatnią wartość; zapis cache nie blokuje wiersza waloru/waluty (równoległe odświeżenie i ręczna cena tego samego dnia mogą rozjechać cache do następnego zapisu); kurs odwrotny ma 9 miejsc po przecinku (mniej cyfr znaczących dla walut o dużym kursie, np. VND); a także: zmiana `currency_id` waloru z historią nie przelicza starych cen (wiersze zachowują starą walutę); `date.today()` serwera wyznacza dzień zapisu (strefa serwera, nie giełdy).
