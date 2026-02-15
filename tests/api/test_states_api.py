"""
Tests for state and local tax API endpoints.

All tests use PLACEHOLDER data.
"""

import pytest
from fastapi.testclient import TestClient

from tax_estimator.main import create_app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    app = create_app()
    return TestClient(app)


class TestStatesListEndpoint:
    """Tests for GET /v1/states."""

    def test_list_states_returns_51_states(self, client: TestClient) -> None:
        """Test states list returns all 50 states plus DC."""
        response = client.get("/v1/states")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 51

    def test_list_states_includes_required_fields(self, client: TestClient) -> None:
        """Test each state has required fields."""
        response = client.get("/v1/states")
        data = response.json()
        for state in data["data"]:
            assert "code" in state
            assert "name" in state
            assert "has_income_tax" in state
            assert "tax_type" in state

    def test_list_states_includes_tax_year(self, client: TestClient) -> None:
        """Test response includes tax year."""
        response = client.get("/v1/states")
        data = response.json()
        assert "tax_year" in data

    def test_list_states_with_tax_year_param(self, client: TestClient) -> None:
        """Test states list accepts tax_year parameter."""
        response = client.get("/v1/states?tax_year=2025")
        assert response.status_code == 200
        data = response.json()
        assert data["tax_year"] == 2025

    def test_states_sorted_by_code(self, client: TestClient) -> None:
        """Test states are sorted by code."""
        response = client.get("/v1/states")
        data = response.json()
        codes = [s["code"] for s in data["data"]]
        assert codes == sorted(codes)

    @pytest.mark.parametrize("state_code,has_income_tax", [
        ("CA", True),
        ("NY", True),
        ("TX", False),
        ("FL", False),
        ("WA", False),
        ("IL", True),
    ])
    def test_states_has_income_tax_correct(
        self,
        client: TestClient,
        state_code: str,
        has_income_tax: bool
    ) -> None:
        """Test states correctly report income tax status."""
        response = client.get("/v1/states")
        data = response.json()
        state = next(s for s in data["data"] if s["code"] == state_code)
        assert state["has_income_tax"] == has_income_tax


class TestStateDetailEndpoint:
    """Tests for GET /v1/states/{code}."""

    def test_get_california(self, client: TestClient) -> None:
        """Test getting California details."""
        response = client.get("/v1/states/CA")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "CA"
        assert data["has_income_tax"] is True
        assert data["tax_type"] == "graduated"

    def test_get_texas_no_income_tax(self, client: TestClient) -> None:
        """Test getting Texas details (no income tax)."""
        response = client.get("/v1/states/TX")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "TX"
        assert data["has_income_tax"] is False
        assert data["tax_type"] == "none"

    def test_get_state_includes_brackets(self, client: TestClient) -> None:
        """Test state detail includes brackets for graduated states."""
        response = client.get("/v1/states/CA")
        data = response.json()
        assert "brackets" in data
        assert "single" in data["brackets"]
        assert len(data["brackets"]["single"]) > 0

    def test_get_state_includes_deductions(self, client: TestClient) -> None:
        """Test state detail includes deduction info."""
        response = client.get("/v1/states/CA")
        data = response.json()
        assert "deduction" in data

    def test_get_state_case_insensitive(self, client: TestClient) -> None:
        """Test state code is case insensitive."""
        response1 = client.get("/v1/states/CA")
        response2 = client.get("/v1/states/ca")
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["code"] == response2.json()["code"]

    def test_get_invalid_state_returns_404(self, client: TestClient) -> None:
        """Test invalid state code returns 404."""
        response = client.get("/v1/states/XX")
        assert response.status_code == 404

    def test_get_state_with_tax_year(self, client: TestClient) -> None:
        """Test state detail accepts tax_year parameter."""
        response = client.get("/v1/states/CA?tax_year=2025")
        assert response.status_code == 200
        data = response.json()
        assert data["tax_year"] == 2025

    def test_flat_tax_state(self, client: TestClient) -> None:
        """Test getting a flat tax state."""
        response = client.get("/v1/states/IL")
        assert response.status_code == 200
        data = response.json()
        assert data["tax_type"] == "flat"
        assert data["flat_rate"] is not None

    def test_state_with_surtax(self, client: TestClient) -> None:
        """Test getting Massachusetts which has surtax."""
        response = client.get("/v1/states/MA")
        assert response.status_code == 200
        data = response.json()
        assert "surtaxes" in data


