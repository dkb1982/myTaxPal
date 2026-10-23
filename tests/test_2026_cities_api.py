"""End-to-end 2026 resident city estimates through the public API.

Expected local tax at $100,000 wages is the hand-computed reference from
tests/calculation/locals/test_2026_locals_reference.py. Here the real 2026
federal and state pipeline supplies the state values the city consumes
(NY taxable income and tax for NYC/Yonkers, MD and IN taxable income), so
this also checks the state-to-city wiring.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from tax_estimator.calculation.coverage import enabled_us_cities
from tax_estimator.main import app

client = TestClient(app)

LOCAL_TAX_AT_100K = {
    "US-NY-NYC": Decimal("3174.52"),
    "US-NY-YNK": Decimal("814.16"),
    "US-PA-PHL": Decimal("3737.50"),
    "US-MI-DET": Decimal("2385.60"),
    "US-OH-CLE": Decimal("2500"),
    "US-OH-CIN": Decimal("1800"),
    "US-OH-CMH": Decimal("2500"),
    "US-MD-BAL": Decimal("2988.80"),
    "US-IN-IND": Decimal("1999.80"),
    "US-AL-BHM": Decimal("1000"),
    "US-KY-LOU": Decimal("2200"),
}
ENABLED = sorted(enabled_us_cities(2026))


def _estimate(city: str, wages: int) -> dict:
    state = city.split("-")[1]
    body = {
        "tax_year": 2026,
        "filer": {"filing_status": "single", "age_at_year_end": 40},
        "residency": {"residence_state": state, "local_jurisdiction_id": city},
        "income": {"wages": [{
            "employer_name": "Employer", "employer_state": state, "gross_wages": wages,
            "federal_withholding": 0, "state_withholding": 0, "local_withholding": 0,
        }]},
    }
    if city == "US-PA-PHL":
        body["us_scenario"] = {"philly_first_half_wages": wages / 2}
    response = client.post("/v1/estimates", json=body)
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_cities_are_enabled_for_2026():
    assert ENABLED


@pytest.mark.parametrize("city", ENABLED)
def test_2026_city_local_tax_matches_reference_at_100k(city):
    data = _estimate(city, 100000)
    assert Decimal(str(data["summary"]["total_local_tax"])) == LOCAL_TAX_AT_100K[city]


@pytest.mark.skipif("US-PA-PHL" not in ENABLED, reason="Philadelphia not enabled")
def test_2026_compare_accepts_philadelphia_scenario_facts():
    response = client.post("/v1/comparison/compare", json={
        "tax_year": 2026, "base_currency": "USD", "filing_status": "single",
        "regions": ["US-PA-PHL", "US-NY-NYC"],
        "income": {"employment_wages": "100000"},
        "us_scenario": {"philly_first_half_wages": "50000"},
    })
    assert response.status_code == 200, response.text
    local = {r["region_id"]: Decimal(r["us_breakdown"]["local_tax"]) for r in response.json()["regions"]}
    assert local == {"US-PA-PHL": LOCAL_TAX_AT_100K["US-PA-PHL"], "US-NY-NYC": LOCAL_TAX_AT_100K["US-NY-NYC"]}


def test_2026_compare_missing_philadelphia_facts_is_a_422():
    response = client.post("/v1/comparison/compare", json={
        "tax_year": 2026, "base_currency": "USD", "filing_status": "single",
        "regions": ["US-PA-PHL"], "income": {"employment_wages": "100000"},
    })
    assert response.status_code == 422, response.text
    assert "us_scenario.philly_first_half_wages" in response.json()["detail"]
    assert "Pipeline" not in response.text
