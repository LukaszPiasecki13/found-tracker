---
id: adr-0004-return-methodology
status: Proposed
type: decision
scope: business/metrics-methodology
last_reviewed: 2026-10-02
---

# Wynik Portfela mierzymy dziennym TWR (konwencja Portfolio Performance) i XIRR; okresów < 365 dni nie annualizujemy

„Wynik %” = **TWR dzienny**; „Mój zwrot %” = **XIRR** na przepływach zewnętrznych; oba z polem `method`. Ryzyko z szeregu TWR.

**Rozstrzyga:** D6. **Blokuje:** E3.1, E2.5 (kolumny `ext_in`, `ext_out`, `r_day`, `twr_index`), E7, E9.

## Kontekst

- Dziś „zwrot” = `(wartość − wpłaty netto) / wpłaty netto` (`backend/app/modules/portfolios/domain/valuation.py:83,88`) — zależy od timingu wpłat.
- GIPS 2.A.12: okresów < roku nie annualizować ([dowód 05](../../research/05_metodyka_metryk.md), §1.2, §1.6).
- Wzór PP: `1 + r_t = (MVE_t + CFout_t) / (MVB_t + CFin_t)`; mianownik 0 → `r_t = 0`, restart.

## Decyzja

1. **TWR**: dzienny, konwencja PP (wpływ = początek dnia, wypływ = koniec); wartość Portfela z gotówką (GIPS 2.A.11). `Decimal` (D11); `R = Π(1 + r_t) − 1 = I_e / I_s − 1`; przepływy z jednego dnia netujemy.
2. **XIRR**: przepływy zewnętrzne + wartość początkowa (jak wpłata) i końcowa (jak wypłata), rok = 365 dni. Kody inline (HTTP 200): `IRR_UNDEFINED` (brak zmiany znaku), `IRR_AMBIGUOUS` (kilka pierwiastków — zwracamy TWR).
3. **Annualizacja**: `(1 + R)^(365/dni) − 1` tylko gdy okres ≥ 365 dni; inaczej `annualized = null`, `reason = "PERIOD_SHORTER_THAN_ONE_YEAR"`. XIRR < 1 roku: zwrot okresu `(1 + IRR)^(dni/365) − 1`.
4. **Modified Dietz** tylko jako fallback dla podokresów bez cen, z `approximation = true`.
5. **Ryzyko** (E7): zmienność, MDD, Sharpe, Sortino, beta z dziennych `r_t`; dni bez sesji pomijane.
6. **Klasyfikacja przepływów**: zewnętrzny = przekracza granicę zakresu (tabela).
7. **API**: `method` `{twr: "daily_pp_v1", irr: "xirr_365_v1"}` **[propozycja nazw]**; zmiana metody = nowa wartość `method` i nowy ADR.
8. **Waluta** [propozycja]: TWR w Walucie bazowej zakresu; efekt FX: najpierw cena po starym kursie, potem kurs na nowej cenie (E7.4).

| Zdarzenie | Portfel | Grupa | Pozycja |
|---|---|---|---|
| Wpłata / wypłata, wpłata automatyczna ([ADR 0003](0003-gotowka-wielowalutowa.md)) | zewnętrzny | zewnętrzny | — |
| Przelew między Portfelami | zewnętrzny (dla obu) | wewnętrzny, gdy oba w Grupie | przepływ Pozycji |
| Przewalutowanie | wewnętrzny | wewnętrzny | — |
| Kupno / sprzedaż | wewnętrzny | wewnętrzny | przepływ Pozycji (z prowizją) |
| Dywidenda, odsetki | dochód | dochód | wypływ z Pozycji |
| Prowizja, opłata, podatek pobrany | koszt | koszt | podatek wyłączony |
| Dywidenda wypłacona poza trackerem | dochód + wypłata zewn. | to samo | wypływ |

## Alternatywy

- Zwrot od wpłat netto (dziś) — zależy od timingu wpłat.
- Jednostki jak w funduszu (myfund) — równoważne TWR, ale rejestr przeliczany wstecz.
- Modified Dietz jako główna — przybliżenie.
- Annualizować zawsze — sprzeczne z GIPS.
- TWR miesięczny — zgodny z GIPS tylko przy małych przepływach.

## Konsekwencje

- (+) Porównywalność z indeksem i Portfolio Performance.
- (−) „Wynik %” różni się od dzisiejszego zwrotu; krótkie okresy bez liczby rocznej.
- (−) TWR Grupy z własnego szeregu, nie średnia TWR Portfeli.
- (−) Wymaga dziennego wektora wyceny (E2.5, E1.1); bez niego fallback z flagą.

## Otwarte

- Stopa wolna od ryzyka dla PLN (NBP vs POLSTR; licencja GPW Benchmark; dowód 05 §4.7) — blokuje E7.1. Skalowanie zmienności PP **[niezweryfikowane]**.
