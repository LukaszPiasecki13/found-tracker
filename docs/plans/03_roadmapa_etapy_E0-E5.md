---
id: plan-feature-roadmap-e0-e5
status: draft
type: mixed
scope: plans/product-roadmap
last_reviewed: 2026-10-02
---

# Jakie kroki składają się na etapy E0–E5 roadmapy?

Część [roadmapy funkcjonalnej](./02_roadmapa_funkcjonalna.md) (L3, szkic). Decyzje D1–D11 i definicja ukończenia — w pliku głównym. Kontynuacja: [etapy E6–E11](./04_roadmapa_etapy_E6-E11.md).

**Format kroku:** cel → zakres backend (moduł) → zakres frontend → kryteria akceptacji → zależności. Rozmiar: **S** ≤ 1 dzień, **M** 2–4 dni, **L** 1–2 tygodnie, **XL** > 2 tygodnie (szacunek **[wniosek]**, jedna osoba).

---

## E0 — Naprawy poprawności

**Cel etapu:** usunąć defekty, które zafałszowują wartości portfeli wielowalutowych i wykresy, zanim cokolwiek zbudujemy na nich. Dowody i lokalizacje: [stan FundTrackera](../research/06_stan_found-tracker_vs_cel.md). Etap nie wymaga nowych ADR-ów.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E0.1** Wycena walut obcych | `assets`: kursy przechowywane względem waluty systemowej (USD) muszą być przeliczane **kursem krzyżowym** na walutę bazową Portfela; `portfolios/domain/valuation.py` dostaje kurs `waluta waloru → waluta Portfela` przez port (np. `FxRateProvider.rate(from, to)`), a nie surowe `currency.exchange_rate` | test: Portfel PLN + walor USD i EUR wyceniony poprawnie przy kursach testowych; Portfel USD bez zmian; testy parytetu zielone | M |
| **E0.2** Wektory metryk spójne z księgą | `portfolios/services/metrics.py`: uwzględnić `fx_rate` operacji i przeliczenie wartości walorów; dywidendy zwiększają wolną gotówkę i zysk | test własności: ostatni punkt `free_cash_vector` = `cash_balance` z księgi; wartość ostatniego dnia = wycena z `PortfolioValuator` (±0,01) | M |
| **E0.3** Operacje wsteczne walidowane historią | `OperationService.create`: operacja z datą wcześniejszą niż ostatnia przechodzi przez `rebuild()` (jak edycja/usunięcie), a nie przez stan bieżący | test: wsteczna sprzedaż, która łamie historię, zwraca 400 z `code`; poprawna jest zapisana i pozycje przeliczone | S |
| **E0.4** Waluta nowego waloru | tworzenie waloru „po tickerze” bierze walutę z notowania dostawcy, nie z waluty bazowej Portfela | test: zakup AAPL w Portfelu PLN tworzy walor w USD | S |
| **E0.5** Tickery GPW | mapowanie tickerów GPW na symbole dostawcy (np. sufiks `.WA` w Yahoo — do potwierdzenia w E1.2); poprawka danych seed | odświeżenie ceny CDR/PKO/PKN działa w środowisku dev | S |
| **E0.6** Zamknięcie rejestracji | konfiguracja `ALLOW_REGISTRATION` (domyślnie `false` poza dev); pierwsze konto tworzone komendą CLI | `POST /auth/register` → 403 z `code` przy wyłączonej rejestracji; test | S |
| **E0.7** Frontend — braki dla istniejącego API | edycja operacji (PUT), dialog dywidendy, prowizja przy wpłacie/wypłacie, sumy kokpitu przeliczone na jedną walutę (do czasu E3.4 — waluta wyświetlania z ustawień), usunięcie martwych linków (`/settings`, `/analytics`, `/alerts`) lub zaślepki „wkrótce” | ręczny scenariusz: dodaj → edytuj → usuń dywidendę; `npm run build` zielony | M |

---

