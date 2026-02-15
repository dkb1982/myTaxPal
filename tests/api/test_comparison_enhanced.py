"""
API tests for enhanced comparison endpoints.

Tests the /comparison endpoints for:
- Multi-region comparison (US states + cities + international)
- Income type breakdown
- Region listings
- Input validation

All tests use PLACEHOLDER rates for development.
"""

from decimal import Decimal
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tax_estimator.api.routes.comparison import router


# =============================================================================
# Test Client Setup
# =============================================================================


@pytest.fixture
def app():
    """Create test FastAPI app with comparison router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# =============================================================================
# POST /comparison/compare Tests
# =============================================================================


class TestCompareEndpoint:
    """Tests for POST /comparison/compare endpoint."""

    def test_compare_us_states_simple_income(self, client):
        """Test comparing US states with simple gross income."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA", "US-TX", "US-FL"],
                "gross_income": 150000,
                "base_currency": "USD",
                "filing_status": "single",
                "tax_year": 2025,
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["base_currency"] == "USD"
        assert data["tax_year"] == 2025
        assert len(data["regions"]) == 3

        # Check each region has required fields
        for region in data["regions"]:
            assert "region_id" in region
            assert "region_name" in region
            assert "region_type" in region
            assert "total_tax_local" in region
            assert "net_income_local" in region
            assert "effective_rate" in region

    def test_compare_us_states_detailed_income(self, client):
        """Test comparing US states with detailed income breakdown."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA", "US-TX"],
                "income": {
                    "employment_wages": 100000,
                    "capital_gains_long_term": 50000,
                    "dividends_qualified": 10000,
                },
                "base_currency": "USD",
                "filing_status": "single",
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Note: Decimal values are serialized as strings in JSON
        assert float(data["total_gross_income"]) == 160000

        # Check income breakdown returned
        assert data["income_breakdown"] is not None
        assert float(data["income_breakdown"]["employment_wages"]) == 100000
        assert float(data["income_breakdown"]["capital_gains_long_term"]) == 50000

    def test_compare_international_countries(self, client):
        """Test comparing international countries."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["GB", "SG", "AE"],
                "gross_income": 150000,
                "base_currency": "USD",
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["regions"]) == 3

        # All should be international type
        for region in data["regions"]:
            assert region["region_type"] == "international"

    def test_compare_mixed_us_and_international(self, client):
        """Test comparing mixed US states and international."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA", "US-TX", "SG", "AE"],
                "gross_income": 150000,
                "base_currency": "USD",
                "filing_status": "single",
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["regions"]) == 4

        # Check we have both types
        types = [r["region_type"] for r in data["regions"]]
        assert "us_state" in types
        assert "international" in types

    def test_compare_us_cities(self, client):
        """Test comparing US cities with local taxes."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-NY-NYC", "US-PA-PHL"],
                "gross_income": 150000,
                "base_currency": "USD",
                "filing_status": "single",
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["regions"]) == 2
        for region in data["regions"]:
            assert region["region_type"] == "us_city"

    def test_lowest_tax_region_identified(self, client):
        """Test that lowest tax region is identified."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA", "US-TX", "AE"],  # AE has no income tax
                "gross_income": 150000,
                "base_currency": "USD",
                "filing_status": "single",
            },
        )
        assert response.status_code == 200
        data = response.json()

        # UAE should have lowest tax (zero)
        assert data["lowest_tax_region"] == "AE"
        assert data["highest_net_income_region"] == "AE"

    def test_disclaimers_included(self, client):
        """Test that disclaimers are included in response."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA"],
                "gross_income": 150000,
                "base_currency": "USD",
                "filing_status": "single",
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "disclaimers" in data
        assert len(data["disclaimers"]) > 0

    def test_us_breakdown_included_for_us_regions(self, client):
        """Test US breakdown is included for US regions."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA"],
                "gross_income": 150000,
                "base_currency": "USD",
                "filing_status": "single",
            },
        )
        assert response.status_code == 200
        data = response.json()

        ca_result = data["regions"][0]
        assert ca_result["us_breakdown"] is not None
        assert "federal_tax" in ca_result["us_breakdown"]
        assert "state_tax" in ca_result["us_breakdown"]

    def test_international_breakdown_for_international(self, client):
        """Test international breakdown for international regions."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["GB"],
                "gross_income": 150000,
                "base_currency": "USD",
            },
        )
        assert response.status_code == 200
        data = response.json()

        gb_result = data["regions"][0]
        assert gb_result["international_breakdown"] is not None

    def test_income_type_results_with_breakdown(self, client):
        """Test income type results when breakdown provided."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA", "SG"],
                "income": {
                    "employment_wages": 100000,
                    "capital_gains_long_term": 50000,
                },
                "base_currency": "USD",
                "filing_status": "single",
            },
        )
        assert response.status_code == 200
        data = response.json()

        for region in data["regions"]:
            if region["income_type_results"]:
                # Check income type results have required fields
                for itr in region["income_type_results"]:
                    assert "income_type" in itr
                    assert "gross_amount" in itr
                    assert "tax_amount" in itr
                    assert "treatment" in itr


class TestCompareEndpointValidation:
    """Tests for input validation on compare endpoint."""

    def test_invalid_region_returns_400(self, client):
        """Test invalid region returns 400 error."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-ZZ"],  # Invalid state
                "gross_income": 150000,
                "base_currency": "USD",
            },
        )
        assert response.status_code == 400
        assert "Invalid regions" in response.json()["detail"]

    def test_too_many_regions_returns_error(self, client):
        """Test too many regions returns error (400 or 422)."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA", "US-TX", "US-FL", "US-NY", "US-WA", "US-NV", "US-AZ"],  # 7 regions
                "gross_income": 150000,
                "base_currency": "USD",
            },
        )
        # Validation error returns 422 in FastAPI
        assert response.status_code in (400, 422)

    def test_duplicate_regions_returns_400(self, client):
        """Test duplicate regions returns 400 error."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA", "US-CA"],  # Duplicate
                "gross_income": 150000,
                "base_currency": "USD",
            },
        )
        assert response.status_code == 400
        assert "Duplicate" in response.json()["detail"]

    def test_no_income_returns_422(self, client):
        """Test missing income returns validation error."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA"],
                "base_currency": "USD",
            },
        )
        # Should fail because neither gross_income nor income provided
        assert response.status_code in (400, 422)

    def test_negative_income_returns_422(self, client):
        """Test negative income returns validation error."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA"],
                "gross_income": -10000,
                "base_currency": "USD",
            },
        )
        assert response.status_code == 422

    def test_invalid_filing_status_returns_422(self, client):
        """Test invalid filing status returns validation error."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA"],
                "gross_income": 150000,
                "base_currency": "USD",
                "filing_status": "invalid_status",
            },
        )
        assert response.status_code == 422

    def test_empty_regions_returns_422(self, client):
        """Test empty regions list returns validation error."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": [],
                "gross_income": 150000,
                "base_currency": "USD",
            },
        )
        assert response.status_code == 422


