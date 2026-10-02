---
id: adr-0007-reference-data-deletion
status: Proposed
type: decision
scope: business/reference-data
last_reviewed: 2026-10-02
---

# Dane referencyjne należą do właściciela instancji, a usuwanie chroni historię: Walor z historią się archiwizuje, paczkę importu cofa się z blokadą edytowanych, Portfel z przelewami blokuje usunięcie

Rekomendacja: Walory, ceny ręczne, tagi i benchmarki są **globalne w instancji**, zapisywać je może tylko **właściciel instancji**, a rejestracja jest zamknięta. Usuwanie ma trzy reguły: archiwizacja Waloru z historią, cofnięcie Paczki importu bez nadpisywania edycji użytkownika oraz blokada usunięcia Portfela powiązanego przelewami.

**Rozstrzyga decyzje roadmapy:** D14 i D15. **Blokuje:** E1.5 (ceny ręczne, Walory użytkownika), E2.3 (przelewy), E4.1 (cofnięcie paczki); E0.6 (zamknięcie rejestracji) jest konfiguracją i go nie wymaga.

## Kontekst

- Dane referencyjne są globalne i bez właściciela: `assets_asset`, `assets_currency`, `assets_assetclass` nie mają `owner_id`; endpointy zapisu `assets/*` nie sprawdzają właściciela, a rejestracja `POST /auth/register` jest otwarta — **każdy zarejestrowany użytkownik edytuje Walory, kursy i ceny** ([dowód 06](../../research/06_stan_found-tracker_vs_cel.md), §2, G20). `User` ma tylko `id`, `email`, `password_hash`, `is_active` (G21).
- Założenie właściciela: jeden użytkownik, self-hosted ([plan](../../plans/02_roadmapa_funkcjonalna.md), §1).
- Usuwanie dziś: Walor w użyciu → 409 ze starym kodem (`backend/app/modules/assets/exceptions.py:89`); Portfel usuwa kaskadowo Operacje i Pozycje w ORM (`portfolio.py:60-65`), bez ochrony przed powiązaniami; brak soft-delete — ADR-0011 świadomie odłożył audyt ([ADR-0011](../../technical/adr/0011-audyt-odlozony.md)).
- Nowe zależności: ceny historyczne i ręczne (E1.1, E1.5), przelewy jako jeden wiersz z `counter_portfolio_id` (E2.3), Paczki importu z poprawkami użytkownika (E4.1).

## Decyzja

**A. Własność danych referencyjnych (D14)**
1. Walory, Klasy waloru, Waluty, kursy, ceny (w tym `source = manual`), tagi i benchmarki są **jedną wspólną przestrzenią instancji**. Odczyt: każdy uwierzytelniony użytkownik. Zapis: wyłącznie **właściciel instancji**.
2. Właściciel instancji to użytkownik z flagą `is_owner` (`Boolean`, NOT NULL, domyślnie `false`) **[propozycja]**, ustawianą dla pierwszego konta ścieżką E0.6 (CLI/pierwsze konto). Brak flagi → `403` `REFERENCE_DATA_OWNER_ONLY`.
3. Rejestracja zamknięta konfiguracją (E0.6). Dane **użytkownika** (Portfele, Operacje, Grupy) zostają per `owner_id`. Warunek ponownej oceny: drugi użytkownik z dostępem do danych (jak w ADR-0011).

**B. Semantyka usuwania (D15)**

| Obiekt | Zasada | Kod błędu / skutek |
|---|---|---|
| Walor bez Operacji, Pozycji i cen | usuwany fizycznie | — |
| Walor z historią (Operacje, Pozycje lub ceny) | **archiwizacja**: `archived_at` `DateTime(tz)`, nullable; znika z wyszukiwarki i formularzy nowych Operacji, zostaje w historii i wycenie istniejących Pozycji; ceny przestają być odświeżane; odwracalna | DELETE → `409 ASSET_HAS_HISTORY` z podpowiedzią archiwizacji (zastępuje dzisiejszy kod sprzed zmiany) |
| Paczka importu | **cofnięcie** usuwa jej Operacje i przebudowuje Portfel jedną transakcją; Operacje z `edited_at` ≠ NULL **blokują** cofnięcie i są wymienione na liście; wynik przebudowy niespójny (np. brak ilości do sprzedaży) → cofnięcie odrzucone w całości | `409 IMPORT_BATCH_HAS_EDITS`, `409 IMPORT_BATCH_REVERT_INVALID` |
| Portfel z przelewami | **blokada** usunięcia, dopóki istnieją wiersze przelewu, w których jest źródłem (`portfolio_id`) lub celem (`counter_portfolio_id`) | `409 PORTFOLIO_HAS_TRANSFERS` z listą Portfeli |
| Portfel bez przelewów | jak dziś: usunięcie kaskadowe Operacji i Pozycji (po potwierdzeniu w UI) | — |
| Usunięcie Operacji przelewu | przelew to jeden wiersz: usunięcie go przebudowuje Portfel źródłowy i docelowy w jednej transakcji z walidacją (E2.3, [ADR 0020](../../technical/adr/0020-plaski-model-operacji.md)) **[propozycja]** | `400` błąd walidacji przebudowy, wycofanie |

