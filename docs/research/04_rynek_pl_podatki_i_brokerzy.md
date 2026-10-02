---
id: research-pl-tax-brokers
status: current
type: mixed
scope: research/pl-tax
last_reviewed: 2026-10-02
---

# Jakie reguły podatkowe i formaty brokerów musi obsłużyć polski tracker inwestycji?
> **Dokument L4 (dowód).** Stan na 2026-10-01/02. Nienormatywny — rekomendacje stąd stają się obowiązujące dopiero przez ADR lub plan. Append-only: nie poprawiamy, dopisujemy nowe badanie i link do następcy.

Odbiorca: projektujący model danych i raport podatkowy w `backend/app/modules/portfolios/`. Kontekst: [05_portfolios_module.md](../technical/backend/05_portfolios_module.md), [01_backend-architecture.md](../technical/backend/01_backend-architecture.md), słownik: [CONTEXT.md](../business/CONTEXT.md). Wycena obligacji skarbowych i źródła kursów NBP: dokument `03_rynek_pl_dane_i_obligacje.md` w tym katalogu.

**Oznaczenia.** **[wniosek]** = wniosek autora; **[niezweryfikowane]** = snippet / strona trzecia; **rekomendacja** = rada inżynierska. To nie jest porada podatkowa. FundTracker ma liczyć dane pomocnicze do PIT-38, a nie zastępować PIT-8C.

**Podstawa prawna.** „Ustawa” = ustawa z 26 lipca 1991 r. o podatku dochodowym od osób fizycznych, tekst jednolity: obwieszczenie Marszałka Sejmu z 17 kwietnia 2026 r., Dz.U. 2026 poz. 592 (stan prawny na 1 kwietnia 2026). „Broszura” = MF, „Broszura informacyjna do zeznania PIT-38 … za rok podatkowy 2025”.

## 1. Reguły podatkowe

### 1.1 Stawki i źródła przychodu

| Przychód | Przepis (cytat) | Stawka | Gdzie w PIT-38 |
|---|---|---|---|
| Zbycie papierów wartościowych, pochodnych, akcji/udziałów; umorzenie jednostek funduszy | art. 30b ust. 1: „z odpłatnego zbycia papierów wartościowych lub pochodnych instrumentów finansowych … z umorzenia, odkupienia, wykupienia albo unicestwienia w inny sposób tytułów uczestnictwa w funduszach kapitałowych – podatek dochodowy wynosi 19 % uzyskanego dochodu” | 19% od dochodu | część C/D (poz. 20–35) |
| Waluty wirtualne (krypto) | art. 30b ust. 1a: „Od dochodów uzyskanych z odpłatnego zbycia walut wirtualnych podatek dochodowy wynosi 19 % uzyskanego dochodu.” | 19% | część E/F (poz. 36–45) — **osobna pula** |
| Odsetki i dyskonto od papierów (obligacje), wykup obligacji z kuponem | art. 30a ust. 1 pkt 2 i 2a | 19% od przychodu (ust. 6: „bez pomniejszania przychodu o koszty uzyskania”) | zwykle pobiera płatnik; zagraniczne → część G |
| Dywidendy | art. 30a ust. 1 pkt 4: „z dywidend i innych przychodów z tytułu udziału w zyskach osób prawnych” | 19% od przychodu | zagraniczne → część G (poz. 47–49) |
| Odsetki od środków na rachunku | art. 30a ust. 1 pkt 3 | 19% | płatnik |
| Odsetki z detalicznych obligacji skarbowych | art. 30a ust. 1 pkt 2 | 19% | pobiera agent emisji (przykłady PKO BP) |

