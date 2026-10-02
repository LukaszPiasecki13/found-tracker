---
id: adr-0006-tax-module-scope
status: Proposed
type: decision
scope: business/taxes
last_reviewed: 2026-10-02
---

# Moduł `taxes` jest szkicem do weryfikacji, nie poradą: trzy pule, jawny zakres v1 i lista nieweryfikowanych założeń

Rekomendacja: moduł podatkowy liczy **dane pomocnicze do PIT-38** w trzech osobnych pulach, każdy wynik i eksport oznacza jako „szkic do weryfikacji”, a zakres v1 jest wąski i jawny. Rachunki IKE/IKZE/PPK/PPE/OIPE są wyłączone z pul. Rzeczy niezweryfikowane są parametrami albo flagami, nie zaszytymi regułami.

**Rozstrzyga decyzję roadmapy:** zakres E6 (decyzje D2, D12 dostarczają dane wejściowe; to ADR zakresu i zastrzeżeń). **Blokuje:** E6.1–E6.7 (do akceptacji nie implementować raportu), E9.2 (rebalancing z kolejnością podatkową).

## Kontekst

- FundTracker ma liczyć dane pomocnicze do PIT-38, nie zastępować PIT-8C ani porady ([dowód 04](../../research/04_rynek_pl_podatki_i_brokerzy.md), nagłówek). Podstawa: ustawa o PIT, tekst jednolity Dz.U. 2026 poz. 592; broszura MF do PIT-38 za 2025.
- Źródła przychodu się nie łączą: art. 30b ust. 5d (krypto), art. 30a ust. 7 (ryczałt) — strata w jednej puli nie pomniejsza podatku w innej.
- Dowód zawiera wprost luki: Ordynacja art. 63 nie pobrana, UPO PL–US tylko ze źródeł trzecich, limity IKE/IKZE/OIPE z artykułów wtórnych, zdarzenia korporacyjne nieprzeanalizowane (luki 2, 3, 4, 8).
- Kolejność i koszty wejściowe: Partie ([ADR 0002](0002-koszt-nabycia-partie-fifo.md)), daty i kursy ([ADR 0005](0005-daty-operacji-i-zdarzenie-podatkowe.md)), Typ rachunku ([ADR 0001](0001-portfel-jest-rachunkiem.md)).

## Decyzja

1. **Charakter**: każdy ekran, raport i eksport `taxes` nosi etykietę „Szkic do weryfikacji — nie porada podatkowa” oraz listę założeń użytych w wyliczeniu (podstawa daty, reguła zaokrąglenia, flagi `[niezweryfikowane]`). Brak automatycznej wysyłki i generowania PIT-8C.
2. **Trzy pule** (nigdy nie łączone):

| Pula | Podstawa | Mechanizm | Krok |
|---|---|---|---|
| (a) papiery wartościowe, fundusze, pochodne | art. 30b ust. 1, 19% dochodu | przychód − koszt z Partii (FIFO/wskazanie), koszty rachunku jako koszt roczny, straty art. 9 ust. 3 | E6.1, E6.2, E6.5 |
| (b) waluty wirtualne | art. 30b ust. 1a; art. 22 ust. 14–16 | koszty roku vs przychody roku, nadwyżka kosztów przechodzi na następny rok; bez FIFO w rachunku kosztu | E6.4 |
| (c) dywidendy i odsetki | art. 30a, 19% przychodu per zdarzenie | WHT i odliczenie do limitu 19% (ust. 9), kurs NBP D−1 dnia wypłaty | E6.3 |

3. **Poza zakresem v1** (z uzasadnieniem):

| Pozycja | Powód |
|---|---|
| Spin-off, prawa poboru/PDA — skutki podatkowe dla kosztu nabycia | dowód ich nie przeanalizował (luka 8); partie po zdarzeniu dostają flagę `tax_review_required`, a raport je wymienia bez wyliczania |
| PIT/ZG dla dywidend | dywidendy (art. 30a) idą do części G, nie do PIT/ZG; PIT/ZG tylko dla **zagranicznych zysków kapitałowych** (art. 30b ust. 5a–5f, per kraj) |
| Wypłaty/zwroty z IKE, IKZE, PPK, OIPE (19% / 10%) | rachunki z ulgą poza pulami; wypłaty to osobne reguły (art. 30a ust. 1 pkt 10–11f; art. 30 ust. 1 pkt 14) — kandydat v2 |
| Raport wpłat IKZE do odliczenia (art. 26 ust. 1 pkt 2b), limity roczne | wartości limitów niezweryfikowane (obwieszczenia M.P. nie pobrane); ostrzeżenie o przekroczeniu — v2 |
| Pochodne, CFD, Forex, krótka sprzedaż | poza zakresem produktu (plan §7) |
| Obligacje skarbowe: podatek od odsetek | pobiera płatnik/agent emisji; FundTracker wykazuje informacyjnie, nie liczy zobowiązania; zagraniczne → część G |
| Elektroniczna wysyłka, XML PIT-38 | poza zakresem |

