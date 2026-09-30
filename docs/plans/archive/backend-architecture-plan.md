---
id: plan-backend-architecture-old
status: draft
type: reference
scope: plans/archive
last_reviewed: 2026-09-30
---

> **Zastąpione** przez [`01_backend-architecture.md`](../../technical/backend/01_backend-architecture.md) i [ADR-y techniczne](../../technical/adr/). Zachowane jako archiwum (reguła: nic nie kasujemy); do usunięcia za zgodą właściciela.

# Backend Architecture Plan - Found Tracker

## 1. Cel dokumentu

Ten dokument opisuje plan docelowej architektury backendu aplikacji Found Tracker na podstawie aktualnego kodu oraz wzorca Layered Modular Monolith.

Cel: uporzadkowac granice modulow, ograniczyc sprzezenie miedzy warstwami, uproscic testowanie i przygotowac backend do dalszego rozwoju bez chaosu strukturalnego.


## 3. Architektura docelowa

Docelowy model: Layered Architecture + Modular Monolith.

### 3.1 Warstwy

- API Layer (presentation): routery FastAPI, walidacja request/response, mapowanie DTO.
- Service Layer (business): przypadki uzycia, reguly biznesowe, orkiestracja.
- Repository Layer (data access): operacje SQL i dostep do zrodel danych.
- Infrastructure Layer: engine SQL, sesje, integracje z uslugami zewnetrznymi.
- Shared Core: konfiguracja, logowanie, zaleznosci globalne.
- Errors: wyjatki domenowe i globalne handlery FastAPI.

### 3.2 Moduly domenowe

- security: logowanie, tokeny, hasla, autoryzacja.
- core_data: user, role, dane referencyjne systemu.
- assets: klasy aktywow, walory, kursy, market data.
- portfolios: portfele, pozycje, operacje, transfery gotowkowe.
- analytics (wydzielenie z portfolios): metryki i wektory portfela.

## 4. Proponowana struktura katalogow

backend/app/
- main.py
- core/
  - config.py
  - dependencies.py
  - logging.py
- errors/
  - exceptions.py
  - handlers.py
- infrastructure/
  - sql/
    - base.py
    - factory.py
    - models_registry.py
- modules/
  - security/
    - api/
    - services/
    - repositories/
    - schemas/
    - models/
    - dependencies.py
    - tests/
  - core_data/
    - api/
    - services/
    - repositories/
    - schemas/
    - models/
    - dependencies.py
    - tests/
  - assets/
    - api/
    - services/
    - repositories/
    - schemas/
    - models/
    - dependencies.py
    - tests/
  - portfolios/
    - api/
    - services/
    - repositories/
    - schemas/
    - models/
    - dependencies.py
    - tests/
  - analytics/
    - services/
    - schemas/
    - tests/

## 5. Reguly zaleznosci

- API moze zalezec od services, errors, core.
- Services moga zalezec od repositories, contracts innych modulow, errors, core.
- Repositories moga zalezec od infrastructure, errors, core.
- Infrastructure moze zalezec tylko od core i errors.
- Zakaz bezposrednich importow API -> repositories.
- Zakaz logiki biznesowej w routerach.
- Zakaz cykli miedzy modulami.


