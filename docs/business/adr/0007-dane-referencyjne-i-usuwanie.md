---
id: adr-0007-reference-data-deletion
status: Accepted
type: decision
scope: business/reference-data
last_reviewed: 2026-10-03
---

# Dane referencyjne należą do właściciela instancji, a Walor z historią się archiwizuje

Walory, ceny ręczne i benchmarki są globalne w instancji; zapisuje je tylko właściciel, rejestracja jest zamknięta. Walor z historią archiwizujemy zamiast usuwać.

**Blokuje:** E1.5, E2.3, E4.1 (E0.6 to konfiguracja, nie jest blokowane).

## Kontekst

- `assets_asset`, `assets_currency`, `assets_assetclass` nie mają `owner_id`; zapis `assets/*` nie sprawdza właściciela, `POST /auth/register` jest otwarty ([dowód 06](../../research/00_analiza_koncowa.md), §2, G20, G21). Założenie: jeden użytkownik ([plan](../../research/00_analiza_koncowa.md), §1).
- Usuwanie dziś: Walor w użyciu → 409 (`backend/app/modules/assets/exceptions.py:89`); Portfel kasuje kaskadowo Operacje i Pozycje (`portfolio.py:60-65`); brak soft-delete — [ADR-0011](../../technical/adr/0011-audyt-odlozony.md) odłożył audyt.

## Decyzja

**A. Własność danych referencyjnych**
1. Walory, Klasy waloru, Waluty, kursy, ceny (też `source = manual`) i benchmarki to wspólna przestrzeń instancji. Odczyt: każdy uwierzytelniony. Zapis: wyłącznie właściciel instancji.
2. Właściciel = użytkownik z `is_owner` (`Boolean`, NOT NULL, domyślnie `false`) **[propozycja]**, ustawianą dla pierwszego konta (E0.6). Brak flagi → `403` `REFERENCE_DATA_OWNER_ONLY`.
3. Rejestracja zamknięta konfiguracją (E0.6). Dane użytkownika (Portfele, Operacje, Grupy) zostają per `owner_id`.

**B. Usuwanie**

| Obiekt | Zasada | Błąd |
|---|---|---|
| Walor bez Operacji, Pozycji i cen | usunięcie fizyczne | — |
| Walor z historią | archiwizacja: `archived_at` `DateTime(tz)` nullable; znika z wyszukiwarki i formularzy nowych Operacji, zostaje w historii i wycenie; ceny przestają się odświeżać; odwracalna | DELETE → `409 ASSET_HAS_HISTORY` (zastępuje obecny kod) |
| Portfel | kaskada Operacji i Pozycji po potwierdzeniu w UI | — |

Archiwizacja dotyczy tylko Waloru; nie wprowadza audytu ani soft-delete Operacji. Cofanie paczek importu: [ADR tech. 0018](../../technical/adr/0018-architektura-importu.md).

## Alternatywy

- Dane referencyjne per `owner_id` — duplikaty Walorów i cen; zysk tylko przy wielu użytkownikach.
- Status quo — przy otwartej rejestracji obcy zmienia ceny i kursy.
- Twarde usuwanie Waloru z kaskadą — utrata historii, ciche psucie Pozycji.
- Soft-delete wszystkiego — sprzeczne z ADR-0011, komplikuje zapytania.

## Konsekwencje

- (+) Historia i wyceny przeżywają sprzątanie Walorów; zapis danych współdzielonych zamknięty bez przebudowy modelu.
- (−) Zarchiwizowany Walor zostaje w bazie (filtr „pokaż zarchiwizowane”). Zmiana kodu błędu wymaga aktualizacji `test_asset_service.py:227` i UI.

## Słownik (`CONTEXT.md`)

**Właściciel instancji** — zapis danych referencyjnych (_unikać_: admin). **Archiwizacja Waloru** — ukrycie przed nowymi Operacjami bez usuwania (_unikać_: usunięcie, dezaktywacja).

## Otwarte

- Przypisanie `is_owner = true` istniejącemu kontu — jednorazowa komenda, wymaga zgody właściciela.
