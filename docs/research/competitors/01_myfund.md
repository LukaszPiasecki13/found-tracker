---
id: research-competitor-myfund
status: current
type: mixed
scope: research/competitors
last_reviewed: 2026-10-02
---

# Co dokładnie oferuje myfund.pl i gdzie jest słaby?

> **Dokument L4 (dowód).** Stan na 2026-10-01/02. Nienormatywny — rekomendacje stąd stają się obowiązujące dopiero przez ADR lub plan. Append-only: nie poprawiamy, dopisujemy nowe badanie i link do następcy.

Materiał: strony myfund.pl pobrane 2026-10-01 jako użytkownik niezalogowany (pomoc, FAQ, cennik, forum) + recenzje stron trzecich. Odnośniki `[TAG]` rozwijają się w tabeli „Źródła” na końcu. Oznaczenia: **[wniosek]** — wniosek autora, nie tekst źródła; **[niezweryfikowane]** — tylko strona trzecia/snippet; **rekomendacja** — rada inżynierska. Słownik FundTrackera: [CONTEXT.md](../../business/CONTEXT.md). Opisując myfund używam jego nazw („aktywa”, „transakcja”, „konto”).

## 0. TL;DR

- Dojrzały (wzmianki o ~2009 r. [PORTFEO]), rozwijany jednoosobowo serwis PHP (właściciel: *Black Fire Damian Piechocki* [REG]). Stan 2026-10-01: 81 589 użytkowników, 194 061 portfeli, 18,4 mld PLN, 22 373 347 operacji, „50+ rynków” [HOME].
- Główna przewaga: **polska specyfika** — TFI, OFE/PPK/PPE/IKE/IKZE/OIPE, obligacje skarbowe (wcześniejszy wykup, zamiana serii, optymalizator), Catalyst (automatyczne odsetki i wykup), PP/PDA, spin-offy, PIT-38 FIFO/HIFO, NBP, straty z 5 lat [H-OP][H-TAX][H-INNE].
- Wycena: **jednostki portfela jak w funduszu (TWR)**, opcjonalnie MWR lub prosta stopa; portfele gotówkowe vs bezgotówkowe [FAQ][H-OPC][H-RAP].
- Ogromna analityka (Sharpe/Sortino/VaR/Beta, Time Under Water, YoC, Snowball 0–100), ale ~połowa za planem Expert [CENNIK].
- Słabości: przeładowany „arkuszowy” UI, wysoki próg wejścia, zawodny import dla części brokerów, mobile długo słabe (przebudowa 4.00 w 07.2026), API = jeden endpoint read-only, automatyczna synchronizacja tylko XTB [PORTFEO][APPSTORE][H-IMP][F-API].
- Cennik od 2026-10-01: 4,99 / 9,99 / 15,99 / 24,99 zł/mies., brak darmowego planu, 30 dni triala Expert [CENNIK][F-CENNIK].
- Ryzyko „bus factor” i jakość danych (2 223 tematy w dziale „Usterki, błędy”) [F-DEATH][F-ABOUT].

## 1. Model danych: użytkownik → portfele → konta → operacje

### 1.1 Portfele

| Element | Opis | Źródło |
|---|---|---|
| Portfel | ≥1 na użytkownika; operacje przypisane do portfela; limit 1/5/20/99 wg planu | [H-START][CENNIK] |
| Gotówkowy | Kupno wymaga gotówki; „algorytmy spójności” odrzucają operacje dające ujemne saldo lub ujemną ilość | [FAQ] |
| Bezgotówkowy | System sam dopisuje „Automatyczna wpłata/wypłata” przy każdym kupnie/sprzedaży | [FAQ] |
| Flagi | archiwalny, ukryty, publiczny, wirtualny (poza podsumowaniami), „w Kokpicie” | [H-OPC] |
| Grupowy | Agregacja portfeli; bez własnych operacji/importu/wzorców; własna data zerowania, TWR/MWR, waluta, benchmarki | [H-INNE] |
| Bliźniaczy | Wirtualna kopia 1:1 operacji źródła z innymi opcjami (waluta, podatek, prowizje) i opcjonalną skalą % (np. 70/30) | [H-INNE] |
| Sub-portfel | Wycinek po tagach ze wszystkich portfeli (kupno, sprzedaż, konwersje, dywidendy, odsetki) | [H-INNE] |
| Narzędzia | Kopiowanie (z datą graniczną), eksport/import całego portfela, przywracanie usuniętego do 7 dni | [H-OPC] |
| Data zerowania | Od niej liczony zysk/stopa w widoku składu | [H-RAP] |
| Waluta przeliczenia | Zmienialna; wpływa na zysk i stopę (z efektem kursowym) | [H-RAP][H-OPC] |

### 1.2 Konta

| Element | Opis | Źródło |
|---|---|---|
| Konta gotówkowe | Domyślne „Gotówka”; dowolna liczba w dowolnej walucie | [FAQ][H-OPC] |
| Konta inwestycyjne | Odpowiednik rachunku w DM/TFI; każde kupno/sprzedaż można przypisać | [H-OPC] |
| Typy kont | „Ogólne – uwzględniaj podatek”, „Ogólne – nie uwzględniaj podatku”, „IKE/IKZE/PPE/OIPE”, IKE, IKZE, PPE, PPK, OIPE | [H-OPC] |
| Statusy | Domyślne, Debetowe (bez kontroli salda), zaokrąglanie splitów do pełnych jednostek, „Monituj o dodanie odsetek”, Aktywne | [H-OPC] |
| PPK | Konto PLN z 3 subkontami: Pracownika, Pracodawcy, Państwa | [H-OPC][H-OP] |
| PPE | Parametr „udział własny” (np. 12% ⇒ automatyczny przychód nadzwyczajny 88% wpłaty) | [H-OPC] |
| Oszczędnościowe | Osobna grupa walorów, nie zerowana w portfelach bezgotówkowych | [H-OPC] |
| Prowizje domyślne | Per konto i typ waloru: procent + minimum; autowyliczanie i szacunek prowizji od sprzedaży | [H-OPC] |
| Stawki podatku | Dywidendy/odsetki, hierarchia **walor > typ waloru > konto > portfel > domyślna**, z datą „od” | [H-OPC] |
| Księgowanie dywidend | Reguła: konto inwestycyjne + waluta → wybrane konto gotówkowe | [H-OPC] |
| Odsetki od kont | **Nie** naliczane automatycznie (wpis ręczny lub przypomnienie) | [FAQ] |

