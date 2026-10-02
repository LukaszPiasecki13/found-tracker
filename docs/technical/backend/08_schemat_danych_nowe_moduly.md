---
id: be-target-schema-new-modules
status: draft
type: mixed
scope: backend/target-schema
last_reviewed: 2026-10-02
---

# Jaki jest docelowy schemat danych nowych modułów i paczek importu?

> **Projekt docelowy (L2, draft).** Opisuje stan docelowy wynikający z roadmapy ([plan](../../plans/02_roadmapa_funkcjonalna.md)), nie stan kodu — ten opisują dokumenty modułów i kod. Obowiązuje po akceptacji ADR-ów, na które się powołuje.

Uzupełnia [`07_schemat_danych_docelowy.md`](./07_schemat_danych_docelowy.md) (konwencje typów, nazw i migracji stamtąd obowiązują tu bez zmian). Kroki: [E0–E5](../../plans/03_roadmapa_etapy_E0-E5.md), [E6–E11](../../plans/04_roadmapa_etapy_E6-E11.md); decyzje D1–D16 w [planie](../../plans/02_roadmapa_funkcjonalna.md). **[propozycja]** = plan nie rozstrzyga; zebrane w „Otwarte punkty”. Pojęcie **Paczka importu** jest proponowane (D3).

## 1. Mapa: moduł → tabele → kroki planu

| Moduł | Tabele | Kroki |
|---|---|---|
| `security` | `security_api_token` | E10.4 |
| `portfolios` (import, D10) | `portfolios_import_batch`, `portfolios_import_row`, `portfolios_import_override`, `portfolios_import_template` | E4.1, E4.2, E4.2a, E4.3, E4.4, E10.3 |
| `portfolios` (limity) | `portfolios_account_limit` | E5.6 |
| `taxes` | `taxes_loss`, `taxes_loss_use`, `taxes_lot_attribute`, `taxes_account_setting`, `taxes_year_parameter`, `taxes_report_snapshot` | E6.1–E6.7 |
| `planning` | `planning_model_portfolio`, `planning_model_target`, `planning_goal`, `planning_fire_scenario`, `planning_recurring_template` | E9.1–E9.6 |
| `notifications` | `notifications_channel`, `notifications_alert_rule`, `notifications_report_schedule`, `notifications_delivery` | E10.1–E10.3 |

## 2. Kierunki zależności modułów (ADR-0006)

FK do tabel innego modułu jest dozwolony (jak dziś `portfolios_operation.asset_id`); **odczyt i zapis tylko przez serwisy** ([ADR-0006](../adr/0006-cross-module-wylacznie-przez-serwisy.md)). Nowe kierunki wymagają ADR-u (luka z przeglądu) — poniższy graf jest jego treścią do zaakceptowania:

| Moduł | Zależy od (przez serwisy) | Nie może zależeć od |
|---|---|---|
| `core_data` | — (waluta w ustawieniach jako kod, doc 07 sekcja 3.2); **dług:** `core_data/services/users.py:7` importuje `security/services/password`, a `security/services/auth.py:2` importuje `core_data` — cykl do usunięcia (hash hasła do `core/` albo wstrzyknięcie), zanim powstaną tokeny API (E10.4) | wszystkich pozostałych |
| `security` | `core_data` (`security/services/auth.py:2`) | pozostałych |
| `assets` | — | `portfolios` i dalszych |
| `portfolios` | `assets`, `core_data` | `taxes`, `planning`, `notifications` |
| `taxes` | `portfolios`, `assets` | `planning`, `notifications` |
| `planning` | `portfolios`, `taxes`, `assets` | `notifications` |
| `notifications` | `portfolios`, `assets`, `planning` (przez port; alert odchylenia E9.1) | `taxes` |

Graf docelowy jest acykliczny (po usunięciu długu `core_data` ↔ `security`). Konsekwencja: limity IKE/IKZE (E5.6) leżą w `portfolios`, nie w `taxes` (inaczej `portfolios → taxes` zamknęłoby cykl z `taxes → portfolios`).

## 3. Moduł `security` — tokeny API (E10.4)

Dziś `security` nie ma modeli (użytkownicy są w `core_data`). Token API to osobny mechanizm obok JWT ([ADR-0012](../adr/0012-jwt-odstepstwa-od-checklisty.md)), rozpoznawany w `get_current_user` po prefiksie nagłówka.

### `security_api_token`

| Kolumna | Typ | Null | Domyślne | Klucz / ograniczenie |
|---|---|---|---|---|
| `id` | `BigInteger` | nie | — | PK |
| `owner_id` | `BigInteger` | nie | — | FK `users.id` ON DELETE CASCADE |
| `name` | `String(100)` | nie | — | etykieta nadana przez użytkownika |
| `token_prefix` | `String(12)` | nie | — | pierwsze znaki jawnego tokenu, tylko do rozpoznania na liście |
| `token_hash` | `String(64)` | nie | — | UNIQUE; hash SHA-256 (hex) tokenu |
| `scope` | `String(10)` | nie | `'read'` | `CHECK IN ('read','write')`; `write` obejmuje `read` (E10.4: odczyt / zapis) |
| `created_at` | `DateTime(tz)` | nie | `now()` | — |
| `expires_at` | `DateTime(tz)` | tak | `NULL` | brak = bez terminu |
| `revoked_at` | `DateTime(tz)` | tak | `NULL` | unieważnienie; token unieważniony → 401 (E10.4) |
| `last_used_at` | `DateTime(tz)` | tak | `NULL` | aktualizowany co najwyżej raz na minutę **[propozycja]** (bez zapisu przy każdym `GET`) |

