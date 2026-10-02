---
id: be-target-api-contract
status: draft
type: mixed
scope: backend/target-api
last_reviewed: 2026-10-02
---

# Jaki jest docelowy kontrakt API backendu FundTrackera?

> **Projekt docelowy (L2, draft).** Opisuje stan docelowy wynikający z roadmapy ([plan](../../plans/02_roadmapa_funkcjonalna.md)), nie stan kodu — ten opisują dokumenty modułów i kod. Obowiązuje po akceptacji ADR-ów, na które się powołuje.

Kontrakt dla tabel z [doc 07](./07_schemat_danych_docelowy.md) i [doc 08](./08_schemat_danych_nowe_moduly.md) (nazwy pól = nazwy kolumn; przy sprzeczności ADR-u z schematem wygrywa schemat, rozbieżności w „Otwarte punkty”). Kroki: [E0–E5](../../plans/03_roadmapa_etapy_E0-E5.md), [E6–E11](../../plans/04_roadmapa_etapy_E6-E11.md). Potrzeby ekranów: [IA i UI](../frontend/ia-i-konwencje-ui.md). Błędy: [ADR-0007](../adr/0007-kontrakt-bledow-z-code.md). Stan dzisiejszy zweryfikowany w `backend/app/modules/*/api`, `schemas`, `core/errors.py`, `core/schemas.py` oraz `frontend/src/services`. **[propozycja]** = plan nie rozstrzyga.

**Notacja.** `D` = `DecimalString` (1.4); `?` = nullable lub opcjonalne; `date` = `YYYY-MM-DD`; lista wartości po `/`. Każde ciało żądania ma `extra="forbid"` (nie powtarzam); `owner_id` nigdy nie jest w żądaniu (z tokenu). `{S}` = zakres (1.1; odpowiedzi niosą `scope: {type, id?, name, currency}`). Statusy w 2: **ist.**, **zmiana** (istniejącego; plan zgodności w sekcji 4), **nowy**. Zapisy w `/assets/**` (poza `/assets/watchlist`) wymaga `is_owner` (D14) → `403 REFERENCE_DATA_OWNER_ONLY`.

## 1. Konwencje

### 1.1 Adresowanie po `id` i okres przejściowy

Dziś Portfel jest adresowany nazwą: `portfolio_name` (`schemas/operations.py:35` opcjonalny, `schemas/positions.py:43` wymagany), `portfolioName` (`schemas/metrics.py:16`), `GET /portfolios/?name=` (`schemas/portfolios.py:19`). `GET /portfolios/{id}` istnieje. Nazwa jest zmienna (PATCH), więc nie jest kluczem.

| Zakres `{S}` | Prefiks | Uwagi |
|---|---|---|
| Portfel | `/portfolios/{portfolio_id}` | `id` int |
| Grupa portfeli | `/groups/{group_id}` | bez zakładki operacji |
| Wszystkie Portfele | `/groups/all` | wirtualna Grupa (IA 1.2) **[propozycja]**; trasa statyczna przed `{group_id:int}` |

1. Nowe endpointy: tylko `id` (ścieżka `{S}` albo `portfolio_id` w query/body). Nazw w nowych endpointach nie ma.
2. Istniejące (`portfolio_name`, `portfolioName`): akceptowane **równolegle** z `portfolio_id`; oba naraz → `400 PORTFOLIO_SELECTOR_AMBIGUOUS` **[propozycja]**; nieznana nazwa → `404 PORTFOLIO_NOT_FOUND` jak dziś.
3. Deprecjacja: `deprecated=True` w OpenAPI, nagłówki `Deprecation` i `Sunset` w odpowiedzi, log `warning` ze ścieżką (widać, kto jeszcze woła).
4. Usunięcie: po kamieniu M1 ([plan](../../plans/02_roadmapa_funkcjonalna.md), „Kolejność realizacji”) i gdy `grep` w `frontend/src` nie zwraca użyć. Nazwa zostaje wyłącznie filtrem `GET /portfolios/?name=` (przekierowania ze starych tras, IA 1.5).

### 1.2 Listy: koperta, paginacja, sortowanie, filtry

Listy **nieograniczone z natury** (Operacje, wiersze importu, paczki, log dostarczeń, sprzedaże podatkowe, zamknięte pozycje) mają kopertę; słowniki i listy małe (Portfele, Grupy, waluty, Klasy, walory, tagi, obserwowane, kanały, reguły, modele) zostają **gołą tablicą** — nie łamie frontendu. Serie czasowe (ceny, wektory) są bez paginacji, z zakresem `from`/`to`.

```json
{ "items": [ ], "total": 10234, "limit": 50, "offset": 0 }
```

| Parametr | Reguła |
|---|---|
| `limit` / `offset` | int, `1–200` (domyślnie 50) / `≥ 0`; poza zakresem → 422 |
| `sort` | `pole` lub `-pole`, lista po przecinku; biała lista per endpoint; serwer dokleja `id` jako ostatni klucz (stabilność) |
| filtry | per endpoint; powtarzalne (`operation_type=buy&operation_type=sell`); daty `from`/`to` włącznie (`operation_day`); `q` = podciąg w notatce/nazwie |
| `format` | `json` (domyślnie) lub `csv` (E3.7; bez `limit`/`offset`, pełny eksport) — tylko endpointy z kolumną „CSV” w opisie |

**Offset czy cursor — rozstrzygnięcie [propozycja]: offset**, dla listy 10 000 Operacji (E2.7: < 300 ms na stronę):

| Argument | Uzasadnienie |
|---|---|
| UI | IA 4.2/6: numerowane strony, `total`, filtry i strona w URL — cursor nie daje skoku na stronę N ani sumy |
| Koszt | indeks `(portfolio_id, operation_day, sequence, id)` (doc 07 5.4) odpowiada kolejności domyślnej; `OFFSET 9950` czyta ≤ 10 000 wpisów indeksu **[nie zmierzone — pomiar w E2.7/E11.7]**; `total` = `COUNT(*)` z tymi samymi filtrami |
| Spójność, furtka | jeden użytkownik; wstawka w trakcie przeglądania przesuwa stronę o wiersz — akceptowalne; `cursor`/`next_cursor` dodamy **addytywnie**, gdy lista przekroczy ~100 tys. wierszy albo pomiar zawiedzie próg |

### 1.3 Wspólna koperta metryk

Każda metryka (E1.7, E3.1) to obiekt; endpoint wielometrykowy zwraca je jako pola. Zgodne z `Metric<T>` z IA 2.4/5.2 i [ADR 0004](../../business/adr/0004-metodologia-stop-zwrotu.md) pkt 7.

| Pole | Typ | Znaczenie |
|---|---|---|
| `value` | `D?` albo obiekt | wartość; `null` = nie da się policzyć (wtedy `reason`) |
| `unit` | string | kod waluty, `ratio` (ułamek: `0.084512` = 8,45%), `pct` (punkty procentowe, pola `*_pct`), `days` |
| `method` | string? | wersjonowana metoda: `daily_pp_v1` (TWR), `xirr_365_v1` (XIRR) **[propozycja nazw z ADR 0004]**; zmiana metody = nowa wartość i nowy ADR |
| `effective_start` | date? | faktyczny początek liczenia (dane od…); może być późniejszy niż `period.from` |
| `data_quality` | `ok/stale/synthetic/missing` | najgorsza wartość z okresu (kolejność `missing` > `synthetic` > `stale` > `ok`; zgodnie z `portfolios_daily.data_quality`, doc 07 5.10) |
| `stale` | bool | użyto ceny starszej niż `stale_price_days` albo snapshot po `dirty_from` (ADR-0016 pkt 5) |
| `source` | string | `snapshot` (z `portfolios_daily`), `live` (przeliczone na żądanie), `manual`, kod dostawcy |
| `as_of` | date | ostatni dzień, który wartość obejmuje |
| `reason` | kod? | przyczyna `null`/zawężenia, np. `IRR_UNDEFINED`, `IRR_AMBIGUOUS`, `PERIOD_SHORTER_THAN_ONE_YEAR`, `INSUFFICIENT_HISTORY` |
| `approximation` | bool? | tylko gdy możliwy fallback (Modified Dietz, ADR 0004 pkt 4) |
| `issues` | tablica? | `[{code, asset_id?, from?, to?}]` — listy braków do tooltipu (`PRICE_STALE`, `PRICE_MISSING`, `RATE_MISSING`, `REBUILD_PENDING`) |

Przykład `GET /portfolios/3/performance?period=YTD` (wartości **przykładowe**; okres 273 dni < 365 → brak annualizacji; XIRR niejednoznaczny → zwrócony TWR, pole puste, ADR 0004 pkt 2):

```json
{ "scope": {"type": "portfolio", "id": 3, "name": "XTB IKE", "currency": "PLN"},
  "period": {"code": "YTD", "from": "2026-01-01", "to": "2026-10-01", "days": 273},
  "as_of": "2026-10-01",
  "profit": {"value": "12345.67", "unit": "PLN", "data_quality": "ok", "stale": false,
             "source": "snapshot", "as_of": "2026-10-01", "effective_start": "2026-01-01"},
  "twr": {"value": "0.084512", "unit": "ratio", "method": "daily_pp_v1", "effective_start": "2026-01-01",
          "data_quality": "stale", "stale": true, "source": "snapshot", "as_of": "2026-10-01",
          "annualized": null, "annualized_reason": "PERIOD_SHORTER_THAN_ONE_YEAR",
          "issues": [{"code": "PRICE_STALE", "asset_id": 41, "from": "2026-09-22", "to": "2026-10-01"}]},
  "xirr": {"value": null, "unit": "ratio", "method": "xirr_365_v1", "reason": "IRR_AMBIGUOUS",
           "data_quality": "ok", "stale": false, "source": "live", "as_of": "2026-10-01"} }
```

