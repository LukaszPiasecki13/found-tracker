---
id: adr-0002-cost-basis-lots-fifo
status: Proposed
type: decision
scope: business/cost-basis
last_reviewed: 2026-10-02
---

# Koszt nabycia liczymy z partii zakupu (FIFO domyślnie, wskazanie partii gdy broker ją identyfikuje); średnia cena służy tylko prezentacji

Rekomendacja: **Partia** (nowe pojęcie, proponowane) powstaje przy każdym zakupie i przelewie papierów, jest daną **pochodną** Operacji i odtwarzalną przez `rebuild`. Sprzedaż zużywa partie wg FIFO w obrębie Portfela (= rachunku, [ADR 0001](0001-portfel-jest-rachunkiem.md)), chyba że Operacja wskazuje konkretne partie. Zysk zrealizowany i wycena otwartych pozycji (koszt) czytają z partii; `average_buy_price` zostaje wyłącznie informacją.

**Rozstrzyga decyzje roadmapy:** D2 i część D3 (pojęcie Partia). **Blokuje:** E2.4, E3.2, E6.1, E6.2, E8.1–E8.3 (operacje na partiach).

## Kontekst

- Dziś sprzedaż **nie zmienia** średniej ceny, a zysk zrealizowany nie istnieje (`backend/app/modules/portfolios/domain/ledger.py:204-225`); koszt wyceny to `ilość × average_buy_price` (`domain/valuation.py:53`). Średnia obejmuje prowizję zakupu (`ledger.py:180`).
- Art. 24 ust. 10 ustawy o PIT ([dowód 04](../../research/04_rynek_pl_podatki_i_brokerzy.md), §1.2): „Jeżeli podatnik dokonuje odpłatnego zbycia papierów wartościowych nabytych po różnych cenach i **nie jest możliwe określenie ceny nabycia** zbywanych papierów wartościowych, przy ustalaniu dochodu z takiego zbycia stosuje się zasadę, że każdorazowo zbycie dotyczy kolejno papierów wartościowych nabytych najwcześniej. Zasadę, o której mowa w zdaniu pierwszym, stosuje się odrębnie dla każdego rachunku papierów wartościowych.” Analogicznie art. 30b ust. 7 (fundusze) i art. 30a ust. 4 (obligacje).
- FIFO jest więc regułą **domyślną przy braku identyfikacji**, nie zakazem identyfikacji; myfund dodał wybór transakcji kupna dla XTB (dowód 04, §1.2). Dla krypto FIFO z art. 30b ust. 7a „odpowiednio” jest niejasne — poza tym ADR-em ([ADR 0006](0006-zakres-modulu-podatkowego.md)).
- Suma zysków (zrealizowany + niezrealizowany) nie zależy od metody; metoda przesuwa zysk między nimi ([dowód 05](../../research/05_metodyka_metryk.md), §6: FIFO 336,50 + 47,50 = 384,00; średnia 286,50 + 97,50 = 384,00).

## Decyzja

1. **Partia** = `(Portfel, Walor, Operacja otwierająca)` z ilością otwartą i pozostałą, kosztem jednostkowym w walucie Waloru (cena + prowizja zakupu, jak dziś w średniej), kursem brokera zamrożonym w dniu zakupu (koszt w walucie Portfela) i kosztem w PLN po kursie podatkowym ([ADR 0005](0005-daty-operacji-i-zdarzenie-podatkowe.md)). Tabele pochodne `portfolios_lot`, `portfolios_lot_consumption` (E2.4); partia nigdy nie jest edytowana, tylko przebudowywana.
2. **Domyślnie FIFO** w obrębie `(Portfel, Walor)`. Prowizja sprzedaży rozkładana proporcjonalnie na zużywane wycinki.
3. **Wskazanie partii** [propozycja]: Operacja sprzedaży może nieść listę `(Operacja otwierająca, ilość)` jako **dane wejściowe** (nie pochodne — przeżywają `rebuild`); niewskazana reszta idzie FIFO. Dozwolone tylko gdy źródło identyfikuje partię (import z brokera, np. IBKR `Trade ID`/`Open/Close Indicator`; ręcznie z potwierdzeniem w UI). Wskazanie nieistniejącej lub za małej partii → błąd `LOT_SELECTION_INVALID`.
4. **Przelew papierów** między Portfelami przenosi partie z kosztem i datą nabycia (E2.3); **split** zmienia ilość i koszt jednostkowy partii bez zmiany kosztu łącznego i daty (E8.1).
5. **Wycena otwartych pozycji**: koszt = Σ koszt pozostały partii; niezrealizowany P/L = wartość rynkowa − ten koszt. `Position.average_buy_price` zostaje jako średnia ruchoma (dziś: bez zmian przy sprzedaży), oznaczona w UI „średnia cena zakupu (informacyjnie)”; **nie** zasila P/L ani raportów.
6. **Zysk zrealizowany** liczony per wycinek zużycia w trzech walutach: Waluty Waloru, Waluty Portfela, PLN po kursie podatkowym.
7. Test akceptacji: złoty test z dowodu 05 §6 (336,50 / 286,50 / 384,00) i test własności „zysk całkowity niezależny od metody”.

