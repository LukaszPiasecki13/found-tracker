---
id: be-security-module
status: current
last_reviewed: 2026-09-30
type: mixed
scope: backend/security
applies_to:
  - backend/app/modules/security/**
---

# Moduł `security`

Uwierzytelnianie (logowanie, tokeny JWT access/refresh) i hashowanie haseł. **Nie** przechowuje użytkowników — to [`core_data`](./02_core_data_module.md). Autoryzacja w FundTrackerze sprowadza się do „zalogowany użytkownik widzi tylko własne dane” (`owner_id`); brak ról i uprawnień. Inne moduły korzystają z `security` przez zależność HTTP (`get_current_user`), nigdy przez jego repozytoria.

## 1. Endpointy

| Metoda i ścieżka | Opis |
|---|---|
| `POST /auth/login` (także `/auth/token`) | E-mail + hasło → para tokenów `{access, refresh}` |
| `POST /auth/token/refresh` | Token odświeżający → nowa para tokenów |

## 2. Mechanizm

- **Hasła:** `passlib[bcrypt]` (`hash_password`, `verify_password` w `services/password.py`).
- **Tokeny:** `python-jose`, `HS256`, `iss`/`aud` walidowane przy dekodowaniu. Token dostępu: 30 min (`access_token_expire_minutes`); odświeżający: 1 dzień. Pole `type` (`access`/`refresh`) odróżnia tokeny.
- **Konfiguracja:** `core/config.py` (`secret_key`, `algorithm`, `jwt_issuer`, `jwt_audience`).
- **`get_current_user`:** dekoduje token dostępu, wczytuje użytkownika, odrzuca nieaktywnego.
- **Zależność biblioteczna:** `python-jose[cryptography]>=3.4.0` (progi bezpieczeństwa z CVE-2024-33663/33664/29370 — [security-checklist](../../../.claude/rules/ai-tools/security-checklist.md)).
- **Odstępstwa od security-checklist** (HS256, `localStorage`, brak rotacji refresh, brak rate-limitu): [ADR-0012](../adr/0012-jwt-odstepstwa-od-checklisty.md).

## 3. Układ docelowy

```text
security/
├─ api/auth.py
├─ services/{auth,token,password}.py
├─ schemas/auth.py
├─ dependencies.py      # get_auth_service, get_token_service, get_current_user, oauth2_scheme
├─ wiring.py            # build_auth_service, build_token_service
└─ tests/{unit,integration}/
```

Moduł nie ma `repositories/` ani `models/` — korzysta z `UserService` z `core_data` przez serwis ([ADR-0006](../adr/0006-cross-module-wylacznie-przez-serwisy.md)). `password.py` i `token.py` zostają w `services/`: zależą od bibliotek trzecich (`passlib`, `jose`), które wykluczają je z `domain/` (DOM-1) — to adaptery.

## 4. Stan vs cel

| Element | Stan | Cel | Krok |
|---|---|---|---|
| Struktura | płaskie `api.py`, `dependencies.py`, `schemas.py`; `services/` już jest | podfoldery wg §3 | R-06 |
| Błędy | `HTTPException(401)` w `AuthService` i `get_current_user` | `AuthenticationError` z `code` (`INVALID_CREDENTIALS`, `INVALID_TOKEN`, `USER_NOT_FOUND`) | R-01 |
| Zależność od repozytorium innego modułu | `AuthService(UserRepository)` — repozytorium `core_data` | `AuthService(UserService)` | R-06 |
| Wiring | `get_token_service()` składa się w `dependencies.py` | `wiring.py`: `build_token_service`, `build_auth_service(session)` | R-06 |
| `get_current_user` | w `core_data/dependencies.py` z importem w ciele funkcji | w `security/dependencies.py` | R-06 |
| Rate limiting logowania | brak (`slowapi` nie jest w `requirements.txt`) | patrz ADR-0012 | poza planem, po decyzji |
| Wersja `python-jose` | `>=3.4.0` w `requirements.txt` (plik zmieniony w drzewie roboczym, niezacommitowany) | utrzymać | — |
