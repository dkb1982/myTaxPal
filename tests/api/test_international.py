"""
API tests for international tax endpoints.

Tests cover:
- POST /v1/international/estimate
- POST /v1/international/compare
- GET /v1/international/countries
- GET /v1/international/countries/{code}
- GET /v1/international/currencies
"""

import pytest
from fastapi.testclient import TestClient

from tax_estimator.main import app


client = TestClient(app)


# =============================================================================
# Test POST /v1/international/estimate
# =============================================================================


class TestInternationalEstimate:
    """Tests for international estimate endpoint."""

    def test_estimate_uk(self):
        """Test UK tax estimate."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "GB",
                "tax_year": 2025,
                "gross_income": 50000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "GB"
        assert data["currency_code"] == "GBP"
        # total_tax is returned as string from API
        assert float(data["total_tax"]) > 0

    def test_estimate_germany(self):
        """Test Germany tax estimate."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "DE",
                "tax_year": 2025,
                "gross_income": 60000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "DE"
        assert data["currency_code"] == "EUR"

    def test_estimate_france(self):
        """Test France tax estimate."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "FR",
                "tax_year": 2025,
                "gross_income": 50000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "FR"

    def test_estimate_singapore(self):
        """Test Singapore tax estimate."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "SG",
                "tax_year": 2025,
                "gross_income": 80000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "SG"
        assert data["currency_code"] == "SGD"

    def test_estimate_hong_kong(self):
        """Test Hong Kong tax estimate."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "HK",
                "tax_year": 2025,
                "gross_income": 500000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "HK"
        assert data["currency_code"] == "HKD"

    def test_estimate_uae_zero_tax(self):
        """Test UAE returns zero tax."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "AE",
                "tax_year": 2025,
                "gross_income": 100000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "AE"
        # API returns strings for numbers
        assert float(data["total_tax"]) == 0
        assert float(data["effective_rate"]) == 0

    def test_estimate_japan(self):
        """Test Japan tax estimate."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "JP",
                "tax_year": 2025,
                "gross_income": 5000000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "JP"
        assert data["currency_code"] == "JPY"

    def test_estimate_australia(self):
        """Test Australia tax estimate."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "AU",
                "tax_year": 2025,
                "gross_income": 80000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "AU"
        assert data["currency_code"] == "AUD"

    def test_estimate_canada(self):
        """Test Canada tax estimate."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "CA",
                "tax_year": 2025,
                "gross_income": 80000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "CA"
        assert data["currency_code"] == "CAD"

    def test_estimate_italy(self):
        """Test Italy tax estimate."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "IT",
                "tax_year": 2025,
                "gross_income": 50000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "IT"

    def test_estimate_spain(self):
        """Test Spain tax estimate."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "ES",
                "tax_year": 2025,
                "gross_income": 50000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "ES"

    def test_estimate_portugal(self):
        """Test Portugal tax estimate."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "PT",
                "tax_year": 2025,
                "gross_income": 50000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "PT"

    def test_estimate_lowercase_country_code(self):
        """Test lowercase country code is accepted."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "gb",
                "tax_year": 2025,
                "gross_income": 50000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "GB"

    def test_estimate_unsupported_country(self):
        """Test unsupported country returns error."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "XX",
                "tax_year": 2025,
                "gross_income": 50000,
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "not supported" in data["detail"].lower()

    def test_estimate_missing_country_code(self):
        """Test missing country code returns error."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "tax_year": 2025,
                "gross_income": 50000,
            },
        )
        assert response.status_code == 422

    def test_estimate_missing_income(self):
        """Test missing income returns error."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "GB",
                "tax_year": 2025,
            },
        )
        assert response.status_code == 422

    def test_estimate_negative_income(self):
        """Test negative income returns error."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "GB",
                "tax_year": 2025,
                "gross_income": -50000,
            },
        )
        assert response.status_code == 422

    def test_estimate_response_has_breakdown(self):
        """Test response includes tax breakdown."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "GB",
                "tax_year": 2025,
                "gross_income": 50000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "breakdown" in data
        assert len(data["breakdown"]) > 0

    def test_estimate_response_has_disclaimers(self):
        """Test response includes disclaimers."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "GB",
                "tax_year": 2025,
                "gross_income": 50000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "disclaimers" in data
        assert len(data["disclaimers"]) > 0


# =============================================================================
# Test POST /v1/international/compare
# =============================================================================


class TestInternationalCompare:
    """Tests for international comparison endpoint."""

    def test_compare_two_countries(self):
        """Test comparing two countries."""
        response = client.post(
            "/v1/international/compare",
            json={
                "base_currency": "USD",
                "gross_income": 100000,
                "regions": ["GB", "DE"],
                "tax_year": 2025,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["base_currency"] == "USD"
        # Response uses 'countries' not 'results'
        assert len(data["countries"]) == 2

    def test_compare_multiple_countries(self):
        """Test comparing multiple countries."""
        response = client.post(
            "/v1/international/compare",
            json={
                "base_currency": "USD",
                "gross_income": 100000,
                "regions": ["GB", "DE", "FR", "SG", "AE"],
                "tax_year": 2025,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["countries"]) == 5

    def test_compare_with_gbp_base(self):
        """Test comparison with GBP as base currency."""
        response = client.post(
            "/v1/international/compare",
            json={
                "base_currency": "GBP",
                "gross_income": 50000,
                "regions": ["GB", "DE"],
                "tax_year": 2025,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["base_currency"] == "GBP"

    def test_compare_with_eur_base(self):
        """Test comparison with EUR as base currency."""
        response = client.post(
            "/v1/international/compare",
            json={
                "base_currency": "EUR",
                "gross_income": 50000,
                "regions": ["DE", "FR", "IT"],
                "tax_year": 2025,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["base_currency"] == "EUR"

    def test_compare_uae_lowest_tax(self):
        """Test UAE shows as lowest tax in comparison."""
        response = client.post(
            "/v1/international/compare",
            json={
                "base_currency": "USD",
                "gross_income": 100000,
                "regions": ["GB", "AE"],
                "tax_year": 2025,
            },
        )
        assert response.status_code == 200
        data = response.json()

        uae_result = next(r for r in data["countries"] if r["country_code"] == "AE")
        gb_result = next(r for r in data["countries"] if r["country_code"] == "GB")

        # total_tax_base is string so convert
        assert float(uae_result["total_tax_base"]) < float(gb_result["total_tax_base"])

    def test_compare_has_exchange_rates(self):
        """Test comparison includes exchange rates."""
        response = client.post(
            "/v1/international/compare",
            json={
                "base_currency": "USD",
                "gross_income": 100000,
                "regions": ["GB", "DE"],
                "tax_year": 2025,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "exchange_rates" in data

    def test_compare_has_disclaimers(self):
        """Test comparison includes disclaimers."""
        response = client.post(
            "/v1/international/compare",
            json={
                "base_currency": "USD",
                "gross_income": 100000,
                "regions": ["GB", "DE"],
                "tax_year": 2025,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "disclaimers" in data
        assert len(data["disclaimers"]) > 0

    def test_compare_empty_regions(self):
        """Test empty regions returns error."""
        response = client.post(
            "/v1/international/compare",
            json={
                "base_currency": "USD",
                "gross_income": 100000,
                "regions": [],
                "tax_year": 2025,
            },
        )
        assert response.status_code == 422

    def test_compare_unsupported_region(self):
        """Test unsupported region returns error."""
        response = client.post(
            "/v1/international/compare",
            json={
                "base_currency": "USD",
                "gross_income": 100000,
                "regions": ["GB", "XX"],
                "tax_year": 2025,
            },
        )
        assert response.status_code == 400

    def test_compare_unsupported_currency(self):
        """Test unsupported currency returns error."""
        response = client.post(
            "/v1/international/compare",
            json={
                "base_currency": "XYZ",
                "gross_income": 100000,
                "regions": ["GB", "DE"],
                "tax_year": 2025,
            },
        )
        assert response.status_code == 400


# =============================================================================
# Test GET /v1/international/countries
# =============================================================================


class TestListCountries:
    """Tests for list countries endpoint."""

    def test_list_countries(self):
        """Test listing all countries."""
        response = client.get("/v1/international/countries")
        assert response.status_code == 200
        data = response.json()
        assert "countries" in data
        assert "total" in data
        assert data["total"] >= 12

    def test_list_countries_has_required_fields(self):
        """Test country objects have required fields."""
        response = client.get("/v1/international/countries")
        assert response.status_code == 200
        data = response.json()

        for country in data["countries"]:
            assert "country_code" in country
            assert "country_name" in country
            assert "currency_code" in country
            assert "has_income_tax" in country

    def test_list_countries_sorted(self):
        """Test countries are sorted by code."""
        response = client.get("/v1/international/countries")
        assert response.status_code == 200
        data = response.json()

        codes = [c["country_code"] for c in data["countries"]]
        assert codes == sorted(codes)


# =============================================================================
# Test GET /v1/international/countries/{code}
# =============================================================================


class TestGetCountry:
    """Tests for get country details endpoint."""

    def test_get_uk_details(self):
        """Test getting UK details."""
        response = client.get("/v1/international/countries/GB")
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "GB"
        assert data["country_name"] == "United Kingdom"
        assert data["currency_code"] == "GBP"

    def test_get_germany_details(self):
        """Test getting Germany details."""
        response = client.get("/v1/international/countries/DE")
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "DE"
        assert data["currency_code"] == "EUR"

    def test_get_uae_no_income_tax(self):
        """Test UAE shows no income tax."""
        response = client.get("/v1/international/countries/AE")
        assert response.status_code == 200
        data = response.json()
        assert data["has_income_tax"] is False

    def test_get_country_has_notes(self):
        """Test country details include notes."""
        response = client.get("/v1/international/countries/GB")
        assert response.status_code == 200
        data = response.json()
        assert "notes" in data
        assert len(data["notes"]) > 0

    def test_get_country_has_disclaimers(self):
        """Test country details include disclaimers."""
        response = client.get("/v1/international/countries/GB")
        assert response.status_code == 200
        data = response.json()
        assert "disclaimers" in data
        assert len(data["disclaimers"]) > 0

    def test_get_country_lowercase(self):
        """Test lowercase country code."""
        response = client.get("/v1/international/countries/gb")
        assert response.status_code == 200
        data = response.json()
        assert data["country_code"] == "GB"

    def test_get_country_not_found(self):
        """Test unsupported country returns 404."""
        response = client.get("/v1/international/countries/XX")
        assert response.status_code == 404


# =============================================================================
# Test GET /v1/international/currencies
# =============================================================================


class TestListCurrencies:
    """Tests for list currencies endpoint."""

    def test_list_currencies(self):
        """Test listing currencies."""
        response = client.get("/v1/international/currencies")
        assert response.status_code == 200
        data = response.json()
        assert "currencies" in data
        assert "total" in data

    def test_list_currencies_has_expected(self):
        """Test expected currencies are present."""
        response = client.get("/v1/international/currencies")
        assert response.status_code == 200
        data = response.json()

        currency_codes = list(data["currencies"].keys())
        assert "GBP" in currency_codes
        assert "EUR" in currency_codes

    def test_currencies_have_countries(self):
        """Test each currency lists countries."""
        response = client.get("/v1/international/currencies")
        assert response.status_code == 200
        data = response.json()

        for currency, info in data["currencies"].items():
            assert "countries" in info
            assert len(info["countries"]) > 0


# =============================================================================
# Request Headers Tests
# =============================================================================


class TestRequestHeaders:
    """Tests for request headers on international endpoints."""

    def test_estimate_returns_request_id(self):
        """Test estimate returns request ID header."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "GB",
                "tax_year": 2025,
                "gross_income": 50000,
            },
        )
        assert response.status_code == 200
        assert "x-request-id" in response.headers

    def test_compare_returns_request_id(self):
        """Test compare returns request ID header."""
        response = client.post(
            "/v1/international/compare",
            json={
                "base_currency": "USD",
                "gross_income": 100000,
                "regions": ["GB", "DE"],
                "tax_year": 2025,
            },
        )
        assert response.status_code == 200
        assert "x-request-id" in response.headers

    def test_countries_returns_request_id(self):
        """Test countries list returns request ID header."""
        response = client.get("/v1/international/countries")
        assert response.status_code == 200
        assert "x-request-id" in response.headers


