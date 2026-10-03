---
id: research-final-analysis
status: current
type: mixed
scope: research/final
last_reviewed: 2026-10-03
---

# FundTracker: analiza końcowa (myfund, rynek, metodyka, stan aplikacji, architektura, decyzje, plan)

> **Dokument zbiorczy.** Zastępuje cząstkowe badania i plany; zawiera wszystko, co ustalono w analizie, w zakresie v1 uzgodnionym z właścicielem (2026-10-03). Szczegółowe, wiążące decyzje są w ADR-ach (sekcja 7).

## 1. Streszczenie i zakres

**Cel.** FundTracker ma działać jak myfund.pl, tylko lepiej: osobisty tracker inwestycji (kupna, sprzedaże, wpłaty i wypłaty, dywidendy, przewalutowania, splity), z metrykami portfela i wykresami w czasie. Dokument zbiera wnioski z analizy myfund i konkurencji, danych rynkowych, metodyki metryk, stanu aplikacji oraz decyzje z wywiadu z właścicielem (2026-10-03).

**Zakres v1**
- Jeden użytkownik (właściciel), rejestracja zamknięta.
- Instrumenty: akcje i ETF-y; broker XTB; ceny z Yahoo Finance, kursy walut z NBP; ceny ręczne tylko awaryjnie.
- Portfel = jeden rachunek maklerski (etykiety `account_type` i `broker`); sumy zbiorcze dają Grupy portfeli.
- Koszt nabycia metodą FIFO na partiach zakupu; gotówka osobno dla każdej pary (Portfel, Waluta); przewalutowanie jako osobna operacja.
- Metryki: wartość, zysk zrealizowany i niezrealizowany, TWR dzienny, XIRR, jeden benchmark; dzienne snapshoty do wykresów.
- Import historii z XTB (później, gdy będą próbki plików).
- Hosting: backend na Render (darmowy plan usypia usługę), Postgres na Supabase; zadania w tle jako CLI plus nadrabianie zaległości po wybudzeniu. Dane startują od zera.

**Zasady „lepiej niż myfund”**
1. Poprawność przed funkcjami: wycena zawsze w walucie Portfela, brak kursu jest jawny (`rate_missing`), nigdy cichy kurs 1.
2. Historia jako fakty: ceny i kursy zapisywane z datą i źródłem, a nie nadpisywane w miejscu.
3. Jawna jakość danych: flagi „nieaktualne”, „syntetyczne”, „brak kursu” widoczne w interfejsie.
4. Wyniki odtwarzalne: stan portfela jest pochodną operacji i można go przeliczyć od zera.
5. Metodologia opisana i testowana liczbami (testy złote), a nie „czarna skrzynka”.

**Najważniejsze wnioski**
- Przed dokładaniem funkcji trzeba było naprawić defekty wyceny walut obcych (F1, F4); zrobione w PR #2.
- Model danych aplikacji był za płaski na cele właściciela: brakowało historii cen i kursów, partii FIFO, gotówki per waluta i dni operacji. Decyzje zebrano w ADR-ach (sekcja 7).
- Najtrudniejsze elementy techniczne to przebudowa snapshotów po edycji wstecz i niezawodność zadań w tle na usypianym serwerze.
- Największe ryzyko zewnętrzne to nieoficjalne API Yahoo Finance oraz limity darmowych planów Render i Supabase.

## 2. myfund.pl i konkurencja

