"""US repair integration checks; parity is not an independent tax-law oracle.

The original 682 observations are preserved under .work/state-validation.
Source-derived numerical expectations live in the state/local policy tests.
"""
from decimal import Decimal as D
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from tax_estimator.calculation.comparison_regions import US_CITIES, US_STATES
from tax_estimator.calculation.comparison_us import USStateComparisonCalculator
from tax_estimator.calculation.locals.loader import LocalRulesLoader, LocalRulesLoaderError
from tax_estimator.calculation.pipeline import CalculationPipeline, PipelineError
from tax_estimator.calculation.stages.base import StageResult, StageStatus
from tax_estimator.main import app
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.us_scenario import USScenarioFacts

SCENARIOS = {
    "wages_25k": {"employment_wages": 25000},
    "wages_100k": {"employment_wages": 100000},
    "wages_300k": {"employment_wages": 300000},
    "wages_1500k": {"employment_wages": 1500000},
    "ordinary_dividends_100k": {"dividends_ordinary": 100000},
    "qualified_dividends_100k": {"dividends_qualified": 100000},
    "stcg_100k": {"capital_gains_short_term": 100000},
    "ltcg_100k": {"capital_gains_long_term": 100000},
    "ltcg_300k": {"capital_gains_long_term": 300000},
    "ltcg_1500k": {"capital_gains_long_term": 1500000},
    "mixed_200k": {"employment_wages": 100000, "dividends_ordinary": 10000,
                   "dividends_qualified": 10000, "capital_gains_short_term": 20000,
                   "capital_gains_long_term": 60000},
}

client = TestClient(app)

_STATE_SOURCE_CASES = []
for _name in ("fixtures_2025_a_m.json", "fixtures_2025_n_w.json"):
    _path = Path(__file__).parent / "calculation" / "states" / _name
    _STATE_SOURCE_CASES.extend(json.loads(_path.read_text())["cases"])

# Literal 56 original local-audit cases (cities.json), now exercised through
# the complete public pipeline. NYC references are gross; credits tested below.
_LOCAL_SOURCE_CASES = []
for _region, _wage, _investment in [
    ("US-NY-NYC", "3441.09", "3441.09"),
    ("US-PA-PHL", "3745", "3740"),
    ("US-MI-DET", "2385.60", "2385.60"),
    ("US-OH-CLE", "2500", "0"), ("US-OH-CIN", "1800", "0"),
    ("US-OH-CMH", "2500", "0"), ("US-MD-BAL", "2990.40", "2990.40"),
    ("US-IN-IND", "1999.80", "1999.80"),
    ("US-AL-BHM", "1000", "0"), ("US-KY-LOU", "2200", "0"),
]:
    for _scenario in ("wages_100k", "ordinary_dividends_100k", "qualified_dividends_100k", "stcg_100k", "ltcg_100k"):
        _expected = _wage if _scenario == "wages_100k" else _investment
        if _region == "US-PA-PHL" and _scenario == "ltcg_100k":
            _expected = "0"
        _LOCAL_SOURCE_CASES.append((_region, _scenario, _expected))
_LOCAL_SOURCE_CASES += [
    ("US-OH-CLE", "mixed_200k", "2500"), ("US-OH-CIN", "mixed_200k", "1800"),
    ("US-OH-CMH", "mixed_200k", "2500"), ("US-KY-LOU", "mixed_200k", "2200"),
    ("US-NY-YNK", "wages_100k", "829.46"), ("US-NY-YNK", "wages_300k", "3350.35"),
]


def facts_for(income):
    # Explicit fixture facts, not application defaults or inferred user consent.
    return USScenarioFacts(
        az_post_2011_eligible_long_term_gains=max(D(0), income.capital_gains_long_term),
        philly_gains_held_six_months_or_less=max(D(0), income.capital_gains_short_term),
        philly_first_half_wages=income.employment_wages / 2,
    )


def payload_for(region, income, facts):
    state = region.split("-")[1]
    city = US_CITIES.get(region)
    return {
        "tax_year": 2025, "filer": {"filing_status": "single", "age_at_year_end": 40},
        "residency": {"residence_state": state,
                      **({"local_jurisdiction_id": city.local_jurisdiction_id} if city else {})},
        "income": {
            "wages": [{"employer_name": "Integration fixture", "employer_state": state,
                       "gross_wages": str(income.employment_wages),
                       "social_security_wages": str(income.employment_wages),
                       "medicare_wages": str(income.employment_wages)}],
            "dividends": {"ordinary": str(income.total_dividends),
                          "qualified": str(income.dividends_qualified)},
            "capital_gains": {"short_term_gain": str(income.capital_gains_short_term),
                              "long_term_gain": str(income.capital_gains_long_term)},
        },
        "us_scenario": facts.model_dump(mode="json"),
    }