### 1.3 Klasy aktywów

FAQ: akcje GPW i NewConnect, obligacje GPW/Catalyst/skarbowe, kontrakty GPW, akcje zagraniczne (NYSE, NASDAQ, LSE, Börse „i wiele innych”), TFI, OFE, waluty, lokaty, pożyczki społecznościowe, walory użytkownika, nieruchomości, ruchomości [FAQ]. Ponadto: produkty strukturyzowane, certyfikaty, surowce [GPLAY]; kryptowaluty (brak tylko bezpośredniego API Binance/Bybit) [H-IMP][H-TAX][F-FREEN]; ETF-y (dodawane do bazy na prośbę) i opcje [F-BUGS]; monety/sztabki z wagą w oz/g [H-RAP]; Forex/CFD z lotem, depozytem i dźwignią [H-IMP]; krótka sprzedaż [H-OP]. Obligacje skarbowe: przy kupnie wybiera się *typ oraz miesiąc i rok wykupu* [H-OP]; system „nalicza wartość wraz z należnymi odsetkami” [F-FREEN], optymalizator zna marżę obligacji indeksowanych inflacją [H-INNE] — lista obsługiwanych serii (EDO/COI/ROD…) **[niezweryfikowane]**. Walor zagraniczny spoza bazy użytkownik dodaje po tickerze z finance.yahoo.com [H-INNE]. Nieruchomości: przychody (czynsz), koszty, inwestycja w wartość, wyceny ręczne, powiązanie z kredytem [H-OP].

### 1.4 Katalog typów operacji ([H-OP], chyba że zaznaczono)

| Operacja | Co robi | Uwagi |
|---|---|---|
| Wpłata / wypłata | Przepływ zewnętrzny na konto gotówkowe | Wpływa na liczbę jednostek |
| Przychód / koszt nadzwyczajny | Gotówka bez waloru | Kategorie użytkownika |
| Odsetki z kont, zyski z lokat, podatek | Zapisy gotówkowe | Flaga „Podatek z PIT-38” |
| Przelew gotówkowy | Między kontami, także między portfelami, z prowizją | Przewalutowanie = przelew między kontami w różnych walutach |
| Lokata | Założenie (kapitalizacja co N mies. / bez), dzienna wycena z odsetkami, auto-zamknięcie, 19% podatku | Odsetki/kupony w trakcie |
| Kupno / sprzedaż | Kurs przeliczeniowy przy innej walucie; prowizja kwotowo/%; walidacja „Sprawdź cenę” (min–max sesji) | Sprzedaż FIFO, **opcjonalnie wskazanie konkretnego kupna** (od 05.2026, pod XTB) [H-OP][FAQ] |
| Kupno z zobowiązaniem | Przypięcie kredytu do zakupu | Odsetki doliczane do kosztu |
| Kupno wg alokacji wzorcowej | Rozbicie jednej wpłaty na walory wg % | — |
| Kupno PPK ze składkami | Pracownik/pracodawca/państwo | Podatek od składki pracodawcy automatycznie (17% / 32%) |
| Pożyczki społecznościowe | Udzielenie, rata, umorzenie, niespłacalność, sprzedaż | — |
| Walor użytkownika | Dowolny (gram złota, sztuka) | Ręczne wyceny historyczne, poziom ryzyka |
| Krótka sprzedaż | Otwarcie/zamknięcie z depozytem | — |
| Konwersje | Akcje→Akcje (zmiana nazwy auto od 2016-10-22, połączenia), PDA→Akcje, PP→Akcje (cena emisyjna), TFI→TFI (auto koszt/przychód różnicy zaokrągleń od 2011-07-08), PPE, PPK, OFE, **Obligacje→Obligacje** (zamiana serii = odsetki + sprzedaż + kupno) | [H-OP][FAQ] |
| Prawa poboru | Teoretyczna wartość PP do pierwszego notowania | — |
| Spin-off | Automatyczny współczynnik i korekta ceny nabycia | — |
| Połączenie spółek | Automatyczne dla zdefiniowanych w bazie | Ekwiwalent za ułamki wg średniej 30-dniowej |
| Split | Automatyczny; ceny historyczne korygowane wstecz | Przy wpisie historycznym trzeba odznaczyć „Sprawdź cenę” [FAQ] |
| Dywidenda | Automatyczna dla portfeli od 2014-09-16 (przelicza się przy zmianie ilości na dzień prawa); ręczna z rokiem dywidendy; obce waluty z kursem | [H-OP][FAQ] |
| Odsetki / wykup Catalyst | Odsetki auto od 2016-03-30 (D+2 KDPW); wykup auto od 2018-03-08 (podatek od dyskonta); częściowy wykup od 2020-04-01 | — |
| Wcześniejszy wykup obl. skarbowych | Odsetki i opłata wyliczane wg typu | Bez podatku na IKE/IKZE/OIPE |
| Nieruchomości/ruchomości | Przychód, koszt, inwestycja w wartość | — |
| Przychód / koszt waloru | Np. zwrot prowizji, ekwiwalent po splicie; przechowanie złota | — |
| Zobowiązania | Dodanie (typ, waluta, okres, oprocentowanie), spłata (kapitał/odsetki — tylko odsetki obniżają stopę), zwiększenie, refinansowanie, rejestr zmian oprocentowania | [H-OP][FAQ] |
| Transfer | Stary: sztuczna sprzedaż+kupno po cenie zamknięcia; nowy: walor/konto/portfel bez sztucznych transakcji, z zachowaniem historii i ceny nabycia | — |
| Kontrakty terminowe | Depozyt 10% wartości, dzienne rozliczenie (saldo może być ujemne) | [FAQ] |
| Operacje cykliczne | Szablon (kwota PLN lub %, cykl, reguła dnia wolnego: w dniu / poprzedni / następny roboczy) | [H-CYK] |
| Historia operacji | Sortowanie, filtry, komentarze, edycja/usuwanie z walidacją spójności | [H-HIST][FAQ] |
| Metadane | Notatki, wiele tagów na walor (też na typy/konta), własne nazwy, typy z kolorem, ryzyko, wyceny, exercise price, wykluczenia z automatów | [H-INNE] |

### 1.5 Wielowalutowość

- Konta i zobowiązania w dowolnej walucie; przy różnicy waluty operacji i konta użytkownik podaje kurs [H-OP][FAQ].
- Zysk w PLN = wartość w PLN dziś − wartość nabycia w PLN (z efektem kursowym); FAQ tłumaczy, czemu wynik różni się od XTB/mBanku [FAQ].
- Raport „Wpłacony kapitał według waluty” odróżnia wpłaty zewnętrzne od przewalutowań (rozpoznaje pary „Currency conversion” z importu); Kokpit sumuje portfele per waluta [H-RAP].

