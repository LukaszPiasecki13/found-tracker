---
id: plan-slice-e0-1-fx-valuation
status: draft
type: mixed
scope: plans/first-slice
last_reviewed: 2026-10-02
---

# Jak naprawić wycenę walut obcych jako pierwszy wycinek implementacji?

> **Plan wykonawczy (L3, draft).** Nie opisuje stanu systemu. Wycinek adaptuje istniejące moduły `assets` i `portfolios` — krok E0.1 [roadmapy](./02_roadmapa_funkcjonalna.md) ([etapy E0–E5](./03_roadmapa_etapy_E0-E5.md)).

Wycinek: wycena pozycji w walucie obcej kursem krzyżowym (waluta waloru → waluta bazowa Portfela), z jawnym `rate_missing` zamiast cichego kursu 1. Rozmiar **M** (4–5 dni), 7 kroków TDD, zero migracji. Dowód defektu: F1 w [stanie vs cel](../research/06_stan_found-tracker_vs_cel.md).

## Dlaczego ten wycinek

| Powód | Dowód |
|---|---|
| Realny defekt wartości, nie refaktor | F1: `valuation.py:55-57` mnoży przez `exchange_rate` („USD za 1 jednostkę”, `assets/services/market_data.py:109`), więc Portfel nie-USD pokazuje liczby w USD; zob. pkt 2 |
| Zero migracji schematu | `Currency.exchange_rate` `Numeric(18,9)` istnieje (`assets/models/currencies.py:20-22`); wycena jest read-modelem, nic nie zapisuje; pkt 6 |
| Niezależny od D1–D16 i ADR-ów | E0 to „naprawy… bez nowych ADR-ów” ([etapy](./03_roadmapa_etapy_E0-E5.md)); używa tylko istniejących kolumn-cache (ADR-0015 pkt 4 zostawia je jako źródło do E1.1) |
| Zmiana mała i warstwowa | domena (`valuation.py`, `protocols.py`), 1 nowy serwis, 2 serwisy (konstruktor), 2 schematy, ~5 plików frontendu; metryki i księga bez zmian |
| Daje „złoty” wynik | Portfel PLN, EUR/USD/PLN: 9 620 PLN (pkt 2) — liczba do testu domeny, serwisu i ręcznej weryfikacji |
| Odblokowuje dalsze kroki | `FxMapBuilder` jest wymagany przez E0.1b (dialogi), E0.2, E0.9 (kokpit w walucie wyświetlania), E2.2, E3.4 |

## Alternatywy (inne małe wycinki)

| Wycinek | Zakres | Dlaczego odłożony |
|---|---|---|
| **B. Ustawienia użytkownika** (E0.9) | nowy zasób w `core_data`: tabela `core_data_user_settings`, `GET/PUT`, test API | wymaga migracji autogenerate i rozstrzygnięć (usunięcie `timezone`, `condition_thresholds`, domyślna waluta); nic nie naprawia; sumy „w walucie wyświetlania” (F3) i tak potrzebują kursu krzyżowego z E0.1 — B zależy od A |
| **C. Zamknięcie rejestracji** (E0.6) | `ALLOW_REGISTRATION`, kolumna `is_owner` (migracja addytywna), pierwszy `cli.py` z `set-owner`, 403 na zapisach `assets` | zmienia zachowanie auth (testy używają `/auth/register`, `conftest.py:46`), dotyka D14 i biznesowego ADR 0007 (decyzja właściciela), wprowadza pierwszy driver CLI pod `test_architecture.py:295`; to utwardzanie, nie poprawność danych |

## 1. Cel i zakres

| IN | OUT (z powodem) |
|---|---|
| `PortfolioValuator.value()` przyjmuje mapę kursów `{(currency_id_z, currency_id_do): Decimal}` | endpoint `GET /portfolios/fx-rate` i podpowiedź kursu w dialogach (F4) — **E0.1b**, ten sam `FxMapBuilder` |
| `FxMapBuilder` w `portfolios/services/` (kurs krzyżowy = rate[z]/rate[do]) | historia kursów i kurs „na dzień” — E1.1 ([ADR-0015](../technical/adr/0015-historia-cen-i-kursow.md)) |
| `rate_missing` i wartości nullable w `PositionResponse`, `PortfolioSummaryResponse` | wektory metryk (`services/metrics.py` nie czyta kursów) — E0.2 |
| minimalny frontend: typy, „—” i znacznik „Brak kursu” | zmiana waluty bazowej Portfela — E0.8; salda wielowalutowe (`valuation.py:82` sumuje jedną gotówkę) — E2.2 |
| golden fixture w testach, aktualizacja L2 | `fx_rate` Operacji (default 1, `schemas/operations.py:52`) — E2.2; zmiana `seed_data.py` — E0.5 |

