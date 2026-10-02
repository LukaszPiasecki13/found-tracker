---
id: be-target-schema-core
status: draft
type: mixed
scope: backend/target-schema
last_reviewed: 2026-10-02
---

# Jaki jest docelowy schemat danych modułów `core_data`, `assets` i `portfolios`?

> **Projekt docelowy (L2, draft).** Opisuje stan docelowy wynikający z roadmapy ([plan](../../plans/02_roadmapa_funkcjonalna.md)), nie stan kodu — ten opisują dokumenty modułów i kod. Obowiązuje po akceptacji ADR-ów, na które się powołuje.

Stan dzisiejszy: [`02_core_data_module.md`](./02_core_data_module.md), [`04_assets_module.md`](./04_assets_module.md), [`05_portfolios_module.md`](./05_portfolios_module.md). Moduły `security`, `taxes`, `planning`, `notifications` i paczki importu: [`08_schemat_danych_nowe_moduly.md`](./08_schemat_danych_nowe_moduly.md). Kroki: [E0–E5](../../plans/03_roadmapa_etapy_E0-E5.md), [E6–E11](../../plans/04_roadmapa_etapy_E6-E11.md); decyzje D1–D16: [plan](../../plans/02_roadmapa_funkcjonalna.md). Oznaczenie **[propozycja]** = decyzja, której plan nie rozstrzyga (zebrane w „Otwarte punkty”). Pojęcia **Partia**, **Grupa portfeli**, **Przelew**, **Przewalutowanie**, **Kurs podatkowy**, **Typ rachunku** są proponowane (D3) i nie ma ich jeszcze w [`CONTEXT.md`](../../business/CONTEXT.md).

## 1. Mapa: moduł → tabele → kroki planu

| Moduł | Tabele istniejące (zmiany) | Tabele nowe | Kroki |
|---|---|---|---|
| `core_data` | `users` (+`is_owner`) | `core_data_user_settings` | E0.6, E0.9, D14 |
| `assets` | `assets_asset`, `assets_currency`, `assets_assetclass` | `assets_price`, `assets_fx_rate`, `assets_listing`, `assets_rate_series`, `assets_rate_value`, `assets_watchlist`, `assets_tag`, `assets_asset_tag`, `assets_bond_series`, `assets_bond_rate_period` | E1.1–E1.9, E3.3, E5.1 |
| `portfolios` | `portfolios_portfolio`, `portfolios_operation`, `portfolios_position` | `portfolios_group`, `portfolios_group_member`, `portfolios_commission_rule`, `portfolios_cash_balance`, `portfolios_auto_flow`, `portfolios_operation_tag`, `portfolios_lot`, `portfolios_lot_consumption`, `portfolios_daily`, `portfolios_position_daily` | E2.0–E2.7, E3.1–E3.8, E7.4, E5.1 |
| `portfolios` (import), `security`, `taxes`, `planning`, `notifications` | — | patrz [doc 08](./08_schemat_danych_nowe_moduly.md) | E4, E6, E9, E10 |

## 2. Konwencje

| Zasada | Reguła |
|---|---|
| Nazwy | tabele `<moduł>_<nazwa>` w liczbie pojedynczej jak dziś (`assets_asset`, `portfolios_operation`); wyjątek istniejący: `users` (bez zmiany nazwy — migracje tylko autogenerate) |
| Typy | kwoty `Numeric(18,2)`; ceny, ilości, kursy, współczynniki `Numeric(18,9)`; `twr_index` `Numeric(24,12)`; daty zdarzeń `Date`; momenty `DateTime(timezone=True)` ([ADR-0010](../adr/0010-decimal-i-precyzja-pieniedzy.md)) |
| Klucze | `id BigInteger` PK; FK jak w kodzie; `owner_id` → `users.id` w danych osobistych (portfel, grupa, lista obserwowanych, ustawienia); dane referencyjne (walory, ceny, tagi, serie) są globalne w instancji (D14) |
| Dane pochodne | tabele przebudowywane z Operacji (`portfolios_position`, `_lot`, `_lot_consumption`, `_cash_balance`, `_auto_flow`, `_daily`, `_position_daily`) **nie są celem FK z tabel z danymi użytkownika** — ich `id` nie są stabilne po `rebuild`; odwołania idą do `portfolios_operation.id` (P3, D16) |
| Migracje | wyłącznie `alembic revision --autogenerate`; nowa kolumna `nullable` albo z `server_default`; zaostrzenie do `NOT NULL` dopiero w osobnej migracji po `rebuild-all` (sekcja 7); nowy model w `infrastructure/sql/models_registry.py` |
| Wartości wyliczeniowe | `String(n)` + `CheckConstraint` (nie `Enum` PG — dodanie wartości wymagałoby ręcznej migracji) |
| Granice modułów | FK między modułami wolno (tak jest dziś: `portfolios_operation.asset_id`); **odczyt i zapis wyłącznie przez serwisy** ([ADR-0006](../adr/0006-cross-module-wylacznie-przez-serwisy.md)) |

## 3. Moduł `core_data`

### 3.1 `users` (istnieje: `core_data/models/user.py:7-13`)

| Kolumna | Dziś | Docelowo | Null | Domyślne | Źródło |
|---|---|---|---|---|---|
| `id`, `email` `String(254)` unikalny, `password_hash` `String(128)`, `is_active` | jak w kodzie | bez zmian | — | — | — |
| `is_owner` | brak | `Boolean` — właściciel instancji; tylko on zapisuje dane globalne (walory, ceny ręczne, tagi, serie) | nie | `server_default false` | D14, E0.6 |

[propozycja] Istniejące konto dostaje `is_owner=true` komendą CLI z `core_data/entrypoints.py` (E0.6 „pierwsze konto z CLI”), nie w migracji (zakaz ręcznej edycji). Do czasu wykonania komendy zapisy globalne są odrzucane kodem `OWNER_REQUIRED`.

### 3.2 `core_data_user_settings` (nowa, E0.9)

Jeden wiersz na użytkownika. Waluta jest zapisana jako **kod**, nie FK — `core_data` nie zależy od `assets` (ADR-0006; luka z przeglądu).

