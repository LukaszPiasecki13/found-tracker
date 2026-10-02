---
id: adr-0018-import-architecture
status: Proposed
type: decision
scope: portfolios/import
last_reviewed: 2026-10-02
---

# Import to potok szkic → zatwierdzenie → cofnięcie w `portfolios`; parsery są adapterami za portem `ImportParser` w `core/`

Plik trafia do `portfolios_import_batch` (hash + surowa treść), parser z `infrastructure/` zamienia go na wiersze pośrednie, serwis rozpoznaje walory, waliduje i oznacza duplikaty. Użytkownik przegląda szkic; zatwierdzenie zapisuje wszystkie Operacje **jednym rdzeniem bez commitu** i **jednym** przebiegiem przebudowy. Paczkę można cofnąć, o ile żadna jej Operacja nie została edytowana.

**Rozstrzyga:** część D10 i D15 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)); miejsce modułu — [ADR-0013](0013-kierunki-zaleznosci-nowych-modulow.md). **Blokuje:** E4.1, E4.2, E4.2a, E4.3. **Blokada zewnętrzna:** format eksportu myfund i pliki brokerów wymagają próbek od właściciela (E4.2a, E4.3).

## Kontekst

- `OperationService._record` otwiera własny `transaction()` (`backend/app/modules/portfolios/services/operations.py:99-100`), więc N Operacji = N commitów i N walidacji na bieżącym stanie; rdzenia `record_many` nie ma ([ADR-0008](0008-rdzenie-bez-commitu-w-operacjach-wielomodulowych.md)).
- Operacja nie ma `external_ref`, `import_batch_id` ani `edited_at` (`models/operation.py:25-69`); `update` nie odnotowuje edycji (`operations.py:128`).
- Wzorzec portu z adapterem już jest: `core/market_data.py:50` + `infrastructure/market_data/yahoo.py` + wybór w `assets/wiring.py:22`.
- Łańcuch walidacji i ekstraktory z testami na zanonimizowanych fiksturach: [trackery §10–11](../../research/competitors/02_trackery_porownanie.md); formaty brokerów: [podatki i brokerzy](../../research/04_rynek_pl_podatki_i_brokerzy.md).

## Decyzja

**1. Port w `core/import_parser.py`** (wzór `core/market_data.py`): `ImportParser` (`Protocol`: `parser_id`, `sniff(raw, filename) -> bool`, `parse(raw, options) -> ParseResult`), `ParsedRow` (numer wiersza, surowa etykieta, wskazówka typu, daty zawarcia/rozrachunku, `isin`, `ticker`, `exchange`, `name`, ilość, cena, kwota, prowizja, waluta, kurs, `external_ref`, surowe pola — liczby `Decimal`), `ImportParseError` (422, `code` `IMPORT_PARSE_FAILED`). Adaptery: `infrastructure/import_parsers/<broker>.py`, importują tylko `core/`. `portfolios/wiring.py` buduje rejestr `{parser_id: ImportParser}`; testy podstawiają fałszywe parsery.

**2. Tabele w `portfolios`** (migracja `autogenerate`, [ADR-0019](0019-migracje-danych-i-kolumny-dat.md))

| Tabela | Kolumny | Klucze |
|---|---|---|
| `portfolios_import_batch` | `id`, `owner_id` FK, `portfolio_id` FK, `parser_id` `String(40)`, `filename` `String(255)`, `file_sha256` `String(64)`, `raw_content` `LargeBinary`, `status` `String(20)` ∈ {`draft`,`committed`,`reverted`}, `created_at`, `committed_at` null, `reverted_at` null | częściowy UNIQUE (`portfolio_id`, `file_sha256`) `WHERE status <> 'reverted'` |
| `portfolios_import_row` | `id`, `batch_id` FK (kaskada), `row_no`, `raw_label` `String(100)`, `payload` `JSON`, pola sparsowane, `asset_id` null, `resolution` ∈ {`ok`,`duplicate`,`unresolved_asset`,`invalid`}, `skip` `Boolean`, `dedup_key` `String(120)`, `message`, `operation_id` null | UNIQUE (`batch_id`, `row_no`) |
| `portfolios_import_override` | `id`, `portfolio_id` FK, `match_key` `String(120)`, `field` `String(40)`, `value` `String(255)` | UNIQUE (`portfolio_id`, `match_key`, `field`) |

