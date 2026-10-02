---
id: adr-0015-price-and-fx-history
status: Proposed
type: decision
scope: assets/price-fx-history
last_reviewed: 2026-10-02
---

# Ceny i kursy walut są historią w bazie (`assets_price`, `assets_fx_rate`), nieskorygowaną i z jawnym źródłem; „bieżąca cena” jest pochodną

`Currency.exchange_rate` i `Asset.current_price` przestają być źródłem prawdy; kurs krzyżowy składa `portfolios`.

**Rozstrzyga:** D5, część D7 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)); reszta — [ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md). **Blokuje:** E0.1, E1.1, E1.2, E1.5, E2.3, E6.

## Kontekst

- Wycena czyta skalary nadpisywane w miejscu (`portfolios/domain/valuation.py:55-57`, `assets/services/market_data.py:105`); kursy względem USD, bez krzyżowych.
- Adapter woła `history(...)` bez jawnego `auto_adjust` (`infrastructure/market_data/yahoo.py:64`); domyślne zachowanie `yfinance` 1.3.0 **[niezweryfikowane]**.
- Operacja ma jeden `fx_rate` (`models/operation.py:52`); podatek wymaga NBP D−1 z numerem tabeli.

## Decyzja

**1. Tabele w `assets`** (migracja `autogenerate`, [ADR-0019](0019-migracje-danych-i-kolumny-dat.md)):

| Tabela | Kolumny | Klucze |
|---|---|---|
| `assets_price` | `asset_id`, `price_date`, `close` `Numeric(18,9)`, `currency_id`, `source` `String(20)`, `is_synthetic`, `fetched_at` | UNIQUE (`asset_id`, `price_date`, `source`) |
| `assets_fx_rate` | `from_currency_id`, `to_currency_id`, `rate_date`, `rate` `Numeric(18,9)`, `source`, `table_no` `String(32)` null, `fetched_at`, `is_synthetic` | UNIQUE (`from`, `to`, `rate_date`, `source`) |
| `assets_listing` | `asset_id`, `provider`, `symbol`, `priority` `SmallInteger` | UNIQUE (`asset_id`, `provider`) |

`rate` = jednostek `to` za jedną `from`; NBP (tabela A, `mid`): `XXX → PLN`.

**2. Ceny nieskorygowane.** `auto_adjust=False` jawnie, kolumna `Close`. Test kontraktowy na walorze po splicie. Split jest zdarzeniem księgi (E8.1).

**3. Źródło i `is_synthetic`.** `source` ∈ {`manual`, `nbp`, `yahoo`, `stooq`, …}. `is_synthetic = true`: cena przed końcem sesji, wartość wyliczona (E5.1, E5.5) lub oszacowanie. Forward-fill nie jest zapisywany: `find_close(asset, date)` zwraca ostatnie zamknięcie ≤ `date` z `price_date` i flagą `stale`. **[propozycja]**

**4. Priorytet źródeł.** Wygrywa najniższa ranga: `manual` = 0, dostawca = `assets_listing.priority` ≥ 1, nieznane = 1000. Zmiana `priority` lub cena `manual` zmienia cenę od najstarszej daty ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)).

**5. „Ostatnia cena” jako pochodna.** `Asset.current_price` i `Currency.exchange_rate` zostają kolumnami-cache, ustawianymi tylko przez serwis `assets`, w tej samej transakcji co zapis najnowszego wiersza historii. Ręczna edycja zapisuje wiersz `source=manual` z dzisiejszą datą.

**6. Kurs krzyżowy składa `portfolios`.** `assets` zwraca tylko kursy bezpośrednie i odwrotne (`GET /assets/currencies/rate`). `FxMapBuilder` w `portfolios`: para → odwrotność → pivot [PLN, waluta systemowa] **[propozycja]**; mapa `{(z, do): Decimal}` na dzień wyceny. Brak kursu → `RATE_MISSING`. `domain/` dostaje tylko mapę.

**7. Trzy kursy na zdarzenie (D5)**

| Kurs | Miejsce | Do czego |
|---|---|---|
| brokera | `portfolios_operation.fx_rate` | księga, gotówka |
| wyceny | `portfolios_position_daily.fx` (ADR-0016) | wartość, wykresy |
| podatkowy | Operacja: `fx_rate_tax` `Numeric(18,9)`, `fx_tax_date`, `fx_tax_table_no` `String(32)` (null) | PIT-38 |

Kurs podatkowy: NBP tabela A, `effectiveDate` < `settlement_date` (D12; dywidenda — dzień wypłaty), cofanie po 404. Przyszła data → `null`; `refresh-fx` ([ADR-0017](0017-zadania-w-tle-i-cli.md)) wypełnia braki.

## Alternatywy

- Forward-fill jako wiersze — mnoży wiersze; odrzucone.
- Priorytet w `assets_price` — duplikat reguły; odrzucone.
- Jedna para kursów względem USD — podatek wymaga NBP/PLN; odrzucone.
- Skorygowane ceny — split liczony dwa razy; odrzucone.

## Konsekwencje

- (+) Wyceny bez sieci w żądaniu; numer tabeli NBP jest dowodem.
- (−) Przejściowo cache + historia; pivot i `is_synthetic` robocze.

## Otwarte

- Walor do testu splitu; `auto_adjust` w `yfinance` 1.3.0 (E1.2).
- Czy lista wyceny pokazuje pozycje częściowo przy `RATE_MISSING` (E0.1).
