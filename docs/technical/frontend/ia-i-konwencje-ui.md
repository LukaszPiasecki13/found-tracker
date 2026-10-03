---
id: fe-ia-ui-conventions
status: draft
type: mixed
scope: frontend/ia-ui
last_reviewed: 2026-10-03
---

# Jak zorganizowane są ekrany, trasy i konwencje UI frontendu FundTrackera?

> **Projekt docelowy (L2, draft).** Opisuje stan docelowy wynikający z roadmapy ([plan](../../plans/02_roadmapa_funkcjonalna.md)), nie stan kodu — ten opisują dokumenty modułów i kod. Obowiązuje po akceptacji ADR-ów, na które się powołuje.

Dokument zamyka luki frontendowe znalezione w przeglądzie roadmapy: brak mapy ekranów, trasy po nazwie, rozproszone formatowanie, brak słownika flag jakości danych, brak decyzji o bibliotece wykresów, kliencie API i testach. Stan faktyczny frontendu: [architektura frontendu](./frontend-architecture.md). Kroki: [E0–E5](../../plans/03_roadmapa_etapy_E0-E5.md); pozostałe etapy w [planie](../../plans/02_roadmapa_funkcjonalna.md). Zasady produktowe: P2 (metodologia w UI), P6 (kokpit → Portfel → walor → operacja, mobile do przeglądania), P7 (jakość danych widoczna).

Konwencja oznaczeń: **[propozycja]** = decyzja, której plan nie rozstrzyga (zebrane w „Otwarte punkty”). Nowe pojęcia słownikowe (Grupa portfeli, Przewalutowanie, Partia, Paczka importu) są **proponowane** (D3). Nazwy nowych endpointów (poza `performance`, E3.1) są roboczymi propozycjami; źródłem prawdy będzie dokument kontraktu API.

## 1. Mapa ekranów i tras

### 1.1 Stan dzisiejszy (z kodu)

| Fakt | Źródło |
|---|---|
| Trasy chronione: `/`, `/pockets/:slug`, `/pockets/:slug/history`, `/pockets/:slug/charts`, `/compare`, `/operations`; publiczne `/login`, `/register`; fallback `*` → `/` | `App.tsx:26-27,31,42,53,64,75,86,97` |
| Portfel w URL to **nazwa** (`encodeURIComponent(name)`), a strony wołają endpointy po nazwie | `sidebar.tsx:109`, `PocketsList.tsx:36`, `PocketDetailsPage.tsx:28-30`, `positionService.ts:7`, `operationService.ts:7`, `analyticsService.ts:16` |
| Nazwę można zmienić (`PUT/PATCH /portfolios/{id}`), więc link po nazwie się psuje | `portfolios.py:57-58`, `PortfolioUpdateRequest.name` (`schemas/portfolios.py`) |
| Dwie nawigacje, które się rozjeżdżają: sidebar (Dashboard, Operacje, Porównaj portfele, „Moje Portfele”) i zakładki nagłówka (Dashboard, **Portfele** i **Analizy** bez linku, Operacje) | `sidebar.tsx:35-39,75-120`, `dashboard-header.tsx:75-80` |
| Martwe odwołania: `/analytics`, `/alerts` w `getTabValue`; link `/settings` bez trasy (wpada w fallback `*`) | `dashboard-header.tsx:47-55,94`, `App.tsx:97` |
| Mobile: wysuwane menu (`Drawer temporary` poniżej `md`) + hamburger; bez dolnej nawigacji, bez manifestu PWA | `sidebar.tsx:43,130-141`, `dashboard-header.tsx:61-70`, `index.html` |
| Brak ekranów: widok waloru, struktura, wyniki, dywidendy, import, dane, ustawienia, metodologia | `src/pages/` (8 plików) |

### 1.2 Drzewo docelowe

Zasada: **URL jest źródłem prawdy o zakresie** (Portfel / Grupa / „Wszystkie”); analityka żyje w zakładkach zakresu, nie w globalnych pozycjach menu (inaczej „Struktura” w sidebarze byłaby dwuznaczna).

```
/                               Kokpit (wszystkie Portfele, waluta wyświetlania)        E3.4
/portfolios/:id                 Portfel  — zakładki:
    (domyślna) Pozycje          /portfolios/:id
    operations                  Historia operacji (filtry, paginacja)                    E2.7
    allocation                  Struktura                                                E3.3
    performance                 Wyniki (TWR, XIRR, benchmark, wykresy)                   E3.1, E3.5
    income                      Dywidendy i odsetki                                      E3.6
    closed                      Zamknięte pozycje                                        E3.2
/groups/:id                     Grupa portfeli — te same zakładki bez „operations"      E2.1
/groups/all                     „Wszystkie portfele" (wirtualna Grupa) [propozycja]
/assets/:id                     Widok waloru (opcjonalnie ?portfolio=<id>)               E3.8
/operations                     Historia operacji ze wszystkich Portfeli                 E2.7
/compare                        Porównanie Portfeli na TWR                               E3.5
/import                         Lista paczek importu (później, XTB)
/import/new, /import/:batchId   Kreator importu (później)                                E4
/data                           Dane i jakość (odświeżenia, błędy dostawców), lista obserwowanych   E1.7, E1.8
/settings                       Ustawienia                                               E0.9
/methodology                    Jak liczymy                                              E3.7
/login, /register               publiczne (rejestracja zamknięta wg E0.6)
```

### 1.3 Nawigacja