## 2. Analityka

### 2.1 Metodologia stopy zwrotu

| Metoda | Definicja w myfund | Źródło |
|---|---|---|
| **Jednostki portfela = TWR** (domyślna) | Pierwsza wpłata kupuje jednostki po 100 PLN, kolejne wpłaty/wypłaty kupują/umarzają je po bieżącej wartości jednostki — „dokładnie tak samo jak w funduszach” | [FAQ] |
| MWR | Wybór w opcjach (także dla grupy); liczba jednostek = wartość / stopa zwrotu, zmienia się bez przepływów | [H-OPC][H-WSK][H-RAP] |
| Prosta stopa zwrotu | W Kokpicie | [H-RAP][H-WSK] |
| Średnioroczna | CAGR | [H-RAP][H-WSK] |
| YTM obligacji | XIRR przeliczone na konwencję rynkową [(1+IRR)^(1/M)−1]·M | [H-WSK] |
| Oczekiwana stopa (cel) | Iteracyjnie jak IRR | [H-WSK] |

Opcje zmieniające wynik: „Uwzględnij podatek” (szacowany podatek Belki od otwartych i niezapłaconych zamkniętych pozycji, ze stratami z 5 lat), „Uwzględnij prowizję od sprzedaży”, „Uwzględnij dywidendy/odsetki w zysku”, uwzględnianie konwersji TFI w średniej cenie [H-RAP][H-TAX]. Średnia cena i zysk niezrealizowany wg **FIFO** (z przejęciami, zmianami nazw, splitami) [FAQ].

### 2.2 Raporty i wykresy ([H-RAP], chyba że zaznaczono)

Wspólne: zakres dat na każdym wykresie; agregacja dzienna → tygodniowa (>½ roku) → miesięczna (>3 lata); eksport tabel i wykresów do CSV/XLS; tabele sortowalne i filtrowalne.

| Grupa | Raporty |
|---|---|
| Skład | Per walor: ryzyko (kolor), zmiana dzienna (waluta portfela i waloru), ilość, średnia cena z prowizją, ostatnia cena, data/godzina wyceny, okres, wartość, udział, zysk %/nominalny, CAGR; grupowanie typ/konto/ryzyko/sektor; ręczne nadpisanie ceny (purpurowe); auto-odświeżanie ≤10 min; kafelki FIRE/Runway i „Cel dochodu z dywidend i odsetek” |
| Statystyki ryzyka | Max Drawdown, maks. czas do nowego ATH, czas od ATH, Beta (WIG, WIG20 + 3 benchmarki; dzienna/tygodniowa), Information ratio, odchylenie standardowe (r/m/t/d), VaR 95% (historyczny 1-dniowy), Sharpe, Sortino |
| Szeregi czasowe | Wartość i liczba jednostek, zmienność stopy (rolling stdev), rolling return (annualizowany, okno 1/3 lata), drawdown, **Time Under Water** (okresy pod ATH, czas powrotu, histogram dni wg głębokości) [H-INNE] |
| Zysk i wkład | Zysk w czasie (sumaryczny/okresowy/drawdown zysku; dla grupy warstwowo; śróddziennie 5 min dla 1 dnia, 1 h do 15 dni), wartość inwestycji, wkład i wartość, wkład i zysk, wpłaty/wypłaty (stacked), kapitał wg waluty |
| Benchmarki | Stopa zwrotu w czasie z **do 10 benchmarkami** (indeksy, fundusze, inflacja, lokaty, własny, inny portfel/grupa, portfel publiczny) z korektą ±pp/rok + stała stopa; benchmarki kategorii funduszy (średnia popularnych: dłużne PL, pieniężne, akcji PL MiŚ, akcji PL, akcji zagr., dłużne zagr.) [H-OPC]; stopa w okresach (t/m/r vs WIG, WIG20, inflacja, lokaty + histogram); zmiana okresowa |
| Struktura | W czasie: typy, walory, tagi, konta, sektory, waluty, udział portfeli w grupie; ekspozycja walutowa (ETF rozbijane na waluty) + mapa świata z walut; analiza sektorowa, indeksowa (GPW/NC), per tag; analiza ryzyka (7 grup wg zmienności dziennej z roku albo 9 grup **SRRI** z tygodniowej zmienności 5 lat) |
| Dochód | Dywidendy w czasie (suma, zmiana, skumulowana, do średniej wartości/wkładu), **YoC** per walor i rok (koszt partii FIFO na dzień prawa), odsetki od obligacji, prowizje (też % obrotu) |
| Kalendaria | Kalendarium spółek (dywidendy, WZA, raporty, PP, emisje, indeksy, wezwania, splity + wydarzenia użytkowników z moderacją); dywidend 12 mies. z prognozą (dywidenda roku poprzedniego × ilość); roczny widok dywidend i odsetek [H-INNE] |
| Wizualizacje rynku | Mapa cieplna portfela (kafelek ∝ wartość, kolor −5%…+5%, dowolna data), heatmapa GPW/NC, statystyki GPW/NC (powyżej SMA, przy ATH) [H-INNE] |
| Zamknięte inwestycje | Podsumowanie (przychód, dywidendy, KUP, prowizja, zysk %), szczegóły per zamknięcie (FIFO), win rate, profit factor, max zysk/strata, symulacja zamknięcia otwartych |
| Porównania | Zysk per typ/konto, udział walorów per konto, ranking walorów, porównanie stóp (do 4 walorów, w walucie), w okresach, analiza kupna w okresach, struktura kupna (partie zakupu) |
| Kokpit | Wszystkie portfele: zmiana dzienna ważona, wartość netto (po zobowiązaniach), zysk całkowity/bieżący, d/m/r/od założenia, CAGR, top 3, mini-wykres; porównania do 10 portfeli |
| Majątek | Zobowiązania w czasie, majątek = inwestycje − zobowiązania, struktura majątku |
| Inne | Bilans kontraktów, skaner obligacji Catalyst [CENNIK][F-DEV], analiza szczegółowa waloru, scatter stopa vs ryzyko [H-INNE], analiza fundamentalna (8 wskaźników, do 5 spółek), skaner spółek (100+ wskaźników, zapisane filtry) [H-SCAN], AT z widgetem TradingView, świece D/W/M z naniesionymi transakcjami |

