---
id: plan-feature-roadmap-e0-e5
status: draft
type: mixed
scope: plans/product-roadmap
last_reviewed: 2026-10-03
---

# Jakie kroki składają się na etapy E0–E4 roadmapy?

Część [roadmapy funkcjonalnej](./02_roadmapa_funkcjonalna.md) (L3, szkic). Decyzje D1–D16, kolejność realizacji i definicja ukończenia — w pliku głównym. Kontynuacja: [etapy E8 i E11](./04_roadmapa_etapy_E6-E11.md). Nazwa pliku zachowuje dawny zakres E0–E5; treść obejmuje E0–E4.

**Format kroku:** zakres (moduł) → kryteria akceptacji → rozmiar. Rozmiar: **S** ≤ 1 dzień, **M** 2–4 dni, **L** 1–2 tygodnie, **XL** > 2 tygodnie (szacunek **[wniosek]**, jedna osoba). Defekty F1–F6 i luki G1–G25: [stan FundTrackera](../research/06_stan_found-tracker_vs_cel.md).

---

## E0 — Naprawy i ustawienia

**Cel:** usunąć defekty, które zafałszowują wartości portfeli wielowalutowych, zanim cokolwiek zbudujemy na nich. Bez nowych ADR-ów.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E0.1** Wycena walut obcych (F1, F4) | Kursy w `assets` są względem waluty systemowej (USD). Serwis `portfolios` wyznacza **kurs krzyżowy** waluta waloru → waluta Portfela i przekazuje do `PortfolioValuator.value()` gotową mapę `{(currency_id_z, currency_id_do): Decimal}` = rate[z]/rate[do] (`FxMapBuilder`; `Currency.exchange_rate` = „USD za 1 jednostkę”, `assets/services/market_data.py:109`) — `domain/` nie dostaje portu ani I/O (ADR-0005). Dialog zakupu podpowiada kurs krzyżowy przez `GET /portfolios/fx-rate?from_currency=&to_currency=` ([kontrakt 2.4](../technical/backend/09_kontrakt_api_docelowy.md)); `GET /assets/currencies/rate` zwraca tylko kursy bezpośrednie/odwrotne. Brak kursu (przed E1.1 heurystyka: `exchange_rate==1` ∧ `code≠USD`; nowa waluta ma domyślnie 1) → wycena pozycji oznaczona `RATE_MISSING` zamiast cichego kursu 1; pola `PositionResponse` dotyczące wartości stają się nullable. `HoldingLike` się zmienia — przepisać `test_valuation.py:54-84`, `test_portfolio_service.py:94`, `test_position_service.py:61`, `test_wiring.py:44`; seed nie ma walut obcych w Portfelach (`seed_data.py:187-211`) → własne fixtures | Portfel PLN z walorami USD i EUR przy kursach testowych (USD=1, EUR=1,08, PLN=0,25 względem USD): wartość = ilość × cena × kurs krzyżowy (±0,000001); Portfel USD bez zmian; brak kursu → `RATE_MISSING`; testy parytetu zielone | M |
| **E0.2** Wektory metryk spójne z księgą (F2) | `services/metrics.py`: uwzględnić `fx_rate` operacji i dywidendy; dywidenda zmienia tylko `free_cash` i `profit`, nie `transaction_cost_vector`; „wszystkie portfele” miesza waluty → wymagać Portfela. Testy do przepisania: `test_metrics_service.py:67-80,143-155`. Wartość walorów obcych przeliczana bieżącym kursem krzyżowym do czasu historii kursów (E1.1) — zapisane jako ograniczenie | ostatni punkt `free_cash_vector` = `cash_balance` z księgi (±0,01 — wektor jest `float`, porównanie z tolerancją); ostatni punkt wartości = wycena z E0.1 (±0,01 przy tej samej cenie wejściowej — wektor bierze `provider.current_price`, wycena `asset.current_price`; test wstrzykuje tę samą cenę) | M |
| **E0.3** Operacje wsteczne walidowane historią | `OperationService.create`: **każda** nowa operacja przechodzi przez `rebuild()` historii (jak edycja/usunięcie) — bez osobnej ścieżki „stan bieżący” (decyzja właściciela); testy `test_operation_service.py:111-390` do przepisania | wsteczna sprzedaż łamiąca historię → 400 z `code`; poprawna → zapisana, pozycje przeliczone | S |
| **E0.4** Waluta nowego waloru (F5) | tworzenie waloru „po tickerze” bierze walutę z notowania dostawcy; wywołanie dostawcy **poza** `transaction()`, błąd dostawcy → 502 `MARKET_DATA_UNAVAILABLE` (nie cicha waluta Portfela); `None` od dostawcy → 404 `ASSET_NOT_FOUND_ON_PROVIDER`; rdzeń `create_from_provider` bez commitu (ADR-0008) wołany po pobraniu notowania, PRZED `transaction()`; testy `test_operation_service.py:224-268`, `integration/test_portfolio_flow.py:127` | zakup AAPL w Portfelu PLN tworzy walor w USD; błąd dostawcy → 502 i brak zapisu | S |
| **E0.5** Tickery GPW | symbole Yahoo z sufiksem `.WA` (sprawdzone w [dowodzie](../research/03_rynek_pl_dane_rynkowe.md)); poprawka danych seed (tickery `.WA`); **seed generuje stany Portfeli i Pozycji replayem operacji**, nie zahardkodowane (dziś gotówka i dywidendy w `seed_data.py` nie zgadzają się z replayem; dane powstają od zera przez seed, [ADR-0019](../technical/adr/0019-migracje-danych-i-kolumny-dat.md)); wpłata Portfela Crypto 8 000 → 16 000 (zakupy BTC/ETH wymagają ≥ 15 632); `with session.begin()` w `seed/seed.py` zgodnie z `transaction()`; bez nowych pól w modelu — symbol dostawcy to po prostu `ticker` z sufiksem do czasu `assets_listing` w E1.2 | odświeżenie ceny CDR/PKO/PKN zwraca cenę w PLN; replay seedu przez `PortfolioLedger` nie rzuca | S |
| **E0.6** Zamknięcie rejestracji | `ALLOW_REGISTRATION` (domyślnie true w `ENVIRONMENT=test`/dev — testy używają `/auth/register`, `conftest.py:46`; false w produkcji); pierwsze konto z CLI; flaga `is_owner` (migracja addytywna) i CLI `set-owner` — podstawa 403 na zapisach `assets` (D14, biz. ADR 0007) | `POST /auth/register` → 403 `REGISTRATION_DISABLED` przy wyłączonej rejestracji; `GET /auth/me` zwraca `is_owner` | S |
| **E0.7** Frontend — braki dla istniejącego API | **naprawa startu** (`frontend/index.html:11` → `main.tsx`, ikona bez backslasha), `lib/format.ts` zastępujący 8 wystąpień `Intl.NumberFormat` (w tym 4 walutowe), runner testów (Vitest — nowa zależność, wymaga zgody właściciela) z pierwszymi testami formatowania, edycja operacji, dialog dywidendy, prowizja przy wpłacie/wypłacie, jedna nawigacja zamiast sidebar + zakładki, usunięcie martwych linków (`/settings` do E0.9, `/analytics`); szczegóły: [IA i konwencje UI](../technical/frontend/ia-i-konwencje-ui.md) | `npm run build` i `npm test` zielone; scenariusz ręczny: dodaj → edytuj → usuń dywidendę | M |
| **E0.8** Zmiana waluty bazowej Portfela (F6, G17) | blokada zmiany, gdy Portfel ma operacje; blokada = 409 `PORTFOLIO_CURRENCY_LOCKED` | test blokady | S |
| **E0.9** Ustawienia użytkownika (G21, F3) | `core_data`: waluta wyświetlania (domyślnie PLN), próg nieaktualnej ceny (dni); strefa czasowa bez ustawienia — stała Europe/Warsaw ([ADR-0019](../technical/adr/0019-migracje-danych-i-kolumny-dat.md)); strona `/settings`; „Całkowita wartość” w kokpicie = gotówka + wycena pozycji (F3), sumy tylko z istniejących endpointów Portfeli (`/dashboard` to E3.4) | sumy kokpitu (gotówka + pozycje) przeliczone na walutę wyświetlania; test API ustawień | M |
| **E0.10** Nazewnictwo frontendu | `Pocket` → `Portfolio` w typach, plikach, hookach i trasach (130 wystąpień w 19 plikach); trasy po `id` (`/portfolios/:id`) z przekierowaniem ze starych `/pockets/:slug`; **przed** nowymi ekranami, żeby nie mnożyć długu; backend: pole `portfolio_id` w odpowiedziach pozycji i operacji (dziś frontend wysyła `portfolio_name`: `positionService.ts:7`, `operationService.ts:7`, `schemas/positions.py:43`) | brak słowa „Pocket” w `frontend/src`, z wyjątkiem pliku przekierowań i aliasu `pocket_value_vector` (usuwany w E3.5); stare linki przekierowują | S |

