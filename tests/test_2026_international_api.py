"""2026 international release: registry, estimate API and mixed US/country Compare.

Country tax values are pinned by tests/calculation/countries/test_<cc>_2026_reference.py;
these tests check the public wiring: which countries are released, the native
period each 2026 result covers, and the Compare rules for mixing US places and
countries.
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from tax_estimator.calculation.countries.router import (
    PENDING_TAX_YEARS,
    SUPPORTED_TAX_YEARS,
    CountryRouter,
)
from tax_estimator.main import app

client = TestClient(app)

RELEASED_2026 = {"AE", "AU", "CA", "DE", "ES", "FR", "GB", "HK", "IT", "JP", "PT", "SG"}
PERIOD_FRAGMENTS = {
    "GB": "2026/27", "HK": "2026/27", "AU": "2026-27", "SG": "YA2027",
    "DE": "2026", "FR": "2026", "IT": "2026", "ES": "2026",
    "CA": "2026", "JP": "2026", "PT": "2026", "AE": "2026",
}
LOCAL_SALARY = {
    "GB": 60000, "DE": 60000, "FR": 60000, "IT": 60000, "ES": 60000, "PT": 60000,
    "CA": 90000, "AU": 100000, "SG": 100000, "HK": 600000, "AE": 300000, "JP": 8000000,
}


def test_released_set_is_pinned_and_disjoint_from_pending():
    assert set(CountryRouter.countries_for_tax_year(2026)) == RELEASED_2026
    assert all(2025 in years for years in SUPPORTED_TAX_YEARS.values())
    assert not {code for code, year in PENDING_TAX_YEARS if year == 2026} & RELEASED_2026


@pytest.mark.parametrize("country", sorted(RELEASED_2026))
def test_estimate_2026_returns_native_period(country):
    response = client.post("/v1/international/estimate", json={
        "country_code": country, "tax_year": 2026, "gross_income": LOCAL_SALARY[country],
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["tax_year"] == 2026
    assert Decimal(data["total_tax"]) >= 0
    listing = client.get("/v1/international/countries", params={"tax_year": 2026}).json()
    labels = {c["country_code"]: c["period_label"] for c in listing["countries"]}
    assert PERIOD_FRAGMENTS[country] in labels[country]


def test_unreleased_year_is_rejected():
    response = client.post("/v1/international/estimate", json={
        "country_code": "GB", "tax_year": 2027, "gross_income": 50000,
    })
    assert response.status_code == 422


def test_2026_refuses_family_profiles():
    response = client.post("/v1/international/estimate", json={
        "country_code": "HK", "tax_year": 2026, "gross_income": 600000,
        "hk": {"is_married": True},
    })
    assert response.status_code == 422
    assert "single" in response.json()["detail"]


def test_compare_regions_2026_lists_released_countries():
    data = client.get("/v1/comparison/regions", params={"tax_year": 2026}).json()
    countries = {c["region_id"]: c for c in data["international"]}
    assert set(countries) == RELEASED_2026
    assert "2026/27" in countries["GB"]["period_label"]


def _compare(regions, currency="USD", **extra):
    return client.post("/v1/comparison/compare", json={
        "regions": regions, "tax_year": 2026, "base_currency": currency,
        "income": {"employment_wages": 100000}, **extra,
    })


def test_compare_2026_mixes_us_state_and_countries():
    response = _compare(["US-TX", "GB", "AE"])
    assert response.status_code == 200, response.text
    data = response.json()
    by_id = {r["region_id"]: r for r in data["regions"]}
    assert set(by_id) == {"US-TX", "GB", "AE"}
    assert "2026/27" in by_id["GB"]["period_label"]
    assert by_id["US-TX"]["period_label"] is None
    assert Decimal(by_id["AE"]["total_tax_base"]) == 0
    text = " ".join(data["disclaimers"])
    assert "IRS 2025 annual-average" in text and "Australia 2026-27" in text
    assert data["exchange_rates"]["base_currency"] == "USD"
    assert Decimal(data["exchange_rates"]["rates"]["GBP"]) != 1


def test_compare_2026_countries_only_may_use_other_base_currency():
    response = _compare(["GB", "DE"], currency="EUR")
    assert response.status_code == 200, response.text


def test_compare_2026_us_places_require_usd():
    response = _compare(["US-TX", "GB"], currency="GBP")
    assert response.status_code == 422
    assert "USD" in response.json()["detail"]


def test_compare_2026_skips_country_with_family_profile():
    response = _compare(["US-TX", "HK"], country_profiles={"HK": {"is_married": True}})
    assert response.status_code == 200, response.text
    skipped = response.json()["skipped_regions"]
    assert [s["region_id"] for s in skipped] == ["HK"]
    assert "single" in skipped[0]["reason"]


@pytest.mark.parametrize("country,profile", [
    ("FR", {"fr": {"is_married": True}}),
    ("JP", {"jp": {"has_spouse": True}}),
    ("DE", {"de": {"tax_class": "III"}}),
])
def test_estimate_2026_refuses_family_profiles_beyond_hk(country, profile):
    response = client.post("/v1/international/estimate", json={
        "country_code": country, "tax_year": 2026, "gross_income": LOCAL_SALARY[country],
        **profile,
    })
    assert response.status_code == 422, response.text


def test_compare_2026_flags_provisional_country():
    data = _compare(["FR", "DE"]).json()
    flags = {r["region_id"]: r["provisional"] for r in data["regions"]}
    assert flags == {"FR": True, "DE": False}
    assert any("(provisional)" in note for r in data["regions"] if r["region_id"] == "FR"
               for note in r["notes"])


def test_2026_refuses_rental_income_for_countries():
    response = client.post("/v1/comparison/compare", json={
        "regions": ["GB", "DE"], "tax_year": 2026, "base_currency": "USD",
        "income": {"employment_wages": 50000, "rental": 20000},
    })
    # Every country is skipped, which Compare reports as a 400.
    assert response.status_code == 400
    assert "rental" in response.json()["detail"]
    estimate = client.post("/v1/international/estimate", json={
        "country_code": "GB", "tax_year": 2026, "gross_income": 70000,
        "income": {"employment_wages": 50000, "rental": 20000},
    })
    assert estimate.status_code == 422


def test_compare_2026_countries_accept_interest():
    response = client.post("/v1/comparison/compare", json={
        "regions": ["GB", "SG"], "tax_year": 2026, "base_currency": "USD",
        "income": {"employment_wages": 80000, "interest": 3000},
    })
    assert response.status_code == 200, response.text