# =============================================================================
# GET /comparison/regions Tests
# =============================================================================


class TestRegionsEndpoint:
    """Tests for GET /comparison/regions endpoint."""

    def test_list_all_regions(self, client):
        """Test listing all comparison regions."""
        response = client.get("/comparison/regions")
        assert response.status_code == 200
        data = response.json()

        assert "us_states" in data
        assert "us_cities" in data
        assert "international" in data

    def test_us_states_complete(self, client):
        """Test all 51 US states/territories returned."""
        response = client.get("/comparison/regions")
        assert response.status_code == 200
        data = response.json()

        assert len(data["us_states"]) == 51

    def test_us_state_fields(self, client):
        """Test US state entries have required fields."""
        response = client.get("/comparison/regions")
        assert response.status_code == 200
        data = response.json()

        for state in data["us_states"]:
            assert "region_id" in state
            assert "name" in state
            assert "abbreviation" in state
            assert "has_income_tax" in state

    def test_us_cities_returned(self, client):
        """Test US cities are returned."""
        response = client.get("/comparison/regions")
        assert response.status_code == 200
        data = response.json()

        assert len(data["us_cities"]) > 0

    def test_us_city_fields(self, client):
        """Test US city entries have required fields."""
        response = client.get("/comparison/regions")
        assert response.status_code == 200
        data = response.json()

        for city in data["us_cities"]:
            assert "region_id" in city
            assert "city_name" in city
            assert "state_code" in city

    def test_international_returned(self, client):
        """Test international countries are returned."""
        response = client.get("/comparison/regions")
        assert response.status_code == 200
        data = response.json()

        assert len(data["international"]) >= 12

    def test_international_fields(self, client):
        """Test international entries have required fields."""
        response = client.get("/comparison/regions")
        assert response.status_code == 200
        data = response.json()

        for country in data["international"]:
            assert "region_id" in country
            assert "name" in country
            assert "currency_code" in country
            assert "has_income_tax" in country
            assert "has_capital_gains_tax" in country


