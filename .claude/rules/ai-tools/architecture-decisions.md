---
paths: ["docs/**/adr/**/*.md", "docs/**/bdr/**/*.md", "**/adr-*.md"]
description: ADR (Architecture Decision Record) template and process. Auto-loaded when working in any docs/**/adr/ or docs/**/bdr/ directory (e.g. docs/adr/, docs/business/bdr/, docs/technical/adr/) or on files named adr-*.
---

# Architecture Decision Records (ADR)

Use ADRs for decisions that affect multiple files, teams, or are hard to reverse.

## When to Write an ADR

- Choosing a framework, library, or tool
- Changing authentication or authorization approach
- Altering database schema strategy
- Selecting state management pattern
- Defining API versioning approach
- Any decision you would want to explain to a new team member

## File Naming and Location

- File: `NNNN-short-title.md` (e.g., `0001-mvp-scope-temperature-pressure.md`)
- Location: `docs/business/bdr/` for business decisions (BDR-NNNN, Business Decision Record), `docs/technical/adr/` for technical ones (ADR-NNNN)
- Number sequentially per directory, never reuse numbers, pad to 4 digits

## Template

```markdown
# {Tytuł decyzji}

{1-3 zdania: co i dlaczego}

## Status
Proposed | Accepted | Deprecated | Superseded by ADR-NNNN

## Kontekst
Jaki problem? Jakie opcje rozważano?

## Decyzja
Co wybrano i dlaczego (konkretne kompromisy).

## Rozpatrywane alternatywy
Czemu zostały odrzucone?

## Konsekwencje
Ułatwia, utrudnia, zamyka?

## Notatki
Opcjonalnie: co nierozstrzygnięte, odnośniki.
```

Wymagane: `Kontekst`, `Decyzja`, `Rozpatrywane alternatywy`, `Konsekwencje`. `Status` i `Notatki` opcjonalnie.
