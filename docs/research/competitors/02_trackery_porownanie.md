---
id: research-competitors-trackers
status: current
type: mixed
scope: research/competitors
last_reviewed: 2026-10-02
---

# Co robią inne trackery portfela i co warto od nich przejąć?

> **Dokument L4 (dowód).** Stan na 2026-10-01/02. Nienormatywny — rekomendacje stąd stają się obowiązujące dopiero przez ADR lub plan. Append-only: nie poprawiamy, dopisujemy nowe badanie i link do następcy.

**Metoda.** Strony oficjalne, centra pomocy i cenniki pobrane 2026-10-01; repozytoria open source
sklonowane płytko (`git clone --depth 1 --filter=blob:none`) i czytane bezpośrednio. HEAD-y:
Portfolio Performance 2026-09-30, Ghostfolio 2026-10-01 (`347cd06`), Wealthfolio 2026-10-01,
Maybe 2025-07-24 (zarchiwizowane), Sure 2026-10-01, Rotki 2026-09-30. Ścieżki plików poniżej
odnoszą się do tych repozytoriów, nie do FundTracker. Strony porównawcze producentów są
oznaczone jako stronnicze. Szczegółowa analiza myfund: [01_myfund.md](./01_myfund.md).
Słownik FundTracker: [CONTEXT.md](../../business/CONTEXT.md).

## 0. TL;DR

1. **Lider metodologii: Portfolio Performance (PP).** Dzienny TTWROR (napływy na początku dnia,
   odpływy na końcu) + IRR, wydzielone zyski walutowe, FIFO i średnia ruchoma, ~136 ekstraktorów
   PDF banków/brokerów — **żadnego polskiego** (brak XTB, mBank, Bossa, BOŚ). Słabości: UI,
   edycja tylko na desktopie.
2. **Wealthfolio ma najnowocześniejszy model danych:** `Decimal`, partie zakupu (loty podatkowe)
   utrwalone w bazie, splity jako współczynnik na partii (bez przepisywania historii), jawny
   klasyfikator przepływów zewnętrznych/wewnętrznych dla TWR, dokument projektowy o rozdzieleniu
   semantyki „holdings mode” i „transaction mode”.
3. **Ghostfolio jest popularny, ale słabszy metodycznie:** pieniądze jako `Float`, w HEAD działa
   tylko ROAI; klasy `twr/`, `mwr/`, `roi/` rzucają `Method not implemented`. Ma za to
   nieniszczący model splitów i podwójne serie „z efektem walutowym / bez”.
4. **Liderzy komercyjni:** Sharesight (raporty podatkowe, automatyczne zdarzenia korporacyjne,
   zmodyfikowana metoda Dietza z rozbiciem kapitał/dywidendy/waluta), Snowball (dywidendy, yield
   on cost), Parqet i getquin (DACH, autosync, TTWROR), Kubera (majątek netto). Żaden nie obsługuje
   PIT-38, reguły kursu NBP z dnia poprzedzającego, obligacji skarbowych EDO/COI ani IKE/IKZE.
5. **Polska:** myfund.pl pozostaje punktem odniesienia (~100 integracji importu, narzędzia PIT,
   nowy cennik od 2026-10-01). Alternatywy: Freenance, Biznesradar (benchmark WIG), arkusz
   Inwestomatu, Portfeo. **[wniosek]** Żadne narzędzie open source/self-hosted nie liczy dobrze
   polskiego podatku ani wyceny obligacji skarbowych.

## 1. Profile aplikacji

### 1.1 Open source

**Portfolio Performance** — Java/Eclipse RCP desktop + mobilny companion; EPL-1.0, darmowy; v0.87.0 (2026-08-16).

| Aspekt | Ustalenia | Źródło |
|---|---|---|
| Użytkownik | Samodzielni inwestorzy DACH; forum głównie po niemiecku | https://forum.portfolio-performance.info/ |
| Platformy | Win/macOS/Linux; iOS/Android czyta ten sam plik przez iCloud/Drive/OneDrive/WebDAV (AES-256); edycja transakcji na mobile „not currently possible”; opcjonalna subskrypcja „Premium” w aplikacji mobilnej | https://www.portfolio-performance.info/en/ ; App Store id6451118191 **[niezweryfikowane]** |
| Model transakcji | Podwójny zapis: papiery w **Portfolio** (depot), gotówka w **Account**; kupno = `BuySellEntry` łączący `PortfolioTransaction` z `AccountTransaction` (`CrossEntry`) | `model/BuySellEntry.java`, `CrossEntry.java` |
| Typy | `PortfolioTransaction.Type`: BUY, SELL, TRANSFER_IN/OUT, DELIVERY_INBOUND/OUTBOUND; `AccountTransaction.Type`: DEPOSIT, REMOVAL, INTEREST, INTEREST_CHARGE, DIVIDENDS, FEES, FEES_REFUND, TAXES, TAX_REFUND, BUY, SELL, TRANSFER_IN/OUT | `model/PortfolioTransaction.java:17-30`, `AccountTransaction.java:12-20` |
| Jednostki | Każda transakcja ma `Unit` typu GROSS_VALUE/TAX/FEE z opcjonalną kwotą w walucie obcej i kursem | `model/Transaction.java:29-31, 66` |
| Koszt | `CostMethod { FIFO, MOVING_AVERAGE }`; 0.87.0 dodało grupowanie per partia zakupu | `model/CostMethod.java`; releases |
| Splity | Kreator zapisuje `SecurityEvent(STOCK_SPLIT)` i **opcjonalnie przepisuje** ilości i ceny historyczne (niszczące); spin-off/fuzja ręcznie przez delivery **[wniosek]** | `ui/wizards/splits/StockSplitModel.java:96-137`; `model/SecurityEvent.java:14-17` |
| Wyniki | TTWROR na dziennych podokresach `(1+r) = (MVE + CFout) / (MVB + CFin)`, łańcuchowo; annualizacja na 365 dni (dokumentacja ostrzega o latach przestępnych); IRR metodą Newtona; kod zgodny z dokumentacją | https://help.portfolio-performance.info/en/concepts/performance/time-weighted/ ; `snapshot/ClientIndex.java:82-100`; `math/IRR.java`, `NewtonGoalSeek.java` |
| Rozbicie | Zyski kapitałowe (zrealizowane/niezrealizowane, „w tym zyski walutowe”), dochody, opłaty, podatki, różnice kursowe gotówki, transfery neutralne | https://help.portfolio-performance.info/en/reference/view/reports/performance/calculation/ |
| Ryzyko, dywidendy | `math/Risk.java` (zmienność, drawdown **[wniosek]**), `AllTimeHigh.java`, `Rebalancer.java`; `DividendCalculation.java`, feed DivvyDiary | repo `online/impl/` |
| Import | ~136 ekstraktorów w `datatransfer/pdf/`, IBKR przez `ibflex/IBFlexStatementExtractor.java`, CSV z zapisanymi konfiguracjami, łańcuch walidacji `datatransfer/actions/`; użytkownicy XTB konwertują CSV ręcznie | repo; https://forum.portfolio-performance.info/t/how-to-import-from-xtb/22308 **[niezweryfikowane]** |
| Dane | Yahoo (zwykłe i skorygowane zamknięcie), Alpha Vantage, CoinGecko, EODHD, Finnhub, TwelveData, giełdy krypto, ECB FX, Eurostat HICP, feedy HTML/JSON | `online/impl/*QuoteFeed.java`; `money/impl/ECBExchangeRateProvider.java` |
| Przechowywanie | Jeden plik XML/protobuf, opcjonalnie szyfrowany; kwoty `long` stałoprzecinkowe: pieniądze ×10², ilości ×10⁸, kursy ×10⁸ | `money/Values.java:227-306` |
| Słabości | Stroma krzywa nauki, przestarzały UI, brak edycji mobilnej | allinvestview.com (strona konkurenta) **[niezweryfikowane]** |

