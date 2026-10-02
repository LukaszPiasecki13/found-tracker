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

**Cel:** roczne rozliczenie zysków kapitałowych gotowe do przepisania do PIT-38, z wyjaśnieniem każdej liczby. Cel terminowy: **szkic PIT-38 za 2026 w lutym 2027** (zeznanie do 30 kwietnia, art. 45). Nowy moduł `taxes` (D10) czyta Portfele, operacje i **rekordy zużycia partii z `portfolios`** wyłącznie przez serwisy ([ADR-0006](../technical/adr/0006-cross-module-wylacznie-przez-serwisy.md)) — nie ma drugiego silnika FIFO. Reguły i cytaty przepisów: [podatki PL](../research/04_rynek_pl_podatki_i_brokerzy.md). Wymaga ADR: **D2, D5, D12** oraz biznesowego „Zakres i zastrzeżenia modułu podatkowego”.

> Moduł liczy **szkic do weryfikacji**, nie doradza podatkowo. Każdy raport nosi tę adnotację i listę założeń.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E6.1** Pule podatkowe | `taxes/domain/`: trzy pule — (a) papiery wartościowe i fundusze (art. 30b ust. 1), (b) waluty wirtualne (art. 30b ust. 1a, koszty roczne z przeniesieniem nadwyżki, art. 22 ust. 14–16), (c) dywidendy i odsetki zryczałtowane (art. 30a, per zdarzenie); przychód i koszt w PLN po kursie podatkowym z Operacji (D5, D12); opłaty bez partii (prowadzenie rachunku, przelew papierów) jako koszt roczny puli (a); flagi partii: ulga IPO (art. 21 ust. 1 pkt 105a), darowizna, spadek; rachunki IKE/IKZE/PPK/PPE/OIPE wyłączone | testy złote: ręcznie policzone scenariusze (zakup i sprzedaż w USD przy różnych kursach D−1; sprzedaż 30.12 z rozrachunkiem 2.01 → przychód następnego roku); scenariusz z broszury MF | L |
| **E6.2** Raport roczny | układ części PIT-38 (C/D, E/F, G); rozbicie „krajowe z PIT-8C” vs „zagraniczne / bez PIT-8C”; **PIT/ZG** dla zagranicznych zysków kapitałowych per kraj (dywidendy nie trafiają do PIT/ZG — [dowód](../research/04_rynek_pl_podatki_i_brokerzy.md)); szczegóły sprzedaży z partiami, kursami i numerami tabel NBP; podstawa i podatek zaokrąglane do pełnych złotych (poz. 31, 35), podatek z art. 30a — do groszy (reguła jako parametr, sprzeczność źródeł opisana w dowodzie) | część krajowa = PIT-8C właściciela (±1 zł); eksport CSV/PDF z adnotacją „szkic” | L |
| **E6.3** Dywidendy i odsetki zagraniczne | WHT z Operacji `tax` (E2.3), dopłata do 19% z limitem odliczenia (art. 30a ust. 9); kurs NBP D−1 dnia wypłaty; odsetki obligacji skarbowych (E5.1) | dywidenda 100 USD, WHT 15%, kurs D−1 4,00 → podatek PL 76,00 zł, odliczenie 60,00 zł, dopłata 16,00 zł | M |
| **E6.4** Kryptowaluty | pula (b): przychód ze zbycia na waluty/towary/usługi (wymiana krypto–krypto nie jest zbyciem, art. 17 ust. 1f), koszty roku + nadwyżka z lat poprzednich; czy FIFO z art. 30b ust. 7a dotyczy krypto — wg [dowodu](../research/04_rynek_pl_podatki_i_brokerzy.md) | scenariusz 3-letni z nadwyżką kosztów przechodzącą na kolejny rok | M |
| **E6.5** Straty z lat ubiegłych | rejestr strat (rok, pula, kwota, wykorzystanie); reguła art. 9 ust. 3: przez 5 kolejnych lat do 50% straty rocznie **albo** jednorazowo do 5 000 000 zł, reszta w pozostałych latach z limitem 50%; straty krypto wyłączone (ust. 3a pkt 2) | test: strata 10 000 zł w 2024 → maks. odliczenie 5 000 zł rocznie albo jednorazowo całość w wybranym roku | S |
| **E6.6** Szacunek podatku w wynikach | przełącznik „wynik po podatku”: szacunek od zysku niezrealizowanego (bez IKE/IKZE) i należny za rok bieżący | oznaczenie „szacunek”; wartość = 19% × dodatni zysk z otwartych partii | S |
| **E6.7** Optymalizator końca roku | otwarte partie ze stratą, których sprzedaż przed ostatnią sesją roku (z uwzględnieniem T+2) kompensuje zysk; brak automatycznych zleceń | lista zgodna z partiami; ostatni dzień transakcji = ostatnia sesja − 2 dni robocze | M |

---

## E7 — Ryzyko i analityka zaawansowana

