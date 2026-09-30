---
id: business-adr-readme
status: current
last_reviewed: 2026-09-30
type: reference
scope: business/adr
---

# ADR-y biznesowe

Decyzje produktowe i domenowe (zakres, reguły rozliczania, model danych z perspektywy użytkownika). Dziś pusty — pierwsze decyzje zapadną wraz z pierwszą zmianą zakresu produktu.

## Konwencja

- Plik: `NNNN-krotki-tytul.md`, numeracja od `0001`, niezależna od [ADR-ów technicznych](../../technical/adr/), nigdy nie używana ponownie.
- Szablon: [`adr.template.md`](../../../.claude/skills/knowledge-base/templates/adr.template.md).
- Status żyje w front-matterze (`status: Proposed` / `Accepted`), nie w treści. Nowy ADR zaczyna jako `Proposed`; na `Accepted` przełącza go człowiek.
- Decyzje czysto techniczne (architektura, sesje, błędy) → [`docs/technical/adr/`](../../technical/adr/).
