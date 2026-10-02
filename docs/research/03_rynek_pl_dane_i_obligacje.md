---
id: research-pl-market-data-bonds
status: current
type: mixed
scope: research/pl-market
last_reviewed: 2026-10-02
---

# Skąd brać dane rynkowe dla polskiego inwestora i jak wyceniać obligacje skarbowe?
> **Dokument L4 (dowód).** Stan na 2026-10-01/02. Nienormatywny — rekomendacje stąd stają się obowiązujące dopiero przez ADR lub plan. Append-only: nie poprawiamy, dopisujemy nowe badanie i link do następcy.

Odbiorca: implementujący wycenę Walorów w `backend/app/modules/assets/` i `portfolios/`. Kontekst: [04_assets_module.md](../technical/backend/04_assets_module.md), [05_portfolios_module.md](../technical/backend/05_portfolios_module.md), słownik: [CONTEXT.md](../business/CONTEXT.md).

**Oznaczenia.** **[wniosek]** = wniosek autora; **[niezweryfikowane]** = tylko snippet wyszukiwarki / strona trzecia; **rekomendacja** = rada inżynierska. Wszystkie testy `curl` wykonano 2026-10-02 z kontenera badania.

## 0. Podsumowanie

| Pytanie | Odpowiedź |
|---|---|
| Kursy walut do podatku | NBP Web API, tabela A (kurs średni), dzień roboczy poprzedzający Operację. Darmowe, bez klucza, historia od 2002-01-02 |
| Notowania GPW (akcje, ETF) | Yahoo (`PKO.WA`, `ETFBW20TR.WA` działają) — dziś adapter `backend/app/infrastructure/market_data/yahoo.py`. Stooq CSV od marca 2026 wymaga klucza API. Oficjalne dane GPW są płatne, a redystrybucja kosztuje 9× cenę |
| Obligacje skarbowe detaliczne | **Nie z rynku.** Wartość liczyć z listu emisyjnego (wzory w §2) i sprawdzać z „Tabelami odsetkowymi” obligacjeskarbowe.pl |
| CPI (COI/EDO/ROS/ROD) | Nie trzeba go liczyć: stopa na kolejny okres jest **ogłaszana** przez MF. **rekomendacja:** przechowywać ogłoszoną stopę dla każdego okresu i serii |
| Wydarzenia korporacyjne | GPW/KDPW/ESPI. Brak darmowego API maszynowego (§3) |

## 1. Źródła danych rynkowych

### 1.1 Tabela źródeł

