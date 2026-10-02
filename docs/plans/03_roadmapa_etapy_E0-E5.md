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
| **E0.1** Wycena walut obcych (F1, F4) | Kursy w `assets` są względem waluty systemowej (USD). Serwis `portfolios` wyznacza **kurs krzyżowy** waluta waloru → waluta Portfela i przekazuje do `PortfolioValuator.value()` gotową mapę `{(currency_id_z, currency_id_do): Decimal}` = rate[z]/rate[do] (`FxMapBuilder`; `Currency.exchange_rate` = „USD za 1 jednostkę”, `assets/services/market_data.py:109`) — `domain/` nie dostaje portu ani I/O (ADR-0005). Dialog zakupu podpowiada kurs krzyżowy przez `GET /portfolios/fx-rate?from_currency=&to_currency=` ([kontrakt 2.4](../technical/backend/09_kontrakt_api_docelowy.md)); `GET /assets/currencies/rate` zwraca tylko kursy bezpośrednie/odwrotne. Brak kursu (przed E1.1 heurystyka: `exchange_rate==1` ∧ `code≠USD`; nowa waluta ma domyślnie 1) → wycena pozycji oznaczona `RATE_MISSING` zamiast cichego kursu 1; pola `PositionResponse` dotyczące wartości stają się nullable. `HoldingLike` się zmienia — przepisać `test_valuation.py:54-84`, `test_portfolio_service.py:94`, `test_position_service.py:61`, `test_wiring.py:44`; seed nie ma walut obcych w Portfelach (`seed_data.py:187-211`) → własne fixtures | Portfel PLN z walorami USD i EUR przy kursach testowych (USD=1, EUR=1,08, PLN=0,25 względem USD): wartość = ilość × cena × kurs krzyżowy (±0,000001); Portfel USD bez zmian; brak kursu → `RATE_MISSING`; testy parytetu zielone | M |
| **E0.2** Wektory metryk spójne z księgą (F2) | `services/metrics.py`: uwzględnić `fx_rate` operacji i dywidendy; dywidenda zmienia tylko `free_cash` i `profit`, nie `transaction_cost_vector`; „wszystkie portfele” miesza waluty → wymagać Portfela. Testy do przepisania: `test_metrics_service.py:67-80,143-155`. Wartość walorów obcych przeliczana bieżącym kursem krzyżowym do czasu historii kursów (E1.1) — zapisane jako ograniczenie | ostatni punkt `free_cash_vector` = `cash_balance` z księgi (±0,01 — wektor jest `float`, porównanie z tolerancją); ostatni punkt wartości = wycena z E0.1 (±0,01 przy tej samej cenie wejściowej — wektor bierze `provider.current_price`, wycena `asset.current_price`; test wstrzykuje tę samą cenę) | M |
| **E0.3** Operacje wsteczne walidowane historią | `OperationService.create`: **każda** nowa operacja przechodzi przez `rebuild()` historii (jak edycja/usunięcie) — bez osobnej ścieżki „stan bieżący” (decyzja właściciela); przed włączeniem `rebuild-all --check` (dane mogą być już niespójne); testy `test_operation_service.py:111-390` do przepisania | wsteczna sprzedaż łamiąca historię → 400 z `code`; poprawna → zapisana, pozycje przeliczone | S |
| **E0.4** Waluta nowego waloru (F5) | tworzenie waloru „po tickerze” bierze walutę z notowania dostawcy; wywołanie dostawcy **poza** `transaction()`, błąd dostawcy → 502 `MARKET_DATA_UNAVAILABLE` (nie cicha waluta Portfela); `None` od dostawcy → 404 `ASSET_NOT_FOUND_ON_PROVIDER`; rdzeń `create_from_provider` bez commitu (ADR-0008) wołany po pobraniu notowania, PRZED `transaction()`; testy `test_operation_service.py:224-268`, `integration/test_portfolio_flow.py:127` | zakup AAPL w Portfelu PLN tworzy walor w USD; błąd dostawcy → 502 i brak zapisu | S |
| **E0.5** Tickery GPW | symbole Yahoo z sufiksem `.WA` (sprawdzone w [dowodzie](../research/03_rynek_pl_dane_i_obligacje.md)); poprawka danych seed (tickery `.WA`); **seed generuje stany Portfeli i Pozycji replayem operacji**, nie zahardkodowane (dziś gotówka i dywidendy w `seed_data.py` nie zgadzają się z replayem — [ADR-0019](../technical/adr/0019-migracje-danych-i-kolumny-dat.md)); wpłata Portfela Crypto 8 000 → 16 000 (zakupy BTC/ETH wymagają ≥ 15 632); `with session.begin()` w `seed/seed.py` zgodnie z `transaction()`; bez nowych pól w modelu — symbol dostawcy to po prostu `ticker` z sufiksem do czasu `assets_listing` w E1.2 (migracja danych wtedy przez `rebuild-all`, nie edycję migracji) | odświeżenie ceny CDR/PKO/PKN zwraca cenę w PLN; replay seedu przez `PortfolioLedger` nie rzuca (`rebuild-all` jest dopiero w E2.0) | S |
| **E0.6** Zamknięcie rejestracji | `ALLOW_REGISTRATION` (domyślnie true w `ENVIRONMENT=test`/dev — testy używają `/auth/register`, `conftest.py:46`; false w produkcji); pierwsze konto z CLI; flaga `is_owner` (migracja addytywna) i CLI `set-owner` — podstawa 403 na zapisach `assets` (D14, biz. ADR 0007) | `POST /auth/register` → 403 `REGISTRATION_DISABLED` przy wyłączonej rejestracji; `GET /auth/me` zwraca `is_owner` | S |
| **E0.7** Frontend — braki dla istniejącego API | **naprawa startu** (`frontend/index.html:11` → `main.tsx`, ikona bez backslasha), `lib/format.ts` zastępujący 5 lokalnych formatterów, runner testów (Vitest — nowa zależność, wymaga zgody właściciela) z pierwszymi testami formatowania, edycja operacji, dialog dywidendy, prowizja przy wpłacie/wypłacie, jedna nawigacja zamiast sidebar + zakładki, usunięcie martwych linków (`/settings` do E0.9, `/analytics`, `/alerts`); szczegóły: [IA i konwencje UI](../technical/frontend/ia-i-konwencje-ui.md) | `npm run build` i `npm test` zielone; scenariusz ręczny: dodaj → edytuj → usuń dywidendę | M |
| **E0.8** Zmiana waluty bazowej Portfela (F6, G17) | blokada zmiany, gdy Portfel ma operacje; blokada = 409 `PORTFOLIO_CURRENCY_LOCKED`; komenda CLI raportująca podejrzane dane: waluta waloru = waluta Portfela ∧ (`exchange==""` ∨ `fx_rate==1` przy różnych walutach) | test blokady; raport CLI na danych seed | S |
| **E0.9** Ustawienia użytkownika (G21, F3) | `core_data`: waluta wyświetlania (domyślnie PLN), próg nieaktualnej ceny (dni), stopa wolna od ryzyka (E7.2); strefa czasowa bez ustawienia — stała Europe/Warsaw ([ADR-0019](../technical/adr/0019-migracje-danych-i-kolumny-dat.md)); strona `/settings`; „Całkowita wartość” w kokpicie = gotówka + wycena pozycji (F3), sumy tylko z istniejących endpointów Portfeli (`/dashboard` to E3.4) | sumy kokpitu (gotówka + pozycje) przeliczone na walutę wyświetlania; test API ustawień | M |
| **E0.10** Nazewnictwo frontendu | `Pocket` → `Portfolio` w typach, plikach, hookach i trasach (130 wystąpień w 19 plikach); trasy po `id` (`/portfolios/:id`) z przekierowaniem ze starych `/pockets/:slug`; **przed** nowymi ekranami, żeby nie mnożyć długu; backend: pole `portfolio_id` w odpowiedziach pozycji i operacji (dziś frontend wysyła `portfolio_name`: `positionService.ts:7`, `operationService.ts:7`, `schemas/positions.py:43`) | brak słowa „Pocket” w `frontend/src`, z wyjątkiem pliku przekierowań i aliasu `pocket_value_vector` (usuwany w E3.5); stare linki przekierowują | S |

