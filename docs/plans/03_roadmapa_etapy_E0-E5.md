---
id: plan-feature-roadmap-e0-e5
status: draft
type: mixed
scope: plans/product-roadmap
last_reviewed: 2026-10-02
---

# Jakie kroki składają się na etapy E0–E5 roadmapy?

Część [roadmapy funkcjonalnej](./02_roadmapa_funkcjonalna.md) (L3, szkic). Decyzje D1–D16, kolejność realizacji i definicja ukończenia — w pliku głównym. Kontynuacja: [etapy E6–E11](./04_roadmapa_etapy_E6-E11.md).

**Format kroku:** zakres (moduł) → kryteria akceptacji → rozmiar. Rozmiar: **S** ≤ 1 dzień, **M** 2–4 dni, **L** 1–2 tygodnie, **XL** > 2 tygodnie (szacunek **[wniosek]**, jedna osoba). Defekty F1–F6 i luki G1–G25: [stan FundTrackera](../research/06_stan_found-tracker_vs_cel.md).

---

## E0 — Naprawy i ustawienia

**Cel:** usunąć defekty, które zafałszowują wartości portfeli wielowalutowych, zanim cokolwiek zbudujemy na nich. Bez nowych ADR-ów.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E0.1** Wycena walut obcych (F1, F4) | Kursy w `assets` są względem waluty systemowej (USD). Serwis `portfolios` wyznacza **kurs krzyżowy** waluta waloru → waluta Portfela i przekazuje do `PortfolioValuator.value()` gotową mapę `{(z, do): Decimal}` — `domain/` nie dostaje portu ani I/O (ADR-0005). Dialog zakupu podpowiada kurs z tego samego źródła | Portfel PLN z walorami USD i EUR przy kursach testowych (USD=1, EUR=1,08, PLN=0,25 względem USD): wartość = ilość × cena × kurs krzyżowy (±0,000001); Portfel USD bez zmian; testy parytetu zielone | M |
| **E0.2** Wektory metryk spójne z księgą (F2) | `services/metrics.py`: uwzględnić `fx_rate` operacji i dywidendy (gotówka, zysk). Wartość walorów obcych przeliczana bieżącym kursem krzyżowym do czasu historii kursów (E1.1) — zapisane jako ograniczenie | ostatni punkt `free_cash_vector` = `cash_balance` z księgi (dokładnie); ostatni punkt wartości = wycena z E0.1 (±0,01) | M |
| **E0.3** Operacje wsteczne walidowane historią | `OperationService.create`: operacja z datą wcześniejszą niż ostatnia przechodzi przez `rebuild()` (jak edycja/usunięcie) | wsteczna sprzedaż łamiąca historię → 400 z `code`; poprawna → zapisana, pozycje przeliczone | S |
| **E0.4** Waluta nowego waloru (F5) | tworzenie waloru „po tickerze” bierze walutę z notowania dostawcy | zakup AAPL w Portfelu PLN tworzy walor w USD | S |
| **E0.5** Tickery GPW | symbole Yahoo z sufiksem `.WA` (sprawdzone w [dowodzie](../research/03_rynek_pl_dane_i_obligacje.md)); poprawka danych seed; mapowanie ticker GPW → symbol dostawcy (pole tymczasowe, docelowo E1.2) | odświeżenie ceny CDR/PKO/PKN zwraca cenę w PLN | S |
| **E0.6** Zamknięcie rejestracji | `ALLOW_REGISTRATION` (domyślnie `false` poza dev); pierwsze konto z CLI (D14) | `POST /auth/register` → 403 z `code` przy wyłączonej rejestracji | S |
| **E0.7** Frontend — braki dla istniejącego API | edycja operacji, dialog dywidendy, prowizja przy wpłacie/wypłacie, usunięcie martwych linków (`/settings` do E0.9, `/analytics`, `/alerts`) | scenariusz e2e ręczny: dodaj → edytuj → usuń dywidendę; `npm run build` zielony | M |
| **E0.8** Zmiana waluty bazowej Portfela (F6, G17) | blokada zmiany, gdy Portfel ma operacje (błąd z `code`); komenda CLI raportująca podejrzane dane: walory z walutą = waluta Portfela, a giełdą zagraniczną; operacje z `fx_rate` = 1 przy różnych walutach | test blokady; raport CLI na danych seed | S |
| **E0.9** Ustawienia użytkownika (G21) | `core_data`: waluta wyświetlania (domyślnie PLN), strefa czasowa (Europe/Warsaw), próg nieaktualnej ceny (dni), stopa wolna od ryzyka (E7.2); strona `/settings` | sumy kokpitu przeliczone na walutę wyświetlania; test API ustawień | M |