**Ghostfolio** — AGPLv3; Angular + NestJS + Prisma/PostgreSQL + Redis; v3.76.0 (2026-09-30).

| Aspekt | Ustalenia | Źródło |
|---|---|---|
| Użytkownik, cena | Self-hosterzy dbający o prywatność, FIRE. Self-hosted i Cloud Basic darmowe; Premium ~$40–48/rok **[niezweryfikowane]** | https://github.com/ghostfolio/ghostfolio ; https://gappsy.com/tools/ghostfolio/ |
| Klasy | `AssetClass` (6 wartości) i `AssetSubClass` (11, m.in. BOND, ETF, MUTUALFUND, PRECIOUS_METAL) | `prisma/schema.prisma:348-370` |
| Model | Płaska tabela `Order`: `type ∈ {BUY, DIVIDEND, FEE, INTEREST, LIABILITY, SELL}`, `quantity/unitPrice/fee Float`; brak nogi gotówkowej, wpłat/wypłat i partii; gotówka jako migawki `AccountBalance` | `prisma/schema.prisma:184-210, 58, 407-414` |
| Splity | Nieniszczące: tabela `AssetProfileSplit(date, numerator, denominator)` stosowana przy odczycie; `adjustActivityBySplits()` kumuluje dokładny ułamek (Big.js) | `.../asset-profile-split/asset-profile-split.helper.ts` |
| Wyniki | Tylko **ROAI** (zysk brutto / średnia dziennie zainwestowanych kwot) dla today/WTD/MTD/YTD/1Y/5Y/Max, każda liczba z bliźniakiem „WithCurrencyEffect”; kalkulatory TWR/MWR/ROI to zaślepki | `apps/api/src/app/portfolio/calculator/{twr,mwr,roi}/portfolio-calculator.ts`; `roai/portfolio-calculator.ts:229-285` |
| Ryzyko | „X-ray”: reguły koncentracji (konto, klasa, waluta, rynek, region), fundusz awaryjny, wskaźnik opłat | `apps/api/src/models/rules/**` |
| Import | CSV w przeglądarce z aliasami nagłówków (`qty/quantity/shares/units`, `commission/fee/ibcommission`), API JSON; brak PDF i synchronizacji brokerów | `apps/client/src/app/services/import-activities.service.ts:20-35` |
| Ceny | `MarketData(dataSource, symbol, date, marketPrice Float, state CLOSE/INTRADAY, isCarriedForward)`, unikalne `(dataSource, date, symbol)` | `prisma/schema.prisma:166-182` |
| UX | Zen mode (ukrywa kwoty), PWA, dostęp `MCP/PRIVATE/PUBLIC`, benchmarki, kalkulator FIRE | README; schema |
| Słabości | „roll your own import flow”; awaria Yahoo API (naprawa 2.73.0, 2024-04-17); `Float` dla pieniędzy **[wniosek]**; brak TWR/IRR | https://community.umbrel.com/t/ghostfolio-needs-to-be-updated-due-to-yahoo-api-issue/16667 ; deddit.petersanchez.com **[niezweryfikowane]** |

**Wealthfolio** — AGPL-3.0; Tauri + Rust + SQLite/Diesel, front React.

| Aspekt | Ustalenia | Źródło |
|---|---|---|
| Cena | Aplikacja darmowa; **Wealthfolio Connect**: Basic $29/rok (sync urządzeń), Essentials $79/rok (sync brokerów, 5 połączeń), Duo $129/rok, Plus $249/rok (wkrótce); sync brokerów tylko przez **SnapTrade** | https://wealthfolio.app/connect/ |
| Model | `ActivityType`: Buy, Sell, Dividend, Interest, Deposit, Withdrawal, TransferIn/Out, Fee, Tax, Split, Credit, Adjustment, Unknown; plus `subtype` (DRIP, STAKING_REWARD…), `source_type` (surowa etykieta brokera), `activity_type_override` (sync go nie rusza), `status ∈ {Posted, Pending, Draft, Void}` (Void = miękkie usunięcie); `rust_decimal::Decimal` | `crates/core/src/activities/activities_model.rs:137-160, 1548-1563` |
| Partie | Księga partii; redukcje FIFO zapisują zbycia i zamknięcia (fakty podatkowe); koszt w walucie bazowej po **kursie z dnia nabycia zapisanym na partii** | `.../holdings_calculator/lots.rs:1-60, 230-241` |
| Splity | Aktywność `SPLIT` mnoży skumulowany `split_ratio` otwartych partii sprzed daty; ilość, cena i koszt bez zmian; ułamki gotówkowe jako osobny SELL | `.../handlers/corporate_actions.rs`; `docs/activities/activity-types.md:125-137` |
| Wyniki | TWR (dzienna seria, zmienność, max drawdown) + IRR; przepływy zewnętrzne tylko DEPOSIT, WITHDRAWAL, zewnętrzne CREDIT/BONUS; osobna klasyfikacja dla zakresu portfela i konta; „holdings mode” nie pokazuje TWR/IRR | `.../performance/flow_classifier.rs:1-64`; `performance_service.rs:2807-2821, 2990-2991`; `docs/features/performance-semantics-design.md` (2026-06-17) |
| Dane rynkowe | Rejestr dostawców z priorytetem, circuit breaker, klasy retry; Yahoo, Alpha Vantage, Finnhub, Börse Frankfurt, MarketData.app, MetalPriceAPI, OpenFIGI, kalkulator US Treasury | `docs/architecture/market-data-quotes.md:407-460, 615-640` |
| Import | Szablony mapowania CSV (`CsvActivity/CsvHoldings/BrokerActivity`, zakres System/User), podgląd rozpoznania walorów, rekordy przebiegów importu, import wspierany AI | `activities_model.rs:76-92, 1126-1304`; `docs/test-data/` |
| Inne | SDK dodatków, asystent AI, MCP/CLI, cele alokacji i rebalans, szyfrowane kopie | `docs/addons/*`, `docs/features/allocations/*` |
| Słabości | Issue #1119: mieszane dashboardy dają sprzeczne zwroty $ vs %; własny dokument nazywa to „semantics gap” | `docs/features/performance-semantics-design.md:9-14` |