Archiwizacja dotyczy **tylko Waloru** — nie wprowadza audytu ani soft-delete Operacji (ADR-0011 pozostaje w mocy).

## Rozpatrywane alternatywy

| Opcja | Koszt / ryzyko | Werdykt |
|---|---|---|
| A1. Dane referencyjne per użytkownik (`owner_id`) | duplikaty Walorów i cen, unikalność tickera per właściciel, rozmnożenie zapytań; zysk tylko przy wielu użytkownikach, których nie planujemy | odrzucona |
| A2. Status quo (każdy zapisuje) | przy otwartej rejestracji obcy użytkownik zmienia ceny i kursy właściciela | odrzucona |
| A3. Globalne + zapis tylko właściciel (rekomendacja) | nowa kolumna i guard; drugi użytkownik w przyszłości będzie czytał cudze ceny ręczne | wybrana |
| B1. Twarde usuwanie z kaskadą (dziś dla Portfela) | utrata historii cen i Operacji; niemożliwe cofnięcie; cicho psuje Pozycje w innych Portfelach | odrzucona dla Waloru i przelewów |
| B2. Soft-delete wszystkiego | sprzeczne z ADR-0011 i zwiększa złożoność każdego zapytania | odrzucona |
| B3. Kaskadowe przeliczenie Portfela z przelewami | usunięcie A zmienia saldo i partie B; przebudowa B może się nie powieść (brak ilości) | odrzucona na rzecz blokady; do przemyślenia po E2.3 |
| B4. Cofnięcie paczki zawsze kasuje wszystko | gubi ręczne poprawki użytkownika | odrzucona |

## Konsekwencje

**Pozytywne**
- Historia i wyceny nie znikają przy sprzątaniu Walorów; cofnięcie importu jest bezpieczne i przewidywalne.
- Zamknięty obieg zapisu na danych współdzielonych bez przebudowy modelu.

**Negatywne**
- Archiwizowany Walor zostaje w bazie na zawsze; lista wymaga filtra „pokaż zarchiwizowane”.
- Użytkownik z edytowaną Operacją z paczki nie cofnie paczki jednym kliknięciem — musi najpierw ją usunąć lub przywrócić (wymaga `edited_at`, nowej kolumny pochodnej od edycji).
- Blokada usunięcia Portfela wymusza ręczne rozwiązanie przelewów przed usunięciem.
- Zmiana dzisiejszego kodu błędu usuwania Waloru na `ASSET_HAS_HISTORY` wymaga aktualizacji testów (`test_asset_service.py:227`) i mapowania w UI.

## Zmiany słownika po akceptacji

| Pojęcie | Wpis w `CONTEXT.md` |
|---|---|
| **Właściciel instancji** | Użytkownik z prawem zapisu danych referencyjnych (Walory, kursy, ceny, tagi, benchmarki). _Unikać_: admin, superużytkownik |
| **Archiwizacja Waloru** | Ukrycie Waloru z historią przed nowymi Operacjami, bez usuwania danych. _Unikać_: usunięcie, dezaktywacja (dla Waloru) |
| **Paczka importu** | Zbiór Operacji zatwierdzonych z jednego pliku; cofalna jako całość, o ile nieedytowana. _Unikać_: batch (w UI), import (jako rzecz) |
| **Przelew** | Jedna Operacja (jeden wiersz) między dwoma Portfelami: `amount` = noga wychodząca, `counter_*` = przychodząca; blokuje usunięcie Portfela. _Unikać_: transfer (w UI), wymiana |

## Otwarte

- Czy cofnięcie paczki ma oferować tryb „cofnij tylko nieedytowane” obok blokady (dziś: blokada z listą).
- Co przy usunięciu Portfela: eksport jego Operacji przed kasowaniem (E4.5) — propozycja ostrzeżenia w UI.
- Migracja istniejącego konta na `is_owner = true` — jednorazowa komenda; wymaga zgody właściciela na wskazanie konta.
