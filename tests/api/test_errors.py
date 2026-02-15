"""
Integration tests for API error handling.

Tests error responses, exception handling, and error formats.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestErrorResponses:
    """Tests for API error response format."""

    def test_validation_error_format(self, client: TestClient):
        """Test that validation errors follow API spec format."""
        request = {
            "tax_year": 2025,
            # Missing filer field
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422
        data = response.json()

        # Check error structure
        assert "error" in data
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert "status" in error
        assert "request_id" in error
        assert "details" in error

    def test_validation_error_includes_field_details(self, client: TestClient):
        """Test that validation errors include field-level details."""
        request = {
            "tax_year": 2025,
            "filer": {},  # Missing filing_status
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422
        data = response.json()

        details = data["error"]["details"]
        assert len(details) >= 1

        detail = details[0]
        assert "field" in detail
        assert "code" in detail
        assert "message" in detail

    def test_not_found_error_format(self, client: TestClient):
        """Test that not found errors follow API spec format."""
        response = client.get("/v1/jurisdictions/US-XX")

        assert response.status_code == 404
        data = response.json()

        assert "error" in data
        error = data["error"]
        assert error["code"] == "RESOURCE_NOT_FOUND"
        assert error["status"] == 404
        assert "request_id" in error

    def test_error_includes_request_id(self, client: TestClient):
        """Test that errors include request_id."""
        request = {"tax_year": "invalid"}  # Invalid type
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422
        data = response.json()

        assert data["error"]["request_id"] is not None
        assert data["error"]["request_id"] != ""

    def test_error_with_custom_request_id(self, client: TestClient):
        """Test that custom request ID appears in error response."""
        custom_id = "custom-error-test-id"
        request = {"tax_year": "invalid"}
        response = client.post(
            "/v1/estimates",
            json=request,
            headers={"X-Request-Id": custom_id},
        )

        assert response.status_code == 422
        data = response.json()

        assert data["error"]["request_id"] == custom_id


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns frontend HTML or API info at /api."""
        # When static files exist, root returns HTML frontend
        response = client.get("/")
        assert response.status_code == 200

        # Check if it's HTML (frontend enabled) or JSON (frontend disabled)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            # Frontend is enabled - verify it serves HTML
            assert "TaxEstimate" in response.text
            # API info should be available at /api
            api_response = client.get("/api")
            assert api_response.status_code == 200
            data = api_response.json()
        else:
            # Frontend not enabled - root returns JSON
            data = response.json()

        assert "name" in data
        assert "version" in data
        assert "disclaimer" in data
        assert "endpoints" in data

    def test_root_includes_endpoints(self, client: TestClient):
        """Test API info endpoint lists available endpoints."""
        # Try /api first (frontend enabled), then / (frontend disabled)
        response = client.get("/api")
        if response.status_code == 404:
            response = client.get("/")

        assert response.status_code == 200
        data = response.json()

        endpoints = data["endpoints"]
        assert "estimates" in endpoints
        assert "jurisdictions" in endpoints
        assert "tax_years" in endpoints
        assert "validate" in endpoints


class TestMiddleware:
    """Tests for API middleware."""

    def test_request_id_header_in_response(self, client: TestClient):
        """Test that X-Request-Id is in all responses."""
        response = client.get("/health")

        assert "X-Request-Id" in response.headers
        assert len(response.headers["X-Request-Id"]) > 0

    def test_custom_request_id_echoed(self, client: TestClient):
        """Test that custom X-Request-Id is echoed."""
        custom_id = "test-id-12345"
        response = client.get(
            "/health",
            headers={"X-Request-Id": custom_id},
        )

        assert response.headers["X-Request-Id"] == custom_id

    def test_timing_header_in_response(self, client: TestClient):
        """Test that X-Response-Time is in responses."""
        response = client.get("/health")

        assert "X-Response-Time" in response.headers
        timing = response.headers["X-Response-Time"]
        assert timing.endswith("ms")

    def test_api_version_header(self, client: TestClient):
        """Test that X-API-Version is in responses."""
        response = client.get("/health")

        assert "X-API-Version" in response.headers
        assert response.headers["X-API-Version"] == "1.0.0"


class TestInvalidRequests:
    """Tests for invalid request handling."""

    def test_invalid_json_body(self, client: TestClient):
        """Test handling of invalid JSON body."""
        response = client.post(
            "/v1/estimates",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_wrong_content_type(self, client: TestClient):
        """Test handling of wrong content type."""
        response = client.post(
            "/v1/estimates",
            data={"tax_year": "2025"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 422

    def test_nonexistent_endpoint(self, client: TestClient):
        """Test 404 for nonexistent endpoint."""
        response = client.get("/v1/nonexistent")

        assert response.status_code == 404

    def test_method_not_allowed(self, client: TestClient):
        """Test 405 for wrong HTTP method."""
        response = client.put("/v1/estimates", json={})

        assert response.status_code == 405