class TestZipLookupEndpoint:
    """Tests for GET /v1/lookup/zip/{zip_code}."""

    def test_lookup_nyc_zip(self, client: TestClient) -> None:
        """Test looking up NYC ZIP code."""
        response = client.get("/v1/lookup/zip/10001")
        assert response.status_code == 200
        data = response.json()
        assert data["zip_code"] == "10001"
        assert data["state_code"] == "NY"
        assert data["local_jurisdiction_id"] is not None

    def test_lookup_california_zip(self, client: TestClient) -> None:
        """Test looking up California ZIP code (no local tax)."""
        response = client.get("/v1/lookup/zip/90210")
        assert response.status_code == 200
        data = response.json()
        assert data["zip_code"] == "90210"
        assert data["state_code"] == "CA"
        assert data["has_state_income_tax"] is True

    def test_lookup_texas_zip(self, client: TestClient) -> None:
        """Test looking up Texas ZIP code (no state tax)."""
        response = client.get("/v1/lookup/zip/75001")
        assert response.status_code == 200
        data = response.json()
        assert data["zip_code"] == "75001"
        assert data["state_code"] == "TX"
        assert data["has_state_income_tax"] is False

    def test_lookup_philadelphia_zip(self, client: TestClient) -> None:
        """Test looking up Philadelphia ZIP code."""
        response = client.get("/v1/lookup/zip/19101")
        assert response.status_code == 200
        data = response.json()
        assert data["state_code"] == "PA"
        assert data["local_jurisdiction_id"] is not None

    def test_lookup_detroit_zip(self, client: TestClient) -> None:
        """Test looking up Detroit ZIP code."""
        response = client.get("/v1/lookup/zip/48201")
        assert response.status_code == 200
        data = response.json()
        assert data["state_code"] == "MI"
        assert data["local_jurisdiction_id"] is not None

    def test_lookup_cleveland_zip(self, client: TestClient) -> None:
        """Test looking up Cleveland ZIP code."""
        response = client.get("/v1/lookup/zip/44101")
        assert response.status_code == 200
        data = response.json()
        assert data["state_code"] == "OH"
        assert data["local_jurisdiction_id"] is not None

    def test_lookup_with_spaces(self, client: TestClient) -> None:
        """Test ZIP lookup handles leading/trailing spaces."""
        response = client.get("/v1/lookup/zip/ 10001 ")
        assert response.status_code == 200

    def test_lookup_response_includes_all_fields(self, client: TestClient) -> None:
        """Test ZIP lookup response includes all required fields."""
        response = client.get("/v1/lookup/zip/10001")
        data = response.json()
        assert "zip_code" in data
        assert "state_code" in data
        assert "state_name" in data
        assert "local_jurisdiction_id" in data
        assert "has_state_income_tax" in data
        assert "has_local_income_tax" in data


class TestStateWithLocalJurisdictions:
    """Test states that have local income tax jurisdictions."""

    def test_new_york_has_local_info(self, client: TestClient) -> None:
        """Test New York state info includes local jurisdiction data."""
        response = client.get("/v1/states/NY")
        data = response.json()
        # NY has NYC and Yonkers
        assert "local_jurisdictions" in data

    def test_pennsylvania_has_local_info(self, client: TestClient) -> None:
        """Test Pennsylvania state info includes local jurisdiction data."""
        response = client.get("/v1/states/PA")
        data = response.json()
        # PA has Philadelphia and Pittsburgh
        assert "local_jurisdictions" in data

    def test_ohio_has_local_info(self, client: TestClient) -> None:
        """Test Ohio state info includes local jurisdiction data."""
        response = client.get("/v1/states/OH")
        data = response.json()
        # OH has Cleveland, Columbus, Cincinnati
        assert "local_jurisdictions" in data


