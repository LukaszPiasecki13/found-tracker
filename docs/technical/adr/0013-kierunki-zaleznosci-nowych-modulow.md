---
id: adr-0013-module-dependency-directions
status: Proposed
type: decision
scope: backend/module-boundaries
last_reviewed: 2026-10-02
---

# Nowe moduły `taxes`, `planning`, `notifications` zależą tylko „w dół” grafu; import żyje w `portfolios`, a jego parser jest portem w `core/`

Rozszerza kierunki z [ADR-0006](0006-cross-module-wylacznie-przez-serwisy.md) o trzy nowe moduły i egzekwuje je testem.

**Rozstrzyga:** D10 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E1.4, E2.5, E4.1, E6.1, E9.1, E10.1.

## Kontekst

- ADR-0006 podaje tylko `portfolios → assets|core_data`, `security → core_data`. Test (`backend/app/core/tests/test_architecture.py:522`) dopuszcza dowolny kierunek między modułami i nie sprawdza importów `infrastructure/`.
- Cykl serwisów: `core_data/services/users.py:7` ↔ `security/services/auth.py:2`.
- Roadmapa dodaje `taxes` (E6), `planning` (E9), `notifications` (E10), walutę wyświetlania w `core_data` (E0.9) i import (E4).

## Decyzja

**1. Graf** (serwisy, repozytoria, `wiring.py`, `entrypoints.py`; `api/` i `dependencies.py` poza grafem):

| Moduł | Może zależeć od |
|---|---|
| `core_data` | — (dług: `→ security`, lista legacy w teście, tylko maleje) |
| `security` | `core_data` |
| `assets` | — |
| `portfolios` | `assets`, `core_data` |
| `taxes` | `portfolios`, `assets` |
| `planning` | `portfolios`, `taxes`, `assets` |
| `notifications` | `assets`, `portfolios`, `planning` — tylko przez porty (pkt 2) |

Zakazane: `assets → portfolios`, `portfolios → taxes|planning|notifications`, `taxes → planning|notifications`; nikt nie zależy od `notifications`.

**2. `notifications` przez porty.** `Protocol`y (`PriceSource`, `PortfolioValueSource`, `PlanningSource`) w `notifications/domain/protocols.py` ([ADR-0005](0005-warstwa-domeny.md)); adapter w `notifications/services/sources.py`. Alerty wyzwala driver CLI ([ADR-0017](0017-zadania-w-tle-i-cli.md)), nie zdarzenie.

**3. Import w `portfolios`** ([ADR-0018](0018-architektura-importu.md)). `import_batch` ma FK do `portfolios_portfolio` i `portfolios_operation`; osobny moduł dałby cykl. `imports` powstaje dopiero, gdy `portfolios` urośnie **i** FK da się odwrócić.

**4. Port parsera w `core/import_parser.py`** (wzór `core/market_data.py:50`): `ImportParser`, `ParsedRow`, `ParseResult`, `ImportParseError`. Adaptery w `infrastructure/import_parsers/`, składane w `portfolios/wiring.py`.

**5. Waluta wyświetlania bez zależności od `assets`.** `core_data` trzyma `display_currency_code` (`String(3)`, bez FK, `^[A-Z]{3}$`). Konsument rozwiązuje kod przez `assets`; nieznany → `CURRENCY_NOT_FOUND` przy wycenie, nie przy zapisie. **[propozycja]**

**6. Egzekwowanie** (`core/tests/test_architecture.py`, każdy test z testem detektora):
- `ALLOWED_MODULE_DEPENDENCIES` = tabela z pkt 1; import spoza niej z `services/`, `repositories/`, `wiring.py`, `entrypoints.py` → błąd.
- `infrastructure/` importuje z `app.*` tylko `app.core` i `app.infrastructure`.
- `core/` nie importuje `app.modules` ani `app.infrastructure`.

## Alternatywy

- Port `CurrencyCatalog` w `core_data` — daje `core_data → assets` i pętlę; odrzucone.
- `notifications` wołające serwisy wprost — wiąże alerty z DTO cudzych modułów; odrzucone.
- Osobny moduł `imports` — cykl FK; odrzucone (D10).
- Zdarzenia zamiast kierunków — jeden proces, driver sekwencjonuje; odrzucone.

## Konsekwencje

- (+) Graf jest tabelą i testem; nowy kierunek wymaga ADR-a. `assets`, `core_data` zostają liśćmi.
- (−) Dług `core_data → security` trwa; `portfolios` rośnie; walidacja waluty z opóźnieniem.

## Otwarte

- Czy `taxes → assets` jest potrzebne (E6.2).
- Przeniesienie haszowania haseł do `core/`.
