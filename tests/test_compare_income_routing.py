"""
Income type routing tests for country calculators.

Tests that each country handles different income types correctly:
- Countries with no CGT should show zero tax on capital gains (once implemented)
- GB should separate CGT from income tax
- Income type split should produce different results than lumped
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


CALCULATORS: dict[str, BaseCountryCalculator] = {
    "GB": gb.GBCalculator(),
    "DE": de.DECalculator(),
    "FR": fr.FRCalculator(),
    "SG": sg.SGCalculator(),
    "HK": hk.HKCalculator(),
    "AE": ae.AECalculator(),
    "JP": jp.JPCalculator(),
    "AU": au.AUCalculator(),
    "CA": ca.CACalculator(),
    "IT": it.ITCalculator(),
    "ES": es.ESCalculator(),
    "PT": pt.PTCalculator(),
}

ALL_COUNTRIES = list(CALCULATORS.keys())

# Income types from IncomeBreakdown
INCOME_TYPES = [
    "employment_wages",
    "capital_gains_short_term",
    "capital_gains_long_term",
    "dividends_qualified",
    "dividends_ordinary",
    "interest",
    "self_employment",
    "rental",
]


def _calc_with_breakdown(
    country_code: str, breakdown: IncomeBreakdown
) -> "InternationalTaxResult":
    """Calculate tax with income breakdown."""
    calc = CALCULATORS[country_code]
    tax_input = InternationalTaxInput(
        country_code=country_code,
        tax_year=2025,
        currency_code="USD",
        gross_income=breakdown.total,
        income_breakdown=breakdown,
    )
    return calc.calculate(tax_input)


def _calc_simple(country_code: str, gross_income: Decimal) -> "InternationalTaxResult":
    """Calculate tax with simple gross income (no breakdown)."""
    calc = CALCULATORS[country_code]
    tax_input = InternationalTaxInput(
        country_code=country_code,
        tax_year=2025,
        currency_code="USD",
        gross_income=gross_income,
    )
    return calc.calculate(tax_input)


# =============================================================================
# Test: Each income type individually produces valid results
# =============================================================================


class TestSingleIncomeType:
    """Each income type individually should produce valid results."""

    @pytest.mark.parametrize("country_code", ALL_COUNTRIES)
    @pytest.mark.parametrize("income_type", INCOME_TYPES)
    def test_single_income_type_valid(self, country_code: str, income_type: str):
        """Every country should handle every income type without errors."""
        breakdown = IncomeBreakdown(**{income_type: Decimal("100000")})
        result = _calc_with_breakdown(country_code, breakdown)

        assert result.total_tax >= 0
        assert result.net_income >= 0
        assert result.effective_rate >= 0
        assert result.effective_rate <= Decimal("1")
        assert result.total_tax + result.net_income == result.gross_income


# =============================================================================
# Test: GB separates CGT from income tax
# =============================================================================


class TestGBIncomeTypeSeparation:
    """GB should properly separate capital gains from income tax."""

    def test_employment_plus_cgt_has_cgt_components(self):
        """GB with employment + capital gains should have CGT breakdown components."""
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("300000"),
            capital_gains_long_term=Decimal("25000"),
        )
        result = _calc_with_breakdown("GB", breakdown)

        cgt_components = [
            c for c in result.breakdown
            if "Capital Gains" in c.name or "CGT" in c.component_id
        ]
        assert len(cgt_components) > 0, (
            "GB with capital gains should have CGT components in breakdown"
        )

    def test_cgt_annual_exempt_amount(self):
        """Small capital gains within AEA should produce zero CGT."""
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("50000"),
            capital_gains_long_term=Decimal("2000"),  # Below £3,000 AEA
        )
        result = _calc_with_breakdown("GB", breakdown)

        cgt_tax_components = [
            c for c in result.breakdown
            if "Capital Gains" in c.name and c.amount > 0
        ]
        assert len(cgt_tax_components) == 0, (
            f"Capital gains of £2k should be within AEA, but got CGT components: "
            f"{[(c.name, c.amount) for c in cgt_tax_components]}"
        )

    def test_employment_only_no_cgt(self):
        """GB with only employment income should have no CGT components."""
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("100000"),
        )
        result = _calc_with_breakdown("GB", breakdown)

        cgt_components = [
            c for c in result.breakdown
            if "Capital Gains" in c.name and c.amount > 0
        ]
        assert len(cgt_components) == 0, (
            "Employment-only should have no CGT"
        )


# =============================================================================
# Test: GB income breakdown vs lumped gives different results
# =============================================================================


class TestGBBreakdownVsLumped:
    """For GB, income breakdown should produce different results than lumping."""

    def test_mixed_income_different_from_lumped(self):
        """£300k employment + £25k LTCG + £100 interest should differ from £325,100 employment."""
        # With breakdown
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("300000"),
            capital_gains_long_term=Decimal("25000"),
            interest=Decimal("100"),
        )
        result_split = _calc_with_breakdown("GB", breakdown)

        # Without breakdown (lumped as employment)
        result_lumped = _calc_simple("GB", Decimal("325100"))

        # Tax should be different because:
        # 1. CGT is taxed at different rates than income tax
        # 2. NI is only on employment income, not capital gains
        assert result_split.total_tax != result_lumped.total_tax, (
            f"Split ({result_split.total_tax}) should differ from "
            f"lumped ({result_lumped.total_tax})"
        )

    def test_split_gives_different_ni(self):
        """NI should be lower when capital gains are separated from employment."""
        # With breakdown — NI only on £100k employment
        breakdown = IncomeBreakdown(
            employment_wages=Decimal("100000"),
            capital_gains_long_term=Decimal("100000"),
        )
        result_split = _calc_with_breakdown("GB", breakdown)

        # Without breakdown — NI on full £200k (incorrectly)
        result_lumped = _calc_simple("GB", Decimal("200000"))

        split_ni = sum(
            c.amount for c in result_split.breakdown
            if "National Insurance" in c.name
        )
        lumped_ni = sum(
            c.amount for c in result_lumped.breakdown
            if "National Insurance" in c.name
        )

        assert split_ni < lumped_ni, (
            f"Split NI ({split_ni}) should be < lumped NI ({lumped_ni}) "
            f"because CGT shouldn't incur NI"
        )


# =============================================================================
# Test: Mixed income standard profile for all countries
# =============================================================================


class TestMixedIncomeProfile:
    """Each country with mixed income should produce valid results."""

    STANDARD_MIXED = IncomeBreakdown(
        employment_wages=Decimal("200000"),
        capital_gains_long_term=Decimal("50000"),
        interest=Decimal("10000"),
        dividends_qualified=Decimal("5000"),
    )

    @pytest.mark.parametrize("country_code", ALL_COUNTRIES)
    def test_mixed_income_valid(self, country_code: str):
        """Standard mixed income profile should work for every country."""
        result = _calc_with_breakdown(country_code, self.STANDARD_MIXED)

        assert result.total_tax >= 0
        assert result.net_income >= 0
        assert result.effective_rate >= 0
        assert result.effective_rate <= Decimal("1")
        assert result.total_tax + result.net_income == result.gross_income

    @pytest.mark.parametrize("country_code", ALL_COUNTRIES)
    def test_backward_compat_no_breakdown(self, country_code: str):
        """Countries should still work with no income breakdown (backward compat)."""
        result = _calc_simple(country_code, Decimal("265000"))

        assert result.total_tax >= 0
        assert result.net_income >= 0
        assert result.total_tax + result.net_income == result.gross_income


# =============================================================================
# Test: UAE zero tax regardless of income type
# =============================================================================


class TestUAEAllIncomeTypes:
    """UAE should have zero tax on every income type."""

    @pytest.mark.parametrize("income_type", INCOME_TYPES)
    def test_uae_zero_on_all_types(self, income_type: str):
        breakdown = IncomeBreakdown(**{income_type: Decimal("100000")})
        result = _calc_with_breakdown("AE", breakdown)

        assert result.total_tax == Decimal("0"), (
            f"UAE should have zero tax on {income_type}, got {result.total_tax}"
        )
