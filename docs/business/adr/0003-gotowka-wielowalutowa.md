---
id: adr-0003-multicurrency-cash
status: Proposed
type: decision
scope: business/cash
last_reviewed: 2026-10-02
---

# Gotówka jest salda per (Portfel, Waluta); istniejące Operacje reinterpretujemy jako rozliczone w Walucie bazowej; automatyczne wpłaty są danymi pochodnymi

Rekomendacja: saldo gotówki przechowujemy per **(Portfel, Waluta)**, a przeliczenie między walutami to jawna Operacja **Przewalutowanie**. Istniejące Operacje zachowują dokładnie obecne skutki: dostają `currency_id` = Waluta bazowa Portfela, więc `cash_balance` po migracji jest identyczne. Tryb automatycznych wpłat (E2.2b) nie tworzy wierszy Operacji — dopisuje dane pochodne.

**Rozstrzyga decyzję roadmapy:** D4 oraz punkt E2.2b. **Blokuje:** E2.2, E2.2b, E2.3 (przelewy i przewalutowania), E2.5 (przepływy w snapshotach), E3.1, E4.1 (import samych transakcji).

## Kontekst

- Dziś jedno saldo `Portfolio.cash_balance` `Numeric(18,3)` w Walucie bazowej i `total_deposited` `Numeric(18,3)` (`backend/app/modules/portfolios/models/portfolio.py:38-43`); stan księgi to jeden `Decimal` (`domain/ledger.py:105`).
- **Jak dziś rozumiany jest `fx_rate`** (zweryfikowane w `domain/ledger.py`): to kurs „waluta bazowa Portfela za 1 jednostkę waluty Waloru”. Zakup: gotówka `−= (ilość·cena + prowizja)·fx_rate` (l.171, 199); sprzedaż: `+= (ilość·cena − prowizja)·fx_rate` (l.213); dywidenda: `+= (kwota − prowizja)·fx_rate` (l.258); prowizja jest więc w walucie Waloru. Wpłata i wypłata: `kwota` i `prowizja` w Walucie bazowej, **bez** `fx_rate` (l.232, 239). `average_fx_rate` to ważona ilością średnia tego kursu (l.193). `CONTEXT.md`: „kurs … do przeliczenia z waluty Waloru na walutę bazową Portfela”.
- Zakup akcji USD w Portfelu PLN odejmuje więc złotówki; nie ma salda USD ani miejsca na przewalutowanie. Eksporty brokerów (IBKR, Trading 212, Exante `AUTOCONVERSION`) rozdzielają waluty i przewalutowania ([dowód 04](../../research/04_rynek_pl_podatki_i_brokerzy.md), §3).
- Zasada P3 (plan §2): Operacje są źródłem prawdy; wszystko inne da się odbudować.

## Decyzja

