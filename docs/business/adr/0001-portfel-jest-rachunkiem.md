---
id: adr-0001-portfolio-is-account
status: Proposed
type: decision
scope: business/portfolio-model
last_reviewed: 2026-10-02
---

# Portfel jest jednym rachunkiem maklerskim; agregację dają Grupy portfeli

Portfel = jeden rachunek maklerski (typ rachunku, broker). Sumowanie rachunków w jeden widok robi nowy byt **Grupa portfeli**, bez własnych Operacji.

**Rozstrzyga:** D1 ([plan](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E2.1, E2.4, E6, pośrednio E2.2, E2.3, E3.1, E4.

## Kontekst

- Prawo liczy FIFO i zwolnienia odrębnie dla każdego rachunku (art. 24 ust. 10; art. 30b ust. 7; art. 21 ust. 1 pkt 58a i 58b — [dowód 04](../../research/04_rynek_pl_podatki_i_brokerzy.md), §1.2, §2). Ten sam ISIN w dwóch brokerach to dwie kolejki.
- Dziś Portfel to „worek” bez typu i brokera (`backend/app/modules/portfolios/models/portfolio.py:26-67`); Pozycja jest unikalna na `(portfolio_id, asset_id)`.
- Nie wiadomo, ilu rachunków właściciel skleił w jednym Portfelu **[niezweryfikowane]** — to wyznacza koszt migracji.

## Decyzja

1. Portfel dostaje pola (nazwy **[propozycja]**): `account_type` `String(10)` — `regular` / `ike` / `ikze` / `ppk` / `ppe` / `oipe`, domyślnie `regular`; `broker` `String(60)`, nullable. Istniejące Portfele: `regular`, `broker = NULL`.
2. Klucz partii FIFO, Pozycji i kolejki sprzedaży to **(Portfel, Walor)** ([ADR 0002](0002-koszt-nabycia-partie-fifo.md)).
3. `account_type` ≠ `regular` wyłącza Operacje Portfela z pul PIT-38 ([ADR 0006](0006-zakres-modulu-podatkowego.md)). Zmiana `account_type` przy istniejących Operacjach: błąd `PORTFOLIO_ACCOUNT_TYPE_LOCKED` (zmiana wsteczna przepisałaby skutki podatkowe historii).
4. **Grupa portfeli**: nazwa unikalna per właściciel, członkostwo wiele-do-wielu, własna Waluta bazowa (przeliczenie wg kursów wyceny), bez Operacji i salda. Metryki: [ADR 0004](0004-metodologia-stop-zwrotu.md).
5. Rachunek z wieloma walutami to jeden Portfel z gotówką wielowalutową ([ADR 0003](0003-gotowka-wielowalutowa.md)).
6. Podział „wewnątrz rachunku” (strategie, cele) przez tagi (D14) i filtry, nie strukturę.

## Alternatywy

- Rachunek jako byt wewnątrz Portfela (myfund, dowód 04) — `account_id` w Operacji, partii i Pozycji (4 tabele), dodatkowy poziom w UI, dwa rodzaje przelewów, przebudowa `PortfolioLedger`; Grupa i tak potrzebna.

## Konsekwencje

- (+) Model prawny pokrywa się z modelem danych; najmniejsza zmiana kodu i UI.
- (−) Kilka rachunków w jednym Portfelu trzeba rozdzielić ręcznie przed E2.4.
- (−) Nie ma „Portfela z rachunkami” ani wspólnej kolejki FIFO Grupy (prawnie niepożądanej).
- Słownik po akceptacji: Portfel = rachunek; „rachunek” nie jest osobnym bytem; Typ rachunku, Broker, Grupa portfeli — wpisy w `CONTEXT.md`.

## Otwarte

- Wyjątek od blokady `account_type` dla Portfela pustego po usunięciu Operacji.
- Lista Portfeli właściciela do zmapowania na rachunki (blokuje migrację E2.1).