## E1 — Dane rynkowe i historia

**Cel etapu:** każda wycena i wykres liczą się z danych w bazie, bez sieci w ścieżce żądania; polskie źródła pierwszej kategorii. Dowody: [dane rynkowe PL](../research/03_rynek_pl_dane_i_obligacje.md), [lekcje techniczne](../research/competitors/02_trackery_porownanie.md). Wymaga ADR: **D5, D7, D8**.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E1.1** Historia cen i kursów | `assets`: tabele `assets_price` (walor, data, zamknięcie, waluta, źródło, `is_synthetic`) i `assets_fx_rate` (waluta z, waluta do, data, kurs, źródło, tabela NBP); unikalność (walor, data, źródło); ceny **nieskorygowane** o splity/dywidendy (zdarzenia modelujemy osobno, E8) | repozytoria `find_close(asset, date)` z regułą forward-fill i flagą syntetycznej ceny; testy | M |
| **E1.2** Rejestr dostawców | port `MarketDataProvider` rozszerzony o `capabilities`; adaptery: **NBP** (kursy tabela A/B, kursy podatkowe), **Stooq** (GPW, NewConnect, ETF, indeksy WIG, fundusze — jeśli dostępne), **Yahoo** (zagranica, krypto); priorytet per walor (`preferred_source`) + mapowanie symboli (`assets_listing`: walor, dostawca, symbol); retry, timeout, wyłącznik awaryjny (circuit breaker) | test kontraktowy każdego adaptera na nagranych odpowiedziach; walor GPW pobiera cenę ze Stooq, a przy awarii z Yahoo | L |
| **E1.3** Identyfikacja walorów | pola `isin`, `mic`/giełda, `country`, `sector`, `asset_type` (akcja, ETF, fundusz, obligacja, krypto, waluta, surowiec, walor użytkownika); lokalny katalog GPW/NC zasilany z listy dostawcy; wyszukiwanie po nazwie i tickerze (dziś: dokładny ticker) | wyszukanie „orlen” zwraca PKN; test | M |
| **E1.4** Odświeżanie w tle | `assets/entrypoints.py` (`session_scope`, ADR-0002) + `app/cli.py`: `refresh-prices`, `refresh-fx`, `backfill --from`; dokumentacja uruchomienia z crona/systemd/kontenera (D8); dociąganie historii tylko dla okresów posiadania (wzorzec beangrow/Wealthfolio) | zadanie idempotentne; brak sieci w `GET /portfolios/positions` (usunięcie synchronicznego odświeżania) | M |
| **E1.5** Ceny ręczne i walory użytkownika | endpoint dodawania/edycji ceny historycznej; walor bez dostawcy (np. złoto fizyczne, mieszkanie, PPK przed E5) | wykres walora z ręcznymi wycenami; ręczna cena ma pierwszeństwo nad dostawcą i jest oznaczona | S |
| **E1.6** Benchmarki i szeregi | benchmark = walor (WIG, WIG20, mWIG40TR, sWIG80, S&P 500, MSCI World/ACWI przez ETF) + szeregi stóp (`assets_rate_series`: CPI GUS r/r, stopa referencyjna NBP, WIBOR/WIRON/POLSTR wg dostępności) | szereg CPI i stopy NBP pobierany przez CLI; test parsera | M |
| **E1.7** Jakość danych | w odpowiedziach wyceny: `price_date`, `stale` (> N dni roboczych), `source`; panel „Dane” w UI (ostatnie odświeżenie, błędy dostawców) | walor bez ceny od 7 dni oznaczony w UI | S |

---

## E2 — Księga v2