---

## E1 — Dane rynkowe i historia

**Cel:** każda wycena i wykres liczą się z danych w bazie, bez sieci w ścieżce żądania. Dowody: [dane rynkowe PL](../research/03_rynek_pl_dane_i_obligacje.md), [lekcje techniczne](../research/competitors/02_trackery_porownanie.md). Wymaga ADR: **D5, D7, D8, D14**.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E1.1** Historia cen i kursów | `assets`: `assets_price` (walor, data, zamknięcie, waluta, źródło, `is_synthetic`), `assets_fx_rate` (z, do, data, kurs, źródło, numer tabeli NBP); unikalność (walor/para, data, źródło); ceny **nieskorygowane**; znacznik `last_price_change_at` | `find_close(asset, date)` z forward-fill i flagą syntetyczną; testy repozytorium | M |
| **E1.2** Rejestr dostawców | port `MarketDataProvider` z `capabilities`; adaptery: **NBP** (kursy tabela A/B; zapytania w paczkach ≤ 93 dni; cofanie po 404 do dnia roboczego), **Yahoo** (GPW `.WA`, zagranica, krypto; jawnie ceny nieskorygowane — `auto_adjust=False` lub równoważne; domyślne zachowanie `yfinance` do weryfikacji **[niezweryfikowane]**), **Stooq** opcjonalnie (klucz API w `.env`); priorytet per walor + mapowanie symboli `assets_listing` (walor, dostawca, symbol); retry, timeout, wyłącznik awaryjny | testy kontraktowe na nagranych odpowiedziach; walor po splicie (np. akcja z udokumentowanym splitem) ma ceny nieskorygowane; kurs NBP USD 2026-09-25 = 3,8404 (tabela 187/A/NBP/2026) w teście nagranym | L |
| **E1.3** Identyfikacja walorów | pola `isin`, giełda/MIC, `country`, `sector`, `asset_type` (akcja, ETF, fundusz, obligacja skarbowa, obligacja, krypto, waluta, surowiec, lokata, walor użytkownika); lokalny katalog GPW/NC; wyszukiwanie po nazwie i tickerze | wyszukanie „orlen” zwraca PKN | M |
| **E1.4** Odświeżanie w tle | `assets/entrypoints.py` (`session_scope`, ADR-0002) + `app/cli.py`: `refresh-prices`, `refresh-fx`; **dociąganie historii orkiestruje `portfolios/entrypoints.py`** (zna okresy posiadania, prosi `assets` przez serwis o zakres dat) — bez zależności `assets → portfolios`; usunięcie synchronicznego odświeżania z `GET /portfolios/positions` | zadania idempotentne (drugie uruchomienie = 0 zapisów); żądania HTTP nie wołają dostawcy (test z dostawcą rzucającym wyjątek) | M |
| **E1.5** Ceny ręczne, walory użytkownika | dodawanie/edycja ceny historycznej; walor bez dostawcy (złoto fizyczne, PPK przed E5.4) | ręczna cena ma pierwszeństwo i jest oznaczona `source=manual` | S |
| **E1.6** Benchmarki i szeregi stóp | benchmark = walor (WIG, WIG20, mWIG40TR, S&P 500, ETF na MSCI World/ACWI); `assets_rate_series`: stopa referencyjna NBP (`stopy_procentowe.xml`), CPI GUS r/r (BDL API) — CPI **tylko** do zwrotu realnego i prognoz, nie do wyceny obligacji (E5.1) | parsery z testami na nagranych plikach | M |
| **E1.7** Jakość danych | w odpowiedziach: `price_date`, `stale` (> próg z E0.9), `source`; panel „Dane” (ostatnie odświeżenie, błędy dostawców) | walor bez ceny od 7 dni oznaczony w UI | S |
| **E1.8** Lista obserwowanych | walory nieposiadane z ceną i zmianą (G25) | dodanie/usunięcie z listy; cena z E1.1 | S |
| **E1.9** Kalendarz sesji | dni sesyjne GPW i giełd zagranicznych (z historii cen + lista świąt); flaga `is_trading_day` | statystyki E7.1 pomijają dni bez sesji | S |

---

## E2 — Księga v2

