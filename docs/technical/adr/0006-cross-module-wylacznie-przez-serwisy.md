---
id: adr-0006-cross-module
status: Proposed
last_reviewed: 2026-09-30
type: decision
scope: backend/cross-module-access
---

# Cross-module wyłącznie przez serwisy — co to znaczy w praktyce

Komunikacja między modułami idzie przez warstwę serwisów. Serwis nie trzyma repozytorium innego modułu; import cudzego modelu ORM w JOIN-ie repozytorium jest dozwolony (tylko odczyt); cudzą warstwę `domain/` importuje się wyłącznie przez jej `__init__.py`. Wzorzec z waterworks (ADR-0025 tamtego projektu).

## Kontekst

Dzisiejszy kod łamie zasadę w kilku miejscach:
- `portfolios/api.py` importuje `AssetRepository`, `AssetClassRepository`, model `Asset` i `MarketDataService` z `assets` — **API → repozytorium cudzego modułu**, z logiką tworzenia waloru w routerze.
- `security/services/auth.py` trzyma `UserRepository` z `core_data`.
- `core_data/dependencies.py` importuje `security.dependencies` w ciele funkcji, by ominąć cykl.

## Decyzja

1. **Serwis nie trzyma repozytorium innego modułu** ani nie woła go bezpośrednio. Brakującą metodę dopisuje się do serwisu tamtego modułu.
2. **API nie importuje repozytoriów** — ani własnych, ani cudzych.
3. **Cudzy serwis składa `wiring.py`** przez import modułu (`from app.modules.assets import wiring as assets_wiring`), nie przez powielanie kompozycji ani import funkcji po nazwie.
4. **Model ORM innego modułu w repozytorium** jest dozwolony wyłącznie do warunku JOIN; repozytorium czyta cudzy model, nigdy go nie zapisuje.
5. **Porty** (`typing.Protocol`) zdefiniowane przez moduł nadrzędny są dozwolone jako odwrócenie zależności przy cyklu; moduł zależny implementuje je strukturalnie, a składa je `wiring.py`.
6. **Cudza warstwa `domain/`** — import wyłącznie z `app.modules.<obcy>.domain` (`__init__.py`), nigdy submodułu.

Dopuszczalny kierunek zależności modułów: `portfolios → assets`, `portfolios → core_data`, `security → core_data`. Odwrotne kierunki wymagają portu.

## Rozpatrywane alternatywy

- **Zakaz także dla modeli ORM w JOIN-ach.** Wymusiłby duplikację kluczy na tabelach bez odpowiadającej korzyści. Odrzucone.
- **Wspólna warstwa „repozytoria” dla wszystkich modułów.** Kończy modularność. Odrzucone.
- **Zdarzenia między modułami.** Jeden proces, nic do zyskania. Odrzucone.

## Konsekwencje

**Pozytywne**
- Logika tworzenia waloru z `ticker` przeniesiona do `assets` (zamiast w routerze portfeli) ma jedno miejsce i jeden zestaw reguł.

**Negatywne**
- Więcej metod w serwisach „dostawców” (`AssetService.get_or_create_by_ticker`, `find_by_ticker`).
- Zakaz jest na razie egzekwowany tylko przeglądem; test AST w kroku R-09.