**Cel etapu:** model księgowy zdolny unieść polskie realia: rachunki IKE/IKZE, gotówkę w wielu walutach, przelewy między rachunkami, koszty i podatki, partie FIFO i dzienne snapshoty. Największy etap — podzielony tak, by każdy krok był addytywną migracją z zielonymi testami parytetu. Wymaga ADR: **D1, D2, D3, D4, D9**.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E2.1** Portfel jako rachunek | `Portfolio`: `account_type` (zwykły, IKE, IKZE, PPK, OIPE), `broker`, `tax_exempt` (pochodna typu), `opened_at`; **Grupa portfeli** (agregacja w kokpicie i analizach, bez własnych operacji) | migracja addytywna; istniejące portfele = „zwykły”; filtrowanie i grupowanie w API | M |
| **E2.2** Gotówka wielowalutowa | `portfolios_cash_balance` (Portfel, Waluta, saldo); operacja `fx_exchange` (przewalutowanie: z waluty, do waluty, kurs, prowizja); zakup w walucie waloru pobiera gotówkę w tej walucie albo przewalutowuje automatycznie (ustawienie Portfela, odpowiednik „bezgotówkowego” trybu myfund) | test: zakup akcji USD z salda USD; brak salda USD → błąd albo auto-przewalutowanie wg ustawienia | L |
| **E2.3** Nowe typy Operacji | `interest` (odsetki), `fee` (opłata, np. za prowadzenie), `tax` (podatek pobrany, np. WHT, Belka), `transfer_out`/`transfer_in` gotówki i walorów między Portfelami (z zachowaniem kosztu i daty nabycia partii), `adjustment`; pola `settlement_date`, `currency_id` operacji, `fx_rate_tax` + data kursu (wypełniane automatycznie z NBP — D5), `external_ref`, `import_batch_id` | każda operacja ma regułę w `PortfolioLedger` + testy; przelew walorów nie zmienia zysku całkowitego | L |
| **E2.4** Partie zakupu (FIFO) | `domain/lots.py`: `LotBook` (otwarcie partii przy zakupie/przelewie, zużycie FIFO przy sprzedaży, alokacja prowizji proporcjonalnie); tabele pochodne `portfolios_lot` i `portfolios_lot_consumption`; **zysk zrealizowany** per sprzedaż (w walucie waloru, w walucie Portfela, w PLN po kursie podatkowym); średnia cena nadal liczona do prezentacji | test złoty z [metodyki](../research/05_metodyka_metryk.md): zrealizowany 336,50 (FIFO) vs 286,50 (średnia), zysk całkowity 384,00 w obu; test własności; `rebuild()` odtwarza partie | L |
| **E2.5** Snapshoty dzienne | `portfolios_daily` (wartość, gotówka, przepływy zewnętrzne we/wy, dochody, opłaty, podatki, `r_day`, `twr_index`, skumulowane przepływy, `data_quality`) i `position_daily`; unieważnienie od daty zmiany (operacja, cena, kurs) i przeliczenie do przodu; zadanie CLI dopisujące bieżący dzień | wektory wykresów (dziś `metrics.py`) czytane ze snapshotów; czas odpowiedzi wykresu 5 lat < 300 ms na danych testowych | L |
| **E2.6** Słownik i dokumentacja | `CONTEXT.md`: Partia, Grupa portfeli, Saldo gotówki per waluta, Przelew, Przewalutowanie, Kurs podatkowy, Typ rachunku; aktualizacja `05_portfolios_module.md` | `kb_validate --strict` bez nowych błędów | S |

---

## E3 — Analityka podstawowa

