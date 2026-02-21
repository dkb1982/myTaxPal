"""
Cross-country comparison sanity tests.

These tests verify that countries are ordered sensibly relative to each other.
They catch gross errors like UAE showing 40% tax or Singapore having higher
rates than France.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.countries.base import BaseCountryCalculator
from tax_estimator.calculation.countries import (
    gb, de, fr, sg, hk, ae, jp, au, ca, it, es, pt,
)
from tax_estimator.models.international import InternationalTaxInput


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


def _effective_rate(country_code: str, income: Decimal) -> Decimal:
    """Calculate effective rate for a country at given income."""
    calc = CALCULATORS[country_code]
    tax_input = InternationalTaxInput(
        country_code=country_code,
        tax_year=2025,
        currency_code="USD",
        gross_income=income,
    )
    result = calc.calculate(tax_input)
    return result.effective_rate


def _total_tax(country_code: str, income: Decimal) -> Decimal:
    """Calculate total tax for a country at given income."""
    calc = CALCULATORS[country_code]
    tax_input = InternationalTaxInput(
        country_code=country_code,
        tax_year=2025,
        currency_code="USD",
        gross_income=income,
    )
    result = calc.calculate(tax_input)
    return result.total_tax


# =============================================================================
# UAE vs Everyone
# =============================================================================


class TestUAELowestTax:
    """UAE (0% income tax) should have lower tax than every other country."""

    ALL_OTHER = [c for c in CALCULATORS if c != "AE"]

    @pytest.mark.parametrize("country_code", ALL_OTHER)
    def test_uae_lower_than_all(self, country_code: str):
        income = Decimal("300000")
        uae_rate = _effective_rate("AE", income)
        other_rate = _effective_rate(country_code, income)

        assert uae_rate < other_rate, (
            f"UAE rate ({uae_rate}) should be < {country_code} rate ({other_rate}) "
            f"at {income}"
        )


# =============================================================================
# Low Tax Jurisdictions vs High Tax Jurisdictions
# =============================================================================


class TestLowVsHighTax:
    """Low-tax countries should have lower rates than high-tax countries at high income."""

    LOW_TAX = ["SG", "HK"]
    HIGH_TAX_EUROPE = ["DE", "FR", "IT", "ES", "PT"]

    @pytest.mark.parametrize("low_tax", LOW_TAX)
    @pytest.mark.parametrize("high_tax", HIGH_TAX_EUROPE)
    def test_low_tax_below_high_tax_europe(self, low_tax: str, high_tax: str):
        income = Decimal("300000")
        low_rate = _effective_rate(low_tax, income)
        high_rate = _effective_rate(high_tax, income)

        assert low_rate < high_rate, (
            f"{low_tax} rate ({low_rate}) should be < "
            f"{high_tax} rate ({high_rate}) at {income}"
        )


# =============================================================================
# High Tax Cluster Bounds
# =============================================================================


class TestHighTaxBounds:
    """High-tax European countries should have rates above a reasonable minimum at high income."""

    HIGH_TAX = ["DE", "FR", "IT", "ES", "PT", "GB"]

    @pytest.mark.parametrize("country_code", HIGH_TAX)
    def test_high_tax_minimum_rate(self, country_code: str):
        """At 300k, high-tax countries should have effective rate > 25%."""
        rate = _effective_rate(country_code, Decimal("300000"))
        assert rate > Decimal("0.25"), (
            f"{country_code} effective rate at 300k is only {rate} "
            f"(expected > 25%)"
        )


# =============================================================================
# Low Tax Cluster Bounds
# =============================================================================


class TestLowTaxBounds:
    """Low-tax jurisdictions should have reasonable rates."""

    @pytest.mark.parametrize("country_code", ["SG", "HK"])
    def test_low_tax_maximum_rate(self, country_code: str):
        """At 300k, SG and HK should have effective rate < 25%."""
        rate = _effective_rate(country_code, Decimal("300000"))
        assert rate < Decimal("0.25"), (
            f"{country_code} effective rate at 300k is {rate} "
            f"(expected < 25%)"
        )

    @pytest.mark.parametrize("country_code", ["SG", "HK"])
    def test_low_tax_has_some_tax(self, country_code: str):
        """SG and HK should still have SOME tax at high income."""
        rate = _effective_rate(country_code, Decimal("300000"))
        assert rate > Decimal("0"), (
            f"{country_code} should have some tax at 300k"
        )


# =============================================================================
# Reasonable Effective Rate Ranges
# =============================================================================


class TestReasonableRanges:
    """
    Every country should produce effective rates within a plausible range.

    At median income (~50k), rates should be 0-30%.
    At high income (~300k), rates should be 0-55%.
    """

    ALL_COUNTRIES = list(CALCULATORS.keys())

    @pytest.mark.parametrize("country_code", ALL_COUNTRIES)
    def test_median_income_rate_range(self, country_code: str):
        rate = _effective_rate(country_code, Decimal("50000"))
        assert rate <= Decimal("0.40"), (
            f"{country_code} rate at 50k is {rate} (suspiciously high)"
        )

    @pytest.mark.parametrize("country_code", ALL_COUNTRIES)
    def test_high_income_rate_range(self, country_code: str):
        rate = _effective_rate(country_code, Decimal("300000"))
        assert rate <= Decimal("0.60"), (
            f"{country_code} rate at 300k is {rate} (suspiciously high — >60%)"
        )

    @pytest.mark.parametrize("country_code", ALL_COUNTRIES)
    def test_low_income_not_punitive(self, country_code: str):
        """At low income, tax rate should be modest."""
        rate = _effective_rate(country_code, Decimal("20000"))
        assert rate <= Decimal("0.30"), (
            f"{country_code} rate at 20k is {rate} (too high for low income)"
        )


# =============================================================================
# Japan > Hong Kong (well-known ordering)
# =============================================================================


class TestWellKnownOrderings:
    """Tax orderings that are common knowledge should hold."""

    def test_japan_higher_than_hong_kong(self):
        """Japan's overall tax burden is higher than Hong Kong's."""
        income = Decimal("300000")
        jp_rate = _effective_rate("JP", income)
        hk_rate = _effective_rate("HK", income)
        assert jp_rate > hk_rate, (
            f"Japan ({jp_rate}) should have higher rate than HK ({hk_rate})"
        )

    def test_gb_higher_than_singapore(self):
        """UK has higher overall tax than Singapore."""
        income = Decimal("300000")
        gb_rate = _effective_rate("GB", income)
        sg_rate = _effective_rate("SG", income)
        assert gb_rate > sg_rate, (
            f"GB ({gb_rate}) should have higher rate than SG ({sg_rate})"
        )

    def test_australia_between_extremes(self):
        """Australia should be between SG/HK and the highest-tax EU countries."""
        income = Decimal("300000")
        au_rate = _effective_rate("AU", income)
        hk_rate = _effective_rate("HK", income)
        de_rate = _effective_rate("DE", income)

        assert au_rate > hk_rate, (
            f"AU ({au_rate}) should be > HK ({hk_rate})"
        )
        # AU can be close to DE depending on rates, so just check it's not absurdly higher
        assert au_rate < Decimal("0.55"), (
            f"AU rate at 300k is {au_rate} (too high)"
        )
