"""
Tests for the FastAPI API endpoints.

This module contains tests for the REST API endpoints including health checks
and tax year listing.

Note: These are the original/legacy tests. Comprehensive API tests are in tests/api/.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check_returns_ok(self, client: TestClient) -> None:
        """GET /health should return status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_root_returns_api_info(self, client: TestClient) -> None:
        """GET / or /api should return API information."""
        response = client.get("/")
        assert response.status_code == 200

        # Check if frontend is serving HTML (static files exist)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            # Frontend enabled - use /api endpoint
            response = client.get("/api")
            assert response.status_code == 200

        data = response.json()
        assert data["name"] == "TaxEstimate API"
        assert "version" in data
        assert "docs" in data
        assert "disclaimer" in data

    def test_docs_endpoint_accessible(self, client: TestClient) -> None:
        """GET /docs should be accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_endpoint_accessible(self, client: TestClient) -> None:
        """GET /redoc should be accessible."""
        response = client.get("/redoc")
        assert response.status_code == 200


class TestTaxYearsEndpoints:
    """Tests for tax years listing endpoints."""

    def test_get_tax_years_returns_structure(self, client: TestClient) -> None:
        """GET /v1/tax-years should return proper structure."""
        response = client.get("/v1/tax-years")
        assert response.status_code == 200
        data = response.json()
        # New API structure
        assert "data" in data
        assert "default_year" in data
        assert isinstance(data["data"], list)
        assert isinstance(data["default_year"], int)

    def test_get_tax_years_includes_2025(self, client: TestClient) -> None:
        """GET /v1/tax-years should include 2025 tax year."""
        response = client.get("/v1/tax-years")
        assert response.status_code == 200
        data = response.json()
        years = [y["year"] for y in data["data"]]
        assert 2025 in years

    def test_get_tax_year_detail(self, client: TestClient) -> None:
        """GET /v1/tax-years/2025 should return tax year details."""
        response = client.get("/v1/tax-years/2025")
        assert response.status_code == 200
        data = response.json()
        assert data["year"] == 2025
        assert "filing_deadline" in data
        assert "status" in data

    def test_get_nonexistent_tax_year_returns_404(self, client: TestClient) -> None:
        """GET /v1/tax-years/2015 should return 404."""
        response = client.get("/v1/tax-years/2015")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data


class TestAPIResponses:
    """Tests for API response format and content."""

    def test_disclaimer_in_root(self, client: TestClient) -> None:
        """API info endpoint should include disclaimer."""
        response = client.get("/")

        # Check if frontend is serving HTML (static files exist)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            # Frontend enabled - use /api endpoint
            response = client.get("/api")

        data = response.json()
        assert "estimation purposes only" in data["disclaimer"].lower()

    def test_version_format(self, client: TestClient) -> None:
        """Version should be in semver format."""
        response = client.get("/")

        # Check if frontend is serving HTML (static files exist)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            # Frontend enabled - use /api endpoint
            response = client.get("/api")

        data = response.json()
        version = data["version"]
        # Should be something like "0.1.0"
        parts = version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)
