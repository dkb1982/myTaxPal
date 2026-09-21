"""Source-derived 2025 repairs and public/main/Compare parity (not tax advice).

IRS Rev Proc 2025-32, 2025 Schedule A/SE; FTB 2025 Form 540 and rate schedules;
HMRC 2025/26 income tax and National Insurance tables. See repair evidence.
"""

from decimal import Decimal as D  # noqa: N817 - compact source arithmetic in tests

import pytest
from fastapi.testclient import TestClient

from tax_estimator.calculation.comparison import RegionComparisonEngine
from tax_estimator.calculation.comparison_enhanced import EnhancedComparisonEngine
from tax_estimator.calculation.comparison_regions import US_CITIES, US_STATES
from tax_estimator.calculation.comparison_us import USStateComparisonCalculator
from tax_estimator.calculation.locals.loader import LocalRulesLoader
from tax_estimator.calculation.states.calculator import StateCalculator
from tax_estimator.calculation.states.models import StateTaxInput
from tax_estimator.main import app
from tax_estimator.models.us_scenario import USScenarioFacts

client = TestClient(app)


def test_us_comparison_breakdown_rate_includes_employee_payroll():
    result = USStateComparisonCalculator().calculate("US-TX", D(100000), "single")
    assert result.breakdown.total_tax == D(21099)
    assert result.breakdown.total_effective_rate == D(".21099")


def test_every_advertised_us_region_has_loadable_rules():
    calculator = USStateComparisonCalculator()
    for region in list(US_STATES) + list(US_CITIES):
        result = calculator.calculate(region, D(100000), "single",
            us_scenario=USScenarioFacts(philly_first_half_wages=D(50000)))
        assert result.region_id == region
        assert result.total_tax >= 0


def estimate(wages=100000, state="TX", **changes):
    payload = {
        "tax_year": 2025,
        "filer": {"filing_status": "single"},
        "residency": {"residence_state": state},
        "income": {
            "wages": [{"employer_name": "Test", "employer_state": state, "gross_wages": wages}]
        },
    }
    payload.update(changes)
    return client.post("/v1/estimates", json=payload)


def test_us_wages_public_and_compare_reconcile_payroll_and_liability():
    response = estimate()
    assert response.status_code == 201, response.text
    summary = response.json()["summary"]
    # $1,192.50 + $4,386 + $7,870.50; employee SS $6,200 + Medicare $1,450.
    assert D(summary["total_federal_tax"]) == 13449
    assert D(summary["employee_payroll_tax"]) == 7650
    assert D(summary["total_statutory_deductions"]) == 21099
    assert D(summary["net_income"]) == 78901
    assert D(summary["balance_due"]) == 13449  # Not income tax plus payroll.
    comparison = client.post(
        "/v1/comparison/compare",
        json={"regions": ["US-TX"], "income": {"employment_wages": 100000}},
    )
    assert comparison.status_code == 200, comparison.text
    region = comparison.json()["regions"][0]
    assert D(region["total_tax_local"]) == D(summary["total_statutory_deductions"])
    components = region["us_breakdown"]
    assert sum(
        D(components[k]) for k in ("federal_tax", "state_tax", "local_tax", "employee_payroll_tax")
    ) == D(region["total_tax_local"])


@pytest.mark.parametrize(
    "changes,expected",
    [
        (
            {
                "income": {
                    "wages": [
                        {"employer_name": "Test", "employer_state": "TX", "gross_wages": 150000}
                    ]
                },
                "deductions": {"type": "itemized", "itemized": {"state_local_taxes_paid": 40000}},
            },
            19247,
        ),
        (
            {
                "income": {
                    "wages": [
                        {"employer_name": "Test", "employer_state": "TX", "gross_wages": 60000}
                    ]
                },
                "filer": {
                    "filing_status": "single",
                    "date_of_birth": "1955-01-01",
                    "qualifies_for_enhanced_senior_deduction": True,
                },
            },
            4112,
        ),
        (
            {
                "income": {
                    "wages": [
                        {"employer_name": "Test", "employer_state": "TX", "gross_wages": 100000}
                    ],
                    "capital_gains": {"short_term_loss": 10000, "long_term_gain": 10000},
                }
            },
            13449,
        ),
    ],
)
def test_source_derived_federal_repairs_through_public_api(changes, expected):
    response = estimate(**changes)
    assert response.status_code == 201, response.text
    assert D(response.json()["summary"]["total_federal_tax"]) == expected


