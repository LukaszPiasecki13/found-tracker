---
paths: ["**/*.py", "**/*.{ts,tsx,js,jsx}", "**/*.{ps1,psm1}"]
description: OWASP Top 10 security checklist - JWT auth, input validation, SQL injection, XSS, CSRF, rate limiting, secrets management. Auto-loaded for Python, TypeScript, and PowerShell files.
---

# Security Checklist

OWASP Top 10. Apply to all code handling auth, user input, database access, or secrets.

**Deviations are allowed, but only through an ADR** in the project (what is skipped, why, and
what would trigger a re-evaluation). A deviation nobody wrote down is a finding; a documented
one is not. Do not "fix" a documented deviation to match this checklist without asking.

## Authentication (JWT)

- Prefer `PyJWT` for new code.
- If a project uses `python-jose`, the floor must be `>=3.4.0`. Everything below it is
  vulnerable to CVE-2024-33663 (algorithm confusion with OpenSSH ECDSA keys),
  CVE-2024-33664 (denial of service via a compressed JWE "JWT bomb") and CVE-2024-29370
  — all three fixed in 3.4.0 (source: OSV/GitHub Advisory Database).
  A dependency pinned `>=3.3.0` is **not** safe: the floor itself is a vulnerable version.
- Algorithms: `RS256` with `audience` and `issuer` validation.
- Access tokens: 15-30 min lifetime. Refresh tokens: 7-30 days, rotate on use.
- Store refresh tokens in `httpOnly`, `Secure`, `SameSite=Strict` cookies. Never in `localStorage`.

## Input Validation

- Validate at system boundary only (API routes). Never trust URL params, request bodies, or query strings.
- Backend: Pydantic with strict field constraints (`min_length`, `max_length`, `pattern`, `Literal` whitelist).
- Frontend: validate UUIDs/IDs before routing or API calls. Never trust route params directly.

## SQL Injection Prevention

- Always use parameterized queries. Never interpolate user input into SQL strings.
- BigQuery: use `QueryJobConfig` with `ScalarQueryParameter`. SQLAlchemy ORM is safe by default.

## Secrets Management

- Never commit secrets, API keys, passwords, or connection strings to git.
- Load from environment variables (`os.environ["KEY"]` - fails fast if missing) or secret managers.
- Add `.env`, `*.pem`, `*.key`, `service-account*.json` to `.gitignore`.
- Block the assistant's own access to them with `permissions.deny` in the project's
  `.claude/settings.json` — see `templates/project/settings.json` in this toolkit.
  `.gitignore` stops commits; only `permissions.deny` stops reads.

## XSS Prevention

- Angular: `{{ }}` interpolation is safe. Never use `[innerHTML]` with user content. Use `DomSanitizer` if raw HTML is required.
- React: JSX expressions are safe. Never use `dangerouslySetInnerHTML` with user content. Use `DOMPurify` if required.

## CSRF Protection

- JWT in `Authorization` header: CSRF protection not needed.
- Cookie-based auth: CSRF middleware required. Angular: configure `withXsrfConfiguration()` in `provideHttpClient()`.

## Rate Limiting

- Apply to all auth and sensitive endpoints. FastAPI: use `slowapi`. Login endpoints: max 5/minute.