Indeksy: UNIQUE `(token_hash)`; `(owner_id, revoked_at)`. **[propozycja]** Jawny token (≥ 32 bajty losowych, `secrets`) pokazywany raz przy utworzeniu; w bazie tylko SHA-256 — wystarczy dla tokenu o wysokiej entropii (hasła osobno, bcrypt). Czytają: `security` (walidacja w zależności HTTP), `core_data.UserService` (ładowanie użytkownika). Tokeny nie dają dostępu do zarządzania tokenami (`scope` nie obejmuje tego; endpoint wymaga JWT).

## 4. Moduł `portfolios` — Paczki importu (E4)

Parsery plików to adaptery w `infrastructure/` (D10); port importu w `core/` ([ADR-0018](../adr/0018-architektura-importu.md)). Potok E4.1: plik → wiersze pośrednie → zatwierdzenie → cofnięcie. Odczyt i zapis wyłącznie przez serwis importu w `portfolios`; rozpoznanie waloru przez serwis `assets` (ISIN, ticker + `mic`). Szkic z e-maila (IMAP, E10.3) to Operacja `status='draft'` (6.4), nie wiersz importu.

### 4.1 Plik importu — kolumny w Paczce

Osobnej tabeli pliku nie ma (dawna `portfolios_import_file`): `filename`, `sha256`, `size_bytes`, `encoding`, `content` leżą w `portfolios_import_batch` (4.2). Limit 10 MB (`IMPORT_FILE_TOO_LARGE`); ten sam plik (`sha256`) nie tworzy drugiej Paczki.

### 4.2 `portfolios_import_batch` — **Paczka importu**

| Kolumna | Typ | Null | Domyślne | Klucz / uwagi |
|---|---|---|---|---|
| `id` | `BigInteger` | nie | — | PK; cel FK `portfolios_operation.import_batch_id` (doc 07, 5.4) — `ON DELETE RESTRICT` |
| `owner_id` | `BigInteger` | nie | — | FK `users.id` |
| `portfolio_id` | `BigInteger` | nie | — | FK `portfolios_portfolio.id` |
| `template_id` | `BigInteger` | tak | `NULL` | FK `portfolios_import_template.id` ON DELETE SET NULL |
| `parser_id` | `String(40)` | nie | — | kod parsera: `csv`, `myfund`, `xtb`, `mbank`, `ibkr`, `degiro`, `trading212`, `revolut`… |
| `filename` | `String(255)` | nie | — | nazwa oryginalna (wklejka: nazwa nadana) |
| `sha256` | `String(64)` | nie | — | hash treści; **UNIQUE `(owner_id, sha256)`**: ponowny plik zwraca istniejącą Paczkę (0 nowych Operacji, E4.1) |
| `size_bytes` | `Integer` | nie | — | `CHECK <= 10485760` **[propozycja]** limit 10 MB |
| `encoding` | `String(20)` | tak | `NULL` | wykryte (UTF-8, cp1250; E4.2) |
| `content` | `LargeBinary` | nie | — | surowa treść, `deferred` **[propozycja]** — plik w bazie, żeby kopia (E4.5, E11.3) obejmowała wszystko; w repo nigdy (testy: pliki zanonimizowane, E4.3) |
| `status` | `String(10)` | nie | `'draft'` | `draft`, `committed`, `reverted`; `CHECK` |
| `created_at` / `committed_at` / `reverted_at` | `DateTime(tz)` | nie / tak / tak | `now()` / `NULL` / `NULL` | — |

Indeksy: `(owner_id, status)`, `(portfolio_id, created_at DESC)`. **Cofnięcie (D15):** serwis usuwa Operacje Paczki, chyba że któraś ma `edited_at IS NOT NULL` — wtedy 409 `IMPORT_BATCH_HAS_EDITS` z listą id; po cofnięciu `status='reverted'`, wiersze zostają (do ponownego zatwierdzenia). Zatwierdzenie = rdzeń `record_many` bez commitu + jeden `rebuild` ([ADR-0008](../adr/0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md); dziś `_record` commituje — `portfolios/services/operations.py:99-100`).

### 4.3 `portfolios_import_row` — wiersz pośredni (odpowiednik `ParsedRow`)

