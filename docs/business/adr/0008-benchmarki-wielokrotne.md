---
id: adr-0008-multiple-benchmarks
status: Proposed
type: decision
scope: business/portfolio-comparison
last_reviewed: 2026-10-09
---

# Benchmarki wielokrotne — do 3 indeksów na ekranie porównania

Portfel można porównywać z wieloma indeksami równocześnie (S&P500, Nasdaq-100, WIG20) na ekranie porównania, zamiast z jednym. Rozszerzenie pkt 5 ADR-0004 bez naruszenia jego podstaw.

## Kontekst

- ADR-0004 pkt 5 ograniczał porównanie do jednego indeksu; wymagało to upraszczającego założenia o jednolitym benchmark'u dla celu.
- Użytkownik chce widzieć wielokrotne benchmarki na jednym wykresie, aby szybko ocenić portfel na tle kilku rynków (USA, całej Europy, Polski/Europy Środkowej).
- Indeksy są dostępne w Yahoo Finance (^GSPC, ^NDX, ETFBW20TR.WA), co nie wymaga nowego portu danych ani migracji — rdzenna infrastruktura `PriceService` wspiera dowolną liczbę Assetów.

## Decyzja

1. **V1 wspiera do 3 benchmarków** — wybór użytkownika przez checkboxes na ekranie `PocketComparisonPage` (S&P500, Nasdaq-100, WIG20).
2. **Benchmarki to Assety z `asset_type="index"`** — nie nowa tabela (DEC-02, ADR-0023), reużycie pipeline'u cen.
3. **API bez nowego endpointu** — query param `benchmarks` (JSON string, jak `vectors`) do `GET /portfolios/portfolio-vectors` (DEC-06).
4. **Rysowanie na ekranie** — benchmarki jako dodatkowe serie na wykresie "Zwrot względny (%)", to samo normalizowanie `(x-1)*100` co portfele (DEC-05).
5. **Forward-fill cen** — benchmarki bez sesji na rynku otrzymują ostatnią znaną cenę (reużycie `PriceService.series(fill="forward")`, AC-04).
6. **Transformacja waluty** — benchmarki normalizują się do bazy 1.0 na starcie zakresu, przeliczają się na walutę portfela (DEC-05, test przesyłanego kursu lub błąd).

## Rozpatrywane alternatywy

- Jeden indeks (ADR-0004) — zbyt ograniczony dla porównania wielorynkowego.
- Dedykowana tabela `assets_benchmark` — duplikuje pipeline cen bez korzyści (odrzucone w DEC-02).
- Per-user benchmarki — większa złożoność per instancję jednoużytkownika (odrzucone w DEC-02).
- Nieograniczona liczba benchmarków — UX zbyt zaawansowany (V1: max 3).

## Konsekwencje

- (+) Szybka ocena portfela na tle wielu rynków; nie zmienia modelu danych; reużycie istniejącego pipeline'u.
- (−) Więcej danych w jednej odpowiedzi przy każdej zmianie zakresu dat (jeśli benchmarki liczone na nowo) — rozwiązane: benchmarki w tym samym requeście co wektory portfela, nie osobnym wywołaniem.
- (−) Wykresy mogą być zaśmiecone przy równoczesnym wyborze >2 portfeli + 3 benchmarków; rozwiązane: UI ogranicza do 4 portfeli + 3 benchmarków.

## Notatki

- Rozszerzenie w przyszłości (V2): dodanie mWIG40, sWIG80 i indeksów międzynarodowych (DAX, CAC, FTSE).
- Inflacja (GUS BDL) — osobny port, poza V1.
- Supersedes ADR-0004 pkt 5 (nie zawiesza całego ADR, rozszerza go — patrz dopisek w ADR-0004).
