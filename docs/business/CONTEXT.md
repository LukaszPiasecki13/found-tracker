---
id: business-context
status: current
last_reviewed: 2026-10-01
type: reference
scope: business/vocabulary
---

# FundTracker — Kontekst Biznesowy

FundTracker to osobista aplikacja do śledzenia inwestycji finansowych (akcje, fundusze, obligacje). Użytkownik zapisuje zdarzenia — zakupy, sprzedaże, wpłaty, wypłaty, dywidendy — a system przelicza z nich stan portfela, metryki i wykresy w czasie. Aplikacja jest jednoużytkownikowa w sensie operacyjnym (brak organizacji, ról i współdzielenia), ale dane są przypisane do konta użytkownika (`owner_id`).

## Słownik — Domeny Biznesowe

### Portfel i jego zawartość

**Portfel** (`portfolios_portfolio`)
Inwestycyjny „worek” użytkownika: nazwa, waluta bazowa, saldo gotówki, suma wpłat. Użytkownik może mieć wiele portfeli; nazwa jest unikalna w obrębie właściciela. W starej aplikacji Django i w części frontendu (`Pocket*`, `PocketsList`) nazywany `Pocket`.
_Unikać_: Pocket (poza kodem legacy i frontendem do czasu zmiany nazw), konto, rachunek, wallet

**Pozycja** (`portfolios_position`)
Stan posiadania jednego waloru w jednym portfelu: ilość, średnia cena zakupu, średni kurs walutowy, łączne opłaty i dywidendy. Pozycja jest **wynikiem** historii Operacji, nie danymi źródłowymi — można ją odbudować z Operacji. Unikalna na parę (Portfel, Walor); pozycja o ilości 0 jest usuwana.
_Unikać_: holding, udział, lot (nie modelujemy lotów)

**Operacja** (`portfolios_operation`)
Zdarzenie zapisane przez użytkownika, niezmienne co do znaczenia: `buy`, `sell`, `deposit`, `withdrawal`, `dividend`. Operacje są źródłem prawdy o portfelu. Usunięcie lub edycja Operacji wymusza przebudowę salda i Pozycji z pozostałej historii.
_Unikać_: transakcja (w kodzie tylko w nazwie technicznej `transaction()` — granica commitu, nie pojęcie domenowe), transfer, wpis

**Saldo gotówki** (`cash_balance`)
Wolna gotówka w walucie bazowej Portfela. Zakup je zmniejsza, sprzedaż i dywidenda zwiększają, wpłata i wypłata zmieniają.
_Unikać_: cash, środki, wolne środki (zbyt ogólnie)

**Suma wpłat** (`total_deposited`)
Łączna kwota netto wpłat minus wypłat. Podstawa do liczenia wyniku portfela względem zainwestowanego kapitału. Nie zawiera zysków.
_Unikać_: kapitał, wkład własny

### Walory i waluty

**Walor** (`assets_asset`)
Instrument finansowy (akcja, fundusz, obligacja) identyfikowany unikalnym tickerem, z aktualną ceną, giełdą i sektorem. Należy do jednej Klasy waloru i ma jedną Walutę notowania.
_Unikać_: aktywo (w polskim UI „aktywo” bywa używane, ale w kodzie i dokumentach trzymamy „walor”), instrument, papier

**Klasa waloru** (`assets_assetclass`)
Kategoria Waloru: akcja, fundusz, obligacja, itp. Słownik zarządzany przez użytkownika.
_Unikać_: typ waloru, kategoria

**Waluta** (`assets_currency`)
Waluta notowania Waloru lub bazowa Portfela. Niesie kurs wymiany względem waluty bazowej systemu (USD), odświeżany z danych rynkowych; kurs między dwiema dowolnymi walutami to iloraz ich kursów. Waluta bez notowania nie ma kursu — wycena pozycji, która go wymaga, pokazuje „brak kursu” zamiast wartości policzonej po kursie 1.
_Unikać_: kurs (kurs to `exchange_rate`, nie Waluta)

**Kurs walutowy operacji** (`fx_rate`)
Kurs zastosowany w momencie Operacji do przeliczenia wartości z waluty Waloru na walutę bazową Portfela. Zapisany w Operacji, nie wyliczany wstecznie.

**Dane rynkowe**
Aktualne ceny Walorów i kursy walut pobierane z zewnętrznego dostawcy (Yahoo Finance przez `yfinance`). Dostawca jest zależnością zewnętrzną, niestabilną i nieudokumentowaną — błędy pobrania to sytuacja normalna, nie wyjątek.
_Unikać_: feed, notowania (zbyt ogólnie)

### Metryki

**Metryki portfela**
Wartości liczone z historii Operacji i cen w czasie: wartość portfela, koszty transakcji, wpłaty netto, wolna gotówka — w postaci **wektorów** dzienne (interwał `1d`). Są obliczeniami, nie danymi źródłowymi: nigdy nie zapisujemy ich jako prawdy.
_Unikać_: statystyki, analityka (jako nazwa modułu — patrz ADR o warstwie `domain/`)

**Wektor portfela**
Seria wartości metryki dla kolejnych dni w zadanym przedziale; dane do wykresów na froncie.

**Benchmark**
Indeks lub walor referencyjny, z którym porównujemy wynik Portfela.

### Użytkownik i dostęp

**Użytkownik** (`users`)
Właściciel danych. Loguje się e-mailem i hasłem; dostaje token dostępu i odświeżający.
_Unikać_: klient, konto (konto = Użytkownik + jego dane)

## Migracja

**Backend-old**
Dawna aplikacja Django (`backend-old/`), usunięta 2026-10-01 po przepisaniu na FastAPI. Nie wracamy do niej; zachowanie odtwarzają testy parytetu.

## Relacje

- Portfel ma wiele Pozycji i wiele Operacji; Operacja należy do jednego Portfela i (oprócz wpłaty/wypłaty) do jednego Waloru.
- Pozycja jest pochodną Operacji; metryki są pochodnymi Operacji i cen rynkowych.
- Walor należy do Klasy waloru i ma Walutę notowania; Portfel ma Walutę bazową.

## Sprzeczności i niejasności

- Frontend używa nazwy `Pocket`, backend `Portfolio`. Nazewnictwo docelowe: **Portfel / Portfolio**; zmiana nazw we froncie jest poza zakresem przepisywania backendu.
- Operacja `dividend` zwiększa `total_dividends` Pozycji i saldo gotówki, ale nie zmienia `total_deposited`.
