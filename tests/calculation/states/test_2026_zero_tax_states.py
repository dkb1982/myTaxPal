"""Regression coverage for the reviewed 2026 zero-income-tax states."""

from decimal import Decimal as D  # noqa: N817 - compact exact-money fixtures

import pytest

from tax_estimator.calculation.comparison_us import USStateComparisonCalculator
from tax_estimator.calculation.states.calculator import (
    StateCalculationError,
    StateCalculator,
)
from tax_estimator.calculation.states.loader import StateRulesLoader
from tax_estimator.calculation.states.models import (
    StateStartingPoint,
    StateTaxInput,
    StateTaxType,
)
from tax_estimator.calculation.us_profile import SUPPORTED_2026_US_STATES

ZERO_TAX_STATES_2026 = frozenset({"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WY"})


def _mixed_income_input(state: str) -> StateTaxInput:
    # Ordinary dividends include the qualified-dividend subset on StateTaxInput.
    return StateTaxInput(
        state_code=state,
        tax_year=2026,
        filing_status="single",
        federal_agi=D("137000"),
        federal_taxable_income=D("120900"),
        wages=D("100000"),
        dividends=D("15000"),
        qualified_dividends=D("10000"),
        net_short_term_gains=D("7000"),
        net_long_term_gains=D("15000"),
        taxpayer_age_at_year_end=40,
        baseline_profile_supported=True,
    )


def test_2026_zero_tax_registry_exactly_matches_loadable_rules() -> None:
    loader = StateRulesLoader()

    assert SUPPORTED_2026_US_STATES == ZERO_TAX_STATES_2026
    assert set(loader.list_available_states(2026)) == ZERO_TAX_STATES_2026

    for state in ZERO_TAX_STATES_2026:
        assert loader.get_rules_file_path(state, 2026).parent.name == "2026"
        rules = loader.load_state_rules(state, 2026)
        assert rules.state_code == state
        assert rules.tax_year == 2026
        assert rules.has_income_tax is False
        assert rules.tax_type == StateTaxType.NONE
        assert rules.starting_point == StateStartingPoint.NOT_APPLICABLE
        assert rules.brackets == []
        assert rules.surtaxes == []


@pytest.mark.parametrize("state", sorted(ZERO_TAX_STATES_2026))
def test_2026_mixed_supported_income_has_zero_state_liability(state: str) -> None:
    result = StateCalculator().calculate(_mixed_income_input(state))

    assert result.state_code == state
    assert result.tax_year == 2026
    assert result.has_income_tax is False
    assert result.tax_type == StateTaxType.NONE
    assert result.tax_before_credits == D(0)
    assert result.total_tax == D(0)
    assert result.net_tax == D(0)


@pytest.mark.parametrize("state", ["CA", "WA"])
def test_direct_2026_state_calculation_rejects_unsupported_states(state: str) -> None:
    with pytest.raises(StateCalculationError, match=rf"not supported for {state}"):
        StateCalculator().calculate(_mixed_income_input(state))


@pytest.mark.parametrize("state", sorted(ZERO_TAX_STATES_2026))
def test_2026_wage_reference_is_identical_across_zero_tax_states(state: str) -> None:
    # IRS 2026 single: $100,000 - $16,100 = $83,900 taxable income;
    # $5,800 + 22% * ($83,900 - $50,400) = $13,170 income tax.
    # Employee FICA is 6.2% Social Security + 1.45% Medicare = $7,650.
    result = USStateComparisonCalculator().calculate(
        f"US-{state}", D("100000"), "single", tax_year=2026
    )

    assert result.breakdown is not None
    assert result.breakdown.state_code == state
    assert result.breakdown.federal_tax == D("13170")
    assert result.breakdown.employee_payroll_tax == D("7650")
    assert result.breakdown.state_tax == D(0)
    assert result.total_tax == D("20820")