## 2. Stan dziś — defekt liczbami

Kursy (`seed_data.py:67-74`; po `refresh_currency_rates`, `market_data.py:109-129`, to samo znaczenie): USD = 1, EUR = 1,08, PLN = 0,25 (USD za jednostkę). Kod (`valuation.py:55-57`):

```
55  market_value = holding.quantity * holding.asset.current_price
56  if holding.asset.currency_id != base_currency_id:
57      market_value = market_value * holding.asset.currency.exchange_rate
```

Kurs nie zależy od waluty bazowej Portfela; dla Portfela PLN wynik jest w USD. Wartości są **obliczone ręcznie** (nic nie uruchamiałem — brak `.venv` w tym środowisku).

Fixture złoty „Z1”: Portfel PLN, `cash_balance` 1 000, `total_deposited` 10 000. Pozycje: A — EUR, 10 szt., śr. cena 90, cena 100, `average_fx_rate` 4,00; B — USD, 10 szt., 80, 100, `average_fx_rate` 4,00; C — PLN, 5 szt., 50, 60, kurs 1.

| Pole | Dziś | Po wycinku | Wzór |
|---|---|---|---|
| A `market_value` | 1 080 | **4 320** | 10·100·(1,08/0,25) |
| B `market_value` | 1 000 | **4 000** | 10·100·(1/0,25) |
| C `market_value` | 300 | 300 | waluta Portfela, kurs 1 |
| A `unrealized_pnl` / `return_pct` | −2 520 / −70 % | 720 / 20 % | koszt 3 600 (`valuation.py:54`) |
| B `unrealized_pnl` / `return_pct` | −2 200 / −68,75 % | 800 / 25 % | koszt 3 200 |
| `positions_value` | 2 380 | **8 620** | |
| `total_value` | 3 380 | **9 620** | + gotówka 1 000 |
| `total_profit_loss` / `total_return_pct` | −6 620 / −66,2 % | −380 / −3,8 % | względem 10 000 |
| `portfolio_weight_pct` A / B / C | 31,9527 / 29,5858 / 8,8757 | 44,9064 / 41,5800 / 3,1185 | `valuation.py:91`, 4 miejsca |

Koszt (`cost_basis_in_portfolio_currency`) był poprawny — liczy się z `average_fx_rate` Operacji (`valuation.py:54`); mylił się tylko licznik wyniku. Pola dotknięte: `PositionResponse` — `market_value`, `unrealized_pnl`, `return_pct`, `portfolio_weight_pct` (`schemas/positions.py:69-72`); `PortfolioSummaryResponse` — `positions_value`, `total_value`, `total_profit_loss`, `total_return_pct` (`schemas/portfolios.py:63-66`). `total_fees` bez zmian (nie zależy od kursu).

## 3. Projekt docelowy (minimalny)

**Skąd waluta bazowa.** Kod już ją zna: `Portfolio.base_currency_id` (`models/portfolio.py:34-36`) → `ValuedPortfolioLike.base_currency_id` (`protocols.py:91-92`) → `valuation.py:80`. Repozytorium ładuje ją i walory z walutami bez N+1 (`repositories/portfolios.py:16-30`). Zmiana nie dotyka repozytoriów.

**Domena** (`valuation.py`, stdlib-only, ADR-0005; bez portu i I/O):

