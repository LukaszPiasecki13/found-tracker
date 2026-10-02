---
id: adr-0020-flat-operation-model
status: Proposed
type: decision
scope: backend/operation-model
last_reviewed: 2026-10-02
---

# Operacja zostaje płaską tabelą z polami rozszerzającymi; przelew i przewalutowanie to jeden wiersz, nie nagłówek z nogami

`portfolios_operation` pozostaje płaską tabelą; nowe zdarzenia (przelew, przewalutowanie, split, zamiana serii) dostają kolumny nullable. Przelew to **jeden wiersz**: `amount` = noga wychodząca, `counter_*` = przychodząca.

**Rozstrzyga:** D9 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E2.2–E2.4, E4.1, E8.1–E8.5. Kolumny: [`07_schemat_danych_docelowy.md`](../backend/07_schemat_danych_docelowy.md) §5.4.

## Kontekst

- Operacja to płaski wiersz (`backend/app/modules/portfolios/models/operation.py:25-69`); `PortfolioLedger.rebuild` składa jeden Portfel z listy wierszy (`domain/ledger.py:311`).
- Roadmapa dodaje zdarzenia dwustronne: przelew (E2.3), przewalutowanie (E2.2), split/scalenie/zamiana tickera/spin-off (E8.1–E8.4), wykup obligacji (E5.1).
- Operacje są źródłem prawdy, reszta pochodną `rebuild` ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)); Operacja edytowalna i usuwalna jako całość.

## Decyzja

1. **Pola rozszerzające** (nullable lub `server_default`; `autogenerate`, [ADR-0019](0019-migracje-danych-i-kolumny-dat.md)):

| Grupa | Pola |
|---|---|
| Czas i porządek | `operation_day`, `sequence`, `settlement_date`, `settlement_source` `String(10)` |
| Waluta i kursy | `currency_id`, `fx_rate_tax`, `fx_tax_date`, `fx_tax_table_no` `String(32)` |
| Druga strona | `counter_portfolio_id` (FK `RESTRICT`), `counter_amount`, `counter_currency_id`, `counter_asset_id`, `ratio` |
| Pochodzenie | `import_batch_id`, `external_ref` `String(120)`, `edited_at` |
| Cykl życia | `status` `String(10)` ∈ {`posted`, `draft`, `void`}, domyślnie `posted` |

2. **Przelew i przewalutowanie = jeden wiersz.** `amount`/`currency_id` = noga wychodząca z `portfolio_id`; `counter_amount`/`counter_currency_id` = noga przychodząca do `counter_portfolio_id` (przewalutowanie: ten sam Portfel, druga waluta). Przelew papierów: `asset_id` + `quantity`, Partie przechodzą z kosztem i datą nabycia ([ADR biznesowy 0002](../../business/adr/0002-koszt-nabycia-partie-fifo.md)).
3. **Widoczność.** `list_by_portfolio` i `list_by_owner` zwracają wiersze, w których Portfel jest źródłem **lub** celem. API niesie `direction` ∈ {`out`, `in`} względem czytanego Portfela; jedno `id`.
4. **`status`.** Księga czyta tylko `posted`. `draft` to propozycja; `accept` → `posted`, `void` unieważnia. Szkice importu żyją w `portfolios_import_row` ([ADR-0018](0018-architektura-importu.md)).
5. **`sequence`.** Numer w obrębie (Portfel, `operation_day`), nadawany automatycznie; klucz księgi `(operation_day, sequence, id)` ([ADR biznesowy 0005](../../business/adr/0005-daty-operacji-i-zdarzenie-podatkowe.md)).
6. **Rebuild.** Przelew przetwarza się raz, na scalonym strumieniu składowej spójnej Portfeli ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)). `domain/` dostaje `Operation` z `counter_*` i `direction` dla danego Portfela; `PortfolioLedger` nie zna drugiego Portfela.
7. **Walidacja per typ w serwisie**, nie CHECK-iem (`autogenerate` nie dodaje CHECK do istniejącej tabeli): macierz „typ → pola wymagane i zakazane” (`transfer` wymaga `counter_portfolio_id`, `split` wymaga `ratio > 0`).
8. **Import:** jeden wiersz pliku = jeden wiersz Operacji; wiersze opisujące jedno zdarzenie (np. przewalutowanie IBKR) łączy parser w jedną `ParsedRow`.

## Rozpatrywane alternatywy

- Nagłówek + nogi (Portfolio Performance, Wealthfolio) — przebudowa księgi, repozytoriów, API, frontendu i migracja wierszy.
- Przelew jako dwa wiersze — edycja jednej strony rozjeżdża drugą.
- Dziedziczenie tabel per typ — JOIN w każdym zapytaniu, trudniejszy ORM.

## Konsekwencje

- (+) Brak zmian w istniejących wierszach i API; `test_ledger_parity.py` bez zmian; para nie może się rozjechać.
- (−) Szeroka tabela; zapytania z `portfolio_id = X OR counter_portfolio_id = X` (indeks częściowy); raport „po Portfelu” musi rozróżniać `direction`, inaczej przelew liczy się dwa razy w sumach Grupy.
- (−) Zdarzenia z więcej niż dwiema stronami: kilka wierszy lub ponowna ocena nagłówka z nogami.

## Otwarte

- Spin-off z jednym walorem wyjściowym i wieloma wynikowymi: jeden wiersz (`counter_asset_id`) czy wiersze powiązane — E8.3.
- Prowizja przelewu w walucie nogi wychodzącej **[propozycja]**, jak przewalutowanie.
