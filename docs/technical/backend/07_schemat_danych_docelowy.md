---
id: be-target-schema-core
status: draft
type: mixed
scope: backend/target-schema
last_reviewed: 2026-10-03
---

# Jaki jest docelowy schemat danych modułów `core_data`, `assets` i `portfolios`?

> **Projekt docelowy (L2, draft).** Opisuje stan docelowy wynikający z roadmapy ([plan](../../plans/02_roadmapa_funkcjonalna.md)), nie stan kodu — ten opisują dokumenty modułów i kod. Obowiązuje po akceptacji ADR-ów, na które się powołuje.

Stan dzisiejszy: [`02_core_data_module.md`](./02_core_data_module.md), [`04_assets_module.md`](./04_assets_module.md), [`05_portfolios_module.md`](./05_portfolios_module.md). Kroki: [E0–E5](../../plans/03_roadmapa_etapy_E0-E5.md); decyzje D1–D16: [plan](../../plans/02_roadmapa_funkcjonalna.md). Oznaczenie **[propozycja]** = decyzja, której plan nie rozstrzyga (zebrane w „Otwarte punkty”). Pojęcia **Partia**, **Grupa portfeli**, **Przewalutowanie**, **Paczka importu** są proponowane (D3) i nie ma ich jeszcze w [`CONTEXT.md`](../../business/CONTEXT.md).

Dane startują od zera (seed albo import): schemat nie zawiera niczego służącego migracji istniejących wierszy.

## 1. Mapa: moduł → tabele → kroki planu

| Moduł | Tabele istniejące (zmiany) | Tabele nowe | Kroki |
|---|---|---|---|
| `core_data` | `users` (+`is_owner`) | `core_data_user_settings` | E0.6, E0.9, D14 |
| `assets` | `assets_asset`, `assets_currency`, `assets_assetclass` | `assets_price`, `assets_fx_rate`, `assets_listing`, `assets_watchlist`, `assets_price_change`, `assets_market_holiday` | E1.1–E1.9 |
| `portfolios` | `portfolios_portfolio`, `portfolios_operation`, `portfolios_position` | `portfolios_group`, `portfolios_group_member`, `portfolios_commission_rule`, `portfolios_cash_balance`, `portfolios_auto_flow`, `portfolios_lot`, `portfolios_lot_consumption`, `portfolios_daily`, `portfolios_position_daily`, `portfolios_market_cursor` | E2.0–E2.7, E3.1–E3.8 |
| `portfolios` (import, później) | — | `portfolios_import_batch`, `portfolios_import_row`, `portfolios_import_override` | E4 |
| wspólna (zadania w tle) | — | `job_run` | E1.4 |

Moduł `security` nie ma tabel (użytkownicy są w `core_data`).

## 2. Konwencje

| Zasada | Reguła |
|---|---|
| Nazwy | tabele `<moduł>_<nazwa>` w liczbie pojedynczej jak dziś (`assets_asset`, `portfolios_operation`); wyjątki: istniejące `users` oraz `job_run` (tabela infrastruktury, nie modułu) |
| Typy | kwoty `Numeric(18,2)`; saldo gotówki i cache Portfela `Numeric(18,3)`; ceny, ilości, kursy, współczynniki `Numeric(18,9)`; `twr_index` `Numeric(24,12)`; daty zdarzeń `Date`; momenty `DateTime(timezone=True)` ([ADR-0010](../adr/0010-decimal-i-precyzja-pieniedzy.md)) |
| Klucze | `id BigInteger` PK; FK jak w kodzie; `owner_id` → `users.id` w danych osobistych (portfel, grupa, lista obserwowanych, ustawienia); dane referencyjne (walory, ceny, kursy) są globalne w instancji (D14) |
| Dane pochodne | tabele przebudowywane z Operacji (`portfolios_lot`, `_lot_consumption`, `_cash_balance`, `_auto_flow`, `_daily`, `_position_daily`; `portfolios_position` aktualizowana w miejscu) **nie są celem FK z tabel z danymi użytkownika** — ich `id` nie są stabilne po przebudowie; odwołania idą do `portfolios_operation.id` (P3, D16) |
| Migracje | wyłącznie `alembic revision --autogenerate` ([ADR-0019](../adr/0019-migracje-danych-i-kolumny-dat.md)); nowy model w `infrastructure/sql/models_registry.py`; dane powstają przez seed albo import, nie przez migrację |
| Wartości wyliczeniowe | `String(n)`, nie `Enum` PG. `CheckConstraint` **tylko w nowych tabelach**; na istniejących (`portfolios_operation`, `portfolios_portfolio`, `assets_asset`) walidacja w serwisie — autogenerate nie generuje CHECK dla istniejących tabel |
| Granice modułów | FK między modułami wolno (tak jest dziś: `portfolios_operation.asset_id`); **odczyt i zapis wyłącznie przez serwisy** ([ADR-0006](../adr/0006-cross-module-wylacznie-przez-serwisy.md)) |

**Kierunki zależności** ([ADR-0013](../adr/0013-kierunki-zaleznosci-nowych-modulow.md)): `core_data` — brak (waluta w ustawieniach jako kod, nie FK); `security` → `core_data`; `assets` — brak; `portfolios` → `assets`, `core_data`. **Dług:** `core_data/services/users.py:7` importuje `security/services/password`, a `security/services/auth.py:2` importuje `core_data` — cykl do usunięcia (hash hasła do `core/` albo wstrzyknięcie).

## 3. Moduł `core_data`

### 3.1 `users` (istnieje: `core_data/models/user.py:7-13`)

