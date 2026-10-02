---
id: adr-0018-import-architecture
status: Proposed
type: decision
scope: portfolios/import
last_reviewed: 2026-10-02
---

# Import to potok szkic → zatwierdzenie → cofnięcie w `portfolios`; parsery są adapterami za portem `ImportParser` w `core/`

Plik trafia do paczki `portfolios_import_batch` (plik, `sha256`, `parser_id`), parser z `infrastructure/` zamienia go na wiersze pośrednie, serwis rozpoznaje walory, waliduje i oznacza duplikaty. Użytkownik przegląda szkic; zatwierdzenie zapisuje wszystkie Operacje **jednym rdzeniem bez commitu** i **jednym** przebiegiem przebudowy. Paczkę można cofnąć, o ile żadna jej Operacja nie została edytowana.

**Rozstrzyga:** część D10 i D15 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)); miejsce modułu — [ADR-0013](0013-kierunki-zaleznosci-nowych-modulow.md). **Blokuje:** E4.1, E4.2, E4.2a, E4.3. **Blokada zewnętrzna:** format eksportu myfund i pliki brokerów wymagają próbek od właściciela (E4.2a, E4.3).

## Kontekst

- `OperationService._record` otwiera własny `transaction()` (`backend/app/modules/portfolios/services/operations.py:99-100`), więc N Operacji = N commitów i N walidacji na bieżącym stanie; rdzenia `record_many` nie ma ([ADR-0008](0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md)).
- Operacja nie ma `external_ref`, `import_batch_id` ani `edited_at` (`models/operation.py:25-69`); `update` nie odnotowuje edycji (`operations.py:128`).
- Wzorzec portu z adapterem już jest: `core/market_data.py:50` + `infrastructure/market_data/yahoo.py` + wybór w `assets/wiring.py:22`.
- Łańcuch walidacji i ekstraktory z testami na zanonimizowanych fiksturach: [trackery §10–11](../../research/competitors/02_trackery_porownanie.md); formaty brokerów: [podatki i brokerzy](../../research/04_rynek_pl_podatki_i_brokerzy.md).

## Decyzja

**1. Port w `core/import_parser.py`** (wzór `core/market_data.py`): `ImportParser` (`Protocol`: `parser_id`, `sniff(raw, filename) -> bool`, `parse(raw, options) -> ParseResult`), `ParsedRow` (numer wiersza, surowa etykieta, wskazówka typu, `operation_day`, `settlement_date`, `isin`, `ticker`, `exchange`, `name`, ilość, cena, kwota, prowizja, waluta, `fx_rate`, `external_ref`, surowe pola — liczby `Decimal`), `ImportParseError` (422, `code` `IMPORT_PARSE_FAILED`). Adaptery: `infrastructure/import_parsers/<broker>.py`, importują tylko `core/`. `portfolios/wiring.py` buduje rejestr `{parser_id: ImportParser}`; testy podstawiają fałszywe parsery.

**2. Tabele w `portfolios`** (migracja `autogenerate`, [ADR-0019](0019-migracje-danych-i-kolumny-dat.md); pełny wykaz kolumn: [`08_schemat_danych_nowe_moduly.md`](../backend/08_schemat_danych_nowe_moduly.md) §4, tu tylko klucze decyzji)

| Tabela | Kolumny | Klucze |
|---|---|---|
| `portfolios_import_batch` | `id`, `owner_id` FK, `portfolio_id` FK, `parser_id` `String(40)`, `filename` `String(255)`, `sha256` `String(64)`, `size_bytes`, plik (`LargeBinary`, ładowany leniwie), `status` `String(10)` ∈ {`draft`,`committed`,`reverted`}, `created_at`, `committed_at` null, `reverted_at` null | UNIQUE (`owner_id`, `sha256`): ten sam plik zwraca istniejącą paczkę; indeks (`portfolio_id`, `created_at` DESC) |
| `portfolios_import_row` | `id`, `batch_id` FK CASCADE, `row_no`, `raw_label` `String(200)`, `payload` `JSONB` (sparsowane pola, w tym `fx_rate`, `settlement_date`), `row_status` `String(12)` ∈ {`ok`,`duplicate`,`unrecognized`,`error`,`skip`}, `dedup_key` `String(120)`, `asset_id` null, `resolution` `JSONB` null (poprawka użytkownika zastosowana do wiersza) **[propozycja]**, `error_code`, `operation_id` null | UNIQUE (`batch_id`, `row_no`); indeks (`batch_id`, `row_status`) |
| `portfolios_import_override` | `id`, `portfolio_id` FK, `parser_id`, `match_key` `String(120)`, `field` `String(40)`, `value` `String(255)` | UNIQUE (`portfolio_id`, `parser_id`, `match_key`, `field`) |

Na `portfolios_operation` dochodzą: `import_batch_id` FK null (`ON DELETE RESTRICT`), `external_ref` `String(120)` null, `edited_at` `DateTime(tz)` null; częściowy UNIQUE (`portfolio_id`, `external_ref`) `WHERE external_ref IS NOT NULL`. Szkic jest w bazie, więc przeżywa odświeżenie strony (do 2 000 wierszy); lista wierszy: `limit`/`offset`, koperta `{items, total, limit, offset}`, filtr `row_status`. Rozmiar pliku ≤ 10 MB (`IMPORT_FILE_TOO_LARGE`) **[propozycja]**; plik właściciela nigdy nie trafia do repo.

