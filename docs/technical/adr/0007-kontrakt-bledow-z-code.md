---
id: adr-0007-error-contract
status: Proposed
last_reviewed: 2026-09-30
type: decision
scope: backend/error-handling
---

# Kontrakt błędów: jedna hierarchia `APIError` z `code`, odpowiedź `{"detail", "code"}`

Wszystkie błędy domenowe dziedziczą z `APIError` (`core/errors.py`) i niosą komunikat, status HTTP i stabilny `code` (`UPPER_SNAKE`). Globalne handlery zamieniają je na `{"detail": "...", "code": "..."}`. Serwisy nigdy nie rzucają `HTTPException`; router nie łapie wyjątków ręcznie. Zgodne z regułą [error-handling-patterns](../../../.claude/rules/ai-tools/error-handling-patterns.md).

## Kontekst

Dziś `core/errors.py` nie istnieje. Serwisy i `dependencies.py` rzucają `HTTPException` (`UserService`, `AuthService`, `get_current_user`), serwisy domenowe rzucają gołe `ValueError`, a `portfolios/api.py` łapie `except Exception → HTTPException(400, str(exc))`, co ujawnia klientowi wewnętrzne komunikaty i ukrywa błędy programistyczne jako 400. Brak `code` uniemożliwia frontendowi mapowanie komunikatów.

## Decyzja

- `APIError(message, status_code, code=None, headers=None)`; podklasy: `BadRequestError` 400, `AuthenticationError` 401, `ForbiddenError` 403, `NotFoundError` 404, `ConflictError` 409, `GoneError` 410, `ValidationException` 422.
- `code` jest obowiązkowe dla błędów domenowych: `<ENCJA>_<WARUNEK>` (`PORTFOLIO_NOT_FOUND`, `INSUFFICIENT_CASH`).
- Handlery: `APIError` → `{"detail", "code"}` (5xx logowane jako `error`, 4xx jako `info`, z metodą i ścieżką); `pydantic.ValidationError` → 422 z listą; każdy inny wyjątek → 500 ze stałym `"Internal server error"`, traceback tylko w logu.
- Komunikaty `detail` są po angielsku (jeden język API); lokalizacja jest sprawą klienta.
- Wyjątek domenowy z `domain/` (`ValueError`) tłumaczy serwis na `BadRequestError`. Złapanie `Exception` w routerze jest zabronione.
- Kierunek: dodanie pól RFC 9457 (`type`, `title`, `status`) addytywnie, gdy frontend będzie gotowy — poza zakresem tego ADR.

## Rozpatrywane alternatywy

- **Zostać przy `HTTPException` w serwisach.** Serwis zna HTTP, brak `code`, trudne do testowania. Odrzucone.
- **Od razu RFC 9457.** Wymaga zmian we frontendzie. Odrzucone na tym etapie; ścieżka addytywna zostaje otwarta.
- **Kody błędów jako `Enum`.** Dodatkowy koszt przy niewielkiej liczbie kodów. Do ponownej oceny, gdy kodów będzie >30.

## Konsekwencje

**Pozytywne**
- Jeden kontrakt dla backendu i frontendu; błędy programistyczne nie maskują się jako 400.

**Negatywne**
- Zmiana kształtu odpowiedzi błędu w endpointach, które dziś zwracają gołe `detail` — frontend czyta `detail`, więc zmiana jest wstecznie zgodna (dodajemy `code`).
- `ValueError` z istniejących serwisów wymaga przejrzenia wszystkich miejsc (krok R-01/R-08).
