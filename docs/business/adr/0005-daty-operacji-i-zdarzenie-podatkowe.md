---
id: adr-0005-operation-dates-tax-event
status: Proposed
type: decision
scope: business/operation-dates
last_reviewed: 2026-10-02
---

# Operacja ma dzień zawarcia i datę rozrachunku; kurs podatkowy NBP D−1 liczymy od daty rozrachunku (ustawienie per Portfel)

Rekomendacja: `operation_day` to data kalendarzowa zawarcia w strefie Europe/Warsaw; `settlement_date` (domyślnie T+2 sesje) wyznacza zdarzenie podatkowe i dzień bazowy kursu NBP z ostatniego dnia roboczego poprzedzającego. Dywidenda — dzień wypłaty. Kolejność w dniu daje `sequence`. Reguła rozrachunku opiera się na wniosku, nie na interpretacji MF, dlatego jest ustawieniem Portfela.

**Rozstrzyga decyzje roadmapy:** D12 i D13. **Blokuje:** E2.0 (migracja dat), E2.3 (pola Operacji z D9), E2.4 (koszt PLN partii), E6.1–E6.3; zależność miękka od E1.9 (kalendarz sesji) i E1.2 (kursy NBP).

## Kontekst

- Dziś `operation_date` to `DateTime(timezone=True)`, indeksowane (`backend/app/modules/portfolios/models/operation.py:52-54`); UI wysyła samą datę `YYYY-MM-DD`; kolejność w dniu to `created_at`, potem `id` (`ledger.py:311-313`). `metrics.py:146-148` wylicza indeks dnia z UTC (`_naive_utc`).
- Art. 17 ust. 1ab pkt 1: przychód ze zbycia papierów „powstaje w momencie przeniesienia na nabywcę własności”; rozrachunek GPW/KDPW to T+2. Art. 11a ust. 1 i 2: kurs średni NBP „z ostatniego dnia roboczego poprzedzającego dzień uzyskania przychodu” / „poniesienia kosztu”; ust. 3 — podatek zapłacony za granicą ([dowód 04](../../research/04_rynek_pl_podatki_i_brokerzy.md), §1.3–1.5).
- **[niezweryfikowane]** Wniosek, że datą przychodu jest data rozrachunku, opiera się na art. 17 ust. 1ab i art. 7 ustawy o obrocie (tylko snippet, bez numeru ustępu); **brak interpretacji ogólnej MF**, a brokerzy zagraniczni mogą raportować datę transakcji (dowód 04, §1.4, luka 1). Różnica jest istotna na przełomie roku (sprzedaż 30.12, rozrachunek 2.01 → przychód następnego roku).
- Dywidenda: data przychodu = dzień wypłaty — **[wniosek]** bez interpretacji (dowód 04, §1.5, luka 6).
- Zmiana typu kolumny `timestamptz → date` autogeneruje migrację bez `USING` (strefa sesji bazy), a ręczna edycja migracji jest zakazana.

## Decyzja

1. **`operation_day`** `Date`, **nowa** kolumna (nie zmieniamy typu `operation_date`), NOT NULL po wypełnieniu przez `rebuild-all` (D16): dzień kalendarzowy `operation_date` w Europe/Warsaw. `operation_date` zostaje jako znacznik czasu (godzina opcjonalna; bez godziny = 00:00 czasu Warszawy). Dzienny wektor, snapshoty (E2.5) i okresy ([ADR 0004](0004-metodologia-stop-zwrotu.md)) używają `operation_day`.
2. **`sequence`** `Integer` NOT NULL: numer kolejny w obrębie `(Portfel, operation_day)`, nadawany automatycznie przy zapisie. Klucz porządku księgi: **`(operation_day, sequence, id)`** (jedyny wariant). Backfill (`rebuild-all`) nadaje `sequence` z kolejności `(operation_date, created_at, id)`, więc dzisiejsza kolejność zostaje zachowana, a parytet i `rebuild` nie zmieniają wyniku.
3. **`settlement_date`** `Date`, nullable, z `settlement_source` `String(10)` ∈ {`default`, `broker`, `manual`} **[propozycja]**. Wartość domyślna: `operation_day` + 2 sesje wg kalendarza E1.9 (`default`). **Przed E1.9** domyślnie +2 dni robocze pn–pt bez świąt (`default`, przeliczane po wdrożeniu kalendarza tylko dla `default`); import dostarcza datę (np. IBKR `Settle Date Target`, `broker`); ręczna zmiana użytkownika → `manual`. Dla funduszy (TFI) datą jest dzień otrzymania/postawienia środków do dyspozycji — wpisywana lub z importu.
4. **Podstawa podatkowa** — ustawienie Portfela `tax_date_basis` ∈ {`settlement`, `trade`}, domyślnie `settlement` **[propozycja]**; jedna podstawa dla przychodu i kosztu (partii) Portfela, aby koszt i przychód były liczone spójnie. Dzień roboczy = dzień publikacji tabeli A NBP; algorytm cofania z dowodu `03_rynek_pl_dane_i_obligacje.md`.
5. **Kurs podatkowy** zapisany w Operacji (D9): `fx_rate_tax` `Numeric`, `fx_tax_date` `Date`, `fx_tax_table_no` `String(32)`. Gdy tabela dla dnia D−1 podstawy **jeszcze nie jest opublikowana** (rozrachunek w przyszłości), kurs jest „oczekujący” i uzupełnia go zadanie w tle (E1.4); raporty podatkowe odmawiają finalizacji z `TAX_RATE_PENDING`. Kurs brokera (`fx_rate`) pozostaje osobno ([ADR 0003](0003-gotowka-wielowalutowa.md)).
6. **Dywidenda**: dzień wypłaty = `settlement_date` Operacji `dividend` (ma też `operation_day` wpisu); kurs NBP D−1 od dnia wypłaty (art. 11a ust. 1); WHT — kurs D−1 dnia zapłaty podatku, domyślnie ten sam dzień **[niezweryfikowane]**.
7. Dzień kalendarzowy Warszawy dotyczy też zleceń na giełdach zagranicznych; zlecenie po północy czasu warszawskiego wymaga ręcznej korekty dnia (patrz Otwarte).

