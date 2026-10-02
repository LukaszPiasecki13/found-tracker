---
id: research-performance-methodology
status: current
type: mixed
scope: research/methodology
last_reviewed: 2026-10-02
---

# Jak poprawnie liczyć stopę zwrotu, ryzyko i koszt nabycia w trackerze portfela?
> **Dokument L4 (dowód).** Stan na 2026-10-01/02. Nienormatywny — rekomendacje stąd stają się obowiązujące dopiero przez ADR lub plan. Append-only: nie poprawiamy, dopisujemy nowe badanie i link do następcy.

Odbiorca: implementujący `backend/app/modules/portfolios/` (FastAPI, `Decimal`, dzienne wektory wyceny); kontekst modułu: [05_portfolios_module.md](../technical/backend/05_portfolios_module.md), słownik: [CONTEXT.md](../business/CONTEXT.md).

**Konwencje.** Wzory zapisane tekstem: `^` potęga, `ln` logarytm naturalny, `Σ` suma, `Π` iloczyn, `sqrt` pierwiastek. **rekomendacja** = rada inżynierska bez autorytetu zewnętrznego; **[niezweryfikowane]** = nie potwierdzone źródłem pierwotnym; **[wniosek]** = wniosek autora. Liczby w przykładach policzono w Pythonie 3.11 (skrypty `rm_examples.py`, `rm_examples2.py` w scratchpadzie badania); wyniki Monte Carlo zależą od ziarna. Investopedia zablokowała pobieranie — nie jest cytowana.
## 0. Podsumowanie: co zbudować
| Metryka | Metoda | Dlaczego |
|---|---|---|
| „Wynik Portfela %” | Prawdziwy dzienny TWR (TTWROR w PP), łączony geometrycznie | Eliminuje wpływ momentu wpłat/wypłat; jedyna liczba porównywalna z indeksem. GIPS wymaga TWR, gdy klient kontroluje przepływy |
| „Mój osobisty zwrot %” | XIRR (ważony kapitałem, MWR) na przepływach zewnętrznych + MV na początku i końcu | „Jak radziły sobie moje pieniądze przy moim timingu”. Główna liczba Sharesight jest ważona kapitałem |
| Szybka liczba przy niepełnej historii | Modified Dietz | Tylko tam, gdzie brakuje dziennego wektora wyceny |
| Annualizacja | `(1+R)^(365/days) − 1` tylko dla okresu ≥ 365 dni (GIPS 2.A.12) | Annualizacja zwrotu 3-dniowego daje absurdy (§1.6) |
| Ryzyko | Z dziennego szeregu zwrotów TWR r_t, nie ze zmian MV | Zmiany MV zawierają wpłaty |
| Podatkowy P/L (PL) | FIFO per rachunek maklerski jako domyślne, gdy nie da się określić ceny nabycia zbywanych papierów (art. 24 ust. 10 ustawy o PIT, §6.2), przeliczenie na PLN kursem średnim NBP z dnia poprzedniego | Obecne `average_buy_price` to średni koszt — OK dla UI, błędne dla PIT-38 |
## 1. Miary zwrotu
### 1.1 Prosty ROI
```
Gain   = MVE − MVB − Σ CF_ext            (CF_ext: deposits +, withdrawals −)
ROI    = Gain / (MVB + Σ deposits)        (one common definition)
```
- Żaden standard nie definiuje „prostego ROI” portfela z przepływami — każdy dostawca wybiera mianownik. Ghostfolio „ROAI” dzieli wynik netto przez **średnią inwestycję ważoną czasem** (`roai/portfolio-calculator.ts`: `sumOfWeightedInvestments / totalInvestmentDays`) — blisko MWR typu Dietz. Klasy `TWR` i `MWR` w Ghostfolio przy commicie `347cd06a` rzucają `Method not implemented`.
- Pułapka: ROI na brutto wpłatach zaniża wynik przy wypłacie i ponownej wpłacie.
- **rekomendacja:** pokazuj bezwzględny `Gain` w walucie bazowej obok TWR i IRR; żadnego ROI % nie nazywaj „wynikiem”.
### 1.2 Prawdziwy TWR (łączenie dzienne)
**GIPS 2020 (słownik):** TWR to metoda „that reflects the change in value and negates the effects of external cash flows”. GIPS 2.A.24: liczyć podokresy przy dużych przepływach, jeśli nie liczy się dziennie, i łączyć je geometrycznie. Wzór PP (PP-TWR, równania 3 i 2):
```
1 + r_t = (MVE_t + CFout_t) / (MVB_t + CFin_t)          daily holding-period return
R       = [(1 + r_1) × (1 + r_2) × … × (1 + r_n)] − 1    linking
```
**Konwencja czasu (PP-TWR):** wpływy na samym początku dnia, wypływy na samym końcu dnia tuż przed wyceną. Kod PP (`ClientIndex.java`):
```
delta[i] = (thisValuation + outboundTransferals[i]) / (valuation + inboundTransferals[i]) − 1
accumulated[i] = (accumulated[i−1] + 1) × (delta[i] + 1) − 1
```
Gdy `valuation + inbound == 0`, PP ustawia `delta = 0` (z ostrzeżeniem, jeśli wartość pojawiła się znikąd). CFin/CFout: na poziomie Portfela tylko wpłaty, wypłaty i dostawy papierów (dywidendy i wpływy ze sprzedaży zostają w Portfelu); na poziomie waloru dywidendy i wpływy ze sprzedaży są przepływami, podatki wyłączone. **Przykład** (konwencja PP, baza PLN):

| Dzień | MVB | CFin (początek) | CFout (koniec) | MVE po przepływach | 1 + r_t |
|---|---|---|---|---|---|
| 1 | 10 000 | 5 000 | 0 | 15 300 | 15 300 / 15 000 = 1.02 |
| 2 | 15 300 | 0 | 2 000 | 13 000 | (13 000 + 2 000) / 15 300 = 0.980392… |
| 3 | 13 000 | 0 | 0 | 13 390 | 1.03 |

TWR = 1.02 × 0.980392 × 1.03 − 1 = **+3.0000 %** — wpłata i wypłata go nie zmieniają. **Mapowanie typów Operacji FundTracker** (`domain/enums.py`):

| Operacja | TWR Portfela | TWR Pozycji |
|---|---|---|
| deposit (wpłata) | CFin (zewnętrzny) | — |
| withdrawal (wypłata) | CFout (zewnętrzny) | — |
| buy (kupno) | wewnętrzny: gotówka ↓, walor ↑, MV bez zmian poza prowizją | CFin do Pozycji (brutto z prowizją; PP-MWR: „Cashflow to and from a security is always inclusive of fees”) |
| sell (sprzedaż) | wewnętrzny | CFout z Pozycji |
| dividend (dywidenda) | dochód wewnętrzny (GIPS: dywidendy i odsetki nie są przepływami zewnętrznymi) | CFout z Pozycji |