| Kolumna | Typ | Null | Uwagi |
|---|---|---|---|
| `id` | `BigInteger` | nie | PK |
| `batch_id` | `BigInteger` | nie | FK `portfolios_import_batch.id` ON DELETE CASCADE |
| `row_no` | `Integer` | nie | numer w pliku; UNIQUE `(batch_id, row_no)` |
| `raw_label` | `String(200)` | tak | **surowa etykieta typu** z pliku (np. „Kupno”) — wejście mapowania na `operation_type` |
| `raw_cells` | `JSONB` | nie | surowy wiersz pliku bez zmian (podgląd, diagnostyka) |
| `payload` | `JSONB` | nie | znormalizowane pola `ParsedRow` (po parsowaniu, przed nadpisaniami) |
| `row_status` | `String(12)` | nie | `ok`, `duplicate`, `unrecognized`, `error`, `skip`; `CHECK` (E4.1); `skip` = wiersz pominięty (duplikat odwrócony, nadpisanie, decyzja użytkownika) |
| `resolution` | `String(12)` | tak | **[propozycja]** po zatwierdzeniu: `created` (powstała Operacja), `skipped`; `NULL` w szkicu |
| `error_code` / `error_detail` | `String(40)` / `String(200)` | tak | kod walidacji (waluta, brutto ≠ ilość × cena ± prowizja, data); bez danych osobowych |
| `dedup_key` | `String(120)` | nie | hash (`operation_day`, `isin` lub `asset_id`, ilość, kwota); gdy jest `external_ref`, klucz = `external_ref` |
| `match_key` | `String(120)` | nie | klucz nadpisań (4.4): `external_ref` albo `dedup_key` |
| `operation_day`, `settlement_date` | `Date` | tak | wartości po parsowaniu i nałożeniu nadpisań |
| `operation_type` | `String(20)` | tak | wartość `OperationType` albo `NULL` przy `unrecognized` |
| `asset_id` | `BigInteger` | tak | FK `assets_asset.id`; `NULL` = nierozpoznany walor |
| `isin`, `ticker` | `String(12)`, `String(20)` | tak | rozpoznawanie waloru (E4.1) |
| `quantity`, `price`, `fx_rate` | `Numeric(18,9)` | tak | `fx_rate` = kurs brokera z pliku |
| `amount`, `fee` | `Numeric(18,2)` | tak | — |
| `currency_code` | `String(3)` | tak | — |
| `external_ref` | `String(120)` | tak | ID z pliku (np. Trading212) |
| `duplicate_of_operation_id` / `operation_id` | `BigInteger` | tak | FK `portfolios_operation.id` ON DELETE SET NULL; `operation_id` wypełniane przy zatwierdzeniu |
| `is_overridden` | `Boolean` | nie (`false`) | wiersz zmieniony przez użytkownika lub nałożone nadpisanie |

Indeksy: `(batch_id, row_status)` (filtr `row_status`, paginacja `limit`/`offset`, do 2 000 wierszy), `(match_key)`. Duplikaty: `external_ref` w tej samej Operacji (UNIQUE częściowy `(portfolio_id, external_ref)`, doc 07 5.4) albo zgodność `dedup_key`.

### 4.4 `portfolios_import_override` — nadpisania użytkownika przy re-imporcie

Poprawki ręczne (zmiana typu, przypisanie waloru, pominięcie wiersza) przeżywają cofnięcie Paczki i ponowny import (E4.1). To wiedza użytkownika, więc nie jest czyszczona z Paczką. Jeden wiersz = jedno pole.

| Kolumna | Typ | Null | Uwagi |
|---|---|---|---|
| `id` | `BigInteger` | nie | PK |
| `portfolio_id` | `BigInteger` | nie | FK CASCADE |
| `parser_id` | `String(40)` | nie | źródło, którego dotyczy nadpisanie |
| `match_key` | `String(120)` | nie | `external_ref` albo `dedup_key` wiersza |
| `field` | `String(40)` | nie | pole z białej listy (`operation_type`, `asset_id`, `skip`…; walidacja w serwisie) |
| `value` | `String(255)` | nie | wartość jako tekst (`skip` = `true`) |
| `updated_at` | `DateTime(tz)` | nie | `now()` |

UNIQUE `(portfolio_id, parser_id, match_key, field)`. Kolejność: parser → nadpisania → rozpoznanie waloru → walidacja → duplikaty. Zaksięgowana Operacja nigdy nie jest nadpisywana: różnice pokazuje podgląd (`CHANGED_AT_SOURCE`), domyślnie `skip`.

### 4.5 `portfolios_import_template` — zapisane mapowania CSV (E4.2)

`id` PK; `owner_id` FK; `name` `String(100)`; `parser_id` `String(40)`; `mapping` `JSONB` (kolumny, separator, przecinek dziesiętny, kodowanie, format daty); `created_at`. UNIQUE `(owner_id, name)`.

### 4.6 `portfolios_account_limit` — limity IKE/IKZE (E5.6)

Konfiguracja roczna, dane globalne (D14); ładowana komendą CLI, nie na sztywno w kodzie.

