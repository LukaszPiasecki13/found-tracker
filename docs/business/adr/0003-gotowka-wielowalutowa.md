---
id: adr-0003-multicurrency-cash
status: Accepted
type: decision
scope: business/cash
last_reviewed: 2026-10-03
---

# Gotówka to salda per (Portfel, Waluta); automatyczne wpłaty są danymi pochodnymi

Saldo gotówki per **(Portfel, Waluta)**; zamiana walut to Operacja **Przewalutowanie**. Opcjonalne automatyczne wpłaty nie tworzą wierszy Operacji.

**Rozstrzyga:** D4 i E2.2b. **Blokuje:** E2.2, E2.2b, E2.3, E2.5, E3.1, E4.1.

## Kontekst

- Dziś jedno saldo `Portfolio.cash_balance` w Walucie bazowej (`backend/app/modules/portfolios/models/portfolio.py:38-43`).
- `fx_rate` = „Waluta bazowa za 1 jednostkę Waluty Waloru” (`domain/ledger.py:171-258`). Brokerzy rozdzielają waluty ([dowód 04](../../research/04_rynek_pl_brokerzy.md), §3).

## Decyzja

1. **Saldo**: tabela pochodna `portfolios_cash_balance(portfolio_id, currency_id, balance)`, unikalność `(portfolio_id, currency_id)`, **[propozycja]** `Numeric(18,3)`. Saldo ujemne per Waluta: `INSUFFICIENT_CASH`.
2. **Waluta nogi gotówkowej**: `currency_id` w Operacji, NOT NULL (domyślnie Waluta waloru; wpłata/wypłata/opłata — Waluta bazowa). Kupno/sprzedaż/dywidenda: Waluta Waloru albo bazowa Portfela; trzecia wymaga Przewalutowania. Dywidenda trafia na saldo w walucie wypłaty (np. MSFT w USD → gotówka USD).
3. **Kursy: dwa**. `fx_rate` w Operacji to kurs brokera, zamrożony przy zapisie; wycena używa dziennego kursu z `assets_fx_rate`. (a) Noga w Walucie bazowej, Waluta Waloru ≠ bazowa: `fx_rate` (> 0) przelicza nogę. (b) Noga w Walucie Waloru: `fx_rate` nie rusza gotówki, służy kosztowi partii w Walucie Portfela ([ADR 0002](0002-koszt-nabycia-partie-fifo.md)); wymagany, gdy Waluta Waloru ≠ bazowa.
4. **Start od zera**: brak migracji i backfillu istniejących Operacji; dane powstają przez seed/import, a `currency_id` jest wymagane od pierwszego wiersza.
5. **Przewalutowanie** (E2.2): `amount`/`currency_id` = noga wychodząca, `counter_amount`/`counter_currency_id` = przychodząca ([ADR 0020](../../technical/adr/0020-plaski-model-operacji.md)); prowizja w walucie nogi wychodzącej.
6. **`cash_balance` i `total_deposited`** to kolumny pochodne zapisywane przez `rebuild`: `cash_balance` = saldo w Walucie bazowej; API dodaje `cash_balances[]`. `total_deposited` = wpłaty netto w Walucie bazowej (obca waluta po `fx_rate` dnia); nie jest podstawą TWR ([ADR 0004](0004-metodologia-stop-zwrotu.md)).
7. **Automatyczne wpłaty (E2.2b)**: `portfolios_portfolio.auto_funding` Boolean, domyślnie wyłączone **[propozycja]**. `rebuild` traktuje niedobór przy zakupie jako wirtualną wpłatę. Dywidendy i odsetki **nie** są wirtualną wypłatą — zostają na saldzie. Zapis w pochodnej `portfolios_auto_flow` ([doc 07 5.8](../../technical/backend/07_schemat_danych_docelowy.md)); TWR i XIRR czytają ją jako przepływy zewnętrzne.
8. **Testy**: `test_ledger_multicurrency.py` (zakup USD z salda USD i z PLN, przewalutowanie, `INSUFFICIENT_CASH`, idempotencja `auto_funding`).

## Alternatywy

- Jedno saldo w Walucie bazowej — nie odtwarza rachunku z USD/EUR.
- Auto-wpłaty jako wiersze `portfolios_operation` — rozjazd przy edycji.

## Konsekwencje

- (+) Saldo per waluta jak w wyciągu.
- (−) `cash_balance` = tylko Waluta bazowa; auto-wpłaty nieedytowalne (linie „auto”).

## Otwarte

- Termin usunięcia kolumn `cash_balance`/`total_deposited`.
