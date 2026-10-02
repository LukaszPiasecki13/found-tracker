---
id: adr-0001-portfolio-is-account
status: Proposed
type: decision
scope: business/portfolio-model
last_reviewed: 2026-10-02
---

# Portfel jest jednym rachunkiem maklerskim; agregację dają Grupy portfeli

Rekomendacja: **Portfel = jeden rachunek maklerski** (typ rachunku, broker), a sumowanie kilku rachunków w jeden widok robi nowy byt **Grupa portfeli** bez własnych Operacji. Alternatywa (Rachunek jako byt wewnątrz Portfela, model myfund) jest bogatsza, ale kosztuje więcej w każdym miejscu, które dotyka rachunku.

**Rozstrzyga decyzję roadmapy:** D1 ([plan](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E2.1 (model Portfela), E2.4 (klucz partii), E6 (pule podatkowe, wyłączenie IKE/IKZE), pośrednio E2.2, E2.3, E3.1 (zakres Grupy), E4 (mapowanie plików na Portfele).

## Kontekst

- Prawo liczy FIFO i zwolnienia **odrębnie dla każdego rachunku** (art. 24 ust. 10; art. 30b ust. 7; art. 21 ust. 1 pkt 58a i 58b — [dowód 04](../../research/04_rynek_pl_podatki_i_brokerzy.md), §1.2, §2). Ten sam ISIN w XTB i mBanku to dwie niezależne kolejki.
- Dziś Portfel to „worek” bez typu i brokera: `portfolios_portfolio` ma `owner_id`, `name`, `base_currency_id`, `cash_balance`, `total_deposited`, `is_active`, unikalność `(owner_id, name)` (`backend/app/modules/portfolios/models/portfolio.py:26-67`). Pozycja jest unikalna na `(portfolio_id, asset_id)`, więc dziś de facto klucz „rachunek+walor” już istnieje, jeśli Portfel = rachunek.
- [`CONTEXT.md`](../CONTEXT.md) wymienia „konto” i „rachunek” na liście _Unikać_ dla Portfela. Dowód 04 (wiersz 1) rekomenduje osobny byt Rachunek; roadmapa wybrała prostszy wariant i prosi właściciela o rozstrzygnięcie.
- Dowód nie wie, ilu rachunków brokerskich właściciel skleił dziś w jednym Portfelu **[niezweryfikowane]** — to wyznacza koszt migracji.

## Decyzja

1. Portfel dostaje pola (nazwy **[propozycja]**, schemat szczegółowy w dokumencie schematu): `account_type` `String(10)`, wartości `regular` / `ike` / `ikze` / `ppk` / `ppe` / `oipe`, domyślnie `regular`; `broker` `String(60)`, nullable. Istniejące Portfele migrują jako `regular`, `broker = NULL`.
2. Klucz partii FIFO, Pozycji i kolejki sprzedaży to **(Portfel, Walor)** ([ADR 0002](0002-koszt-nabycia-partie-fifo.md)). Nie ma drugiego poziomu.
3. `account_type` ≠ `regular` wyłącza Operacje Portfela z pul PIT-38 ([ADR 0006](0006-zakres-modulu-podatkowego.md)). Zmiana `account_type` jest zablokowana, gdy Portfel ma Operacje (błąd `PORTFOLIO_ACCOUNT_TYPE_LOCKED`) — zmiana wstecz przepisałaby skutki podatkowe całej historii. Właściciel zakłada nowy Portfel i przenosi Operacje.
4. **Grupa portfeli** (nowa): nazwa unikalna per właściciel, członkostwo wiele-do-wielu (jeden Portfel może być w kilku Grupach, np. „Emerytalne” i „Wszystko”). Grupa nie ma Operacji ani salda — jest filtrem agregacji z własną Walutą bazową (przeliczenie wg kursów wyceny). Metryki Grupy: [ADR 0004](0004-metodologia-stop-zwrotu.md).
5. Jeden rachunek brokera z wieloma walutami to **jeden** Portfel z gotówką wielowalutową ([ADR 0003](0003-gotowka-wielowalutowa.md)), nie kilka Portfeli.
6. Widoki „wewnątrz rachunku” (strategie, cele) nie są obsługiwane strukturą; do tego służą tagi (D14) i filtry.

## Rozpatrywane alternatywy

| | A. Portfel = rachunek (rekomendacja) | B. Rachunek wewnątrz Portfela (myfund, dowód 04) |
|---|---|---|
| FIFO art. 24 ust. 10 | klucz `(Portfel, Walor)`; zero nowych kolumn w partii | klucz `(Rachunek, Walor)`; `account_id` w Operacji, partii i Pozycji; unikalność Pozycji zmienia się na `(account_id, asset_id)` |
| IKE/IKZE | typ na Portfelu; wyłączenie z puli jednym warunkiem | typ na Rachunku; Portfel może mieszać rachunki z ulgą i bez — raporty muszą filtrować per rachunek |
| UI | Portfele na liście, Grupa jako widok łączony; brak kroku „wybierz rachunek” | dodatkowy poziom w każdym formularzu i tabeli (Portfel → Rachunek → Pozycja) |
| Import | plik brokera → jeden Portfel; mapowanie 1:1 (Bossa: osobne pliki IKE/IKZE = osobne Portfele) | plik → Rachunek, ale Portfel i Rachunek wybierane osobno; więcej błędów mapowania |
| Przelewy (E2.3) | między Portfelami: jeden wiersz Operacji z `counter_portfolio_id` (D9) | między Rachunkami: ruch wewnątrz Portfela jest przelewem bez Portfela-kontrahenta — dwa rodzaje przelewów |
| Agregacja | tylko przez Grupę | Portfel agreguje „za darmo”, Grupa i tak potrzebna dla wielu Portfeli |
| Zmiana kodu | mała: nowe kolumny, nowa tabela Grup | duża: nowa tabela Rachunków, klucz obcy w 4 tabelach, przebudowa `PortfolioLedger` |

Odrzucenie B nie jest bezkosztowe: traci się „jeden Portfel = cały majątek z podziałem na rachunki”; to zastępuje Grupa, ale **bez** salda i kolejki FIFO wspólnej dla Grupy (i prawnie nie powinno jej być).

## Konsekwencje

**Pozytywne**
- Model prawny (rachunek) pokrywa się z modelem danych; test FIFO „ten sam ISIN w dwóch Portfelach” jest trywialny.
- Najmniejsza zmiana kodu i UI; zachowuje obecne adresowanie Portfela.

**Negatywne**
- Użytkownik, który trzymał kilka rachunków w jednym Portfelu, musi go rozdzielić ręcznie przed E2.4 (nie ma automatycznego podziału; skutek dla historii i partii).
- Brak jednego „Portfela z rachunkami” wymaga Grup i jest widoczny w nawigacji (E3.4).
- Rachunki o podwójnej naturze (np. rachunek maklerski z kontem gotówkowym) mają jedną gotówkę per waluta; osobne konto bankowe to osobny Portfel, jeśli ma być śledzone.

## Zmiany słownika po akceptacji

| Pojęcie | Wpis w `CONTEXT.md` |
|---|---|
| **Portfel** (zmiana definicji) | „Jeden rachunek maklerski użytkownika: nazwa, typ rachunku, broker, waluta bazowa, gotówka.” Zdanie o „worku” usunąć. _Unikać_: Pocket (poza legacy), konto (zarezerwowane dla Użytkownika), wallet; **„rachunek” jako osobny byt** — Rachunek nie istnieje, to właśnie Portfel |
| **Typ rachunku** (`account_type`) | `regular`, `ike`, `ikze`, `ppk`, `ppe`, `oipe`; decyduje o udziale w pulach podatkowych. _Unikać_: tax_wrapper, rodzaj konta |
| **Broker** | Tekstowa etykieta rachunku; bez słownika. _Unikać_: dom maklerski w kodzie |
| **Grupa portfeli** | Zbiór Portfeli do wspólnych metryk; bez własnych Operacji. _Unikać_: folder, katalog, portfel zbiorczy |

## Otwarte

- Czy zmiana `account_type` ma mieć wyjątek „Portfel pusty po usunięciu Operacji” (dziś: blokada gdy są jakiekolwiek Operacje).
- Lista Portfeli właściciela do zmapowania na rachunki — blokada migracji E2.1 (dane od właściciela).
