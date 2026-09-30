---
id: adr-0010-decimal-money
status: Proposed
last_reviewed: 2026-09-30
type: decision
scope: backend/money-precision
---

# Kwoty, ceny, ilości i kursy są `Decimal` od bazy do granicy schematu; `float` tylko w wektorach do wykresów

W modelu, repozytoriach, serwisach i `domain/` wszystkie wartości pieniężne i ilościowe to `Decimal` (kolumny `Numeric`). `float` dopuszczamy wyłącznie w wynikach wektorów metryk przeznaczonych do wykresów, po zakończeniu obliczeń kwotowych.

## Kontekst

Modele używają `Numeric` (`cash_balance` `(18,3)`, `quantity` `(18,9)`, `price` `(18,9)`, `fee` `(18,2)`), serwisy liczą na `Decimal(str(x))`. Jednocześnie `portfolios/api.py` konwertuje wartości na `float` (`_as_float`) przy wyliczaniu pól pozycji i portfela, a `PortfolioMetrics` liczy na `numpy` (`float64`). Mieszanie `float` z `Decimal` daje błędy zaokrągleń w saldzie i `TypeError` przy mnożeniu.

## Decyzja

- Jedyny typ dla kwot/cen/ilości/kursów w backendzie: `Decimal`. Konwersja z wejścia zawsze przez `Decimal(str(value))`, nigdy `Decimal(float)`.
- Schematy Pydantic: pola kwotowe typu `Decimal`; serializacja JSON zgodnie z ustaleniem kontraktu API (dziś liczby). Zmiana reprezentacji w JSON (liczba vs napis) wymaga zmiany we frontendzie i jest poza tym ADR-em.
- Zaokrąglanie: jawne `quantize` z ustaloną precyzją na granicy zapisu, nie w środku obliczeń.
- `float` dozwolony wyłącznie w wektorach metryk (`numpy`) po zakończeniu obliczeń kwotowych; wynik nie wraca do modelu ani do salda.
- `Decimal` w dzielnikach: dzielenie przez zero obsługuje `domain/` jawnie (np. cena średnia przy ilości 0).

## Rozpatrywane alternatywy

- **Liczby całkowite w groszach.** Niewygodne przy cenach do 9 miejsc (instrumenty z ułamkowymi jednostkami). Odrzucone.
- **`float` wszędzie.** Błędy zaokrągleń kumulują się w saldzie i średniej cenie. Odrzucone.

## Konsekwencje

**Pozytywne**
- Deterministyczne saldo i średnie ceny; testy mogą porównywać równość dokładną.

**Negatywne**
- `numpy`/`pandas` nie wspierają `Decimal` natywnie — granica `Decimal → float` musi być jawna i zlokalizowana w metrykach.
- Wymaga przeglądu `portfolios/api.py` i `analytics/` (krok R-08).
