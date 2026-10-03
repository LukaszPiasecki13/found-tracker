---
id: business-adr-readme
status: current
last_reviewed: 2026-10-03
type: reference
scope: business/adr
---

# ADR-y biznesowe

Decyzje produktowe i domenowe (zakres, reguły rozliczania, model danych z perspektywy użytkownika). Rejestr zawiera ADR 0001–0005 i 0007 (status `Accepted`); numeracja od 0001.

## Konwencja

- Plik: `NNNN-krotki-tytul.md`, numeracja od `0001`, niezależna od [ADR-ów technicznych](../../technical/adr/), nigdy nie używana ponownie.
- Szablon: szablon `adr.template.md` ze skilla `knowledge-base` (repo ai-tools).
- Status żyje w front-matterze (`status: Proposed` / `Accepted`), nie w treści. Nowy ADR zaczyna jako `Proposed`; na `Accepted` przełącza go człowiek.
- Decyzje czysto techniczne (architektura, sesje, błędy) → [`docs/technical/adr/`](../../technical/adr/).

## Rejestr

| ADR | Temat |
|---|---|
| [0001](0001-portfel-jest-rachunkiem.md) | Portfel = rachunek; Grupy portfeli |
| [0002](0002-koszt-nabycia-partie-fifo.md) | Koszt nabycia: partie FIFO |
| [0003](0003-gotowka-wielowalutowa.md) | Gotówka per (Portfel, Waluta) |
| [0004](0004-metodologia-stop-zwrotu.md) | TWR dzienny i XIRR |
| [0005](0005-daty-operacji-dzien-i-kolejnosc.md) | Dzień operacji i kolejność w dniu |
| [0007](0007-dane-referencyjne-i-usuwanie.md) | Dane referencyjne i archiwizacja Walorów |