### 2.3 Kondycja portfela (Snowball) — tylko Expert [H-RAP]

Deterministyczny wynik 0–100 (bez AI): **100 − 20×„Ważne” − 10×„Uwaga” − 3×„Obserwacja”**. Reguły (próg Uwaga/Ważne):

| Reguła | Progi |
|---|---|
| Dominacja pojedynczej pozycji | ≥25% / ≥35% |
| TOP3 pozycje | ≥60% / ≥75% |
| Efektywna liczba pozycji 1/HHI | < 5 |
| Dominująca klasa | ≥65% / ≥80% |
| Sektor | ≥30% / ≥45% |
| Ekspozycja walutowa | ≥60% / ≥80% |
| Kapitał w stratnych pozycjach | ≥40% / ≥65% |
| Pozycja głęboko na minusie | ≤−20% przy udziale ≥5% |
| Pozostałe | koncentracja zysków, koncentracja ruchu dziennego, śladowe pozycje, wyceny starsze niż 7 dni; ETF-y traktowane specjalnie |

### 2.4 Cele, FIRE, rebalancing, strategie

| Funkcja | Opis | Źródło |
|---|---|---|
| Portfele wzorcowe | 5 rodzajów wzorca (typy, tagi, sektory GPW/NC, walory, ryzyko) + wzorzec udziału portfeli w grupie; % lub nominalnie z marginesem ±pp; „Inner rails”; wartość docelowa; e-mail o przekroczeniu | [H-WZ] |
| Rebalancing | Zwykły; tylko kupno do wzorca; tylko kupno / tylko sprzedaż / kupno i sprzedaż do wartości docelowej; zmiana udziału jednej pozycji | [H-WZ] |
| Cel inwestycyjny | Start/koniec, wartość początkowa, wpłata miesięczna (może być wyliczona), dodatkowe wpłaty, oczekiwana stopa; wykres rzeczywistość vs ścieżka, faza wypłat | [H-INNE][H-WSK] |
| FIRE / Runway | Koszty życia, realna stopa, inflacja (nominal = (1+r)(1+π)−1), SWR; kapitał minus zobowiązania i nieruchomości | [H-INNE][H-RAP] |
| PPK | Projekcja wartości; symulacja wypłaty teraz (30% pracodawcy do ZUS, część państwowa pomijana, 19% od zysku) | [H-RAP] |
| Wielkość pozycji | Maks. liczba akcji wg ryzyka na pozycję i Stop Loss | [H-INNE] |
| Strategie (sygnały) | Wybicie z kanału, przebicie SMA, EMA, EMA/SMA, SMA/EMA, Darwin+Defender, Siła Relatywna (Levy), GEM + dual momentum, Momentum, AEM, Kirkpatrick | [H-STR] |

## 3. Podatki — tylko plan Expert ([H-TAX][CENNIK])

| Funkcja | Szczegóły |
|---|---|
| Oblicz podatek | Rok/miesiąc/kwartał, jeden lub wiele portfeli; tabela o strukturze **PIT-8C** per walor; daty rozliczenia KDPW (akcje/PDA D+2, obligacje/PP D+2, kontrakty D+0); FIFO niezależnie per portfel i konto |
| Szczegóły | Każda sprzedaż z dopasowanymi partiami zakupu (FIFO), kurs **NBP D−1 lub D+1** (opcja), przychód/koszt w walucie i PLN |
| Straty z lat ubiegłych | Do 2018: max 50% straty z roku; od 2019: 100% (≤5 mln PLN); 5 lat |
| Optymalizuj podatek | Które otwarte partie zamknąć do końca roku; ostatni dzień transakcji w roku; max/min strata do odliczenia; **FIFO i HIFO** (HIFO dla części TFI); interaktywny wybór partii |
| Dywidendy zagraniczne | 19% w PL minus WHT (≤ stawka UPO 15%), kurs z dnia poprzedzającego wypłatę; autor: „najlepsza wiedza”, interpretacje US mogą się różnić |
| Kryptowaluty | Przychód: krypto→fiat; koszt: fiat→krypto + prowizje fiat; koszty z lat ubiegłych; NBP z poprzedniego dnia roboczego |
| Inne | Odsetki z kont/lokat zagranicznych, odsetki obligacji korporacyjnych (gdy DM nie pobrał, zmiany od 2023-01-01), pożyczki społecznościowe |
| Szacunek w wynikach | „Uwzględnij podatek”, wyłączany dla IKE/IKZE |
| Limity IKE/IKZE/PPE/OIPE | Pozostała kwota wpłat w roku per konto — **wszystkie plany** [H-INNE][CENNIK] |

## 4. Import danych

### 4.1 Mechanizmy [H-IMP]

1. **Wklejka CSV (średnik)**:
   `Data(RRRR-MM-DD HH:MI:SS);nazwa waloru;KUPNO|SPRZEDAŻ;ilość [waluta];cena;prowizja;kurs [waluta konta]` — cena
   i prowizja opcjonalne (brana wycena z dnia); fundusze muszą mieć nazwy jak w myfund („nazwy funduszy nie są
   znormalizowane”).
2. **Plik brokera** — wybór pliku i „Banku (źródła pliku)”, **podgląd w tabeli przed importem**; brak formatu ⇒
   próbka do autora.
3. **Kreator portfela AI** (Pro+) — zgaduje brokera z pliku historii, tworzy portfel, konta, ustawienia, operacje;
   kolejne importy „starą metodą”.
4. **Forex/CFD** (liczba = loty × wielkość lota, depozyt, dźwignia).
5. **Przepływy gotówkowe**: `Data;Wpłata|Wypłata|Koszt|Przychód;wartość;typ` oraz `Data;Odsetki;brutto;podatek`.
6. **Transfery krypto / przelewy fiat**: `Data;Przelew;wpłata [WAL];wypłata [WAL];prowizja [WAL];komentarz`.
7. **Historia spłat kredytu**, **koszty/przychody nieruchomości** (z banku).
8. **E-mail**: przekierowanie potwierdzeń z DM na `import@myfund.pl`; konfiguracja (nadawca, DM, opcjonalnie numer
   rachunku → konto), obsługa duplikatów, auto-wpłata; „mail uniwersalny” z `[IMPORT]` w temacie i składnią
   `[Kupno;2017-08-04 12:34:56;KGHM;100;120;59;Wybicie]`. Nowy parser DM „max 24 h” po przesłaniu próbki.
