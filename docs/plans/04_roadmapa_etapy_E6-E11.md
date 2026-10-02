---
id: plan-feature-roadmap-e6-e11
status: draft
type: mixed
scope: plans/product-roadmap
last_reviewed: 2026-10-02
---

# Jakie kroki składają się na etapy E6–E11 roadmapy?

Część [roadmapy funkcjonalnej](./02_roadmapa_funkcjonalna.md) (L3, szkic). Poprzednia część: [etapy E0–E5](./03_roadmapa_etapy_E0-E5.md). Format kroku i skala rozmiarów jak tam.

---

## E6 — Podatki (PIT-38)

**Cel etapu:** roczne rozliczenie zysków kapitałowych gotowe do przepisania do PIT-38, z wyjaśnieniem każdej liczby — funkcja, którą myfund trzyma w najdroższym planie. Nowy moduł `taxes` (D10), czyta Portfele, partie i operacje **wyłącznie przez serwisy** `portfolios` ([ADR-0006](../technical/adr/0006-cross-module-wylacznie-przez-serwisy.md)). Reguły i cytaty przepisów: [podatki PL](../research/04_rynek_pl_podatki_i_brokerzy.md). Wymaga ADR: **D2, D5** oraz biznesowego ADR „Zakres i zastrzeżenia modułu podatkowego”.

> Moduł liczy **szkic do weryfikacji**, nie doradza podatkowo. Każdy raport nosi tę adnotację i listę przyjętych założeń.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E6.1** Silnik podatkowy | `taxes/domain/`: dla każdej sprzedaży dopasowanie partii FIFO w obrębie rachunku (D1/D2), przychód i koszt w PLN po **kursie NBP z ostatniego dnia roboczego przed dniem przychodu/kosztu** (art. 11a — data kursu wg [dowodu](../research/04_rynek_pl_podatki_i_brokerzy.md); kwestia daty zawarcia vs rozliczenia rozstrzygnięta w ADR), prowizje jako koszty; rachunki IKE/IKZE/PPK wyłączone | testy złote na przykładach z broszury MF do PIT-38 i na ręcznie policzonych scenariuszach (zakup USD, sprzedaż USD, różne kursy) | L |
| **E6.2** Raport roczny | struktura zgodna z sekcjami PIT-38 (papiery wartościowe, kryptowaluty osobno, dywidendy zagraniczne); szczegóły: każda sprzedaż z partiami, kursami i datami; rozbicie na kraje dla PIT/ZG (jeśli dotyczy wg dowodu) | suma zgadza się z sumą transakcji; eksport CSV/PDF z adnotacją „szkic” | M |
| **E6.3** Dywidendy i odsetki zagraniczne | podatek pobrany u źródła (operacja `tax` z E2.3), dopłata do 19% w PL z limitem odliczenia wg umowy o unikaniu podwójnego opodatkowania; kursy NBP D−1 | test: dywidenda USD z 15% WHT → dopłata 4% (przykład liczbowy w dokumentacji) | M |
| **E6.4** Kryptowaluty | osobna pula przychodów/kosztów (zbycie na waluty, koszty nabycia, nadwyżka kosztów przechodzi na kolejny rok — wg [dowodu](../research/04_rynek_pl_podatki_i_brokerzy.md)) | test na scenariuszu wieloletnim | M |
| **E6.5** Straty z lat ubiegłych | rejestr strat z deklaracji (rok, kwota, wykorzystanie); reguła odliczania wg art. 9 ust. 3 (limit roczny / jednorazowy — dokładne brzmienie w dowodzie); podpowiedź maksymalnego odliczenia | test na przykładzie z dowodu | S |
| **E6.6** Szacunek podatku w wynikach | opcja „pokaż wynik po podatku” w kokpicie i pozycjach: podatek od zysku niezrealizowanego (szacunek, bez IKE/IKZE) i należny za rok bieżący | przełącznik w UI; oznaczenie „szacunek” | S |
| **E6.7** Optymalizator końca roku | lista otwartych partii ze stratą, które można sprzedać przed ostatnią sesją roku, by skompensować zysk; ostatni dzień transakcji z uwzględnieniem rozliczenia | lista zgodna z partiami; brak automatycznych transakcji | M |

---

## E7 — Ryzyko i analityka zaawansowana

