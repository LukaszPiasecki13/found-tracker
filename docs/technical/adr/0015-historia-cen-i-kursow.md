---
id: adr-0015-price-and-fx-history
status: Accepted
type: decision
scope: assets/price-fx-history
last_reviewed: 2026-10-05
---

# Ceny i kursy walut są historią w bazie (`assets_price`, `assets_fx_rate`), nieskorygowaną i z jawnym źródłem; „bieżąca cena” jest pochodną

`Currency.exchange_rate` i `Asset.current_price` przestają być źródłem prawdy; kurs krzyżowy składa `portfolios`.

**Blokuje:** E0.1, E1.1, E1.2, E1.5, E2.3.

## Kontekst

- Wycena czyta skalary nadpisywane w miejscu (`portfolios/domain/valuation.py:55-57`, `assets/services/market_data.py:105`); kursy względem USD, bez krzyżowych.
- Adapter woła `history(...)` bez jawnego `auto_adjust` (`infrastructure/market_data/yahoo.py:64`); domyślne zachowanie `yfinance` 1.3.0 **[niezweryfikowane]**.
- Operacja ma jeden `fx_rate` (`models/operation.py:52`); wycena potrzebuje osobnego kursu dziennego.

## Decyzja

**1. Tabele w `assets`** (migracja `autogenerate`, [ADR-0019](0019-migracje-danych-i-kolumny-dat.md)):

| Tabela | Kolumny | Klucze |
|---|---|---|
| `assets_price` | `asset_id`, `price_date`, `close` `Numeric(18,9)`, `currency_id`, `source` `String(20)`, `is_synthetic`, `fetched_at` | UNIQUE (`asset_id`, `price_date`, `source`) |
| `assets_fx_rate` | `from_currency_id`, `to_currency_id`, `rate_date`, `rate` `Numeric(18,9)`, `source`, `fetched_at`, `is_synthetic` | UNIQUE (`from`, `to`, `rate_date`, `source`) |
| `assets_listing` | `asset_id`, `provider`, `symbol`, `priority` `SmallInteger` | UNIQUE (`asset_id`, `provider`) |

`rate` = jednostek `to` za jedną `from`; NBP (tabela A, `mid`): `XXX → PLN`.

**2. Ceny nieskorygowane.** `auto_adjust=False` jawnie, kolumna `Close`. Test kontraktowy na walorze po splicie. Split jest zdarzeniem księgi (E8.1).

**3. Źródło i `is_synthetic`.** `source` ∈ {`manual`, `nbp`, `yahoo`}; `manual` tylko awaryjnie. `is_synthetic = true`: cena przed końcem sesji lub oszacowanie. Forward-fill nie jest zapisywany: `find_close(asset, date)` zwraca ostatnie zamknięcie ≤ `date` z `price_date` i flagą `stale`. **[propozycja]**

**4. Priorytet źródeł.** Wygrywa najniższa ranga: `manual` = 0, dostawca = `assets_listing.priority` ≥ 1, nieznane = 1000. Zmiana `priority` lub cena `manual` zmienia cenę od najstarszej daty ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)).

**5. „Ostatnia cena” jako pochodna.** `Asset.current_price` i `Currency.exchange_rate` zostają kolumnami-cache, ustawianymi tylko przez serwis `assets`, w tej samej transakcji co zapis najnowszego wiersza historii. Ręczna edycja zapisuje wiersz `source=manual` z dzisiejszą datą.

**6. Kurs krzyżowy składa `portfolios`.** `assets` zwraca tylko kursy bezpośrednie i odwrotne (`GET /assets/currencies/rate`). `FxMapBuilder` w `portfolios`: para → odwrotność → pivot [PLN, waluta systemowa] **[propozycja]**; mapa `{(z, do): Decimal}` na dzień wyceny. Brak kursu → `RATE_MISSING`. `domain/` dostaje tylko mapę.

**7. Dwa kursy na zdarzenie**

| Kurs | Miejsce | Do czego |
|---|---|---|
| brokera | `portfolios_operation.fx_rate` | księga, gotówka |
| wyceny | `portfolios_position_daily.fx` (ADR-0016), dzienny z `assets_fx_rate` | wartość, wykresy |

Brakujące kursy dzienne uzupełnia `refresh-fx` ([ADR-0017](0017-zadania-w-tle-i-cli.md)).

## Alternatywy

- Forward-fill jako wiersze — mnoży wiersze; odrzucone.
- Priorytet w `assets_price` — duplikat reguły; odrzucone.
- Jedna para kursów względem USD — brak kursów krzyżowych z PLN; odrzucone.
- Skorygowane ceny — split liczony dwa razy; odrzucone.

## Konsekwencje

- (+) Wyceny bez sieci w żądaniu.
- (−) Przejściowo cache + historia; pivot i `is_synthetic` robocze.

## Otwarte

- Walor do testu splitu; `auto_adjust` w `yfinance` 1.3.0 (E1.2).
  - *Rozstrzygnięte 2026-10-05 (weryfikacja na DNP.WA, split 10:1 z 2025-07-31, i NVDA):* `Close` z `auto_adjust=False` jest **skorygowany o splity** (koryguje tylko dywidendy `Adj Close`), więc sam `auto_adjust=False` nie daje cen nieskorygowanych. Adapter mnoży zamknięcia przez splity późniejsze niż ich dzień (`Ticker.splits`), co przywraca ceny z dnia; test kontraktowy na walorze po splicie: `test_yahoo_provider.py`.
- Czy lista wyceny pokazuje pozycje częściowo przy `RATE_MISSING` (E0.1).
