---
paths: ["**/*.py", "**/*.{ts,tsx,js,jsx}"]
description: Error handling patterns for Python backend and TypeScript frontend - exception hierarchy, HTTP error contract, logging strategy. Framework-neutral; the exact response shape is a per-project decision. Auto-loaded for Python and TypeScript files.
---

# Error Handling Patterns

Rules: validate at entry points, catch only known exceptions, log once, never expose internal details in responses.

**The exact class names and response shape are a per-project decision** — record it in a project
ADR and follow it. If the project already has an error contract, extend it additively; do not
introduce a second one. The rules below describe the invariants that apply to any contract choice.

## Invariants (every project)

1. **One base exception** for domain errors, carrying a human-readable message, a stable
   machine-readable `code`, and the HTTP status it maps to (directly or via a lookup).
2. **`code` on every domain error.** `UPPER_SNAKE`, naming the entity and condition
   (`DEVICE_NOT_FOUND`). The `code` is the contract with clients; the message is not — clients
   translate `code` and use the message only as a fallback.
3. **The message language is fixed per API** (one language, not a mix). Localisation is the
   client's job.
4. **Services raise domain exceptions, never `HTTPException`.** The API layer maps them. FastAPI
   dependencies count as API layer, but should still raise the domain exceptions, so the response
   carries `code` like every other error.
5. **Log once**, in the layer that catches. `logger.exception()` for unexpected errors.
6. **Never expose internals** (stack traces, SQL, paths) in a response.
7. **Validation errors follow the same envelope** as domain errors, with per-field detail in a
   dedicated array (`errors[]`), not smuggled into the `detail` field.

## This Project: Waterworks Monitoring Platform

**Current contract** (shipped, read by frontend and firmware per ADR-0006):

```json
{
  "detail": "Device 42 does not exist in this organization",
  "code": "DEVICE_NOT_FOUND"
}
```

- `detail`: human-readable message (always a string)
- `code`: machine-readable error identifier (always present on domain errors)
- Validation errors: `detail` is an array of Pydantic `ValidationError.errors()`

**Direction: additive migration to RFC 9457**

No breaking changes. Plan: add RFC 9457 fields (`type`, `title`, `status`) alongside
existing `detail`/`code`, migrate client code to read from RFC 9457 fields first (with
fallback to `detail`/`code`), then remove old fields in a later major version. Example target:

```json
{
  "type": "urn:waterworks:error:device-not-found",
  "title": "Device not found",
  "status": 404,
  "detail": "Device 42 does not exist in this organization",
  "code": "DEVICE_NOT_FOUND",
  "errors": [{"field": "email", "message": "..."}]
}
```

**Implementation notes:**
- `type` is always `urn:waterworks:error:` + kebab-case of `code`
- `title` is a short label (from `code`); `detail` is the full context
- Validation `errors[]` replaces the current practice of putting `ValidationError.errors()` into `detail`
- Migration step 1: update handler to emit RFC fields; both formats coexist
- Firmware may need a bridge if it reads validation responses (unlikely in device auth flow)

## Reference: Generic codes (for projects that have none)

| Status | Code (generic fallback) | When |
|--------|-------------------------|------|
| 400 | BAD_REQUEST | Malformed request |
| 401 | UNAUTHORIZED | Missing/invalid token |
| 403 | FORBIDDEN | Insufficient permissions |
| 404 | NOT_FOUND | Resource does not exist |
| 409 | CONFLICT | Duplicate or version conflict |
| 422 | VALIDATION_ERROR | Semantically invalid input |
| 500 | INTERNAL_ERROR | Never expose internal details |

Prefer specific codes (`DEVICE_NOT_FOUND`, `ACTIVATION_CODE_EXPIRED`) over generic fallbacks.

## Python Backend (Waterworks Monitoring Platform)

### Exception hierarchy

The project uses `APIError(Exception)` as base with `message`, `code`, and status; subclasses
are `NotFoundError`, `AuthenticationError`, `ForbiddenError`, `ConflictError`, `ValidationException`,
and `GoneError`. All carry a `code` or accept one at construction.

- Use a specific subclass when the status code is always the same (e.g., `NotFoundError` →
  404; `ConflictError` → 409).
- For custom domain logic, raise `BadRequestError` with a specific `code`.
- Never raise `HTTPException` from services; let the API layer catch `APIError` and map it.

### FastAPI exception handler

Registered in `app/core/errors.py`:

- `APIError` handler logs to `info` (4xx) or `error` (5xx) and returns `{"detail", "code"}`.
- `ValidationError` (Pydantic) handler returns validation array in `detail` (to be migrated to
  `errors[]` per migration plan above).
- Catch-all handler logs unhandled exceptions and returns fixed `"Internal server error"` with
  no `code`.

**To add RFC 9457 fields:**
Update `_error_response()` to emit `type`, `title`, `status` alongside `detail` and `code`.
Both formats coexist until clients (frontend, firmware) are fully migrated.

### Logging

- Structured logging: `logger.info("...", extra={"key": value})`.
- 4xx errors at `info`, 5xx errors at `error`, unhandled exceptions at `exception`.
- Log the request path and method for every API error, not just unhandled ones.

## TypeScript Frontend

Framework-neutral rules; framework specifics live in the `react-patterns` / `angular-patterns`
skills.

- Handle errors in one place (HTTP client interceptor or query client), not in every component.
- 401 → end the session and route to login; 403 → permission message; network error →
  connection message; everything else → surface to the component.
- Map `code` to a user-facing message in one table. Fall back to the server `detail` only when
  `code` is missing or unknown, then to a generic message.