- **Źródła się nie łączą.** Art. 30b ust. 5d: „Dochodów z odpłatnego zbycia walut wirtualnych nie łączy się z dochodami opodatkowanymi na zasadach określonych w ust. 1”. Art. 30a ust. 7: dochodów z art. 30a „nie łączy się z dochodami opodatkowanymi na zasadach określonych w art. 27”. **[wniosek]:** strata na akcjach nie pomniejsza podatku od dywidend ani od krypto. Trzeba liczyć trzy pule: (a) art. 30b ust. 1, (b) art. 30b ust. 1a (krypto), (c) art. 30a (zryczałtowany, per zdarzenie).
- **Koszty (pula a):** art. 30b ust. 2 pkt 1 odsyła do art. 23 ust. 1 pkt 38 („wydatków na objęcie lub nabycie … papierów wartościowych … są jednak kosztem uzyskania przychodu z odpłatnego zbycia”). Broszura (cz. C): koszty to „cena jednostkowa x ilość” oraz „prowizje zapłacone przy kupnie i sprzedaży …, opłaty związane z prowadzeniem lub założeniem rachunku, transferu, zdeponowania papierów”. **[wniosek]:** opłaty za rachunek są kosztem, który nie należy do żadnej partii zakupu — model musi go przyjąć jako koszt roczny puli.
- **Koszty krypto (pula b):** art. 22 ust. 14 „udokumentowane wydatki bezpośrednio poniesione na nabycie waluty wirtualnej oraz koszty związane ze zbyciem”; ust. 15 „potrącane w tym roku podatkowym, w którym zostały poniesione”; ust. 16 nadwyżka kosztów „powiększa koszty … poniesione w następnym roku podatkowym”. **[wniosek]:** krypto to pula „koszty roku vs przychody roku”, bez FIFO na partiach zakupu. Wymiana krypto–krypto nie jest zbyciem (art. 17 ust. 1f: zbycie to wymiana „na prawny środek płatniczy, towar, usługę lub prawo majątkowe inne niż waluta wirtualna”). Wydatki na nią nie są kosztem (art. 23 ust. 1 pkt 38d).
- **IPO-ulga:** art. 21 ust. 1 pkt 105a — dochód ze zbycia akcji z pierwszej oferty publicznej (nabytych po 31.12.2021) zwolniony po upływie 3 lat (broszura, wiersz 3, poz. 24–25). Wymaga flagi na partii zakupu.

### 1.2 FIFO

- Art. 24 ust. 10 (cytat): „Jeżeli podatnik dokonuje odpłatnego zbycia papierów wartościowych nabytych po różnych cenach i nie jest możliwe określenie ceny nabycia zbywanych papierów wartościowych, przy ustalaniu dochodu z takiego zbycia stosuje się zasadę, że każdorazowo zbycie dotyczy kolejno papierów wartościowych nabytych najwcześniej. Zasadę, o której mowa w zdaniu pierwszym, stosuje się **odrębnie dla każdego rachunku papierów wartościowych**.”
- Fundusze: art. 30b ust. 7 — FIFO dla tytułów uczestnictwa, „odrębnie do każdego rachunku inwestycyjnego”. Ust. 7a rozszerza to „odpowiednio do innych dochodów, o których mowa w ust. 1, i do dochodów, o których mowa w ust. 1b”.
- Obligacje (dyskonto/wykup): art. 30a ust. 4 — FIFO „odrębnie do każdego rachunku inwestycyjnego”.
- Wyjątek funduszy: art. 17 ust. 1c — konwersja między subfunduszami tego samego funduszu parasolowego nie tworzy przychodu. **[wniosek]:** partia zakupu przechodzi z kosztem i datą.
- **rekomendacja:** FIFO z kluczem `(rachunek, walor)`. Ten sam ISIN w XTB i mBanku to dwie niezależne kolejki.

### 1.3 Przeliczenie walut (art. 11a)

- Ust. 1: „Przychody w walutach obcych przelicza się na złote według kursu średniego walut obcych ogłaszanego przez Narodowy Bank Polski z ostatniego dnia roboczego poprzedzającego dzień uzyskania przychodu.”
- Ust. 2: „Koszty poniesione w walutach obcych przelicza się na złote według kursu średniego ogłaszanego przez Narodowy Bank Polski z ostatniego dnia roboczego poprzedzającego dzień poniesienia kosztu.”
- Ust. 3: to samo dla „podatek” zapłacony za granicą — „z ostatniego dnia roboczego poprzedzającego dzień … zapłaty podatku”.
- **[wniosek]:** kurs kosztu (zakup) i kurs przychodu (sprzedaż) są różne. Partia zakupu musi pamiętać koszt w PLN z dnia D-1 zakupu; nie przelicza się go ponownie przy sprzedaży. Prowizja w walucie: kurs D-1 dnia jej poniesienia.
- **„Dzień roboczy”** dla NBP = dzień, w którym opublikowano tabelę A. Algorytm cofania po 404 opisuje §1.2 dokumentu `03_rynek_pl_dane_i_obligacje.md`.

