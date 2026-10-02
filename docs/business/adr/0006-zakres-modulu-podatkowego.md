---
id: adr-0006-tax-module-scope
status: Proposed
type: decision
scope: business/taxes
last_reviewed: 2026-10-02
---

# Moduł `taxes` jest szkicem do weryfikacji, nie poradą: trzy pule, jawny zakres v1 i lista nieweryfikowanych założeń

Moduł liczy dane pomocnicze do PIT-38 w trzech osobnych pulach, każdy wynik to „szkic do weryfikacji”. Zakres v1 wąski i jawny; IKE/IKZE/PPK/PPE/OIPE poza pulami; rzeczy niezweryfikowane to parametry lub flagi, nie zaszyte reguły.

**Rozstrzyga:** zakres E6 (D2, D12 dają dane wejściowe). **Blokuje:** E6.1–E6.7, E9.2.

## Kontekst

- Podstawa: ustawa o PIT, Dz.U. 2026 poz. 592; broszura MF do PIT-38 za 2025 ([dowód 04](../../research/04_rynek_pl_podatki_i_brokerzy.md)). Źródeł przychodu się nie łączy: art. 30b ust. 5d (krypto), art. 30a ust. 7 (ryczałt).
- Luki dowodu: Ordynacja art. 63, UPO PL–US (źródła trzecie), limity IKE/IKZE/OIPE (źródła wtórne), zdarzenia korporacyjne (luki 2, 3, 4, 8).
- Zależne od: Partie ([ADR 0002](0002-koszt-nabycia-partie-fifo.md)), daty i kursy ([ADR 0005](0005-daty-operacji-i-zdarzenie-podatkowe.md)), Typ rachunku ([ADR 0001](0001-portfel-jest-rachunkiem.md)).

## Decyzja

1. **Charakter**: każdy ekran, raport i eksport `taxes` nosi etykietę „Szkic do weryfikacji — nie porada podatkowa” i listę użytych założeń (podstawa daty, zaokrąglenie, flagi). Bez wysyłki i generowania PIT-8C.
2. **Trzy pule**, nigdy nie łączone:
   - (a) papiery, fundusze, pochodne — art. 30b ust. 1, 19% dochodu; przychód − koszt z Partii, koszty rachunku jako koszt roczny, straty art. 9 ust. 3 (E6.1, E6.2, E6.5).
   - (b) waluty wirtualne — art. 30b ust. 1a, art. 22 ust. 14–16; nadwyżka kosztów przechodzi na następny rok; bez FIFO (E6.4).
   - (c) dywidendy i odsetki — art. 30a, 19% przychodu per zdarzenie; WHT odliczany do limitu 19% (ust. 9), kurs NBP D−1 dnia wypłaty (E6.3).
3. **Poza zakresem v1**:
   - Spin-off, prawa poboru/PDA (luka 8) — znacznik `TAX_REVIEW_REQUIRED` liczony z łańcucha Operacji (nie kolumna); raport wymienia, nie wylicza.
   - PIT/ZG dla dywidend — dywidendy (art. 30a) idą do części G; PIT/ZG tylko dla zagranicznych zysków kapitałowych (art. 30b ust. 5a–5f).
   - Wypłaty/zwroty z IKE, IKZE, PPK, OIPE (art. 30a ust. 1 pkt 10–11f, art. 30 ust. 1 pkt 14) — v2.
   - Limity wpłat IKE/IKZE i raport wpłat IKZE (art. 26 ust. 1 pkt 2b) — v2; w E5.6 limity tylko jako konfiguracja z `source_ref` i etykietą [niezweryfikowane].
   - Pochodne, CFD, Forex, krótka sprzedaż — poza produktem (plan §7).
   - Obligacje skarbowe — podatek pobiera płatnik; wykazujemy informacyjnie; zagraniczne → część G.
   - Wysyłka elektroniczna, XML PIT-38.
4. **Rachunki z ulgą**: Operacje Portfela z `account_type` ≠ `regular` nie zasilają żadnej puli; dywidenda nie generuje dopłaty, strata nie wchodzi do PIT-38 (art. 9 ust. 3a pkt 4, art. 30a ust. 8d).
5. **Zaokrąglenia per pole raportu**: podstawa i podatek PIT-38 (poz. 31, 35, 41, 45) do pełnych złotych (od 50 gr w górę); rachunki pośrednie `Decimal` bez zaokrągleń. Dla art. 30a ust. 1 pkt 1–3 źródła sprzeczne (broszura MF, art. 63 § 1a Ordynacji: „do pełnych groszy w górę”; przykłady PKO BP przeczą). Parametr `rounding_rule_30a` ∈ {`grosz_up`, `zloty_half_up`} **[propozycja]**, domyślnie `grosz_up` **[niezweryfikowane]**.
6. **Weryfikacje przed uznaniem raportu za „sprawdzony”** (do tego czasu flagi): art. 63 Ordynacji; UPO PL–US i W-8BEN (15%, dopłata 4%); data przychodu (ADR 0005); limity IKE/IKZE/OIPE z M.P.; FIFO „odpowiednio” dla krypto (art. 30b ust. 7a); zgodność z PIT-8C właściciela (kryterium E6.2).

## Alternatywy

- Nie budować modułu — rezygnacja z głównej przewagi PL.
- Pełny PIT-38 ze wszystkimi przypadkami — fałszywa kompletność.
- Jedna pula z rozbiciem w raporcie — sprzeczne z art. 30b ust. 5d i art. 30a ust. 7.

## Konsekwencje

- (+) Błąd interpretacji ma ograniczony zasięg; zmiana reguły to zmiana parametru. Akceptacja: część krajowa zgodna z PIT-8C (±1 zł), scenariusz WHT 15% → dopłata 16,00 zł.
- (−) Spin-off, wypłaty IKE/IKZE i krypto-FIFO wymagają oceny ręcznej; dopóki flagi są otwarte, „szkic” nie jest jedyną podstawą zeznania.

## Słownik (`CONTEXT.md` po akceptacji)

**Pula podatkowa** — jedna z trzech niełączonych grup dochodu (_unikać_: koszyk). **Szkic podatkowy** — wynik `taxes` do weryfikacji (_unikać_: rozliczenie, deklaracja).

## Otwarte

- PIT-8C właściciela z poprzedniego roku — brak, blokuje akceptację E6.2.
- Czy v1 obejmuje obligacje w kolejce FIFO art. 30a ust. 4 (zależy od E5.1).
