---
id: be-core-data-module
status: current
last_reviewed: 2026-09-30
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

- E-mail unikalny (konflikt → `ConflictError`, `code=EMAIL_ALREADY_REGISTERED`).
- Hasło hashuje `security` (`hash_password`). `core_data` **zależy od `security` tylko przez serwis haszujący**, a `security` zależy od `core_data` przez odczyt użytkownika — cykl rozwiązywany przez port albo wydzielenie hashowania do `core/` (decyzja w R-06).

## 4. Układ docelowy

```text
core_data/
├─ api/users.py
├─ services/users.py
├─ repositories/users.py
├─ schemas/users.py
├─ models/user.py
├─ dependencies.py      # get_user_service, get_current_user
├─ wiring.py            # build_user_service
└─ tests/{unit,integration}/
```

## 5. Stan vs cel

| Element | Stan | Cel | Krok |
|---|---|---|---|
| Struktura | płaskie pliki: `api.py`, `service.py`, `repository.py`, `models.py`, `schemas.py` | podfoldery wg §4 | R-05 |
| Błędy | `HTTPException(400)` w serwisie dla zajętego e-maila | `ConflictError` z `code` | R-01 |
| Transakcje | `repo.create` robi `commit` + `refresh` | `transaction()` w serwisie, repo tylko `add`/`flush` | R-02 |
| Wiring | łańcuch `Depends` w `dependencies.py` | `wiring.py` + `provide` | R-05 |
| `get_current_user` | w `core_data/dependencies.py`, rzuca `HTTPException`, import `security` w ciele funkcji (obejście cyklu) | zależność HTTP w `security/dependencies.py`, rzuca `AuthenticationError` z `code` | R-06 |
| Testy | `tests/` płasko + `integration/` | `tests/unit/`, `tests/integration/` | R-05 |
