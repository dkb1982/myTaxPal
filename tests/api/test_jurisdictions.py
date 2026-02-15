"""
Integration tests for the /v1/jurisdictions endpoint.

Tests jurisdiction listing, details, and bracket retrieval.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestListJurisdictions:
    """Tests for GET /v1/jurisdictions endpoint."""

    def test_list_jurisdictions_returns_data(self, client: TestClient):
        """Test that list jurisdictions returns data array."""
        response = client.get("/v1/jurisdictions")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert isinstance(data["data"], list)

    def test_list_jurisdictions_includes_federal(self, client: TestClient):
        """Test that list includes federal jurisdiction."""
        response = client.get("/v1/jurisdictions")

        assert response.status_code == 200
        data = response.json()

        jurisdiction_ids = [j["id"] for j in data["data"]]
        assert "US" in jurisdiction_ids

    def test_list_jurisdictions_includes_states(self, client: TestClient):
        """Test that list includes state jurisdictions."""
        response = client.get("/v1/jurisdictions")

        assert response.status_code == 200
        data = response.json()

        jurisdiction_ids = [j["id"] for j in data["data"]]
        # Check for some major states
        assert "US-CA" in jurisdiction_ids
        assert "US-NY" in jurisdiction_ids
        assert "US-TX" in jurisdiction_ids

    def test_list_jurisdictions_filter_by_level_federal(self, client: TestClient):
        """Test filtering jurisdictions by level=federal."""
        response = client.get("/v1/jurisdictions?level=federal")

        assert response.status_code == 200
        data = response.json()

        assert len(data["data"]) >= 1
        for jurisdiction in data["data"]:
            assert jurisdiction["level"] == "federal"

    def test_list_jurisdictions_filter_by_level_state(self, client: TestClient):
        """Test filtering jurisdictions by level=state."""
        response = client.get("/v1/jurisdictions?level=state")

        assert response.status_code == 200
        data = response.json()

        for jurisdiction in data["data"]:
            assert jurisdiction["level"] == "state"

    def test_list_jurisdictions_filter_by_has_income_tax(self, client: TestClient):
        """Test filtering jurisdictions by has_income_tax."""
        response = client.get("/v1/jurisdictions?has_income_tax=true&level=state")

        assert response.status_code == 200
        data = response.json()

        for jurisdiction in data["data"]:
            assert jurisdiction["has_income_tax"] is True

    def test_list_jurisdictions_filter_no_income_tax(self, client: TestClient):
        """Test filtering jurisdictions without income tax."""
        response = client.get("/v1/jurisdictions?has_income_tax=false&level=state")

        assert response.status_code == 200
        data = response.json()

        # Should include states like TX, FL, WA
        jurisdiction_ids = [j["id"] for j in data["data"]]
        no_tax_states = {"US-TX", "US-FL", "US-WA", "US-NV", "US-WY", "US-SD", "US-AK"}
        found_no_tax = jurisdiction_ids[0] if jurisdiction_ids else None
        assert found_no_tax is None or found_no_tax in no_tax_states

    def test_list_jurisdictions_pagination(self, client: TestClient):
        """Test pagination of jurisdictions list."""
        response = client.get("/v1/jurisdictions?limit=10&offset=0")

        assert response.status_code == 200
        data = response.json()

        assert len(data["data"]) <= 10
        assert data["pagination"]["limit"] == 10
        assert data["pagination"]["offset"] == 0
        assert "total" in data["pagination"]
        assert "has_more" in data["pagination"]

    def test_list_jurisdictions_pagination_offset(self, client: TestClient):
        """Test pagination with offset."""
        # Get first page
        response1 = client.get("/v1/jurisdictions?limit=5&offset=0")
        data1 = response1.json()

        # Get second page
        response2 = client.get("/v1/jurisdictions?limit=5&offset=5")
        data2 = response2.json()

        # Ensure different results
        ids1 = {j["id"] for j in data1["data"]}
        ids2 = {j["id"] for j in data2["data"]}
        assert ids1.isdisjoint(ids2), "Paginated results should not overlap"


class TestGetJurisdiction:
    """Tests for GET /v1/jurisdictions/{id} endpoint."""

    def test_get_federal_jurisdiction(self, client: TestClient):
        """Test getting federal jurisdiction details."""
        response = client.get("/v1/jurisdictions/US")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == "US"
        assert data["level"] == "federal"
        assert data["has_income_tax"] is True

    def test_get_state_jurisdiction(self, client: TestClient):
        """Test getting state jurisdiction details."""
        response = client.get("/v1/jurisdictions/US-CA")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == "US-CA"
        assert data["level"] == "state"
        assert data["parent_id"] == "US"

    def test_get_jurisdiction_includes_links(self, client: TestClient):
        """Test that jurisdiction details include links."""
        response = client.get("/v1/jurisdictions/US-CA")

        assert response.status_code == 200
        data = response.json()

        assert "links" in data
        assert "self" in data["links"]

    def test_get_jurisdiction_not_found(self, client: TestClient):
        """Test getting non-existent jurisdiction."""
        response = client.get("/v1/jurisdictions/US-XX")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    def test_get_no_income_tax_state(self, client: TestClient):
        """Test getting state without income tax."""
        response = client.get("/v1/jurisdictions/US-TX")

        assert response.status_code == 200
        data = response.json()

        assert data["has_income_tax"] is False

    def test_get_jurisdiction_with_tax_year(self, client: TestClient):
        """Test getting jurisdiction with specific tax year."""
        response = client.get("/v1/jurisdictions/US-CA?tax_year=2025")

        assert response.status_code == 200
        data = response.json()

        assert data["tax_year"] == 2025


class TestGetJurisdictionBrackets:
    """Tests for GET /v1/jurisdictions/{id}/brackets endpoint."""

    def test_get_federal_brackets(self, client: TestClient):
        """Test getting federal tax brackets."""
        response = client.get("/v1/jurisdictions/US/brackets")

        assert response.status_code == 200
        data = response.json()

        assert data["jurisdiction_id"] == "US"
        assert "brackets_by_filing_status" in data

    def test_get_brackets_by_filing_status(self, client: TestClient):
        """Test getting brackets filtered by filing status."""
        response = client.get("/v1/jurisdictions/US/brackets?filing_status=single")

        assert response.status_code == 200
        data = response.json()

        # Should have brackets for single or all
        brackets = data["brackets_by_filing_status"]
        assert "single" in brackets or "all" in brackets

    def test_get_brackets_with_tax_year(self, client: TestClient):
        """Test getting brackets for specific tax year."""
        response = client.get("/v1/jurisdictions/US/brackets?tax_year=2025")

        assert response.status_code == 200
        data = response.json()

        assert data["tax_year"] == 2025

    def test_get_brackets_not_found(self, client: TestClient):
        """Test getting brackets for non-existent jurisdiction."""
        response = client.get("/v1/jurisdictions/US-XX/brackets")

        assert response.status_code == 404

    def test_brackets_have_required_fields(self, client: TestClient):
        """Test that brackets have required fields."""
        response = client.get("/v1/jurisdictions/US/brackets")

        assert response.status_code == 200
        data = response.json()

        for status, brackets in data["brackets_by_filing_status"].items():
            for bracket in brackets:
                assert "min" in bracket
                assert "rate" in bracket
                # max can be None for highest bracket
                assert "max" in bracket
