"""
API middleware for the Tax Estimator.

This module provides middleware for:
- Request ID tracking
- Request timing
- Common response headers
- Rate limiting

Based on the API specification in 09-api-specifications.md.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from tax_estimator.logging_config import request_id_var


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request ID tracking.

    - Uses X-Request-Id header from client if provided
    - Generates a new UUID if not provided
    - Attaches request_id to request.state for use in handlers
    - Returns X-Request-Id header in response
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request with request ID tracking."""
        # Get request ID from header or generate new one
        request_id = request.headers.get("X-Request-Id")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Attach to request state for use in handlers
        request.state.request_id = request_id

        # Set context var for log correlation
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            request_id_var.reset(token)


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track request processing time.

    Adds X-Response-Time header with processing time in milliseconds.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request with timing tracking."""
        start_time = time.perf_counter()

        response = await call_next(request)

        process_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
        response.headers["X-Response-Time"] = f"{process_time:.2f}ms"

        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Logs every request with method, path, status, duration, and client IP."""

    def __init__(self, app: "ASGIApp") -> None:
        super().__init__(app)
        self.logger = logging.getLogger("tax_estimator.access")

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Log request after processing."""
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        client_ip = request.client.host if request.client else "-"

        self.logger.info(
            "%s %s %d %.1fms client=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            client_ip,
        )
        return response


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add API version header.

    Adds X-API-Version header to all responses.
    """

    def __init__(self, app, version: str = "1.0.0"):
        """
        Initialize with API version.

        Args:
            app: The ASGI application
            version: API version string
        """
        super().__init__(app)
        self.version = version

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request with API version header."""
        response = await call_next(request)
        response.headers["X-API-Version"] = self.version
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Thread-safe in-memory rate limiting middleware with periodic cleanup.

    Limits requests per IP address using a sliding window counter.
    Note: For production with multiple instances, use Redis-backed rate limiting.

    Security features:
    - Thread-safe with asyncio locks per IP
    - Periodic cleanup to prevent memory leaks
    - Configurable proxy trust settings to prevent X-Forwarded-For spoofing
    """

    # Cleanup interval: clean all stale entries every N requests
    CLEANUP_INTERVAL = 100

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        enabled: bool = True,
        trust_proxy: bool = False,
        trusted_proxy_ips: list[str] | None = None,
        window_seconds: int = 60,
    ):
        """
        Initialize rate limiter.

        Args:
            app: The ASGI application
            requests_per_minute: Maximum requests per minute per IP
            enabled: Whether rate limiting is enabled
            trust_proxy: Whether to trust X-Forwarded-For header. MUST be
                        explicitly enabled and should only be True when behind
                        a trusted reverse proxy.
            trusted_proxy_ips: List of trusted proxy IPs. If provided and trust_proxy
                              is True, only trust X-Forwarded-For from these IPs.
            window_seconds: Rate limit window in seconds (default 60)
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.enabled = enabled
        self.trust_proxy = trust_proxy
        self.trusted_proxy_ips = set(trusted_proxy_ips) if trusted_proxy_ips else None
        self._window_seconds = window_seconds
        self._window_size = timedelta(seconds=window_seconds)

        # Store request counts per IP: {ip: [(timestamp, count), ...]}
        self._request_counts: dict[str, list[tuple[datetime, int]]] = defaultdict(list)

        # Per-IP locks for thread safety
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Global lock for cleanup operations
        self._global_lock = asyncio.Lock()

        # Request counter for periodic cleanup
        self._request_counter = 0

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP from request with security considerations.

        Only trusts X-Forwarded-For when:
        1. trust_proxy is explicitly set to True AND
        2. Either trusted_proxy_ips is not set, OR the direct client IP is in trusted_proxy_ips
        """
        direct_ip = request.client.host if request.client else "unknown"

        # Only trust X-Forwarded-For if explicitly enabled
        if not self.trust_proxy:
            return direct_ip

        # If we have a trusted proxy list, verify the direct client is in it
        if self.trusted_proxy_ips and direct_ip not in self.trusted_proxy_ips:
            return direct_ip

        # Now we can trust the X-Forwarded-For header
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the first IP in the chain (original client)
            return forwarded.split(",")[0].strip()

        return direct_ip

    def _clean_old_requests(self, ip: str, now: datetime) -> None:
        """Remove request records older than the window for a specific IP."""
        cutoff = now - self._window_size
        self._request_counts[ip] = [
            (ts, count) for ts, count in self._request_counts[ip]
            if ts > cutoff
        ]
        # Remove empty entries to prevent memory leak
        if not self._request_counts[ip]:
            del self._request_counts[ip]
            # Also clean up the lock if no longer needed
            if ip in self._locks:
                del self._locks[ip]

    async def _cleanup_all_stale_entries(self, now: datetime) -> None:
        """
        Periodic cleanup of all stale entries to prevent memory leaks.

        This removes entries for IPs that have no recent requests, preventing
        unbounded memory growth from unique IPs that make one request and leave.
        """
        async with self._global_lock:
            cutoff = now - self._window_size
            stale_ips = []

            for ip in list(self._request_counts.keys()):
                # Clean old requests for this IP
                self._request_counts[ip] = [
                    (ts, count) for ts, count in self._request_counts[ip]
                    if ts > cutoff
                ]
                # Mark for removal if empty
                if not self._request_counts[ip]:
                    stale_ips.append(ip)

            # Remove stale entries
            for ip in stale_ips:
                del self._request_counts[ip]
                if ip in self._locks:
                    del self._locks[ip]

    def _get_request_count(self, ip: str) -> int:
        """Get the total request count for an IP in the current window."""
        return sum(count for _, count in self._request_counts[ip])

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request with rate limiting."""
        if not self.enabled:
            return await call_next(request)

        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/"]:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = datetime.now()

        # Periodic cleanup of all stale entries
        self._request_counter += 1
        if self._request_counter >= self.CLEANUP_INTERVAL:
            self._request_counter = 0
            # Run cleanup in background to not block the request
            asyncio.create_task(self._cleanup_all_stale_entries(now))

        # Use per-IP lock for thread-safe rate limiting
        async with self._locks[client_ip]:
            # Clean old entries for this IP
            self._clean_old_requests(client_ip, now)

            # Check current count
            current_count = self._get_request_count(client_ip)

            if current_count >= self.requests_per_minute:
                # Rate limit exceeded
                request_id = getattr(request.state, "request_id", "unknown")
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please try again later.",
                            "status": 429,
                            "request_id": request_id,
                        }
                    },
                    headers={
                        "Retry-After": str(self._window_seconds),
                        "X-RateLimit-Limit": str(self.requests_per_minute),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int((now + self._window_size).timestamp())),
                    },
                )

            # Record this request
            self._request_counts[client_ip].append((now, 1))
            new_count = current_count + 1

        # Process the request (outside the lock)
        response = await call_next(request)

        # Add rate limit headers to response
        remaining = max(0, self.requests_per_minute - new_count)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int((now + self._window_size).timestamp()))

        return response

    def get_stats(self) -> dict:
        """Get rate limiter statistics for monitoring."""
        return {
            "tracked_ips": len(self._request_counts),
            "active_locks": len(self._locks),
            "requests_per_minute": self.requests_per_minute,
            "window_seconds": self._window_seconds,
            "trust_proxy": self.trust_proxy,
        }


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard security headers to all responses."""

    _DEFAULT_CSP = "; ".join([
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' https://cdn.jsdelivr.net",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ])

    def __init__(
        self,
        app: "ASGIApp",
        csp_policy: str | None = None,
        hsts_max_age: int = 31536000,
        debug: bool = False,
    ) -> None:
        super().__init__(app)
        self.csp_policy = csp_policy or self._DEFAULT_CSP
        self.hsts_max_age = hsts_max_age
        self.debug = debug

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        if not self.debug:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains"
            )
        response.headers["Content-Security-Policy"] = self.csp_policy
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects request bodies exceeding a configured size limit."""

    def __init__(self, app: "ASGIApp", max_bytes: int = 1_048_576) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes
        self.logger = logging.getLogger("tax_estimator.security")

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_bytes:
            request_id = getattr(request.state, "request_id", "unknown")
            self.logger.warning(
                "Request body too large: %s bytes (limit %s) [%s]",
                content_length,
                self.max_bytes,
                request_id,
            )
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "REQUEST_TOO_LARGE",
                        "message": (
                            f"Request body exceeds maximum size of {self.max_bytes} bytes"
                        ),
                        "status": 413,
                        "request_id": request_id,
                    }
                },
            )
        return await call_next(request)


# =============================================================================
# Functional Middleware (for use with @app.middleware decorator)
# =============================================================================


async def add_request_id_middleware(request: Request, call_next) -> Response:
    """
    Functional middleware for request ID tracking.

    Can be used with @app.middleware("http") decorator.

    Usage:
        app.middleware("http")(add_request_id_middleware)
    """
    request_id = request.headers.get("X-Request-Id")
    if not request_id:
        request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id

    return response


async def add_timing_middleware(request: Request, call_next) -> Response:
    """
    Functional middleware for request timing.

    Can be used with @app.middleware("http") decorator.
    """
    start_time = time.perf_counter()

    response = await call_next(request)

    process_time = (time.perf_counter() - start_time) * 1000
    response.headers["X-Response-Time"] = f"{process_time:.2f}ms"

    return response


def setup_middleware(
    app: "FastAPI",
    rate_limit_enabled: bool = True,
    rate_limit_requests_per_minute: int = 60,
    rate_limit_trust_proxy: bool = False,
    rate_limit_trusted_proxy_ips: list[str] | None = None,
    rate_limit_window_seconds: int = 60,
    security_headers_enabled: bool = True,
    csp_policy: str | None = None,
    hsts_max_age: int = 31536000,
    max_request_body_bytes: int = 1_048_576,
    debug: bool = False,
) -> None:
    """
    Configure all middleware for the application.

    This function adds middleware in the correct order.
    Order matters: first added = outermost = last to process request.
    Last added via add_middleware() = innermost = first to run on request.
    """
    # API Version (outermost - just adds header)
    app.add_middleware(APIVersionMiddleware, version="1.0.0")

    # Access logging (logs after timing and request ID are available)
    app.add_middleware(AccessLogMiddleware)

    # Timing (measures total request time)
    app.add_middleware(TimingMiddleware)

    # Security headers
    if security_headers_enabled:
        app.add_middleware(
            SecurityHeadersMiddleware,
            csp_policy=csp_policy,
            hsts_max_age=hsts_max_age,
            debug=debug,
        )

    # Rate Limiting (before request processing)
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=rate_limit_requests_per_minute,
        enabled=rate_limit_enabled,
        trust_proxy=rate_limit_trust_proxy,
        trusted_proxy_ips=rate_limit_trusted_proxy_ips,
        window_seconds=rate_limit_window_seconds,
    )

    # Request body size limit
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=max_request_body_bytes)

    # Request ID (innermost - needs to be available for all other middleware)
    app.add_middleware(RequestIDMiddleware)
