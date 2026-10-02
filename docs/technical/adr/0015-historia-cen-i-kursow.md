---
id: adr-0015-price-and-fx-history
status: Proposed
type: decision
scope: assets/price-fx-history
last_reviewed: 2026-10-02
---

# Ceny i kursy walut są historią w bazie (`assets_price`, `assets_fx_rate`), nieskorygowaną i z jawnym źródłem; „bieżąca cena” jest pochodną

Moduł `assets` przechowuje dzienne zamknięcia i kursy jako fakty z źródłem i flagą `is_synthetic`. Kurs krzyżowy liczy serwis `portfolios` i przekazuje domenie jako mapę. Każde zdarzenie ma do trzech kursów o różnym przeznaczeniu. `Currency.exchange_rate` i `Asset.current_price` przestają być źródłem prawdy.

**Rozstrzyga:** D5 i część D7 ([roadmapa](../../plans/02_roadmapa_funkcjonalna.md)); reszta D7 — [ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md). **Blokuje:** E0.1 (mapa kursów), E1.1, E1.2, E1.5, E2.3, E6.

## Kontekst

- Wycena czyta pola-skalary: `holding.asset.current_price` i `holding.asset.currency.exchange_rate` (`backend/app/modules/portfolios/domain/valuation.py:55-57`). Odświeżenie nadpisuje je w miejscu (`backend/app/modules/assets/services/market_data.py:105`, `:127`), a `GET /portfolios/positions` robi to synchronicznie (`backend/app/modules/portfolios/services/positions.py:37-39`).
- Kursy są względem waluty systemowej (`DEFAULT_CURRENCY_CODE = "USD"`, `assets/constants.py:4`); kurs krzyżowy nie istnieje (F1, F4 w [stanie vs cel](../../research/06_stan_found-tracker_vs_cel.md)).
- Port ma już `fetch_close_history` (`backend/app/core/market_data.py:50`), ale adapter wywołuje `history(start, end, interval="1d")` bez jawnego `auto_adjust` (`backend/app/infrastructure/market_data/yahoo.py:64`); domyślne zachowanie `yfinance` 1.3.0 (`requirements.txt:73`) **[niezweryfikowane]**.
- Operacja ma jeden kurs, `fx_rate` (`backend/app/modules/portfolios/models/operation.py:52`), a podatek wymaga kursu NBP D−1 z numerem tabeli ([dane PL §1.2](../../research/03_rynek_pl_dane_i_obligacje.md), [podatki](../../research/04_rynek_pl_podatki_i_brokerzy.md)).

## Decyzja

**1. Tabele w `assets`** (modele zarejestrowane w `models_registry.py`; migracja `autogenerate`, [ADR-0019](0019-migracje-danych-i-kolumny-dat.md)):

| Tabela | Kolumny (typ) | Klucze i indeksy |
|---|---|---|
| `assets_price` | `id`, `asset_id` FK, `price_date` `Date`, `close` `Numeric(18,9)`, `currency_id` FK (waluta notowania), `source` `String(20)`, `is_synthetic` `Boolean` default false, `fetched_at` `DateTime(tz)` | UNIQUE (`asset_id`, `price_date`, `source`); indeks (`asset_id`, `price_date` DESC) |
| `assets_fx_rate` | `id`, `from_currency_id` FK, `to_currency_id` FK, `rate_date` `Date`, `rate` `Numeric(18,9)`, `source` `String(20)`, `table_no` `String(30)` null (np. `187/A/NBP/2026`), `fetched_at` | UNIQUE (`from`, `to`, `rate_date`, `source`); indeks (`from`, `to`, `rate_date` DESC) |
| `assets_listing` | `asset_id`, `provider` `String(20)`, `symbol` `String(40)`, `priority` `SmallInteger` | UNIQUE (`asset_id`, `provider`) |

`rate` = jednostek `to` za jedną `from` (kontrakt `fetch_fx_rate`, `core/market_data.py`). NBP (tabela A, `mid`) zapisuje pary `XXX → PLN`; Yahoo — wg adaptera.

**2. Ceny nieskorygowane.** Adapter przekazuje `auto_adjust=False` jawnie i czyta kolumnę `Close`, nie `Adj Close`. **Test kontraktowy** na nagranej odpowiedzi dla waloru po splicie (walor wybrany przy E1.2): cena sprzed splitu zgadza się z notowaniem historycznym, nie z przeliczoną. Split jest zdarzeniem w księdze (E8.1), więc skorygowana cena liczyłaby go dwa razy.