**3. Potok** (`portfolios/services/imports.py`, `ImportService`; transakcja per krok):
1. `upload` — `sha256`, zapis paczki, parser, wiersze; ponowny plik o tym samym `sha256` zwraca istniejącą paczkę (0 nowych Operacji; nieznany `parser_id` → `IMPORT_PARSER_UNKNOWN`).
2. **Rozpoznanie waloru** (`AssetService`, E1.3): `isin` → (`ticker`, `exchange`) → alias brokera jako wiersz `assets_listing` z `provider = 'import:<parser_id>'` ([ADR-0015](0015-historia-cen-i-kursow.md)) **[propozycja]**; reszta wierszy `unrecognized` z kandydatami (`asset_candidates`). Mapowanie użytkownika zapisuje alias, więc następny import jest rozpoznany.
3. **Walidacja:** waluta, brutto = ilość × cena ± prowizja (tolerancja 0,01 **[propozycja]**), data, typ.
4. **Deduplikacja:** `external_ref`, a bez niego `dedup_key` = hash (`operation_day`, `isin` lub `asset_id`, ilość, kwota). Duplikat dostaje `row_status = duplicate` i nie jest zatwierdzany; użytkownik może to odwrócić (`ok`) albo pominąć wiersz (`skip`).
5. `commit` — wymaga braku wierszy `unrecognized`/`error` (409 `IMPORT_UNRESOLVED_ROWS`) i stanu `draft` (409 `IMPORT_BATCH_STATE_INVALID`).

**4. Zatwierdzenie = rdzeń `record_many` bez commitu.** `OperationService.record_many(drafts, owner_id)` ma docstring „No-commit core — transaction belongs to caller” (ADR-0008) i nie woła `transaction()`; `_record` rozdziela się na rdzeń + opakowanie z transakcją. `ImportService.commit` otwiera **jedną** transakcję: tworzy brakujące walory (rdzeń `get_or_create_by_ticker`), zapisuje Operacje z `import_batch_id`, ustawia `dirty_from = min(operation_day)` (przez `portfolios`) i wykonuje **jedną** przebudowę składowej ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)). Odrzucenie przez księgę cofa całość: 400 `IMPORT_COMMIT_REJECTED` z numerem pierwszego wiersza.

**5. Cofnięcie (D15).** `revert` usuwa Operacje paczki i przebudowuje; jeśli którakolwiek ma `edited_at IS NOT NULL` — 409 `IMPORT_BATCH_HAS_EDITS` z `params.operation_ids` (nic nie jest usuwane); niespójny wynik przebudowy → 409 `IMPORT_BATCH_REVERT_INVALID`. `OperationService.update` ustawia `edited_at` przy każdej faktycznej zmianie pola (`operations.py:128`).

**6. Nadpisania przy ponownym imporcie.** Poprawka użytkownika w szkicu (np. zmiana typu) zapisuje się w `portfolios_import_override` jako trójka (`match_key` = `external_ref` lub `dedup_key`, `field`, `value`) i jest stosowana do sparsowanego wiersza przy każdym kolejnym imporcie. Operacja już zaksięgowana (nawet nieedytowana) nigdy nie jest nadpisywana: nowy wiersz o tym kluczu to `duplicate`; różnice wobec zapisu pokazuje podgląd jako kod inline `CHANGED_AT_SOURCE` (HTTP 200), domyślnie `skip` **[propozycja]**.

## Rozpatrywane alternatywy

- **Zatwierdzanie przez N wywołań `record`.** N commitów, częściowy zapis przy błędzie, N przebudów. Odrzucone.
- **Surowy plik poza bazą (dysk).** Rozjazd z paczką i kopią zapasową; E4.5 eksportuje z bazy. Odrzucone.
- **Aktualizacja zaksięgowanych Operacji nowszym eksportem.** Niszczy ręczne poprawki. Odrzucone.
- **Parsery w `portfolios/services/`.** Wiążą logikę brokera z domeną i uniemożliwiają dodanie bibliotek PDF/XLSX poza `infrastructure/`. Odrzucone.

## Konsekwencje

**Pozytywne**
- Atomowy import z jednym `rebuild`; cofnięcie bez utraty ręcznych poprawek.
- Nowy broker = nowy adapter + wpis w rejestrze, bez zmian w serwisie.

**Negatywne**
- Trzy nowe tabele i trzy kolumny w `portfolios_operation`; plik w bazie zwiększa jej rozmiar. Plik `sha256` UNIQUE blokuje „nowa paczka z tego samego pliku” — poprawka pliku to nowy plik.
- `portfolios` rośnie; import ma własny plik serwisu.

## Otwarte

- Próbki od właściciela: eksport myfund, wyciągi XTB/mBank/IBKR/DEGIRO/Trading212/Revolut, zanonimizowane — bez nich E4.2a/E4.3 nie ruszą.
- Nowe zależności parserów (XLSX, PDF) — wymagają zgody właściciela.