---

## E1 — Dane rynkowe i historia

**Cel:** każda wycena i wykres liczą się z danych w bazie, bez sieci w ścieżce żądania. Dowody: [dane rynkowe PL](../research/03_rynek_pl_dane_i_obligacje.md), [lekcje techniczne](../research/competitors/02_trackery_porownanie.md). Wymaga ADR: **D5, D7, D8, D14**.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E1.1** Historia cen i kursów | `assets`: `assets_price` (walor, data, zamknięcie, waluta, źródło, `is_synthetic`), `assets_fx_rate` (z, do, data, kurs, źródło, numer tabeli NBP); unikalność (walor/para, data, źródło); ceny **nieskorygowane**; dziennik zmian `assets_price_change` ([ADR-0016](../technical/adr/0016-snapshoty-dzienne-i-przebudowa.md)); zapis `current_price` w tej samej transakcji co zapis ceny ([ADR-0015](../technical/adr/0015-historia-cen-i-kursow.md)) | `find_close(asset, date)` z forward-fill i flagą syntetyczną; testy repozytorium | M |
| **E1.2** Rejestr dostawców | port `MarketDataProvider` z `capabilities`; adaptery: **NBP** (kursy tabela A/B; zapytania w paczkach ≤ 93 dni; cofanie po 404 do dnia roboczego), **Yahoo** (GPW `.WA`, zagranica, krypto; jawnie ceny nieskorygowane — `auto_adjust=False` lub równoważne; domyślne zachowanie `yfinance` do weryfikacji **[niezweryfikowane]**), **Stooq** opcjonalnie (klucz API w `.env`); priorytet per walor + mapowanie symboli `assets_listing` (walor, dostawca, symbol); retry, timeout, wyłącznik awaryjny | testy kontraktowe na nagranych odpowiedziach; walor po splicie (np. akcja z udokumentowanym splitem) ma ceny nieskorygowane; kurs NBP USD 2026-09-25 = 3,8404 (tabela 187/A/NBP/2026) w teście nagranym | L |
| **E1.3** Identyfikacja walorów | pola `isin`, giełda/MIC, `country`, `sector`, `asset_type` (akcja, ETF, fundusz, obligacja skarbowa, obligacja, krypto, waluta, surowiec, lokata, walor użytkownika); lokalny katalog GPW/NC (źródło listy do ustalenia przy E1.2 — dowód nie wskazuje darmowego, oficjalnego źródła; kandydat: lista z dostawcy); relacja `asset_type` ↔ `assets_assetclass` rozstrzygnięta w [schemacie](../technical/backend/07_schemat_danych_docelowy.md); wyszukiwanie po nazwie i tickerze | wyszukanie „orlen” zwraca PKN | M |
| **E1.4** Odświeżanie w tle | `assets/entrypoints.py` (`session_scope`, ADR-0002) + `app/cli.py`: `refresh-prices`, `refresh-fx`; **dociąganie historii orkiestruje `portfolios/entrypoints.py`** (zna okresy posiadania, prosi `assets` przez serwis o zakres dat) — bez zależności `assets → portfolios`; usunięcie synchronicznego odświeżania z `GET /portfolios/positions`; wyjątek: „żądania HTTP nie wołają dostawcy synchronicznie; wyjątek: jawne ręczne odświeżenie ceny przez przycisk — `POST /assets/refresh-prices` → 202, `BackgroundTasks` wołające tylko `assets.entrypoints.refresh_prices`” ([ADR-0017](../technical/adr/0017-zadania-w-tle-i-cli.md)) | zadania idempotentne dla zamknięć dziennych (drugie uruchomienie = 0 nowych wierszy; cena bieżąca jest nadpisywana); żądania HTTP nie wołają dostawcy synchronicznie (test z dostawcą rzucającym wyjątek; `refresh-prices` zwraca 202) | M |
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
| **E2.0** Polityka migracji danych | `portfolios/entrypoints.py` + CLI `rebuild-all` (pozycje, salda, partie, snapshoty z operacji); **nowe kolumny `operation_day`** (data w Europe/Warsaw), `sequence` (z kolejności `(operation_date, created_at, id)`) i `currency_id` (= waluta bazowa Portfela dla istniejących wierszy) obok `operation_date`; klucz księgi `(operation_day, sequence, id)`; pozycje aktualizowane W MIEJSCU (zachowuje `opened_at`); `portfolios_portfolio.dirty_from` wprowadzone tu (nie w E2.5) (D13; zamiana typu istniejącej kolumny bez `USING` użyłaby strefy sesji DB, [ADR-0019](../technical/adr/0019-migracje-danych-i-kolumny-dat.md)); schematy: [schemat danych](../technical/backend/07_schemat_danych_docelowy.md) | po naprawie seed (E0.5) `rebuild-all` daje stan identyczny z operacjami; drugie uruchomienie bez zmian (idempotencja) | M |
| **E2.1** Portfel jako rachunek | `account_type` (zwykły, IKE, IKZE, PPK, PPE, OIPE), `broker`, domyślna prowizja (% + minimum) per Klasa waloru do czasu `asset_type` (E1.3); **Grupa portfeli** (agregacja bez własnych operacji) | istniejące Portfele = `regular`; filtr i grupowanie w API | M |
| **E2.2** Gotówka wielowalutowa | `portfolios_cash_balance` (Portfel, Waluta); operacja przewalutowania jako typ Operacji w tym kroku (`amount` = noga wychodząca, `counter_*` = przychodząca, kurs, prowizja); `LedgerState.cash_balance` zostaje jako właściwość salda waluty bazowej (parytet: `test_ledger_parity.py:58,87,133,144,186`), `valuation.py:82` sumuje salda wszystkich walut przeliczone kursami; `fx_rate` default 1 (`schemas/operations.py:52`) niewymuszalny — serwis wymaga kursu przy walucie ≠ bazowej (`RATE_MISSING`); skala salda `Numeric(18,3)`; reguła reinterpretacji `fx_rate` istniejących operacji wg ADR D4; nowa baza testów parytetu | zakup akcji USD z salda USD; brak salda → błąd z `code` | L |
| **E2.2b** Tryb automatycznych wpłat | ustawienie Portfela: przy zakupie bez gotówki system dopisuje automatyczną wpłatę, przy sprzedaży — wypłatę (odpowiednik portfela „bezgotówkowego” myfund, [dowód](../research/competitors/01_myfund.md)); potrzebne przy imporcie samych transakcji | TWR i XIRR traktują automatyczne wpłaty jako przepływy zewnętrzne; test | S |
| **E2.3** Nowe typy Operacji | `interest`, `fee` (z flagą „koszt podatkowy”), `tax` (WHT, Belka), przelew gotówki i walorów między Portfelami jako **jeden wiersz** (`counter_portfolio_id`, `counter_amount`, `counter_currency_id`; `direction` w odpowiedzi; FK `ON DELETE RESTRICT`; `total_deposited` się nie zmienia; **kaskadowe przeliczenie powiązanego Portfela**) — przelew gotówki od E2.3, **przelew papierów dopiero po E2.4** (zachowanie kosztu i daty nabycia Partii); `adjustment` = korekta ilości/gotówki z `notes` (definicja w 07); `fx_rate_tax` przed E1.2 tylko ręczny; pola z D9 (m.in. `settlement_date`, `fx_rate_tax` + tabela NBP — wypełniane automatycznie wg D12, `status`, `external_ref`) | każda operacja ma regułę w `PortfolioLedger` i test; przelew walorów nie zmienia zysku całkowitego obu Portfeli łącznie; edycja przelewu w A przelicza B | L |
| **E2.4** Partie zakupu | `domain/lots.py` (wewnętrzny moduł ledgera, DOM-10; wpis w `DOMAIN_LAYERS` testu czystości): `LotBook` — otwarcie przy zakupie/przelewie, zużycie FIFO lub wskazanej partii (D2), prowizja sprzedaży proporcjonalnie; tabele pochodne `portfolios_lot` (`open_operation_id`, `origin_operation_id`), `portfolios_lot_consumption`, wskazanie partii `portfolios_operation_lot_pick`; `HoldingLike` (`protocols.py:73-85`) i `valuation.py:53` czytają Partie, repozytorium je ładuje (`repositories/portfolios.py:16-30`); **zysk zrealizowany** (waluta waloru, waluta Portfela, PLN po kursie podatkowym) | **wycena otwartych pozycji czyta koszt z partii** (dziś `ilość × średnia`, `valuation.py:53`); wskazanie partii przy sprzedaży (`lot_pick`: `origin_operation_id`, D2); test złoty z [metodyki](../research/05_metodyka_metryk.md): zrealizowany 336,50 (FIFO) vs 286,50 (średnia), zysk całkowity 384,00 w obu; test własności „zysk całkowity niezależny od metody” | L |
| **E2.5** Snapshoty dzienne | `portfolios_daily` (wartość, gotówka, przepływy zewn. we/wy, dochody, opłaty, podatki, `r_day`, `twr_index` jako `Decimal`, skumulowane przepływy, `data_quality`) i `portfolios_position_daily`; unieważnienie od **daty najstarszej zmiany**: operacja (natychmiast), cena/kurs (entrypoint `portfolios` czyta dziennik `assets_price_change` przez kursor `portfolios_market_cursor`, kolumna `dirty_from`, [ADR-0016](../technical/adr/0016-snapshoty-dzienne-i-przebudowa.md)); `position_daily` zawiera wartość i kurs w walucie waloru (dla E7.4) | wektory wykresów czytane ze snapshotów; wykres 5 lat < 300 ms na zbiorze 10 lat × 200 operacji × 30 walorów | L |
| **E2.6** Słownik i dokumentacja | `CONTEXT.md` (D3); `05_portfolios_module.md` | `kb_validate --strict` bez nowych błędów | S |
| **E2.7** Historia operacji | paginacja, filtry (typ, walor, data, tag, status), komentarze; godzina operacji (D13) w UI | lista 10 000 operacji < 300 ms na stronę | M |

