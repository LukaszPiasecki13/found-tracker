---
id: adr-0014-statistics-numerics
status: Proposed
type: decision
scope: backend/numerics
last_reviewed: 2026-10-02
---

# Księga, partie i wycena obligacji liczą się na `Decimal` w `domain/`; statystyki na `float` z `numpy` w `services/`

Pieniądze, ilości i koszt — `Decimal`, `domain/` tylko ze stdlib. Statystyki — `float` i `numpy` w `services/`. Zamyka wariant (a) [ADR-0005](0005-warstwa-domeny.md), dodaje `assets/domain/bonds.py`, uzupełnia [ADR-0010](0010-decimal-i-precyzja-pieniedzy.md).

**Rozstrzyga:** D11 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E3.1, E5.1, E6.1, E7.1, E9.2, E9.5.

## Kontekst

- Metryki są w `services/metrics.py` (`numpy`, `backend/app/modules/portfolios/services/metrics.py:31`); ADR-0010 dopuszcza `float` tylko w wektorach wykresów, nie rozstrzyga skalarów ani przechowywanego `twr_index`.
- Test czystości (`portfolios/tests/unit/test_domain_purity.py:17`) jest per moduł; `assets/domain/` i `taxes/domain/` byłyby bez kontroli.
- Dowód: [metodyka §10.1](../../research/05_metodyka_metryk.md).

## Decyzja

**1. Podział**

| Obliczenie | Typ | Miejsce |
|---|---|---|
| Księga, partie FIFO, zysk zrealizowany | `Decimal` | `portfolios/domain/` |
| `r_day`, `twr_index` | `Decimal` | `portfolios/domain/` |
| Wycena obligacji | `Decimal` | `assets/domain/bonds.py` |
| Pule podatkowe, straty, WHT, kurs podatkowy | `Decimal` | `taxes/domain/` |
| Rebalansing | `Decimal` | `planning/domain/rebalancing.py` **[propozycja]** |
| XIRR, TWR okresu | `float` → `Decimal` | `portfolios/services/performance.py` |
| Zmienność, Sharpe, Sortino, MDD, beta, korelacja, VaR, ES | `float` | `portfolios/services/risk.py` |
| Monte Carlo (stałe ziarno, ≥ 10 000 ścieżek) | `float` | `planning/services/monte_carlo.py` |
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
- Test czystości → `core/tests/test_domain_purity.py`, parametryzowany po `modules/*/domain`; dozwolone jak dziś plus `calendar`, `itertools` **[propozycja]**; `DOMAIN_LAYERS` obejmuje `assets` i `taxes` (`planning` przy E9.2).
- Brak `float` w `models/` i polach `Decimal*` schematów (`DecimalNumber`).

## Alternatywy

- `numpy` w `domain/` — łamie DOM-1; odrzucone.
- Statystyki na `Decimal` — niedokładne `**`, wolne; odrzucone.
- Wszystko `float`, w tym `twr_index` — dryf, brak dokładnej równości w testach; odrzucone.
- `pandas` — zbędna zależność; odrzucone.

## Konsekwencje

- (+) Księga i podatek testowalne bez `numpy`; jedna granica konwersji; `domain/` pod jednym testem.
- (−) Dwie arytmetyki w `portfolios`; rebalansing w `domain/` roboczy; `performance.py` odstępuje od DOM-6 (zapis w dokumencie modułu).

## Otwarte

- Czy `Numeric(24, 12)` wystarcza dla `twr_index` po 10 latach — test własności przy E2.5.
