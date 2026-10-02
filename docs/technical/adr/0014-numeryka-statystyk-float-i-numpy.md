---
id: adr-0014-statistics-numerics
status: Proposed
type: decision
scope: backend/numerics
last_reviewed: 2026-10-02
---

# Księga, partie i wycena obligacji liczą się na `Decimal` w `domain/`; statystyki na `float` z `numpy` w `services/`

Czysta numeryka ma dwa miejsca. **Pieniądze, ilości i koszt** (księga, partie FIFO, wycena obligacji, pule podatkowe, rebalansing) — `Decimal`, `domain/` tylko z biblioteki standardowej. **Statystyki** (XIRR, zmienność, Sharpe, VaR, korelacja, Monte Carlo) — `float` i `numpy` w `services/`. Granica jest jawna i jednokierunkowa. Zamyka wariant (a) z [ADR-0005](0005-warstwa-domeny.md), uzupełnia go o `assets/domain/bonds.py` (reguła DOM-7 mówiła „`assets` bez `domain/`”) i uzupełnia [ADR-0010](0010-decimal-i-precyzja-pieniedzy.md) (bez edycji tamtych ADR-ów).

**Rozstrzyga:** D11 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)); wariant (a)/(b) ADR-0005. **Blokuje:** E3.1, E5.1, E6.1, E7.1, E9.2, E9.5.

## Kontekst

- ADR-0005 zostawił otwarte, czy `numpy` wolno w `domain/`; rekomendował (a): nie. Metryki są dziś w `services/metrics.py` (`import numpy as np`, `backend/app/modules/portfolios/services/metrics.py:31`).
- ADR-0010 dopuszcza `float` „wyłącznie w wektorach metryk do wykresów”. Nowe wskaźniki są skalarami (XIRR, Sharpe, VaR), a `twr_index` ma być przechowywany — ADR-0010 tego nie rozstrzyga.
- Test czystości zabrania wszystkiego poza `collections`, `dataclasses`, `datetime`, `decimal`, `enum`, `types`, `typing` (`backend/app/modules/portfolios/tests/unit/test_domain_purity.py:17`) i jest per moduł — [`01_backend-architecture.md` §10](../backend/01_backend-architecture.md) notuje brak testu ogólnego. `assets/domain/` i `taxes/domain/` bez niego byłyby niekontrolowane.
- Dowód: [metodyka §10.1](../../research/05_metodyka_metryk.md) — rejestr, wektor wartości i indeks TWR w `Decimal`; solver IRR, zmienność, VaR, Monte Carlo w `float`; przejście `float(d)` na wejściu, `Decimal(str(f))` na wyjściu.

## Decyzja

**1. Gdzie leży która numeryka**

| Obliczenie | Typ | Miejsce | Krok |
|---|---|---|---|
| Księga (`PortfolioLedger`), partie FIFO (`LotBook`), zysk zrealizowany | `Decimal` | `portfolios/domain/` | E2.4 |
| `r_day`, `twr_index` (przechowywany, mnożony łańcuchowo) | `Decimal` | `portfolios/domain/` | E2.5, E3.1 |
| Wycena obligacji skarbowych (funkcja per typ: OTS…ROD) | `Decimal` | `assets/domain/bonds.py` | E5.1 |
| Pule podatkowe, straty, WHT, kurs podatkowy | `Decimal` | `taxes/domain/` | E6.1–E6.5 |
| Rebalansing (odchylenia, całe jednostki, kwoty) | `Decimal` | `planning/domain/rebalancing.py` **[propozycja]** | E9.2 |
| XIRR (Newton + bisekcja), TWR okresu z indeksu | `float` → `Decimal` | `portfolios/services/performance.py` | E3.1 |
| Zmienność, Sharpe, Sortino, MDD, beta, korelacja, VaR, ES | `float` | `portfolios/services/risk.py` | E7.1 |
| Monte Carlo (stałe ziarno, ≥ 10 000 ścieżek) | `float` | `planning/services/monte_carlo.py` | E9.5 |
| Wektory wykresów | `float` | `portfolios/services/metrics.py` (jest) | — |