9. **API brokera** — „W tej chwili myfund.pl obsługuje tylko API z XTB” (login + hasło, opcjonalnie zapisane
   zaszyfrowane); otwarte pozycje XTB re-importowane za każdym razem.
10. **Wtyczka Chrome „myfund.pl – Exporter”** (scraping): Finax, mBank SFI, Noble Securities, BNP Paribas PPK,
    Millenium PPK, Investors PPK, Santander PPK.
11. **Eksport/import całego portfela** (własny format) [H-OPC].

Starsza treść FAQ mówi, że import obejmuje tylko kupno/sprzedaż GPW [FAQ] — sprzeczne z nowszą pomocą; **[wniosek]** FAQ nieaktualne w tym punkcie.

### 4.2 Integracje (78 nazw w [INTEG]; strona główna deklaruje „100+” [HOME])

- **Brokerzy PL**: XTB, mBank, MDM, BOS, PKO BP, Santander, Alior, Pekao, ING, BNP Paribas, Noble, BDM, BMMS, Millennium PPK, Dif.
- **Brokerzy zagraniczni**: DEGIRO, Interactive Brokers, Lynx, Exante, Saxo Bank, Trading 212, Revolut, eToro, Freedom24, Freetrade, Firstrade, Tastyworks, InvestEngine, Oanda, Finax, Private Wealth Consulting.
- **Krypto**: Binance, BitBay, Bitget, Bybit, Coinbase, Crypto.com, Kraken, Kanga, Ledger, Robinhood Crypto.
- **TFI/PPK/PPE/OFE/IKE**: Allianz (OFE/PPK/TFI), NN (DFE, DFE PPK, OFE, PPK, TFI, Nnppk3), PZU (IKE/OFE/PPE/PPK, inPZU), Generali (+PPK), Uniqa (+OFE/PPK), Esaliens (PPK/TFI), Investors (PPE/PPK), Compensa PPK, PFR PPK, PKO PPK, Pekao PPK, Pocztylion PPK, Santander PPK, Orange PPE, Bankowy OFE, Vienna OFE, Analizy.pl, KupFundusz.
- **Inne**: Obligacje Skarbowe, GoldSaver, Zus Konto.
- **[wniosek]**: „BOS” = DM BOŚ (film w pomocy pokazuje import z DM BOŚ [H-IMP]); „MDM” = mBank DM; „Obligacje Skarbowe” = obligacjeskarbowe.pl. Instrukcje per instytucja (`raport=ImportFileGuides`) wymagają logowania — nie pobrano.

### 4.3 Problemy z importem

- Wątki „Import z XTB” (22 wpisy, 23 687 wyświetleń), „XTB — nowy format pliku eksportu”, „Problem z importem VWRD” (Exante AUTOCONVERSION), „nie można importować transakcji” [F-BUGS][F-DEV].
- Portfeo (konkurent, 2026-05-05): „skuteczność importu plików od brokerów i giełd krypto bywa różna; inwestorzy często spędzają godziny na ręcznym poprawianiu raportów” [PORTFEO].

## 5. Alerty, raporty e-mail, społeczność, notowania

| Funkcja | Opis | Źródło |
|---|---|---|
| Alerty (Pro+) | E-mail, push w mobile. SL/TP: kwota, % od daty startu, % od ostatniej/średniej ceny zakupu, % od max/min 365 dni, spadek jednostki od ATH; C/Z (P/E z 4Q); kroczące KSL/KTP; zmiana dzienna; jednorazowe/wielokrotne (analiza nocna ~4:00, bo wyceny TFI po 22:00) i online (co 10 min, „minimalny czas trwania”) | [H-AL][FAQ][CENNIK] |
| Podsumowania e-mail (Expert) | Do 3 harmonogramów (portfele, okres, godzina, dni) | [H-RAP][CENNIK] |
| Powiadomienia | Przekroczenie wzorca, nowe sygnały AT, wydarzenia spółek, operacje w portfelach subskrybowanych | [H-WZ][H-INNE][H-MOB] |
| Informacje rynkowe (Pro+) | Sygnały AT, ESPI/EBI, rekomendacje, kalendarium | [CENNIK][H-INNE] |
| Portfele publiczne | Lista z wyceną jednostki, CAGR, ryzykiem, „wiarygodnością”, obserwującymi; ukrycie kwot, historii, hasło, banner, wątek-blog | [H-PUB] |
| Portfele subskrybowane | Cena min. 100 zł/rok, okresy 1–36 mies., podział netto 30% myfund / 70% właściciel | [H-SUB] |
| Forum | 6 919 tematów, 31 639 wpisów; de facto changelog, bugtracker i support; forum spółek w mobile | [F-ABOUT][H-INNE] |
| Notowania i ranking | Watchlista, ulubione porównania, notowania bieżące/historyczne z filtrami; ranking funduszy (Sharpe 12M, udział zakupów użytkowników, stopy 6/12/36M; statystyczny: mediana i 75 percentyl 22-dniowych stóp) — także bez abonamentu | [H-INNE][H-RANK][CENNIK] |
| Dla doradców | White-label z logo, zarządzanie klientami, 3 mies. testu; widget WWW, program partnerski, gadżet Windows (Pro+) | [DORADCY][CENNIK] |

## 6. Cennik i macierz plan → funkcje (stan 2026-10-01)

Dla FundTrackera (single-user, self-hosted) cennik nie ma znaczenia — istotne jest tylko to, **które funkcje myfund uznaje za „premium”**, bo to sygnał, za co użytkownicy płacą **[wniosek]**.

Ceny brutto; nowe ceny dla nowych kont od 2026-10-01, dotychczasowi zachowują stare do 2027-06-30; poprzednia zmiana w połowie 2022 r. [CENNIK][F-CENNIK]. Rabaty: półrocznie −16,7%, rocznie −33,3%. Trial 30 dni Expert bez karty [HOME][F-FREEN]. Bez abonamentu tylko: historia operacji, wykresy liniowe, notowania, ranking funduszy, forum spółek, portfele publiczne [CENNIK].

