---
id: be-core-data-module
status: current
last_reviewed: 2026-10-01
type: mixed
scope: backend/core_data
applies_to:
  - backend/app/modules/core_data/**
---

# Moduł `core_data`

Dane referencyjne współdzielone przez inne moduły. W FundTrackerze (aplikacja jednoużytkownikowa, bez organizacji) moduł zawiera wyłącznie **Użytkownika** — konto, do którego przypisane są portfele. Inne moduły korzystają z jego serwisów, nigdy z repozytoriów ([ADR-0006](../adr/0006-cross-module-wylacznie-przez-serwisy.md)).

Architektura ogólna: [`01_backend-architecture.md`](./01_backend-architecture.md). Słownik: [`CONTEXT.md`](../../business/CONTEXT.md).

## 1. Model danych

| Tabela | Encja | Pola |
|---|---|---|
| `users` | `User` | `id`, `email` (unikalny, max 254), `password_hash`, `is_active` |

E-mail jest normalizowany (`strip().lower()`) przed zapisem i wyszukiwaniem. Hasło nigdy nie jest zwracane — schemat odpowiedzi `UserRead` nie zawiera `password_hash`.

## 2. Endpointy

| Metoda i ścieżka | Opis | Autoryzacja |
|---|---|---|
| `POST /auth/register` (także `/auth/register/`) | Rejestracja konta | brak |
| `GET /auth/me` (także `/auth/users/me/`) | Bieżący użytkownik | token dostępu |

Prefiks `/auth` jest historyczny (kompatybilność z frontendem); logowanie leży w [`security`](./03_security_module.md).

## 3. Reguły biznesowe

- E-mail unikalny (konflikt → `ConflictError`, HTTP 409, `code=EMAIL_ALREADY_REGISTERED`); porównanie po normalizacji (`strip().lower()`), sprawdzenie i zapis w jednym `transaction()`.
- Hasło hashuje `security` (`hash_password`, funkcja z `security/services/password.py`). `core_data` importuje ją bezpośrednio; `security` zależy od `core_data` przez `UserService` — to cykl importów modułów (`core_data.services` → `security.services.password` → …, `security.services.auth` → `core_data.services`), tolerowany dzięki pustemu `security/services/__init__.py`; szczegóły w [`03_security_module.md` §4](./03_security_module.md#4-układ).
- Serwis wystawia dla innych modułów: `find_by_id`, `find_by_email` (zwracają `None`), `register`. Repozytorium: `find_by_id`, `get_by_id` (`USER_NOT_FOUND`), `find_by_email`, `create` (tylko `add` + `flush`).
- Schemat żądania `UserCreateRequest` ma `extra="forbid"`; odpowiedź `UserResponse` nie zawiera `password_hash`.

## 4. Struktura

```text
core_data/
├─ api/users.py
├─ services/users.py
├─ repositories/users.py
├─ schemas/users.py
├─ models/user.py
├─ dependencies.py      # get_user_service = provide(build_user_service)
├─ wiring.py            # build_user_service
└─ tests/{unit,integration}/
```

Brak `entrypoints.py` — moduł nie ma jeszcze operacji spoza HTTP (kandydat: utworzenie konta administracyjnego).

## 5. Stan vs cel

| Element | Stan | Cel | Krok |
|---|---|---|---|
| Struktura, wiring, transakcje, błędy (`ConflictError`), testy `unit/` + `integration/` | zgodne ze wzorcem | — | R-05 (domknięty) |