| Kolumna | Typ | Null | Domyślne | Klucz / ograniczenie | Źródło |
|---|---|---|---|---|---|
| `id` | `BigInteger` | nie | — | PK | — |
| `user_id` | `BigInteger` | nie | — | FK `users.id`, UNIQUE | E0.9 |
| `display_currency_code` | `String(3)` | nie | `'PLN'` | walidacja istnienia w `assets_currency` w serwisie kontraktu | E0.9, E3.4 |
| `timezone` | `String(40)` | nie | `'Europe/Warsaw'` | nazwa IANA, walidowana w serwisie | E0.9, D13 |
| `stale_price_days` | `SmallInteger` | nie | `7` | `CHECK >= 1` | E0.9, E1.7 |
| `risk_free_series_code` | `String(40)` | tak | `NULL` (= stopa referencyjna NBP) | kod z `assets_rate_series.code`, bez FK | E7.2 |
| `updated_at` | `DateTime(tz)` | nie | `now()` | — | — |

Wiersz tworzy się leniwie przy pierwszym `GET`.

## 4. Moduł `assets`

### 4.1 `assets_asset` (istnieje: `assets/models/assets.py:15-39`)

| Kolumna | Dziś | Docelowo | Null | Domyślne | Klucz | Źródło |
|---|---|---|---|---|---|---|
| `id`, `ticker` `String(20)` UNIQUE+index, `name` `String(100)`, `currency_id`, `sector` `String(100)`, `exchange` `String(50)`, `updated_at` | jak w kodzie | bez zmian; `exchange` zostaje tekstem wolnym (tylko wyświetlanie), logika „giełda zagraniczna” (E0.8) opiera się na `mic`/`country` | — | — | — | E1.3 |
| `asset_class_id` | NOT NULL FK `assets_assetclass` | bez zmian (**[propozycja]** relacja do `asset_type` niżej) | nie | — | FK | E3.3 |
| `current_price` | `Numeric(18,9)` NOT NULL, default 0 | **pochodna** (cache ostatniej ceny z `assets_price`) — patrz sekcja 6 | nie | `0` | — | E1.1, E1.4 |
| `isin` | brak | `String(12)` | tak | `NULL` | UNIQUE (wiele `NULL` dozwolone w PG) | E1.3, E4.1 |
| `mic` | brak | `String(4)` — kod giełdy ISO 10383 | tak | `NULL` | — | E1.3 |
| `country` | brak | `String(2)` — ISO 3166 kraj emitenta | tak | `NULL` | — | E1.3, E3.3 |
| `asset_type` | brak | `String(20)`: `stock`, `etf`, `fund`, `treasury_bond`, `bond`, `crypto`, `currency`, `commodity`, `deposit`, `user_asset` | nie | `'user_asset'` | `CHECK` na zbiór | E1.3 |
| `archived_at` | brak | `DateTime(tz)` — walor z historią cen lub operacjami tylko archiwizowany | tak | `NULL` | indeks częściowy `WHERE archived_at IS NULL` | D15 |
| `last_price_change_at` | brak | `Date` — **data najstarszej ceny zmienionej** od ostatniego potwierdzenia przez konsumenta (sekcja 4.3) | tak | `NULL` | — | D7, E2.5 |
| `provider_symbol` | brak | tymczasowe `String(40)` z E0.5; po E1.2 CLI kopiuje do `assets_listing` i kolumna znika (autogenerate) | tak | `NULL` | — | E0.5, E1.2 |

**[propozycja] `asset_type` ↔ `assets_assetclass`.** Dwie osie, dwa cele:

| Oś | Kto ją ustala | Do czego służy | Zbiór |
|---|---|---|---|
| `asset_type` (kolumna) | system / import | zachowanie: wycena (obligacja per partia, lokata), dostawca, domyślna prowizja, podatek | zamknięty (`CHECK`) |
| Klasa waloru (`assets_assetclass`, CRUD w API — `name` `String(20)` UNIQUE, `asset_classes.py:15-16`) | użytkownik | alokacja „wg Klas” (E3.3, E9.1), kolor/etykieta | otwarty, dziś |

Powód: Klasa jest już publicznym słownikiem z CRUD; zamiana jej w stały enum łamie API i dane. `asset_type` bez FK do Klasy; przy tworzeniu waloru serwis podpowiada Klasę z `asset_type` (mapowanie w konfiguracji, nie w schemacie). Alternatywa odrzucona: `asset_type` jako kolumna `assets_assetclass.kind` — jedna Klasa musiałaby mieć jeden typ, a użytkownicy grupują np. „ETF-y i fundusze” razem.

Indeksy: istniejące `ix_assets_asset_id`, `ix_assets_asset_ticker` (UNIQUE) — `ticker` zostaje globalnie unikalny **[propozycja]**; ten sam symbol na dwóch giełdach rozróżnia się sufiksem tickera (np. `.WA`, E0.5), a nie kluczem złożonym. Nowe: `(asset_type)`, `(isin)` UNIQUE, `(last_price_change_at) WHERE last_price_change_at IS NOT NULL`.

### 4.2 `assets_currency` i `assets_assetclass` (istnieją)

| Tabela.kolumna | Dziś | Docelowo | Źródło |
|---|---|---|---|
| `assets_currency.exchange_rate` `Numeric(18,9)` NOT NULL default 1 | kurs względem waluty systemowej (USD) | **pochodna**, sekcja 6 | E0.1, E1.1 |
| `assets_currency.base_currency_id` FK self, nullable | tylko CRUD, nie używana w wycenie (`assets/services/currencies.py:44-67`) | **wygaszana**, sekcja 6 | E1.1 |

### 4.3 `assets_price` (nowa, E1.1, D7)

Ceny zamknięcia **nieskorygowane** (splity są Operacjami, E8.1).