**3. Źródło i `is_synthetic`.** `source` ∈ {`manual`, `nbp`, `yahoo`, `stooq`, …}. `is_synthetic = true` oznacza wartość **nie będącą oficjalnym zamknięciem**: cena bieżąca zapisana jako wiersz dnia przed końcem sesji (nadpisywana przy następnym odświeżeniu), wartość wyliczona (obligacje E5.1, lokaty E5.5) lub ręczne oszacowanie. Forward-fill **nie jest zapisywany**: `find_close(asset, date)` zwraca ostatnie zamknięcie ≤ `date` z `price_date`, i flagą `stale` (próg z E0.9). **[propozycja]**

**4. Priorytet źródeł per walor.** Efektywna cena dnia = wiersz o najniższej randze: `manual` = 0 (zawsze najwyższy, bez wpisu w `assets_listing`), dostawca = `assets_listing.priority` ≥ 1, nieznane źródło = 1000. Zmiana `priority` lub dodanie ceny `manual` jest zmianą ceny od najstarszej daty, której dotyczy ([ADR-0016](0016-snapshoty-dzienne-i-przebudowa.md)).

**5. „Ostatnia cena” jako pochodna.**
- `Asset.current_price` (`models/assets.py:29`) i `Currency.exchange_rate` (`models/currencies.py:20`) zostają jako **kolumny-cache**, ustawiane wyłącznie przez serwis `assets` przy zapisie wiersza o najnowszej dacie (ta sama transakcja). Pola API `current_price`/`exchange_rate` (`schemas/assets.py:92`, `schemas/currencies.py:19`) bez zmiany kontraktu.
- Ręczna edycja (`AssetUpdateRequest.current_price`, `schemas/assets.py:58`) zapisuje wiersz `source=manual` z dzisiejszą datą; cache wynika z niego.
- Czytelnicy (wycena, pozycje) przechodzą na `find_close`/mapę kursów; usunięcie kolumn — osobny ADR po E3.

**6. Kurs krzyżowy w `portfolios`.** Serwis `portfolios` (`FxMapBuilder`) pyta `assets` o pary bezpośrednie (para → odwrotność → przez pivot z listy [PLN, waluta systemowa] **[propozycja]**) i składa mapę `{(z, do): Decimal}` na dzień wyceny. `domain/` dostaje tylko mapę, bez portu i I/O (ADR-0005, E0.1). Kurs krzyżowy nie jest zapisywany; przy pivocie innym niż NBP odpowiedź niesie `data_quality`.

**7. Trzy kursy na zdarzenie (D5)**

| Kurs | Kolumna / miejsce | Źródło | Do czego |
|---|---|---|---|
| brokera | `portfolios_operation.fx_rate` (istnieje) | wyciąg / użytkownik | księga, gotówka |
| wyceny | `portfolios_position_daily.fx` (ADR-0016) | `assets_fx_rate` wg priorytetu | wartość, wykresy |
| podatkowy | `fx_rate_tax` `Numeric(18,9)`, `fx_tax_table_no` `String(30)`, `fx_tax_effective_date` `Date` (wszystkie null) na Operacji | NBP tabela A, `effectiveDate` < data podatkowa, cofanie po 404 | PIT-38 |

Data podatkowa = `settlement_date` (D12), dla dywidendy dzień wypłaty. Kurs D−1 jest zawsze już opublikowany dla dat ≤ dziś; dla przyszłej daty rozrachunku pola zostają `null`, a `refresh-fx` ([ADR-0017](0017-zadania-w-tle-i-cli.md)) wypełnia `fx_rate_tax IS NULL AND data ≤ dziś`.

## Rozpatrywane alternatywy

- **Zapis forward-fill jako wierszy `is_synthetic`.** Mnoży wiersze i trzeba je unieważniać po każdej nowej cenie. Odrzucone.
- **Priorytet jako kolumna w `assets_price`.** Duplikuje regułę w każdym wierszu; zmiana priorytetu = przepisanie tabeli. Odrzucone.
- **Jedna para kursów względem USD (dziś).** Podatek wymaga NBP/PLN z numerem tabeli. Odrzucone.
- **Skorygowane ceny + korekta splitu w księdze.** Podwójne ujęcie splitu ([ryzyka w planie](../../plans/02_roadmapa_funkcjonalna.md)). Odrzucone.

## Konsekwencje

**Pozytywne**
- Wyceny i wykresy bez sieci w żądaniu; numer tabeli NBP jest dowodem dla urzędu.

**Negatywne**
- Dwa źródła prawdy w okresie przejściowym (cache + historia); odpowiada za to jedna ścieżka zapisu.
- Reguła pivotu i definicja `is_synthetic` są robocze.

## Otwarte

- Wybór waloru do testu kontraktowego splitu; zachowanie `auto_adjust` w `yfinance` 1.3.0 — zweryfikować w E1.2.
- Kurs krzyżowy, gdy brak kursu dla pary w ogóle (nowa waluta ma dziś domyślnie 1): błąd z `code` czy `data_quality` (E0.1).
