---
id: adr-0005-domain-layer
status: Proposed
last_reviewed: 2026-09-30
type: decision
scope: backend/domain-layer
---

# Szablon modułu dostaje opcjonalną warstwę `domain/` — logikę biznesową bez ORM, sesji i zegara

Szablon modułu ma piąty, opcjonalny podkatalog `domain/`: logika biznesowa bez ORM, `Session`, zegara i I/O, dostępna modułowi, który jej faktycznie potrzebuje. Pierwszym kandydatem jest `portfolios`. Reguły DOM-1–DOM-11 są przejęte z waterworks (ADR-0027 tamtego projektu).

## Kontekst

Architektura warstwowa (API → Services → Repositories → Infrastructure) nie ma miejsca na logikę bez I/O. W `portfolios` reguły salda i pozycji (kupno, sprzedaż, wpłata, dywidenda, przebudowa z historii) są czystą arytmetyką na `Decimal`, ale żyją w `PortfolioService`/`TransactionService` splecione z repozytoriami, przyjmują `dict` z kluczami `portfolio`/`asset` i są zduplikowane w walidacji routera. Metryki (`portfolios/analytics/`) mieszają obliczenia z pobieraniem cen z `yfinance`.

## Decyzja

**`domain/` jest piątym, opcjonalnym podkatalogiem modułu** (DOM-7: powstaje, gdy moduł ma logikę bez I/O; czysty CRUD go nie dostaje).

| # | Reguła |
|---|---|
| DOM-1 | `domain/` importuje wyłącznie bibliotekę standardową i inne pliki `domain/` tego samego modułu. Zakazane: `sqlalchemy`, `fastapi`, `pydantic`, `app.core.*`, `app.infrastructure.*`, biblioteki trzecie |
| DOM-2 | Bez zegara i I/O: żadnego `datetime.now`, odczytu plików, sieci. Czas i konfiguracja przychodzą jako argumenty |
| DOM-3 | `domain/` importują `services/` (zawsze) oraz `models/`/`schemas/` (wyłącznie po słownik: enumy, stałe i predykaty bez efektów ubocznych). `repositories/` nie importuje `domain/`. `wiring.py` może. `api/` idzie do `domain/` przez serwis |
| DOM-4 | Forma: niemutowalne `@dataclass(frozen=True, slots=True)`, `StrEnum`, tagged union, funkcje tam, gdzie „to nie jest rzecz”. Pliki nazwane pojęciem z dziedziny |
| DOM-5 | Publiczne API przez `domain/__init__.py` z `__all__`; obcy moduł importuje tylko stamtąd |
| DOM-6 | `services/` modułu z `domain/` zawiera klasy `*Service` w plikach `<resource>.py` |
| DOM-7 | `domain/` jest opcjonalny |
| DOM-8 | Granica z ORM/Pydantic przez `typing.Protocol` (strukturalny widok), nie przez zachowanie dopisane do modelu ORM ani klasę-lustro |
| DOM-9 | Warstwy wewnątrz `domain/`: słownik → silnik → warianty → komponenty; import tylko w dół |
| DOM-10 | Serwis rozmawia z domeną wyłącznie przez komponenty — klasy z metodami instancji budowane w `wiring.py` i wstrzykiwane przez konstruktor |
| DOM-11 | `domain/__init__.py` eksportuje tylko to, co konsument spoza `domain/` trzyma w rękach |

Błędy domeny: pytanie tak/nie zwraca `bool`; naruszenie niezmiennika rzuca wyjątkiem domenowym (podklasa `ValueError`, bez zależności od `app.core`). Serwis tłumaczy go na `BadRequestError` z `code`; domena o HTTP nie wie.

**Otwarte i nierozstrzygnięte przez ten ADR:** wektory metryk portfela liczone na `numpy`/`pandas` (DOM-1 zabrania bibliotek trzecich). Warianty do decyzji właściciela:
- **(a)** metryki zostają w `portfolios/services/metrics.py` jako adapter nad `numpy`; `domain/` zawiera tylko reguły salda i pozycji (`Decimal`). Historia cen dostarczana portem (`PriceHistoryProvider`).
- **(b)** wyjątek od DOM-1: `numpy` dopuszczony w `domain/` (biblioteka numeryczna bez I/O, deterministyczna); `pandas` i `yfinance` nie.

Rekomendacja: (a) — DOM-1 zostaje bez wyjątków, a metryki i tak są adapterem nad I/O cen.

## Rozpatrywane alternatywy

- **Uporządkować tylko nazwy plików w `services/`.** Czysty kod nadal bez warstwy. Odrzucone.
- **Osobny moduł `analytics`** (stary plan architektury). Metryki i reguły salda dzielą te same Operacje i ten sam stan; osobny moduł wymusiłby zależność cykliczną lub duplikację. Odrzucone.
- **Pełna Clean/Hexagonal Architecture.** Większy koszt niż zysk przy tej skali; `domain/` domyka układ warstwowy, nie zastępuje go. Odrzucone.
- **Zachowanie na modelu ORM** (`Portfolio.apply_buy()`). `models/` to warstwa ORM, nie miejsce na reguły. Odrzucone na rzecz DOM-8.
- **Logika w `services/` (obecny stan).** Serwis miesza arytmetykę z I/O; nie da się jej testować bez mocków repozytoriów. Odrzucone.

## Konsekwencje

**Pozytywne**
- Reguły salda testowane bez bazy i bez mocków; jedno źródło walidacji zamiast dwóch (router + serwis).

**Negatywne**
- Nowa warstwa i konwencje (Protocol, komponenty w `wiring.py`) do opanowania.
- Dopóki nie ma testu AST, DOM-1–DOM-3 egzekwuje tylko review (krok R-09).

## Notatki

Mapowanie plik-po-plik: [`05_portfolios_module.md` §4](../backend/05_portfolios_module.md#4-warstwa-domain). Moduły `assets`, `security`, `core_data` `domain/` nie dostają (DOM-7).
