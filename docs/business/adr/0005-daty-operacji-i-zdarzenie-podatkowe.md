---
id: adr-0005-operation-dates-tax-event
status: Proposed
type: decision
scope: business/operation-dates
last_reviewed: 2026-10-02
---

# Operacja ma dzień zawarcia i datę rozrachunku; kurs podatkowy NBP D−1 liczymy od daty rozrachunku (ustawienie per Portfel)

`operation_day` to data zawarcia (Europe/Warsaw); `settlement_date` (domyślnie T+2 sesje) wyznacza zdarzenie podatkowe i dzień bazowy kursu NBP z poprzedzającego dnia roboczego. Reguła to wniosek, nie interpretacja MF — stąd ustawienie Portfela.

**Rozstrzyga:** D12, D13. **Blokuje:** E2.0, E2.3, E2.4, E6.1–E6.3; miękko E1.9 (kalendarz sesji), E1.2 (kursy NBP).

## Kontekst

- `operation_date` to `DateTime(timezone=True)` (`backend/app/modules/portfolios/models/operation.py:52-54`); kolejność w dniu: `created_at`, `id` (`ledger.py:311-313`); `metrics.py:146-148` liczy dzień z UTC.
- Art. 17 ust. 1ab pkt 1: przychód ze zbycia powstaje z przeniesieniem własności (GPW/KDPW: T+2). Art. 11a ust. 1–2: kurs NBP z ostatniego dnia roboczego przed dniem przychodu/kosztu ([dowód 04](../../research/04_rynek_pl_podatki_i_brokerzy.md), §1.3–1.5).
- **[niezweryfikowane]** Data rozrachunku jako data przychodu: brak interpretacji MF, brokerzy zagraniczni mogą raportować datę transakcji (dowód 04, §1.4, luka 1); różnica liczy się na przełomie roku. Dywidenda — dzień wypłaty, też bez interpretacji (§1.5, luka 6).

## Decyzja

1. **`operation_day`** `Date`, nowa kolumna, NOT NULL po wypełnieniu przez `rebuild-all` (D16): dzień `operation_date` w Europe/Warsaw. `operation_date` zostaje znacznikiem czasu (bez godziny = 00:00 Warszawy). Snapshoty (E2.5) i okresy ([ADR 0004](0004-metodologia-stop-zwrotu.md)) używają `operation_day`.
2. **`sequence`** `Integer` NOT NULL: numer w `(Portfel, operation_day)`, nadawany przy zapisie. Klucz księgi: `(operation_day, sequence, id)`. Backfill z `(operation_date, created_at, id)` zachowuje obecną kolejność.
3. **`settlement_date`** `Date`, nullable, + `settlement_source` `String(10)` ∈ {`default`, `broker`, `manual`} **[propozycja]**. Domyślnie `operation_day` + 2 sesje (kalendarz E1.9); przed E1.9 +2 dni robocze pn–pt bez świąt (po wdrożeniu przeliczane tylko dla `default`). Import dostarcza datę (`broker`); ręczna zmiana → `manual`. Fundusze (TFI): dzień postawienia środków.
4. **`tax_date_basis`** (ustawienie Portfela) ∈ {`settlement`, `trade`}, domyślnie `settlement` **[propozycja]**; jedna podstawa dla przychodu i kosztu. Dzień roboczy = dzień publikacji tabeli A NBP.
5. **Kurs podatkowy** w Operacji (D9): `fx_rate_tax` `Numeric`, `fx_tax_date` `Date`, `fx_tax_table_no` `String(32)`. Tabela D−1 nieopublikowana → kurs „oczekujący”, uzupełnia go zadanie w tle (E1.4); raporty odmawiają finalizacji z `TAX_RATE_PENDING`. Kurs brokera `fx_rate` osobno ([ADR 0003](0003-gotowka-wielowalutowa.md)).
6. **Dywidenda**: dzień wypłaty = `settlement_date` Operacji `dividend`; kurs D−1 od tego dnia (art. 11a ust. 1). WHT: kurs D−1 dnia zapłaty, domyślnie ten sam dzień **[niezweryfikowane]**.
7. Dzień Warszawy dotyczy też giełd zagranicznych; zlecenie po północy wymaga ręcznej korekty dnia.

## Alternatywy

- Podatek wg daty zawarcia — zły rok i kurs na przełomie roku; dostępna jako `tax_date_basis = trade`.
- Zmiana typu `operation_date` na `date` — migracja bez `USING` (ręczna edycja zakazana), utrata godziny importu.
- Czysty UTC dla dni — wieczór PL wpada w inny dzień.
- `settlement_date` tylko ręcznie — błędy przy każdej sprzedaży.

## Konsekwencje

- (+) Granica roku i kurs D−1 zgodne z przeniesieniem własności; kolejność w dniu jawna (E2.7).
- (−) Wynik może różnić się od brokera zagranicznego — pokazujemy obie daty i podstawę. Do E1.9 `settlement_date` to przybliżenie (święta GPW).

## Słownik (`CONTEXT.md` po akceptacji)

**Dzień operacji** — data zawarcia (_unikać_: data transakcji). **Data rozrachunku** — przeniesienie własności, domyślnie T+2. **Kurs podatkowy** — średni NBP z dnia roboczego przed podstawą, z numerem tabeli (_unikać_: kurs NBP bez daty). **Kurs walutowy operacji** — kurs brokera, nie podatkowy.

## Otwarte

- Interpretacja MF / opinia doradcy dla daty przychodu — blokuje zaufanie do E6, nie model danych.
- Zlecenia po północy na giełdach USA: dzień Warszawy czy giełdy.
- Brak próbek eksportów z datami rozrachunku (IBKR, XTB).
