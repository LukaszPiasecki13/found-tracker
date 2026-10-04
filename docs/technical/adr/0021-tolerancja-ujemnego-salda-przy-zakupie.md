---
id: adr-0021-buy-overdraft-tolerance
status: Proposed
type: decision
scope: portfolios/ledger
last_reviewed: 2026-10-04
---

# Zakup może zejść najwyżej 0,50 poniżej zera salda; pozostałe operacje nie

Księga dopuszcza, by zakup zostawił saldo w przedziale od −0,50 do 0 (w walucie portfela). Wypłata, opłata i pozostałe operacje nadal wymagają pokrycia w saldzie. Stała `BUY_OVERDRAFT_TOLERANCE` leży w `domain/ledger.py`.

## Status

Proposed

## Kontekst

- Eksport XTB konta USD (`USD_50495891_…xlsx`) ma jeden moment, w którym według kwot z pliku saldo wynosi −0,10: zakup 0,9 SMCI za 360,05 przy 359,95 gotówki (26.09.2024). Broker rozlicza ułamkowe akcje co do centa i dopuścił to.
- Księga odrzucała zakup, gdy koszt przekraczał saldo (`domain/ledger.py`, `_buy`), więc import tego pliku kończył się `INSUFFICIENT_CASH` w wierszu 304.
- Historia zapisanych Operacji musi dać się odtworzyć przez `rebuild` ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)); zapis z wyjątkiem tylko dla importu zepsułby późniejszą przebudowę (edycja, cofnięcie innego importu).

## Decyzja

1. `PortfolioLedger` dopuszcza zakup, gdy `saldo + 0,50 ≥ koszt`. Saldo może być przez to ujemne (−0,50…0) do najbliższego wpływu.
2. Wyjątek dotyczy tylko kupna. Wypłata, opłata i odsetki/opłaty importowane z brokera nadal wymagają pokrycia.
3. Reguła obowiązuje wszystkie ścieżki (ręczny zapis, import, przebudowa), bo księga jest jedna.

## Rozpatrywane alternatywy

- **Tolerancja tylko w imporcie.** Zapisana historia nie przeszłaby ścisłej przebudowy; odrzucone.
- **Syntetyczna operacja +0,10 w imporcie.** Fałszuje saldo końcowe względem brokera; odrzucone.
- **Ręczna wpłata przed importem.** Fałszuje sumę wpłat i saldo; odrzucone.

## Konsekwencje

- (+) Pliki brokerów z groszowymi przejściami przez zero importują się bez ingerencji w dane.
- (−) Ręczny zakup może zostawić saldo do −0,50; UI pokaże je jako ujemne.
- (−) Stała 0,50 jest w walucie portfela, bez przeliczenia na inne waluty.

## Otwarte

- Czy tolerancja ma być konfigurowalna, czy zostaje stałą domeny.