4. **Rachunki z ulgą**: Operacje na Portfelu z `account_type` ≠ `regular` nie zasilają żadnej puli, dywidendy na nim nie generują dopłaty, strata nie wchodzi do PIT-38 (art. 9 ust. 3a pkt 4, art. 30a ust. 8d).
5. **Zaokrąglenia jako parametr per pole raportu**: podstawa i podatek PIT-38 (poz. 31, 35, 41, 45) do pełnych złotych (od 50 gr w górę); rachunki pośrednie na `Decimal` bez zaokrągleń. Dla podatku z art. 30a ust. 1 pkt 1–3 **źródła są sprzeczne**: broszura MF (art. 63 § 1a Ordynacji) — „do pełnych groszy w górę”, przykłady PKO BP dla obligacji temu przeczą. Parametr `rounding_rule_30a` ∈ {`grosz_up`, `zloty_half_up`} **[propozycja]**, domyślnie `grosz_up` wg broszury, oznaczone **[niezweryfikowane]** w raporcie.
6. **Weryfikacje wymagane przed uznaniem raportu za „sprawdzony”** (każda w raporcie jako flaga, dopóki otwarta): tekst art. 63 Ordynacji; UPO PL–US i skutki W-8BEN (15%, dopłata 4%); interpretacja daty przychodu (ADR 0005); limity IKE/IKZE/OIPE z obwieszczeń M.P.; FIFO „odpowiednio” dla krypto (art. 30b ust. 7a); zgodność wyniku z **PIT-8C właściciela** (kryterium E6.2) — wymaga próbki dokumentu.

## Rozpatrywane alternatywy

| Opcja | Koszt / ryzyko | Werdykt |
|---|---|---|
| A. Nie budować modułu | rezygnacja z głównej przewagi PL nad zagranicznymi trackerami; ręczny Excel | odrzucona |
| B. Pełna deklaracja PIT-38 ze wszystkimi przypadkami | koszt rośnie z każdym nieprzeanalizowanym przypadkiem; fałszywe poczucie kompletności | odrzucona |
| C. Szkic z jawnym zakresem (rekomendacja) | użytkownik musi sam sprawdzić pozycje poza zakresem; wynik wymaga porównania z PIT-8C | wybrana |
| D. Jedna wspólna pula z rozbiciem w raporcie | sprzeczne z art. 30b ust. 5d i art. 30a ust. 7; błędny podatek przy stracie w innej puli | odrzucona |

## Konsekwencje

**Pozytywne**
- Błąd interpretacji ma ograniczony zasięg i jest widoczny w raporcie; zmiana reguły to zmiana parametru, nie przepisanie modułu.
- Test akceptacji wprost: część krajowa zgodna z PIT-8C (±1 zł) oraz scenariusze złote (WHT 15% → dopłata 16,00 zł).

**Negatywne**
- Wartość raportu w v1 jest ograniczona: spin-off, wypłaty IKE/IKZE i krypto-FIFO wymagają ręcznej oceny.
- Dopóki flagi są otwarte, „szkic” nie może być jedyną podstawą zeznania; ryzyko to właściciel ponosi świadomie.
- Rozjazd z brokerem zagranicznym (data transakcji) może wymagać zmiany `tax_date_basis`.

## Zmiany słownika po akceptacji

| Pojęcie | Wpis w `CONTEXT.md` |
|---|---|
| **Pula podatkowa** | Jedna z trzech niełączonych grup dochodu: papiery (30b ust. 1), krypto (30b ust. 1a), dywidendy i odsetki (30a). _Unikać_: koszyk, źródło (poza cytatem ustawy) |
| **Szkic podatkowy** | Wynik modułu `taxes` do weryfikacji; nie porada. _Unikać_: rozliczenie, deklaracja, PIT (bez „szkic”) |
| **Kurs podatkowy** | Patrz [ADR 0005](0005-daty-operacji-i-zdarzenie-podatkowe.md) |

## Otwarte

- Próbki: PIT-8C właściciela z poprzedniego roku (kryterium zgodności E6.2) — **brak, blokuje akceptację E6.2**.
- Czy v1 obejmuje obligacje w kolejce FIFO art. 30a ust. 4 (zależy od E5.1).