### 1.4 Data przychodu: transakcja czy rozrachunek?

- Art. 17 ust. 1ab pkt 1: przychód ze zbycia papierów wartościowych „powstaje w momencie przeniesienia na nabywcę własności”. Broszura (cz. C) powtarza: „powstaje w momencie przeniesienia na nabywcę własności papierów wartościowych … (przychodem są kwoty należne choćby nie zostały faktycznie otrzymane)”.
- Fundusze: broszura — przychód z umorzenia „powstaje w momencie otrzymania lub postawienia podatnikowi do dyspozycji pieniędzy”.
- Ustawa o obrocie instrumentami finansowymi, art. 7: zdematerializowane papiery przechodzą na nabywcę „z chwilą dokonania odpowiedniego zapisu na rachunku papierów wartościowych” **[niezweryfikowane]** (snippet lexlege.pl; nie ustalono numeru ustępu; nie pobrano tekstu ustawy). Rozrachunek GPW/KDPW to T+2 od 2014-10-06.
- **[wniosek]:** dla akcji i ETF na rynku regulowanym datą przychodu (i dniem bazowym kursu D-1) jest **data rozrachunku**, nie data zawarcia transakcji. Rozbieżność jest istotna na przełomie roku: sprzedaż 30.12 rozliczona 2.01 → przychód następnego roku. Nie znaleziono interpretacji ogólnej MF przesądzającej to wprost, a brokerzy zagraniczni mogą raportować datę transakcji **[niezweryfikowane]**.
- **rekomendacja:** Operacja ma dwie daty: `trade_date` i `settlement_date`. Do podatku `settlement_date`, z możliwością wyboru w ustawieniach rachunku.

### 1.5 Dywidendy i podatek zagraniczny

- Art. 30a ust. 9: od podatku 19% od zagranicznych przychodów z ust. 1 pkt 1–5 podatnicy „odliczają kwotę równą podatkowi zapłaconemu za granicą, jednakże odliczenie to nie może przekroczyć kwoty podatku obliczonego od tych przychodów (dochodów) przy zastosowaniu stawki 19 %”. Ust. 11: kwoty te wykazuje się w zeznaniu (PIT-38 część G: poz. 47 podatek 19%, poz. 48 zapłacony za granicą, poz. 49 różnica).
- Art. 30a ust. 2: stawki z umów o unikaniu podwójnego opodatkowania (UPO) wymagają „certyfikatem rezydencji”.
- **USA:** po złożeniu W-8BEN pobór u źródła wynosi 15% (UPO PL–US), w Polsce dopłata 19% − 15% = 4% **[niezweryfikowane]** (strony trzecie, np. freenance.io; tekstu UPO nie pobrano). Bez W-8BEN pobór 30% — odliczenie ograniczone do 19%, nadwyżka do odzyskania tylko w USA **[wniosek]** z art. 30a ust. 9.
- **Zyski kapitałowe z zagranicy (pula a):** art. 30b ust. 5a — dochody krajowe i zagraniczne „łączy się” i odlicza podatek zapłacony za granicą do proporcji. Broszura podaje wzór limitu: podatek 19% od łącznego dochodu × dochód zagraniczny / dochód łączny.
- **PIT/ZG:** broszura (cz. L) — załącznik dla dochodów z art. 30b ust. 5a, 5b, 5e, 5f „odrębnie dla każdego państwa”. **[wniosek]:** dywidendy (art. 30a) idą do części G, nie do PIT/ZG. Do PIT/ZG trafia sprzedaż Walorów, gdy podatek zapłacono za granicą. Rachunek PIT/ZG wymaga kraju źródła na Operacji.
- **rekomendacja:** Operacja `DIVIDEND`: `gross`, `wht_amount`, `wht_currency`, `country`, `pay_date`, kurs NBP D-1 dla `pay_date` (art. 11a ust. 1 i 3). Data przychodu = dzień wypłaty **[wniosek]** (art. 30a „uzyskanych”; nie zweryfikowano interpretacją).

