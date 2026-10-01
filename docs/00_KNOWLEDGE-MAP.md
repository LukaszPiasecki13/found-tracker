---
id: knowledge-map
status: current
type: reference
scope: docs/knowledge-map
last_reviewed: 2026-10-01
---

# Mapa wiedzy — FundTracker

Jedyny punkt wejścia do dokumentacji projektu. Zanim zaczniesz czegokolwiek szukać w `docs/`, przeczytaj tę stronę i wejdź stąd bezpośrednio w potrzebny dokument. Wyszukiwanie pełnotekstowe po `docs/` jest ostatecznością — jeśli go potrzebujesz, ta mapa ma lukę i należy ją zgłosić.

Wzorzec architektury i organizacji dokumentacji pochodzi z projektu **waterworks-monitoring-platform** (źródło prawdy dla wzorca); FundTracker go dostosowuje, nie kopiuje (decyzje: [ADR-y techniczne](./technical/adr/)).

## Jak czytać tę bazę

Wiedza dzieli się na **warstwy według roli**. Przy sprzeczności wygrywa warstwa wyższa, a sama sprzeczność jest defektem do zgłoszenia.

| Warstwa | Rola | Gdzie w tym repo |
|---|---|---|
| **L0 — Konstytucja** | reguły zachowania agenta | [`CLAUDE.md`](../CLAUDE.md), [`.claude/rules/ai-tools/`](../.claude/rules/ai-tools/) |
| **L1 — Kanon** | słownik, decyzje produktowe | [`business/CONTEXT.md`](./business/CONTEXT.md), [`business/adr/`](./business/adr/README.md) |
| **L2 — Kontrakty** | architektura, moduły, ADR-y techniczne | [`technical/`](./technical/) |
| **L3 — Pamięć robocza** | plany zadań | [`plans/`](./plans/) |
| **L4 — Dowody** | analizy, materiały źródłowe | brak (nie istnieje) |

> **Plan nie opisuje stanu systemu.** Stan opisuje wyłącznie warstwa L2 i kod. Dokumenty modułów zawierają tabelę „Stan vs cel” z przypisaniem do kroku planu.

## Od czego zacząć