| Element | Decyzja |
|---|---|
| Desktop | **Jedna** nawigacja: sidebar. Usunąć zakładki nagłówka i `getTabValue` (`dashboard-header.tsx:47-55,75-80`); nagłówek zostaje na tytuł, wybór zakresu i menu użytkownika |
| Sidebar | Kokpit · Portfele (rozwijana lista z `id`) · Grupy · Operacje · Import (po wdrożeniu) · Dane · Ustawienia · Metodologia. Pozycji bez gotowego ekranu **nie** pokazujemy (koniec martwych linków, E0.7) |
| Mobile (poniżej `md`) | Do E11.1: obecny hamburger + `Drawer`. Od E11.1: dolna nawigacja (Kokpit, Portfele, Operacje, „Więcej”) + przycisk „Dodaj operację”, reszta w „Więcej” [propozycja] |
| Zakres | Zakładki Portfela/Grupy to podtrasy; wybrana zakładka jest zachowywana przy przełączaniu Portfela |
| 404 | Zamiast cichego `Navigate "/"` (`App.tsx:97`) ekran „Nie znaleziono” z linkiem do kokpitu [propozycja] |

### 1.4 Telefon a desktop (P6, E11.1)

| Ekran | Telefon | Uwagi |
|---|---|---|
| Kokpit, Portfel (pozycje), widok waloru | pełne | pozycje jako karty zamiast szerokiej tabeli (`PositionsTable.tsx`) |
| Dodanie operacji | pełne | `OperationFormDialog` na pełnym ekranie (`fullScreen` poniżej `sm`) |
| Historia operacji, wyniki, struktura, dywidendy | przegląd | wykresy w jednej kolumnie; edycja masowa niedostępna |
| Import (kreator), ustawienia | **tylko desktop** | na telefonie komunikat „Otwórz na komputerze” + link; bez blokady routingu |

### 1.5 Przekierowania ze starych tras (E0.10)

| Stara trasa | Nowa trasa | Mechanizm |
|---|---|---|
| `/pockets/:slug` | `/portfolios/:id` | komponent `LegacyPortfolioRedirect`: `decodeURIComponent(slug)` → `GET /portfolios/?name=` (jak `pocketService.ts:15-25`) → `Navigate replace` |
| `/pockets/:slug/history` | `/portfolios/:id/operations` | j.w. |
| `/pockets/:slug/charts` | `/portfolios/:id/performance` | j.w. |
| `/compare`, `/operations` | bez zmian | — |

Nieznana nazwa → ekran 404. Przekierowania usuwamy po jednym kamieniu milowym (jedyny użytkownik, zakładki w przeglądarce) [propozycja].

## 2. Konwencje UI

### 2.1 Formatowanie: jeden moduł `lib/format.ts` (E0.7)

Dziś 8 niezależnych `Intl.NumberFormat`: 4 walutowe (`PositionsTable.tsx:39`, `PocketsList.tsx:40`, `portfolio-overview.tsx:25`, `PocketDetailsPage.tsx:61`) i 4 w wykresach (`LineChartCard.tsx:52`, `AreaChartCard.tsx:52`, `PieChartCard.tsx:82`, `MiniLineChart.tsx:22`); 35 wywołań `toFixed`, 32 `Number()`. `portfolio-overview.tsx:28` ma **sztywne PLN** (defekt F3 — kokpit sumuje salda w różnych walutach, `DashboardPage.tsx:14-16`).

| Funkcja | Reguła | Dziś / źródło reguły |
|---|---|---|
| `formatMoney(v, currency)` | waluta **zawsze podana jawnie**: waluta Portfela, waluta waloru, a w kokpicie waluta wyświetlania (E0.9); 2 miejsca (0 w skrótach kokpitu); locale `pl-PL` | koniec `currency: 'PLN'` na sztywno |
| `formatQuantity(v)` | do 9 miejsc, bez zer końcowych (kolumna `Numeric(18, 9)`, `schemas/operations.py:18`) [propozycja] | dziś `toFixed(4)` (`PositionsTable.tsx:75`) ucina ułamkowe ilości |
| `formatPrice(v, currency)` | min. 2, maks. 4 miejsca | j.w. |
| `formatRate(v)` | kurs walutowy: 4–6 miejsc [propozycja] | `fx_rate` `Numeric(18, 9)` |
| `formatPercent(v)` | 2 miejsca, **jawny znak** (+/−); `null` → „—” (np. annualizacja < 365 dni, E3.1) | dziś `toFixed(2)` bez spójnego znaku |
| `formatDate(d)` | data kalendarzowa `DD.MM.YYYY` (jak `OperationsTable.tsx:74`); znaczniki czasu (`created_at`) z `timeZone: 'Europe/Warsaw'` (stała, D13, ADR-0019; bez ustawienia strefy) | wykresy: `new Date(label)` (`LineChartCard.tsx:82`) |
| `formatCompact(v)` | skróty osi wykresu (k, M) | `LineChartCard.tsx:46-48` (kopie w `AreaChartCard.tsx`) |

Wszystkie funkcje przyjmują `number | string | null | undefined` i zwracają „—” dla braku wartości (nie `0`). Kolejny powód centralizacji: tryb prywatności (E11.2) ukrywa kwoty jedną zmianą w `formatMoney`. Parsowanie dat bez czasu: `dayjs('YYYY-MM-DD')`, nie `new Date(...)` (ISO bez czasu jest parsowane jako UTC i w strefach na zachód od UTC pokazuje dzień wcześniej). Test jednostkowy dla każdej funkcji — pierwszy zestaw Vitest (E0.7).

### 2.2 Decimal po stronie UI

Backend liczy na `Decimal` (ADR-0010), ale `DecimalNumber` serializuje do JSON jako **float** (`app/core/schemas.py:11-13`), a widoki wartościowane dodatkowo zaokrągla do 3/4/2 miejsc (`schemas/positions.py`, `RoundedValue`/`RoundedPercent`/`RoundedFees`). Typy TS to `number` (`types/api.ts:37-46`). Wniosek: `Number()` jest bezpieczne do **wyświetlania** wartości zaokrąglonych, ale nie do rachunków księgowych (IEEE 754 daje ok. 15–17 cyfr znaczących, kolumna `Numeric(18, 9)` do 18).

