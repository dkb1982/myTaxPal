"""
Integration tests for the /v1/tax-years endpoint.

Tests tax year listing and details.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestListTaxYears:
    """Tests for GET /v1/tax-years endpoint."""

    def test_list_tax_years_returns_data(self, client: TestClient):
        """Test that list tax years returns data array."""
        response = client.get("/v1/tax-years")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "default_year" in data
        assert isinstance(data["data"], list)

    def test_list_tax_years_includes_2025(self, client: TestClient):
        """Test that list includes 2025 tax year."""
        response = client.get("/v1/tax-years")

        assert response.status_code == 200
        data = response.json()

        years = [y["year"] for y in data["data"]]
        assert 2025 in years

    def test_list_tax_years_includes_2024(self, client: TestClient):
        """Test that list includes 2024 tax year."""
        response = client.get("/v1/tax-years")

        assert response.status_code == 200
        data = response.json()

        years = [y["year"] for y in data["data"]]
        assert 2024 in years

    def test_list_tax_years_has_default_year(self, client: TestClient):
        """Test that response includes default year."""
        response = client.get("/v1/tax-years")

        assert response.status_code == 200
        data = response.json()

        assert data["default_year"] in [2024, 2025]

    def test_tax_year_summary_has_required_fields(self, client: TestClient):
        """Test that tax year summaries have required fields."""
        response = client.get("/v1/tax-years")

        assert response.status_code == 200
        data = response.json()

        for year_info in data["data"]:
            assert "year" in year_info
            assert "status" in year_info
            assert "filing_deadline" in year_info
            assert "rules_version" in year_info

    def test_tax_year_status_values(self, client: TestClient):
        """Test that tax year status has valid values."""
        response = client.get("/v1/tax-years")

        assert response.status_code == 200
        data = response.json()

        valid_statuses = {"current", "prior", "upcoming"}
        for year_info in data["data"]:
            assert year_info["status"] in valid_statuses


class TestGetTaxYear:
    """Tests for GET /v1/tax-years/{year} endpoint."""

    def test_get_tax_year_2025(self, client: TestClient):
        """Test getting 2025 tax year details."""
        response = client.get("/v1/tax-years/2025")

        assert response.status_code == 200
        data = response.json()

        assert data["year"] == 2025
        assert data["filing_deadline"] == "2026-04-15"

    def test_get_tax_year_2024(self, client: TestClient):
        """Test getting 2024 tax year details."""
        response = client.get("/v1/tax-years/2024")

        assert response.status_code == 200
        data = response.json()

        assert data["year"] == 2024
        assert data["filing_deadline"] == "2025-04-15"

    def test_get_tax_year_includes_key_thresholds(self, client: TestClient):
        """Test that tax year details include key thresholds."""
        response = client.get("/v1/tax-years/2025")

        assert response.status_code == 200
        data = response.json()

        assert "key_thresholds" in data
        if data["key_thresholds"]:
            thresholds = data["key_thresholds"]
            assert "standard_deduction" in thresholds
            assert "social_security_wage_base" in thresholds

    def test_get_tax_year_includes_supported_jurisdictions(self, client: TestClient):
        """Test that tax year details include jurisdiction counts."""
        response = client.get("/v1/tax-years/2025")

        assert response.status_code == 200
        data = response.json()

        assert "supported_jurisdictions" in data
        if data["supported_jurisdictions"]:
            jur = data["supported_jurisdictions"]
            assert "federal" in jur
            assert "states" in jur

    def test_get_tax_year_not_found(self, client: TestClient):
        """Test getting unsupported tax year."""
        response = client.get("/v1/tax-years/2015")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    def test_get_tax_year_has_changelog(self, client: TestClient):
        """Test that tax year details include changelog."""
        response = client.get("/v1/tax-years/2025")

        assert response.status_code == 200
        data = response.json()

        assert "changelog" in data
        if data["changelog"]:
            assert len(data["changelog"]) >= 1
            entry = data["changelog"][0]
            assert "date" in entry
            assert "version" in entry

    def test_get_tax_year_extension_deadline(self, client: TestClient):
        """Test that tax year includes extension deadline."""
        response = client.get("/v1/tax-years/2025")

        assert response.status_code == 200
        data = response.json()

        assert "extension_deadline" in data
        # 2025 extension deadline should be October 2026
        if data["extension_deadline"]:
            assert "2026-10" in data["extension_deadline"]