| Kolumna | Dziś | Docelowo | Null | Domyślne | Źródło |
|---|---|---|---|---|---|
| `id`, `email` `String(254)` unikalny, `password_hash` `String(128)`, `is_active` | jak w kodzie | bez zmian | — | — | — |
| `is_owner` | brak | `Boolean` — właściciel instancji; tylko on zapisuje dane globalne (walory, ceny ręczne) | nie | `server_default false` | D14, E0.6 |

[propozycja] Właściciela ustawia komenda CLI `set-owner` z `core_data/entrypoints.py` ([ADR-0017](../adr/0017-zadania-w-tle-i-cli.md)), nie migracja. Do czasu jej wykonania zapisy globalne są odrzucane kodem `REFERENCE_DATA_OWNER_ONLY`.

### 3.2 `core_data_user_settings` (nowa, E0.9)

Jeden wiersz na użytkownika. Waluta i benchmark są zapisane jako **kod / id bez FK** — `core_data` nie zależy od `assets` (ADR-0006).

| Kolumna | Typ | Null | Domyślne | Klucz / ograniczenie | Źródło |
|---|---|---|---|---|---|
| `id` | `BigInteger` | nie | — | PK | — |
| `user_id` | `BigInteger` | nie | — | FK `users.id`, UNIQUE | E0.9 |
| `display_currency_code` | `String(3)` | nie | `'PLN'` | kod weryfikowany przy wycenie (ADR-0013 pkt 5), nie przy zapisie | E0.9, E3.4 |
| `stale_price_days` | `SmallInteger` | nie | `7` | `CHECK >= 1` | E0.9, E1.7 |
| `benchmark_asset_id` | `BigInteger` | tak | `NULL` | `id` Waloru-indeksu do porównania; bez FK, weryfikowane przy odczycie | E3.5 |
| `updated_at` | `DateTime(tz)` | nie | `now()` | — | — |

Wiersz tworzy się leniwie przy pierwszym `GET`. Strefa czasowa jest stała (Europe/Warsaw, ADR-0019) — brak kolumny `timezone` (E0.9).

## 4. Moduł `assets`

Instrumenty: akcje i ETF-y. Dostawca notowań: Yahoo Finance; kursy walut: NBP.

### 4.1 `assets_asset` (istnieje: `assets/models/assets.py:15-39`)

| Kolumna | Dziś | Docelowo | Null | Domyślne | Klucz | Źródło |
|---|---|---|---|---|---|---|
| `id`, `ticker` `String(20)` UNIQUE+index, `name` `String(100)`, `currency_id`, `sector` `String(100)`, `exchange` `String(50)`, `updated_at` | jak w kodzie | bez zmian; `exchange` zostaje tekstem wolnym (tylko wyświetlanie); `ticker` z sufiksem giełdy (`.WA`) jest symbolem u dostawcy (E0.5) | — | — | — | E1.3 |
| `asset_class_id` | NOT NULL FK `assets_assetclass` | bez zmian | nie | — | FK | E3.3 |
| `current_price` | `Numeric(18,9)` NOT NULL, default 0 | **pochodna** (cache ostatniej ceny z `assets_price`) — sekcja 6 | nie | `0` | — | E1.1, E1.4 |
| `isin` | brak | `String(12)` | tak | `NULL` | UNIQUE (wiele `NULL` dozwolone w PG) | E1.3 |
| `mic` | brak | `String(4)` — kod giełdy ISO 10383 | tak | `NULL` | — | E1.3 |
| `country` | brak | `String(2)` — ISO 3166 kraj emitenta | tak | `NULL` | — | E1.3, E3.3 |
| `asset_type` | brak | `String(10)`: `stock`, `etf` | nie | `'stock'` | zbiór walidowany w serwisie | E1.3 |
| `archived_at` | brak | `DateTime(tz)` — walor z historią cen lub operacjami tylko archiwizowany | tak | `NULL` | indeks częściowy `WHERE archived_at IS NULL` | D15 |

**[propozycja] `asset_type` ↔ `assets_assetclass`.** `asset_type` (system) opisuje rodzaj instrumentu i domyślną prowizję; Klasa waloru (`assets_assetclass`, CRUD w API — `name` `String(20)` UNIQUE, `asset_classes.py:15-16`) to otwarty słownik użytkownika do alokacji „wg Klas” (E3.3). Bez FK `asset_type` → Klasa: zamiana Klasy w stały enum łamie istniejące API i dane.

Indeksy: istniejące `ix_assets_asset_id`, `ix_assets_asset_ticker` (UNIQUE) — `ticker` zostaje globalnie unikalny **[propozycja]**; ten sam symbol na dwóch giełdach rozróżnia sufiks (`.WA`), nie klucz złożony. Nowe: `(isin)` UNIQUE. `assets_listing` (4.5) powstaje w E1.2 z istniejących tickerów.

### 4.2 `assets_currency` i `assets_assetclass` (istnieją)

| Tabela.kolumna | Dziś | Docelowo | Źródło |
|---|---|---|---|
| `assets_currency.exchange_rate` `Numeric(18,9)` NOT NULL default 1 | USD za 1 jednostkę waluty (`assets/services/market_data.py:109`) | **pochodna**, sekcja 6 | E0.1, E1.1 |
| `assets_currency.base_currency_id` FK self, nullable | tylko CRUD, nie używana w wycenie (`assets/services/currencies.py:44-67`) | **wygaszana**, sekcja 6 | E1.1 |