## Rozpatrywane alternatywy

| Opcja | Koszt / ryzyko | Werdykt |
|---|---|---|
| A. Podatek wg daty zawarcia | prostsze, nie wymaga kalendarza; ryzyko błędnego roku podatkowego i kursu na przełomie roku, jeśli rozrachunek jest właściwy | alternatywa dostępna przez `tax_date_basis = trade` |
| B. Zmiana typu `operation_date` na `date` | migracja bez `USING` interpretuje strefą sesji bazy; ręczna edycja zakazana; tracimy godzinę z importu (IBKR `Trade Time`) | odrzucona |
| C. Nowa kolumna `operation_day` (rekomendacja) | dwie kolumny o podobnym znaczeniu; trzeba pilnować spójności (wypełnia ją serwis, nie klient) | wybrana |
| D. Czysty UTC dla dni | dzień Operacji z wieczoru PL może wpaść w inny dzień; już dziś `metrics.py` liczy w UTC | odrzucona |
| E. `settlement_date` tylko ręcznie | zero zależności, ale ręczna praca przy każdej sprzedaży i błędy | odrzucona |

## Konsekwencje

**Pozytywne**
- Granica roku i kurs D−1 policzone zgodnie z przeniesieniem własności; opcja `trade` zostaje, jeśli właściciel wybierze inną wykładnię.
- Kolejność w dniu jest jawna (Przewalutowanie przed zakupem; E2.7).

**Negatywne**
- Raport podatkowy opiera się na wniosku bez interpretacji; wynik może różnić się od brokera zagranicznego (data transakcji) — trzeba pokazać obie daty i podstawę.
- Do czasu E1.9 `settlement_date` jest przybliżeniem (`settlement_source = default`, bez świąt); święta GPW mogą przesunąć rok podatkowy.
- Przed zapisem kursu NBP Operacje z przyszłym rozrachunkiem mają kurs „oczekujący”.
- Dodatkowe kolumny (`operation_day`, `sequence`, `settlement_date`, `settlement_source`, `tax_date_basis`) — nowe pola w imporcie (E4).

## Zmiany słownika po akceptacji

| Pojęcie | Wpis w `CONTEXT.md` |
|---|---|
| **Dzień operacji** (`operation_day`) | Data zawarcia, kalendarz Europe/Warsaw. _Unikać_: data transakcji (niejednoznaczne: zawarcie vs rozrachunek) |
| **Data rozrachunku** (`settlement_date`) | Dzień przeniesienia własności (domyślnie T+2). _Unikać_: data księgowania, valuta |
| **Kurs podatkowy** | Kurs średni NBP z ostatniego dnia roboczego przed podstawą podatkową; zapisany z numerem tabeli. _Unikać_: kurs NBP (bez daty), kurs brokera (inne pojęcie) |
| **Kurs walutowy operacji** (zmiana) | Dopisać: to kurs brokera, nie podatkowy |

## Otwarte

- Interpretacja MF / opinia doradcy dla daty przychodu ze zbycia papierów — blokuje wyłącznie zaufanie do E6, nie model danych.
- Zlecenia po północy czasu warszawskiego na giełdach USA: dzień zawarcia = dzień Warszawy czy giełdy.
- Próbki eksportów z datami rozrachunku (IBKR, XTB) — brak.
