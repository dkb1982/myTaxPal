"""Independent statutory credit examples; source links live in the policy module."""
from decimal import Decimal as D

import pytest

from tax_estimator.calculation.states.credits_2025_additional import apply_additional_2025_credits
from tax_estimator.calculation.states.loader import StateRulesLoader
from tax_estimator.calculation.states.models import StatePolicyComputation, StateTaxInput
from tax_estimator.calculation.states.policy_common import build_state_result, StatePolicyError


def credit_fixture(code, income="10000", gross="100"):
    rules = StateRulesLoader().load_state_rules(code)
    t = StateTaxInput(state_code=code, tax_year=2025, filing_status="single",
        federal_agi=D(income), federal_taxable_income=D(0), wages=D(income),
        net_short_term_gains=D(0), net_long_term_gains=D(0),
        taxpayer_age_at_year_end=40, baseline_profile_supported=True,
        federal_eitc_eligibility_asserted=True, federal_earned_income_credit=D(649))
    c = StatePolicyComputation(starting_income=D(income), state_agi=D(income),
        taxable_income=D(income), ordinary_tax=D(gross), tax_before_credits=D(gross))
    return t, rules, c


@pytest.mark.parametrize("state,credit,net", [("CO", "324.50", "-224.50"),
    ("IL", "129.80", "-29.80"), ("IA", "97.35", "2.65"), ("KS", "110.33", "-10.33"),
    ("LA", "32.45", "67.55")])
def test_federal_linked_credit_known_649(state, credit, net):
    # $649 is an independently supplied 2025 childless federal-EIC fixture;
    # this test isolates the state multiplier/refund from the federal engine.
    t, r, c = credit_fixture(state)
    result = build_state_result(t, r, apply_additional_2025_credits(t, r, c))
    assert result.credits == D(credit)
    assert result.total_tax == D(net)
    if state == "KS":
        assert result.nonrefundable_credits == 100
        assert result.refundable_credits == D("10.33")
    else:
        assert result.refundable_credits == D(credit)


@pytest.mark.parametrize("assertion,federal,warning", [(None, None, True),
    (False, None, False), (None, "0", False), (True, "0", False)])
@pytest.mark.parametrize("state", ["CO", "IL", "IA", "KS", "LA"])
def test_unknown_zero_and_declined_credit_are_distinct(state, assertion, federal, warning):
    t, r, c = credit_fixture(state)
    t.federal_eitc_eligibility_asserted = assertion
    t.federal_earned_income_credit = D(federal) if federal is not None else None
    result = build_state_result(t, r, apply_additional_2025_credits(t, r, c))
    assert result.total_tax == 100
    assert bool(result.warnings) == warning


@pytest.mark.parametrize("income,gross,net", [("7999", "179.95", "0"),
    ("8000", "180", "0"), ("8001", "180.05", ".10"),
    ("10000", "280", "200"), ("14000", "816", "600"),
    ("14001", "816.085", "816.09")])
def test_ma_relief_boundaries_and_capital_tax(income, gross, net):
    # 14k example is ST gain: (14000-4400)*8.5%=816; cap 10%*(14000-8000).
    # Gross amounts at lower examples represent dividends, with no FICA deduction.
    t, r, c = credit_fixture("MA", income, gross)
    result = build_state_result(t, r, apply_additional_2025_credits(t, r, c))
    assert result.total_tax == D(net)


def test_ma_credit_agi_does_not_deduct_fica():
    # Wages 10k, employee FICA765: ordinary MA tax=(10000-765-4400)*5%=241.75.
    # Correct LIC is 41.75, leaving200; using AGI9235 would falsely leave123.50.
    t, r, c = credit_fixture("MA", "10000", "241.75")
    c.state_agi = D(9235)
    result = apply_additional_2025_credits(t, r, c)
    assert result.credits[-1].amount_applied == D("41.75")


def test_ma_signed_losses_cannot_silently_enter_positive_profile():
    t, r, c = credit_fixture("MA")
    t.net_short_term_gains = D(-1000)
    with pytest.raises(StatePolicyError, match="signed capital losses"):
        apply_additional_2025_credits(t, r, c)


@pytest.mark.parametrize("state", ["CO", "IL", "IA", "KS", "LA"])
def test_required_federal_amount_cannot_be_unknown_after_assertion(state):
    t, r, c = credit_fixture(state)
    t.federal_earned_income_credit = None
    with pytest.raises(StatePolicyError, match="requires known input"):
        apply_additional_2025_credits(t, r, c)
