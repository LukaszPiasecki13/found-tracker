---
id: research-pl-tax-brokers
status: current
type: mixed
scope: research/pl-brokers
last_reviewed: 2026-10-03
---

# Jakie formaty eksportu mają brokerzy, których historię trzeba zaimportować?
> **Dokument L4 (dowód).** Stan na 2026-10-01/02. Nienormatywny — rekomendacje stąd stają się obowiązujące dopiero przez ADR lub plan. Append-only: nie poprawiamy, dopisujemy nowe badanie i link do następcy.

Odbiorca: projektujący import w `backend/app/modules/portfolios/`. Kontekst: [05_portfolios_module.md](../technical/backend/05_portfolios_module.md), [01_backend-architecture.md](../technical/backend/01_backend-architecture.md), słownik: [CONTEXT.md](../business/CONTEXT.md). Źródła kursów NBP: dokument `03_rynek_pl_dane_rynkowe.md` w tym katalogu.

**Oznaczenia.** **[wniosek]** = wniosek autora; **[niezweryfikowane]** = snippet / strona trzecia; **rekomendacja** = rada inżynierska.

## 1. Eksporty brokerów

Stan wiedzy: w kodzie nie ma importu ([06_stan_found-tracker_vs_cel.md](./06_stan_found-tracker_vs_cel.md), luka G13). Kolumny podajemy tylko tam, gdzie znaleziono źródło. „nieznane” = nie znaleziono dokumentacji, nie zgadujemy.

| Broker | Eksport | Format | Kolumny (jeśli udokumentowane) | Osobliwości |
|---|---|---|---|---|
| XTB (xStation 5) | Historia konta: zakładki zamknięte pozycje, „Cash Operations” (wpłaty, wypłaty, dywidendy), zlecenia | XLSX (Excel); inne źródło wspomina CSV/HTML **[niezweryfikowane]** (strony pomocy XTB — snippety; WebFetch 403) | nieznane (oficjalnej listy kolumn nie znaleziono) | myfund: „W historii transakcji zamknięte transakcje są łączone w pary kupno/sprzedaż, a otwarte pozycje są jedną pozycją z uśrednioną ceną” → import otwartych pozycji trzeba za każdym razem kasować i wczytywać od nowa (myfund pomoc helpID=30). Forum myfund: „XTB — nowy format pliku eksportu” → format się zmienia. myfund obsługuje też API XTB |
| mBank eMakler (mDM) | nieznane | nieznane | nieznane (znalezione kolumny „Data księg., Kod transakcji, Kwota…” dotyczą rachunku **bankowego** mBank, nie eMaklera) | myfund importuje „mBank” i „MDM” ([01_myfund.md](./competitors/01_myfund.md), inferencja) |
| Bossa (DM BOŚ) | historia transakcji CSV, osobno dla każdego typu rachunku **[niezweryfikowane]** (freenance.io) | CSV | nieznane | osobne pliki per rachunek → mapowanie na osobne Portfele FundTrackera |
| BM PKO BP | nieznane | nieznane | nieznane | myfund obsługuje „PKO BP” |
| Santander BM | nieznane | nieznane | nieznane | myfund obsługuje „Santander” |
| Interactive Brokers | Flex Query (definiowalny raport), CSV lub XML | CSV/XML | Oficjalna lista pól sekcji Trades (ibkrguides.com) obejmuje m.in.: „Currency”, „FX Rate to Base”, „Symbol”, „ISIN”, „Trade Date”, „Trade Time”, „Settle Date Target”, „Quantity”, „Trade Price”, „Proceeds”, „Taxes”, „IB Commission”, „IB Commission Currency”, „Cost Basis”, „Realized PNL”, „Buy/Sell”, „Open/Close Indicator”, „Trade ID”, „Notes/Codes” | Data w formacie `YYYYMMDD` **[niezweryfikowane]** (opis crate ib-flex). `Settle Date Target` daje datę rozrachunku. Kurs „FX Rate to Base” to kurs IB, nie NBP |
| DEGIRO | Transakcje (CSV), Rachunek (CSV) | CSV | **[niezweryfikowane]** (snippet z forum Portfolio Performance): „Date, Time, Product, ISIN, Reference, Venue, Quantity, Price, Local value, Value, Exchange rate, Transaction and/or third, Total” | Nagłówki zlokalizowane wg języka interfejsu **[niezweryfikowane]** |
| Revolut (Trading) | wyciąg inwestycyjny CSV | CSV | nieznane | Navexa: „upload the original CSV without changing its headings” **[niezweryfikowane]** |
| Trading 212 | Historia → „Export history”, typy: „Orders, Dividends and Transactions”; „365 days is the longest possible period”; niedostępne dla kont CFD | CSV | **[niezweryfikowane]** (agregacja snippetów): „Action, Time, ISIN, Ticker, Name, No. of shares, Price / share, Currency (Price / share), Exchange rate, Total (EUR), Withholding tax, Currency (Withholding tax), Charge amount (EUR), Notes, ID” | Nazwa kolumny zawiera walutę konta (np. „(EUR)”) → parser po prefiksie. Limit 365 dni → import wielu plików z deduplikacją po `ID` |
| Exante | nieznane | nieznane | nieznane | myfund: problem importu „VWRD” (Exante AUTOCONVERSION) — automatyczne przewalutowania jako osobne wiersze **[wniosek]** |