`IRR_UNDEFINED` i `IRR_AMBIGUOUS` to **kody wewnątrz metryki (HTTP 200)**, nie wyjątki — odpowiedź nadal niesie TWR **[propozycja]**.

### 1.4 Kwoty i liczby: string czy liczba

Dziś `DecimalNumber` serializuje `Decimal` do `float` (`app/core/schemas.py:11-13`), a wartościowane widoki zaokrągla do 3/4/2 miejsc (`schemas/positions.py:35-37`); typy TS to `number` (IA 2.2). Kolumny to `Numeric(18,9)`, `(18,2)`, `twr_index` `(24,12)` — więcej cyfr, niż mieści IEEE 754 (15–17 znaczących).

**Rekomendacja [propozycja]: `DecimalString`** — string dziesiętny, kropka, bez notacji wykładniczej, np. `"1234.50"`, `"0.000012345"`, dla kwot, cen, ilości, kursów, współczynników i stóp (`unit: ratio`). Nowy typ w `core/schemas.py` (`PlainSerializer(format(v, "f"))`).

| Rodzaj | Format | Uwagi |
|---|---|---|
| kwoty, ceny, ilości, kursy, `*_rate` | `D` | bez zaokrąglenia ponad kolumnę |
| stopy (`unit: ratio`) | `D`, 6 miejsc | `Decimal(str(f))` + `quantize` na granicy API (ADR-0014 pkt 2) |
| `*_pct` (punkty %) | `D` | nowe pola 2 miejsca; istniejące `RoundedPercent` bez zmiany (4) |
| wektory wykresów, statystyki ryzyka (wewnątrz koperty), Monte Carlo | `D` w kopercie / `float` w tablicach serii | tablice `charts` zostają `float` (ADR-0014, IA 3) |
| wejście (żądania) | string lub liczba; **klient wysyła string** | odrzucane `NaN`/`Infinity` (jak `allow_inf_nan=False`, `schemas/operations.py:20,23`) |

**Skutek dla frontendu:** typ `DecimalString = string`; `format*` przyjmują `string` (IA 2.1 już tak); zakaz arytmetyki na kwotach w przeglądarce (IA 2.2); `Number()` tylko na granicy wykresu. Dwie konwencje współistnieją do jednego **kroku przełączenia istniejących schematów** (Portfel, Pozycja, Operacja, Walor, Waluta) — razem z typami generowanymi z OpenAPI (IA 5.1), aby kompilator wskazał każde użycie. Do tego czasu istniejące pola są `number`, nowe `string`; każdy endpoint w sekcji 2 ma typ w tabeli.

### 1.5 Daty i czas

| Pole | Typ | Reguła |
|---|---|---|
| `operation_day` | `date` | dzień kalendarzowy w **Europe/Warsaw** (D13, doc 07 5.4); klucz kolejności `(operation_day, sequence, id)` |
| `operation_date` | datetime ISO 8601 z offsetem | chwila (timestamptz); w żądaniu legacy; serwer wylicza z niej `operation_day` |
| żądanie Operacji | `operation_day` + `operation_time?` (`HH:MM[:SS]`, czas Warszawy) **albo** legacy `operation_date` | dokładnie jedno; brak godziny = 00:00 Warszawy (ADR 0005 pkt 1) |
| `settlement_date`, `price_date`, `rate_date`, `acquired_on`, `as_of`, `from`, `to` | `date` | bez strefy |
| `created_at`, `updated_at`, `*_at` | datetime UTC (`Z`) | wyświetlanie w Europe/Warsaw (stała, ADR-0019; `timezone` w `/settings` nie istnieje); `operation_day` zawsze Warszawa |

### 1.6 Błędy i kody

Format: `{"detail": "<angielski>", "code": "UPPER_SNAKE"}` (`core/errors.py:80-89,112`). **Zmiany addytywne [propozycja]:** (a) opcjonalne `params` (obiekt) — lista id przy blokadach, waluta przy `INSUFFICIENT_CASH`; wymaga pola w `APIError`; (b) 422 z walidacji dostaje `code: "REQUEST_VALIDATION_FAILED"` (dziś `detail` to lista bez `code`, `core/errors.py:115-122`). Wszystkie kody i `reason` są `UPPER_SNAKE` (ADR-0007), jednolite warianty (słownik niżej).

Istniejące kody (m.in. `*_NOT_FOUND`, `*_ALREADY_EXISTS`, `INSUFFICIENT_CASH`, `INSUFFICIENT_QUANTITY`, `INVALID_OPERATION`, `CONCURRENT_CHANGE`, `INVALID_DATE*`, `MARKET_DATA_UNAVAILABLE`, `INVALID_CREDENTIALS`; pełna lista w IA 2.7) zostają bez zmian.

| Kod | HTTP | Kiedy | Źródło |
|---|---|---|---|
| `REGISTRATION_DISABLED` | 403 | `POST /auth/register` przy `ALLOW_REGISTRATION=false` (domyślnie true w dev/test, false w produkcji) | E0.6 |
| `REFERENCE_DATA_OWNER_ONLY` | 403 | zapis danych globalnych bez `is_owner` | biz. 0007 |
| `ASSET_NOT_FOUND_ON_PROVIDER` | 404 | dostawca nie zna tickera przy tworzeniu Waloru (`None` od dostawcy) | E0.4 |
| `PORTFOLIO_CURRENCY_LOCKED` | 409 | zmiana `base_currency_id` Portfela z Operacjami | E0.8 |
| `PORTFOLIO_ACCOUNT_TYPE_LOCKED` | 409 | zmiana `account_type` Portfela z Operacjami | biz. 0001 (409 [propozycja]) |
| `PORTFOLIO_HAS_TRANSFERS` | 409 | DELETE Portfela z przelewami; `params.portfolio_ids` | biz. 0007, tech. 0016 |
| `PORTFOLIO_SELECTOR_AMBIGUOUS` | 400 | `portfolio_id` i `portfolio_name` naraz | 1.1 [propozycja] |
| `ASSET_HAS_HISTORY` / `ASSET_ARCHIVED` | 409 | DELETE Waloru z historią (zastępuje `ASSET_IN_USE`) / Operacja na zarchiwizowanym | biz. 0007 |
| `RATE_MISSING` | 404 (200 inline; wdrożone: `rate_missing: bool` + puste pola wyceny, bez `issues[]`) | `GET /assets/currencies/rate` bez kursu; w wycenie jako `issues[]` | E0.1 |
| `LOT_SELECTION_INVALID` | 400 | `lot_pick` wskazuje brak/za małą Partię | biz. 0002 |
| `TRANSFER_SAME_PORTFOLIO`, `TRANSFER_CROSS_OWNER` | 400 | przelew A→A / do cudzego Portfela | tech. 0016 |
| `OPERATION_EXTERNAL_REF_EXISTS` / `OPERATION_STATE_INVALID` | 409 | UNIQUE `(portfolio_id, external_ref)` (doc 07 5.4) / `accept` na nie-`draft`, `void` na `void` | [propozycja] |
| `IMPORT_PARSE_FAILED` / `IMPORT_PARSER_UNKNOWN` | 422 / 400 | plik nieczytelny / nieznany `parser_id` | tech. 0018 |
| `IMPORT_FILE_TOO_LARGE` | 413 | plik > 10 MB | doc 08 4.1 [propozycja] |
| `IMPORT_BATCH_STATE_INVALID` | 409 | commit/edycja nie-`draft`, revert nie-`committed` | E4.1 [propozycja] |
| `IMPORT_UNRESOLVED_ROWS` | 409 | commit z wierszami `unrecognized`/`error` (nie `skip`) | tech. 0018 pkt 3.5 |
| `IMPORT_COMMIT_REJECTED` | 400 | księga odrzuciła; `params.row_no` | tech. 0018 pkt 4 |
| `IMPORT_BATCH_HAS_EDITS` | 409 | cofnięcie z edytowanymi Operacjami; `params.operation_ids` | biz. 0007, tech. 0018 |
| `IMPORT_BATCH_REVERT_INVALID` | 409 | przebudowa po cofnięciu niespójna | biz. 0007 |
| `TAX_RATE_PENDING` | 409 | migawka/zamknięcie roku przy kursie podatkowym „oczekującym” | biz. 0005 (409 [propozycja]) |
| `TAX_YEAR_PARAMETER_MISSING`, `TAX_LOSS_OVERUSE` | 409 | brak `taxes_year_parameter` / odliczenie > `amount_initial` | doc 08 5.4, 5.1 [propozycja] |
| `PLANNING_SCOPE_INVALID`, `PLANNING_MODEL_TARGETS_EXCEED_100`, `ALERT_RULE_INVALID` | 400 | oba/żaden z `portfolio_id`/`group_id`; Σ `target_pct` > 100; FK niezgodny z `rule_type` | doc 08 6.1, 7.2 |
| `CHANNEL_SECRET_MISSING` / `CHANNEL_DELIVERY_FAILED` | 409 / 502 | brak zmiennej środowiskowej z `secret_ref` / błąd wysyłki testowej | doc 08 7.1 [propozycja] |
| `INVALID_API_TOKEN` / `API_TOKEN_SCOPE_INSUFFICIENT` / `JWT_REQUIRED` | 401 / 403 / 403 | token zły, unieważniony lub wygasły / `read` na zapisie / zarządzanie tokenami tokenem API | E10.4 [propozycja] |
| `<ENCJA>_NOT_FOUND` / `_ALREADY_EXISTS` | 404 / 409 | nowe encje: `PRICE`, `RATE_SERIES`, `BOND_SERIES`, `GROUP`, `TAG`, `IMPORT_BATCH`, `IMPORT_ROW`, `TAX_LOSS`, `PLANNING_MODEL`, `PLANNING_GOAL`, `FIRE_SCENARIO`, `RECURRING_TEMPLATE`, `NOTIFICATION_CHANNEL`, `ALERT_RULE`, `REPORT_SCHEDULE`, `API_TOKEN`, `IMPORT_TEMPLATE` | ADR-0007 |