| Element | Dziś | Docelowo |
|---|---|---|
| Typ mapy | brak | `FxMap = Mapping[tuple[int, int], Decimal]` w `valuation.py`, eksport w `domain/__init__.py` (DOM-11; `Mapping` z `collections.abc` jest na liście `test_domain_purity.py:17-26`) |
| Sygnatura | `value(portfolio, holdings)` (`:77-79`) | `value(portfolio, holdings, fx_rates: FxMap)` |
| Kurs pozycji | `exchange_rate` waluty (`:56-57`) | waluta waloru = bazowa → 1 (mapa ignorowana); inaczej `fx_rates.get((asset.currency_id, base_currency_id))` |
| `PositionValuation` (`:26-36`) | wszystkie pola `Decimal` | `market_value`, `unrealized_pnl`, `return_pct`, `portfolio_weight_pct`: `Decimal \| None`; nowe `rate_missing: bool`; koszty zawsze policzone |
| `PortfolioValuation` (`:39-49`) | wszystkie `Decimal` | `positions_value`, `total_value`, `total_profit_loss`, `total_return_pct`: `Decimal \| None`; nowe `rate_missing: bool`; `total_fees` zawsze |
| `QuotedAssetLike` (`protocols.py:62-70`) | ma `currency` | bez `currency`; usunąć `CurrencyRateLike` (`:57-59`, brak innych użyć — sprawdzone `grep`); `HoldingLike` (`:73-85`) zmienia się pośrednio |

**Reguła `rate_missing`** **[propozycja]**:

| Sytuacja | Wynik |
|---|---|
| waluta waloru = waluta Portfela | kurs 1, nigdy `rate_missing` |
| para w mapie | wycena kursem z mapy |
| pary brak w mapie | pozycja: wartości `null`, `rate_missing=true`; koszty policzone |
| ≥ 1 pozycja z `rate_missing` | Portfel: `positions_value`, `total_value`, `total_profit_loss`, `total_return_pct` = `null`, `rate_missing=true`; **udziały wszystkich pozycji `null`** (mianownik nieznany); wartości pozostałych pozycji zostają |
| odpowiedź HTTP | zawsze 200; `RATE_MISSING` inline (kontrakt 09 wiersz `RATE_MISSING`: „w wycenie jako `issues[]`”) — tu uproszczone do flagi, `issues[]` w E1.7 |

Sumy częściowe odrzucone: po cichu zaniżałyby wartość (to ten sam rodzaj błędu co F1).

**`FxMapBuilder`** (nowy, `portfolios/services/fx.py`): `FxMapBuilder(currency_service)` z `build(base_currency_ids: Iterable[int]) -> FxMap`; jedno `CurrencyService.list_currencies()` (`assets/services/currencies.py:28-29`) na wywołanie. Waluta jest „z kursem”, gdy `code == DEFAULT_CURRENCY_CODE` (USD, `assets/constants.py:4`; kurs efektywny 1) albo `exchange_rate > 0` ∧ `exchange_rate != 1` (heurystyka sprzed E1.1; nowa waluta ma domyślnie 1 — `currencies.py:84-94`). Do mapy trafia para `(z, do)`, `z ≠ do`, `do` ∈ `base_currency_ids`, gdy obie waluty są „z kursem”: `rate[z] / rate[do]`, bez `quantize` (ADR-0010; zaokrągla schemat). Brak pary identycznościowej. Nazwa `FxMapBuilder` wg roadmapy i ADR-0015; klasa czyta I/O, więc nie jest komponentem domeny (DOM-10) — mieszka w `services/` obok `*Service`.

**Serwisy i wiring.** `PortfolioService(…, valuator, fx_builder)` (`services/portfolios.py:67-75`): `list_summaries` buduje mapę raz dla zbioru walut bazowych Portfeli (`:93`), `get_detail` dla jednej (`:104`). `PositionService(…, valuator, fx_builder)` (`services/positions.py:16-26`): mapa **po** `refresh_currency_rates()` i `refresh_asset_prices()` (`:37-39`), przed `value()` (`:41`) — odświeżenie zatwierdza własną transakcję, więc kursy są świeże. `wiring.py`: `build_fx_map_builder(session)` (`assets_wiring.build_currency_service`, jak `:34`), przekazany w `build_portfolio_service` (`:31-36`) i `build_position_service` (`:39-45`). `position_response` (`services/portfolios.py:30-43`) i `_summary_fields` (`:46-56`) kopiują `rate_missing` i wartości nullable.

**Reguły z `core/tests/test_architecture.py`, których dotyczy zmiana:**

