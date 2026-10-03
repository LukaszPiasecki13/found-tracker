---
id: adr-0005-operation-dates
status: Accepted
type: decision
scope: business/operation-dates
last_reviewed: 2026-10-03
---

# Operacja ma dzień (Europe/Warsaw) i numer kolejny w dniu

`operation_day` to data zawarcia w strefie Europe/Warsaw; `sequence` jawnie ustala kolejność Operacji w dniu. Snapshoty i okresy używają `operation_day`.

**Blokuje:** E2.0, E2.3, E2.4.

## Kontekst

- `operation_date` to `DateTime(timezone=True)` (`backend/app/modules/portfolios/models/operation.py:52-54`); kolejność w dniu: `created_at`, `id` (`ledger.py:311-313`); `metrics.py:146-148` liczy dzień z UTC, więc wieczór czasu polskiego wpada w inny dzień.

## Decyzja

1. **`operation_day`** `Date`, NOT NULL: dzień `operation_date` w Europe/Warsaw. `operation_date` zostaje znacznikiem czasu (bez godziny = 00:00 Warszawy). Snapshoty (E2.5) i okresy ([ADR 0004](0004-metodologia-stop-zwrotu.md)) używają `operation_day`.
2. **`sequence`** `Integer` NOT NULL: numer w `(Portfel, operation_day)`, nadawany przy zapisie. Klucz księgi: `(operation_day, sequence, id)`.
3. Dzień Warszawy dotyczy też giełd zagranicznych; zlecenie po północy wymaga ręcznej korekty dnia.

## Alternatywy

- Zmiana typu `operation_date` na `date` — utrata godziny importu.
- Czysty UTC dla dni — wieczór PL wpada w inny dzień.

## Konsekwencje

- (+) Dzień i kolejność w dniu są jawne i stabilne (E2.7).
- (−) Dodatkowa kolumna i numerowanie przy zapisie.

## Słownik (`CONTEXT.md`)

**Dzień operacji** — data zawarcia w Europe/Warsaw (_unikać_: data transakcji).

## Otwarte

- Zlecenia po północy na giełdach USA: dzień Warszawy czy giełdy.
