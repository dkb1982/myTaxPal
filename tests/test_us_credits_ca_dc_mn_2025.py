"""Focused 2025 CA/DC/MN refundable-credit source fixtures."""
from decimal import Decimal

import pytest

from tax_estimator.calculation.states.credits_2025_ca_dc_mn import apply_ca_dc_mn_credits
from tax_estimator.calculation.states.loader import StateRulesLoader
from tax_estimator.calculation.states.models import StatePolicyComputation, StateTaxInput
from tax_estimator.calculation.states.policy_common import StatePolicyError, build_state_result

D = Decimal


def fixture(code: str, wages: str, *, agi: str | None = None, asserted: bool | None = True):
    rules = StateRulesLoader().load_state_rules(code)
    income = D(agi if agi is not None else wages)
    tax_input = StateTaxInput(
        state_code=code, tax_year=2025, filing_status="single", federal_agi=income,
        federal_taxable_income=D("0"), wages=D(wages), taxpayer_age_at_year_end=40,
        baseline_profile_supported=True, federal_eitc_eligibility_asserted=asserted,
        net_short_term_gains=D("0"), net_long_term_gains=D("0"),
    )
    computation = StatePolicyComputation(
        starting_income=income, state_agi=income, taxable_income=income,
        ordinary_tax=D("100"), tax_before_credits=D("100"),
    )
    return tax_input, rules, computation


@pytest.mark.parametrize(("wages", "agi", "expected"), [
    ("8483", "8483", "648.9495"),  # $8,483 × 7.65%
    ("8484", "8484", "649"),
    ("25000", "25000", "503.8224"),  # 649 - (25,000 - 23,288) × 8.48%
    ("30941", "30941", ".0256"),
    ("30942", "30942", "0"),
])
def test_dc_2025_childless_worksheet_boundaries(wages, agi, expected):
    t, r, c = fixture("DC", wages, agi=agi)
    result = build_state_result(t, r, apply_ca_dc_mn_credits(t, r, c))
    if D(expected):
        assert result.credit_components[-1].credit_id == "DC-EIC"
        assert result.credit_components[-1].amount_available == D(expected).quantize(D(".01"))
    else:
        assert not result.credit_components


def test_dc_uses_greater_of_earned_income_and_agi_for_phaseout():
    t, r, c = fixture("DC", "10000", agi="25000")
    result = build_state_result(t, r, apply_ca_dc_mn_credits(t, r, c))
    assert result.refundable_credits == D("503.82")


@pytest.mark.parametrize(
    ("wages", "expected"),
    [("1", "0"), ("25", "1"), ("9480", "379"), ("10000", "379"), ("32000", "373"), ("35109", "0")],
)
def test_mn_working_family_credit_2025_rate_and_cap(wages, expected):
    t, r, c = fixture("MN", wages)
    result = build_state_result(t, r, apply_ca_dc_mn_credits(t, r, c))
    if D(expected):
        assert result.credit_components[-1].credit_id == "MN-WFC"
    else:
        assert not result.credit_components
    assert result.refundable_credits == D(expected)


@pytest.mark.parametrize("state", ["DC", "MN"])
@pytest.mark.parametrize("asserted", [None, False])
def test_dc_mn_do_not_invent_missing_or_disclaimed_eligibility(state, asserted):
    t, r, c = fixture(state, "10000", asserted=asserted)
    result = build_state_result(t, r, apply_ca_dc_mn_credits(t, r, c))
    assert result.refundable_credits == 0
    assert bool(result.warnings) is (asserted is None)


@pytest.mark.parametrize(("wages", "agi", "expected"), [
    ("10000", "10000", "211"),
    ("25000", "25000", "73"),
    ("32851", "32851", "1"),
    ("32900", "32900", "1"),
    # FTB 3514 Step 6 retains the earned-income table amount below $4,661 AGI.
    ("10000", "4000", "211"),
    # At/above $4,661, differing AGI uses the lower of the two exact table values.
    ("10000", "25000", "73"),
])
def test_ca_2025_caleitc_full_official_table_and_step_six(wages, agi, expected):
    t, r, c = fixture("CA", wages, agi=agi)
    result = build_state_result(t, r, apply_ca_dc_mn_credits(t, r, c))
    assert result.credit_components[-1].credit_id == "CA-EITC"
    assert result.refundable_credits == D(expected)


def test_ca_known_investment_income_limit_is_not_overridden_by_assertion():
    t, r, c = fixture("CA", "10000", agi="15000")
    t.dividends = D("5000")
    result = build_state_result(t, r, apply_ca_dc_mn_credits(t, r, c))
    assert result.refundable_credits == 0
    assert not result.warnings


def test_dc_known_investment_income_above_limit_is_not_overridden_by_assertion():
    t, r, c = fixture("DC", "10000", agi="25000")
    t.dividends = D("15000")
    result = build_state_result(t, r, apply_ca_dc_mn_credits(t, r, c))
    assert result.refundable_credits == 0
    assert not result.warnings


def test_mn_uses_state_credit_when_known_federal_eic_is_zero():
    t, r, c = fixture("MN", "10000")
    t.federal_earned_income_credit = D("0")
    result = build_state_result(t, r, apply_ca_dc_mn_credits(t, r, c))
    assert result.refundable_credits == D("379")


@pytest.mark.parametrize("state", ["DC", "MN"])
def test_high_income_short_circuits_before_missing_eligibility_warning(state):
    t, r, c = fixture(state, "50000", asserted=None)
    result = build_state_result(t, r, apply_ca_dc_mn_credits(t, r, c))
    assert result.refundable_credits == 0
    assert not result.warnings


@pytest.mark.parametrize("state,dividends", [("CA", "5000"), ("DC", "12000"), ("MN", "12000")])
def test_capital_loss_does_not_offset_dividends_for_investment_limit(state, dividends):
    # Eligibility worksheets include positive net capital gain, not a negative
    # capital amount that would offset ordinary dividends.
    t, r, c = fixture(state, "10000", agi=str(D("7000") + D(dividends)))
    t.dividends = D(dividends)
    t.net_short_term_gains = D("-3000")
    result = build_state_result(t, r, apply_ca_dc_mn_credits(t, r, c))
    assert result.refundable_credits == 0


@pytest.mark.parametrize("state", ["CA", "DC", "MN"])
def test_missing_income_character_cannot_be_silently_omitted(state):
    t, r, c = fixture(state, "10000")
    t.net_short_term_gains = None
    with pytest.raises(StatePolicyError, match="known input"):
        apply_ca_dc_mn_credits(t, r, c)


@pytest.mark.parametrize("amount,expected", [("32900.20", "1"), ("32901", "0")])
def test_ca_income_cutoff_and_whole_dollar_table_convention(amount, expected):
    t, r, c = fixture("CA", amount)
    result = build_state_result(t, r, apply_ca_dc_mn_credits(t, r, c))
    assert result.refundable_credits == D(expected)
