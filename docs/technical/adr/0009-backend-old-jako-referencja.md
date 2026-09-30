---
id: adr-0009-backend-old-reference
status: Proposed
last_reviewed: 2026-09-30
type: decision
scope: backend/migration
---

# `backend-old/` (Django) jest wyłącznie referencją logiki biznesowej; nowa logika powstaje w `backend/app/`

Stara aplikacja Django w `backend-old/` służy do odczytu obecnego zachowania (np. `portfolios/services/`, `portfolios/analytics/`). Nie importujemy z niej, nie dodajemy tam funkcji; zostanie usunięta po zakończeniu przepisywania.

## Kontekst

Backend jest w trakcie migracji z Django na FastAPI. Logika biznesowa (przeliczanie salda, pozycji, metryk) została zaprojektowana w Django; jej zachowanie jest jedyną specyfikacją, bo brak osobnych wymagań. `backend-old/` jest niezacommitowany (`??` w `git status`).

## Decyzja

- `backend-old/` to **specyfikacja wykonywalna**: przed przepisaniem reguły czytamy jej implementację i testy (`backend-old/portfolios/tests/`).
- Nowy kod nie importuje z `backend-old/` i nie jest od niego zależny w czasie wykonywania.
- Zgodność zachowania potwierdzamy testami w `backend/app/**/tests/` (te same scenariusze, wartości liczbowe jako `Decimal`).
- Rozbieżność świadomie wprowadzona względem Django (poprawka błędu) jest zapisywana w dokumencie modułu w sekcji „Stan vs cel”, nie po cichu.
- Usunięcie `backend-old/` następuje po domknięciu kroków R-04…R-08 planu i za zgodą właściciela.

## Rozpatrywane alternatywy

- **Zachować Django jako drugi backend.** Dwa źródła prawdy, podwójne utrzymanie. Odrzucone.
- **Automatyczne tłumaczenie kodu.** Nie zachowa architektury docelowej (warstwy, `domain/`). Odrzucone.
- **Usunąć `backend-old/` od razu.** Gubimy specyfikację w trakcie przepisywania. Odrzucone (git trzyma historię, ale czytanie z working tree jest wygodniejsze).

## Konsekwencje

**Pozytywne**
- Jasne źródło odpowiedzi na „jak to działało”.

**Negatywne**
- Katalog zaśmieca repozytorium do końca migracji; ryzyko przypadkowego importu (pilnuje test architektury, krok R-09).
