"""Security services - authentication business logic.

Intentionally does not re-export `AuthService`: `core_data.services.users`
imports `services.password`, and `services.auth` imports `core_data`'s
`UserService` - a re-export here would close that import cycle.
"""
