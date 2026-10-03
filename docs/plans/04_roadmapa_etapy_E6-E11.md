---
id: plan-feature-roadmap-e6-e11
status: draft
type: mixed
scope: plans/product-roadmap
last_reviewed: 2026-10-03
---

# Jakie kroki składają się na etapy E8 i E11 roadmapy?

Część [roadmapy funkcjonalnej](./02_roadmapa_funkcjonalna.md) (L3, szkic). Poprzednia część: [etapy E0–E4](./03_roadmapa_etapy_E0-E5.md). Format kroku i skala rozmiarów jak tam. Nazwa pliku zachowuje dawny zakres E6–E11; numeracja etapów ma luki (patrz plik główny).

---

## E8 — Zdarzenia korporacyjne i dywidendy

**Cel:** zdarzenia korporacyjne nie psują historii ani stóp zwrotu (częsta skarga w kategorii — [dowód](../research/competitors/02_trackery_porownanie.md)). Ceny w bazie nieskorygowane (E1.1), zdarzenia są Operacjami.

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E8.1** Split i scalenie (ręcznie; realizowany w M0) | Operacja `split` (nowe:stare) zmienia ilość i cenę jednostkową otwartych partii bez zmiany kosztu łącznego i daty nabycia (wzorzec Wealthfolio); ułamki rozliczone jako sprzedaż | split 1:10 → ilość ×10, koszt bez zmian, TWR ciągły w dniu splitu | M |
| **E8.2** Zmiana tickera / połączenie | wymiana walorów (stary → nowy, przelicznik, gotówka za ułamki) z przeniesieniem partii | zysk całkowity bez zmian | M |
| **E8.3** Spin-off | wydzielenie części kosztu partii do nowego waloru (współczynnik), data nabycia zachowana | suma kosztów partii przed = po | M |
| **E8.4** Prawa poboru i PDA | PP jako walor z ceną teoretyczną do pierwszego notowania; zapis i przydział (PP + cena emisyjna → akcje) | scenariusz emisji z przydziałem częściowym | M |
| **E8.5** Źródło zdarzeń | dywidendy i splity od dostawców (Yahoo; kalendarium GPW jest płatne — [dowód](../research/03_rynek_pl_dane_rynkowe.md)); **propozycje jako Operacje `status=draft`** (widok `/operations?status=draft`, akcje `accept`/`void`; bez osobnej tabeli zdarzeń), z ilością na dzień ustalenia prawa (T+2); orkiestracja w `portfolios/entrypoints.py` | propozycja dywidendy po dniu ustalenia prawa; akceptacja tworzy Operację | L |
| **E8.6** Kalendarz i prognoza dywidend | 12 miesięcy: ogłoszone, z historii (ostatnia DPS × częstotliwość), TTM | prognoza oznaczona jako szacunek; źródło każdej pozycji widoczne | M |

---

## E11 — Jakość i eksploatacja (ciągłe)

| Krok | Zakres | Kryteria akceptacji | Rozmiar |
|---|---|---|---|
| **E11.1** PWA i widok mobilny | responsywny kokpit, Portfel, walor, dodawanie operacji; instalacja jako PWA | Lighthouse PWA bez błędów; ręczny test na telefonie | M |
| **E11.2** Tryb prywatności | ukrycie kwot jednym przełącznikiem (wzorzec Ghostfolio) | brak kwot na wszystkich widokach | S |
| **E11.4** Audyt zmian | historia zmian Operacji — dziś odłożona ([ADR-0011](../technical/adr/0011-audyt-odlozony.md)); powrót po E4 | ADR zastępujący ADR-0011 zaakceptowany przez właściciela | M |
| **E11.6** Testy frontendu | runner (Vitest) wprowadzony w E0.7; tu: e2e krytycznych ścieżek (Playwright) | CI frontendu uruchamia testy jednostkowe i e2e | M |
| **E11.7** Wydajność | pomiar na zbiorze 10 lat × 200 operacji × 30 walorów; indeksy; cache po `dirty_from` Portfela ([ADR-0016](../technical/adr/0016-snapshoty-dzienne-i-przebudowa.md)) | wykres < 300 ms, kokpit < 500 ms (p95, lokalnie) | S |
| **E11.8** UX i pierwsze uruchomienie | system komponentów i wzorce widoków (progresywne ujawnianie), kreator pierwszego uruchomienia (Portfel → operacje → benchmark), stany puste z podpowiedzią | nowy Portfel z pierwszymi operacjami w ≤ 5 krokach | M |

## Źródła

Odwołania prowadzą do dokumentów L4 z 2026-10-01/02 wymienionych w [pliku głównym](./02_roadmapa_funkcjonalna.md).