---

## E1 — Dane rynkowe i historia

**Cel:** każda wycena i wykres liczą się z danych w bazie, bez sieci w ścieżce żądania. Dowody: [dane rynkowe PL](../research/03_rynek_pl_dane_rynkowe.md), [lekcje techniczne](../research/competitors/02_trackery_porownanie.md). Wymaga ADR: **D5, D7, D8, D14**.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E1.1** Historia cen i kursów | `assets`: `assets_price` (walor, data, zamknięcie, waluta, źródło, `is_synthetic`), `assets_fx_rate` (z, do, data, kurs, źródło, numer tabeli NBP); unikalność (walor/para, data, źródło); ceny **nieskorygowane**; dziennik zmian `assets_price_change` ([ADR-0016](../technical/adr/0016-snapshoty-dzienne-i-przebudowa.md)); zapis `current_price` w tej samej transakcji co zapis ceny ([ADR-0015](../technical/adr/0015-historia-cen-i-kursow.md)) | `find_close(asset, date)` z forward-fill i flagą syntetyczną; testy repozytorium | M |
| **E1.2** Rejestr dostawców | port `MarketDataProvider` z `capabilities`; adaptery: **NBP** (kursy tabela A/B; zapytania w paczkach ≤ 93 dni; cofanie po 404 do dnia roboczego), **Yahoo** (GPW `.WA`, zagranica; jawnie ceny nieskorygowane — `auto_adjust=False` lub równoważne; domyślne zachowanie `yfinance` do weryfikacji **[niezweryfikowane]**); priorytet per walor + mapowanie symboli `assets_listing` (walor, dostawca, symbol); retry, timeout, wyłącznik awaryjny; kolejne adaptery za portem | testy kontraktowe na nagranych odpowiedziach; walor po splicie (np. akcja z udokumentowanym splitem) ma ceny nieskorygowane; kurs NBP USD 2026-09-25 = 3,8404 (tabela 187/A/NBP/2026) w teście nagranym | L |
| **E1.3** Identyfikacja walorów | pola `isin`, giełda/MIC, `country`, `sector`, `asset_type` (akcja, ETF); lokalny katalog GPW/NC (źródło listy do ustalenia przy E1.2 — dowód nie wskazuje darmowego, oficjalnego źródła; kandydat: lista z dostawcy); relacja `asset_type` ↔ `assets_assetclass` rozstrzygnięta w [schemacie](../technical/backend/07_schemat_danych_docelowy.md); wyszukiwanie po nazwie i tickerze | wyszukanie „orlen” zwraca PKN | M |
| **E1.4** Odświeżanie w tle | `assets/entrypoints.py` (`session_scope`, ADR-0002) + `app/cli.py`: `refresh-prices`, `refresh-fx` jako wspólna implementacja; **nadrabianie zaległości po wybudzeniu**: pierwsze żądanie dnia rejestruje w `BackgroundTasks` odświeżenie cen/kursów i przebudowę zaległych dni (idempotentne); ochrona przed równoległym przebiegiem: blokada w transakcji w bazie (tabela `job_run` z ostatnim przebiegiem), nie `flock` ani blokady sesyjne; **dociąganie historii orkiestruje `portfolios/entrypoints.py`** (zna okresy posiadania, prosi `assets` przez serwis o zakres dat) — bez zależności `assets → portfolios`; usunięcie synchronicznego odświeżania z `GET /portfolios/positions`; wyjątek: „żądania HTTP nie wołają dostawcy synchronicznie; wyjątek: jawne ręczne odświeżenie ceny przez przycisk — `POST /assets/refresh-prices` → 202, `BackgroundTasks` wołające tylko `assets.entrypoints.refresh_prices`” ([ADR-0017](../technical/adr/0017-zadania-w-tle-i-cli.md)) | zadania idempotentne dla zamknięć dziennych (drugie uruchomienie = 0 nowych wierszy; cena bieżąca jest nadpisywana); dwa równoległe przebiegi → jeden wykonuje, drugi pomija; żądania HTTP nie wołają dostawcy synchronicznie (test z dostawcą rzucającym wyjątek; `refresh-prices` zwraca 202) | M |
| **E1.5** Ceny ręczne | awaryjne dodawanie/edycja ceny historycznej, gdy dostawca nie ma notowania | ręczna cena ma pierwszeństwo i jest oznaczona `source=manual` | S |
| **E1.6** Benchmark | benchmark = walor (WIG, WIG20, mWIG40TR, S&P 500, ETF na MSCI World/ACWI); jeden indeks wybierany do porównania; benchmarki jako dane globalne | benchmark ma historię cen z E1.1; wybór indeksu zapisany w ustawieniach | M |
| **E1.7** Jakość danych | w odpowiedziach: `price_date`, `stale` (> próg z E0.9), `source`; panel „Dane” (ostatnie odświeżenie, błędy dostawców) | walor bez ceny od 7 dni oznaczony w UI | S |
| **E1.8** Lista obserwowanych | walory nieposiadane z ceną i zmianą (G25) | dodanie/usunięcie z listy; cena z E1.1 | S |
| **E1.9** Kalendarz sesji | dni sesyjne GPW i giełd zagranicznych (z historii cen + lista świąt); flaga `is_trading_day` | wykresy i porównanie z benchmarkiem pomijają dni bez sesji | S |