### 4.3 `assets_price` i `assets_price_change` (nowe, E1.1, D7, [ADR-0016](../adr/0016-snapshoty-dzienne-i-przebudowa.md))

Ceny zamknięcia **nieskorygowane** (splity są Operacjami).

| Kolumna | Typ | Null | Domyślne | Klucz / ograniczenie |
|---|---|---|---|---|
| `id` | `BigInteger` | nie | — | PK |
| `asset_id` | `BigInteger` | nie | — | FK `assets_asset.id` |
| `price_date` | `Date` | nie | — | — |
| `close` | `Numeric(18,9)` | nie | — | `CHECK > 0` |
| `currency_id` | `BigInteger` | nie | — | FK `assets_currency.id` (waluta notowania z dostawcy; zwykle = waluta waloru) |
| `source` | `String(20)` | nie | — | kod dostawcy (`yahoo`) albo `manual` (awaryjnie) |
| `is_synthetic` | `Boolean` | nie | `false` | wiersz wyliczony, nie notowanie |
| `fetched_at` | `DateTime(tz)` | nie | `now()` | — |

Ograniczenie: UNIQUE `(asset_id, price_date, source)`. Indeks: `(asset_id, price_date DESC)`.

**Pierwszeństwo źródeł [propozycja]:** `manual` zawsze wygrywa (E1.5); pozostałe wg `assets_listing.priority` rosnąco. Wiersze różnych źródeł współistnieją; `find_close(asset, date)` wybiera jeden i zwraca `source`, `is_synthetic`, flagę forward-fill (E1.1, E1.7). Forward-fill liczy się przy odczycie — nie zapisuje.

**Dziennik zmian `assets_price_change` (D7, E2.5, ADR-0016).** Serwis `assets` zapisuje wiersz **w tej samej transakcji** co korektę historii: zapis do `assets_price`/`assets_fx_rate` o dacie starszej od najnowszej w serii albo zmianę istniejącej wartości (dopisanie nowego dnia nie wpisuje nic). Znacznik jest per walor i per para walut; konsument (`portfolios`) czyta dziennik przez serwis `assets` po kursorze (5.9).

| Kolumna | Typ | Null | Uwagi |
|---|---|---|---|
| `id` | `BigInteger` | nie | PK; rosnący — kursor wskazuje ostatnio przeliczony |
| `kind` | `String(5)` | nie | `price` albo `fx`; `CHECK` |
| `asset_id` | `BigInteger` | tak | FK `assets_asset.id`; dla `price` |
| `from_currency_id`, `to_currency_id` | `BigInteger` | tak | FK `assets_currency.id`; dla `fx`; `CHECK` zgodny z `kind` |
| `changed_from` | `Date` | nie | data najstarszej zmiany |
| `recorded_at` | `DateTime(tz)` | nie | `now()` |

### 4.4 `assets_fx_rate` (nowa, E1.1, D5)

| Kolumna | Typ | Null | Domyślne | Klucz / ograniczenie |
|---|---|---|---|---|
| `id` | `BigInteger` | nie | — | PK |
| `from_currency_id` | `BigInteger` | nie | — | FK `assets_currency.id` |
| `to_currency_id` | `BigInteger` | nie | — | FK `assets_currency.id`, `CHECK from <> to` |
| `rate_date` | `Date` | nie | — | — |
| `rate` | `Numeric(18,9)` | nie | — | `CHECK > 0`; ile `to` za 1 `from` |
| `source` | `String(20)` | nie | — | `nbp`, `manual` |
| `is_synthetic` | `Boolean` | nie | `false` | — |
| `fetched_at` | `DateTime(tz)` | nie | `now()` | — |

UNIQUE `(from_currency_id, to_currency_id, rate_date, source)`; indeks `(from_currency_id, to_currency_id, rate_date DESC)`. **[propozycja]** Pary: przechowujemy tylko pary notowane u źródła (NBP: waluta → PLN). Serwis `assets` zwraca wyłącznie kursy bezpośrednie i odwrotne; **kurs krzyżowy składa `portfolios`** (`FxMapBuilder`): mapa `{(currency_id_z, currency_id_do): Decimal}` = rate[z]/rate[do]. Brak kursu w historii/cache = `RATE_MISSING`. Dwa kursy z D5: brokera = `portfolios_operation.fx_rate`, wyceny = ta tabela (dzienny).

### 4.5 `assets_listing` (nowa, E1.2)

Symbol waloru u dostawcy i priorytet źródeł.

| Kolumna | Typ | Null | Domyślne | Klucz / ograniczenie |
|---|---|---|---|---|
| `id` | `BigInteger` | nie | — | PK |
| `asset_id` | `BigInteger` | nie | — | FK `assets_asset.id` ON DELETE CASCADE |
| `provider` | `String(20)` | nie | — | kod adaptera |
| `symbol` | `String(40)` | nie | — | symbol u dostawcy (np. `PKN.WA`) |
| `priority` | `SmallInteger` | nie | `100` | mniejsza = ważniejsze; `manual` poza tabelą, zawsze pierwsze |
| `is_enabled` | `Boolean` | nie | `true` | wyłącznik awaryjny per walor |
| `last_success_at` / `last_error_at` | `DateTime(tz)` | tak | `NULL` | panel „Dane” (E1.7) |
| `last_error` | `String(200)` | tak | `NULL` | skrót błędu dostawcy, bez danych wrażliwych |

UNIQUE `(asset_id, provider)` i `(provider, symbol)`. CLI E1.2 tworzy wiersze z istniejących tickerów (np. `PKN.WA`).

