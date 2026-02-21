"""
Property-based invariant tests for the Compare screen.

These tests verify mathematical properties that must ALWAYS hold,
regardless of the specific tax rates used. They catch logic errors,
not rate errors.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.countries.base import BaseCountryCalculator
from tax_estimator.calculation.countries import (
    gb, de, fr, sg, hk, ae, jp, au, ca, it, es, pt,
)
from tax_estimator.models.international import InternationalTaxInput
from tax_estimator.models.income_breakdown import IncomeBreakdown

# All supported country calculators
CALCULATORS: list[tuple[str, BaseCountryCalculator]] = [
    ("GB", gb.GBCalculator()),
    ("DE", de.DECalculator()),
    ("FR", fr.FRCalculator()),
    ("SG", sg.SGCalculator()),
    ("HK", hk.HKCalculator()),
    ("AE", ae.AECalculator()),
    ("JP", jp.JPCalculator()),
    ("AU", au.AUCalculator()),
    ("CA", ca.CACalculator()),
    ("IT", it.ITCalculator()),
    ("ES", es.ESCalculator()),
    ("PT", pt.PTCalculator()),
]

COUNTRY_CODES = [code for code, _ in CALCULATORS]

# Income levels in USD (converted via gross_income in local currency equivalent)
INCOME_LEVELS = [
    Decimal("0"),
    Decimal("1"),
    Decimal("20000"),
    Decimal("50000"),
    Decimal("100000"),
    Decimal("300000"),
    Decimal("1000000"),
]


def _make_input(country_code: str, gross_income: Decimal) -> InternationalTaxInput:
    """Create a simple InternationalTaxInput for testing."""
    return InternationalTaxInput(
        country_code=country_code,
        tax_year=2025,
        currency_code="USD",  # Simplified — real usage converts to local
        gross_income=gross_income,
    )


def _get_calculator(country_code: str) -> BaseCountryCalculator:
    """Get calculator for country code."""
    for code, calc in CALCULATORS:
        if code == country_code:
            return calc
    raise ValueError(f"No calculator for {country_code}")


# =============================================================================
# Invariant 1: Tax + Net = Gross
# =============================================================================


class TestTaxPlusNetEqualsGross:
    """total_tax + net_income must always equal gross_income."""

    @pytest.mark.parametrize("country_code", COUNTRY_CODES)
    @pytest.mark.parametrize("income", INCOME_LEVELS)
    def test_tax_plus_net_equals_gross(self, country_code: str, income: Decimal):
        calc = _get_calculator(country_code)
        tax_input = _make_input(country_code, income)
        result = calc.calculate(tax_input)

        total = result.total_tax + result.net_income
        assert total == result.gross_income, (
            f"{country_code} at {income}: "
            f"tax({result.total_tax}) + net({result.net_income}) = {total} "
            f"!= gross({result.gross_income})"
        )


# =============================================================================
# Invariant 2: Effective Rate Bounds
# =============================================================================


class TestEffectiveRateBounds:
    """Effective rate must be between 0 and 1 (inclusive)."""

    @pytest.mark.parametrize("country_code", COUNTRY_CODES)
    @pytest.mark.parametrize("income", [i for i in INCOME_LEVELS if i > 0])
    def test_effective_rate_bounds(self, country_code: str, income: Decimal):
        calc = _get_calculator(country_code)
        tax_input = _make_input(country_code, income)
        result = calc.calculate(tax_input)

        assert result.effective_rate >= Decimal("0"), (
            f"{country_code}: effective_rate {result.effective_rate} < 0"
        )
        assert result.effective_rate <= Decimal("1"), (
            f"{country_code}: effective_rate {result.effective_rate} > 1"
        )


# =============================================================================
# Invariant 3: UAE is always zero
# =============================================================================


class TestUAEAlwaysZero:
    """UAE has no personal income tax."""

    @pytest.mark.parametrize("income", INCOME_LEVELS)
    def test_uae_zero_tax(self, income: Decimal):
        calc = _get_calculator("AE")
        tax_input = _make_input("AE", income)
        result = calc.calculate(tax_input)

        assert result.total_tax == Decimal("0"), (
            f"UAE should have zero tax, got {result.total_tax}"
        )
        assert result.effective_rate == Decimal("0"), (
            f"UAE effective rate should be 0, got {result.effective_rate}"
        )
        assert result.net_income == income, (
            f"UAE net income should equal gross, got {result.net_income} != {income}"
        )


# =============================================================================
# Invariant 4: Monotonicity (higher income → higher or equal tax)
# =============================================================================


class TestMonotonicity:
    """Tax should increase (or stay same) as income increases."""

    @pytest.mark.parametrize("country_code", COUNTRY_CODES)
    def test_tax_increases_with_income(self, country_code: str):
        calc = _get_calculator(country_code)
        positive_incomes = [i for i in INCOME_LEVELS if i > 0]

        prev_tax = None
        for income in positive_incomes:
            tax_input = _make_input(country_code, income)
            result = calc.calculate(tax_input)

            if prev_tax is not None:
                assert result.total_tax >= prev_tax, (
                    f"{country_code}: tax decreased from {prev_tax} to "
                    f"{result.total_tax} as income increased to {income}"
                )
            prev_tax = result.total_tax


# =============================================================================
# Invariant 5: Progressive rates (higher income → higher effective rate)
# =============================================================================


class TestProgressiveRates:
    """For progressive tax systems, effective rate should increase with income.

    Note: Countries with social insurance ceilings (DE, JP, etc.) can see
    a tiny dip in *total* effective rate at incomes just above the SI ceiling,
    because SI becomes a smaller share of income while income tax hasn't fully
    compensated. We allow a small tolerance (1.5pp) to accommodate this.

    SG is excluded because CPF (20% of income up to SGD 81,600) dominates
    at low-to-mid income, causing total effective rate to genuinely decrease
    at higher incomes. SG's *income tax* is progressive, but total rate isn't.
    """

    # Countries with progressive tax systems (exclude AE=0% and SG=CPF ceiling effect)
    PROGRESSIVE_COUNTRIES = [c for c in COUNTRY_CODES if c not in ("AE", "SG")]

    @pytest.mark.parametrize("country_code", PROGRESSIVE_COUNTRIES)
    def test_effective_rate_increases(self, country_code: str):
        calc = _get_calculator(country_code)
        # Use medium-to-high incomes where progressivity is clear
        test_incomes = [Decimal("50000"), Decimal("100000"), Decimal("300000")]

        prev_rate = None
        for income in test_incomes:
            tax_input = _make_input(country_code, income)
            result = calc.calculate(tax_input)

            if prev_rate is not None:
                # Allow tolerance for social insurance ceiling effects.
                # E.g. SG CPF is 20% up to SGD 81,600 — at 50k it's 20%,
                # at 100k it's ~16%, causing total effective rate to dip.
                tolerance = Decimal("0.015")  # 1.5 percentage points
                assert result.effective_rate >= prev_rate - tolerance, (
                    f"{country_code}: effective rate decreased from {prev_rate} "
                    f"to {result.effective_rate} as income increased to {income} "
                    f"(more than {tolerance} drop)"
                )
            prev_rate = result.effective_rate


# =============================================================================
# Invariant 6: Zero income → zero tax
# =============================================================================


class TestZeroIncome:
    """Zero income should always produce zero tax."""

    @pytest.mark.parametrize("country_code", COUNTRY_CODES)
    def test_zero_income_zero_tax(self, country_code: str):
        calc = _get_calculator(country_code)
        tax_input = _make_input(country_code, Decimal("0"))
        result = calc.calculate(tax_input)

        assert result.total_tax == Decimal("0"), (
            f"{country_code}: zero income should have zero tax, got {result.total_tax}"
        )


# =============================================================================
# Invariant 7: Tax components sum correctly
# =============================================================================


class TestComponentsSum:
    """income_tax + social_insurance + other_taxes must equal total_tax."""

    @pytest.mark.parametrize("country_code", COUNTRY_CODES)
    @pytest.mark.parametrize("income", [Decimal("50000"), Decimal("300000")])
    def test_components_sum_to_total(self, country_code: str, income: Decimal):
        calc = _get_calculator(country_code)
        tax_input = _make_input(country_code, income)
        result = calc.calculate(tax_input)

        component_sum = result.income_tax + result.social_insurance + result.other_taxes
        assert component_sum == result.total_tax, (
            f"{country_code}: income_tax({result.income_tax}) + "
            f"social_insurance({result.social_insurance}) + "
            f"other_taxes({result.other_taxes}) = {component_sum} "
            f"!= total_tax({result.total_tax})"
        )


# =============================================================================
# Invariant 8: Non-negative results
# =============================================================================


class TestNonNegative:
    """Tax amounts should never be negative."""

    @pytest.mark.parametrize("country_code", COUNTRY_CODES)
    @pytest.mark.parametrize("income", [Decimal("50000"), Decimal("300000")])
    def test_non_negative_results(self, country_code: str, income: Decimal):
        calc = _get_calculator(country_code)
        tax_input = _make_input(country_code, income)
        result = calc.calculate(tax_input)

        assert result.total_tax >= 0, f"{country_code}: total_tax is negative"
        assert result.income_tax >= 0, f"{country_code}: income_tax is negative"
        assert result.social_insurance >= 0, f"{country_code}: social_insurance is negative"
        assert result.net_income >= 0, f"{country_code}: net_income is negative at {income}"


# =============================================================================
# Invariant 9: Idempotency (same input → same output)
# =============================================================================


class TestIdempotency:
    """Same input must always produce the same output."""

    @pytest.mark.parametrize("country_code", COUNTRY_CODES)
    def test_same_input_same_output(self, country_code: str):
        calc = _get_calculator(country_code)
        income = Decimal("100000")
        tax_input = _make_input(country_code, income)

        result1 = calc.calculate(tax_input)
        result2 = calc.calculate(tax_input)

        assert result1.total_tax == result2.total_tax
        assert result1.effective_rate == result2.effective_rate
        assert result1.net_income == result2.net_income


# =============================================================================
# Invariant 10: GB NI only on employment income
# =============================================================================


class TestGBNIScope:
    """For GB with income breakdown, NI should only apply to employment income."""

    def test_ni_only_on_employment(self):
        calc = _get_calculator("GB")

        # Pure capital gains — should have zero NI
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("0"),
            capital_gains_long_term=Decimal("100000"),
        )
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=breakdown.total,
            income_breakdown=breakdown,
        )
        result = calc.calculate(tax_input)

        # Check no NI components
        ni_components = [
            c for c in result.breakdown
            if "National Insurance" in c.name
        ]
        ni_total = sum(c.amount for c in ni_components)
        assert ni_total == Decimal("0"), (
            f"NI should be zero for capital gains only, got {ni_total}"
        )

    def test_ni_with_employment(self):
        calc = _get_calculator("GB")

        # Employment + capital gains — NI should only be on employment
        employment = Decimal("50000")
        cap_gains = Decimal("50000")
        breakdown = IncomeBreakdown(
            employment_wages=employment,
            capital_gains_long_term=cap_gains,
        )
        tax_input = InternationalTaxInput(
            country_code="GB",
            tax_year=2025,
            currency_code="GBP",
            gross_income=breakdown.total,
            income_breakdown=breakdown,
        )
        result = calc.calculate(tax_input)

        # NI should be on £50k employment, not £100k total
        ni_components = [
            c for c in result.breakdown
            if "National Insurance" in c.name
        ]
        ni_total = sum(c.amount for c in ni_components)

        # Calculate expected NI on £50k employment only
        # (above primary threshold, below UEL — just main rate)
        # This should be less than NI would be on £100k
        tax_input_100k = _make_input("GB", Decimal("100000"))
        result_100k = calc.calculate(tax_input_100k)
        ni_100k = sum(
            c.amount for c in result_100k.breakdown
            if "National Insurance" in c.name
        )

        assert ni_total < ni_100k, (
            f"NI on £50k employment ({ni_total}) should be less than "
            f"NI on £100k all-employment ({ni_100k})"
        )


# =============================================================================
# Invariant 11: Very high income doesn't overflow
# =============================================================================


class TestHighIncomeNoOverflow:
    """Calculator should handle very high incomes without errors."""

    @pytest.mark.parametrize("country_code", COUNTRY_CODES)
    def test_ten_million(self, country_code: str):
        calc = _get_calculator(country_code)
        income = Decimal("10000000")
        tax_input = _make_input(country_code, income)

        # Should not raise
        result = calc.calculate(tax_input)
        assert result.total_tax >= 0
        assert result.total_tax <= income  # Can't pay more than you earn
        assert result.effective_rate <= Decimal("1")
