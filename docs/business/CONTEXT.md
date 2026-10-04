---
id: business-context
status: current
last_reviewed: 2026-10-03

type: reference
scope: business/vocabulary
---

# FundTracker — Kontekst Biznesowy

FundTracker to osobista aplikacja do śledzenia inwestycji finansowych (akcje i ETF-y). Użytkownik zapisuje zdarzenia — zakupy, sprzedaże, wpłaty, wypłaty, dywidendy, opłaty, przewalutowania, splity — a system przelicza z nich stan portfela, metryki i wykresy w czasie. Aplikacja jest jednoużytkownikowa (jeden właściciel, rejestracja zamknięta); dane są przypisane do konta (`owner_id`).

## Słownik — Domeny Biznesowe

### Portfel i jego zawartość

**Portfel** (`portfolios_portfolio`)
Jeden rachunek maklerski użytkownika ([ADR 0001](adr/0001-portfel-jest-rachunkiem.md)): nazwa, waluta bazowa, salda gotówki, suma wpłat, informacyjne etykiety `account_type` i `broker`. Użytkownik może mieć wiele portfeli; nazwa jest unikalna w obrębie właściciela. W części frontendu (`Pocket*`, `PocketsList`) nazywany `Pocket`.
_Unikać_: Pocket (poza frontendem do czasu zmiany nazw), konto, wallet

**Pozycja** (`portfolios_position`)
Stan posiadania jednego waloru w jednym portfelu: ilość, średnia cena zakupu, średni kurs walutowy, łączne opłaty i dywidendy. Pozycja jest **wynikiem** historii Operacji, nie danymi źródłowymi — można ją odbudować z Operacji. Unikalna na parę (Portfel, Walor); pozycja o ilości 0 jest usuwana.
_Unikać_: holding, udział

**Operacja** (`portfolios_operation`)
Zdarzenie zapisane przez użytkownika, niezmienne co do znaczenia: `buy`, `sell`, `deposit`, `withdrawal`, `dividend`, `interest`, `fee`, `currency_exchange` (przewalutowanie), `split`. Operacje są źródłem prawdy o portfelu. Usunięcie lub edycja Operacji wymusza przebudowę salda i Pozycji z pozostałej historii.
_Unikać_: transakcja (w kodzie tylko w nazwie technicznej `transaction()` — granica commitu, nie pojęcie domenowe), wpis

**Paczka importu** (`portfolios_import_batch`)
Jeden zaimportowany plik z banku lub domu maklerskiego i jego los: `committed` (wiersze `ok` stały się Operacjami); cofnięcie usuwa Operacje i samą paczkę razem z plikiem. Przed importem podgląd (niezapisywany) pokazuje wiersze i raport zgodności, który porównuje stan z pliku ze stanem Portfela. Opis działania: [`07_import.md`](../technical/backend/07_import.md).
_Unikać_: upload (jako nazwa pojęcia), migracja danych

**Saldo gotówki**
Wolna gotówka Portfela osobno dla każdej Waluty ([ADR 0003](adr/0003-gotowka-wielowalutowa.md)); kolumna `cash_balance` to saldo w walucie bazowej. Zakup je zmniejsza, sprzedaż i dywidenda zwiększają (w walucie wypłaty), wpłata i wypłata zmieniają.
_Unikać_: cash, środki, wolne środki (zbyt ogólnie)

**Suma wpłat** (`total_deposited`)
Łączna kwota netto wpłat minus wypłat. Nie zawiera zysków; nie jest podstawą TWR.
_Unikać_: kapitał, wkład własny

**Partia**
Część zakupu jeszcze nieprzeznaczona na sprzedaż; sprzedaż zużywa partie FIFO w obrębie Portfela ([ADR 0002](adr/0002-koszt-nabycia-partie-fifo.md)). Dana pochodna.
_Unikać_: lot

**Grupa portfeli**
Widok agregujący kilka Portfeli, bez własnych Operacji.

**Dzień operacji** (`operation_day`)
Data zawarcia Operacji w Europe/Warsaw; z numerem `sequence` ustala kolejność ([ADR 0005](adr/0005-daty-operacji-dzien-i-kolejnosc.md)).
_Unikać_: data transakcji

### Walory i waluty

**Walor** (`assets_asset`)
Instrument finansowy (akcja, ETF) identyfikowany unikalnym tickerem, z aktualną ceną, giełdą i sektorem. Należy do jednej Klasy waloru i ma jedną Walutę notowania.
_Unikać_: aktywo (w polskim UI „aktywo” bywa używane, ale w kodzie i dokumentach trzymamy „walor”), instrument, papier

