---
id: be-security-module
status: current
last_reviewed: 2026-10-01
type: mixed
scope: backend/security
applies_to:
  - backend/app/modules/security/**
---

# Moduł `security`

Uwierzytelnianie (logowanie, tokeny JWT access/refresh), hashowanie haseł i zależność HTTP `get_current_user`. **Nie** przechowuje użytkowników — to [`core_data`](./02_core_data_module.md). Autoryzacja w FundTrackerze sprowadza się do „zalogowany użytkownik widzi tylko własne dane” (`owner_id`); brak ról i uprawnień (w waterworks: grupy/uprawnienia — tu świadomie pominięte). Inne moduły korzystają z `security` przez zależność HTTP (`get_current_user`) i `password.py`, nigdy przez jego repozytoria (moduł ich nie ma).

## 1. Endpointy

| Metoda i ścieżka | Opis |
|---|---|
| `POST /auth/login` (także `/auth/token`) | E-mail + hasło → para tokenów `{access, refresh}` |
| `POST /auth/token/refresh` (także z `/` na końcu) | Token odświeżający → nowa para tokenów |

Rejestracja i `GET /auth/me` leżą w `core_data` (prefiks `/auth` jest historyczny).

## 2. Mechanizm

- **Hasła:** `bcrypt` bezpośrednio (`hash_password`, `verify_password` w `services/password.py`); legacy `pbkdf2_sha256` z Django jest nadal weryfikowany. Limit bcrypt 72 bajty egzekwują `LoginRequest.password` (`max_length`) i `validate_password_length` (rejestracja → `PASSWORD_TOO_LONG`). Zniekształcony hash lub brak hasha → `False`, nigdy 500.
- **Brak enumeracji kont:** nieznany użytkownik, konto nieaktywne i złe hasło dają ten sam błąd `INVALID_CREDENTIALS`; hasło jest weryfikowane przed sprawdzeniem `is_active`, a dla nieznanego użytkownika wykonywana jest atrapa weryfikacji (`burn_password_verification`), żeby czas odpowiedzi nie zdradzał istnienia ani stanu konta.
- **Tokeny:** `python-jose`, `HS256`, `iss`/`aud` walidowane przy dekodowaniu. Access: `access_token_expire_minutes` (domyślnie 30 min); refresh: `refresh_token_expire_days` (domyślnie 1 dzień), oba z `core/config.py`. Pole `type` (`access`/`refresh`) odróżnia tokeny; token niewłaściwego typu jest odrzucany po obu stronach. `sub` musi być ASCII-liczbą (`parse_user_id`), inaczej 401, nie 500; tokeny bez `exp`/`iss`/`aud` są odrzucane (`python-jose` domyślnie ich nie wymaga).
- **`get_current_user`** (`dependencies.py`): `HTTPBearer(auto_error=False)`, dekoduje token dostępu, wczytuje użytkownika przez `UserService`, odrzuca nieaktywnego. Każdy 401 z tej zależności niesie `WWW-Authenticate: Bearer` (RFC 6750).
- **Zależność biblioteczna:** `python-jose[cryptography]>=3.4.0` (progi bezpieczeństwa z CVE-2024-33663/33664/29370 — [security-checklist](../../../.claude/rules/ai-tools/security-checklist.md)).
- **Odstępstwa od security-checklist** (HS256, `localStorage`, brak rotacji refresh, brak rate-limitu): [ADR-0012](../adr/0012-jwt-odstepstwa-od-checklisty.md).

## 3. Kody błędów (`errors.py`, [ADR-0007](../adr/0007-kontrakt-bledow-z-code.md))

| `code` | Status | Kiedy |
|---|---|---|
| `INVALID_CREDENTIALS` | 401 | zły e-mail/hasło/konto nieaktywne |
| `INVALID_REFRESH_TOKEN` | 401 | refresh nieczytelny, wygasły lub złego typu |
| `REFRESH_USER_NOT_FOUND` | 401 | właściciel refresh tokenu nie istnieje lub jest nieaktywny |
| `MISSING_CREDENTIALS` | 401 + challenge | brak nagłówka `Authorization: Bearer` |
| `INVALID_ACCESS_TOKEN` | 401 + challenge | access nieczytelny, złego typu lub z błędnym `sub` |
| `INACTIVE_USER` | 401 + challenge | właściciel access tokenu nie istnieje lub jest nieaktywny |

## 4. Układ

```text
security/
├─ api/auth.py
├─ services/{auth,token,password}.py
├─ schemas/auth.py
├─ constants.py         # typy tokenów, limit bajtów hasła
├─ errors.py            # InvalidCredentialsError, MissingCredentialsError, ...
├─ dependencies.py      # get_auth_service = provide(build_auth_service), get_token_service, get_current_user
├─ wiring.py            # build_token_service, build_auth_service
└─ tests/{unit,integration}/
```

Moduł nie ma `repositories/`, `models/` ani `entrypoints.py` (brak operacji spoza HTTP) — korzysta z `UserService` z `core_data` przez serwis ([ADR-0006](../adr/0006-cross-module-wylacznie-przez-serwisy.md)). `password.py` i `token.py` zostają w `services/`: zależą od bibliotek trzecich (`bcrypt`, `jose`), które wykluczają je z `domain/` (DOM-1) — to adaptery.

**Cykl `core_data` ↔ `security`:** `core_data.services.users` importuje `security.services.password`, a `security.services.auth` — `core_data.services.users`. Dlatego `security/services/__init__.py` niczego nie re-eksportuje, a `security/wiring.py` importuje `core_data.wiring` jako moduł (niezależność od kolejności importów). Kierunek `core_data → security` (tylko `hash_password`/`validate_password_length`) to świadome odstępstwo od [ADR-0006](../adr/0006-cross-module-wylacznie-przez-serwisy.md) — do decyzji właściciela (przeniesienie haszowania do `core/` lub port). Nie dodawaj re-eksportów do tego `__init__.py`.

## 5. Stan vs cel

| Element | Stan | Cel | Krok |
|---|---|---|---|
| Struktura, wiring, błędy z `code`, `get_current_user` w `security/dependencies.py`, testy `unit/` + `integration/` | zgodne ze wzorcem | — | R-06 (domknięty) |
| Rate limiting logowania | brak (`slowapi` nie jest w `requirements.txt`) | patrz ADR-0012 | poza planem, po decyzji |
| Rotacja/unieważnianie refresh tokenów (waterworks: tabela `refresh_tokens`, wykrywanie reuse) | brak — tokeny bezstanowe | patrz ADR-0012 | poza planem, po decyzji |
| Wersja `python-jose` | `>=3.4.0` w `requirements.txt` (plik zmieniony w drzewie roboczym, niezacommitowany) | utrzymać | — |