**Inline (HTTP 200, w `reason`/`issues[]`):** `IRR_UNDEFINED`, `IRR_AMBIGUOUS` (E3.1), `PERIOD_SHORTER_THAN_ONE_YEAR`, `INSUFFICIENT_HISTORY` (< 60 obserwacji, E7.1), `PRICE_STALE`, `PRICE_SYNTHETIC`, `PRICE_MISSING`, `RATE_MISSING`, `REBUILD_PENDING`, `TAX_REVIEW_REQUIRED` (liczone z łańcucha Operacji, np. po spin-off, biz. 0006 pkt 3; nie kolumna), `CHANGED_AT_SOURCE` (podgląd importu, tech. 0018 pkt 6). `IRR_*` i `PERIOD_SHORTER_THAN_ONE_YEAR` nigdy nie są 4xx.

### 1.7 Idempotencja i dry-run

| Mechanizm | Reguła |
|---|---|
| Klucze naturalne | `external_ref` (UNIQUE `(portfolio_id, external_ref)`) → `OPERATION_EXTERNAL_REF_EXISTS`; wiersz importu ze znanym `dedup_key` = `duplicate`; ponowny plik (`sha256` UNIQUE) zwraca istniejącą paczkę (200, `known_file: true`), 0 nowych Operacji |
| Maszyna stanów | `commit` tylko z `draft`, `revert` tylko z `committed`; powtórka → `409 IMPORT_BATCH_STATE_INVALID` (nie podwaja skutków); `accept`/`void` Operacji j.w. |
| `Idempotency-Key` | **nie w v1**; wymagałby tabeli kluczy poza doc 07/08 — otwarty punkt |
| Dry-run | osobne endpointy `POST …/preview` (nie parametr, by OpenAPI miał jeden typ odpowiedzi): Operacja (create/update) i paczka importu. Ta sama walidacja i `PortfolioLedger`, rdzeń bez commitu ([ADR-0008](../adr/0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md)), `rollback` |

Odpowiedź podglądu — **200 także przy odrzuceniu przez księgę** (wynik biznesowy): `{ok, errors: [{code, detail, params?}], before, after, realized_pnl?, lots_consumed?, rebuild_from, warnings}`; `before`/`after`: `cash: [{currency, balance D}]` i `position: {asset_id, quantity D, average_buy_price D}`; `realized_pnl`: `{local D, base D, tax_pln D?}`; `lots_consumed`: `[{open_operation_id, origin_operation_id, quantity D, cost_base D}]`. Zły kształt → 422 jak zawsze.

### 1.8 Wersjonowanie

Bez prefiksu `/v1` **[propozycja]** (jeden użytkownik, jeden frontend w repo). Dodanie pola, endpointu lub opcjonalnego parametru = zmiana zgodna. Zmiana łamiąca = protokół z 1.1: nowy kształt obok starego → `deprecated` + `Deprecation`/`Sunset` → usunięcie po kamieniu milowym i po zerowym użyciu. Zrzut OpenAPI w repo (`app.openapi()`, IA 5.1) jest bramką CI na dryf; `info.version` rośnie przy usunięciu endpointu. Metodę metryk wersjonuje `method` (1.3), nie URL.

### 1.9 Uwierzytelnianie

| Mechanizm | Reguła |
|---|---|
| JWT | `Authorization: Bearer <access>` (`security/dependencies.py:22,34-58`), access 30 min (`core/config.py:24`), odświeżanie `POST /auth/token/refresh`; zgodnie z [ADR-0012](../adr/0012-jwt-odstepstwa-od-checklisty.md) |
| Token API (E10.4, doc 08 §3) | ten sam nagłówek `Bearer`; rozpoznawany po prefiksie `ft_` **[propozycja]** (w bazie tylko SHA-256); `read` = `GET` i endpointy podglądu (`…/preview`); `write` = wszystko poza zarządzaniem tokenami |
| Zarządzanie tokenami; rejestracja | `/auth/api-tokens*` wyłącznie JWT (`403 JWT_REQUIRED`), jawny token tylko w odpowiedzi `POST`; rejestracja domyślnie zamknięta (`REGISTRATION_DISABLED`), konta z CLI `create-user` ([ADR-0017](../adr/0017-zadania-w-tle-i-cli.md)) |

## 2. Katalog endpointów

### 2.1 `core_data`

| Endpoint | Cel | Parametry | Żądanie | Odpowiedź | Błędy | Krok | Status |
|---|---|---|---|---|---|---|---|
| `GET /settings` | ustawienia (wiersz leniwie, doc 07 3.2) | — | — | `display_currency_code`, `stale_price_days`, `risk_free_series_code?`, `condition_thresholds?` (JSONB, E7.6), `updated_at` | — | E0.9 | nowy |
| `PUT /settings` (`PATCH`) | zapis | — | `display_currency_code` `^[A-Z]{3}$`, `stale_price_days` int ≥ 1, `risk_free_series_code?` str(40), `condition_thresholds?` obiekt; waluta bez walidacji przy zapisie (ADR-0013 pkt 5) | j.w. | `REQUEST_VALIDATION_FAILED` | E0.9, E7.2, E7.6 | nowy |
| `POST /auth/register` | rejestracja | — | `email`, `password` (min 8) | `id`, `email`, `is_active` | `REGISTRATION_DISABLED`, `EMAIL_ALREADY_REGISTERED` | E0.6 | zmiana |
| `GET /auth/me` | profil | — | — | `id`, `email`, `is_active`, **+`is_owner`** | 401 | E0.6 | zmiana (addytywna) |

### 2.2 `security`

| Endpoint | Cel | Parametry | Żądanie | Odpowiedź | Błędy | Krok | Status |
|---|---|---|---|---|---|---|---|
| `POST /auth/login` (alias `/auth/token`), `POST /auth/token/refresh` | JWT; odświeżenie | — | `email`, `password` / `refresh` | `access`, `refresh` | `INVALID_CREDENTIALS`, `INVALID_REFRESH_TOKEN` | — | ist. |
| `GET /auth/api-tokens` | lista | — | — | `[{id, name, token_prefix, scope, created_at, expires_at?, revoked_at?, last_used_at?}]` | `JWT_REQUIRED` | E10.4 | nowy |
| `POST /auth/api-tokens` | utworzenie | — | `name` str(100), `scope` `read/write`, `expires_at?` | j.w. + `token` (jawny, jednorazowo), 201 | `JWT_REQUIRED` | E10.4 | nowy |
| `DELETE /auth/api-tokens/{id}` | unieważnienie (`revoked_at`) | — | — | 204 | `API_TOKEN_NOT_FOUND` | E10.4 | nowy |

### 2.3 `assets`