| Reguła | Uzasadnienie |
|---|---|
| UI **nie sumuje** pieniędzy z różnych Portfeli/walut — sumy, kursy i przeliczenia liczy backend | dziś `DashboardPage.tsx:14-16` sumuje `cash_balance` bez walut |
| `Number()` tylko na granicy wyświetlania, wyłącznie przez `format*`; zakaz `parseFloat(...) * parseFloat(...)` do wartości, które trafią do zapisu | dialogi liczą brutto na floatach (`BuyAssetDialog.tsx:310-367`) |
| Nowe endpointy z kwotą/ilością: kontrakt API rozstrzyga, czy zwracać string dziesiętny (typ `DecimalString`); UI trzyma wartość jako `string`, formatuje `Intl.NumberFormat#format(string)` [propozycja; do sprawdzenia w docelowych przeglądarkach] | brak utraty precyzji bez biblioteki |
| Podgląd skutku operacji liczy **backend** (dry-run, p. 4.1), nie arytmetyka w przeglądarce | jedna reguła księgi (P3), brak duplikacji `PortfolioLedger` w TS |

### 2.3 Kolor zysku/straty nie jest jedynym nośnikiem

Dziś kolor sam niesie znak w: `PocketsList.tsx:150`, `portfolio-overview.tsx:54,84,89`, `PocketDetailsPage.tsx:141`. Lepiej w `PositionsTable.tsx:116-122` (ikona + kolor, ale bez jawnego „+”) i `OperationsTable.tsx:140-146` (znak + kolor).

Komponent `SignedValue` (jeden na całą aplikację): **znak** (+/−/0), **ikona** kierunku (`aria-hidden`), kolor z tokenów motywu (`success`/`error`, `theme.ts`), tekst dla czytników (`aria-label="zysk 1 234,00 zł"`). Kontrast tokenów na białym tle (obliczony: `#2e7d32` = 5,13:1, `#d32f2f` = 4,98:1 — oba ≥ 4,5:1 dla tekstu); na `#f5f5f5` (tło strony) do ponownego sprawdzenia. Skale kolorów w wykresach: p. sekcja 3.

### 2.4 Jakość danych i metodologia: `DataQualityBadge` i `MetricLabel`

Każda metryka z backendu (E1.7, E3.1) niesie flagi; UI pokazuje je jednym komponentem, nie ad hoc. Wartości flag ustala kontrakt API; poniżej słownik oczekiwanego zachowania.

| Flaga | Skąd | Wygląd | Tooltip „Jak liczymy” |
|---|---|---|---|
| `stale` (bool) | E1.7: cena starsza niż próg z E0.9 | żółty znacznik „Nieaktualna cena” + data (`price_date`) | „Ostatnia cena z <data>; próg: <N> dni (Ustawienia)” |
| `is_synthetic` | E1.1: cena uzupełniona/odtworzona, nie z notowania | znacznik „Szacunek” | „Brak notowania z tego dnia; użyto wartości przybliżonej” |
| `source` | E1.1/E1.5: dostawca, NBP, `manual` | drobny tekst/ikona przy wartości | „Źródło: <dostawca>” (dla `manual`: „wpisana ręcznie”) |
| `method` | E3.1: np. TWR, XIRR, Modified Dietz (fallback) | etykieta przy liczbie | opis metody + link do `/methodology` (E3.7) |
| `data_quality` | E2.5/E3.1: poziom kompletności serii | znacznik tylko gdy ≠ pełna | lista braków (np. „brak kursów NBP dla 3 dni”) |
| `effective_start` | E3.1: faktyczny początek liczenia | „od <data>” pod wartością | „Dane dostępne od <data>; okres skrócony” |
| `annualized = null` | E3.1: okres < 365 dni | „—” + dopisek „< 1 roku, bez annualizacji” | „GIPS 2.A.12” (zasada P2) |

`MetricLabel` = etykieta + wartość (`SignedValue`/`format*`) + `DataQualityBadge` + ikona „Jak liczymy”. Kryterium E3.7 („każda metryka w UI ma tooltip”) sprowadza się do reguły: **metryka nie jest wyświetlana inaczej niż przez `MetricLabel`**. Typ UI: `Metric<T> { value: T; method?; data_quality?; effective_start?; stale?; source?; as_of? }` [propozycja] — jeden envelope dla wszystkich endpointów metryk (kontrakt API definiuje pola po stronie serwera).

### 2.5 Stany ekranu

Dziś: spinner na całą stronę (`PocketDetailsPage.tsx:39-44`), `ChartCard` ma `loading`/`error` (`ChartCard.tsx`), `ErrorBoundary` dla wyjątków renderowania. Brak stanu pustego i częściowych danych (definicja ukończenia kroku, pkt 5 planu, wymaga: pusty, błąd, ładowanie).

| Stan | Wzorzec | Komponent |
|---|---|---|
| Ładowanie | szkielet (`Skeleton`) o kształcie docelowej tabeli/karty; spinner tylko dla akcji | `ScreenState` / `QueryBoundary` nad wynikiem TanStack Query |
| Pusty — pierwsze użycie | wyjaśnienie + główna akcja („Dodaj pierwszy Portfel”, „Importuj plik”) | `EmptyState` (kreator pierwszego uruchomienia: E11.8) |
| Pusty — filtry | „Brak wyników dla filtrów” + „Wyczyść filtry”; bez CTA tworzenia | `EmptyState variant="filtered"` |
| Błąd | komunikat PL z mapowania `code` (2.7) + „Spróbuj ponownie”; szczegóły techniczne zwijane | `ErrorState` |
| Częściowe dane | dane **widoczne**, nad nimi pasek „N walorów z nieaktualną ceną” + znacznik w wierszu (2.4); nie zastępujemy ekranu błędem | `StaleBanner` + `DataQualityBadge` |
| Odświeżanie w tle | stare dane zostają, cienki wskaźnik postępu (`isFetching`) | wskaźnik w nagłówku sekcji |
| Błąd odświeżania | ostatnie dane + pasek „Nie udało się odświeżyć” | `StaleBanner variant="error"` |