**Cel etapu:** statystyki, które myfund daje dopiero w planie Expert, policzone z szeregu TWR (nie z wartości, która zawiera wpłaty). Formuły: [metodyka](../research/05_metodyka_metryk.md). numpy w `services/` (D11).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E7.1** Statystyki portfela | zmienność (dzienna ×√252 i miesięczna ×√12 — z etykietą), maksymalne obsunięcie z czasem trwania i powrotu, Sharpe, Sortino, beta i alfa vs benchmark, korelacja, VaR historyczny 95% + Expected Shortfall; tylko dni sesyjne | testy złote z metodyki; minimalna liczba obserwacji (szare pola poniżej progu) | M |
| **E7.2** Stopa wolna od ryzyka | szereg z E1.6 (POLSTR/WIRON, fallback stopa referencyjna NBP; €STR/SOFR dla EUR/USD — jeśli dostępne); wybór w ustawieniach | wybór widoczny przy Sharpe | S |
| **E7.3** Wykresy ryzyka | obsunięcie w czasie, czas pod wodą (TUW) z histogramem, krocząca stopa zwrotu i zmienność (okno 1/3 lata), mapa korelacji walorów (tygodniowe stopy dla par z różnych giełd) | wykresy na snapshotach | M |
| **E7.4** Efekt walutowy | rozbicie zysku: cena / waluta / dywidendy / koszty / podatki (konwencja „najpierw cena, potem waluta na nowej cenie” — opisana w UI); seria „z efektem walutowym” i „bez” | test z przykładu: +10% cena, −5% waluta → +4,5% | M |
| **E7.5** Benchmark „te same przepływy” | symulowany portfel benchmarku kupowany za każdą wpłatę i sprzedawany przy wypłacie; XIRR portfela vs XIRR benchmarku | test: brak przepływów → wynik = TWR benchmarku | M |
| **E7.6** Kondycja portfela | reguły progowe w stylu myfund Snowball / Ghostfolio X-ray: koncentracja pozycji, TOP3, efektywna liczba pozycji (1/HHI), dominująca klasa, sektor, waluta, pozycje ze stratą > próg, śladowe pozycje, nieaktualne wyceny; wynik 0–100 z wyjaśnieniem każdej reguły; progi konfigurowalne | każda reguła z testem; wynik deterministyczny | M |

---

## E8 — Zdarzenia korporacyjne i dywidendy

**Cel etapu:** splity, prawa poboru i dywidendy nie psują historii ani stóp zwrotu (najczęstsza skarga w kategorii — [dowód](../research/competitors/02_trackery_porownanie.md)). Ceny w bazie są nieskorygowane (E1.1), zdarzenia są operacjami.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E8.1** Split i scalenie | operacja `split` (stosunek nowe:stare) zmieniająca ilość i cenę jednostkową otwartych partii bez zmiany kosztu i daty nabycia (wzorzec Wealthfolio, bez przepisywania historii); ułamki rozliczone jako sprzedaż | wykres ilości i TWR ciągłe przez split; test | M |
| **E8.2** Zmiana tickera / połączenie | operacja wymiany walorów (stary → nowy, przelicznik, ekwiwalent gotówkowy za ułamki) z przeniesieniem partii | test: zysk całkowity bez zmian | M |
| **E8.3** Spin-off | wydzielenie części kosztu partii do nowego waloru (współczynnik), data nabycia zachowana | test | M |
| **E8.4** Prawa poboru i PDA | PP jako walor z ceną teoretyczną do pierwszego notowania, zapis i przydział (PP + cena emisyjna → akcje) | test scenariusza emisji | M |
| **E8.5** Źródło zdarzeń | pobieranie dywidend i splitów od dostawców (Yahoo/Stooq; GPW/ESPI wg [dowodu](../research/03_rynek_pl_dane_i_obligacje.md)); **propozycje operacji** do akceptacji przez użytkownika (nie automatyczny zapis), z ilością na dzień ustalenia prawa | propozycja dywidendy pojawia się po dniu ustalenia prawa; akceptacja tworzy operację | L |
| **E8.6** Kalendarz i prognoza dywidend | 12 miesięcy: ogłoszone (pewne), z historii (ostatnia DPS × częstotliwość), TTM; różne style dla źródeł; dochód miesięczny łącznie z odsetkami obligacji (E5.2) | prognoza oznaczona jako szacunek; test | M |

---

## E9 — Planowanie