| Endpoint | Cel | Parametry | Żądanie | Odpowiedź | Błędy | Krok | Status |
|---|---|---|---|---|---|---|---|
| `GET/POST/PUT·PATCH/DELETE /assets/currencies[/{id}]` | CRUD walut | — | `code` `^[A-Za-z]{3}$`, `exchange_rate?` D > 0 (**null dozwolone**), `base_currency_id?` (wygaszane) | `id`, `code`, `exchange_rate?` (dziś `number`, wtedy `D?`), `base_currency_id?` | `CURRENCY_ALREADY_EXISTS`, `CURRENCY_IN_USE`, `CURRENCY_NOT_FOUND` | E0.1, E1.1 | zmiana |
| `GET /assets/currencies/rate` | kurs **bezpośredni lub odwrotny** z bazy (bez składania krzyżowych; kurs krzyżowy: `GET /portfolios/fx-rate`) | `from_currency`, `to_currency` (kody), `date?` (dziś) | — | `from_currency`, `to_currency`, `rate` D, `rate_date`, `source`, `table_no?`, `is_synthetic`, `stale`, `via` (`direct/inverse`) | `CURRENCY_NOT_FOUND`, `RATE_MISSING` | E0.1, E1.1 | nowy |
| `GET·PUT /assets/fx-rates` | historia pary / kurs ręczny (`source=manual`) | GET: `from_currency`, `to_currency`, `from?`, `to?`, `source?` | PUT: `from_currency_id`, `to_currency_id`, `rate_date`, `rate` D > 0 | GET: `{items: [{rate_date, rate D, source, table_no?, is_synthetic}]}` | `CURRENCY_NOT_FOUND` | E1.1, E1.5 | nowy |
| `GET/POST/PUT·PATCH/DELETE /assets/asset-classes[/{id}]` | CRUD Klas waloru | — | `name` str(1–20) | `id`, `name` | `ASSET_CLASS_*` | — | ist. |
| `GET /assets/` | lista i wyszukiwanie po nazwie, tickerze, ISIN | `search` (ticker/nazwa dziś, `repositories/assets.py:20-26`; **+ISIN**), `asset_type?`, `asset_class_id?`, `country?`, `include_archived` (false) | — | `[AssetResponse]` + `isin?`, `mic?`, `country?`, `asset_type`, `archived_at?`, `price_date?`, `stale`, `price_source?` | — | E1.3, E1.7 | zmiana (addytywna) |
| `POST /assets/` | utworzenie | — | `ticker` str(20), `name` str(100), `asset_class_id`, `currency_id`, `current_price`, `exchange`, `sector` **+`isin?` str(12), `mic?` str(4), `country?` str(2), `asset_type`** | `AssetResponse` | `ASSET_ALREADY_EXISTS`, `CURRENCY_NOT_FOUND`, `ASSET_CLASS_NOT_FOUND` | E1.3 | zmiana |
| `GET /assets/search-yahoo`, `POST /assets/create-from-yahoo` | wyszukiwanie u dostawcy; utworzenie z notowania | `q` (min 2) | `ticker`, `asset_class_id?`, `currency_id?` | `{local: [...], yahoo: [...]}` (klucz historyczny); `AssetDetailResponse` | `ASSET_NOT_FOUND_ON_PROVIDER`, `MARKET_DATA_UNAVAILABLE` | E0.4 | ist. |
| `GET /assets/{id}` | szczegół | — | — | `AssetDetailResponse` + pola jak w liście, `listings` | `ASSET_NOT_FOUND` | E1.3, E1.7 | zmiana |
| `PUT·PATCH /assets/{id}` | edycja (null = błąd 422 jak dziś) | — | pola z `POST`; `current_price` zapisuje wiersz `manual` (ADR 0015 pkt 5) | `AssetResponse` | `ASSET_NOT_FOUND`, `ASSET_ALREADY_EXISTS` | E1.5 | zmiana |
| `DELETE /assets/{id}` | usunięcie waloru bez historii | — | — | 204 | `ASSET_HAS_HISTORY` | D15 | zmiana |
| `POST /assets/{id}/archive`, `/unarchive` | archiwizacja (D15) | — | — | `AssetResponse` z `archived_at` | `ASSET_NOT_FOUND` | E1.3 | nowy |
| `GET /assets/{id}/prices` | seria zamknięć (efektywna cena dnia wg priorytetu) | `from?`, `to?`, `source?`, `fill` `none/forward` (none) | — | `{asset_id, currency, items: [{price_date, close D, source, is_synthetic, stale}]}` | `ASSET_NOT_FOUND` | E1.1 | nowy |
| `PUT·DELETE /assets/{id}/prices/{price_date}` | cena ręczna (`source=manual`) / usunięcie ręcznej | — | PUT: `close` D > 0, `currency_id?` (waluta waloru) | wiersz, 200/201 / 204 | `ASSET_NOT_FOUND`, `ASSET_ARCHIVED`, `PRICE_NOT_FOUND` | E1.5 | nowy |
| `GET /assets/{id}/listings`, `PUT·DELETE …/{provider}` | symbole i priorytet dostawców | — | `symbol` str(40), `priority` int ≥ 1, `is_enabled` | `[{provider, symbol, priority, is_enabled, last_success_at?, last_error_at?, last_error?}]` | `ASSET_NOT_FOUND` | E1.2 | nowy |
| `POST /assets/refresh-prices` | ręczne odświeżenie wybranych walorów: **202** + `BackgroundTasks` wołające wyłącznie `assets.entrypoints.refresh_prices`; żądanie nie woła dostawcy (wyjątek E1.4, ADR-0017) | — | `asset_ids` int[] (1–50) | 202 `{accepted: [id]}`; wynik widać w `price_date`/`data-status` | `ASSET_NOT_FOUND` | E1.4 | nowy |
| `GET /assets/data-status` | panel „Dane” | `only_problems` bool | — | `{fx: {last_success_at?}, assets: [{asset_id, ticker, price_date?, stale, source?, last_success_at?, last_error_at?, last_error?}]}` | — | E1.7 | nowy |
| `GET·POST /assets/tags`, `PATCH·DELETE /assets/tags/{id}`, `PUT /assets/{id}/tags` | tagi globalne; zbiór tagów waloru | — | `name` str(50) (unikalne bez wielkości liter), `color?` `#RRGGBB`; `tag_ids` int[] | `[{id, name, color?}]` | `TAG_ALREADY_EXISTS`, `TAG_NOT_FOUND` | E2.7, E3.3 | nowy |
| `GET /assets/watchlist` | obserwowane (per `owner_id`) | — | — | `[{asset, note?, added_at, price: {close D, price_date, stale, source}, change_1d_pct? D}]` | — | E1.8 | nowy |
| `PUT·DELETE /assets/watchlist/{asset_id}` | dodanie/notatka, usunięcie | — | `note?` str(200) | wpis / 204 | `ASSET_NOT_FOUND` | E1.8 | nowy |
| `GET /assets/rate-series`, `GET …/{code}/values` | szeregi stóp (NBP, CPI) | `from?`, `to?` | — | `[{code, name, unit, frequency, source}]` / `{code, items: [{valid_from, value D}]}` | `RATE_SERIES_NOT_FOUND` | E1.6 | nowy |
| `GET·PUT /assets/{id}/bond` | parametry serii obligacji | — | `bond_type` `OTS/ROR/DOR/TOS/COI/EDO/ROS/ROD`, `sale_start`, `sale_end`, `nominal` D, `term_months`, `first_rate` D, `margin?` D, `early_redemption_fee` D, `payout_mode` `at_maturity/annual/monthly/capitalized`, `issue_letter_ref?` | j.w. + `rates: [{period_no, rate D, announced_on?, source_ref?}]` | `ASSET_NOT_FOUND`, `BOND_SERIES_NOT_FOUND` | E5.1 | nowy |
| `PUT /assets/{id}/bond/rates/{period_no}` | ogłoszona stopa okresu (fakt) | — | `rate` D, `announced_on?`, `source_ref` str(200) **wymagane** | wiersz | `BOND_SERIES_NOT_FOUND` | E5.1 | nowy |

### 2.4 `portfolios`

**Ciało Operacji** (`POST`/`PUT`/`PATCH`, `extra="forbid"`; w `PUT/PATCH` nie zmieniają się `portfolio_id`, `operation_type`, `asset_id` — `schemas/operations.py:61-73`):

| Pole | Typ | Uwagi |
|---|---|---|
| `portfolio_id` | int | jak dziś |
| `operation_type` | enum | dziś `buy/sell/deposit/withdrawal/dividend`; docelowo + `interest/fee/tax/transfer/fx_exchange/adjustment/split/symbol_change/spin_off/redemption/bond_switch` (doc 07 5.4, nazwy [propozycja]) |
| `asset_id?` lub `ticker?` + `asset_class?` | int / str | jak dziś (tworzenie po tickerze) |
| `operation_day` + `operation_time?` albo `operation_date` | 1.5 | |
| `quantity`, `price`, `amount?`, `fee`, `fx_rate` | `D` | kursy: brokera (ADR 0003 pkt 3); `quantity`/`price` `Numeric(18,9)`, `amount`/`fee` `(18,2)` |
| `currency_id` | int | **jawne** dla nowych wierszy; pominięte → API wstawia walutę waloru (wpłata/wypłata: bazową Portfela); NULL tylko w danych sprzed `rebuild-all` (ADR biz. 0003 pkt 4) |
| `settlement_date?`, `settlement_source?`, `tax_deductible` | date, `default/broker/manual`, bool | `fx_rate_tax`, `fx_tax_table_no`, `fx_tax_date` **tylko w odpowiedzi** (wypełnia serwer wg D12) |
| `counter_portfolio_id?`, `counter_amount?` D, `counter_currency_id?`, `counter_asset_id?`, `ratio?` D > 0 | | przelew (**jeden wiersz**: `amount` = noga wychodząca z Portfela źródłowego, `counter_*` = przychodząca), przewalutowanie (tak samo), split, wymiana |
| `lot_pick?` | `[{open_operation_id, origin_operation_id, quantity D}]` | wskazanie Partii przy sprzedaży (D2), tabela `portfolios_operation_lot_pick`; niewskazana reszta FIFO |
| `status`, `sequence?`, `external_ref?` str(120), `tag_ids` | `posted/draft`, int ≥ 0, | `void` tylko przez `…/void`; `sequence` nadawany automatycznie, w żądaniu tylko zmiana kolejności w dniu |
| odpowiedź | — | dziś pola `OperationResponse`; **+** `portfolio_id` (E0.10), `direction` (`out`/`in`: dla przelewu zależnie od Portfela, w którego kontekście czytamy; pozostałe `out`), `operation_day`, `settlement_date?`, `settlement_source`, `currency_id`, pola kursu podatkowego, `counter_*`, `ratio?`, `lot_pick`, `status`, `sequence`, `edited_at?`, `import_batch_id?`, `external_ref?`, `tag_ids`, `tax_deductible` |

