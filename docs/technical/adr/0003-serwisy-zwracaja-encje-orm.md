---
id: adr-0003-services-return-orm
status: Proposed
last_reviewed: 2026-09-30
type: decision
scope: backend/service-contracts
---

# Serwisy CRUD zwracają encje ORM; DTO buduje FastAPI przez `response_model`

Serwis operujący na encji zwraca obiekt SQLAlchemy, nie schemat Pydantic. Konwersja następuje w warstwie HTTP przez `response_model=` i `ConfigDict(from_attributes=True)`. Wyjątek: serwisy odczytowe agregujące dane bez odpowiadającej encji (np. wektory metryk) zwracają DTO.

## Kontekst

Serwis może oddawać encję albo schemat. Dziś routery zwracają częściowo encje (`response_model=PortfolioRead`), częściowo `dict` (`response_model=list[dict]`, `_serialize_portfolio`), co gubi kontrakt odpowiedzi.

## Decyzja

- Serwis CRUD zwraca encję; za serializację odpowiada FastAPI.
- Warunkiem jest `expire_on_commit=False` w `sessionmaker` (już ustawione) — bez tego encja po commicie miałaby wygaszone atrybuty.
- Kryterium: **CRUD nad encją → ORM; model odczytowy lub agregat → DTO** (Pydantic, zdefiniowany w `schemas/`).
- Endpoint bez `response_model` jest usterką: FastAPI zserializuje całą encję, łącznie z polami, których nie chcemy pokazywać (`User.password_hash`). Zwracanie gołego `dict` z routera jest niedozwolone.

## Rozpatrywane alternatywy

- **Serwis zwraca DTO (`model_validate(entity)`).** Czystsza granica, ale warstwa mapowania dubluje to, co robi `response_model`. Odrzucone dla CRUD; zachowane dla modeli odczytowych.
- **Obecny stan: routery budują `dict`.** Brak kontraktu, brak walidacji odpowiedzi. Odrzucone.

## Konsekwencje

**Pozytywne**
- Brak warstwy mapowania encja → DTO w każdym serwisie.

**Negatywne**
- Serwis pośrednio zależy od `expire_on_commit=False`; zmiana na `True` zepsułaby serializację bez błędu w serwisach.
- Encja ORM przecieka o warstwę wyżej, niż mówi model warstwowy — świadomie akceptowane przy tej skali.

## Notatki

Wymaga przeniesienia „pól wyliczonych” portfela i pozycji (dziś `_compute_position_fields`, `_portfolio_computed` w routerze) do serwisu odczytowego zwracającego DTO — krok R-08.