### 2.6 Wymuszenie odświeżenia cen (po E1.4)

Dziś `GET /portfolios/positions` odświeża kursy i ceny w żądaniu (`positions.py:27`), więc UI nigdy nie widzi „starej” ceny. E1.4 usuwa to z żądań HTTP (test z dostawcą rzucającym wyjątek); cena pochodzi z bazy, a odświeża ją CLI (D8).

| Element UI | Zachowanie |
|---|---|
| Kolumna/tooltip daty ceny | `price_date` przy każdej pozycji; `stale` → znacznik (2.4) |
| Przycisk „Odśwież ceny” (Portfel, `/data`) | `POST /assets/refresh-prices` → **202, odświeżenie w tle** (wyjątek E1.4: żądanie nie woła dostawcy, ADR-0017); UI pokazuje „Odświeżanie zleczone”, po odświeżeniu (polling `price_date`) unieważnia klucze `portfolio`, `positions`, `performance`, `dashboard` |
| Błąd dostawcy | `MARKET_DATA_UNAVAILABLE` (502, `core/market_data.py:82`) → „Dostawca notowań niedostępny; pokazuję ostatnie ceny” (stany: 2.5) |

### 2.7 Błędy API: mapowanie `code` → komunikat PL

Dziś `getErrorMessage` (`lib/api.ts:72-95`) czyta `detail` (`api.ts:75-77`) lub pierwszy klucz z tablicą; `ApiError` w `types/api.ts:146-149` nie zna `code`. Backend zwraca `{"detail", "code"}` (`core/errors.py:80-89`, ADR-0007), a `detail` jest po angielsku. Dla 422 z `ValidationError` `detail` to **lista** (`core/errors.py:114-122`, handler `ValidationError`), którą `getErrorMessage` zwraca bez konwersji — zachowanie w snackbarze niezweryfikowane uruchomieniem (**suggestion**: sprawdzić w E0.7).

Rozwiązanie: `lib/errors.ts` — `parseApiError(error)` → `{ status, code?, detail? }` oraz słownik `ERROR_MESSAGES: Record<string, string>`; kolejność: (1) `code` ze słownika, (2) komunikat wg statusu (401/403/404/409/422/5xx/brak sieci), (3) ogólny „Coś poszło nie tak” + `detail` w zwijanych szczegółach technicznych. `getErrorMessage` deleguje do tego modułu. Każdy `code` w słowniku ma test (Vitest); nieznany `code` nie psuje UI.

| `code` | Status | Komunikat PL (propozycja) | Źródło |
|---|---|---|---|
| `INSUFFICIENT_CASH` | 400 | „Za mało gotówki w Portfelu na tę operację.” | `portfolios/domain/errors.py:45` |
| `INSUFFICIENT_QUANTITY` | 400 | „Nie masz tylu sztuk tego waloru (wg historii na tę datę).” | `domain/errors.py:56`; E0.3 |
| `INVALID_OPERATION`, `OPERATION_REQUIRES_ASSET`, `OPERATION_FORBIDS_ASSET` | 400 | „Operacja jest niezgodna z regułami Portfela.” / „Wybierz walor.” / „Ten typ nie dotyczy waloru.” | `domain/errors.py:16-38` |
| `PORTFOLIO_NOT_FOUND`, `OPERATION_NOT_FOUND`, `ASSET_NOT_FOUND` | 404 | „Nie znaleziono Portfela / operacji / waloru.” | `portfolios/exceptions.py:19-61` |
| `PORTFOLIO_ALREADY_EXISTS`, `ASSET_ALREADY_EXISTS` | 409 | „Taka nazwa/ticker już istnieje.” | `exceptions.py:36`, `assets/exceptions.py:62` |
| `ASSET_HAS_HISTORY`, `CURRENCY_IN_USE` | 409 | „Nie można usunąć — ma historię / jest używana; zarchiwizuj” (D15; `ASSET_HAS_HISTORY` zastępuje dotychczasowy `ASSET_IN_USE`, `assets/exceptions.py:89`) | `assets/exceptions.py:89,106` |
| `CONCURRENT_CHANGE` | 409 | „Dane zmieniły się równolegle — spróbuj ponownie.” | `portfolios/exceptions.py:116` |
| `INVALID_DATE`, `INVALID_DATE_RANGE` | 400 | „Niepoprawna data / zakres dat.” | `exceptions.py:89,95` |
| `MARKET_DATA_UNAVAILABLE` | 502 | „Dostawca notowań jest niedostępny.” | `core/market_data.py:82` |
| `ASSET_NOT_FOUND_ON_PROVIDER` | 404 | „Dostawca nie zna tego tickera.” | `assets/exceptions.py:34` |
| `INVALID_CREDENTIALS`, `INVALID_REFRESH_TOKEN` | 401 | „Błędny e-mail lub hasło.” / przekierowanie do logowania | `security/errors.py:25,32` |
| `EMAIL_ALREADY_REGISTERED` | 409 | „Ten e-mail jest już zarejestrowany.” | `core_data/services/users.py:30` |
| `IRR_UNDEFINED`, `IRR_AMBIGUOUS`, `PERIOD_SHORTER_THAN_ONE_YEAR` | **200 inline** (`reason` w metryce, nie błąd; mapowane przez `MetricLabel`) | „XIRR nieokreślony (brak przepływów o różnych znakach).” / „XIRR niejednoznaczny — pokazuję TWR.” / „< 1 roku, bez annualizacji” | E3.1 |
| `REGISTRATION_DISABLED` | 403 | „Rejestracja jest wyłączona.” | E0.6 |
| `REFERENCE_DATA_OWNER_ONLY`, `PORTFOLIO_CURRENCY_LOCKED` | 403 / 409 | „Tylko właściciel zmienia dane globalne.” / „Waluty Portfela nie zmienisz, gdy są operacje.” | E0.6, E0.8; kody `UPPER_SNAKE` |

