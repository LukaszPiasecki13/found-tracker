---
id: adr-0023-benchmark-as-asset-index
status: Proposed
type: decision
scope: assets/models, portfolios/metrics
last_reviewed: 2026-10-09
---

# Benchmark jako Asset z asset_type="index" — pełne reużycie pipeline'u cen

Indeks benchmarku (S&P500, Nasdaq-100, WIG20) reprezentuje się Assetem z nową wartością `asset_type="index"` w kolumnie `String(10)`, a nie osobną tabelą. Ceny pobierane są przez istniejący `PriceService` (ADR-0015, ADR-0014), normalizacją wektora obsługuje serwis metryk (Float, numpy).

## Kontekst

- Wycena wektora portfela (`portfolio_vectors`) pobiera ceny z `assets_price` przez `PriceService.series()` i transformuje je do wektora (Float, numpy; ADR-0014). Benchmarki muszą przechodzić ten sam pipeline.
- Alternatywa: dedykowana tabela `assets_benchmark` — duplikuje kolumny `assets_price`, `assets_fx_rate` bez korzyści w V1 dla jednoużytkownika.
- Rdzenny model: Asset już ma `asset_type` (String(10), enum'owany w `ASSET_TYPES`); walor kupiony to `("stock", "etf", "bond")`, indeks to nowy typ.
- Asset będący indeksem (nie kupionym) nie może trafić do Operacji (`DEC-04`, filtr `exclude_asset_type="index"` w wyszukiwarce).

## Decyzja

1. **Reprezentacja:** Benchmark to Asset z `asset_type="index"`, bez nowych kolumn. Tickery: `^GSPC`, `^NDX`, `ETFBW20TR.WA`.
2. **Brak migracji:** Kolumna `asset_type` jest już String(10) w `assets_asset`; wartość enum'owana w `ASSET_TYPES` (constants.py), walidowana na wejściu (schemas/assets.py).
3. **Historia cen:** Ceny indeksu zapisane w `assets_price` (UNIQUE `asset_id, price_date, source`), pobierane przez `PriceService.series(asset_id, ...)` — brak zmian interfejsu.
4. **Waluta:** Indeksy mają `currency_id` jak każdy Asset; kursy pobierane przez `FxRateService.rate_vector()` transformują wektor z waluty indeksu na walutę portfela.
5. **Zakazana pozycja (tylko na poziomie wyszukiwania w V1):** wyszukiwanie tickera przy
   tworzeniu Operacji wyklucza Assety `asset_type="index"` filtrem `exclude_asset_type="index"`
   (DEC-04). `OperationService.create()` nie ma dziś twardej walidacji `asset_type` — podanie
   `asset_id` indeksu wprost (np. bezpośrednim wywołaniem API, z pominięciem wyszukiwarki)
   nie jest blokowane po stronie serwisu. Zostaje jako otwarty punkt do decyzji, nie wchodzi
   do V1 (DEC-04 dotyczył wyłącznie warstwy wyszukiwania).

## Rozpatrywane alternatywy

- **Dedykowana tabela `assets_benchmark`** — `id`, `ticker`, `name`, `currency_id`, alias dla `^GSPC` → S&P500. Duplicates `assets_price`, `assets_fx_rate` bez korzyści. Odrzucone: większa złożoność, duplikacja, uniemożliwia łatwe dodanie nowych indeksów.
- **Per-user benchmarki** — osobne rekordy po użytkowniku. Odrzucone: V1 to jeden użytkownik; ADR-0007 mówi, że benchmarki to dane globalne instancji (jak Waluty).
- **Enum strict (baza constraint `CHECK asset_type IN ...`)** — odrzucone: enum'owania robi Pydantic w schemacie; kolumna pozostaje String(10) dla elastyczności.

## Konsekwencje

- (+) Brak migracji (ani `alembic revision`, ani UPDATE); reużycie 100% istniejącego pipeline'u cen i kursów.
- (+) Benchmark traktowany jak Asset w całej wycenie: forward-fill, transformacja walut, obsługa braku danych.
- (+) Łatwe dodanie nowych indeksów (V2): jeden INSERT w `assets` + seed'owanie cen.
- (−) Asset z `asset_type="index"` nigdy nie ma Pozycji, Operacji ani snapshotu dziennego (model jest uniwersalny, ale znaczenie tego typu ograniczone); logika wyliczenia musi je traktować osobno (już wdrożone: filtr w `VectorCalculator.benchmarks()`, pobieranie cen bez udziału Pozycji).
- (−) UI — wyszukiwanie tickera wyklucza indeksy (DEC-04); użytkownik końcowy nie widzi ich w listach operacji.

## Notatki

- Wartość `asset_type="index"` dodana do `ASSET_TYPES` (constants.py) w ramach DEC-02.
- Seed trzech indeksów (`^GSPC`, `^NDX`, `ETFBW20TR.WA`) — `entrypoints.py:seed_benchmark_assets()` (non-HTTP callable).
- Walidacja Asset'u w operacji — `OperationService.create()` NIE sprawdza `asset_type`; jedyną
  barierą jest wykluczenie z wyszukiwania (patrz pkt 5 Decyzji, otwarty punkt).
- Forward-fill cen i transformacja waluty — `VectorCalculator.benchmarks()` (services/metrics.py) reużywa `rate_vector()` i `_filled()`.
- Supersedes ADR-0004 pkt 5 (indeks, nie benchmarki) — patrz dopisek w ADR-0004 i nowy ADR-0008 (biznesowy).