1. **Saldo**: tabela pochodna `portfolios_cash_balance(portfolio_id, currency_id, balance)` **[propozycja: `Numeric(18,3)`, jak dziś]**; unikalność `(portfolio_id, currency_id)`. Saldo ujemne jest zabronione per Waluta (błąd `INSUFFICIENT_CASH` z Walutą) — jak dziś w jednej walucie.
2. **Waluta nogi gotówkowej**: Operacja dostaje `currency_id`, zawsze jawne dla nowych wierszy (API domyślnie wypełnia Walutą waloru, a dla wpłaty/wypłaty/opłaty Walutą bazową Portfela). Kolumna jest nullable tylko do czasu `rebuild-all` (pkt 4). Dozwolone wartości dla kupna/sprzedaży/dywidendy: **Waluta Waloru albo Waluta bazowa Portfela**; trzecia waluta wymaga najpierw Przewalutowania.
3. **Znaczenie `fx_rate` po zmianie**: bez zmiany semantyki — kurs „Waluta bazowa za 1 jednostkę Waluty Waloru” w dniu Operacji. (a) Gdy noga gotówkowa jest w Walucie bazowej i Waluta Waloru ≠ bazowa: `fx_rate` przelicza nogę jak dziś (wymagany, > 0). (b) Gdy noga jest w Walucie Waloru: `fx_rate` **nie wpływa na gotówkę**, służy kosztowi partii w Walucie Portfela ([ADR 0002](0002-koszt-nabycia-partie-fifo.md)) i jest wymagany, gdy Waluta Waloru ≠ bazowa.
4. **Reinterpretacja istniejących Operacji**: migracja ustawia `currency_id` = `base_currency_id` Portfela dla wszystkich dotychczasowych Operacji (komenda `rebuild-all`, D16 — nie edytujemy migracji ręcznie); po backfillu NULL nie ma żadnej semantyki (w szczególności nie znaczy „Waluta waloru”). `rebuild-all` zapisuje też `operation_day` i `sequence` ([ADR 0005](0005-daty-operacji-i-zdarzenie-podatkowe.md)). Skutek: każda dotychczasowa Operacja daje to samo saldo w Walucie bazowej co dziś; saldo w pozostałych walutach = 0. `Portfolio.cash_balance` po przebudowie = saldo w Walucie bazowej sprzed migracji (do grosza). Skala salda i cache Portfela: `Numeric(18,3)`.
5. **Przewalutowanie** (nowy typ, E2.2): `amount`/`currency_id` = noga wychodząca (kwota „z”), `counter_amount`/`counter_currency_id` = noga przychodząca (kwota „do”; D9, [ADR 0020](../../technical/adr/0020-plaski-model-operacji.md)), kurs wynika z ilorazu; prowizja w walucie nogi wychodzącej **[propozycja]**. Zmienia dwa salda, nie zmienia wartości Portfela poza prowizją.
6. **`Portfolio.cash_balance` i `total_deposited`**: kolumny zostają jako **pochodne** zapisywane przez `rebuild`, bez usuwania (zmiana addytywna): `cash_balance` = saldo w Walucie bazowej Portfela (bez przeliczania innych walut); API dodaje `cash_balances[]` per Waluta. „Wolna gotówka łącznie” to wielkość **wyceny** (kursy dzienne), nie zapisywana. `total_deposited` = wpłaty netto w Walucie bazowej: wpłata w innej walucie wymaga `fx_rate` dnia wpłaty i wchodzi po kursie; to liczba informacyjna, nie podstawa TWR ([ADR 0004](0004-metodologia-stop-zwrotu.md)).
7. **Automatyczne wpłaty (E2.2b) — wariant pochodny.** Ustawienie `portfolios_portfolio.auto_funding` (Boolean, domyślnie wyłączone **[propozycja]**). Przy włączeniu `rebuild` traktuje niedobór gotówki przy zakupie jako wirtualną wpłatę w tej walucie, a przychody gotówkowe ze sprzedaży, dywidendy i odsetek jako wirtualną wypłatę (saldo pozostaje 0 — „portfel bezgotówkowy”). Zapis w tabeli pochodnej `portfolios_auto_flow(portfolio_id, flow_day, sequence, currency_id, flow_type, amount, trigger_operation_id)` (kolumny jak w [doc 07 5.8](../../technical/backend/07_schemat_danych_docelowy.md)), odbudowywanej przy każdym `rebuild`. TWR i XIRR czytają ją jako przepływy zewnętrzne.
8. **Testy parytetu**: `test_ledger_parity.py` (7 testów) pozostaje bez zmian i dowodzi punktu 4 (scenariusze Django w Walucie bazowej); parytet zielony: `LedgerState.cash_balance` zostaje właściwością = saldo Waluty bazowej. Nowa baza: `test_ledger_multicurrency.py` ze złotymi scenariuszami: zakup USD z salda USD (`fx_rate` nie rusza gotówki), zakup USD z PLN (`fx_rate` rusza), przewalutowanie, brak salda → `INSUFFICIENT_CASH`, równoważność legacy (replay z `currency_id` = baza daje stan sprzed zmiany), idempotencja `rebuild` z `auto_funding`.