| Kolumna | Typ | Null | Domyślne | Klucz / ograniczenie |
|---|---|---|---|---|
| `id` | `BigInteger` | nie | — | PK |
| `asset_id` | `BigInteger` | nie | — | FK `assets_asset.id` |
| `price_date` | `Date` | nie | — | — |
| `close` | `Numeric(18,9)` | nie | — | `CHECK > 0` |
| `currency_id` | `BigInteger` | nie | — | FK `assets_currency.id` (waluta notowania z dostawcy; zwykle = waluta waloru) |
| `source` | `String(20)` | nie | — | kod dostawcy (`yahoo`, `stooq`, `nbp`…) albo `manual` |
| `is_synthetic` | `Boolean` | nie | `false` | wiersz wyliczony (np. wycena obligacji E5.1, lokaty E5.5), nie notowanie |
| `fetched_at` | `DateTime(tz)` | nie | `now()` | — |

Ograniczenie: UNIQUE `(asset_id, price_date, source)`. Indeks: `(asset_id, price_date DESC)`.

**Pierwszeństwo źródeł [propozycja]** (luka E1.2): `manual` zawsze wygrywa (E1.5); pozostałe wg `assets_listing.priority` rosnąco. Wiersze różnych źródeł współistnieją; `find_close(asset, date)` wybiera jeden i zwraca `source`, `is_synthetic`, flagę forward-fill (E1.1, E1.7). Forward-fill liczy się przy odczycie — nie zapisuje.

**`last_price_change_at` (D7, E2.5) — semantyka [propozycja].** Zapis do `assets_price` o dacie `d` **starszej od najnowszej istniejącej** (korekta historii, wpis ręczny wstecz) ustawia `assets_asset.last_price_change_at = LEAST(current, d)`; dopisanie ceny po najnowszej dacie nie zmienia znacznika. Konsument (`portfolios/entrypoints.py`) czyta znacznik przez serwis `assets`, unieważnia snapshoty portfeli posiadających walor od tej daty, a po przeliczeniu wywołuje serwis „potwierdź” z warunkiem `WHERE last_price_change_at = :odczytana` (compare-and-set → `NULL`). Zmiana w trakcie przeliczenia zostaje, bo nie zgadza się z odczytaną wartością. Znacznik jest **per walor**, nie globalny. Analogiczny znacznik kursów: `assets_currency.fx_changed_from` `Date` null (ta sama semantyka, **[propozycja]**; dla unieważnienia po zmianie `assets_fx_rate`).

### 4.4 `assets_fx_rate` (nowa, E1.1, D5)

| Kolumna | Typ | Null | Domyślne | Klucz / ograniczenie |
|---|---|---|---|---|
| `id` | `BigInteger` | nie | — | PK |
| `from_currency_id` | `BigInteger` | nie | — | FK `assets_currency.id` |
| `to_currency_id` | `BigInteger` | nie | — | FK `assets_currency.id`, `CHECK from <> to` |
| `rate_date` | `Date` | nie | — | — |
| `rate` | `Numeric(18,9)` | nie | — | `CHECK > 0`; ile `to` za 1 `from` |
| `source` | `String(20)` | nie | — | `nbp`, `yahoo`, `manual` |
| `table_no` | `String(32)` | tak | `NULL` | numer tabeli NBP (np. `187/A/NBP/2026`) — wymagany dla `source='nbp'` (kurs podatkowy) |
| `is_synthetic` | `Boolean` | nie | `false` | — |

UNIQUE `(from_currency_id, to_currency_id, rate_date, source)`; indeks `(from_currency_id, to_currency_id, rate_date DESC)`. **[propozycja]** Pary: przechowujemy tylko pary notowane u źródła (NBP: waluta → PLN); kursy krzyżowe (USD→EUR) liczy serwis przy odczycie przez PLN (luka E1.1 „które pary”). Trzy kursy z D5: brokera = `portfolios_operation.fx_rate`, wyceny = ta tabela, podatkowy = `fx_rate_tax` Operacji (kopiowany z tej tabeli z `table_no`).

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

UNIQUE `(asset_id, provider)` i `(provider, symbol)`.

### 4.6 `assets_rate_series` + `assets_rate_value` (nowe, E1.6)

Szeregi stóp: stopa referencyjna NBP, CPI GUS r/r. CPI wyłącznie do zwrotu realnego i prognoz — **nie** do wyceny obligacji (E1.6, E5.1).

| Tabela | Kolumna | Typ | Null | Uwagi |
|---|---|---|---|---|
| `assets_rate_series` | `id` PK; `code` `String(40)` UNIQUE (`nbp_ref`, `cpi_gus_yoy`); `name` `String(100)`; `unit` `String(10)` (`percent`); `frequency` `String(10)` (`daily`, `monthly`); `source` `String(20)` | — | — |
| `assets_rate_value` | `id` PK; `series_id` FK; `valid_from` `Date`; `value` `Numeric(12,6)`; `fetched_at` `DateTime(tz)` | nie | UNIQUE `(series_id, valid_from)`; wartość obowiązuje od `valid_from` do następnego wiersza |

### 4.7 `assets_watchlist` (nowa, E1.8)

Dane osobiste, więc `owner_id` (nie globalne jak walory).

| Kolumna | Typ | Null | Klucz |
|---|---|---|---|
| `id` | `BigInteger` | nie | PK |
| `owner_id` | `BigInteger` | nie | FK `users.id` |
| `asset_id` | `BigInteger` | nie | FK `assets_asset.id` |
| `note` | `String(200)` | tak | — |
| `added_at` | `DateTime(tz)` | nie (`now()`) | — |

UNIQUE `(owner_id, asset_id)`.

### 4.8 Tagi: `assets_tag`, `assets_asset_tag` (nowe, E2.7, E3.3)

Tagi globalne w instancji (D14). **[propozycja]** Tabela tagów w `assets` (tag klasyfikuje w pierwszej kolejności Waloru — alokacja „wg tagów” E3.3, E9.1); powiązanie z Operacją leży w `portfolios` (sekcja 5.9) i wskazuje `assets_tag.id`; `portfolios` czyta tagi przez serwis `assets`.

| Tabela | Kolumny | Ograniczenia |
|---|---|---|
| `assets_tag` | `id` PK; `name` `String(50)`; `color` `String(7)` null; `created_at` | UNIQUE `lower(name)` (indeks funkcyjny) |
| `assets_asset_tag` | `asset_id` FK CASCADE; `tag_id` FK CASCADE | PK `(asset_id, tag_id)`; indeks `(tag_id)` |