---

## E2 — Księga v2

**Cel:** model księgowy unoszący realia wielowalutowego rachunku maklerskiego. Każdy krok to addytywna migracja (`autogenerate`) z zielonymi testami. Wymaga ADR: **D1, D2, D3, D4, D9, D13, D15, D16**.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E2.0** Kolumny dat i przebudowa | `portfolios/entrypoints.py` + CLI `rebuild` per Portfel (pozycje, salda, partie, snapshoty z operacji); **nowe kolumny `operation_day`** (data w Europe/Warsaw), `sequence` i `currency_id` obok `operation_date`; klucz księgi `(operation_day, sequence, id)`; pozycje aktualizowane W MIEJSCU (zachowuje `opened_at`); `portfolios_portfolio.dirty_from` wprowadzone tu (nie w E2.5) (D13; [ADR-0019](../technical/adr/0019-migracje-danych-i-kolumny-dat.md)); dane od zera — bez backfillu; schematy: [schemat danych](../technical/backend/07_schemat_danych_docelowy.md) | po naprawie seed (E0.5) `rebuild` daje stan identyczny z operacjami; drugie uruchomienie bez zmian (idempotencja) | M |
| **E2.1** Portfel jako rachunek | `account_type` i `broker` jako etykiety informacyjne (bez wpływu na reguły), domyślna prowizja (% + minimum) per Klasa waloru do czasu `asset_type` (E1.3); **Grupa portfeli** (agregacja bez własnych operacji) | filtr i grupowanie w API | M |
| **E2.2** Gotówka wielowalutowa | `portfolios_cash_balance` (Portfel, Waluta); operacja przewalutowania jako typ Operacji w tym kroku (noga wychodząca i przychodząca, kurs, prowizja w walucie wychodzącej); dywidenda trafia na saldo w walucie wypłaty; `LedgerState.cash_balance` zostaje jako właściwość salda waluty bazowej, `valuation.py:82` sumuje salda wszystkich walut przeliczone kursami; `fx_rate` default 1 (`schemas/operations.py:52`) niewymuszalny — serwis wymaga kursu przy walucie ≠ bazowej (`RATE_MISSING`); skala salda `Numeric(18,3)` | zakup akcji USD z salda USD; brak salda → błąd z `code` | L |
| **E2.2b** Tryb automatycznych wpłat | opcjonalne `auto_funding` per Portfel (domyślnie wyłączone): niedobór przy zakupie = wirtualna wpłata; dywidendy i odsetki **nie** są wirtualną wypłatą — zostają na saldzie (odpowiednik portfela „bezgotówkowego” myfund, [dowód](../research/competitors/01_myfund.md)) | TWR i XIRR traktują automatyczne wpłaty jako przepływy zewnętrzne; test | S |
| **E2.3** Nowe typy Operacji | `interest`, `fee`, `split` (E8.1), przewalutowanie (E2.2); pola z D9 (`status`, `external_ref`, `import_batch_id`); każda operacja ma regułę w `PortfolioLedger` i test | edycja operacji wstecz przelicza historię (E0.3); testy reguł dla każdego typu | L |
| **E2.4** Partie zakupu | `domain/lots.py` (wewnętrzny moduł ledgera, DOM-10; wpis w `DOMAIN_LAYERS` testu czystości): `LotBook` — otwarcie przy zakupie, zużycie FIFO w obrębie Portfela (D2), prowizja sprzedaży proporcjonalnie; split zachowuje koszt łączny; tabele pochodne `portfolios_lot` (`open_operation_id`), `portfolios_lot_consumption`; `HoldingLike` (`protocols.py:73-85`) i `valuation.py:53` czytają Partie, repozytorium je ładuje (`repositories/portfolios.py:16-30`); **zysk zrealizowany** (waluta waloru i waluta Portfela) | **wycena otwartych pozycji czyta koszt z partii** (dziś `ilość × średnia`, `valuation.py:53`); test złoty z [metodyki](../research/05_metodyka_metryk.md): zrealizowany 336,50 (FIFO) vs 286,50 (średnia), zysk całkowity 384,00 w obu; test własności „zysk całkowity niezależny od metody” | L |
| **E2.5** Snapshoty dzienne | `portfolios_daily` (wartość, gotówka, przepływy zewn. we/wy, dochody, opłaty, `r_day`, `twr_index` jako `Decimal`, skumulowane przepływy, `data_quality`) i `portfolios_position_daily`; przebudowa per Portfel (synchroniczna do progu, powyżej w tle); unieważnienie od **daty najstarszej zmiany**: operacja (natychmiast), cena/kurs (entrypoint `portfolios` czyta dziennik `assets_price_change` przez kursor `portfolios_market_cursor`, kolumna `dirty_from`, [ADR-0016](../technical/adr/0016-snapshoty-dzienne-i-przebudowa.md)) | wektory wykresów czytane ze snapshotów; wykres 5 lat < 300 ms na zbiorze 10 lat × 200 operacji × 30 walorów | L |
| **E2.6** Słownik i dokumentacja | `CONTEXT.md` (D3); `05_portfolios_module.md` | `kb_validate --strict` bez nowych błędów | S |
| **E2.7** Historia operacji | paginacja, filtry (typ, walor, data, status), komentarze; godzina operacji (D13) w UI | lista 10 000 operacji < 300 ms na stronę | M |

