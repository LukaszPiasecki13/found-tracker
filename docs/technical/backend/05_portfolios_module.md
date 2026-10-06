---
id: be-portfolios-module
status: current
last_reviewed: 2026-10-06
type: mixed
scope: backend/portfolios
applies_to:
  - backend/app/modules/portfolios/**
---

# Moduł `portfolios`

Serce aplikacji: portfele, pozycje, operacje (kupno, sprzedaż, wpłata, wypłata, dywidenda, odsetki, opłata) oraz metryki i wektory portfela do wykresów. Słownik: [`CONTEXT.md`](../../business/CONTEXT.md). Logika biznesowa pochodzi z dawnej aplikacji Django, usuniętej w R-13 (ADR-0009, usunięty); jej zachowanie chronią testy parytetu. Jedyny moduł z warstwą `domain/` ([ADR-0005](../adr/0005-warstwa-domeny.md)).

## 1. Model danych

| Tabela | Encja | Kluczowe pola |
|---|---|---|
| `portfolios_portfolio` | `Portfolio` | `owner_id`, `name` (unikalna per właściciel), `base_currency_id`, `cash_balance` `(18,3)`, `total_deposited` `(18,3)`, `dirty_from?` (data, od której wiersze `portfolios_daily` są nieaktualne), `is_active` |
| `portfolios_daily` | `PortfolioDaily` | pochodna Operacji i cen ([ADR-0016](../adr/0016-snapshoty-dzienne-i-przebudowa.md)): PK `(portfolio_id, day)`, `value`, `cash`, `inflow`, `outflow` `(18,3)`, `r_day`, `twr_index` `(24,12)` — [§6.1](#61-zwrot-portfela-twr-i-snapshoty-dzienne) |
| `portfolios_position` | `Position` | `portfolio_id`, `asset_id` (unikalna para), `quantity` `(18,9)`, `average_buy_price` `(18,9)`, `average_fx_rate` `(18,9)`, `total_fees` `(18,2)`, `total_dividends` `(18,2)`, `opened_at` |
| `portfolios_operation` | `Operation` | `portfolio_id`, `asset_id?`, `operation_type` (wartość `OperationType`), `quantity`, `price`, `amount?` `(18,2)`, `fee` `(18,2)`, `fx_rate`, `notes?`, `operation_date`, `external_ref?` (id w źródle importu; częściowo unikalny z `portfolio_id`), `import_batch_id?`, `edited_at?` (ustawiane przy ręcznej zmianie pola) |
| `portfolios_import_batch` | `ImportBatch` | paczka importu: `owner_id`, `portfolio_id`, `parser_id`, `filename`, `sha256` (unikalny per właściciel), `file`, `status`, `payload` — [`07_import.md`](./07_import.md) |
| `portfolios_import_row` | `ImportRow` | wiersz paczki: `row_number`, `row_status`, `payload`, `dedup_key`, `asset_id?`, `operation_id?` |

Modele w stylu `Mapped[...]`/`mapped_column`; kwoty i ilości to `Numeric` ↔ `Decimal` ([ADR-0010](../adr/0010-decimal-i-precyzja-pieniedzy.md)). **Pozycja i saldo są pochodnymi Operacji** — edycja lub usunięcie operacji odtwarza je z historii. Kolumny `Numeric` zaokrąglają przy zapisie: to jedyna granica zaokrąglenia stanu (domena liczy bez zaokrągleń).

## 2. Endpointy

Wszystkie wymagają zalogowanego użytkownika (`get_current_user`) i działają wyłącznie na jego danych; cudzy portfel lub operacja → 404, nigdy 403 (nie ujawniamy istnienia). Parametry ścieżki mają konwerter `:int`, więc `/portfolios/positions`, `/portfolios/operations` i `/portfolios/portfolio-vectors` nigdy nie trafiają do `/{id}`.

| Metoda i ścieżka | Odpowiedź |
|---|---|
| `GET /portfolios/?name=` | `PortfolioSummaryResponse[]` — portfel z polami wyliczonymi (`positions_value`, `total_value`, `total_profit_loss`, `total_return_pct` (TWR), `return_method`, `total_fees`) |
| `POST /portfolios/` | 201, `PortfolioResponse` (encja, bez pól wyliczonych) |
| `GET /portfolios/{id}` | `PortfolioDetailResponse` — podsumowanie + `positions` (wycenione, z `portfolio_weight_pct`) + `updated_at` |
| `PUT`/`PATCH /portfolios/{id}` | `PortfolioResponse`; jawny `null` = „bez zmian” |
| `DELETE /portfolios/{id}` | 204; usuwa też pozycje i operacje |
| `GET /portfolios/fx-rate?from_currency=&to_currency=` | `FxRateResponse` — kurs krzyżowy (`rate`, `via`: `identity/direct/inverse/cross`) składany z kursów `assets`; `CURRENCY_NOT_FOUND`, `RATE_MISSING` (oba 404); podpowiedź kursu w dialogach kupna/sprzedaży |
| `GET /portfolios/positions?portfolio_name=` | `PositionResponse[]` — wycena po zapisanych cenach, bez efektów ubocznych |
| `POST /portfolios/positions/refresh?portfolio_name=` | `PositionResponse[]` — najpierw odświeża kursy walut i ceny walorów pozycji (best-effort, [`04_assets_module.md` §3](./04_assets_module.md#3-reguły-biznesowe)), potem wycenia |
| `GET /portfolios/operations?portfolio_name=` | `OperationResponse[]`, od najnowszej (`operation_date`, `created_at`) |
| `POST /portfolios/operations` | 201, `OperationResponse` |
| `PUT`/`PATCH /portfolios/operations/{id}` | `OperationResponse`; zmienia `quantity`, `price`, `amount`, `fee`, `fx_rate`, `notes`, `operation_date` (typ i walor są stałe; jawny `null` = „bez zmian”, poza `notes`) |
| `DELETE /portfolios/operations/{id}` | 204 |
| `GET /portfolios/portfolio-vectors?portfolioName=&startDate=&endDate=&interval=&vectors=` | `PortfolioVectorsResponse` (§6) |

Kwoty w JSON są liczbami (`core.schemas.DecimalNumber`). Schematy żądań mają `extra="forbid"` i sprawdzają tylko kształt (typy, długości, pojemność kolumn `Numeric`); znaki i relacje pól sprawdza domena — w jednym miejscu.

## 3. Reguły biznesowe

Wszystkie reguły liczbowe są w `PortfolioLedger` (§4); router i schematy ich nie powtarzają.

- **Kupno:** walor, `quantity > 0`, `price > 0`, `fee ≥ 0`, `fx_rate > 0`; koszt `(ilość × cena + opłata) × fx_rate` musi się mieścić w saldzie; zakup może zejść do 0,50 poniżej zera ([ADR-0021](../adr/0021-tolerancja-ujemnego-salda-przy-zakupie.md)). Średnia cena (w walucie waloru, z opłatą) `(q₀·śr₀ + q·cena + opłata) / (q₀ + q)`; średni kurs ważony ilością `(q₀·fx₀ + q·fx) / (q₀ + q)`; `total_fees += opłata`.
- **Sprzedaż:** walor, te same znaki co kupno; pozycja musi istnieć i mieć dość ilości; wpływ `(ilość × cena − opłata) × fx_rate`; średnie bez zmian (średnia ważona, nie FIFO); `total_fees += opłata`; pozycja o ilości 0 jest usuwana.
- **Wpłata / wypłata:** bez waloru, `amount > 0`, `fee ≥ 0`. Wpłata: saldo `+= amount − fee`, `total_deposited += amount`. Wypłata: `amount + fee` musi się mieścić w saldzie; saldo `-= amount + fee`, `total_deposited -= amount`.
- **Odsetki / opłata** (`interest`, `fee`): bez waloru, `amount > 0`, `fee ≥ 0`; **nie ruszają `total_deposited`**. Odsetki: saldo `+= amount − fee`. Opłata (np. podatek od odsetek): `amount + fee` musi się mieścić w saldzie; saldo `-= amount + fee`. W metrykach odsetki są ujemnym kosztem, opłata kosztem — `free_cash` zgadza się z saldem księgi. Pochodzą z importu ([`07_import.md`](./07_import.md)); frontend jeszcze ich nie zna.
- **Dywidenda:** walor z otwartą pozycją, `amount > 0`, `fee ≥ 0`, `fx_rate > 0`; `total_dividends += amount`, saldo `+= (amount − fee) × fx_rate`.
- **Split:** walor z otwartą pozycją, `ratio > 0` (kolumna `portfolios_operation.ratio`, [ADR-0020](../adr/0020-plaski-model-operacji.md)); ilość `×= ratio`, średnia cena `÷= ratio`, więc koszt łączny, opłaty i dywidendy zostają, a gotówka się nie zmienia. Wykresy w czasie (`MetricsService`) liczą ilość w jednostkach danego dnia (split mnoży ją od swojego dnia), a ceny z dostawcy też są w jednostkach dnia ([`04_assets_module.md` §3](./04_assets_module.md#3-reguły-biznesowe)).
- **`amount` przy kupnie i sprzedaży** jest informacyjny (frontend wysyła `ilość × cena ± opłata`) — zapisywany, nieczytany przez księgę.
- **Rejestracja operacji** (`POST`): księga stosuje operację do **bieżącego** stanu (salda i pozycji z bazy), niezależnie od `operation_date`.
- **Edycja / usunięcie operacji:** przebudowa salda i pozycji z całej historii w kolejności `(operation_date, created_at, id)`. Wiersze pozycji walorów, które nadal są w portfelu, są aktualizowane w miejscu (zachowują `id` i `opened_at`); zamknięte — usuwane; nowe — tworzone. Historia, która łamie regułę (np. usunięcie wpłaty, z której opłacono kupno) → 400 z `code`, nic się nie zmienia.
- **Walor operacji:** `asset_id` (musi istnieć), albo `ticker` — istniejący walor (ticker normalizowany jak w `assets`), a gdy go nie ma i podano `asset_class`, nowy walor w tej klasie i w walucie bazowej portfela (rdzeń bez commitu `AssetService.get_or_create_by_ticker`, [ADR-0008](../adr/0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md)). Odrzucona operacja nie zostawia nowego waloru ani klasy.
- **Atomowość:** każdy zapis to jedna `transaction()` serwisu ([ADR-0001](../adr/0001-jedna-sesja-na-request.md)).

### Kody błędów

| Status | `code` | Kiedy |
|---|---|---|
| 404 | `PORTFOLIO_NOT_FOUND` | portfel nie istnieje lub nie należy do użytkownika (także `portfolio_id` w treści operacji i `portfolio_name` pozycji) |
| 404 | `OPERATION_NOT_FOUND` | operacja nie istnieje lub nie należy do użytkownika |
| 409 | `PORTFOLIO_ALREADY_EXISTS` | nazwa zajęta u tego właściciela (tworzenie i zmiana nazwy) |
| 409 | `ASSET_ARCHIVED` | nowa operacja na zarchiwizowanym walorze (po `asset_id` albo `ticker`); odwołaj archiwizację w `assets`, by go użyć |
| 409 | `CONCURRENT_CHANGE` | wyścig na unikalnym kluczu przy rejestracji operacji (ten sam nowy ticker/klasa/waluta jednocześnie); ponowienie żądania się powiedzie |
| 400 | `CURRENCY_NOT_FOUND` | nieznana `base_currency_id` |
| 400 | `ASSET_NOT_FOUND` | nieznany `asset_id`; nieznany `ticker` bez `asset_class` |
| 400 | `INVALID_OPERATION` | znak/relacja pola (komunikat nazywa pole), nieznany typ w zapisanej historii |
| 400 | `OPERATION_REQUIRES_ASSET` / `OPERATION_FORBIDS_ASSET` | kupno/sprzedaż/dywidenda bez waloru; wpłata/wypłata z walorem |
| 400 | `INSUFFICIENT_CASH` / `INSUFFICIENT_QUANTITY` | brak środków; sprzedaż ponad posiadaną ilość |
| 400 | `POSITION_NOT_FOUND` | sprzedaż lub dywidenda bez otwartej pozycji |
| 400 | `INVALID_VECTORS`, `INVALID_DATE`, `INVALID_DATE_RANGE`, `UNSUPPORTED_INTERVAL` | parametry wektorów (§6) |
| 422 | — | kształt żądania (np. nieznany `operation_type`, nadmiarowe pole, liczba poza pojemnością kolumny) |

## 4. Warstwa `domain/`

Reguły z §3 i wycena to czysta arytmetyka na `Decimal` — `portfolios/domain/` według [ADR-0005](../adr/0005-warstwa-domeny.md): tylko biblioteka standardowa, bez zegara i I/O, wartości niemutowalne (`@dataclass(frozen=True, slots=True)`), bez zaokrągleń. Warstwy DOM-9:

| Poziom | Plik | Zawartość |
|---|---|---|
| 0 — słownik | `enums.py` | `OperationType` (`StrEnum`: buy, sell, deposit, withdrawal, dividend, interest, fee), `ImportStatus`, `ImportRowStatus`; `ASSET_OPERATIONS`, `CASH_OPERATIONS`, `INCOME_COST_OPERATIONS`, `TRADE_OPERATIONS` |
| 0 — słownik | `errors.py` | `PortfolioDomainError(ValueError)` z klasowym `code`; podklasy `InvalidOperationError` (z `field`), `AssetRequiredError`, `AssetNotAllowedError`, `InsufficientCashError`, `InsufficientQuantityError`, `PositionNotFoundError` |
| 1 — granica ORM | `protocols.py` | `Protocol`y (DOM-8): `OperationLike`, `PositionLike`, `PortfolioBalanceLike`, `HoldingLike`, `QuotedAssetLike`, `ValuedPortfolioLike` — wiersze ORM spełniają je strukturalnie |
| 2 — komponent | `ledger.py` | `PortfolioLedger`: `validate(op)`, `apply(state, op) -> LedgerState`, `rebuild(ops) -> LedgerState`; wartości `OperationInput`, `PositionState`, `LedgerState` (`LedgerState.of(portfolio, positions)`, `OperationInput.from_operation(row)`) |
| 2 — komponent | `valuation.py` | `PortfolioValuator.value(portfolio, holdings, fx_rates: FxMap) -> PortfolioValuation` (z `PositionValuation` per pozycja) |

Publiczne API wyłącznie przez `domain/__init__.py` (`__all__`, DOM-11). Komponenty buduje `wiring.py` (`build_portfolio_ledger`, `build_portfolio_valuator`) i wstrzykuje przez konstruktor (DOM-10). Serwis tłumaczy każdy `PortfolioDomainError` w jednym miejscu (`_ledger_errors_rejected` w `services/operations.py`) na `OperationRejectedError` (400) z `code` domeny. Czystość, warstwy i import tylko przez `__init__` sprawdza `tests/unit/test_domain_purity.py`.

**Wariant (a) ADR-0005 jest zastosowany w kodzie:** `numpy` nie wchodzi do `domain/`, wektory metryk są w `services/metrics.py` (§6). ADR ma nadal status `Proposed` — wariant musi zaakceptować właściciel.

## 5. Wycena (modele odczytowe)

`PortfolioValuator` liczy dokładnie (na `Decimal`): koszt nabycia `ilość × średnia cena` (waluta waloru) i `× średni kurs` (waluta portfela); wartość rynkowa `ilość × cena bieżąca`, a gdy waluta waloru ≠ waluta bazowa portfela — `× kurs krzyżowy` z mapy `FxMap` (`(id waluty waloru, id waluty bazowej) -> rate[waloru]/rate[bazowej]`, kursy `assets` są „USD za jednostkę”; buduje ją `services/fx.py::FxMapBuilder`, domena dostaje gotową mapę); niezrealizowany wynik, zwrot % pozycji; dla portfela: wartość pozycji, wartość całkowita (z gotówką), wynik względem `total_deposited`, suma `total_fees` pozycji (zwrot portfela to TWR z [§6.1](#61-zwrot-portfela-twr-i-snapshoty-dzienne), nie ze stosunku do wpłat); udział pozycji względem wartości całkowitej. Dzielenie przez zero daje 0. **Brak kursu** (waluta bez notowania; `exchange_rate` równy 1 na walucie innej niż USD to wartość domyślna kolumny, nie kurs) → pola wyceny pozycji `null` + `rate_missing=true`; sumy portfela (`positions_value`, `total_value`, `total_profit_loss`) są `null`, gdy brakuje kursu którejkolwiek pozycji (bez sum częściowych); koszty i `total_fees` nie wymagają kursu. Zaokrąglenie dopiero w schemacie odpowiedzi (typy `RoundedValue`/`RoundedPercent`/`RoundedFees` w `schemas/positions.py`): wartości 3 miejsca, procenty 4, opłaty 2, `ROUND_HALF_EVEN` (jak `round` Pythona).

**Widok w walucie waloru** (bez kursu, też przy `rate_missing`): `market_value_asset_currency` = ilość × cena, `unrealized_pnl_asset_currency` = ilość × (cena − średnia cena), `price_change_pct` = zmiana ceny waloru względem średniej (`null` przy cenie lub średniej `0`). Cena `0` oznacza brak notowania, więc pola w walucie waloru są wtedy `null`. **Rozbicie zysku w PLN**: `price_effect` = ilość × (cena − średnia) × kurs; `fx_effect` = ilość × średnia cena × (kurs − średni kurs zakupu); suma = `unrealized_pnl`. W walucie bazowej `fx_effect` = 0. `fx_rate_applied` (kurs zastosowany, 6 miejsc, `RoundedPositionRate`) jest `null` przy braku kursu. Źródło: `domain/valuation.py`; pola są dodatkowe w `PositionResponse`, istniejące bez zmian.

Serwisy odczytowe zwracają DTO (`PortfolioSummaryResponse`, `PortfolioDetailResponse`, `PositionResponse` — [ADR-0003](../adr/0003-serwisy-zwracaja-encje-orm.md)); repozytoria ładują pozycje → walor → waluta/klasa zapytaniami `selectinload`/`joinedload` (bez N+1) z `populate_existing`, więc odczyt w tej samej sesji po zapisie widzi świeży stan.

## 6. Metryki (wektory)

`MetricsService.portfolio_vectors(owner_id, query)` w `services/metrics.py` (wariant (a) ADR-0005: `numpy` w serwisie). Historia cen przez port `PriceHistoryProvider` (`close_history(ticker, start, end)` z `end` wyłącznym, `current_price(ticker)`), zdefiniowany w tym pliku; `assets.MarketDataService` spełnia go strukturalnie (składa `wiring.py`). Historia każdego tickera jest pobierana raz na żądanie. Kwoty sumowane jako `Decimal`, na `float` zamieniane przy wpisie do wektora (ADR-0010).

- Parametry (nazwy z frontendu): `portfolioName` (brak = wszystkie portfele użytkownika), `startDate`/`endDate` (`YYYY-MM-DD`), `interval` (tylko `1d`), `vectors` (lista JSON nazw; pusta = wszystkie). Bez operacji → `{}` (przed walidacją parametrów). Kolejność kontroli: `vectors` → daty → zakres → interwał.
- Wektory: `date` (każdy dzień od `start` do `end` włącznie, `YYYY-MM-DDT00:00:00`), `assets` (`{ticker: wartości}`), `asset_classes` (`{klasa: wartości}`), `net_deposits_vector`, `transaction_cost_vector`, `profit_vector` (wartość walorów − koszt transakcji), `free_cash_vector` (wpłaty netto − koszt transakcji), `portfolio_value_vector` i jego alias `pocket_value_vector` (wolna gotówka + wartość walorów). Nieznane nazwy są pomijane.
- Operacja trafia na dzień `max(0, ⌊(operation_date UTC − start) / 1 dzień⌋)` i ustawia sumę narastającą od tego dnia; operacje po `end` nie są widoczne. Koszt transakcji: kupno `+ilość·cena+opłata`, sprzedaż `−(ilość·cena−opłata)`, pozostałe `+opłata`.
- Cena dzienna: zamknięcia z portu rozłożone na pełny kalendarz; ostatni dzień — cena bieżąca, gdy `end` to dzień roboczy; luki wypełniane w przód, potem początkowe wstecz. Ticker bez żadnej ceny psuje swój wektor.
- Wektor, którego nie da się policzyć (np. awaria dostawcy), jest logowany i zwracany jako zera; pozostałe są liczone.

Odpowiedź `PortfolioVectorsResponse` to `RootModel[dict[str, list[datetime] | list[float] | dict[str, list[float]]]]` — ten sam JSON co przed migracją (`PocketVectorsResponse` we frontendzie).

### 6.1. Zwrot portfela (TWR) i snapshoty dzienne

`total_return_pct` portfela to **skumulowany zwrot ważony czasem** od pierwszej operacji ([ADR-0004](../../business/adr/0004-metodologia-stop-zwrotu.md), konwencja Portfolio Performance), `return_method` = `daily_pp_v1`. Dla dnia: `1 + r = (wartość końcowa + wypłata) / (wartość początkowa + wpłata)`; wpłata liczy się od początku dnia, wypłata od końca, przepływy jednego dnia są netowane, mianownik 0 daje `r = 0` (restart); dywidendy, odsetki i opłaty są wartością, nie przepływem. `twr_index` to iloczyn `(1 + r)`, wynik = `(twr_index − 1) × 100`. Rachunek jest w `domain/snapshots.py` (`DailySnapshotBuilder`, `Decimal`, odtwarza stan przez `PortfolioLedger`); zamknięcia i ilości z księgi są w jednostkach danego dnia (adapter cofa korektę splitów Yahoo, zarejestrowany `split` mnoży ilość), więc wycena nie zależy od tego, czy split trafił do historii portfela, gdy waloru w dniu splitu nie było.

Dane dzienne trzyma `portfolios_daily` — pochodna Operacji i cen, nie źródło prawdy ([ADR-0016](../adr/0016-snapshoty-dzienne-i-przebudowa.md)). `SnapshotService` (`services/snapshots.py`) utrzymuje je **leniwie przy odczycie** (`get_detail`, `list_summaries`):

- zapis operacji (`OperationService._rebuild`) tylko ustawia `portfolios_portfolio.dirty_from = min(dirty_from, data operacji)` w tej samej transakcji (dodanie, edycja — mniejsza z dat starej i nowej, usunięcie, import, cofnięcie importu);
- odczyt, gdy `dirty_from` jest ustawione albo brakuje dni do wczoraj: dociąga zamknięcia dostawcy dla budowanych dni (`MarketDataService.backfill_closes` → `assets_price`, bez korekty o dywidendy, [ADR-0015](../adr/0015-historia-cen-i-kursow.md)), potem w transakcji z blokadą wiersza portfela kasuje wiersze od pierwszego nieaktualnego dnia i dopisuje nowe do wczoraj; **dzisiaj nie jest zapisywany** — dolicza go bieżąca wycena i dzisiejsze przepływy;
- kolejny odczyt nie pyta dostawcy o zapisane dni.

Walor, którego dostawca w ogóle nie zna (ticker z importu bez notowań w Yahoo), jest wyceniany po **cenie ostatniej transakcji** (w jednostkach danego dnia, splity ją dzielą) — to przybliżenie, więc `return_method` = `daily_pp_v1+last_trade`. Gdy taki walor jest nadal w portfelu, zwrotu nie podajemy (dzisiejsza wartość nie zgadzałaby się z wyceną po ostatniej transakcji).

Gdy zwrotu nie da się podać, pole jest `null` (UI: „—”), a nic się nie zapisuje: brak operacji lub bieżącej wyceny, walor w innej walucie niż bazowa portfela (brak historycznych kursów FX), luka w zamknięciach waloru, który ma notowania, awaria dostawcy. Poza zakresem (ADR-0016): `portfolios_position_daily`, przebudowa asynchroniczna i `stale`, unieważnianie po korekcie cen wstecz (`assets_price_change`), XIRR.

## 7. Serwisy (API publiczne)

| Serwis | Metody |
|---|---|
| `PortfolioService(portfolio_repo, currency_service, valuator, fx_map_builder, snapshot_service)` | `list_summaries(owner_id, name=None)`, `get_detail(portfolio_id, owner_id)`, `get_owned(portfolio_id, owner_id)`, `get_owned_by_name(owner_id, name)`, `create(data, owner_id)`, `update(portfolio_id, data, owner_id)`, `delete(portfolio_id, owner_id)` |
| `PositionService(portfolio_service, position_repo, market_data, valuator, fx_map_builder)` | `list_valued(owner_id, portfolio_name)` |
| `OperationService(portfolio_repo, position_repo, operation_repo, asset_service, ledger)` | `list_operations(owner_id, portfolio_name=None)`, `record(data, owner_id)`, `update(operation_id, data, owner_id)`, `delete(operation_id, owner_id)` — orkiestrator operacji wielomodułowej; dla importu rdzenie bez commitu `record_many_core`, `revert_import_batch_core` oraz `preview_state`, `existing_external_refs` |
| `ImportService(import_repo, operation_service, asset_service, portfolio_service, parsers)` | `list_batches`, `get_detail`, `upload`, `confirm`, `revert` — [`07_import.md`](./07_import.md) |
| `MetricsService(operation_repo, prices)` | `portfolio_vectors(owner_id, query)` |
| `SnapshotService(portfolio_repo, daily_repo, operation_repo, price_service, market_data, builder)` | `twr(portfolio, current_value)` — zwrot TWR i leniwa przebudowa `portfolios_daily` ([§6.1](#61-zwrot-portfela-twr-i-snapshoty-dzienne)) |

Zależności zewnętrzne: `assets` (`CurrencyService`, `AssetService`, `MarketDataService`) wyłącznie przez serwisy składane `assets_wiring.build_*` ([ADR-0006](../adr/0006-cross-module-wylacznie-przez-serwisy.md)); `core_data` tylko przez `get_current_user`.

## 8. Układ

```text
portfolios/
├─ api/{portfolios,positions,operations,metrics,fx_rates}.py   # __init__.py: wspólny `router` dla main.py
├─ services/{portfolios,positions,operations,metrics,fx,snapshots}.py
├─ domain/{enums,errors,protocols,ledger,valuation,snapshots}.py # + __init__.py z __all__
├─ repositories/{portfolios,positions,operations,daily}.py
├─ schemas/{portfolios,positions,operations,metrics,fx_rates}.py
├─ models/{portfolio,position,operation,portfolio_daily}.py
├─ exceptions.py  dependencies.py  wiring.py
└─ tests/unit/        # domena (w tym parytet z Django), serwisy, API, wiring, czystość domain/
   tests/integration/ # pełny przepływ HTTP + baza, repozytoria na PostgreSQL
```

Testy parytetu (`tests/unit/test_ledger_parity.py`) odtwarzają scenariusze testów widoków z dawnego Django (`test_views.py`, usuniętego) (losowe kupna i sprzedaże ze stałym ziarnem, wpłaty, wypłaty, błędne dane, usuwanie wpłat/wypłat) na księdze. Świadome różnice wobec Django: `total_fees` portfela to suma opłat pozycji (Django: wszystkich operacji); usuwanie kupna/sprzedaży działa (w Django niezaimplementowane).

## 9. Zmiany kontraktu HTTP przy R-07/R-08

| Było | Jest |
|---|---|
| duplikat nazwy przy tworzeniu portfela → 400 | 409 `PORTFOLIO_ALREADY_EXISTS` (jak przy zmianie nazwy) |
| `POST/PUT/PATCH /portfolios/…` zwracały też pola wyliczone ustawione na 0 | `PortfolioResponse` bez pól wyliczonych (wartości: `GET`) |
| `PortfolioCreate` bez ograniczeń i bez `extra="forbid"` | `name` 1–100, `base_currency_id > 0`, nadmiarowe pola → 422 |
| nieznany `operation_type` → 400 | 422 (schemat, `OperationType`) |
| znaki pól przy edycji operacji (`ge=0`, `gt=0`) → 422 | 400 `INVALID_OPERATION` (domena) |
| `ticker: ""` ignorowany, `asset_class` > 20 znaków → 500 | 422 |
| nieznany `asset_id` przy wpłacie/wypłacie ignorowany | 400 `ASSET_NOT_FOUND` |
| `/portfolios/operations/{id}` z nie-liczbą → 422 | 404 (konwerter `:int`) |
| wektory: `start > end` lub `interval ≠ 1d` → 500 | 400 `INVALID_DATE_RANGE` / `UNSUPPORTED_INTERVAL`; `vectors` nie-lista → 400 `INVALID_VECTORS` (było 500 lub cicho ignorowane) |
| wektory: brak `currentPrice` u dostawcy wpisywał 0 w ostatni dzień | cena bieżąca portu (`currentPrice` → `regularMarketPrice` → `previousClose`), a gdy brak — ostatnie zamknięcie |
| wektory: sumy narastające na `float` | sumy na `Decimal`, `float` dopiero w wektorze (różnice tylko w szumie ostatnich cyfr) |
| pola wyliczone na `float`, `positions_value` = suma już zaokrąglonych wartości pozycji, udziały z wartości zaokrąglonych | `Decimal`, zaokrąglenie raz na granicy schematu (dla wielu pozycji różnica ≤ 0,001 w trzecim miejscu) |
| błędy 400 bez `code` | `{"detail", "code"}` ([ADR-0007](../adr/0007-kontrakt-bledow-z-code.md)) |

## 10. Stan vs cel

| Element | Stan | Cel | Krok |
|---|---|---|---|
| Struktura, wiring, błędy z `code`, `transaction()`, `find_`/`get_`, testy `unit/` + `integration/` | zgodne z celem | — | R-07 (domknięty) |
| `domain/` (księga, wycena), typowane argumenty, `Decimal` do granicy schematu, port cen, testy parytetu | zgodne z celem; wariant (a) ADR-0005 czeka na akceptację | — | R-08 (domknięty) |
| Rejestracja operacji z datą wcześniejszą niż istniejące | stosowana do bieżącego stanu; późniejsza przebudowa (edycja/usunięcie) układa historię wg dat i może ją odrzucić | decyzja właściciela: walidować `POST` przebudową całej historii albo zostawić | — (otwarte) |
| Kurs waluty = heurystyka (`exchange_rate` ≠ 1 lub USD), kursy bez historii; kurs jest zawsze „USD za jednostkę” — `FxMapBuilder` ignoruje `Currency.base_currency_id`, więc ręczny kurs względem innej bazy zepsuje wycenę do następnego odświeżenia; `CURRENCY_NOT_FOUND` ma tu dwa statusy (400 w ciele operacji, 404 w `GET /portfolios/fx-rate`) | tabela kursów z historią i źródłem ([ADR-0015](../adr/0015-historia-cen-i-kursow.md)) | E1.1 |
| Odświeżanie kursów/cen | synchronicznie w `POST /portfolios/positions/refresh` | entrypoint + harmonogram ([`04_assets_module.md`](./04_assets_module.md)) | — (poza planem) |
| `mypy` | nieuruchamiany | `mypy app` zielone | R-10 |