### 4.9 Obligacje skarbowe: `assets_bond_series`, `assets_bond_rate_period` (nowe, E5.1)

Seria = Walor (`asset_type='treasury_bond'`, `ticker` = symbol serii, np. `EDO1036`). Wzory wyceny to czyste funkcje w `assets/domain/bonds.py` (E5.1); schemat trzyma **fakty**: parametry serii i ogłoszone stopy. Termin wykupu i początek okresów liczy się **od dnia zakupu** ([dowód](../../research/03_rynek_pl_dane_i_obligacje.md)), więc daty okresów nie są w serii — wynikają z Partii (sekcja 5.6).

| Tabela | Kolumna | Typ | Null | Uwagi |
|---|---|---|---|---|
| `assets_bond_series` | `id` PK; `asset_id` FK UNIQUE | — | nie | jeden Walor = jedna seria |
| | `bond_type` | `String(4)` | nie | `OTS`, `ROR`, `DOR`, `TOS`, `COI`, `EDO`, `ROS`, `ROD`; `CHECK` |
| | `sale_start`, `sale_end` | `Date` | nie | okno sprzedaży oferty (data emisji, E5.1) |
| | `nominal` | `Numeric(18,2)` | nie | domyślnie `100.00` |
| | `term_months` | `SmallInteger` | nie | termin wykupu liczony od zakupu |
| | `first_rate` | `Numeric(9,6)` | nie | stopa 1. okresu z listu emisyjnego (ułamek: `0.0535`) |
| | `margin` | `Numeric(9,6)` | tak | marża od okresu 2 (COI/EDO/ROS/ROD) |
| | `early_redemption_fee` | `Numeric(18,2)` | nie | opłata za wykup przedterminowy wg listu serii (zmienia się w czasie — wartość dotyczy tej serii) |
| | `payout_mode` | `String(12)` | nie | `at_maturity`, `annual`, `monthly`, `capitalized`; `CHECK` |
| | `issue_letter_ref` | `String(60)` | tak | numer/odnośnik listu emisyjnego (źródło faktów) |
| `assets_bond_rate_period` | `id` PK; `series_id` FK CASCADE; `period_no` `SmallInteger` | — | nie | UNIQUE `(series_id, period_no)` |
| | `rate` | `Numeric(9,6)` | nie | **ogłoszona stopa okresu — fakt**, nie liczona z CPI (E5.1) |
| | `announced_on` | `Date` | tak | — |
| | `source_ref` | `String(200)` | tak | URL lub list; bez tego stopa nie przechodzi walidacji ręcznej |