Do E2 (kolejność realizacji M0) dołączony jest **E8.1 split ręczny** — split w historii właściciela zepsułby wyceny przed E8.

---

## E3 — Analityka podstawowa

**Cel:** „ile zarobiłem”, „jak wypadam na tle indeksu”, „z czego składa się portfel” — poprawnie i z jawną metodą. Wymaga ADR: **D6, D11**. Formuły i testy złote: [metodyka](../research/05_metodyka_metryk.md).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E3.1** Stopy zwrotu | `GET /portfolios/{id}/performance?period=1M\|3M\|6M\|YTD\|1Y\|3Y\|5Y\|MAX\|custom` (też Grupa i „wszystkie”): zysk kwotowy, TWR (`twr_index`), XIRR (Newton + bisekcja, kody inline `IRR_UNDEFINED`/`IRR_AMBIGUOUS`, HTTP 200), annualizacja tylko ≥ 365 dni, `effective_start`, `method`, `data_quality`; zakres Portfel / Grupa | TWR 3-dniowy = 3,0000%; XIRR przykład Excela = 0,373362535 (±1e-8); Modified Dietz 1,20 (fallback); okres < 365 dni → `annualized = null` | L |
| **E3.2** Zamknięte pozycje | raport z partii: przychód, koszt, prowizje, dywidendy, zysk, %, skuteczność, profit factor | suma zysków = suma zrealizowanego z E2.4 | M |
| **E3.3** Struktura | alokacja wg Walorów, Klas, sektora, waluty, kraju; w czasie | suma udziałów = 100% (gotówka osobno) | M |
| **E3.4** Kokpit | wszystkie Portfele w walucie wyświetlania (E0.9): wartość, zmiana dzienna, zysk, TWR YTD/1Y, wygrani/przegrani dnia, mini-wykres | sumy = Σ wycen Portfeli przeliczonych kursem dnia | M |
| **E3.5** Wykresy | wartość vs wpłaty netto, zysk w czasie, TWR vs benchmark (E1.6), stopy w okresach (mapa ciepła miesiąc × rok), porównanie Portfeli **na TWR**, mapa cieplna Portfela, porównanie do 4 walorów | brak wywołań dostawcy (test) | L |
| **E3.6** Dywidendy i odsetki | dochód pasywny miesięcznie/rocznie, stopa TTM, **stopa od kosztu** z partii, top płatnicy | 5,00% i 7,33% dla przykładu z metodyki | M |
| **E3.7** „Jak liczymy” | strona metodologii + tooltipy (metoda, okres, kursy, annualizacja); eksport tabel do CSV | każda metryka w UI ma tooltip | S |
| **E3.8** Widok waloru | wykres ceny z naniesionymi Operacjami i dywidendami, partie, zysk, stopa zwrotu pozycji, dywidendy | przejście kokpit → Portfel → walor → operacja | M |