### 4.6 `assets_watchlist` (nowa, E1.8)

Dane osobiste, więc `owner_id` (nie globalne jak walory).

| Kolumna | Typ | Null | Klucz |
|---|---|---|---|
| `id` | `BigInteger` | nie | PK |
| `owner_id` | `BigInteger` | nie | FK `users.id` |
| `asset_id` | `BigInteger` | nie | FK `assets_asset.id` |
| `note` | `String(200)` | tak | — |
| `added_at` | `DateTime(tz)` | nie (`now()`) | — |

UNIQUE `(owner_id, asset_id)`.

### 4.7 `assets_market_holiday` (nowa, E1.9)

Dni wolne giełd — kalendarz sesji (wypełnianie cen, flaga `stale`). Dane globalne (D14); ładowane komendą CLI. PK `(mic, holiday_date)`: `mic` `String(4)` (jak `assets_asset.mic`), `holiday_date` `Date`, `name` `String(100)` null. Weekendy wynikają z kodu, nie z tabeli.

## 5. Moduł `portfolios`

### 5.1 `portfolios_portfolio` (istnieje: `models/portfolio.py:26-67`)

**Portfel = jeden rachunek** (ADR biznesowy 0001). `account_type` i `broker` są wyłącznie etykietami informacyjnymi — nie zmieniają zasad księgi.

| Kolumna | Dziś | Docelowo | Null | Domyślne | Klucz | Źródło |
|---|---|---|---|---|---|---|
| `id`, `owner_id` FK, `name` `String(100)`, `base_currency_id` FK, `is_active`, `created_at`, `updated_at` | jak w kodzie; UNIQUE `(owner_id, name)` (`unique_portfolio_per_user`) | bez zmian; zmiana `base_currency_id` przy istniejących Operacjach: 409 `PORTFOLIO_CURRENCY_LOCKED` | — | — | — | E0.8 |
| `cash_balance` | `Numeric(18,3)` NOT NULL | **pochodna** (cache salda w walucie bazowej Portfela) — sekcja 6 | nie | `0` | — | E2.2 |
| `total_deposited` | `Numeric(18,3)` NOT NULL | **pochodna** — sekcja 6 | nie | `0` | — | E2.2 |
| `account_type` | brak | `String(30)` — etykieta (np. `regular`, `ike`, `ikze`), bez walidacji zbioru | nie | `'regular'` | — | E2.1, D1 |
| `broker` | brak | `String(60)` — etykieta | tak | `NULL` | — | E2.1 |
| `auto_funding` | brak | `Boolean` — niedobór gotówki przy zakupie = wirtualna wpłata (5.6) | nie | `false` | — | E2.2b |
| `dirty_from` | brak | `Date` — wiersze snapshotów `day ≥ dirty_from` są nieaktualne; `NULL` = aktualne (ADR-0016) | tak | `NULL` | — | E2.0, E2.5 |

Indeksy: UNIQUE `(owner_id, name)` bez zmian; `(owner_id, is_active)`.

### 5.2 `portfolios_commission_rule` (nowa, E2.1)

Domyślna prowizja per typ waloru (% + minimum) podpowiadana w formularzu; nie jest księgowana.

| Kolumna | Typ | Null | Klucz / uwagi |
|---|---|---|---|
| `id` | `BigInteger` | nie | PK |
| `portfolio_id` | `BigInteger` | nie | FK CASCADE |
| `asset_type` | `String(10)` | tak | `NULL` = wszystkie typy; wartość z `assets_asset.asset_type` |
| `rate_pct` | `Numeric(9,6)` | nie | `CHECK >= 0` |
| `min_fee` | `Numeric(18,2)` | nie (domyślnie `0`) | — |
| `currency_id` | `BigInteger` | tak | FK `assets_currency.id`; `NULL` = waluta Portfela |

UNIQUE `(portfolio_id, asset_type)`.

### 5.3 `portfolios_group` + `portfolios_group_member` (nowe, E2.1, E3.1)

**Grupa portfeli** agreguje bez własnych Operacji (D1).

| Tabela | Kolumny | Ograniczenia |
|---|---|---|
| `portfolios_group` | `id` PK; `owner_id` FK `users.id`; `name` `String(100)`; `currency_code` `String(3)` null (`NULL` = waluta wyświetlania z ustawień); `created_at` | UNIQUE `(owner_id, name)` |
| `portfolios_group_member` | `group_id` FK CASCADE; `portfolio_id` FK CASCADE | PK `(group_id, portfolio_id)`; indeks `(portfolio_id)`; Portfel może być w wielu Grupach; serwis wymusza jednego właściciela |

### 5.4 `portfolios_operation` (istnieje: `models/operation.py:31-69`)

Kolumny istniejące: `id`; `portfolio_id` FK NOT NULL; `asset_id` FK null; `operation_type` `String(20)`; `quantity`, `price` `(18,9)` default 0; `amount` `(18,2)` null; `fee` `(18,2)` default 0; `fx_rate` `(18,9)` default 1 (broker: waluta waloru → waluta Portfela, `ledger.py:170`); `notes` `Text` null; `operation_date` `DateTime(tz)` NOT NULL + index; `created_at`. Wszystkie zostają. Dodawane (D9):