Stan na 2026-10-01/02, strony niezalogowane (pomoc, FAQ, cennik, forum). Statystyki myfund: 81 589 użytkowników, 194 061 portfeli, 22 373 347 operacji (https://myfund.pl/index.php). Jednoosobowy serwis PHP, rozwijany od ok. 2009 r.

### 2.1 Model danych myfund

- **Portfel**: gotówkowy (kupno wymaga gotówki; „algorytmy spójności” odrzucają ujemne saldo i ujemną ilość) albo bezgotówkowy (system sam dopisuje „Automatyczną wpłatę/wypłatę” przy każdym kupnie/sprzedaży) (https://myfund.pl/index.php?raport=FAQ).
- **Konta gotówkowe**: dowolna liczba, w dowolnej walucie. Status „Debetowe” wyłącza kontrolę salda (https://myfund.pl/index.php?raport=pomoc&helpID=50).
- **Portfel grupowy**: agreguje portfele, nie ma własnych operacji; ma własną datę zerowania, TWR/MWR, walutę i benchmarki. Odpowiednik naszych Grup portfeli.
- **Operacje** (helpID=20): wpłata/wypłata, kupno/sprzedaż, dywidenda, split, przewalutowanie (= przelew między kontami w różnych walutach). Kupno/sprzedaż ma prowizję kwotowo lub procentowo, kurs przeliczeniowy przy różnicy walut oraz walidację „Sprawdź cenę” (cena w min–max sesji).
- **Pozycje**: średnia cena i zysk niezrealizowany wg FIFO.
- **Split**: automatyczny, ceny historyczne korygowane wstecz. Dywidendy automatyczne od 2014-09-16, ręczne z kursem dla walut obcych.
- **Kursy**: gdy waluta operacji różni się od waluty konta, użytkownik sam podaje kurs. Zysk w PLN = wartość dziś − wartość nabycia w PLN (z efektem kursowym). Waluta przeliczenia portfela jest zmienialna.
- Walor zagraniczny dodaje się po tickerze Yahoo (np. `2408.TW`, `JEQP.L`) — **[wniosek]** źródłem jest Yahoo lub dostawca o tej samej symbolice.

### 2.2 Wycena i wykresy

| Element | Rozwiązanie myfund |
|---|---|
| Stopa zwrotu (domyślna) | „Jednostki portfela” jak w funduszu = TWR: pierwsza wpłata kupuje jednostki po 100 PLN, kolejne przepływy po bieżącej wartości jednostki [FAQ] |
| Alternatywy | MWR (do wyboru, także dla grupy), prosta stopa, CAGR |
| Przełączniki wyniku | prowizja od sprzedaży, dywidendy w zysku, data zerowania |
| Wyceny | dzienne przy pierwszym logowaniu dnia; notowania online z opóźnieniem 15–20 min; ręczne nadpisanie ceny |
| Wykresy | zakres dat na każdym; agregacja dzienna → tygodniowa (>½ roku) → miesięczna (>3 lata); wartość i wkład, zysk w czasie, wpłaty/wypłaty, kapitał wg waluty |
| Benchmarki | do 10 na wykresie (indeksy, inflacja, własny, inny portfel), z korektą ±pp/rok (helpID=40) |

Brak publicznej strony metodologii: FAQ opisuje jednostki skrótowo, bez wzorów krok po kroku (np. moment wyceny przy przepływie).

### 2.3 Import

Wklejka CSV (średnik): `Data;nazwa waloru;KUPNO|SPRZEDAŻ;ilość;cena;prowizja;kurs`. Plik brokera z podglądem w tabeli przed importem. E-mail z potwierdzeniami (`import@myfund.pl`). Kreator AI (od planu Pro). API brokera — „obsługuje tylko API z XTB”. Wtyczka Chrome (scraping). Lista integracji: 78 nazw w pliku JSON vs deklarowane „100+” na stronie głównej (https://myfund.pl/landing2026/data/integrations-list.json). FAQ twierdzi, że import obejmuje tylko GPW — **[wniosek]** nieaktualne.

### 2.4 Słabości myfund (nasza przewaga)

| Obszar | Dowód |
|---|---|
| UI | „wygląd… wciąż przypomina skomplikowany arkusz” (Portfeo, 2026-05-05); mobile „looks like PC port” (App Store, 2025-02-19) |
| Import | „nazwy funduszy nie są znormalizowane”; „godziny na ręcznym poprawianiu” (Portfeo); wątek „Import z XTB” 22 wpisy, 23 687 wyświetleń |
| Jakość danych | 2 223 tematy w „Usterki, błędy”: brak dywidendy JEQP.L od 08.2025, „MWIG40TR – błędna stopa zwrotu”, „Rozjazd historycznych cen”, „SYN2BIO – stopy w milionach %” |
| Przejrzystość | wątki „Skąd różnice w podsumowaniu”, „Wkład vs Wartość”; FAQ tłumaczy rozbieżności z wynikami XTB |
| API | jeden endpoint read-only `GET /API/v1/getPortfel.php` (od 2025-05-28, po prośbach od 2017) |
| Paywall, ciągłość | brak planu darmowego (4,99–24,99 zł/mies. od 2026-10-01); bus factor jednego autora |
| Dokumentacja | FAQ o imporcie i pomoc mobilna sprzeczne z cennikiem — **[wniosek]** nieaktualne |

### 2.5 Macierz konkurentów (tylko zakres v1)

Legenda: ✅ tak, ◐ częściowo, ❌ nie, ? niezweryfikowane. Źródło: kod repozytoriów lub strony oficjalne z 2026-10-01.

| Aplikacja | Wielowalutowość | Import | Wykresy / TWR | Benchmark | Self-host |
|---|---|---|---|---|---|
| Portfolio Performance | ✅ kursy ECB, wydzielone zyski walutowe | CSV konfigurowalny; ~136 ekstraktorów PDF (brak polskich) | ✅ dzienny TTWROR + IRR | ✅ | ✅ plik lokalny |
| Ghostfolio | ◐ serie „z/bez efektu walutowego” | CSV z aliasami nagłówków, brak synchronizacji | ❌ TWR/MWR to zaślepki (`Method not implemented`); tylko ROAI | ✅ | ✅ |
| Wealthfolio | ◐ kurs nabycia zapisany na partii | szablony CSV, podgląd rozpoznania walorów; sync brokerów płatny (SnapTrade) | ✅ TWR + IRR | ✅ | ✅ SQLite |
| Sharesight | ✅ rozbicie kapitał/dywidendy/waluta | 200+ brokerów, noty e-mailem | ❌ TWR; zmodyfikowana metoda Dietza | ✅ | ❌ |
| Snowball | ? | CSV, Yodlee + SnapTrade | ✅ TWR (3P) + IRR | ✅ | ❌ |
| Parqet | ? | przeciągnięcie PDF, 50+ brokerów, autosync | ✅ TTWROR | ✅ | ❌ |
| getquin | ? | CSV, integracje | ✅ TTWROR + IRR | ✅ | ❌ |

Żaden nie obsługuje polskich brokerów (XTB, mBank, Bossa) poza PP po ręcznej konwersji CSV **[niezweryfikowane]**. **[wniosek]** Żaden self-host nie łączy poprawnego TWR, wielowalutowości i polskiego importu — to nasza nisza.

### 2.6 Lekcje dla budowy (9)

1. **TTWROR dzienny z jawną konwencją**: `(1+r) = (MVE + CFout) / (MVB + CFin)`, napływ na początku dnia, odpływ na końcu, łańcuchowo; IRR metodą Newtona (PP: `snapshot/ClientIndex.java:82-100`, https://help.portfolio-performance.info/en/concepts/performance/time-weighted/). Roczna annualizacja na 365 dni z zastrzeżeniem o latach przestępnych.
2. **Klasyfikator przepływów zewnętrznych/wewnętrznych z zakresem** (Wealthfolio `flow_classifier.rs`): przepływ zewnętrzny dla konta bywa wewnętrzny dla Grupy portfeli.
3. **Odmowa liczenia zamiast niemożliwych procentów**: bez datowanych przepływów brak TWR/IRR; etykieta metody przy każdej liczbie (`performance-semantics-design.md` Wealthfolio, issue #1119).
4. **`Decimal` wszędzie**: Ghostfolio trzyma pieniądze jako `Float` (`schema.prisma:184-210`) — unikać; Wealthfolio używa `rust_decimal`.
5. **Nieniszczące splity**: współczynnik na partii (Wealthfolio) albo tabela stosowana przy odczycie (Ghostfolio); kreator PP przepisuje historię — unikać.
6. **Dekompozycja wyniku**: zysk kapitałowy / dywidendy / efekt walutowy / opłaty (Sharesight, PP) oraz seria „z/bez FX”.
7. **Ceny**: zapisywać źródło każdej ceny, oznaczać dni przeniesione (`isCarriedForward`), trzymać zamknięcie nieskorygowane, stan synchronizacji per walor (Wealthfolio `QuoteSyncState`), dociągać tylko brakujące ceny — kluczowe przy nadrabianiu zaległości po uśpieniu Rendera.
8. **Pipeline importu XTB** [propozycja]: surowy plik + hash → ekstraktor do wiersza staging → rozpoznanie waloru (ISIN, potem ticker + MIC) → walidacja (brutto = ilość × cena ± opłaty) → duplikaty po referencji brokera → podgląd jako Draft → zatwierdzenie pod wycofywalnym `import_batch_id`; fikstury tekstowe jak w PP.
9. **Nadpisania użytkownika odporne na reimport** i miękkie usuwanie (`activity_type_override`, status Draft/Posted/Void w Wealthfolio).

Domyślny benchmark: WIG/WIG20 (Biznesradar) **[propozycja]**.

### 2.7 Zasady „lepiej niż myfund”

**Poprawność.** Zestaw przypadków referencyjnych (TWR, XIRR, FIFO, split, FX) w CI; spójność księgi (brak ujemnych ilości i sald) sprawdzana dla każdego dnia; wynik z brakującymi danymi oznaczony, nie zgadywany.

**Jawne źródło i jakość danych.** Każda cena i kurs z polem źródła, daty i flagi przeniesienia; wskaźnik świeżości wyceny widoczny przy liczbie; publiczny opis wzorów i rozbicie wyniku (wkład, zysk, kurs, prowizje) — odpowiedź na wątki „Skąd różnice”.

**Historia jako fakty.** Operacje i zdarzenia korporacyjne niezmienne (korekta = nowy fakt lub Void), dzienne snapshoty odtwarzalne z księgi, splity bez przepisywania historii, import wycofywalny w całości. Pełne API (odczyt i zapis Operacji) zamiast jednego endpointu.

### 2.8 Czego nie przejmujemy

Spójny, jednoużytkownikowy zakres v1 bez forum, portfeli publicznych i subskrybowanych, skanerów, kalendarium spółek i white-label dla doradców; konkurencja ma szerszy zakres, obejmujący funkcje poza zakresem v1.

## 3. Dane rynkowe i brokerzy

Stan badania: 2026-10-01/02. Testy `curl` wykonano z kontenera badania.

### 3.1 Kursy walut: NBP Web API

Źródło kursów FX: `https://api.nbp.pl` (darmowe, bez klucza, JSON/XML, REST). Historia kursów od 2002-01-02 (test: `2001-12-28` daje 404, `2002-01-02` daje `1/A/NBP/2002`, `mid 3.9480`).

| Element | Wartość |
|---|---|
| Kurs z dnia | `GET /api/exchangerates/rates/{table}/{code}/{date}/?format=json`. Test: `rates/a/usd/2026-09-25` zwraca `{"no":"187/A/NBP/2026","effectiveDate":"2026-09-25","mid":3.8404}` |
| Zakres / ostatnie N | `…/rates/{table}/{code}/{startDate}/{endDate}/`, `…/rates/{table}/{code}/last/{topCount}/` |
| Tabele | A i B: kursy średnie (`mid`); C: `bid`/`ask`. Dla v1 wystarczy A |
| Publikacja tabeli A | dni robocze, 11:45-12:15 (strona nbp.pl, wynik wyszukiwarki) **[niezweryfikowane]** |
| Dzień bez notowań | HTTP 404 `NotFound - Brak danych` (test: niedziela 2026-09-27) |
| Limit zakresu | Dokumentacja: 93 dni. Faktycznie 2025-01-01…2026-03-01 daje `400 Przekroczony limit 367 dni`. Dokumentacja i API się różnią, więc limit może się zmienić bez ogłoszenia |
| HTTPS | Obowiązkowy od 2025-08-01 |

**Rekomendacja:** pobierać paczki do 93 dni (zgodnie z dokumentacją). Brak kursu na dany dzień (404) obsługiwać cofnięciem się do ostatniej tabeli z wcześniejszą `effectiveDate`. Przy każdym kursie zapisywać `source`, `fetched_at`, numer tabeli (`no`) i `effectiveDate`. Dziś `yahoo.py:52-53` bierze kurs z Yahoo jako `f"{from_code}{to_code}=X"`. Docelowo kursy walut dostarcza osobny adapter `NbpFxProvider` (propozycja źródła; ADR biz. dla przewalutowania rozstrzyga resztę).

### 3.2 Ceny akcji i ETF: Yahoo Finance

- **GPW:** sufiks `.WA`. Test 2026-10-02: `PKO.WA` zwraca `exchangeName":"WSE","currency":"PLN"`, `firstTradeDate` 1100073600 (2004-11-10); `ETFBW20TR.WA` zwraca `instrumentType":"ETF"`. NewConnect nie testowano **[niezweryfikowane]**.
- **Zagraniczne:** ten sam mechanizm bez sufiksu `.WA` (ticker giełdowy Yahoo). Adapter wywołuje `yf.Ticker(ticker).history(start, end, interval="1d")` (`backend/app/infrastructure/market_data/yahoo.py:64`); `yfinance` jest importowany tylko w tym module, a wyjątki sieciowe są przepakowywane do błędów domenowych (`yahoo.py:31`).
- **Dostęp:** nieoficjalne JSON (`query1.finance.yahoo.com/v8/finance/chart/…`) lub `yfinance`. Dane: EOD i intraday.
- **Ograniczenia:** brak publicznej licencji na dane, użytek osobisty **[wniosek]**; nieoficjalne API może się zmienić bez zapowiedzi. Dla jednoosobowej aplikacji to akceptowalne ryzyko, ale wymaga planu B (3.5).

### 3.3 Stooq (zapas)

CSV: `https://stooq.pl/q/d/l/?s=<sym>&i=d`. Od marca 2026 pobieranie wymaga klucza API ("As March 2026, Stooq requires an API key for data downloads", pandas-datareader #1012, 2026-04-13). Klucz przez `get_apikey` z CAPTCHA, dzienny limit wywołań **[niezweryfikowane]** (snippet). Z kontenera badania: `Connection reset by peer` (stooq.pl i stooq.com), więc działania nie zweryfikowano. **Rekomendacja:** `StooqProvider` z kluczem w `.env`, wyłącznie jako zapas dla GPW.

### 3.4 Licencje GPW: co wolno

Oficjalne dane GPW (Cennik Usług Informacyjnych od 2025-01-01) są płatne: "Wyniki sesji (dane GPW)" 3 500 zł netto/rok, wraz z BondSpot 7 600 zł. Przypis 3: dalsze rozpowszechnianie elektroniczne kosztuje "dziewięciokrotność stawki". Wniosek **[wniosek]**: dla jednoosobowej aplikacji własnej dane oficjalne to przesada. Wolno natomiast używać Yahoo i Stooq na własny użytek, nie wolno ich redystrybuować. Płatne API z pokryciem GPW (np. EODHD, giełda `WAR`, `PKO.WAR`: Historian 19,99 USD/mies.) to opcja rezerwowa. Pokrycie EODHD ze snippetu **[niezweryfikowane]**.

### 3.5 Strategia źródeł (rekomendacja)

Port `MarketDataProvider` (`backend/app/core/market_data.py:50-73`) zostaje; wybór adaptera w `assets/wiring.py`. Kolejność:

| Priorytet | Źródło | Rola |
|---|---|---|
| 1 | Yahoo (`yahoo.py`) | ceny EOD akcji i ETF, GPW i zagraniczne |
| 2 | Stooq (klucz w `.env`) | zapas dla GPW |
| 3 | Ceny ręczne | awaryjnie, gdy 1 i 2 zawiodą |
| FX | NBP tabela A | kursy walut, niezależnie od cen |

**Ceny ręczne awaryjne** (propozycja): użytkownik wpisuje cenę z datą dla waloru, zapis oznaczony `source=manual`, widoczny w UI jako ręczny i nadpisywalny późniejszą ceną automatyczną. Dzienne snapshoty nie mogą stanąć przez awarię jednego dostawcy.

### 3.6 Infrastruktura wpływająca na pobieranie danych

- **Render free:** usypia usługę po 15 min bez ruchu, wybudzenie trwa ok. minuty. Pobieranie nie może zakładać stale działającego procesu: po wybudzeniu trzeba nadrobić brakujące dni.
- **Postgres:** u nas na Supabase, nie na Renderze. Darmowy Postgres Rendera wygasa po 30 dniach, więc nie jest opcją.
- **Supabase free:** pauzuje projekt po tygodniu bez aktywności; limit 500 MB. Dzienne snapshoty i historia cen/kursów muszą się w nim mieścić.
- **Pooler transakcyjny Supabase:** obsługiwany. Fabryka sesji ustawia `SET LOCAL search_path TO …` w transakcji (`backend/app/infrastructure/sql/factory.py:62`), bo ustawienie sesyjne nie przeżywa przełączania połączeń przez pooler.

### 3.7 Brokerzy: import (później)

Import nie istnieje w kodzie; wchodzi po v1. Wymagania na przyszły importer: surowy plik, mapowanie, `external_id` do deduplikacji, Operacje oznaczone źródłem, test każdego parsera na zanonimizowanym pliku, podgląd przed zapisem. Importer wykrywa kodowanie (UTF-8 BOM / cp1250), separator i separator dziesiętny z próbki; polskie cechy eksportów (przecinek, cp1250, `DD.MM.YYYY`) **nie zostały potwierdzone** dla żadnego brokera.

**XTB (xStation 5), broker docelowy:**

- Eksport historii konta: zakładki zamkniętych pozycji, "Cash Operations" (wpłaty, wypłaty, dywidendy) i zleceń. Format XLSX; inne źródła wspominają CSV/HTML **[niezweryfikowane]** (strona pomocy XTB zwróciła 403, tylko snippety).
- Kolumny: oficjalnej listy nie znaleziono, więc ich nie zgadujemy. Parser trzeba oprzeć na prawdziwym pliku właściciela.
- Pułapka 1: zamknięte transakcje są łączone w pary kupno/sprzedaż, a otwarte pozycje są jedną pozycją z uśrednioną ceną (myfund, helpID=30). Pozycja uśredniona nie niesie partii potrzebnych do FIFO. Import otwartych pozycji trzeba więc traktować jako stan początkowy albo kasować i wczytywać od nowa.
- Pułapka 2: format pliku się zmienia (forum myfund: "XTB - nowy format pliku eksportu"), więc parser musi wersjonować nagłówki i zawodzić głośno.

**Inni brokerzy (po XTB):** udokumentowane kolumny ma tylko Interactive Brokers (Flex Query CSV/XML: m.in. `Symbol`, `ISIN`, `Trade Date`, `Quantity`, `Trade Price`, `IB Commission`, `Trade ID`; `FX Rate to Base` to kurs IB, nie NBP). Trading 212: CSV, eksport max 365 dni, `ID` do deduplikacji **[niezweryfikowane]**. DEGIRO: CSV **[niezweryfikowane]**. Dla pozostałych (mBank, Bossa, PKO BP, Santander, Revolut, Exante) kolumn nie znaleziono.

## 4. Metodyka metryk

Podstawa: badanie `05_metodyka_metryk.md` (2026-10-01/02), ADR biz. 0002 i 0004, ADR tech. 0014 i 0016 (Accepted). Standardy: GIPS 2020 (https://www.gipsstandards.org/wp-content/uploads/2021/03/2020_gips_standards_firms.pdf), podręcznik Portfolio Performance (PP, https://help.portfolio-performance.info/en/concepts/performance/time-weighted/).

### 4.1 Dwie główne liczby

„Wynik %” = TWR dzienny (`method.twr = daily_pp_v1`), „Mój zwrot %” = XIRR (`method.irr = xirr_365_v1`) **[propozycja nazw]**. Dziś „zwrot” = `(wartość − wpłaty netto) / wpłaty netto` (`domain/valuation.py:83,88`) i zależy od timingu wpłat. Obok liczb pokazujemy zysk bezwzględny; zmiana metody = nowa wartość `method` i nowy ADR.

### 4.2 TWR dzienny (konwencja PP)

```
1 + r_t = (MVE_t + CFout_t) / (MVB_t + CFin_t)
R = Π(1 + r_t) − 1 = I_e / I_s − 1,   I_t = Π_{u≤t}(1 + r_u)
```

- Wpływ zewnętrzny na początku dnia, wypływ na końcu, tuż przed wyceną. Wartość Portfela zawiera gotówkę (GIPS 2.A.11). Przepływy z jednego dnia netujemy.
- Mianownik 0: `r_t = 0` i restart (jak `ClientIndex.java` w PP).
- Okres: zamknięcie dnia startu → zamknięcie dnia końca. Start sprzed powstania Portfela przycinamy (`effective_start`), bez dopełniania zerami.
- Przepływy: wpłata, wypłata i wpłata automatyczna — zewnętrzne (Portfel, Grupa); przewalutowanie, kupno, sprzedaż — wewnętrzne (dla Pozycji: przepływ z prowizją); dywidenda, odsetki — dochód; prowizja, opłata — koszt.
- TWR Grupy i Portfela z własnego szeregu, nie średnia TWR składników.

**Test złoty (Decimal, równość dokładna).** Dzień 1: MVB 10 000, wpłata 5 000, MVE 15 300 → 15 300/15 000 = 1,02. Dzień 2: wypłata 2 000 na końcu, MVE 13 000 → 15 000/15 300 = 0,980392…. Dzień 3: MVE 13 390 → 1,03. TWR = **+3,0000 %** (0,03). Kontrola: +100 %, potem −25 % → 0,50.

### 4.3 XIRR i annualizacja

- Znaki: wpłaty ujemne, wypłaty dodatnie, wartość początkowa jak wpłata, końcowa jak wypłata. Rok = 365 dni: `Σ P_i / (1 + r)^((d_i − d_1)/365) = 0`. Solver na `float` **[propozycja]**: agregacja przepływów z tej samej daty, Newton od 0,1 z pochodną analityczną, przy niepowodzeniu skan siatki i bisekcja.
- `IRR_UNDEFINED` — brak zmiany znaku; nigdy ostatnia iteracja. `IRR_AMBIGUOUS` — kilka pierwiastków (−100, +230, −132 w t = 0, 1, 2 → 10 % i 20 %); zwracamy TWR. Kody inline, HTTP 200.
- **Annualizacja:** `(1 + R)^(365/dni) − 1` tylko dla okresu ≥ 365 dni (GIPS 2.A.12). Krótszy: `annualized = null`, `reason = "PERIOD_SHORTER_THAN_ONE_YEAR"`; XIRR < 1 roku → zwrot okresu `(1 + IRR)^(dni/365) − 1`. Motyw: dane z 4.2 jako przepływy z datami dają IRR = 3914 % p.a. (PP pokazuje IRR zawsze p.a., odstępując od GIPS).
- **Modified Dietz** wyłącznie jako fallback dla podokresów bez cen, z `approximation = true`: `R = (B − A − F) / (A + Σ W_i·F_i)`, `W_i = (C − D_i)/C`. Dane z 4.2: zysk 390, średni kapitał 14 333,33 → **2,7209 %** (TWR 3,0000 %).

**Złote testy XIRR (tolerancja jawna):** przykład z dokumentacji Excel (2008-01-01 −10 000; 2008-03-01 +2 750; 2008-10-30 +4 250; 2009-02-15 +3 250; 2009-04-01 +2 750) → **0,373362535 ± 1e-8**; PP: −66 EUR, +111,76 EUR po 255 dniach → 1,1253 ± 1e-4; annualizacja 30 % w 730 dniach → 0,140175.

### 4.4 FIFO i partie (ADR biz. 0002)

- Partia = (Portfel, Walor, Operacja otwierająca): ilość otwarta/pozostała, koszt jednostkowy w walucie Waloru (cena + prowizja), kurs brokera `fx_rate` zamrożony w dniu zakupu. Tabele pochodne `portfolios_lot`, `portfolios_lot_consumption`, odtwarzalne przez `rebuild`.
- Sprzedaż zużywa najstarsze partie w obrębie (Portfel, Walor); prowizja sprzedaży pro rata na wycinki. Split zmienia ilość i cenę jednostkową przy stałym koszcie łącznym.
- `average_buy_price` jest tylko informacją w UI.

```
Realized   = Σ zużytych wycinków (wpływ netto − koszt)
Unrealized = Σ otwartych partii (Q_rem × P_t × FX_t − koszt)
Total P/L  = Realized + Unrealized + Dywidendy − pozostałe koszty
```

**Test złoty.** Kupno 10 po 100 + prowizja 5 (100,50/szt.); kupno 10 po 120 + 5 (120,50); sprzedaż 15 po 130, prowizja 6 (wpływ netto 1 944).

| | FIFO | Średnia (110,50) |
|---|---|---|
| Koszt 15 sprzedanych | 1 607,50 | 1 657,50 |
| Zrealizowany | **336,50** | 286,50 |
| Pozostałe 5 szt., koszt | 602,50 | 552,50 |
| Niezrealizowany (MV 650) | **47,50** | 97,50 |
| Razem | **384,00** | **384,00** |

Zysk całkowity nie zależy od metody (test własności).

### 4.5 Wycena wielowalutowa

- `MV_base = Q × P_local × FX`. `FxMapBuilder` (`services/fx.py`) buduje mapę `(z, do) → rate[z]/rate[do]` (kursy `assets` są „USD za jednostkę”); kolejność: para → odwrotność → pivot **[propozycja]**. `domain/` dostaje gotową mapę.
- Brak kursu: pola wyceny pozycji `null` + `rate_missing = true`, sumy Portfela `null` (bez sum częściowych); endpoint kursu zwraca `RATE_MISSING` (404). `exchange_rate = 1` na walucie innej niż USD to wartość domyślna kolumny, nie kurs.
- Efekt FX **[propozycja]**: `1 + R_base = (1 + R_local)(1 + R_fx)`; najpierw cena po starym kursie, potem kurs na nowej cenie. Test: 100 → 110 USD, USD/PLN 4,00 → 3,80 → **+4,5 %** = 0,10 − 0,05 − 0,005 (+40 − 22 = +18 PLN).
- Dni nienotowane: forward-fill ceny i kursu; dni bez sesji pomijane w statystykach benchmarku.

### 4.6 Snapshoty dzienne i przebudowa (ADR tech. 0016)

- Tabele pochodne `portfolios_daily` (PK `portfolio_id`, `day`: wartość, gotówka, przepływy, `r_day`, `twr_index` `Numeric(24,12)`, `data_quality`) i `portfolios_position_daily`.
- `portfolios_portfolio.dirty_from` (`Date`, null = aktualne). Operacja: `LEAST(dirty_from, operation_day)` w transakcji zapisu; korekta ceny/kursu z daty `d`: `LEAST(dirty_from, d)` w `rebuild-dirty`. Nowy dzień nie unieważnia — przebieg dopisuje brakujące dni (nadrabianie po uśpieniu backendu).
- Przebudowa per Portfel: `SELECT … FOR UPDATE`, kasowanie wierszy `≥ dirty_from`, przeliczenie, `dirty_from = null`; idempotentna (drugi przebieg = 0 zapisów).
- Synchronicznie, gdy `dni × otwarte pozycje ≤ 20 000` **[propozycja; kalibracja w E2.5]**, inaczej `BackgroundTasks` i odczyt z `stale=true`.

### 4.7 Benchmark

ADR biz. 0004: jeden indeks zestawiany z TWR Portfela w tym samym okresie i walucie (najlepiej total return). **[propozycja]** wariant „te same przepływy”: przy każdej zewnętrznej wpłacie `units += CF / P_bench,d` (z FX_d), `Bench_MV_t = units × P_bench,t × FX_t`; porównanie `IRR_portfolio` z `IRR_benchmark` na identycznych przepływach. Wypłata ponad wartość benchmarku → `units` przycięte do 0 i flaga.

### 4.8 Granica Decimal / float (ADR tech. 0014)

| Obliczenie | Typ | Miejsce |
|---|---|---|
| Księga, partie, zysk zrealizowany, `r_day`, `twr_index`, kursy | `Decimal` | `portfolios/domain/` (stdlib) |
| XIRR, statystyki benchmarku | `float` | `services/performance.py` |
| Wektory wykresów | `float` | `services/metrics.py` |

Wejście: `float(d)` w jednym miejscu. Wyjście: `Decimal(str(f))` + `quantize` na granicy API (stopy 6 miejsc, procenty 2); nigdy `Decimal(f)`. Wynik statystyki nie wraca do księgi, partii ani snapshotu (poza `twr_index`). `numpy` tylko w `services/`. Testy: `Decimal` — równość dokładna, `float` — jawna tolerancja. Otwarte: czy `Numeric(24,12)` wystarcza po 10 latach.

**Testy własności:** wpłata skalowana z MV nie zmienia TWR; bez przepływów TWR = IRR; Total P/L równy dla FIFO i średniej; dwa przebiegi przebudowy dają identyczne wiersze.

## 5. Stan aplikacji i luki

Stan na 2026-10-03, HEAD `5fddc10` (kod przeczytany, testów nie uruchamiano). Dokument badawczy `06_stan_found-tracker_vs_cel` to migawka z `9eda5fe` (2026-10-01/02) - kod poszedł dalej, niżej wartości aktualne z kodu.

### 5.1 Co aplikacja ma dziś

- **Stos:** FastAPI + SQLAlchemy + Alembic, Python 3.14, Postgres; warstwowy monolit modułowy (`api -> services -> repositories`, czysta `domain/`), moduły `security`, `core_data`, `assets`, `portfolios`. Frontend: React 19, Vite, MUI 7, TanStack Query/Table, Recharts 3. CI: ruff, `mypy --strict`, `alembic check`, pytest. Auth: JWT HS256 (access 30 min, refresh 1 dzień).
- **Modele (6 tabel, 2 migracje):** `users`; `assets_assetclass`; `assets_currency` (`exchange_rate` = **USD za 1 jednostkę**); `assets_asset` (jedna `current_price`, bez historii); `portfolios_portfolio` (`cash_balance`, `total_deposited` - jedna pula gotówki w walucie bazowej); `portfolios_position` (średnia ważona: `average_buy_price` z prowizją, `average_fx_rate`, `total_fees`, `total_dividends`); `portfolios_operation` (`buy/sell/deposit/withdrawal/dividend`, `fx_rate`, `operation_date`).
- **Endpointy:** `/auth/*`; `/assets/{asset-classes,currencies}` (CRUD), `/assets/` (+ `search-yahoo` po dokładnym tickerze, `create-from-yahoo`); `/portfolios/` (CRUD); `/portfolios/operations` (CRUD; każda zmiana = pełna przebudowa księgi); `GET /portfolios/positions` (czysty odczyt po zapisanych cenach) i `POST /portfolios/positions/refresh` (odświeża kursy i ceny z Yahoo); `GET /portfolios/fx-rate`; `GET /portfolios/portfolio-vectors` (wektory dzienne, numpy).
- **Frontend:** kokpit, widok Portfela (pozycje, dialogi kupna/sprzedaży/gotówki), historia operacji, wykresy, porównanie do 4 Portfeli.
- **Księga:** średnia ważona (nie FIFO), brak zysku zrealizowanego. Ceny wyłącznie Yahoo na żądanie; brak NBP, brak tabel historii cen i kursów, brak harmonogramu (`entrypoints.py`/`cli.py` nie istnieją).

### 5.2 Defekty F1-F6

| # | Defekt | Status | Dowód |
|---|---|---|---|
| F1 | Wycena FX liczona względem USD | **Naprawiony (PR #2).** `FxMapBuilder` składa kurs krzyżowy `rate[z]/rate[do]`; brak kursu (`exchange_rate == 1` dla waluty innej niż USD) daje `rate_missing`, nie ciche ×1 | `portfolios/services/fx.py:42-90`; `portfolios/domain/valuation.py:64-85` |
| F2 | Wektory ignorują FX i dywidendy | **Naprawiony w kodzie (nie wiążę z PR).** Koszt i dywidenda mnożone przez `fx_rate`; dywidenda zasila `free_cash` i `profit`. **Ograniczenie zostaje:** wartość walorów = ilość x zamknięcie w walucie waloru, bez przeliczenia (brak historii kursów); bez `portfolioName` wektory mieszają waluty | `portfolios/services/metrics.py:113-133, 270-273`; docstring l.21-25 |
| F3 | „Całkowita wartość" na dashboardzie = sama gotówka | **Częściowo naprawiony (PR #3, tylko dashboard).** Suma = `total_value ?? cash_balance` przeliczona na PLN (`baza/PLN`); Portfele z `rate_missing` wyłączone ze wszystkich sum + ostrzeżenie; brak kursu PLN = alert błędu. Waluta wyświetlania zaszyta na PLN (brak ustawień); przy braku `total_value` fallback to gotówka | `frontend/src/pages/DashboardPage.tsx:13-14, 20, 28-37` |
| F4 | Dialog kupna podpowiada kurs USD | **Naprawiony (PR #2).** Kupno i sprzedaż pobierają `GET /portfolios/fx-rate`; przy braku kursu pole jest puste i wymaga ręcznego wpisu | `BuyAssetDialog.tsx:55-79`; `SellAssetDialog.tsx:43-67`; `portfolios/api/fx_rates.py:17` |
| F5 | Walor z tickera dostaje walutę Portfela | **Naprawiony w kodzie.** Waluta z notowania dostawcy; waluta Portfela tylko gdy dostawca nie zna tickera lub nie działa (plan E0.4 chciał tu 502) | `assets/services/assets.py:193-231`; `portfolios/services/operations.py:174` |
| F6 | Zmiana waluty bazowej reinterpretuje gotówkę | **Naprawiony w kodzie:** 409 `PORTFOLIO_CURRENCY_LOCKED`, gdy Portfel ma operacje | `portfolios/services/portfolios.py:167-174`; `portfolios/exceptions.py:49` |

Także zamknięte względem migawki: operacja wsteczna przechodzi przez pełny `rebuild()` pod blokadą wiersza Portfela (`portfolios/services/operations.py:84-117`); tickery GPW w seedzie mają `.WA` (`backend/seed/seed_data.py:132,141,150`); odświeżanie jest osobnym `POST .../refresh`, a `GET` nie ma skutków ubocznych.

### 5.3 Znany błąd: `opened_at` pozycji

`Position.opened_at` ma `server_default=func.now()` (`portfolios/models/position.py:52`), a przebudowa tworzy wiersz bez tej wartości (`portfolios/services/operations.py:210-218`). Pole przechowuje więc czas **zapisu wiersza**, nie `operation_date` pierwszego zakupu. Skutek: dla importu lub operacji wstecznej „data otwarcia" jest późniejsza niż pierwszy zakup. Poprawka: ustawiać z daty pierwszej operacji przy tworzeniu wiersza, w E2.0 (aktualizacja pozycji w miejscu, kolumny `operation_day`).

### 5.4 Pozostałe luki wobec celu v1

| Luka | Skutek | Gdzie naprawiana |
|---|---|---|
| Brak historii cen i kursów (`Asset.current_price`, `Currency.exchange_rate` nadpisywane); każdy wykres pyta Yahoo | wolne i niestabilne wykresy; brak wyceny historycznej walorów obcych (reszta F2) | E1.1 (`assets_price`, `assets_fx_rate`), ADR tech. 0015 |
| Tylko Yahoo; brak NBP; wyszukiwanie po dokładnym tickerze; domyślna waluta USD | brak oficjalnych kursów walut; brak wyszukiwania po nazwie | E1.2, E1.3 |
| Brak odświeżania w tle i nadrabiania zaległości (Render usypia usługę) | ceny nieaktualne bez ręcznego `refresh` | E1.4 (`entrypoints.py` + CLI), ADR tech. 0017 |
| Brak snapshotów dziennych i TWR/XIRR; zwrot = (wartość - wpłaty netto)/wpłaty netto | liczba nieporównywalna z benchmarkiem i innymi trackerami | E2.5 (ADR tech. 0016), E3.1 |
| Brak benchmarku: `benchmarkService.getSP500Data()` zwraca `null`, nieużywany (`frontend/src/services/benchmarkService.ts:29-37`) | brak porównania z indeksem | E1.6, E3.5 |
| Średnia ważona zamiast FIFO; brak zysku zrealizowanego (`domain/ledger.py` sprzedaż: średnia bez zmian) | brak zysku z zamkniętych pozycji | E2.4, E3.2 |
| Jedna pula gotówki w walucie bazowej; brak typu przewalutowania | nie da się odwzorować rachunku wielowalutowego | E2.2 |
| `fx_rate` Operacji wpisywany ręcznie, brak kursu historycznego | błędny koszt przy ręcznej pomyłce | E1.1, E1.2 |
| Brak Grup portfeli i agregacji w jednej walucie; `portfolio-vectors` bez nazwy miesza waluty | brak sumy po rachunkach | E2.1, E3.4 |
| Brak importu XTB | ręczne wpisywanie operacji | E4 (po dostarczeniu eksportu) |
| Operacje bez paginacji i filtrów; z UI tylko data, kolejność dnia wg `created_at` | wolna lista, niejednoznaczna kolejność | E2.0, E2.7 |
| Brak ustawień użytkownika (waluta wyświetlania), `/settings` martwy; rejestracja otwarta; dane referencyjne (Waloru, Waluty) edytowalne przez każdego użytkownika | zaszyte PLN; ryzyko przy publicznym hostingu | E0.9, E0.6 |
| Frontend: brak edycji Operacji i wpisu dywidendy, atrapy w nagłówku, brak testów | niepełne UI nad istniejącym API | E0.7, E0.10, E11.6 |
| Brak splitów (zdarzenia korporacyjne) | błędna ilość i cena po splicie | E8.1 |

## 6. Architektura docelowa

Stan kodu (2026-10-03, `backend/app/modules/*/models`): istnieją tylko `assets_asset`, `assets_currency`, `assets_assetclass`, `portfolios_portfolio`, `portfolios_operation`, `portfolios_position`; wszystko poniżej oznaczone „nowa” jest do zbudowania. Dane startują od zera (seed albo import). ADR tech. 0013–0017, 0019, 0020 oraz biz. 0001–0005, 0007 mają status Accepted; ADR tech. 0018 (import) jest Proposed.

### 6.1 Moduły i kierunki zależności

| Moduł | Może zależeć od | Zawartość |
|---|---|---|
| `core_data` | — (dług: `→ security`, cykl `users.py:7` ↔ `auth.py:2`) | użytkownicy (`is_owner`), `core_data_user_settings` |
| `security` | `core_data` | JWT, logowanie |
| `assets` | — | walory, waluty, ceny, kursy |
| `portfolios` | `assets`, `core_data` | księga, partie, snapshoty, import |

Zakazane: `assets → portfolios|core_data|security`. Moduły wołają się wyłącznie przez serwisy (ADR tech. 0006); graf egzekwuje `test_architecture.py` (`ALLOWED_MODULE_DEPENDENCIES`; `infrastructure/` importuje tylko `core` i `infrastructure`). Import żyje w `portfolios` (osobny moduł dałby cykl FK); port `ImportParser` w `core/import_parser.py`, adapter XTB w `infrastructure/import_parsers/`. Waluta wyświetlania to kod `String(3)` bez FK. Numeryka (ADR tech. 0014): księga, partie, `r_day`, `twr_index`, kursy na `Decimal` w `domain/` (tylko stdlib); XIRR i statystyki benchmarku na `float`/`numpy` wyłącznie w `services/`; wynik wraca jako `Decimal(str(f))` z `quantize`. Migracje tylko `alembic revision --autogenerate`; zmiana typu istniejącej kolumny zakazana, stąd nowa kolumna `operation_day` zamiast zmiany `operation_date` (ADR tech. 0019).

### 6.2 Model danych

Typy: kwoty `Numeric(18,2)`; saldo gotówki `(18,3)`; ceny, ilości, kursy `(18,9)`; `twr_index` `(24,12)`; wartości wyliczeniowe jako `String`, `CHECK` tylko w nowych tabelach. Tabele pochodne (partie, salda, snapshoty) nie są celem FK z danych użytkownika — odwołania idą do `portfolios_operation.id`.

| Tabela | Klucz i kolumny | Dziś / docelowo |
|---|---|---|
| `portfolios_portfolio` | UNIQUE `(owner_id, name)`; `base_currency_id`; **+** `account_type` `String(10)` (etykieta, domyślnie `regular`), `broker` `String(60)`, `auto_funding` bool (false), `dirty_from` `Date` | istnieje; `cash_balance`, `total_deposited` zostają jako cache (waluta bazowa) |
| `portfolios_operation` | płaska; istniejące: `operation_type`, `quantity`, `price`, `amount`, `fee`, `fx_rate` (kurs brokera), `operation_date` timestamptz. **+** `operation_day` `Date` (Europe/Warsaw), `sequence`, `currency_id`, `counter_amount`/`counter_currency_id`, `ratio`, `external_ref` `String(120)`, `import_batch_id`, `edited_at` | istnieje; klucz księgi `(operation_day, sequence, id)` zastępuje `(operation_date, created_at, id)` |
| `portfolios_lot` | partia FIFO: `open_operation_id` (UNIQUE), `quantity_initial/open`, `unit_price`, `cost_local/base`, `fx_rate`, `acquired_on`, `split_ratio`, `closed_on` | nowa, pochodna |
| `portfolios_lot_consumption` | `lot_id`, `close_operation_id`, `quantity`, `proceeds/cost/fee_local`, `*_base` | nowa, pochodna |
| `portfolios_cash_balance` | UNIQUE `(portfolio_id, currency_id)`, `balance` | nowa, pochodna |
| `portfolios_auto_flow` | wirtualne wpłaty przy `auto_funding` (czytane przez TWR/XIRR jako przepływy zewnętrzne) | nowa, pochodna **[propozycja]** |
| `portfolios_group`, `_group_member` | Grupa: UNIQUE `(owner_id, name)`, `currency_code`; członkostwo M:N, bez Operacji | nowe |
| `portfolios_daily` | PK `(portfolio_id, day)`: `value`, `cash`, `positions_value`, `income`, `fees`, `ext_in/out`, `r_day`, `twr_index`, `cum_ext_*`, `data_quality` | nowa, pochodna |
| `portfolios_position_daily` | PK `(portfolio_id, asset_id, day)`: `quantity`, `price_local`, `fx`, `mv_local/base`, `cost_base`, `is_stale`, `is_synthetic` | nowa, pochodna (~110 tys. wierszy/Portfel przy 30 walorach × 10 lat **[wniosek]**) |
| `assets_price` | UNIQUE `(asset_id, price_date, source)`; `close` nieskorygowany (`auto_adjust=False`), `is_synthetic` | nowa; `current_price` = cache |
| `assets_fx_rate` | UNIQUE `(from, to, rate_date, source)`; NBP `XXX→PLN`, `source` ∈ {`nbp`,`manual`} | nowa; `exchange_rate` waluty nullable (brak kursu = `RATE_MISSING`, nie 1) |
| `assets_listing`, `assets_price_change` | symbol i priorytet dostawcy; dziennik korekt historii (kursor przebudowy) | nowe |
| `job_run` | PK `job_name`, `last_started_at`, `last_finished_at`, `last_status`, `last_ok_day` | nowa |
| `portfolios_import_batch/_row/_override` | UNIQUE `(owner_id, sha256)`, `status` draft/committed/reverted; plik ≤ 10 MB **[propozycja]** | nowe, później (ADR 0018) |

Reguły: FIFO per (Portfel, Walor), sprzedaż zawsze zużywa najstarsze partie; split zmienia `split_ratio`, nie koszt (biz. 0002). Saldo per (Portfel, Waluta); przewalutowanie to jeden wiersz (`amount` = noga wychodząca, `counter_*` = przychodząca, prowizja w walucie wychodzącej; tech. 0020). Dwa kursy: brokera (`operation.fx_rate`, koszt i gotówka) i wyceny (`assets_fx_rate`, dzienny). Kurs krzyżowy składa `portfolios` (`FxMapBuilder`: para → odwrotność → pivot **[propozycja]**). Źródło ceny: `manual` zawsze pierwsze, dalej `assets_listing.priority`; forward-fill liczony przy odczycie. Snapshoty: korekta operacji ustawia `dirty_from = LEAST(dirty_from, operation_day)`, przebudowa per Portfel kasuje wiersze `≥ dirty_from` i liczy od nowa (idempotentna); synchronicznie, gdy dni × otwarte pozycje ≤ 20 000 **[propozycja]**, inaczej w tle. Walor z historią archiwizujemy (`archived_at`), zapis danych globalnych tylko dla `is_owner`.

### 6.3 Kontrakt API

Grupy (docelowo; kontrakt to szkic, `{S}` = `/portfolios/{id}` lub `/groups/{id}`): `/auth/*`, `/settings`; `/assets/*` (waluty, `currencies/rate`, `fx-rates`, ceny, listingi, `refresh-prices`, `data-status`); `/portfolios/*` (CRUD, `commission-rules`, operacje wszystkich typów + `preview` jako dry-run); `/groups/*`; `{S}/positions|lots|closed-positions|performance|allocation|charts/{series}|income`; `/portfolios/compare`, `/dashboard`; `/portfolios/imports*` (później). Nowe endpointy adresują Portfel po `id`; `portfolio_name` działa równolegle do kamienia M1 (`deprecated`, `Sunset`).

**Błędy** (ADR tech. 0007): `{"detail": "<EN>", "code": "UPPER_SNAKE"}`; **[propozycja]** opcjonalne `params` oraz `code: REQUEST_VALIDATION_FAILED` dla 422 (dziś bez `code`, `core/errors.py:115-122`). Kody: `INSUFFICIENT_CASH`, `INSUFFICIENT_QUANTITY`, `INVALID_OPERATION`, `CONCURRENT_CHANGE`, `RATE_MISSING`, `MARKET_DATA_UNAVAILABLE` (502), `PORTFOLIO_CURRENCY_LOCKED` (409), `ASSET_HAS_HISTORY` (409, zastępuje `ASSET_IN_USE`), `REFERENCE_DATA_OWNER_ONLY` (403), `REGISTRATION_DISABLED` (403), `OPERATION_EXTERNAL_REF_EXISTS`, `IMPORT_*` (m.in. `IMPORT_UNRESOLVED_ROWS`, `IMPORT_BATCH_HAS_EDITS`). Kody metryk są w odpowiedzi 200: `IRR_UNDEFINED`, `IRR_AMBIGUOUS` (zwracany TWR), `PERIOD_SHORTER_THAN_ONE_YEAR`.

**Koperta metryki:** `value`, `unit` (waluta/`ratio`/`pct`/`days`), `method` (`daily_pp_v1`, `xirr_365_v1` **[propozycja nazw]**), `effective_start`, `data_quality` (`ok/stale/synthetic/missing`), `stale`, `source`, `as_of`, `reason`, `approximation`, `issues[]` (`PRICE_STALE`, `PRICE_MISSING`, `RATE_MISSING`, `REBUILD_PENDING`). Annualizacja tylko ≥ 365 dni (biz. 0004).

**Konwencje:** listy nieograniczone (Operacje) w kopercie `{items,total,limit,offset}`, `limit` 1–200 (domyślnie 50), paginacja offsetem (cel < 300 ms dla 10 000 Operacji, **niezmierzone**); małe słowniki jako gołe tablice. **DecimalNumber vs string:** dziś `DecimalNumber` serializuje `Decimal` do `float` (`core/schemas.py:11-13`), a typy TS to `number`; **propozycja** `DecimalString` (string dziesiętny, bez notacji wykładniczej) dla kwot, cen, ilości i kursów, wektory wykresów zostają `float`, przełączenie istniejących schematów jednorazowo z typami z OpenAPI. Dzień: `operation_day` + `operation_time` (Warszawa) albo legacy `operation_date`. Bez prefiksu `/v1` **[propozycja]**; bez `Idempotency-Key` w v1.

### 6.4 UI

Trasy v1: `/` kokpit (waluta wyświetlania); `/portfolios/:id` (pozycje) z zakładkami `operations`, `allocation`, `performance`, `income`, `closed`; `/groups/:id` i `/groups/all` **[propozycja]**; `/assets/:id` (wykres ceny z markerami operacji); `/operations`; `/compare`; `/data` (jakość danych); `/settings`; `/methodology`; `/import*` (później, tylko desktop); `/login`. Jedna nawigacja (sidebar); stare `/pockets/:slug*` przekierowuje `LegacyPortfolioRedirect` przez `GET /portfolios/?name=`. Jeden `OperationFormDialog` dla wszystkich typów z podglądem „przed → po” z backendu (dry-run), bez arytmetyki na kwotach w przeglądarce.

**Formatowanie** (`lib/format.ts`, `pl-PL`): `formatMoney` z jawną walutą (2 miejsca), `formatQuantity` do 9 miejsc, `formatPrice` 2–4, `formatRate` 4–6 **[propozycja]**, `formatPercent` 2 miejsca z jawnym znakiem, `formatDate` `DD.MM.YYYY`; brak wartości = „—”, nie 0. Zysk/strata: znak + ikona + kolor (`SignedValue`). Wykresy: Recharts 3 + własny `HeatmapGrid` **[propozycja]**.

**Flagi jakości danych** (`DataQualityBadge`, wyświetlane wyłącznie przez `MetricLabel`): `stale` (cena starsza niż `stale_price_days`, domyślnie 7; znacznik z `price_date`), `synthetic` („Szacunek”, brak notowania z dnia), `rate_missing` (brak kursu; wycena pusta zamiast domyślnego 1; wdrożone dziś jako `rate_missing: bool` w odpowiedzi kursu), `missing` (brak ceny przy niezerowej pozycji), plus `source`, `method`, `effective_start`, `annualized = null`. Dane częściowe są pokazywane z paskiem `StaleBanner`, nie zastępowane błędem.

### 6.5 Zadania w tle

Brak Celery/Redis i brak harmonogramu w procesie (Render usypia backend). Polecenia `python -m app.cli <zadanie>` wołają wyłącznie `entrypoints.py`: `refresh-fx` (NBP przed cenami), `refresh-prices`, `backfill`, `rebuild-dirty`, `rebuild-all`, `create-user`, `set-owner`. Kody wyjścia: 0 ok, 1 błąd, 2 argumenty, 3 częściowe niepowodzenie **[propozycja]**; błąd jednego waloru nie przerywa reszty. **Nadrabianie:** pierwsze żądanie dnia (stan z `job_run`, nie z pamięci procesu) rejestruje w `BackgroundTasks` tylko `refresh_fx_rates`, `refresh_prices`, `rebuild_dirty`; zadania są idempotentne. **Blokada:** wiersz `job_run` w transakcji, `SELECT … FOR UPDATE SKIP LOCKED` (brak wiersza w wyniku = inny przebieg trwa, wyjście bez pracy); przebieg bez `last_finished_at` po 30 minutach uznaje się za przerwany. Nie `flock` ani blokady sesyjne (pooler transakcyjny Supabase). `POST /assets/refresh-prices` zwraca 202; żadne żądanie HTTP nie woła dostawcy synchronicznie. Zewnętrzny cron (jedna linia) jest opcjonalny.

## 7. Decyzje

Decyzje projektowe żyją jako ADR-y w `docs/business/adr/` (reguły domenowe) i `docs/technical/adr/` (architektura). Status zmienia człowiek. Poniższe tabele są streszczeniem.

### Biznesowe

| ADR | Decyzja | Status |
|---|---|---|
| 0001 | Portfel = jeden rachunek maklerski; agregację dają Grupy portfeli | Accepted |
| 0002 | Koszt nabycia z partii zakupu, FIFO w obrębie Portfela; split zachowuje koszt łączny | Accepted |
| 0003 | Gotówka per (Portfel, Waluta); przewalutowanie jako operacja; opcjonalne `auto_funding` (domyślnie wyłączone) | Accepted |
| 0004 | Dzienny TWR (konwencja Portfolio Performance) i XIRR; brak annualizacji poniżej 365 dni | Accepted |
| 0005 | Operacja ma dzień (`operation_day`, Europe/Warsaw) i numer kolejny w dniu (`sequence`) | Accepted |
| 0007 | Dane referencyjne należą do właściciela instancji; walor z historią się archiwizuje | Accepted |

### Techniczne (nowe)

| ADR | Decyzja | Status |
|---|---|---|
| 0013 | Graf zależności czterech modułów (`core_data`, `security`, `assets`, `portfolios`) egzekwowany testem; `assets` nie zależy od `core_data` ani `security` | Accepted |
| 0014 | Księga, partie, TWR i kursy na `Decimal`; `float` z `numpy` tylko dla XIRR i statystyk benchmarku | Accepted |
| 0015 | Ceny i kursy jako historia w bazie (`assets_price`, `assets_fx_rate`), nieskorygowane, z jawnym źródłem; dwa kursy: brokera i wyceny | Accepted |
| 0016 | Snapshoty dzienne jako pochodna księgi; przebudowa per Portfel od najstarszej zmiany; synchronicznie do progu | Accepted |
| 0017 | Zadania w tle: CLI `python -m app.cli <zadanie>` wołające `entrypoints.py` plus nadrabianie po wybudzeniu; blokada transakcyjna `job_run` | Accepted |
| 0018 | Import: paczka z cofnięciem w `portfolios`; parser jako adapter za portem; pierwszy adapter XTB | Proposed (do czasu próbek plików) |
| 0019 | Migracje tylko `autogenerate`; `operation_day` + `sequence`; dane od zera | Accepted |
| 0020 | Płaska tabela operacji z polami rozszerzającymi; przewalutowanie to jeden wiersz | Accepted |

### Wcześniejsze decyzje architektoniczne (opisują istniejący kod, status Proposed)

0001 jedna sesja SQLAlchemy na żądanie; 0002 sesja poza żądaniem tylko przez `entrypoints.py` i `wiring.py`; 0003 serwisy CRUD zwracają encje ORM; 0004 `find_*` kontra `get_*` w repozytoriach; 0005 opcjonalna warstwa `domain/` bez ORM, sesji i zegara; 0006 komunikacja między modułami wyłącznie przez serwisy; 0007 kontrakt błędów `{"detail", "code"}`; 0008 rdzenie bez commitu w operacjach wielomodulowych; 0010 `Decimal` od bazy do granicy schematu; 0011 audyt zmian odłożony; 0012 JWT: HS256, tokeny w `localStorage`, stateless refresh.

## 8. Plan wdrożenia

Plan (warstwa L3, szkic do akceptacji właściciela) dzieli prace na etapy E0–E4, część E8 i E11. Numeracja ma luki (brak E5–E7, E9, E10, D12) i nie jest przenumerowywana, bo odwołują się do niej ADR-y. Rozmiary kroków: S ≤ 1 dzień, M 2–4 dni, L 1–2 tygodnie, XL > 2 tygodnie (jedna osoba) **[wniosek]**.

### Etapy: cel, kroki kluczowe, zależności

| Etap | Cel | Kroki kluczowe | Zależy od |
|---|---|---|---|
| **E0** Naprawy i ustawienia (XL) | Wiarygodne liczby dla portfeli wielowalutowych, zanim cokolwiek na nich zbudujemy | E0.1 wycena walut obcych kursem krzyżowym `rate[z]/rate[do]` (`FxMapBuilder`), brak kursu = `RATE_MISSING`; E0.2 wektory metryk zgodne z księgą; E0.3 każda nowa operacja przechodzi przez `rebuild()` historii; E0.4 waluta nowego waloru z notowania dostawcy; E0.5 tickery GPW z sufiksem `.WA`, seed przez replay operacji; E0.6 `ALLOW_REGISTRATION=false` w produkcji, `is_owner`; E0.7 frontend (naprawa startu, `lib/format.ts`, Vitest, edycja operacji, dialog dywidendy); E0.8 blokada zmiany waluty Portfela z operacjami (409); E0.9 ustawienia (waluta wyświetlania, próg nieaktualnej ceny); E0.10 `Pocket` → `Portfolio` we froncie | — |
| **E1** Dane rynkowe i historia (XL) | Każda wycena i wykres liczą się z bazy, bez sieci w ścieżce żądania | E1.1 `assets_price`, `assets_fx_rate` (ceny nieskorygowane, `is_synthetic`); E1.2 rejestr dostawców: NBP (tabele A/B, paczki ≤ 93 dni) i Yahoo (`auto_adjust=False`, zachowanie domyślne `yfinance` **[niezweryfikowane]**); E1.3 ISIN/MIC/`asset_type`, wyszukiwanie; E1.4 odświeżanie w tle z nadrabianiem po wybudzeniu, tabela `job_run`; E1.5 ceny ręczne (`source=manual`); E1.6 benchmark; E1.7 `stale`, `price_date`; E1.8 lista obserwowanych; E1.9 kalendarz sesji | E0 |
| **E2** Księga v2 (XL) | Model księgowy dla wielowalutowego rachunku maklerskiego | E2.0 `operation_day`/`sequence`/`currency_id`, `dirty_from`, CLI `rebuild`; E2.1 Portfel jako rachunek, Grupy portfeli; E2.2 gotówka per (Portfel, Waluta) i przewalutowanie; E2.3 typy `interest`, `fee`, `split`, pola `status`/`external_ref`/`import_batch_id`; E2.4 partie FIFO (`LotBook`, `portfolios_lot`), zysk zrealizowany; E2.5 `portfolios_daily`, `portfolios_position_daily`; E2.6 słownik; E2.7 historia operacji z paginacją | E0, E1 |
| **E3** Analityka podstawowa (XL) | „Ile zarobiłem”, „jak wypadam na tle indeksu”, „z czego składa się portfel” | E3.1 `GET /portfolios/{id}/performance` (zysk, TWR, XIRR, `method`, `data_quality`); E3.2 zamknięte pozycje; E3.3 struktura; E3.4 kokpit; E3.5 wykresy (TWR vs benchmark); E3.6 dywidendy (stopa TTM, stopa od kosztu); E3.7 strona „Jak liczymy”; E3.8 widok waloru | E1, E2 |
| **E4** Import (L, później) | Wieloletnia historia z XTB w minuty, z cofnięciem | E4.1 potok: plik z hashem → parser (port `core/import_parser.py`) → walidacja → duplikaty → `import_batch` przez `record_many` + jeden `rebuild`; E4.2 adapter XTB | E2.3 |
| **E8** Zdarzenia korporacyjne (część, XL) | Split i dywidendy nie psują historii ani stóp zwrotu | E8.1 split ręczny (zmiana ilości i ceny partii, koszt łączny bez zmian; realizowany w M0); E8.5 propozycje dywidend i splitów od dostawcy jako Operacje `status=draft` (`accept`/`void`, ilość na dzień ustalenia prawa T+2); E8.6 kalendarz i prognoza dywidend 12 mies. (oznaczona jako szacunek) | E1, E2 |
| **E11** Jakość (ciągły) | Użyteczność i wydajność | E11.1 PWA i widok mobilny; E11.7 pomiar na 10 lat × 200 operacji × 30 walorów (wykres < 300 ms, kokpit < 500 ms, p95); E11.8 kreator pierwszego uruchomienia | ciągle |

### Stan wykonania

- **Zrobione:** E0.1 (wycena walut obcych i dialogi) — PR #2; poprawka dashboardu — PR #3.
- **Dalej:** reszta E0 (E0.2–E0.10), potem E1.1–E1.4. Dokument planu nie podaje innych zamkniętych kroków.

### Kamienie milowe

| Kamień | Kroki | Kryterium akceptacji | Szacunek **[wniosek]** |
|---|---|---|---|
| **M0 — rdzeń** | E0 → E1.1–E1.4 → E2.0–E2.5 + E8.1 → E3.1 | Historia jednego rachunku wpisana ręcznie; ilości i salda gotówki zgadzają się dokładnie z wyciągiem brokera; TWR i XIRR przechodzą testy złote | 2–4 mies. |
| **M1 — na co dzień** | E1.5–E1.9, E2.6–E2.7, E3.2–E3.8, E4 (gdy właściciel zdecyduje) | Wszystkie rachunki; wartość po cenach i kursach brokera zgodna z wyciągiem ±0,01 zł; TWR/XIRR vs benchmark, struktura, dywidendy | +2–3 mies. |
| **M2 — zdarzenia** | E8.5–E8.6 (w zakresie v1) | Splity i dywidendy nie psują historii ani stóp zwrotu | +1–2 mies. |
| **M3 — jakość** | E11 | PWA, wydajność w budżecie | ciągle |

Blokada zewnętrzna: E4.2 wymaga zanonimizowanego eksportu z XTB od właściciela (oficjalnej listy kolumn nie znaleziono). ADR tech. 0018 (architektura importu) ma status `Proposed`; ADR-y tech. 0013–0017, 0019–0020 są `Accepted`. Agent nie przełącza ADR-ów na `Accepted`.

### Definicja ukończenia kroku

1. Zgodność z architekturą (warstwy, `wiring.py`, `transaction()`, błędy z `code`, `Decimal`, `extra="forbid"`, `domain/` bez I/O); test architektury zielony.
2. Migracje wyłącznie `alembic revision --autogenerate`; `alembic check` bez dryfu; model w `models_registry.py`.
3. Testy: jednostkowe domeny z testami złotymi, integracyjne endpointów, testy własności obliczeń.
4. `ruff check .`, `ruff format --check .`, `mypy app`, `pytest`; frontend `npm run lint`, `npm run build`.
5. Funkcja w UI ze stanami: pusty, błąd, ładowanie.
6. Dokument modułu („Stan vs cel”), `CONTEXT.md`, mapa wiedzy, `kb_validate --strict` bez nowych błędów.
7. Dla danych pochodnych: `rebuild()` dwukrotnie daje identyczny stan.

### Ryzyka i mitygacje

| Ryzyko | Mitygacja |
|---|---|
| Yahoo jest nieoficjalne, API może się zmienić | Rejestr dostawców za portem `MarketDataProvider` (E1.2); ceny w bazie; ceny ręczne awaryjnie (E1.5); kolejny adapter za portem |
| Ceny skorygowane o splity podwoiłyby efekt splitu | Pobieranie cen nieskorygowanych + test kontraktowy na walorze po splicie (E1.2) |
| Render usypia backend; zaległe odświeżenia | Pierwsze żądanie dnia rejestruje w `BackgroundTasks` odświeżenie i przebudowę; zadania idempotentne; blokada w tabeli `job_run`, nie `flock` (ADR tech. 0017, E1.4) |
| Supabase pauzuje projekt po tygodniu bez aktywności | **[propozycja]** zadanie dzienne (E1.4) lub zewnętrzny ping co kilka dni; procedura ręcznego wznowienia w panelu; plan nie opisuje tego ryzyka, dodać do rejestru |
| Przebudowa po edycji wstecz (wolna lub niespójna) | `dirty_from` per Portfel i unieważnianie od najstarszej zmiany (ADR tech. 0016); przebudowa synchroniczna do progu, powyżej w tle; E0.3 (walidacja historią); test idempotencji; pomiar E11.7 |
| Zmiana wyceny niezrealizowanego P/L po wprowadzeniu FIFO (dziś koszt = `ilość × średnia`, `valuation.py:53`; po E2.4 koszt z partii) | Test złoty: zrealizowany 336,50 (FIFO) vs 286,50 (średnia), zysk całkowity 384,00 w obu; test własności „zysk całkowity niezależny od metody”; metoda widoczna w UI (E3.7); ADR biz. 0002 przed E2.4 |
| Rozrost E2 | Kroki E2.0–E2.7 z addytywną migracją i zielonymi testami |
| Zmiana metodologii po wdrożeniu | ADR biz. 0004 przed E3; pole `method` w odpowiedziach API |
| Praca jednoosobowa | M0 jako mały, użyteczny rdzeń |

### Zakres pominięty w v1

Świadomie pomijamy funkcje spoza opisanego zakresu.

## 9. Otwarte kwestie

| Kwestia | Stan | Co dalej |
|---|---|---|
| Próbki plików XTB (historia konta, operacje gotówkowe) | brak; blokuje ADR 0018 i adapter importu | dostarczyć zanonimizowane eksporty przed implementacją importu |
| Kurs waluty = „USD za jednostkę” | `Currency.base_currency_id` ignorowane; ręczny kurs względem innej bazy zepsuje wycenę do następnego odświeżenia | zastąpi to historia kursów (ADR 0015) |
| Heurystyka braku kursu | kurs równy 1 na walucie innej niż USD uznawany za „brak kursu” | zastąpi to historia kursów |
| `CURRENCY_NOT_FOUND` | w jednym module ma dwa statusy: 400 w ciele operacji, 404 w `GET /portfolios/fx-rate` | zdecydować o ujednoliceniu |
| `opened_at` pozycji | dostaje czas zapisu zamiast daty operacji | osobna poprawka (dotyka przebudowy pozycji, która celowo zachowuje `opened_at`) |
| `total_fees` | sumuje opłaty w różnych walutach | policzyć per waluta albo w walucie Portfela |
| Yahoo Finance | nieoficjalne, bywa niestabilne | ceny ręczne jako awaryjne, historia w bazie, źródła wymienne za portem |
| Render i Supabase (darmowe plany) | Render usypia po 15 minutach bez ruchu; Supabase ma limit 500 MB | zadania nadrabiają zaległości; monitorować rozmiar bazy |

**Historia dokumentów.** Dokumenty usunięte przez właściciela (m.in. schemat danych docelowy, kontrakt API, IA interfejsu, plan wycinka E0.1, plan refaktoryzacji) są w historii gita przed commitem `5fddc10`; ich treść w zakresie v1 jest streszczona w sekcjach 6 i 8.