**Maybe Finance / Sure** (Rails, AGPLv3). Maybe zarchiwizowane 2025-07-27 po v0.6.0 (pivot na B2B);
aktywny fork społeczności Sure (~10,4 tys. gwiazdek). Model: polimorficzne `entries` (`amount
decimal(19,4)`, `locked_attributes jsonb`), `trades`, **materializowane** dzienne `holdings`,
`security_prices`, `exchange_rates` (`db/schema.rb`). `Holding::ForwardCalculator` odtwarza
transakcje; `Holding::ReverseCalculator` idzie wstecz od bieżącej migawki brokera, bo dostawcy
„supply current day holdings but not all the historical trades” (`reverse_calculator.rb:17-22`).
Brak modelu partii/splitów **[wniosek]** — to przede wszystkim aplikacja do budżetu i majątku.
Źródła: https://github.com/maybe-finance/maybe ; https://github.com/we-promise/sure ; https://piefed.jeena.net/post/210475

**Rotki** (AGPLv3, Python + Vue, lokalna szyfrowana baza; krypto/DeFi). Metody kosztu FIFO, LIFO,
HIFO, ACB jako kopiec z różnymi kluczami priorytetu (`rotkehlchen/accounting/cost_basis/base.py:106-395`);
okres zwolnienia z podatku (zyski z walorów trzymanych > N dni → `pnl_free`); reguły księgowe per
typ zdarzenia (`accounting/rules.py`). Plany Free/Basic/Advanced, ceny niepokazane.
Źródła: https://github.com/rotki/rotki ; https://rotki.com/products ; https://docs.rotki.com/usage-guides/accounting-rules.html **[niezweryfikowane]**

