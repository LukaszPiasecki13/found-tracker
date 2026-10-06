---
id: adr-0022-tickery-i-wycena-bez-notowan
status: Proposed
type: decision
scope: portfolios/metrics, assets/market-data, portfolios/import
last_reviewed: 2026-10-06
---

# Tickery zostają jak przychodzą z importu; walor bez notowań jest wyceniany po cenach transakcji

Wykres portfela (`GET /portfolios/portfolio-vectors`) nie może przestać działać, bo jeden walor nie ma notowań u dostawcy. Tickery w bazie zostają w formie z importu XTB, a brak notowań obsługuje wycena po cenach własnych transakcji. Decyzja nie zmienia ADR-0015, tylko opisuje odstępstwo, które na razie akceptujemy.

## Status

Proposed

## Kontekst

- Import tworzy aktywa po tickerze z pliku: `app_ticker` obcina sufiks giełdy (`PL` → `.WA`, `US` → bez sufiksu, `DE` → `.DE`), a `get_or_create_by_ticker` szuka aktywa po tym tickerze lub tworzy nowe (`portfolios/services/import_mapping.py`, `portfolios/services/imports.py`).
- Sufiks `UK` nie jest w mapowaniu, więc walory `.UK` (np. `XNAS.UK`) trafiają do bazy z sufiksem `.UK`.
- Yahoo używa innych symboli: `BRKB` → `BRK-B`, `XNAS.UK`/`DTLA.UK`/`ICOM.UK`/`SMSN.UK` → `.L`. Część walorów nie ma notowań wcale (`01C.WA`, `CCC.WA`, `IGN.WA`, `LTS.WA`, `PGN.WA`).
- Przed tą decyzją wykres padał z 502 `PRICE_DATA_MISSING` już wtedy, gdy walor sprzedany w 2021 roku nie miał notowań, bo wycena pobierała ceny każdego waloru z historii portfela, także wyzerowanego przed zakresem.
- ADR-0015 (Accepted) wymaga, by wycena czytała ceny z `assets_price` / `assets_fx_rate` i nie robiła sieci w żądaniu. Obecny kod nadal pobiera historię od dostawcy w trakcie żądania.

## Decyzja

1. **Tickery w bazie nie są zmieniane.** Ani ręcznie, ani w imporcie. Zmiana nazwy aktywa spowodowałaby, że kolejny import utworzy duplikat pod starą nazwą, a nowe transakcje trafiłyby do walora bez notowań.
2. **Aktywo nigdy niedzierżone w zakresie jest warte 0** i nie jest pobierane (już wdrożone).
3. **Aktywo trzymane w zakresie bez notowań u dostawcy jest wyceniane po cenach własnych kupna i sprzedaży** (ostatnia znana cena transakcji, w walucie waloru, forward-fill). Wartość jest szacunkiem; kod zapisuje ostrzeżenie w logu. Jeśli nie ma żadnej użytecznej ceny transakcji (np. cena 0), żądanie nadal kończy się 502 `PRICE_DATA_MISSING`.
4. **Odstępstwo od ADR-0015 jest czasowe.** Wycena nadal pobiera historię od dostawcy w trakcie żądania. Przepięcie na `assets_price` to osobna decyzja.

## Rozpatrywane alternatywy

- **Zmiana tickerów w bazie** (np. `BRKB` → `BRK-B`). Odrzucona na razie: psuje kolejne importy (duplikaty), a scalenie `DTLA.UK` z `DTLA.L` wymaga osobnej decyzji.
- **Alias symboli w adapterze Yahoo** (`BRKB` → `BRK-B`, `.UK` → `.L`), bez zmiany danych ani importu. Rozważona jako bezpieczniejsza od zmiany w bazie; nie wdrożona, bo decyzja była inna.
- **Zostawić 502** dla każdego walora bez notowań. Odrzucona: jeden walor psuje cały wykres.
- **Mapowanie `UK` → `.L` w imporcie.** Odłożone: wymaga równoczesnej zmiany istniejących aktywów, inaczej nowe importy tworzą duplikaty.

## Konsekwencje

- (+) Wykresy działają dla portfeli z walorami bez notowań; import nie zmienia się.
- (+) Wycena po cenach transakcji nie daje zera tam, gdzie walor był trzymany.
- (−) Wartość walorów bez notowań jest szacunkiem. API nie sygnalizuje tego w odpowiedzi, tylko w logu serwera.
- (−) Walory `BRKB`, `XNAS.UK` i pozostałe `.UK` są wyceniane po cenach transakcji zamiast po notowaniach, dopóki ich tickery nie zostaną zmienione w adapterze lub w danych.
- (−) Import XTB dla walorów `.UK` nadal tworzy aktywa z sufiksem `.UK`. To problem istniejący przed tą decyzją.
- (−) Odstępstwo od ADR-0015 trwa.

## Otwarte

- Wybór mechanizmu mapowania symboli do Yahoo: alias w adapterze czy zmiana w imporcie i danych.
- Czy odpowiedź API ma sygnalizować walory wycenione szacunkowo (np. pole w odpowiedzi lub ostrzeżenie w `data_quality`).
- Przepięcie wyceny na `assets_price` / `assets_fx_rate` zgodnie z ADR-0015 (osobne zadanie).
- Scalenie `DTLA.UK` z `DTLA.L` (id 545 → 559) i mapowanie sufiksu `UK` w imporcie.