| Kolumna | Typ | Null | Klucz / uwagi |
|---|---|---|---|
| `id` | `BigInteger` | nie | PK |
| `year` | `SmallInteger` | nie | — |
| `account_type` | `String(10)` | nie | `CHECK IN ('ike','ikze')` |
| `variant` | `String(16)` | nie (`'regular'`) | `regular`, `self_employed` (dla IKZE dwie wartości w dowodzie, [podatki](../../research/04_rynek_pl_podatki_i_brokerzy.md)) |
| `limit_amount` | `Numeric(18,2)` | nie | `CHECK > 0`; wartości z dowodu, nie z pamięci |
| `source_ref` | `String(200)` | tak | źródło limitu (np. numer obwieszczenia) — wymagane przez E5.6, ADR-0017, biznesowy 0006 |

UNIQUE `(year, account_type, variant)`. Czyta tylko `portfolios` (wpłaty za rok z Operacji `deposit`/przelewów); wybór wariantu IKZE per Portfel — otwarty punkt.

## 5. Moduł `taxes` (E6)

Nie ma drugiego silnika FIFO: czyta `portfolios_lot_consumption` (doc 07, 5.7) przez serwis `portfolios` i dokłada własne dane. Tabele `taxes_*` nie są pochodnymi księgi — trzymają **dane użytkownika i decyzje**. Każdy raport nosi adnotację „szkic do weryfikacji” ([plan E6](../../plans/04_roadmapa_etapy_E6-E11.md)).

### 5.1 `taxes_loss` + `taxes_loss_use` — rejestr strat (E6.5)

Reguła (art. 9 ust. 3): przez 5 lat do 50% straty rocznie **albo** jednorazowo do 5 000 000 zł; straty krypto wyłączone ([plan E6.5](../../plans/04_roadmapa_etapy_E6-E11.md)).

| Tabela | Kolumna | Typ | Null | Uwagi |
|---|---|---|---|---|
| `taxes_loss` | `id` PK; `owner_id` FK `users.id` | — | nie | — |
| | `loss_year` | `SmallInteger` | nie | rok powstania straty |
| | `pool` | `String(1)` | nie | `CHECK IN ('a','b')`: a = papiery i fundusze (art. 30b ust. 1), b = waluty wirtualne; pula c (art. 30a, per zdarzenie) nie ma strat przenoszonych **[propozycja]** — punkt otwarty |
| | `kind` | `String(12)` | nie | `loss` (a), `excess_cost` (b — nadwyżka kosztów roku do przeniesienia, art. 22 ust. 14–16) |
| | `amount_initial` | `Numeric(18,2)` | nie | PLN, `CHECK > 0` |
| | `source` | `String(12)` | nie | `manual` (lata przed aplikacją), `year_close` (z zamkniętego roku) |
| | `created_at` | `DateTime(tz)` | nie | `now()` |
| `taxes_loss_use` | `id` PK; `loss_id` FK CASCADE | — | nie | — |
| | `use_year` | `SmallInteger` | nie | rok odliczenia; UNIQUE `(loss_id, use_year)` |
| | `amount` | `Numeric(18,2)` | nie | `CHECK > 0`; suma ≤ `amount_initial` pilnuje serwis |
| | `mode` | `String(10)` | nie | `annual_50` albo `one_time` — **wybór użytkownika**, dlatego zapisany |

UNIQUE `(owner_id, loss_year, pool)`; indeks `(owner_id, pool, loss_year)`. Straty roku bieżącego są wyliczane, nie zapisywane, dopóki użytkownik nie zamknie roku (5.5).

### 5.2 `taxes_lot_attribute` — flagi Partii (E6.1)

Odpowiedź na „gdzie leżą ipo_relief, gift, inheritance”: **w `taxes`, kluczowane `origin_operation_id`** (pierwotny zakup), nie w `portfolios_lot`. Powód: `portfolios_lot` jest przebudowywana (`id` niestabilne), a flagi to dane wpisane przez użytkownika; `portfolios_operation.id` jest stabilne. `portfolios` nie czyta tej tabeli (kierunek `taxes → portfolios`); `taxes` łączy zużycie Partii (serwis `portfolios` zwraca `origin_operation_id`) z atrybutami po tym kluczu.

| Kolumna | Typ | Null | Domyślne | Uwagi |
|---|---|---|---|---|
| `origin_operation_id` | `BigInteger` | nie | — | PK; FK `portfolios_operation.id` ON DELETE CASCADE |
| `acquisition_kind` | `String(12)` | nie | `'purchase'` | `purchase`, `gift`, `inheritance`; `CHECK` |
| `ipo_relief` | `Boolean` | nie | `false` | ulga IPO (art. 21 ust. 1 pkt 105a) |
| `ipo_admission_date` | `Date` | tak | `NULL` | początek 3-letniego biegu; wymagana, gdy `ipo_relief` (`CHECK`) |
| `cost_override` | `Numeric(18,2)` | tak | `NULL` | PLN; darowizna: `0` wg reguły z dowodu, spadek: koszt spadkodawcy; `NULL` = koszt z Partii |
| `updated_at` | `DateTime(tz)` | nie | `now()` | — |

`origin_operation_id` jest niezmienny przy przelewie papierów i splicie (doc 07, 5.6), więc flagi „podążają” za Partią bez dodatkowego mechanizmu (E2.3, E8.1); wymiany (`symbol_change`, `spin_off`) — otwarty punkt 6.