# =============================================================================
# GET /comparison/regions/us-states Tests
# =============================================================================


class TestUSStatesEndpoint:
    """Tests for GET /comparison/regions/us-states endpoint."""

    def test_list_us_states(self, client):
        """Test listing US states."""
        response = client.get("/comparison/regions/us-states")
        assert response.status_code == 200
        data = response.json()

        assert "popular" in data
        assert "all" in data
        assert "total" in data
        assert "no_income_tax_states" in data

    def test_no_income_tax_states_listed(self, client):
        """Test no-income-tax states are listed."""
        response = client.get("/comparison/regions/us-states")
        assert response.status_code == 200
        data = response.json()

        no_tax = data["no_income_tax_states"]
        assert "US-TX" in no_tax
        assert "US-FL" in no_tax
        assert "US-WA" in no_tax

    def test_popular_states_separated(self, client):
        """Test popular states are listed separately."""
        response = client.get("/comparison/regions/us-states")
        assert response.status_code == 200
        data = response.json()

        assert len(data["popular"]) > 0


# =============================================================================
# GET /comparison/regions/us-cities Tests
# =============================================================================


class TestUSCitiesEndpoint:
    """Tests for GET /comparison/regions/us-cities endpoint."""

    def test_list_us_cities(self, client):
        """Test listing US cities."""
        response = client.get("/comparison/regions/us-cities")
        assert response.status_code == 200
        data = response.json()

        assert "cities" in data
        assert "total" in data

    def test_major_cities_included(self, client):
        """Test major cities are included."""
        response = client.get("/comparison/regions/us-cities")
        assert response.status_code == 200
        data = response.json()

        city_ids = [c["region_id"] for c in data["cities"]]
        assert "US-NY-NYC" in city_ids


# =============================================================================
# GET /comparison/regions/international Tests
# =============================================================================


class TestInternationalEndpoint:
    """Tests for GET /comparison/regions/international endpoint."""

    def test_list_international(self, client):
        """Test listing international countries."""
        response = client.get("/comparison/regions/international")
        assert response.status_code == 200
        data = response.json()

        assert "no_income_tax" in data
        assert "no_capital_gains_tax" in data
        assert "full_tax" in data
        assert "total" in data

    def test_uae_in_no_income_tax(self, client):
        """Test UAE is in no-income-tax list."""
        response = client.get("/comparison/regions/international")
        assert response.status_code == 200
        data = response.json()

        no_tax_ids = [c["region_id"] for c in data["no_income_tax"]]
        assert "AE" in no_tax_ids

    def test_singapore_in_no_cgt(self, client):
        """Test Singapore is in no-CGT list."""
        response = client.get("/comparison/regions/international")
        assert response.status_code == 200
        data = response.json()

        no_cgt_ids = [c["region_id"] for c in data["no_capital_gains_tax"]]
        assert "SG" in no_cgt_ids


# =============================================================================
# GET /comparison/regions/{region_id} Tests
# =============================================================================


