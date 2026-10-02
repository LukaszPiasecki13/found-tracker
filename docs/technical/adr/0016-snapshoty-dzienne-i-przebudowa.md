---
id: adr-0016-daily-snapshots-rebuild
status: Proposed
type: decision
scope: portfolios/snapshots-rebuild
last_reviewed: 2026-10-02
---

# Snapshoty dzienne są pochodną księgi; przebudowa startuje od daty najstarszej zmiany i obejmuje całą spójną grupę Portfeli powiązanych przelewami

`portfolios_daily` i `portfolios_position_daily` da się w całości odtworzyć z Operacji, cen i kursów. Zmiana ustawia w Portfelu znacznik `dirty_from` (data najstarszej zmiany); przebudowa kasuje wiersze od tej daty i liczy je od nowa. Przelewy między Portfelami wiążą ich historie, więc przebudowa działa na **składowej spójnej** jednym przebiegiem po globalnie uporządkowanych zdarzeniach.

**Rozstrzyga:** D7 (reszta po [ADR-0015](0015-historia-cen-i-kursow.md)), problem przelewów z przeglądu, część D15. **Blokuje:** E2.3, E2.5, E3.1, E7.4.

## Kontekst

- Księga składa **jeden** Portfel: `PortfolioLedger.rebuild(operations)` (`backend/app/modules/portfolios/domain/ledger.py:311`), stan to jedno saldo (`LedgerState.cash_balance`, `:105`). Kolejność historii: (`operation_date`, `created_at`, `id`) (`repositories/operations.py:53-57`).
- Operacja kupna commituje sama (`services/operations.py:99-100`); edycja/usunięcie przebudowuje Portfel (`:128-155`, `_rebuild` `:187`).
- E2.3: przelew między Portfelami (D9: jeden wiersz z `counter_portfolio_id`). Historia B zawiera wpływ z A, a przelew papierów przenosi partie A → B z kosztem i datą nabycia — przebudowa A i B jest wzajemnie zależna.
- Zmiana ceny/kursu z przeszłości (korekta, uzupełnienie historii) wymaga **daty** najstarszej zmiany, nie znacznika czasu (przegląd roadmapy 2026-10-02, D7). Schemat snapshotów: [metodyka §10.4](../../research/05_metodyka_metryk.md).

## Decyzja

**1. Tabele (pochodne, odtwarzalne; migracja `autogenerate`)**
- `portfolios_daily` (PK `portfolio_id`, `snapshot_date` `Date`): wartość, gotówka, przepływy zewn. we/wy, dochody, opłaty, podatki, `r_day`, `twr_index` `Numeric(24,12)`, skumulowane przepływy, `data_quality`.
- `portfolios_position_daily` (PK `portfolio_id`, `asset_id`, `snapshot_date`): `qty`, `price_local`, `mv_local`, `fx`, `mv_base`, przepływy, `r_day` — wartość w walucie waloru i kurs są niezbędne dla efektu walutowego (E7.4).
- `portfolios_portfolio.dirty_from` `Date` null: wiersze o `snapshot_date ≥ dirty_from` są nieaktualne; `null` = aktualne.
- Typy: `Decimal` ([ADR-0014](0014-numeryka-statystyk-float-i-numpy.md)).

**2. Globalna kolejność zdarzeń:** (`operation_day`, `sequence`, `id`) ([ADR-0019](0019-migracje-danych-i-kolumny-dat.md)) — jeden porządek całkowity dla wszystkich Portfeli właściciela, zastępuje `operation_date`/`created_at`. Nowa operacja dostaje `sequence` = następny wolny numer dnia, chyba że klient poda własny **[propozycja]**.

**3. Unieważnianie od daty najstarszej zmiany**

| Zmiana | Ustawia `dirty_from` Portfela | Kiedy |
|---|---|---|
| operacja: dodanie / usunięcie / edycja | `LEAST(dirty_from, operation_day)`; przy zmianie daty — `min(stara, nowa)` | w tej samej transakcji co zapis |
| cena (`assets_price`) lub kurs (`assets_fx_rate`) z daty `d` | `LEAST(dirty_from, d)` dla Portfeli, które trzymały walor / używały pary od `d` | w przebiegu `rebuild-dirty` (pkt 4) |
| zmiana `assets_listing.priority`, cena `manual` | j.w., od najstarszej daty serii | j.w. |

Nowy dzień (nocny dopis ceny z datą > ostatnia znana) nie unieważnia; przebieg tylko **dopisuje** brakujące dni do dziś.