### 1.6 Straty, zaokrąglenia, terminy

- **Przenoszenie strat** — art. 9 ust. 3 (cytat): „O wysokość straty ze źródła przychodów, poniesionej w roku podatkowym, podatnik może: 1) obniżyć dochód uzyskany z tego źródła w najbliższych kolejno po sobie następujących pięciu latach podatkowych, z tym że kwota obniżenia w którymkolwiek z tych lat nie może przekroczyć 50 % wysokości tej straty, albo 2) obniżyć jednorazowo dochód uzyskany z tego źródła w jednym z najbliższych kolejno po sobie następujących pięciu lat podatkowych o kwotę nieprzekraczającą 5 000 000 zł, nieodliczona kwota podlega rozliczeniu w pozostałych latach tego pięcioletniego okresu, z tym że kwota obniżenia w którymkolwiek z tych lat nie może przekroczyć 50 % wysokości tej straty.”
- Art. 9 ust. 6 pkt 1 stosuje ust. 3 do strat ze zbycia papierów wartościowych, pkt 5 — do jednostek funduszy kapitałowych. Art. 9 ust. 3a pkt 2: ust. 3 **nie** dotyczy strat „z odpłatnego zbycia walut wirtualnych” (krypto ma mechanizm z art. 22 ust. 16).
- Broszura (cz. D, poz. 30): odliczenie w PIT-38 za 2025 dotyczy strat z lat 2020–2024. „Kwota z poz. 30 nie może przekroczyć kwoty z poz. 28.”
- **Zaokrąglenia (broszura):** podstawę opodatkowania (poz. 31, 41) i podatek należny (poz. 35, 45) zaokrągla się „do pełnych złotych w ten sposób, że końcówki kwot wynoszące mniej niż 50 groszy pomija się, a końcówki kwot wynoszące 50 i więcej groszy podwyższa się”. Wyjątek: „zgodnie z art. 63 § 1a Ordynacji podatkowej” podatek z art. 30a ust. 1 pkt 1–3 — „do pełnych groszy w górę”. Tekstu Ordynacji nie pobrano **[niezweryfikowane]** (cytat za broszurą). Przykłady PKO BP dla obligacji temu przeczą — patrz `03_rynek_pl_dane_i_obligacje.md` §2.4.
- **Termin:** art. 45 ust. 1 — zeznanie „w terminie od dnia 15 lutego do dnia 30 kwietnia roku następującego po roku podatkowym”. Ust. 1a pkt 1: odrębne zeznanie dla dochodów z art. 30b (PIT-38).
- **PIT-8C:** broszura, cz. C wiersz 1 — poz. 20/21 z poz. 35/36 PIT-8C. Brokerzy zagraniczni PIT-8C nie wystawiają → wiersz 2 (poz. 22/23). **rekomendacja:** raport FundTrackera rozbity na „krajowe z PIT-8C” (do porównania z PIT-8C) i „zagraniczne / bez PIT-8C”.

## 2. Rachunki z ulgą: IKE, IKZE, PPK, OIPE

