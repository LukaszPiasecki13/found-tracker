---
id: adr-0013-module-dependency-directions
status: Proposed
type: decision
scope: backend/module-boundaries
last_reviewed: 2026-10-02
---

# Nowe moduły `taxes`, `planning`, `notifications` zależą tylko „w dół” grafu; import żyje w `portfolios`, a jego parser jest portem w `core/`

Rozszerza listę dopuszczalnych kierunków z [ADR-0006](0006-cross-module-wylacznie-przez-serwisy.md) (bez edycji tamtego ADR-a) o trzy nowe moduły, rozstrzyga wyjątek `core_data` ↔ waluta oraz miejsce importu. Kierunki stają się egzekwowane testem, a nie samym przeglądem.

**Rozstrzyga:** D10 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)). **Blokuje:** E1.4, E2.5, E4.1, E6.1, E9.1, E10.1; test kierunków — przed pierwszym kodem nowego modułu.

## Kontekst

- ADR-0006 podaje tylko `portfolios → assets`, `portfolios → core_data`, `security → core_data`; dla reszty wymaga portu.
- **Test tego nie egzekwuje.** `test_services_and_repositories_reach_other_modules_only_through_services` (`backend/app/core/tests/test_architecture.py:522`) zakazuje cudzych `repositories`/`api` i podmodułów `domain/` (`:478`), ale dopuszcza dowolny kierunek między modułami. Nie ma też testu, że `infrastructure/` importuje tylko `core/`/`errors` (tabela w [`01_backend-architecture.md` §2.1](../backend/01_backend-architecture.md)).
- Istniejące odstępstwo: `core_data/services/users.py:7` importuje `security.services.password`, a `security/services/auth.py:2` — `core_data`. To cykl na poziomie serwisów, którego ADR-0006 nie przewiduje.
- Roadmapa dodaje moduły `taxes` (E6), `planning` (E9), `notifications` (E10), ustawienie waluty wyświetlania w `core_data` (E0.9) i import (E4).

## Decyzja

**1. Graf zależności serwisów, repozytoriów, `wiring.py` i `entrypoints.py`** (strzałka = „może importować”; `api/` i `dependencies.py` są poza grafem — każde `api/` importuje `security.dependencies.get_current_user`, §2.1 architektury):

| Moduł | Może zależeć od | Uwagi |
|---|---|---|
| `core_data` | — | liść; `core_data → security` jest długiem, nie wzorem: `core_data/services/users.py:7` ↔ `security/services/auth.py:2` (lista legacy w teście, tylko maleje) |
| `security` | `core_data` | bez zmian |
| `assets` | — | nie zależy od żadnego modułu biznesowego |
| `portfolios` | `assets`, `core_data` | bez zmian; import (pkt 3) mieszka tu |
| `taxes` | `portfolios`, `assets` | czyta rekordy zużycia partii (`portfolios_lot_consumption`, E2.4) przez serwis `portfolios`; z `assets` tylko metadane waloru (kraj, typ) |
| `planning` | `portfolios`, `taxes`, `assets` | rebalansing szacuje podatek FIFO (E9.2) przez serwis `taxes`; z `assets` ceny i metadane Walorów (kierunek `planning → assets`) |
| `notifications` | `assets`, `portfolios`, `planning` — **tylko przez porty** | pkt 2; kierunek `notifications → planning` dla alertu o celu/rebalansingu (E9.1); `notifications → taxes` nie istnieje |

Zakazane na stałe: `assets → portfolios`, `portfolios → taxes|planning|notifications`, `taxes → planning|notifications`. Nikt nie zależy od `notifications`.

**2. `notifications` przez porty.** Moduł definiuje `Protocol`y (`PriceSource`, `PortfolioValueSource`, `PlanningSource`) w `notifications/domain/protocols.py` (DOM-8, [ADR-0005](0005-warstwa-domeny.md)). Adapter w `notifications/services/sources.py` opakowuje `AssetService`/`PortfolioService`/serwis `planning` składane przez `assets_wiring`/`portfolios_wiring`/`planning_wiring`. Powód: reguła alertu to czysta logika nad kilkoma liczbami — testowalna bez bazy i niezależna od kształtu DTO cudzych modułów. Wyzwalanie alertów po odświeżeniu cen robi driver (CLI, [ADR-0017](0017-zadania-w-tle-i-cli.md)), nie zdarzenie.