Numer okresu liczy się od dnia zakupu Partii (okres k = k-ty rok od zakupu), więc stopa okresu jest wspólna dla całej serii niezależnie od dnia zakupu — **[propozycja]**, zgodnie z „ogłoszona stopa… nie ulega zmianie” z dowodu. Dla ROR/DOR (okresy krótsze niż rok) `period_no` oznacza kolejny okres od zakupu w tej samej tabeli; reguła dat okresu per typ jest w kodzie domeny. **Ładowanie** [propozycja]: stopy wprowadza się komendą CLI z pliku CSV lub ręcznie (źródło to strona serwisu, bez API); Tabele odsetkowe (PDF) to **wyrocznia testów** (fixture'y), nie dane runtime.

## 5. Moduł `portfolios`

### 5.1 `portfolios_portfolio` (istnieje: `models/portfolio.py:26-67`)

| Kolumna | Dziś | Docelowo | Null | Domyślne | Klucz | Źródło |
|---|---|---|---|---|---|---|
| `id`, `owner_id` FK, `name` `String(100)`, `base_currency_id` FK, `is_active`, `created_at`, `updated_at` | jak w kodzie; UNIQUE `(owner_id, name)` (`unique_portfolio_per_user`) | bez zmian; zmiana `base_currency_id` zablokowana przy istniejących Operacjach | — | — | — | E0.8 |
| `cash_balance` | `Numeric(18,3)` NOT NULL | **pochodna** (cache salda w walucie bazowej Portfela) — sekcja 6 | nie | `0` | — | E2.2 |
| `total_deposited` | `Numeric(18,3)` NOT NULL | **pochodna** — sekcja 6 | nie | `0` | — | E2.2 |
| `account_type` | brak | `String(10)`: `standard`, `ike`, `ikze`, `ppk`, `ppe`, `oipe` (**Typ rachunku**, D1) | nie | `'standard'` | `CHECK` | E2.1, D1 |
| `broker` | brak | `String(60)` | tak | `NULL` | — | E2.1 |
| `tax_date_basis` | brak | `String(10)`: `settlement` albo `trade` — data zdarzenia podatkowego per rachunek (D12) | nie | `'settlement'` | `CHECK` | D12 |
| `settlement_lag_days` | brak | `SmallInteger` — przesunięcie rozrachunku w dniach sesyjnych; `NULL` = domyślne rynku z kalendarza (T+2, E1.9) | tak | `NULL` | `CHECK >= 0` | D12, E1.9 |
| `auto_deposit_mode` | brak | `String(10)`: `off`, `auto` — tryb automatycznych wpłat/wypłat | nie | `'off'` | `CHECK` | E2.2b |
| `last_snapshot_date` | brak | `Date` — ostatni dzień, dla którego `portfolios_daily` jest ważne; unieważnienie cofa go do `dzień − 1` | tak | `NULL` | — | E2.5, E11.7 |

Istniejące wiersze: `account_type='standard'` z `server_default`, reszta `NULL`/domyślne (E2.1 „istniejące Portfele = zwykły”). Indeksy: UNIQUE `(owner_id, name)` bez zmian; `(owner_id, is_active)`.

### 5.2 `portfolios_commission_rule` (nowa, E2.1)

Domyślna prowizja per typ waloru (% + minimum) podpowiadana w formularzu; nie jest księgowana.

| Kolumna | Typ | Null | Klucz / uwagi |
|---|---|---|---|
| `id` | `BigInteger` | nie | PK |
| `portfolio_id` | `BigInteger` | nie | FK CASCADE |
| `asset_type` | `String(20)` | tak | `NULL` = wszystkie typy; wartość z `assets_asset.asset_type` |
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

Kolumny istniejące: `id`; `portfolio_id` FK NOT NULL; `asset_id` FK null; `operation_type` `String(20)`; `quantity`, `price` `(18,9)` default 0; `amount` `(18,2)` null; `fee` `(18,2)` default 0; `fx_rate` `(18,9)` default 1 (broker: waluta waloru → waluta Portfela, `ledger.py:170`); `notes` `Text` null; `operation_date` `DateTime(tz)` NOT NULL + index; `created_at`. Indeks `ix_operation_portfolio_date (portfolio_id, operation_date)`. Wszystkie zostają. Dodawane (D9; wszystkie `nullable` albo `server_default`):

| Kolumna | Typ | Null | Domyślne | Znaczenie | Źródło |
|---|---|---|---|---|---|
| `operation_day` | `Date` | tak (po backfillu → nie) | `NULL` | **dzień operacji w Europe/Warsaw**; kolejność i snapshoty liczone od niego | D13, E2.0 |
| `settlement_date` | `Date` | tak | `NULL` | data rozrachunku; `NULL` = wylicz z `tax_date_basis`/lagu Portfela | D12, E2.3 |
| `currency_id` | `BigInteger` FK `assets_currency.id` | tak | `NULL` | waluta `price`/`amount`/`fee`; **`NULL` = waluta waloru** (operacje z walorem) **lub waluta bazowa Portfela** (wpłata, wypłata, odsetki, opłata, podatek bez waloru) | D9, E2.2 |
| `fx_rate_tax` | `Numeric(18,9)` | tak | `NULL` | **Kurs podatkowy**: NBP tabela A z ostatniego dnia roboczego przed datą zdarzenia podatkowego | D5, D12 |
| `fx_tax_table_no` | `String(32)` | tak | `NULL` | numer tabeli NBP kursu podatkowego | D5 |
| `fx_tax_date` | `Date` | tak | `NULL` | data notowania kursu podatkowego | D5 |
| `counter_portfolio_id` | `BigInteger` FK `portfolios_portfolio.id` | tak | `NULL` | drugi Portfel **Przelewu** | D9, E2.3 |
| `counter_amount` | `Numeric(18,2)` | tak | `NULL` | kwota po stronie przeciwnej (Przelew gotówki, Przewalutowanie) | D9 |
| `counter_currency_id` | `BigInteger` FK | tak | `NULL` | waluta strony przeciwnej | D9 |
| `counter_asset_id` | `BigInteger` FK `assets_asset.id` | tak | `NULL` | walor docelowy: zmiana tickera, zamiana serii, spin-off, prawa poboru | D9, E8.2–E8.4, E5.1 |
| `ratio` | `Numeric(18,9)` | tak | `NULL` | przelicznik nowe:stare (split, scalenie, wymiana); `CHECK > 0` | D9, E8.1 |
| `tax_deductible` | `Boolean` | nie | `false` | opłata (`fee`) jako koszt podatkowy | E2.3 |
| `lot_ref_operation_id` | `BigInteger` FK `portfolios_operation.id` | tak | `NULL` | wskazanie Partii przy sprzedaży = Operacja otwierająca Partię (stabilne, w odróżnieniu od `portfolios_lot.id`) | D2, E2.4 |
| `import_batch_id` | `BigInteger` FK | tak | `NULL` | paczka importu — tabela w [doc 08](./08_schemat_danych_nowe_moduly.md) | D9, E4.1 |
| `external_ref` | `String(100)` | tak | `NULL` | identyfikator z pliku brokera (deduplikacja) | D9, E4.1 |
| `status` | `String(10)` | nie | `'posted'` | `posted`, `draft`, `void` (zaksięgowana/szkic/unieważniona); księga czyta tylko `posted` | D9 |
| `sequence` | `Integer` | nie | `0` | kolejność w dniu; globalna kolejność księgi: `(operation_day, sequence, created_at, id)` | D9, D13 |
| `edited_at` | `DateTime(tz)` | tak | `NULL` | ręczna edycja po zapisie; cofnięcie paczki jest blokowane dla edytowanych (D15) | D15, E4.1 |

**Nowe wartości `operation_type`** (dziś: `buy`, `sell`, `deposit`, `withdrawal`, `dividend` — `domain/enums.py:9-14`; kolumna `String(20)` wystarcza), **[propozycja]** nazwy: `interest`, `fee`, `tax`, `transfer` (z walorem = przelew papierów, bez = przelew gotówki), `fx_exchange` (**Przewalutowanie**), `adjustment`, `split`, `symbol_change`, `spin_off`, `redemption` (wykup i wykup przedterminowy obligacji; `fee` = opłata), `bond_switch`. Źródła: E2.2, E2.3, E8.1–E8.3, E5.1. Dodanie wartości do `CheckConstraint` na `operation_type` = zwykła migracja autogenerate.

**Ograniczenia i indeksy:** `CHECK status IN ('posted','draft','void')`; `CHECK ratio IS NULL OR ratio > 0`; UNIQUE częściowy `(portfolio_id, external_ref) WHERE external_ref IS NOT NULL`. Indeksy: `(portfolio_id, operation_day, sequence, id)` (lista i `rebuild`, E2.7), `(counter_portfolio_id) WHERE counter_portfolio_id IS NOT NULL` (historia Portfela B czyta wiersze A), `(asset_id, operation_day)`, `(import_batch_id) WHERE import_batch_id IS NOT NULL`, `(status)` częściowy `WHERE status <> 'posted'`.

**Przelewy [propozycja]** (BLOCKER z przeglądu): Przelew to **jeden wiersz** w Portfelu źródłowym A z `counter_portfolio_id=B`; księga B czyta go zapytaniem `portfolio_id = B OR counter_portfolio_id = B` jako wpływ. Przelew papierów przenosi Partie A→B z zachowaniem `acquired_on` i kosztu. Przebudowa obejmuje **spójną składową** Portfeli powiązanych przelewami; algorytm i unieważnianie — ADR techniczny (D9, D15), nie schemat.

**`operation_day` vs `operation_date` (D13) [propozycja]:** `operation_date` zostaje `timestamptz` (chwila, z godziną z UI); typ **nie jest zmieniany** (zmiana timestamptz→date bez `USING` użyłaby strefy sesji DB, a ręczna edycja migracji jest zakazana — D16). `operation_day` to nowa kolumna `Date`, wypełniana przez `rebuild-all` konwersją `operation_date AT TIME ZONE 'Europe/Warsaw'`; od tej chwili logika (`metrics.py:74,148` liczy dziś dzień w UTC) czyta `operation_day`. Zaostrzenie do `NOT NULL` — migracja po backfillu. `fx_rate` istniejących wierszy: reguła reinterpretacji w ADR biznesowym D4 (nie tutaj).

### 5.5 `portfolios_position` (istnieje: `models/position.py:26-70`)

Kolumny bez zmian: `portfolio_id`, `asset_id`, `quantity` `(18,9)`, `average_buy_price` `(18,9)`, `average_fx_rate` `(18,9)`, `total_fees` `(18,2)`, `total_dividends` `(18,2)`, `opened_at`, `updated_at`; UNIQUE `unique_position_per_portfolio (portfolio_id, asset_id)`. Status docelowy: **agregat pochodny Partii** (suma `quantity_open`), z `average_buy_price` wyłącznie do prezentacji (D2). Wycena kosztu czyta Partie, nie średnią (dziś `quantity × average_buy_price` — `domain/valuation.py:53`).

**Konflikt: unikalność `(portfolio_id, asset_id)` vs obligacje per Partia (E5.1) — rozwiązanie [propozycja]:** unikalność **zostaje**. Obligacje z różnych dni zakupu tej samej serii to jedna Pozycja (Walor = seria) i wiele Partii w `portfolios_lot` z różnym `acquired_on`; wycena obligacji liczy się per Partia. Alternatywa odrzucona: Pozycja per Partia — łamie FIFO per rachunek (D2), kontrakt API pozycji i test architektury modułów.

### 5.6 `portfolios_lot` (nowa, E2.4) — **Partia**, dane pochodne

| Kolumna | Typ | Null | Domyślne | Uwagi |
|---|---|---|---|---|
| `id` | `BigInteger` | nie | — | PK (niestabilny po `rebuild`) |
| `portfolio_id` | `BigInteger` | nie | — | FK `portfolios_portfolio.id` CASCADE; FIFO obowiązuje w obrębie Portfela = rachunku (D2) |
| `asset_id` | `BigInteger` | nie | — | FK `assets_asset.id` |
| `open_operation_id` | `BigInteger` | nie | — | FK `portfolios_operation.id` CASCADE; Operacja otwierająca (buy, przelew przychodzący, split-wynik) — **klucz biznesowy Partii** |
| `acquired_on` | `Date` | nie | — | data nabycia (przy przelewie papierów zachowana z Portfela źródłowego) |
| `tax_date` | `Date` | nie | — | data zdarzenia podatkowego (rozrachunek wg D12) |
| `quantity_initial` / `quantity_open` | `Numeric(18,9)` | nie | — | `CHECK quantity_open >= 0 AND quantity_open <= quantity_initial` |
| `unit_price` | `Numeric(18,9)` | nie | — | cena jednostkowa w walucie waloru, bez prowizji |
| `cost_local` | `Numeric(18,2)` | nie | — | koszt nabycia pozostałej ilości w walucie waloru, z prowizją |
| `cost_base` | `Numeric(18,2)` | nie | — | jw. w walucie Portfela, po kursie brokera |
| `cost_tax_pln` | `Numeric(18,2)` | tak | `NULL` | jw. w PLN po Kursie podatkowym (`NULL` do czasu publikacji tabeli NBP, E2.3) |
| `fx_rate` / `fx_rate_tax` | `Numeric(18,9)` | nie / tak | `1` / `NULL` | kopie kursów z Operacji (audytowalność kosztu) |
| `closed_on` | `Date` | tak | `NULL` | data wyczerpania Partii |

Indeksy: `(portfolio_id, asset_id, acquired_on, open_operation_id) WHERE quantity_open > 0` (kolejka FIFO), UNIQUE `(open_operation_id)`. Flagi podatkowe Partii (ulga IPO, darowizna, spadek) **nie leżą tu** (dane użytkownika, tabela jest przebudowywana) — `taxes_lot_attribute` w [doc 08](./08_schemat_danych_nowe_moduly.md), klucz `open_operation_id`.

### 5.7 `portfolios_lot_consumption` (nowa, E2.4) — dane pochodne

| Kolumna | Typ | Null | Uwagi |
|---|---|---|---|
| `id` | `BigInteger` | nie | PK |
| `lot_id` | `BigInteger` | nie | FK `portfolios_lot.id` CASCADE |
| `close_operation_id` | `BigInteger` | nie | FK `portfolios_operation.id` CASCADE (sprzedaż, wykup, przelew wychodzący) |
| `closed_on` | `Date` | nie | dzień zamknięcia (`operation_day`) |
| `quantity` | `Numeric(18,9)` | nie | `CHECK > 0` |
| `proceeds_local`, `cost_local`, `fee_local` | `Numeric(18,2)` | nie | w walucie waloru; prowizja sprzedaży rozdzielona proporcjonalnie (E2.4) |
| `proceeds_base`, `cost_base` | `Numeric(18,2)` | nie | w walucie Portfela (kurs brokera) |
| `proceeds_tax_pln`, `cost_tax_pln` | `Numeric(18,2)` | tak | w PLN po Kursie podatkowym (D5); wejście dla `taxes` |

UNIQUE `(lot_id, close_operation_id)`; indeksy `(close_operation_id)`, `(closed_on)`. Zysk zrealizowany = `proceeds − cost − fee` (E2.4); test złoty: [metodyka](../../research/05_metodyka_metryk.md).

### 5.8 `portfolios_cash_balance` + `portfolios_auto_flow` (nowe, E2.2, E2.2b) — dane pochodne

| Tabela | Kolumny | Ograniczenia |
|---|---|---|
| `portfolios_cash_balance` | `id` PK; `portfolio_id` FK CASCADE; `currency_id` FK; `balance` `Numeric(18,2)` null=nie (domyślnie `0`) | UNIQUE `(portfolio_id, currency_id)`; saldo ujemne odrzuca księga (`INSUFFICIENT_CASH`-podobny kod z ledgera), nie `CHECK` |
| `portfolios_auto_flow` | `id` PK; `portfolio_id` FK CASCADE; `trigger_operation_id` FK `portfolios_operation.id` CASCADE; `currency_id` FK; `flow_type` `String(10)` (`deposit`, `withdrawal`); `amount` `Numeric(18,2)`; `flow_day` `Date` | indeks `(portfolio_id, flow_day)`, `(trigger_operation_id)` |

**[propozycja] Automatyczne wpłaty (E2.2b) są pochodne, nie wierszami `portfolios_operation`.** Powód: P3 — Operacje to źródło prawdy; wiersz wygenerowany przez księgę musiałby być kasowany i odtwarzany przy edycji operacji wyzwalającej, a użytkownik mógłby go edytować (konflikt z P3). `rebuild` buduje `portfolios_auto_flow` od zera; TWR/XIRR czytają go jako przepływy zewnętrzne (E2.2b), eksport (E4.5) go pomija. Ostrzeżenie: wymaga ADR, bo zmienia definicję „przepływu zewnętrznego”.

### 5.9 `portfolios_operation_tag` (nowa, E2.7)

`operation_id` FK `portfolios_operation.id` CASCADE; `tag_id` FK `assets_tag.id` CASCADE; PK `(operation_id, tag_id)`; indeks `(tag_id)`. To dane użytkownika (nie pochodne), więc FK do Operacji jest dozwolony.

### 5.10 `portfolios_daily` (nowa, E2.5, D7) — snapshot dzienny, pochodny

Klucz: PK `(portfolio_id, day)`; `portfolio_id` FK CASCADE; `day` `Date` (dzień w strefie z D13). Szereg po dniach kalendarzowych; dni bez sesji mają przeniesioną wycenę (statystyki E7.1 pomijają je przez kalendarz E1.9).

| Kolumna | Typ | Null | Uwagi |
|---|---|---|---|
| `value`, `cash`, `positions_value` | `Numeric(18,2)` | nie | w walucie Portfela, po kursach wyceny dnia |
| `ext_in`, `ext_out` | `Numeric(18,2)` | nie | przepływy zewnętrzne dnia (wpłaty, wypłaty, `portfolios_auto_flow`, przelewy spoza Grupy wg zakresu — E3.1) |
| `income`, `fees`, `taxes` | `Numeric(18,2)` | nie | dochody (dywidendy, odsetki), opłaty, podatki dnia |
| `r_day` | `Numeric(18,12)` | tak | stopa dnia; `NULL` przy wartości początkowej 0 |
| `twr_index` | `Numeric(24,12)` | nie | `Π(1+r)`, `Decimal` (D7, D11) |
| `cum_ext_in`, `cum_ext_out` | `Numeric(18,2)` | nie | skumulowane przepływy — zysk okresu w O(1) ([metodyka](../../research/05_metodyka_metryk.md)) |
| `data_quality` | `String(12)` | nie | `ok`, `stale`, `synthetic`, `missing` (brak ceny przy niezerowej Pozycji — nie wyceniamy cicho na zero) |

### 5.11 `portfolios_position_daily` (nowa, E2.5, E7.4) — pochodna

PK `(portfolio_id, asset_id, day)`; FK CASCADE na `portfolios_portfolio`, FK `assets_asset`.

| Kolumna | Typ | Null | Uwagi |
|---|---|---|---|
| `quantity` | `Numeric(18,9)` | nie | stan na koniec dnia |
| `price_local` | `Numeric(18,9)` | tak | cena zamknięcia w walucie waloru (z `find_close`) |
| `fx` | `Numeric(18,9)` | nie | kurs wyceny waluta waloru → waluta Portfela tego dnia (E7.4) |
| `mv_local` | `Numeric(18,2)` | tak | **wartość w walucie waloru** = `quantity × price_local` (E7.4: rozbicie cena/waluta) |
| `mv_base` | `Numeric(18,2)` | tak | `mv_local × fx`, waluta Portfela |
| `cost_base` | `Numeric(18,2)` | nie | koszt otwartych Partii (E2.4) |
| `flow_in`, `flow_out` | `Numeric(18,2)` | nie | przepływy waloru dnia (zakup/sprzedaż) |
| `r_day`, `twr_index` | `Numeric(18,12)`, `Numeric(24,12)` | tak / nie | stopa i indeks waloru |
| `is_stale`, `is_synthetic` | `Boolean` | nie | z `find_close` |

Indeks: `(asset_id, day)` (alokacje, wykres waloru E3.8). Rozmiar [wniosek]: 30 walorów × 3 650 dni ≈ 110 tys. wierszy na Portfel (liczba z przeglądu) — dlatego `rebuild` zapisuje partiami.

## 6. Kolumny pochodne i wygaszane

| Kolumna | Decyzja [propozycja] | Uzasadnienie | Kiedy usunąć |
|---|---|---|---|
| `portfolios_portfolio.cash_balance` | zostaje jako **cache salda w walucie bazowej Portfela** (linia `portfolios_cash_balance` dla `base_currency_id`); pole API `cash_balance` bez zmiany; sumę wielowalutową liczy serwis kursem wyceny | API (`schemas/portfolios.py`) i `LedgerState.cash_balance` (`ledger.py:105`) to jeden `Decimal`; usunięcie łamie frontend | po E3.4 (kokpit liczy z Salda per waluta), osobnym ADR-em |
| `portfolios_portfolio.total_deposited` | zostaje jako cache = `cum_ext_in − cum_ext_out` ostatniego `portfolios_daily`, przepływy przeliczone **kursem Operacji** na walutę Portfela | w wielu walutach „suma wpłat” wymaga jednego kursu — kurs z momentu wpłaty jest jedyną definicją niezależną od dnia wyceny (reguła do potwierdzenia w ADR D4) | jw. |
| `assets_asset.current_price` | cache ostatniej ceny z `assets_price`; zapisuje go wyłącznie zadanie odświeżania (E1.4); nowe odczyty wyceny idą do `find_close` | ścieżka żądania nie woła dostawcy (E1.4), a bieżąca cena bez historii nie spełnia D7 | po E2.5 |
| `assets_currency.exchange_rate` | cache kursu względem USD do czasu E1.1 (E0.1 liczy kurs krzyżowy z niego, `domain/valuation.py:55-57`); potem z `assets_fx_rate`; nowa waluta **bez kursu** nie dostaje domyślnego 1 — kolumna staje się `nullable`, brak kursu → błąd z `code` | domyślne `1` zafałszowuje wycenę po cichu | po E1.4 |
| `assets_currency.base_currency_id` | wygasza się: żaden kod wyceny jej nie czyta (tylko CRUD `currencies.py:44-67`); usunięcie po sprawdzeniu, że żaden wiersz jej nie używa | historia kursów w `assets_fx_rate` zastępuje relację | E1.1 + zgoda właściciela (usunięcie kolumny z danymi) |

## 7. Polityka migracji (D16, E2.0)

| Krok | Zasada |
|---|---|
| Kształt migracji | jedna migracja `--autogenerate` per krok planu; tylko nowe tabele i kolumny `nullable`/`server_default`; test `alembic check` bez dryfu |
| Wypełnianie danych | komenda `rebuild-all` (`portfolios/entrypoints.py` + `app/cli.py`): `operation_day`, `status='posted'` (z `server_default`), Partie, zużycie, salda per waluta, `portfolios_auto_flow`, snapshoty, `cost_tax_pln` tam, gdzie kurs jest dostępny |
| Idempotencja | `rebuild-all` dwa razy = identyczny stan (DoD 8); kasuje i odtwarza tabele pochodne, nie dotyka `portfolios_operation` poza `operation_day` |
| Zaostrzenie | `operation_day NOT NULL`, `assets_currency.exchange_rate NULL`-owalność, usunięcie `provider_symbol` — osobne migracje po zielonym `rebuild-all` |
| Seed | `seed/seed_data.py` ma zahardkodowany stan (`cash_balance=15000.000` w l.191, `total_dividends=18.50` w l.222), więc kryterium E2.0 „rebuild-all na seed daje stan identyczny z obecnym” jest fałszywe — **seed trzeba naprawić (stan wyliczać replayem) albo zmienić kryterium** |

## 8. Konflikty z istniejącym kodem

| # | Kod dziś | Konflikt | Rozwiązanie |
|---|---|---|---|
| 1 | `Position` UNIQUE `(portfolio_id, asset_id)`, `position.py:66-69` | obligacje per Partia | unikalność zostaje, Partie osobno (5.5) |
| 2 | `valuation.py:53` koszt = ilość × średnia | wycena z Partii | `HoldingLike` czyta Partie; przepisać `test_valuation.py` |
| 3 | `LedgerState.cash_balance` jeden `Decimal` (`ledger.py:105`) | gotówka per waluta | stan księgi = mapa `waluta → saldo`; kolumny Portfela jako cache (sekcja 6) |
| 4 | `PortfolioLedger.rebuild` składa jeden portfel (`ledger.py:311`) | przelewy łączą Portfele | przebudowa spójnej składowej (5.4), ADR |
| 5 | `operation_date` `timestamptz`; dzień w UTC (`metrics.py:148`) | D13 | `operation_day` (5.4) |
| 6 | `OperationService._record` commituje (`operations.py:99-100`) | import/przelew potrzebują `record_many` bez commitu | rdzeń bez commitu ([ADR-0008](../adr/0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md)); szczegóły w doc 08 |

## Otwarte punkty

| # | Punkt | Blokuje |
|---|---|---|
| 1 | Zatwierdzenie ADR: D1, D2, D4, D9, D12, D13, D15, D16 (biznesowe i techniczne) — tabele z tego dokumentu są szkicem do ich czasu | E2.1–E2.4 |
| 2 | **[propozycja]** `asset_type` osobno od Klasy waloru; mapowanie typ → domyślna Klasa w konfiguracji | E1.3, E3.3 |
| 3 | **[propozycja]** `last_price_change_at` jako `Date` per walor z compare-and-set; analogiczny znacznik kursów na `assets_currency` | E2.5 |
| 4 | **[propozycja]** Przelew jako jeden wiersz + przebudowa spójnej składowej; algorytm w ADR | E2.3 |
| 5 | **[propozycja]** Automatyczne wpłaty pochodne (`portfolios_auto_flow`) zamiast Operacji | E2.2b |
| 6 | **[propozycja]** `portfolios_operation.lot_ref_operation_id` zamiast FK do Partii | E2.4 |
| 7 | **[propozycja]** `cash_balance`/`total_deposited` jako cache; definicja `total_deposited` wielowalutowa | E2.2 |
| 8 | **[propozycja]** Ticker globalnie UNIQUE; ten sam symbol na dwóch giełdach rozróżnia sufiks w tickerze | E1.3 |
| 9 | **[propozycja]** Okresy obligacji: stopa na `(seria, nr okresu)`; ROR/DOR (okresy krótsze niż rok) wymagają potwierdzenia na listach emisyjnych | E5.1 |
| 10 | Źródło ogłoszonych stóp obligacji i sposób ich ładowania (brak API); Tabele odsetkowe jako PDF — próbki właściciela/pobranie | E5.1 |
| 11 | Źródło lokalnego katalogu GPW/NewConnect (E1.3) — nie występuje w dowodzie | E1.3 |
| 12 | **[propozycja]** Limity IKE/IKZE: tabela `portfolios_account_limit` ([doc 08](./08_schemat_danych_nowe_moduly.md), 4.6), nie w `core_data_user_settings` ani `taxes` (cykl modułów) | E5.6 |
| 13 | Kontrakty API (ścieżki, koperty, paginacja) tych tabel — osobny dokument; adresowanie Portfela po `id` zamiast `portfolio_name` | E2.7, E3.1 |
| 14 | Próbki plików właściciela (eksport myfund, wyciągi brokerów) — nie wpływają na ten schemat, blokują doc 08 (import) | E4.2a, E4.3 |