**Cel:** model księgowy unoszący polskie realia. Każdy krok to addytywna migracja z zielonymi testami parytetu i przebudową istniejących danych (D16). Wymaga ADR: **D1, D2, D3, D4, D9, D12, D13, D15, D16**.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E2.0** Polityka migracji danych | `portfolios/entrypoints.py` + CLI `rebuild-all` (pozycje, salda, partie, snapshoty z operacji); `operation_date` → data w Europe/Warsaw + `sequence` (D13) | `rebuild-all` na danych seed daje stan identyczny z obecnym; drugie uruchomienie bez zmian | M |
| **E2.1** Portfel jako rachunek | `account_type` (zwykły, IKE, IKZE, PPK, PPE, OIPE), `broker`, domyślna prowizja (% + minimum) per typ waloru; **Grupa portfeli** (agregacja bez własnych operacji) | istniejące Portfele = „zwykły”; filtr i grupowanie w API | M |
| **E2.2** Gotówka wielowalutowa | `portfolios_cash_balance` (Portfel, Waluta); operacja przewalutowania (kwota z, kwota do, kurs, prowizja); reguła reinterpretacji `fx_rate` istniejących operacji wg ADR D4; nowa baza testów parytetu | zakup akcji USD z salda USD; brak salda → błąd z `code` | L |
| **E2.2b** Tryb automatycznych wpłat | ustawienie Portfela: przy zakupie bez gotówki system dopisuje automatyczną wpłatę, przy sprzedaży — wypłatę (odpowiednik portfela „bezgotówkowego” myfund, [dowód](../research/competitors/01_myfund.md)); potrzebne przy imporcie samych transakcji | TWR i XIRR traktują automatyczne wpłaty jako przepływy zewnętrzne; test | S |
| **E2.3** Nowe typy Operacji | `interest`, `fee` (z flagą „koszt podatkowy”), `tax` (WHT, Belka), przelew gotówki i walorów między Portfelami (z zachowaniem kosztu i daty nabycia partii; **kaskadowe przeliczenie powiązanego Portfela**), `adjustment`; pola z D9 (m.in. `settlement_date`, `fx_rate_tax` + tabela NBP — wypełniane automatycznie wg D12, `status`, `external_ref`) | każda operacja ma regułę w `PortfolioLedger` i test; przelew walorów nie zmienia zysku całkowitego obu Portfeli łącznie; edycja przelewu w A przelicza B | L |
| **E2.4** Partie zakupu | `domain/lots.py`: `LotBook` — otwarcie przy zakupie/przelewie, zużycie FIFO lub wskazanej partii (D2), prowizja sprzedaży proporcjonalnie; tabele pochodne `portfolios_lot`, `portfolios_lot_consumption`; **zysk zrealizowany** (waluta waloru, waluta Portfela, PLN po kursie podatkowym) | test złoty z [metodyki](../research/05_metodyka_metryk.md): zrealizowany 336,50 (FIFO) vs 286,50 (średnia), zysk całkowity 384,00 w obu; test własności „zysk całkowity niezależny od metody” | L |
| **E2.5** Snapshoty dzienne | `portfolios_daily` (wartość, gotówka, przepływy zewn. we/wy, dochody, opłaty, podatki, `r_day`, `twr_index` jako `Decimal`, skumulowane przepływy, `data_quality`) i `portfolios_position_daily`; unieważnienie od daty zmiany: operacja (natychmiast), cena/kurs (entrypoint `portfolios` porównuje `last_price_change_at`, D7) | wektory wykresów czytane ze snapshotów; wykres 5 lat < 300 ms na zbiorze 10 lat × 200 operacji × 30 walorów | L |
| **E2.6** Słownik i dokumentacja | `CONTEXT.md` (D3); `05_portfolios_module.md` | `kb_validate --strict` bez nowych błędów | S |
| **E2.7** Historia operacji | paginacja, filtry (typ, walor, data, tag, status), komentarze; godzina operacji (D13) w UI | lista 10 000 operacji < 300 ms na stronę | M |

Do E2 (kolejność realizacji M0) dołączony jest **E8.1 split ręczny** — split w historii właściciela zepsułby wyceny przed E8.

---

## E3 — Analityka podstawowa