| Plan | Miesiąc | Rok | Portfele | Funkcje dochodzące w planie |
|---|---|---|---|---|
| Basic | 4,99 zł | 39,92 zł | 1 | Wszystkie operacje, konta, zobowiązania, operacje cykliczne; skład; struktura w czasie; stopa zwrotu z benchmarkiem; mapa cieplna; zamknięte – podsumowanie; limity IKE/IKZE/PPK; TradingView; notowania (15 min opóźnienia); kokpit; tagi, notatki, exercise price; eksport/import portfela; aplikacje mobilne; 1 grupowy + 1 bliźniaczy |
| Standard | 9,99 zł | 79,92 zł | 5 | Jednostki w czasie, zmienność, rolling return, drawdown, zysk i wartość w czasie, zobowiązania w czasie, wpłaty/wypłaty, porównania walorów, świece, **walory użytkownika** |
| Pro | 15,99 zł | 127,92 zł | 20 | **Import (plik, e-mail), kreator AI**, zysk per typ/konto, majątek, wkład i wartość/zysk, stopa w okresach, ranking walorów, **dywidendy w czasie**, prowizje, zamknięte – szczegóły i statystyki, porównania portfeli, **alerty**, sygnały AT, ESPI, kalendarium, kopiowanie portfela |
| Expert | 24,99 zł | 199,92 zł | 99 | **Statystyki ryzyka** (Sharpe/Sortino/VaR/Beta), struktura kupna, ekspozycja walutowa, fundamenty, analiza ryzyka/sektorowa/indeksowa/tagów, podsumowania e-mail, skanery, strategie, **wszystkie narzędzia podatkowe**, subkonta, sub-portfele, nielimitowane grupy/bliźniaki, własne benchmarki, **portfel wzorcowy, cel, FIRE, Snowball** |

Niespójności: pomoc mobilna wymaga „co najmniej Pro” do synchronizacji [H-MOB], cennik daje mobile od Basic [CENNIK] — **[wniosek]** pomoc nieaktualna. Freenance podaje „Free tier + Premium 19 PLN/mies.” [FREENANCE] — sprzeczne z cennikiem, autor zarzucił Freenance nieprawdę [F-FREEN]. Starsze ceny: 2020 r. Basic ok. 2,99 zł, Expert ok. 10,41 zł/mies. [DNA] **[niezweryfikowane]**.

## 7. Aplikacje mobilne, API, źródła notowań

### 7.1 Mobile

- Android: 4,2★ / 213 ocen, 10 tys.+ pobrań, aktualizacja 2026-09-28, bez reklam, deklaracja „nie zbiera danych” [GPLAY]. iOS: 3,9★ / 110 ocen [APPSTORE]; Apple Watch [H-MOB].
- Funkcje: notowania GPW/NC/TFI bez logowania, skład, wykresy struktury/zysku/wartości/stopy, komunikaty spółek, operacje, kupno/sprzedaż, sygnały AT, kokpit, alerty, portfele publiczne i subskrybowane [H-MOB][ANDROID].
- Wersja 4.00 (2026-07-28): odświeżony wygląd, biometria, jasny/ciemny motyw, widżety iOS; 4.22 ma „Asystenta AI” odpowiadającego na pytania o serwis (bez dostępu do danych portfela) [F-APP4][FAQ].
- Braki po 4.00: brak skompresowanego widoku składu, wyboru ekranu startowego, notatki przy transakcji w iOS, ręcznego wyboru motywu, zakresu dat wykresu; **brak strategii (autor: „nie miałem w planach”)**; sortowanie nie zapisywało się na iOS [F-APP4][F-WYKR]. Stara wersja WAP `m.myfund.pl` nadal w pomocy [H-100].

### 7.2 API (jedyny endpoint)

- Od 2025-05-28, po prośbach od 2017 r.: `GET https://myfund.pl/API/v1/getPortfel.php?portfel={nazwa}&apiKey={klucz}&format=json` [F-API].
- Klucz w Konto→Ustawienia; odpowiedź: `status`, `portfel` (zmiany W/2W/M/3M/6M/R/3R/5R/MdD/RdD), `tickers`, `struktura`, `strukturaWalory`, `zyskWCzasie`, `wartoscWCzasie`, `wkladWCzasie`, `benchWCzasie`, `stopaZwrotuWCzasie`, `zmianaDzienna`; cache 5 min; wymaga abonamentu; kody statusu 0/1/2/7 (2 nieopisany) [F-API].
- Brak API zapisu — **[wniosek]** z wątku (opisany tylko odczyt). Eksport: każda tabela/wykres do CSV/XLS [H-RAP].

### 7.3 Źródła danych

| Dane | Ustalenia | Źródło |
|---|---|---|
| Opóźnienia | Notowania online ~15–20 min; intraday co ≤10 min; wyceny dzienne przy pierwszym logowaniu dnia; TFI z 2–3-dniowym opóźnieniem | [FAQ][H-ONL][CENNIK] |
| Akcje zagraniczne | Dodawanie po tickerze z finance.yahoo.com; tickery w formacie Yahoo (`2408.TW`, `JEQP.L`) — **[wniosek]** źródłem jest Yahoo Finance lub dostawca o tej samej symbolice | [H-INNE][F-TW][F-BUGS] |
| Fundusze | Analizy.pl wspomniane w pomocy i na liście importów — **[wniosek]** możliwe źródło wycen TFI, niepotwierdzone | [H-INNE][INTEG] |
| Kursy do podatków | NBP (D−1 / D+1) | [H-TAX] |
| Sektory | Własna klasyfikacja + społecznościowy wigwatch.pl | [H-INNE] |
| Wykresy | TradingView (`charting_library.standalone.js`); Chart.js + chartjs-chart-financial, dhtmlxGrid, jQuery UI 1.10.3 — **[wniosek]** z nazw skryptów | [H-RAP] |
| Dostawca danych GPW | Brak publicznej deklaracji — **[niezweryfikowane]** | — |

## 8. UX

### 8.1 Mocne strony

- Kompletność polskich przypadków brzegowych (PP, PDA, spin-off, split z korektą historii, konwersje TFI, obligacje skarbowe z opłatą za wcześniejszy wykup, Catalyst D+2, PPK z subkontami, PPE z udziałem własnym) [H-OP].
- Rygorystyczny model księgowy: brak ujemnych ilości/sald, walidacja ceny z zakresem sesji [FAQ][H-OP].
- Szeroka analityka i podatki z optymalizatorem [H-RAP][H-TAX].
- Szybki osobisty support autora (poprawki w ciągu godzin, np. Tajwan 2026-09-30) [F-TW][F-WYKR]; App Store: „Dobry kontakt. Szybkie wsparcie producenta” [APPSTORE].
- Prywatność: tylko login/e-mail/hasło, serwery w Polsce, 2FA, historia i powiadomienia o logowaniu [BEZP][HOME].

### 8.2 Słabości i skargi