**Przypadki brzegowe:**
1. **Gotówka musi być częścią MV** (GIPS 2.A.11). Bez niej każde kupno wygląda jak wpłata, a dywidenda znika.
2. **Zerowy mianownik** (pierwsza wpłata do pustego Portfela przy konwencji końca dnia, Portfel w pełni wypłacony): r_t = 0 i restart, bez dzielenia przez zero (jak PP).
3. **Pełna wypłata i nowa wpłata po miesiącach:** łączenie przez lukę z r = 0 jest poprawne, ale UI nie może sugerować, że pieniądze „zarobiły 0 %” — ich nie było.
4. **Wpłata i wypłata tego samego dnia:** duży obrót w ciągu dnia zawyża mianownik. **rekomendacja:** netuj przepływy zewnętrzne z tego samego dnia i udokumentuj to.
5. **Operacje wstecz** zmieniają każde r_t od tej daty — inwalidacja cache w §10.4.
6. **Prowizje:** GIPS 2.A.13 — zwroty po kosztach transakcyjnych. Przy MV z gotówką prowizja obniża MVE i r_t (TWR netto kosztów — poprawnie).
7. **Podatki:** PP wlicza je na poziomie Portfela, wyłącza na poziomie waloru (PP-MWR). **rekomendacja:** ten sam podział — TWR Portfela po podatku, TWR Pozycji przed podatkiem (podatek zależy od całego Portfela).
### 1.3 Modified Dietz (skrót)
Źródło pierwotne: Dietz, *Pension Funds: Measuring Investment Performance* (1966); GIPS 2.A.24(d) wymaga dziennego ważenia przepływów, jeśli nie liczy się dziennych zwrotów. Wzór za Wikipedią (wtórne):
```
R_MD = (B − A − F) / (A + Σ W_i × F_i)
W_i  = (C − D_i) / C            flow at end of day D_i
W_i  = (C − D_i + 1) / C        flow at start of day D_i
A = start value, B = end value, F = Σ F_i (net external flows), C = calendar days in the period
```
- Wikipedia: A = 100, B = 300, +50 w połowie roku → 150 / 125 = **120 %**.
- Dane z §1.2 (C = 3; +5 000 początek dnia 1, W = 1; −2 000 koniec dnia 2, W = 1/3): zysk 390, średni kapitał 14 333.33 → R_MD = **2.7209 %** (TWR 3.0000 %).
- Pułapki (Wikipedia): ujemny średni kapitał daje ujemny wynik mimo zysku; zerowy — wynik nieokreślony; rozjazd z IRR przy dużych przepływach i zwrotach.
- **rekomendacja:** FundTracker ma dzienne wyceny → dzienny TWR; Dietz tylko jako fallback dla podokresów bez cen, oznaczony jako przybliżenie.
### 1.4 MWR / IRR / XIRR
GIPS 2020: MWR odzwierciedla zmianę wartości oraz moment i wielkość przepływów; 2.A.29 wymaga dziennych przepływów i annualizowanego MWR od początku. Wzór PP (PP-MWR):
```
MVB × (1 + IRR)^(RD/365) + Σ CF_t × (1 + IRR)^(RD_t/365) = MVE
RD_t = remaining days from flow t to the end of the period
```
Excel XIRR: szuka r, dla którego `Σ P_i / (1 + r)^((d_i − d_1)/365) = 0`; start 0.1; dokładność 0.000001 %; #NUM! po 100 próbach; wymaga co najmniej jednego przepływu dodatniego i ujemnego.

**Znaki — Portfel (perspektywa inwestora):** wpłaty ujemne, wypłaty dodatnie, MVB na dacie startu ujemne (jak wpłata), MVE na dacie końca dodatnie (jak wypłata). **Pozycja:** kupna z prowizją ujemne; sprzedaże, dywidendy i końcowa MV dodatnie; podatki wyłączone na poziomie waloru, wliczone na poziomie Portfela; dla pojedynczej Operacji PP wlicza prowizje i podatki. **Złote przykłady (testy jednostkowe):**

| Przypadek | Przepływy | Oczekiwane |
|---|---|---|
| Przykład z dokumentacji Excel | 2008-01-01 −10 000; 2008-03-01 +2 750; 2008-10-30 +4 250; 2009-02-15 +3 250; 2009-04-01 +2 750 | 0.373362535 (Excel); Newton autora: 0.3733625335 w 5 iteracjach |
| Przykład PP-MWR | −66 EUR (8 × 8 EUR + 2 EUR prowizji), wartość końcowa 111.76 EUR po 255 dniach | 112.53 % p.a.; kontrola: (111.76/66)^(365/255) − 1 = 1.12528 |
| Dane z §1.2 jako przepływy z datami | 2026-01-01 −10 000; 01-02 −5 000; 01-03 +2 000; 01-04 +13 390 | IRR = 3914 % p.a. — arytmetyka poprawna; powód, by nie annualizować < 1 roku (§1.6) |

**Algorytm PP** (`IRR.java`, `NewtonGoalSeek.java`, `NPVFunction.java`): zmienna x = 1 + r; `npv(x) = Σ v_i / x^(days_i/365)` (dni od pierwszego przepływu); bisekcja na (0, 1) przy różnych znakach do szerokości < 0.001, inaczej start x = 1.05; potem Newton `x_{i+1} = x_i − f(x_i)/f'(x_i)`, stop |Δ| < 1e-5, max 500 iteracji, pochodna numeryczna (`PseudoDerivativeFunction`).