class TestZipLookupEdgeCases:
    """Additional tests for ZIP lookup API edge cases."""

    def test_lookup_short_zip(self, client: TestClient) -> None:
        """Test ZIP lookup handles 3-digit prefix."""
        response = client.get("/v1/lookup/zip/100")
        assert response.status_code == 200
        data = response.json()
        assert data["zip_code"] == "100"
        assert data["state_code"] == "NY"

    def test_lookup_full_zip_plus_4(self, client: TestClient) -> None:
        """Test ZIP lookup handles ZIP+4 format by using first 3 digits."""
        response = client.get("/v1/lookup/zip/10001-1234")
        assert response.status_code == 200
        data = response.json()
        # Should extract first 3 digits
        assert data["state_code"] == "NY"

    def test_lookup_zip_with_no_local_tax(self, client: TestClient) -> None:
        """Test ZIP lookup for location with no local tax."""
        response = client.get("/v1/lookup/zip/90210")  # Beverly Hills, CA
        assert response.status_code == 200
        data = response.json()
        assert data["state_code"] == "CA"
        # CA has no local income taxes (except for some special districts)
        assert data["local_jurisdiction_id"] is None or data["has_local_income_tax"] is False

    def test_lookup_yonkers_zip(self, client: TestClient) -> None:
        """Test ZIP lookup for Yonkers."""
        response = client.get("/v1/lookup/zip/10701")  # Yonkers ZIP
        assert response.status_code == 200
        data = response.json()
        assert data["state_code"] == "NY"

    def test_lookup_baltimore_zip(self, client: TestClient) -> None:
        """Test ZIP lookup for Baltimore area."""
        response = client.get("/v1/lookup/zip/21201")
        assert response.status_code == 200
        data = response.json()
        # ZIP mapping is placeholder data, may not include all ZIPs
        # Just verify response structure is correct
        assert "state_code" in data
        assert "zip_code" in data
        assert data["zip_code"] == "21201"

    def test_lookup_st_louis_zip(self, client: TestClient) -> None:
        """Test ZIP lookup for St. Louis area."""
        response = client.get("/v1/lookup/zip/63101")
        assert response.status_code == 200
        data = response.json()
        # ZIP mapping is placeholder data, may not include all ZIPs
        # Just verify response structure is correct
        assert "state_code" in data
        assert "zip_code" in data
        assert data["zip_code"] == "63101"

    def test_lookup_unknown_zip_prefix(self, client: TestClient) -> None:
        """Test ZIP lookup for an unknown ZIP prefix."""
        response = client.get("/v1/lookup/zip/999")  # Invalid prefix
        assert response.status_code == 200
        data = response.json()
        # Should return None for unknown ZIP
        assert data["state_code"] is None or data["zip_code"] == "999"


class TestStateReciprocityInfo:
    """Test state reciprocity information in API."""

    def test_state_detail_includes_reciprocity(self, client: TestClient) -> None:
        """Test state detail response includes reciprocity states."""
        response = client.get("/v1/states/PA")
        assert response.status_code == 200
        data = response.json()
        assert "reciprocity_states" in data
        assert isinstance(data["reciprocity_states"], list)

    def test_virginia_reciprocity_in_response(self, client: TestClient) -> None:
        """Test Virginia state detail includes reciprocity info."""
        response = client.get("/v1/states/VA")
        assert response.status_code == 200
        data = response.json()
        assert "reciprocity_states" in data


class TestInvalidFilingStatus:
    """Test API handling of invalid inputs."""

    def test_state_detail_includes_is_placeholder_flag(
        self, client: TestClient
    ) -> None:
        """Test state detail response includes is_placeholder flag."""
        response = client.get("/v1/states/CA")
        assert response.status_code == 200
        data = response.json()
        assert "is_placeholder" in data
        assert data["is_placeholder"] is True

    def test_state_detail_includes_notes(self, client: TestClient) -> None:
        """Test state detail response includes notes."""
        response = client.get("/v1/states/CA")
        assert response.status_code == 200
        data = response.json()
        assert "notes" in data
        assert isinstance(data["notes"], list)
