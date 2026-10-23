"""End-to-end 2026 estimates for every enabled taxed state.

The per-state reference tests run each policy directly with hand-computed
federal inputs. This test runs the public API so the real 2026 federal
pipeline feeds the state policy. Per-state amounts are pinned by the
reference tests; this checks wiring, sign and monotonicity.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from tax_estimator.calculation.coverage import enabled_us_states
from tax_estimator.calculation.states.loader import StateRulesLoader
from tax_estimator.main import app

client = TestClient(app)
TAXED_2026 = sorted(
    code for code in enabled_us_states(2026)
    if StateRulesLoader().load_state_rules(code, 2026).has_income_tax
)


def _estimate(state: str, wages: int, *, qualified_dividends: int = 0, ltcg: int = 0) -> dict:
    income: dict = {"wages": [{
        "employer_name": "Employer", "employer_state": state, "gross_wages": wages,
        "federal_withholding": 0, "state_withholding": 0, "local_withholding": 0,
    }]}
    if qualified_dividends:
        income["dividends"] = {"ordinary": qualified_dividends, "qualified": qualified_dividends}
    if ltcg:
        income["capital_gains"] = {"long_term_gain": ltcg}
    body = {
        "tax_year": 2026,
        "filer": {"filing_status": "single", "age_at_year_end": 40},
        "residency": {"residence_state": state},
        "income": income,
    }
    if state == "AZ" and ltcg:
        body["us_scenario"] = {"az_post_2011_eligible_long_term_gains": ltcg}
    response = client.post("/v1/estimates", json=body)
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_taxed_states_are_enabled_for_2026():
    assert TAXED_2026, "no taxed 2026 states enabled"


@pytest.mark.parametrize("state", TAXED_2026)
@pytest.mark.parametrize("wages", [40000, 100000, 250000])
def test_2026_wage_estimate_has_positive_state_tax(state, wages):
    data = _estimate(state, wages)
    assert data["tax_year"] == 2026
    states = data["states"]
    assert len(states) == 1 and states[0]["jurisdiction_id"] == f"US-{state}"
    tax = Decimal(str(data["summary"]["total_state_tax"]))
    # North Dakota's 0% band covers $40,000 of wages, so only >= 0 there.
    assert Decimal(0) <= tax < Decimal(wages) * Decimal("0.15")
    if wages >= 100000:
        assert tax > 0


@pytest.mark.parametrize("state", TAXED_2026)
def test_2026_state_tax_is_monotonic_in_wages(state):
    taxes = [Decimal(str(_estimate(state, w)["summary"]["total_state_tax"])) for w in (60000, 61000, 120000)]
    assert taxes[0] <= taxes[1] <= taxes[2]


@pytest.mark.parametrize("state", TAXED_2026)
def test_2026_mixed_income_estimate(state):
    data = _estimate(state, 80000, qualified_dividends=5000, ltcg=10000)
    assert Decimal(str(data["summary"]["total_income"])) == Decimal(95000)
    assert Decimal(str(data["summary"]["total_state_tax"])) > 0