Kody nowych kroków (cofnięcie paczki z edycjami `IMPORT_BATCH_HAS_EDITS` E4.1/D15) są dopisywane do słownika w tym samym kroku, w którym backend je wprowadza (definicja ukończenia, pkt 5).

### 2.8 Dostępność

| Obszar | Dziś | Wymóg |
|---|---|---|
| Sortowanie tabeli | emotikony 🔼/🔽 w treści nagłówka, klikalny `TableCell` bez fokusu (`OperationsTable.tsx:214-219`) | `TableSortLabel` (przycisk, fokus z klawiatury) + `aria-sort` |
| Kolor zysku/straty | sam kolor w kilku miejscach (2.3) | `SignedValue` |
| Etykiety ikon | jedno `aria-label` (`dashboard-header.tsx:65`) | `aria-label` na wszystkich `IconButton`; ikony dekoracyjne `aria-hidden` |
| Język dokumentu | `<html lang="en">` (`index.html:2`) | `lang="pl"` |
| Wykresy | brak alternatywy tekstowej | `aria-label` z podsumowaniem + tabela danych pod „Pokaż jako tabelę”; mapa cieplna zawsze z wartością w komórce |
| Klawiatura | domyślna z MUI (dialogi mają pułapkę fokusu) | kreator importu i edycja wierszy w pełni z klawiatury (Tab/Enter/Esc), fokus wraca na wiersz po zapisie |
| Animacje | brak decyzji | respektować `prefers-reduced-motion` |
| Cele dotykowe | domyślne MUI | ≥ 44 px dla głównych akcji na telefonie |

## 3. Wykresy: Recharts 3 czy dodatkowa biblioteka?

Zainstalowany `recharts ^3.7.0` (`package.json`); zawartość wersji 3.7.0 sprawdzona na liście plików paczki (cdn.jsdelivr.net): są `ComposedChart`, `Scatter`, `ReferenceDot`, `ReferenceArea`, `Brush`, `Treemap`, `Sankey`, `SunburstChart`, `AreaChart`, `BarChart`; **brak** heatmapy i macierzy. Dziś używane: `LineChart`, `AreaChart` (`stackId`, `AreaChartCard.tsx:91`), `PieChart` w opakowaniach `components/charts/*`.

| Wymaganie | Krok | Recharts 3.7 | Realizacja |
|---|---|---|---|
| Mapa cieplna miesiąc × rok | E3.5 | brak | **własny `HeatmapGrid`** (siatka CSS/SVG, skala dywergentna, wartość w komórce) |
| Mapa cieplna Portfela (kafelek ∝ wartość) | E3.5 | `Treemap` z własnym `content` | Recharts |
| Wykres ceny z markerami operacji i dywidend | E3.8 | `ComposedChart` + `Line` + `Scatter` (lub `ReferenceDot`) | Recharts; własny tooltip i kształt markera (kupno/sprzedaż/dywidenda różnią się kształtem, nie tylko kolorem) |
| Struktura w czasie (warstwowy) | E3.3 | `AreaChart` ze `stackId`; udziały 100% przez normalizację danych po stronie serwera | Recharts |
| Wartość vs wpłaty, TWR vs benchmark | E3.5 | `AreaChart`/`LineChart` | Recharts |

**Rekomendacja [propozycja]: zostać przy Recharts + własny `HeatmapGrid`; nie dodawać drugiej biblioteki.** Uzasadnienie: jedyny typ bez wsparcia (mapa miesiąc × rok) jest prostą siatką wartości, dla której biblioteka wykresów daje mało ponad CSS; druga biblioteka oznacza drugi system motywów, tooltipów i dostępności oraz większy bundle [rozmiar niezmierzony]. Koszt własnego komponentu: jeden komponent ok. 150–250 linii + testy jednostkowe skali kolorów **[wniosek]**.

Kiedy zmienić zdanie: wykres ceny z markerami przy tysiącach punktów okaże się za wolny albo potrzebne będą świece/wskaźniki — wtedy rozważyć wyspecjalizowaną bibliotekę (np. lightweight-charts) **tylko** dla widoku waloru; ocena wymaga pomiaru na danych 10 lat (E11.7). Wspólne reguły: skale kolorów bezpieczne dla daltonistów (nie para czerwony–zielony; znak zawsze w tekście), wartości wykresów to `float` (ADR-0010, wektory), format osi z `lib/format.ts`.

## 4. Formularze

### 4.1 `OperationFormDialog`: jeden dialog dla wszystkich typów Operacji

Dziś trzy osobne dialogi na `useState`: `BuyAssetDialog.tsx` (392 linie), `SellAssetDialog.tsx` (343), `CashOperationDialog.tsx` (130); `react-hook-form` i `@mui/x-date-pickers` są w `package.json`, ale **nie są importowane** w `src/`; brak dialogu dywidendy i edycji (`PUT /portfolios/operations/{id}` istnieje — `operations.py:41-42` — ale `operationService.ts` nie ma `updateOperation`).

Jeden `OperationFormDialog` (tryb: utwórz / edytuj) z konfiguracją pól per typ; wybór typu na górze; React Hook Form (już zależność) z funkcjami walidacji, bez nowej biblioteki schematów [propozycja]. Zbiór typów i pól: E2.3, D9; kolumny `ratio`/`counter_*` nie są w D9 (przegląd roadmapy) — **[propozycja]** do kontraktu.

| Typ | Pola wymagane | Pola opcjonalne | Krok |
|---|---|---|---|
| `buy`, `sell` | Portfel, data, Walor, ilość, cena | prowizja, kurs brokera, notatka | dziś |
| `dividend` | Portfel, data, Walor, kwota (w walucie wypłaty) | notatka | dziś (brak UI → E0.7) |
| `deposit`, `withdrawal` | Portfel, data, kwota | prowizja, waluta | dziś (prowizja → E0.7) |
| `interest`, `fee` | Portfel, data, kwota, waluta | Walor | E2.3 |
| Przewalutowanie | Portfel, data, kwota z + waluta, kwota do + waluta | kurs, prowizja (w walucie wychodzącej) | E2.2 |
| `split` | Portfel, data, Walor, proporcja nowe:stare | — | E8.1 |