### 5.3 `taxes_account_setting` — ustawienia podatkowe rachunku (E6.2)

Data zdarzenia podatkowego (`tax_date_basis`, `settlement_lag_days`) leży w `portfolios_portfolio` (doc 07, 5.1; D12) i jest czytana przez serwis — nie jest tu duplikowana.

| Kolumna | Typ | Null | Domyślne | Uwagi |
|---|---|---|---|---|
| `portfolio_id` | `BigInteger` | nie | — | PK; FK `portfolios_portfolio.id` CASCADE |
| `broker_country` | `String(2)` | tak | `NULL` | kraj brokera (PIT/ZG, podział krajowe/zagraniczne) |
| `issues_pit8c` | `Boolean` | nie | `false` | rozbicie „krajowe z PIT-8C” vs „zagraniczne / bez PIT-8C” (E6.2) |

Wiersz tworzy się leniwie; rachunki IKE/IKZE/PPK/PPE/OIPE są wyłączone z raportu na podstawie `account_type`, nie tej tabeli (E6.1).

### 5.4 `taxes_year_parameter` — parametry roczne (globalne, D14)

| Kolumna | Typ | Null | Domyślne | Uwagi |
|---|---|---|---|---|
| `tax_year` | `SmallInteger` | nie | — | PK |
| `pit_rate_pct` | `Numeric(5,2)` | nie | `19.00` | stawka dla pul a, b, c |
| `loss_lump_cap` | `Numeric(18,2)` | nie | `5000000.00` | limit jednorazowego odliczenia straty (E6.5) |
| `rounding_rule_30a` | `String(16)` | nie | `'grosz_up'` | `grosz_up` albo `zloty_half_up` — reguła zaokrąglenia podatku z art. 30a jako parametr, bo źródła są sprzeczne ([dowód](../../research/04_rynek_pl_podatki_i_brokerzy.md), E6.2) |

### 5.5 Raport roczny — liczony na żądanie, migawka na żądanie

**[propozycja]** Raport PIT-38 (E6.2) jest **liczony na żądanie** z Partii, zużycia, kursów i rejestru strat; nie ma tabel pośrednich z wynikiem. Powód: P3 — wynik jest pochodną Operacji; zapisany raport musiałby być unieważniany przy każdej edycji historii. Wyjątek: użytkownik może zapisać **migawkę** złożonej wersji.

| Kolumna `taxes_report_snapshot` | Typ | Null | Uwagi |
|---|---|---|---|
| `id` PK; `owner_id` FK | — | nie | — |
| `tax_year` | `SmallInteger` | nie | — |
| `payload` | `JSONB` | nie | pełny raport (pozycje, partie, kursy, numery tabel NBP, założenia, adnotacja „szkic”) |
| `input_hash` | `String(64)` | nie | hash wejść (Operacje, parametry roku) — wykrycie, że historia zmieniła się po migawce |
| `is_year_closed` | `Boolean` | nie (`false`) | `true` = zamknięcie roku: strata roku przechodzi do `taxes_loss` (`source='year_close'`) |
| `created_at` | `DateTime(tz)` | nie | `now()` |

Indeks `(owner_id, tax_year, created_at DESC)`. Czytają: `taxes` (własne), `planning` (szacunek podatku przy rebalancingu, E9.2 — przez serwis `taxes`), `notifications` — nie (zależność usunięta, sekcja 2).

## 6. Moduł `planning` (E9)

Cel (Portfel albo Grupa) zapisany jako para `portfolio_id` / `group_id` z `CHECK` „dokładnie jedno”. Czyta `portfolios` (wartości, alokacje, Grupy), `taxes` (szacunek podatku, E9.2), `assets` (Klasy, tagi) wyłącznie przez serwisy.

### 6.1 `planning_model_portfolio` + `planning_model_target` — portfel wzorcowy (E9.1)

| Tabela | Kolumna | Typ | Null | Uwagi |
|---|---|---|---|---|
| `planning_model_portfolio` | `id` PK; `owner_id` FK `users.id`; `name` `String(100)` | — | nie | UNIQUE `(owner_id, name)` |
| | `portfolio_id` / `group_id` | `BigInteger` | tak / tak | FK `portfolios_portfolio.id` / `portfolios_group.id` CASCADE; `CHECK` dokładnie jedno |
| | `dimension` | `String(10)` | nie | `class`, `tag`, `asset` (E9.1) |
| | `band_abs_pp` / `band_rel_pct` | `Numeric(7,4)` | tak / tak | domyślne pasma modelu: bezwzględne (pp) i względne (%); `CHECK` co najmniej jedno |
| | `created_at`, `updated_at` | `DateTime(tz)` | nie | `now()` |
| `planning_model_target` | `id` PK; `model_id` FK CASCADE | — | nie | — |
| | `asset_class_id` / `tag_id` / `asset_id` | `BigInteger` | tak | FK `assets_assetclass` / `assets_tag` / `assets_asset`; `CHECK` dokładnie jedno i zgodne z `dimension` (serwis) |
| | `target_pct` | `Numeric(7,4)` | nie | `CHECK BETWEEN 0 AND 100`; suma ≤ 100 pilnuje serwis (reszta = gotówka) |
| | `band_abs_pp` / `band_rel_pct` | `Numeric(7,4)` | tak | nadpisanie pasma modelu dla pozycji |

