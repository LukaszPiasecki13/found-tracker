---
id: adr-0002-session-outside-request
status: Proposed
last_reviewed: 2026-09-30
type: decision
scope: backend/session-outside-request
---

# Poza żądaniem HTTP sesję otwiera entrypoint modułu przez `session_scope()`, a obiekty składa wyłącznie `wiring.py`

Kod uruchamiany bez żądania HTTP (start aplikacji, CLI, zadania w tle) nie pisze własnego szkieletu otwórz → commit → rollback → zamknij. Sesję otwiera `session_scope()`: gwarantuje rollback przy błędzie i zamknięcie, ale **nigdy nie commituje**. Wołać go wolno tylko w `entrypoints.py` modułu. Serwisy składa jedna funkcja `build_<x>(session)` w `wiring.py`, wspólna dla HTTP, entrypointów i testów. Uzupełnia [ADR-0001](0001-jedna-sesja-na-request.md). Wzorzec z waterworks (ADR-0024 tamtego projektu).

## Kontekst

- Poza żądaniem (odświeżanie kursów walut i cen, przebudowa pozycji, seedy) nie ma czego wstrzyknąć; dziś `backend/seed/` tworzy sesję ręcznie.
- Dziś serwisy składane są łańcuchami `Depends` w `dependencies.py`, co wiąże je z FastAPI i uniemożliwia użycie poza HTTP. `security/dependencies.py` importuje w ciele funkcji `core_data`, żeby obejść cykl importów.
- Reguła „serwis nie zna `Session`” wymaga, by kto inny otwierał sesję także poza żądaniem.

## Decyzja

**1. Mechanizm.** `SQLConnectionFactory.create_session_scope()` zwraca context manager: otwiera sesję, przy **dowolnym** wyjątku (`BaseException`) robi rollback (błąd rollbacku jest logowany i nie przykrywa oryginału), zawsze zamyka, loguje ostrzeżenie o niezacommitowanych zmianach, **nigdy nie commituje**. `get_db` działa na tym samym mechanizmie. `core/dependencies.py` wystawia `session_scope`, typ `SessionScope` i `provide(builder)`.

**2. Anatomia modułu.** `wiring.py` (`build_<x>(session)`, bez FastAPI, bez I/O, bez commitu), `dependencies.py` (adapter: `get_<x> = provide(build_<x>)` + zależności tylko-HTTP), `entrypoints.py` (tylko gdy moduł ma operację spoza HTTP).

**3. Reguły.**

| # | Reguła |
|---|---|
| R1 | Serwisy i repozytoria nie otwierają sesji (`session_scope`, `Session(...)`, `sessionmaker(...)`) i nie importują `fastapi` |
| R2 | Obiekty składa wyłącznie `wiring.py`; konfigurację czyta z `core.config`; builder innego modułu wołamy przez `from app.modules.x import wiring as x_wiring` (toleruje cykle) |
| R3 | `dependencies.py` nie składa grafu, tylko wystawia buildery przez `provide` |
| R4 | Kod spoza HTTP (`wiring.py`, `entrypoints.py`, serwisy) nie importuje żadnego `dependencies.py` |
| R5 | Sesję poza HTTP w `backend/app/` otwiera wyłącznie `entrypoints.py`; nie commituje, nie dotyka repozytoriów, zwraca dane (nie encje ORM), przyjmuje `scope: SessionScope = session_scope` |
| R6 | Granica transakcji należy do serwisu (`repo.transaction()`) |
| R7 | Polityka błędów: domenowa w entrypoincie, procesowa (kod wyjścia, „nie startuje”) w driverze |
| R8 | Drivery (`main.py`, `cli.py`, `BackgroundTasks` w `api/`) wołają tylko entrypointy |

Skrypty `backend/seed/` są wyjątkiem od R5: wołają `session_scope()` wprost i składają serwisy przez `wiring.py`.

## Rozpatrywane alternatywy

- **Brak wspólnego mechanizmu.** Różne warianty rollbacku i zamykania. Odrzucone.
- **`build_*` w `dependencies.py`.** Kod spoza HTTP zależałby od adaptera HTTP. Odrzucone.
- **Builder tylko dla serwisów z wołającym spoza HTTP.** Dwa sposoby składania w jednym module; przenoszenie serwisu przy pierwszym wołającym spoza HTTP. Odrzucone.
- **Kontener DI (`dependency-injector`), `fastapi-injectable`.** Nowa zależność większa niż zastępowane buildery. Odrzucone.
- **`sessionmaker.begin()`** (commit na końcu bloku). Nie obsługuje operacji z kilkoma warunkowymi commitami. Odrzucone.
- **Klasa Unit of Work.** Dubluje wspólną sesję z ADR-0001. Odrzucone.

## Konsekwencje

**Pozytywne**
- Jeden szkielet cyklu życia sesji w całym repo; rollback gwarantowany mechanizmem.
- Zmiana konstruktora serwisu to jedna edycja w `wiring.py`; testy składają serwis tą samą funkcją co produkcja.

**Negatywne**
- Do dwóch nowych plików na moduł.
- `session_scope` nie commituje — serwis bez `transaction()` traci zapis.

## Notatki

Opis dla piszących kod: [`06_wiring_i_entrypointy.md`](../backend/06_wiring_i_entrypointy.md). Egzekwowanie: test AST (krok R-09 planu).