# =============================================================================
# Test income breakdown on international estimate
# =============================================================================


class TestInternationalIncomeBreakdown:
    """Tests for income type breakdown on international estimate endpoint."""

    def test_singapore_ltcg_exempt(self):
        """Singapore should not tax capital gains."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "SG",
                "tax_year": 2025,
                "gross_income": 100000,
                "income": {
                    "capital_gains_long_term": 100000,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data["total_tax"]) == 0
        assert float(data["effective_rate"]) == 0
        assert float(data["net_income"]) == 100000
        assert any("capital gains" in n.lower() for n in data["calculation_notes"])

    def test_singapore_wages_still_taxed(self):
        """Singapore should still tax employment wages."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "SG",
                "tax_year": 2025,
                "gross_income": 100000,
                "income": {
                    "employment_wages": 100000,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data["total_tax"]) > 0

    def test_singapore_mixed_income_partial_exemption(self):
        """Singapore should tax wages but not LTCG."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "SG",
                "tax_year": 2025,
                "gross_income": 200000,
                "income": {
                    "employment_wages": 100000,
                    "capital_gains_long_term": 100000,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Should tax only the wages portion
        assert float(data["total_tax"]) > 0
        assert float(data["gross_income"]) == 200000
        # Effective rate on full gross should be roughly half of wages-only rate
        # since LTCG half is exempt
        wages_only = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "SG",
                "tax_year": 2025,
                "gross_income": 100000,
                "income": {"employment_wages": 100000},
            },
        )
        wages_rate = float(wages_only.json()["effective_rate"])
        mixed_rate = float(data["effective_rate"])
        assert mixed_rate < wages_rate

    def test_hong_kong_ltcg_and_dividends_exempt(self):
        """Hong Kong should not tax capital gains or dividends."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "HK",
                "tax_year": 2025,
                "gross_income": 100000,
                "income": {
                    "capital_gains_long_term": 50000,
                    "dividends_qualified": 50000,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data["total_tax"]) == 0
        assert float(data["effective_rate"]) == 0

    def test_uae_all_income_exempt(self):
        """UAE should not tax any personal income."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "AE",
                "tax_year": 2025,
                "gross_income": 100000,
                "income": {
                    "employment_wages": 50000,
                    "capital_gains_long_term": 50000,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data["total_tax"]) == 0

    def test_uk_income_breakdown_still_taxed(self):
        """UK with income breakdown should still compute tax (control test)."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "GB",
                "tax_year": 2025,
                "gross_income": 100000,
                "income": {
                    "employment_wages": 100000,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        # UK taxes employment income
        assert float(data["total_tax"]) > 0

    def test_backward_compatible_without_income(self):
        """Endpoint should work without income breakdown (backward compatible)."""
        response = client.post(
            "/v1/international/estimate",
            json={
                "country_code": "SG",
                "tax_year": 2025,
                "gross_income": 80000,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Without breakdown, all income treated as gross — taxes apply
        assert float(data["total_tax"]) > 0