**Beancount / Fava.** `fava_investor`: alokacja, tax-loss harvester, cash drag, gains minimizer
(https://github.com/redstreet/fava_investor). `beangrow`: zwroty typu IRR z księgi;
`download_prices.py` dociąga dokładnie te ceny, których brak zgłosił przebieg obliczeń
(https://pypi.org/project/beangrow).

### 1.2 Komercyjne

| Aplikacja | Cena (2026-10-01) | Wyróżniki | Słabości / uwagi | Źródło |
|---|---|---|---|---|
| **Sharesight** (NZ) | Free (1 portfel, 10 pozycji); Starter $7/mies.; Standard $18; Premium $23,25 (rozliczenie roczne) | 700k+ walorów, 60+ rynków, import od 200+ brokerów, e-mail z notami; automatyczne dywidendy, DRP, splity; zwrot ważony kapitałem — wariant zmodyfikowanej metody Dietza, annualizacja dopiero gdy AYI ≥ 1, rozbicie kapitał/dywidendy/waluta; raporty CGT AU/CA z metodami FIFO, LIFO, Minimise Gain/CGT | Podwyżka 2024 z $279 na $348 (+24,7%); sprzedane pozycje liczą się do limitu; Capterra value-for-money 2,5/5 **[niezweryfikowane]** | https://www.sharesight.com/pricing/ ; https://help.sharesight.com/performance_calculation_method/ ; https://community.sharesight.com/t/sharesight-subscription-price-increase/880 |
| **Snowball Analytics** | Free (10 pozycji); $79,99 / $149,99 / $249,99 rocznie | 70+ giełd; kalendarz i prognoza dywidend, yield on cost, Sharpe, look-through; Yodlee + SnapTrade; tryby *Holdings* (pozycje + średni koszt) vs *Transactions* (IRR, zrealizowany P&L) | Błędy synchronizacji, prognozy ignorują reinwestycję, spin-offy ręcznie, split jako >1000% zwrotu (Trustpilot 4,5/433) **[niezweryfikowane]** | https://snowball-analytics.com/pricing ; https://help.snowball-analytics.com/holdings-vs-transactions/ |
| **Parqet** (DE) | Basic darmowy; Plus €95,92/rok (X-Ray, **dashboard podatkowy**); Investor €299,88/rok | Import przez przeciągnięcie PDF, 50+ brokerów, autosync (Trade Republic, Scalable, ING), integracje AI; TTWROR tym samym wzorem co PP | Brak polskich brokerów | https://www.parqet.com/en/pricing ; https://parqet.com/en/blog/true-time-weighted-rate-of-return |
| **getquin** (DE) | Free; Premium €89,99/rok; Wealth €149,99/rok | 500k+ użytkowników, funkcje społecznościowe; TTWROR od v2.40.0, IRR | Wg Freenance (strona konkurenta): brak polskiego podatku, ręczny import PL, brak obligacji skarbowych | https://www.getquin.com/pricing ; https://help.getquin.com/en/articles/8064745-ttwror-true-time-weigted-rate-of-return |
| **Kubera** | Essentials $250/rok; Black $2 500/rok | Majątek netto: Plaid, Yodlee, Salt Edge; IRR dla alternatyw; „Dead Man's Switch” | Częste ponowne autoryzacje połączeń **[niezweryfikowane]** | https://www.kubera.com/ |
| **Delta (eToro)** | Basic darmowy; PRO $60–80/rok **[niezweryfikowane]** | Sync z „over 10,000 brokers, exchanges, banks, and wallets” | Brak dokumentacji metodologii; mocny w krypto **[wniosek]** | https://www.etoro.com/investing/delta/ |
| **Simply Wall St** | Free / Premium / Unlimited (~$120–258/rok **[niezweryfikowane]**) | Import transakcji AI, analiza dywidend, IRR **[niezweryfikowane]** | — | https://simplywall.st/plans |
| **Stock Events** | Free (15 akcji); Pro $49,99/rok; Connect $0,99/tydz. | Kalendarz dywidend i wyników, „Why is it moving?”, API | — | https://stockevents.app/en/pricing |
| **Yahoo Finance** | Plus $249,99–349,99/rok **[niezweryfikowane]** | Brokerzy przez Yodlee; ręczne partie zakupu (DRIP) | Pozycji z synchronizacji nie da się edytować | https://help.yahoo.com/kb/SLN28346.html **[niezweryfikowane]** |

### 1.3 Polskie

| Narzędzie | Ustalenia | Źródło |
|---|---|---|
| **myfund.pl** | Cennik od 2026-10-01: Basic 39,92, Standard 79,92, Pro 127,92, Expert 199,92 PLN/rok; portfele 1/5/20/99; import transakcji od Pro, narzędzia podatkowe tylko w Expert; „100+ integracji”, kreator importu AI; flaga „Uwzględnij w PIT” na operacji i stawka 19% per konto (`kontoStopaPodatku`); aplikacje mobilne v4.00 (2026-07-28, forum myfund, wątek 6881). Szczegóły: [01_myfund.md](./01_myfund.md) | https://myfund.pl/index.php?mod=cennik |
| **Freenance** | PSD2, inwestycje, IKE/IKZE/PPK, krypto; ceny niespójne między stronami (19,99 PLN/mies. vs 49 PLN/mies.) **[niezweryfikowane]**; dominuje wyniki SEO stronami porównawczymi — traktować jako stronnicze | https://freenance.io/porownania/freenance-vs-myfund-vs-getquin-2026-najlepszy-tracker-portfela-inwestycyjnego-etf-polska/ |
| **Biznesradar** | Portfel wirtualny (3 portfele); BR Plus 285 PLN/rok: więcej portfeli, alerty, historia wartości vs **WIG** | https://www.biznesradar.pl/premium/brplus |
| **Inwestomat** | Darmowy arkusz Google (2024-10-07): GPW/NC i rynki zagraniczne, automatyczna historia dzienna, **XIRR**, **FIFO** | https://inwestomat.eu/wszystkie-twoje-inwestycje-w-1-miejscu/ |
| **Portfeo** | Konkurent myfund; 2026-05-05 opublikował porównanie „Portfeo czy myfund” | https://www.portfeo.pl/blog/wpis/portfeo-czy-myfund-porownanie-narzedzi-do-monitorowania-portfela-w-2026-roku |

Nie znaleziono: odrębnego produktu „Portfel Inwestora”; funkcji portfela stockwatch.pl;
oficjalnej dokumentacji analityki zwrotów XTB i Bossa.

**Polskie przepisy kształtujące model danych:**
- Przychody i koszty w walucie obcej przelicza się po **średnim kursie NBP z ostatniego dnia
  roboczego poprzedzającego** dzień przychodu (art. 11a ust. 1 ustawy o PIT) —
  https://lexlege.pl/ustawa-o-podatku-dochodowym-od-osob-fizycznych/art-11a/ **[niezweryfikowane]**.
- Gdy nie da się ustalić kosztu sprzedanych papierów, stosuje się **FIFO osobno dla każdego
  rachunku papierów wartościowych** (art. 24 ust. 10) —
  https://pro.rp.pl/podatki/art7443161-jak-ustalic-cene-nabycia-sprzedawanych-akcji **[niezweryfikowane]**.

## 2. Macierz porównawcza

Legenda: ✅ obsługiwane, ◐ częściowo, ❌ brak, ? niezweryfikowane. *Kod* — sprawdzone w kodzie;
*Dok* — strona oficjalna; *3P* — tylko źródło trzecie. Pominięto kolumny Delta, SWS,
Stock Events, Yahoo (dane w §1.2).

| Funkcja | PP | Ghostfolio | Wealthfolio | Maybe/Sure | Rotki | Sharesight | Snowball | Parqet | getquin | Kubera | myfund |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Self-hosted / dane lokalne | ✅ plik *Kod* | ✅ *Kod* | ✅ SQLite *Kod* | ✅ *Kod* | ✅ *Kod* | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Licencja / cena | darmowy | darmowy / Premium ? | darmowy + Connect $29–249/rok | darmowy | darmowy + Premium | $0–31/mies. | $0–250/rok | €0–300/rok | €0–150/rok | $250–2 500/rok | 40–200 PLN/rok |
| Akcje / ETF | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Obligacje (w tym EDO/COI) | ◐ ręcznie | ◐ ręcznie | ◐ (US Treasury) | ? | ❌ | ? | ? | ? | ❌ (3P) | ◐ | ✅ *Dok* |
| Krypto | ✅ feedy | ✅ | ✅ | ◐ | ✅ głęboko | ✅ | ? | ✅ | ✅ | ✅ | ✅ |
| Nieruchomości / walory własne | ◐ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ◐ | ? | ✅ | ✅ |
| Gotówka jako pełna księga | ✅ | ◐ migawki | ✅ | ✅ | n/d | ✅ | ? | ? | ? | ✅ | ✅ |
| Partie zakupu (loty podatkowe) | ✅ FIFO/średnia | ❌ | ✅ FIFO | ❌ | ✅ FIFO/LIFO/HIFO/ACB | ✅ FIFO/LIFO/min/max | ? | ? | ? | ❌ | ✅ FIFO **[wniosek]** z PIT |
| Splity | ◐ niszczący kreator | ✅ tabela | ✅ `split_ratio` partii | ❌ | n/d | ✅ automatycznie | ◐ błędy | ✅ (3P) | ? | ? | ✅ [H-OP] |
| Spin-off / fuzja / zmiana tickera | ◐ delivery | ❌ | ◐ Adjustment | ❌ | n/d | ✅ „adjustments” (zakres ?) | ◐ ręcznie (3P) | ? | ? | ? | ✅ konwersje [H-OP] |
| TWR | ✅ dzienny TTWROR | ❌ zaślepka | ✅ | ? | ❌ | ❌ (tylko MWR) | ✅ (3P) | ✅ TTWROR | ✅ TTWROR | ❌ | ✅ jednostki portfela *Dok* |
| MWR / IRR | ✅ IRR | ❌ zaślepka | ✅ | ? | ❌ | ✅ zmod. Dietz | ✅ IRR | ? | ✅ | ✅ IRR (alternatywy) | ✅ do wyboru *Dok* |
| Inna miara | bezwzględna, delta | ROAI + efekt walutowy | zmiana wartości, zysk vs koszt | — | PnL | CAGR / prosta | — | — | — | — | stopa zwrotu |
| Atrybucja walutowa | ✅ | ◐ z/bez FX | ◐ kurs nabycia na partii | ❌ | n/d | ✅ | ? | ? | ? | ◐ | ? |
| Benchmark | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Ryzyko | zmienność, drawdown, rebalans | reguły X-ray | zmienność, drawdown, rebalans | ❌ | ❌ | Drawdown Risk | Sharpe, dywersyfikacja | X-Ray | ocena AI | ❌ | skład |
| Kalendarz / prognoza dywidend | ◐ feed | ◐ | ◐ | ❌ | ❌ | ✅ Future Income | ✅ YoC, prognoza | ✅ 35k walorów | ✅ | ❌ | ✅ analiza |
| Raporty podatkowe | ❌ (tylko zyski) | ❌ | ◐ zrealizowany P&L | ❌ | ✅ PnL z okresem zwolnienia | ✅ CGT AU/CA | ❌ | ✅ dashboard DE | ❌ | ❌ | ✅ PIT (Expert) |
| Import CSV | ✅ konfigurowalny | ✅ aliasy | ✅ szablony + AI | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Parsowanie PDF | ✅ ~136 banków | ❌ | ❌ | ❌ | ❌ | ✅ noty e-mailem | ❌ | ✅ | ? | ❌ | ✅ kreator AI |
| API brokera / agregator | ◐ plik IBKR Flex | ❌ | ✅ SnapTrade (płatny) | ✅ Plaid (Maybe) | ✅ giełdy/łańcuchy | ✅ 200+ | ✅ Yodlee + SnapTrade | ✅ autosync | ✅ | ✅ Plaid/Yodlee/Salt Edge | ◐ XTB API |
| Polscy brokerzy | ❌ | ❌ | ❌ | ❌ | ❌ | ? | ? | ❌ | ❌ (3P) | ? | ✅ XTB, mBank, Bossa, BOŚ (3P) |
| Alerty cenowe | ◐ limity | ❌ | ? | ❌ | ❌ | ✅ | ? | ? | ? | ❌ | ✅ [H-AL] |
| Mobile | ◐ companion tylko do odczytu | PWA | ✅ iOS | ✅ (Sure) | ❌ | ✅ web | ✅ | ✅ | ✅ | ✅ | ✅ v4.00 |

myfund TWR/MWR: FAQ opisuje „jednostki portfela” jak w funduszach (= TWR), MWR do wyboru —
https://myfund.pl/index.php?raport=FAQ. Kody [H-OP] i [H-AL] (strony pomocy myfund) oraz import przez API XTB — [01_myfund.md](./01_myfund.md).

## 3. Najlepsze pomysły do przejęcia

| # | Pomysł | Kto robi to najlepiej | Dlaczego ważne dla FundTracker |
|---|---|---|---|
| 1 | **Dzienny TTWROR z jawną konwencją czasu przepływów** (napływ na początku dnia, odpływ na końcu) + IRR, annualizacja na 365 dni z udokumentowanym zastrzeżeniem o latach przestępnych | PP (`snapshot/ClientIndex.java:82-100`; strona pomocy) | Skopiować wzór i styl dokumentacji; Parqet i getquin używają tego samego wzoru |
| 2 | **Klasyfikator przepływów zewnętrznych/wewnętrznych** z zakresem (granica portfela vs konta) | Wealthfolio (`flow_classifier.rs`) | TWR na poziomie konta traktuje transfery między kontami jako zewnętrzne, TWR portfela — nie |
| 3 | **Rozdzielenie „holdings mode” i „transaction mode”**; odmowa TWR/IRR bez datowanych przepływów; etykieta metody i jakości danych przy każdej liczbie | Wealthfolio (dokument projektowy); Snowball | Usuwa najczęstszą skargę: niemożliwe procenty |
| 4 | **Transfery w naturze:** wartość rynkowa w dniu transferu jako przepływ do wyników, pierwotny koszt do podatku | Wealthfolio §„External Security Transfer”; PP `DELIVERY_INBOUND/OUTBOUND` | Przenoszenie Pozycji między polskimi brokerami (np. transfer IKE) |
| 5 | **Dekompozycja zwrotu:** zysk kapitałowy / dywidendy / zysk walutowy / opłaty / podatki | Sharesight; PP (widok kalkulacji) | Polacy z ETF-ami USA/UE w PLN muszą widzieć efekt FX |
| 6 | **Podwójna seria „z efektem walutowym / bez”** | Ghostfolio (`*WithCurrencyEffect`) | Tanie, gdy FX jest per data |
| 7 | **Nieniszczące splity** (zdarzenia stosowane przy odczycie lub współczynnik per partia) | Ghostfolio `adjustActivityBySplits`; Wealthfolio `split_ratio` | Unikać przepisywania historii jak w PP |
| 8 | **Wymienne strategie kosztu** (FIFO/LIFO/HIFO/średnia) za jednym interfejsem | Rotki `cost_basis/base.py` | W Polsce FIFO **per rachunek papierów** jest domyślne, gdy nie da się określić ceny nabycia zbywanych papierów (art. 24 ust. 10); wskazanie partii dopuszczalne, gdy broker ją identyfikuje (myfund od 05.2026 dla XTB, [01_myfund.md](./01_myfund.md)) — **[wniosek]**, zakres rozstrzyga biznesowy ADR; inne strategie do widoków „co jeśli” |
| 9 | **Optymalizacja podatkowa przydziału sprzedaży** (Minimise Gain / CGT) | Sharesight AU CGT | W PL FIFO jest domyślne; wskazanie partii tylko gdy da się określić cenę nabycia zbywanych papierów (art. 24 ust. 10) — optymalizacja do PIT-38 możliwa najwyżej w tym zakresie, poza nim tylko informacyjnie **[wniosek]** |
| 10 | **DSL ekstraktorów PDF per bank** testowany na zanonimizowanych fiksturach tekstowych | PP `datatransfer/pdf/*` (`DocumentType` → `Block` → `section().match(regex)`) | Wyciągi i potwierdzenia XTB, mBank, Bossa, BOŚ |
| 11 | **Łańcuch walidacji importu:** waluty → wartość brutto FX → duplikaty → zapis | PP `datatransfer/actions/*` | Idempotentne ponowne importy |
| 12 | **Zapisane szablony mapowania CSV + podgląd rozpoznania walorów** (`ExistingAsset / AutoResolvedNewAsset / NeedsFixing`) | Wealthfolio | UX dla niedopasowanych tickerów, np. GPW vs Yahoo `.WA` |
| 13 | **Nadpisania użytkownika, których sync nie ruszy** + status Draft/Pending/Posted/Void | Wealthfolio `activity_type_override`; Maybe `locked_attributes` | Poprawki nie giną przy ponownym imporcie |
| 14 | **Rejestr dostawców danych rynkowych** z priorytetem, preferowanym dostawcą per walor, circuit breakerem i stanem synchronizacji (Active/Closed/Dormant) | Wealthfolio `market-data-quotes.md` | **rekomendacja:** rozszerzyć istniejący port `MarketDataProvider` (`backend/app/core/market_data.py`) na wielu dostawców (Stooq, NBP, Yahoo) |
| 15 | **Dociąganie tylko brakujących cen potrzebnych do obliczeń** | beangrow `download_prices.py` | Mniej wywołań dostawcy |
| 16 | **Zwroty realne** (skorygowane o inflację) z serii CPI | PP `ConsumerPriceIndex`, feed Eurostat HICP | Realny zwrot vs CPI GUS; EDO/COI są indeksowane CPI **[wniosek]** |
| 17 | **Regułowy „X-ray” portfela** (koncentracja per konto, waluta, region; wskaźnik opłat; fundusz awaryjny) | Ghostfolio `models/rules/**` | Tanie, wyjaśnialne podpowiedzi o ryzyku |
| 18 | **Kalendarz dywidend + prognoza + yield on cost** | Snowball, Sharesight „Future Income”, Parqet | — |
| 19 | **Tryb Zen / prywatności** ukrywający kwoty | Ghostfolio | Trywialne; popularne przy udostępnianiu zrzutów ekranu |
| 20 | **Szyfrowany pojedynczy plik + companion mobilny tylko do odczytu** | PP (AES-256, odczyt przez dysk w chmurze) | Tania droga do mobile dla self-hosted **[wniosek]** |
| 21 | **Flaga „uwzględnij w podatku” na Operacji** i stawka per konto (IKE/IKZE zwolnione) | myfund (`Uwzględnij w PIT`, `kontoStopaPodatku`) | Bazowe oczekiwanie polskich użytkowników |
| 22 | **Benchmark względem indeksu lokalnego (WIG)** | Biznesradar BR Plus | Domyślny benchmark narzędzia „Polska najpierw” |

## 4. Typowe skargi użytkowników w kategorii

| # | Skarga | Przykłady | Źródło |
|---|---|---|---|
| 1 | Zawodna synchronizacja brokerów | Kubera (ponowne autoryzacje), Snowball (złe wartości, Vanguard > tydzień), Wealthfolio (#1119 dotyczy importowanych pozycji) | §1.1, §1.2 |
| 2 | Błędne zdarzenia korporacyjne | Split jako >1000% zwrotu, spin-offy ręcznie (Snowball); splity — najwyżej głosowana prośba w Ghostfolio (53 głosy) | §1.2; https://github.com/ghostfolio/ghostfolio/discussions |
| 3 | Sprzeczne lub mylące zwroty | $ i % z różnych metod (diagnoza Wealthfolio); ujemny TTWROR przy dodatnim zysku bezwzględnym wymaga wyjaśnienia (pomoc getquin) | §1.1, §1.2 |
| 4 | Ceny | Podwyżki i limity liczące sprzedane pozycje (Sharesight); paywalle na import i podatki (myfund Pro/Expert, dashboard podatkowy Parqet od Plus) | §1.2, §1.3 |
| 5 | Ciężar importu w self-hosted | „roll your own import flow” (Ghostfolio); CSV polskich brokerów wymagają ręcznej konwersji dla PP (przecinek dziesiętny, kolumna typu) | §1.1 |
| 6 | Kruchość dostawców danych | Blokada Yahoo API zepsuła Ghostfolio (naprawa 2.73.0); opóźnione notowania tajwańskie w myfund (forum, 2026-09-30) | §1.1; forum myfund na stronie cennika |
| 7 | Przestarzały UI i krzywa nauki | PP; myfund („Interfejs wygląda jak z 2010 roku” — strona Freenance) | §1.1, §1.3 |
| 8 | Brak lokalnego kontekstu podatkowego w aplikacjach zagranicznych | Brak PIT-38, podatku Belki, IKE/IKZE, obligacji skarbowych w getquin, Parqet, Sharesight (Freenance; dla Parqet i Sharesight **[wniosek]** z list krajów) | §1.2 |
| 9 | Niedokładne prognozy dywidend | Ignorują wzrost z DRIP (Snowball, Trustpilot) | §1.2 |

## 5. Lekcje techniczne z open source

### 5.1 Model operacji i partii zakupu

| Projekt | Typ pieniędzy | Główne encje | Partie | Lekcja |
|---|---|---|---|---|
| PP | `long` stałoprzecinkowy (kwota ×100, ilość ×10⁸, kurs ×10⁸); `BigDecimal` dla kursu FX | `Client` → `Portfolio` (papiery) i `Account` (gotówka); pary `BuySellEntry`/`CrossEntry`; `Transaction.Unit{GROSS_VALUE,TAX,FEE}` z kwotą i kursem FX | liczone w locie (FIFO lub średnia ruchoma) | Sparowana noga gotówkowa jednoznacznie wyznacza salda i przepływy zewnętrzne; typowane jednostki opłat i podatków umożliwiają dokładną dekompozycję |
| Ghostfolio | `Float` + Big.js w obliczeniach | jedna tabela `Order`; brak nogi gotówkowej; migawki `AccountBalance` | brak | Łatwy start, ale bez przepływów gotówki nie da się liczyć TWR. **Unikać.** |
| Wealthfolio | `rust_decimal::Decimal` | `Activity`: typ kanoniczny + subtype + source_type + override + status; księga partii ze zbyciami i zamknięciami | utrwalone, z kursem FX nabycia | Najlepszy wzorzec nowoczesnego schematu: surowa etykieta brokera, nadpisanie użytkownika, miękkie usuwanie, utrwalone fakty podatkowe |
| Maybe | `decimal(19,4)` | polimorficzne `entries` → `trades`/`transactions`/`valuations`; materializowane dzienne `holdings` | brak | Kalkulatory w przód i wstecz; wstecz ważne, gdy broker daje tylko bieżące Pozycje |
| Rotki | `FVal` (decimal) **[wniosek]** | historia zdarzeń → accountant → pot → kopiec kosztów | FIFO/LIFO/HIFO/ACB | Wzorzec strategii dla kosztu; okres zwolnienia |

**rekomendacja** (**[wniosek]**, zgodne z ADR-0010 o `Decimal`):
- `Decimal` wszędzie.
- Operacja jako nagłówek + typowane nogi (walor, gotówka, opłata, podatek), w stylu PP.
- Utrwalać partie zakupu jak Wealthfolio, z kursem FX nabycia i kursem NBP D-1 zapisanym na
  każdej partii i każdym zbyciu.
- FIFO **per rachunek papierów wartościowych** (art. 24 ust. 10).

### 5.2 Splity i zdarzenia korporacyjne

| Projekt | Mechanizm | Ocena |
|---|---|---|
| PP (`StockSplitModel.applyChanges`) | Zapisuje `STOCK_SPLIT`, potem *opcjonalnie* mnoży ilości wcześniejszych transakcji i dzieli historyczne kursy (HALF_EVEN); traci oryginalne liczby brokera | **Unikać** |
| Ghostfolio | Tabela splitów, unikalne `(symbolProfileId, date)`, stosowana przy odczycie; liczniki i mianowniki wszystkich późniejszych splitów mnożone przed dzieleniem („so that the cumulative split factor of consecutive splits stays exact”); błędne splity pomijane | **Dobre** |
| Wealthfolio | Aktywność SPLIT zmienia skumulowany `split_ratio` partii, koszt bez zmian; ułamki gotówkowe jako osobny SELL | **Najlepsze** — w księdze aktywności, działa z partiami |

Żaden projekt open source nie ma pierwszoklasowych typów spin-off / fuzja / zmiana tickera
(Wealthfolio: ogólne `Adjustment`; PP: pary delivery in/out). **Luka do wypełnienia [wniosek]:**
Operacja `ASSET_EXCHANGE` / `SPINOFF`, przenosząca określoną część kosztu z partii macierzystej
na partię potomną z zachowaniem daty nabycia dla FIFO.

### 5.3 FX — trzy kursy na zdarzenie

- **PP:** każdy `Transaction.Unit` przechowuje kwotę w walucie transakcji, kwotę w walucie obcej
  i kurs; walidacja toleruje ±0,003 zaokrąglenia kursu (`Transaction.java:102-127`); dostawcy:
  ECB, stały, oparty na walorze (`money/impl/*`). 0.86.1 poprawiło zyski kapitałowe, by używały
  „transaction-specific exchange rates”.
- **Wealthfolio:** serwis FX + konwerter; partie zachowują kurs nabycia (`stored_fx_rate_to`),
  z fallbackiem na kurs rynkowy z dnia nabycia; kontrola `fx_integrity.rs`.
- **Ghostfolio:** serwis kursów; podwójne serie z/bez efektu walutowego.
- **Dla Polski [wniosek] — trzy kursy na każde zdarzenie w walucie obcej:**
  1. faktyczny kurs brokera (z wyciągu),
  2. kurs rynkowy lub ECB/NBP z dnia wyceny (do wyników),
  3. średni kurs NBP z ostatniego dnia roboczego przed zdarzeniem (art. 11a, do PIT).

### 5.4 Przechowywanie historii cen

| Projekt | Schemat |
|---|---|
| PP | `SecurityPrice(LocalDate, long value)` w pamięci, w pliku klienta, + `LatestSecurityPrice` |
| Ghostfolio | `MarketData(dataSource, symbol, date, marketPrice Float, state CLOSE/INTRADAY, isCarriedForward)`, unikalne `(dataSource, date, symbol)`; `isCarriedForward` oznacza dni uzupełnione (syntetyczne) |
| Wealthfolio | `Quote(id = asset_date_source, OHLC, adjclose, currency, data_source)` + `QuoteSyncState` (pierwsza/ostatnia data aktywności, najwcześniejsze/najnowsze notowanie, ostatni błąd; Active/Closed/Dormant/FxRate); okna synchronizacji wg dat aktywności — pobiera tylko okresy posiadania |
| Maybe | Proste tabele `security_prices(date, price, currency)` i `exchange_rates(from, to, rate, date)` |

**Lekcje:** zapisywać źródło każdej ceny; oznaczać ceny przeniesione/syntetyczne; trzymać
zamknięcie **nieskorygowane** (skorygowane liczy splity i dywidendy podwójnie, gdy modelujemy te
zdarzenia); wiersz stanu synchronizacji per walor; FX jako kolejny wyceniany walor.

### 5.5 Pipeline importu

- **PP:** `PDFImportAssistant` → `*PDFExtractor` per bank z `DocumentType` + `Block` (regex
  startu) + `section(...).match(regex)` → `Extractor.Item` → łańcuch akcji (`CheckCurrenciesAction`,
  `CheckForexGrossValueAction`, `CheckSecurityRelatedValuesAction`, `CheckTransactionDateAction`,
  `DetectDuplicatesAction`, `InsertAction`); fikstury tekstowe per bank w
  `name.abuchen.portfolio.tests/.../datatransfer/pdf/<bank>/*.txt`.
- **Wealthfolio:** szablony mapowania (System/User/Broker) → rekord przebiegu importu
  (`import_run_model.rs`) → podgląd rozpoznania walorów → aktywności jako Draft, potem Posted;
  mapowanie wspierane AI testowane fiksturami CSV z przypadkami brzegowymi.
- **Ghostfolio:** parsowanie CSV po stronie klienta z listami aliasów (`ACCOUNT_KEYS`,
  `FEE_KEYS = ['commission','fee','ibcommission']`) → DTO JSON → walidacja na serwerze
  (`import-data.dto.ts`, `import.service.ts`).
- **Maybe:** `import_id` na każdym wpisie — śledzenie pochodzenia i wycofanie całego importu.

**Rekomendowany pipeline [wniosek]:**
1. Zapisać surowy plik i jego hash.
2. Parsować ekstraktorem właściwym dla brokera do znormalizowanego wiersza staging,
   zachowując surową etykietę.
3. Rozpoznać walor (ISIN, potem ticker + MIC).
4. Walidować (waluta, brutto = ilość × cena ± opłaty, data).
5. Wykrywać duplikaty kluczem naturalnym: referencja brokera albo data + ISIN + ilość + kwota.
6. Podgląd jako Draft.
7. Zatwierdzić w jednej transakcji bazodanowej pod `import_batch_id`, który da się wycofać.

## 6. Luki rynkowe, które polski tracker może zająć [wniosek]

| # | Luka | Szczegóły |
|---|---|---|
| 1 | Silnik PIT-38 / PIT-ZG | FIFO per rachunek papierów, średni kurs NBP z dnia roboczego przed zdarzeniem dla sprzedaży i zakupu, opłaty jako koszty, zagraniczny podatek u źródła vs 19% podatek Belki. Żadne narzędzie open source tego nie robi; myfund tylko w planie Expert |
| 2 | Detaliczne obligacje skarbowe (EDO, COI, TOS, ROR, DOR) | Wycena ze wzorów listu emisyjnego i ogłoszonej stopy każdego okresu (nie wyliczanej z CPI GUS — `../03_rynek_pl_dane_rynkowe.md`) zamiast ręcznego wpisu; wg źródeł trzecich większość aplikacji wymaga ręcznej aktualizacji co 6–12 miesięcy (Freenance **[niezweryfikowane]**) |
| 3 | IKE / IKZE / PPK | Rachunki zwolnione z podatku, limity wpłat, osobne pule FIFO |
| 4 | Ekstraktory polskich brokerów | XTB, mBank eMakler, Bossa, BOŚ, PKO BP DM, Santander BM — podejście DSL + fikstury z PP |
| 5 | Domyślny benchmark WIG/WIG20 | Waluta bazowa PLN, widok zwrotu realnego vs polski CPI |
| 6 | Przejrzysta strona metodologii | TTWROR + IRR + dekompozycja jak u PP i Sharesight. myfund dokumentuje swój TWR oparty na jednostkach portfela tylko skrótowo w FAQ; brak szczegółowej strony metodologii (https://myfund.pl/index.php?raport=FAQ) |

## Źródła

Dostęp 2026-10-01, o ile nie zaznaczono inaczej. „snippet” = tylko fragment z wyszukiwarki.

- Portfolio Performance: https://www.portfolio-performance.info/en/ ;
  https://help.portfolio-performance.info/en/concepts/performance/ ;
  https://help.portfolio-performance.info/en/concepts/performance/time-weighted/ ;
  https://help.portfolio-performance.info/en/reference/view/reports/performance/calculation/ ;
  https://github.com/portfolio-performance/portfolio (+ /releases) ; https://forum.portfolio-performance.info/ ;
  https://forum.portfolio-performance.info/t/how-to-import-from-xtb/22308 (snippet) ;
  https://www.allinvestview.com/articles/portfolio-performance-vs-allinvestview/ (snippet)
- Ghostfolio: https://github.com/ghostfolio/ghostfolio (+ /discussions) ; https://ghostfol.io/en/pricing ;
  https://gappsy.com/tools/ghostfolio/ ;
  https://community.umbrel.com/t/ghostfolio-needs-to-be-updated-due-to-yahoo-api-issue/16667 ;
  https://deddit.petersanchez.com/g/selfhosted@lemmy.world/p/f58f69zV2Fz65D6381-Self-hosted-portfolio-tracking (snippet)
- Wealthfolio: https://github.com/afadil/wealthfolio ; https://wealthfolio.app/ ; https://wealthfolio.app/connect/
- Maybe / Sure: https://github.com/maybe-finance/maybe ; https://github.com/we-promise/sure ; https://piefed.jeena.net/post/210475
- Rotki: https://github.com/rotki/rotki ; https://rotki.com/products ; https://docs.rotki.com/usage-guides/accounting-rules.html (snippet)
- Beancount / Fava: https://github.com/redstreet/fava_investor ; https://pypi.org/project/beangrow
- Sharesight: https://www.sharesight.com/pricing/ ; https://www.sharesight.com/features/ ;
  https://help.sharesight.com/performance_calculation_method/ ;
  https://www.sharesight.com/blog/how-sharesight-calculates-your-investment-performance/ ;
  https://help.sharesight.com/capital_gains/ (snippet) ;
  https://community.sharesight.com/t/sharesight-subscription-price-increase/880 (snippet) ;
  https://www.capterra.com/p/207519/Sharesight/ (snippet)
- Snowball: https://snowball-analytics.com/ ; https://snowball-analytics.com/pricing ;
  https://help.snowball-analytics.com/holdings-vs-transactions/ ;
  https://nz.trustpilot.com/review/snowball-analytics.com?page=7 (snippet)
- Parqet: https://www.parqet.com/ ; https://www.parqet.com/en/pricing ;
  https://parqet.com/en/blog/true-time-weighted-rate-of-return ; https://etf.capital/parqet-app/
- getquin: https://www.getquin.com/ ; https://www.getquin.com/pricing ;
  https://help.getquin.com/en/articles/8064745-ttwror-true-time-weigted-rate-of-return ;
  https://alphagrowth.io/getquin/company (snippet)
- Kubera: https://www.kubera.com/ ; https://thecollegeinvestor.com/36895/kubera-review/ (snippet)
- Delta: https://www.etoro.com/investing/delta/ ; App Store id1288676542 (snippet)
- Simply Wall St: https://simplywall.st/plans
- Stock Events: https://stockevents.app/en ; https://stockevents.app/en/pricing
- Yahoo: https://help.yahoo.com/kb/SLN28346.html (snippet) ; https://help.yahoo.com/kb/SLN2312.html (snippet)
- myfund: https://myfund.pl/ ; https://myfund.pl/index.php?mod=cennik ; https://myfund.pl/index.php?raport=FAQ (dostęp 2026-10-02)
- Freenance (strony producenta): https://freenance.io/porownania/freenance-vs-myfund-vs-getquin-2026-najlepszy-tracker-portfela-inwestycyjnego-etf-polska/ ;
  https://freenance.io/rankingi/najlepsze-aplikacje-do-sledzenia-portfela-inwestycyjnego-2026 ;
  https://freenance.io/narzedzia-finansowe/narzedzia-do-sledzenia-portfela/
- Biznesradar: https://www.biznesradar.pl/premium/brplus
- Inwestomat: https://inwestomat.eu/wszystkie-twoje-inwestycje-w-1-miejscu/
- Portfeo: https://www.portfeo.pl/blog/wpis/portfeo-czy-myfund-porownanie-narzedzi-do-monitorowania-portfela-w-2026-roku (nie pobrano treści)
- PIT art. 11a: https://lexlege.pl/ustawa-o-podatku-dochodowym-od-osob-fizycznych/art-11a/ (snippet)
- PIT art. 24 ust. 10: https://pro.rp.pl/podatki/art7443161-jak-ustalic-cene-nabycia-sprzedawanych-akcji (snippet)

## Luki i niepewności

| Element | Problem |
|---|---|
| `ghostfol.io/en/pricing` | Cena renderowana po stronie klienta; brak kwoty |
| `help.parqet.com` | Błąd DNS (ENOTFOUND) |
| `www.kubera.com/pricing` | 404; cena ze strony głównej |
| `delta.app` | 403 |
| `docs.rotki.com/usage-guides/accounting.html` | 404; użyto `accounting-rules` ze snippetu |
| `help.sharesight.com/performance-calculation-methodology/` | 404; użyto `/performance_calculation_method/` |
| Porównania `myfinancetools.io`, `inwestycje.pl` | 429 / CAPTCHA |
| `lexlege.pb.pl` | Pobranie zablokowane; tekst prawny tylko ze snippetów |
| Metodologia myfund | FAQ opisuje TWR oparty na jednostkach portfela tylko skrótowo, MWR do wyboru; brak szczegółowej strony metodologii |
| Portfeo | Treść porównania nie była analizowana; odnotowano tylko jego istnienie |
| XTB / Bossa — analityka wbudowana | Brak oficjalnej dokumentacji |
| „Portfel Inwestora”, stockwatch.pl | Nie znaleziono odrębnego produktu / funkcji portfela |
| Ceny Ghostfolio Premium, Delta PRO, SWS, Yahoo Plus, Freenance | Tylko źródła trzecie lub niespójne strony — **[niezweryfikowane]** |