| Rachunek | Zwolnienie / ulga (cytat) | Wypłata | Limit 2025 | Limit 2026 |
|---|---|---|---|---|
| IKE | art. 21 ust. 1 pkt 58a: wolne „dochody z tytułu oszczędzania na indywidualnym koncie emerytalnym … uzyskane w związku z: a) gromadzeniem i wypłatą środków”; zwolnienie nie działa, gdy oszczędzający miał „więcej niż jednym indywidualnym koncie emerytalnym” | zwrot (nie wypłata) → 19%: art. 30a ust. 1 pkt 10; dochód = wartość − suma wpłat (ust. 8) | 26 019 zł | 28 260 zł (obwieszczenie MRPiPS z 17.11.2025, M.P. 2025 poz. 1202) |
| IKZE | art. 26 ust. 1 pkt 2b: odliczenie od dochodu „wpłat na indywidualne konto zabezpieczenia emerytalnego dokonanych przez podatnika w roku podatkowym, do wysokości określonej w przepisach” | art. 30 ust. 1 pkt 14: „od kwoty wypłat z indywidualnego konta zabezpieczenia emerytalnego … w wysokości 10 % przychodu”; transfery zwolnione (art. 21 ust. 1 pkt 58b) | 10 407,60 zł; samozatrudnieni 15 611,40 zł | 11 304 zł; samozatrudnieni 16 956 zł (obwieszczenie MRPiPS z 10.11.2025, M.P. 2025 poz. 1156) |
| OIPE | art. 21 ust. 1 pkt 58aa (gromadzenie i wypłata zwolnione); zwrot → 19% art. 30a ust. 1 pkt 10a | — | — | 28 260 zł (M.P. 2025 poz. 1151) |
| PPK | art. 21 ust. 1 pkt 58c — dochody z uczestnictwa w PPK, „z zastrzeżeniem art. 30a ust. 1 pkt 11a i 11b”; dopłaty roczne i wpłata powitalna wolne (pkt 47f) | 19% przy zwrotach i wypłatach z art. 30a ust. 1 pkt 11a–11f | brak limitu wpłat (procent wynagrodzenia) **[niezweryfikowane]** | — |

- Limity 2025/2026 pochodzą z artykułów czasopismo.legeartis.org (listopad 2025), które cytują numery M.P.; samych obwieszczeń w Monitorze Polskim nie pobrano **[niezweryfikowane — źródło wtórne z referencją do pierwotnego]**. Inne snippety podawały inne kwoty dla 2026 (np. „26 532 zł i 10 612 zł”, freenance.io) — przyjęto wartości z referencją M.P.
- **[wniosek]:** strata na IKE/IKZE nie wchodzi do PIT-38. Art. 9 ust. 3a pkt 4 wyłącza przenoszenie strat „ze źródeł przychodów, z których dochody są wolne od podatku”, a art. 30a ust. 8d — dochodu IKE „nie pomniejsza się o straty”.
- **rekomendacja:** rachunek ma `tax_wrapper ∈ {NONE, IKE, IKZE, PPK, OIPE}`. Operacje na rachunku z ulgą nie zasilają pul PIT-38, a dywidendy na nim nie generują dopłaty. Limit wpłat roczny per `tax_wrapper` (tabela konfiguracji per rok) z ostrzeżeniem przy przekroczeniu. IKZE: raport „wpłaty do odliczenia w PIT-37/36” (art. 26 ust. 1 pkt 2b). Detaliczne obligacje skarbowe mogą leżeć na IKE/IKZE w PKO BP (list emisyjny 99/2026 ust. 6) — bez opłaty za przedterminowy wykup przy wypłacie z IKE/IKZE.

## 3. Eksporty brokerów

Stan wiedzy: w kodzie nie ma importu (`research_codebase.md` G13: „No import/export”). Kolumny podajemy tylko tam, gdzie znaleziono źródło. „nieznane” = nie znaleziono dokumentacji, nie zgadujemy.

