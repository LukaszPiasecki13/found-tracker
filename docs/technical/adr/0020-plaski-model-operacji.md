---
id: adr-0020-flat-operation-model
status: Proposed
type: decision
scope: backend/operation-model
last_reviewed: 2026-10-03
---

# Operacja zostaje płaską tabelą z polami rozszerzającymi; przewalutowanie to jeden wiersz

`portfolios_operation` pozostaje płaską tabelą; nowe zdarzenia (przewalutowanie, split) dostają kolumny nullable. Przewalutowanie to **jeden wiersz**: `amount`/`currency_id` = noga wychodząca, `counter_amount`/`counter_currency_id` = przychodząca.

**Rozstrzyga:** D9 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)). Kolumny: [`07_schemat_danych_docelowy.md`](../backend/07_schemat_danych_docelowy.md) §5.4.

## Kontekst

- Operacja to płaski wiersz (`backend/app/modules/portfolios/models/operation.py:25-69`); `PortfolioLedger.rebuild` składa jeden Portfel z listy wierszy (`domain/ledger.py:311`).
- Nowe zdarzenia: przewalutowanie i split; typy v1: kupno, sprzedaż, wpłata, wypłata, dywidenda, odsetki, opłata, przewalutowanie, split.
- Operacje są źródłem prawdy, reszta pochodną `rebuild` ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)); Operacja edytowalna i usuwalna jako całość.

## Decyzja

1. **Pola rozszerzające** (nullable lub `server_default`; `autogenerate`, [ADR-0019](0019-migracje-danych-i-kolumny-dat.md)):

| Grupa | Pola |
|---|---|
| Czas i porządek | `operation_date`, `operation_day`, `sequence` |
| Waluta | `currency_id` |
| Przewalutowanie | `counter_amount`, `counter_currency_id` |
| Split | `ratio` |
| Import | `external_ref` `String(120)`, `import_batch_id`, `edited_at` ([ADR-0018](0018-architektura-importu.md)) |

2. **Przewalutowanie = jeden wiersz** w jednym Portfelu: `amount`/`currency_id` schodzi z salda waluty wychodzącej, `counter_amount`/`counter_currency_id` wchodzi na saldo drugiej; prowizja w walucie wychodzącej ([ADR biznesowy 0003](../../business/adr/0003-gotowka-wielowalutowa.md)).
3. **Split:** `ratio > 0`; zmienia ilość, zachowuje koszt łączny Partii ([ADR biznesowy 0002](../../business/adr/0002-koszt-nabycia-partie-fifo.md)).
4. **`sequence`.** Numer w obrębie (Portfel, `operation_day`), nadawany automatycznie; klucz księgi `(operation_day, sequence, id)` ([ADR biznesowy 0005](../../business/adr/0005-daty-operacji-dzien-i-kolejnosc.md)).
5. **Walidacja per typ w serwisie**, nie CHECK-iem (`autogenerate` nie dodaje CHECK do istniejącej tabeli): macierz „typ → pola wymagane i zakazane” (`currency_exchange` wymaga `counter_amount` i `counter_currency_id`, `split` wymaga `ratio`).
6. **Import:** jeden wiersz pliku = jeden wiersz Operacji; wiersze opisujące jedno zdarzenie łączy parser w jedną `ParsedRow`.

## Rozpatrywane alternatywy

- Nagłówek + nogi — przebudowa księgi, repozytoriów, API i frontendu.
- Przewalutowanie jako dwa wiersze — edycja jednej strony rozjeżdża drugą.
- Dziedziczenie tabel per typ — JOIN w każdym zapytaniu, trudniejszy ORM.

## Konsekwencje

- (+) Małe zmiany w istniejących wierszach i API; para nóg nie może się rozjechać.
- (−) Szeroka tabela; część kolumn nullable zależnie od typu.
