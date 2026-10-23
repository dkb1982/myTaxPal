"""Tests for API middleware: security headers, access logging, request size limits."""

from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient

from tax_estimator.config import Settings
from tax_estimator.main import create_app


@pytest.fixture
def prod_client() -> Generator[TestClient, None, None]:
    """Client with production-like settings (debug=False)."""
    settings = Settings(
        debug=False,
        rate_limit_enabled=False,
        security_headers_enabled=True,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def debug_client() -> Generator[TestClient, None, None]:
    """Client with debug=True."""
    settings = Settings(
        debug=True,
        rate_limit_enabled=False,
        security_headers_enabled=True,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def no_security_client() -> Generator[TestClient, None, None]:
    """Client with security headers disabled."""
    settings = Settings(
        debug=False,
        rate_limit_enabled=False,
        security_headers_enabled=False,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def small_body_client() -> Generator[TestClient, None, None]:
    """Client with a very small request body limit."""
    settings = Settings(
        debug=True,
        rate_limit_enabled=False,
        max_request_body_bytes=100,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


class TestSecurityHeaders:
    """Tests for SecurityHeadersMiddleware."""

    def test_csp_header_present(self, prod_client: TestClient) -> None:
        response = prod_client.get("/health")
        assert "Content-Security-Policy" in response.headers
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_x_content_type_options(self, prod_client: TestClient) -> None:
        response = prod_client.get("/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options(self, prod_client: TestClient) -> None:
        response = prod_client.get("/health")
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_referrer_policy(self, prod_client: TestClient) -> None:
        response = prod_client.get("/health")
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, prod_client: TestClient) -> None:
        response = prod_client.get("/health")
        assert "camera=()" in response.headers["Permissions-Policy"]

    def test_hsts_present_in_production(self, prod_client: TestClient) -> None:
        response = prod_client.get("/health")
        assert "Strict-Transport-Security" in response.headers
        assert "max-age=" in response.headers["Strict-Transport-Security"]

    def test_hsts_skipped_in_debug(self, debug_client: TestClient) -> None:
        response = debug_client.get("/health")
        assert "Strict-Transport-Security" not in response.headers

    def test_security_headers_disabled(self, no_security_client: TestClient) -> None:
        response = no_security_client.get("/health")
        assert "Content-Security-Policy" not in response.headers
        assert "X-Frame-Options" not in response.headers

    def test_csp_allows_jsdelivr_styles(self, prod_client: TestClient) -> None:
        csp = prod_client.get("/health").headers["Content-Security-Policy"]
        assert "style-src 'self' https://cdn.jsdelivr.net" in csp

    def test_csp_no_unsafe_inline(self, prod_client: TestClient) -> None:
        csp = prod_client.get("/health").headers["Content-Security-Policy"]
        assert "unsafe-inline" not in csp


class TestConditionalOpenAPI:
    """Tests for conditional /docs exposure."""

    def test_docs_available_in_debug(self, debug_client: TestClient) -> None:
        response = debug_client.get("/docs")
        assert response.status_code == 200

    def test_docs_hidden_in_production(self, prod_client: TestClient) -> None:
        response = prod_client.get("/docs")
        assert response.status_code == 404

    def test_openapi_json_hidden_in_production(self, prod_client: TestClient) -> None:
        response = prod_client.get("/openapi.json")
        assert response.status_code == 404

    def test_redoc_hidden_in_production(self, prod_client: TestClient) -> None:
        response = prod_client.get("/redoc")
        assert response.status_code == 404


class TestRequestSizeLimit:
    """Tests for RequestSizeLimitMiddleware."""

    def test_normal_request_succeeds(self, debug_client: TestClient) -> None:
        response = debug_client.get("/health")
        assert response.status_code == 200

    def test_oversized_body_rejected(self, small_body_client: TestClient) -> None:
        large_body = '{"data": "' + "x" * 200 + '"}'
        response = small_body_client.post(
            "/v1/estimates",
            content=large_body,
            headers={"Content-Type": "application/json", "Content-Length": str(len(large_body))},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


class TestRequestID:
    """Tests for request ID middleware."""

    def test_generates_request_id(self, debug_client: TestClient) -> None:
        response = debug_client.get("/health")
        assert "X-Request-Id" in response.headers
        assert len(response.headers["X-Request-Id"]) > 0

    def test_echoes_provided_request_id(self, debug_client: TestClient) -> None:
        response = debug_client.get(
            "/health", headers={"X-Request-Id": "my-custom-id-123"}
        )
        assert response.headers["X-Request-Id"] == "my-custom-id-123"


class TestAccessLog:
    """Tests for access log middleware."""

    def test_access_log_emitted(self, debug_client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("INFO", logger="tax_estimator.access"):
            debug_client.get("/health")
        assert any("GET /health 200" in record.message for record in caplog.records)


class TestRequestSizeLimitHardening:
    """Malformed and streamed bodies are handled without a 500."""

    def test_malformed_content_length_is_400(self, small_body_client: TestClient) -> None:
        response = small_body_client.post(
            "/v1/estimates",
            content=b"{}",
            headers={"Content-Type": "application/json", "Content-Length": "abc"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_CONTENT_LENGTH"

    def test_chunked_oversized_body_rejected(self, small_body_client: TestClient) -> None:
        def chunks():
            for _ in range(10):
                yield b"x" * 50

        response = small_body_client.post(
            "/v1/estimates",
            content=chunks(),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_validation_errors_do_not_echo_submitted_values(debug_client: TestClient) -> None:
    response = debug_client.post(
        "/v1/estimates",
        json={"tax_year": 2025, "filer": {"filing_status": "single", "date_of_birth": "1985-02-30"},
              "residency": {"residence_state": "CA"}, "income": {"wages": [{"gross_wages": 98765.43}]}},
    )
    assert response.status_code == 422
    assert "98765.43" not in response.text
    assert "1985-02-30" not in response.text
    assert "help_url" not in response.text


def test_oversized_response_keeps_security_headers(small_body_client: TestClient) -> None:
    def chunks():
        for _ in range(10):
            yield b"x" * 50

    response = small_body_client.post(
        "/v1/estimates", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert "Content-Security-Policy" in response.headers
    assert "X-Content-Type-Options" in response.headers


def test_duplicate_forwarded_for_lines_use_rightmost_hop() -> None:
    from starlette.datastructures import Headers
    from unittest.mock import MagicMock

    from tax_estimator.api.middleware import RateLimitMiddleware

    middleware = RateLimitMiddleware(app=None, requests_per_minute=10, trust_proxy=True, enabled=True)
    request = MagicMock()
    # Client-supplied line first, then the line appended by the trusted proxy.
    request.headers = Headers(raw=[(b"x-forwarded-for", b"1.1.1.1"), (b"x-forwarded-for", b"203.0.113.9")])
    request.client.host = "127.0.0.1"
    assert middleware._get_client_ip(request) == "203.0.113.9"
