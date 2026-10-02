---
id: adr-0004-return-methodology
status: Proposed
type: decision
scope: business/metrics-methodology
last_reviewed: 2026-10-02
---

# Wynik Portfela mierzymy dziennym TWR (konwencja Portfolio Performance) i XIRR; nie annualizujemy okresów krótszych niż 365 dni

Rekomendacja: „Wynik %” to **TWR dzienny** łączony geometrycznie, „Mój zwrot %” to **XIRR** na przepływach zewnętrznych, oba z jawnym polem `method` w odpowiedzi. Annualizacja tylko dla okresów ≥ 365 dni. Ryzyko liczone z szeregu TWR. To, co jest przepływem zewnętrznym, zależy od zakresu (Portfel, Grupa, Pozycja).

**Rozstrzyga decyzję roadmapy:** D6. **Blokuje:** E3.1 (stopy zwrotu), E2.5 (kolumny snapshotu: `ext_in`, `ext_out`, `r_day`, `twr_index`), E7 (ryzyko), E9 (planowanie korzysta z definicji okresu). Zasada P2 planu (przejrzysta metodologia).

## Kontekst

- Dziś „zwrot” to `(wartość − wpłaty netto) / wpłaty netto` (`backend/app/modules/portfolios/domain/valuation.py:83,88`) — zależy od momentu wpłat; wykres `/compare` normalizuje wartość do 100, co wpłaty zniekształcają ([dowód 06](../../research/06_stan_found-tracker_vs_cel.md), §5, G3).
- GIPS wymaga TWR, gdy klient kontroluje przepływy; 2.A.12: „Returns for periods of less than one year must not be annualized.” ([dowód 05](../../research/05_metodyka_metryk.md), §1.2, §1.6). Przykład z dowodu: dane 3-dniowe dają XIRR p.a. 3914% — arytmetyka poprawna, liczba bezużyteczna.
- Wzór PP: `1 + r_t = (MVE_t + CFout_t) / (MVB_t + CFin_t)`, wpływy na początku dnia, wypływy na końcu; `R = Π(1 + r_t) − 1`. Gdy mianownik = 0, `r_t = 0` i restart.
- Alternatywa z roadmapy (D6): jednostki jak w funduszu (model myfund, [dowód](../../research/competitors/01_myfund.md)) — równoważne TWR przy wycenie w dniach przepływów.
- Zakres decyduje o klasyfikacji: przelew między Portfelami Grupy jest wewnętrzny dla Grupy, a zewnętrzny dla każdego z jej Portfeli (roadmapa E3.1).

## Decyzja

1. **TWR**: dzienny, konwencja PP (wpływ = początek dnia, wypływ = koniec dnia); wartość Portfela **z gotówką** (GIPS 2.A.11). Obliczenia i `twr_index` w `Decimal` (D11); wszystkie okresy z jednego indeksu: `R(s,e) = I_e / I_s − 1`. Przepływy zewnętrzne z tego samego dnia netujemy i dokumentujemy.
2. **XIRR**: na przepływach zewnętrznych plus wartość początkowa (jak wpłata) i końcowa (jak wypłata), rok = 365 dni; solver wg dowodu 05 §1.4 (Newton + bisekcja). Kody: `irr_undefined` (brak zmiany znaku), `irr_ambiguous` (kilka pierwiastków — zwracamy TWR i pole puste).
3. **Annualizacja**: `(1 + R)^(365/dni) − 1` tylko gdy okres ≥ 365 dni; inaczej `annualized = null`, `reason = "period_shorter_than_one_year"`. Dla XIRR < 1 roku pokazujemy zwrot okresu `(1 + IRR)^(dni/365) − 1`, nie stopę roczną.
4. **Modified Dietz** wyłącznie jako fallback dla podokresów bez cen, z flagą `approximation = true`.
5. **Ryzyko** (E7): zmienność, MDD, Sharpe, Sortino, beta liczone z dziennych `r_t`; dni bez sesji pominięte (E1.9), nigdy ze zmian surowej wartości.
6. **Klasyfikacja przepływów** — tabela poniżej; reguła: *zewnętrzny = przekracza granicę zakresu*.
7. **Odpowiedź API**: `method` `{twr: "daily_pp_v1", irr: "xirr_365_v1"}` **[propozycja nazw]**, `effective_start`, `annualized`, `data_quality`; zmiana metody = nowa wartość `method` i nowy ADR, nigdy ciche przeliczenie.
8. **Konwencja walutowa** [propozycja]: TWR w Walucie bazowej zakresu; efekt walutowy rozkładany „najpierw cena po starym kursie, potem kurs na nowej cenie” (składnik krzyżowy trafia do efektu FX), konwencja stała (E7.4).