@pytest.mark.parametrize("region", list(US_STATES) + list(US_CITIES))
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_all_682_public_estimate_compare_pairs(region, scenario):
    income = IncomeBreakdown(**SCENARIOS[scenario])
    facts = facts_for(income)
    response = client.post("/v1/estimates", json=payload_for(region, income, facts))
    assert response.status_code == 201, response.text
    body = response.json()
    summary = body["summary"]
    comparison = USStateComparisonCalculator().calculate(region, income, "single", us_scenario=facts)
    assert D(summary["total_state_tax"]) == comparison.state_tax
    assert D(summary["total_local_tax"]) == comparison.local_tax
    assert D(summary["total_modelled_deductions"]) == comparison.total_tax
    assert D(summary["total_modelled_deductions"]) == sum(
        D(summary[key]) for key in ("total_federal_tax", "total_state_tax", "total_local_tax", "employee_payroll_tax")
    )
    assert D(summary["net_income"]) == D(summary["total_income"]) - comparison.total_tax
    assert not any("unvalidated profile inputs" in str(w) for w in body.get("warnings", []))
    for state in body["states"]:
        assert D(state["total_tax"]) == (
            D(state["tax_before_credits"]) + D(state["surtax"]) + D(state["recapture"])
            - D(state["nonrefundable_credits"]) - D(state["refundable_credits"])
        )
    for local in body["local"]:
        assert D(local["total_tax"]) == D(local["tax_before_credits"]) - D(local["total_credits"])


@pytest.mark.parametrize("case", _STATE_SOURCE_CASES, ids=lambda case: case["original_case_id"])
def test_retained_state_source_fixtures_through_public_api(case):
    """Original audit IDs with explicit, reviewable gross/net/rounding amendments."""
    region = "US-" + case.get("state", case.get("state_code"))
    income = IncomeBreakdown(**SCENARIOS[case["scenario"]])
    response = client.post("/v1/estimates", json=payload_for(region, income, facts_for(income)))
    assert response.status_code == 201, response.text
    state = response.json()["states"][0]
    field = "total_tax" if case["comparison_field"] == "net_tax" else case["comparison_field"]
    assert D(state[field]) == D(case["current_expected"]), case
    if "net_expected" in case:
        assert D(state["total_tax"]) == D(case["net_expected"])


def test_retained_state_case_ids_unique_and_cover_all_states():
    ids = [case["original_case_id"] for case in _STATE_SOURCE_CASES]
    assert len(ids) == len(set(ids)) == 120
    assert {"US-" + case.get("state", case.get("state_code")) for case in _STATE_SOURCE_CASES} == set(US_STATES)


@pytest.mark.parametrize("region,scenario,expected", _LOCAL_SOURCE_CASES)
def test_retained_56_local_source_cases_through_public_api(region, scenario, expected):
    income = IncomeBreakdown(**SCENARIOS[scenario])
    response = client.post("/v1/estimates", json=payload_for(region, income, facts_for(income)))
    assert response.status_code == 201, response.text
    local = response.json()["local"][0]
    field = "tax_before_credits" if region == "US-NY-NYC" else "total_tax"
    assert D(local[field]) == D(expected)
    if region == "US-NY-NYC":
        assert D(local["total_tax"]) == D("3174.69")


@pytest.mark.parametrize("stage_id", ["state_tax", "local_tax"])
def test_pipeline_component_failure_cannot_publish_partial_total(stage_id):
    broken = SimpleNamespace(stage_id=stage_id, stage_order=1, dependencies=[],
        should_skip=lambda _: False,
        execute=lambda _: StageResult(stage_id, StageStatus.ERROR, "Injected failure", "RULE_ERROR"))
    final = SimpleNamespace(stage_id="final", stage_order=2, dependencies=[],
        should_skip=lambda _: False, execute=Mock())
    with pytest.raises(PipelineError, match="Injected failure"):
        CalculationPipeline([broken, final]).execute(SimpleNamespace(trace=Mock()))
    final.execute.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("tax_type", "typo"), ("applies_to", "typo"), ("has_income_tax", "true"),
])
def test_local_loader_rejects_unknown_semantics(field, value):
    rules = {"jurisdiction_id": "US-OH-CLE", "parent_state": "OH", "has_income_tax": True,
             "tax_type": "earnings_tax", "applies_to": "both_residents_and_workers",
             "rate_schedule": {"rate_type": "flat", "tax_base": "wages_only", "flat_rates": {"rate": .025}}}
    rules[field] = value
    with pytest.raises(LocalRulesLoaderError):
        LocalRulesLoader()._parse_rules(rules, "US-OH-CLE")


