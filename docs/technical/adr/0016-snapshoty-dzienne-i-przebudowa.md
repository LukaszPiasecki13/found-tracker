---
id: adr-0016-daily-snapshots-rebuild
status: Accepted
type: decision
scope: portfolios/snapshots-rebuild
last_reviewed: 2026-10-03
---

# Snapshoty dzienne są pochodną księgi; przebudowa jest per Portfel i startuje od daty najstarszej zmiany

Zmiana ustawia `dirty_from` Portfela; przebudowa kasuje wiersze od tej daty i liczy od nowa.

**Rozstrzyga:** D7 (reszta po [ADR-0015](0015-historia-cen-i-kursow.md)), część D15. **Blokuje:** E2.3, E2.5, E3.1.

## Kontekst

- Księga składa jeden Portfel (`domain/ledger.py:311`); kolejność (`operation_date`, `created_at`, `id`) (`repositories/operations.py:53-57`).
- Portfel to jeden rachunek bez przelewów, więc historie Portfeli są niezależne.
- Zmiana ceny/kursu z przeszłości wymaga daty, nie znacznika czasu. Schemat: [metodyka §10.4](../../research/05_metodyka_metryk.md).

## Decyzja

**1. Tabele** (pochodne; migracja `autogenerate`; typy `Decimal`, [ADR-0014](0014-numeryka-statystyk-float-i-numpy.md))
- `portfolios_daily` (PK `portfolio_id`, `day`): wartość, gotówka, przepływy, dochody, opłaty, `r_day`, `twr_index` `Numeric(24,12)`, `data_quality`.
- `portfolios_position_daily` (PK `portfolio_id`, `asset_id`, `day`): `quantity`, `price_local`, `mv_local`, `fx`, `mv_base`, `r_day`.
- `portfolios_portfolio.dirty_from` `Date` null: `day ≥ dirty_from` nieaktualne; `null` = aktualne.

**2. Kolejność zdarzeń:** (`operation_day`, `sequence`, `id`) ([ADR-0019](0019-migracje-danych-i-kolumny-dat.md)). `sequence` — numer w (Portfel, `operation_day`), nadawany przy zapisie.

**3. Unieważnianie**

| Zmiana | `dirty_from` Portfela | Kiedy |
|---|---|---|
| operacja: dodanie/usunięcie/edycja | `LEAST(dirty_from, operation_day)`; zmiana daty: `min(stara, nowa)` | w transakcji zapisu |
| cena/kurs z daty `d`, `priority`, cena `manual` | `LEAST(dirty_from, d)` dla Portfeli z walorem/parą od `d` | w `rebuild-dirty` |

Nowy dzień nie unieważnia; przebieg dopisuje brakujące dni.

**4. Orkiestracja w `portfolios/entrypoints.py`** (ADR-0002, [ADR-0013](0013-kierunki-zaleznosci-nowych-modulow.md)):
- `assets` zapisuje korekty historii do `assets_price_change` (`id`, `kind` `price|fx`, `asset_id` lub para walut, `changed_from` `Date`, `recorded_at`) — per walor/parę.
- `portfolios_market_cursor` (`last_change_id`). `rebuild_dirty` czyta zmiany po kursorze przez serwis `assets`, ustawia `dirty_from`, przebudowuje i przesuwa kursor — w jednej transakcji.

**5. Sync vs async**
- Księga zawsze synchronicznie.
- Snapshoty synchronicznie, gdy `dni(dirty_from → dziś) × otwarte pozycje ≤ 20 000` **[propozycja; kalibracja w E2.5]**. Powyżej: `BackgroundTasks` w `api/` rejestruje tylko `rebuild_dirty`; odczyt zwraca wiersze `< dirty_from` z `stale=true`.

**6. Przebudowa per Portfel.** Jeden przebieg, jeden `LedgerState`. Przed przebudową `SELECT … FOR UPDATE` wiersza Portfela w transakcji (nie blokady sesyjne — pooler transakcyjny); równoległy zapis operacji czeka. Błąd domenowy (`INSUFFICIENT_QUANTITY`/`INSUFFICIENT_CASH`) cofa transakcję (ADR-0001).

**7. Idempotencja.** Kasuje wiersze `≥ dirty_from`, wstawia nowe, zeruje `dirty_from`. Test: dwa przebiegi → identyczne wiersze; drugi = 0 zapisów.

## Alternatywy

- Znacznik czasu zamiast daty — nie wiadomo, od kiedy liczyć; odrzucone.
- Liczenie na żądanie — brak limitu wydajności; odrzucone.
- Zawsze async — nieaktualne liczby po operacji; odrzucone.

## Konsekwencje

- (+) Przebudowa deterministyczna, ograniczona do okna i do jednego Portfela.
- (−) Próg sync/async roboczy.

## Otwarte

- Mapowanie zmiany kursu na Portfele (para → Portfele z walutą w parze) — test E2.5.