| Test (linia) | Dlaczego |
|---|---|
| `:216` R1 | `fx.py` nie otwiera sesji ani nie importuje `fastapi` |
| `:244` R4 | `fx.py`, `wiring.py` nie importują `dependencies.py` |
| `:522` ADR-0006 | `fx.py` sięga do `assets` tylko przez `CurrencyService`; import stałej `DEFAULT_CURRENCY_CODE` nie jest flagowany (regex `:475-500` zakazuje `repositories`, `api`, podmodułów `domain`, `models`) — **[propozycja]** zob. Otwarte punkty |
| `:549` | `wiring.py` bez `fastapi` |
| `:576` | `FxMapBuilder` nie commituje (odczyt); granica commitu bez zmian (ADR-0001) |
| `test_domain_purity.py:150,196,242,266` | mapa to `collections.abc`; brak nowego pliku w `domain/` (`DOMAIN_LAYERS` bez zmian); `FxMap` importowany z `domain/__init__.py`; `api/` nie importuje domeny |

## 4. Kolejność prac (małe kroki TDD)

Każdy krok: test najpierw (czerwony lokalnie), potem kod, osobny commit i review (≤ ~150 linii diff). Commit tylko za zgodą właściciela (`CLAUDE.md`, sekcja Git).

| # | Cel | Pliki | Test najpierw | Zielone gdy |
|---|---|---|---|---|
| K1 | `FxMapBuilder` + alias `FxMap` | nowe: `services/fx.py`, `tests/unit/test_fx_map_builder.py`; `domain/valuation.py` (+alias), `domain/__init__.py:42-67`, `services/__init__.py`, `wiring.py` (+`build_fx_map_builder`), `test_wiring.py:44` | `test_builds_cross_rates_for_pln_base`: USD 1, EUR 1,08, PLN 0,25 → `{(USD,PLN): 4, (EUR,PLN): 4.32}` | testy buildera i wiringu zielone; `pytest -m "not integration"` bez regresji (~110 linii) |
| K2 | Schematy odpowiedzi: nullable + `rate_missing` (przed domeną, żeby `mypy app` strict nie świecił na czerwono po zmianie typów w K3) | `schemas/positions.py:69-72` (`RoundedValue \| None`, `rate_missing: bool = False`), `schemas/portfolios.py:63-66`; `services/portfolios.py:30-56`; `test_portfolios_api.py:195-214` | `test_summary_exposes_rate_missing_and_nullable_totals` (JSON `null`) | `model_dump(mode="json")` daje `null`/`false`; zaokrąglenie 3/4 miejsc bez zmian; `mypy app` zielone (~60) |
| K3 | Domena: mapa kursów, wartości nullable, `rate_missing` — **z tymczasowym zapasem** | `domain/valuation.py:26-94`; `tests/unit/test_valuation.py` (pkt 5; w tym kroku testy przechodzą na `fx_rates=`, a `currency=` w `_holding` zostaje — usunięcie dopiero w K4) | `test_eur_position_in_pln_portfolio_uses_the_cross_rate`: 10·100 EUR, `{(EUR,PLN): 4.32}` → 4 320 | `fx_rates=None` przechodzi starą ścieżką (`exchange_rate`), więc serwisy działają bez zmian; nowe testy zielone; `mypy app` zielone (~150) |
| K4 | Serwisy używają buildera; usunięcie zapasu | `services/portfolios.py:67-75,93,104`; `services/positions.py:16-41`; `wiring.py:31-45`; `protocols.py:57-70`; `valuation.py` (bez `exchange_rate`); testy z pkt 5 | `test_list_valued_builds_the_fx_map_after_the_refreshes` (kolejność `rates → positions → prices → fx → value`) | `grep -rn exchange_rate backend/app/modules/portfolios/domain` puste; golden Z1 = 9 620 (~150) |
| K5 | Frontend: typy i „Brak kursu” | pkt 7 | build/lint (brak runnera testów do E0.7) | `npm run lint`, `npm run build`; scenariusz ręczny z pkt 9 (~80) |
| K6 | Integracyjny golden Z1 przez HTTP | `tests/integration/test_portfolio_flow.py` (+test); fixture: waluty o literalnych kodach (`get_or_create_by_code('USD')` z kursem 1, EUR 1,08, PLN 0,25 — fixture `currency_codes` w `conftest.py:65-80` wydaje losowe kody, a reguła „z kursem” zależy od kodu `USD`); wiersze wycofuje rollback testu | `test_foreign_positions_are_valued_at_cross_rates` (`@integration`, PostgreSQL) | `GET /portfolios/{id}`: `total_value` 9 620, `rate_missing` false (~90) |
| K7 | Dokumentacja L2 | `docs/technical/backend/05_portfolios_module.md` (zob. pkt 9) | `kb_validate --strict` | brak nowych błędów (~25) |