**Cel etapu:** odpowiedzieć na pytania „ile zarobiłem”, „jak wypadam na tle WIG” i „z czego składa się portfel” — poprawnie i z jawną metodą. Wymaga ADR: **D6**. Formuły i testy złote: [metodyka](../research/05_metodyka_metryk.md).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E3.1** Stopy zwrotu | `GET /portfolios/{id}/performance?period=1M|3M|6M|YTD|1Y|3Y|5Y|MAX|custom` (także dla Grupy i „wszystkie”): zysk kwotowy, TWR (z `twr_index`), XIRR (solver Newton + bisekcja, kody `irr_undefined`/`irr_ambiguous`), annualizacja tylko ≥ 365 dni, `effective_start`, `method`, `data_quality` | testy złote: TWR 3-dniowy = 3,0000%; XIRR przykład Excela 0,373362535; Modified Dietz 1,20 (przykład Wikipedii) jako fallback | L |
| **E3.2** Zysk zrealizowany i zamknięte pozycje | raport zamkniętych pozycji z partii FIFO: przychód, koszt, prowizje, dywidendy, zysk, % oraz statystyki (skuteczność, profit factor) | zgodność sum z księgą; test | M |
| **E3.3** Struktura portfela | alokacja wg Walorów, Klas walorów, sektora, waluty ekspozycji, kraju, typu rachunku, **tagów** (nowe: tagi użytkownika na walorach); w czasie (wykres warstwowy) | suma udziałów = 100% (z gotówką jako osobną pozycją) | M |
| **E3.4** Kokpit | wszystkie Portfele w walucie wyświetlania (ustawienia użytkownika, domyślnie PLN): wartość, zmiana dzienna, zysk, TWR YTD/1Y, najwięksi wygrani i przegrani dnia, mini-wykres | sumy przeliczone kursami dnia; test | M |
| **E3.5** Wykresy | wartość vs wpłaty netto, zysk w czasie, TWR vs do 5 benchmarków (wspólny start, ta sama waluta), stopy zwrotu w okresach (miesiąc × rok — mapa ciepła), obsunięcie w czasie, porównanie Portfeli **na TWR** (dziś: normalizacja na wartości, zniekształcona wpłatami) | wykresy czytają snapshoty; brak wywołań dostawcy | L |
| **E3.6** Dywidendy i odsetki | dochód pasywny w czasie (miesięcznie/rocznie, brutto/netto), stopa dywidendy TTM, **stopa od kosztu (YoC)** z partii, top płatnicy | test na przykładzie z metodyki (5,00% i 7,33%) | M |
| **E3.7** „Jak liczymy” | strona metodologii w UI + tooltipy przy każdej metryce (metoda, okres, kursy, czy annualizowana); eksport tabel do CSV | każda metryka w UI ma tooltip z metodą | S |

---

## E4 — Import i eksport

**Cel etapu:** wprowadzenie wieloletniej historii z brokerów w minuty, bez ręcznego przepisywania, z bezpiecznym wycofaniem. Nowy moduł `imports` (D10). Formaty: [podatki i brokerzy](../research/04_rynek_pl_podatki_i_brokerzy.md); wzorce: Portfolio Performance (ekstraktory + łańcuch walidacji), Wealthfolio (szablony mapowania, podgląd) — [lekcje](../research/competitors/02_trackery_porownanie.md).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E4.1** Potok importu | `imports`: przyjęcie pliku (hash, surowa treść) → parser → wiersze pośrednie z zachowaną surową etykietą → rozpoznanie waloru (ISIN, potem ticker + giełda) → walidacja (waluta, brutto = ilość × cena ± prowizja, data) → wykrycie duplikatów (`external_ref` albo data+ISIN+ilość+kwota) → **podgląd (szkic)** → zatwierdzenie w jednej transakcji jako `import_batch` → możliwość cofnięcia partii importu | ponowny import tego samego pliku = 0 nowych operacji; cofnięcie partii przywraca stan sprzed importu | L |
| **E4.2** CSV z mapowaniem | ogólny import CSV/XLSX: wybór kolumn, separatora, formatu liczby (przecinek dziesiętny), kodowania (UTF-8, cp1250), formatu daty; zapisane szablony mapowania; format wklejki zgodny z myfund (`Data;walor;KUPNO|SPRZEDAŻ;ilość;cena;prowizja;kurs`) | test na plikach przykładowych | M |
| **E4.3** Parsery brokerów — pierwsza fala | XTB, mBank eMakler, Interactive Brokers (Flex Query), DEGIRO, Trading212, Revolut; każdy z plikami testowymi (zanonimizowanymi) jak w PP | dla każdego parsera: test na pliku przykładowym, w tym dywidendy, podatek u źródła, przewalutowania | L (per broker S–M) |
| **E4.4** Parsery — druga fala | Bossa (DM BOŚ), BM PKO BP, Santander BM, Exante, obligacjeskarbowe.pl (po E5.1), giełdy krypto (CSV) | jw. | L |
| **E4.5** Eksport i kopia | eksport pełny (JSON: operacje, walory, ceny ręczne, ustawienia; CSV operacji) i import pełny do pustej instancji; eksport w formacie CSV importowalnym przez Portfolio Performance (walidacja krzyżowa metryk) | test: eksport → import do czystej bazy → identyczne snapshoty | M |

