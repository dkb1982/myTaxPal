"""Independent final-review oracles for Arkansas's 2025 indexed schedule."""

from decimal import Decimal as D  # noqa: N817 - compact source arithmetic

import pytest

from tax_estimator.calculation.states.calculator import StateCalculator
from tax_estimator.calculation.states.models import StateTaxInput
from tax_estimator.calculation.states.policies_2025_a_m import _ar_table_tax


@pytest.mark.parametrize(
    ("taxable_income", "expected_tax"),
    [
        # Official 2025 brackets PDF examples: use each $100 row's midpoint.
        ("14800", "222"),
        # The printed 2025 Regular Income Tax Table (2025_TaxTables.pdf p. 28) has
        # rows "as much as 75,801 but less than 75,901" -> 2,538 and "75,901 but less
        # than 76,001" -> 2,542, so the brackets-PDF example row ($2,542) starts at
        # 75,901; 75,900 itself is in the 2,538 row (75,850.5 x .039 - 419.96 = 2,538.21).
        ("75901", "2542"),
        ("75900", "2538"),
        # The final lower-table row ends inclusively at $94,700. The phaseout
        # begins at $94,701 and therefore uses a different midpoint/adjustment.
        ("94700", "3271"),
        ("94701", "3296"),
        ("94800", "3296"),
        ("94801", "3310"),
        ("97800", "3713"),
        ("97801", "3727"),
        ("97900", "3727"),
        ("97901", "3731"),
        ("98000", "3731"),
        ("98001", "3735"),
        ("100000", "3809"),
        ("100001", "3809.039"),
        ("15999.49", "255"),
        ("15999.50", "258"),
        ("94700.49", "3271"),
        ("94700.50", "3296"),
        ("100000.49", "3809"),
        ("100000.50", "3809.039"),
    ],
)
def test_arkansas_indexed_phaseout_and_schedule_boundary(
    taxable_income: str, expected_tax: str
) -> None:
    """Match the official $100 bands and the $100,001 formula exactly."""
    assert _ar_table_tax(D(taxable_income)) == D(expected_tax)


@pytest.mark.parametrize(
    ("long_term_gain", "expected_subtraction", "expected_net_tax"),
    [
        ("10000000", "5000000", "194783.67"),
        ("10000001", "5000001", "194783.67"),
        ("12000000", "7000000", "194783.67"),
    ],
)
def test_arkansas_large_net_capital_gain_exclusion(
    long_term_gain: str, expected_subtraction: str, expected_net_tax: str
) -> None:
    """AR1000D caps the 50% inclusion base at $10 million."""
    gain = D(long_term_gain)
    result = StateCalculator().calculate(
        StateTaxInput(
            state_code="AR",
            tax_year=2025,
            filing_status="single",
            federal_agi=gain,
            federal_taxable_income=max(D(0), gain - D("15750")),
            net_short_term_gains=D(0),
            net_long_term_gains=gain,
            federal_agi_capital_gain=gain,
            federal_income_tax_after_nonrefundable_credits=D(0),
            federal_earned_income_credit=D(0),
            federal_deduction_amount=D("15750"),
            employee_social_security_tax=D(0),
            employee_medicare_tax=D(0),
            taxpayer_age_at_year_end=40,
            baseline_profile_supported=True,
        )
    )

    assert result.subtractions[0].amount == D(expected_subtraction)
    assert result.total_tax == D(expected_net_tax)
