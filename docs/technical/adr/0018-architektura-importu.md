---
id: adr-0018-import-architecture
status: Proposed
type: decision
scope: portfolios/import
last_reviewed: 2026-10-03
---

# Import to paczka z cofnięciem w `portfolios`; parser jest adapterem za portem `ImportParser`, pierwszy adapter to XTB

**Implementacja później:** ten ADR ustala kształt, nic z niego nie jest jeszcze zbudowane. Najpierw tylko adapter XTB; kolejne źródła później.

Plik trafia do paczki `portfolios_import_batch`, parser zamienia go na wiersze, serwis rozpoznaje walory, waliduje i oznacza duplikaty. Zatwierdzenie zapisuje wszystkie Operacje jednym rdzeniem bez commitu i jedną przebudową. Paczkę można cofnąć, o ile żadna jej Operacja nie została edytowana.

## Kontekst

- `OperationService._record` otwiera własny `transaction()` (`backend/app/modules/portfolios/services/operations.py:99-100`): N Operacji = N commitów; `record_many` nie ma ([ADR-0008](0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md)).
- Operacja nie ma `external_ref`, `import_batch_id`, `edited_at` (`models/operation.py:25-69`); `update` nie odnotowuje edycji (`operations.py:128`).

## Decyzja

1. **Port `core/import_parser.py`**: `ImportParser` (`Protocol`: `parser_id`, `sniff(raw, filename) -> bool`, `parse(raw, options) -> ParseResult`), `ParsedRow` (pola Operacji, `isin`/`ticker`, `external_ref`; liczby `Decimal`), `ImportParseError` (422, `IMPORT_PARSE_FAILED`). Adapter XTB: `infrastructure/import_parsers/xtb.py` (importuje tylko `core/`); rejestr `{parser_id: ImportParser}` buduje `portfolios/wiring.py`.
2. **Tabele** (`autogenerate`, [ADR-0019](0019-migracje-danych-i-kolumny-dat.md)): `portfolios_import_batch` (`parser_id`, `filename`, `sha256`, plik `LargeBinary`, `status` ∈ {`draft`,`committed`,`reverted`}; UNIQUE (`owner_id`, `sha256`)), `portfolios_import_row` (`raw_cells`/`payload` `JSONB`, `row_status` ∈ {`ok`,`duplicate`,`unrecognized`,`error`,`skip`}, `dedup_key`, `asset_id`, `operation_id`) i `portfolios_import_override` (`match_key`, `field`, `value`). `portfolios_operation` dostaje `import_batch_id`, `external_ref`, `edited_at` ([ADR-0020](0020-plaski-model-operacji.md)); częściowy UNIQUE (`portfolio_id`, `external_ref`) `WHERE external_ref IS NOT NULL`. Plik ≤ 10 MB (`IMPORT_FILE_TOO_LARGE`) **[propozycja]**.
3. **Potok** (`ImportService`, transakcja per krok):
   1. `upload` — `sha256`, paczka, parser, wiersze; ten sam `sha256` zwraca istniejącą paczkę; nieznany `parser_id` → `IMPORT_PARSER_UNKNOWN`.
   2. **Rozpoznanie waloru** (`AssetService`): `isin` → (`ticker`, `exchange`); reszta `unrecognized` z `asset_candidates`.
   3. **Walidacja:** waluta, brutto = ilość × cena ± prowizja (tolerancja 0,01 **[propozycja]**), data, typ.
   4. **Deduplikacja:** `external_ref`, a bez niego `dedup_key` = hash (`operation_day`, `isin` lub `asset_id`, ilość, kwota). Duplikat dostaje `duplicate` i nie jest zatwierdzany; użytkownik może przywrócić (`ok`) albo pominąć (`skip`).
   5. `commit` — wymaga braku `unrecognized`/`error` (409 `IMPORT_UNRESOLVED_ROWS`) i stanu `draft` (409 `IMPORT_BATCH_STATE_INVALID`).
4. **Zatwierdzenie = `OperationService.record_many(drafts, owner_id)`** — rdzeń bez commitu (ADR-0008). `commit` w **jednej** transakcji: tworzy brakujące walory, zapisuje Operacje z `import_batch_id`, ustawia `dirty_from = min(operation_day)`, robi **jedną** przebudowę ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)). Odrzucenie przez księgę cofa całość: 400 `IMPORT_COMMIT_REJECTED` z numerem pierwszego wiersza.
5. **Cofnięcie.** `revert` usuwa Operacje paczki i przebudowuje; przy dowolnym `edited_at IS NOT NULL` — 409 `IMPORT_BATCH_HAS_EDITS` z `params.operation_ids`, nic nie jest usuwane. `OperationService.update` ustawia `edited_at` przy każdej faktycznej zmianie pola.
6. **Nadpisania.** Poprawka użytkownika w szkicu zapisuje się w `portfolios_import_override` (`match_key` = `external_ref` lub `dedup_key`) i działa przy kolejnych importach. Zaksięgowana Operacja nigdy nie jest nadpisywana: nowy wiersz o tym kluczu to `duplicate`; różnice pokazuje podgląd jako `CHANGED_AT_SOURCE` (HTTP 200), domyślnie `skip` **[propozycja]**.

## Rozpatrywane alternatywy

- N wywołań `record` — N commitów, częściowy zapis, N przebudów.
- Plik na dysku — rozjazd z paczką i kopią.
- Aktualizacja zaksięgowanych Operacji nowszym eksportem — niszczy ręczne poprawki.

## Konsekwencje

- (+) Atomowy import, jeden `rebuild`; cofnięcie bez utraty poprawek; nowe źródło = nowy adapter.
- (−) Trzy tabele, plik w bazie; poprawiony plik to nowa paczka.

## Otwarte

- Zanonimizowana próbka eksportu XTB od właściciela; zgoda na nowe zależności parsera (np. XLSX), jeśli eksport ich wymaga.