| Endpoint | Cel | Parametry | Żądanie | Odpowiedź | Błędy | Krok | Status |
|---|---|---|---|---|---|---|---|
| `GET /portfolios/fx-rate` | **jedyna ścieżka UI po kurs krzyżowy** (podpowiedź w dialogu zakupu/przewalutowania, E0.1): `FxMapBuilder` składa rate[z]/rate[do] z kursów `assets` | `from_currency`, `to_currency` (kody), `date?` | — | `from_currency`, `to_currency`, `rate` D, `rate_date`, `via` (`direct/inverse/cross`), `stale`, `is_synthetic` | `CURRENCY_NOT_FOUND`, `RATE_MISSING` | E0.1 | nowy; **wdrożony podzbiór (E0.1b):** `from_currency`, `to_currency` → `from_currency`, `to_currency`, `rate` (9 miejsc), `via` (+ `identity`); `date?`, `rate_date`, `stale`, `is_synthetic` czekają na historię kursów (E1.1) |
| `GET /portfolios/` | lista Portfeli z wyceną | `name?`, `account_type?`, `is_active?` | — | `[PortfolioSummaryResponse]` + `account_type`, `broker?`, `tax_date_basis`, `settlement_lag_days?`, `auto_funding`, `cash_balances: [{currency, balance D}]`, `stale`, `as_of` | — | E2.1, E2.2 | zmiana (addytywna) |
| `POST /portfolios/` | utworzenie | — | `name` str(1–100), `base_currency_id`, **+`account_type` (`regular/ike/ikze/ppk/ppe/oipe`, domyślnie `regular`), `broker?` str(60), `tax_date_basis` `settlement/trade`, `settlement_lag_days?` ≥ 0, `auto_funding` bool (false)** | `PortfolioResponse` | `PORTFOLIO_ALREADY_EXISTS`, `BASE_CURRENCY_NOT_FOUND` | E2.1, E2.2b | zmiana |
| `GET /portfolios/{id}` | Portfel z pozycjami | — | — | `PortfolioDetailResponse` + pola jak w liście | `PORTFOLIO_NOT_FOUND` | E2.1 | zmiana |
| `PUT·PATCH /portfolios/{id}` | edycja | — | pola `POST`, null = bez zmian | `PortfolioResponse` | `PORTFOLIO_CURRENCY_LOCKED`, `PORTFOLIO_ACCOUNT_TYPE_LOCKED`, `PORTFOLIO_ALREADY_EXISTS` | E0.8, E2.1 | zmiana (łamiąca) |
| `DELETE /portfolios/{id}` | usunięcie kaskadowe | — | — | 204 | `PORTFOLIO_HAS_TRANSFERS` | D15 | zmiana |
| `GET·PUT /portfolios/{id}/commission-rules` | domyślne prowizje | — | lista `{asset_type?, rate_pct D ≥ 0, min_fee D, currency_id?}` (zastępuje zbiór) | lista | `PORTFOLIO_NOT_FOUND` | E2.1 | nowy |
| `GET /portfolios/{id}/limits` | limit IKE/IKZE: wpłacono, pozostało | `year?` | — | `{applicable, year, account_type, variant (`regular`), limit_amount D, deposited D, remaining D}` | `PORTFOLIO_NOT_FOUND` | E5.6 | nowy |
| `GET·POST /groups`, `GET·PATCH·DELETE /groups/{id}`, `PUT /groups/{id}/members` | CRUD Grup, skład | — | `name` str(1–100), `currency_code?`, `portfolio_ids` int[] (zastępuje zbiór) | `[{id, name, currency_code?, portfolio_ids, created_at}]` / 204 | `GROUP_ALREADY_EXISTS`, `GROUP_NOT_FOUND`, `PORTFOLIO_NOT_FOUND` | E2.1 | nowy |
| `GET /portfolios/positions` | pozycje (legacy) | `portfolio_name` (wymagany) **albo** `portfolio_id` | — | `[PositionResponse]` | `PORTFOLIO_NOT_FOUND` | E0.10, E1.4 | zmiana: bez odświeżania dostawcy (`services/positions.py:37-39`); `portfolio_name` deprecated; odpowiedź + `portfolio_id` (E0.10) |
| `GET {S}/positions` | pozycje zakresu (Grupa: suma po Walorze) | `as_of?`, `include_closed` (false) | — | `[PositionResponse]` + `price_date`, `stale`, `price_source`, `is_synthetic`, `lots_count`, koszt z Partii | `PORTFOLIO_NOT_FOUND`, `GROUP_NOT_FOUND` | E2.4, E1.7 | nowy |
| `GET /operations`, `GET /portfolios/{id}/operations` | historia wszystkich Portfeli / jednego (koperta, CSV); zawiera przelewy, w których Portfel jest źródłem **lub** celem (`direction`); szkice: `status=draft` | `portfolio_id?` (tylko `/operations`), `operation_type*`, `asset_id?`, `from?`, `to?`, `tag_id*`, `status` (`posted`; `draft/void/all`), `q?`, `limit`, `offset`, `sort` (`operation_day`, `amount`, `asset`), `format` | — | `{items: [OperationResponse], total, limit, offset}` | `PORTFOLIO_NOT_FOUND`, `INVALID_DATE_RANGE` | E2.7 | nowy |
| `GET /portfolios/operations` | lista legacy: goła tablica, bez paginacji | `portfolio_name?` / `portfolio_id?` | — | `[OperationResponse]` | `PORTFOLIO_NOT_FOUND` | E2.7 | ist., deprecated |
| `GET /portfolios/operations/{id}` | jedna Operacja | — | — | `OperationResponse` | `OPERATION_NOT_FOUND` | E3.8 | nowy |
| `POST /portfolios/operations` | zapis Operacji wszystkich typów | — | ciało Operacji | `OperationResponse`, 201 | `INSUFFICIENT_CASH`, `INSUFFICIENT_QUANTITY`, `INVALID_OPERATION`, `OPERATION_REQUIRES_ASSET`, `LOT_SELECTION_INVALID`, `TRANSFER_*`, `OPERATION_EXTERNAL_REF_EXISTS`, `ASSET_ARCHIVED`, `RATE_MISSING` | E2.3, E2.4 | zmiana |
| `PUT·PATCH /portfolios/operations/{id}` | edycja; ustawia `edited_at`, przebudowa od daty | — | pola ciała poza `portfolio_id`/`operation_type`/`asset_id` | `OperationResponse` | j.w. + `OPERATION_NOT_FOUND`, `CONCURRENT_CHANGE` | E2.3 | zmiana |
| `DELETE /portfolios/operations/{id}` | usunięcie (przelew: jeden wiersz, przebudowa obu Portfeli) | — | — | 204 | `OPERATION_NOT_FOUND`, błąd przebudowy | E2.3 | zmiana |
| `POST /portfolios/operations/preview`, `POST …/{id}/preview` | dry-run (1.7): create / update | — | ciało jak `POST` / `PATCH` | podgląd (1.7) | tylko 422/404 | E2.3 | nowy |
| `POST /portfolios/operations/{id}/accept`, `/void` | `draft→posted` (propozycje: dywidendy E8.5, cykliczne E9.6, e-mail E10.3) / `posted→void` | — | `accept`: opcjonalnie pola jak `PATCH`; `void`: — | `OperationResponse` | `OPERATION_STATE_INVALID` | E8.5, E9.6 | nowy |
| `GET {S}/lots` | otwarte Partie | `asset_id?`, `include_closed` (false) | — | `[{open_operation_id, origin_operation_id, portfolio_id, asset_id, acquired_on, tax_date, quantity_initial D, quantity_open D, unit_price D, cost_local D, cost_base D, cost_tax_pln? D, fx_rate D, fx_rate_tax? D, closed_on?}]` | — | E2.4 | nowy |
| `GET {S}/closed-positions` | raport zamkniętych pozycji (koperta, CSV) | `from?`, `to?` (`closed_on`), `asset_id?`, `limit`, `offset`, `sort`, `format` | — | `{summary: {proceeds, cost, fees, dividends, profit, return, win_rate, profit_factor: Metric}, items: [...], total, limit, offset}` | `INVALID_DATE_RANGE` | E3.2 | nowy |
| `GET {S}/performance` | zysk, TWR, XIRR okresu | `period` `1M/3M/6M/YTD/1Y/3Y/5Y/MAX/custom`, `from?`/`to?` (przy `custom`), `currency?`, `real` (false, po E1.6), `metrics?` (CSV: `profit,twr,xirr,realized,income,fees,taxes`) | — | koperta metryk (1.3) | `INVALID_DATE_RANGE`, `PORTFOLIO_NOT_FOUND`, `GROUP_NOT_FOUND` | E3.1 | nowy |
| `GET /portfolios/portfolio-vectors` | wektory wykresów (legacy) | `portfolioName?`, `startDate?`, `endDate?`, `interval` (tylko `1d`, `services/metrics.py:51`), `vectors` (JSON) | — | `{date: [...], <wektor>: [float]}` | `INVALID_VECTORS`, `UNSUPPORTED_INTERVAL`, `INVALID_DATE*`, `PORTFOLIO_NOT_FOUND` | E3.5 | ist., deprecated po E3.5 |
| `GET {S}/allocation` | struktura (suma udziałów = 100%, gotówka osobno) | `by` `asset/class/sector/currency/country/account_type/tag`, `as_of?`, `over_time` (false), `from?`, `to?` | — | `{by, as_of, currency, total D, cash D, items: [{key, label, value D, weight_pct D}], series?, data_quality, stale}` | — | E3.3 | nowy |
| `GET /dashboard` | kokpit w walucie wyświetlania | — | — | `{currency, as_of, total_value, cash, positions_value, day_change, twr_ytd, twr_1y: Metric, portfolios: [{id, name, value D, day_change D, sparkline: [float]}], winners, losers}` | `CURRENCY_NOT_FOUND`, `RATE_MISSING` | E3.4 | nowy |
| `GET {S}/charts/{series}` | wykresy ze snapshotów (bez dostawcy) | `series`: `value-vs-contributions`, `profit`, `twr`, `drawdown`, `monthly-returns`, `treemap`, `rolling`; `period`/`from`/`to`; `benchmark_asset_id*` (≤ 5), `asset_id*` (≤ 4) | — | `{date: [...], <seria>: [float], data_quality, stale, as_of}` | `ASSET_NOT_FOUND` | E3.5, E7.3 | nowy |
| `GET /portfolios/compare` | porównanie Portfeli na TWR | `portfolio_id*` (2–10), `period`/`from`/`to` | — | `{items: [{portfolio_id, twr, xirr: Metric}], series: {date: [...], "<id>": [float]}}` | `PORTFOLIO_NOT_FOUND` | E3.5 | nowy |
| `GET {S}/assets/{asset_id}` | widok waloru w zakresie | `period?` | — | `{asset, positions: [...], lots: [...], realized, return, income: Metric}` | `ASSET_NOT_FOUND` | E3.8 | nowy |
| `GET {S}/income` | dywidendy i odsetki (CSV) | `from?`, `to?`, `granularity` `month/year`, `basis` `gross/net`, `asset_id?`, `format` | — | `{items: [{period, gross D, net D, tax D}], ttm_yield, yield_on_cost: Metric, top_payers: [{asset_id, amount D}]}` | — | E3.6 | nowy |
| `GET {S}/calendar` | dywidendy i wykupy, prognoza 12 mies.; kalendarz globalny = `/groups/all/calendar` (nie osobna trasa) | `from?`, `to?` | — | `{items: [{date, kind, asset_id, amount D, status, source}]}`; `kind` `dividend/interest/redemption`, `status` `booked/announced/forecast` (**szacunek oznaczony**) | — | E8.6, E5.2 | nowy (zdarzenia: Operacje `status=draft`, E8.5) |
| `GET {S}/risk` | statystyki ryzyka | `period`/`from`/`to`, `benchmark_asset_id?`, `risk_free_series_code?` | — | `volatility`, `max_drawdown` (+`duration_days`, `recovery_days`), `sharpe`, `sortino`, `beta`, `alpha`, `correlation`, `var_95`, `expected_shortfall_95`: Metric (`INSUFFICIENT_HISTORY` < 60 obs.) | `ASSET_NOT_FOUND` | E7.1, E7.2 | nowy |
| `GET {S}/fx-effect` | rozbicie zysku: cena/waluta/dywidendy/koszty/podatki | `period`/`from`/`to` | — | `{components: [{key, value D}], series_with_fx, series_without_fx: [float], date}` | — | E7.4 | nowy |
| `GET {S}/benchmark-flows` | benchmark „te same przepływy” | `benchmark_asset_id`, `period` | — | `{xirr_portfolio, xirr_benchmark: Metric, series}` | `ASSET_NOT_FOUND` | E7.5 | nowy |
| `GET {S}/condition` | kondycja portfela | — | — | `{score, rules: [{code, level, value, threshold, explanation}]}` | — | E7.6 | nowy |
| `GET {S}/bonds` | wycena obligacji per Partia, wykupy | `as_of?` | — | `[{asset_id, open_operation_id, origin_operation_id, period_no, rate D, accrued_interest D, value D, early_redemption_fee D, net_value D, maturity_date}]` | `BOND_SERIES_NOT_FOUND` | E5.1, E5.2 | nowy |
| `GET /portfolios/imports/parsers` | dostępne źródła | — | — | `[{parser_id, label, formats, needs_mapping}]` | — | E4.2 | nowy |
| `POST /portfolios/imports` | wgranie pliku → szkic | — | multipart: `file` (≤ 10 MB), `portfolio_id`, `parser_id` str(40), `template_id?`, `options?` | Paczka: `id`, `portfolio_id`, `parser_id`, `status`, `file: {filename, sha256, size_bytes, encoding?}`, `template_id?`, `counts: {ok, duplicate, unrecognized, error, skip}`, `created_at`, `committed_at?`, `reverted_at?`, `known_file`; 201 (nowa) lub 200 (ten sam `sha256` → istniejąca paczka, `known_file: true`) | `IMPORT_FILE_TOO_LARGE`, `IMPORT_PARSER_UNKNOWN`, `IMPORT_PARSE_FAILED`, `PORTFOLIO_NOT_FOUND` | E4.1 | nowy |
| `GET /portfolios/imports`, `GET·DELETE …/{id}` | lista paczek (koperta); paczka / usunięcie szkicu lub cofniętej | `portfolio_id?`, `status?`, `limit`, `offset`, `sort` | — | `{items: [Paczka], ...}` / Paczka / 204 | `IMPORT_BATCH_NOT_FOUND`, `IMPORT_BATCH_STATE_INVALID` | E4.1 | nowy |
| `PUT /portfolios/imports/{id}/mapping` | mapowanie CSV/XLSX, ponowne parsowanie | — | `columns` `{pole: kolumna}`, `separator`, `decimal_separator`, `encoding`, `date_format`, `save_as?` str(100) | `{batch, preview_rows: [10]}` | `IMPORT_BATCH_STATE_INVALID`, `IMPORT_PARSE_FAILED` | E4.2 | nowy |
| `GET /portfolios/imports/{id}/rows` | wiersze szkicu (koperta ≤ 200) | `row_status*` (`ok/duplicate/unrecognized/error/skip`), `q?`, `limit`, `offset`, `sort` (`row_no`) | — | `{items: [{row_id, row_no, raw_label?, raw_cells, row_status, dedup_key?, resolution?, error_code?, error_detail?, operation_day?, operation_type?, asset_id?, isin?, ticker?, quantity? D, price? D, amount? D, fee? D, fx_rate? D, settlement_date?, currency_code?, external_ref?, match_key?, match_key?, field?, value?, duplicate_of_operation_id?, operation_id?, is_overridden, asset_candidates?}], total, limit, offset, counts}` | `IMPORT_BATCH_NOT_FOUND` | E4.1 | nowy |
| `PATCH /portfolios/imports/{id}/rows/{row_id}` | edycja wiersza; zapis nadpisania (doc 08 4.4) | — | `operation_type?`, `asset_id?`, `operation_day?`, `quantity?`, `price?`, `amount?`, `fee?`, `currency_code?`, `fx_rate?`, `settlement_date?`, `row_status?` (`ok`/`skip`; biała lista) | wiersz po walidacji | `IMPORT_ROW_NOT_FOUND`, `IMPORT_BATCH_STATE_INVALID` | E4.1 | nowy |
| `POST /portfolios/imports/{id}/preview` | dry-run zatwierdzenia (1.7) | — | `{}` | podgląd + `operations_count` | `IMPORT_UNRESOLVED_ROWS` w `errors` | E4.1 | nowy |
| `POST /portfolios/imports/{id}/commit` | zatwierdzenie: jedna transakcja, jedna przebudowa | — | `{}` | `{batch, created_operations, skipped, rebuild_from}` | `IMPORT_UNRESOLVED_ROWS`, `IMPORT_COMMIT_REJECTED`, `IMPORT_BATCH_STATE_INVALID` | E4.1 | nowy |
| `POST /portfolios/imports/{id}/revert` | cofnięcie (D15) | — | `{}` | Paczka (`reverted`) | `IMPORT_BATCH_HAS_EDITS`, `IMPORT_BATCH_REVERT_INVALID`, `IMPORT_BATCH_STATE_INVALID` | E4.1 | nowy |
| `GET·POST·DELETE /portfolios/import-templates[/{id}]` | szablony mapowania | — | `name` str(100), `parser_id` str(40), `mapping` obiekt | `[{id, name, parser_id, mapping, created_at}]` | `IMPORT_TEMPLATE_NOT_FOUND` | E4.2 | nowy |
| `GET /portfolios/operations/export` | CSV operacji | `portfolio_id?`, `from?`, `to?`, `flavor` `native/portfolio_performance` | — | `text/csv` | `PORTFOLIO_NOT_FOUND` | E4.5 | nowy |
| `GET /portfolios/export` | kopia danych `portfolios` (JSON: Portfele, Grupy, Operacje, tagi) | — | — | JSON z `schema_version` | — | E4.5 | nowy |

