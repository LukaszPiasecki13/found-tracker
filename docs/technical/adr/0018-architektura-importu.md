---
id: adr-0018-import-architecture
status: Proposed
type: decision
scope: portfolios/import
last_reviewed: 2026-10-02
---

# Import to potok szkic → zatwierdzenie → cofnięcie w `portfolios`; parsery są adapterami za portem `ImportParser` w `core/`

Plik trafia do paczki `portfolios_import_batch`, parser z `infrastructure/` zamienia go na wiersze, serwis rozpoznaje walory, waliduje i oznacza duplikaty. Zatwierdzenie zapisuje wszystkie Operacje jednym rdzeniem bez commitu i jedną przebudową. Paczkę można cofnąć, o ile żadna jej Operacja nie została edytowana.

**Rozstrzyga:** część D10 i D15 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)); moduł — [ADR-0013](0013-kierunki-zaleznosci-nowych-modulow.md). **Blokuje:** E4.1, E4.2, E4.2a, E4.3 (E4.2a, E4.3 także próbki od właściciela).

## Kontekst

- `OperationService._record` otwiera własny `transaction()` (`backend/app/modules/portfolios/services/operations.py:99-100`): N Operacji = N commitów; `record_many` nie ma ([ADR-0008](0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md)).
- Operacja nie ma `external_ref`, `import_batch_id`, `edited_at` (`models/operation.py:25-69`); `update` nie odnotowuje edycji (`operations.py:128`).

## Decyzja

**1. Port `core/import_parser.py`**: `ImportParser` (`Protocol`: `parser_id`, `sniff(raw, filename) -> bool`, `parse(raw, options) -> ParseResult`), `ParsedRow` (pola Operacji, `isin`/`ticker`/`exchange`, `external_ref`, surowe pola; liczby `Decimal`), `ImportParseError` (422, `IMPORT_PARSE_FAILED`). Adaptery: `infrastructure/import_parsers/<broker>.py` (importują tylko `core/`); rejestr `{parser_id: ImportParser}` buduje `portfolios/wiring.py`, wzorem `core/market_data.py:50`.

**2. Tabele** (`autogenerate`, [ADR-0019](0019-migracje-danych-i-kolumny-dat.md); kolumny: [`08_schemat_danych_nowe_moduly.md`](../backend/08_schemat_danych_nowe_moduly.md) §4):

| Tabela | Klucze decyzji |
|---|---|
| `portfolios_import_batch` | `parser_id`, `filename`, `sha256`, plik `LargeBinary` (leniwie), `status` ∈ {`draft`,`committed`,`reverted`}; UNIQUE (`owner_id`, `sha256`) |
| `portfolios_import_row` | `raw_cells` `JSONB`, `payload` `JSONB`, `row_status` ∈ {`ok`,`duplicate`,`unrecognized`,`error`,`skip`}, `dedup_key` `String(120)`, `asset_id`, `operation_id`; UNIQUE (`batch_id`, `row_no`) |
| `portfolios_import_override` | `match_key`, `field`, `value`; UNIQUE (`portfolio_id`, `parser_id`, `match_key`, `field`) |

`portfolios_operation` dostaje: `import_batch_id` FK null (`ON DELETE RESTRICT`), `external_ref` `String(120)` null, `edited_at` `DateTime(tz)` null; częściowy UNIQUE (`portfolio_id`, `external_ref`) `WHERE external_ref IS NOT NULL`. Szkic żyje w bazie (do 2 000 wierszy), lista wierszy stronicowana. Plik ≤ 10 MB (`IMPORT_FILE_TOO_LARGE`) **[propozycja]**.

**3. Potok** (`ImportService`, transakcja per krok):
1. `upload` — `sha256`, paczka, parser, wiersze; ten sam `sha256` zwraca istniejącą paczkę; nieznany `parser_id` → `IMPORT_PARSER_UNKNOWN`.
2. **Rozpoznanie waloru** (`AssetService`): `isin` → (`ticker`, `exchange`) → alias brokera jako `assets_listing` z `provider = 'import:<parser_id>'` ([ADR-0015](0015-historia-cen-i-kursow.md)) **[propozycja]**; reszta `unrecognized` z `asset_candidates`.
3. **Walidacja:** waluta, brutto = ilość × cena ± prowizja (tolerancja 0,01 **[propozycja]**), data, typ.
4. **Deduplikacja:** `external_ref`, a bez niego `dedup_key` = hash (`operation_day`, `isin` lub `asset_id`, ilość, kwota). Duplikat dostaje `duplicate` i nie jest zatwierdzany; użytkownik może przywrócić (`ok`) albo pominąć (`skip`).
5. `commit` — wymaga braku `unrecognized`/`error` (409 `IMPORT_UNRESOLVED_ROWS`) i stanu `draft` (409 `IMPORT_BATCH_STATE_INVALID`).

**4. Zatwierdzenie = `OperationService.record_many(drafts, owner_id)`** — rdzeń bez commitu (ADR-0008). `ImportService.commit` w **jednej** transakcji: tworzy brakujące walory, zapisuje Operacje z `import_batch_id`, ustawia `dirty_from = min(operation_day)`, robi **jedną** przebudowę ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)). Odrzucenie przez księgę cofa całość: 400 `IMPORT_COMMIT_REJECTED` z numerem pierwszego wiersza.

**5. Cofnięcie (D15).** `revert` usuwa Operacje paczki i przebudowuje; przy dowolnym `edited_at IS NOT NULL` — 409 `IMPORT_BATCH_HAS_EDITS` z `params.operation_ids`, nic nie jest usuwane; niespójna przebudowa — 409 `IMPORT_BATCH_REVERT_INVALID`. `OperationService.update` ustawia `edited_at` przy każdej faktycznej zmianie pola.

**6. Nadpisania.** Poprawka użytkownika w szkicu zapisuje się w `portfolios_import_override` (`match_key` = `external_ref` lub `dedup_key`, `field`, `value`) i działa przy kolejnych importach. Zaksięgowana Operacja nigdy nie jest nadpisywana: nowy wiersz o tym kluczu to `duplicate`; różnice pokazuje podgląd jako `CHANGED_AT_SOURCE` (HTTP 200), domyślnie `skip` **[propozycja]**.

## Rozpatrywane alternatywy

- N wywołań `record` — N commitów, częściowy zapis, N przebudów.
- Plik na dysku — rozjazd z paczką i kopią.
- Aktualizacja zaksięgowanych Operacji nowszym eksportem — niszczy ręczne poprawki.
- Parsery w `portfolios/services/` — broker wiązany z domeną.

## Konsekwencje

- (+) Atomowy import, jeden `rebuild`; cofnięcie bez utraty poprawek; nowy broker = nowy adapter.
- (−) Trzy tabele, plik w bazie; poprawiony plik to nowa paczka.

## Otwarte

- Zanonimizowane próbki od właściciela (myfund, brokerzy).
- Nowe zależności parserów (XLSX, PDF) — zgoda właściciela.