| Broker | Eksport | Format | Kolumny (jeśli udokumentowane) | Osobliwości |
|---|---|---|---|---|
| XTB (xStation 5) | Historia konta: zakładki zamknięte pozycje, „Cash Operations” (wpłaty, wypłaty, dywidendy), zlecenia | XLSX (Excel); inne źródło wspomina CSV/HTML **[niezweryfikowane]** (strony pomocy XTB — snippety; WebFetch 403) | nieznane (oficjalnej listy kolumn nie znaleziono) | myfund: „W historii transakcji zamknięte transakcje są łączone w pary kupno/sprzedaż, a otwarte pozycje są jedną pozycją z uśrednioną ceną” → import otwartych pozycji trzeba za każdym razem kasować i wczytywać od nowa (myfund pomoc helpID=30). Forum myfund: „XTB — nowy format pliku eksportu” → format się zmienia. myfund obsługuje też API XTB |
| mBank eMakler (mDM) | nieznane | nieznane | nieznane (znalezione kolumny „Data księg., Kod transakcji, Kwota…” dotyczą rachunku **bankowego** mBank, nie eMaklera) | myfund importuje „mBank” i „MDM” (badanie myfund, inferencja) |
| Bossa (DM BOŚ) | historia transakcji CSV, osobno dla rachunku zwykłego, IKE, IKZE **[niezweryfikowane]** (freenance.io) | CSV | nieznane | rachunki IKE/IKZE = osobne pliki → mapowanie na osobne rachunki FundTrackera |
| BM PKO BP | nieznane | nieznane | nieznane | myfund obsługuje „PKO BP” |
| Santander BM | nieznane | nieznane | nieznane | myfund obsługuje „Santander” |
| Interactive Brokers | Flex Query (definiowalny raport), CSV lub XML | CSV/XML | Oficjalna lista pól sekcji Trades (ibkrguides.com) obejmuje m.in.: „Currency”, „FX Rate to Base”, „Symbol”, „ISIN”, „Trade Date”, „Trade Time”, „Settle Date Target”, „Quantity”, „Trade Price”, „Proceeds”, „Taxes”, „IB Commission”, „IB Commission Currency”, „Cost Basis”, „Realized PNL”, „Buy/Sell”, „Open/Close Indicator”, „Trade ID”, „Notes/Codes” | Data w formacie `YYYYMMDD` **[niezweryfikowane]** (opis crate ib-flex). `Settle Date Target` daje datę rozrachunku (§1.4). Kurs „FX Rate to Base” to kurs IB, nie NBP — **nie** używać do podatku |
| DEGIRO | Transakcje (CSV), Rachunek (CSV) | CSV | **[niezweryfikowane]** (snippet z forum Portfolio Performance): „Date, Time, Product, ISIN, Reference, Venue, Quantity, Price, Local value, Value, Exchange rate, Transaction and/or third, Total” | Nagłówki zlokalizowane wg języka interfejsu **[niezweryfikowane]** |
| Revolut (Trading) | wyciąg inwestycyjny CSV | CSV | nieznane | Navexa: „upload the original CSV without changing its headings” **[niezweryfikowane]** |
| Trading 212 | Historia → „Export history”, typy: „Orders, Dividends and Transactions”; „365 days is the longest possible period”; niedostępne dla kont CFD | CSV | **[niezweryfikowane]** (agregacja snippetów): „Action, Time, ISIN, Ticker, Name, No. of shares, Price / share, Currency (Price / share), Exchange rate, Total (EUR), Withholding tax, Currency (Withholding tax), Charge amount (EUR), Notes, ID” | Nazwa kolumny zawiera walutę konta (np. „(EUR)”) → parser po prefiksie. Limit 365 dni → import wielu plików z deduplikacją po `ID` |
| Exante | nieznane | nieznane | nieznane | myfund: problem importu „VWRD” (Exante AUTOCONVERSION) — automatyczne przewalutowania jako osobne wiersze **[wniosek]** |
| obligacjeskarbowe.pl (PKO BP) | nieznane (nie zbadano serwisu transakcyjnego) | nieznane | nieznane | Pozycję obligacji można odtworzyć z (seria, data zakupu, liczba sztuk) — wycena wg wzorów z listu emisyjnego |

