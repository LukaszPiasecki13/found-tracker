---
id: adr-0001-single-session
status: Proposed
last_reviewed: 2026-09-30
type: decision
scope: backend/session-per-request
---

# Jedna sesja SQLAlchemy na żądanie; `transaction()` z dowolnego repozytorium domyka całą jednostkę pracy

Wszystkie repozytoria w jednym żądaniu HTTP dzielą **jedną** `Session` z zależności `get_db`. Repozytorium nie commituje samo; commit wykonuje `SQLRepository.transaction()` wołane przez serwis. Wzorzec przejęty z waterworks (ADR-0001 tamtego projektu), bez części audytowej.

## Kontekst

Operacje biznesowe dotykają wielu tabel: dodanie operacji zmienia `Operation`, `Position` i `Portfolio` naraz, a usunięcie operacji przebudowuje pozycje. Dziś repozytoria commitują same albo przyjmują `commit: bool` (`create(..., commit=False)`), a router woła `op_repo.commit()` ręcznie na końcu ([`portfolios/api.py`](../../../backend/app/modules/portfolios/api.py)) — granica transakcji jest rozsiana po trzech warstwach.

## Decyzja

- `core/dependencies.py` tworzy jedną `sessionmaker` (`expire_on_commit=False`); `get_db` wydaje sesję na żądanie i zamyka ją po odpowiedzi.
- Każde `<X>Repository(session)` składane w `wiring.py` dostaje **tę samą** sesję.
- `SQLRepository.transaction()` jest context managerem: commit po bezusterkowym wyjściu, rollback + re-raise przy wyjątku. Nie otwiera własnej transakcji — domyka całą sesję.
- Metody `create/update/delete` repozytoriów robią `add`/`delete` + `flush`, **nigdy `commit`**. Parametr `commit: bool` znika.
- Granicę transakcji wyznacza **serwis** (`with self._repo.transaction():`).

## Rozpatrywane alternatywy

- **Obecny stan: commit w repozytorium z flagą `commit: bool`.** Flagę łatwo zapomnieć; router i serwis mogą commitować w różnych miejscach, więc częściowy zapis jest możliwy. Odrzucone.
- **Klasa Unit of Work przekazywana do serwisów.** Dubluje współdzieloną sesję i zmienia sygnatury wszystkich serwisów. Odrzucone.
- **Commit w `get_db` po odpowiedzi.** Ukrywa granicę transakcji, a błąd commitu wychodzi po wysłaniu odpowiedzi. Odrzucone.

## Konsekwencje

**Pozytywne**
- Atomowość operacji wielotabelowych wynika z konstrukcji, nie z dyscypliny.
- Jedno miejsce (`transaction()`) zamiast powtarzanego `try/commit/except/rollback`.

**Negatywne**
- Serwis, który zapomni `transaction()`, po cichu nic nie zapisze; łagodzi to tylko ostrzeżenie w logu przy zamknięciu sesji ([ADR-0002](0002-sesja-poza-zadaniem-entrypointy-i-wiring.md)).
- `transaction()` nie jest re-entrantne: zagnieżdżony blok commituje zewnętrzną jednostkę pracy w połowie operacji. Operację wielomodułową opisuje [ADR-0008](0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md).
- Zależność między modułami przestaje być widoczna w sygnaturach (wspólna sesja).

## Notatki

Bez `skip_audit` i `AuditAwareSession` z waterworks — audyt odłożony, [ADR-0011](0011-audyt-odlozony.md).