Kalkulatory statystyk to klasy bez I/O (jak `_VectorCalculator`, `metrics.py:119`), budowane w `wiring.py`, testowane bez bazy. Rebalansing jest w `domain/`, bo operuje kwotami i całymi jednostkami, nie statystyką.

**2. Granica `Decimal` ↔ `float`**
- Wejście do statystyk: `float(d)` — jedyne miejsce konwersji w górę, na początku kalkulatora.
- Wyjście: `Decimal(str(f))`, potem jawny `quantize` na granicy API (stopy 6 miejsc, procenty 2 — [metodyka §10.1](../../research/05_metodyka_metryk.md)). Nigdy `Decimal(f)` (ADR-0010).
- Wynik statystyki **nie wraca** do księgi, partii, salda ani snapshotu poza `twr_index`.
- `twr_index` liczy `domain/` na `Decimal`: `(1 + r_day)` z wartości `Decimal` snapshotu; kolumna `Numeric(24, 12)` **[propozycja]**; kontekst `localcontext()` z jawną precyzją 28 i trybem zaokrąglenia w czystej funkcji.
- Dokładność w testach: `Decimal` — równość dokładna; `float` — tolerancja jawna w teście (XIRR 0,373362535 ± 1e-8, [metodyka §10.5](../../research/05_metodyka_metryk.md)).

**3. Egzekwowanie** (testy, [ADR-0013](0013-kierunki-zaleznosci-nowych-modulow.md) pkt 6 dla konwencji):
- `numpy` importowany tylko w `*/services/` (wzór: test `yfinance`, `backend/app/core/tests/test_architecture.py:446`); `domain/`, `repositories/`, `api/` — nigdy.
- Test czystości `domain/` przenosimy do `core/tests/test_domain_purity.py` i parametryzujemy po `modules/*/domain`; dozwolone moduły jak dziś plus `calendar` (arytmetyka miesięcy w okresach obligacji) i `itertools` **[propozycja]**. Warstwy (DOM-9) — słownik `DOMAIN_LAYERS` per moduł w tym teście; dopisujemy do niego `assets` (`bonds.py`) i `taxes` jako warstwy domenowe (`planning` — przy E9.2).
- Brak `float` w `models/` i w polach `Decimal*` schematów (`DecimalNumber`, `backend/app/core/schemas.py`).

## Rozpatrywane alternatywy

- **Wariant (b): `numpy` w `domain/`.** Łamie DOM-1 i wymusza `numpy` w teście czystości; metryki i tak są adapterem nad cenami. Odrzucone.
- **Statystyki na `Decimal`.** `**` z ułamkowym wykładnikiem jest niedokładne, `Decimal` jest wolny i bez realnej korzyści ([metodyka §10.1](../../research/05_metodyka_metryk.md)). Odrzucone.
- **Wszystko na `float`, w tym `twr_index`.** Indeks jest przechowywany i mnożony przez lata; dryf rośnie, a testy złote tracą dokładną równość. Odrzucone.
- **`pandas` do statystyk.** Zbędna zależność ponad `numpy`; DataFrame zaciera granicę typów. Odrzucone.

## Konsekwencje

**Pozytywne**
- Księga i podatek są testowalne bez `numpy`, z dokładną równością; statystyki mają jedną, wąską granicę konwersji.
- `domain/` w trzech modułach pod jednym testem czystości.

**Negatywne**
- Dwie arytmetyki w jednym module `portfolios` — dyscyplina konwersji (łagodzi ją test i jedno miejsce `float(d)`).
- Rebalansing w `planning/domain/` jest decyzją roboczą; jeśli potrzebuje `numpy` (optymalizacja), wraca do `services/`.
- Nazwa pliku `performance.py` dla klas `*Calculator` odstępuje od DOM-6 (`*Service` w `services/`) — wymaga zapisu w dokumencie modułu.

## Otwarte

- Czy `Numeric(24, 12)` wystarcza dla `twr_index` po 10 latach dziennych mnożeń — zweryfikować testem własności przy E2.5.
