---
id: adr-0002-cost-basis-lots-fifo
status: Proposed
type: decision
scope: business/cost-basis
last_reviewed: 2026-10-03
---

# Koszt nabycia liczymy z partii zakupu metodą FIFO

**Partia** powstaje przy zakupie; jest daną pochodną Operacji, odtwarzalną przez `rebuild`. Sprzedaż zawsze zużywa partie FIFO w obrębie Portfela ([ADR 0001](0001-portfel-jest-rachunkiem.md)). `average_buy_price` zostaje wyłącznie informacją.

**Rozstrzyga:** D2. **Blokuje:** E2.4, E3.2, E8.1–E8.3.

## Kontekst

- Dziś sprzedaż nie zmienia średniej ceny, zysk zrealizowany nie istnieje (`backend/app/modules/portfolios/domain/ledger.py:204-225`); koszt wyceny = `ilość × average_buy_price` (`domain/valuation.py:53`).
- Zysk zrealizowany wymaga kosztu konkretnych sprzedanych sztuk.

## Decyzja

1. **Partia** = `(Portfel, Walor, Operacja otwierająca)`: ilość otwarta i pozostała, koszt jednostkowy w walucie Waloru (cena + prowizja zakupu), kurs brokera `fx_rate` zamrożony w dniu zakupu. Tabele pochodne `portfolios_lot`, `portfolios_lot_consumption`; partia tylko przebudowywana. `open_operation_id` = zakup otwierający Partię.
2. **FIFO** w obrębie `(Portfel, Walor)`. Prowizja sprzedaży rozkładana proporcjonalnie na zużywane wycinki.
3. **Bez wskazywania partii**: sprzedaż zawsze zużywa najstarsze partie.
4. **Split** nie tworzy Operacji otwierającej: zmienia `split_ratio`, ilość i cenę jednostkową przy stałym koszcie łącznym i dacie.
5. **Wycena**: koszt = Σ koszt pozostały partii; niezrealizowany P/L = wartość rynkowa − koszt. `average_buy_price` — średnia ruchoma, w UI „informacyjnie”, nie zasila P/L.
6. **Zysk zrealizowany** per wycinek zużycia, w walucie Waloru i walucie Portfela (po kursie brokera z zakupu i sprzedaży).
7. **Test złoty** ([dowód 05](../../research/05_metodyka_metryk.md), §6): FIFO 336,50 + 47,50 = 384,00; średnia 286,50 + 97,50 = 384,00 — zysk całkowity niezależny od metody.

## Alternatywy

- Tylko średnia ważona — brak zysku zrealizowanego.
- Metoda do wyboru per Portfel (LIFO/HIFO) — komplikacja bez potrzeby.
- Partie jako dane źródłowe — łamie zasadę „Operacje są źródłem prawdy”.
- Średnia do wyceny, FIFO do zysku — dwa różne „zyski niezrealizowane”.

## Konsekwencje

- (+) Zysk zrealizowany i raport zamkniętych pozycji z jednego rejestru.
- (−) Niezrealizowany P/L po częściowej sprzedaży zmienia wartość względem dziś (zmiana oczekiwań w `test_valuation.py`).
- (−) Edycja Operacji wstecz przelicza FIFO od jej daty.