**Osobliwości ogólne:** przecinek dziesiętny, kodowanie cp1250 i format daty `DD.MM.YYYY` w eksportach polskich domów maklerskich — **nie potwierdzono** dla żadnego z nich w tym badaniu (brak dostępu do przykładowych plików). **rekomendacja:** importer wykrywa kodowanie (UTF-8 BOM / cp1250), separator (`;`/`,`) i separator dziesiętny z próbki. Każdy parser ma test na zanonimizowanym pliku (wzorzec fixture'ów z Portfolio Performance, `research_competitors.md`), a przed zapisem pokazuje podgląd. To samo zalecało badanie myfund.

## 4. Wymagania dla modelu danych FundTrackera (rekomendacje)

| # | Wymaganie | Uzasadnienie (przepis / źródło) | Dotyczy |
|---|---|---|---|
| 1 | **Rachunek** (rachunek maklerski) jako byt: broker, waluta bazowa, `tax_wrapper` (NONE/IKE/IKZE/PPK/OIPE), kraj brokera, `settlement_lag` | FIFO „odrębnie dla każdego rachunku” (art. 24 ust. 10; art. 30b ust. 7); zwolnienia IKE/IKZE (art. 21 ust. 1 pkt 58a, 58b) | Portfel ↔ rachunek: Portfel może grupować kilka rachunków |
| 2 | **FIFO per (rachunek, Walor)** na partiach zakupu (lotach podatkowych) z kosztem w PLN zamrożonym w dniu nabycia | art. 24 ust. 10, art. 11a ust. 2 | dziś `average_buy_price` — zostaje dla UI |
| 3 | **Kurs NBP D-1 zapisany w Operacji**: `fx_rate`, `fx_table_no`, `fx_effective_date` (osobno dla kosztu, przychodu, prowizji, WHT) | art. 11a ust. 1–3 | Operacje w walucie ≠ PLN |
| 4 | **Dwie daty Operacji**: `trade_date`, `settlement_date`; podatek liczony od `settlement_date` | art. 17 ust. 1ab, broszura cz. C; T+2 | akcje, ETF, obligacje giełdowe |
| 5 | **Trzy pule podatkowe**: 30b ust. 1 (papiery/fundusze/pochodne), 30b ust. 1a (krypto: koszty roczne + carry-forward nadwyżki kosztów), 30a (dywidendy/odsetki: per zdarzenie, z WHT) | art. 30b ust. 5d; art. 22 ust. 14–16; art. 30a ust. 7, 9 | raport PIT-38 części C–G |
| 6 | **Dywidenda / odsetki**: brutto, WHT, waluta WHT, kraj źródła, data wypłaty | art. 30a ust. 9, 11; PIT/ZG per kraj (broszura cz. L) | Operacja `DIVIDEND`, `INTEREST` |
| 7 | **Rejestr strat** per rok i pula, z historią odliczeń (≤ 50% rocznie albo jednorazowo ≤ 5 000 000 zł, 5 lat); krypto wyłączone | art. 9 ust. 3, 3a pkt 2, ust. 6 | raport roczny |
| 8 | **Zaokrąglenia jako reguła per pole** (podstawa i podatek do pełnych zł; 30a pkt 1–3 do groszy) — liczyć na `Decimal`, zaokrąglać tylko na wyjściu raportu | broszura PIT-38; ADR-0010 projektu (Decimal) | raport |
| 9 | **Koszty bez partii**: opłaty za prowadzenie rachunku, przelew papierów — koszt roczny puli (a) | broszura cz. C | Operacja `FEE` z flagą „koszt podatkowy” |
| 10 | **Flagi partii**: IPO-ulga (data dopuszczenia + 3 lata), darowizna (koszt 0), spadek (koszt spadkodawcy) | art. 21 ust. 1 pkt 105a; broszura cz. C | rzadkie, ale zmieniają wynik |
| 11 | **Obligacje skarbowe detaliczne** jako osobna Klasa waloru: seria, data zakupu, stopy per okres (fakty), opłata z listu; wycena wzorem, nie ceną rynkową | listy emisyjne 97–99/2026; `03_rynek_pl_dane_i_obligacje.md` §2 | Pozycja = (seria, data zakupu) |
| 12 | **Import**: surowy plik + mapowanie + `external_id` do deduplikacji; Operacje z importu oznaczone źródłem | Trading 212 limit 365 dni; XTB parowanie pozycji | moduł importu (nowy) |
| 13 | **Limity IKE/IKZE/OIPE** jako tabela konfiguracji per rok (wartości z obwieszczeń) | M.P. 2025 poz. 1151, 1156, 1202 | ostrzeżenia UI |

Każda z tych zmian modelu wymaga ADR (CLAUDE.md projektu: ADR-y w `docs/technical/adr/`, status `Proposed`).

## Źródła

Dostęp 2026-10-01/02.
- Ustawa o PIT, t.j. Dz.U. 2026 poz. 592 (obwieszczenie z 17.04.2026): https://dziennikustaw.gov.pl/DU/2026/592 — tekst pobrany jako PDF przez wcześniejszy etap badania. Artykuły: 9, 11a, 17, 21, 22, 23, 24, 26, 30, 30a, 30b, 45.
- MF, Broszura informacyjna do zeznania PIT-38 za 2025: https://www.podatki.gov.pl/pit/ (portal; dokładnego URL pliku nie zapisano — plik pobrany przez wcześniejszy etap).
- Limity IKE/IKZE/OIPE: https://czasopismo.legeartis.org/2025/11/limit-wplat-ike-2026/ ; https://czasopismo.legeartis.org/2025/11/limit-wplat-ikze-2026-oipe-suma-skladek-dodatkowych-ppe-obwieszczenie-mrpips/
- Limity 2025 (snippet): https://www.gazetaprawna.pl/praca/emerytury-i-renty/artykuly/10917855,ostatni-moment-by-skorzystac-z-limitow-ike-i-ikze.html
- Ustawa o obrocie instrumentami finansowymi art. 7 (snippet): https://lexlege.pl/ustawa-o-obrocie-instrumentami-finansowymi/art-7/
- KDPW T+2: https://www.30.kdpw.pl/uploads/user_files/zmiana_cyklu_rozrachunkowego_z_t_plus_3_na_t_plus_2.pdf (snippet)
- Dywidendy USA / W-8BEN (strona trzecia): https://freenance.io/podatki/podatek-od-dywidend-amerykanskich-2026-w-8ben-15-procent-jak-zlozyc-rozliczyc-pit-38/
- IBKR Flex Query Trades: https://www.ibkrguides.com/reportingreference/reportguide/tradesfq.htm
- Trading 212 eksport: https://help-en.portfoliodividendtracker.com/article/279-download-your-trading-212-actions (aktualizacja 2026-07-30); kolumny: https://help-en.portfoliodividendtracker.com/article/298-import-your-trading-212-actions (snippet)
- DEGIRO (snippet): https://forum.portfolio-performance.info/t/pdf-import-from-degiro/12145?page=4
- XTB pomoc (snippety, WebFetch 403): https://www.xtb.com/en/help-center/our-platforms/history-on-the-xstation-platform
- Bossa (strona trzecia): https://freenance.io/poradniki/jak-sledzic-portfel-bossa-w-freenance-2026-pl-emakler-ike-ikze-dywidenda-pit-38-tutorial-krok-po-kroku/
- Revolut (strona trzecia): https://help.navexa.com/en/articles/16116548-import-trades-from-revolut
- myfund, Import operacji: https://myfund.pl/index.php?raport=pomoc&helpID=30
- Listy emisyjne obligacji 97–99/2026: patrz `03_rynek_pl_dane_i_obligacje.md`.

## Luki i niepewności

1. **Data przychodu (transakcja vs rozrachunek):** wniosek oparty na art. 17 ust. 1ab i art. 7 ustawy o obrocie (ten ostatni tylko ze snippetu). Brak interpretacji ogólnej MF.
2. **Art. 63 Ordynacji podatkowej** — nie pobrano tekstu; zaokrąglenia cytowane za broszurą MF. Przykłady PKO BP są sprzeczne z regułą „w górę”.
3. **UPO PL–US (15%)** i procedura W-8BEN — tylko źródła trzecie.
4. **Limity IKE/IKZE/OIPE 2025–2026** — źródło wtórne z numerami M.P.; obwieszczeń nie pobrano. Limit IKE jako „3× prognozowane wynagrodzenie” — nie zweryfikowano w ustawie o IKE/IKZE.
5. **Formaty eksportu:** XTB, mBank eMakler, Bossa, BM PKO BP, Santander BM, Revolut, Exante, obligacjeskarbowe.pl — kolumny nieznane. Trading 212 i DEGIRO — kolumny tylko ze snippetów stron trzecich. Kodowanie, separatory i formaty dat nie potwierdzone.
6. **Data przychodu z dywidendy** (wypłata vs ustalenie prawa) — wniosek, bez interpretacji.
7. **PPK** — nie sprawdzono zasad wpłat ani limitów.
8. Wydarzenia korporacyjne (spin-off, prawo poboru) — skutki podatkowe dla kosztu nabycia nie przeanalizowane.
