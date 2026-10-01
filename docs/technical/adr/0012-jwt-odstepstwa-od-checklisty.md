---
id: adr-0012-jwt-deviations
status: Proposed
last_reviewed: 2026-09-30
type: decision
scope: backend/security/jwt
---

# JWT: HS256, tokeny w `localStorage`, stateless refresh — odstępstwa od security-checklist

Reguła [security-checklist](../../../.claude/rules/ai-tools/security-checklist.md) dopuszcza odstępstwa wyłącznie przez ADR. Ten dokument zapisuje obecny stan uwierzytelniania i to, co świadomie odbiega od checklisty. Stan opisuje kod (`security/services/token.py`, `frontend/src/contexts/AuthContext.tsx`); decyzja o zaakceptowaniu należy do człowieka.

## Kontekst

Aplikacja jest osobista i jednoużytkownikowa, bez danych innych osób. Stan faktyczny:
- algorytm `HS256` z jednym `secret_key`; `iss`/`aud` walidowane;
- access token 30 min, refresh token 1 dzień, oba bezstanowe (brak rotacji, brak listy unieważnionych);
- tokeny w `localStorage` przeglądarki;
- brak rate limitingu na `/auth/login`;
- logowanie nieistniejącego konta kosztuje tyle samo co błędne hasło (`burn_password_verification`), a błąd jest jeden (`INVALID_CREDENTIALS`) — brak enumeracji kont;
- biblioteka `python-jose[cryptography]>=3.4.0` (zgodna z progiem CVE).

## Decyzja

Zaakceptowane odstępstwa (do zatwierdzenia przez właściciela):

| Wymóg checklisty | Stan | Uzasadnienie | Warunek ponownej oceny |
|---|---|---|---|
| `RS256` | `HS256` | jeden proces, jeden wystawca i weryfikator; brak kluczy publicznych do dystrybucji | rozdzielenie wystawcy i weryfikatora |
| Access 15–30 min | 30 min | zgodne (górna granica) | — |
| Refresh 7–30 dni, rotacja | 1 dzień, bez rotacji | krótszy niż minimum checklisty; rotacja wymaga stanu w bazie | dostęp z zewnątrz sieci domowej |
| Refresh w `httpOnly` cookie | `localStorage` | istniejąca architektura frontendu; wymagałaby CSRF i zmiany klienta | wdrożenie publiczne |
| Rate limiting logowania | brak | brak w `requirements.txt` | publiczny adres API |

Niezmienione wymagania: `python-jose >= 3.4.0`; sekrety wyłącznie w `.env`.

## Rozpatrywane alternatywy

- **Spełnić checklistę od razu (RS256, cookie, rotacja, rate limit).** Duży zakres zmian w backendzie i frontendzie, niewspółmierny do profilu ryzyka aplikacji osobistej. Odrzucone teraz, nie na zawsze.
- **`PyJWT` zamiast `python-jose`.** Checklista preferuje PyJWT dla nowego kodu; migracja biblioteki to osobne zadanie. Odłożone.

## Konsekwencje

**Pozytywne**
- Udokumentowane odstępstwa przestają być „findingiem” przy review.

**Negatywne**
- Kradzież tokenu przez XSS daje pełny dostęp do danych na czas ważności refresh tokenu.
- Wdrożenie aplikacji poza sieć zaufaną wymaga przeglądu tej tabeli przed uruchomieniem.