**Cel:** „ile zarobiłem”, „jak wypadam na tle WIG”, „z czego składa się portfel” — poprawnie i z jawną metodą. Wymaga ADR: **D6, D11**. Formuły i testy złote: [metodyka](../research/05_metodyka_metryk.md).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E3.1** Stopy zwrotu | `GET /portfolios/{id}/performance?period=1M\|3M\|6M\|YTD\|1Y\|3Y\|5Y\|MAX\|custom` (też Grupa i „wszystkie”): zysk kwotowy, TWR (`twr_index`), XIRR (Newton + bisekcja, kody `irr_undefined`/`irr_ambiguous`), annualizacja tylko ≥ 365 dni, `effective_start`, `method`, `data_quality`; klasyfikacja przepływów zależna od zakresu (przelew między Portfelami Grupy jest wewnętrzny dla Grupy, zewnętrzny dla Portfela); TWR realny (CPI z E1.6) | TWR 3-dniowy = 3,0000%; XIRR przykład Excela = 0,373362535 (±1e-8); Modified Dietz 1,20 (fallback); okres < 365 dni → `annualized = null` | L |
| **E3.2** Zamknięte pozycje | raport z partii: przychód, koszt, prowizje, dywidendy, zysk, %, skuteczność, profit factor | suma zysków = suma zrealizowanego z E2.4 | M |
| **E3.3** Struktura | alokacja wg Walorów, Klas, sektora, waluty, kraju, typu rachunku, **tagów użytkownika**; w czasie | suma udziałów = 100% (gotówka osobno) | M |
| **E3.4** Kokpit | wszystkie Portfele w walucie wyświetlania (E0.9): wartość, zmiana dzienna, zysk, TWR YTD/1Y, wygrani/przegrani dnia, mini-wykres | sumy = Σ wycen Portfeli przeliczonych kursem dnia | M |
| **E3.5** Wykresy | wartość vs wpłaty netto, zysk w czasie, TWR vs do 5 benchmarków (CPI i oprocentowanie lokat też jako benchmark), stopy w okresach (mapa ciepła miesiąc × rok), obsunięcie, porównanie Portfeli **na TWR**, mapa cieplna Portfela, porównanie do 4 walorów | brak wywołań dostawcy (test) | L |
| **E3.6** Dywidendy i odsetki | dochód pasywny miesięcznie/rocznie (brutto/netto), stopa TTM, **stopa od kosztu** z partii, top płatnicy | 5,00% i 7,33% dla przykładu z metodyki | M |
| **E3.7** „Jak liczymy” | strona metodologii + tooltipy (metoda, okres, kursy, annualizacja); eksport tabel do CSV | każda metryka w UI ma tooltip | S |
| **E3.8** Widok waloru | wykres ceny z naniesionymi Operacjami i dywidendami, partie, zysk, stopa zwrotu pozycji, dywidendy | przejście kokpit → Portfel → walor → operacja | M |

W kolejności realizacji M1 do E3 dochodzi **E7.4 efekt walutowy** (inwestor PLN z ETF-ami w USD potrzebuje go od początku).

---

## E4 — Import i eksport

**Cel:** wieloletnia historia z brokerów i z myfund w minuty, z bezpiecznym wycofaniem. Import w module `portfolios` (D10). Formaty: [podatki i brokerzy](../research/04_rynek_pl_podatki_i_brokerzy.md); wzorce PP i Wealthfolio: [lekcje](../research/competitors/02_trackery_porownanie.md). Realizacja: E4.1, E4.2, E4.2a w M0 (zaraz po E2.4).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E4.1** Potok importu | plik (hash, surowa treść) → parser (adapter w `infrastructure/`) → wiersze pośrednie z surową etykietą → rozpoznanie waloru (ISIN, ticker + giełda) z podglądem nierozpoznanych → walidacja (waluta, brutto = ilość × cena ± prowizja, data) → duplikaty (`external_ref` albo data+ISIN+ilość+kwota) → **szkic** → zatwierdzenie jako `import_batch` przez rdzeń `record_many` bez commitu (ADR-0008) z jednym `rebuild` → cofnięcie partii (D15); poprawki użytkownika (np. zmiana typu) zachowane przy ponownym imporcie | ponowny import tego samego pliku = 0 nowych operacji; cofnięcie partii przywraca stan sprzed importu; import 2 000 wierszy < 10 s | L |
| **E4.2** CSV z mapowaniem | CSV/XLSX: wybór kolumn, separatora, przecinka dziesiętnego, kodowania (UTF-8, cp1250), formatu daty; zapisane szablony; format wklejki myfund (`Data;walor;KUPNO\|SPRZEDAŻ;ilość;cena;prowizja;kurs`) | testy na plikach przykładowych w obu kodowaniach | M |
| **E4.2a** Przeniesienie z myfund | import eksportu portfela myfund i eksportu historii operacji (CSV/XLS z tabel); format do ustalenia na pliku właściciela **[niezweryfikowane]**; uzgodnienie wartości ze składem portfela w myfund | ilości i salda zgodne z myfund dla portfela właściciela | M |
| **E4.3** Parsery — fala 1 | XTB, mBank eMakler (CSV lub PDF — ekstraktor wzorem PP), Interactive Brokers (Flex Query), DEGIRO, Trading212 (pliki ≤ 365 dni, deduplikacja po `ID`), Revolut; zanonimizowane pliki testowe | test na pliku przykładowym, w tym dywidendy, WHT, przewalutowania | XL (per broker S–M) |
| **E4.4** Parsery — fala 2 | Bossa (osobne pliki dla IKE/IKZE), BM PKO BP, Santander BM, Exante, obligacjeskarbowe.pl (po E5.1), giełdy krypto | jw. | L |
| **E4.5** Eksport i kopia | eksport pełny (JSON) i import do pustej instancji; CSV operacji; CSV zgodny z importem Portfolio Performance (walidacja krzyżowa metryk) | eksport → import do czystej bazy → identyczne snapshoty | M |

