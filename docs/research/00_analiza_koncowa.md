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

Stan na 2026-10-01/02, strony niezalogowane (pomoc, FAQ, cennik, forum); wszystkie źródła pobrane 2026-10-01, lista URL-i w 2.9. Statystyki myfund: 81 589 użytkowników, 194 061 portfeli, 22 373 347 operacji (https://myfund.pl/index.php). Jednoosobowy serwis PHP, rozwijany od ok. 2009 r.

### 2.1 Model danych myfund

- **Portfel**: gotówkowy (kupno wymaga gotówki; „algorytmy spójności” odrzucają ujemne saldo i ujemną ilość) albo bezgotówkowy (system sam dopisuje „Automatyczną wpłatę/wypłatę” przy każdym kupnie/sprzedaży) (https://myfund.pl/index.php?raport=FAQ).
- **Konta gotówkowe**: dowolna liczba i waluta. Status „Debetowe” wyłącza kontrolę salda (https://myfund.pl/index.php?raport=pomoc&helpID=50).
- **Portfel grupowy**: agreguje portfele, nie ma własnych operacji; ma własną datę zerowania, TWR/MWR, walutę i benchmarki. Odpowiednik naszych Grup portfeli.
- **Operacje** (helpID=20): wpłata/wypłata, kupno/sprzedaż, dywidenda, split, przewalutowanie (= przelew między kontami w różnych walutach). Kupno/sprzedaż ma prowizję kwotowo lub procentowo, kurs przeliczeniowy przy różnicy walut oraz walidację „Sprawdź cenę” (cena w min–max sesji).
- **Pozycje**: średnia cena i zysk niezrealizowany wg FIFO.
- **Split**: automatyczny, ceny historyczne korygowane wstecz; status „zaokrąglanie splitów do pełnych jednostek”. Dywidendy automatyczne od 2014-09-16 (ręczne z kursem dla walut obcych), zmiana nazwy od 2016-10-22 — zdarzenia korporacyjne to największa ukryta praca myfund.
- **Prowizje i dywidendy**: prowizje domyślne per konto i typ waloru (% + minimum); reguła „konto inwestycyjne + waluta → konto gotówkowe” dla dywidend. U nas: reguły prowizji per Portfel, dywidenda księgowana na saldo (Portfel, waluta dywidendy) bez konwersji.
- **Kursy**: gdy waluta operacji różni się od waluty konta, użytkownik sam podaje kurs. Zysk w PLN = wartość dziś − wartość nabycia w PLN (z efektem kursowym). Waluta przeliczenia portfela jest zmienialna. Raport „Wpłacony kapitał według waluty” rozdziela wpłaty od przewalutowań (pary „Currency conversion” z importu).
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
| Skład (pozycje) | ilość, średnia cena z prowizją, ostatnia cena z godziną wyceny, zmiana dzienna, wartość, udział, zysk % i nominalny, CAGR; cena ręczna wyróżniona kolorem |
| Kokpit | zmiana dzienna ważona, zysk całkowity, zmiany d/m/r, top 3 pozycje, porównanie do 10 portfeli |
| Zamknięte inwestycje | przychód, dywidendy, prowizja, zysk %; partie FIFO per zamknięcie; symulacja sprzedaży dziś |
| Dywidendy w czasie | suma, skumulowane, roczny; prognoza = dywidenda roku poprzedniego × ilość (bez reinwestycji) |

Brak publicznej metodologii: FAQ opisuje jednostki skrótowo, bez wzorów (np. moment wyceny przy przepływie).

### 2.3 Import

Wklejka CSV (średnik): `Data(RRRR-MM-DD HH:MI:SS);nazwa waloru;KUPNO|SPRZEDAŻ;ilość [waluta];cena;prowizja;kurs [waluta konta]`. Cena i prowizja opcjonalne (wtedy wycena z dnia) — u nas brak ceny to błąd walidacji. Plik brokera z podglądem w tabeli przed importem; brak formatu = próbka do autora (parser „max 24 h”). E-mail z potwierdzeniami (`import@myfund.pl`); kreator AI (Pro). API brokera — „obsługuje tylko API z XTB”: login i hasło (opcjonalnie zapisane zaszyfrowane), otwarte pozycje XTB re-importowane za każdym razem (ryzyko dubli lub nadpisań); u nas bez przechowywania hasła do brokera. Integracje: 78 nazw w JSON vs „100+” na stronie głównej (https://myfund.pl/landing2026/data/integrations-list.json). FAQ twierdzi, że import obejmuje tylko GPW — **[wniosek]** nieaktualne. Znany problem: błędne rozpoznanie przewalutowań (wątek „Problem z importem VWRD”).

### 2.4 Słabości myfund (nasza przewaga)

| Obszar | Dowód |
|---|---|
| UI | „wygląd… wciąż przypomina skomplikowany arkusz” (Portfeo, 2026-05-05); mobile „looks like PC port” (App Store, 2025-02-19); „klawiatura zasłania przyciski” (Google Play, 2023-09-07) |
| Mobile po 4.00 | brak widoku kompaktowego, ekranu startowego, motywu, zakresu dat wykresu; na iOS brak notatki i niezapamiętane sortowanie (forum 2/6881, 6/7108). Wymagania PWA: zapamiętane sortowanie i zakres dat, widok kompaktowy, pola niezasłaniane klawiaturą |
| Import | „nazwy funduszy nie są znormalizowane”; „godziny na ręcznym poprawianiu” (Portfeo); wątek „Import z XTB” 22 wpisy, 23 687 wyświetleń |
| Instrumenty | ETF-y dodawane do bazy na prośbę (wątek „Braki na liście instrumentów”, 32 wpisy); inne po tickerze Yahoo. U nas: wyszukiwanie po nazwie i ISIN, automatyczne dodanie waloru (E1.3) |
| Jakość danych | 2 223 tematy w „Usterki, błędy”: brak dywidendy JEQP.L od 08.2025, „MWIG40TR – błędna stopa zwrotu”, „Rozjazd historycznych cen”, „SYN2BIO – stopy w milionach %” |
| Przejrzystość | wątki „Skąd różnice w podsumowaniu”, „Wkład vs Wartość”; FAQ tłumaczy rozbieżności z wynikami XTB |
| API | jeden endpoint read-only `GET /API/v1/getPortfel.php?portfel={nazwa}&apiKey={klucz}&format=json` (od 2025-05-28, po prośbach od 2017; cache 5 min, wymaga abonamentu). Serie: `zyskWCzasie`, `wartoscWCzasie`, `wkladWCzasie`, `benchWCzasie`, `stopaZwrotuWCzasie` — wzorzec dla naszego `charts/{series}` |
| Paywall, ciągłość | brak planu darmowego (4,99–24,99 zł/mies. od 2026-10-01); bus factor jednego autora. Pro: import plików/e-mail, kreator AI, dywidendy w czasie; benchmark i skład już w Basic |
| Dokumentacja | FAQ o imporcie i pomoc mobilna sprzeczne z cennikiem — **[wniosek]** nieaktualne |

**Uwaga o źródłach.** Portfeo i Freenance konkurują z myfund, więc cytaty Portfeo to opinia (zweryfikować przed użyciem publicznym); autor myfund sprostował Freenance (forum 1/7056: plan darmowy i 19 zł/mies. sprzeczne z cennikiem); PortfolioGlance (2026-07-05) częściowo błędny.

### 2.5 Macierz konkurentów (tylko zakres v1)

Legenda: ✅ tak, ◐ częściowo, ❌ nie, ? niezweryfikowane. Źródło: kod repozytoriów lub strony oficjalne z 2026-10-01. Czytane HEAD-y (klon `--depth 1`): Portfolio Performance 2026-09-30 (v0.87.0); Ghostfolio 2026-10-01 (`347cd06`, v3.76.0); Wealthfolio 2026-10-01; Maybe 2025-07-24 (archiwum); Sure 2026-10-01.

| Aplikacja | Wielowalutowość | Import | Wykresy / TWR | Benchmark | Self-host |
|---|---|---|---|---|---|
| Portfolio Performance | ✅ kursy ECB, wydzielone zyski walutowe | CSV konfigurowalny; ~136 ekstraktorów PDF (brak polskich) | ✅ dzienny TTWROR + IRR | ✅ | ✅ plik lokalny |
| Ghostfolio | ◐ serie „z/bez efektu walutowego” | CSV z aliasami nagłówków, brak synchronizacji | ❌ TWR/MWR to zaślepki (`Method not implemented`); tylko ROAI | ✅ | ✅ |
| Wealthfolio | ◐ kurs nabycia zapisany na partii | szablony CSV, podgląd rozpoznania walorów; sync brokerów płatny (SnapTrade) | ✅ TWR + IRR | ✅ | ✅ SQLite |
| Sharesight | ✅ rozbicie kapitał/dywidendy/waluta | 200+ brokerów, noty e-mailem | ❌ TWR; zmodyfikowana metoda Dietza | ✅ | ❌ |
| Snowball | ? | CSV, Yodlee + SnapTrade | ✅ TWR (3P) + IRR | ✅ | ❌ |
| Parqet | ? | przeciągnięcie PDF, 50+ brokerów, autosync | ✅ TTWROR | ✅ | ❌ |
| getquin | ? | CSV, integracje | ✅ TTWROR + IRR | ✅ | ❌ |

Partie zakupu: PP (FIFO/średnia, *Kod*), Wealthfolio (FIFO, *Kod*), Sharesight (FIFO/LIFO, *Dok*); Ghostfolio bez partii. Gotówka jako księga: PP, Wealthfolio, Sharesight (Ghostfolio: migawki `AccountBalance`). Splity: PP niszczącym kreatorem, Ghostfolio tabelą, Wealthfolio `split_ratio` partii, Sharesight automatycznie, Snowball z błędami (*3P*).

Żaden nie obsługuje polskich brokerów (XTB, mBank, Bossa) poza PP po ręcznej konwersji CSV (przecinek dziesiętny, kolumna typu) **[niezweryfikowane]**. **[wniosek]** Żaden self-host nie łączy poprawnego TWR, wielowalutowości i polskiego importu — to nasza nisza. Spin-off, fuzja i zmiana tickera: brak pierwszoklasowej obsługi w open source; ewentualna Operacja `ASSET_EXCHANGE` przeniosłaby koszt partii z zachowaniem daty nabycia — **[wniosek]** poza v1, do tego czasu korekta ręczna z komentarzem.

**Dowody ryzyk.** Blokada API Yahoo zepsuła Ghostfolio (naprawa v2.73.0, 2024-04-17; https://community.umbrel.com/t/ghostfolio-needs-to-be-updated-due-to-yahoo-api-issue/16667). Splity to najwyżej głosowana prośba Ghostfolio (53 głosy; https://github.com/ghostfolio/ghostfolio/discussions). Snowball: split jako >1000% zwrotu (Trustpilot) **[niezweryfikowane]**.

### 2.6 Lekcje dla budowy (9)

1. **TTWROR dzienny z jawną konwencją**: `(1+r) = (MVE + CFout) / (MVB + CFin)`, napływ na początku dnia, odpływ na końcu, łańcuchowo; IRR metodą Newtona (PP: `snapshot/ClientIndex.java:82-100`, https://help.portfolio-performance.info/en/concepts/performance/time-weighted/). Ujemny TWR przy dodatnim zysku jest poprawny, gdy duża wpłata trafiła tuż przed spadkiem — „Jak liczymy” pokazuje przykład obok XIRR i zysku w walucie (https://help.getquin.com/en/articles/8064745-ttwror-true-time-weigted-rate-of-return).
2. **Klasyfikator przepływów z zakresem** (Wealthfolio `flow_classifier.rs:1-64`): przepływ zewnętrzny dla konta bywa wewnętrzny dla Grupy portfeli. Przewalutowanie to przepływ wewnętrzny — importer XTB łączy wiersze konwersji w jedną Operację `fx_convert` i nie liczy ich jako wpłat/wypłat w TWR/XIRR (test: para kont PLN/USD).
3. **Odmowa liczenia zamiast niemożliwych procentów**: bez datowanych przepływów brak TWR/IRR; etykieta metody przy każdej liczbie (`docs/features/performance-semantics-design.md:9-14` Wealthfolio, issue #1119). Wealthfolio i Snowball rozdzielają tryb „holdings” (bez TWR) od „transactions”; Maybe/Sure cofa się od migawki (`reverse_calculator.rb:17-22`). Pozycja zaimportowana jako stan początkowy dostaje flagę `holdings_only`, a TWR/IRR przed jej datą = `null` z `reason`.
4. **`Decimal` wszędzie**: Ghostfolio trzyma pieniądze jako `Float` (`schema.prisma:184-210`) — unikać; Wealthfolio używa `rust_decimal`.
5. **Nieniszczące splity**: współczynnik na partii (Wealthfolio) albo tabela stosowana przy odczycie (Ghostfolio); kreator PP przepisuje historię (`StockSplitModel.java:96-137`) — unikać. **[propozycja]** współczynnik jako para całkowita `ratio_num/ratio_den`; skumulowany = iloczyn liczników / iloczyn mianowników, dzielony dopiero przy odczycie (Ghostfolio `adjustActivityBySplits`); ułamki po splicie jako osobna Operacja `sell` z ceną rozliczenia, koszt łączny partii bez zmian (Wealthfolio `activity-types.md:125-137`).
6. **Dekompozycja wyniku**: zysk kapitałowy / dywidendy / efekt walutowy / opłaty (Sharesight, PP) oraz seria „z/bez FX”. PP uwzględnia też różnice kursowe gotówki: saldo w walucie obcej zmienia wartość bez Operacji. **[propozycja]** `FX_cash_t = Σ_waluty saldo_{t-1} × (FX_t − FX_{t-1})`; test: 1 000 USD po 4,00, kurs 3,80 → −200 PLN bez Operacji, w `MV`, nie w przepływach. PP dodaje typ `FEES_REFUND` i toleruje ±0,003 kursu (`Transaction.java:102-127`).
7. **Ceny**: zapisywać źródło każdej ceny i walutę kwotowania, oznaczać dni przeniesione (`isCarriedForward`), trzymać zamknięcie nieskorygowane, stan synchronizacji per walor (Wealthfolio `QuoteSyncState`, stany Active/Closed/Dormant; `docs/architecture/market-data-quotes.md:407-460`), pobierać tylko okres posiadania (zamknięte walory nie są odświeżane), dociągać tylko brakujące, circuit breaker po N błędach dostawcy — kluczowe przy nadrabianiu po uśpieniu Rendera i limicie 500 MB Supabase.
8. **Pipeline importu XTB** [propozycja]: surowy plik + hash → ekstraktor do wiersza staging (surowa etykieta brokera, aliasy nagłówków) → rozpoznanie waloru (ISIN, potem ticker + MIC; statusy `existing` / `auto_resolved_new` / `needs_fixing`; GPW vs Yahoo `.WA`; ręczne aliasy) → walidacja jak w PP (waluty → brutto FX → pola walorowe → data → duplikaty; brutto = ilość × cena ± opłaty) → duplikaty po referencji brokera, a bez niej po kluczu `data + ISIN + ilość + kwota` → podgląd jako Draft → zatwierdzenie pod wycofywalnym `import_batch_id`; fikstury tekstowe jak w PP (`.../datatransfer/pdf/<bank>/*.txt`). Walidacja ceny sesji (min–max) tylko jako `warning`, nigdy `400` — myfund każe ją wyłączać ręcznie przy wpisie historycznym i splicie.
9. **Nadpisania odporne na reimport** i miękkie usuwanie (`activity_type_override`, Draft/Posted/Void w Wealthfolio). **[propozycja]** edycja Operacji z importu ustawia `edited_at`; reimport jej nie nadpisuje; wycofanie paczki z edycjami zwraca `IMPORT_BATCH_HAS_EDITS`.

Domyślny benchmark: WIG/WIG20 **[propozycja]**; symbol w Yahoo niesprawdzony — zweryfikować przed E1.6 (`ETFBW20TR.WA` to potwierdzony ETF na WIG20TR). Konkurencja lokalna: Biznesradar BR Plus, 285 PLN/rok (https://www.biznesradar.pl/premium/brplus); Inwestomat, darmowy arkusz Google z XIRR i FIFO (https://inwestomat.eu/wszystkie-twoje-inwestycje-w-1-miejscu/).

### 2.7 Zasady „lepiej niż myfund”

**Poprawność.** Zestaw przypadków referencyjnych (TWR, XIRR, FIFO, split, FX) w CI; spójność księgi (brak ujemnych ilości i sald) sprawdzana dla każdego dnia; wynik z brakującymi danymi oznaczony, nie zgadywany.

**Jawne źródło i jakość danych.** Każda cena i kurs z polem źródła, daty i flagi przeniesienia; wskaźnik świeżości wyceny widoczny przy liczbie; publiczny opis wzorów i rozbicie wyniku (wkład, zysk, kurs, prowizje) — odpowiedź na wątki „Skąd różnice”. „Jak liczymy” generowane z kodu i testów złotych.

**Historia jako fakty.** Operacje i zdarzenia korporacyjne niezmienne (korekta = nowy fakt lub Void), dzienne snapshoty odtwarzalne z księgi, splity bez przepisywania historii, import wycofywalny w całości. Pełne API zamiast jednego endpointu.

**UI.** Mniej tabel, sensowne widoki domyślne, progresywne odsłanianie; komentarz na każdej Operacji we wszystkich widokach.

### 2.8 Czego nie przejmujemy

Spójny, jednoużytkownikowy zakres v1 bez forum, portfeli publicznych i subskrybowanych, skanerów, kalendarium spółek i white-label dla doradców; konkurencja ma szerszy zakres, obejmujący funkcje poza zakresem v1.

### 2.9 Źródła i luki badania

Forum myfund (`https://myfund.pl/index.php?raport=forum&forum=F&topic=T`, zapis F/T): cennik 2/7101; aplikacje 4.00 2/6881; wykresy 6/7108; Tajwan 9/7116; API 6/847 (2017-03-18 → 2026-09-28); Freenance 1/7056; ciągłość 1/4174; „Usterki, błędy” forum=7. Ponadto `raport=cennik`, `raport=regulamin`. Pomoc `helpID=`: 5 start; 15 definicje; 20 operacje; 30 import; 40 raporty; 50 opcje portfeli; 90 notowania online. Sklepy: Google Play `https://play.google.com/store/apps/details?id=pl.myfund.myfundpl20&hl=pl` (4,2★/213); App Store `https://apps.apple.com/pl/app/myfund-pl-portfel-inwestycji/id557701295` (3,9★/110). Recenzje: Portfeo `https://www.portfeo.pl/blog/wpis/portfeo-czy-myfund-porownanie-narzedzi-do-monitorowania-portfela-w-2026-roku`; PortfolioGlance `https://www.portfolioglance.com/investing-apps/myfund`.

Luki: `raport=APIdoc` i `ImportFileGuides` wymagają logowania (nieczytane); dostawca danych GPW niepotwierdzony; liczby i oceny to migawka z 2026-10-01.

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
| Cała tabela | `GET /api/exchangerates/tables/{table}/{date}/` zwraca wszystkie waluty (test dla C: `tables/c/2026-09-25` → `tradingDate 2026-09-24`, `effectiveDate 2026-09-25`, `bid/ask`); tabela A analogicznie, więc jeden dzień = jedno zapytanie dla wielu walut **[wniosek]** |
| Limit zakresu | Dokumentacja: 93 dni. Faktycznie 2025-01-01…2026-03-01 daje `400 Przekroczony limit 367 dni`. Dokumentacja i API się różnią, więc limit może się zmienić bez ogłoszenia |
| HTTPS | Obowiązkowy od 2025-08-01 |
| Licencja | Opis API jej nie zawiera (odczyt 2026-10-02) |
| Źródła | https://api.nbp.pl, https://nbp.pl/statystyka-i-sprawozdawczosc/kursy/informacja-o-terminach-publikacji-kursow-walut/ |

**Rekomendacja:** pobierać paczki do 93 dni (zgodnie z dokumentacją). Brak kursu na dany dzień (404) obsługiwać cofnięciem się do ostatniej tabeli z wcześniejszą `effectiveDate`. Przy każdym kursie zapisywać `source`, `fetched_at`, numer tabeli (`no`) i `effectiveDate`. Dziś `yahoo.py:52-53` bierze kurs z Yahoo jako `f"{from_code}{to_code}=X"`. Docelowo kursy walut dostarcza osobny adapter `NbpFxProvider` (propozycja źródła; ADR biz. dla przewalutowania rozstrzyga resztę).

### 3.2 Ceny akcji i ETF: Yahoo Finance

- **GPW:** sufiks `.WA`. Test 2026-10-02: `PKO.WA` zwraca `exchangeName":"WSE","currency":"PLN"`, `firstTradeDate` 1100073600 (2004-11-10); `ETFBW20TR.WA` zwraca `instrumentType":"ETF"`. NewConnect nie testowano **[niezweryfikowane]**.
- **Zagraniczne:** ten sam mechanizm bez sufiksu `.WA` (ticker giełdowy Yahoo). Adapter wywołuje `yf.Ticker(ticker).history(start, end, interval="1d")` (`backend/app/infrastructure/market_data/yahoo.py:64`); `yfinance` jest importowany tylko w tym module, a wyjątki sieciowe są przepakowywane do błędów domenowych (`yahoo.py:31`).
- **Dostęp:** nieoficjalne JSON (`query1.finance.yahoo.com/v8/finance/chart/…`) lub `yfinance`. Dane: EOD i intraday.
- **Ograniczenia:** brak publicznej licencji na dane, użytek osobisty **[wniosek]**; nieoficjalne API może się zmienić bez zapowiedzi. Dla jednoosobowej aplikacji to akceptowalne ryzyko, ale wymaga planu B (3.5).

### 3.3 Stooq (zapas)

CSV: `https://stooq.pl/q/d/l/?s=<sym>&i=d`; paczki bulk `stooq.com/db/h/` i historia „dekady” **[niezweryfikowane]**. Od marca 2026 pobieranie wymaga klucza API ("As March 2026, Stooq requires an API key for data downloads", https://github.com/pydata/pandas-datareader/issues/1012, otwarte 2026-04-13). Klucz przez `get_apikey` z CAPTCHA, dzienny limit wywołań **[niezweryfikowane]** (snippet). Z kontenera badania: `Connection reset by peer` (stooq.pl i stooq.com), więc działania nie zweryfikowano. **Rekomendacja:** `StooqProvider` z kluczem w `.env`, wyłącznie jako zapas dla GPW.

### 3.4 Licencje GPW: co wolno

Oficjalne dane GPW (Cennik Usług Informacyjnych od 2025-01-01) są płatne: "Wyniki sesji (dane GPW)" 3 500 zł netto/rok, wraz z BondSpot 7 600 zł. Przypis 3: dalsze rozpowszechnianie elektroniczne kosztuje "dziewięciokrotność stawki". Wniosek **[wniosek]**: dla jednoosobowej aplikacji własnej dane oficjalne to przesada. Wolno natomiast używać Yahoo i Stooq na własny użytek, nie wolno ich redystrybuować. Regulamin: https://www.gpw.pl/pub/GPW/files/PDF/cennik/Regulamin_swiadczenia_uslug_info_2025.pdf.

**Płatni dostawcy (plan B, snippety, wszystko [niezweryfikowane]):** EODHD: giełda `WAR`, `PKO.WAR`, 613 tickerów; Sandbox 0 USD (20 wywołań/dzień, 1 rok historii), Historian 19,99, Active trader 29,99, Equity analyst 59,99, All-in-one 99,99 USD/mies.; pełna lista tickerów wymaga „All World Extended package or higher” (https://eodhd.com/pricing, https://eodhd.com/exchange/WAR). Twelve Data (od 29 USD/mies.), FMP (od 29 USD), Alpha Vantage: pokrycie GPW nieustalone.

### 3.5 Strategia źródeł (rekomendacja)

Port `MarketDataProvider` (`backend/app/core/market_data.py:50-73`) zostaje; wybór adaptera w `assets/wiring.py`. Kolejność:

| Priorytet | Źródło | Rola |
|---|---|---|
| 1 | Yahoo (`yahoo.py`) | ceny EOD akcji i ETF, GPW i zagraniczne |
| 2 | Stooq (klucz w `.env`) | zapas dla GPW |
| 3 | Ceny ręczne | awaryjnie, gdy 1 i 2 zawiodą |
| FX | NBP tabela A | kursy walut, niezależnie od cen |

**Ceny ręczne awaryjne** (propozycja): użytkownik wpisuje cenę z datą dla waloru, zapis oznaczony `source=manual`, widoczny w UI jako ręczny i nadpisywalny późniejszą ceną automatyczną. Dzienne snapshoty nie mogą stanąć przez awarię jednego dostawcy.

### 3.6 Brakujące ceny i kursy: reguły

- **Forward-fill** ostatniego zamknięcia w dni nienotowane (GIPS 2.A.21 dopuszcza „the last available historical price” jako wartość godziwą). Nie zapisujemy go jako wierszy: `find_close(asset, date)` zwraca ostatnie zamknięcie ≤ `date` z `price_date` i flagą `stale` (ADR tech. 0015).
- **Nieaktualność:** licznik per cena (`price_date` vs `valuation_date`); powyżej progu `stale_price_days` Pozycja jest `stale`. Wartości progu nie ustala ADR tech. 0015 ani kod (grep `stale_price_days` w `backend/`: brak trafień): badanie 05 sugerowało 5 dni roboczych, dokument zbiorczy 7 dni kalendarzowych. **[propozycja]** 5 dni roboczych, do decyzji.
- **FX w weekendy:** forward-fill ostatniego fixingu (NBP publikuje tylko w polskie dni robocze). Wycena na dzień kalendarzowy bierze kurs z tej daty, nie z daty notowania waloru.
- Wektor wyceny na **każdy dzień kalendarzowy** z flagą `is_trading_day` per giełda (proste złączenia, dokładne daty przepływów). Dni nienotowane wyłączone ze statystyk benchmarku.
- Walor bez ceny przed pierwszą Operacją: wycena po cenie Operacji z tego dnia. Brak ceny na koniec okresu przy niezerowej Pozycji: nigdy cicho zero, tylko ostrzeżenie `data_quality` albo odmowa (Ghostfolio: `hasErrors` przy braku ceny na start lub koniec).

### 3.7 Zdarzenia korporacyjne: reguły i źródła

- **Dywidenda:** modelować dzień ustalenia prawa (ex-date), dzień wypłaty, kwotę/akcję, walutę. Przy rozrachunku T+2 (od 2014-10-06) akcje trzeba kupić nie później niż dwie sesje przed dniem dywidendy (https://www.sii.org.pl/7513/analizy/newsroom/nowy-cykl-rozliczeniowy-na-gpw.html, snippet **[niezweryfikowane]**). KDPW (T vs T+2, nie pobrano): https://www.30.kdpw.pl/uploads/user_files/zmiana_cyklu_rozrachunkowego_z_t_plus_3_na_t_plus_2.pdf.
- **Split/scalenie:** współczynnik k, data zmiany w KDPW. Partie: ilość × k, cena / k, TEN SAM koszt i data nabycia (FIFO nie może zmienić kolejności) **[wniosek]**.
- **Źródła:** brak darmowego API maszynowego dla GPW/KDPW/ESPI; kalendarium GPW 8 100 zł/rok, „Operacje na papierach / emisji” 4 900 zł/rok.
- **[propozycja] MVP:** zdarzenia wpisywane ręcznie jako typy Operacji z polem `source_url` (link do raportu ESPI); automat płatny się nie opłaca przy jednym użytkowniku. Pola `source_url` w `portfolios_operation` dziś nie ma.

### 3.8 Infrastruktura wpływająca na pobieranie danych

- **Render free:** usypia usługę po 15 min bez ruchu, wybudzenie trwa ok. minuty. Pobieranie nie może zakładać stale działającego procesu: po wybudzeniu trzeba nadrobić brakujące dni.
- **Postgres:** u nas na Supabase, nie na Renderze. Darmowy Postgres Rendera wygasa po 30 dniach, więc nie jest opcją.
- **Supabase free:** pauzuje projekt po tygodniu bez aktywności; limit 500 MB. Dzienne snapshoty i historia cen/kursów muszą się w nim mieścić.
- **Pooler transakcyjny Supabase:** obsługiwany. Fabryka sesji ustawia `SET LOCAL search_path TO …` w transakcji (`backend/app/infrastructure/sql/factory.py:62`), bo ustawienie sesyjne nie przeżywa przełączania połączeń przez pooler.

### 3.9 Brokerzy: import (później)

Import nie istnieje w kodzie; wchodzi po v1. Wymagania na przyszły importer: surowy plik, mapowanie, `external_id` do deduplikacji, Operacje oznaczone źródłem, test każdego parsera na zanonimizowanym pliku, podgląd przed zapisem. Importer wykrywa kodowanie (UTF-8 BOM / cp1250), separator i separator dziesiętny z próbki; polskie cechy eksportów (przecinek, cp1250, `DD.MM.YYYY`) **nie zostały potwierdzone** dla żadnego brokera.

**XTB (xStation 5), broker docelowy:**

- Źródła: https://www.xtb.com/en/help-center/our-platforms/history-on-the-xstation-platform (snippety, WebFetch 403); myfund, import operacji: https://myfund.pl/index.php?raport=pomoc&helpID=30; wybór transakcji kupna dla XTB (maj 2026): https://myfund.pl/index.php?raport=pomoc&helpID=20.
- Eksport historii konta: zakładki zamkniętych pozycji, "Cash Operations" (wpłaty, wypłaty, dywidendy) i zleceń. Format XLSX; inne źródła wspominają CSV/HTML **[niezweryfikowane]** (strona pomocy XTB zwróciła 403, tylko snippety).
- Kolumny: oficjalnej listy nie znaleziono, więc ich nie zgadujemy. Parser trzeba oprzeć na prawdziwym pliku właściciela.
- Pułapka 1: zamknięte transakcje są łączone w pary kupno/sprzedaż, a otwarte pozycje są jedną pozycją z uśrednioną ceną (myfund, helpID=30). Pozycja uśredniona nie niesie partii potrzebnych do FIFO. Import otwartych pozycji trzeba więc traktować jako stan początkowy albo kasować i wczytywać od nowa.
- Konsekwencja: broker sam identyfikuje partie, więc FIFO aplikacji może dać inny wynik zrealizowany niż raport XTB; import powinien mieć raport uzgodnienia (FAQ myfund tłumaczy takie rozbieżności).
- Pułapka 2: format pliku się zmienia (forum myfund: "XTB - nowy format pliku eksportu"), więc parser musi wersjonować nagłówki i zawodzić głośno.

**Inni brokerzy (po XTB):**

- **Interactive Brokers**, Flex Query Trades (https://www.ibkrguides.com/reportingreference/reportguide/tradesfq.htm): `Currency, FX Rate to Base, Symbol, ISIN, Trade Date, Trade Time, Settle Date Target, Quantity, Trade Price, Proceeds, IB Commission, IB Commission Currency, Cost Basis, Realized PNL, Buy/Sell, Open/Close Indicator, Trade ID, Notes/Codes`; daty `YYYYMMDD` **[niezweryfikowane]**. `FX Rate to Base` to kurs IB, nie NBP.
- **Trading 212** **[niezweryfikowane]**: `Action, Time, ISIN, Ticker, Name, No. of shares, Price / share, Currency (Price / share), Exchange rate, Total (EUR), Charge amount (EUR), Notes, ID`. Nazwa kolumny zawiera walutę konta, więc parser po prefiksie; eksport max 365 dni, więc wiele plików i deduplikacja po `ID`.
- **DEGIRO** **[niezweryfikowane]**: `Date, Time, Product, ISIN, Reference, Venue, Quantity, Price, Local value, Value, Exchange rate, Transaction and/or third, Total`; nagłówki zlokalizowane wg języka UI.
- **Exante**: AUTOCONVERSION jako osobne wiersze przewalutowania **[wniosek]**. **Bossa**: osobny CSV per typ rachunku, więc osobne Portfele **[niezweryfikowane]**.
- Dla mBank, PKO BP, Santander, Revolut kolumn nie znaleziono.

## 4. Metodyka metryk

Podstawa: badanie `05_metodyka_metryk.md` (2026-10-01/02), ADR biz. 0002 i 0004, ADR tech. 0014 i 0016 (Accepted). Standardy: GIPS 2020 (https://www.gipsstandards.org/wp-content/uploads/2021/03/2020_gips_standards_firms.pdf), podręcznik Portfolio Performance (PP, https://help.portfolio-performance.info/en/concepts/performance/time-weighted/).

### 4.1 Dwie główne liczby

„Wynik %” = TWR dzienny (`method.twr = daily_pp_v1`), „Mój zwrot %” = XIRR (`method.irr = xirr_365_v1`) **[propozycja nazw]**. Dziś „zwrot” = `(wartość − wpłaty netto) / wpłaty netto` (`domain/valuation.py:83,88`) i zależy od timingu wpłat. Obok liczb pokazujemy zysk bezwzględny `Gain = MVE − MVB − Σ CF_ext` (wpłaty +, wypłaty −), w walucie bazowej. Dla dowolnego okresu w O(1) ze snapshotów: `Gain(s,e) = MV_e − MV_s − (cum_in_e − cum_in_s) + (cum_out_e − cum_out_s)`. Prostego ROI = Gain/(MVB + Σ wpłat) nie nazywamy „wynikiem”: każdy dostawca definiuje mianownik inaczej, a na brutto wpłatach ROI zaniża wynik przy wypłacie i ponownej wpłacie. Zmiana metody = nowa wartość `method` i nowy ADR.

### 4.2 TWR dzienny (konwencja PP)

```
1 + r_t = (MVE_t + CFout_t) / (MVB_t + CFin_t)
R = Π(1 + r_t) − 1 = I_e / I_s − 1,   I_t = Π_{u≤t}(1 + r_u)
```

- Wpływ zewnętrzny na początku dnia, wypływ na końcu, tuż przed wyceną. Wartość Portfela zawiera gotówkę (GIPS 2.A.11); bez niej każde kupno wyglądałoby jak wpłata. Przepływy zewnętrzne z jednego dnia netujemy.
- Mianownik 0 (`MVB + CFin = 0`): `r_t = 0` i restart (jak `ClientIndex.java` w PP, które ostrzega, gdy wartość pojawiła się znikąd). Pełna wypłata i nowa wpłata po miesiącach: łączenie przez lukę z `r = 0` jest poprawne, ale UI nie sugeruje, że pieniądze „zarobiły 0 %”.
- Okres: zamknięcie dnia startu → zamknięcie dnia końca; Operacje z dnia startu są już w MVB, z dnia końca wliczone (PP-Period). Start sprzed powstania Portfela przycinamy (`effective_start`), bez dopełniania zerami. Presety (start = wycena na zamknięcie): 1D poprzedni dzień wyceny; 1M/3M/6M ten sam dzień N miesięcy wstecz z przycięciem do końca miesiąca (31 mar → 28/29 lut, `dateutil.relativedelta`); YTD 31 grudnia poprzedniego roku (późniejszy start Portfela: od startu); 1Y/3Y/5Y ta sama data wstecz (29 lut → 28 lut), annualizacja dla 3Y i 5Y; MAX dzień przed pierwszym przepływem zewnętrznym (MVB = 0); custom [s, e].
- Prowizje obniżają MVE i `r_t` (TWR netto kosztów, GIPS 2.A.13).
- Przepływy: wpłata, wypłata i wpłata automatyczna — zewnętrzne (Portfel, Grupa); przewalutowanie, kupno, sprzedaż — wewnętrzne (dla Pozycji: przepływ z prowizją, kupno = CFin, sprzedaż i dywidenda = CFout); dywidenda, odsetki od gotówki — dochód wewnętrzny Portfela; prowizja, opłata za prowadzenie rachunku — koszt wewnętrzny, nieprzypisany do Pozycji (lub pro rata). Dywidenda wypłacana wprost na konto poza trackerem = dochód + natychmiastowa wypłata zewnętrzna w dniu wypłaty (inaczej zwrot zaniżony).
- TWR Grupy i Portfela z własnego szeregu, nie średnia TWR składników ani Pozycji; Pozycja ma własną MV i `twr_index`.

**Test złoty (Decimal, równość dokładna).** MVE jest wartością PO przepływach. Dzień 1: MVB 10 000, wpłata 5 000 na początku, MVE 15 300 → 15 300/15 000 = 1,02. Dzień 2: wypłata 2 000 na końcu, MVE 13 000 (mianownik = MVB 15 300 bez CFin, licznik 13 000 + 2 000) → 15 000/15 300 = 0,980392…. Dzień 3: MVE 13 390 → 1,03. TWR = **+3,0000 %** (0,03). Kontrola: +100 %, potem −25 % → 0,50.

### 4.3 XIRR i annualizacja

- Znaki: wpłaty ujemne, wypłaty dodatnie, wartość początkowa jak wpłata, końcowa jak wypłata. Rok = 365 dni: `Σ P_i / (1 + r)^((d_i − d_1)/365) = 0`. Solver na `float` **[propozycja]**, kolejno: (1) walidacja ≥ 1 przepływu ujemnego i ≥ 1 dodatniego, sortowanie po dacie, agregacja przepływów z tej samej daty; dziedzina r > −1; (3) Newton od 0,1 z pochodną `f'(r) = Σ −t_i·P_i·(1+r)^(−t_i−1)`, `t_i = dni_i/365`; akceptacja, gdy `|f| < 1e-10·Σ|P_i|` ORAZ `|Δr| < 1e-12`; przerwanie, gdy krok wychodzi poza (−1, ∞), pochodna ≈ 0 albo > 50 iteracji; (4) fallback: skan siatki r ∈ {−0,9999; −0,99; −0,9; −0,5; 0; 0,5; 1; 2; 5; 10; 100}, zmiana znaku `f`, bisekcja do 1e-12 (≈ 60 iteracji, zawsze zbieżna po zbracketowaniu; SciPy `brentq` to wzorzec, ale zależność to osobna decyzja). Referencje: Excel XIRR (start 0,1, `#NUM!` po 100 próbach); algorytm PP (`IRR.java`): `x = 1 + r`, `npv(x) = Σ v_i / x^(dni_i/365)`, bisekcja na (0, 1) do szerokości < 0,001 (inaczej start x = 1,05), potem Newton ze stopem |Δ| < 1e-5, max 500 iteracji, pochodna numeryczna.
- `IRR_UNDEFINED` — brak zmiany znaku (np. same wpłaty i zerowa wartość końcowa); nigdy ostatnia iteracja. Strumień z jedną zmianą znaku ma co najwyżej jeden pierwiastek r > −1 (reguła znaków Kartezjusza; atrybucja rozszerzenia Laguerre **[niezweryfikowane]**); przy > 1 zmianie znaku skanujemy całą siatkę. `IRR_AMBIGUOUS` — kilka pierwiastków (−100, +230, −132 w t = 0, 1, 2 → 10 % i 20 %, NPV ≈ 1e-14); zwracamy TWR. Kody inline, HTTP 200.
- **Annualizacja:** `(1 + R)^(365/dni) − 1` tylko dla okresu ≥ 365 dni (GIPS 2.A.12). Krótszy: `annualized = null`, `reason = "PERIOD_SHORTER_THAN_ONE_YEAR"`; XIRR < 1 roku → zwrot okresu `(1 + IRR)^(dni/365) − 1`. Motyw: dane z 4.2 jako przepływy z datami dają IRR = 3914 % p.a. (PP pokazuje IRR zawsze p.a., odstępując od GIPS).
- **Modified Dietz** wyłącznie jako fallback dla podokresów bez cen, z `approximation = true`: `R = (B − A − F) / (A + Σ W_i·F_i)`, `W_i = (C − D_i)/C` (koniec dnia) lub `(C − D_i + 1)/C` (początek dnia). Ujemny średni kapitał daje ujemny wynik mimo zysku, zerowy jest nieokreślony. Test Wikipedii: A = 100, B = 300, +50 w połowie roku → 150/125 = 1,20 dokładnie. Dane z 4.2: zysk 390, średni kapitał 14 333,33 → **2,7209 %** (TWR 3,0000 %).

**Złote testy XIRR (tolerancja jawna):** przykład z dokumentacji Excel (2008-01-01 −10 000; 2008-03-01 +2 750; 2008-10-30 +4 250; 2009-02-15 +3 250; 2009-04-01 +2 750) → **0,373362535 ± 1e-8** (Newton autora: 0,3733625335 w 5 iteracjach); PP: 8 × 8 EUR + 2 EUR prowizji = −66 EUR, +111,76 EUR po 255 dniach → 1,1253 ± 1e-4 (kontrola `(111,76/66)^(365/255) − 1 = 1,12528`); annualizacja 30 % w 730 dniach → 0,140175; przepływy IRR = 3914 % p.a.: 2026-01-01 −10 000; 01-02 −5 000; 01-03 +2 000; 01-04 +13 390; wiele pierwiastków: wynik `IRR_AMBIGUOUS` albo 0,10/0,20 z flagą. Rok = 365 dni (PP, Excel XIRR, Ghostfolio).

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

Zysk całkowity nie zależy od metody (test własności). Drugi przykład (PP, 400 akcji, średnio 103 EUR): średnia 1 650 + 1 200, FIFO 2 250 + 600, razem 2 850 w obu. Kurs brokera per partia (średni FX × średnia cena ≠ suma kosztów partii).

### 4.5 Wycena wielowalutowa

- `MV_base = Q × P_local × FX`. `FxMapBuilder` (`services/fx.py`) buduje mapę `(z, do) → rate[z]/rate[do]` (kursy `assets` są „USD za jednostkę”); kolejność: para → odwrotność → pivot **[propozycja]**. `domain/` dostaje gotową mapę.
- Brakujące ceny, forward-fill, flagi `stale`/`missing` i wycena przed pierwszą Operacją: pkt 3.6.
- Brak kursu: pola wyceny pozycji `null` + `rate_missing = true`, sumy Portfela `null` (bez sum częściowych); endpoint kursu zwraca `RATE_MISSING` (404). `exchange_rate = 1` na walucie innej niż USD to wartość domyślna kolumny, nie kurs.
- Efekt FX **[propozycja]**: `1 + R_base = (1 + R_local)(1 + R_fx)`; najpierw cena po starym kursie, potem kurs na nowej cenie (składnik krzyżowy trafia do efektu FX; to konwencja, którą wybieramy raz i nie zmieniamy). Test: 100 → 110 USD, USD/PLN 4,00 → 3,80 → **+4,5 %** = 0,10 − 0,05 − 0,005 (+40 − 22 = +18 PLN).
- Dni nienotowane: forward-fill ceny i kursu; dni bez sesji pomijane w statystykach benchmarku.
- Alokacja: `w_i = MV_i / Σ MV`, gotówka jako osobna klasa (per waluta); walory bez ceny nie są zerowane po cichu.

### 4.6 Snapshoty dzienne i przebudowa (ADR tech. 0016)

- Tabele pochodne `portfolios_daily` (PK `portfolio_id`, `day`: wartość, gotówka, przepływy, `r_day`, `twr_index` `Numeric(24,12)`, `data_quality`) i `portfolios_position_daily` (`portfolio_id, asset_id, date, qty, price_local, fx, mv_base`; **[propozycja]** dla TWR Pozycji dodać `flow_in, flow_out, r_day, twr_index`) oraz skumulowane `cum_in`/`cum_out`.
- `portfolios_portfolio.dirty_from` (`Date`, null = aktualne). Operacja: `LEAST(dirty_from, operation_day)` w transakcji zapisu; korekta ceny/kursu z daty `d`: `LEAST(dirty_from, d)` w `rebuild-dirty`. Nowy dzień nie unieważnia — przebieg dopisuje brakujące dni (nadrabianie po uśpieniu backendu).
- Przebudowa per Portfel: `SELECT … FOR UPDATE`, kasowanie wierszy `≥ dirty_from`, przeliczenie, `dirty_from = null`; idempotentna (drugi przebieg = 0 zapisów).
- Cache i koszt: TWR dowolnego okresu O(1) z `twr_index_e / twr_index_s − 1`; IRR nie ma prefiksu do cache'owania (przepływy okresu + MV_s, MV_e), O(liczba przepływów) na żądanie; metryki kroczące liczone na żądanie z `r_day` w oknie (n ≤ ok. 1 300 dla 5Y), cache po `(portfolio_id, period, last_snapshot_date)`. Normalnie append-only; korekta z dnia d przelicza od wiersza d−1.
- Synchronicznie, gdy `dni × otwarte pozycje ≤ 20 000` **[propozycja; kalibracja w E2.5]**, inaczej `BackgroundTasks` i odczyt z `stale=true`.

### 4.7 Benchmark

ADR biz. 0004: jeden indeks zestawiany z TWR Portfela w tym samym okresie i walucie (najlepiej total return). **[propozycja]** wariant „te same przepływy”: przy każdej zewnętrznej wpłacie `units += CF / P_bench,d` (z FX_d), `Bench_MV_t = units × P_bench,t × FX_t`; porównanie `IRR_portfolio` z `IRR_benchmark` na identycznych przepływach. Wypłata ponad wartość benchmarku → `units` przycięte do 0 i flaga. Gdy szereg nie jest total return: w dniu dywidendy `units += units × div_ps,d / P_bench,d` (indeks cenowy zaniża benchmark). Lustro przepływów zewnętrznych zamiast lustra Operacji (TradingView), bo to drugie pomija bezczynną gotówkę i faworyzuje benchmark. Porównanie w tym samym [s, e] i okresowości (GIPS 2.A.18). Konkurencja: PP (`SecurityIndex.java`) łączy dziennie szereg cen przeliczony na walutę Portfela (cenowy TWR, FX z wybranej daty kalendarzowej); Ghostfolio: prosta zmiana ceny od startu.

### 4.8 Granica Decimal / float (ADR tech. 0014)

| Obliczenie | Typ | Miejsce |
|---|---|---|
| Księga, partie, zysk zrealizowany, `r_day`, `twr_index`, kursy | `Decimal` | `portfolios/domain/` (stdlib) |
| XIRR, statystyki benchmarku | `float` | `services/performance.py` |
| Wektory wykresów | `float` | `services/metrics.py` |

Domyślny kontekst `prec = 28, ROUND_HALF_EVEN`; zaokrąglamy tylko na granicy prezentacji, nigdy w krokach pośrednich, z jawnym trybem w każdym `quantize` (w czystych funkcjach domeny `decimal.localcontext()`). Pieniądze do wyświetlania: `quantize(Decimal("0.01"), ROUND_HALF_UP)`, obliczenia w pełnej skali; dzienny wektor MV bez kwantyzacji. Czynniki `(1 + r_t)`, indeks i TWR: `Decimal` prec 28. Ceny: skala ze źródła; ilości: skala ≥ 8. `Decimal` z potęgą ułamkową jest nieścisły i wolny, więc XIRR i statystyki wyłącznie `float`. Wejście: `float(d)` w jednym miejscu. Wyjście: `Decimal(str(f))` + `quantize` na granicy API (stopy 6 miejsc, procenty 2); nigdy `Decimal(f)` (importuje szum binarny, np. 0.1000000000000000055…); wolno `Decimal(repr(f))`. Wynik statystyki nie wraca do księgi, partii ani snapshotu (poza `twr_index`). `numpy` tylko w `services/`. Testy: `Decimal` — równość dokładna, `float` — jawna tolerancja. Otwarte: czy `Numeric(24,12)` wystarcza po 10 latach.

**Testy własności:** wpłata skalowana z MV nie zmienia TWR; bez przepływów annualizowane IRR = TWR; Total P/L równy dla FIFO i średniej; dwa przebiegi przebudowy dają identyczne wiersze; łączenie `R(a,c) = (1 + R(a,b))(1 + R(b,c)) − 1`; suma MV Pozycji = MV Portfela − gotówka. Walidacja krzyżowa: eksport przykładowego Portfela do PP (import CSV) i porównanie TTWROR, IRR i zrealizowanych zysków FIFO (oczekiwane drobne różnice: FX z EBC vs NBP).

### 4.9 Dywidendy: stopy i prognoza

```
DPS_TTM = Σ DPS z ex-date w (t−365d, t];   yield_TTM = DPS_TTM / cena;   forward_yield = oczekiwane DPS (12 mies.) / cena
YoC = roczne DPS / średni (lub partii) koszt na akcję;   dochód_TTM = Σ otrzymanych dywidend z datą wypłaty w (t−365d, t]
```

Test: DPS kwartalnie 0,55, cena 44, koszt 30 → yield 2,20/44 = **5,00 %**, YoC 2,20/30 = **7,33 %**. Pułapki: YoC rośnie z ceną bez zmiany dywidendy, więc nie jest miarą zwrotu; ex-date decyduje o uprawnieniu i DPS_TTM, data wypłaty o dochodzie gotówkowym; dywidendy specjalne (flaga `is_special`, **[propozycja]**) wyłączone z prognozy; historyczne DPS korygować współczynnikiem splitu; Ghostfolio `dividendYieldPercent` to zrealizowany dochód / średnia inwestycja, nie stopa rynkowa. Prognoza **[propozycja]**, od najpewniejszej: (1) ogłoszone a niewypłacone × akcje na ex-date; (2) ostatnia regularna DPS × częstotliwość × bieżące akcje, daty = zeszłoroczne ex-date + rok; (3) DPS_TTM × bieżące akcje rozłożone na zeszłoroczne miesiące. Zawsze etykieta „szacunek”, FX z dnia obliczenia. Kalendarz per Pozycja: przewidywane i faktyczne ex-date i wypłaty na 12 mies.

## 5. Stan aplikacji i luki

Stan na 2026-10-03, kod z HEAD `5fddc10` (HEAD `7fa9c9e` zmienia tylko dokumenty; kod przeczytany, testów nie uruchamiano). Dokument badawczy `06_stan_found-tracker_vs_cel` to migawka z `9eda5fe` (2026-10-01/02) - kod poszedł dalej; kolumny „przed poprawką” i dowody G niżej pochodzą z tej migawki, wartości „dziś” z kodu.

### 5.1 Co aplikacja ma dziś

- **Stos:** FastAPI + SQLAlchemy + Alembic, Python 3.14, Postgres; warstwowy monolit modułowy (`api -> services -> repositories`, czysta `domain/`), moduły `security`, `core_data`, `assets`, `portfolios`. Frontend: React 19, Vite, MUI 7, TanStack Query/Table, Recharts 3. CI: ruff, `mypy --strict`, `alembic check`, pytest; gitleaks, pip-audit i npm audit nieblokujące. Auth: JWT HS256 (access 30 min, refresh 1 dzień). Wersje: `yfinance==1.3.0`, `numpy==2.4.6`, `pandas==3.0.3`, `python-jose==3.5.0`, `mypy==2.3.0`; `passlib==1.7.4` nieużywany. Uruchomienie: `pip install -r requirements.txt`, `alembic upgrade head`, `python -m seed.seed`, `pytest` (z `TEST_DATABASE_URL`; `-m "not integration"` też go wymaga), frontend z `VITE_API_URL`.
- **Modele (6 tabel, 2 migracje):** `users`; `assets_assetclass`; `assets_currency` (`exchange_rate` = **USD za 1 jednostkę**); `assets_asset` (jedna `current_price`, bez historii); `portfolios_portfolio` (`cash_balance`, `total_deposited` - jedna pula gotówki w walucie bazowej); `portfolios_position` (średnia ważona: `average_buy_price` z prowizją, `average_fx_rate`, `total_fees`, `total_dividends`); `portfolios_operation` (`buy/sell/deposit/withdrawal/dividend`, `fx_rate`, `operation_date`).
- **Uwagi o schemacie:** kaskada usuwania tylko w ORM (`cascade="all, delete-orphan"`, `portfolio.py:59-62`), bez `ON DELETE CASCADE` w FK - usunięcie poza ORM zostawia sieroty; `operation_type` to `String(20)` bez `CHECK` (`operation.py:41`); `Currency.base_currency_id` nieużywane przez logikę; `User` bez znaczników czasu; `exchange_rate` `Numeric(18,9)`, `cash_balance` `Numeric(18,3)`, `amount` `Numeric(18,2)`; ticker `strip().upper()`; indeks `(portfolio_id, operation_date)`. `CHECK` tylko w nowych tabelach, stare kolumny pozostają bez ograniczeń.
- **Endpointy:** `/auth/*`; `/assets/{asset-classes,currencies}` (CRUD), `/assets/` (+ `search-yahoo` po dokładnym tickerze, `create-from-yahoo`); `/portfolios/` (CRUD); `/portfolios/operations` (CRUD; każda zmiana = pełna przebudowa księgi); `GET /portfolios/positions` (czysty odczyt po zapisanych cenach) i `POST /portfolios/positions/refresh` (odświeża kursy i ceny z Yahoo); `GET /portfolios/fx-rate`; `GET /portfolios/portfolio-vectors` (wektory dzienne, numpy).
- **Frontend:** kokpit, widok Portfela (pozycje, dialogi kupna/sprzedaży/gotówki), historia operacji, wykresy, porównanie do 4 Portfeli.
- **Księga:** średnia ważona (nie FIFO), brak zysku zrealizowanego. `domain/valuation.py:28-31` (`_percent`) zwraca 0 przy dzieleniu przez zero (zwrot % bez kosztu lub wpłat) - sprzeczne z zasadą „brak wartości = `null`”; docelowo `None` + `reason` (`NO_COST_BASIS`, `NO_DEPOSITS`). Wektory (`metrics.py`) rzucają błąd zamiast zer.
- **Dane rynkowe:** ceny wyłącznie Yahoo na żądanie; brak NBP, tabel historii cen i kursów, harmonogramu (`entrypoints.py`/`cli.py` nie istnieją). Adapter `yahoo.py` (stan z migawki, nieprzeczytany ponownie): bez retry, timeoutów, limitów i cache; każdy wyjątek -> `MarketDataUnavailableError`; kurs FX z `{FROM}{TO}=X` w kolejności bid -> regularMarketPrice -> previousClose; `search` przy awarii zwraca `[]` (użytkownik widzi „brak wyników”), `create-from-yahoo` zwraca 502. Wymaganie E1.2: timeout, ograniczone retry z backoffem, rozróżnienie „brak wyników” od „dostawca niedostępny”.
- **Porównanie Portfeli (`PocketComparisonPage.tsx:35-44, 62-84`):** 4 zaszyte hooki `usePocketVectors`, wartość normalizowana do 100 na starcie (`pocket_value_vector[idx] / startVal * 100`), więc wpłaty i wypłaty wyglądają jak zysk lub strata - dokładnie to, co ma naprawić TWR. Naprawa: porównywać `twr_index` (E2.5/E3.5), hooki zastąpić `useQueries` z limitem po stronie UI.
- **Pokrycie testami (liczby z migawki, nieprzeliczone):** unit ledger 28, parity 7, valuation 6, metrics_service 13, architektura 18 (egzekwuje warstwy, brak repo w API, `HTTPException` tylko w `dependencies.py`, `yfinance` tylko w infrastructure, commit tylko w `transaction()`). Niepokryte wg migawki: FX w wycenie, wektory wielowalutowe, dywidendy w wektorach, cały frontend (brak runnera w `package.json`; Vitest w E0.7). Integracyjne testy izoluje zewnętrzna transakcja z rollbackiem i savepointami.

### 5.2 Defekty F1-F6

Dokument źródłowy wymaga testu odtwarzającego przed poprawką; „przed” = migawka `9eda5fe`.

| # | Przed poprawką (`9eda5fe`) i skutek | Status w kodzie | Dowód dziś |
|---|---|---|---|
| F1 | `refresh_currency_rates` ustawia kursy jako „USD za jednostkę” (`assets/services/market_data.py:109`, `assets/constants.py:4`), a `_value_holding` mnoży przez `asset.currency.exchange_rate` bez względu na walutę bazową (`valuation.py:55-57`, `positions.py:37`). Portfel PLN + akcja USD zostaje w USD (×1), + akcja EUR wychodzi w USD (×1,08); koszt idzie po `average_fx_rate`, więc zysk niezrealizowany miesza jednostki. Test odtwarzający: Portfel PLN, akcja USD i EUR, kurs krzyżowy `rate[z]/rate[do]` | **Naprawiony (PR #2).** `FxMapBuilder` składa kurs krzyżowy; brak kursu (`exchange_rate == 1` dla waluty innej niż USD) daje `rate_missing`, nie ciche ×1 | `portfolios/services/fx.py:42-90`; `portfolios/domain/valuation.py:64-85` |
| F2 | Koszt bez `fx_rate`, wartości walorów nieprzeliczane, dywidenda tylko jako koszt prowizji (`metrics.py:108-116, 185-187`). Wykresy wielowalutowe błędne; `free_cash_vector` != `cash_balance` po dywidendzie; zysk zaniżony o dywidendy | **Naprawiony w kodzie (nie wiążę z PR).** Koszt i dywidenda mnożone przez `fx_rate`; dywidenda zasila `free_cash` i `profit`. **Ograniczenie zostaje:** wartość walorów = ilość x zamknięcie w walucie waloru, bez przeliczenia (brak historii kursów); bez `portfolioName` wektory mieszają waluty | `portfolios/services/metrics.py:113-133, 270-273`; docstring l.21-25 |
| F3 | „Całkowita wartość” = suma samego `cash_balance`; `positionsCount` = liczba Portfeli; sumy bez przeliczenia walut (`DashboardPage.tsx:14, 36`). Główna liczba aplikacji pomijała wartość pozycji | **Częściowo naprawiony (PR #3).** Suma = `total_value ?? cash_balance` przeliczona na PLN (`baza/PLN`); Portfele z `rate_missing` wyłączone z sum + ostrzeżenie; brak kursu PLN = alert błędu. **Nadal błędne (zweryfikowane w kodzie):** `positionsCount={totalMetrics.pocketCount}` (`DashboardPage.tsx:64`, liczba Portfeli, nie pozycji); `PortfolioOverview` zawsze w PLN (`portfolio-overview.tsx:27`), a wpłaty netto podpisuje „Kapitał początkowy” (`:116`); przy braku `total_value` fallback to gotówka; waluta wyświetlania zaszyta na PLN | `DashboardPage.tsx:13-14, 20-37, 64` |
| F4 | Domyślny `fx_rate` z `selectedAsset.currency.exchange_rate` - kurs wobec USD (`BuyAssetDialog.tsx:55-69`, kurs l.63); dla Portfela nie-USD błędny kurs trafiał do `average_fx_rate` | **Naprawiony (PR #2).** Kupno i sprzedaż pobierają `GET /portfolios/fx-rate`; przy braku kursu pole puste, wymaga ręcznego wpisu | `BuyAssetDialog.tsx:55-79`; `SellAssetDialog.tsx:43-67`; `portfolios/api/fx_rates.py:17` |
| F5 | Walor tworzony po tickerze w POST Operacji dostawał `currency_id=portfolio.base_currency_id` (`operations.py:176-180`); zagraniczna akcja w Portfelu PLN zapisana jako Walor w PLN - wycena i FX trwale błędne | **Naprawiony w kodzie.** Waluta z notowania dostawcy; waluta Portfela tylko gdy dostawca nie zna tickera lub nie działa (plan E0.4 chciał tu 502) | `assets/services/assets.py:193-231`; `portfolios/services/operations.py:174` |
| F6 | Zmiana waluty bazowej ustawiała pole bez przeliczenia gotówki, `total_deposited` i historii (`portfolios.py:150-153`) - ta sama liczba cicho zmieniała walutę | **Naprawiony w kodzie:** 409 `PORTFOLIO_CURRENCY_LOCKED`, gdy Portfel ma operacje | `portfolios/services/portfolios.py:167-174`; `portfolios/exceptions.py:49` |

Także zamknięte względem migawki: operacja wsteczna przechodzi przez pełny `rebuild()` pod blokadą wiersza Portfela (`portfolios/services/operations.py:84-117`; G15); tickery GPW w seedzie mają `.WA` (`backend/seed/seed_data.py:132,141,150`); odświeżanie jest osobnym `POST .../refresh`, a `GET` nie ma skutków ubocznych.

### 5.3 Znane błędy i zagrożenia w kodzie

- **`opened_at` pozycji.** `Position.opened_at` ma `server_default=func.now()` (`portfolios/models/position.py:52`), a przebudowa tworzy wiersz bez tej wartości (`portfolios/services/operations.py:205-215`). Pole przechowuje czas **zapisu wiersza**, nie `operation_date` pierwszego zakupu; dla importu lub operacji wstecznej „data otwarcia” jest późniejsza niż pierwszy zakup. Poprawka: ustawiać z daty pierwszej operacji przy tworzeniu wiersza, w E2.0 (aktualizacja pozycji w miejscu, kolumny `operation_day`).
- **Seed z kontem `admin`.** `backend/seed/seed_data.py:64-65` tworzy `admin@foundtracker.com` z hasłem `admin` (zweryfikowane). Uruchomiony na produkcji (Render) da logowalne konto ze znanymi poświadczeniami, mimo planu „dane od zera” i zamkniętej rejestracji (E0.6, `is_owner`). **[propozycja]** seed nie działa na produkcji; konto właściciela przez `python -m app.cli create-user` i `set-owner`; seed czyta e-mail i hasło ze zmiennych środowiskowych i odmawia startu bez nich; test: seed bez zmiennych kończy się błędem.
- **Testy księgi a przejście na FIFO.** `portfolios/tests/unit/test_ledger_parity.py` istnieje (7 funkcji testowych, ziarna losowe stałe). Pięć z nich (wpłata, wypłata, błędne dane, dwie „destroy”) nie zależy od metody kosztu. Dwa (`test_buy_random_assets_with_replacement`, `test_buy_sell_random`) zakładają średnią ważoną: `:84` porównuje `average_buy_price` z `cost / quantity`, a `:101,131` wymaga, by sprzedaż **nie zmieniała** średniej ceny (komentarz: „Weighted average, unchanged by a sell”). Po E2.4 (partie FIFO) sprzedaż zmieni koszt pozostałych partii, więc te dwa staną się czerwone; ich kontrakt gotówkowy (`state.cash_balance == expected_cash`) pozostaje ważny. Decyzja przed E2.4: (a) przepisać je na parytet kwot gotówki i sumy Total P/L (niezależne od metody kosztu) albo (b) zamrozić jako `legacy_average` i usunąć po akceptacji ADR 0002. Nie wyłączać po cichu. Nagłówek pliku powołuje się na usunięty kod referencyjny i trzeba go przepisać niezależnie od wyniku.

### 5.4 Luki wobec celu v1 (G1-G25, tylko zakres v1)

Numeracja z migawki; pominięte G8, G10, G11, G17, G25 leżą poza zakresem v1. Dowody `plik:linia` ze stanu `9eda5fe`; nie wszystkie sprawdzono w HEAD.

| G | Luka i skutek | Dowód | Naprawa |
|---|---|---|---|
| G1 | Brak historii cen i kursów (`Asset.current_price`, `Currency.exchange_rate` nadpisywane); każdy wykres pyta Yahoo - wolne, niestabilne wykresy; brak wyceny historycznej walorów obcych (reszta F2) | `metrics.py:172` | E1.1 (`assets_price`, `assets_fx_rate`), ADR tech. 0015 |
| G2 | Brak odświeżania w tle i nadrabiania zaległości (Render usypia usługę) - ceny nieaktualne bez ręcznego `refresh` | `find`: brak `entrypoints.py`/`cli.py` | E1.4, ADR tech. 0017 |
| G3 | Brak snapshotów dziennych i TWR/XIRR; zwrot = (wartość - wpłaty netto)/wpłaty netto - nieporównywalny z benchmarkiem | `valuation.py:83,88` | E2.5 (ADR tech. 0016), E3.1 |
| G4 | Brak zysku zrealizowanego (sprzedaż: średnia bez zmian) | `ledger.py:204-225` | E2.4, E3.2 |
| G5 | Średnia ważona zamiast partii/FIFO | `ledger.py:184-196` | E2.4 |
| G6 | Brak splitów i typów interest/fee/przewalutowanie (enum: `buy/sell/deposit/withdrawal/dividend`) - błędna ilość i cena po splicie | `enums.py:9-14` | E2.3, E8.1 |
| G7 | Jedna pula gotówki w walucie bazowej; brak typu przewalutowania - nie odwzorujemy rachunku wielowalutowego | `portfolio.py:38-43` | E2.2 |
| G9 | `fx_rate` Operacji wpisywany ręcznie, brak kursu historycznego - błędny koszt przy pomyłce | `ledger.py:170` | E1.1, E1.2 |
| G12 | Tylko Yahoo, brak NBP; wyszukiwanie po dokładnym tickerze; domyślna waluta USD - brak oficjalnych kursów i wyszukiwania po nazwie | `market_data.py:49-68`; `constants.py:4` | E1.2, E1.3 |
| G13 | Brak importu XTB - ręczne wpisywanie operacji | grep | E4 (po dostarczeniu eksportu) |
| G14 | Brak benchmarku: `benchmarkService.getSP500Data()` zwraca `null`, nieużywany | `benchmarkService.ts:29-37` | E1.6, E3.5 |
| G15 | Backdating bez walidacji historii w POST | `operations.py:99-126` | zamknięte (E0.3) |
| G16 | Brak Grup portfeli i agregacji w jednej walucie; `portfolio-vectors` bez nazwy miesza waluty | `metrics.py:328-330` | E2.1, E3.4 |
| G18 | Brak audytu i miękkiego usuwania (ADR-0011 odłożony) | `docs/technical/adr/0011-audyt-odlozony.md` | `status=void` (E2.3) |
| G19 | Operacje bez paginacji i filtrów - wolna lista | `repositories/operations.py:32-45` | E2.7 |
| G20 | Dane referencyjne (Walor, Waluta) edytowalne przez każdego użytkownika; rejestracja otwarta - ryzyko przy publicznym hostingu | `assets/api/*.py` | E0.6 |
| G21 | Brak ustawień użytkownika (waluta wyświetlania), `/settings` martwy - zaszyte PLN | `user.py:7-13`; `dashboard-header.tsx:94` | E0.9 |
| G22 | Luki frontendu (niżej) | migawka §5 | E0.7, E0.10, E11.6 |
| G23 | Z UI tylko data, kolejność dnia wg `created_at` - niejednoznaczna | `BuyAssetDialog.tsx`; `repositories/operations.py:53-57` | E2.0, E2.7 |
| G24 | Wycena nieaktualna w `/portfolios/` i `/{id}` (do potwierdzenia) | `services/portfolios.py:63-64` vs `positions.py:37-39` | E1.7 |

**Luki frontendu (G22).** Brak edycji Operacji i wpisu dywidendy; `CashOperationDialog` z `fee: 0` na sztywno (`CashOperationDialog.tsx:42`, zweryfikowane) - brak prowizji przy wpłacie/wypłacie; brak UI do zarządzania Walorami, Walutami i Klasami oraz zmiany nazwy Portfela; brak alokacji wg klasy/sektora/waluty/kraju i wykresu wartości na dashboardzie; `MiniLineChart` (`components/charts/MiniLineChart.tsx`) nigdzie nieużywany; zakładki nagłówka bez linku i nieistniejące trasy (`dashboard-header.tsx:52-53`); nazewnictwo „Pocket” zamiast „Portfel”; brak testów frontendu.

### 5.5 Ryzyka porządkowe

- Splity (G6, E8.1): zdarzenia korporacyjne to największa ukryta praca konkurencji (zob. sekcja 2).
- Słownik: `CONTEXT.md` zabrania „lot” i „transakcja”, a planowane `portfolios_lot`, `portfolios_lot_consumption`, `LotBook` używają „lot” - **[propozycja]** w E2.6 dopisać „Partia zakupu = `lot`” (kod angielski, UI i dokumenty po polsku).
- Niespójności dokumentacji: `CLAUDE.md` wymienia jako otwarte `mypy` (R-10), reguły ai-tools (R-11) i CI (R-12), choć CI z `mypy --strict` działa; opis `python-jose 3.3.0` jest nieaktualny (w kodzie `3.5.0`); `05_portfolios_module.md:164` nadal nazywa `mypy` nieuruchamianym.
- Domyślne `auto_adjust` w `yfinance` - **[niezweryfikowane]**; do rozstrzygnięcia na wersji 1.3.0 przed E1.1.

## 6. Architektura docelowa

Stan kodu (2026-10-03, `backend/app/modules/*/models`): istnieją tylko `assets_asset`, `assets_currency`, `assets_assetclass`, `portfolios_portfolio`, `portfolios_operation`, `portfolios_position`; reszta jest do zbudowania. Dane startują od zera (seed albo import). ADR tech. 0013–0017, 0019, 0020 oraz biz. 0001–0005, 0007 mają status Accepted; ADR tech. 0018 (import) jest Proposed. Gdy szkice (doc 07/09) różnią się od ADR-ów, wygrywa ADR.

### 6.1 Moduły i kierunki zależności

| Moduł | Może zależeć od | Zawartość |
|---|---|---|
| `core_data` | — (dług: `→ security`, cykl `users.py:7` ↔ `auth.py:2`) | użytkownicy (`is_owner`), `core_data_user_settings` |
| `security` | `core_data` | JWT, logowanie |
| `assets` | — | walory, waluty, ceny, kursy |
| `portfolios` | `assets`, `core_data` | księga, partie, snapshoty, import |

Zakazane: `assets → portfolios|core_data|security`. Moduły wołają się wyłącznie przez serwisy (ADR tech. 0006); graf egzekwuje `test_architecture.py`. Import żyje w `portfolios` (osobny moduł dałby cykl FK); port `ImportParser` w `core/import_parser.py`, adapter XTB w `infrastructure/import_parsers/`. Numeryka (ADR tech. 0014): księga, partie, `r_day`, `twr_index`, kursy na `Decimal` w `domain/` (tylko stdlib); XIRR i statystyki benchmarku na `float`/`numpy` wyłącznie w `services/`, wynik jako `Decimal(str(f))` z `quantize`. Migracje tylko `alembic revision --autogenerate`; zmiana typu istniejącej kolumny zakazana, stąd nowa `operation_day` (ADR tech. 0019); nowe kolumny nullable lub z `server_default`.

### 6.2 Model danych

Konwencje: PK `id BigInteger`; `owner_id` tylko w danych osobistych (dane referencyjne globalne). Typy: kwoty `Numeric(18,2)`; salda gotówki `(18,3)`; ceny, ilości, kursy `(18,9)`; `r_day` `(18,12)`; `twr_index` `(24,12)`; wartości wyliczeniowe jako `String`, `CHECK` tylko w nowych tabelach (walidacja typów Operacji w serwisie, ADR tech. 0020). Tabele pochodne (partie, salda, snapshoty, `auto_flow`) nie są celem FK z danych użytkownika; odwołania idą do `portfolios_operation.id`.

**`portfolios_portfolio`.** UNIQUE `(owner_id, name)` (bez zmian), nowy indeks `(owner_id, is_active)`. Nowe: `account_type` `String(10)` NOT NULL domyślnie `regular` (etykieta bez walidacji zbioru), `broker` `String(60)` NULL, `auto_funding` bool NOT NULL false, `dirty_from` `Date` NULL (snapshoty `day ≥ dirty_from` nieaktualne; NULL = aktualne). *Rozbieżność:* doc 07 i 09 podają `String(30)`; ADR biz. 0001 mówi `String(10)` i to obowiązuje. Zmiana `base_currency_id` przy istniejących Operacjach: 409 `PORTFOLIO_CURRENCY_LOCKED`.

**`portfolios_operation`.** Istniejące bez zmian: `portfolio_id` FK, `asset_id` FK NULL, `operation_type` `String(20)`, `quantity`/`price` `(18,9)` domyślnie 0, `amount` `(18,2)` NULL, `fee` `(18,2)` domyślnie 0, `fx_rate` `(18,9)` domyślnie 1 (kurs brokera: waluta waloru → waluta Portfela), `notes`, `operation_date` timestamptz NOT NULL (indeks `ix_operation_portfolio_date` zostaje), `created_at`.

| Nowa kolumna | Typ / NULL | Znaczenie |
|---|---|---|
| `operation_day` | `Date` NOT NULL | `operation_date` w Europe/Warsaw, wyliczana przy zapisie; od niej kolejność i snapshoty |
| `sequence` | `Integer` NOT NULL, 0 | numer w (Portfel, `operation_day`), nadawany automatycznie; w żądaniu tylko do zmiany kolejności w dniu |
| `currency_id` | FK `assets_currency` NOT NULL | waluta `price`/`amount`/`fee`; domyślnie waluta waloru, dla wpłaty/wypłaty/odsetek/opłaty waluta bazowa Portfela (ADR biz. 0003) |
| `counter_amount`, `counter_currency_id` | `(18,2)` / FK, NULL | noga przychodząca przewalutowania; `amount` = noga wychodząca |
| `ratio` | `(18,9)` NULL | split nowe:stare, serwis wymaga `> 0` |
| `external_ref` | `String(120)` NULL | id z pliku brokera (deduplikacja) |
| `import_batch_id` | FK NULL, `ON DELETE RESTRICT` | paczka importu |
| `edited_at` | timestamptz NULL | ręczna edycja; blokuje cofnięcie paczki |

Klucz księgi `(operation_day, sequence, id)` zastępuje `(operation_date, created_at, id)`. Nowe `operation_type`: `interest`, `fee`, `currency_exchange`, `split` (doc 07/09 piszą `fx_exchange`; ADR tech. 0020 `currency_exchange` — przyjęto ADR). Indeksy: UNIQUE częściowy `(portfolio_id, external_ref) WHERE external_ref IS NOT NULL`; `(portfolio_id, operation_day, sequence, id)`; `(asset_id, operation_day)`. **Brak kolumny `status`** (draft/posted/void) w ADR-ach; dotyczy kroku spoza v1, nie wprowadzamy jej.

**Tabele nowe.**

| Tabela | Kolumny i ograniczenia |
|---|---|
| `portfolios_lot` (pochodna) | `portfolio_id`, `asset_id` FK; `open_operation_id` FK CASCADE, UNIQUE; `split_ratio` =1; `acquired_on` (dzień zakupu, niezmienny przy splicie); `quantity_initial`, `quantity_open`, `unit_price` `(18,9)`, `CHECK 0 ≤ quantity_open ≤ quantity_initial`; `cost_local`, `cost_base` `(18,2)` (koszt pozostałej ilości z prowizją; waluta waloru / Portfela po kursie brokera); `fx_rate` =1; `closed_on` NULL. Split nie tworzy Operacji otwierającej. Indeks FIFO `(portfolio_id, asset_id, acquired_on, open_operation_id) WHERE quantity_open > 0` |
| `portfolios_lot_consumption` (pochodna) | `lot_id`, `close_operation_id` FK CASCADE; `closed_on`; `quantity` `CHECK > 0`; `proceeds_local`, `cost_local`, `fee_local`, `proceeds_base`, `cost_base` `(18,2)`; UNIQUE `(lot_id, close_operation_id)`. `proceeds` = brutto; prowizja sprzedaży proporcjonalnie na partie, reszta zaokrąglenia na ostatnie zużycie; zysk zrealizowany = `proceeds − cost − fee` |
| `portfolios_cash_balance` (pochodna) | UNIQUE `(portfolio_id, currency_id)`; `balance` `(18,3)`; ujemne saldo odrzuca księga (`INSUFFICIENT_CASH`), nie CHECK |
| `portfolios_auto_flow` (pochodna) **[propozycja]** | `portfolio_id`, `trigger_operation_id` CASCADE, `currency_id`, `amount`, `flow_day`, `sequence`. Wirtualna wpłata przy niedoborze **zakupu** (`auto_funding`); dywidendy i odsetki nie są wirtualną wypłatą. Przebudowa buduje ją od zera; TWR/XIRR czytają ją jako przepływy zewnętrzne (ADR biz. 0003) |
| `portfolios_group` | `owner_id`, `name` `String(100)`, `currency_code` `String(3)` NULL (NULL = waluta wyświetlania), `created_at`; UNIQUE `(owner_id, name)` |
| `portfolios_group_member` | PK `(group_id, portfolio_id)`, CASCADE; Portfel w wielu Grupach, jeden właściciel; Grupa nie ma Operacji |
| `portfolios_commission_rule` | domyślna prowizja podpowiadana w formularzu: `portfolio_id`; `asset_type` NULL (= wszystkie); `rate_pct` `(9,6)` `CHECK ≥ 0`; `min_fee` `(18,2)`; `currency_id` NULL; UNIQUE `(portfolio_id, asset_type)` |
| `portfolios_daily` (pochodna) | PK `(portfolio_id, day)`; `value`, `cash`, `positions_value`, `income`, `fees`, `ext_in`, `ext_out`, `cum_ext_in`, `cum_ext_out` `(18,2)` (waluta Portfela, kursy dnia); `r_day` `(18,12)` NULL (przy wartości początkowej 0); `twr_index` `(24,12)`; `data_quality` `String(12)` (`ok/stale/synthetic/missing`; `missing` = brak ceny przy niezerowej pozycji, nie wyceniamy na zero). Dni kalendarzowe, dni bez sesji z przeniesioną wyceną |
| `portfolios_position_daily` (pochodna) | PK `(portfolio_id, asset_id, day)`; `quantity`, `price_local` NULL, `fx`; `mv_local`, `mv_base`, `cost_base`, `flow_in`, `flow_out`, `r_day`, `twr_index`; `is_stale`, `is_synthetic`; indeks `(asset_id, day)`; ~110 tys. wierszy/Portfel (30 walorów × 10 lat) **[wniosek]** |
| `portfolios_market_cursor` | jeden wiersz: `id` PK `CHECK id = 1`, `last_change_id` `BigInteger`. `rebuild_dirty` czyta zmiany po kursorze przez serwis `assets`, ustawia `dirty_from`, przebudowuje i przesuwa kursor w jednej transakcji (ADR tech. 0016) |
| `assets_price` | UNIQUE `(asset_id, price_date, source)`; `close` `(18,9)` `CHECK > 0`, nieskorygowany (`auto_adjust=False`); `currency_id`; `source` (`yahoo`, `manual`); `is_synthetic`; `fetched_at`; indeks `(asset_id, price_date DESC)` |
| `assets_fx_rate` | UNIQUE `(from, to, rate_date, source)`; `CHECK from <> to`; `rate` `(18,9)` `CHECK > 0` (ile `to` za 1 `from`); `source` ∈ {`nbp`,`manual`}; `is_synthetic`; trzymamy pary notowane u źródła (NBP: waluta→PLN). Numeru tabeli NBP nie ma gdzie zapisać — **[propozycja]** `source_ref` `String(40)` albo rezygnacja |
| `assets_listing` | UNIQUE `(asset_id, provider)`, `(provider, symbol)`; `symbol` `String(40)` (np. `PKN.WA`); `priority` `SmallInteger` =100 (mniej = ważniejsze; `manual` poza tabelą); `is_enabled` =true; `last_success_at`, `last_error_at`, `last_error` |
| `assets_price_change` | dziennik korekt historii, zapisywany w tej samej transakcji co korekta (cena/kurs o dacie starszej niż najnowsza w serii albo zmiana wartości; nowy dzień nie wpisuje nic): `id` rosnący, `kind` (`price`/`fx`), `asset_id` albo para walut, `changed_from` `Date`, `recorded_at` |
| `job_run` | patrz 6.5 |
| `portfolios_import_batch/_row/_override` | później (ADR tech. 0018, Proposed): UNIQUE `(owner_id, sha256)`, `status` draft/committed/reverted, `size_bytes ≤ 10485760`; wiersz `row_status` `ok/duplicate/unrecognized/error/skip`, UNIQUE `(batch_id, row_no)`. Cofnięcie usuwa Operacje paczki, chyba że któraś ma `edited_at` (409). Zatwierdzenie = `record_many` bez commitu + jedna przebudowa (dziś `_record` commituje: `portfolios/services/operations.py:99-100`) |

**Kolumny użytkowników i walorów.** `users.is_owner` Boolean NOT NULL `server_default false`, ustawiany CLI `set-owner`; do tego czasu zapisy globalne → 403 `REFERENCE_DATA_OWNER_ONLY`. `core_data_user_settings` (jeden wiersz, tworzony leniwie przy pierwszym `GET`): `user_id` UNIQUE FK; `display_currency_code` `String(3)` =`PLN` (bez FK, weryfikowany przy wycenie); `stale_price_days` `SmallInteger` =7 `CHECK ≥ 1`; `benchmark_asset_id` `BigInteger` NULL (bez FK, weryfikowany przy odczycie — tu zapisany jest wybrany benchmark); `updated_at`. `assets_asset` nowe: `isin` `String(12)` NULL UNIQUE; `mic` `String(4)`; `country` `String(2)`; `asset_type` `String(10)` NOT NULL =`stock` (`stock`/`etf`, walidacja w serwisie); `archived_at` timestamptz NULL. `ticker` zostaje globalnie UNIQUE (sufiks giełdy). **[propozycja]** `asset_type` (rodzaj instrumentu, domyślna prowizja) jest rozłączny z Klasą waloru (`assets_assetclass`, słownik użytkownika do alokacji).

**`portfolios_position`** (kolumny bez zmian; UNIQUE `(portfolio_id, asset_id)`): przebudowa aktualizuje w miejscu (zachowuje `opened_at`); docelowo agregat Partii (suma `quantity_open`), `average_buy_price` tylko do prezentacji.

**Kolumny pochodne i cache.**

| Kolumna | Reguła |
|---|---|
| `portfolio.cash_balance` | cache salda w walucie bazowej Portfela (linia `cash_balance` dla `base_currency_id`); sumę wielowalutową liczy serwis kursem wyceny; zapisywana przez `rebuild`; termin usunięcia otwarty (ADR biz. 0003) |
| `portfolio.total_deposited` | wpłaty − wypłaty w walucie bazowej, obca waluta przeliczona po `fx_rate` (ADR biz. 0003 mówi „kurs dnia”; doc 07: kurs Operacji — **do potwierdzenia**); nie jest podstawą TWR |
| `asset.current_price` | cache ostatniej ceny, zapisywany w tej samej transakcji co cena; nowe odczyty idą przez `find_close` |
| `currency.exchange_rate` | cache, kolumna nullable; brak kursu = `RATE_MISSING`, nigdy domyślne 1; `base_currency_id` wygaszane |

**Reguły.** FIFO per (Portfel, Walor); split zmienia `split_ratio`, nie koszt (biz. 0002). Przewalutowanie to jeden wiersz, prowizja w walucie wychodzącej (tech. 0020). Dwa kursy: brokera (`operation.fx_rate`, koszt i gotówka) i wyceny (`assets_fx_rate`, dzienny). Kurs krzyżowy składa `portfolios` (`FxMapBuilder`: para → odwrotność → pivot **[propozycja]**). Źródło ceny: `manual` zawsze pierwsze, dalej `assets_listing.priority`; wiersze różnych źródeł współistnieją, `find_close(asset, date)` wybiera jeden; forward-fill przy odczycie. Snapshoty: korekta operacji ustawia `dirty_from = LEAST(dirty_from, operation_day)`; przebudowa kasuje wiersze `≥ dirty_from` i liczy od nowa (idempotentna); synchronicznie, gdy dni × otwarte pozycje ≤ 20 000 **[propozycja]**, inaczej w tle. Walor z historią tylko archiwizujemy; zapis danych globalnych tylko `is_owner` (biz. 0007).

### 6.3 Kontrakt API

Szkic; `{S}` = `/portfolios/{id}`, `/groups/{id}` lub `/groups/all`. Nowe endpointy adresują Portfel po `id`; `portfolio_name`/`portfolioName` działa równolegle do kamienia M1 (`deprecated`, nagłówki `Deprecation`/`Sunset`, log `warning`); oba selektory naraz → 400 `PORTFOLIO_SELECTOR_AMBIGUOUS` **[propozycja]**. Bez prefiksu `/v1` **[propozycja]**; zmiana addytywna jest zgodna, łamiąca idzie ścieżką deprecjacji; metodę metryk wersjonuje `method`, nie URL.

| Endpoint | Parametry | Odpowiedź / błędy |
|---|---|---|
| `POST /auth/login` (alias `/auth/token`), `/auth/token/refresh`, `/auth/register`, `GET /auth/me` | `email`, `password` (min 8) / `refresh` | `access`, `refresh`; `me`: `id`, `email`, `is_active`, `is_owner`; konta tworzy CLI `create-user` |
| `GET`/`PUT`/`PATCH /settings` | `display_currency_code` `^[A-Z]{3}$`, `stale_price_days` ≥ 1, `benchmark_asset_id?` | `{…, updated_at}`; `ASSET_NOT_FOUND` |
| `GET /assets/` | `search` (ticker, nazwa, ISIN), `asset_type?`, `asset_class_id?`, `country?`, `include_archived` | `AssetResponse` + `isin`, `mic`, `country`, `asset_type`, `archived_at`, `price_date`, `stale`, `price_source` |
| `POST /assets/`, `PUT/PATCH /assets/{id}`, `DELETE`, `…/archive`, `/unarchive` | `ticker` `str(20)`, `name` `str(100)`, `asset_class_id`, `currency_id`, `isin?`, `mic?`, `country?`, `asset_type` | `ASSET_ALREADY_EXISTS`, `ASSET_HAS_HISTORY`; `current_price` w PUT zapisuje wiersz `manual` |
| `GET /assets/currencies/rate` | `from_currency`, `to_currency`, `date?` | kurs bezpośredni/odwrotny z bazy: `rate`, `rate_date`, `source`, `is_synthetic`, `stale`, `via`; `RATE_MISSING` |
| `GET /portfolios/fx-rate` | j.w. | jedyna ścieżka UI po kurs krzyżowy; `via` ∈ `direct/inverse/cross/identity`. Wdrożone: `from_currency`, `to_currency`, `rate` (9 miejsc), `via`; reszta po E1.1 |
| `GET /assets/{id}/prices`, `PUT`/`DELETE …/prices/{price_date}` | `from?`, `to?`, `source?`, `fill` = `none`/`forward`; PUT: `close > 0` (cena ręczna, `source=manual`) | `{asset_id, currency, items: [{price_date, close, source, is_synthetic, stale}]}`; `ASSET_ARCHIVED`, `PRICE_NOT_FOUND` |
| `POST /assets/refresh-prices` | `asset_ids` (1–50) | **202** `{accepted}`; wynik widać w `price_date`/`data-status` |
| `GET /assets/data-status` | `only_problems` | `{fx, jobs: [{job_name, last_finished_at, last_status, last_ok_day}], assets: [{asset_id, ticker, price_date, stale, source, last_error}]}` |
| `/assets/currencies`, `/fx-rates`, `/{id}/listings`, `search-yahoo`, `create-from-yahoo` | `code` `^[A-Za-z]{3}$`, `exchange_rate?` > 0 (null dozwolone); PUT kursu ręcznego (`source=manual`, `rate > 0`) | `CURRENCY_ALREADY_EXISTS`, `CURRENCY_IN_USE`, `ASSET_NOT_FOUND_ON_PROVIDER` |
| `GET /portfolios/` | `name?`, `account_type?`, `is_active?` | + `account_type`, `broker`, `auto_funding`, `cash_balances: [{currency, balance}]`, `stale`, `as_of` |
| `POST`/`PUT`/`PATCH`/`DELETE /portfolios/[{id}]` | `name` `str(1–100)`, `base_currency_id`, `account_type?`, `broker?`, `auto_funding` | `PORTFOLIO_ALREADY_EXISTS`, `PORTFOLIO_CURRENCY_LOCKED`; DELETE kaskadowo (204) |
| `/groups*`, `PUT /groups/{id}/members`, `/portfolios/{id}/commission-rules`, `GET {S}/lots`, `GET /portfolios/compare` (2–10 `portfolio_id`) | `name` `str(1–100)`, `currency_code?`; `portfolio_ids` zastępuje zbiór | `GROUP_ALREADY_EXISTS`, `GROUP_NOT_FOUND`; reguła prowizji `{asset_type?, rate_pct, min_fee, currency_id?}` |
| `GET /operations`, `GET /portfolios/{id}/operations` | `portfolio_id?`, `operation_type*`, `asset_id?`, `from?`, `to?` (po `operation_day`), `q?`, `limit`, `offset`, `sort` | `{items, total, limit, offset}`; `INVALID_DATE_RANGE`; legacy `GET /portfolios/operations` = goła tablica, deprecated |
| `POST /portfolios/operations` (201), `PUT/PATCH …/{id}`, `DELETE …/{id}` (204) | ciało niżej; PUT/PATCH nie zmieniają `portfolio_id`, `operation_type`, `asset_id`, ustawiają `edited_at` i przebudowują od daty | `INSUFFICIENT_CASH`, `INSUFFICIENT_QUANTITY`, `INVALID_OPERATION`, `OPERATION_REQUIRES_ASSET`, `ASSET_ARCHIVED`, `RATE_MISSING`, `CONCURRENT_CHANGE` |
| `POST /portfolios/operations/preview`, `…/{id}/preview` | j.w. | dry-run, niżej |
| `GET {S}/positions` | `as_of?`, `include_closed` | `PositionResponse` + `price_date`, `stale`, `price_source`, `is_synthetic`; koszt z Partii |
| `GET {S}/closed-positions` | `from?`, `to?` (po `closed_on`), `asset_id?`, `limit`, `offset`, `sort` | `{summary: {proceeds, cost, fees, dividends, profit, return, win_rate, profit_factor: Metric}, items, total, limit, offset}` |
| `GET {S}/performance` | `period` = `1M/3M/6M/YTD/1Y/3Y/5Y/MAX/custom`; `from?`/`to?`; `currency?`; `metrics?` (`profit,twr,xirr,realized,income,fees,benchmark`) | koperta metryk; `benchmark` = TWR waloru z `benchmark_asset_id`; `INVALID_DATE_RANGE` |
| `GET {S}/allocation` | `by` = `asset/class/sector/currency/country/account_type`; `as_of?`; `over_time`; `from?`, `to?` | `{by, as_of, currency, total, cash, items: [{key, label, value, weight_pct}], series?, data_quality, stale}`; udziały = 100%, gotówka osobno |
| `GET {S}/charts/{series}` | `series` = `value-vs-contributions`, `profit`, `twr`, `monthly-returns`, `treemap`; `period`/`from`/`to`; `benchmark_asset_id?`; `asset_id*` (do 4) | `{date: […], <seria>: [float], data_quality, stale, as_of}`; bez wywołań dostawcy |
| `GET {S}/income` | `from?`, `to?`, `granularity` = `month/year`, `asset_id?` | `{items: [{period, amount}], ttm_yield, yield_on_cost, top_payers}` |
| `GET /dashboard` | — | `{currency, as_of, total_value, cash, positions_value, day_change, twr_ytd, twr_1y, portfolios: [{id, name, value, day_change, sparkline}], winners, losers}` |

**Ciało Operacji** (`extra="forbid"`): `portfolio_id`; `operation_type` (`buy/sell/deposit/withdrawal/dividend/interest/fee/currency_exchange/split`); `asset_id?` albo `ticker?`; dokładnie jedno z: `operation_day` + `operation_time?` (Warszawa; brak = 00:00) albo legacy `operation_date` (ISO z offsetem); `quantity`, `price`, `amount?`, `fee`, `fx_rate`, `currency_id`, `counter_amount?`, `counter_currency_id?`, `ratio? > 0`, `external_ref?`, `sequence? ≥ 0`. Odpowiedź: te pola + `edited_at`, `import_batch_id`.

**Dry-run** to osobne endpointy `preview` (jeden typ odpowiedzi w OpenAPI), ta sama walidacja i `PortfolioLedger`, rdzeń bez commitu (ADR tech. 0008), `rollback`. Zawsze 200, także gdy księga odrzuca: `{ok, errors: [{code, detail, params?}], before, after, realized_pnl?, lots_consumed?, rebuild_from, warnings}`; `before`/`after`: `cash: [{currency, balance}]`, `position: {asset_id, quantity, average_buy_price}`. Zły kształt żądania → 422. Bez `Idempotency-Key` w v1 (klucze naturalne: `external_ref`, `sha256`).

**Błędy** (ADR tech. 0007): `{"detail": "<EN>", "code": "UPPER_SNAKE"}`; **[propozycja]** opcjonalne `params` (lista id, waluta) i `code: REQUEST_VALIDATION_FAILED` dla 422 (dziś bez `code`, `core/errors.py:115-122`).

| Kod | HTTP | Kiedy |
|---|---|---|
| `INSUFFICIENT_CASH`, `INSUFFICIENT_QUANTITY` | 400 | brak gotówki w walucie operacji / sprzedaż > ilość wg historii na datę |
| `INVALID_OPERATION`, `OPERATION_REQUIRES_ASSET`, `OPERATION_FORBIDS_ASSET`, `INVALID_DATE`, `INVALID_DATE_RANGE`, `PORTFOLIO_SELECTOR_AMBIGUOUS` | 400 | reguły operacji, daty, selektor |
| `INVALID_CREDENTIALS`, `INVALID_REFRESH_TOKEN` | 401 | logowanie, odświeżenie |
| `REGISTRATION_DISABLED`, `REFERENCE_DATA_OWNER_ONLY` | 403 | `ALLOW_REGISTRATION=false` (domyślnie false w produkcji); zapis globalny bez `is_owner` |
| `*_NOT_FOUND` (`PORTFOLIO`, `OPERATION`, `ASSET`, `CURRENCY`, `ASSET_CLASS`, `PRICE`, `GROUP`, `IMPORT_*`), `ASSET_NOT_FOUND_ON_PROVIDER` | 404 | brak encji / dostawca nie zna tickera |
| `RATE_MISSING` | 404 na endpointach kursu; inline w wycenie | brak kursu (wdrożone: `rate_missing: bool` + puste pola) |
| `*_ALREADY_EXISTS`, `EMAIL_ALREADY_REGISTERED`, `CURRENCY_IN_USE`, `ASSET_HAS_HISTORY` (zastępuje `ASSET_IN_USE`), `ASSET_ARCHIVED`, `PORTFOLIO_CURRENCY_LOCKED`, `CONCURRENT_CHANGE`, `OPERATION_EXTERNAL_REF_EXISTS` | 409 | duplikat, użycie, blokady |
| `REQUEST_VALIDATION_FAILED` | 422 | **[propozycja]** |
| `MARKET_DATA_UNAVAILABLE` | 502 | dostawca notowań niedostępny |
| `IMPORT_*` (później): `IMPORT_FILE_TOO_LARGE` 413, `IMPORT_PARSE_FAILED` 422, `IMPORT_UNRESOLVED_ROWS`, `IMPORT_BATCH_HAS_EDITS`, `IMPORT_BATCH_STATE_INVALID` 409 | | import |

Kody metryk w odpowiedzi 200 (nigdy 4xx): `IRR_UNDEFINED`, `IRR_AMBIGUOUS` (zwracany TWR), `PERIOD_SHORTER_THAN_ONE_YEAR`; oraz `issues[]`: `PRICE_STALE`, `PRICE_SYNTHETIC`, `PRICE_MISSING`, `RATE_MISSING`, `REBUILD_PENDING`.

**Koperta metryki:**

| Pole | Znaczenie |
|---|---|
| `value` | `DecimalString`; `null` = nie da się policzyć (wtedy `reason`) |
| `unit` | waluta, `ratio` (0,084512 = 8,45%), `pct` (punkty, pola `*_pct`), `days` |
| `method` | `daily_pp_v1` (TWR), `xirr_365_v1` (XIRR) **[propozycja nazw]**; zmiana metody = nowa wartość i nowy ADR |
| `effective_start` | faktyczny początek, może być późniejszy niż `period.from` |
| `data_quality` | najgorsza z okresu: `missing` > `synthetic` > `stale` > `ok` |
| `stale` | cena starsza niż `stale_price_days` albo snapshot po `dirty_from` |
| `source` / `as_of` | `snapshot`, `live`, `manual` lub dostawca / ostatni dzień objęty |
| `reason`, `approximation`, `issues[]` | przyczyna `null`; fallback (Modified Dietz); `[{code, asset_id?, from?, to?}]` |

Annualizacja tylko ≥ 365 dni (biz. 0004), inaczej `annualized: null` + `annualized_reason`. Przykład `GET /portfolios/3/performance?period=YTD` (wartości przykładowe; 273 dni → brak annualizacji; XIRR niejednoznaczny → puste pole, zwrócony TWR):

```json
{"period":{"code":"YTD","from":"2026-01-01","to":"2026-10-01","days":273},"as_of":"2026-10-01",
 "twr":{"value":"0.084512","unit":"ratio","method":"daily_pp_v1","data_quality":"stale","stale":true,
   "annualized":null,"annualized_reason":"PERIOD_SHORTER_THAN_ONE_YEAR",
   "issues":[{"code":"PRICE_STALE","asset_id":41,"from":"2026-09-22","to":"2026-10-01"}]},
 "xirr":{"value":null,"unit":"ratio","method":"xirr_365_v1","reason":"IRR_AMBIGUOUS","source":"live"}}
```

**Konwencje.** Listy nieograniczone (Operacje, zamknięte pozycje) w kopercie `{items,total,limit,offset}`, `limit` 1–200 (domyślnie 50), `offset ≥ 0`, poza zakresem → 422; `sort` = `pole`/`-pole` z białej listy, serwer dokleja `id`; filtry powtarzalne, `from`/`to` włącznie. Małe słowniki to gołe tablice, szeregi czasowe bez paginacji. Offset, bo UI ma numerowane strony i `total`; cel < 300 ms dla 10 000 Operacji **niezmierzone** (pomiar w E2.7). **Liczby:** dziś `DecimalNumber` serializuje do `float` (`core/schemas.py:11-13`), typy TS to `number`; **propozycja** `DecimalString` (`format(v, "f")`, bez notacji wykładniczej; `NaN`/`Infinity` odrzucane) dla kwot, cen, ilości, kursów; `ratio` 6 miejsc; `*_pct` 2 miejsca; wektory wykresów zostają `float`; przełączenie istniejących schematów jednorazowo z typami z OpenAPI (do tego czasu stare pola `number`, nowe `string`). **Daty:** `price_date`, `rate_date`, `acquired_on`, `as_of`, `from`, `to` to `date` bez strefy; `*_at` w UTC; `operation_day` zawsze Warszawa. **Zmiany łamiące:** `portfolio_name`→`portfolio_id`; `GET /portfolios/operations`→`GET /operations`; `number`→`DecimalString`; `operation_date`→`operation_day`+`operation_time`; `GET /portfolios/positions` przestaje odświeżać dostawcę; `ASSET_IN_USE`→`ASSET_HAS_HISTORY`; `portfolio-vectors`→`charts/{series}`. Zrzut `app.openapi()` w repo jako bramka CI — **[niezweryfikowane]**.

### 6.4 UI

**Trasy v1:** `/` kokpit (waluta wyświetlania); `/portfolios/:id` (pozycje) z zakładkami `operations`, `allocation`, `performance`, `income`, `closed`; `/groups/:id` (te same zakładki bez `operations`) i `/groups/all` **[propozycja]**; `/assets/:id` (wykres ceny z markerami; opcjonalnie `?portfolio=<id>`); `/operations`; `/compare`; `/data`; `/settings`; `/methodology`; `/import`, `/import/new`, `/import/:batchId` (później, tylko desktop; na telefonie „Otwórz na komputerze”); `/login`. URL jest źródłem prawdy o zakresie; analityka żyje w zakładkach zakresu. Jedna nawigacja (sidebar), bez pozycji bez gotowego ekranu. Nieznana trasa → „Nie znaleziono”. Stare trasy: `/pockets/:slug` → `/portfolios/:id`, `…/history` → `…/operations`, `…/charts` → `…/performance`.

`LegacyPortfolioRedirect`: `decodeURIComponent(slug)` → `GET /portfolios/?name=` → `Navigate replace`; nieznana nazwa → 404; usuwany po jednym kamieniu milowym.

**`OperationFormDialog`** (jeden dla wszystkich typów, tryb utwórz/edytuj, React Hook Form bez nowej biblioteki schematów; na telefonie `fullScreen` poniżej `sm`):

| Typ | Wymagane | Opcjonalne |
|---|---|---|
| `buy`, `sell` | Portfel, data, Walor, ilość, cena | prowizja, kurs brokera, notatka |
| `dividend` | Portfel, data, Walor, kwota (w walucie wypłaty) | notatka |
| `deposit`, `withdrawal` | Portfel, data, kwota | prowizja, waluta |
| `interest`, `fee` | Portfel, data, kwota, waluta | Walor |
| przewalutowanie | Portfel, data, kwota z + waluta, kwota do + waluta | kurs, prowizja (w walucie wychodzącej) |
| `split` | Portfel, data, Walor, proporcja nowe:stare | — |

Walidacja klienta tylko kształtu; reguły księgi rozstrzyga backend. Ostrzeżenia, nie blokady: sprzedaż > posiadana ilość, zakup > gotówka (możliwe `auto_funding`), data w przyszłości. Podgląd „przed → po” (gotówka per waluta, pozycja, zużyte Partie, zysk zrealizowany) z `…/preview` po 300 ms, bez arytmetyki na kwotach w przeglądarce. Edycja: „przebuduje pozycje od <data>”; typ, walor i Portfel tylko do odczytu.

**Formatowanie** (`lib/format.ts`, `pl-PL`, funkcje przyjmują `number | string | null | undefined`, test Vitest każdej): `formatMoney` z jawną walutą (2 miejsca; 0 w skrótach kokpitu), `formatQuantity` do 9 miejsc bez zer końcowych, `formatPrice` 2–4, `formatRate` 4–6 **[propozycja]**, `formatPercent` 2 miejsca ze znakiem, `formatCompact` (k, M) dla osi, `formatDate` `DD.MM.YYYY` (znaczniki czasu w `Europe/Warsaw`; daty bez czasu przez `dayjs('YYYY-MM-DD')`, nie `new Date`). Brak wartości = „—”, nie 0; sprawdzaj `== null` przed `Number()`. UI nie sumuje pieniędzy między Portfelami ani walutami. Zysk/strata: znak + ikona + kolor (`SignedValue`). Wykresy: Recharts 3 (brak heatmapy) + własny `HeatmapGrid` **[propozycja]**; wykres ceny z markerami = `ComposedChart` + `Scatter`.

**Stany ekranu:** ładowanie — `Skeleton` (`ScreenState`); pusty — wyjaśnienie + akcja (`EmptyState`), po filtrach „Wyczyść filtry”; błąd — komunikat PL + „Spróbuj ponownie” (`ErrorState`); dane częściowe — `StaleBanner` „N walorów z nieaktualną ceną”; odświeżanie w tle — stare dane + `isFetching`. „Odśwież ceny” → 202, polling `price_date`, potem unieważnienie kluczy `portfolio`, `positions`, `performance`, `dashboard`.

**Flagi jakości** (`DataQualityBadge` przez `MetricLabel` = etykieta + wartość + znacznik + „Jak liczymy”):

Wygląd: `stale` — żółty „Nieaktualna cena” + `price_date` (próg `stale_price_days`, domyślnie 7); `is_synthetic` — „Szacunek” (brak notowania z dnia); `rate_missing` — „Brak kursu”, wycena pusta (nie 1), „—”; `missing` — brak ceny przy niezerowej pozycji; `source`, `method` (opis + link do `/methodology`), `effective_start` („od <data>”); `annualized = null` — „—” + „< 1 roku, bez annualizacji” (GIPS 2.A.12).

Dane częściowe pokazujemy z paskiem, nie zastępujemy błędem. Teksty w `lib/errors.ts` i `lib/dataQuality.ts`.

**Komunikaty błędów** (`parseApiError` → `{status, code?, detail?}`; kolejność: słownik `ERROR_MESSAGES` po `code`, potem komunikat wg statusu 401/403/404/409/422/5xx/brak sieci, potem „Coś poszło nie tak” + `detail` w zwijanych szczegółach; każdy kod ma test Vitest, nieznany nie psuje UI):

| `code` | Komunikat PL |
|---|---|
| `INSUFFICIENT_CASH` / `INSUFFICIENT_QUANTITY` | Za mało gotówki w Portfelu na tę operację. / Nie masz tylu sztuk tego waloru (wg historii na tę datę). |
| `INVALID_OPERATION` / `OPERATION_REQUIRES_ASSET` / `OPERATION_FORBIDS_ASSET` | Operacja jest niezgodna z regułami Portfela. / Wybierz walor. / Ten typ nie dotyczy waloru. |
| `*_NOT_FOUND`, `*_ALREADY_EXISTS` | Nie znaleziono Portfela / operacji / waloru. Taka nazwa / taki ticker już istnieje. |
| `ASSET_HAS_HISTORY`, `CURRENCY_IN_USE` | Nie można usunąć: ma historię / jest używana; zarchiwizuj. |
| `CONCURRENT_CHANGE`, `INVALID_DATE(_RANGE)` | Dane zmieniły się równolegle, spróbuj ponownie. Niepoprawna data / zakres dat. |
| `MARKET_DATA_UNAVAILABLE`, `ASSET_NOT_FOUND_ON_PROVIDER` | Dostawca notowań jest niedostępny; pokazuję ostatnie ceny. Dostawca nie zna tego tickera. |
| `INVALID_CREDENTIALS`, `EMAIL_ALREADY_REGISTERED`, `REGISTRATION_DISABLED`, `REFERENCE_DATA_OWNER_ONLY`, `PORTFOLIO_CURRENCY_LOCKED` | Błędny e-mail lub hasło. Ten e-mail jest już zarejestrowany. Rejestracja jest wyłączona. Tylko właściciel zmienia dane globalne. Waluty Portfela nie zmienisz, gdy są operacje. |
| `IRR_UNDEFINED`, `IRR_AMBIGUOUS`, `PERIOD_SHORTER_THAN_ONE_YEAR` (200 inline) | XIRR nieokreślony (brak przepływów o różnych znakach). XIRR niejednoznaczny, pokazuję TWR. < 1 roku, bez annualizacji |

**Ustawienia:** jeden „Zapisz” (bez autozapisu); pola: waluta wyświetlania, próg nieaktualnej ceny, benchmark; zmiana waluty unieważnia klucze kokpitu i wyników.

### 6.5 Zadania w tle

Brak Celery/Redis i harmonogramu w procesie (Render usypia backend). Polecenia `python -m app.cli <zadanie>` wołają wyłącznie `entrypoints.py`: `refresh-fx` (NBP przed cenami), `refresh-prices`, `backfill`, `rebuild-dirty`, `rebuild-all`, `create-user`, `set-owner`. Kody wyjścia: 0 ok, 1 błąd, 2 argumenty, 3 częściowe niepowodzenie **[propozycja]**; błąd jednego waloru nie przerywa reszty.

**`job_run`:** `job_name` `String(40)` PK (`refresh-prices`, `refresh-fx`, `rebuild-dirty`); `last_started_at` timestamptz NOT NULL; `last_finished_at` NULL; `last_status` `String(10)` NULL (`ok/failed/partial`); `last_ok_day` `Date` NULL (ostatni dzień Europe/Warsaw z udanym przebiegiem = warunek „zaległość”); `last_error` `String(200)` NULL (bez sekretów). *Rozbieżność:* ADR tech. 0017 podaje `job`, `status`, bez `last_ok_day`/`last_error` (sam nazywa tabelę i kody „roboczymi”); przyjęto nazwy z doc 07. **Wiersze tworzy seed** (`INSERT … ON CONFLICT DO NOTHING`): bez wiersza `SELECT … FOR UPDATE SKIP LOCKED` nic nie zwraca i przebieg uznałby, że „inny trwa”, więc zadanie nigdy by nie ruszyło.

**Nadrabianie:** pierwsze żądanie dnia (stan z `job_run`, nie z pamięci procesu) rejestruje w `BackgroundTasks` tylko `refresh_fx_rates`, `refresh_prices`, `rebuild_dirty`; zadania są idempotentne. **Blokada:** wiersz `job_run` w transakcji (`FOR UPDATE SKIP LOCKED`; brak wiersza w wyniku = inny przebieg trwa, wyjście bez pracy); `status` i `last_started_at` informacyjne; przebieg bez `last_finished_at` po 30 minutach uznaje się za przerwany. Nie `flock` ani blokady sesyjne (pooler Supabase). `POST /assets/refresh-prices` zwraca 202; żadne żądanie HTTP nie woła dostawcy synchronicznie. Zewnętrzny cron (jedna linia) jest opcjonalny.

## 7. Decyzje

Decyzje projektowe żyją jako ADR-y w `docs/business/adr/` (reguły domenowe) i `docs/technical/adr/` (architektura). Status zmienia człowiek. Poniższe tabele są streszczeniem.

### Biznesowe

| ADR | Decyzja | Status |
|---|---|---|
| 0001 | Portfel = jeden rachunek maklerski; agregację dają Grupy portfeli | Accepted |
| 0002 | Koszt nabycia z partii zakupu, FIFO w obrębie Portfela; split zachowuje koszt łączny | Accepted |
| 0003 | Gotówka per (Portfel, Waluta); przewalutowanie jako operacja; opcjonalne `auto_funding` (domyślnie wyłączone); automatyczne wpłaty to dane pochodne (`portfolios_auto_flow`), nie wiersze Operacji; `cash_balance`/`total_deposited` to cache waluty bazowej | Accepted |
| 0004 | Dzienny TWR (konwencja Portfolio Performance) i XIRR; brak annualizacji poniżej 365 dni | Accepted |
| 0005 | Operacja ma dzień (`operation_day`, Europe/Warsaw) i numer kolejny w dniu (`sequence`) | Accepted |
| 0007 | Dane referencyjne należą do właściciela instancji; walor z historią się archiwizuje (DELETE = 409 `ASSET_HAS_HISTORY`); właściciel = `is_owner`, zapis globalny bez niej = 403 `REFERENCE_DATA_OWNER_ONLY` | Accepted |

### Techniczne (nowe)

| ADR | Decyzja | Status |
|---|---|---|
| 0013 | Graf zależności czterech modułów (`core_data`, `security`, `assets`, `portfolios`) egzekwowany testem; `assets` nie zależy od `core_data` ani `security` | Accepted |
| 0014 | Księga, partie, TWR i kursy na `Decimal`; `float` z `numpy` tylko dla XIRR i statystyk benchmarku | Accepted |
| 0015 | Ceny i kursy jako historia w bazie (`assets_price`, `assets_fx_rate`), nieskorygowane, z jawnym źródłem; dwa kursy: brokera i wyceny | Accepted |
| 0016 | Snapshoty dzienne jako pochodna księgi; przebudowa per Portfel od najstarszej zmiany; synchronicznie do progu | Accepted |
| 0017 | Zadania w tle: CLI `python -m app.cli <zadanie>` wołające `entrypoints.py` plus nadrabianie po wybudzeniu; blokada transakcyjna `job_run` | Accepted |
| 0018 | Import: paczka z cofnięciem w `portfolios`; parser jako adapter za portem; pierwszy adapter XTB; cofnięcie paczki usuwa jej Operacje, chyba że któraś była edytowana (409 `IMPORT_BATCH_HAS_EDITS`) | Proposed (do czasu próbek plików) |
| 0019 | Migracje tylko `autogenerate`; `operation_day` + `sequence`; dane od zera | Accepted |
| 0020 | Płaska tabela operacji z polami rozszerzającymi; przewalutowanie to jeden wiersz | Accepted |

### Wcześniejsze decyzje architektoniczne (opisują istniejący kod, status Proposed)

0001 jedna sesja SQLAlchemy na żądanie; 0002 sesja poza żądaniem tylko przez `entrypoints.py` i `wiring.py`; 0003 serwisy CRUD zwracają encje ORM; 0004 `find_*` kontra `get_*` w repozytoriach; 0005 opcjonalna warstwa `domain/` bez ORM, sesji i zegara; 0006 komunikacja między modułami wyłącznie przez serwisy; 0007 kontrakt błędów `{"detail", "code"}`; 0008 rdzenie bez commitu w operacjach wielomodulowych; 0010 `Decimal` od bazy do granicy schematu; 0011 audyt zmian odłożony; 0012 JWT: HS256, tokeny w `localStorage`, stateless refresh.

## 8. Plan wdrożenia

Plan (warstwa L3, szkic do akceptacji właściciela) dzieli prace na etapy E0–E4, część E8 i E11. Numeracja ma luki (brak E5–E7, E9, E10, D12) i nie jest zmieniana, bo odwołują się do niej ADR-y. Rozmiary kroków: S ≤ 1 dzień, M 2–4 dni, L 1–2 tygodnie, XL > 2 tygodnie (jedna osoba, dni robocze) **[wniosek]**; rozmiar etapu to suma kroków. Kolejność realizacji różni się od kolejności etapów (tanie kroki wcześniej, by właściciel używał aplikacji jak najszybciej); start od E0, bo naprawy nie wymagają nowych ADR i usuwają defekty F1–F6.

### Etapy i zależności

E0 Naprawy i ustawienia (XL; bez zależności): wiarygodne liczby portfeli wielowalutowych. E1 Dane rynkowe i historia (XL; po E0): wycena i wykresy z bazy, bez sieci w ścieżce żądania. E2 Księga v2 (XL; po E0, E1): model wielowalutowego rachunku maklerskiego, każdy krok to addytywna migracja z zielonymi testami. E3 Analityka podstawowa (XL; po E1, E2): zysk, TWR/XIRR vs benchmark, struktura. E4 Import (L, później; po E2.3). E8 Zdarzenia korporacyjne, część (XL; po E1, E2): split i dywidendy nie psują historii. E11 Jakość (ciągły).

### Kroki: rozmiar i kryterium akceptacji

**E0**

| Krok | Rozm. | Kryterium akceptacji |
|---|---|---|
| E0.1 Wycena walut obcych kursem krzyżowym `rate[z]/rate[do]` (`FxMapBuilder`; F1, F4) | M | Portfel PLN, kursy testowe USD=1, EUR=1,08, PLN=0,25: wartość = ilość × cena × kurs krzyżowy (±0,000001); Portfel USD bez zmian; brak kursu = `RATE_MISSING`; testy parytetu zielone. Fixture Z1 (gotówka 1 000, wpłaty 10 000; A: EUR, 10 szt., cena 100, koszt 90 × 4,00; B: USD, 10 szt., 100, koszt 80 × 4,00; C: PLN, 5 szt., 60): wartości A 4 320, B 4 000, C 300; `total_value` 9 620, `total_profit_loss` −380 (−3,8%); udziały 44,9064 / 41,5800 / 3,1185. **Zrobione, PR #2** |
| E0.2 Wektory metryk zgodne z księgą (F2) | M | ostatni punkt `free_cash_vector` = `cash_balance` (±0,01, wektor jest `float`); ostatni punkt wartości = wycena z E0.1 (±0,01 przy tej samej cenie); dywidenda zmienia tylko `free_cash` i `profit`; wymagać Portfela (nie „wszystkich”) |
| E0.3 Operacje wsteczne walidowane historią | S | **każda** nowa operacja przechodzi przez `rebuild()`; wsteczna sprzedaż łamiąca historię = 400 z `code`; poprawna zapisana, pozycje przeliczone |
| E0.4 Waluta nowego waloru z notowania dostawcy (F5) | S | zakup AAPL w Portfelu PLN tworzy walor w USD; błąd dostawcy = 502 `MARKET_DATA_UNAVAILABLE` i brak zapisu; `None` = 404 `ASSET_NOT_FOUND_ON_PROVIDER`; dostawca wołany poza `transaction()` (ADR tech. 0008) |
| E0.5 Tickery GPW `.WA` | S | odświeżenie CDR/PKO/PKN zwraca cenę w PLN; seed generuje Portfele i Pozycje replayem operacji (nie wartościami zahardkodowanymi), replay przez `PortfolioLedger` nie rzuca; `with session.begin()` w `seed/seed.py` |
| E0.6 Zamknięcie rejestracji | S | `POST /auth/register` = 403 `REGISTRATION_DISABLED` przy `ALLOW_REGISTRATION=false` (domyślnie true w dev/test, false w produkcji); `GET /auth/me` zwraca `is_owner`; pierwsze konto z CLI; `is_owner` migracją addytywną, CLI `set-owner` |
| E0.7 Frontend: braki dla istniejącego API | M | `npm run build` i `npm test` zielone; ręcznie: dodaj, edytuj, usuń dywidendę. Zakres: naprawa startu, `lib/format.ts` (zastępuje 8 × `Intl.NumberFormat`), Vitest (nowa zależność, wymaga zgody), edycja operacji, dialog dywidendy, jedna nawigacja |
| E0.8 Blokada zmiany waluty Portfela z operacjami (F6) | S | test: 409 `PORTFOLIO_CURRENCY_LOCKED` |
| E0.9 Ustawienia (F3) | M | sumy kokpitu (gotówka + pozycje) przeliczone na walutę wyświetlania; test API ustawień; sumy tylko z istniejących endpointów Portfeli (`/dashboard` to E3.4) |
| E0.10 `Pocket` → `Portfolio` we froncie | S | brak „Pocket” w `frontend/src` (wyjątek: plik przekierowań i alias `pocket_value_vector`, usuwany w E3.5); stare linki przekierowują; backend dodaje `portfolio_id` do odpowiedzi pozycji i operacji |

**E1**

| Krok | Rozm. | Kryterium akceptacji |
|---|---|---|
| E1.1 `assets_price`, `assets_fx_rate` (numer tabeli NBP, ceny nieskorygowane, `is_synthetic`), `assets_price_change`, zapis `current_price` w tej samej transakcji | M | `find_close(asset, date)` z forward-fill i flagą syntetyczną; testy repozytorium |
| E1.2 Rejestr dostawców: port `MarketDataProvider` z `capabilities`; NBP (tabele A/B, paczki ≤ 93 dni, cofanie po 404 do dnia roboczego); Yahoo (`.WA`, zagranica, `auto_adjust=False` **[niezweryfikowane]** czy to domyślne `yfinance`); priorytet per walor, `assets_listing`, wyłącznik | L | testy kontraktowe na nagranych odpowiedziach; walor po splicie ma ceny nieskorygowane; kurs NBP USD z 2026-09-25 = 3,8404 (tabela 187/A/NBP/2026) w teście nagranym |
| E1.3 `isin`, MIC, `country`, `sector`, `asset_type` (akcja, ETF); lokalny katalog GPW/NC (źródło do ustalenia, brak darmowego oficjalnego); wyszukiwanie | M | wyszukanie „orlen” zwraca PKN |
| E1.4 Odświeżanie w tle: `assets/entrypoints.py` + `app/cli.py`; nadrabianie po wybudzeniu; blokada `job_run`; historię dociąga `portfolios/entrypoints.py` (zna okresy posiadania); koniec synchronicznego odświeżania w `GET /portfolios/positions` (wyjątek: `POST /assets/refresh-prices` = 202) | M | drugie uruchomienie = 0 nowych wierszy dla zamknięć dziennych (cena bieżąca nadpisywana); dwa równoległe przebiegi: jeden wykonuje, drugi pomija; żądania HTTP nie wołają dostawcy (test z dostawcą rzucającym wyjątek) |
| E1.5 Ceny ręczne | S | ręczna cena ma pierwszeństwo, `source=manual` |
| E1.6 Benchmark = walor (WIG, WIG20, mWIG40TR, S&P 500, ETF na MSCI World/ACWI); jeden indeks; dane globalne | M | historia cen z E1.1; wybór zapisany w ustawieniach (`benchmark_asset_id`) |
| E1.7 `price_date`, `stale` (> próg z E0.9), `source`; panel „Dane” | S | walor bez ceny od 7 dni oznaczony w UI |
| E1.8–E1.9 Lista obserwowanych; kalendarz sesji (`is_trading_day`: historia cen + lista świąt) | S+S | dodanie/usunięcie z listy; wykresy i benchmark pomijają dni bez sesji |

**E2**

| Krok | Rozm. | Kryterium akceptacji |
|---|---|---|
| E2.0 `operation_day`/`sequence`/`currency_id` obok `operation_date`; klucz `(operation_day, sequence, id)`; CLI `rebuild` per Portfel; pozycje aktualizowane w miejscu (zachowuje `opened_at`); `dirty_from` tu, nie w E2.5; dane od zera | M | po E0.5 `rebuild` daje stan identyczny z operacjami; drugie uruchomienie bez zmian |
| E2.1 Portfel jako rachunek (`account_type`, `broker` jako etykiety); domyślna prowizja (% + minimum) per Klasa waloru do czasu `asset_type`; Grupy portfeli bez własnych operacji | M | filtr i grupowanie w API |
| E2.2 Gotówka wielowalutowa: `portfolios_cash_balance`; przewalutowanie (noga wychodząca i przychodząca, kurs, prowizja w walucie wychodzącej); dywidenda na saldo w walucie wypłaty; `valuation.py:82` sumuje salda przeliczone kursami; serwis wymaga kursu przy walucie ≠ bazowej (`RATE_MISSING`; domyślne `fx_rate` = 1 jest niewymuszalne) | L | zakup akcji USD z salda USD; brak salda = błąd z `code` |
| **E2.2b Tryb automatycznych wpłat** (ADR biz. 0003): `auto_funding` per Portfel, domyślnie wyłączone; niedobór przy zakupie = wirtualna wpłata; dywidendy i odsetki nie są wirtualną wypłatą (zostają na saldzie); zapis w pochodnej `portfolios_auto_flow`, nie jako wiersze Operacji | S | TWR i XIRR traktują automatyczne wpłaty jako przepływy zewnętrzne; test; idempotencja `rebuild` |
| E2.3 Typy `interest`, `fee`, `split`, przewalutowanie; pola `status`, `external_ref`, `import_batch_id`; reguła w `PortfolioLedger` dla każdego typu | L | edycja wstecz przelicza historię (E0.3); testy reguł każdego typu |
| E2.4 `domain/lots.py` (`LotBook`, wpis w `DOMAIN_LAYERS`): zakup otwiera partię, FIFO w obrębie Portfela, prowizja sprzedaży proporcjonalnie, split zachowuje koszt łączny; `HoldingLike` i `valuation.py:53` czytają Partie; zysk zrealizowany | L | wycena otwartych pozycji czyta koszt z partii; test złoty: zrealizowany 336,50 (FIFO) vs 286,50 (średnia), razem 384,00 w obu; test własności „zysk całkowity niezależny od metody” |
| E2.5 `portfolios_daily`, `portfolios_position_daily`; przebudowa per Portfel (synchronicznie do progu); unieważnianie: operacja natychmiast, cena/kurs przez `assets_price_change` + `portfolios_market_cursor` + `dirty_from` | L | wykresy ze snapshotów; **wykres 5 lat < 300 ms na zbiorze 10 lat × 200 operacji × 30 walorów** |
| E2.6 `CONTEXT.md` (Partia, Grupa portfeli, Przewalutowanie), dokument modułu | S | `kb_validate --strict` czysty |
| E2.7 Historia operacji: paginacja, filtry (typ, walor, data, status), komentarze, godzina | M | lista 10 000 operacji < 300 ms na stronę |

**E3**

| Krok | Rozm. | Kryterium akceptacji |
|---|---|---|
| E3.1 `GET /portfolios/{id}/performance?period=1M\|3M\|6M\|YTD\|1Y\|3Y\|5Y\|MAX\|custom` (też Grupa): zysk, TWR, XIRR (Newton + bisekcja, kody inline), `effective_start`, `method`, `data_quality` | L | TWR 3-dniowy = 3,0000%; XIRR z przykładu Excela = 0,373362535 (±1e-8); Modified Dietz (fallback) dla przykładu Wikipedii (A = 100, B = 300, +50 w połowie okresu) = 1,20 (120%); okres < 365 dni = `annualized = null` |
| E3.2 Zamknięte pozycje: przychód, koszt, prowizje, zysk, %, skuteczność | M | suma zysków = zrealizowany z E2.4 |
| E3.3 Struktura: wg waloru, Klasy, sektora, waluty, kraju; w czasie | M | suma udziałów = 100% (gotówka osobno) |
| E3.4 Kokpit: wartość, zmiana dzienna, zysk, TWR YTD/1Y, wygrani/przegrani dnia | M | sumy = suma wycen Portfeli kursem dnia |
| E3.5 Wykresy: wartość vs wpłaty, zysk, TWR vs benchmark, mapa cieplna miesiąc × rok, porównanie Portfeli | L | brak wywołań dostawcy (test) |
| E3.6 Dywidendy: dochód miesięcznie/rocznie, stopa TTM, stopa od kosztu, top płatnicy | M | 5,00% i 7,33% dla DPS kwartalnej 0,55, ceny 44, kosztu 30 (2,20/44; 2,20/30) |
| E3.7 „Jak liczymy”: strona metodologii + tooltipy | S | każda metryka w UI ma tooltip |
| E3.8 Widok waloru: wykres ceny z Operacjami i dywidendami, partie, zysk | M | przejście kokpit → Portfel → walor → operacja |

**E4, E8, E11**

| Krok | Rozm. | Kryterium akceptacji |
|---|---|---|
| E4.1 Potok: plik z hashem → parser (`core/import_parser.py`) → walidacja (waluta, brutto = ilość × cena ± prowizja, data) → duplikaty (`external_ref` albo data + ISIN + ilość + kwota) → `record_many` + jeden `rebuild` | L | ponowny import tego pliku = 0 nowych operacji; cofnięcie przywraca stan sprzed; 2 000 wierszy < 10 s (zatwierdzenie, nie render) |
| E4.2 Adapter XTB (historia konta, operacje gotówkowe) | M | test na zanonimizowanym pliku, w tym dywidendy i przewalutowania |
| E8.1 Split ręczny (w M0) | M | split 1:10: ilość × 10, koszt bez zmian, TWR ciągły; ułamki jako sprzedaż; data nabycia partii niezmieniona |
| E8.5 Propozycje dywidend i splitów od dostawcy jako Operacje `status=draft` (`accept`/`void`, widok `/operations?status=draft`), ilość na dzień ustalenia prawa (T+2); kalendarium GPW jest płatne | L | propozycja po dniu ustalenia prawa; akceptacja tworzy Operację |
| E8.6 Kalendarz i prognoza dywidend, 12 mies.: ogłoszone, z historii (ostatnia DPS × częstotliwość), TTM | M | oznaczone jako szacunek; źródło każdej pozycji widoczne |
| E11.7 Wydajność: pomiar na 10 lat × 200 operacji × 30 walorów; indeksy; cache po `dirty_from` | S | wykres < 300 ms, kokpit < 500 ms (p95, lokalnie) |
| E11.8 Kreator pierwszego uruchomienia (Portfel → operacje → benchmark), stany puste z podpowiedzią | M | nowy Portfel z operacjami w ≤ 5 krokach |

ADR-y blokują kroki (nagłówki ADR): biz. 0001 → E2.1, E2.4; 0002 → E2.4, E3.2; 0003 → E2.2–E2.5, E3.1, E4.1; 0004 → E2.5, E3.1; 0005 → E2.0, E2.3, E2.4; 0007 → E1.5, E2.3, E4.1; tech. 0014 → E3.1; 0015 → E0.1, E1.1, E1.2, E1.5, E2.3; 0016 → E2.3, E2.5, E3.1; 0017 → E1.4, E2.0. ADR tech. 0018 (import) ma status `Proposed`, pozostałe `Accepted`; agent nie przełącza ADR-ów na `Accepted`.

### Stan wykonania

- **Zrobione:** E0.1 (wycena walut obcych i dialogi) — PR #2; poprawka dashboardu — PR #3.
- **Dalej:** E0.2–E0.10, potem E1.1–E1.4. Plan nie podaje innych zamkniętych kroków.

### Kamienie milowe

Czasy liczone z sumy rozmiarów kroków, bez buforu **[wniosek]**; po każdym kamieniu przegląd planu.

| Kamień | Kroki | Kryterium akceptacji | Szacunek |
|---|---|---|---|
| **M0 — rdzeń** | E0 → E1.1–E1.4 → E2.0–E2.5 + E8.1 → E3.1 | historia jednego rachunku wpisana ręcznie; ilości i salda gotówki zgodne **dokładnie** z wyciągiem brokera; TWR i XIRR przechodzą testy złote | 2–4 mies. |
| **M1 — na co dzień** | E1.5–E1.9, E2.6–E2.7, E3.2–E3.8, E4 (gdy właściciel zdecyduje) | wszystkie rachunki; wartość po cenach i kursach brokera zgodna z wyciągiem ±0,01 zł; TWR/XIRR vs benchmark, struktura, dywidendy | +2–3 mies. |
| **M2 — zdarzenia** | E8.5–E8.6 | splity i dywidendy nie psują historii ani stóp zwrotu | +1–2 mies. |
| **M3 — jakość** | E11 | PWA, wydajność w budżecie | ciągle |

E8.1 jest w M0, bo split w historii właściciela zepsułby wyceny, zanim powstanie reszta E8. Blokada zewnętrzna: E4.2 wymaga zanonimizowanego eksportu XTB od właściciela (oficjalnej listy kolumn nie znaleziono).

### Definicja ukończenia kroku

1. Zgodność z architekturą (warstwy, `wiring.py`, `transaction()`, błędy z `code`, `Decimal`, `extra="forbid"`, `domain/` bez I/O); `test_domain_purity.py` i `test_architecture.py` zielone.
2. Migracje wyłącznie `alembic revision --autogenerate`; `alembic check` bez dryfu; model w `models_registry.py`.
3. Testy: jednostkowe domeny bez bazy (złote), integracyjne endpointów, własności obliczeń.
4. `ruff check .`, `ruff format --check .`, `mypy app`, `pytest`; frontend `npm run lint`, `npm run build`.
5. Funkcja w UI ze stanami: pusty, błąd, ładowanie.
6. Dokument modułu („Stan vs cel”), `CONTEXT.md`, mapa wiedzy, `kb_validate.py --root . --strict` bez nowych błędów.
7. Dane pochodne: `rebuild()` dwukrotnie daje identyczny stan.

### Ryzyka i mitygacje

| Ryzyko | Wpływ | Mitygacja |
|---|---|---|
| Yahoo nieoficjalne, API może się zmienić | brak cen | port `MarketDataProvider`; ceny w bazie; ceny ręczne (E1.5); kolejny adapter |
| Ceny skorygowane o splity | podwójne ujęcie splitu | ceny nieskorygowane + test kontraktowy na walorze po splicie (E1.2) |
| Licencje danych GPW (redystrybucja = 9× stawka) | ryzyko prawne | użytek własny, bez publikacji danych |
| Render usypia backend | zaległe odświeżenia i przebudowy | pierwsze żądanie dnia rejestruje w `BackgroundTasks` odświeżenie i przebudowę; idempotencja; blokada w `job_run`, nie `flock` (ADR tech. 0017) |
| Supabase pauzuje projekt po tygodniu bez aktywności | niedostępna baza | **[propozycja]** zadanie dzienne (E1.4) lub ping co kilka dni; procedura wznowienia w panelu; plan tego nie opisuje |
| Kurs po awarii dostawcy zostaje z poprzedniego odświeżenia (`market_data.py:121-123`) | cicha nieaktualność | `stale` dopiero w E1.7; heurystyka `exchange_rate == 1` ∧ kod ≠ USD błądzi tylko w stronę „brak kursu” |
| Przebudowa po edycji wstecz, wydajność | wolne wykresy, niespójność | `dirty_from` per Portfel (ADR tech. 0016); synchronicznie do progu; E0.3; test idempotencji; pomiar E11.7 |
| FIFO zmienia niezrealizowany P/L (dziś koszt = `ilość × średnia`, `valuation.py:53`) | zaskakujące liczby | test złoty 336,50 vs 286,50 (razem 384,00); test własności; metoda widoczna w UI (E3.7); ADR biz. 0002 przed E2.4 |
| Zmiana metodologii po wdrożeniu | utrata zaufania | ADR biz. 0004 przed E3; pole `method` w API |
| Rozrost E2; praca jednoosobowa | opóźnienie, porzucenie | kroki E2.0–E2.7 z addytywnymi migracjami; M0 jako mały, użyteczny rdzeń |

## 9. Otwarte kwestie

| Kwestia | Stan | Co dalej |
|---|---|---|
| Próbki plików XTB (historia konta, operacje gotówkowe) | brak; blokują ADR tech. 0018 (`Proposed`) i adapter E4.2; możliwa zgoda na nowe zależności parsera (np. XLSX) | zanonimizowane eksporty od właściciela przed implementacją importu |
| Kurs waluty = „USD za jednostkę” | `Currency.base_currency_id` ignorowane; ręczny kurs względem innej bazy psuje wycenę do następnego odświeżenia | zastąpi to historia kursów (ADR tech. 0015, E1.1) |
| Heurystyka braku kursu | kurs 1 na walucie ≠ USD uznawany za „brak kursu” | zastąpi to historia kursów |
| `CURRENCY_NOT_FOUND` | dwa statusy: 400 w ciele operacji, 404 w `GET /portfolios/fx-rate` | zdecydować o ujednoliceniu |
| `opened_at` pozycji | dostaje czas zapisu zamiast daty operacji | osobna poprawka (przebudowa celowo zachowuje `opened_at`) |
| `total_fees` | sumuje opłaty w różnych walutach | policzyć per waluta albo w walucie Portfela |
| Status Operacji (`draft`/`posted`/`void`) | E2.3 i E8.5 na nim stoją, a schemat nie definiuje kolumny | zdecydować: `status String(10)` czy inny mechanizm |
| Numer tabeli NBP (`no`) i `effectiveDate` | plan każe je zapisywać, brak kolumny | dodać `source_ref String(40)` albo zrezygnować |
| `asset_type` a Klasa waloru | **[propozycja]** rozłączne (system vs słownik użytkownika), bez FK | potwierdzić przy E1.3 |
| Katalog GPW/NewConnect (E1.3) i lista świąt (E1.9) | brak ustalonego, darmowego, oficjalnego źródła; kryterium „orlen” → PKN zależy od katalogu | ustalić przy E1.2 |
| `auto_flow` zmienia definicję „przepływu zewnętrznego” | tabela `portfolios_auto_flow` to **[propozycja]** | potwierdzić w ADR (ADR biz. 0003 pkt 7) |
| Kolumny `cash_balance`, `total_deposited`, `current_price` | cache do czasu E3.4/E2.5 | termin usunięcia osobnym ADR |
| `is_owner` dla istniejącego konta | wymaga jednorazowej komendy `set-owner` | zgoda właściciela |
| Próg przebudowy sync/async (`dni × pozycje ≤ 20 000`) | roboczy | kalibracja w E2.5 |
| Wydajność paginacji offsetowej (10 000 operacji) | niezmierzona | pomiar w E2.7; `cursor` dopiero przy > ~100 tys. wierszy |
| `REQUEST_VALIDATION_FAILED` (422 z `code`) i `params` w błędach | **[propozycja]**; dziś 422 bez `code` (`core/errors.py:115-122`) | zmiana `APIError` i dopisek do ADR tech. 0007 |
| UX „Odśwież ceny” | polling `price_date` zamiast natychmiastowego wyniku | potwierdzić w E1.4/E1.7 |
| Yahoo Finance | nieoficjalne; `auto_adjust=False` vs domyślne `yfinance` **[niezweryfikowane]** | test kontraktowy w E1.2; ceny ręczne awaryjnie |
| Render i Supabase (darmowe plany) | Render usypia po 15 min; Supabase: 500 MB i pauza po tygodniu bez aktywności | zadania nadrabiają zaległości; monitorować rozmiar; ping lub zadanie dzienne |

**Historia dokumentów.** Dokumenty usunięte przez właściciela (schemat danych docelowy, kontrakt API, IA interfejsu, plan wycinka E0.1, plan refaktoryzacji) są w historii gita przed commitem `5fddc10`; ich treść w zakresie v1 streszczają sekcje 6 i 8.