| Kolumna | Typ | Null | Domyślne | Znaczenie | Źródło |
|---|---|---|---|---|---|
| `operation_day` | `Date` | nie | — | **dzień operacji w Europe/Warsaw** wyliczany z `operation_date`; kolejność i snapshoty liczone od niego | D13, E2.0 |
| `sequence` | `Integer` | nie | `0` | numer w obrębie (Portfel, `operation_day`), nadawany automatycznie przy zapisie | D9, D13, E2.0 |
| `currency_id` | `BigInteger` FK `assets_currency.id` | nie | — | waluta `price`/`amount`/`fee`; API wypełnia walutą waloru, gdy klient jej nie poda; wpłata/wypłata/odsetki/opłata bez waloru — walutą bazową Portfela | D9, E2.2 |
| `counter_amount` / `counter_currency_id` | `Numeric(18,2)` / `BigInteger` FK | tak | `NULL` | noga **przychodząca** Przewalutowania; `amount` = noga wychodząca w `currency_id` | D9 |
| `ratio` | `Numeric(18,9)` | tak | `NULL` | przelicznik nowe:stare (split); serwis wymaga `> 0` | D9, E8.1 |
| `import_batch_id` | `BigInteger` FK | tak | `NULL` | paczka importu (5.10) | D9, E4.1 |
| `external_ref` | `String(120)` | tak | `NULL` | identyfikator z pliku brokera (deduplikacja) | D9, E4.1 |
| `edited_at` | `DateTime(tz)` | tak | `NULL` | ręczna edycja po zapisie; cofnięcie paczki jest blokowane dla edytowanych (D15) | D15, E4.1 |

**Klucz porządku księgi: `(operation_day, sequence, id)`** — jedyny; zastępuje `(operation_date, created_at, id)` z `repositories/operations.py:53-57`.

**Wartości `operation_type`** (dziś: `buy`, `sell`, `deposit`, `withdrawal`, `dividend` — `domain/enums.py:9-14`; kolumna `String(20)` wystarcza; walidacja w serwisie). **[propozycja]** nowe: `interest` (odsetki od gotówki), `fee` (opłata), `fx_exchange` (**Przewalutowanie**), `split`. Źródła: E2.2, E2.3, E8.1.

**Gotówka i waluty.** Dywidenda i odsetki trafiają na saldo w walucie wypłaty (`currency_id`; np. MSFT w USD → gotówka USD). Przewalutowanie to jeden wiersz: `amount` w `currency_id` (noga wychodząca), `counter_amount` w `counter_currency_id`; prowizja (`fee`) jest w walucie wychodzącej. Dwa kursy: `fx_rate` Operacji (brokera) i dzienny z `assets_fx_rate` (wyceny).

**Split** nie zmienia kosztu łącznego Partii (5.5): `ratio` przelicza ilość i cenę jednostkową.

**Indeksy** (autogenerate): UNIQUE częściowy `(portfolio_id, external_ref) WHERE external_ref IS NOT NULL`; `(portfolio_id, operation_day, sequence, id)` (lista i przebudowa, E2.7); `(asset_id, operation_day)`; `(import_batch_id) WHERE import_batch_id IS NOT NULL`. Istniejący `ix_operation_portfolio_date` zostaje. Model płaski: [ADR-0020](../adr/0020-plaski-model-operacji.md).

**`operation_day` vs `operation_date` (D13) [propozycja]:** `operation_date` zostaje `timestamptz` (chwila, z godziną z UI) — typ **nie jest zmieniany**; `operation_day` to kolumna `Date` wyliczana przy zapisie jako `operation_date AT TIME ZONE 'Europe/Warsaw'`. Od tej chwili logika (`metrics.py:74,148` liczy dziś dzień w UTC) czyta `operation_day` ([ADR biznesowy 0005](../../business/adr/0005-daty-operacji-dzien-i-kolejnosc.md)).

### 5.5 `portfolios_position` (istnieje: `models/position.py:26-70`) i `portfolios_lot`

`portfolios_position` — kolumny bez zmian: `portfolio_id`, `asset_id`, `quantity` `(18,9)`, `average_buy_price` `(18,9)`, `average_fx_rate` `(18,9)`, `total_fees` `(18,2)`, `total_dividends` `(18,2)`, `opened_at`, `updated_at`; UNIQUE `unique_position_per_portfolio (portfolio_id, asset_id)`. Przebudowa aktualizuje Pozycje **w miejscu** (zachowuje `opened_at`). Status docelowy: **agregat pochodny Partii** (suma `quantity_open`), z `average_buy_price` wyłącznie do prezentacji (D2). Wycena kosztu czyta Partie, nie średnią (dziś `quantity × average_buy_price` — `domain/valuation.py:53`).

**`portfolios_lot` (nowa, E2.4) — Partia, dane pochodne.** FIFO w obrębie Portfela = rachunku (ADR biznesowy 0002).

| Kolumna | Typ | Null | Domyślne | Uwagi |
|---|---|---|---|---|
| `id` | `BigInteger` | nie | — | PK (niestabilny po przebudowie) |
| `portfolio_id` | `BigInteger` | nie | — | FK `portfolios_portfolio.id` CASCADE |
| `asset_id` | `BigInteger` | nie | — | FK `assets_asset.id` |
| `open_operation_id` | `BigInteger` | nie | — | FK `portfolios_operation.id` CASCADE; zakup, który otworzył Partię — klucz biznesowy |
| `split_ratio` | `Numeric(18,9)` | nie | `1` | skumulowany przelicznik splitów zastosowanych do Partii (E8.1) |
| `acquired_on` | `Date` | nie | — | data nabycia (`operation_day` zakupu), niezmienna przy splicie |
| `quantity_initial` / `quantity_open` / `unit_price` | `Numeric(18,9)` | nie | — | `CHECK 0 <= quantity_open <= quantity_initial`; cena w walucie waloru, bez prowizji, po splicie przeliczona przy stałym koszcie |
| `cost_local` / `cost_base` | `Numeric(18,2)` | nie | — | koszt nabycia pozostałej ilości z prowizją: w walucie waloru / w walucie Portfela po kursie brokera |
| `fx_rate` | `Numeric(18,9)` | nie | `1` | kopia kursu brokera z Operacji (audytowalność kosztu) |
| `closed_on` | `Date` | tak | `NULL` | data wyczerpania Partii |

