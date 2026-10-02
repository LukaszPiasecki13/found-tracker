---
id: adr-0003-multicurrency-cash
status: Proposed
type: decision
scope: business/cash
last_reviewed: 2026-10-02
---

# Gotówka to salda per (Portfel, Waluta); istniejące Operacje rozliczone w Walucie bazowej; automatyczne wpłaty są danymi pochodnymi

Saldo gotówki per **(Portfel, Waluta)**; przeliczenie walut to Operacja **Przewalutowanie**. Istniejące Operacje dostają `currency_id` = Waluta bazowa. Automatyczne wpłaty nie tworzą wierszy Operacji.

**Rozstrzyga:** D4 i E2.2b. **Blokuje:** E2.2, E2.2b, E2.3, E2.5, E3.1, E4.1.

## Kontekst

- Dziś jedno saldo `Portfolio.cash_balance` w Walucie bazowej (`backend/app/modules/portfolios/models/portfolio.py:38-43`).
- `fx_rate` = „Waluta bazowa za 1 jednostkę Waluty Waloru” (`domain/ledger.py:171-258`): zakup/sprzedaż/dywidenda przeliczają gotówkę przez `fx_rate`, prowizja w walucie Waloru; wpłata i wypłata — w Walucie bazowej, bez `fx_rate`. Brokerzy rozdzielają waluty ([dowód 04](../../research/04_rynek_pl_podatki_i_brokerzy.md), §3).

## Decyzja

1. **Saldo**: tabela pochodna `portfolios_cash_balance(portfolio_id, currency_id, balance)`, unikalność `(portfolio_id, currency_id)`, **[propozycja]** `Numeric(18,3)`. Saldo ujemne per Waluta: `INSUFFICIENT_CASH`.
2. **Waluta nogi gotówkowej**: `currency_id` w Operacji, jawne dla nowych wierszy (domyślnie Waluta waloru; wpłata/wypłata/opłata — Waluta bazowa). Kupno/sprzedaż/dywidenda: Waluta Waloru albo bazowa Portfela; trzecia wymaga Przewalutowania. NULL tylko do pkt 4.
3. **`fx_rate`** — semantyka bez zmian. (a) Noga w Walucie bazowej, Waluta Waloru ≠ bazowa: `fx_rate` (> 0) przelicza nogę jak dziś. (b) Noga w Walucie Waloru: `fx_rate` nie rusza gotówki, służy kosztowi partii w Walucie Portfela ([ADR 0002](0002-koszt-nabycia-partie-fifo.md)); wymagany, gdy Waluta Waloru ≠ bazowa.
4. **Migracja**: `currency_id` = `base_currency_id` Portfela dla wszystkich dotychczasowych Operacji (`rebuild-all`, D16); NULL po backfillu nie ma semantyki. `rebuild-all` zapisuje też `operation_day` i `sequence` ([ADR 0005](0005-daty-operacji-i-zdarzenie-podatkowe.md)). Saldo w Walucie bazowej bez zmian (do grosza), w pozostałych 0.
5. **Przewalutowanie** (E2.2): `amount`/`currency_id` = noga wychodząca, `counter_amount`/`counter_currency_id` = przychodząca (D9, [ADR 0020](../../technical/adr/0020-plaski-model-operacji.md)); prowizja w walucie nogi wychodzącej **[propozycja]**.
6. **`cash_balance` i `total_deposited`** zostają jako kolumny pochodne zapisywane przez `rebuild`: `cash_balance` = saldo w Walucie bazowej; API dodaje `cash_balances[]`. `total_deposited` = wpłaty netto w Walucie bazowej (obca waluta po `fx_rate` dnia); nie jest podstawą TWR ([ADR 0004](0004-metodologia-stop-zwrotu.md)).
7. **Automatyczne wpłaty (E2.2b)**: `portfolios_portfolio.auto_funding` Boolean, domyślnie wyłączone **[propozycja]**. `rebuild` traktuje niedobór przy zakupie jako wirtualną wpłatę, a przychód (sprzedaż, dywidenda, odsetki) jako wirtualną wypłatę (saldo 0). Zapis w pochodnej `portfolios_auto_flow` ([doc 07 5.8](../../technical/backend/07_schemat_danych_docelowy.md)); TWR i XIRR czytają ją jako przepływy zewnętrzne.
8. **Testy**: `test_ledger_parity.py` bez zmian; nowy `test_ledger_multicurrency.py` (zakup USD z salda USD i z PLN, przewalutowanie, `INSUFFICIENT_CASH`, równoważność legacy, idempotencja `auto_funding`).

## Alternatywy

- Jedno saldo w Walucie bazowej — nie odtwarza rachunku z USD/EUR.
- Reinterpretacja legacy `fx_rate` — zmienia saldo istniejących Operacji, łamie parytet.
- Auto-wpłaty jako wiersze `portfolios_operation` — rozjazd przy edycji, łamie P3.
- Usunięcie `cash_balance` od razu — zmiana nieaddytywna.

## Konsekwencje

- (+) Saldo per waluta jak w wyciągu; parytet zachowany.
- (−) Dwa sposoby rozliczenia tej samej Operacji.
- (−) `cash_balance` = tylko Waluta bazowa; auto-wpłaty nieedytowalne (linie „auto”).

## Otwarte

- Dywidendy i odsetki w `auto_funding`: wypłata (rekomendacja) czy zostają na saldzie — zmienia TWR.
- Waluta prowizji przewalutowania i kolejność w dniu (`sequence`).
- Termin usunięcia kolumn `cash_balance`/`total_deposited`.