def test_self_employment_additional_medicare_and_compare_parity():
    response = estimate(income={"self_employment": [{"gross_income": 300000}]})
    assert response.status_code == 201, response.text
    body = response.json()
    assert D(body["federal"]["additional_medicare_tax"]) == D("693.45")
    assert D(body["federal"]["self_employment_tax"]) == D("29870.85")
    assert D(body["summary"]["employee_payroll_tax"]) == 0
    assert D(body["summary"]["total_fica_tax"]) == D("30564.30")
    assert D(body["summary"]["total_statutory_deductions"]) == D(body["summary"]["total_tax"])
    comparison = client.post(
        "/v1/comparison/compare", json={"regions": ["US-TX"], "income": {"self_employment": 300000}}
    )
    assert comparison.status_code == 200, comparison.text
    assert D(comparison.json()["regions"][0]["total_tax_local"]) == D(
        body["summary"]["total_statutory_deductions"]
    )


def test_child_eligibility_and_earned_refund_survive_public_boundary():
    response = estimate(
        wages=10000,
        filer={"filing_status": "single", "has_valid_ssn_for_ctc": True},
        dependents=[
            {
                "first_name": "Child",
                "last_name": "Test",
                "date_of_birth": "2015-01-01",
                "relationship": "child",
                "months_lived_with_taxpayer": 12,
                "has_ssn": True,
                "qualifies_for_ctc": True,
            }
        ],
    )
    assert response.status_code == 201, response.text
    assert D(response.json()["federal"]["total_refundable_credits"]) == 1125
    assert D(response.json()["summary"]["total_federal_tax"]) == -1125


def test_payroll_explicit_zero_and_investment_income_are_not_wages():
    zero = estimate(
        income={
            "wages": [
                {
                    "employer_name": "Exempt",
                    "employer_state": "TX",
                    "gross_wages": 100000,
                    "social_security_wages": 0,
                    "medicare_wages": 0,
                }
            ]
        }
    )
    assert zero.status_code == 201, zero.text
    assert D(zero.json()["summary"]["employee_payroll_tax"]) == 0
    investment = estimate(income={"interest": {"taxable": 100000}})
    assert investment.status_code == 201, investment.text
    assert D(investment.json()["summary"]["employee_payroll_tax"]) == 0


def test_social_security_taxability_does_not_drop_nontaxable_household_income():
    response = estimate(income={"retirement": {"social_security": 30000, "pension": 20000}})
    assert response.status_code == 201, response.text
    body = response.json()
    assert D(body["federal"]["adjusted_gross_income"]) == 25350
    assert D(body["summary"]["total_federal_tax"]) == 960
    assert D(body["summary"]["total_income"]) == 50000
    assert D(body["summary"]["net_income"]) == 49040