**Cel etapu:** przejść od „co mam” do „co zrobić”. Nowy moduł `planning` (D10). Algorytmy: [metodyka](../research/05_metodyka_metryk.md) (rebalancing, projekcje).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E9.1** Portfel wzorcowy | alokacja docelowa wg Klas walorów, tagów lub Walorów (dla Portfela lub Grupy), pasma tolerancji bezwzględne i względne; odchylenia w UI | test pasm (5 pp / 25%) | M |
| **E9.2** Rebalancing | tryby: tylko nową gotówką (algorytm „wyrównywania od najbardziej niedoważonych”), pełny (kup i sprzedaj), do krawędzi pasma; zaokrąglenie do całych jednostek; przy sprzedaży szacunek podatku FIFO (E6) | testy złote z metodyki (2 000 i 1 000 zł) | M |
| **E9.3** Cel inwestycyjny | wartość docelowa, data, wpłaty miesięczne, oczekiwana stopa (nominalna lub realna); ścieżka do celu vs rzeczywistość; wymagana wpłata / liczba miesięcy | test FV = 613 795 dla przykładu z metodyki | S |
| **E9.4** FIRE / runway | koszty życia, bezpieczna stopa wypłaty, inflacja; kapitał z Grupy portfeli | test | S |
| **E9.5** Projekcje Monte Carlo | rozkład lognormalny, ≥ 10 000 ścieżek, percentyle P10/P50/P90, prawdopodobieństwo osiągnięcia celu, stały seed; opis ograniczeń w UI | wynik powtarzalny dla seeda | M |
| **E9.6** Operacje cykliczne | szablon (kwota, cykl, reguła dnia wolnego) generujący propozycje operacji (np. comiesięczna wpłata na IKE) | propozycja w dniu cyklu; test | S |

---

## E10 — Powiadomienia i automatyzacja

**Cel etapu:** aplikacja przychodzi do użytkownika, zamiast czekać na wizytę. Nowy moduł `notifications` (D10); kanały self-hosted (e-mail SMTP, ntfy, Telegram — wybór w ADR).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E10.1** Alerty cenowe | warunki: cena powyżej/poniżej, zmiana % od średniej ceny zakupu, od maksimum 52 tyg., zmiana dzienna, obsunięcie Portfela od szczytu; jednorazowe/wielokrotne; sprawdzanie przez zadanie CLI po odświeżeniu cen | alert wyzwolony raz na przekroczenie; test | M |
| **E10.2** Raport okresowy | e-mail tygodniowy/miesięczny: wartość, zysk, TWR vs benchmark, dywidendy, nadchodzące wykupy obligacji i dywidendy | podgląd raportu w UI | M |
| **E10.3** Import z e-maila | skrzynka IMAP: potwierdzenia transakcji z biura maklerskiego → parser (E4) → szkic do akceptacji | test na zanonimizowanych wiadomościach | L |
| **E10.4** Token API | osobisty token dostępu (zakres: odczyt / zapis), dokumentacja OpenAPI; skrypty użytkownika | token działa, można go unieważnić; test | S |
| **E10.5** Asystent AI na własnych danych (opcjonalnie) | serwer MCP lub endpoint czatu z dostępem tylko do odczytu do własnych danych (odpowiedzi typu „ile dywidend dostałem w 2025?”); myfund ma asystenta bez dostępu do danych portfela ([dowód](../research/competitors/01_myfund.md)) | wymaga ADR (prywatność, dostawca modelu) | M |

---

## E11 — Jakość i eksploatacja (ciągłe)

Kroki realizowane równolegle z etapami, gdy pojawi się potrzeba.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E11.1** PWA i widok mobilny | responsywny kokpit, Portfel, dodawanie operacji; instalacja jako PWA | Lighthouse PWA; ręczny test na telefonie | M |
| **E11.2** Tryb prywatności | ukrycie kwot (tylko %) jednym przełącznikiem (wzorzec Ghostfolio) | przełącznik działa na wszystkich widokach | S |
| **E11.3** Kopie zapasowe | automatyczny eksport (E4.5) i zrzut bazy wg harmonogramu; instrukcja odtworzenia | odtworzenie sprawdzone na czystej instancji | S |
| **E11.4** Audyt zmian | historia zmian operacji (kto/kiedy/co) — dziś świadomie odłożona ([ADR-0011](../technical/adr/0011-audyt-odlozony.md)); powrót do decyzji po E4 (import zwiększa liczbę zmian masowych) | nowy ADR | M |
| **E11.5** Nazewnictwo frontendu | `Pocket` → `Portfolio` w typach i ścieżkach frontu ([CONTEXT](../business/CONTEXT.md), sekcja „Sprzeczności”) | brak „Pocket” w `frontend/src` | S |
| **E11.6** Testy frontendu | runner testów (np. Vitest) dla logiki formatowania i hooków; testy e2e krytycznych ścieżek | CI frontendu uruchamia testy | M |
| **E11.7** Wydajność | pomiar endpointów wykresów na danych 10-letnich; indeksy; cache odpowiedzi per `last_snapshot_date` | budżet: wykres < 300 ms, kokpit < 500 ms | S |

## Źródła

Wszystkie odwołania w tym pliku prowadzą do dokumentów L4 z 2026-10-01/02 wymienionych w [pliku głównym](./02_roadmapa_funkcjonalna.md).