@pytest.mark.parametrize("rate", [None, "bad", "full_rate", "NaN", "Infinity", -1, 2])
def test_local_loader_rejects_invalid_tax_rate(rate):
    rules = {"has_income_tax": True, "tax_type": "earnings_tax",
             "applies_to": "both_residents_and_workers",
             "rate_schedule": {"tax_base": "wages_only", "rate_type": "flat", "flat_rates": {"rate": rate}}}
    with pytest.raises(LocalRulesLoaderError):
        LocalRulesLoader()._parse_rules(rules, "US-OH-CLE")


@pytest.mark.parametrize("region,field", [
    ("US-AZ", "az_post_2011_eligible_long_term_gains"),
    ("US-PA-PHL", "philly_first_half_wages"),
    ("US-PA-PHL", "philly_gains_held_six_months_or_less"),
])
def test_ambiguous_tax_facts_are_required_not_silently_defaulted(region, field):
    income = IncomeBreakdown(**SCENARIOS["mixed_200k"])
    payload = payload_for(region, income, facts_for(income))
    payload["us_scenario"].pop(field)
    response = client.post("/v1/estimates", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MISSING_SCENARIO_FACTS"
    assert any(item["field"] == f"us_scenario.{field}" for item in response.json()["error"]["details"])


def test_philadelphia_zip_missing_fact_is_a_request_error():
    income = IncomeBreakdown(employment_wages=100000)
    payload = payload_for("US-PA-PHL", income, facts_for(income))
    payload["residency"].pop("local_jurisdiction_id", None)
    payload["residency"]["residence_zip"] = "19103"
    payload["us_scenario"].pop("philly_first_half_wages")
    response = client.post("/v1/estimates", json=payload)
    assert response.status_code == 422
    assert "philly_first_half_wages" in response.text


def test_age_conflict_and_qualified_dividend_subset_rejected():
    income = IncomeBreakdown(employment_wages=100000)
    payload = payload_for("US-NY", income, facts_for(income))
    payload["filer"]["date_of_birth"] = "1975-01-01"
    assert client.post("/v1/estimates", json=payload).status_code == 422
    payload["filer"].pop("date_of_birth")
    payload["income"]["dividends"] = {"ordinary": 100, "qualified": 101}
    assert client.post("/v1/estimates", json=payload).status_code == 422


@pytest.mark.parametrize("change", ["unknown_age", "older", "married", "interest", "itemized"])
def test_nonbaseline_profile_is_explicitly_unvalidated(change):
    income = IncomeBreakdown(employment_wages=100000)
    payload = payload_for("US-NY", income, facts_for(income))
    if change == "unknown_age":
        payload["filer"].pop("age_at_year_end")
    elif change == "older":
        payload["filer"]["age_at_year_end"] = 65
    elif change == "married":
        payload["filer"]["filing_status"] = "mfj"
    elif change == "interest":
        payload["income"]["interest"] = {"taxable": 100}
    else:
        payload["deductions"] = {"type": "itemized", "itemized": {"state_local_taxes_paid": 10000}}
    response = client.post("/v1/estimates", json=payload)
    assert response.status_code == 201, response.text
    assert "outside source-checked scope" in str(response.json()["warnings"])


def test_compare_facts_convert_with_income_and_eligibility_propagates(monkeypatch):
    from tax_estimator.calculation.comparison_enhanced import EnhancedComparisonEngine
    engine = EnhancedComparisonEngine()
    received = []
    calculate = engine._us_calculator.calculate

    def capture(**kwargs):
        received.append(kwargs)
        return calculate(**kwargs)

    monkeypatch.setattr(engine._us_calculator, "calculate", capture)
    income = IncomeBreakdown(**SCENARIOS["mixed_200k"])
    engine.compare(["US-PA-PHL"], income=income, base_currency="GBP",
                   us_scenario=facts_for(income), eitc_eligibility_asserted=True)
    actual = received[0]
    assert actual["us_scenario"].philly_first_half_wages == engine.convert_currency(D(50000), "GBP", "USD")
    assert actual["us_scenario"].philly_gains_held_six_months_or_less == engine.convert_currency(D(20000), "GBP", "USD")
    assert actual["income"].employment_wages == engine.convert_currency(D(100000), "GBP", "USD")
    assert actual["eitc_eligibility_asserted"] is True


@pytest.mark.parametrize("local", ["ny_missing_city", "md_baltimore"])
def test_missing_or_wrong_state_city_cannot_return_success(local):
    income = IncomeBreakdown(employment_wages=100000)
    payload = payload_for("US-NY", income, facts_for(income))
    payload["residency"]["local_jurisdiction_id"] = local
    assert client.post("/v1/estimates", json=payload).status_code != 201


def test_compare_rejects_whole_ranking_when_selected_city_is_incomplete():
    response = client.post("/v1/comparison/compare", json={
        "regions": ["US-TX", "US-PA-PHL"], "income": {"employment_wages": 100000},
    })
    assert response.status_code == 400
    assert "regions" not in response.json()


@pytest.mark.parametrize("region", list(US_STATES) + list(US_CITIES))
@pytest.mark.parametrize("wages", [0, 1000, 10000, 15650, 19104])
def test_low_income_credit_components_reconcile(region, wages):
    """Structural checks with explicit EIC legal assertion, not credit oracles."""
    income = IncomeBreakdown(employment_wages=wages)
    result = USStateComparisonCalculator().calculate(region, income, "single",
        us_scenario=facts_for(income), eitc_eligibility_asserted=True)
    assert result.total_tax == (result.federal_tax + result.state_tax
                               + result.local_tax + result.breakdown.employee_payroll_tax)
    for detail in [result.breakdown.state_details, *result.breakdown.local_details]:
        gross = D(detail.get("tax_before_credits", 0)) + D(detail.get("surtax", 0)) + D(detail.get("recapture", 0))
        nonref = D(detail.get("nonrefundable_credits", 0))
        refundable = D(detail.get("refundable_credits", 0))
        assert 0 <= nonref <= max(D(0), gross)
        assert refundable >= 0
        net = detail["total_state_tax"] if "total_state_tax" in detail else detail["net_tax"]
        assert D(net) == gross - nonref - refundable


@pytest.mark.parametrize("income,expected", [
    ({"employment_wages": 10000}, "200.00"),
    ({"dividends_ordinary": 8000}, "0.00"),
    ({"capital_gains_short_term": 14000}, "600.00"),
])
def test_ma_low_income_relief_reaches_both_public_paths(income, expected):
    # MGL62 §5: zero through AGI8k; then tax capped at10% of excess
    # through14k. EmployeeFICA does not reduce this eligibilityAGI.
    profile = IncomeBreakdown(**income)
    facts = facts_for(profile)
    response = client.post("/v1/estimates", json=payload_for("US-MA", profile, facts))
    assert response.status_code == 201, response.text
    assert D(response.json()["summary"]["total_state_tax"]) == D(expected)
    result = USStateComparisonCalculator().calculate("US-MA", profile, "single", us_scenario=facts)
    assert result.state_tax == D(expected)


@pytest.mark.parametrize("region,wages,credit,net", [
    ("US-CA", 10000, "211", "-211"),
    ("US-CA", 25000, "73", "49.09"),
    ("US-DC", 10000, "649", "-649"),
    ("US-DC", 25000, "503.82", "-103.82"),
    ("US-MN", 10000, "379", "-379"),
    ("US-MN", 25000, "379", "158.68"),
])
def test_independent_state_credits_survive_zero_federal_eic(region, wages, credit, net):
    # State worksheets have their own thresholds; federal childless EIC is
    # zero at25k but these state credits remain. Sources in the credit module.
    income = IncomeBreakdown(employment_wages=wages)
    facts = facts_for(income)
    payload = payload_for(region, income, facts)
    payload["eitc_eligibility_asserted"] = True
    response = client.post("/v1/estimates", json=payload)
    assert response.status_code == 201, response.text
    state = response.json()["states"][0]
    assert D(state["refundable_credits"]) == D(credit)
    assert D(state["total_tax"]) == D(net)
    comparison = USStateComparisonCalculator().calculate(region, income, "single",
        us_scenario=facts, eitc_eligibility_asserted=True)
    assert comparison.state_tax == D(net)


def test_alabama_niit_deduction_reaches_public_estimate_and_compare():
    # Form 40 p31: $262,927.50 regular federal tax + $49,400 NIIT.
    # AL tax: ($1.5m - $312,327.50 - $2,500 - $1,500) * 5% - $40.
    income = IncomeBreakdown(capital_gains_long_term=1500000)
    facts = facts_for(income)
    response = client.post("/v1/estimates", json=payload_for("US-AL", income, facts))
    assert response.status_code == 201, response.text
    assert D(response.json()["states"][0]["total_tax"]) == D("59143.63")
    comparison = USStateComparisonCalculator().calculate("US-AL", income, "single", us_scenario=facts)
    assert comparison.state_tax == D("59143.63")


def test_hawaii_conditional_food_credit_is_not_silently_granted_publicly():
    income = IncomeBreakdown(employment_wages=10000)
    response = client.post("/v1/estimates", json=payload_for("US-HI", income, facts_for(income)))
    assert response.status_code == 201, response.text
    assert not any(credit["code"] == "HI-FOOD" for credit in response.json()["states"][0]["credits"])
    assert "more than nine months" in response.text