**Cel:** statystyki, które myfund daje w planie Expert, liczone z szeregu TWR. Formuły: [metodyka](../research/05_metodyka_metryk.md). numpy w `services/`, float zgodnie z D11.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E7.1** Statystyki portfela | zmienność (dzienna ×√252 i miesięczna ×√12, z etykietą), MDD z czasem trwania i powrotu, Sharpe, Sortino, beta/alfa vs benchmark, korelacja, VaR historyczny 95% + Expected Shortfall; tylko dni sesyjne (E1.9) | testy złote z metodyki: σ roczna 65,69%, MDD 4,90%, Sharpe 2,48, Sortino 4,76, β 1,30, ρ 0,995 (dane przykładowe); < 60 obserwacji → pole puste z wyjaśnieniem | M |
| **E7.2** Stopa wolna od ryzyka | szereg z E1.6 (stopa referencyjna NBP; POLSTR/WIRON jeśli dostępne bez licencji — WIBOR/WIRON są płatne wg [dowodu](../research/03_rynek_pl_dane_i_obligacje.md)); wybór w ustawieniach (E0.9) | wybrana stopa widoczna przy Sharpe | S |
| **E7.3** Wykresy ryzyka | obsunięcie w czasie, czas pod wodą (TUW) z histogramem, krocząca stopa zwrotu i zmienność (okno 1/3 lata), mapa korelacji walorów (tygodniowe stopy dla par z różnych giełd) | wykresy ze snapshotów | M |
| **E7.4** Efekt walutowy | rozbicie zysku: cena / waluta / dywidendy / koszty / podatki (konwencja „cena, potem waluta na nowej cenie” — opisana w UI); seria z efektem walutowym i bez | +10% cena, −5% waluta → +4,5% (+40 / −22 zł na 1 szt.) | M |
| **E7.5** Benchmark „te same przepływy” | symulowany portfel benchmarku kupowany za każdą wpłatę, sprzedawany przy wypłacie; XIRR portfela vs XIRR benchmarku | brak przepływów → wynik = TWR benchmarku | M |
| **E7.6** Kondycja portfela | reguły progowe (wzorzec myfund Snowball / Ghostfolio X-ray): pozycja ≥ 25/35%, TOP3 ≥ 60/75%, 1/HHI < 5, klasa ≥ 65/80%, sektor ≥ 30/45%, waluta ≥ 60/80%, kapitał w stratnych ≥ 40/65%, pozycja ≤ −20% przy udziale ≥ 5%, wyceny > 7 dni; wynik 100 − 20×„ważne” − 10×„uwaga” − 3×„obserwacja” z wyjaśnieniem; progi konfigurowalne | każda reguła z testem granicznym; wynik deterministyczny | M |

---

## E8 — Zdarzenia korporacyjne i dywidendy

**Cel:** zdarzenia korporacyjne nie psują historii ani stóp zwrotu (częsta skarga w kategorii — [dowód](../research/competitors/02_trackery_porownanie.md)). Ceny w bazie nieskorygowane (E1.1), zdarzenia są Operacjami.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E8.1** Split i scalenie (ręcznie; realizowany w M0) | Operacja `split` (nowe:stare) zmienia ilość i cenę jednostkową otwartych partii bez zmiany kosztu i daty nabycia (wzorzec Wealthfolio); ułamki rozliczone jako sprzedaż | split 1:10 → ilość ×10, koszt bez zmian, TWR ciągły w dniu splitu | M |
| **E8.2** Zmiana tickera / połączenie | wymiana walorów (stary → nowy, przelicznik, gotówka za ułamki) z przeniesieniem partii | zysk całkowity bez zmian | M |
| **E8.3** Spin-off | wydzielenie części kosztu partii do nowego waloru (współczynnik), data nabycia zachowana; skutki podatkowe do potwierdzenia (dowód ich nie przeanalizował) | suma kosztów partii przed = po | M |
| **E8.4** Prawa poboru i PDA | PP jako walor z ceną teoretyczną do pierwszego notowania; zapis i przydział (PP + cena emisyjna → akcje) | scenariusz emisji z przydziałem częściowym | M |
| **E8.5** Źródło zdarzeń | dywidendy i splity od dostawców (Yahoo; kalendarium GPW jest płatne — [dowód](../research/03_rynek_pl_dane_i_obligacje.md)); **propozycje Operacji** do akceptacji, z ilością na dzień ustalenia prawa (T+2); orkiestracja w `portfolios/entrypoints.py` | propozycja dywidendy po dniu ustalenia prawa; akceptacja tworzy Operację | L |
| **E8.6** Kalendarz i prognoza dywidend | 12 miesięcy: ogłoszone, z historii (ostatnia DPS × częstotliwość), TTM; dochód miesięczny łącznie z odsetkami obligacji (E5.2) | prognoza oznaczona jako szacunek; źródło każdej pozycji widoczne | M |

---

## E9 — Planowanie

