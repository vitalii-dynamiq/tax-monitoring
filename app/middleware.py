import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger("taxlens")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generates or propagates X-Request-ID for tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter based on client IP."""

    def __init__(self, app, default_rpm: int = 200, expensive_rpm: int = 20, auth_rpm: int = 10):
        super().__init__(app)
        self.default_rpm = default_rpm
        self.expensive_rpm = expensive_rpm
        self.auth_rpm = auth_rpm
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._request_count = 0

    EXPENSIVE_PREFIXES = (
        "/v1/monitoring/jobs/",
        "/v1/monitoring/discovery/",
    )

    AUTH_PATHS = ("/v1/auth/login", "/v1/auth/register")

    def _is_expensive(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.EXPENSIVE_PREFIXES) and path.endswith("/run")

    def _is_auth(self, path: str) -> bool:
        return path in self.AUTH_PATHS

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting in non-production environments
        if not settings.is_production:
            return await call_next(request)

        # Prefer X-Forwarded-For from reverse proxy, fall back to direct client IP
        forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        client_ip = forwarded or (request.client.host if request.client else "unknown")
        now = time.monotonic()
        window = 60.0  # 1 minute

        # Periodic cleanup of stale entries to prevent memory leak
        self._request_count += 1
        if self._request_count % 1000 == 0:
            cutoff = now - window
            self._hits = defaultdict(list, {
                k: v for k, v in (
                    (k, [t for t in ts if t > cutoff]) for k, ts in self._hits.items()
                ) if v
            })

        if self._is_auth(request.url.path):
            bucket = "auth"
            limit = self.auth_rpm
        elif self._is_expensive(request.url.path):
            bucket = "expensive"
            limit = self.expensive_rpm
        else:
            bucket = "default"
            limit = self.default_rpm
        key = f"{client_ip}:{bucket}"

        # Clean old entries
        self._hits[key] = [t for t in self._hits[key] if now - t < window]

        if len(self._hits[key]) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )

        self._hits[key].append(now)
        return await call_next(request)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validates Authorization: Bearer <JWT> or X-API-Key header on all non-public endpoints."""

    PUBLIC_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/v1/auth/login", "/v1/auth/register"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # 1. Check Authorization: Bearer <JWT> first
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                from app.services.auth_service import decode_token

                payload = decode_token(token)
                request.state.user = payload.get("sub")
                request.state.user_role = payload.get("role", "user")
                return await call_next(request)
            except Exception:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or expired token"},
                )

        # 2. Fall back to X-API-Key check
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # 2a. Try DB-backed per-user API key
            if api_key.startswith("txl_"):
                try:
                    from app.db.session import async_session_factory
                    from app.services.api_key_service import validate_api_key

                    async with async_session_factory() as session:
                        result = await validate_api_key(session, api_key)
                    if result:
                        request.state.user = result[0]
                        request.state.user_role = result[1]
                        return await call_next(request)
                except Exception as exc:
                    logger.warning("API key validation error: %s", exc)

            # 2b. Static key (backward compatible)
            if api_key == settings.api_key:
                request.state.user = "api-key-user"
                request.state.user_role = "admin"
                return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API key"},
        )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs request method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        request_id = getattr(request.state, "request_id", "-")
        logger.info(
            "%s %s %d %.1fms [%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )

        response.headers["X-Request-Duration-Ms"] = f"{duration_ms:.1f}"
        return response


def setup_middleware(app: FastAPI) -> None:
    """Configure all middleware on the FastAPI app."""
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "Authorization", "X-Request-ID"],
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(APIKeyMiddleware)
    app.add_middleware(RequestIdMiddleware)
