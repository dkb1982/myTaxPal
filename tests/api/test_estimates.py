"""
Integration tests for the /v1/estimates endpoint.

Tests the estimate creation functionality including:
- Simple estimate creation
- Complex multi-income estimates
- Self-employment income
- Validation errors
- Error handling

All test values are FAKE and for testing only.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient


class TestCreateEstimate:
    """Tests for POST /v1/estimates endpoint."""

    def test_create_simple_estimate(
        self, client: TestClient, simple_estimate_request: dict[str, Any]
    ):
        """Test creating a simple tax estimate."""
        response = client.post("/v1/estimates", json=simple_estimate_request)

        assert response.status_code == 201
        data = response.json()

        # Check basic response structure
        assert "id" in data
        assert data["id"].startswith("est_")
        assert data["tax_year"] == 2025
        assert data["status"] in ["complete", "partial"]
        assert "summary" in data
        assert "federal" in data
        assert "disclaimers" in data

    def test_create_estimate_response_has_summary(
        self, client: TestClient, simple_estimate_request: dict[str, Any]
    ):
        """Test that estimate response includes summary with expected fields."""
        response = client.post("/v1/estimates", json=simple_estimate_request)

        assert response.status_code == 201
        data = response.json()
        summary = data["summary"]

        # Check summary fields
        assert "total_income" in summary
        assert "adjusted_gross_income" in summary
        assert "taxable_income" in summary
        assert "total_federal_tax" in summary
        assert "total_tax" in summary
        assert "effective_rate" in summary
        assert "marginal_rate" in summary
        assert "balance_due" in summary

    def test_create_estimate_response_has_federal_result(
        self, client: TestClient, simple_estimate_request: dict[str, Any]
    ):
        """Test that estimate response includes federal tax result."""
        response = client.post("/v1/estimates", json=simple_estimate_request)

        assert response.status_code == 201
        data = response.json()
        federal = data["federal"]

        # Check federal result fields
        assert federal["jurisdiction_id"] == "US"
        assert "gross_income" in federal
        assert "adjusted_gross_income" in federal
        assert "deduction_type" in federal
        assert "deduction_amount" in federal
        assert "taxable_income" in federal
        assert "tax_before_credits" in federal
        assert "total_tax" in federal
        assert "balance_due_or_refund" in federal

    def test_create_estimate_has_disclaimers(
        self, client: TestClient, simple_estimate_request: dict[str, Any]
    ):
        """Test that estimate includes required disclaimers."""
        response = client.post("/v1/estimates", json=simple_estimate_request)

        assert response.status_code == 201
        data = response.json()

        assert len(data["disclaimers"]) >= 1
        # Check that at least one disclaimer mentions not being tax advice
        has_tax_advice_disclaimer = any(
            "not" in d.lower() and "tax advice" in d.lower()
            for d in data["disclaimers"]
        )
        assert has_tax_advice_disclaimer, "Should include 'not tax advice' disclaimer"

    def test_create_estimate_has_links(
        self, client: TestClient, simple_estimate_request: dict[str, Any]
    ):
        """Test that estimate includes HATEOAS links."""
        response = client.post("/v1/estimates", json=simple_estimate_request)

        assert response.status_code == 201
        data = response.json()

        assert "links" in data
        links = data["links"]
        assert "self" in links
        assert data["id"] in links["self"]

    def test_create_estimate_mfj_with_spouse(
        self, client: TestClient, complex_estimate_request: dict[str, Any]
    ):
        """Test creating estimate for married filing jointly."""
        response = client.post("/v1/estimates", json=complex_estimate_request)

        assert response.status_code == 201
        data = response.json()

        # Verify combined income from two wage earners
        # Note: Decimal values are serialized as strings in JSON
        summary = data["summary"]
        total_income = float(summary["total_income"])
        assert total_income >= 200000  # 120k + 80k + interest/dividends

    def test_create_estimate_with_self_employment(
        self, client: TestClient, self_employment_request: dict[str, Any]
    ):
        """Test creating estimate with self-employment income."""
        response = client.post("/v1/estimates", json=self_employment_request)

        assert response.status_code == 201
        data = response.json()

        # Self-employment should trigger SE tax
        federal = data["federal"]
        se_tax = float(federal["self_employment_tax"])
        assert se_tax > 0

    def test_create_estimate_missing_required_field(self, client: TestClient):
        """Test validation error when required field is missing."""
        # Missing filer field
        request = {
            "tax_year": 2025,
            "residency": {"residence_state": "CA"},
            "income": {"wages": []},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422
        data = response.json()
        assert "error" in data

    def test_create_estimate_missing_filing_status(self, client: TestClient):
        """Test validation error when filing_status is missing."""
        request = {
            "tax_year": 2025,
            "filer": {},  # Missing filing_status
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        # Check that the error mentions the missing field
        error_details = data["error"].get("details", [])
        assert len(error_details) > 0

    def test_create_estimate_invalid_state_code(self, client: TestClient):
        """Test validation error for invalid state code."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "XX"},  # Invalid
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_STATE_CODE"

    def test_create_estimate_unsupported_tax_year(self, client: TestClient):
        """Test validation error for unsupported tax year."""
        request = {
            "tax_year": 2020,  # Too old
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {},
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 422

    def test_create_estimate_returns_request_id_header(
        self, client: TestClient, simple_estimate_request: dict[str, Any]
    ):
        """Test that response includes X-Request-Id header."""
        response = client.post("/v1/estimates", json=simple_estimate_request)

        assert response.status_code == 201
        assert "X-Request-Id" in response.headers

    def test_create_estimate_echoes_provided_request_id(
        self, client: TestClient, simple_estimate_request: dict[str, Any]
    ):
        """Test that provided X-Request-Id is echoed in response."""
        custom_request_id = "test-request-12345"
        response = client.post(
            "/v1/estimates",
            json=simple_estimate_request,
            headers={"X-Request-Id": custom_request_id},
        )

        assert response.status_code == 201
        assert response.headers.get("X-Request-Id") == custom_request_id

    def test_create_estimate_includes_timing_header(
        self, client: TestClient, simple_estimate_request: dict[str, Any]
    ):
        """Test that response includes timing header."""
        response = client.post("/v1/estimates", json=simple_estimate_request)

        assert response.status_code == 201
        assert "X-Response-Time" in response.headers
        # Should be in format like "123.45ms"
        timing = response.headers["X-Response-Time"]
        assert timing.endswith("ms")


class TestEstimateEdgeCases:
    """Tests for edge cases in estimate creation."""

    def test_estimate_with_zero_income(self, client: TestClient):
        """Test estimate with zero income."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {},  # No income
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201
        data = response.json()
        summary = data["summary"]
        # Note: Decimal values are serialized as strings in JSON
        assert float(summary["total_income"]) == 0
        assert float(summary["total_tax"]) == 0

    def test_estimate_no_income_tax_state(self, client: TestClient):
        """Test estimate for state without income tax."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "TX"},  # No income tax
            "income": {
                "wages": [
                    {
                        "employer_name": "Test",
                        "employer_state": "TX",
                        "gross_wages": 50000,
                    }
                ]
            },
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201
        data = response.json()
        summary = data["summary"]
        # No state tax expected (Decimal serialized as string)
        assert float(summary["total_state_tax"]) == 0

    def test_estimate_itemized_deductions(self, client: TestClient):
        """Test estimate with itemized deductions."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {
                "wages": [
                    {
                        "employer_name": "Test",
                        "employer_state": "CA",
                        "gross_wages": 150000,
                    }
                ]
            },
            "deductions": {
                "type": "itemized",
                "itemized": {
                    "mortgage_interest": 15000,
                    "state_local_taxes_paid": 10000,
                    "charitable_cash": 5000,
                },
            },
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201
        data = response.json()
        federal = data["federal"]
        assert federal["deduction_type"] == "itemized"

    def test_estimate_with_multiple_wages(self, client: TestClient):
        """Test estimate with multiple W-2s."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "NY"},
            "income": {
                "wages": [
                    {
                        "employer_name": "Employer A",
                        "employer_state": "NY",
                        "gross_wages": 50000,
                    },
                    {
                        "employer_name": "Employer B",
                        "employer_state": "NY",
                        "gross_wages": 30000,
                    },
                    {
                        "employer_name": "Employer C",
                        "employer_state": "NJ",
                        "gross_wages": 20000,
                    },
                ]
            },
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201
        data = response.json()
        summary = data["summary"]
        total_income = float(summary["total_income"])
        assert total_income >= 100000  # 50k + 30k + 20k

    def test_estimate_with_capital_gains(self, client: TestClient):
        """Test estimate with capital gains includes income split and tax amounts."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {
                "wages": [
                    {
                        "employer_name": "Test",
                        "employer_state": "CA",
                        "gross_wages": 100000,
                    }
                ],
                "capital_gains": {
                    "long_term_gain": 20000,
                    "short_term_gain": 5000,
                },
            },
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201
        data = response.json()
        summary = data["summary"]
        total_income = float(summary["total_income"])
        assert total_income >= 125000  # 100k + 20k + 5k

        # Verify income type split is in the response
        federal = data["federal"]
        assert "ordinary_income" in federal
        assert "preferential_income" in federal
        assert "ordinary_tax" in federal
        assert "preferential_tax" in federal

        # LTCG should be preferential, STCG should be ordinary
        pref_income = float(federal["preferential_income"])
        assert pref_income == 20000.0  # Only LTCG

        # Tax amounts should be non-negative
        assert float(federal["ordinary_tax"]) > 0
        assert float(federal["preferential_tax"]) >= 0

        # Total tax before credits = ordinary + preferential (+ surtaxes)
        assert float(federal["tax_before_credits"]) >= (
            float(federal["ordinary_tax"]) + float(federal["preferential_tax"])
        )

    def test_mixed_income_effective_rate_is_blended(self, client: TestClient):
        """Test that effective rate with mixed income is properly blended."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {
                "wages": [
                    {
                        "employer_name": "Test",
                        "employer_state": "CA",
                        "gross_wages": 80000,
                    }
                ],
                "capital_gains": {
                    "long_term_gain": 30000,
                },
            },
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201
        data = response.json()
        federal = data["federal"]

        # Effective rate should be a blend between ordinary rates and preferential rates
        effective_rate = float(data["summary"]["effective_rate"])
        assert effective_rate > 0
        # Should be less than the top ordinary bracket rate
        assert effective_rate < 0.40

        # Preferential rate breakdown should be present if preferential income > 0
        pref_income = float(federal["preferential_income"])
        if pref_income > 0:
            assert len(federal["preferential_rate_breakdown"]) > 0
            for entry in federal["preferential_rate_breakdown"]:
                assert "rate" in entry
                assert "income_in_bracket" in entry
                assert "tax_in_bracket" in entry

    def test_estimate_with_interest_dividends(self, client: TestClient):
        """Test estimate with interest and dividend income."""
        request = {
            "tax_year": 2025,
            "filer": {"filing_status": "single"},
            "residency": {"residence_state": "CA"},
            "income": {
                "interest": {
                    "taxable": 5000,
                    "tax_exempt": 2000,
                },
                "dividends": {
                    "ordinary": 3000,
                    "qualified": 2000,
                },
            },
        }
        response = client.post("/v1/estimates", json=request)

        assert response.status_code == 201
        data = response.json()
        summary = data["summary"]
        # Taxable interest + ordinary dividends
        total_income = float(summary["total_income"])
        assert total_income >= 8000
