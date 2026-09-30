---
id: plan-refactor-to-waterworks
status: draft
last_reviewed: 2026-09-30
type: mixed
scope: plans/backend-refactor
---

# Plan: doprowadzenie backendu do wzorca waterworks

Plan (L3) — **nie opisuje stanu systemu**; stan opisują dokumenty [L2](../technical/backend/01_backend-architecture.md#10-stan-kodu-vs-cel) i kod. Cel: warstwa biznesowa rozwijana tak jak w waterworks-monitoring-platform. Wszystkie ADR-y z [`technical/adr/`](../technical/adr/) mają status `Proposed` — **kroki kodowe ruszają po ich akceptacji przez człowieka.**

## Zasady wykonania

- Jeden krok = jedno zadanie = osobny przegląd. Bez commitów bez zgody ([CLAUDE.md](../../CLAUDE.md)).
- Przed krokiem: przeczytaj odpowiedni dokument modułu i fragment `backend-old/` ([ADR-0009](../technical/adr/0009-backend-old-jako-referencja.md)).
- Po kroku: `ruff check .`, `ruff format --check .`, `pytest` (wymaga `DATABASE_URL`), aktualizacja sekcji „Stan vs cel” dokumentu modułu i `last_reviewed`.
- Moduł, którego dotykasz, doprowadzasz do pełnej struktury docelowej (nie mieszaj stylów).
- Instalacja zależności i uruchomienie `install.py` — tylko za zgodą.

## Kroki

### Faza A — infrastruktura (bez zmiany zachowania API)

| Krok | Zakres | Kryterium ukończenia | Zależy od |
|---|---|---|---|
| **R-01** | `core/errors.py`: `APIError` + podklasy + `register_error_handlers`; podpięcie w `main.py` ([ADR-0007](../technical/adr/0007-kontrakt-bledow-z-code.md)). Zamiana `HTTPException` w serwisach i `ValueError` na wyjątki z `code` | Brak `HTTPException` w `services/`; brak `except Exception → 400` w routerach; testy kontraktu `{"detail","code"}` | ADR-0007 |
| **R-02** | `infrastructure/sql/repository.py`: `SQLRepository.transaction()`; repozytoria dziedziczą, tracą `commit`/`commit: bool`; `get_*`→`find_*` ([ADR-0001](../technical/adr/0001-jedna-sesja-na-request.md), [ADR-0004](../technical/adr/0004-repozytoria-get-vs-find.md)); granica transakcji w serwisach | `grep commit=` w `repositories/` puste; każdy zapis w serwisie pod `transaction()` | ADR-0001, ADR-0004 |
| **R-03** | `session_scope`, `SessionScope`, `provide` w `core/dependencies.py`; `create_session_scope` w `factory.py`; testy jednostkowe w `infrastructure/tests/unit/` ([ADR-0002](../technical/adr/0002-sesja-poza-zadaniem-entrypointy-i-wiring.md)) | `get_db` zbudowany na tym samym mechanizmie; testy rollbacku (w tym `SystemExit`) | R-02 |

### Faza B — moduły (po jednym, w tej kolejności)

| Krok | Moduł | Zakres | Kryterium ukończenia |
|---|---|---|---|
| **R-04** | `assets` | rozbicie `services/service.py` na serwisy zasobów + `market_data`; port rynkowy (`yfinance` za `Protocol`); logika z `api/assets.py` do serwisów; `wiring.py`; `AssetService.get_or_create_by_ticker` (dla `portfolios`); `tests/unit/` | router bez repozytoriów i bez `HTTPException`; testy serwisu bez sieci |
| **R-05** | `core_data` | struktura `api/ services/ repositories/ schemas/ models/`; `wiring.py`; `ConflictError` | płaskie pliki znikają; testy w `unit/` + `integration/` |
| **R-06** | `security` | struktura docelowa; `AuthService(UserService)`; `get_current_user` przeniesiony do `security/dependencies.py`; `AuthenticationError` z `code`; `wiring.py`; usunięcie importu w ciele funkcji | brak zależności `security → core_data.repository`; brak cyklu importów |
| **R-07** | `portfolios` (struktura) | podfoldery `api/ services/ repositories/ schemas/ models/`; rozbicie `api.py` na `portfolios`, `operations`, `metrics`; router tylko przez serwisy; `wiring.py` | `api/` nie importuje repozytoriów ani modeli; brak funkcji `_serialize_*` w routerze |
| **R-08** | `portfolios` (`domain/`) | `domain/` z `PortfolioLedger`, enumami i błędami ([ADR-0005](../technical/adr/0005-warstwa-domeny.md)); `OperationService` z typowanymi argumentami zamiast `dict`; `Decimal` do granicy schematu ([ADR-0010](../technical/adr/0010-decimal-i-precyzja-pieniedzy.md)); rozdzielenie I/O od obliczeń w `analytics/` (port cen); rdzenie bez commitu ([ADR-0008](../technical/adr/0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md)); testy domeny bez bazy; testy parytetu z `backend-old/portfolios/tests/` | walidacja operacji w jednym miejscu; `test_domain_purity`; testy parytetu wartości z Django zielone |

### Faza C — egzekwowanie i otoczenie

| Krok | Zakres | Kryterium ukończenia |
|---|---|---|
| **R-09** | `core/tests/test_architecture.py` (AST): R1, R4, R5, R8 z ADR-0002; API bez repozytoriów; brak `HTTPException` w serwisach; `domain/` bez zakazanych importów; brak importów z `backend-old/` | test zielony; test detektorów (brak fałszywych negatywów) |
| **R-10** | `mypy`: instalacja w `.venv` (za zgodą), poprawka `mypy_path` w `pyproject.toml` (dziś wskazuje katalog obcego projektu), override dla `api/` i testów; naprawa błędów | `mypy app` przechodzi |
| **R-11** | Reguły `architecture-decisions` i `knowledge-base` w `.claude/rules/ai-tools/` (`install.py --only ...`, za zgodą); `.claude/rules/ai-tools/` zsynchronizowane z ai-tools | reguły obecne; wpis w `CLAUDE.md` zgodny |
| **R-12** | `.github/workflows` (backend: ruff, mypy, pytest z Postgres; frontend: lint, build), `.pre-commit-config.yaml` | CI zielone na `main` |
| **R-13** | `docs/knowledge_base/` (potwierdzone ustalenia), hook `kb-validate`; usunięcie `backend-old/` po zgodzie właściciela ([ADR-0009](../technical/adr/0009-backend-old-jako-referencja.md)) | walidator `--strict` zielony; `backend-old/` usunięty |

## Kolejność i równoległość

R-01 → R-02 → R-03 sekwencyjnie. R-04…R-06 można robić w dowolnej kolejności po R-03, ale `portfolios` (R-07, R-08) dopiero po R-04 (potrzebuje `AssetService`) i R-06 (`get_current_user`). R-09 najlepiej zaraz po R-03, z listą wyjątków, która maleje z każdym modułem.

## Ryzyka

- **Zmiana kontraktu błędów** (R-01): frontend czyta dziś `detail`; dodanie `code` jest wstecznie zgodne, ale komunikaty zmienią się tam, gdzie były `str(exc)`.
- **Brak testów parytetu** dla metryk: wektory zależą od danych Yahoo; testy muszą używać stałych cen z portu.
- **Niezacommitowana migracja** w drzewie roboczym: kroki R-xx zmieniają te same pliki — wykonuj je dopiero po domknięciu obecnej serii zmian przez właściciela.
- **Otwarte:** wariant (a)/(b) dla `numpy` w `domain/` ([ADR-0005](../technical/adr/0005-warstwa-domeny.md)).
