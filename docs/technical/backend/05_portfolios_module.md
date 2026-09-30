---
id: be-portfolios-module
status: current
last_reviewed: 2026-09-30
type: mixed
scope: backend/portfolios
applies_to:
  - backend/app/modules/portfolios/**
---

# Moduł `portfolios`

Serce aplikacji: portfele, pozycje, operacje (kupno, sprzedaż, wpłata, wypłata, dywidenda) oraz metryki i wektory portfela do wykresów. Słownik: [`CONTEXT.md`](../../business/CONTEXT.md). Logika biznesowa pochodzi z Django (`backend-old/portfolios/services/`, `backend-old/portfolios/analytics/`) — referencja, nie kod do importu ([ADR-0009](../adr/0009-backend-old-jako-referencja.md)).

## 1. Model danych

| Tabela | Encja | Kluczowe pola |
|---|---|---|
| `portfolios_portfolio` | `Portfolio` | `owner_id`, `name` (unikalna per właściciel), `base_currency_id`, `cash_balance`, `total_deposited`, `is_active` |
| `portfolios_position` | `Position` | `portfolio_id`, `asset_id` (unikalna para), `quantity`, `average_buy_price`, `average_fx_rate`, `total_fees`, `total_dividends` |
| `portfolios_operation` | `Operation` | `portfolio_id`, `asset_id?`, `operation_type`, `quantity`, `price`, `amount?`, `fee`, `fx_rate`, `operation_date` |

Kwoty i ilości: `Numeric` ↔ `Decimal` ([ADR-0010](../adr/0010-decimal-i-precyzja-pieniedzy.md)). **Pozycja i saldo są pochodnymi Operacji** — `rebuild_portfolio` odtwarza je z historii.

## 2. Endpointy

| Metoda i ścieżka | Opis |
|---|---|
| `GET/POST /portfolios/`, `PUT/PATCH/DELETE /portfolios/{id}` | CRUD portfeli (widok z wyliczonymi polami) |
| `GET /portfolios/positions` | Pozycje z wyliczonymi polami (wartość, zwrot, zysk) |
| `GET /portfolios/operations`, `POST`, `PUT/PATCH/DELETE /portfolios/operations/{id}` | Operacje |
| `GET /portfolios/portfolio-vectors` | Wektory metryk w zadanym przedziale (`1d`) |

Wszystkie endpointy wymagają zalogowanego użytkownika i działają wyłącznie na jego portfelach (`owner_id`); cudzy portfel → 404, nie 403 (nie ujawniamy istnienia).

## 3. Reguły biznesowe (przeniesione z Django)

- **Kupno:** wymaga waloru, `quantity > 0`, `price > 0`, `fee ≥ 0`, `fx_rate > 0`; koszt `(ilość × cena + opłata) × fx_rate` musi się mieścić w saldzie gotówki; średnie ceny i kurs liczone ważoną średnią.
- **Sprzedaż:** wymaga istniejącej pozycji i wystarczającej ilości; wpływ `(ilość × cena − opłata) × fx_rate`; pozycja o ilości 0 jest usuwana.
- **Wpłata / wypłata:** `amount > 0`, `fee ≥ 0`; wypłata nie może przekroczyć salda; zmieniają `total_deposited`; operacje nie mają waloru.
- **Dywidenda:** wymaga pozycji; zwiększa `total_dividends` i saldo o `(kwota − opłata) × fx_rate`.
- **Usunięcie / edycja operacji:** przebudowa salda i pozycji z pozostałej historii w kolejności `(operation_date, created_at, id)`.
- **Jeden moment prawdy:** walidacja liczbowa (znaki, relacje) jest regułą **domeny**, nie routera (dziś zduplikowana w `api.py` i serwisach).

## 4. Warstwa `domain/` (plan)

Reguły z §3 są czystą arytmetyką na `Decimal` — kandydat na `portfolios/domain/` ([ADR-0005](../adr/0005-warstwa-domeny.md)). Proponowany układ (DOM-9: słownik → silnik → komponenty):

| Plik | Zawartość |
|---|---|
| `domain/enums.py` | `OperationType` (`StrEnum`) |
| `domain/errors.py` | wyjątki domenowe (podklasy `ValueError`): `InsufficientCash`, `InsufficientQuantity`, `InvalidAmount`, … |
| `domain/ledger.py` | `PortfolioLedger` (komponent): `apply(state, operation) -> state` dla każdego typu operacji; `rebuild(operations) -> state` |
| `domain/protocols.py` | `Protocol`y widoków `Portfolio`/`Position`/`Operation` (DOM-8) |

Serwis (`OperationService`) ładuje portfel i pozycje, woła komponent, zapisuje wynik w jednej `transaction()` i tłumaczy wyjątki domenowe na `BadRequestError` z `code`.

**Metryki (wektory).** `portfolios/analytics/portfolio_metrics.py` używa `numpy`/`pandas` i pobiera historię cen z `yfinance` w środku obliczeń. Obliczenia na wektorach nie spełniają DOM-1 (biblioteka standardowa). Rozstrzygnięcie — **otwarte**, patrz [ADR-0005, sekcja „Otwarte”](../adr/0005-warstwa-domeny.md): dwa warianty (a) metryki zostają w `services/metrics.py` jako adapter, historia cen wstrzykiwana portem; (b) `numpy` dopuszczony w `domain/` wyjątkiem. Niezależnie od wariantu: **pobieranie cen wychodzi z obliczeń** (port `PriceHistoryProvider`, implementacja w `assets`).

## 5. Układ docelowy

```text
portfolios/
├─ api/{portfolios,operations,metrics}.py
├─ services/{portfolios,operations,metrics}.py
├─ domain/{enums,errors,ledger,protocols}.py      # + __init__.py z __all__
├─ repositories/{portfolios,positions,operations}.py
├─ schemas/{portfolios,operations,metrics}.py
├─ models/{portfolio,position,operation}.py
├─ dependencies.py
├─ wiring.py
└─ tests/{unit,integration}/
```

Zależności zewnętrzne: `assets` (walor, waluta, ceny) przez `AssetService` / port cen; `core_data` (właściciel) tylko przez `get_current_user`.

## 6. Stan vs cel

| Element | Stan | Cel | Krok |
|---|---|---|---|
| Struktura | płaskie `api.py` (493 linie), `models.py`, `repository.py`, `schemas.py`; `services/` i `analytics/` są podfolderami | wg §5 | R-07 |
| Logika w routerze | `create_operation` (≈120 linii): wyszukanie/utworzenie waloru, walidacja, dispatch po typie, zapis operacji; `_compute_position_fields` liczy metryki na `float` | delegacja do `OperationService` | R-07, R-08 |
| API → repozytoria | router importuje `AssetRepository`, `AssetClassRepository`, `OperationRepository` i modele `assets` | tylko serwisy ([ADR-0006](../adr/0006-cross-module-wylacznie-przez-serwisy.md)) | R-07 |
| Serwisy przyjmują `dict` | `execute_buy(data: dict)`, `deposit_cash(data: dict)` z kluczami `portfolio`/`asset` | typowane argumenty / value objecty | R-08 |
| Błędy | `ValueError` z serwisów, `HTTPException` w routerze (`except Exception → 400`) | wyjątki domenowe → `BadRequestError` z `code` | R-01, R-08 |
| Transakcje | `commit=False` rozsiane po repozytoriach + ręczny `op_repo.commit()` w routerze | `transaction()` w serwisie | R-02, R-08 |
| Pieniądze | `Decimal` w serwisach, `float` w routerze i `PortfolioMetrics` | `Decimal` do granicy schematu ([ADR-0010](../adr/0010-decimal-i-precyzja-pieniedzy.md)) | R-08 |
| `analytics/` | `AssetCalculator` woła `yfinance` w konstruktorze (I/O w konstruktorze), `PortfolioMetrics` pobiera historię w pętli | port cen + obliczenia oddzielone od I/O | R-08 |
| Testy | `tests/test_api.py`, `test_services.py` płasko, `integration/test_portfolio_flow.py` | `tests/unit/`, `tests/integration/` | R-07 |