Na `portfolios_operation` dochodzą: `import_batch_id` FK null, `external_ref` `String(120)` null, `edited_at` `DateTime(tz)` null; częściowy UNIQUE (`portfolio_id`, `external_ref`) `WHERE external_ref IS NOT NULL`. Szkic jest w bazie, więc przeżywa odświeżenie strony (2 000 wierszy, filtry po `resolution`). Rozmiar pliku ≤ 10 MB **[propozycja]**; surowy plik właściciela nigdy nie trafia do repo.

**3. Potok** (`portfolios/services/imports.py`, `ImportService`; transakcja per krok):
1. `upload` — hash, zapis paczki, parser, wiersze; ponowny plik o tym samym hashu zwraca istniejącą paczkę (0 nowych Operacji).
2. **Rozpoznanie waloru** (`AssetService`, E1.3): `isin` → (`ticker`, `exchange`) → alias brokera jako wiersz `assets_listing` z `provider = 'import:<parser_id>'` ([ADR-0015](0015-historia-cen-i-kursow.md)) **[propozycja]**; reszta `unresolved_asset` z kandydatami. Mapowanie użytkownika zapisuje alias, więc następny import jest rozpoznany.
3. **Walidacja:** waluta, brutto = ilość × cena ± prowizja (tolerancja 0,01 **[propozycja]**), data, typ.
4. **Deduplikacja:** `external_ref`, a bez niego `dedup_key` = hash (`operation_day`, `isin` lub `asset_id`, ilość, kwota). Duplikat dostaje `skip = true`; użytkownik może to odwrócić.
5. `commit` — wymaga braku wierszy `unresolved_asset`/`invalid` bez `skip` (409 `IMPORT_UNRESOLVED_ROWS`).

**4. Zatwierdzenie = rdzeń `record_many` bez commitu.** `OperationService.record_many(drafts, owner_id)` ma docstring „No-commit core — transaction belongs to caller” (ADR-0008) i nie woła `transaction()`; `_record` rozdziela się na rdzeń + opakowanie z transakcją. `ImportService.commit` otwiera **jedną** transakcję: tworzy brakujące walory (rdzeń `get_or_create_by_ticker`), zapisuje Operacje z `import_batch_id`, ustawia `dirty_from = min(operation_day)` i wykonuje **jedną** przebudowę składowej ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)). Odrzucenie przez księgę cofa całość: 400 `IMPORT_COMMIT_REJECTED` z numerem pierwszego wiersza.

**5. Cofnięcie (D15).** `revert` usuwa Operacje paczki i przebudowuje; jeśli którakolwiek ma `edited_at IS NOT NULL` — 409 `IMPORT_BATCH_EDITED` z listą (nic nie jest usuwane). `OperationService.update` ustawia `edited_at` przy każdej faktycznej zmianie pola (`operations.py:128`).

**6. Nadpisania przy ponownym imporcie.** Poprawka użytkownika w szkicu (np. zmiana typu) zapisuje się w `portfolios_import_override` pod `match_key` (= `external_ref` lub `dedup_key`) i jest stosowana do sparsowanego wiersza przy każdym kolejnym imporcie. Operacja już zaksięgowana (nawet nieedytowana) nigdy nie jest nadpisywana: nowy wiersz o tym kluczu to `duplicate`; różnice wobec zapisu pokazuje podgląd (`changed_at_source`), domyślnie `skip` **[propozycja]**.

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
- Trzy nowe tabele i trzy kolumny w `portfolios_operation`; surowa treść w bazie zwiększa jej rozmiar.
- `portfolios` rośnie; import ma własny plik serwisu.

## Otwarte

- Próbki od właściciela: eksport myfund, wyciągi XTB/mBank/IBKR/DEGIRO/Trading212/Revolut, zanonimizowane — bez nich E4.2a/E4.3 nie ruszą.
- Nowe zależności parserów (XLSX, PDF) — wymagają zgody właściciela.