Walidacja klienta to **kształt i wygoda** (wymagane pola, liczba, zakresy kolumn `Numeric(18, 9)`/`(18, 2)`, `extra="forbid"` po stronie API), nie reguły księgi; autorytatywny jest backend (`INSUFFICIENT_CASH`, `INSUFFICIENT_QUANTITY`, 2.7). Podpowiedzi: sprzedaż > posiadana ilość i zakup > gotówka dają ostrzeżenie przed wysłaniem (nie blokadę — opcjonalne automatyczne wpłaty E2.2b (`auto_funding`)); data w przyszłości = ostrzeżenie [propozycja]. Domyślny kurs z tego samego źródła co wycena (E0.1).

**Podgląd skutku** („przed → po”): gotówka per waluta, ilość i średnia cena pozycji, zużyte Partie, zysk zrealizowany (E2.4). Źródłem jest endpoint dry-run `POST /portfolios/operations/preview` (nowy, ta sama walidacja i `PortfolioLedger` bez zapisu) [propozycja], wywoływany z opóźnieniem 300 ms; błędy księgi pokazują się w podglądzie jako komunikaty z 2.7. Edycja: ostrzeżenie „zmiana przebuduje pozycje od <data>” (przebudowa — E0.3/P3); typ, walor i Portfel w trybie edycji tylko do odczytu (`OperationUpdateRequest`, `schemas/operations.py:61-73`).

### 4.2 Kreator importu XTB (E4) — później

Desktop-only (1.4). Implementacja po przeglądzie reszty; najpierw tylko adapter XTB, kolejne źródła później ([ADR-0018](../adr/0018-architektura-importu.md)). Stan paczki: **szkic → zatwierdzona → cofnięta** (D15). Wzorzec konkurenta: podgląd w tabeli przed importem ([myfund](../../research/competitors/01_myfund.md)); słabość do pokonania: „godziny ręcznego poprawiania”.

| Krok | Ekran | Zachowanie | Endpoint (nowy) [propozycja] |
|---|---|---|---|
| 1. Plik | Portfel docelowy, wgranie pliku XTB | `sha256` pliku → „ten plik już zaimportowano” (backend zwraca istniejącą paczkę, E4.1) | `POST /portfolios/imports` |
| 2. Podgląd i naprawa | tabela wierszy z surową etykietą; filtry `row_status`: wszystkie / `ok` / **`duplicate`** / **`unrecognized`** / **`error`** / `skip`; liczniki; wiersz pomijany = `skip` | edycja wiersza (typ, walor, ilość, cena, waluta, kurs) w panelu bocznym; rozpoznanie waloru (ISIN, ticker + giełda); walidacja brutto = ilość × cena ± prowizja; wiersz poprawiony ręcznie oznaczony; szkic zapisany na serwerze (powrót pod `/import/:batchId`) | `GET …/{id}/rows`, `PATCH …/{id}/rows/{row}` |
| 3. Zatwierdzenie | podsumowanie: liczba operacji, pominięte duplikaty, skutek (gotówka/pozycje) | jedna transakcja i jeden `rebuild` (ADR-0008, E4.1) | `POST …/{id}/commit` |
| 4. Cofnięcie | lista paczek `/import`, akcja „Cofnij” z potwierdzeniem | blokada z listą operacji, jeśli któraś była edytowana (D15) | `POST …/{id}/revert` |

**Paginacja 2000 wierszy:** paginacja **po stronie serwera** (koperta jak w E2.7: `items`, `total`, `limit`, `offset`; filtr `row_status`), 100–200 wierszy na stronę; bez wirtualizacji (brak nowej zależności) [propozycja]. Filtry i strona są w URL (query), by odświeżenie karty nie gubiło widoku. Kryterium E4.1: 2000 wierszy < 10 s dotyczy zatwierdzenia, nie renderu.

### 4.3 Ustawienia (E0.9)

Formularz sekcyjny z jednym przyciskiem „Zapisz” i stanem „niezapisane zmiany” (bez autozapisu) [propozycja]. Pola: waluta wyświetlania (domyślnie PLN), próg nieaktualnej ceny (dni), benchmark (jeden Walor-indeks do porównania, E3.5); strefa czasowa jest stała (Europe/Warsaw, ADR-0019), bez pola. Kolejne sekcje dopisywane przez kroki: tryb prywatności (E11.2; ustawienie przeglądarki, nie serwera). Zmiana waluty wyświetlania unieważnia klucze kokpitu i wyników. Endpointy: `GET/PUT /settings` [propozycja], pola wg kontraktu API.

## 5. Infrastruktura frontendu

### 5.1 Klient API generowany z OpenAPI — decyzja [propozycja]

| Wariant | Za | Przeciw |
|---|---|---|
| A. Ręczne typy (dziś: `types/api.ts`, 149 linii) | zero narzędzi | dryf względem backendu; `ApiError` bez `code`; przy ~30 nowych endpointach błędy typów wychodzą w produkcji |
| **B. Generowane tylko typy** (np. `openapi-typescript`) + dotychczasowy `axios` i ręczne serwisy | typy zawsze zgodne z backendem; mały narzut; bez runtime generatora | nowa zależność deweloperska i krok w CI |
| C. Pełny SDK (generator klienta) | najmniej kodu serwisów | narzuca klienta HTTP, trudniej zachować interceptor odświeżania tokenu (`api.ts:33-67`) |