Unikalność celu: trzy indeksy częściowe `UNIQUE (model_id, <kolumna>) WHERE <kolumna> IS NOT NULL`. Przykład z planu: odchylenie 6 pp przy paśmie 5 pp → poza pasmem; 5% przy celu 4% i paśmie względnym 25% → w normie (E9.1). Odchylenie liczy serwis `planning`; `notifications` odczytuje je przez ten serwis (alert).

### 6.2 `planning_goal` — cel inwestycyjny (E9.3, E9.5)

| Kolumna | Typ | Null | Domyślne | Uwagi |
|---|---|---|---|---|
| `id`, `owner_id` | `BigInteger` | nie | — | PK, FK `users.id` |
| `name` | `String(100)` | nie | — | UNIQUE `(owner_id, name)` |
| `portfolio_id` / `group_id` | `BigInteger` | tak / tak | `NULL` | jak wyżej; `CHECK` co najwyżej jedno (cel bez kapitału startowego dozwolony) |
| `currency_code` | `String(3)` | nie | — | kod, bez FK |
| `target_amount` | `Numeric(18,2)` | nie | — | `CHECK > 0` |
| `target_date` | `Date` | nie | — | — |
| `monthly_contribution` | `Numeric(18,2)` | nie | `0` | wpłata miesięczna |
| `return_nominal_pct` | `Numeric(7,4)` | nie | — | stopa nominalna |
| `inflation_pct` | `Numeric(7,4)` | tak | `NULL` | `NULL` = bez wersji realnej |
| `volatility_pct` | `Numeric(7,4)` | tak | `NULL` | wejście Monte Carlo (E9.5) |
| `mc_seed` | `Integer` | tak | `NULL` | stały seed → wynik powtarzalny; wyniki symulacji **nie są zapisywane** (liczone na żądanie) |

### 6.3 `planning_fire_scenario` (E9.4)

`id` PK; `owner_id` FK; `name` `String(100)`; `group_id` FK `portfolios_group.id` null (kapitał z Grupy; `NULL` = wszystkie Portfele); `currency_code` `String(3)`; `monthly_expenses` `Numeric(18,2)`; `withdrawal_rate_pct` `Numeric(7,4)`; `inflation_pct` `Numeric(7,4)`; `created_at`. UNIQUE `(owner_id, name)`.

### 6.4 `planning_recurring_template` — szablony operacji cyklicznych (E9.6)

| Kolumna | Typ | Null | Uwagi |
|---|---|---|---|
| `id`, `owner_id` | `BigInteger` | nie | PK, FK `users.id` |
| `portfolio_id` | `BigInteger` | nie | FK `portfolios_portfolio.id` |
| `operation_type` | `String(20)` | nie | np. `deposit` (wpłata na IKE) |
| `asset_id` | `BigInteger` | tak | FK `assets_asset.id` |
| `amount`, `fee` | `Numeric(18,2)` | tak / nie (`0`) | — |
| `currency_id` | `BigInteger` | tak | FK; `NULL` = domyślna przy generowaniu: serwis wpisuje do szkicu **jawnie** walutę waloru (bez waloru — bazową Portfela), doc 07 5.4 |
| `cycle` | `String(10)` | nie | `weekly`, `monthly`, `quarterly`, `yearly` |
| `day_of_cycle` | `SmallInteger` | tak | dzień miesiąca (1–31) lub tygodnia |
| `weekend_rule` | `String(10)` | nie (`'next'`) | `next`, `previous`, `keep` — dzień wolny |
| `starts_on` / `ends_on` | `Date` | nie / tak | — |
| `last_generated_on` | `Date` | tak | granica generowania propozycji |
| `is_active` | `Boolean` | nie (`true`) | — |

**[propozycja]** Propozycja to Operacja `status='draft'` utworzona przez serwis `portfolios` z `external_ref = 'recurring:<template_id>:<data>'` — UNIQUE częściowy `(portfolio_id, external_ref)` (doc 07 5.4) daje idempotencję generowania; akceptacja zmienia status na `posted`. Ten sam mechanizm dla propozycji dywidend i splitów (E8.5) — **bez osobnej tabeli zdarzeń** — i szkiców z e-maila (E10.3). UI: widok `/operations?status=draft` z akcjami `accept`/`void`. Generuje CLI (`planning/entrypoints.py`). Indeks `(is_active, starts_on)`.

## 7. Moduł `notifications` (E10)

Kanały self-hosted (SMTP, ntfy, Telegram); wybór — ADR (plan E10). **Sekrety nie trafiają do bazy** ani do repo.

### 7.1 `notifications_channel`

