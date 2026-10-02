---
id: adr-0020-flat-operation-model
status: Proposed
type: decision
scope: backend/operation-model
last_reviewed: 2026-10-02
---

# Operacja zostaje płaską tabelą z polami rozszerzającymi; przelew i przewalutowanie to jeden wiersz, nie nagłówek z nogami

`portfolios_operation` pozostaje jedną płaską tabelą. Nowe zdarzenia (przelew, przewalutowanie, split, zamiana serii) dostają **dodatkowe kolumny nullable** zamiast tabeli nogów. Przelew między Portfelami to **jeden wiersz** (`amount` = noga wychodząca, `counter_*` = noga przychodząca). Cykl życia niesie `status`, kolejność w dniu `sequence`. Alternatywa — nagłówek + nogi (Portfolio Performance, Wealthfolio) — jest bogatsza, ale przebudowuje księgę, repozytoria i import.

**Rozstrzyga:** D9 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E2.2, E2.3, E2.4, E4.1, E8.1–E8.5. Schemat kolumn: [`07_schemat_danych_docelowy.md`](../backend/07_schemat_danych_docelowy.md) §5.4.

## Kontekst

- Dziś Operacja to płaski wiersz: `portfolio_id`, `asset_id` (null), `operation_type`, `quantity`, `price`, `amount`, `fee`, `fx_rate`, `notes`, `operation_date`, `created_at` (`backend/app/modules/portfolios/models/operation.py:25-69`). `PortfolioLedger.rebuild` składa jeden Portfel z listy takich wierszy (`domain/ledger.py:311`); repozytoria zwracają wiersze po `portfolio_id` (`repositories/operations.py:53-57`).
- Roadmapa dodaje zdarzenia z dwiema stronami: przelew gotówki i papierów (E2.3), przewalutowanie (E2.2), split, scalenie, zamiana tickera, spin-off (E8.1–E8.4), wykup obligacji (E5.1).
- Zasada P3: Operacje są źródłem prawdy, reszta jest pochodną odtwarzaną przez `rebuild` ([ADR biznesowy 0003](../../business/adr/0003-gotowka-wielowalutowa.md)).
- Jedna Operacja musi być edytowalna i usuwalna jako całość; edycja/usunięcie wyzwala przebudowę ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)).

## Decyzja

1. **Płaska tabela z polami rozszerzającymi** (wszystkie `nullable` albo `server_default`; migracja `autogenerate`, [ADR-0019](0019-migracje-danych-i-kolumny-dat.md)):

| Grupa | Pola | Krok |
|---|---|---|
| Czas i porządek | `operation_day` `Date`, `sequence` `Integer`, `settlement_date` `Date`, `settlement_source` `String(10)` | E2.0, E2.3 |
| Waluta i kursy | `currency_id`, `fx_rate_tax`, `fx_tax_date`, `fx_tax_table_no` `String(32)` | E2.2, E1.2 |
| Druga strona zdarzenia | `counter_portfolio_id` (FK `RESTRICT`), `counter_amount`, `counter_currency_id`, `counter_asset_id`, `ratio` | E2.3, E8.1–E8.4 |
| Pochodzenie | `import_batch_id`, `external_ref` `String(120)`, `edited_at` | E4.1 |
| Cykl życia | `status` `String(10)` ∈ {`posted`, `draft`, `void`}, domyślnie `posted` | E8.5, E9.6, E10.3 |

