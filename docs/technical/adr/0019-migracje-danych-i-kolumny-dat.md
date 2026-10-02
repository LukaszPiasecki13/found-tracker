---
id: adr-0019-data-migrations-date-columns
status: Proposed
type: decision
scope: backend/migrations-seed-dates
last_reviewed: 2026-10-02
---

# Dane istniejące wypełnia `rebuild-all`, nie migracja; `operation_day` jest nową kolumną obok `operation_date`; seed generuje stany z Operacji

Migracje schematu powstają wyłącznie z `alembic revision --autogenerate`, są addytywne (kolumny `null` albo z `server_default`), a dane pochodne i wsteczne uzupełnienia robi idempotentna komenda CLI. Data kalendarzowa Operacji (D13) trafia do **nowej** kolumny `operation_day`, bo zmiana typu istniejącej kolumny wymagałaby ręcznej edycji migracji. Seed przestaje trzymać zahardkodowane stany, które nie zgadzają się z replayem Operacji.

**Rozstrzyga:** D16 i techniczną część D13 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E2.0, E2.3, E2.5, E0.5 (migracja pola tymczasowego). Reguła interpretacji `fx_rate` (D4) jest decyzją biznesową, poza tym ADR-em.

## Kontekst

- `operation_date` to `DateTime(timezone=True)` (`backend/app/modules/portfolios/models/operation.py:57`); schematy wystawiają `datetime` (`schemas/operations.py:54`, `:93`). Wektory liczą dzień **w UTC** (`services/metrics.py:147-149`), a Operacja z godziny 00:30 w Warszawie ląduje dzień wcześniej.
- `ALTER COLUMN … TYPE date` z `timestamptz` bez `USING` rzutuje wg strefy sesji bazy (`factory.py` jej nie ustawia, `backend/app/infrastructure/sql/factory.py:45-55`); `autogenerate` nie dopisze `postgresql_using`, a ręczna edycja migracji jest zakazana ([architektura §9](../backend/01_backend-architecture.md), CLAUDE.md repo).
- `alembic/env.py:74-75` ma `compare_type=True` i `compare_server_default=True`, więc `autogenerate` wykrywa zmianę typu i wartości domyślnych; zmianę `nullable` wykrywa domyślnie.
- **Seed nie zgadza się z księgą.** Replay Operacji z `backend/seed/seed_data.py` przez `PortfolioLedger.rebuild` (uruchomiony 2026-10-02; Operacje po `days_ago` malejąco) daje:

| Portfel | Seed (`seed_data.py`) | Replay Operacji |
|---|---|---|
| US Stocks | gotówka 15 000 (`:191`) | 8 971,50 |
| European Portfolio | gotówka 8 000 | 7 561,95 |
| Polish Stocks | gotówka 25 000 | 12 669,30 |
| Crypto Portfolio | wpłata 8 000 | `InsufficientCashError`: zakup BTC 8 120 > 8 000; z ETH wymagane ≥ 15 632 |
| AAPL w US Stocks | dywidendy 18,50 (`:222`), cena średnia 180 | dywidendy 15,00 (Operacja `:359`), cena średnia 180,33 (z prowizją) |

  Cena średnia pozycji w replayu zawiera prowizję (stąd 180,33 zamiast 180), a `total_fees` zgadza się tylko w części pozycji (US Stocks: AAPL 7,00 vs 5,00, NVDA 5,00 vs 7,50). Seed wstawia stany wprost (`seed.py:270`) i osobno Operacje (`seed.py:288-302`), więc kryterium E2.0 „`rebuild-all` na seed daje stan identyczny z obecnym” jest **fałszywe**.

## Decyzja

**1. Polityka migracji (D16)**

| Reguła | Treść |
|---|---|
| M1 | Migracja tylko z `alembic revision --autogenerate`; model w `models_registry.py`; `alembic check` bez dryfu |
| M2 | Nowa kolumna: `nullable=True` albo `server_default`; „NOT NULL bez defaultu” w dwóch krokach (pkt 3) |
| M3 | Zmiany typu istniejącej kolumny z niejawnym rzutowaniem — zakazane; nowa kolumna obok, stara wygaszona osobnym ADR-em |
| M4 | Dane (backfill, przeniesienia) **nie** w migracjach; idempotentne polecenie CLI ([ADR-0017](0017-zadania-w-tle-i-cli.md)), np. `rebuild-all` — dotyczy też „pola tymczasowego” z E0.5, znikającego w E1.2 |