| Klasa waloru / dana | Źródło | Koszt | Dostęp | Licencja / ToS | Historia | Kadencja | Niezawodność / uwagi |
|---|---|---|---|---|---|---|---|
| Akcje i ETF GPW, NewConnect | Yahoo Finance (sufiks `.WA`) | darmowe | nieoficjalne JSON (`query1.finance.yahoo.com/v8/finance/chart/…`) / `yfinance` | brak publicznej licencji na dane, użytek osobisty **[wniosek]** | `PKO.WA`: `firstTradeDate` = 1100073600 (2004-11-10) | EOD + intraday | Test 2026-10-02: `PKO.WA` → `exchangeName":"WSE","currency":"PLN"`; `ETFBW20TR.WA` → `instrumentType":"ETF"`. NewConnect nie testowano **[niezweryfikowane]** |
| Akcje GPW (wszystkie rynki) | Stooq CSV `https://stooq.pl/q/d/l/?s=<sym>&i=d` | darmowe z kluczem | CSV | „As March 2026, Stooq requires an API key for data downloads” (pandas-datareader #1012, 2026-04-13) | dekady **[niezweryfikowane]** | EOD | Z kontenera: `Recv failure: Connection reset by peer` (stooq.pl i stooq.com). Klucz przez `get_apikey` z CAPTCHA, dzienny limit wywołań, paczki bulk `stooq.com/db/h/` **[niezweryfikowane]** (snippet) |
| Dane oficjalne GPW | GPW „Cennik Usług Informacyjnych” od 2025-01-01 | płatne | e-mail/https/SFTP | „Wyniki sesji (dane GPW)” 3 500 zł netto/rok; „Wyniki sesji (dane GPW i BondSpot)” 7 600 zł; „Dane referencyjne i notowania instrumentów dłużnych (dane GPW)” 1 900 zł. Przypis 3: dalsze rozpowszechnianie elektroniczne = **„dziewięciokrotności stawki”** | historyczne za dopłatą | po sesji | Dla jednoosobowego trackera self-hosted to przesada **[wniosek]** |
| Catalyst (obligacje korporacyjne, skarbowe hurtowe) | GPW/BondSpot (płatne, j.w. poz. 15–16, 26); Yahoo — nie sprawdzono | płatne / ? | — | jak wyżej | — | EOD | **[niezweryfikowane]**, czy Yahoo lub Stooq pokrywa Catalyst |
| Fundusze TFI (wycena JU) | strony TFI, analizy.pl, Stooq | darmowe | HTML/CSV, scraping | ToS poszczególnych serwisów nie sprawdzono | — | dzienna wycena | **[niezweryfikowane]**. myfund importuje TFI i Analizy.pl ([01_myfund.md](./competitors/01_myfund.md)) |
| Akcje i ETF zagraniczne | Yahoo | darmowe | j.w. | j.w. | długa | EOD | Działa dziś w `yahoo.py:60-64` (`yf.Ticker(...).history`) |
| Kursy walut | **NBP Web API** `https://api.nbp.pl` | darmowe | JSON/XML, REST | brak warunków licencyjnych na stronie API (WebFetch 2026-10-02) | „dla kursów walut – od 2 stycznia 2002 r.” | tabela A: dni robocze | §1.2 |
| Złoto | NBP `api/cenyzlota` | darmowe | JSON | j.w. | „dla cen złota – od 2 stycznia 2013 r.” | dni robocze | Test: `cenyzlota/2026-09-25` → `cena 528.37` (PLN/g); `2012-12-31` → 404 |
| Kryptowaluty | giełdy (API), Yahoo `BTC-USD` | darmowe | REST | ToS giełd | — | 24/7 | Nie badano. **[niezweryfikowane]** |
| CPI | GUS: BDL API `https://bdl.stat.gov.pl/api/v1/` (HTTP 200), DBW `api-dbw.stat.gov.pl` (302) | darmowe | JSON | — | — | miesięcznie | Do obligacji niepotrzebne, bo MF ogłasza stopę (§2.3). Przydatne do „zwrotu realnego” |
| Stopa referencyjna NBP | `https://static.nbp.pl/dane/stopy/stopy_procentowe.xml` | darmowe | XML | — | od daty publikacji pliku | przy zmianie | Test: `data_publikacji="2026-03-05"`, stopa referencyjna `oprocentowanie="3,75"`, `obowiazuje_od="2026-03-05"` |
| WIBOR / WIRON | GPW Benchmark | płatne | e-mail/https | Cennik GPW poz. 19 „Stawki referencyjne WIBOR, WIBID i WIRON (dane GPWB)” 4 600 zł netto/rok. WIRON po sesji, WIBOR „następnego Dnia Roboczego przed godziną 11:00” | — | dziennie | Potrzebne tylko do obligacji zmiennokuponowych z Catalyst |
| POLSTR | GPW Benchmark | ? | strona administratora | ? | od 2025-06-02 | dziennie | KS NGR w listopadzie–grudniu 2024 wybrał WIRF-; ostateczna decyzja o POLSTR jako następcy WIBOR: 30.01.2025. WIBOR: komunikat GPW Benchmark z 18.05.2026 — O/N nie jest opracowywany od 2026-10-01, ostatni fixing 1M/3M/6M 31.12.2036 **[niezweryfikowane]** (źródła wtórne: komunikaty banków, np. citibank.pl; gpwbenchmark.pl nie pobrano — 404) |

### 1.2 NBP Web API — szczegóły do implementacji

| Element | Wartość | Źródło / weryfikacja |
|---|---|---|
| Kurs jednej waluty z dnia | `GET https://api.nbp.pl/api/exchangerates/rates/{table}/{code}/{date}/?format=json` | api.nbp.pl. Test: `rates/a/usd/2026-09-25` → `{"no":"187/A/NBP/2026","effectiveDate":"2026-09-25","mid":3.8404}` |
| Zakres dat | `…/rates/{table}/{code}/{startDate}/{endDate}/` | api.nbp.pl |
| Ostatnie N | `…/rates/{table}/{code}/last/{topCount}/` | api.nbp.pl |
| Całe tabele | `…/exchangerates/tables/{table}/{date}/` | test: `tables/c/2026-09-25` → `tradingDate 2026-09-24`, `effectiveDate 2026-09-25`, `bid/ask` |
| Tabele | A, B: kursy **średnie** (`mid`); C: kupna/sprzedaży (`bid`, `ask`) | api.nbp.pl |
| Publikacja | A: „w każdy dzień roboczy, między godziną 11:45 a 12:15”; B: „w każdą środę, między godziną 11:45 a 12:15” (gdy środa wolna — dzień wcześniej); C: dni robocze 7:45–8:15 | nbp.pl „Informacja o terminach publikacji kursów walut” (wynik wyszukiwarki, 2026-10-02) **[niezweryfikowane]**, ale B potwierdza test: `rates/b/afn` → `effectiveDate 2026-09-30` (środa) |
| Dzień bez notowań | HTTP 404 `NotFound - Brak danych` (test 2026-09-27, niedziela) | test |
| Maks. zakres zapytania | Dokumentacja: „pojedyncze zapytanie nie może obejmować przedziału dłuższego, niż 93 dni”. **Faktycznie** 2025-01-01…2025-12-31 → 200; 2025-01-01…2026-03-01 → `400 BadRequest - Przekroczony limit 367 dni` | rozbieżność dokumentacji i API. **rekomendacja:** paczki ≤ 93 dni (zgodne z dokumentacją) |
| Historia | od 2002-01-02 (test: `2001-12-28` → 404, `2002-01-02` → `1/A/NBP/2002`, `mid 3.9480`) | api.nbp.pl + test |
| HTTPS | „Od 1 sierpnia 2025 r. cała komunikacja z API.nbp.pl musi odbywać się za pośrednictwem protokołu HTTPS.” | api.nbp.pl |

**rekomendacja (algorytm „kurs D-1” do PIT, art. 11a — patrz dokument podatkowy `04_rynek_pl_podatki_i_brokerzy.md`):** dla daty przychodu/kosztu `t` weź pierwszą tabelę A z `effectiveDate < t`, cofając się po 404 (weekendy, święta). Zapisz w Operacji: kurs, numer tabeli (`no`), `effectiveDate`. Numer tabeli jest dowodem dla urzędu. Obecnie `yahoo.py:52-53` bierze kurs `f"{from_code}{to_code}=X"` z Yahoo — do wyceny bieżącej wystarczy, do podatku nie.

### 1.3 Płatne API z pokryciem GPW (XWAR)

| Dostawca | Pokrycie GPW | Cena (stan 2026-10-02) | Status |
|---|---|---|---|
| EODHD | Giełda `WAR` (MIC XWAR), tickery `PKO.WAR`, „613 active tickers”; pobranie pełnej listy wymaga pakietu „All World Extended package or higher” | Sandbox 0 USD (20 wywołań/dzień, 1 rok historii); Historian 19,99 USD/mies.; Active trader 29,99; Equity analyst 59,99; All-in-one 99,99 | ceny z eodhd.com/pricing (WebFetch); pokrycie z eodhd.com/exchange/WAR (snippet) **[niezweryfikowane]** |
| Twelve Data | strony `twelvedata.com/markets/.../stock/gpw/...` istnieją | Basic free; Grow 29 USD/mies.; Pro 99; Ultra 329 | snippet **[niezweryfikowane]**; nie ustalono, który plan obejmuje GPW |
| Alpha Vantage | nie ustalono | — | brak danych |
| Financial Modeling Prep | nie ustalono pokrycia WSE | Starter 29 USD/mies., Premium 69 USD/mies. | snippet apis.io **[niezweryfikowane]** |

**rekomendacja:** port `MarketDataProvider` (`backend/app/core/market_data.py:50-73`) zostaje; dodać adaptery: `NbpFxProvider` (podatek i wycena FX), `StooqProvider` (z kluczem z `.env`) jako zapas dla GPW, ręczne/CSV ceny TFI. Każdy kurs zapisany z `source` i `fetched_at`.

## 2. Obligacje skarbowe detaliczne (oszczędnościowe)

Źródło: strony ofert obligacjeskarbowe.pl pobrane 2026-10-01 (oferta **październik 2026**, sprzedaż 01.10.2026–31.10.2026) oraz listy emisyjne nr 97/2026 (TOS1029), 98/2026 (COI1030) i 99/2026 (EDO1036) z 2026-09-21, pobrane 2026-10-02.

### 2.1 Parametry i oferta (październik 2026)

| Typ | Seria X.2026 | Zapadalność | Nominał / cena | Oprocentowanie | Kapitalizacja / wypłata | Opłata za przedterminowy wykup (emisje od 2024-09-01) | Cena zamiany |
|---|---|---|---|---|---|---|---|
| OTS | OTS0127 | 3 mies. | 100 zł | 2,00% stałe; „Odsetki: 0,50 zł” | wypłata przy wykupie | przy wykupie przed terminem „klient otrzymuje wpłacone środki w pełnej wysokości” (bez odsetek) | 100,00 zł |
| ROR | ROR1027 | 1 rok | 100 zł | 1. miesiąc 4,00%; dalej „stopa referencyjna NBP+0,00%” | brak; wypłata co miesiąc | 0,50 zł; w 1. okresie ≤ narosłe odsetki, od 2. okresu „w pełnej wysokości z należności do wykupu (również w przypadku gdy wartość narosłych odsetek … jest mniejsza” — wypłata może spaść poniżej 100 | 99,90 zł |
| DOR | DOR1028 | 2 lata | 100 zł | 1. miesiąc 4,15%; dalej „stopa referencyjna NBP+0,15%” | brak; co miesiąc | 0,70 zł; reguła jak ROR (1. okres ≤ narosłe, od 2. okresu w pełnej wysokości) | 99,90 zł |
| TOS | TOS1029 | 3 lata | 100 zł | 4,40% stałe; wierzytelność w dniu wykupu 113,79 zł (list 97/2026 ust. 14) | roczna kapitalizacja; wypłata przy wykupie | 1,00 zł (0,70 zł dla emisji do 2024-08-31) | 99,90 zł |
| COI | COI1030 | 4 lata | 100 zł | 1. rok 4,75%; dalej „marża 1,50% + inflacja” | brak; odsetki co roku | 2,00 zł (0,70 zł do 2024-08-31) | 99,90 zł |
| EDO | EDO1036 | 10 lat | 100 zł | 1. rok 5,35%; dalej „marża 2,00% + inflacja” | roczna kapitalizacja; przy wykupie | 3,00 zł (2,00 zł do 2024-08-31) | 99,90 zł |
| ROS | ROS1032 | 6 lat | 100 zł | 1. rok 5,00%; dalej „marża 2,00% + inflacja” | roczna kapitalizacja; przy wykupie | 2,00 zł (0,70 zł do 2024-08-31) | — |
| ROD | ROD1038 | 12 lat | 100 zł | 1. rok 5,60%; dalej „marża 2,50% + inflacja” | roczna kapitalizacja; przy wykupie | 3,00 zł (2,00 zł do 2024-08-31) | — |

- **Symbol:** typ + miesiąc + rok wykupu („EDO … 09 – miesiąc wykupu … 36 – rok wykupu”). Seria wyznacza parametry, ale **termin wykupu i początek okresów liczy się od dnia zakupu**: list 99/2026 — „o terminach wykupu od dnia 1 do dnia 31 października 2036 r.”; ust. 14 pkt 1 — odsetki „poczynając od dnia jej sprzedaży”. **rekomendacja:** Pozycja obligacji = (seria, data zakupu, liczba sztuk), nie sama seria.
- **ROS/ROD (rodzinne):** „przeznaczone są wyłącznie dla beneficjentów programu realizowanego na mocy ustawy z dnia 11 lutego 2016 r. o pomocy państwa w wychowywaniu dzieci” (800+). Limit zakupu = „suma miesięcznych kwot świadczenia od początku jego przyznania … pomniejszona o wartość poprzednio zakupionych Rodzinnych Obligacji Skarbowych”.
- **Okno przedterminowego wykupu (EDO1036, COI1030, TOS1029):** nie wcześniej niż „po upływie siedmiu dni kalendarzowych od dnia sprzedaży” i nie później niż „dwadzieścia dni kalendarzowych przed dniem wykupu”. Starsze COI: jeden miesiąc (list 60/2012 ust. 20). Odsetki naliczane „do piątego dnia roboczego włącznie, następującego po dniu złożenia dyspozycji”. „Do dni roboczych … nie wlicza się sobót.”
- **IKE/IKZE:** obligacje kupione przez PKO BP „mogą być wykorzystane jako forma lokaty oszczędności w ramach … (IKE) i … (IKZE)”. Przy wypłacie z IKE/IKZE „potrącenia nie dokonuje się” (list 99/2026 ust. 6, ust. 26 pkt 5).
- **Agent emisji:** PKO BP i Pekao. Obligacji nie można przenieść między rejestrami agentów (ust. 34). **[wniosek]:** dla FundTrackera to dwa różne rachunki.
- **Niespójność źródła:** strona OTS pokazuje „Okres oprocentowania: 01.09.2026-01.12.2026” przy serii OTS0127 sprzedawanej w październiku. Wygląda to na nieaktualny tekst strony. Wiążący jest list emisyjny (OTS nie pobrano).

### 2.2 Wzory z listów emisyjnych (oznaczenia jak w listach)

`N` = 100 zł; `r_k` = stopa k-tego okresu; `a_k` = „rzeczywista liczba dni od pierwszego dnia … okresu odsetkowego, z włączeniem tego dnia, do dnia „d” z wyłączeniem dnia „d””; `ACT` = „rzeczywista liczba dni w danym okresie odsetkowym z włączeniem pierwszego dnia … oraz wyłączeniem ostatniego dnia”; `b` = opłata. **[wniosek]:** to konwencja actual/actual **w obrębie okresu odsetkowego** (365 albo 366 dni zależnie od tego, czy okres obejmuje 29 lutego), a nie actual/365.

| Typ | Wartość w dniu wykupu | Przedterminowy wykup w dniu d (okres k) | Dolne ograniczenie |
|---|---|---|---|
| EDO (list 99/2026, zał. 2–3) | `W = N·Π_{k=1..10}(1+r_k)`, zaokr. do 0,01 tylko na końcu | `WP_k = N·Π_{j<k}(1+r_j)·(1 + r_k·a_k/ACT) − b`; „pomniejszana o kwotę narosłych odsetek, ale nie wyższą niż 3,00 zł” | „dla WPk < 100 WPk = 100” |
| TOS (list 97/2026, zał. 1–2) | `W = N·(1+r)^3` = 113,79 | `WP_k = N_{k−1}·(1 + r·a_k/ACT) − b`, gdzie `N_{k−1}` jest „zaokrąglona do dwóch miejsc po przecinku” (N0=100, N1=100(1+r), N2=100(1+r)²); opłata ≤ 1,00 zł i ≤ narosłe odsetki | „W przypadku gdy WPk < 100 przyjmuje się WPk = 100” |
| COI (list 98/2026, zał. 2–3) | odsetki roczne `O = N·r`, „zaokrąglone do dwóch miejsc po przecinku”, wypłacane „w ostatnim dniu danego okresu odsetkowego” | `WP = N·(1 + r·a/ACT) − b`; w 1. okresie b ≤ narosłe odsetki (max 2,00 zł), **od 2. okresu b = 2,00 zł zawsze** | „WP = 100 – w pierwszym okresie odsetkowym” (tylko w 1. okresie; później WP może spaść poniżej 100 — strona COI: opłata „również w przypadku gdy wartość narosłych odsetek jest mniejsza od wartości opłaty”) |
| Stopa COI/EDO/ROS/ROD, okres ≥ 2 | `r = i + m`; i = „stopa wzrostu cen towarów i usług konsumpcyjnych, przyjmowana dla 12 miesięcy i ogłaszana przez Prezesa Głównego Urzędu Statystycznego w miesiącu poprzedzającym pierwszy miesiąc danego okresu odsetkowego”; „w przypadku gdy i < 0 przyjmuje się że i = 0” | — | i ≥ 0 |

**Uwaga o zaokrągleniach [wniosek]:** EDO zaokrągla tylko wynik końcowy (iloczyn bez zaokrągleń pośrednich), a TOS zaokrągla `N_{k−1}` do groszy. Należy to zaimplementować dosłownie, osobną funkcją dla każdego typu, i sprawdzić z Tabelami odsetkowymi.

### 2.3 Algorytm dziennej wyceny (rekomendacja)

Wejście dla Pozycji: `typ`, `seria`, `data_zakupu P`, `ilość`, lista ogłoszonych stóp `r_1..r_n` (r_1 z listu emisyjnego, kolejne z obligacjeskarbowe.pl lub gov.pl/finanse/dlug-publiczny; „Ogłoszona stopa procentowa nie ulega zmianie”), `opłata b` (z listu danej serii, zależnie od daty emisji), `rachunek` (zwykły / IKE / IKZE).

```
okresy: start_k = P + (k-1) lat, end_k = P + k lat     (EDO/COI/TOS/ROS/ROD; roczne)
dla dnia d (start_k <= d < end_k):
  a   = (d - start_k).days ;  ACT = (end_k - start_k).days      # 365 lub 366
  EDO/TOS/ROS/ROD: base = N * Π_{j<k}(1+r_j)  [TOS: round2(base)]
                   brutto = base * (1 + r_k*a/ACT)
  COI:             brutto = N * (1 + r_k*a/ACT)  (+ odsetki za okresy <k już wypłacone jako Operacja „odsetki”)
  narosłe = brutto - N_aktualne_niewypłacone
  wartość „gdybym dziś zamknął”:
      opłata = min(b, narosłe)   [EDO, TOS, ROS, ROD, COI k=1]
      opłata = b                 [COI k>=2]
      przed_podatkiem = brutto - opłata
      if typ != COI or k == 1: przed_podatkiem = max(przed_podatkiem, 100)   # floor wg tabeli 2.2
      podatek = 19% * max(przed_podatkiem - 100, 0), zaokr. do grosza (rachunek zwykły; reguła — §2.4); 0 na IKE/IKZE
  ROR/DOR: odsetki miesięczne = N * r_m/12 ; narosłe w miesiącu = N * r_m/12 * a/ACT_m   [wniosek, §2.4]
      opłata = min(b, narosłe)  [k == 1]  ;  opłata = b  [k >= 2, bez dolnego ograniczenia 100]
      przed_podatkiem = N + narosłe - opłata          # ROR0623: 100 + 0,18 - 0,50 = 99,68
```

- **„Wartość rynkowa” w UI [wniosek]:** dwie liczby: `brutto` (wartość nominalna + narosłe odsetki; tak pokazuje to Tabela odsetkowa) oraz „wartość likwidacyjna netto” (po opłacie i podatku). Z drugiej liczby liczy się realny wynik.
- **Który odczyt CPI:** list mówi tylko „ogłaszana … w miesiącu poprzedzającym pierwszy miesiąc danego okresu”. Rynek przyjmuje, że chodzi o odczyt za miesiąc X−2, publikowany w X−1 **[niezweryfikowane]** (nie znaleziono pierwotnego potwierdzenia, czy chodzi o szybki szacunek, czy odczyt finalny). **rekomendacja:** nie wyliczać `i` z danych GUS. Pobierać **ogłoszoną stopę okresu** dla serii (strona oferty: „Okres oprocentowania” + Tabela odsetkowa) i zapisywać ją jako fakt. CPI z GUS służy wyłącznie do szacunku przyszłych okresów („prognoza”, wyraźnie oznaczona).
- **Podatek (19%):** od odsetek z obligacji — art. 30a ust. 1 pkt 2 ustawy o PIT (szczegóły w `04_rynek_pl_podatki_i_brokerzy.md`). Zaokrąglenie podatku — patrz sprzeczność w §2.4. COI: podatek przy każdej rocznej wypłacie odsetek. EDO/TOS/ROS/ROD: przy wykupie lub przedterminowym wykupie, od (narosłe − opłata).

### 2.4 Złote dane testowe (golden tests) z przykładów MF/PKO BP — sprawdzone

Sprawdzono w Pythonie (`Decimal`, `ROUND_HALF_UP`) 2026-10-02. „Odsetki narosłe na dzień X” odpowiadają `d = X` (dzień X wyłączony).

| Przykład (strona oferty) | Dane | Wynik wzoru | Wartość w źródle |
|---|---|---|---|
| EDO0524: zakup 10.05.2014, r1 = 4,00%, r2 = 1,50%, odsetki „narosłe na 16.06.2015” | base = 104,00; a = 37; ACT = 366 | 4,16 | „4,16 zł (odsetki narosłe na 16.06.2015 r.)”; wypłata 101,75 = 100 + 4,16 − 2 − 0,41 (podatek od 2,16) ✔ |
| TOS0825: zakup 1.08.2022, r = 6,50%, „narosłe na 17.10.2023” | N1 = 106,50; a = 77; ACT = 366 | 7,96 | „7,96 zł”; 105,88 = 100 + 7,96 − 0,70 − 1,38 ✔ |
| TOS1029: W = 100·1,044³ | — | 113,79 | list 97/2026 ust. 14: „113,79 zł” ✔ |
| ROR0623: zakup 01.06.2022, r = 5,25%, pełny 1. miesiąc | 100·0,0525/12 | 0,44 | „0,44 zł przed opodatkowaniem” ✔ |
| ROR0623: „narosłe na 29.06.2022” | 100·0,0525/12·28/30 | 0,41 | „0,41 zł” ✔ — wzór miesięczny `r/12·a/ACT` to **[wniosek]** dopasowany do przykładu; listu ROR nie pobrano |
| ROR0623: przedterminowy wykup, 2. okres (r = 5,25%), „narosłe na 14.07.2022” | 100·0,0525/12·13/31; opłata 0,50 (k = 2, pełna) | 0,18; 99,68 | „99,68 zł = 100 zł + 0,18 zł (odsetki narosłe na 14.07.2022 r.) – 0,50 zł” ✔ |

**Zaokrąglenie podatku — sprzeczność źródeł.** Broszura MF do PIT-38 (art. 63 § 1a Ordynacji) mówi o zaokrągleniu podatku z art. 30a ust. 1 pkt 1–3 „do pełnych groszy w górę”. Przykłady PKO BP temu przeczą: 19% × 2,16 = 0,4104 → podatek **0,41** (zaokrąglenie w górę dałoby 0,42); 19% × 0,44 = 0,0836 → wypłata 0,36, czyli podatek **0,08**. Wynik zgadza się z zaokrągleniem matematycznym do grosza. **rekomendacja:** test złoty z przykładów MF/PKO BP, reguła jako parametr; rozstrzygnąć na Tabelach odsetkowych lub potwierdzeniach wykupu.

**Tabele odsetkowe** (`https://www.obligacjeskarbowe.pl/tabele-odsetkowe/`): „dzienne wartości narosłych odsetek od obligacji”, wybór produktu → emisji → okresu (np. „2026-10-01 -> 2027-10-01”), plik „Pobierz tabelę odsetkową” w **PDF** (np. `/media_files/30a88aa2-….pdf` dla ROR1027). **rekomendacja:** pobrać po kilka PDF dla każdego typu (w tym okresy z 29 lutego i okresy ≥ 2 EDO) jako fixture'y testów parametryzowanych. Są one wyrocznią (test oracle) dla funkcji wyceny.

## 3. Wydarzenia korporacyjne na GPW (skrót)

| Zdarzenie | Co modelować | Źródło danych | Uwagi |
|---|---|---|---|
| Dywidenda | dzień ustalenia prawa (dzień dywidendy), dzień wypłaty, kwota/akcję, waluta | raporty ESPI/EBI spółki, kalendarium GPW (płatne: cennik poz. 11 „Kalendarium wydarzeń rynkowych (dane GPW)” 8 100 zł/rok), Stooq (z kluczem) | Przy rozrachunku T+2 (od 2014-10-06) trzeba kupić akcje „nie później niż dwie sesje przed dniem dywidendy” (KDPW, sii.org.pl — snippet) **[niezweryfikowane]**. Przychód podatkowy w dniu wypłaty, nie ustalenia **[wniosek]** — patrz dokument podatkowy |
| Split / scalenie (resplit) | współczynnik, data zmiany w KDPW | ESPI, komunikaty KDPW, GPW „Operacje na papierach / emisji (dane GPW)” (4 900 zł/rok) | Partie zakupu (loty podatkowe) przeliczyć: ilość × k, cena / k, ten sam koszt i data nabycia **[wniosek]** |
| Prawo poboru | PDA/prawo poboru jako osobny Walor; przychód ze zbycia prawa poboru: art. 17 ust. 1 pkt 7 ustawy o PIT | ESPI, GPW | Koszt nabycia akcji z poboru = cena emisyjna **[niezweryfikowane]** |
| Spin-off / podział | nowy Walor; podział kosztu nabycia proporcjonalnie (ustawa o PIT art. 22 ust. 1 i następne — nie przeanalizowano) | ESPI | **[niezweryfikowane]** |
| Rozrachunek | data transakcji T vs data rozrachunku T+2 | KDPW „zmiana cyklu rozrachunkowego z T+3 na T+2” (`https://www.30.kdpw.pl/uploads/user_files/zmiana_cyklu_rozrachunkowego_z_t_plus_3_na_t_plus_2.pdf`, nie pobrano) | Ma znaczenie podatkowe (moment przeniesienia własności) |

**rekomendacja:** w MVP wydarzenia korporacyjne wprowadzane ręcznie jako typy Operacji (`SPLIT`, `RIGHTS_ISSUE`, `SPINOFF`), z polem `source_url` (link do raportu ESPI). Automatyczne pozyskiwanie przez płatne kalendarium GPW nie opłaca się przy jednym użytkowniku **[wniosek]**.

## Źródła

Dostęp 2026-10-01/02, o ile nie zaznaczono inaczej.
- Strony ofert: `https://www.obligacjeskarbowe.pl/oferta-obligacji/obligacje-10-letnie-edo/` (i analogicznie: `-4-letnie-coi`, `-3-letnie-tos`, `-2-letnie-dor`, `obligacje-roczne-ror`, `-3-miesieczne-ots`, `-6-letnie-ros`, `-12-letnie-rod`) — pobrane 2026-10-01.
- Tabele odsetkowe: https://www.obligacjeskarbowe.pl/tabele-odsetkowe/ (2026-10-01).
- List emisyjny 99/2026 (EDO1036): https://www.obligacjeskarbowe.pl/media_files/4f5f6353-fdcd-4b7e-b44f-63088098c534.pdf
- List emisyjny 98/2026 (COI1030): https://www.obligacjeskarbowe.pl/media_files/e156037b-5b0c-40b8-85e1-0b205d4ac395.pdf
- List emisyjny 97/2026 (TOS1029): https://www.obligacjeskarbowe.pl/media_files/c15a26ae-de6e-4b89-a137-cb16687a7b0a.pdf
- List emisyjny 60/2012 (COI0117) i inne historyczne listy COI 2007–2012 (do porównania historycznego), pobrane przez wcześniejszy etap badania.
- NBP Web API: https://api.nbp.pl/ ; terminy publikacji: https://nbp.pl/statystyka-i-sprawozdawczosc/kursy/informacja-o-terminach-publikacji-kursow-walut/ ; stopy: https://static.nbp.pl/dane/stopy/stopy_procentowe.xml
- GPW, Cennik Usług Informacyjnych obowiązujący od 1 stycznia 2025 (tekst pobrany przez wcześniejszy etap badania; dokładnego URL pliku nie zapisano); regulamin: https://www.gpw.pl/pub/GPW/files/PDF/cennik/Regulamin_swiadczenia_uslug_info_2025.pdf
- Stooq / klucz API: https://github.com/pydata/pandas-datareader/issues/1012 (otwarte 2026-04-13)
- Yahoo chart API (test): https://query1.finance.yahoo.com/v8/finance/chart/PKO.WA
- EODHD: https://eodhd.com/pricing , https://eodhd.com/exchange/WAR
- Twelve Data: https://twelvedata.com/prime (snippet); FMP: https://apis.io/plans/financialmodelingprep/financialmodelingprep-plans-pricing/ (snippet)
- POLSTR: https://bankoweabc.pl/nowy-wskaznik-polstr-zastapi-wibor/ (snippet); WIBOR, komunikat GPW Benchmark z 18.05.2026 (wtórnie): https://www.citibank.pl/poland/files/gpwb-komunikat.25.05.pdf , https://comparic.pl/koniec-wibor-ogloszony-gpw-benchmark-wyznaczyl-date-co-to-oznacza-dla-kredytobiorcow/ (snippety wyszukiwarki)
- GUS BDL API: https://bdl.stat.gov.pl/api/v1/
- KDPW T+2 i dywidendy: https://www.sii.org.pl/7513/analizy/newsroom/nowy-cykl-rozliczeniowy-na-gpw.html (snippet)

## Luki i niepewności

1. **Odczyt CPI dla COI/EDO/ROS/ROD:** list emisyjny nie mówi, który miesiąc i czy szybki szacunek, czy odczyt finalny. Teza „X−2” jest niepotwierdzona → rekomendacja: przechowywać ogłoszoną stopę.
2. **ROR/DOR:** listów emisyjnych nie pobrano. Wzór miesięczny `r/12·a/ACT` odtworzono z przykładu (zgadza się z dwoma liczbami), ale go nie zweryfikowano. Nie sprawdzono też, z którego dnia brana jest stopa referencyjna NBP.
3. **OTS:** listu nie pobrano. Strona ma niespójny „Okres oprocentowania”.
4. Stooq: nie dało się połączyć z kontenera (reset połączenia). Limit dzienny i warunki klucza znane tylko ze snippetów.
5. Pokrycie GPW/NewConnect/Catalyst w Twelve Data, Alpha Vantage, FMP — nie potwierdzone. Ceny Twelve Data i FMP tylko ze snippetów.
6. Yahoo: brak licencji. Pokrycia NewConnect i Catalyst nie testowano. Możliwe zmiany nieoficjalnego API.
7. Ceny funduszy TFI: nie zbadano ToS ani formatów analizy.pl i stron TFI.
8. Wydarzenia korporacyjne: rozliczenie kosztu przy spin-off i prawie poboru — nie przeanalizowano przepisów.
9. NBP: dokumentacja (93 dni) i zachowanie API (367 dni) różnią się — limit może się zmienić bez ogłoszenia.