---

## E4 — Import

**Cel:** wieloletnia historia z XTB w minuty, z bezpiecznym wycofaniem. **Realizacja później** (po M0; najpierw tylko XTB). Import w module `portfolios` (D10); zakres wg [ADR-0018](../technical/adr/0018-architektura-importu.md): port parsera, paczki importu z cofnięciem, adapter XTB jako pierwszy. Formaty brokerów: [eksporty](../research/04_rynek_pl_brokerzy.md); wzorce PP i Wealthfolio: [lekcje](../research/competitors/02_trackery_porownanie.md).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E4.1** Potok importu | plik (hash, surowa treść) → parser (port `core/import_parser.py`, adapter w `infrastructure/`) → wiersze pośrednie → rozpoznanie waloru (ISIN, ticker + giełda) → walidacja (waluta, brutto = ilość × cena ± prowizja, data) → duplikaty (`external_ref` albo data+ISIN+ilość+kwota) → zapis jako paczka importu (`import_batch`) przez rdzeń `record_many` bez commitu (ADR-0008) z jednym `rebuild` → cofnięcie paczki (D15) | ponowny import tego samego pliku = 0 nowych operacji; cofnięcie paczki przywraca stan sprzed importu; import 2 000 wierszy < 10 s | L |
| **E4.2** Adapter XTB | parser eksportu XTB (historia konta, operacje gotówkowe: wpłaty, wypłaty, dywidendy); **blokada: wymaga zanonimizowanego eksportu od właściciela** (oficjalnej listy kolumn nie znaleziono — [dowód](../research/04_rynek_pl_brokerzy.md)); kolejne źródła później | test na zanonimizowanym pliku XTB, w tym dywidendy i przewalutowania | M |
