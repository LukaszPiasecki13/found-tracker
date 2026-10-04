---
id: be-import
status: current
last_reviewed: 2026-10-04
type: mixed
scope: backend/import
applies_to:
  - backend/app/core/import_parser.py
  - backend/app/infrastructure/import_parsers/**
  - backend/app/modules/portfolios/services/imports.py
  - backend/app/modules/portfolios/services/import_mapping.py
  - backend/app/modules/portfolios/api/imports.py
  - backend/app/modules/portfolios/repositories/imports.py
  - backend/app/modules/portfolios/models/import_batch.py
  - backend/app/modules/assets/services/assets.py
---

# Import danych z plików banków

Import pozwala wczytać eksport z banku lub domu maklerskiego i **sprawdzić, czy operacje i stan portfela zgadzają się z plikiem** — to główny cel (raport zgodności). Pierwszym źródłem jest raport XTB (`.xlsx`). Decyzja i uzasadnienie: [ADR-0018](../adr/0018-architektura-importu.md) (`Proposed`); ten dokument opisuje **kod**, w tym odstępstwa od ADR-a (§6). Operacje i księga: [`05_portfolios_module.md`](./05_portfolios_module.md).

## 1. Wzorzec: port, adapter, rejestr

```
core/import_parser.py            port: ImportParser (Protocol), ParsedRow, ParseIssue,
                                 ImportExpectations, ParseResult, ImportParseError
infrastructure/import_parsers/   adaptery (jedyne miejsce z openpyxl): XtbParser
portfolios/wiring.py             rejestr: build_import_parsers() -> (XtbParser(), ...)
portfolios/services/imports.py   ImportService — nie zna żadnego formatu pliku
```

- **Strategy + Registry:** `ImportService` bierze pierwszy parser z rejestru, którego `sniff(filename, content)` przyjmie plik. **Nowe źródło = nowy adapter + wpis w `build_import_parsers()`** — `ImportService` się nie zmienia (test: `test_a_new_source_needs_no_change_in_the_service`).
- **Adapter** zna tylko bibliotekę standardową, `openpyxl` i `app.core`; nie zna modułów, ORM ani `AssetService`. Zwraca wiersze neutralne wobec źródła (`ParsedRow`: typ operacji jako tekst wartości `OperationType`, surowy ticker i sufiks giełdy, ilość, cena, kwota, data UTC, `external_ref`). Egzekwuje to `core/tests/test_architecture.py`.
- **Mapowanie na aplikację** (ticker źródła → ticker aplikacji: `.PL` → `.WA`, `.US` → bez sufiksu, `.DE` → `.DE`; rozpoznanie waloru, deduplikacja, zapis) należy do `ImportService` i `import_mapping.py`. Raport zgodności liczy `ImportReconciler` (`import_reconciliation.py`).

## 2. Przepływ

**Do zatwierdzenia nic nie jest zapisywane**: ani plik, ani wiersze, ani walory. Podgląd liczy się w pamięci, a „Anuluj” lub powrót nie zostawiają śladu w bazie.

| Krok | Endpoint | Co się dzieje |
|---|---|---|
| podgląd | `POST /portfolios/{id}/imports/preview` (multipart `file`, ≤ 10 MB) | parser → wiersze; klasyfikacja; raport zgodności (§4); `existing_batch_id`, gdy ten sam plik był już zatwierdzony. **Nic nie jest zapisywane** |
| import | `POST /portfolios/{id}/imports` (ten sam plik ponownie) | pierwszy zapis: jedna transakcja — paczka (`committed`), wiersze, brakujące walory, operacje; jedna przebudowa portfela. Ten sam plik (sha256) = ta sama paczka (idempotentnie) |
| szczegóły | `GET /portfolios/{id}/imports/{batch}` | wiersze ze statusami + `reconciliation` |
| cofnięcie | `POST …/{batch}/revert` | usuwa operacje paczki, przebudowuje portfel i **usuwa samą paczkę** (plik i wiersze); odpowiedź ma status `reverted`, ale paczka już nie istnieje |
| lista | `GET /portfolios/{id}/imports` | zatwierdzone paczki portfela, bez pliku i wierszy |

Plik jest wysyłany dwa razy (podgląd, import): serwer niczego nie przechowuje między wywołaniami, więc import liczy wiersze od nowa na aktualnym stanie bazy (duplikaty, walory, dywidendy). Zapisana paczka ma zawsze status `committed`; `draft` (podgląd) i `reverted` (odpowiedź na cofnięcie) nigdy nie są zapisywane.

Wszystko jest scoped do właściciela; cudzy portfel lub paczka → 404. Metoda serwisu nazywa się `confirm` (test architektury zabrania wywołań `.commit(` poza granicą transakcji).

**Statusy wiersza:** `ok` (do zapisania; nieznane walory będą utworzone przy zatwierdzeniu), `duplicate` (operacja z tym `external_ref` już jest w portfelu), `unrecognized` (nieznany typ, brak tickera, zarchiwizowany walor, wiersz nieczytelny dla parsera), `error` (zarezerwowany; dziś żaden wiersz go nie dostaje), `skip` (kwota 0 — nic do zapisania). Zatwierdzenie blokują tylko `unrecognized` i `error` (409 `IMPORT_UNRESOLVED_ROWS`); `duplicate` i `skip` są pomijane.

**Transakcje (ADR-0001, ADR-0008):** `ImportService` trzyma `transaction()` swojego repozytorium i woła rdzenie bez commitu `OperationService.record_many_core` / `revert_import_batch_core`. Odrzucenie przez księgę (np. brak środków) → 400 `IMPORT_COMMIT_REJECTED` z numerem wiersza źródła; nic nie jest zapisane. Wyścig na unikalnym `external_ref` → 409 `CONCURRENT_CHANGE`.

**Cofnięcie:** operacja zmieniona ręcznie (`edited_at` ustawia `OperationService.update` przy faktycznej zmianie pola) blokuje cofnięcie — 409 `IMPORT_BATCH_HAS_EDITS` z id operacji, nic nie jest usuwane. Cofnięty plik można zaimportować od nowa, bo po cofnięciu nic z niego nie zostaje.

## 3. Adapter XTB

Operacje powstają z arkusza `Cash Operations` (źródło prawdy); jedynym wyjątkiem są splity (niżej). `Open Positions` i `Closed Positions` służą poza tym do oczekiwań. Kolumny są czytane po nagłówkach, nie po literach.

| Typ w XTB | Wynik | Uwagi |
|---|---|---|
| `Deposit` / `Withdrawal` | `deposit` / `withdrawal` | kwota bezwzględna; znak musi się zgadzać (wpłata +, wypłata −), inaczej wiersz `unrecognized` |
| `Stock purchase` / `Stock sell` | `buy` / `sell` | ilość i cena z `Comment` (`OPEN BUY 84 @ 40.710`, `CLOSE BUY 40/84 @ 40.730` — przy `40/84` ilością jest 40); kwota z kolumny `Amount` |
| `Dividend` | `dividend` | z walorem (ticker); gdy w dniu wypłaty nie ma otwartej pozycji (księga by odrzuciła), `ImportService` księguje ją jako `interest` bez waloru z komunikatem i notatką „Dividend TICKER: …” |
| `Free funds interest`, `Free funds interest tax`, `Withholding tax`, `SEC fee`, `Close trade` (CFD), `Swap` (CFD), `Correction` | `interest` gdy kwota > 0, `fee` gdy < 0 | gotówka bez waloru; notatka „Typ \| TICKER \| komentarz”. Nazwy typów znaczą tu „przychód / koszt gotówkowy”. Bez tych wierszy saldo konta nie zgadza się z brokerem, a księga odrzuca zakupy i wypłaty finansowane CFD i odsetkami |
| transfer pozycji w `Closed Positions` (komentarz „… Transfer Out”) | `split` | wiersz bez gotówki (`amount` 0), `ratio` = ilość pozycji otwartych przez transfer ÷ ilość zamkniętych; patrz niżej |
| inny typ | wiersz `unrecognized` | |

**Splity.** XTB księguje split jako transfer pozycji: stare pozycje są zamykane korektą z komentarzem „STC Transfer Out”, a nowe (ilość × `ratio`) otwierają się w ciągu godzin bez wiersza w `Cash Operations`. Bez tego późniejsze sprzedaże dotyczyłyby akcji, których księga nie widzi. Parser wykrywa transfer w `Closed Positions`, a pozycje po splicie zlicza z obu arkuszy (zamknięte i jeszcze otwarte), pomijając te, których otwarcie ma wiersz gotówkowy `OPEN`; okno to 6 godzin. Wiersz ma datę zamknięcia starych pozycji i numer po ostatnim wierszu `Cash Operations`. Transfer bez zmiany ilości (`ratio` 1) nie jest splitem, a transfer, po którym nie znaleziono nowych pozycji, to wiersz `unrecognized` (nieznany `ratio`).

- **Daty:** komórki daty czytane są jako `datetime` i uznawane za UTC; liczba (serial Excela, system 1900) jest przeliczana awaryjnie.
- **`external_ref`:** transakcje `xtb:pos:{Position ID}:{open|close}`, reszta `xtb:cash:{ID}`. Gdy ten sam ref ma kilka wierszy (zanonimizowane ID), dopisywany jest czas wiersza (i numer wystąpienia) — deterministycznie, więc ponowne wczytanie tego samego eksportu nadal się deduplikuje.
- **Waluta:** kwoty w pliku są w walucie konta (portfela), opłata 0 (kwota jest już netto). Gdy kwota transakcji różni się od ilość × cena o więcej niż 0,01 (akcje w USD/EUR kupione za PLN), `fx_rate = kwota / (ilość × cena)` — ledger księguje wtedy dokładnie kwotę z pliku, a wiersz ma komunikat o kursie. Dywidenda: `fx_rate = 1`, kwota w walucie konta.
- **Klasa waloru:** z kolumny `Category` (`STOCK` → `Stock`, `ETF` → `ETF`, inne → `Title`).
- **Bezpieczeństwo pliku:** przed otwarciem archiwum sprawdzane są łączny rozmiar po rozpakowaniu (≤ 50 MB), liczba wpisów (≤ 100) i stopień kompresji (≤ 100); arkusz ma ≤ 20 000 wierszy; skoroszyt otwierany jest `read_only`, `data_only`. Naruszenie → 422 `IMPORT_PARSE_FAILED`.

## 4. Raport zgodności

`ParseResult.expectations`: suma gotówki (wiersz `Total` arkusza Cash Operations), otwarte pozycje (arkusz Open Positions: ticker → ilość) i zrealizowany zysk (informacyjnie). `ImportService` porównuje je ze stanem portfela: dla podglądu — takim, jaki byłby po zatwierdzeniu (`OperationService.preview_state`, nic nie jest zapisywane), dla `committed` — rzeczywistym. Różnice: `cash_balance` (tolerancja 0,01 na każdą transakcję — źródło zaokrągla kwoty do groszy) i `position:{ticker}` (tolerancja 1e-6; walor spoza pliku też jest różnicą). Gdy księga odrzuciłaby historię, raport niesie `ledger_error` zamiast porównania. Raport ma sens dla portfela, który zawiera tylko to, co jest w pliku.

## 5. Kody błędów

| Status | `code` | Kiedy |
|---|---|---|
| 404 | `IMPORT_BATCH_NOT_FOUND` | paczka nie istnieje, cudza lub z innego portfela |
| 413 | `IMPORT_FILE_TOO_LARGE` | plik > 10 MB |
| 422 | `IMPORT_PARSER_UNKNOWN` | żaden parser nie czyta pliku |
| 422 | `IMPORT_PARSE_FAILED` | plik nieczytelny lub przekracza limity archiwum |
| 409 | `IMPORT_UNRESOLVED_ROWS` | import z wierszami `unrecognized`/`error` |
| 409 | `IMPORT_BATCH_STATE_INVALID` | cofnięcie paczki, która nie jest `committed` |
| 409 | `IMPORT_BATCH_HAS_EDITS` | cofnięcie, gdy operacja była edytowana ręcznie |
| 409 | `IMPORT_ALREADY_UPLOADED` | ten sam plik jest już paczką innego portfela |
| 400 | `IMPORT_COMMIT_REJECTED` | księga odrzuca historię; komunikat zaczyna się od `Row N` |

## 6. Stan vs cel i odstępstwa od ADR-0018

| Zagadnienie | ADR-0018 | Kod |
|---|---|---|
| Walory nieznane w bazie | zatwierdzenie tworzy brakujące | **tworzy** — nieznane walory (wiersz `ok` bez `asset_id`) są tworzone przy zatwierdzeniu przez `AssetService.get_or_create_by_ticker`; klasa waloru pochodzi z kolumny Category pliku (XTB) lub domyślnie "Stock"; waluta z notowań providera, fallback = waluta bazowa portfela |
| Ręczne poprawki wierszy (`import_override`) | tabela nadpisań | brak — rozwiązanie nie tworzy asset zaczyna się od ponownego wczytania pliku (podgląd i import klasyfikują wiersze od nowa) |
| Kolumny operacji | `operation_day`, `sequence`, `currency_id` | tylko `external_ref`, `import_batch_id`, `edited_at` ([ADR-0020](../adr/0020-plaski-model-operacji.md)); reszta poza zakresem |
| Typy operacji | — | nowe `interest`, `fee` (odsetki i podatek od odsetek nie są depozytem ani dywidendą) |
| Raport zgodności | — | dodany (§4); działa też dla podglądu (walory, które dopiero powstaną, mają w replayu ujemne id zastępcze) |
| Fallback `dedup_key` | porównanie hasza | hasz jest zapisywany w wierszu, ale deduplikacja działa po `external_ref` (porównanie po haszu uznałoby dwie identyczne, legalne operacje za duplikat) |
| Frontend | — | brak UI importu; lista operacji nie zna typów `interest`/`fee` |
| Migracja | `alembic revision --autogenerate` | do wygenerowania na lokalnej bazie (nie ma jej w tym środowisku) |