Split **nie tworzy** Operacji otwierającej: Partia zostaje, zmienia się `split_ratio`, ilość i cena jednostkowa przy stałym koszcie i dacie nabycia. UNIQUE `(open_operation_id)`; indeks kolejki FIFO `(portfolio_id, asset_id, acquired_on, open_operation_id) WHERE quantity_open > 0`.

### 5.6 `portfolios_lot_consumption` (nowa, E2.4) — dane pochodne

| Kolumna | Typ | Null | Uwagi |
|---|---|---|---|
| `id` | `BigInteger` | nie | PK |
| `lot_id` | `BigInteger` | nie | FK `portfolios_lot.id` CASCADE |
| `close_operation_id` | `BigInteger` | nie | FK `portfolios_operation.id` CASCADE (sprzedaż) |
| `closed_on` | `Date` | nie | dzień zamknięcia (`operation_day`) |
| `quantity` | `Numeric(18,9)` | nie | `CHECK > 0` |
| `proceeds_local`, `cost_local`, `fee_local` | `Numeric(18,2)` | nie | w walucie waloru; `proceeds` = przychód **brutto**; prowizja sprzedaży rozłożona proporcjonalnie na zużyte Partie, reszta zaokrąglenia kosztu do `(18,2)` trafia do ostatniego zużycia (E2.4) |
| `proceeds_base`, `cost_base` | `Numeric(18,2)` | nie | w walucie Portfela (kurs brokera) |

UNIQUE `(lot_id, close_operation_id)`; indeksy `(close_operation_id)`, `(closed_on)`. Zysk zrealizowany = `proceeds − cost − fee` (E2.4); test złoty: [metodyka](../../research/05_metodyka_metryk.md).

### 5.7 `portfolios_cash_balance` + `portfolios_auto_flow` (nowe, E2.2, E2.2b) — dane pochodne

| Tabela | Kolumny | Ograniczenia |
|---|---|---|
| `portfolios_cash_balance` | `id` PK; `portfolio_id` FK CASCADE; `currency_id` FK; `balance` `Numeric(18,3)` nie null (domyślnie `0`) | UNIQUE `(portfolio_id, currency_id)`; saldo ujemne odrzuca księga (`INSUFFICIENT_CASH`), nie `CHECK` |
| `portfolios_auto_flow` | `id` PK; `portfolio_id` FK CASCADE; `trigger_operation_id` FK `portfolios_operation.id` CASCADE; `currency_id` FK; `amount` `Numeric(18,2)` (wpłata); `flow_day` `Date`; `sequence` `Integer` (miejsce w kolejności dnia) | indeksy `(portfolio_id, flow_day, sequence)`, `(trigger_operation_id)` |

**[propozycja] Automatyczne wpłaty (E2.2b, flaga `auto_funding`, domyślnie wyłączona) są pochodne, nie wierszami `portfolios_operation`.** Niedobór gotówki przy **zakupie** to wirtualna wpłata w walucie zakupu; dywidendy i odsetki nie są wirtualną wypłatą — zostają na saldzie. Powód: P3 — Operacje to źródło prawdy; wiersz wygenerowany przez księgę musiałby być kasowany i odtwarzany przy edycji operacji wyzwalającej. Przebudowa buduje `portfolios_auto_flow` od zera; TWR/XIRR czytają go jako przepływy zewnętrzne. Wymaga ADR, bo zmienia definicję „przepływu zewnętrznego”.

### 5.8 `portfolios_daily` + `portfolios_position_daily` (nowe, E2.5, D7) — snapshoty dzienne, pochodne

**`portfolios_daily`.** PK `(portfolio_id, day)`; `portfolio_id` FK CASCADE; `day` `Date` (dzień w strefie z D13). Wiersze `day ≥ portfolios_portfolio.dirty_from` są nieaktualne (5.1). Szereg po dniach kalendarzowych; dni bez sesji mają przeniesioną wycenę. Przebudowa per Portfel: synchronicznie do progu, powyżej w tle (ADR-0016).

| Kolumna | Typ | Null | Uwagi |
|---|---|---|---|
| `value`, `cash`, `positions_value`, `income`, `fees` | `Numeric(18,2)` | nie | w walucie Portfela, po kursach wyceny dnia; dochody (dywidendy, odsetki) i opłaty dnia |
| `ext_in`, `ext_out` | `Numeric(18,2)` | nie | przepływy zewnętrzne dnia (wpłaty, wypłaty, `portfolios_auto_flow`) |
| `r_day` | `Numeric(18,12)` | tak | stopa dnia; `NULL` przy wartości początkowej 0 |
| `twr_index` | `Numeric(24,12)` | nie | `Π(1+r)`, `Decimal` (D7, D11) |
| `cum_ext_in`, `cum_ext_out` | `Numeric(18,2)` | nie | skumulowane przepływy — zysk okresu w O(1) ([metodyka](../../research/05_metodyka_metryk.md)) |
| `data_quality` | `String(12)` | nie | `ok`, `stale`, `synthetic`, `missing` (brak ceny przy niezerowej Pozycji — nie wyceniamy cicho na zero) |