**rekomendacja — odporny solver dla FundTracker:**
1. Walidacja: ≥ 1 przepływ ujemny i ≥ 1 dodatni, inaczej `None` z kodem `irr_undefined`. Sortuj po dacie, agreguj przepływy z tej samej daty.
2. Licz we `float` (iteracyjne szukanie pierwiastka z ułamkowymi wykładnikami); wynik → `Decimal` i kwantyzacja (§10.1).
3. Dziedzina r > −1; podstawienie w r lub w ln(1 + r) dla stabilności przy dużym t.
4. Najpierw Newton od 0.1 z analityczną pochodną `f'(r) = Σ −t_i × P_i × (1 + r)^(−t_i − 1)`, t_i = days_i/365. Akceptuj, gdy |f| < 1e-10 × Σ|P_i| i |Δr| < 1e-12. Przerwij, gdy krok wyjdzie poza (−1, ∞), pochodna ≈ 0 lub > 50 iteracji.
5. Fallback: skan siatki [−0.9999, −0.99, −0.9, −0.5, 0, 0.5, 1, 2, 5, 10, 100], znajdź zmianę znaku, potem Brent lub bisekcja (zawsze zbieżna po zbracketowaniu). `scipy.optimize.brentq` to wzorzec, ale SciPy to decyzja o zależności; bisekcja do 1e-12 ≈ 60 iteracji — wystarczy.
6. **Wiele pierwiastków.** Strumień „konwencjonalny” (jedna zmiana znaku) ma co najwyżej jeden pierwiastek r > −1 (reguła znaków Kartezjusza, rozszerzenie na wykładniki rzeczywiste przypisywane Laguerre'owi — atrybucja **[niezweryfikowane]**, argument monotoniczności łatwy do sprawdzenia). Przykład z dwiema zmianami znaku: −100, +230, −132 przy t = 0, 1, 2 → pierwiastki **10 %** i **20 %** (NPV ≈ 1e-14 w obu). Przy > 1 zmianie znaku skanuj całą siatkę; przy > 1 pierwiastku zwróć najbliższy TWR albo `None` z kodem `irr_ambiguous` i pokaż TWR.
7. **Brak rozwiązania** (np. same wpłaty i zerowa wartość końcowa): `None`, nigdy ostatnia iteracja.

**IRR vs TWR:** TWR mierzy strategię (niezależny od timingu), IRR — doświadczenie inwestora. Bez przepływów zewnętrznych w okresie annualizowane IRR i TWR są równe.
### 1.5–1.6 Skumulowany vs annualizowany; reguła annualizacji
```
Cumulative R over [s, e] = Π(1 + r_t) − 1
Annualized               = (1 + R)^(365 / days) − 1          (PP-TWR; PP example: 30 % over 730 days → 14.02 %)
```
- Ghostfolio: ten sam wykładnik `365/daysInMarket` (`calculation-helper.ts: getAnnualizedPerformancePercent`). PP, Excel XIRR i Ghostfolio liczą rok jako 365 dni. **rekomendacja:** dni rzeczywiste / 365, udokumentowane.
- **GIPS 2020, 2.A.12:** „Returns for periods of less than one year must not be annualized.” GIPS 5.A.1(b): przy historii krótszej niż rok prezentuje się nieannualizowany MWR od początku.
- Sharesight: < 1 roku zwrot z okresu posiadania; od 1 roku „additional annualisation step”. PP pokazuje IRR zawsze p.a. (także przykład 255-dniowy) — tu nie trzyma się GIPS.
- **rekomendacja:** dla okresu < 365 dni `annualized = null` z powodem `period_shorter_than_one_year`. IRR to stopa — dla < 1 roku pokazuj MWR okresu `(1 + IRR)^(days/365) − 1` albo IRR tylko dla ≥ 1 roku. Inaczej użytkownik zobaczy 3914 % z §1.4.
### 1.7 Wybór okresu
PP: okres trwa „od zamknięcia [daty startu] do zamknięcia [daty końca]” — Operacje z dnia startu są już w MVB i wyłączone, z dnia końca — wliczone (PP-Period). **rekomendacja (definicje):**

| Preset | Kotwica startu (wycena na zamknięcie) | Uwaga |
|---|---|---|
| 1D | poprzedni dzień wyceny | |
| 1M / 3M / 6M | ten sam dzień N miesięcy wstecz; przycięcie do końca miesiąca (31 mar → 28/29 lut) | semantyka `dateutil.relativedelta` |
| YTD | 31 grudnia poprzedniego roku (zamknięcie) | jeśli start Portfela później — od startu |
| 1Y / 3Y / 5Y | ta sama data 1/3/5 lat wstecz (29 lut → 28 lut) | 3Y i 5Y annualizuj; 1Y nie wymaga |
| MAX | dzień przed pierwszym przepływem zewnętrznym (MVB = 0) | |
| custom [s, e] | zamknięcie s → zamknięcie e | |

- Start sprzed powstania Portfela → start od powstania i `effective_start` w odpowiedzi; nigdy nie dopełniaj zerowymi zwrotami (rozcieńcza annualizację).
- TWR dowolnego podokresu z indeksu skumulowanego: `R(s, e) = I_e / I_s − 1`, `I_t = Π_{u ≤ t}(1 + r_u)` (§10.4).
## 2. Przepływy zewnętrzne vs wewnętrzne
GIPS 2020: przepływ zewnętrzny to kapitał (gotówka lub inwestycje) wchodzący/wychodzący z portfela; dywidendy i odsetki nimi nie są. GIPS 2.A.29(c): dystrybucje akcji to przepływy zewnętrzne dla MWR — w trackerze odpowiednik to transfer papierów (PP: „deliveries”).

| Zdarzenie | TWR / IRR Portfela | TWR / IRR Pozycji | Uwagi |
|---|---|---|---|
| Wpłata / wypłata gotówki | zewnętrzny | n/d | |
| Transfer papierów do/z (dostawa) | zewnętrzny, wyceniony po rynku w dniu transferu | przepływ Pozycji | przeniesienie między brokerami; **rekomendacja:** typ Operacji `transfer_in` / `transfer_out` |
| Kupno / sprzedaż | wewnętrzny | przepływ Pozycji (z prowizją) | |
| Dywidenda na rachunku | dochód wewnętrzny | wypływ z Pozycji (dochód) | podatek u źródła: netto na poziomie Portfela |
| Dywidenda wprost na konto bankowe poza trackerem | dochód + natychmiastowa wypłata zewnętrzna w dniu wypłaty | wypływ z Pozycji | inaczej zwrot zaniżony |
| Prowizja transakcyjna | obniża MV i zwrot (GIPS 2.A.13) | w przepływie | |
| Opłata za prowadzenie rachunku | koszt wewnętrzny | nieprzypisana (lub pro rata) | **rekomendacja** |
| Podatek od zysków pobrany z rachunku | koszt wewnętrzny (PP) | wyłączony (PP) | Podatek Belki w PL zwykle rozliczany poza rachunkiem (PIT-38) — często brak w danych |
| Odsetki od gotówki | dochód wewnętrzny | n/d | |

- TWR Pozycji: własna MV Pozycji, kupna = CFin, sprzedaże i dywidendy = CFout (PP-TWR „security level”).
- TWR Portfela **nie** jest średnią ważoną TWR Pozycji (wagi zmieniają się codziennie; wątek forum PP „Gesamt-Performance … entspricht nicht Durchschnitt der Bestandteile”). **rekomendacja:** obie wartości licz z własnych szeregów wartości.
## 3. Wiele walut
Pozycja w walucie L, wyceniana w walucie bazowej B (PLN): `MV_B,t = Q_t × P_L,t × FX_t` (FX = PLN za 1 L). Zwrot lokalny z P_L, zwrot bazowy z MV_B. Dekompozycja (Karnosky & Singer 1994; dokumentacja atrybucji Eagle, wtórne):
```
1 + R_base     = (1 + R_local) × (1 + R_fx)
R_fx           = (1 + R_base) / (1 + R_local) − 1
R_base         = R_local + R_fx + R_local × R_fx          (cross term)
```
**Przykład:** akcja USA 100 → 110 USD, USD/PLN 4.00 → 3.80. R_local = +10 %, R_fx = −5 %, R_base = 110 × 3.80 / (100 × 4.00) − 1 = **+4.5 %** = 10 % − 5 % − 0.5 % (składnik krzyżowy). Kwotowo dla 1 akcji (koszt 400 PLN, teraz 418 PLN): efekt ceny po starym kursie (110 − 100) × 4.00 = +40 PLN; efekt walutowy po nowej cenie 110 × (3.80 − 4.00) = −22 PLN; razem +18 PLN. Kolejność „najpierw cena, potem FX na nowej cenie” wkłada składnik krzyżowy do efektu FX. **rekomendacja:** wybierz jedną kolejność, udokumentuj, nie zmieniaj — to konwencja, nie prawo. Sharesight raportuje zysk walutowy „purely in relation to the currency movement on the invested capital”; jego składowe % nie sumują się (5.39 % dywidendowy + 5.39 % kapitałowy = 9.86 % łącznie); Sharesight tłumaczy to tym, że kapitalizacja jest „exponential rather than linear” (Sharesight components, https://help.sharesight.com/components-return/).

**Jakie kursy FX:**
- PP używa kursów referencyjnych EBC i ostrzega, że „will probably differ slightly from the real transaction rates” (PP-Prices).
- Podatek w PL: kwoty walutowe po średnim kursie NBP (tabela A) z ostatniego dnia roboczego przed dniem przychodu/kosztu (art. 11a ustawy o PIT; cytat z tekstu jednolitego Dz.U. 2026 poz. 592 w [04_rynek_pl_podatki_i_brokerzy.md](./04_rynek_pl_podatki_i_brokerzy.md)).
- **rekomendacja:** przechowuj `fx_rate` i `fx_source` (`broker`, `nbp_a`, `ecb`) per Operacja; kurs brokera dla kosztu nabycia w UI, NBP A z D−1 dla rejestru podatkowego, dzienny kurs rynkowy/NBP dla wyceny. Istniejące `average_fx_rate` w `domain/protocols.py` to pojęcie kosztu nabycia — trzymaj osobno od FX wyceny.
## 4. Metryki ryzyka
GIPS 2.A.18: okresowość i metodologia ryzyka dla kompozytu i benchmarku muszą być takie same. Każdą metrykę licz z szeregu TWR r_t (§1.2), nigdy ze zmian surowej MV. Przykładowy szereg (indeks 100, 102, 99, 101, 97, 103): r = [+2.0000 %, −2.9412 %, +2.0202 %, −3.9604 %, +6.1856 %]; wyniki niżej to dane zabawkowe.

| Metryka | Wzór | Przykład / uwagi |
|---|---|---|
| Zmienność | `σ_daily` = odchylenie std. próbkowe r_t (n − 1); `σ_ann = σ_daily × sqrt(252)` (× sqrt(12) miesięcznie, × sqrt(52) tygodniowo) | σ_daily = 4.1381 % → σ_ann = **65.69 %** |
| Max drawdown | `Peak_t = max_{u ≤ t} I_u`; `DD_t = (Peak_t − I_t) / Peak_t`; `MDD = max_t DD_t` | szczyt 102, dołek 97 → MDD = **4.90 %** |
| Sharpe | `D_t = R_Fund,t − R_B,t`; `S = mean(D) / stdev(D)`; `S_T = S_1 × sqrt(T)` | rf 4 % rocznie → dziennie (1.04)^(1/252) − 1 = 0.01556 %; S dzienny 0.1559, × sqrt(252) = **2.48** |
| Sortino | `DD_down = sqrt( Σ_t min(0, r_t − MAR)² / N )` (N = wszystkie obserwacje); `Sortino = (mean(r) − MAR) / DD_down` | MAR = 0: DD_down = 2.2061 %, dzienny 0.2995, ×√252 = 4.76 |
| Beta / alfa / korelacja | `β = Cov(r_p, r_b) / Var(r_b)`; `α (Jensen 1968) = mean(r_p − r_f) − β × mean(r_b − r_f)`; `ρ = Cov(r_p, r_b) / (σ_p × σ_b)` | benchmark +1 %, −2 %, +1.5 %, −3 %, +5 % (α bez rf): β = 1.30, ρ = 0.995 |
| VaR historyczny | `VaR_α = −Quantile_{1−α}(r_t) × V` (np. α = 95 %, 1 dzień, V = bieżąca MV) | 20 zwrotów z `rm_examples2.py`: kwantyl 5 % zwrotów: nearest-rank (k = ceil(0.05 × 20) = 1) → −2.60 %, interpolacja liniowa (NumPy, typ 7) → −2.125 %; VaR (dodatni, strata) = **2.60 %** albo **2.125 %** × V |

- **Zmienność.** Skalowanie pierwiastkiem czasu zakłada niezależność zwrotów (Sharpe 1994; Lo 2002 kwantyfikuje błąd). GIPS 4.A: 3-letnie annualizowane odchylenie ex post „using monthly returns”. **rekomendacja:** pokazuj obie wersje (×√252 z dziennych, ×√12 z miesięcznych) z etykietą. PP (`Risk.Volatility`, `PerformanceIndex.filterReturnsForVolatilityCalculation`) używa log-zwrotów `ln(1 + r)`, pomija pierwszy dzień, dni bez posiadania, weekendy i święta (`TradeCalendar`) i liczy `sqrt(Σ(lr − mean)² / (n − 1) × n)` — **[wniosek]** z lektury kodu: to zmienność za cały okres, nie p.a.; sprawdź przed porównaniem z PP. **Pułapka:** wektor na każdy dzień kalendarzowy z forward-fill daje r = 0 w weekendy i obniża σ o ok. sqrt(5/7) — filtruj dni nienotowane (§10.3).
- **Drawdown.** PP (`Risk.Drawdown`) raportuje też maksymalny czas trwania drawdownu (najdłużej „pod wodą” od ostatniego szczytu) i najdłuższy czas odrabiania (od dołka do nowego szczytu). Licz z indeksu TWR I_t, nie z MV (wypłata nie jest drawdownem). Nieodrobiony drawdown na końcu okresu → `recovered = false`; MDD zależy od okresu; dane dzienne zaniżają drawdowny śróddzienne.
- **Sharpe** (Sharpe 1994: krótkie okresy, np. miesięczne, i annualizacja). Odejmuj rf per okres przed liczeniem odchylenia (szereg rf zmienny w czasie); < ok. 36 obserwacji miesięcznych — estymata bardzo zaszumiona (Lo 2002); ujemnego Sharpe'a nie da się sensownie rankingować.
- **Sortino** (Sortino & Price 1994). PP pokazuje pokrewne „semi-deviation” z log-zwrotów poniżej ich średniej, nie poniżej MAR. **rekomendacja:** domyślne MAR = dzienna stopa wolna od ryzyka, konfigurowalne.
- **Beta/alfa.** Annualizuj α przez ×252 (przybliżenie arytmetyczne) albo (1 + α_d)^252 − 1 — napisz którą. Macierz korelacji: Pearson parami na wyrównanych szeregach. **rekomendacja:** wyrównuj do dat notowań obu walorów; dla rynków w różnych strefach (GPW vs NYSE) dzienne korelacje są obciążone niesynchronicznymi zamknięciami — lepiej tygodniowe; min. 60 wspólnych obserwacji (komórki poniżej wyszarzone); pairwise deletion może dać macierz nie-PSD — do symulacji (§9) użyj complete-case.
- **VaR.** Bez założeń o rozkładzie; wynik zależy od definicji kwantyla — **rekomendacja:** wybierz jedną, udokumentuj, przetestuj. < ok. 250 obserwacji → VaR 99 % bez sensu; skalowanie na 10 dni zakłada niezależność; VaR nic nie mówi o stratach za kwantylem → **rekomendacja:** pokazuj też Expected Shortfall (średnia zwrotów poniżej kwantyla VaR). Źródło pierwotne dla VaR nie było pobierane; standardowy podręcznik: Jorion, *Value at Risk* (McGraw-Hill) (**[niezweryfikowane]** wydanie i strony).
### 4.7 Stopa wolna od ryzyka dla PLN
| Kandydat | Zalety | Wady | Status |
|---|---|---|---|
| Stopa referencyjna NBP | oficjalna, prosta, funkcja schodkowa | stopa polityki, nie inwestowalny zwrot | źródła wtórne: 3.75 % w lipcu 2026 (**[niezweryfikowane]**: nbp.pl blokował automatyczny dostęp) |
| WIBOR 3M | długa historia | wygaszany; komunikat GPW Benchmark z 18.05.2026: WIBOR O/N nie jest opracowywany od 2026-10-01, ostatni fixing 1M/3M/6M 31.12.2036 (**[niezweryfikowane]**, wtórne) | |
| WIRON → POLSTR | stopa overnight typu risk-free (GPW Benchmark) | krótka historia; KS NGR w listopadzie–grudniu 2024 wybrał WIRF-, a ostateczną decyzję o **POLSTR** jako indeksie docelowym w miejsce WIRON podjął 30.01.2025 (wtórne) | |
| Rentowność 52-tyg. bonów / krótkich obligacji | inwestowalna | nieregularne emisje | |
| 0 % | proste | zawyża Sharpe'a przy wysokich stopach | |

**rekomendacja:** stopa jako szereg czasowy `rate_series(code, date, annual_rate)`, kapitalizowana dziennie `rf_d = (1 + rf_annual)^(1/365 or 1/252) − 1` (ta sama baza dni co zwroty); domyślnie stopa referencyjna NBP (darmowa); POLSTR, jeśli licencja pozwala (dane WIBOR/WIRON GPW Benchmark są płatne — `./03_rynek_pl_dane_i_obligacje.md`), wybór widoczny w UI; dla innych walut bazowych €STR (EUR) lub SOFR (USD) (**[niezweryfikowane]** przydatność).
## 5. Benchmarking
- TWR Portfela vs zwrot całkowity indeksu w tym samym [s, e] i tej samej okresowości (GIPS 2.A.18). Indeks **total return** (dywidendy reinwestowane), gdy istnieje — indeks cenowy zaniża benchmark. Osobne wytyczne GIPS o benchmarkach (nieczytane szczegółowo): https://www.gipsstandards.org/wp-content/uploads/2023/08/gs_benchmarks_firms.pdf
- **PP** (`SecurityIndex.java`): benchmark to **szereg cen** waloru, przeliczany na walutę Portfela kursem z wybranej daty (nie daty notowania — ważne w weekendy), wyrównany do pierwszego punktu Portfela, łączony dziennie `accumulated = (acc_{t−1} + 1) × (1 + delta_t) − 1` — czyli cenowy TWR; dywidendy tylko w indeksie TR.
- **Ghostfolio** (`benchmarks.service.ts`): `calculateChangeInPercentage(marketPriceAtStartDate, price)` — prosta zmiana ceny od startu.
- **Sharesight** (blog): benchmark „assumes a common investment amount and start date”.

**Symulowany benchmark „te same przepływy”.** TradingView: przy każdym zakupie w portfelu wirtualny zakup benchmarku za równoważną kwotę, przy sprzedaży — wirtualna sprzedaż po cenie benchmarku z dnia sprzedaży (lustro Operacji). **rekomendacja — wariant FundTracker (lustro przepływów zewnętrznych):**
```
units_0 = 0
on each external flow CF at date d (deposit +, withdrawal −):
    units += CF / P_bench,d               (in base currency, P converted with FX_d)
optionally on dividends of the benchmark (if price series is not total-return):
    units += units × div_ps,d / P_bench,d (reinvest)
Bench_MV_t = units × P_bench,t × FX_t
```
- Policz IRR na tych samych przepływach zewnętrznych z Bench_MV_e jako wartością końcową; porównaj `IRR_portfolio` z `IRR_benchmark` (identyczny timing). Odpowiada na „co gdybym przy każdej wpłacie kupił indeks”.
- Lustro przepływów zewnętrznych > lustro Operacji: lustro Operacji pomija bezczynną gotówkę, co faworyzuje benchmark.
- Wypłata większa niż wartość benchmarku (Portfel bił indeks) daje ujemne units → przytnij do zera i oflaguj.
## 6. Koszt nabycia: średni vs FIFO vs wskazanie partii
- **Średnia ruchoma:** „All shares are assigned the same average purchase price”, przeliczana tylko przy kupnach (PP-Cost).
- **FIFO:** „Each share retains its original purchase price. When a sale occurs, the oldest shares are sold first.”
- **Wskazanie konkretnej partii:** dopuszczalne podatkowo w wielu krajach; w Polsce dopuszczalne, gdy da się określić cenę nabycia zbywanych papierów — FIFO jest regułą domyślną (§6.2).
- PP (400 akcji, średnio 103 EUR): średnia → zrealizowany 1 650 + niezrealizowany 1 200; FIFO → 2 250 + 600; razem 2 850 w obu. „The total gain remains identical; methodology only reallocates gains between realized and unrealized.” PP liczy obie (`PerformanceIndex.getClientPerformanceSnapshot(useFifo)`).

**Przykład** (prowizje w koszcie nabycia, jak PP-Purchase: „totaling 67 EUR, including 3 EUR in fees and taxes”):

| Data | Zdarzenie | Ilość | Cena | Prowizja | Koszt partii / szt. |
|---|---|---|---|---|---|
| 2026-01-10 | kupno | 10 | 100 | 5 | 100.50 |
| 2026-03-10 | kupno | 10 | 120 | 5 | 120.50 |
| 2026-06-10 | sprzedaż | 15 | 130 | 6 | wpływ netto 1 944 |

| | FIFO | Średni koszt (110.50) |
|---|---|---|
| Koszt 15 sprzedanych | 10 × 100.50 + 5 × 120.50 = 1 607.50 | 15 × 110.50 = 1 657.50 |
| Zrealizowany P/L | 336.50 | 286.50 |
| Pozostałe 5 szt.: koszt | 602.50 | 552.50 |
| Niezrealizowany przy 130 (MV 650) | 47.50 | 97.50 |
| **Razem** | **384.00** | **384.00** |
### 6.2 Dlaczego FIFO ma znaczenie w Polsce (PIT-38)
- **Art. 24 ust. 10 ustawy o PIT** (tekst jednolity Dz.U. 2026 poz. 592; pełny cytat w [04_rynek_pl_podatki_i_brokerzy.md](./04_rynek_pl_podatki_i_brokerzy.md)): FIFO stosuje się, „jeżeli … nie jest możliwe określenie ceny nabycia zbywanych papierów wartościowych”, „odrębnie dla każdego rachunku papierów wartościowych”. FIFO jest więc regułą domyślną, nie zakazem identyfikacji: gdy broker identyfikuje sprzedawaną partię, można przyjąć jej cenę. Przykład: myfund w maju 2026 dodał wybór konkretnej transakcji kupna dla XTB (https://myfund.pl/index.php?raport=pomoc&helpID=20). **[wniosek]:** model partii musi dopuszczać wskazanie partii obok FIFO; czy FundTracker to obsłuży — decyduje biznesowy ADR. `Portfolio` w FundTracker może nie odpowiadać 1:1 rachunkowi.
- Koszty i przychody walutowe → PLN po średnim kursie NBP z ostatniego dnia roboczego przed (art. 11a; cytat w [04_rynek_pl_podatki_i_brokerzy.md](./04_rynek_pl_podatki_i_brokerzy.md)).
- Zaokrąglenie podstawy i podatku: art. 63 §1 Ordynacji podatkowej (do pełnych złotych, od 50 gr w górę) (**[niezweryfikowane]**) — dotyczy deklarowanej podstawy i podatku, nie rejestru partii. Wyjątek (broszura MF, art. 63 § 1a Ordynacji): podatek z art. 30a ust. 1 pkt 1–3 zaokrągla się do pełnych groszy w górę — szczegóły i sprzeczność z przykładami PKO BP w `./04_rynek_pl_podatki_i_brokerzy.md`.
- To nie jest porada podatkowa. **rekomendacja:** eksport PIT-38 oznaczać jako „szkic do sprawdzenia”.

**Konsekwencja:** obecna domena (`PositionState.average_buy_price`, `average_fx_rate`) to średni koszt — dobry dla „średniej ceny” w UI, ale zrealizowany P/L podatkowy musi pochodzić z rejestru partii (FIFO domyślnie) z przeliczeniem na PLN kursem NBP z D−1 **każdej partii**. Średni FX × średnia cena ≠ suma kosztów PLN per partia.
### 6.3 Model danych partii zakupu (lotów podatkowych) (**rekomendacja**)
> Terminy „partia (lot podatkowy)” i `transfer_in`/`transfer_out` są **proponowane**: [CONTEXT.md](../business/CONTEXT.md) wymienia dziś „lot” i „transfer” na liście _Unikać_. Przyjęcie wymaga zmiany CONTEXT.md przez decyzję D3 [roadmapy](../plans/02_roadmapa_funkcjonalna.md).
```
tax_lot
  id, portfolio_id, account_ref (broker account for per-account FIFO), asset_id
  open_operation_id (buy / transfer_in)
  open_date (trade date), settle_date
  qty_open        Decimal(28,10)   -- original quantity
  qty_remaining   Decimal(28,10)
  unit_cost_local Decimal          -- (price*qty + fees)/qty in instrument currency
  fx_cost         Decimal          -- rate used (broker) ; fx_cost_tax (NBP A, D-1) + fx_tax_date
  cost_pln_tax    Decimal          -- qty_open * unit_cost_local * fx_cost_tax, kept exact (not re-derived)

lot_consumption  (one row per sell × lot slice)
  sell_operation_id, tax_lot_id, qty, cost_local, cost_pln_tax,
  proceeds_local (pro-rata of net proceeds), proceeds_pln_tax, realized_pln_tax
```
1. Partie są niezmienne; sprzedaż tylko tworzy wiersze `lot_consumption` i zmniejsza `qty_remaining`.
2. Operacja kupna/sprzedaży wstecz → replay FIFO od tej daty dla rachunku i waloru. Partie to dane pochodne, odtwarzalne z Operacji (spójnie z `PortfolioLedger.rebuild`).
3. Splity korygują ilość i koszt jednostkowy każdej otwartej partii bez zmiany kosztu łącznego.
4. Prowizję sprzedaży rozkładaj pro rata na skonsumowane wycinki.
5. Przechowuj „koszt UI” (FX brokera) i „koszt podatkowy” (NBP D−1) — zawsze się nieco różnią.
```
Realized   = Σ over consumed slices (net proceeds − cost)
Unrealized = Σ over open lots (Q_remaining × P_t × FX_t − cost)
Total P/L  = Realized + Unrealized + Dividends(net) − other expenses
```
Total P/L nie zależy od metody (jak u PP). **rekomendacja:** test właściwości.
## 7. Analityka dywidend
```
Trailing (TTM) dividend per share = Σ dividends per share with ex-date in (t − 365d, t]
Dividend yield (TTM)   = TTM DPS / current price
Forward yield          = expected next-12M DPS / current price
Yield on cost (YoC)    = annual DPS / average (or lot) cost per share
Portfolio TTM income   = Σ received net dividends with pay date in (t − 365d, t]
```
- Przykład: DPS kwartalnie 0.55, cena 44, koszt 30 → yield 2.20/44 = **5.00 %**, YoC 2.20/30 = **7.33 %**.
- Ghostfolio: `dividendYieldPercent = annualize(totalDividend / averageInvestment, daysInMarket)` (`roai/portfolio-calculator.ts`) — zrealizowany dochód na średniej inwestycji, nie rynkowa stopa dywidendy.
- Pułapki: (1) YoC rośnie z ceną bez zmiany dywidendy — nie przedstawiaj jako miary zwrotu; (2) **dzień ustalenia prawa (ex-date)** decyduje o uprawnieniu i TTM DPS, **dzień wypłaty** — o dochodzie gotówkowym; (3) brutto vs netto konsekwentnie: dochód Portfela netto, stopa waloru brutto; (4) dywidendy specjalne zniekształcają TTM — **rekomendacja:** flaga `is_special`, wyłączona z prognozy; (5) splity: historyczne DPS korygować współczynnikiem splitu.
- **Prognoza (rekomendacje, od najpewniejszej):** (1) dywidendy ogłoszone a niewypłacone (znane ex-date, dzień wypłaty, kwota) × akcje posiadane na ex-date; (2) ostatnia regularna DPS × częstotliwość (kwartalna ×4 itd.) × bieżące akcje, daty = zeszłoroczne ex-date + rok; (3) TTM DPS × bieżące akcje, rozłożone na zeszłoroczne miesiące. Zawsze etykieta „szacunek”, przeliczenie po dzisiejszym FX.
- **Kalendarz:** per Pozycja przewidywane ex-date i dni wypłaty na 12 miesięcy plus pozycje otrzymane (faktyczne); słupki z (1), (2), (3) w różnym stylu.
## 8. Alokacja i rebalansowanie
```
w_i = MV_i / Σ MV          (include cash as its own class)
drift_i = w_i − target_i
absolute band: |drift_i| > b_abs               (e.g. 5 percentage points)
relative band: |drift_i| / target_i > b_rel     (e.g. 25 %)
```
- Vanguard (Jaconetti i in.): „no optimal frequency or threshold”; monitoring roczny/półroczny z rebalansowaniem przy **progach 5 %** „likely to produce a reasonable balance between risk control and cost minimization”. Cel: kontrola ryzyka, nie maksymalizacja zwrotu.
- **rekomendacja:** obie pasma; względne ważne dla małych celów (pasmo 5 pp przy celu 5 % nic nie znaczy).

**Tylko nowa gotówka (bez sprzedaży).** Cele E/B/G = 60/30/10, stan 7 000 / 2 000 / 1 000 (razem 10 000).
- Nowa gotówka 2 000: cele 7 200 / 3 600 / 1 200, niedobory 200 / 1 600 / 200 = dokładnie 2 000.
- Nowa gotówka 1 000: cele 6 600 / 3 300 / 1 100; E −400 (przeważona, 0), B 1 300, G 100. Proporcjonalnie do niedoborów: B 928.57, G 71.43. **Water-filling** (minimalizacja największego względnego niedoważenia): całe 1 000 do B; luka B 300/3 300 = 9.09 % = luka G 100/1 100 = 9.09 %.

Algorytm water-filling (**rekomendacja**, O(k log k)): (1) posortuj niedoważone klasy po luce względnej `g_i = (T_i − MV_i)/T_i` malejąco; (2) podnoś czołową grupę do poziomu następnej luki aż do wyczerpania gotówki, resztę dziel w grupie proporcjonalnie do `T_i`; (3) na końcu zaokrąglij do całych jednostek/akcji metodą największej reszty, resztkę gotówki na największą pozostałą lukę.

**Pełne rebalansowanie (kupno i sprzedaż).**
- Wektor Operacji `x_i = target_i × V − MV_i` (Σ x_i = 0 przy stałym V) — minimalny obrót dla jednego rachunku bez tarcia: turnover = Σ|x_i|/2.
- **rekomendacja (wariant brzegowy):** handluj tylko klasami poza pasmem, do krawędzi pasma (mniej Operacji) albo do celu (rzadsze rebalansowanie).
- **rekomendacja (kolejność podatkowa, PL):** zakupy najpierw z nowej gotówki, potem z przeważonych Pozycji o najmniejszym zysku zrealizowanym FIFO lub największej stracie; przed wykonaniem pokaż szacowany PIT (19 % × zysk FIFO, **[niezweryfikowane]** szczegóły stosowania stawki).
- PP (`math/Rebalancer.java`): ograniczone najmniejsze kwadraty po taksonomiach przez SVD; `FixedSumRebalancer` „minimizes the mean square error while respecting the desired rebalancing sum” — przydatne przy wielopoziomowych taksonomiach (walor w kilku klasach).
## 9. Projekcje
```
r_m  = (1 + r_annual)^(1/12) − 1                    (monthly rate equivalent to annual r)
g    = (1 + r_m)^n
FV   = PV × g + PMT × (g − 1) / r_m                  contributions at end of month (ordinary annuity)
PMT_required = (Goal − PV × g) × r_m / (g − 1)
n_required   = ln((Goal + PMT/r_m) / (PV + PMT/r_m)) / ln(1 + r_m)
```
- r_m = 0 → granica FV = PV + PMT × n. Wpłaty na początku miesiąca (annuity due) → składnik PMT × (1 + r_m).
- Przykład: PV 50 000, PMT 1 000/mies., r 6 % p.a., n 240 → r_m = 0.4868 %, g = 3.2071, FV = **613 795**; cel 600 000 wymaga PMT 969.58 lub 236.5 miesiąca.
- **rekomendacja:** stopa realna albo nominalna + inflacja; Fisher `real = (1 + nominal)/(1 + inflation) − 1`; wynik w dzisiejszych PLN.

**Monte Carlo (rekomendacja, standardowy model lognormalny):** miesięczny log-zwrot ~ N(m/12, s²/12); `s² = ln(1 + σ²/(1 + μ)²)`, `m = ln(1 + μ) − s²/2`; co miesiąc `V ← V × exp(ε) + PMT`; ≥ 10 000 ścieżek; percentyle P10/P50/P90 i P(V_n ≥ Goal). Przykład (dane z FV, μ = 6 %, σ = 15 %, 20 000 ścieżek, seed 42): P10 ≈ 315 k, **P50 ≈ 542 k**, P90 ≈ 989 k, P(≥ 600 k) ≈ **41 %**. Deterministyczne 614 k leży powyżej mediany, bo wzrost mediany jest geometryczny (≈ μ − σ²/2) — główna lekcja dla użytkownika. Zastrzeżenia do wyświetlenia: (1) parametry to zgadywanie, historyczne μ mają duży błąd standardowy; (2) grube ogony i klastrowanie zmienności — model lognormalny i.i.d. zaniża krachy (alternatywa: block bootstrap historycznych zwrotów miesięcznych); (3) korelacje między klasami niestabilne; (4) inflację, opłaty i podatki modelować jawnie albo stopy netto; (5) przy wypłatach dominuje ryzyko sekwencji zwrotów; (6) to nie prognozy. Brak jednego standardu; mapowanie lognormalne to algebra podręcznikowa; źródło pierwotne praktyki MC nie było pobierane (**[niezweryfikowane]**) — funkcja w UI jako ilustracyjna. Inżynieryjnie: `float` (NumPy lub `random`), stałe ziarno per żądanie, wektoryzacja, limit ścieżki × miesiące (np. 20 000 × 600), nigdy `Decimal`.
## 10. Wskazówki numeryczne i inżynieryjne
### 10.1 Granica Decimal / float (rekomendacja)
| Domena | Typ | Powód |
|---|---|---|
| Rejestr: ilości, ceny, kwoty, prowizje, kursy FX, koszt nabycia, zrealizowany P/L, salda gotówki | `Decimal` (ADR-0010), `NUMERIC` w Postgres | Dokładne sumy; muszą się uzgadniać z wyciągiem brokera |
| Dzienny wektor MV | `Decimal`, kwantyzacja do 0.01 waluty bazowej **tylko do wyświetlania**; do obliczeń bez kwantyzacji | Brak dryfu od zaokrągleń przed dzieleniem |
| Czynniki (1 + r_t), indeks skumulowany, TWR | `Decimal` (prec 28) lub `float` | 28 cyfr ≫ precyzja danych; **rekomendacja:** `Decimal` dla TWR i indeksu (przechowywane i sumowane), float dla statystyk |
| Solver IRR, zmienność, Sharpe, β, VaR, korelacja, Monte Carlo | `float` (lub NumPy) | Iteracyjne/statystyczne, `sqrt`, `ln`, potęgi ułamkowe; `Decimal` ma `ln()`, `exp()`, `sqrt()`, `**` (docs: potęga „will be inexact unless y is integral”), ale jest wolny i bez realnej korzyści |
| Wyjście API wskaźników i procentów | `Decimal` kwantyzowany (np. 6 miejsc dla stóp, 2 dla %) | Stabilny JSON i złote testy |

Przejście: `float(d)` na wejściu do statystyk, `Decimal(repr(f))` lub `Decimal(str(f))` na wyjściu. Nigdy `Decimal(f)` z floata — importuje szum binarny (0.1000000000000000055…).
### 10.2 Polityka zaokrągleń (rekomendacja)
- Domyślny kontekst Pythona: `prec=28, rounding=ROUND_HALF_EVEN` (docs). Zaokrąglaj tylko na granicy prezentacji i granicy prawnej, nigdy w krokach pośrednich.
- Pieniądze do wyświetlania: `quantize(Decimal("0.01"), ROUND_HALF_UP)`; obliczenia w pełnej skali.
- Ceny: skala ze źródła (niektóre fundusze 4–6 miejsc). Ilości: skala ≥ 8 (ułamkowe akcje, krypto).
- Podatek: przeliczenia PLN per Operacja do grosza (jak raportują brokerzy), sumy PIT-38 do pełnych złotych (§6.2, **[niezweryfikowane]** artykuł).
- Tryb zaokrąglenia jawnie w każdym `quantize`; nie polegaj na globalnym kontekście — `decimal.localcontext()` w czystych funkcjach domeny.
### 10.3 Brakujące ceny, weekendy, święta (rekomendacja na bazie PP i GIPS)
- **Forward-fill** ostatniego zamknięcia w dni nienotowane. GIPS 2.A.21 dopuszcza „the last available historical price” jako wartość godziwą (z obowiązkiem późniejszej oceny różnicy). PP używa notowania „Close”; jego benchmark bierze cenę ważną na datę, FX z daty kalendarzowej (`SecurityIndex.convert`).
- Licznik nieaktualności per cena (`price_date` vs `valuation_date`); powyżej N dni roboczych (np. 5) Pozycja `stale` w API. Ghostfolio oznacza `hasErrors`, gdy brak ceny na start lub koniec.
- FX w weekendy: forward-fill ostatniego fixingu (NBP publikuje tylko w polskie dni robocze).
- Wektor na **każdy dzień kalendarzowy** (proste złączenia, dokładne daty przepływów) z flagą `is_trading_day` per giełda; dni nienotowane wyłączone ze statystyk ryzyka (§4), jak `filterReturnsForVolatilityCalculation` w PP.
- Walor bez ceny przed pierwszą Operacją: wycena po cenie Operacji tego dnia.
- Brak ceny na koniec okresu przy niezerowej Pozycji: nie wyceniaj po cichu na zero — ostrzeżenie `data_quality` albo odmowa.
### 10.4 Wydajność codziennego przeliczania (rekomendacja)
Tabele snapshotów (pochodne, odtwarzalne):
```
portfolio_daily(portfolio_id, date,
  mv_base, cash_base, ext_in, ext_out, income, fees, taxes,
  r_day, twr_index /* Π(1+r) */, cum_ext_in, cum_ext_out, data_quality)
position_daily(portfolio_id, asset_id, date, qty, price_local, fx, mv_base, flow_in, flow_out, r_day, twr_index)
```
- TWR dowolnego okresu O(1): `R(s, e) = twr_index_e / twr_index_s − 1`. Zysk dowolnego okresu O(1): `MV_e − MV_s − (cum_in_e − cum_in_s) + (cum_out_e − cum_out_s)`.
- **Inwalidacja:** wstawienie/zmiana/usunięcie Operacji z datą d albo korekta ceny lub FX z daty d → usuń wiersze z datą ≥ d dla Portfela (i waloru) i przelicz od wiersza d − 1. Normalnie append-only (nocne zadanie dopisuje dzisiejszy wiersz).
- IRR nie da się cache'ować prefiksowo — potrzebuje przepływów z okresu oraz MV_s i MV_e: O(liczba przepływów) per żądanie, tanio.
- Kroczące metryki ryzyka na żądanie z `r_day` w oknie (O(n), n ≤ ok. 1 300 dla 5Y); cache po `(portfolio_id, period, last_snapshot_date)`.
- Odpowiedzialność: przebudowa snapshotu w serwisie wewnątrz `repo.transaction()` (ADR-0001); nocne zadanie przez `entrypoints.py` z `session_scope()` (ADR-0002) — por. [01_backend-architecture.md](../technical/backend/01_backend-architecture.md).
### 10.5 Złote testy (rekomendacja)
| Test | Oczekiwane |
|---|---|
| Przykład XIRR z dokumentacji Excel (§1.4) | 0.373362535 ± 1e-8 |
| PP IRR, pojedyncze kupno: −66 EUR, +111.76 po 255 d | 1.1253 ± 1e-4 |
| PP annualizacja: 30 % w 730 d | 0.140175 |
| Wikipedia, przykład Modified Dietz | 1.20 dokładnie |
| Wikipedia, przykład TWR (+100 %, potem −25 %) | 0.50 |
| TWR trzydniowy z §1.2 | 0.03 dokładnie (Decimal) |
| Modified Dietz na tych samych danych (§1.3) | 0.027209… |
| IRR z wieloma pierwiastkami (−100, +230, −132) | solver zwraca `irr_ambiguous` albo 0.10 / 0.20 z flagą |
| Brak zmiany znaku (same ujemne przepływy) | `None`, kod `irr_undefined` |
| FIFO vs średni (§6) | zrealizowany 336.50 / 286.50; razem 384.00 w obu |
| Dekompozycja FX (§3) | 0.045 = 0.10 − 0.05 − 0.005 |
| Okres krótszy niż 365 d | `annualized is None` |

**Testy właściwości** (Hypothesis, jeśli dodany — decyzja o zależności): wpłata w dowolnej dacie nie zmienia TWR, gdy MV skaluje się razem z nią; bez przepływów zewnętrznych TWR = IRR (okresu, de-annualizowany); Total P/L identyczny dla FIFO i średniego kosztu; `R(a, c) = (1 + R(a, b))(1 + R(b, c)) − 1` (łączenie); drawdown nigdy ujemny; suma MV Pozycji = MV Portfela minus gotówka. **Walidacja krzyżowa:** eksport przykładowego Portfela do Portfolio Performance (import CSV) i porównanie TTWROR, IRR, MDD i zysków zrealizowanych FIFO. Oczekiwane drobne różnice ze źródeł FX (EBC vs NBP) i skalowania zmienności PP (§4).
## 11. Pytania otwarte (do weryfikacji przed implementacją)
1. Art. 63 Ordynacji podatkowej — czytane tylko źródła wtórne (art. 24 ust. 10, 11a, 30b ustawy o PIT zacytowano z tekstu jednolitego Dz.U. 2026 poz. 592 w [04_rynek_pl_podatki_i_brokerzy.md](./04_rynek_pl_podatki_i_brokerzy.md)).
2. Bieżąca stopa referencyjna NBP i dostępność danych POLSTR/WIRON, w tym licencja GPW Benchmark na redystrybucję w aplikacji.
3. Czy `Portfolio` w FundTracker = jeden rachunek maklerski (FIFO per rachunek).
4. Czy dodać typy Operacji `transfer_in`/`transfer_out`, `fee`, `tax`, `interest`, `split` — wszystkie potrzebne do poprawnego TWR i partii.
5. Skalowanie zmienności w PP (`Risk.Volatility`: × n) — potwierdzić w UI PP przed deklarowaniem zgodności.
## Źródła
Dostęp: 2026-10-01.
- GIPS 2020: https://www.gipsstandards.org/wp-content/uploads/2021/03/2020_gips_standards_firms.pdf ; Handbook: https://www.gipsstandards.org/wp-content/uploads/2021/04/gips-standards-handbook-firms.pdf ; benchmarki: https://www.gipsstandards.org/wp-content/uploads/2023/08/gs_benchmarks_firms.pdf
- Podręcznik PP (TWR, MWR, okres, koszt, wartość zakupu, ceny, widok Performance): https://help.portfolio-performance.info/en/concepts/performance/time-weighted/ , https://help.portfolio-performance.info/en/concepts/performance/money-weighted/ , https://help.portfolio-performance.info/en/concepts/reporting-period/ , https://help.portfolio-performance.info/en/concepts/cost-methodology/ , https://help.portfolio-performance.info/en/concepts/purchase-value/ , https://help.portfolio-performance.info/en/concepts/historical-prices/ , https://help.portfolio-performance.info/en/reference/view/reports/performance/
- Kod PP, commit `6076b449` (2026-09-30): https://github.com/portfolio-performance/portfolio/tree/master/name.abuchen.portfolio/src/name/abuchen/portfolio ; kod Ghostfolio, commit `347cd06a` (2026-10-01): https://github.com/ghostfolio/ghostfolio
- Sharesight: https://help.sharesight.com/performance_calculation_method/ , https://help.sharesight.com/components-return/ ; Excel XIRR: https://support.microsoft.com/en-us/office/xirr-function-de1242ec-6477-445b-b11b-a303ad9adc9d
- Sharpe 1994 (DOI 10.3905/jpm.1994.409501): https://web.stanford.edu/~wfsharpe/art/sr/sr.htm ; Sharpe 1966: https://doi.org/10.1086/294846 ; Sortino & Price 1994: https://doi.org/10.3905/joi.3.3.59 ; Jensen 1968: https://doi.org/10.1111/j.1540-6261.1968.tb00815.x ; Lo 2002: https://doi.org/10.2469/faj.v58.n4.2453
- Karnosky & Singer 1994: https://rpc.cfainstitute.org/research/foundation/1994/global-asset-management-and-performance-attribution ; Vanguard, rebalansowanie (lustro PDF strony trzeciej): https://www.aaii.com/files/journal/pdf/best-practices-for-portfolio-rebalancing.pdf
- TradingView, benchmark: https://www.tradingview.com/support/solutions/43000756149-what-is-a-benchmark-and-how-does-benchmarking-work/ ; Python `decimal`: https://docs.python.org/3/library/decimal.html
- Wikipedia (wtórne): https://en.wikipedia.org/wiki/Modified_Dietz_method , https://en.wikipedia.org/wiki/Time-weighted_return ; ustawa o PIT, tekst jednolity Dz.U. 2026 poz. 592 — patrz [04_rynek_pl_podatki_i_brokerzy.md](./04_rynek_pl_podatki_i_brokerzy.md)

## Luki i niepewności
- Art. 63 Ordynacji — tylko źródła wtórne; szczegóły stosowania stawki 19 % niezweryfikowane. Art. 24 ust. 10, 11a, 30b ustawy o PIT: tekst jednolity Dz.U. 2026 poz. 592, cytaty w [04_rynek_pl_podatki_i_brokerzy.md](./04_rynek_pl_podatki_i_brokerzy.md).
- Stopa referencyjna NBP 3.75 % (lipiec 2026), harmonogram wygaszania WIBOR, wybór POLSTR — źródła wtórne; nbp.pl blokował dostęp. Przydatność €STR/SOFR jako rf — niezweryfikowana.
- Brak źródła pierwotnego dla VaR (Jorion — wydanie/strony niezweryfikowane) i praktyki Monte Carlo; atrybucja rozszerzenia reguły Kartezjusza (Laguerre) niezweryfikowana.
- Skalowanie zmienności w PP (× n) to odczyt kodu, niepotwierdzony w UI. Investopedia niedostępna; dokumentacja atrybucji Eagle i wątek forum PP cytowane wtórnie, bez URL w materiale.