Do E2 (kolejność realizacji M0) dołączony jest **E8.1 split ręczny** — split w historii właściciela zepsułby wyceny przed E8.

---

## E3 — Analityka podstawowa

**Cel:** „ile zarobiłem”, „jak wypadam na tle WIG”, „z czego składa się portfel” — poprawnie i z jawną metodą. Wymaga ADR: **D6, D11**. Formuły i testy złote: [metodyka](../research/05_metodyka_metryk.md).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E3.1** Stopy zwrotu | `GET /portfolios/{id}/performance?period=1M\|3M\|6M\|YTD\|1Y\|3Y\|5Y\|MAX\|custom` (też Grupa i „wszystkie”): zysk kwotowy, TWR (`twr_index`), XIRR (Newton + bisekcja, kody inline `IRR_UNDEFINED`/`IRR_AMBIGUOUS`, HTTP 200), annualizacja tylko ≥ 365 dni, `effective_start`, `method`, `data_quality`; klasyfikacja przepływów zależna od zakresu (przelew między Portfelami Grupy jest wewnętrzny dla Grupy, zewnętrzny dla Portfela); TWR realny (CPI z E1.6 — po M0) | TWR 3-dniowy = 3,0000%; XIRR przykład Excela = 0,373362535 (±1e-8); Modified Dietz 1,20 (fallback); okres < 365 dni → `annualized = null` | L |
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
| **E4.1** Potok importu | plik (hash, surowa treść) → parser (adapter w `infrastructure/`) → wiersze pośrednie z surową etykietą → rozpoznanie waloru (ISIN, ticker + giełda) z podglądem nierozpoznanych → walidacja (waluta, brutto = ilość × cena ± prowizja, data) → duplikaty (`external_ref` albo data+ISIN+ilość+kwota) → **szkic** → zatwierdzenie jako paczka importu (`import_batch`) przez rdzeń `record_many` bez commitu (ADR-0008) z jednym `rebuild` → cofnięcie paczki (D15); poprawki użytkownika (np. zmiana typu) zachowane przy ponownym imporcie | ponowny import tego samego pliku = 0 nowych operacji; cofnięcie paczki przywraca stan sprzed importu; import 2 000 wierszy < 10 s | L |
| **E4.2** CSV z mapowaniem | CSV/XLSX: wybór kolumn, separatora, przecinka dziesiętnego, kodowania (UTF-8, cp1250), formatu daty; zapisane szablony; format wklejki myfund (`Data;walor;KUPNO\|SPRZEDAŻ;ilość;cena;prowizja;kurs`) | testy na plikach przykładowych w obu kodowaniach | M |
| **E4.2a** Przeniesienie z myfund | import eksportu portfela myfund i eksportu historii operacji (CSV/XLS z tabel); **blokada: wymaga próbki eksportu myfund od właściciela** (format niepublicznie udokumentowany **[niezweryfikowane]**); uzgodnienie wartości ze składem portfela w myfund | ilości i salda zgodne z myfund dla portfela właściciela; parser z testem na zanonimizowanej próbce | M |
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
| **E5.6** Limity IKE/IKZE | pozostały limit wpłat w roku per rachunek (limity jako konfiguracja roczna z `source_ref` i etykietą **[niezweryfikowane]**: 2026 — IKE 28 260 zł, IKZE 11 304 zł / 16 956 zł; [dowód](../research/04_rynek_pl_podatki_i_brokerzy.md)); raport wpłat IKZE do odliczenia poza zakresem (v2, [ADR biznesowy 0006](../business/adr/0006-zakres-modulu-podatkowego.md)) | ostrzeżenie przy przekroczeniu; pozostały limit w roku | S |
| **E5.7** Obligacje Catalyst (opcjonalnie) | kupony, odsetki narosłe przy kupnie/sprzedaży, wykup | test na jednej serii | M |

## Źródła

Odwołania prowadzą do dokumentów L4 z 2026-10-01/02 wymienionych w [pliku głównym](./02_roadmapa_funkcjonalna.md).