| Kolumna | Typ | Null | Domyślne | Uwagi |
|---|---|---|---|---|
| `id`, `owner_id` | `BigInteger` | nie | — | PK, FK `users.id` |
| `kind` | `String(10)` | nie | — | `smtp`, `ntfy`, `telegram`, `imap` (wejście E10.3); `CHECK` |
| `name` | `String(60)` | nie | — | UNIQUE `(owner_id, name)` |
| `config` | `JSONB` | nie | `{}` | część jawna: host, port, temat, adres odbiorcy |
| `secret_ref` | `String(60)` | tak | `NULL` | **nazwa zmiennej środowiskowej** z sekretem (hasło, token bota) — **[propozycja]** zgodnie z regułą security-checklist (sekrety w env) |
| `is_enabled` | `Boolean` | nie | `true` | — |
| `created_at` | `DateTime(tz)` | nie | `now()` | — |

### 7.2 `notifications_alert_rule` (E10.1)

| Kolumna | Typ | Null | Domyślne | Uwagi |
|---|---|---|---|---|
| `id`, `owner_id` | `BigInteger` | nie | — | PK, FK |
| `name` | `String(100)` | nie | — | — |
| `rule_type` | `String(24)` | nie | — | `price_above`, `price_below`, `change_from_avg_cost`, `change_from_52w_high`, `daily_change`, `portfolio_drawdown`; `CHECK`; `model_deviation` (pasmo E9.1) **[propozycja]** jako 7. typ |
| `asset_id` | `BigInteger` | tak | `NULL` | FK `assets_asset.id`; wymagane dla typów cenowych |
| `portfolio_id` | `BigInteger` | tak | `NULL` | FK `portfolios_portfolio.id`; dla `portfolio_drawdown` |
| `model_id` | `BigInteger` | tak | `NULL` | FK `planning_model_portfolio.id`; dla `model_deviation` |
| `threshold` | `Numeric(18,9)` | nie | — | próg: cena albo procent wg `threshold_unit` |
| `threshold_unit` | `String(5)` | nie | — | `price`, `pct` |
| `repeat_mode` | `String(10)` | nie | `'once'` | `once`, `repeat` |
| `state` | `String(10)` | nie | `'armed'` | **uzbrojony** `armed` / **wyzwolony** `triggered` / `disabled` |
| `last_triggered_at` | `DateTime(tz)` | tak | `NULL` | ostatnie wyzwolenie |
| `last_value` | `Numeric(18,9)` | tak | `NULL` | wartość w chwili wyzwolenia |
| `last_evaluated_at` | `DateTime(tz)` | tak | `NULL` | — |
| `channel_id` | `BigInteger` | tak | `NULL` | FK `notifications_channel.id` SET NULL; `NULL` = wszystkie włączone |
| `created_at` | `DateTime(tz)` | nie | `now()` | — |

Przejścia stanu (E10.1): `armed → triggered` przy przekroczeniu progu (jedno wyzwolenie); `triggered → armed` dopiero po powrocie wartości poniżej progu (`repeat`) albo `triggered → disabled` (`once`). Wymagane `CHECK` zgodny z `rule_type` (który FK niepusty) — w serwisie, bo zależy od typu. Indeksy: `(state, rule_type)` częściowy `WHERE state = 'armed'` (ścieżka CLI po odświeżeniu cen), `(asset_id)`, `(portfolio_id)`. Ewaluacja: `notifications/entrypoints.py` po `refresh-prices` (ADR-0002); ceny przez serwis `assets` (`find_close`), wartości Portfela przez serwis `portfolios`.

### 7.3 `notifications_report_schedule` (E10.2)

`id` PK; `owner_id` FK; `period` `String(10)` (`weekly`, `monthly`); `day_of_period` `SmallInteger`; `channel_id` FK SET NULL; `sections` `JSONB` (lista: wartość, zysk, TWR vs benchmark, dywidendy, wykupy E5.2, dywidendy E8.6); `is_enabled` `Boolean` (`true`); `last_sent_at` `DateTime(tz)` null. Treść jest generowana tą samą funkcją co podgląd w UI (E10.2) — **nie jest zapisywana**.

### 7.4 `notifications_delivery` — log dostarczeń

| Kolumna | Typ | Null | Uwagi |
|---|---|---|---|
| `id`, `owner_id` | `BigInteger` | nie | PK, FK `users.id` |
| `rule_id` | `BigInteger` | tak | FK `notifications_alert_rule.id` ON DELETE SET NULL |
| `schedule_id` | `BigInteger` | tak | FK `notifications_report_schedule.id` ON DELETE SET NULL; dokładnie jedno z `rule_id`/`schedule_id` (`CHECK` poza usuniętymi) |
| `channel_id` | `BigInteger` | tak | FK SET NULL |
| `subject` | `String(200)` | nie | bez kwot, gdy włączony tryb prywatności (E11.2) **[propozycja]** |
| `status` | `String(10)` | nie | `sent`, `failed`, `skipped` |
| `attempts` | `SmallInteger` | nie (`1`) | — |
| `error` | `String(200)` | tak | skrót błędu, bez sekretów |
| `dedupe_key` | `String(100)` | tak | UNIQUE częściowy — jedno wyzwolenie = jedna dostawa przy ponowieniu zadania |
| `created_at` / `sent_at` | `DateTime(tz)` | nie / tak | — |

