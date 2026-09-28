---
paths:
  - "**/*.{ts,tsx,mts,cts}"
  - "**/*.{js,jsx,mjs,cjs}"
  - "**/*.{html,scss,css}"
description: Framework-agnostic TypeScript/JavaScript standards - strict mode, formatting, complexity limits, naming. Framework specifics live in the angular-patterns and react-patterns skills.
---

# TypeScript Coding Standards

Applies to every TS/JS file regardless of framework. Framework-specific architecture is **not**
here on purpose — it loads on demand from the `angular-patterns` or `react-patterns` skill.

## Comment and Identifier Language

Code, identifiers, and code comments are always written in English, regardless of what
language the project's documentation (README, `docs/`, ADRs) uses. This keeps source readable
for tooling, linters, and any contributor who doesn't share the docs' language. User-facing
strings (UI labels, error messages shown to end users) follow the product's target language
instead — that's a product decision, not a code-comment one.

## Formatting (Prettier)

- Print width: 100 characters
- Quotes: single (`'`) in TS/JS, double in HTML attributes
- Semicolons: yes
- Trailing commas: ES5
- Indent: 2 spaces

## Type Safety (strict mode)

`strict: true` is mandatory. Never use `any` — use `unknown` plus narrowing.

```typescript
function parseResponse(data: unknown): Report {
  if (!isReport(data)) throw new Error('Invalid report data');
  return data;
}

// Unused parameters: prefix with underscore
function handler(_event: Event, data: Report): void {
  process(data);
}
```

Additional required compiler options: `noUncheckedIndexedAccess`, `noImplicitOverride`,
`exactOptionalPropertyTypes`. Each one removes a class of runtime error the type checker
otherwise lets through.

Type assertions (`as`) are an escape hatch, not a tool. Every `as` that is not
`as const` needs a comment explaining why the compiler cannot prove the type.

## Complexity Limits

| Metric | Limit |
|--------|-------|
| Cyclomatic complexity | max 15 |
| Lines per function | max 100 |
| `console.log` | error (only `console.warn`, `console.error` allowed) |

## Error Handling at Boundaries

Never swallow a rejected promise. Every `await` on I/O either has a `try/catch` that maps
the failure to a typed result, or sits inside a boundary that does (an error boundary,
a query client, an interceptor). See the `error-handling-patterns` rule for the contract.

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|----------|
| Class | PascalCase | `ReportListComponent` |
| Interface | PascalCase, no `I` prefix | `Report`, `UserProfile` |
| Type alias | PascalCase | `LoadState<T>` |
| Enum / enum value | PascalCase | `ReportStatus.Draft` |
| Function | camelCase | `getReportById()` |
| Variable | camelCase | `reportCount` |
| Constant (module-level) | UPPER_SNAKE | `MAX_RETRIES` |
| Constant (local) | camelCase | `defaultConfig` |
| Observable | camelCase + `$` suffix | `reports$` |
| Signal | camelCase, no suffix | `reports` |
| Boolean | `is`/`has`/`can` prefix | `isActive`, `hasPermission` |
| Private member | `private` keyword, no underscore | `private readonly service` |

### File Naming

| Type | Convention | Example |
|------|-----------|----------|
| Angular file | kebab-case + suffix | `report-list.component.ts` |
| React component | PascalCase | `ReportList.tsx` |
| Hook / util | camelCase | `useReports.ts` |
| Test file | source name + `.test`/`.spec` | `report.service.spec.ts` |
| Config file | kebab-case | `eslint.config.mjs` |
| Folder | kebab-case | `report-management/` |

## Backend ↔ Frontend Field Mapping

| Context | Convention | Example |
|---------|-----------|----------|
| Backend JSON field | snake_case | `created_at`, `company_id` |
| Frontend TS property | camelCase | `createdAt`, `companyId` |

Map at the API-client boundary, in one place, never ad hoc inside components.

## Security Invariants

- Never render user-controlled HTML. Angular: no `[innerHTML]`. React: no `dangerouslySetInnerHTML`.
  If raw HTML is unavoidable, sanitize with `DomSanitizer` (Angular) or `DOMPurify` (React).
- Never put tokens in `localStorage`. See the `security-checklist` rule.
