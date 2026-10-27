"""Public 2026 coverage and independent vanilla federal/Texas reference cases."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from tax_estimator.main import app

client = TestClient(app)


def _estimate(state="TX", *, wages="100000", age=40, year=2026):
    return client.post("/v1/estimates", json={
        "tax_year": year,
        "filer": {"filing_status": "single", "age_at_year_end": age},
        "residency": {"residence_state": state},
        "income": {"wages": [{"employer_name": "Example", "employer_state": state,
                              "gross_wages": wages, "social_security_wages": wages,
                              "medicare_wages": wages}]},
    })


def _compare(income, *, regions=None, currency="USD", year=2026):
    return client.post("/v1/comparison/compare", json={
        "tax_year": year,
        "base_currency": currency,
        "regions": regions or ["US-TX"],
        "filing_status": "single",
        "income": income,
    })


def test_2026_discovery_is_limited_to_supported_states():
    from tax_estimator.calculation.comparison_regions import US_STATES
    from tax_estimator.calculation.countries.router import CountryRouter
    from tax_estimator.calculation.coverage import enabled_us_cities, enabled_us_states

    enabled = enabled_us_states(2026)
    cities = enabled_us_cities(2026)
    supported = {f"US-{code}" for code in enabled}
    # Washington taxes only long-term capital gains, so it has no income tax.
    no_tax = {"US-AK", "US-FL", "US-NV", "US-NH", "US-SD", "US-TN", "US-TX", "US-WA", "US-WY"}
    response = client.get("/v1/comparison/regions?tax_year=2026")
    assert response.status_code == 200, response.text
    assert {state["region_id"] for state in response.json()["us_states"]} == supported
    assert {city["region_id"] for city in response.json()["us_cities"]} == cities
    countries = set(CountryRouter.countries_for_tax_year(2026))
    assert {c["region_id"] for c in response.json()["international"]} == countries
    states_group = client.get("/v1/comparison/regions/us-states?tax_year=2026")
    assert states_group.status_code == 200, states_group.text
    assert states_group.json()["total"] == len(supported)
    assert set(states_group.json()["no_income_tax_states"]) == no_tax
    assert client.get("/v1/comparison/regions/us-cities?tax_year=2026").json()["total"] == len(cities)
    assert client.get("/v1/comparison/regions/international?tax_year=2026").json()["total"] == len(countries)
    assert client.get("/v1/comparison/regions/US-TX?tax_year=2026").status_code == 200
    for region_id in sorted(set(US_STATES) - supported)[:1]:
        assert client.get(f"/v1/comparison/regions/{region_id}?tax_year=2026").status_code == 404
    years = client.get("/v1/tax-years")
    assert years.status_code == 200, years.text
    assert 2026 in [item["year"] for item in years.json()["data"]]
    details = client.get("/v1/tax-years/2026")
    assert details.status_code == 200, details.text
    assert details.json()["supported_jurisdictions"] == {
        "federal": 1, "states": len(enabled), "local": len(cities),
    }
    jurisdictions = client.get("/v1/jurisdictions?tax_year=2026")
    assert jurisdictions.status_code == 200, jurisdictions.text
    assert {item["id"] for item in jurisdictions.json()["data"]} == {"US", *supported}
    texas = client.get("/v1/jurisdictions/US-TX?tax_year=2026")
    assert texas.status_code == 200, texas.text
    assert texas.json()["tax_summary"]["type"] == "none"
    assert texas.json()["local_taxes"]["has_local_income_tax"] is False
    brackets = client.get("/v1/jurisdictions/US-TX/brackets?tax_year=2026")
    assert brackets.status_code == 200, brackets.text
    assert brackets.json()["brackets_by_filing_status"] == {}


def test_2026_wage_only_texas_public_estimate():
    # IRS 2026 single schedule: taxable income 100,000 - 16,100 = 83,900.
    # Ordinary tax 5,800 + (83,900 - 50,400) * 22% = 13,170.
    # Employee FICA 100,000 * (6.2% + 1.45%) = 7,650.
    response = _estimate()
    assert response.status_code == 201, response.text
    summary = response.json()["summary"]
    assert Decimal(summary["total_federal_tax"]) == Decimal("13170.00")
    assert Decimal(summary["total_state_tax"]) == 0
    assert Decimal(summary["employee_payroll_tax"]) == Decimal("7650.00")
    assert Decimal(summary["total_modelled_deductions"]) == Decimal("20820.00")


def test_2026_new_state_estimate_and_two_state_comparison_agree():
    florida = _estimate("FL")
    assert florida.status_code == 201, florida.text
    assert Decimal(florida.json()["summary"]["total_modelled_deductions"]) == Decimal("20820")

    comparison = _compare(
        {"employment_wages": "100000"}, regions=["US-FL", "US-TX"]
    )
    assert comparison.status_code == 200, comparison.text
    body = comparison.json()
    assert {item["region_id"] for item in body["regions"]} == {"US-FL", "US-TX"}
    assert all(Decimal(item["total_tax_local"]) == Decimal("20820") for item in body["regions"])
    assert body["exchange_rates"]["rates"] == {"USD": "1"}


def test_2026_short_loss_nets_long_gain_without_preferential_tax():
    response = client.post("/v1/estimates", json={
        "tax_year": 2026,
        "filer": {"filing_status": "single", "age_at_year_end": 40},
        "residency": {"residence_state": "NH"},
        "income": {
            "wages": [{"employer_name": "Example", "employer_state": "NH",
                       "gross_wages": "100000"}],
            "capital_gains": {"short_term_loss": "10000", "long_term_gain": "10000"},
        },
    })
    assert response.status_code == 201, response.text
    summary = response.json()["summary"]
    assert Decimal(summary["total_federal_tax"]) == Decimal("13170")
    assert Decimal(summary["total_state_tax"]) == 0


@pytest.mark.parametrize(("field", "federal_tax", "payroll"), [
    ("employment_wages", "13170.00", "7650.00"),
    ("dividends_ordinary", "13170.00", "0.00"),
    ("capital_gains_short_term", "13170.00", "0.00"),
    ("dividends_qualified", "5168.00", "0.00"),
    ("capital_gains_long_term", "5168.00", "0.00"),
])
def test_2026_income_character_is_respected_in_texas(field, federal_tax, payroll):
    # QD/LTCG: 83,900 taxable less 49,450 zero-rate band = 34,450 at 15%,
    # or 5,167.50 before the engine's Form-1040 whole-dollar rounding.
    response = _compare({field: "100000"})
    assert response.status_code == 200, response.text
    result = response.json()["regions"][0]
    breakdown = result["us_breakdown"]
    assert Decimal(breakdown["federal_tax"]) == Decimal(federal_tax)
    assert Decimal(breakdown["employee_payroll_tax"]) == Decimal(payroll)
    assert Decimal(breakdown["state_tax"]) == 0
    assert Decimal(result["total_tax_local"]) == Decimal(federal_tax) + Decimal(payroll)


def test_2026_niit_and_no_2025_fx_claim():
    response = _compare({"employment_wages": "200000", "dividends_qualified": "10000"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(body["regions"][0]["us_breakdown"]["federal_niit"]) == Decimal("380.00")
    assert body["exchange_rates"]["rates"] == {"USD": "1"}
    assert "No currency conversion" in body["exchange_rates"]["source"]
    assert all("IRS 2025 annual average" not in item for item in body["disclaimers"])


@pytest.mark.parametrize(("income", "regions", "currency"), [
    ({"employment_wages": "100000"}, ["US-CO"], "USD"),
    ({"employment_wages": "100000"}, ["US-TX"], "GBP"),
    ({"employment_wages": "100000", "interest": "1"}, ["US-TX"], "USD"),
])
def test_unsupported_2026_compare_requests_fail_closed(income, regions, currency):
    response = _compare(income, regions=regions, currency=currency)
    assert response.status_code == 422, response.text


def test_unsupported_2026_estimates_fail_closed():
    assert _estimate("CO").status_code == 422
    assert _estimate("TX", age=41).status_code == 422
    assert client.get("/v1/comparison/regions?tax_year=2027").status_code == 422
    assert client.get("/v1/jurisdictions/US-CO?tax_year=2026").status_code == 404
    assert _compare({"employment_wages": "100000"}, year=2027).status_code == 422


def test_2025_region_discovery_is_unchanged():
    response = client.get("/v1/comparison/regions?tax_year=2025")
    assert response.status_code == 200
    assert len(response.json()["us_states"]) == 51
    assert response.json()["us_cities"]