**`portfolios_position_daily`.** PK `(portfolio_id, asset_id, day)`; FK CASCADE na `portfolios_portfolio`, FK `assets_asset`.

| Kolumna | Typ | Null | Uwagi |
|---|---|---|---|
| `quantity` | `Numeric(18,9)` | nie | stan na koniec dnia |
| `price_local` | `Numeric(18,9)` | tak | cena zamknięcia w walucie waloru (z `find_close`) |
| `fx` | `Numeric(18,9)` | nie | kurs wyceny waluta waloru → waluta Portfela tego dnia |
| `mv_local`, `mv_base` | `Numeric(18,2)` | tak | `quantity × price_local` / `mv_local × fx` |
| `cost_base`, `flow_in`, `flow_out` | `Numeric(18,2)` | nie | koszt otwartych Partii (E2.4); przepływy waloru dnia (zakup/sprzedaż) |
| `r_day`, `twr_index` | `Numeric(18,12)`, `Numeric(24,12)` | tak / nie | stopa i indeks waloru |
| `is_stale`, `is_synthetic` | `Boolean` | nie | z `find_close` |

Indeks: `(asset_id, day)` (alokacje, wykres waloru E3.8). Rozmiar [wniosek]: 30 walorów × 3 650 dni ≈ 110 tys. wierszy na Portfel — dlatego przebudowa zapisuje partiami.

### 5.9 `portfolios_market_cursor` (nowa, E2.5)

Jeden wiersz (`id` PK z `CHECK id = 1`, `last_change_id` `BigInteger` — ostatni przeliczony wiersz `assets_price_change`). `rebuild_dirty` czyta zmiany po kursorze przez serwis `assets`, ustawia `dirty_from`, przebudowuje i przesuwa kursor w jednej transakcji (ADR-0016).

### 5.10 Import XTB: `portfolios_import_*` (nowe, E4) — **później**

Implementacja po przeglądzie reszty; najpierw tylko adapter XTB, kolejne źródła później. Kształt i potok: [ADR-0018](../adr/0018-architektura-importu.md) (port parsera w `core/import_parser.py`, adapter w `infrastructure/`, rozpoznanie waloru przez serwis `assets`). Zatwierdzenie = rdzeń `record_many` bez commitu + jedna przebudowa ([ADR-0008](../adr/0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md); dziś `_record` commituje — `portfolios/services/operations.py:99-100`).

| Tabela | Kolumny | Ograniczenia |
|---|---|---|
| `portfolios_import_batch` — **Paczka importu** | `id` PK; `owner_id` FK `users.id`; `portfolio_id` FK `portfolios_portfolio.id`; `parser_id` `String(40)` (`xtb`); `filename` `String(255)`; `sha256` `String(64)`; `size_bytes` `Integer`; `content` `LargeBinary` deferred; `status` `String(10)` (`draft`, `committed`, `reverted`); `created_at`, `committed_at`, `reverted_at` | UNIQUE `(owner_id, sha256)` — ponowny plik zwraca istniejącą Paczkę; `CHECK size_bytes <= 10485760` **[propozycja]**; `Operation.import_batch_id` → `ON DELETE RESTRICT`; indeks `(owner_id, status)` |
| `portfolios_import_row` | `id` PK; `batch_id` FK CASCADE; `row_no` `Integer`; `raw_label` `String(200)`; `raw_cells`, `payload` `JSONB`; `row_status` `String(12)` (`ok`, `duplicate`, `unrecognized`, `error`, `skip`); `error_code`, `error_detail`; `dedup_key`, `match_key` `String(120)`; `asset_id` FK null; `isin`, `ticker`; `operation_id` FK `portfolios_operation.id` SET NULL | UNIQUE `(batch_id, row_no)`; indeks `(batch_id, row_status)` |
| `portfolios_import_override` | `id` PK; `portfolio_id` FK CASCADE; `parser_id`; `match_key`; `field` (biała lista, walidacja w serwisie); `value` `String(255)`; `updated_at` | UNIQUE `(portfolio_id, parser_id, match_key, field)` |

Cofnięcie (D15): serwis usuwa Operacje Paczki, chyba że któraś ma `edited_at IS NOT NULL` — wtedy 409 `IMPORT_BATCH_HAS_EDITS`; po cofnięciu `status='reverted'`. Nadpisania przeżywają cofnięcie (wiedza użytkownika). Zaksięgowana Operacja nigdy nie jest nadpisywana — różnice pokazuje podgląd (`CHANGED_AT_SOURCE`).

## 6. Kolumny pochodne i wygaszane