**3. Import w `portfolios`, nie osobny moduł** ([ADR-0018](0018-architektura-importu.md)). Paczka importu (`import_batch`) ma FK do `portfolios_portfolio` i `portfolios_operation` w obie strony; osobny moduł `imports` wymusiłby zależność `portfolios ↔ imports`. Moduł `imports` powstaje tylko, jeśli `portfolios` przekroczy rozsądny rozmiar **i** FK da się odwrócić (D10).

**4. Port parsera w `core/`.** `core/import_parser.py` (wzorem `core/market_data.py:50`, port `MarketDataProvider`): `ImportParser` (`Protocol`), `ParsedRow`, `ParseResult`, `ImportParseError`. Adaptery per broker w `infrastructure/import_parsers/`, składane w `portfolios/wiring.py` (§2.1: Wiring może importować adaptery; wzór `assets/wiring.py:22`). `infrastructure/` zależy tylko od `core/` i `errors`.

**5. Waluta wyświetlania w `core_data` bez zależności od `assets`.** `core_data` przechowuje `display_currency_code` (`String(3)`, bez FK, format `^[A-Z]{3}$`). Konsument (`portfolios`, kokpit E3.4) rozwiązuje kod przez `assets`; nieznany kod → błąd z `code` `CURRENCY_NOT_FOUND` przy wycenie, nie przy zapisie ustawienia. **[propozycja]** — wariant z portem `CurrencyCatalog` zdefiniowanym w `core_data` odrzucony (pkt „Alternatywy”).

**6. Egzekwowanie** (testy w `core/tests/test_architecture.py`, w stylu istniejących; każdy z testem detektora, jak `test_cross_module_detector_catches_every_form`, `:503`):
- `ALLOWED_MODULE_DEPENDENCIES` = tabela z pkt 1; import `app.modules.<inny>` z `services/`, `repositories/`, `wiring.py`, `entrypoints.py` spoza tabeli → błąd; wyjątek `core_data → security` w liście legacy, która tylko maleje (jak `_LEGACY_R1_FASTAPI_IMPORTS`, `:47`).
- `infrastructure/` importuje z `app.*` tylko `app.core` i `app.infrastructure`.
- `core/` nie importuje `app.modules` ani `app.infrastructure`.

## Rozpatrywane alternatywy

- **Port `CurrencyCatalog` w `core_data` (walidacja kodu przy zapisie).** Daje `core_data → assets` w `wiring.py` i zamyka pętlę `assets.api → security → core_data → assets`. Lepszy komunikat błędu nie warte cyklu przy liściu. Odrzucone; wraca, jeśli walidacja przy zapisie okaże się potrzebna.
- **`notifications` wołające serwisy bezpośrednio.** Dozwolone przez ADR-0006, ale wiąże reguły alertów z DTO dwóch modułów. Odrzucone.
- **Osobny moduł `imports`.** Cykl FK z `portfolios`. Odrzucone teraz (D10).
- **Zdarzenia zamiast kierunków** (np. „ceny odświeżone” → alerty). Jeden proces; driver i tak sekwencjonuje zadania. Odrzucone ([ADR-0006](0006-cross-module-wylacznie-przez-serwisy.md), alternatywa „zdarzenia”).

## Konsekwencje

**Pozytywne**
- Graf jest jawną tabelą i testem; nowy kierunek wymaga zmiany testu, więc ADR-a.
- `assets` i `core_data` pozostają liśćmi — łatwe do testowania i późniejszego wydzielenia.

**Negatywne**
- Dług `core_data → security` pozostaje do osobnej decyzji (przeniesienie haszowania haseł do `core/`).
- `portfolios` rośnie (partie, snapshoty, import, grupy); plan nie dzieli jego serwisów — podział na pliki per zasób jest obowiązkiem implementacji.
- Walidacja waluty wyświetlania z opóźnieniem (przy wycenie, nie zapisie).

## Otwarte

- Czy `taxes → assets` jest potrzebne, czy wystarczy kraj/typ waloru w DTO `portfolios` — rozstrzygnąć przy E6.2 (PIT/ZG).
- Wydzielenie haszowania haseł z `security` do `core/` (usunięcie długu).