**2. `operation_day` i `sequence`**
- `operation_day` `Date` (kalendarz **Europe/Warsaw**, D13) — nowa kolumna, `null` w migracji A; źródło prawdy dla porządku, podatku i snapshotów. `operation_date` (`timestamptz`) zostaje jako moment zdarzenia (godzina opcjonalna); wygaszenie po przejściu frontendu — osobny ADR.
- `sequence` `Integer`, `server_default '0'`, NOT NULL — porządek w obrębie dnia; globalny klucz (`operation_day`, `sequence`, `id`) ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)).
- **Zapis:** serwis wylicza `operation_day` z `operation_date` przez `zoneinfo.ZoneInfo("Europe/Warsaw")` (`tzdata` jest w `requirements.txt:68`), nie SQL-em — niezależnie od strefy sesji.
- Wektory metryk przechodzą na `operation_day` (zamiast dnia UTC, `metrics.py:147`).
- **Backfill:** `rebuild-all` zapisuje w istniejących wierszach `operation_day` (tą samą funkcją), `sequence` (wg dotychczasowej kolejności `operation_date`, `created_at`, `id`, `repositories/operations.py:53-57`, numerowane per (Portfel, `operation_day`)) i `currency_id` = waluta bazowa Portfela ([ADR biznesowy 0003](../../business/adr/0003-gotowka-wielowalutowa.md) pkt 4). Pozycje aktualizuje **w miejscu** (zachowuje `opened_at`), nie kasuje ich i nie odtwarza. Zapis jest deterministyczny, więc drugi przebieg nic nie zmienia.

**3. Kolejność wdrożenia**
1. Migracja A (`autogenerate`): nowe tabele i kolumny `null`/`server_default`.
2. Wdrożenie kodu zapisującego `operation_day`/`sequence` (odczyt nadal po `operation_date`).
3. `rebuild-all`: backfill, partie, snapshoty, salda; `rebuild-all --check` zwraca 1 przy różnicach względem zapisanych stanów.
4. Weryfikacja: drugi przebieg = 0 zapisów; dane właściciela porównane z kopią sprzed zmiany.
5. Migracja B (`autogenerate`): `operation_day` NOT NULL (zmianę `nullable` wykrywa `autogenerate`); potem odczyty na `operation_day`.

**4. Seed generuje stany z Operacji**
- `seed_data.py` zawiera Operacje i dane referencyjne; **usuwamy** `cash_balance`/`total_deposited` z `PortfolioSeed` (`:187-211`) i `POSITIONS` (`:214-312`). Portfel startuje od 0.
- Po wstawieniu Operacji seed woła przebudowę przez `wiring.py` (wyjątek od R5 dla `backend/seed/`, [ADR-0002](0002-sesja-poza-zadaniem-entrypointy-i-wiring.md)); stany i pozycje powstają z `PortfolioLedger`.
- Dane Operacji muszą dać poprawny replay: wpłata Crypto Portfolio 8 000 → **16 000** (zakupy BTC/ETH wymagają ≥ 15 632) **[propozycja]**; test seeda: replay seeda nie rzuca, a przebudowa dwukrotnie daje ten sam stan.
- Kryterium E2.0 obowiązuje dopiero po naprawie seeda i brzmi: „`rebuild-all` na seed daje stan równy replayowi Operacji; drugi przebieg bez zmian”. Kryterium E0.5 to samo sprawdza replayem przez `PortfolioLedger` (bez `rebuild-all`, który powstaje w E2.0).

## Rozpatrywane alternatywy

- **`ALTER COLUMN operation_date TYPE date`.** Wynik zależy od strefy sesji (przesunięcie dnia dla godzin 00:00–02:00 czasu warszawskiego); korekta wymaga ręcznej edycji migracji. Odrzucone.
- **Backfill w migracji (`op.execute`).** Zakazana edycja, brak idempotencji, niepowtarzalne dla kopii danych. Odrzucone.
- **Poprawić tylko liczby w seedzie.** Wartości znów rozjadą się przy zmianie reguł księgi (np. prowizja w cenie średniej). Odrzucone.

## Konsekwencje

**Pozytywne**
- Brak ręcznych edycji migracji; dzień Operacji nie zależy od strefy bazy ani procesu.
- Seed jest testem zgodności księgi z danymi startowymi, nie drugim źródłem prawdy.

**Negatywne**
- Dwie kolumny dat do czasu wygaszenia `operation_date`; `rebuild-all` jest krokiem wdrożenia (kolejność ma znaczenie).

## Otwarte
- Strefa backfillu: stała Europe/Warsaw (D13) czy ustawienie użytkownika z E0.9 — przyjęto stałą.
