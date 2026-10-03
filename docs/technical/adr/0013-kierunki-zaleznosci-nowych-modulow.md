---
id: adr-0013-module-dependency-directions
status: Accepted
type: decision
scope: backend/module-boundaries
last_reviewed: 2026-10-03
---

# Graf zależności czterech modułów jest tabelą egzekwowaną testem; import żyje w `portfolios`, a jego parser jest portem w `core/`

Rozszerza kierunki z [ADR-0006](0006-cross-module-wylacznie-przez-serwisy.md) o pełny graf modułów `core_data`, `security`, `assets`, `portfolios` i egzekwuje go testem.

**Rozstrzyga:** D10 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E1.4, E2.5, E4.1.

## Kontekst

- ADR-0006 podaje tylko `portfolios → assets|core_data`, `security → core_data`. Test (`backend/app/core/tests/test_architecture.py:522`) dopuszcza dowolny kierunek między modułami i nie sprawdza importów `infrastructure/`.
- Cykl serwisów: `core_data/services/users.py:7` ↔ `security/services/auth.py:2`.
- Roadmapa dodaje walutę wyświetlania w `core_data` (E0.9) i import (E4).

## Decyzja

**1. Graf** (serwisy, repozytoria, `wiring.py`, `entrypoints.py`; `api/` i `dependencies.py` poza grafem):

| Moduł | Może zależeć od |
|---|---|
| `core_data` | — (dług: `→ security`, lista legacy w teście, tylko maleje) |
| `security` | `core_data` |
| `assets` | — |
| `portfolios` | `assets`, `core_data` |

Zakazane: `assets → portfolios`, `assets → core_data|security`.

**2. Bez dodatkowych kanałów.** Moduły wołają się wyłącznie przez serwisy ([ADR-0006](0006-cross-module-wylacznie-przez-serwisy.md)); nowy kierunek wymaga nowego ADR-a.

**3. Import w `portfolios`** ([ADR-0018](0018-architektura-importu.md)). `import_batch` ma FK do `portfolios_portfolio` i `portfolios_operation`; osobny moduł dałby cykl.

**4. Port parsera w `core/import_parser.py`** (wzór `core/market_data.py:50`): `ImportParser`, `ParsedRow`, `ParseResult`, `ImportParseError`. Adaptery w `infrastructure/import_parsers/`, składane w `portfolios/wiring.py`.

**5. Waluta wyświetlania bez zależności od `assets`.** `core_data` trzyma `display_currency_code` (`String(3)`, bez FK, `^[A-Z]{3}$`). Konsument rozwiązuje kod przez `assets`; nieznany → `CURRENCY_NOT_FOUND` przy wycenie, nie przy zapisie. **[propozycja]**

**6. Egzekwowanie** (`core/tests/test_architecture.py`, każdy test z testem detektora):
- `ALLOWED_MODULE_DEPENDENCIES` = tabela z pkt 1; import spoza niej z `services/`, `repositories/`, `wiring.py`, `entrypoints.py` → błąd.
- `infrastructure/` importuje z `app.*` tylko `app.core` i `app.infrastructure`.
- `core/` nie importuje `app.modules` ani `app.infrastructure`.

## Alternatywy

- Port `CurrencyCatalog` w `core_data` — daje `core_data → assets` i pętlę; odrzucone.
- Osobny moduł `imports` — cykl FK; odrzucone (D10).
- Zdarzenia zamiast kierunków — jeden proces, wystarczą wywołania serwisów; odrzucone.

## Konsekwencje

- (+) Graf jest tabelą i testem. `assets` i `core_data` zostają liśćmi (poza długiem `→ security`).
- (−) Dług `core_data → security` trwa; walidacja waluty z opóźnieniem.

## Otwarte

- Przeniesienie haszowania haseł do `core/` (zamyka dług `core_data → security`).