| Obszar | Dowód | Źródło |
|---|---|---|
| UI przeładowany | „interfejs przytłaczający… mnóstwo tabel i suwaków… wygląd mimo odświeżenia w 2024 r. wciąż przypomina skomplikowany arkusz”; „Complex interface overwhelming for beginners”, słabe skalowanie wykresów (2020) | [PORTFEO][DNA] |
| Mobile | „UX not designed for mobile devices looks like PC port” (2025-02-19); „używalność pozostawia wiele do życzenia… klawiatura zasłania przyciski” (2023-09-07); po 4.00 lepsze recenzje, ale braki vs web | [APPSTORE][GPLAY][F-APP4] |
| Import | Zawodny dla części brokerów; fundusze wymagają nazw z bazy myfund | §4.3, [H-IMP] |
| Brak synchronizacji | Automatycznie tylko XTB API | [H-IMP][PGLANCE] |
| Jakość danych | 2 223 tematy w „Usterki, błędy”; IX 2026: brak dywidendy JEQP.L od 08.2025, brak ESPI dla PGH, „MWIG40TR – błędna stopa zwrotu”, „Rozjazd historycznych cen na wykresie”, „Niepoprawna skala na wykresach”, brak wyceny opcji NVDA; „braki na liście instrumentów” (32 wpisy) | [F-BUGS][F-ABOUT] |
| Metodologia nieintuicyjna | Wątki „Skąd różnice w podsumowaniu”, „SYN2BIO – stopy zwrotu w milionach %”, „Wkład vs Wartość”; FAQ tłumaczy różnice vs XTB/mBank | [F-ABOUT][FAQ] |
| Bus factor | Jednoosobowy rozwój; autor deklaruje dokument operacyjny i sukcesję | [F-DEATH] |
| API | Od 2025, tylko odczyt jednego portfela | [F-API] |
| Nieruchomości/metale | Brak modułu najmu; metale po spocie bez marży dealera | [PORTFEO] |
| Paywall | Większość analiz w Expert; brak darmowego planu | [CENNIK] |
| Dokumentacja | Częściowo nieaktualna (FAQ o imporcie, pomoc mobilna) — **[wniosek]** | [FAQ][H-IMP][H-MOB] |

### 8.3 Sprzeczne twierdzenia osób trzecich (do zignorowania)

- [PGLANCE] (2026-07-05): brak goal trackingu i „portfolio health scoring” — sprzeczne z [H-INNE] (cel, FIRE) i [H-RAP] (Snowball).
- [FREENANCE]: darmowy plan, 19 zł/mies., brak krypto, brak FIRE, start w 2019 — sprzeczne z [CENNIK], [H-TAX], [H-INNE], [PORTFEO]; autor myfund opublikował sprostowanie [F-FREEN].

## 9. Co z tego wynika dla FundTrackera

Kontekst FundTrackera: [architektura backendu](../../technical/backend/01_backend-architecture.md), [moduł portfolios](../../technical/backend/05_portfolios_module.md), [moduł assets](../../technical/backend/04_assets_module.md).

1. **[wniosek]** Rdzeń zaufania użytkowników myfund to model jednostek (TWR) + MWR + prosta stopa + CAGR, z jawnymi
   przełącznikami (podatek, prowizja od sprzedaży, dywidendy w zysku). **rekomendacja**: zaimplementować te same
   miary jako czyste funkcje domenowe (warstwa `domain/` w `portfolios`).
2. **[wniosek]** Myfund traktuje spójność księgi (brak ujemnych ilości/sald na każdy dzień) jako twardy inwariant
   portfela gotówkowego. **rekomendacja**: walidacja spójności przy każdej Operacji, z jawnym trybem „bezgotówkowym”
   (automatyczne wpłaty/wypłaty).
3. **[wniosek]** Automatyczne zdarzenia korporacyjne (split, dywidenda, odsetki/wykup Catalyst, zmiana nazwy) to
   największa ukryta praca myfund — włączane datami „od kiedy automatyczne” (2011, 2014, 2016, 2018, 2020).
4. **rekomendacja**: obligacje skarbowe jako Klasa waloru pierwszej klasy (seria = typ + miesiąc wykupu, marża,
   inflacja, opłata za wcześniejszy wykup, zamiana serii) — tu konkurencja zagraniczna nie ma odpowiednika.
5. **rekomendacja**: PIT-38 (FIFO per konto, NBP D−1, straty 5 lat z regułą 50%/100%, dywidendy zagraniczne z UPO,
   optymalizator końca roku FIFO/HIFO) jako deterministyczne, testowalne funkcje.
6. **[wniosek]** Hierarchia stawek podatku (walor > typ > konto > portfel > domyślna) i domyślne prowizje (% + minimum)
   per konto i typ to tani mechanizm usuwający ręczne wpisy.
7. **[wniosek]** Funkcje, które myfund trzyma w Expert (statystyki ryzyka, podatki, wzorce/rebalancing, cel/FIRE,
   Snowball) i Pro (import, dywidendy w czasie, alerty), to sygnał najwyżej cenionych funkcji.

### 9.1 Gdzie FundTracker może być „lepszy niż myfund” (**rekomendacja**)

| # | Obszar | Słabość myfund | Kierunek dla FundTrackera |
|---|---|---|---|
| 1 | Przejrzysta metodologia | Wątki „Skąd różnice”, „stopy w milionach %” [F-ABOUT] | Publiczny opis wzorów + rozbicie wyniku (wkład, zysk, kurs, podatek) przy każdej liczbie |
| 2 | Testy złote | Błędne stopy zwrotu zgłaszane na forum [F-BUGS] | Zestaw przypadków referencyjnych (TWR/MWR/FIFO/PIT-38) w CI |
| 3 | Nowoczesny UI | „skomplikowany arkusz” [PORTFEO] | Mniej tabel, sensowne widoki domyślne, progresywne odsłanianie |
| 4 | Responsywność | Mobile jako „PC port” [APPSTORE] | Jeden responsywny frontend zamiast osobnej aplikacji |
| 5 | Pełne API | Jeden endpoint read-only [F-API] | REST odczyt + zapis Operacji (już naturalne przy FastAPI) |
| 6 | Brak paywalla | Analityka głównie w Expert [CENNIK] | Wszystkie funkcje dostępne (single-user) |
| 7 | Importer z podglądem i diagnostyką | Import zawodny, godziny poprawek [PORTFEO] | Podgląd, walidacja, raport różnic i idempotencja przed zapisem; importery jako wtyczki |
| 8 | Znormalizowane nazwy funduszy | „nazwy funduszy nie są znormalizowane” [H-IMP] | Dopasowanie po ISIN/aliasach z ręcznym mapowaniem |
| 9 | Jakość danych widoczna | Braki dywidend/wycen wykrywane przez użytkowników [F-BUGS] | Wskaźnik świeżości wyceny i braków (jak reguła Snowball „wyceny >7 dni”) |
| 10 | Snowball + TUW | Tylko Expert [H-RAP] | Tanie do skopiowania: reguły progowe z wagami (§2.3) |
| 11 | Własność danych | SaaS, bus factor [F-DEATH] | Self-hosted, eksport pełnej księgi do otwartego formatu |
| 12 | Metadane operacji | Brak notatki przy transakcji w iOS [F-APP4] | Komentarz i tagi na każdej Operacji we wszystkich widokach |
| 13 | Spójna dokumentacja | FAQ i pomoc sprzeczne z cennikiem/importem | Dokumentacja generowana z kodu/testów |
| 14 | Wybór partii zakupu | Wskazanie konkretnego kupna dopiero od 05.2026 [H-OP] | Wybór partii zakupu (lotu podatkowego) od początku, FIFO jako domyślne |