2. **Przelew i przewalutowanie = JEDEN wiersz.** `amount`/`currency_id` = noga wychodząca z Portfela źródłowego (`portfolio_id`), `counter_amount`/`counter_currency_id` = noga przychodząca do `counter_portfolio_id` (przy przewalutowaniu — ten sam Portfel, druga waluta). Przelew papierów: `asset_id` + `quantity`, Partie przechodzą z kosztem i datą nabycia (`origin_operation_id`, [ADR biznesowy 0002](../../business/adr/0002-koszt-nabycia-partie-fifo.md)).
3. **Widoczność dla obu stron.** Repozytoria `list_by_portfolio` i `list_by_owner` zwracają wiersze, w których Portfel jest źródłem **lub** celem (`counter_portfolio_id`). Odpowiedź API niesie `direction` ∈ {`out`, `in`} względem Portfela, w którego kontekście czytamy; ta sama Operacja ma jedno `id`.
4. **`status`.** Księga czyta wyłącznie `posted`. `draft` to propozycja (dywidenda, split, szablon cykliczny, szkic z e-maila) — `accept` zmienia na `posted`, `void` unieważnia bez usuwania. Szkice importu żyją w `portfolios_import_row` ([ADR-0018](0018-architektura-importu.md)), nie jako `draft`.
5. **`sequence`.** Numer w obrębie (Portfel, `operation_day`), nadawany automatycznie; klucz porządku księgi `(operation_day, sequence, id)` ([ADR biznesowy 0005](../../business/adr/0005-daty-operacji-i-zdarzenie-podatkowe.md)).
6. **Rebuild.** Przelew przetwarza się raz, na scalonym strumieniu zdarzeń składowej spójnej Portfeli ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)): wypływ w źródle, wpływ w celu. `domain/` dostaje `Operation` z polami `counter_*` i `direction` wyliczonym dla danego Portfela; `PortfolioLedger` nie zna drugiego Portfela.
7. **Walidacja per typ w serwisie**, nie CHECK-iem: macierz „typ → wymagane i zakazane pola” (np. `transfer` wymaga `counter_portfolio_id`, `split` wymaga `ratio > 0`). Powód: `autogenerate` nie dodaje CHECK do istniejącej tabeli.
8. **Import** mapuje jeden wiersz pliku brokera na jeden wiersz Operacji; dwa wiersze pliku opisujące jedno zdarzenie (np. przewalutowanie w IBKR) łączy parser w jedną `ParsedRow`.

## Rozpatrywane alternatywy

| Opcja | Koszt / ryzyko | Werdykt |
|---|---|---|
| A. Płaska Operacja + pola (rekomendacja) | tabela szeroka, wiele kolumn null; walidacja per typ w serwisie; przelew czytany z dwóch stron przez `OR` | wybrana |
| B. Nagłówek + nogi (PP, Wealthfolio) | naturalny model wielonogowy, ale: nowa tabela nogów, przebudowa `PortfolioLedger`, repozytoriów, schematów API, 4 testów parytetu i frontendu; migracja istniejących wierszy w nogi | odrzucona |
| C. Przelew jako dwa powiązane wiersze | proste `list_by_portfolio`; ale edycja jednej strony rozjeżdża drugą, usunięcie wymaga klucza powiązania i transakcji na parze, kolejność nóg w dniu | odrzucona |
| D. Dziedziczenie tabel per typ | sztywne typy; JOIN w każdym zapytaniu; ORM trudniej utrzymać | odrzucona |

## Konsekwencje

**Pozytywne**
- Zero zmian w istniejących wierszach i kontrakcie API (pola dodawane); parytet `test_ledger_parity.py` bez zmian.
- Edycja, usunięcie i `rebuild` operują na jednym `id`; para nie może się rozjechać.
- Import i dedup po `external_ref` pozostają jednowierszowe.

**Negatywne**
- Szeroka tabela z kolumnami zależnymi od typu; poprawność trzyma serwis i testy macierzy typów.
- Zapytania „Operacje Portfela” mają warunek `portfolio_id = X OR counter_portfolio_id = X` (indeks częściowy na `counter_portfolio_id`).
- Zdarzenia z więcej niż dwiema stronami (np. spin-off z wieloma walorami) wymagają kilku wierszy lub rozszerzenia; wraca wtedy ocena wariantu B.
- Raport „po Portfelu” musi rozróżniać kierunek (`direction`), inaczej przelew policzy się dwa razy w sumach Grupy.

## Otwarte

- Czy spin-off z jednym walorem wyjściowym i wieloma wynikowymi mieści się w jednym wierszu (`counter_asset_id`), czy wymaga wierszy powiązanych — rozstrzygnąć w E8.3.
- Prowizja przelewu: w walucie nogi wychodzącej (przyjęto [propozycja], jak przewalutowanie).
