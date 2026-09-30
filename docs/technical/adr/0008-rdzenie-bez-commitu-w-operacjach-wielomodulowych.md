---
id: adr-0008-cores-no-commit
status: Proposed
last_reviewed: 2026-09-30
type: decision
scope: backend/transaction-ownership
---

# W operacji obejmującej kilka modułów serwisy wystawiają rdzenie bez commitu, a transakcję trzyma orkiestrator

Metoda serwisu przeznaczona na krok większej operacji **nie otwiera własnego `transaction()`** — zapisuje i flushuje, zostawiając commit wołającemu. Kontrakt zapisany w docstringu: „No-commit core — transaction belongs to caller.” Wzorzec z waterworks (ADR-0008 tamtego projektu).

## Kontekst

Dodanie operacji kupna w `portfolios` może wymagać utworzenia waloru w `assets` (gdy użytkownik podaje nieznany ticker z klasą waloru), a potem zmiany salda, pozycji i zapisu operacji. Wszystko musi być atomowe: nieudana operacja nie może zostawić nowego waloru. Dziś atomowość zapewnia `commit=False` przekazywany do repozytoriów cudzego modułu i ręczny `op_repo.commit()` w routerze.

## Decyzja

- Metoda, która ma być krokiem większej operacji, jest „rdzeniem bez commitu”: zapisuje przez repozytorium, `flush()` gdy potrzebuje ID, **nie** commituje.
- Fakt ten jest deklarowany w docstringu metody.
- Transakcję otwiera jedna klasa orkiestrująca (np. `OperationService.record`), która odpowiada za atomowość. Działa to dzięki współdzielonej sesji ([ADR-0001](0001-jedna-sesja-na-request.md)).
- Serwis ma więc dwa rodzaje metod: samodzielne (własne `with transaction()`) i rdzenie.

## Rozpatrywane alternatywy

- **Parametr `commit: bool = True`** (obecny stan). Widoczny w sygnaturze, ale rozgałęzia każdą metodę i zachęca do `commit=False` tam, gdzie nie ma orkiestratora. Odrzucone.
- **Serwis cyklu życia jako dekorator** (ADR-0028 waterworks). Potrzebny przy portach zmian zasobów; we FundTrackerze brak takich powiadomień. Nie wdrażamy do czasu pojawienia się potrzeby.
- **Zdarzenia domenowe.** Jeden proces; nic do zyskania. Odrzucone.

## Konsekwencje

**Pozytywne**
- Atomowość operacji wielomodułowych z konstrukcji.

**Negatywne**
- Rdzeń bez commitu wywołany bez otwartej transakcji **po cichu nic nie zapisze**; jedyną ochroną jest docstring i ostrzeżenie w logu przy zamknięciu sesji.
- Dwa rodzaje metod w jednym serwisie wymagają dyscypliny nazewnictwa.