**Rekomendacja: B.** `/openapi.json` jest wystawiany tylko gdy `docs_enabled` (`main.py:37`; `config.py:45-47`: `not is_production`), więc generowanie ma czerpać ze **zrzutu schematu bez uruchamiania serwera** (`app.openapi()` w skrypcie backendu — niezweryfikowane lokalnie: brak zainstalowanego FastAPI w tym środowisku) zapisanego w repo; CI sprawdza dryf (jak `sync_copilot.py` w ai-tools). Uwaga: `DecimalNumber` daje w schemacie `number` (`core/schemas.py:11-13`) — typ `DecimalString` dla nowych pól to decyzja kontraktu API. Wprowadzić razem z Vitest (E0.7), by nowe endpointy miały typy od pierwszego dnia.

### 5.2 Wspólny envelope metryk po stronie UI

Jeden typ `Metric<T>` i jeden komponent (`MetricLabel`, 2.4); hooki danych zwracają envelope bez rozbijania na pola; klucze TanStack Query zawierają zakres i okres (`['performance', scope, id, period]`). Obecne klucze po nazwie (`['pockets','by-name',name]`, `usePockets.ts:24`; `['positions', pocketName]`, `usePositions.ts`) znikają w E0.10.

### 5.3 Testy: Vitest od E0.7 (nie E11.6)

Plan już to przyjmuje (E0.7, E11.6: „runner wprowadzony w E0.7”). Dziś: skrypty `dev`, `build`, `lint`, `preview` — brak `test` (`package.json`); `.github/workflows/frontend.yml` uruchamia tylko `npm run lint` i `npm run build`. Zakres E0.7: Vitest + React Testing Library; pierwsze testy: `lib/format.ts`, `lib/errors.ts` (każdy `code` ze słownika), walidacja `OperationFormDialog`, `SignedValue`; krok `npm test` w workflow. Mockowanie sieci (np. MSW) — dopiero przy testach ekranów [propozycja]. E2E (Playwright) zostaje w E11.6.

### 5.4 Migracja nazw Pocket → Portfolio przed nowymi ekranami (E0.10)

`grep -rn Pocket frontend/src` → **130 wystąpień w 19 plikach**; `grep -rni pocket frontend/src` → 278 linii w 25 plikach (z `pocketName`, `/pockets/`). Najwięcej: `PocketComparisonPage.tsx` (38), `pocketService.ts`, `usePockets.ts`, `AddPocketDialog.tsx`, `PocketsList.tsx` (po 11), `App.tsx` (8).

| Warstwa | Zmiana |
|---|---|
| Typy (`types/api.ts`) | `Pocket` → `Portfolio`, `PocketVectorsResponse` → `PortfolioVectorsResponse`, `CreatePocketRequest` → `CreatePortfolioRequest` |
| Serwisy/hooki | `pocketService` → `portfolioService`; `usePockets` → `usePortfolios`; `usePocketVectors` → `usePortfolioVectors`; klucze `['pockets']` → `['portfolios']`; usunąć `getPocketByName`/`usePocketByName` poza `LegacyPortfolioRedirect` |
| Komponenty/strony | `PocketsList` → `PortfoliosList`; `AddPocketDialog` → `AddPortfolioDialog`; `PocketDetailsPage` → `PortfolioPage`; `PocketHistoryPage` → zakładka `operations`; `PocketChartsPage` → zakładka `performance`; `PocketComparisonPage` → `ComparePage` |
| Trasy | `/portfolios/:id` itd. (1.2), przekierowania (1.5) |

Backend adresuje dziś Portfel **nazwą** (`portfolio_name`: `operations.py:29`, `positions.py:28`; `portfolioName`: `schemas/metrics.py:16`), ale `GET /portfolios/{id}` istnieje i zwraca Portfel z pozycjami (`PortfolioDetailResponse`, `schemas/portfolios.py`). Dlatego E0.10 wymaga w backendzie pola `portfolio_id` w odpowiedziach pozycji i operacji (dziś frontend wysyła `portfolio_name`: `positionService.ts:7`, `operationService.ts:7`, `schemas/positions.py:43`); trasa po `id`, strona pobiera Portfel po `id` (`pocketService.ts:10-13`), a endpointy po nazwie działają równolegle (kontrakt API 1.1). **Wyjątek od kryterium E0.10** („brak słowa Pocket w `frontend/src`”): plik przekierowań `LegacyPortfolioRedirect` i alias `pocket_value_vector` (usuwany w E3.5).

Kolejność [propozycja]: (1) naprawa startu (5.6), (2) E0.10 (rename), (3) reszta E0.7 (`lib/format.ts`, Vitest, nawigacja, dialogi) — E0.7 dotyka tych samych plików, więc rename najpierw; nowe pliki od początku nazywamy `Portfolio*`.

### 5.5 Język (i18n)

Decyzja jawna [propozycja]: **tylko polski**, bez frameworka i18n. Teksty PL w komponentach są dozwolone, ale komunikaty błędów (2.7) i słownik flag jakości (2.4) żyją w jednym miejscu (`lib/errors.ts`, `lib/dataQuality.ts`), co zostawia drogę do przyszłej lokalizacji. `detail` API jest po angielsku (ADR-0007) i nie jest pokazywany jako główny komunikat. Zmiana decyzji wymaga drugiego języka użytkownika (dziś: jeden użytkownik, D14).

### 5.6 Naprawa startu

| Defekt | Dowód | Poprawka |
|---|---|---|
| Skrypt wejściowy wskazuje nieistniejący plik | `frontend/index.html:11` → `/src/main.jsx`; w `src/` jest tylko `main.tsx` | `/src/main.tsx` |
| Ikona ze ścieżką z backslashem i niezgodnym typem | `index.html:5`: `href="public\FundTracker.png"`, `type="image/svg+xml"`; plik `public/FundTracker.png` jest PNG | `href="/FundTracker.png"`, `type="image/png"` |
| `lang="en"`, tytuł „Found Tracker” (nagłówek: „FoundTracker”, `dashboard-header.tsx:72`; projekt: „FundTracker”) | `index.html:2,7` | `lang="pl"`, jedna nazwa produktu [propozycja] |