class TestRegionDetailsEndpoint:
    """Tests for GET /comparison/regions/{region_id} endpoint."""

    def test_get_us_state_details(self, client):
        """Test getting US state details."""
        response = client.get("/comparison/regions/US-CA")
        assert response.status_code == 200
        data = response.json()

        assert data["region_id"] == "US-CA"
        assert data["region_type"] == "us_state"
        assert "California" in data["name"]
        assert data["currency"] == "USD"

    def test_get_us_city_details(self, client):
        """Test getting US city details."""
        response = client.get("/comparison/regions/US-NY-NYC")
        assert response.status_code == 200
        data = response.json()

        assert data["region_id"] == "US-NY-NYC"
        assert data["region_type"] == "us_city"
        assert "New York" in data["name"]

    def test_get_international_details(self, client):
        """Test getting international country details."""
        response = client.get("/comparison/regions/GB")
        assert response.status_code == 200
        data = response.json()

        assert data["region_id"] == "GB"
        assert data["region_type"] == "international"
        assert data["name"] == "United Kingdom"
        assert data["currency"] == "GBP"

    def test_get_no_tax_country_details(self, client):
        """Test getting details for no-tax country."""
        response = client.get("/comparison/regions/AE")
        assert response.status_code == 200
        data = response.json()

        assert data["has_income_tax"] is False
        assert "No personal income tax" in str(data["notes"])

    def test_get_invalid_region_returns_404(self, client):
        """Test getting invalid region returns 404."""
        response = client.get("/comparison/regions/INVALID")
        assert response.status_code == 404

    def test_details_include_disclaimers(self, client):
        """Test region details include disclaimers."""
        response = client.get("/comparison/regions/US-CA")
        assert response.status_code == 200
        data = response.json()

        assert "disclaimers" in data
        assert len(data["disclaimers"]) > 0


# =============================================================================
# Currency Handling Tests
# =============================================================================


class TestCurrencyHandling:
    """Tests for currency handling in comparison."""

    def test_usd_base_currency(self, client):
        """Test comparison with USD base currency."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA", "GB"],
                "gross_income": 100000,
                "base_currency": "USD",
                "filing_status": "single",
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["base_currency"] == "USD"

        # US should have same local and base
        us_result = next(r for r in data["regions"] if r["region_id"] == "US-CA")
        assert us_result["currency_code"] == "USD"

        # UK should have different local (GBP) vs base (USD)
        gb_result = next(r for r in data["regions"] if r["region_id"] == "GB")
        assert gb_result["currency_code"] == "GBP"

    def test_exchange_rates_included(self, client):
        """Test exchange rates are included in response."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-CA", "GB"],
                "gross_income": 100000,
                "base_currency": "USD",
                "filing_status": "single",
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "exchange_rates" in data
        assert data["exchange_rates"]["base_currency"] == "USD"


# =============================================================================
# Filing Status Tests
# =============================================================================


class TestFilingStatus:
    """Tests for filing status handling."""

    @pytest.mark.parametrize(
        "status",
        ["single", "mfj", "mfs", "hoh"],
    )
    def test_valid_filing_statuses(self, client, status):
        """Test valid filing statuses are accepted."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-TX"],
                "gross_income": 150000,
                "base_currency": "USD",
                "filing_status": status,
            },
        )
        assert response.status_code == 200

    def test_filing_status_affects_tax(self, client):
        """Test filing status affects calculated tax."""
        # Compare single vs MFJ
        response_single = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-TX"],
                "gross_income": 150000,
                "base_currency": "USD",
                "filing_status": "single",
            },
        )
        response_mfj = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-TX"],
                "gross_income": 150000,
                "base_currency": "USD",
                "filing_status": "mfj",
            },
        )

        assert response_single.status_code == 200
        assert response_mfj.status_code == 200

        single_tax = response_single.json()["regions"][0]["total_tax_local"]
        mfj_tax = response_mfj.json()["regions"][0]["total_tax_local"]

        # MFJ typically has lower tax at same income
        assert mfj_tax < single_tax


# =============================================================================
# No Tax Location Tests
# =============================================================================


class TestNoTaxLocations:
    """Tests for no-tax locations."""

    def test_texas_no_state_tax(self, client):
        """Test Texas has no state tax."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["US-TX"],
                "gross_income": 150000,
                "base_currency": "USD",
                "filing_status": "single",
            },
        )
        assert response.status_code == 200
        data = response.json()

        tx_result = data["regions"][0]
        # Decimal values are serialized as strings
        assert float(tx_result["us_breakdown"]["state_tax"]) == 0
        assert tx_result["us_breakdown"]["has_state_income_tax"] is False

    def test_uae_no_income_tax(self, client):
        """Test UAE has no income tax."""
        response = client.post(
            "/comparison/compare",
            json={
                "regions": ["AE"],
                "gross_income": 500000,
                "base_currency": "USD",
            },
        )
        assert response.status_code == 200
        data = response.json()

        ae_result = data["regions"][0]
        # Decimal values are serialized as strings
        assert float(ae_result["total_tax_local"]) == 0
        assert float(ae_result["effective_rate"]) == 0