Indeksy: `(owner_id, created_at DESC)`, `(rule_id, created_at DESC)`. Retencja logu (np. 180 dni) — otwarty punkt.

## 8. Czytelnicy i serwisy — zestawienie (ADR-0006)

| Tabela | Zapisuje (serwis) | Czyta spoza modułu (przez serwis) |
|---|---|---|
| `security_api_token` | `security` | — |
| `portfolios_import_*` | `portfolios` (serwis importu) | — (IMAP tworzy Operację `draft` przez serwis `portfolios`) |
| `portfolios_account_limit` | `portfolios` (CLI) | — |
| `taxes_loss*`, `taxes_account_setting`, `taxes_year_parameter`, `taxes_report_snapshot` | `taxes` | `planning` (szacunek podatku) |
| `taxes_lot_attribute` | `taxes` | — (FK do `portfolios_operation`, bez odczytu przez `portfolios`) |
| `planning_*` | `planning` | `notifications` (odchylenie od wzorca, przez port) |
| `notifications_*` | `notifications` | — |

## Otwarte punkty

| # | Punkt | Blokuje |
|---|---|---|
| 1 | ADR kierunków modułów (sekcja 2: `taxes`, `planning`, `notifications`, dług `core_data` ↔ `security`) i portu importu w `core/` | E4.1, E6, E9, E10 |
| 2 | **[propozycja]** Hash tokenów API SHA-256 + pokazanie jawnego tokenu raz; throttling `last_used_at` | E10.4 |
| 3 | **[propozycja]** Plik w Paczce (`LargeBinary`, limit 10 MB), UNIQUE `(owner_id, sha256)` — ponowny plik zwraca istniejącą Paczkę | E4.1, E11.3 |
| 4 | **[propozycja]** Szkic importu w `portfolios_import_row`; Operacja `draft` dla propozycji (E8.5, E9.6, E10.3); `resolution` wiersza (`created`/`skipped`) | E4.1 |
| 5 | **[propozycja]** Nadpisania po `match_key` + `field`; zakres „białej listy” pól | E4.1 |
| 6 | **[propozycja]** Flagi Partii w `taxes_lot_attribute` po `origin_operation_id` (przelew i split ją zachowują); zachowanie flag przy wymianie (`symbol_change`, `spin_off`) do ADR | E6.1, E8.1 |
| 7 | **[propozycja]** Raport roczny liczony na żądanie + migawka na żądanie; `year_close` tworzy straty roku | E6.2, E6.5 |
| 8 | Czy pula c (art. 30a) może mieć przenoszoną stratę — plan i dowód milczą; `taxes_loss.pool` dopuszcza dziś tylko `a`,`b` | E6.1 |
| 9 | **[propozycja]** Limity IKE/IKZE w `portfolios_account_limit` (nie `taxes`); wybór wariantu IKZE per Portfel nieustalony; wartości z dowodu | E5.6 |
| 10 | **[propozycja]** Propozycje cykliczne jako Operacje `draft` z `external_ref` | E9.6 |
| 11 | **[propozycja]** Sekrety kanałów tylko w zmiennych środowiskowych (`secret_ref`); wybór kanałów i IMAP — ADR | E10.1–E10.3 |
| 12 | **[propozycja]** `model_deviation` jako typ reguły alertu; retencja logu dostarczeń | E9.1, E10.1 |
| 13 | Format eksportu myfund i pliki brokerów (XTB, mBank, IBKR, DEGIRO, Trading212, Revolut) — **brak próbek od właściciela**; kolumny `portfolios_import_row` są wspólnym mianownikiem i mogą wymagać rozszerzenia po obejrzeniu plików; PIT-8C do testów E6.2 | E4.2a, E4.3, E6.2 |
| 14 | Kontrakty API (ścieżki, koperty, kody błędów) — osobny dokument | wszystkie |

## Zmiany względem poprzedniej wersji

| Zmiana | Źródło |
|---|---|
| Import wg kanonu: plik w `portfolios_import_batch` (`parser_id`, `sha256` UNIQUE → istniejąca Paczka), bez `portfolios_import_file` | B |
| `portfolios_import_row`: `raw_cells`, `payload`, `row_status` z `skip`, `dedup_key`, `match_key`, `resolution`, `fx_rate`, `settlement_date`, `external_ref` `String(120)`; nadpisania jako `match_key`/`field`/`value` | B |
| Błąd cofnięcia `IMPORT_BATCH_HAS_EDITS`; paginacja `limit`/`offset` z filtrem `row_status` | B, C |
| Zależności: `planning→assets`, `notifications→planning`, usunięte `notifications→taxes`; dług `core_data` ↔ `security` | C |
| `taxes_lot_attribute` po `origin_operation_id`; `variant` `regular` | A2, A8 |
| Szkice jako Operacje `draft` (dywidendy, splity, cykliczne, e-mail), jawne `currency_id` szablonu | C, A4 |