Dlaczego schematy przed domeną (K2 przed K3): Pydantic v2 typuje `__init__`, więc `PositionValuation` z polami `Decimal | None` przekazane do `PositionResponse.market_value` (`services/portfolios.py:35-43`) łamałoby `mypy app` do czasu K2. Dlaczego zapas w K3: gdyby `fx_rates` był wymagany od razu, K3 musiałby jednocześnie zmienić serwisy i testy (~250 linii) albo zostawić commit z cichym kursem 1. Zapas żyje jeden commit i znika w K4 (kryterium `grep`).

## 5. Testy

**Do przepisania** (zweryfikowane w kodzie):

| Plik:linia | Zmiana |
|---|---|
| `test_valuation.py:18-38` (`_holding`) | usunąć `currency=` i `exchange_rate`; wywołania `value(...)` (`:44,59,74,90,99,112`) dostają mapę |
| `test_valuation.py:41-51` | pozycja w walucie Portfela ignoruje mapę (zatruta para `(PLN,PLN): 999`) |
| `test_valuation.py:54-66` | `exchange_rate="4.1"` → `fx_rates={(USD,PLN): D("4.1")}`; liczby bez zmian (1 025, 245) |
| `test_valuation.py:68-84` | `exchange_rate="4"` (`:71`) → mapa `{(USD,PLN): D("4")}`; 720 i udziały bez zmian |
| `test_portfolio_service.py:92-94` | fixture dostaje stub buildera (`MagicMock`, `build.return_value`) |
| `test_portfolio_service.py:247-269` | para `(2,1): 3.9` w stubie zamiast `_currency(2, rate="3.9")` (`:250`); 493,900 / 593,900 bez zmian |
| `test_portfolio_service.py:272-308` | stub zwraca `{}` (same waluty Portfela) |
| `test_position_service.py:57-61` | fixture z builderem; `:64-90` rozszerzyć kolejność wywołań o `fx` |
| `test_wiring.py:44-47` (+`:18-33`) | asercje: `_fx` w obu serwisach jest `FxMapBuilder` |
| `test_portfolios_api.py:195-214` | dodać `"rate_missing": False` do oczekiwanego ciała |
| `integration/test_portfolio_flow.py:202-216` | bez zmian (jedna waluta) — kontrola parytetu |

**Nowe:**

| Plik | Test (przypadek) | Oczekiwanie |
|---|---|---|
| `test_valuation.py` | EUR w Portfelu PLN | 4 320 |
| | USD w Portfelu PLN | 4 000 |
| | PLN w Portfelu USD, `(PLN,USD): 0,25` | parytet ze starym wzorem: cena × 0,25 |
| | brak pary | wartości `None`, `rate_missing`, koszty policzone |
| | jedna pozycja bez kursu | sumy Portfela i wszystkie udziały `None`, `total_fees` policzone |
| | golden Z1 | 8 620; 9 620; −380; −3,8; udziały z pkt 2 |
| | zaokrąglenia | kurs 28 cyfr (PLN→EUR = 0,2314814814814814814814814815) × 300 PLN pozostaje dokładny w domenie; `PositionResponse` daje 69,444 |
| `test_fx_map_builder.py` | trzy waluty (pkt 2) | `(USD,PLN)=4`, `(EUR,PLN)=4,32`, `(PLN,EUR)=0,2314…` |
| | brak pary identycznościowej | brak `(PLN,PLN)` |
| | waluta `GBP` z kursem 1 | brak par z GBP po obu stronach |
| | USD z kursem 1 | uznany za „z kursem” |
| | kurs 0 | para pominięta (bez dzielenia przez zero) |
| | jedno zapytanie | `list_currencies` wołane raz |
| `test_portfolio_service.py` | `list_summaries` dwóch Portfeli (PLN, USD) | `build` raz, ze zbiorem `{id_PLN, id_USD}` |
| `test_position_service.py` | walor GBP bez kursu | `rate_missing=True`, `market_value=None` |
| `test_ledger_parity.py`, `test_ledger.py` | bez zmian | zielone; `git diff` na `domain/ledger.py` pusty |

