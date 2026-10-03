---
id: adr-0001-portfolio-is-account
status: Accepted
type: decision
scope: business/portfolio-model
last_reviewed: 2026-10-03
---

# Portfel jest jednym rachunkiem maklerskim; agregację dają Grupy portfeli

Portfel = jeden rachunek maklerski. Sumowanie rachunków w jeden widok robi byt **Grupa portfeli**, bez własnych Operacji.

**Blokuje:** E2.1, E2.4, pośrednio E2.2, E2.3, E3.1.

## Kontekst

- Ten sam ISIN u dwóch brokerów to dwie osobne kolejki partii; tak wygląda wyciąg każdego brokera.
- Dziś Portfel to „worek” bez typu i brokera (`backend/app/modules/portfolios/models/portfolio.py:26-67`); Pozycja jest unikalna na `(portfolio_id, asset_id)`.

## Decyzja

1. Portfel dostaje pola informacyjne (nazwy **[propozycja]**): `account_type` `String(10)`, domyślnie `regular`; `broker` `String(60)`, nullable. To etykiety — nie wpływają na obliczenia i można je zmieniać w każdej chwili.
2. Klucz partii FIFO, Pozycji i kolejki sprzedaży to **(Portfel, Walor)** ([ADR 0002](0002-koszt-nabycia-partie-fifo.md)).
3. Zmiana etykiet `account_type` / `broker` jest dowolna, bez blokady i bez przeliczania historii.
4. **Grupa portfeli**: nazwa unikalna per właściciel, członkostwo wiele-do-wielu, własna Waluta bazowa (przeliczenie wg kursów wyceny), bez Operacji i salda. Metryki: [ADR 0004](0004-metodologia-stop-zwrotu.md).
5. Rachunek z wieloma walutami to jeden Portfel z gotówką wielowalutową ([ADR 0003](0003-gotowka-wielowalutowa.md)).
6. Podział „wewnątrz rachunku” (strategie, cele) robi się osobnym Portfelem i Grupą, nie dodatkową strukturą.

## Alternatywy

- Rachunek jako byt wewnątrz Portfela — `account_id` w Operacji, partii i Pozycji, dodatkowy poziom w UI; Grupa i tak potrzebna.

## Konsekwencje

- (+) Model danych pokrywa się z wyciągiem brokera; najmniejsza zmiana kodu i UI.
- (−) Brak wspólnej kolejki FIFO dla Grupy; kilka rachunków trzeba prowadzić jako osobne Portfele.
- Słownik: Portfel = rachunek; Typ rachunku, Broker, Grupa portfeli — wpisy w `CONTEXT.md`.
