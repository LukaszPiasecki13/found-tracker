---
id: adr-0004-repo-get-vs-find
status: Proposed
last_reviewed: 2026-09-30
type: decision
scope: backend/repository-contracts
applies_to:
  - backend/app/modules/*/repositories/**
---

# Repozytorium ma dwie metody odczytu: `find_*` zwraca `None`, `get_*` rzuca `NotFoundError`

W repozytoriach `find_by_<klucz>` zwraca `T | None`, a `get_by_<klucz>` woła `find_*` i rzuca `NotFoundError`, gdy wyniku brak. Kolekcje to `list_*`. Konwencja dotyczy wyłącznie repozytoriów; w serwisach kontrakt odczytu mówi sygnatura zwrotu, nie prefiks.

## Kontekst

Dziś wszystkie repozytoria mają `get_by_id(...) -> T | None`, więc każdy wołający powtarza `if x is None: raise HTTPException(404, "... not found")`; teksty i statusy rozjeżdżają się między routerami (`portfolios/api.py`, `assets/api/*`). Pominięcie sprawdzenia kończy się `AttributeError` na `None`. Zmiana nazewnictwa jest przy okazji wymuszona: `get_*` zmienia znaczenie z „zwraca `None`” na „rzuca”.

## Decyzja

- `find_*` zwraca `T | None` i nigdy nie rzuca. Używamy tam, gdzie brak wyniku jest poprawnym stanem (unikalność, idempotencja, opcjonalna relacja).
- `get_*` zwraca `T` i rzuca `NotFoundError` z `code` (`PORTFOLIO_NOT_FOUND`). Używamy tam, gdzie brak jest błędem.
- `list_*` zwraca `list`, nie rzuca przy pustym wyniku.
- Parę tworzymy **na żądanie**: `get_*` powstaje tylko, gdy jedyne, co wołający robi z `None`, to zamiana na generyczny `NotFoundError`. Jeśli `None` wchodzi w złożony warunek (np. sprawdzenie właściciela → 404, nie 403) albo jest stanem poprawnym, zostaje sam `find_*` i check w serwisie.

## Rozpatrywane alternatywy

- **Repozytorium tylko z `Optional`, wyjątek rzuca serwis.** Czystsza granica, ale każdy serwis powtarza sprawdzenie i tekst błędu. Odrzucone.
- **Jedna metoda z flagą `raise_if_missing`.** Typ zwrotu zależy od wartości flagi (`@overload` + `Literal` na każdej metodzie). Odrzucone.
- **Odwrotne nazwy** (`get_*` = `None`, `find_*` = rzuca). Semantycznie równoważne; wybrano zgodność z waterworks, aby jedna konwencja obowiązywała w obu projektach.

## Konsekwencje

**Pozytywne**
- Tekst i `code` błędu „nie znaleziono” żyją w jednym miejscu.

**Negatywne**
- Repozytorium importuje `NotFoundError` z `core/errors` — wyjątek niosący status HTTP; świadomy przeciek warstwy (jak [ADR-0003](0003-serwisy-zwracaja-encje-orm.md)).
- Znaczenie `find`/`get` nie jest w ekosystemie jednolite; konwencji trzeba się nauczyć.
- Przy migracji wszystkie dzisiejsze `get_by_id -> T | None` trzeba przemianować na `find_by_id` (krok R-02), a następnie dodać `get_*` tam, gdzie kryterium jest spełnione.