## 6. Migracje

**Brak zmiany schematu.** Zweryfikowane w modelach: `Currency.exchange_rate` `Numeric(18,9)` (`assets/models/currencies.py:20-22`), `Portfolio.base_currency_id` (`portfolios/models/portfolio.py:34-36`), `Position.average_fx_rate` `Numeric(18,9)` (`models/position.py:42-44`). Nowe wartości (kurs krzyżowy, flaga) są liczone w locie i niezapisywane. Kryterium: `git diff --stat -- backend/alembic` pusty. Gdyby ktoś chciał kolumnę `rate_missing` lub cache kursu — odrzucone: ADR-0015 pkt 6 mówi „kurs krzyżowy nie jest zapisywany”.

## 7. Kontrakt API i frontend

| Element | Zmiana | Zgodność wsteczna |
|---|---|---|
| `PositionResponse` | 4 pola wartości `number \| null`; nowe `rate_missing: boolean` | pole nowe addytywne; `null` tylko gdy brak kursu — dawniej liczba w złej walucie |
| `PortfolioSummaryResponse`, `PortfolioDetailResponse` | 4 pola `number \| null`; `rate_missing` | j.w. |
| `GET /portfolios/positions` | bez zmian parametrów | — |
| Wartości liczbowe | Portfel nie-USD z walorami obcymi: inne liczby (poprawne) | zamierzona zmiana; Portfel USD i waluta = Portfela: identycznie |

Frontend (bez Vitest — E0.7; weryfikacja `npm run lint`, `npm run build`, ręcznie):

| Plik:linia | Zmiana |
|---|---|
| `types/api.ts:42-46, 64-67` | `number \| null` dla czterech pól + `rate_missing?: boolean` |
| `components/PositionsTable.tsx:94-102` | `!== undefined` → `!= null`; usunąć zapas z `exchange_rate` (`:101`, zła semantyka) → „—” |
| `components/PositionsTable.tsx:105-152` | komórki wartość/zysk/zwrot/udział: „—” + `Chip` „Brak kursu” przy `rate_missing` |
| `pages/PocketDetailsPage.tsx:68-72,119,129,143-147` | dziś liczy sumy lokalnie z `market_value`; użyć `pocket.total_value` i `positions_value`; sprawdzać `== null` PRZED `Number()` (`Number(null)` = 0, więc `Number(pocket.total_profit_loss) \|\| (totalValue - totalDeposited)` w `:71` ukryje `null` i pokaże „0,00%”) — usunąć ten fallback; przy `null` „—” i `Alert` „Brak kursu waluty” |
| `components/PocketsList.tsx:138-154` | `!== undefined` → `!= null`; przy `null` pokaż „—” i `Chip` „Brak kursu” (samo `!= null` ukryłoby blok zysku) |
| bez zmian | `PocketChartsPage.tsx:85-88` (`\|\| 0` obsługuje `null`), `positionService.ts`, `DashboardPage.tsx:14-16` (F3 → E0.9) |

## 7a. Stan realizacji (branch `feat/e0-1-wycena-walut-obcych`)

K1–K7 oraz E0.1b wykonane. Odstępstwa od planu: (1) K2 poszedł po K3/K4 — schematy nullable zmieniono razem z domeną, bo `mypy app` strict wymaga spójnych typów w jednym kroku; (2) zapas „kurs z `exchange_rate` waluty waloru” w domenie nie powstał — domena od razu wymaga `FxMap`, więc nie było commitu z cichym kursem; (3) E0.1b (endpoint `GET /portfolios/fx-rate` + poprawka obu dialogów) wdrożone razem z wycinkiem, zgodnie z ryzykiem z §8; (4) istniejące Operacje z kursem USD nie są naprawiane (E0.8/E2.0), a `total_fees` dalej sumuje różne waluty.

## 8. Ryzyka i wycofanie