---

## E5 — Polskie instrumenty

**Cel etapu:** obsłużyć instrumenty, których zagraniczne trackery nie mają, z automatyczną wyceną. Dowody: [obligacje i dane PL](../research/03_rynek_pl_dane_i_obligacje.md), [IKE/IKZE](../research/04_rynek_pl_podatki_i_brokerzy.md).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E5.1** Obligacje skarbowe detaliczne | `assets/domain/bonds.py` (czysta funkcja wyceny dziennej): typy OTS, ROR, DOR, TOS, COI, EDO, ROS, ROD; parametry serii (data emisji, oprocentowanie 1. okresu, marża, typ: stałe / stopa NBP + marża / CPI + marża, kapitalizacja vs wypłata, opłata za wcześniejszy wykup); seria = typ + miesiąc wykupu (np. EDO1036); dane CPI i stopy NBP z E1.6; operacje: zakup, wypłata odsetek (COI, ROR, DOR), wcześniejszy wykup z opłatą ograniczoną do odsetek, wykup w terminie z podatkiem 19% (poza IKE/IKZE), zamiana serii | testy złote na „Tabelach odsetkowych” z obligacjeskarbowe.pl dla co najmniej EDO, COI, TOS, ROR | L |
| **E5.2** Kalendarz obligacji | wykupy i odsetki w przyszłości, dochód odsetkowy miesięcznie | widok roczny | S |
| **E5.3** Fundusze inwestycyjne (TFI) | wyceny jednostek z dostawcy (Stooq/analizy.pl — wg [dowodu](../research/03_rynek_pl_dane_i_obligacje.md)); konwersja między subfunduszami jako operacja (sprzedaż + kupno bez zmiany daty nabycia podatkowego — do weryfikacji podatkowej) | wycena TFI w kokpicie; test konwersji | M |
| **E5.4** PPK | rachunek PPK z podziałem wpłat: pracownik, pracodawca, dopłaty państwa; podatek od wpłaty pracodawcy jako koszt poza rachunkiem; symulacja wypłaty (zwrot 30% wpłat pracodawcy do ZUS, utrata dopłat — wg [dowodu](../research/04_rynek_pl_podatki_i_brokerzy.md)) | test na przykładzie liczbowym | M |
| **E5.5** Lokaty i konta oszczędnościowe | walor typu lokata: kwota, oprocentowanie, okres, kapitalizacja; dzienna wycena z odsetkami narosłymi; automatyczne zamknięcie z podatkiem 19% | test wyceny w trakcie i po zakończeniu | S |
| **E5.6** Limity IKE/IKZE | pozostały limit wpłat w roku per rachunek (limity roczne jako dane konfiguracyjne, aktualizowane co rok); ostrzeżenie przy przekroczeniu | test: wpłaty sumowane w roku kalendarzowym | S |
| **E5.7** Obligacje Catalyst (opcjonalnie) | kupony, odsetki narosłe przy kupnie/sprzedaży, wykup | test na jednej serii | M |

## Źródła

Wszystkie odwołania w tym pliku prowadzą do dokumentów L4 z 2026-10-01/02 wymienionych w [pliku głównym](./02_roadmapa_funkcjonalna.md).