Czy build/dev się wywala — **niezweryfikowane uruchomieniem** (brak `node_modules` w środowisku); Vite rozwiązuje `<script type="module" src>` z `index.html`, więc brakujący plik powinien zatrzymać `vite build` i `vite dev`. Weryfikacja: `cd frontend && npm ci && npm run build`.

## 6. Strona → komponenty → endpointy → kroki

Legenda endpointów: **ist.** = istnieje w `backend/app/modules/*/api`; **nowy** = do powstania (ścieżka wg kontraktu API). Komponenty `Portfolio*` zakładają wykonane E0.10.

| Ekran (trasa) | Komponenty | Endpointy | Kroki |
|---|---|---|---|
| Kokpit (`/`) | `DashboardPage`, `PortfoliosList`, `PortfolioOverview`, `MiniLineChart`, `SignedValue`, `MetricLabel` | ist. `GET /portfolios/`; nowy: agregat kokpitu (wartość w walucie wyświetlania, zmiana dzienna, TWR YTD/1Y, wygrani/przegrani) | E0.9, E3.4 |
| Portfel — pozycje (`/portfolios/:id`) | `PortfolioPage`, `PositionsTable`, `OperationFormDialog`, `StaleBanner`, przycisk „Odśwież ceny” | ist. `GET /portfolios/{id}`, `GET /portfolios/positions`; nowy: podgląd operacji, `POST /assets/refresh-prices` (202) | E0.10, E0.7, E1.4, E1.7 |
| Grupa portfeli (`/groups/:id`) | `GroupPage` (zakładki jak Portfel), `GroupFormDialog` | nowy: CRUD Grup, agregaty zakresu | E2.1, E3.1 |
| Widok waloru (`/assets/:id`) | `AssetPage`, `PriceChartWithMarkers`, `LotsTable`, `MetricLabel` | ist. `GET /assets/{id}`; nowy: historia cen, partie, operacje waloru | E1.1, E2.4, E3.8 |
| Historia operacji (`/portfolios/:id/operations`, `/operations`) | `OperationsTable` (paginacja/filtry serwerowe), `OperationFormDialog` (edycja) | ist. `GET/PUT/DELETE /portfolios/operations…` (dziś goła lista bez paginacji, `operations.py:23-29`); nowy: koperta z paginacją i filtrami | E0.7, E2.7 |
| Struktura (`…/allocation`) | `AllocationChart` (`PieChartCard`, `AreaChartCard` warstwowy), `MetricLabel` | nowy: alokacja wg Walorów, Klas, sektora, waluty, kraju | E3.3 |
| Wyniki (`…/performance`, `/compare`) | `PerformancePage`, `LineChartCard`, `HeatmapGrid`, `DateRangePicker`, `MetricLabel` | ist. `GET /portfolios/portfolio-vectors` (dziś); nowy: `GET /portfolios/{id}/performance` (E3.1), seria benchmarku | E3.1, E3.5 |
| Dywidendy i odsetki (`…/income`) | `IncomeChart`, `MetricLabel` | nowy: dochód pasywny (`GET {S}/income`) | E3.6 |
| Zamknięte pozycje (`…/closed`) | `ClosedPositionsTable`, `MetricLabel` | nowy: raport z partii | E3.2 |
| Import — kreator (`/import/new`, `/import/:batchId`, `/import`) | `ImportWizard`, `ImportRowsTable`, `RowEditPanel`, `BatchList` | nowy: p. 4.2 (później) | E4 |
| Dane i jakość (`/data`) | `DataStatusPage`, `WatchlistTable`, `ManualPriceDialog` | nowy: status odświeżeń i zadań w tle, ceny ręczne (awaryjne), lista obserwowanych | E1.5, E1.7, E1.8 |
| Ustawienia (`/settings`) | `SettingsPage` (sekcje) | nowy: `GET/PUT /settings` (4.3) | E0.9 |
| Metodologia (`/methodology`) | `MethodologyPage` (kotwice per `method`) | brak (treść statyczna) | E3.7 |
| Logowanie/rejestracja (`/login`, `/register`) | `LoginPage`, `RegisterPage`, `ProtectedRoute` | ist. `POST /auth/login`, `/auth/token/refresh`, `POST /auth/register` | E0.6 (zamknięcie rejestracji) |

## Otwarte punkty

| # | Co | Blokuje / kto |
|---|---|---|
| 1 | Przycisk „Odśwież ceny” = 202 + zadanie w tle (wyjątek E1.4 w ADR-0017); polling `price_date` zamiast natychmiastowego wyniku — do potwierdzenia UX | E1.4, 2.6 |
| 2 | Kształt envelope i wartości `method`/`data_quality` (słownik 2.4 jest oczekiwany, nie zdefiniowany) oraz `DecimalString` | dokument kontraktu API, E3.1 |
| 3 | Mapowanie nowych kodów (`UPPER_SNAKE`) w `ERROR_MESSAGES` rośnie z każdym krokiem backendu | każdy krok |
| 4 | Wyjątek E0.10 (plik przekierowań, alias `pocket_value_vector`) zapisany w planie 03 | E0.10 |
| 5 | Endpoint dry-run podglądu operacji i sekcja ustawień (`/settings`) | kontrakt API; E0.9, E2.3 |
| 6 | Nawigacja mobilna (dolny pasek) wchodzi dopiero w E11.1 — do tego czasu hamburger | akceptacja kolejności |
| 7 | Wybór narzędzia do generowania typów OpenAPI i skryptu zrzutu schematu (niezweryfikowane lokalnie) | E0.7 |
| 8 | Zachowanie `getErrorMessage` przy 422 (lista w `detail`) — do sprawdzenia uruchomieniem; `npm run build` z niedziałającym `index.html` — do potwierdzenia | brak `node_modules` w środowisku autora |
| 9 | Zanonimizowana próbka eksportu XTB potrzebna do ostatecznego kształtu kroku 2 kreatora | właściciel; E4 |