| Ryzyko | Mitygacja |
|---|---|
| **Dialogi nadal podpowiadają kurs USD** (`BuyAssetDialog.tsx:62-64`, `SellAssetDialog.tsx:49` — ten drugi nie jest w F4): nowa Operacja w Portfelu PLN na walorze EUR dostanie `fx_rate` 1,08 zamiast 4,32, a wartość będzie już poprawna — wynik (`unrealized_pnl`) zrobi się zawyżony | E0.1b (S, ~1 dzień) **blokuje wydanie na `main` razem z tym wycinkiem** (nie wdrażać K1–K7 bez E0.1b); do tego czasu wpisywać kurs ręcznie; istniejące operacje z kursem z dialogu — raport E0.8 / przebudowa E2.0 |
| Heurystyka `exchange_rate == 1` ∧ kod ≠ USD (przed E1.1) | błąd tylko w stronę „brak kursu”, nigdy cichego kursu 1; zastępowana w E1.1 |
| Zmiana kształtu odpowiedzi (`null`) | frontend w K5; pola addytywne; typy `\| null` przechwycą użycia przy `npm run build` |
| Stale kursy po awarii dostawcy (`market_data.py:121-123` pomija walutę) | kurs z poprzedniego odświeżenia zostaje (jak dziś); „nieaktualny” — E1.7 |
| `DashboardPage.tsx:16` używa `Number(null) \|\| 0` — przy `null` suma kokpitu po cichu się zaniży (ten sam rodzaj błędu co F1) | do E0.9 kokpit pokazuje sumy tylko z pól bez `null`; w K5 dopisać „—” dla Portfela z `rate_missing` albo wyłączyć dodawanie takich Portfeli do sumy z adnotacją |
| `FxMapBuilder` pomija `Currency.base_currency_id` (seed ma EUR z bazą USD); heurystyka `exchange_rate != 1` nie odróżni waluty o kursie dokładnie 1 | błąd tylko w stronę „brak kursu”; `base_currency_id` nie jest używane przez wycenę dziś; zastąpione historią kursów w E1.1 |
| ADR-0015 i ADR-0005 mają status `Proposed` | wycinek używa tylko ustalonej w roadmapie formy (mapa z serwisu); przy odrzuceniu zmienia się źródło mapy w `FxMapBuilder`, nie domena |

Wycofanie: brak migracji ani danych — `git revert` kroków od K5 wstecz do K1; krok K3 jest wstecznie zgodny (zapas), więc dowolny prefiks K1–K3 można wdrożyć osobno.

## 9. Definicja ukończenia

Komendy z `CLAUDE.md` projektu (backend z aktywnym `.venv`, `cd backend`):

| Co | Komenda |
|---|---|
| Lint / format | `ruff check .` ; `ruff format --check .` |
| Typy | `mypy app` (`strict`) |
| Testy | `pytest` — wymaga jednorazowej bazy PostgreSQL w `TEST_DATABASE_URL` (lub lokalnego `DATABASE_URL`; `conftest.py` odmawia startu na nielokalnej); bez bazy: `pytest -m "not integration"` (K6 wtedy niezweryfikowany — zaznaczyć w opisie) |
| Czystość domeny / granice | `pytest app/modules/portfolios/tests/unit/test_domain_purity.py app/core/tests/test_architecture.py` |
| Brak migracji | `git diff --stat -- backend/alembic` puste |
| Księga bez zmian | `git diff --stat -- backend/app/modules/portfolios/domain/ledger.py` puste; `test_ledger_parity.py` zielony |
| Frontend (`cd frontend`) | `npm run lint` ; `npm run build` |
| Baza wiedzy | `.venv/Scripts/python.exe .claude/skills/knowledge-base/scripts/kb_validate.py --root . --strict` (w tym środowisku: `python3 /home/user/ai-tools/skills/knowledge-base/scripts/kb_validate.py --root . --strict`) |

**Kryteria akceptacji** (liczby z pkt 2, tolerancja ±0,000001 na kursie, wartości w odpowiedzi do 3 miejsc):