| Zdarzenie | Portfel | Grupa | Pozycja |
|---|---|---|---|
| Wpłata / wypłata | zewnętrzny | zewnętrzny | — |
| Wpłata automatyczna ([ADR 0003](0003-gotowka-wielowalutowa.md)) | zewnętrzny | zewnętrzny (źródło spoza Grupy) | — |
| Przelew gotówki lub papierów między Portfelami | zewnętrzny (dla obu) | wewnętrzny, gdy oba w Grupie; inaczej zewnętrzny | przepływ Pozycji |
| Przewalutowanie | wewnętrzny | wewnętrzny | — |
| Kupno / sprzedaż | wewnętrzny | wewnętrzny | przepływ Pozycji (z prowizją) |
| Dywidenda, odsetki | dochód wewnętrzny | dochód wewnętrzny | wypływ z Pozycji |
| Prowizja, opłata za rachunek | koszt wewnętrzny (obniża wynik) | koszt wewnętrzny | w przepływie / nieprzypisana |
| Podatek pobrany z rachunku (WHT, Belka) | koszt wewnętrzny | koszt wewnętrzny | wyłączony (przed podatkiem) |
| Dywidenda wypłacona poza trackerem | dochód + wypłata zewnętrzna | to samo | wypływ |

## Rozpatrywane alternatywy

| Opcja | Koszt / ryzyko | Werdykt |
|---|---|---|
| A. Zwrot od wpłat netto (dziś) | zależy od timingu wpłat; wypłata i ponowna wpłata zaniżają wynik | odrzucona |
| B. Jednostki jak w funduszu (myfund) | równoważne TWR (wg D6), ale wymaga trwałego rejestru jednostek, przeliczanego wstecz przy edycji; gorzej wyjaśnialne; trudna agregacja Grup | odrzucona |
| C. Modified Dietz jako główna metoda | przybliżenie, rozjeżdża się przy dużych przepływach (2,72% vs 3,00% w przykładzie dowodu) | tylko fallback |
| D. Annualizować zawsze (jak PP dla IRR) | liczby w rodzaju 3914% p.a.; sprzeczne z GIPS 2.A.12 | odrzucona |
| E. TWR miesięczny/okresowy | zgodny z GIPS tylko przy małych przepływach; dzienne ceny już są | odrzucona |

Koszt rekomendacji: pełny dzienny wektor wyceny (snapshoty E2.5, historia cen E1.1) jest warunkiem — bez niego Portfel pokazuje fallback z flagą.

## Konsekwencje

**Pozytywne**
- Liczba porównywalna z indeksem i z Portfolio Performance (walidacja krzyżowa, dowód 05 §10.5).
- Jawne `method` i `reason` — zmiana metody jest widoczna, nie cicha.

**Negatywne**
- „Wynik %” zmienia wartość względem dzisiejszego zwrotu od wpłat; użytkownik zobaczy dwie różne liczby (TWR i dotychczasowy zysk kwotowy).
- Krótkie okresy bez annualizacji — brak „ładnej” liczby rocznej dla nowych Portfeli.
- TWR Grupy nie jest średnią ważoną TWR Portfeli; liczone z własnego szeregu.
- Zerowy mianownik (nowy lub w pełni wypłacony Portfel) wymaga komunikatu, by przerwa nie wyglądała jak „0%”.

## Zmiany słownika po akceptacji

| Pojęcie | Wpis w `CONTEXT.md` |
|---|---|
| **TWR (stopa zwrotu ważona czasem)** | Dzienny, konwencja PP; eliminuje wpływ wpłat i wypłat. _Unikać_: wynik, ROI, zwrot (bez przymiotnika) |
| **XIRR (zwrot ważony kapitałem)** | Stopa na przepływach zewnętrznych z datami. _Unikać_: IRR p.a. dla okresu < 1 roku |
| **Przepływ zewnętrzny / wewnętrzny** | Zewnętrzny przekracza granicę zakresu (Portfel/Grupa); zależy od zakresu. _Unikać_: wpłata (jako ogólne słowo) |
| **Suma wpłat** (zmiana) | Dopisać: nie jest podstawą wyniku % |

## Otwarte

- Stopa wolna od ryzyka dla PLN (stopa referencyjna NBP vs POLSTR; licencja GPW Benchmark) — dowód 05 §4.7, blokuje E7.1, nie TWR.
- Skalowanie zmienności w PP (`Risk.Volatility`) niepotwierdzone w UI PP — [niezweryfikowane] przed deklarowaniem zgodności.