### 2.5 `taxes` (E6)

Każda odpowiedź raportowa niesie `disclaimer` („Szkic do weryfikacji — nie porada podatkowa”) i `assumptions: [{code, text, verified}]` ([ADR 0006](../../business/adr/0006-zakres-modulu-podatkowego.md) pkt 1). Kwoty w PLN (`D`). Rachunki `ike/ikze/ppk/ppe/oipe` poza pulami (po `account_type`).

| Endpoint | Cel | Parametry | Żądanie | Odpowiedź | Błędy | Krok | Status |
|---|---|---|---|---|---|---|---|
| `GET /taxes/{year}/report`, `…/report/export` | PIT-38: pule a/b/c, PIT/ZG; plik z adnotacją „szkic” | `portfolio_id*`; `format` `csv/pdf` (export) | — | `{tax_year, disclaimer, assumptions, pools: {a, b, c: {revenue, cost, income, loss_deduction, base, tax}}, pit_zg: [{country, income, tax_paid}], split: {domestic, foreign}, data_quality, issues}` | `TAX_YEAR_PARAMETER_MISSING` | E6.1, E6.2 | nowy |
| `GET /taxes/{year}/sales` | sprzedaże z Partiami (koperta, CSV) | `portfolio_id*`, `asset_id?`, `pool?`, `limit`, `offset`, `sort`, `format` | — | `{items: [{close_operation_id, open_operation_id, origin_operation_id, asset_id, acquired_on, tax_date, quantity D, proceeds_pln, cost_pln, fee_pln, fx_rate_tax, fx_tax_table_no}], ...}` | — | E6.2 | nowy |
| `GET /taxes/{year}/dividends` | dywidendy i odsetki: WHT, dopłata | `portfolio_id*`, `format` | — | `{items: [{operation_id, asset_id, pay_date, gross_pln, wht_pln, pl_tax_pln, credit_pln, top_up_pln, fx_rate_tax, fx_tax_table_no}], totals}` | — | E6.3 | nowy |
| `GET /taxes/{year}/optimizer` | optymalizator końca roku | `as_of?` | — | `{last_trade_day, items: [{open_operation_id, origin_operation_id, asset_id, unrealized_loss_pln}]}` | — | E6.7 | nowy |
| `GET /taxes/estimate` | „wynik po podatku” (szacunek; `portfolios` nie zależy od `taxes`, ADR-0013) | `portfolio_id?`/`group_id?`, `as_of?` | — | `{unrealized_tax, current_year_due: Metric, label: "szacunek"}` | — | E6.6 | nowy |
| `GET·POST /taxes/losses`, `DELETE …/{id}` | rejestr strat; strata ręczna (`source=manual`); usunięcie bez użyć | `pool?` | `loss_year`, `pool` `a/b`, `kind` `loss/excess_cost`, `amount_initial` D > 0 | `[{id, loss_year, pool, kind, amount_initial, source, used: [{use_year, amount, mode}], remaining}]` / 204 | `TAX_LOSS_ALREADY_EXISTS`, `TAX_LOSS_NOT_FOUND` | E6.5 | nowy |
| `POST /taxes/losses/{id}/uses` | odliczenie | — | `use_year`, `amount` D > 0, `mode` `annual_50/one_time` | strata z `used` | `TAX_LOSS_OVERUSE`, `TAX_LOSS_NOT_FOUND` | E6.5 | nowy |
| `GET·PUT /taxes/lot-attributes/{origin_operation_id}` | flagi Partii | — | `acquisition_kind` `purchase/gift/inheritance`, `ipo_relief`, `ipo_admission_date?` (wymagana przy `ipo_relief`), `cost_override?` D | atrybuty | `OPERATION_NOT_FOUND` | E6.1 | nowy |
| `GET·PUT /taxes/portfolios/{portfolio_id}/settings` | ustawienia podatkowe rachunku | — | `broker_country?` str(2), `issues_pit8c` | j.w. | `PORTFOLIO_NOT_FOUND` | E6.2 | nowy |
| `GET·PUT /taxes/years/{year}/parameters` | parametry roczne (zapis: właściciel) | — | `pit_rate_pct` D, `loss_lump_cap` D, `rounding_rule_30a` `grosz_up/zloty_half_up` | j.w. | `REFERENCE_DATA_OWNER_ONLY` | E6.2 | nowy |
| `POST·GET /taxes/{year}/snapshots`, `GET /taxes/snapshots/{id}` | migawka złożonej wersji / zamknięcie roku | — | `close_year` bool | `{id, tax_year, input_hash, is_year_closed, created_at, changed_since, payload?}` | `TAX_RATE_PENDING`, `TAX_YEAR_PARAMETER_MISSING` | E6.2, E6.5 | nowy |