1. Portfel PLN, Z1: A = 4 320, B = 4 000, C = 300; `positions_value` = 8 620, `total_value` = 9 620, `total_profit_loss` = −380, `total_return_pct` = −3,8; udziały 44,9064 / 41,5800 / 3,1185; `rate_missing` = false.
2. Portfel USD: wartości jak dotąd (EUR ×1,08, PLN ×0,25); pozycje w walucie Portfela: kurs 1.
3. Walor w walucie bez kursu: pozycja `rate_missing=true`, wartości `null`; Portfel `total_value=null`, `rate_missing=true`; HTTP 200.
4. `grep -rn exchange_rate backend/app/modules/portfolios/domain` puste; `test_architecture.py` i `test_domain_purity.py` zielone.
5. Frontend: pozycja z `rate_missing` pokazuje „—” i „Brak kursu”, bez „0,00”.

**Dokumentacja (K7, w tym samym commicie co kod, reguły 4, 7, 8 z `knowledge-base.md`):** `05_portfolios_module.md` — §3 (reguły), §4 (tabela `valuation.py`: nowa sygnatura), §5 (wycena kursem krzyżowym, `rate_missing`), §7 (konstruktory serwisów), §8 (układ: `services/fx.py`), §10 „Stan vs cel” (wiersz: wycena walut obcych → zgodne), `last_reviewed: 2026-10-02`; `docs/business/CONTEXT.md` — nowe pojęcia „Kurs krzyżowy” i „Brak kursu” (z listą _Unikać_); [kontrakt API](../technical/backend/09_kontrakt_api_docelowy.md) — wiersz `RATE_MISSING` i pola odpowiedzi (`rate_missing`, wartości nullable); [stan vs cel](../research/06_stan_found-tracker_vs_cel.md) jest dowodem L4 (append-only) — nie edytować, status F1 odnotować w `05_portfolios_module.md` §10; `04_assets_module.md` bez zmian (kontrakt `assets` nietknięty). Wiersz planu w `docs/00_KNOWLEDGE-MAP.md` jest już dodany (ten sam commit co plan). Po wdrożeniu: ustawić status tego planu zgodnie z konwencją (draft → po akceptacji właściciela).

**Rozmiar:** M — K1 0,5 d, K2 0,5 d, K3 0,5 d, K4 1 d, K5 0,5 d, K6 0,5 d (PostgreSQL), K7 0,25 d = ok. 3,75 d samej pracy; **4–5 d** realnie: K4 dotyka 5 plików testów, wiringu i protokołów, K5 — 4 plików frontendu bez testów, K6 wymaga fixture PostgreSQL (szacunek **[wniosek]**).

## Otwarte punkty

| # | Pytanie / blokada | Rekomendacja |
|---|---|---|
| 1 | Co pokazać przy braku kursu: sumy `null` czy suma częściowa z flagą? | `null` + `rate_missing` (pkt 3); decyzja właściciela |
| 2 | Czy E0.1b (endpoint `fx-rate` + oba dialogi) w tym samym wycinku? | osobny review i commity, ale **wydanie na `main` blokujące razem z wycinkiem** — ryzyko w pkt 8 |
| 3 | `FxMapBuilder` importuje stałą `DEFAULT_CURRENCY_CODE` z `assets.constants` czy dostaje kod USD z `CurrencyService`? | stała (test architektury jej nie flaguje, `test_architecture.py:475-500`); metoda w serwisie, jeśli właściciel woli ścisłą lekturę ADR-0006 |
| 4 | `total_fees` Portfela sumuje opłaty w walutach waloru (`valuation.py:89`; `ledger.py:182,195`) | osobny defekt, poza wycinkiem — kandydat do E2.x |
| 5 | Operacje już zapisane z `fx_rate` z dialogu (USD-owym) | raport E0.8, przebudowa E2.0; wycinek ich nie naprawia |
| 6 | Seed: blok `PORTFOLIOS` to `seed_data.py:187-212` (roadmapa podaje 187-211 — różnica o jedną linię, bez znaczenia) | seed ma tylko Portfele w walucie waloru — fixture w testach, nie w seedzie |
| 7 | Akceptacja ADR-0005 i ADR-0015 (`Proposed`) | wycinek nie wymaga; E1.1 wymaga ADR-0015 |
| 8 | Brak `.venv` i PostgreSQL w środowisku autora planu | liczby policzone ręcznie, testów nie uruchamiano; pierwszy krok K1 zaczyna od `pytest -m "not integration"` jako bazy odniesienia |