## Rozpatrywane alternatywy

| Opcja | Koszt / ryzyko | Werdykt |
|---|---|---|
| A. Jedno saldo w Walucie bazowej (dziś) | nie da się wiernie odtworzyć rachunku z saldem USD/EUR; przewalutowania brokera znikają; zgodność z wyciągiem ±0,01 (M1) niemożliwa | odrzucona |
| B. Reinterpretacja legacy `fx_rate` jako kursu nogi w Walucie Waloru | zmieniłaby saldo istniejących Operacji (kasa PLN → USD) i złamała parytet | odrzucona |
| C. Automatyczne wpłaty jako wiersze `portfolios_operation` | widoczne i edytowalne w Historii, ale: edycja/usunięcie zakupu wymaga odtworzenia powiązanych wierszy; ręczna edycja wiersza „auto” rozjeżdża regułę; deduplikacja przy imporcie; łamie P3 (Operacje generowane z Operacji) | odrzucona |
| D. Automatyczne wpłaty jako dane pochodne (rekomendacja) | niewidoczne jako edytowalne Operacje — UI pokazuje je jako linie „auto”; wymaga tabeli pochodnej i czytania jej w metrykach | wybrana |
| E. Usunąć `cash_balance` z `portfolios_portfolio` od razu | zmiana nieaddytywna, psuje kontrakt API i frontend | odroczona do osobnego ADR |

## Konsekwencje

**Pozytywne**
- Saldo odpowiada wyciągowi brokera per waluta; istniejące dane i testy parytetu zachowane bez zmiany wyniku.
- Edycja Operacji wyzwalającej przelicza wpłaty automatycznie (jedna ścieżka `rebuild`).

**Negatywne**
- Dwa sposoby rozliczenia tej samej Operacji (Waluta bazowa z kursem vs Waluta Waloru) — użytkownik musi rozumieć, które wybiera; UI domyślnie podpowiada Walutę Waloru.
- `cash_balance` na liście Portfeli oznacza tylko gotówkę w Walucie bazowej; łączna wartość gotówki to wycena (zależna od kursu).
- `total_deposited` dla wpłat w obcej walucie zależy od wpisanego kursu dnia wpłaty — przybliżenie.
- Wpłaty automatyczne nie są edytowalne; błędny import „samych transakcji” poprawia się przez Operacje źródłowe.

## Zmiany słownika po akceptacji

| Pojęcie | Wpis w `CONTEXT.md` |
|---|---|
| **Saldo gotówki** (zmiana) | „Wolna gotówka Portfela osobno w każdej Walucie.” Pole `cash_balance` = saldo w Walucie bazowej. _Unikać_: gotówka łączna jako wielkość zapisana |
| **Przewalutowanie** | Operacja zmieniająca dwa salda gotówki jednego Portfela (kwota „z”, kwota „do”, kurs, prowizja). _Unikać_: wymiana walut, exchange, konwersja |
| **Wpłata automatyczna** | Dana pochodna trybu `auto_funding`: wirtualny przepływ zewnętrzny z niedoboru lub przychodu. _Unikać_: wpłata (to słowo oznacza Operację `deposit`) |
| **Kurs walutowy operacji** (zmiana) | Dodać: wpływa na gotówkę tylko gdy noga gotówkowa jest w Walucie bazowej |

## Otwarte

- Czy dywidendy i odsetki w `auto_funding` mają być wypłatą (rekomendacja: tak — saldo 0), czy zostawać na saldzie; zmienia TWR Portfela.
- Waluta prowizji przewalutowania i kolejność w dniu ([ADR 0005](0005-daty-operacji-i-zdarzenie-podatkowe.md), `sequence`).
- Termin usunięcia kolumn pochodnych `cash_balance`/`total_deposited` (osobny ADR).