### 2.6 `planning` (E9)

| Endpoint | Cel | Parametry | Żądanie | Odpowiedź | Błędy | Krok | Status |
|---|---|---|---|---|---|---|---|
| `GET·POST /planning/models`, `GET·PUT·DELETE …/{id}` | portfel wzorcowy | — | `name`, `portfolio_id?`/`group_id?` (dokładnie jedno), `dimension` `class/tag/asset`, `band_abs_pp?` D, `band_rel_pct?` D (≥ 1 z dwóch), `targets: [{asset_class_id?/tag_id?/asset_id?, target_pct D 0–100, band_abs_pp?, band_rel_pct?}]` | model z `targets` | `PLANNING_SCOPE_INVALID`, `PLANNING_MODEL_TARGETS_EXCEED_100`, `PLANNING_MODEL_NOT_FOUND`, `PLANNING_MODEL_ALREADY_EXISTS` | E9.1 | nowy |
| `GET /planning/models/{id}/deviation` | odchylenie od wzorca | `as_of?` | — | `{items: [{key, target_pct, actual_pct, deviation_pp, status, band}], cash_pct}`; `status` `in_band/out_of_band` | `PLANNING_MODEL_NOT_FOUND` | E9.1 | nowy |
| `POST /planning/models/{id}/rebalance` | propozycja (bez zapisu) | — | `mode` `new_cash/full/to_band`, `cash_amount?` D, `currency_code?`, `whole_units` (true), `include_tax_estimate` | `{trades: [{asset_id, side, quantity D, amount D, tax_estimate_pln? D}], residual_cash D}` | `PLANNING_MODEL_NOT_FOUND` | E9.2 | nowy |
| `GET·POST /planning/goals`, `GET·PUT·DELETE …/{id}` | cele | — | `name`, `portfolio_id?`/`group_id?` (≤ jedno), `currency_code`, `target_amount` D > 0, `target_date`, `monthly_contribution` D, `return_nominal_pct` D, `inflation_pct?`, `volatility_pct?`, `mc_seed?` | cel | `PLANNING_GOAL_NOT_FOUND`, `PLANNING_SCOPE_INVALID` | E9.3 | nowy |
| `GET /planning/goals/{id}/projection` | ścieżka vs rzeczywistość | `real` (false) | — | `{path: [{date, planned D, actual D?}], required_contribution, months_to_goal: Metric}` | `PLANNING_GOAL_NOT_FOUND` | E9.3 | nowy |
| `POST /planning/goals/{id}/monte-carlo` | symulacja (wynik niezapisywany) | — | `paths` int 10 000–100 000 (górna granica [propozycja]), `seed?` (domyślnie `mc_seed`) | `{seed, paths, method, p10, p50, p90: [float], goal_probability}` | `PLANNING_GOAL_NOT_FOUND` | E9.5 | nowy |
| `GET·POST /planning/fire-scenarios`, `GET·PUT·DELETE …/{id}`, `GET …/{id}/result` | FIRE / runway | — | `name`, `group_id?`, `currency_code`, `monthly_expenses` D, `withdrawal_rate_pct` D, `inflation_pct` D | scenariusz / `{fire_number, progress, runway_months: Metric}` | `FIRE_SCENARIO_NOT_FOUND` | E9.4 | nowy |
| `GET·POST /planning/recurring-templates`, `GET·PUT·DELETE …/{id}` | szablony cykliczne (generuje CLI; akceptacja propozycji przez `POST /portfolios/operations/{id}/accept`) | — | `portfolio_id`, `operation_type`, `asset_id?`, `amount?` D, `fee` D, `currency_id?`, `cycle` `weekly/monthly/quarterly/yearly`, `day_of_cycle?`, `weekend_rule` `next/previous/keep`, `starts_on`, `ends_on?`, `is_active` | szablon (+`last_generated_on?`) | `RECURRING_TEMPLATE_NOT_FOUND` | E9.6 | nowy |

### 2.7 `notifications` (E10)

| Endpoint | Cel | Parametry | Żądanie | Odpowiedź | Błędy | Krok | Status |
|---|---|---|---|---|---|---|---|
| `GET·POST /notifications/channels`, `GET·PUT·DELETE …/{id}` | kanały | — | `kind` `smtp/ntfy/telegram/imap`, `name` str(60), `config` obiekt (jawny), `secret_ref?` str(60) (**nazwa zmiennej środowiskowej**, nigdy sekret), `is_enabled` | kanał (bez sekretu) | `NOTIFICATION_CHANNEL_NOT_FOUND` | E10.1 | nowy |
| `POST /notifications/channels/{id}/test` | wysyłka testowa | — | — | `{status, error?}` | `CHANNEL_SECRET_MISSING`, `CHANNEL_DELIVERY_FAILED` | E10.1 | nowy |
| `GET·POST /notifications/alert-rules`, `GET·PUT·DELETE …/{id}` | reguły alertów (ewaluacja: CLI po `refresh-prices`) | — | `name`, `rule_type` (7 wartości, doc 08 7.2), `asset_id?`, `portfolio_id?`, `model_id?`, `threshold` D, `threshold_unit` `price/pct`, `repeat_mode` `once/repeat`, `channel_id?`, `state?` `armed/disabled` | reguła + `state`, `last_triggered_at?`, `last_value?`, `last_evaluated_at?` | `ALERT_RULE_INVALID`, `ALERT_RULE_NOT_FOUND` | E10.1 | nowy |
| `GET /notifications/deliveries` | log (koperta) | `rule_id?`, `schedule_id?`, `status?`, `limit`, `offset` | — | `{items: [{id, rule_id?, schedule_id?, channel_id?, subject, status, attempts, error?, created_at, sent_at?}], ...}` | — | E10.1 | nowy |
| `GET·POST /notifications/report-schedules`, `GET·PUT·DELETE …/{id}`, `GET …/{id}/preview` | raport okresowy; podgląd = treść e-maila | — | `period` `weekly/monthly`, `day_of_period`, `channel_id?`, `sections` string[], `is_enabled` | harmonogram (+`last_sent_at?`) / `{subject, html, sections}` | `REPORT_SCHEDULE_NOT_FOUND` | E10.2 | nowy |

