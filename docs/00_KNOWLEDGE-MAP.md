---
id: knowledge-map
status: current
type: reference
scope: docs/knowledge-map
last_reviewed: 2026-10-02
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
| **L4 — Dowody** | analizy, materiały źródłowe | [`research/`](./research/) |

> **Plan nie opisuje stanu systemu.** Stan opisuje wyłącznie warstwa L2 i kod. Dokumenty modułów zawierają tabelę „Stan vs cel” z przypisaniem do kroku planu.

## Od czego zacząć

| Zadanie | Kolejność czytania |
|---|---|
| Pierwszy kontakt z projektem | [`CONTEXT.md`](./business/CONTEXT.md) → [architektura backendu](./technical/backend/01_backend-architecture.md) → [plan refaktoryzacji](./plans/01_refaktoryzacja_do_wzorca_waterworks.md) |
| Zmiana w backendzie | [`CONTEXT.md`](./business/CONTEXT.md) → [architektura](./technical/backend/01_backend-architecture.md) → dokument modułu (niżej) → [wiring](./technical/backend/06_wiring_i_entrypointy.md) |
| Nowa operacja lub reguła portfela | [`05_portfolios_module.md`](./technical/backend/05_portfolios_module.md) → [ADR-0005 (domain)](./technical/adr/0005-warstwa-domeny.md) → testy parytetu `portfolios/tests/unit/test_ledger_parity.py` |
| Zmiana we frontendzie | [architektura frontendu](./technical/frontend/frontend-architecture.md) |
| Decyzja techniczna | [ADR-y techniczne](#adr-y-techniczne) |
| Nowa funkcja produktu (zakres „jak myfund, tylko lepiej”) | [roadmapa funkcjonalna](./plans/02_roadmapa_funkcjonalna.md) → etap w [E0–E5](./plans/03_roadmapa_etapy_E0-E5.md) / [E6–E11](./plans/04_roadmapa_etapy_E6-E11.md) → dowód L4 wskazany w kroku |

## L1 — Kanon

| Dokument | Co zawiera |
|---|---|
| [`business/CONTEXT.md`](./business/CONTEXT.md) | Słownik domeny: Portfel, Pozycja, Operacja, Walor, Klasa waloru, Waluta, Metryki. **Obowiązujące nazewnictwo** w kodzie, dokumentach i rozmowie |
| [`business/adr/`](./business/adr/README.md) | ADR-y biznesowe (wszystkie `Proposed`, decyzje właściciela D1–D15 z [roadmapy](./plans/02_roadmapa_funkcjonalna.md)): [0001 Portfel = rachunek](./business/adr/0001-portfel-jest-rachunkiem.md), [0002 koszt nabycia, partie FIFO](./business/adr/0002-koszt-nabycia-partie-fifo.md), [0003 gotówka wielowalutowa](./business/adr/0003-gotowka-wielowalutowa.md), [0004 metodologia stóp zwrotu](./business/adr/0004-metodologia-stop-zwrotu.md), [0005 daty i zdarzenie podatkowe](./business/adr/0005-daty-operacji-i-zdarzenie-podatkowe.md), [0006 zakres modułu podatkowego](./business/adr/0006-zakres-modulu-podatkowego.md), [0007 dane referencyjne i usuwanie](./business/adr/0007-dane-referencyjne-i-usuwanie.md) |

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
| [`0013`](./technical/adr/0013-kierunki-zaleznosci-nowych-modulow.md) | Nowe moduły `taxes`/`planning`/`notifications`: kierunki zależności; import w `portfolios` (propozycja) |
| [`0014`](./technical/adr/0014-numeryka-statystyk-float-i-numpy.md) | Księga i obligacje na `Decimal` w `domain/`; statystyki na `float`/numpy w `services/` (propozycja) |
| [`0015`](./technical/adr/0015-historia-cen-i-kursow.md) | Historia cen i kursów w bazie, nieskorygowana, ze źródłem (propozycja) |
| [`0016`](./technical/adr/0016-snapshoty-dzienne-i-przebudowa.md) | Snapshoty dzienne jako pochodna księgi; przebudowa od daty najstarszej zmiany, spójna składowa Portfeli (propozycja) |
| [`0017`](./technical/adr/0017-zadania-w-tle-i-cli.md) | Zadania w tle jako `python -m app.cli`, wołające tylko `entrypoints.py` (propozycja) |
| [`0018`](./technical/adr/0018-architektura-importu.md) | Import: szkic → zatwierdzenie → cofnięcie; parsery jako adaptery (propozycja) |
| [`0019`](./technical/adr/0019-migracje-danych-i-kolumny-dat.md) | Dane istniejące wypełnia `rebuild-all`; `operation_day` nową kolumną (propozycja) |

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
| [schemat danych docelowy](./technical/backend/07_schemat_danych_docelowy.md) | `draft` — projekt docelowy: core_data, assets, portfolios (tabele i kolumny dziś → docelowo) |
| [schemat danych — nowe moduły](./technical/backend/08_schemat_danych_nowe_moduly.md) | `draft` — projekt docelowy: security (tokeny), import, taxes, planning, notifications |
| [kontrakt API docelowy](./technical/backend/09_kontrakt_api_docelowy.md) | `draft` — projekt docelowy: ścieżki, koperty, paginacja, kody błędów |

### Frontend

| Dokument | Zakres kodu |
|---|---|
| [architektura frontendu](./technical/frontend/frontend-architecture.md) | `frontend/src/**` — opis stanu faktycznego (`draft`) |
| [IA i konwencje UI](./technical/frontend/ia-i-konwencje-ui.md) | `draft` — projekt docelowy: trasy, nawigacja, formatowanie, flagi jakości danych, kreator importu |

## Baza potwierdzonych ustaleń technicznych (`docs/knowledge_base/`)

Osobny zbiór od tej mapy: zdiagnozowane, potwierdzone zaskoczenia, jeden plik na problem. Zasady: [`knowledge_base/README.md`](./knowledge_base/README.md).

| Domena | Pliki dziś |
|---|---|
| `backend/` | [`except A, B:` w Pythonie 3.14](./knowledge_base/backend/python-314-except-bez-nawiasow.md) |

## L3 — Pamięć robocza

| Dokument | Status |
|---|---|
| [plan refaktoryzacji do wzorca waterworks](./plans/01_refaktoryzacja_do_wzorca_waterworks.md) | `draft` — kroki R-01…R-13 wykonane (2026-10-01) |
| [roadmapa funkcjonalna](./plans/02_roadmapa_funkcjonalna.md) | `draft` — etapy E0–E11, decyzje D1–D11 do ADR-ów; czeka na akceptację właściciela |
| [roadmapa — etapy E0–E5](./plans/03_roadmapa_etapy_E0-E5.md) | `draft` — naprawy, dane rynkowe, księga v2, analityka, import, instrumenty PL |
| [roadmapa — etapy E6–E11](./plans/04_roadmapa_etapy_E6-E11.md) | `draft` — PIT-38, ryzyko, zdarzenia korporacyjne, planowanie, powiadomienia, jakość |
| [archiwum: dawny plan architektury](./plans/archive/backend-architecture-plan.md) | Zastąpiony przez L2; do usunięcia za zgodą |

## L4 — Dowody

Badania z datą i źródłami; **nienormatywne** — rekomendacje stąd obowiązują dopiero przez ADR lub plan. Append-only: nowe badanie zastępuje stare dopiskiem, nie edycją.

| Dokument | Co zawiera (stan na 2026-10-01/02) |
|---|---|
| [`research/competitors/01_myfund.md`](./research/competitors/01_myfund.md) | myfund.pl: model danych, operacje, analityka, podatki, import, cennik, słabości |
| [`research/competitors/02_trackery_porownanie.md`](./research/competitors/02_trackery_porownanie.md) | Portfolio Performance, Ghostfolio, Wealthfolio, Sharesight, Snowball, Parqet, getquin i in.: macierz funkcji, pomysły do przejęcia, lekcje techniczne |
| [`research/03_rynek_pl_dane_i_obligacje.md`](./research/03_rynek_pl_dane_i_obligacje.md) | źródła danych rynkowych PL (NBP, Stooq, GPW, GUS), obligacje skarbowe i algorytmy wyceny |
| [`research/04_rynek_pl_podatki_i_brokerzy.md`](./research/04_rynek_pl_podatki_i_brokerzy.md) | PIT-38, FIFO, art. 11a, IKE/IKZE/PPK, formaty eksportu brokerów |
| [`research/05_metodyka_metryk.md`](./research/05_metodyka_metryk.md) | TWR, XIRR, ryzyko, benchmark, FIFO, dywidendy, rebalancing, projekcje, testy złote |
| [`research/06_stan_found-tracker_vs_cel.md`](./research/06_stan_found-tracker_vs_cel.md) | migawka kodu z 2026-10-01: defekty poprawności i luki G1…G25 względem myfund |

## Czego tu nie ma

- **Kontrakt API** (REST) jako osobny dokument — opisują go schematy w `backend/app/modules/*/schemas/` i dokumenty modułów.
- **`PRODUCT.md`** — kanon produktu w jednym miejscu; do czasu powstania zakres opisuje [`CONTEXT.md`](./business/CONTEXT.md).
- **Automatyczny walidator** — ręcznie: `python .claude/skills/knowledge-base/scripts/kb_validate.py --root . --strict`. Sekcja *Indeks dokumentów* poniżej pozostaje pusta, dopóki walidator nie wygeneruje jej (`--write-index`).

## Indeks dokumentów

<!-- KB-INDEX:START -->
<!-- Generowane przez: python kb_validate.py --root . --write-index -->
<!-- KB-INDEX:END -->