## Rozpatrywane alternatywy

| Opcja | Koszt / ryzyko | Werdykt |
|---|---|---|
| A. Tylko średnia ważona (dziś) | brak zysku zrealizowanego i PIT-38; średni FX × średnia cena ≠ suma kosztów PLN per partia (dowód 05 §6.2) | odrzucona |
| B. Samo FIFO bez wskazania partii | prostsze (brak danych wejściowych w sprzedaży), ale zawyża/zaniża podatek, gdy broker identyfikuje partię (IBKR) | odrzucona; wskazanie jest tanie, gdy partie istnieją |
| C. Wybór metody per Portfel (LIFO/HIFO/średnia) | prawo przewiduje FIFO albo identyfikację; wielość metod mnoży testy i tworzy fałszywe poczucie zgodności | odrzucona (plan §7: LIFO/HIFO tylko „co by było”) |
| D. Partie jako dane źródłowe (zapisywane niezależnie od Operacji) | łamie „Operacje są źródłem prawdy” (P3); edycja Operacji rozjeżdża partie | odrzucona |
| E. Zachować średnią jako koszt wyceny, FIFO tylko w podatkach | dwa różne „zyski niezrealizowane” w aplikacji; sprzeczne liczby na ekranie i w raporcie | odrzucona |

## Konsekwencje

**Pozytywne**
- Zysk zrealizowany, raport zamkniętych pozycji (E3.2) i PIT-38 (E6) z jednego rejestru; koszt PLN nie jest wyprowadzany ponownie przy sprzedaży.
- `rebuild` pozostaje jedyną ścieżką — idempotencja testowalna (DoD pkt 8).

**Negatywne**
- Niezrealizowany P/L po częściowej sprzedaży **zmienia wartość** względem dziś (liczony z partii, nie ze średniej); `ilość × średnia cena` ≠ koszt pozycji — UI musi to oznaczyć. Testy parytetu `test_ledger_parity.py` (kasa i Pozycje) pozostają zielone; zmieniają się oczekiwania w `test_valuation.py`.
- Każda edycja/usunięcie Operacji wstecz przelicza kolejkę FIFO od jej daty (koszt O(operacje waloru)).
- Wskazanie partii to dane wejściowe, które mogą „zawisnąć”, gdy edycja zakupu zmieni jego identyfikację — wymaga walidacji przy `rebuild`.
- Rzadkie flagi partii (ulga IPO, darowizna, spadek) są zakresem E6.1, nie tego ADR.

## Zmiany słownika po akceptacji

| Pojęcie | Wpis w `CONTEXT.md` |
|---|---|
| **Partia** (`portfolios_lot`) | „Część Pozycji nabyta jedną Operacją: ilość, koszt jednostkowy, data nabycia. Dana pochodna Operacji; zużywana przy sprzedaży (FIFO lub wskazana).” _Unikać_: lot (poza dyskusją o prawie), transza, paczka zakupu |
| **Zużycie partii** | Wycinek Partii skonsumowany przez sprzedaż; źródło zysku zrealizowanego. _Unikać_: alokacja |
| **Zysk zrealizowany** | Wynik sprzedaży wyliczony ze zużytych Partii. _Unikać_: zysk gotówkowy |
| **Pozycja** (zmiana) | Usunąć _Unikać_: „lot”; „średnia cena zakupu” oznaczyć jako informacyjną |

## Otwarte

- Czy wskazanie partii wymaga osobnej tabeli wejściowej `portfolios_operation_lot_pick` czy pola na Operacji — decyzja techniczna przy E2.4 ([propozycja]: tabela).
- Próbki plików brokerów identyfikujących partie (IBKR, XTB) — brak; blokuje E4.3, nie ten ADR.