| Kolumna | Decyzja [propozycja] | Uzasadnienie |
|---|---|---|
| `portfolios_portfolio.cash_balance` | zostaje jako **cache salda w walucie bazowej Portfela** (linia `portfolios_cash_balance` dla `base_currency_id`); pole API `cash_balance` bez zmiany; sumę wielowalutową liczy serwis kursem wyceny | API (`schemas/portfolios.py`) i `LedgerState.cash_balance` (`ledger.py:105`) to jeden `Decimal`; usunięcie łamie frontend. Usunięcie po E3.4 osobnym ADR-em |
| `portfolios_portfolio.total_deposited` | zostaje jako cache: suma wpłat − wypłat (`deposit`/`withdrawal`, `portfolios_auto_flow`) przeliczona **kursem Operacji** na walutę Portfela | w wielu walutach „suma wpłat” wymaga jednego kursu — kurs z momentu wpłaty jest jedyną definicją niezależną od dnia wyceny (reguła do potwierdzenia w ADR D4) |
| `assets_asset.current_price` | cache ostatniej ceny z `assets_price`; zapisuje go serwis `assets` w tej samej transakcji co zapis ceny ([ADR-0015](../adr/0015-historia-cen-i-kursow.md)); nowe odczyty wyceny idą do `find_close`; usunięcie po E2.5 | ścieżka żądania nie woła dostawcy (E1.4), a bieżąca cena bez historii nie spełnia D7 |
| `assets_currency.exchange_rate` | cache kursu względem USD do czasu E1.1 (E0.1 liczy kurs krzyżowy z niego, `domain/valuation.py:55-57`); potem z `assets_fx_rate`; nowa waluta **bez kursu** nie dostaje domyślnego 1 — kolumna staje się `nullable`, brak kursu → `RATE_MISSING` | domyślne `1` zafałszowuje wycenę po cichu |
| `assets_currency.base_currency_id` | wygasza się: żaden kod wyceny jej nie czyta (tylko CRUD `currencies.py:44-67`); usunięcie kolumny wymaga zgody właściciela | historia kursów w `assets_fx_rate` zastępuje relację |

## 7. Zadania w tle: `job_run`

Implementacja zadań jest wspólna: CLI `python -m app.cli <zadanie>` i **nadrabianie zaległości po wybudzeniu** (Render usypia backend) wołają te same funkcje z `entrypoints.py` ([ADR-0017](../adr/0017-zadania-w-tle-i-cli.md)). Pierwsze żądanie dnia rejestruje w `BackgroundTasks` odświeżenie cen i kursów oraz przebudowę zaległych dni; zadania są idempotentne.

**`job_run`** (nowa, infrastruktura) — jeden wiersz na zadanie; służy jako rejestr ostatniego przebiegu **i** blokada przed równoległym przebiegiem.

| Kolumna | Typ | Null | Uwagi |
|---|---|---|---|
| `job_name` | `String(40)` | nie | PK (`refresh-prices`, `refresh-fx`, `rebuild-dirty`) |
| `last_started_at` / `last_finished_at` | `DateTime(tz)` | nie / tak | — |
| `last_status` | `String(10)` | tak | `ok`, `failed`, `partial` |
| `last_ok_day` | `Date` | tak | ostatni dzień (Europe/Warsaw), dla którego przebieg się powiódł — warunek „zaległość” |
| `last_error` | `String(200)` | tak | skrót błędu, bez sekretów |

**Blokada:** blokadą jest wyłącznie wiersz w transakcji; `last_status` i `last_started_at` są informacyjne, a przebieg bez `last_finished_at` po 30 minutach uznaje się za przerwany. Przebieg otwiera transakcję i wykonuje `SELECT … FROM job_run WHERE job_name = :n FOR UPDATE SKIP LOCKED`; brak wiersza w wyniku = inny przebieg trwa, przebieg się kończy bez pracy. Wiersze tworzy seed (`INSERT … ON CONFLICT DO NOTHING`). Pooler transakcyjny Supabase nie dopuszcza blokad sesyjnych ani `pg_advisory_lock` na poziomie sesji — blokada wierszowa w transakcji jest dozwolona. Nie używamy `flock`. Zewnętrzny harmonogram (jedna linia cron) jest opcjonalny.

## 8. Konflikty z istniejącym kodem

| # | Kod dziś | Konflikt | Rozwiązanie |
|---|---|---|---|
| 1 | `LedgerState.cash_balance` jeden `Decimal` (`ledger.py:105`); `valuation.py:53` koszt = ilość × średnia | gotówka per waluta, wycena z Partii | stan księgi = mapa `waluta → saldo`, `HoldingLike` czyta Partie (przepisać `test_valuation.py`); kolumny Portfela jako cache (sekcja 6) |
| 2 | `OperationService._record` commituje (`operations.py:99-100`) | import potrzebuje `record_many` bez commitu | rdzeń bez commitu ([ADR-0008](../adr/0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md)) |

## Otwarte punkty

| # | Punkt | Blokuje |
|---|---|---|
| 1 | Zatwierdzenie ADR: D1, D2, D4, D9, D13, D15, D16 (biznesowe i techniczne) — tabele z tego dokumentu są szkicem do ich czasu | E2.1–E2.4 |
| 2 | **[propozycja]** `asset_type` (`stock`/`etf`) osobno od Klasy waloru | E1.3, E3.3 |
| 3 | **[propozycja]** Automatyczne wpłaty pochodne (`portfolios_auto_flow`, `auto_funding`) zamiast Operacji | E2.2b |
| 4 | **[propozycja]** `cash_balance`/`total_deposited` jako cache; `total_deposited` kursem Operacji | E2.2 |
| 5 | **[propozycja]** Ticker globalnie UNIQUE; ten sam symbol na dwóch giełdach rozróżnia sufiks | E1.3 |
| 6 | Źródło lokalnego katalogu GPW/NewConnect (E1.3) i kalendarza `assets_market_holiday` — nie występuje w dowodzie | E1.3, E1.9 |
| 7 | **[propozycja]** Blokada zadań przez wiersz `job_run` (`FOR UPDATE SKIP LOCKED`); zachowanie przy przerwanym przebiegu (wiersz zwalnia się z transakcją) do sprawdzenia testem | E1.4 |
| 8 | Kontrakty API tych tabel: [doc 09](./09_kontrakt_api_docelowy.md); import XTB wymaga zanonimizowanej próbki eksportu od właściciela | E2.7, E4 |