**Archiwizacja waloru** (`assets_asset.archived_at`)
Ukrycie waloru w wyszukiwarce i przed nowymi Operacjami bez usuwania: historia, Pozycje i wycena zostają, odświeżanie cen się zatrzymuje, operację można cofnąć. Walor z historią (Operacje, Pozycje, ceny) nie może być usunięty, tylko zarchiwizowany.
_Unikać_: dezaktywacja, usunięcie (miękkie)

**Historia cen i kursów** (`assets_price`, `assets_fx_rate`)
Zamknięcia dzienne waloru i kursy walut, każde z jawnym źródłem (`manual`, `yahoo`). Tego samego dnia wygrywa wpis ręczny, potem dostawca. `current_price` i `exchange_rate` to tylko cache najnowszej wartości.
_Unikać_: notowanie (ogólnie), cena bieżąca jako źródło prawdy

**Klasa waloru** (`assets_assetclass`)
Kategoria Waloru: akcja, ETF. Słownik zarządzany przez użytkownika.
_Unikać_: typ waloru, kategoria

**Waluta** (`assets_currency`)
Waluta notowania Waloru lub bazowa Portfela. Niesie kurs wymiany względem waluty bazowej systemu (USD), odświeżany z danych rynkowych; kurs między dwiema dowolnymi walutami to iloraz ich kursów. Waluta bez notowania nie ma kursu — wycena pozycji, która go wymaga, pokazuje „brak kursu” zamiast wartości policzonej po kursie 1.
_Unikać_: kurs (kurs to `exchange_rate`, nie Waluta)

**Kurs krzyżowy**
Kurs między dwiema dowolnymi Walutami, liczony jako iloraz ich kursów względem waluty bazowej systemu; nie jest zapisany w bazie. Służy do wyceny pozycji w walucie Portfela.
_Unikać_: kurs wymiany (bez przymiotnika)

**Brak kursu**
Stan Waluty bez notowania: wycena pozycji, która go wymaga, nie jest liczona (wartości puste, `rate_missing`), zamiast być liczona po kursie 1.
_Unikać_: kurs zerowy, kurs domyślny

**Kurs walutowy operacji** (`fx_rate`)
Kurs brokera zastosowany w momencie Operacji do przeliczenia wartości z waluty Waloru na walutę bazową Portfela. Zapisany w Operacji, nie wyliczany wstecznie. Wycena używa osobno dziennego kursu z `assets_fx_rate` (źródło: NBP).

**Dane rynkowe**
Ceny Walorów (Yahoo Finance przez `yfinance`) i kursy walut (NBP). Ceny ręczne tylko awaryjnie (`source=manual`). Dostawca jest zależnością zewnętrzną, niestabilną i nieudokumentowaną — błędy pobrania to sytuacja normalna, nie wyjątek.
_Unikać_: feed, notowania (zbyt ogólnie)

### Metryki

**Metryki portfela**
Wartości liczone z historii Operacji i cen w czasie: wartość portfela, koszty transakcji, wpłaty netto, wolna gotówka, zysk zrealizowany i niezrealizowany, TWR, XIRR — w postaci **wektorów** dziennych (interwał `1d`; [ADR 0004](adr/0004-metodologia-stop-zwrotu.md)). Są obliczeniami, nie danymi źródłowymi: nigdy nie zapisujemy ich jako prawdy.
_Unikać_: statystyki, analityka (jako nazwa modułu — patrz ADR o warstwie `domain/`)

**Wektor portfela**
Seria wartości metryki dla kolejnych dni w zadanym przedziale; dane do wykresów na froncie.

**Benchmark**
Indeks referencyjny, z którym porównujemy wynik Portfela.

### Użytkownik i dostęp

**Użytkownik** (`users`)
Właściciel danych (flaga `is_owner` daje zapis danych referencyjnych — [ADR 0007](adr/0007-dane-referencyjne-i-usuwanie.md)). Loguje się e-mailem i hasłem; dostaje token dostępu i odświeżający.
_Unikać_: klient, konto (konto = Użytkownik + jego dane)

## Relacje

- Portfel ma wiele Pozycji i wiele Operacji; Operacja należy do jednego Portfela i (oprócz wpłaty/wypłaty/przewalutowania) do jednego Waloru. Grupa portfeli agreguje Portfele.
- Pozycja jest pochodną Operacji; metryki są pochodnymi Operacji i cen rynkowych.
- Walor należy do Klasy waloru i ma Walutę notowania; Portfel ma Walutę bazową.

## Sprzeczności i niejasności

- Frontend używa nazwy `Pocket`, backend `Portfolio`. Nazewnictwo docelowe: **Portfel / Portfolio**; zmiana nazw we froncie jest poza zakresem przepisywania backendu.
- Operacja `dividend` zwiększa `total_dividends` Pozycji i saldo gotówki (w walucie wypłaty), ale nie zmienia `total_deposited`.
