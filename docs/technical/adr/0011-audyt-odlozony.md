---
id: adr-0011-audit-deferred
status: Proposed
last_reviewed: 2026-09-30
type: decision
scope: backend/audit
---

# Audyt zmian jest świadomie odłożony; `transaction()` działa bez wpisu audytowego

FundTracker nie przejmuje z waterworks mechanizmu audytu (`AuditAwareSession`, `AuditPort`, `skip_audit`, moduł `audit`). Jeśli potrzeba się pojawi, audyt dodajemy jako port w `core/`.

## Kontekst

W waterworks każdy commit biznesowy wymaga wpisu audytowego, egzekwowanego na poziomie sesji. Jest tam uzasadniony wieloma użytkownikami, organizacjami i wymaganiami regulacyjnymi. FundTracker jest aplikacją osobistą; historia zdarzeń inwestycyjnych jest już zapisana w `portfolios_operation` i jest źródłem prawdy o portfelu ([`CONTEXT.md`](../../business/CONTEXT.md)).

## Decyzja

- Nie wprowadzamy modułu `audit`, `AuditAwareSession` ani parametru `skip_audit`. `SQLRepository.transaction()` ma sygnaturę bez niego ([ADR-0001](0001-jedna-sesja-na-request.md)).
- Reguły waterworks dotyczące audytu (`# audit-skip:`, `AuditPort`, niezmiennik przy commicie) **nie obowiązują** w tym repo.
- Warunek ponownej oceny: pojawienie się drugiego użytkownika z dostępem do cudzych danych, wymóg śladu zmian edycji/usuwania operacji, albo potrzeba cofania zmian.
- Dodanie audytu będzie nowym ADR-em; wzorzec (`AuditPort` w `core/`, implementacja w module `audit`) można przejąć z waterworks bez przebudowy warstw.

## Rozpatrywane alternatywy

- **Przenieść audyt teraz.** Duży koszt (moduł, sesja, testy) bez użytkownika tej funkcji. Odrzucone.
- **Audyt przez trigger w bazie.** Poza architekturą warstwową; do rozważenia, jeśli pojawi się potrzeba. Odrzucone teraz.

## Konsekwencje

**Pozytywne**
- Prostszy `SQLRepository` i brak dodatkowego pojęcia w każdej operacji zapisu.

**Negatywne**
- Edycja i usunięcie operacji nie zostawia śladu zmiany (przebudowa portfela nadpisuje stan). Świadomie akceptowane.
- Późniejsze dodanie audytu dotknie wszystkich ścieżek zapisu.