**Osobliwości ogólne:** przecinek dziesiętny, kodowanie cp1250 i format daty `DD.MM.YYYY` w eksportach polskich domów maklerskich — **nie potwierdzono** dla żadnego z nich w tym badaniu (brak dostępu do przykładowych plików). **rekomendacja:** importer wykrywa kodowanie (UTF-8 BOM / cp1250), separator (`;`/`,`) i separator dziesiętny z próbki. Każdy parser ma test na zanonimizowanym pliku (wzorzec fixture'ów z Portfolio Performance, [02_trackery_porownanie.md](./competitors/02_trackery_porownanie.md)), a przed zapisem pokazuje podgląd. To samo zalecało badanie myfund ([01_myfund.md](./competitors/01_myfund.md)).

## 2. Wymagania dla importu (rekomendacje)

| # | Wymaganie | Uzasadnienie |
|---|---|---|
| 1 | Surowy plik + mapowanie + `external_id` do deduplikacji; Operacje z importu oznaczone źródłem | Trading 212: limit 365 dni na eksport; XTB: parowanie zamkniętych pozycji |
| 2 | Każdy parser ma test na zanonimizowanym pliku | formaty zmieniają się bez zapowiedzi (XTB, DEGIRO) |

Każda z tych zmian modelu wymaga ADR (CLAUDE.md projektu: ADR-y w `docs/technical/adr/`, status `Proposed`).

## Źródła

Dostęp 2026-10-01/02.
- IBKR Flex Query Trades: https://www.ibkrguides.com/reportingreference/reportguide/tradesfq.htm
- Trading 212 eksport: https://help-en.portfoliodividendtracker.com/article/279-download-your-trading-212-actions (aktualizacja 2026-07-30); kolumny: https://help-en.portfoliodividendtracker.com/article/298-import-your-trading-212-actions (snippet)
- DEGIRO (snippet): https://forum.portfolio-performance.info/t/pdf-import-from-degiro/12145?page=4
- XTB pomoc (snippety, WebFetch 403): https://www.xtb.com/en/help-center/our-platforms/history-on-the-xstation-platform
- Bossa (strona trzecia): poradnik na freenance.io (adres nie zapisany po usunięciu wątku podatkowego)
- Revolut (strona trzecia): https://help.navexa.com/en/articles/16116548-import-trades-from-revolut
- myfund, Import operacji: https://myfund.pl/index.php?raport=pomoc&helpID=30

## Luki i niepewności

1. **Formaty eksportu:** XTB, mBank eMakler, Bossa, BM PKO BP, Santander BM, Revolut, Exante — kolumny nieznane. Trading 212 i DEGIRO — kolumny tylko ze snippetów stron trzecich. Kodowanie, separatory i formaty dat nie potwierdzone.