## 3. Ekran UI → endpointy

Ekrany z [IA §6](../frontend/ia-i-konwencje-ui.md). **BRAK** = wymaga decyzji lub danych poza katalogiem.

| Ekran (trasa) | Endpointy | Braki |
|---|---|---|
| Kokpit `/` | `GET /portfolios/`, `GET /dashboard`, `GET /settings` | — |
| Portfel — pozycje; Grupa `/groups/:id`, `/groups/all` | `GET /portfolios/{id}`, `/groups*`, `GET {S}/positions`, `POST /portfolios/operations[/preview]`, `GET /assets/?search`, `POST /assets/refresh-prices` (202, w tle) | — |
| Widok waloru `/assets/:id` | `GET {S}/assets/{asset_id}`, `GET /assets/{id}/prices`, `GET /operations?asset_id=`, `GET {S}/income?asset_id=` | — |
| Historia operacji | `GET /operations`, `GET /portfolios/{id}/operations`, `PUT·PATCH·DELETE /portfolios/operations/{id}` | — |
| Struktura; Wyniki; `/compare`; Zamknięte pozycje | `GET {S}/allocation`, `/performance`, `/charts/{series}`, `/closed-positions`, `GET /portfolios/compare`, `GET /assets/tags`, `GET /assets/?asset_type=` (benchmarki) | — |
| Dywidendy i kalendarz | `GET {S}/income`, `GET {S}/calendar` | — (zdarzenia = Operacje `status=draft`, E8.5; kalendarz globalny `/groups/all/calendar`) |
| Obligacje `/bonds` | `GET {S}/bonds`, `GET·PUT /assets/{id}/bond`, `PUT …/rates/{n}` | — |
| Ryzyko | `GET {S}/risk`, `/fx-effect`, `/benchmark-flows`, `/condition`, `/charts/{series}` | — (progi: `condition_thresholds` w `/settings`) |
| Import `/import*` | `/portfolios/imports*`, `/portfolios/import-templates*`, `GET /assets/?search`, `GET /portfolios/`, `GET /operations?status=draft` (szkice) | — (kształt wierszy zależy od próbek brokerów) |
| Podatki; Planowanie; Alerty | `/taxes/**` (2.5), `/planning/**` (2.6) + `POST /portfolios/operations/{id}/accept`, `/notifications/alert-rules*`, `/deliveries` | — |
| Dane i jakość `/data` | `GET /assets/data-status`, `/assets/watchlist`, `PUT /assets/{id}/prices/{date}`, `/assets/{id}/listings` | kalendarz sesji (E1.9): tabela `assets_market_holiday`, bez endpointu |
| Ustawienia | `/settings`, `/auth/api-tokens*`, `/notifications/channels*`, `/notifications/report-schedules*` | — |
| Logowanie; przekierowania `/pockets/:slug`; Metodologia | `/auth/*`; `GET /portfolios/?name=`; brak (treść statyczna) | — |
| Eksport CSV (E3.7), kopia (E4.5) | `format=csv` na operacjach, zamkniętych pozycjach, dywidendach, sprzedażach; `GET /portfolios/operations/export`, `GET /portfolios/export` | pełna kopia instancji i restore: **BRAK endpointu** (cross-module; CLI) |

## 4. Zmiany łamiące i okres przejściowy

Frontend dziś woła (`frontend/src/services`): `GET/POST/DELETE /portfolios/…`, `GET /portfolios/?name=`, `GET /portfolios/positions?portfolio_name=`, `GET/POST/DELETE /portfolios/operations`, `GET /portfolios/portfolio-vectors`, `GET /assets/currencies`, `GET /assets/asset-classes`, `GET /assets/search-yahoo`, `POST /assets/create-from-yahoo`, `/auth/*`. Okres przejściowy = od wprowadzenia nowego kształtu do kamienia M1; usunięcia tylko po warunku z 1.1 pkt 4.

| # | Zmiana | Używa frontend? | Zgodność wsteczna i okres | Usunięcie starego |
|---|---|---|---|---|
| 1 | `portfolio_name`/`portfolioName` → `portfolio_id` | tak (`positionService.ts:7`, `operationService.ts:7`, `analyticsService.ts:16`) | oba parametry równolegle, `deprecated` + `Sunset`; odpowiedzi pozycji i operacji dostają `portfolio_id` (E0.10) | po M1 i zerowym `grep` |
| 2 | `GET /portfolios/operations` (tablica) → `GET /operations` (koperta) | tak | stary endpoint bez zmian i **bez limitu** do przełączenia UI na E2.7 | po E2.7 + M1 |
| 3 | kwoty `number` → `DecimalString` w istniejących schematach | tak (`types/api.ts:37-46`) | jeden krok z typami z OpenAPI (1.4); do tego czasu nowe pola `string` | — (zmiana typu) |
| 4 | `operation_date` → `operation_day` + `operation_time` | tak (dialogi) | żądanie przyjmuje oba; odpowiedź zwraca oba | `operation_date` w żądaniu po M1 |
| 5 | `GET /portfolios/positions` przestaje odświeżać dostawcę | pośrednio | kształt bez zmian; dochodzą `price_date`/`stale` | — (E1.4) |
| 6 | `PUT/PATCH /portfolios/{id}`: `base_currency_id` zablokowane przy Operacjach | nie (brak edycji w UI) | `409 PORTFOLIO_CURRENCY_LOCKED`; dziś zmiana przechodzi | — |
| 7 | `DELETE /assets/{id}`: `ASSET_IN_USE` → `ASSET_HAS_HISTORY` | mapowanie w UI (IA 2.7) | kod zmieniony od razu (tylko UI i `test_asset_service.py:227`) | — |
| 8 | `POST /auth/register` → `403 REGISTRATION_DISABLED` domyślnie | tak (`/register`) | UI ukrywa rejestrację; `ALLOW_REGISTRATION=true` w dev | — |
| 9 | `exchange_rate` waluty `null`, brak domyślnego 1 | tak (typ `Currency`) | pole nullable; wycena zwraca `RATE_MISSING` zamiast kursu 1 | — |
| 10 | kody `UPPER_SNAKE` (plan: małe litery); 422 dostaje `code`, błędy `params` | `getErrorMessage` (IA 2.7) | addytywne; plan i ADR-y poprawione na `UPPER_SNAKE` | — |
| 11 | `portfolio-vectors` zastąpione `{S}/charts/{series}` | tak (`analyticsService.ts:14`) | stary działa bez zmian do E3.5; alias `pocket_value_vector` usuwany razem | po E3.5 + M1 |

## Otwarte punkty

| # | Punkt | Blokuje |
|---|---|---|
| 1 | **[propozycja]** offset zamiast cursor; próg wydajności (< 300 ms/stronę dla 10 000 Operacji) do zmierzenia | E2.7, E4.1 |
| 2 | **[propozycja]** `DecimalString` dla nowych pól i jednorazowe przełączenie istniejących; czy żądania mają przyjmować liczby JSON | E0.7, E3.1 |
| 5 | `taxes_lot_attribute` i wskazanie Partii kluczowane po `origin_operation_id`; kształt przelewu papierów (wiele Partii z jedną Operacją otwierającą) do potwierdzenia testem E2.4 | E2.4 |
| 6 | Pole `params` w błędach i `code` w 422 wymagają zmiany `core/errors.py` — dopisek do ADR-0007 | E2.3, E4.1 |
| 7 | Brak podglądu usunięcia Operacji (UI: ostrzeżenie „przebuduje od <data>”); `Idempotency-Key` poza v1 (wymaga tabeli) — ochrona = `external_ref` i maszyna stanów | E2.3 |
| 9 | Token API: prefiks `ft_`, zakres `read` obejmuje `…/preview`; asystent MCP (E10.5) poza tym kontraktem | E10.4, E10.5 |
| 10 | Pełna kopia instancji i restore (E4.5) obejmują wszystkie moduły; graf ADR-0013 nie wskazuje właściciela endpointu — **[propozycja]** polecenia CLI `export-all`/`import-all` (rozszerzenie ADR-0017); HTTP tylko `GET /portfolios/export` | E4.5, E11.3 |
| 11 | `GET /groups/all` jako wirtualna Grupa; zapisy Operacji pod `/portfolios/operations`, odczyty pod `/operations` (symetria?) | E3.1, E2.7 |
| 12 | Wariant IKZE (`regular`/`self_employed`) per Portfel — brak pola, `limits` zwraca domyślny | E5.6 |
| 13 | Daty `Sunset` i definicja „zerowego użycia” — decyzja właściciela; zrzut OpenAPI przez `app.openapi()` niezweryfikowany (brak FastAPI w środowisku autora) | M1 |
| 14 | Kształt wierszy importu i `source` — próbki od właściciela (myfund, XTB, mBank, IBKR, DEGIRO, Trading212, Revolut) oraz PIT-8C do E6.2 | E4.2a, E4.3, E6.2 |
