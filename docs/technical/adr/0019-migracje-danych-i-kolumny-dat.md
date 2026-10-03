---
id: adr-0019-data-migrations-date-columns
status: Proposed
type: decision
scope: backend/migrations-seed-dates
last_reviewed: 2026-10-03
---

# Migracje tylko z `autogenerate`; dzień Operacji to `operation_day` (Europe/Warsaw) z `sequence`; dane startują od zera

Schemat zmienia wyłącznie `alembic revision --autogenerate`. Dane powstają przez seed albo import, nie przez migracje. Porządek i snapshoty opierają się na `operation_day` (D13) i `sequence`.

**Rozstrzyga:** D16 i techniczną część D13 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)).

## Kontekst

- `operation_date` to `DateTime(timezone=True)` (`backend/app/modules/portfolios/models/operation.py:57`); wektory liczą dzień w UTC (`services/metrics.py:147-149`) — Operacja z 00:30 w Warszawie ląduje dzień wcześniej.
- `autogenerate` nie dopisze `postgresql_using`, a ręczna edycja migracji jest zakazana — zmiana typu `timestamptz` → `date` w istniejącej kolumnie jest niewykonalna zgodnie z regułami projektu.
- Dane istniejące nie są przenoszone: baza startuje od zera, więc nie ma backfillu ani migracji danych.

## Decyzja

1. **Polityka migracji**

| Reguła | Treść |
|---|---|
| M1 | Tylko `autogenerate`; model w `models_registry.py`; `alembic check` bez dryfu |
| M2 | Zmiana typu istniejącej kolumny z niejawnym rzutowaniem zakazana; używamy nowej kolumny |
| M3 | Dane (słowniki, stany początkowe) przez seed lub import ([ADR-0018](0018-architektura-importu.md)), nie przez migracje |

2. **`operation_day` i `sequence`**
   - `operation_day` `Date` NOT NULL — dzień kalendarzowy **Europe/Warsaw**; źródło prawdy dla porządku, wycen i snapshotów. `operation_date` zostaje jako moment zdarzenia.
   - `sequence` `Integer`, `server_default '0'`, NOT NULL; klucz porządku (`operation_day`, `sequence`, `id`) ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md), [ADR biznesowy 0005](../../business/adr/0005-daty-operacji-dzien-i-kolejnosc.md)).
   - Serwis wylicza `operation_day` przez `zoneinfo.ZoneInfo("Europe/Warsaw")`, nie SQL-em. Wektory metryk korzystają z `operation_day`.
3. **Seed generuje stany z Operacji.** Portfel startuje od 0 (bez wprost wstawianych `cash_balance`/`total_deposited`); po zapisie Operacji seed woła przebudowę przez `wiring.py` (wyjątek od R5 dla `backend/seed/`, [ADR-0002](0002-sesja-poza-zadaniem-entrypointy-i-wiring.md)). Test seeda: replay nie rzuca, dwie przebudowy dają ten sam stan.

## Rozpatrywane alternatywy

- `ALTER COLUMN operation_date TYPE date` — wynik zależy od strefy sesji, korekta wymaga ręcznej edycji migracji.
- Dzień liczony w SQL — zależny od strefy sesji bazy.

## Konsekwencje

- (+) Brak ręcznych edycji migracji; dzień Operacji niezależny od strefy bazy; seed zawsze zgodny z księgą.
- (−) Dwie kolumny dat (`operation_date` jako moment, `operation_day` jako klucz).
