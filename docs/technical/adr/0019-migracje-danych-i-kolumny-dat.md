---
id: adr-0019-data-migrations-date-columns
status: Proposed
type: decision
scope: backend/migrations-seed-dates
last_reviewed: 2026-10-02
---

# Dane istniejące wypełnia `rebuild-all`, nie migracja; `operation_day` jest nową kolumną obok `operation_date`; seed generuje stany z Operacji

Migracje tylko z `autogenerate`, addytywne; backfill robi idempotentne polecenie CLI. Dzień Operacji (D13) trafia do **nowej** kolumny `operation_day`. Seed przestaje trzymać stany niezgodne z replayem.

**Rozstrzyga:** D16 i techniczną część D13 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E2.0, E2.3, E2.5.

## Kontekst

- `operation_date` to `DateTime(timezone=True)` (`backend/app/modules/portfolios/models/operation.py:57`); wektory liczą dzień w UTC (`services/metrics.py:147-149`) — Operacja z 00:30 w Warszawie ląduje dzień wcześniej.
- `ALTER COLUMN … TYPE date` z `timestamptz` bez `USING` rzutuje wg strefy sesji; `autogenerate` nie dopisze `postgresql_using`, ręczna edycja migracji jest zakazana.
- Replay Operacji z `backend/seed/seed_data.py` przez `PortfolioLedger.rebuild` (2026-10-02) nie zgadza się z seedem: gotówka US Stocks 15 000 vs 8 971,50, European 8 000 vs 7 561,95, Polish 25 000 vs 12 669,30; Crypto Portfolio rzuca `InsufficientCashError` (wpłata 8 000, zakupy ≥ 15 632). Seed wstawia stany wprost (`seed.py:270`), więc kryterium E2.0 „`rebuild-all` na seed daje stan identyczny z obecnym” jest fałszywe.

## Decyzja

**1. Polityka migracji (D16)**

| Reguła | Treść |
|---|---|
| M1 | Tylko `autogenerate`; model w `models_registry.py`; `alembic check` bez dryfu |
| M2 | Nowa kolumna: `nullable=True` albo `server_default`; NOT NULL bez defaultu w dwóch krokach (pkt 3) |
| M3 | Zmiana typu istniejącej kolumny z niejawnym rzutowaniem zakazana; nowa kolumna obok, stara wygaszona osobnym ADR-em |
| M4 | Dane (backfill, przeniesienia) nie w migracjach; idempotentne polecenie CLI ([ADR-0017](0017-zadania-w-tle-i-cli.md)) |

**2. `operation_day` i `sequence`**
- `operation_day` `Date` (kalendarz **Europe/Warsaw**, D13), `null` w migracji A; źródło prawdy dla porządku, podatku i snapshotów. `operation_date` zostaje jako moment zdarzenia.
- `sequence` `Integer`, `server_default '0'`, NOT NULL; klucz porządku (`operation_day`, `sequence`, `id`) ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)).
- Serwis wylicza `operation_day` przez `zoneinfo.ZoneInfo("Europe/Warsaw")`, nie SQL-em. Wektory metryk przechodzą na `operation_day`.
- `rebuild-all` uzupełnia w istniejących wierszach `operation_day`, `sequence` (wg `operation_date`, `created_at`, `id`, numerowane per Portfel i `operation_day`) i `currency_id` = waluta bazowa Portfela ([ADR biznesowy 0003](../../business/adr/0003-gotowka-wielowalutowa.md) pkt 4). Pozycje aktualizuje w miejscu (zachowuje `opened_at`); drugi przebieg nic nie zmienia.

**3. Kolejność wdrożenia:** migracja A (nowe tabele, kolumny `null`/`server_default`) → kod zapisujący `operation_day`/`sequence` → `rebuild-all` (`--check` zwraca 1 przy różnicach) → weryfikacja (drugi przebieg = 0 zapisów) → migracja B (`operation_day` NOT NULL) → odczyty na `operation_day`.

**4. Seed generuje stany z Operacji**
- Z `PortfolioSeed` i `POSITIONS` znika `cash_balance`/`total_deposited` (`seed_data.py:187-312`); Portfel startuje od 0.
- Po Operacjach seed woła przebudowę przez `wiring.py` (wyjątek od R5 dla `backend/seed/`, [ADR-0002](0002-sesja-poza-zadaniem-entrypointy-i-wiring.md)).
- Wpłata Crypto Portfolio 8 000 → **16 000** **[propozycja]**; test seeda: replay nie rzuca, dwie przebudowy dają ten sam stan.
- Kryterium E2.0 po naprawie seeda: „`rebuild-all` na seed daje stan równy replayowi Operacji; drugi przebieg bez zmian”. E0.5 sprawdza to replayem przez `PortfolioLedger`.

## Rozpatrywane alternatywy

- `ALTER COLUMN operation_date TYPE date` — wynik zależy od strefy sesji, korekta wymaga ręcznej edycji migracji.
- Backfill w migracji — zakazana edycja, brak idempotencji.
- Poprawić tylko liczby w seedzie — rozjadą się przy zmianie reguł księgi.

## Konsekwencje

- (+) Brak ręcznych edycji migracji; dzień Operacji niezależny od strefy bazy.
- (−) Dwie kolumny dat do wygaszenia `operation_date`; `rebuild-all` jest krokiem wdrożenia.

## Otwarte

- Strefa backfillu: stała Europe/Warsaw (przyjęta) czy ustawienie użytkownika z E0.9.