def test_new_york_zip_local_and_withholding_survive_all_layers():
    response = estimate(
        state="NY",
        filer={"filing_status": "single", "age_at_year_end": 40},
        residency={"residence_state": "NY", "residence_zip": "10001"},
        income={
            "wages": [
                {
                    "employer_name": "NY",
                    "employer_state": "NY",
                    "gross_wages": 100000,
                    "state_withholding": 5000,
                    "local_withholding": 3500,
                }
            ]
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["local"]) == 1
    assert D(body["local"][0]["total_tax"]) > 0
    assert D(body["local"][0]["withholding"]) == 3500
    assert D(body["states"][0]["withholding"]) == 5000
    assert D(body["summary"]["total_withholding"]) == 8500
    assert D(body["summary"]["total_local_tax"]) == D(body["local"][0]["total_tax"])
    assert D(body["summary"]["total_tax"]) - 8500 == D(body["summary"]["balance_due"])
    comparison = client.post(
        "/v1/comparison/compare", json={"regions": ["US-NY-NYC"], "gross_income": 100000}
    )
    assert comparison.status_code == 200, comparison.text
    assert D(comparison.json()["regions"][0]["total_tax_local"]) == D(
        body["summary"]["total_statutory_deductions"]
    )


def ca(income, status="single", dependents=0, **kwargs):
    return StateCalculator().calculate(
        StateTaxInput(
            state_code="CA",
            tax_year=2025,
            filing_status=status,
            federal_agi=D(income),
            federal_taxable_income=D(income),
            wages=D(income),
            num_dependents=dependents,
            **kwargs,
        )
    )


def test_ca_exemptions_are_nonrefundable_credits_not_income_deductions():
    result = ca(100000)
    assert result.taxable_income == D(94294)
    assert result.tax_before_credits == D("5207.98")
    assert result.credits == 153
    assert result.total_tax == D("5054.98")
    assert ca(100000, dependents=1).total_tax == D("4579.98")
    assert ca(100000, age_65_or_older=True).total_tax == D("4901.98")
    assert ca(1000, dependents=2).total_tax == 0


@pytest.mark.parametrize(
    "status,threshold,step",
    [("single", 252203, 2500), ("mfs", 252203, 1250), ("mfj", 504411, 2500), ("hoh", 378310, 2500)],
)
def test_ca_credit_phaseout_boundaries(status, threshold, step):
    count = 2 if status == "mfj" else 1
    assert ca(threshold, status).credits == 153 * count
    assert ca(threshold + 1, status).credits == 147 * count
    assert ca(threshold + step + 1, status).credits == 141 * count


@pytest.mark.parametrize("status", ["single", "mfj", "mfs", "hoh", "qss"])
def test_ca_high_income_has_only_one_percent_surtax(status):
    lower = ca(3000000, status)
    upper = ca(3001000, status)
    assert upper.total_tax - lower.total_tax == D(133)  # 12.3% + 1%, never 14.3%.


@pytest.mark.parametrize("engine", [RegionComparisonEngine, EnhancedComparisonEngine])
def test_fx_is_sourced_shared_and_missing_rates_fail(engine):
    instance = engine()
    assert instance.convert_currency(D(1000), "USD", "GBP") == D(759)
    assert "IRS 2025 annual average" in instance._rate_source
    assert instance._rate_date == "2025-12-31"
    with pytest.raises(ValueError, match="Missing"):
        instance.convert_currency(D(1000), "XYZ", "XYZ")
    for invalid in ({}, {"USD": D(1), "GBP": D(0)}, {"USD": D(1), "GBP": D("NaN")}):
        with pytest.raises(ValueError):
            engine(exchange_rates=invalid)


def test_only_supported_years_are_advertised_and_no_silent_state_local_relabelling():
    years = client.get("/v1/tax-years").json()
    assert [row["year"] for row in years["data"]] == [2025]
    assert client.get("/v1/tax-years/2024").status_code == 404
    assert estimate(tax_year=2024).status_code == 422
    with pytest.raises(Exception, match="Unsupported tax year"):
        StateCalculator().calculate(
            StateTaxInput(
                state_code="CA",
                tax_year=2024,
                filing_status="single",
                federal_agi=D(100000),
                federal_taxable_income=D(100000),
            )
        )
    with pytest.raises(Exception, match="Unsupported tax year"):
        LocalRulesLoader().load_local_rules("US-NY-NYC", 2024)


def test_inconsistent_profiles_and_unsupported_residency_fail_explicitly():
    assert estimate(residency={"residence_state": "TX", "is_part_year": True}).status_code == 422
    assert (
        client.post(
            "/v1/international/estimate",
            json={"country_code": "GB", "gross_income": 20000, "currency_code": "USD"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/international/estimate",
            json={
                "country_code": "GB",
                "gross_income": 20000,
                "income": {"dividends_ordinary": 19000},
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/comparison/compare",
            json={
                "regions": ["GB"],
                "gross_income": 20000,
                "country_profiles": {"GB": {"employment_income": 1}},
            },
        ).status_code
        == 400
    )
