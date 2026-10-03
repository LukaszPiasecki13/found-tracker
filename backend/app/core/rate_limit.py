"""Rate limiting for endpoints prone to credential-guessing abuse.

In-memory (slowapi/limits default): fine for a single-instance deployment. Move to
a Redis storage backend if the backend ever runs behind a load balancer with more
than one instance, since per-instance counters would no longer add up to one limit.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import get_settings


def resolve_client_ip(request: Request) -> str | None:
    """Resolve the real client address, not the shared proxy hop.

    With `trust_proxy_headers` on, take the *last* `X-Forwarded-For` entry: the
    reverse proxy appends the real client address, so the client cannot control it.
    The first entry is whatever the client sent - trusting it would let anyone
    bypass the limiter with a fabricated header.
    """
    if get_settings().effective_trust_proxy_headers:
        x_forwarded_for = request.headers.get("x-forwarded-for", "")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[-1].strip()
    if request.client is None:
        return None
    return request.client.host


def limiter_key_func(request: Request) -> str:
    return resolve_client_ip(request) or "unknown"


limiter = Limiter(key_func=limiter_key_func)


def register_rate_limiting(app: FastAPI) -> None:
    """Wire the limiter into the app, matching the API's error contract (ADR-0007)."""
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    def rate_limit_exceeded_handler(
        request: Request, exc: RateLimitExceeded
    ) -> Response:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests", "code": "RATE_LIMIT_EXCEEDED"},
        )