**Cel:** od „co mam” do „co zrobić”. Moduł `planning` (D10). Algorytmy: [metodyka](../research/05_metodyka_metryk.md).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E9.1** Portfel wzorcowy | alokacja docelowa wg Klas, tagów lub Walorów (Portfel lub Grupa); pasma bezwzględne i względne | odchylenie 6 pp przy paśmie 5 pp → alert; 5% udziału przy celu 4% i paśmie względnym 25% → w normie | M |
| **E9.2** Rebalancing | tylko nową gotówką (wyrównywanie od najbardziej niedoważonych), pełny, do krawędzi pasma; całe jednostki; szacunek podatku FIFO (E6) przy sprzedaży | testy z metodyki: 60/30/10 i 7 000/2 000/1 000 → przy 2 000 zł: 200/1 600/200; przy 1 000 zł: B 1 000 | M |
| **E9.3** Cel inwestycyjny | wartość docelowa, data, wpłaty, stopa nominalna/realna; ścieżka vs rzeczywistość; wymagana wpłata / liczba miesięcy | PV 50 000, 1 000/mies., 6%, 240 mies. → FV 613 795; wpłata dla 600 000 = 969,58 | S |
| **E9.4** FIRE / runway | koszty życia, stopa wypłaty, inflacja; kapitał z Grupy portfeli | przykład liczbowy w teście | S |
| **E9.5** Monte Carlo | rozkład lognormalny, ≥ 10 000 ścieżek, P10/P50/P90, prawdopodobieństwo celu, stały seed; ograniczenia opisane w UI | wynik powtarzalny dla seeda | M |
| **E9.6** Operacje cykliczne | szablon (kwota, cykl, reguła dnia wolnego) generujący propozycje (np. comiesięczna wpłata na IKE) | propozycja w dniu cyklu; dzień wolny → wg reguły | S |

---

## E10 — Powiadomienia i automatyzacja

**Cel:** aplikacja przychodzi do użytkownika. Moduł `notifications` (D10); kanały self-hosted (SMTP, ntfy, Telegram — wybór w ADR).

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E10.1** Alerty cenowe | cena powyżej/poniżej, zmiana % od średniej ceny zakupu, od maksimum 52 tyg., zmiana dzienna, obsunięcie Portfela od szczytu; jednorazowe/wielokrotne; sprawdzanie po odświeżeniu cen (CLI) | alert wyzwolony raz na przekroczenie; ponownie dopiero po powrocie poniżej progu | M |
| **E10.2** Raport okresowy | e-mail tygodniowy/miesięczny: wartość, zysk, TWR vs benchmark, dywidendy, nadchodzące wykupy (E5.2) i dywidendy (E8.6) | podgląd w UI = treść e-maila | M |
| **E10.3** Import z e-maila | IMAP: potwierdzenia transakcji → parser (E4) → szkic do akceptacji | test na zanonimizowanych wiadomościach | L |
| **E10.4** Token API | osobisty token (odczyt / zapis), unieważnianie; dokumentacja OpenAPI | żądanie z unieważnionym tokenem → 401 | S |
| **E10.5** Asystent AI (opcjonalnie) | serwer MCP lub czat tylko do odczytu własnych danych („ile dywidend w 2025?”); myfund ma asystenta bez dostępu do danych portfela ([dowód](../research/competitors/01_myfund.md)) | wymaga ADR (prywatność, dostawca modelu) | M |

---

## E11 — Jakość i eksploatacja (ciągłe)

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E11.1** PWA i widok mobilny | responsywny kokpit, Portfel, walor, dodawanie operacji; instalacja jako PWA | Lighthouse PWA bez błędów; ręczny test na telefonie | M |
| **E11.2** Tryb prywatności | ukrycie kwot jednym przełącznikiem (wzorzec Ghostfolio) | brak kwot na wszystkich widokach | S |
| **E11.3** Kopie zapasowe | automatyczny eksport (E4.5) i zrzut bazy; instrukcja odtworzenia | odtworzenie sprawdzone na czystej instancji | S |
| **E11.4** Audyt zmian | historia zmian Operacji — dziś odłożona ([ADR-0011](../technical/adr/0011-audyt-odlozony.md)); powrót po E4 | ADR zastępujący ADR-0011 zaakceptowany przez właściciela | M |
| **E11.5** Nazewnictwo frontendu | `Pocket` → `Portfolio` ([CONTEXT](../business/CONTEXT.md), „Sprzeczności”) | brak „Pocket” w `frontend/src` | S |
| **E11.6** Testy frontendu | runner testów (np. Vitest) + e2e krytycznych ścieżek | CI frontendu uruchamia testy | M |
| **E11.7** Wydajność | pomiar na zbiorze 10 lat × 200 operacji × 30 walorów; indeksy; cache per `last_snapshot_date` | wykres < 300 ms, kokpit < 500 ms (p95, lokalnie) | S |
| **E11.8** UX i pierwsze uruchomienie | system komponentów i wzorce widoków (progresywne ujawnianie), kreator pierwszego uruchomienia (Portfel → import → benchmark), stany puste z podpowiedzią | nowy Portfel z importem w ≤ 5 krokach | M |

## Źródła

Odwołania prowadzą do dokumentów L4 z 2026-10-01/02 wymienionych w [pliku głównym](./02_roadmapa_funkcjonalna.md).