**[wniosek]** Nie warto konkurować w: społeczności (forum, portfele publiczne/subskrybowane), skanerach i danych fundamentalnych, kalendarium spółek, white-label dla doradców — to funkcje wymagające licencjonowanych danych lub użytkowników, bez wartości dla aplikacji single-user.

## Źródła

Wszystkie pobrane 2026-10-01.

| Tag | URL | Uwagi |
|---|---|---|
| HOME | https://myfund.pl/index.php | statystyki, plany |
| CENNIK | https://myfund.pl/index.php?raport=cennik | macierz funkcji z HTML |
| FAQ | https://myfund.pl/index.php?raport=FAQ | — |
| H-… (strony pomocy) | https://myfund.pl/index.php?raport=pomoc&helpID={N} | N: H-START=5 Jak zacząć; H-WSK=15 Definicje wskaźników; H-OP=20 Rodzaje operacji; H-HIST=23 Historia operacji; H-CYK=25 Operacje cykliczne; H-IMP=30 Import operacji; H-RAP=40 Raporty, analizy, wykresy; H-SCAN=41 Skaner spółek; H-RANK=42 Ranking funduszy; H-INNE=45 Inne narzędzia; H-OPC=50 Opcje portfeli; H-WZ=55 Wzorce/rebalancing; H-AL=60 Alerty; H-STR=65 Strategie; H-PUB=70 Portfele publiczne; H-SUB=71 Portfele subskrybowane; H-TAX=80 Narzędzia podatkowe; H-ONL=90 Notowania online; H-MOB=95 Aplikacje mobilne; H-100=100 m.myfund.pl (WAP) |
| INTEG | https://myfund.pl/landing2026/data/integrations-list.json | 78 nazw |
| BEZP | https://myfund.pl/index.php?raport=bezpieczenstwo | bezpieczeństwo |
| DORADCY | https://myfund.pl/index.php?raport=dlaDoradcow | oferta dla doradców |
| ANDROID | https://myfund.pl/index.php?raport=android | strona aplikacji |
| REG | https://myfund.pl/index.php?raport=regulamin | właściciel, BLIK, SLA 48 h |
| F-CENNIK | https://myfund.pl/index.php?raport=forum&forum=2&topic=7101 | zmiana cennika, 2026-09-25 |
| F-APP4 | https://myfund.pl/index.php?raport=forum&forum=2&topic=6881 | aplikacje 4.00, od 2026-07-28 |
| F-WYKR | https://myfund.pl/index.php?raport=forum&forum=6&topic=7108 | „Wykresy portfela”, 2026-09-28..30 |
| F-TW | https://myfund.pl/index.php?raport=forum&forum=9&topic=7116 | notowania Tajwan, 2026-09-30 |
| F-API | https://myfund.pl/index.php?raport=forum&forum=6&topic=847 | „API do serwisu”, 2017-03-18 → 2026-09-28 |
| F-FREEN | https://myfund.pl/index.php?raport=forum&forum=1&topic=7056 | sprostowanie autora, 2026-09-15 |
| F-DEATH | https://myfund.pl/index.php?raport=forum&forum=1&topic=4174 | ciągłość serwisu, 2024-03-20 → 2026-08-19 |
| F-BUGS | https://myfund.pl/index.php?raport=forum&forum=7 | „Usterki, błędy” |
| F-DEV | https://myfund.pl/index.php?raport=forum&forum=6 | „Rozwój myfund.pl” |
| F-ABOUT | https://myfund.pl/index.php?raport=forum | statystyki forum |
| GPLAY | https://play.google.com/store/apps/details?id=pl.myfund.myfundpl20&hl=pl | Google Play |
| APPSTORE | https://apps.apple.com/pl/app/myfund-pl-portfel-inwestycji/id557701295?see-all=reviews&platform=iphone | recenzje iOS |
| PORTFEO | https://www.portfeo.pl/blog/wpis/portfeo-czy-myfund-porownanie-narzedzi-do-monitorowania-portfela-w-2026-roku | 2026-05-05; **konkurent** |
| PGLANCE | https://www.portfolioglance.com/investing-apps/myfund | 2026-07-05; częściowo błędne |
| DNA | https://dnarynkow.pl/jak-skutecznie-kontrolowac-swoje-inwestycje-poznaj-platforme-myfund/ | 2020-10-15 |
| FREENANCE | https://freenance.io/products/myfund-review-2026-polski-portfolio-tracker-akcje-etf-fundusze/ | **konkurent, niewiarygodne** |

## Luki i niepewności

- `raport=APIdoc` i `raport=ImportFileGuides` wymagają logowania — treści nie pobrano; konta demo nie eksplorowano.
- Obsługiwane serie obligacji skarbowych (EDO/COI/ROD/TOS/OTS…) i dostawca danych GPW — niezweryfikowane.
- Źródło notowań zagranicznych (Yahoo) i wycen TFI (Analizy.pl) — tylko wnioski z symboliki i wzmianek.
- Inny badacz nie znalazł publicznej metodologii stopy zwrotu myfund; ten dokument opiera „jednostki = TWR” na FAQ myfund [FAQ] — źródło pierwotne, ale bez wzorów krok po kroku (np. moment wyceny przy przepływie).
- Reddit, forum.bankier.pl — brak wyników; sii.org.pl — HTTP 403; filmy YouTube nieprzejrzane.
- Liczby użytkowników/portfeli i ocen w sklepach są migawką z 2026-10-01.
