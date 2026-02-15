"""
Integration tests for the /v1/validate endpoint.

Tests input validation without full calculation.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient


class TestValidateInput:
    """Tests for POST /v1/validate endpoint."""

    def test_validate_valid_input(
        self, client: TestClient, simple_estimate_request: dict[str, Any]
    ):
        """Test validation of valid input."""
        response = client.post("/v1/validate", json=simple_estimate_request)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "errors" in data
        assert len(data["errors"]) == 0

    def test_validate_returns_warnings(
        self, client: TestClient, validation_request_with_issues: dict[str, Any]
    ):
        """Test that validation returns warnings for potential issues."""
        response = client.post("/v1/validate", json=validation_request_with_issues)

        assert response.status_code == 200
        data = response.json()
        assert "warnings" in data
        # Should have warnings for HOH without dependents, no income tax state, etc.
        assert len(data["warnings"]) >= 1

    def test_validate_returns_suggestions(
        self, client: TestClient, validation_request_with_issues: dict[str, Any]
    ):
        """Test that validation returns suggestions for optimization."""
        response = client.post("/v1/validate", json=validation_request_with_issues)

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        # Should suggest standard deduction if itemized is lower
        if data["suggestions"]:
            suggestion_codes = [s["code"] for s in data["suggestions"]]
            assert "BELOW_STANDARD_DEDUCTION" in suggestion_codes

    def test_validate_invalid_state_code(self, client: TestClient):
        """Test validation catches invalid state code."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "XX"},  # Invalid
            "income": {},
        }
        response = client.post("/v1/validate", json=request)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

        error_codes = [e["code"] for e in data["errors"]]
        assert "INVALID_STATE_CODE" in error_codes

    def test_validate_unsupported_tax_year(self, client: TestClient):
        """Test validation catches unsupported tax year via schema validation."""
        request = {
            "tax_year": 2020,  # Too old - fails schema validation (ge=2024, le=2025)
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/validate", json=request)

        # Schema validation fails before business validation
        # tax_year field has ge=2024, le=2025 constraint
        assert response.status_code == 422
        data = response.json()
        assert "error" in data

    def test_validate_hoh_without_dependents_warning(self, client: TestClient):
        """Test validation warns about HOH without dependents."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "hoh"},
            "residency": {"residence_state": "CA"},
            "income": {"wages": [{"employer_name": "Test", "employer_state": "CA", "gross_wages": 50000}]},
        }
        response = client.post("/v1/validate", json=request)

        assert response.status_code == 200
        data = response.json()
        assert "warnings" in data

        warning_codes = [w["code"] for w in data["warnings"]]
        assert "HOH_NO_DEPENDENTS" in warning_codes

    def test_validate_no_income_tax_state_info(self, client: TestClient):
        """Test validation provides info about no income tax states."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "TX"},  # No income tax
            "income": {"wages": [{"employer_name": "Test", "employer_state": "TX", "gross_wages": 50000}]},
        }
        response = client.post("/v1/validate", json=request)

        assert response.status_code == 200
        data = response.json()

        warning_codes = [w["code"] for w in data["warnings"]]
        assert "NO_STATE_INCOME_TAX" in warning_codes

    def test_validate_mfj_without_spouse_info(self, client: TestClient):
        """Test validation warns about MFJ without spouse info."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "mfj"},
            "residency": {"residence_state": "CA"},
            "income": {"wages": [{"employer_name": "Test", "employer_state": "CA", "gross_wages": 50000}]},
            # No spouse field
        }
        response = client.post("/v1/validate", json=request)

        assert response.status_code == 200
        data = response.json()

        warning_codes = [w["code"] for w in data["warnings"]]
        assert "MISSING_SPOUSE_INFO" in warning_codes


class TestValidateAddress:
    """Tests for POST /v1/validate/address endpoint."""

    def test_validate_valid_address(self, client: TestClient):
        """Test validation of valid address."""
        address = {
            "street": "123 Main Street",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94102",
        }
        response = client.post("/v1/validate/address", json=address)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "standardized" in data

    def test_validate_address_returns_standardized(self, client: TestClient):
        """Test that validation returns standardized address."""
        address = {
            "street": "123 main st",
            "city": "san francisco",
            "state": "CA",
            "zip": "94102",
        }
        response = client.post("/v1/validate/address", json=address)

        assert response.status_code == 200
        data = response.json()

        standardized = data["standardized"]
        assert standardized["city"] == "San Francisco"  # Title case
        assert "formatted" in standardized

    def test_validate_address_returns_jurisdictions(self, client: TestClient):
        """Test that validation returns jurisdiction lookup."""
        address = {
            "street": "123 Main Street",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94102",
        }
        response = client.post("/v1/validate/address", json=address)

        assert response.status_code == 200
        data = response.json()

        assert "jurisdiction_lookup" in data
        lookup = data["jurisdiction_lookup"]
        assert lookup["state"] == "US-CA"

    def test_validate_nyc_address(self, client: TestClient):
        """Test validation of NYC address includes city jurisdiction."""
        address = {
            "street": "350 5th Avenue",
            "city": "New York",
            "state": "NY",
            "zip": "10118",
        }
        response = client.post("/v1/validate/address", json=address)

        assert response.status_code == 200
        data = response.json()

        lookup = data["jurisdiction_lookup"]
        assert lookup["state"] == "US-NY"
        assert lookup["city"] == "US-NY-NYC"

    def test_validate_invalid_state_address(self, client: TestClient):
        """Test validation of address with invalid state."""
        address = {
            "street": "123 Main Street",
            "city": "Some City",
            "state": "XX",  # Invalid
            "zip": "12345",
        }
        response = client.post("/v1/validate/address", json=address)

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
