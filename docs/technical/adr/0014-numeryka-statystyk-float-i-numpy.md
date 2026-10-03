---
id: adr-0014-statistics-numerics
status: Accepted
type: decision
scope: backend/numerics
last_reviewed: 2026-10-03
---

# Księga, partie, TWR i kursy liczą się na `Decimal` w `domain/`; `float` z `numpy` tylko dla XIRR i statystyk benchmarku w `services/`

Pieniądze, ilości, koszt i `twr_index` — `Decimal`, `domain/` tylko ze stdlib. `float` i `numpy` wyłącznie w `services/`. Zamyka wariant (a) [ADR-0005](0005-warstwa-domeny.md), uzupełnia [ADR-0010](0010-decimal-i-precyzja-pieniedzy.md).

**Rozstrzyga:** D11 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E3.1.

## Kontekst

- Metryki są w `services/metrics.py` (`numpy`, `backend/app/modules/portfolios/services/metrics.py:31`); ADR-0010 dopuszcza `float` tylko w wektorach wykresów, nie rozstrzyga skalarów ani przechowywanego `twr_index`.
- Test czystości (`portfolios/tests/unit/test_domain_purity.py:17`) jest per moduł.
- Dowód: [metodyka §10.1](../../research/05_metodyka_metryk.md).

## Decyzja

**1. Podział**

| Obliczenie | Typ | Miejsce |
|---|---|---|
| Księga, partie FIFO, zysk zrealizowany | `Decimal` | `portfolios/domain/` |
| `r_day`, `twr_index`, kursy | `Decimal` | `portfolios/domain/` |
| XIRR | `float` → `Decimal` | `portfolios/services/performance.py` |
| Statystyki benchmarku | `float` | `portfolios/services/performance.py` |
| Wektory wykresów | `float` | `portfolios/services/metrics.py` |

Kalkulatory to klasy bez I/O, budowane w `wiring.py`.

**2. Granica `Decimal` ↔ `float`**
- Wejście: `float(d)`, jedno miejsce, początek kalkulatora.
- Wyjście: `Decimal(str(f))` + jawny `quantize` na granicy API (stopy 6 miejsc, procenty 2). Nigdy `Decimal(f)`.
- Wynik statystyki nie wraca do księgi, partii, salda ani snapshotu poza `twr_index`.
- `twr_index` liczy `domain/` na `Decimal`: `(1 + r_day)`, kolumna `Numeric(24, 12)` **[propozycja]**, `localcontext()` z precyzją 28.
- Testy: `Decimal` — równość dokładna; `float` — jawna tolerancja (XIRR 0,373362535 ± 1e-8).

**3. Egzekwowanie** ([ADR-0013](0013-kierunki-zaleznosci-nowych-modulow.md) pkt 6)
- `numpy` tylko w `*/services/` (wzór: test `yfinance`, `test_architecture.py:446`).
- Test czystości → `core/tests/test_domain_purity.py`, parametryzowany po `modules/*/domain`; dozwolone jak dziś plus `calendar`, `itertools` **[propozycja]**.
- Brak `float` w `models/` i polach `Decimal*` schematów (`DecimalNumber`).

## Alternatywy

- `numpy` w `domain/` — łamie DOM-1; odrzucone.
- XIRR na `Decimal` — iteracja z `**`, niedokładna i wolna; odrzucone.
- Wszystko `float`, w tym `twr_index` — dryf, brak dokładnej równości w testach; odrzucone.
- `pandas` — zbędna zależność; odrzucone.

## Konsekwencje

- (+) Księga testowalna bez `numpy`; jedna granica konwersji; `domain/` pod jednym testem.
- (−) Dwie arytmetyki w `portfolios`; `performance.py` odstępuje od DOM-6 (zapis w dokumencie modułu).

## Otwarte

- Czy `Numeric(24, 12)` wystarcza dla `twr_index` po 10 latach — test własności przy E2.5.