---

## E5 — Polskie instrumenty

**Cel:** instrumenty, których zagraniczne trackery nie mają. Dowody: [obligacje i dane PL](../research/03_rynek_pl_dane_i_obligacje.md), [IKE/IKZE](../research/04_rynek_pl_podatki_i_brokerzy.md).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E5.1** Obligacje skarbowe detaliczne | wzory z listów emisyjnych jako czyste funkcje w `assets/domain/bonds.py` (osobna funkcja per typ: OTS, ROR, DOR, TOS, COI, EDO, ROS, ROD — różne zaokrąglenia i reguły opłat, w tym ROR/DOR i COI od 2. okresu: pełna opłata bez dolnego ograniczenia); **wycena per partia** (seria, data zakupu, ilość) w `portfolios` (zależy od E2.4); **ogłoszona stopa każdego okresu przechowywana jako fakt** (nie liczona z CPI); operacje: zakup, wypłata odsetek (COI, ROR, DOR), przedterminowy wykup z opłatą, wykup, zamiana serii; podatek 19% poza IKE/IKZE | testy złote z dowodu: EDO0524 4,16 / 101,75; TOS0825 7,96 / 105,88; TOS1029 113,79; ROR0623 0,44 / 0,41 / 0,18 / 99,68; dodatkowo fixture'y z Tabel odsetkowych (PDF), w tym okres z 29 lutego | L |
| **E5.2** Kalendarz obligacji | wykupy i odsetki w przyszłości, dochód odsetkowy miesięcznie | widok roczny zgodny z E5.1 | S |
| **E5.3** Fundusze TFI | wyceny jednostek: źródło do wyboru po zbadaniu ToS (analizy.pl / strony TFI / CSV ręczny — [dowód](../research/03_rynek_pl_dane_i_obligacje.md) nie rozstrzyga); konwersja między subfunduszami parasola bez przychodu (art. 17 ust. 1c) z przeniesieniem partii | wycena TFI w kokpicie; konwersja nie zmienia kosztu podatkowego | M |
| **E5.4** PPK | rachunek PPK z wpłatami: pracownik, pracodawca, dopłaty państwa; podatek od wpłaty pracodawcy jako koszt; symulacja wypłaty — zasady do zweryfikowania w źródle pierwotnym (dowód nie sprawdził PPK) | test na przykładzie liczbowym z ustawy o PPK | M |
| **E5.5** Lokaty | walor typu lokata: kwota, oprocentowanie, okres, kapitalizacja; dzienna wycena; zamknięcie z podatkiem 19% | wycena w trakcie i po zakończeniu | S |
| **E5.6** Limity IKE/IKZE | pozostały limit wpłat w roku per rachunek (limity jako konfiguracja roczna: 2026 — IKE 28 260 zł, IKZE 11 304 zł / 16 956 zł; [dowód](../research/04_rynek_pl_podatki_i_brokerzy.md)); raport wpłat IKZE do odliczenia w PIT-37/36 | ostrzeżenie przy przekroczeniu; suma wpłat IKZE za rok | S |
| **E5.7** Obligacje Catalyst (opcjonalnie) | kupony, odsetki narosłe przy kupnie/sprzedaży, wykup | test na jednej serii | M |

## Źródła

Odwołania prowadzą do dokumentów L4 z 2026-10-01/02 wymienionych w [pliku głównym](./02_roadmapa_funkcjonalna.md).
