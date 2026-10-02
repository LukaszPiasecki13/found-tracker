---
id: adr-0007-reference-data-deletion
status: Proposed
type: decision
scope: business/reference-data
last_reviewed: 2026-10-02
---

# Dane referencyjne należą do właściciela instancji, a usuwanie chroni historię: Walor z historią się archiwizuje, paczkę importu cofa się z blokadą edytowanych, Portfel z przelewami blokuje usunięcie

Walory, ceny ręczne, tagi i benchmarki są globalne w instancji; zapisuje je tylko właściciel instancji, rejestracja jest zamknięta. Usuwanie: archiwizacja Waloru z historią, cofnięcie Paczki importu bez nadpisywania edycji, blokada usunięcia Portfela z przelewami.

**Rozstrzyga:** D14, D15. **Blokuje:** E1.5, E2.3, E4.1 (E0.6 to konfiguracja, nie jest blokowane).

## Kontekst

- `assets_asset`, `assets_currency`, `assets_assetclass` nie mają `owner_id`; zapis `assets/*` nie sprawdza właściciela, `POST /auth/register` jest otwarty — każdy użytkownik edytuje Walory, kursy i ceny ([dowód 06](../../research/06_stan_found-tracker_vs_cel.md), §2, G20, G21). Założenie: jeden użytkownik, self-hosted ([plan](../../plans/02_roadmapa_funkcjonalna.md), §1).
- Usuwanie dziś: Walor w użyciu → 409 (`backend/app/modules/assets/exceptions.py:89`); Portfel kasuje kaskadowo Operacje i Pozycje (`portfolio.py:60-65`); brak soft-delete — [ADR-0011](../../technical/adr/0011-audyt-odlozony.md) odłożył audyt.
- Nowe zależności: ceny ręczne (E1.1, E1.5), przelewy jako jeden wiersz z `counter_portfolio_id` (E2.3), Paczki importu z poprawkami (E4.1).

## Decyzja

**A. Własność danych referencyjnych (D14)**
1. Walory, Klasy waloru, Waluty, kursy, ceny (też `source = manual`), tagi i benchmarki to wspólna przestrzeń instancji. Odczyt: każdy uwierzytelniony. Zapis: wyłącznie właściciel instancji.
2. Właściciel = użytkownik z `is_owner` (`Boolean`, NOT NULL, domyślnie `false`) **[propozycja]**, ustawianą dla pierwszego konta (E0.6). Brak flagi → `403` `REFERENCE_DATA_OWNER_ONLY`.
3. Rejestracja zamknięta konfiguracją (E0.6). Dane użytkownika (Portfele, Operacje, Grupy) zostają per `owner_id`. Ponowna ocena: drugi użytkownik z dostępem do danych (jak w ADR-0011).

**B. Usuwanie (D15)**

| Obiekt | Zasada | Błąd |
|---|---|---|
| Walor bez Operacji, Pozycji i cen | usunięcie fizyczne | — |
| Walor z historią | archiwizacja: `archived_at` `DateTime(tz)` nullable; znika z wyszukiwarki i formularzy nowych Operacji, zostaje w historii i wycenie; ceny przestają się odświeżać; odwracalna | DELETE → `409 ASSET_HAS_HISTORY` (zastępuje obecny kod) |
| Paczka importu | cofnięcie usuwa jej Operacje i przebudowuje Portfel jedną transakcją; Operacje z `edited_at` ≠ NULL blokują cofnięcie (lista); niespójna przebudowa → odrzucenie w całości | `409 IMPORT_BATCH_HAS_EDITS`, `409 IMPORT_BATCH_REVERT_INVALID` |
| Portfel z przelewami | blokada, dopóki istnieją przelewy z nim jako źródłem (`portfolio_id`) lub celem (`counter_portfolio_id`) | `409 PORTFOLIO_HAS_TRANSFERS` z listą Portfeli |
| Portfel bez przelewów | kaskada Operacji i Pozycji po potwierdzeniu w UI | — |
| Operacja przelewu | usunięcie przebudowuje Portfel źródłowy i docelowy w jednej transakcji z walidacją (E2.3, [ADR 0020](../../technical/adr/0020-plaski-model-operacji.md)) **[propozycja]** | `400`, wycofanie |

Archiwizacja dotyczy tylko Waloru; nie wprowadza audytu ani soft-delete Operacji.

## Alternatywy

- Dane referencyjne per `owner_id` — duplikaty Walorów i cen; zysk tylko przy wielu użytkownikach.
- Status quo — przy otwartej rejestracji obcy zmienia ceny i kursy.
- Twarde usuwanie z kaskadą — utrata historii, ciche psucie Pozycji w innych Portfelach; odrzucone dla Waloru i przelewów.
- Soft-delete wszystkiego — sprzeczne z ADR-0011, komplikuje zapytania.
- Kaskadowe przeliczenie Portfela z przelewami — przebudowa drugiego Portfela może się nie powieść; blokada wybrana, do przemyślenia po E2.3.
- Cofnięcie paczki zawsze kasujące wszystko — gubi poprawki użytkownika.

## Konsekwencje

- (+) Historia i wyceny przeżywają sprzątanie Walorów; cofnięcie importu jest przewidywalne; zapis danych współdzielonych zamknięty bez przebudowy modelu.
- (−) Zarchiwizowany Walor zostaje w bazie (filtr „pokaż zarchiwizowane”). Edytowanej paczki nie cofnie się jednym kliknięciem (wymaga `edited_at`). Blokada Portfela wymusza ręczne rozwiązanie przelewów. Zmiana kodu błędu wymaga aktualizacji `test_asset_service.py:227` i UI.

## Słownik (`CONTEXT.md` po akceptacji)

**Właściciel instancji** — zapis danych referencyjnych (_unikać_: admin). **Archiwizacja Waloru** — ukrycie przed nowymi Operacjami bez usuwania (_unikać_: usunięcie, dezaktywacja). **Paczka importu** — Operacje z jednego pliku, cofalne jako całość, o ile nieedytowane (_unikać_: batch w UI). **Przelew** — jedna Operacja między dwoma Portfelami (`amount` = noga wychodząca, `counter_*` = przychodząca); blokuje usunięcie Portfela (_unikać_: transfer w UI).

## Otwarte

- Cofnięcie paczki: tryb „cofnij tylko nieedytowane” obok blokady?
- Usunięcie Portfela: ostrzeżenie z eksportem Operacji (E4.5)?
- Migracja istniejącego konta na `is_owner = true` — jednorazowa komenda, wymaga zgody właściciela.