| Zadanie | Kolejność czytania |
|---|---|
| Pierwszy kontakt z projektem | [`CONTEXT.md`](./business/CONTEXT.md) → [architektura backendu](./technical/backend/01_backend-architecture.md) → [plan refaktoryzacji](./plans/01_refaktoryzacja_do_wzorca_waterworks.md) |
| Zmiana w backendzie | [`CONTEXT.md`](./business/CONTEXT.md) → [architektura](./technical/backend/01_backend-architecture.md) → dokument modułu (niżej) → [wiring](./technical/backend/06_wiring_i_entrypointy.md) |
| Nowa operacja lub reguła portfela | [`05_portfolios_module.md`](./technical/backend/05_portfolios_module.md) → [ADR-0005 (domain)](./technical/adr/0005-warstwa-domeny.md) → testy parytetu `portfolios/tests/unit/test_ledger_parity.py` |
| Zmiana we frontendzie | [architektura frontendu](./technical/frontend/frontend-architecture.md) |
| Decyzja techniczna | [ADR-y techniczne](#adr-y-techniczne) |

## L1 — Kanon

| Dokument | Co zawiera |
|---|---|
| [`business/CONTEXT.md`](./business/CONTEXT.md) | Słownik domeny: Portfel, Pozycja, Operacja, Walor, Klasa waloru, Waluta, Metryki. **Obowiązujące nazewnictwo** w kodzie, dokumentach i rozmowie |
| [`business/adr/`](./business/adr/README.md) | ADR-y biznesowe — dziś puste; konwencja numeracji |

## ADR-y techniczne

Numeracja w `docs/technical/adr/`, niezależna od biznesowych. Status ADR-a żyje w front-matterze (`status:`). Wszystkie poniższe mają status **Proposed** — akceptuje człowiek.

| Dokument | Decyzja |
|---|---|
| [`0001`](./technical/adr/0001-jedna-sesja-na-request.md) | Jedna sesja SQLAlchemy na żądanie; `transaction()` domyka jednostkę pracy; repozytorium nie commituje |
| [`0002`](./technical/adr/0002-sesja-poza-zadaniem-entrypointy-i-wiring.md) | Poza żądaniem sesję otwiera `entrypoints.py` przez `session_scope()`; serwisy składa wyłącznie `wiring.py` (R1–R8) |
| [`0003`](./technical/adr/0003-serwisy-zwracaja-encje-orm.md) | Serwisy CRUD zwracają encje ORM; DTO buduje FastAPI przez `response_model` |
| [`0004`](./technical/adr/0004-repozytoria-get-vs-find.md) | `find_*` zwraca `None`, `get_*` rzuca `NotFoundError` |
| [`0005`](./technical/adr/0005-warstwa-domeny.md) | Opcjonalna warstwa `domain/` (DOM-1–DOM-11); otwarte: `numpy` w domenie (kod realizuje wariant (a)) |
| [`0006`](./technical/adr/0006-cross-module-wylacznie-przez-serwisy.md) | Cross-module wyłącznie przez serwisy; API nie importuje repozytoriów |
| [`0007`](./technical/adr/0007-kontrakt-bledow-z-code.md) | Jedna hierarchia `APIError` z `code`, odpowiedź `{"detail","code"}` |
| [`0008`](./technical/adr/0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md) | Rdzenie bez commitu w operacjach wielomodułowych; transakcję trzyma orkiestrator |
| `0009` | Usunięty wraz z `backend-old/` (2026-10-01); numer nie jest ponownie używany |
| [`0010`](./technical/adr/0010-decimal-i-precyzja-pieniedzy.md) | `Decimal` dla kwot/cen/ilości/kursów; `float` tylko w wektorach do wykresów |
| [`0011`](./technical/adr/0011-audyt-odlozony.md) | Audyt zmian świadomie odłożony |
| [`0012`](./technical/adr/0012-jwt-odstepstwa-od-checklisty.md) | JWT: odstępstwa od security-checklist (HS256, `localStorage`, stateless refresh) |

## L2 — Kontrakty

### Backend

| Dokument | Zakres kodu |
|---|---|
| [architektura](./technical/backend/01_backend-architecture.md) | `backend/app/**` — warstwy, zakazy zależności, błędy, testy, stan vs cel |
| [`core_data`](./technical/backend/02_core_data_module.md) | `backend/app/modules/core_data/**` — użytkownicy |
| [`security`](./technical/backend/03_security_module.md) | `backend/app/modules/security/**` — logowanie, JWT, hasła |
| [`assets`](./technical/backend/04_assets_module.md) | `backend/app/modules/assets/**` — waluty, klasy, walory, dane rynkowe |
| [`portfolios`](./technical/backend/05_portfolios_module.md) | `backend/app/modules/portfolios/**` — portfele, pozycje, operacje, metryki |
| [wiring i entrypointy](./technical/backend/06_wiring_i_entrypointy.md) | `backend/app/modules/*/{wiring,entrypoints,dependencies}.py`, `main.py` |

### Frontend

| Dokument | Zakres kodu |
|---|---|
| [architektura frontendu](./technical/frontend/frontend-architecture.md) | `frontend/src/**` — opis stanu faktycznego (`draft`) |

## Baza potwierdzonych ustaleń technicznych (`docs/knowledge_base/`)

Osobny zbiór od tej mapy: zdiagnozowane, potwierdzone zaskoczenia, jeden plik na problem. Zasady: [`knowledge_base/README.md`](./knowledge_base/README.md).

| Domena | Pliki dziś |
|---|---|
| `backend/` | [`except A, B:` w Pythonie 3.14](./knowledge_base/backend/python-314-except-bez-nawiasow.md) |

## L3 — Pamięć robocza

| Dokument | Status |
|---|---|
| [plan refaktoryzacji do wzorca waterworks](./plans/01_refaktoryzacja_do_wzorca_waterworks.md) | `draft` — kroki R-01…R-13 wykonane (2026-10-01) |
| [archiwum: dawny plan architektury](./plans/archive/backend-architecture-plan.md) | Zastąpiony przez L2; do usunięcia za zgodą |

## Czego tu nie ma

- **Kontrakt API** (REST) jako osobny dokument — opisują go schematy w `backend/app/modules/*/schemas/` i dokumenty modułów.
- **`PRODUCT.md`** — kanon produktu w jednym miejscu; do czasu powstania zakres opisuje [`CONTEXT.md`](./business/CONTEXT.md).
- **Automatyczny walidator** — ręcznie: `python .claude/skills/knowledge-base/scripts/kb_validate.py --root . --strict`. Sekcja *Indeks dokumentów* poniżej pozostaje pusta, dopóki walidator nie wygeneruje jej (`--write-index`).

## Indeks dokumentów

<!-- KB-INDEX:START -->
<!-- Generowane przez: python kb_validate.py --root . --write-index -->
<!-- KB-INDEX:END -->
