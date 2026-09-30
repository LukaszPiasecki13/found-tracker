---
id: be-assets-module
status: current
last_reviewed: 2026-09-30
type: mixed
scope: backend/assets
applies_to:
  - backend/app/modules/assets/**
---

# Moduł `assets`

Walory, klasy waloru, waluty oraz dane rynkowe (ceny i kursy z Yahoo Finance przez `yfinance`). Dane referencyjne, na których buduje [`portfolios`](./05_portfolios_module.md). Słownik: [`CONTEXT.md`](../../business/CONTEXT.md).

## 1. Model danych

| Tabela | Encja | Pola |
|---|---|---|
| `assets_assetclass` | `AssetClass` | `id`, `name` (unikalna, max 20) |
| `assets_currency` | `Currency` | `id`, `code` (unikalny, 3), `exchange_rate` (`Numeric(18,9)`), `base_currency_id` |
| `assets_asset` | `Asset` | `id`, `ticker` (unikalny), `name`, `asset_class_id`, `currency_id`, `current_price`, `exchange`, `sector`, `updated_at` |

## 2. Endpointy

| Prefiks | Zasób |
|---|---|
| `/currencies` | CRUD walut |
| `/assets/asset-classes` | CRUD klas waloru |
| `/assets` | CRUD walorów |
| `/assets/search-yahoo`, `/assets/create-from-yahoo` | Wyszukiwanie i tworzenie waloru z danych Yahoo |

## 3. Reguły biznesowe

- Unikalność: `ticker` walorów, `code` walut, `name` klas — konflikt → `ConflictError` z `code`.
- Dane rynkowe są **zależnością zewnętrzną**: błąd pobrania to sytuacja normalna. Odświeżanie wielu walut nie przerywa się przy błędzie jednej (polityka domenowa, ewentualnie w `entrypoints.py` — [`06_wiring_i_entrypointy.md` §4](./06_wiring_i_entrypointy.md#4-wejście-spoza-http--entrypointspy)).
- Dostęp do Yahoo Finance jest **adapterem**: `yfinance` nie wchodzi do `domain/` (DOM-1). Serwis `MarketDataService` zostaje w `services/`; jego zależność od `yfinance` ukrywa port (`Protocol`) wstrzykiwany w `wiring.py`, co pozwala testować serwis bez sieci.

## 4. Układ docelowy

```text
assets/
├─ api/{assets,currencies}.py
├─ services/{assets,currencies,market_data}.py
├─ repositories/{assets,currencies}.py
├─ schemas/{assets,currencies}.py
├─ models/{assets,currencies}.py
├─ dependencies.py
├─ wiring.py
├─ entrypoints.py        # refresh_currency_rates (opcjonalnie)
└─ tests/{unit,integration}/
```

Moduł nie ma `domain/` — to w przeważającej mierze CRUD plus I/O (DOM-7).

## 5. Stan vs cel

| Element | Stan | Cel | Krok |
|---|---|---|---|
| Struktura | podfoldery `api/`, `models/`, `repositories/`, `schemas/` — tak; `services/service.py` (jedna klasa `MarketDataService`) | osobne serwisy zasobów (`assets`, `currencies`) + `market_data`; CRUD poza routerem | R-04 |
| Logika w routerze | `api/assets.py` (219 linii): sprawdzanie duplikatów, tworzenie z Yahoo, konwersje | delegacja do serwisów | R-04 |
| Błędy | `HTTPException` 404/409 w routerach; `raise Exception(...)` w `MarketDataService` | `NotFoundError`/`ConflictError` z `code`; błąd dostawcy jako wyjątek domenowy | R-01, R-04 |
| Transakcje | repo commituje | `transaction()` w serwisie | R-02 |
| Wiring | łańcuch `Depends` | `wiring.py` | R-04 |
| Testy | `tests/integration/test_assets_flow.py` | dodać `tests/unit/` z zamockowanym portem rynkowym | R-04 |
