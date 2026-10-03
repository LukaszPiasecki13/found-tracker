---
id: fe-architecture
status: draft
last_reviewed: 2026-09-30
type: fact
scope: frontend/architecture
applies_to:
  - frontend/src/**
---

# Architektura frontendu (stan faktyczny)

Krótki opis stanu, żeby mapa wiedzy nie miała dziury. Frontend **nie jest** przedmiotem migracji backendu i konsumuje REST API bez zmian ([CLAUDE.md](../../../CLAUDE.md)). Docelowa mapa ekranów i tras, konwencje UI (formatowanie, stany, błędy, wykresy, formularze) i decyzje infrastrukturalne frontendu opisuje [IA i konwencje UI](../../research/00_analiza_koncowa.md).

## Stos

React + Vite + TypeScript, MUI (motyw w `lib/theme.ts`), TanStack Query (dane z API) i TanStack Table, Recharts (wykresy). Build: `npm run build` (`tsc -b && vite build`), lint: `npm run lint`.

## Struktura `frontend/src/`

| Katalog | Zawartość |
|---|---|
| `pages/` | Strony: `DashboardPage`, `Login/RegisterPage`, `Operations/Pocket*Page` |
| `components/` | Komponenty współdzielone, `charts/`, `dialogs/`, `PositionsTable`, `OperationsTable` |
| `services/` | Klienci API: `authService`, `pocketService`, `operationService`, `positionService`, `analyticsService`, `benchmarkService` |
| `hooks/` | Hooki danych: `usePockets`, `useOperations`, `usePositions`, `usePocketVectors` |
| `contexts/` | `AuthContext` (sesja) |
| `lib/` | `api.ts` (klient HTTP), `theme.ts` |
| `types/api.ts` | Typy odpowiedzi API |

## Fakty istotne dla backendu

- Tokeny JWT (`access`, `refresh`) są trzymane w `localStorage` (`contexts/AuthContext.tsx`) — [ADR-0012](../adr/0012-jwt-odstepstwa-od-checklisty.md).
- Frontend nazywa portfel `Pocket` (`pocketService`, `PocketsList`); backend `Portfolio` — [`CONTEXT.md`](../../business/CONTEXT.md#sprzeczności-i-niejasności).
- Kontrakt błędów (`detail` + `code`, [ADR-0007](../adr/0007-kontrakt-bledow-z-code.md)) jest docelowy; dziś część endpointów zwraca same `detail`.
- Zmiana kontraktu API wymaga równoległej zmiany w `services/` i `types/api.ts`.
