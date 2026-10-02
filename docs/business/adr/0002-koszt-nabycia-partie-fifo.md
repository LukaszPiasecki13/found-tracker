---
id: adr-0002-cost-basis-lots-fifo
status: Proposed
type: decision
scope: business/cost-basis
last_reviewed: 2026-10-02
---

# Koszt nabycia liczymy z partii zakupu (FIFO domyślnie, wskazanie partii gdy broker ją identyfikuje)

**Partia** (nowe pojęcie) powstaje przy zakupie i przelewie papierów; jest daną pochodną Operacji, odtwarzalną przez `rebuild`. Sprzedaż zużywa partie FIFO w obrębie Portfela ([ADR 0001](0001-portfel-jest-rachunkiem.md)), chyba że wskazano partie. `average_buy_price` zostaje wyłącznie informacją.

**Rozstrzyga:** D2 i część D3. **Blokuje:** E2.4, E3.2, E6.1, E6.2, E8.1–E8.3.

## Kontekst

- Dziś sprzedaż nie zmienia średniej ceny, zysk zrealizowany nie istnieje (`backend/app/modules/portfolios/domain/ledger.py:204-225`); koszt wyceny = `ilość × average_buy_price` (`domain/valuation.py:53`).
- Art. 24 ust. 10 ustawy o PIT ([dowód 04](../../research/04_rynek_pl_podatki_i_brokerzy.md), §1.2): FIFO obowiązuje, gdy **nie jest możliwe określenie ceny nabycia**, odrębnie dla każdego rachunku; analogicznie art. 30b ust. 7 i art. 30a ust. 4. Identyfikacja partii jest więc dozwolona. Krypto: ([ADR 0006](0006-zakres-modulu-podatkowego.md)).

## Decyzja

1. **Partia** = `(Portfel, Walor, Operacja otwierająca, Operacja pierwotna)`: ilość otwarta i pozostała, koszt jednostkowy w walucie Waloru (cena + prowizja zakupu), kurs brokera zamrożony w dniu zakupu, koszt w PLN po kursie podatkowym ([ADR 0005](0005-daty-operacji-i-zdarzenie-podatkowe.md)). Tabele pochodne `portfolios_lot`, `portfolios_lot_consumption`; partia tylko przebudowywana. `open_operation_id` = Operacja otwierająca Partię w tym Portfelu (zakup lub przelew przychodzący); `origin_operation_id` = pierwotny zakup, niezmienny przy przelewie i splicie.
2. **FIFO** w obrębie `(Portfel, Walor)`. Prowizja sprzedaży rozkładana proporcjonalnie na zużywane wycinki.
3. **Wskazanie partii** [propozycja]: tabela wejściowa `portfolios_operation_lot_pick(operation_id, open_operation_id, origin_operation_id, quantity Numeric(28,10))` — dane wejściowe, przeżywają `rebuild`; reszta FIFO. Tylko gdy źródło identyfikuje partię (np. IBKR `Trade ID`) lub ręcznie z potwierdzeniem. Nieistniejąca lub za mała partia: `LOT_SELECTION_INVALID`.
4. **Przelew papierów** przenosi partie z kosztem i datą nabycia. **Split** nie tworzy Operacji otwierającej: zmienia `split_ratio`, ilość i cenę jednostkową przy stałym koszcie łącznym i dacie. `taxes_lot_attribute` i wskazanie partii kluczowane po `origin_operation_id`.
5. **Wycena**: koszt = Σ koszt pozostały partii; niezrealizowany P/L = wartość rynkowa − koszt. `average_buy_price` — średnia ruchoma, w UI „informacyjnie”, nie zasila P/L.
6. **Zysk zrealizowany** per wycinek zużycia w walucie Waloru, walucie Portfela i PLN po kursie podatkowym.
7. **Test złoty** ([dowód 05](../../research/05_metodyka_metryk.md), §6): FIFO 336,50 + 47,50 = 384,00; średnia 286,50 + 97,50 = 384,00 — zysk całkowity niezależny od metody.

## Alternatywy

- Tylko średnia ważona — brak zysku zrealizowanego i PIT-38.
- Samo FIFO — błędny podatek, gdy broker identyfikuje partię.
- Metoda per Portfel (LIFO/HIFO) — prawo zna FIFO albo identyfikację.
- Partie jako dane źródłowe — łamie P3.
- Średnia do wyceny, FIFO do podatków — dwa różne „zyski niezrealizowane”.

## Konsekwencje

- (+) Zysk zrealizowany, raport zamkniętych pozycji i PIT-38 z jednego rejestru.
- (−) Niezrealizowany P/L po częściowej sprzedaży zmienia wartość względem dziś (zmiana oczekiwań w `test_valuation.py`).
- (−) Edycja Operacji wstecz przelicza FIFO od jej daty; wskazanie partii wymaga walidacji przy `rebuild`.

## Otwarte

- Próbki plików IBKR/XTB identyfikujących partie (blokuje E4.3, nie ten ADR).