**4. Orkiestracja w `portfolios/entrypoints.py`** (ADR-0002; `assets` nie zależy od `portfolios`, [ADR-0013](0013-kierunki-zaleznosci-nowych-modulow.md)):
- `assets` zapisuje każdą korektę historii (zapis dla daty < najnowszej znanej w serii albo zmiana istniejącej wartości) do dziennika `assets_price_change` (`id` `BigInteger`, `kind` `price|fx`, `asset_id` albo para walut (null, gdy nie dotyczy), `changed_from` `Date`, `recorded_at` `DateTime(tz)`) — znacznik **per walor i per para**, nie globalny.
- `portfolios_market_cursor` (jeden wiersz: `last_change_id`) pamięta, co `portfolios` już przeliczył. Entrypoint `rebuild_dirty` czyta przez serwis `assets` zmiany po kursorze, mapuje je na Portfele (po pozycjach i walutach), ustawia `dirty_from`, przebudowuje i przesuwa kursor — **w jednej transakcji**.

**5. Synchroniczne vs asynchroniczne**
- Księga (pozycje, saldo, partie) zawsze **synchronicznie** w żądaniu (E0.3, `_rebuild`).
- Snapshoty: synchronicznie, gdy okno `dni(dirty_from → dziś) × otwarte pozycje ≤ 20 000` **[propozycja; próg skalibrować pomiarem E2.5 na 10 lat × 200 operacji × 30 walorów]**; powyżej — `dirty_from` zostaje, a `BackgroundTasks` w `api/` rejestruje wyłącznie entrypoint `rebuild_dirty` (R8). Odczyt zwraca wiersze `< dirty_from` i `stale=true` do czasu przebiegu.

**6. Przelewy — przebudowa składowej spójnej**
- Graf: Portfele = węzły, każdy przelew (`counter_portfolio_id`) = krawędź. `TransferGraph` w `portfolios/domain/` (czysta) wyznacza **składowe spójne** w oknie od `dirty_from`.
- Przebudowa składowej to **jeden przebieg po scalonym strumieniu zdarzeń** (pkt 2) z osobnym `LedgerState` na Portfel; przelew przetwarza się raz: wypływ z A, wpływ do B (partie przenoszone z kosztem i datą nabycia). Nie ma kolejności „A, potem B”, więc **cykl na poziomie Portfeli** (A→B dnia 1, B→A dnia 5) nie jest błędem — porządek całkowity zdarzeń go rozstrzyga.
- `dirty_from` składowej = minimum po jej członkach; po przebiegu wszystkie dostają `null`.
- Błędy (`code`, 400): `TRANSFER_SAME_PORTFOLIO` (A = B), `TRANSFER_CROSS_OWNER` (inny właściciel **[propozycja]**), `INSUFFICIENT_QUANTITY`/`INSUFFICIENT_CASH` z ledgera; każdy cofa całą składową (ADR-0001).
- Usunięcie Portfela z przelewami: blokada 409 `PORTFOLIO_HAS_TRANSFERS` (D15) **[propozycja]**; edycja/usunięcie przelewu w A przebudowuje składową z B.
- Współbieżność: `SELECT … FOR UPDATE` na wierszach `portfolios_portfolio` składowej w kolejności `id`.

**7. Idempotencja.** `rebuild` jest funkcją (Operacje, ceny, kursy, ustawienia): kasuje wiersze `≥ dirty_from`, wstawia nowe, zeruje `dirty_from`. Test (DoD pkt 8): dwa przebiegi → identyczne wiersze, bez kolumn `created_at`/`updated_at`; drugi przebieg bez zmian = 0 zapisów.

## Rozpatrywane alternatywy

- **Przebudowa Portfel po Portfelu w kolejności topologicznej.** Wymaga acyklicznego grafu; przelewy w obie strony w różnych dniach go łamią. Odrzucone.
- **Znacznik czasu `last_price_change_at` zamiast daty.** Nie wie, od kiedy liczyć. Odrzucone.
- **Liczenie na żądanie (dziś).** Brak limitu wydajności, sieć w żądaniu. Odrzucone.
- **Zawsze asynchronicznie.** Użytkownik widziałby nieaktualne liczby po każdej operacji. Odrzucone.

## Konsekwencje

**Pozytywne**
- Przebudowa jest deterministyczna i ograniczona do okna zmiany; przelewy nie wymagają wykrywania cykli.

**Negatywne**
- Składowa spójna może urosnąć (wszystkie Portfele spięte przelewami) — pełny koszt przebiegu rośnie.
- Dziennik zmian i kursor to dwie nowe tabele pomocnicze; próg sync/async jest roboczy.

## Otwarte

- Granularność mapowania zmiany kursu na Portfele (para → Portfele z walutą w parze) do potwierdzenia testem E2.5.
