"""
Golden comparison tests for the Compare screen.

Each test compares calculator output against hand-verified expected values.
These are the "source of truth" tests — if a golden test fails, either:
1. The calculator has a bug, or
2. The golden fixture needs updating (with documented justification)

Tolerance: Typically 1 unit of local currency to allow for rounding differences.
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class GoldenVector:
    """A golden test vector with expected calculator output."""

    id: str
    country_code: str
    currency_code: str
    gross_income: Decimal
    expected_income_tax: Decimal
    expected_social_insurance: Decimal
    expected_other_taxes: Decimal
    expected_total_tax: Decimal
    expected_effective_rate: Decimal
    tolerance: Decimal = Decimal("1")  # 1 unit of local currency
    notes: str = ""


# =============================================================================
# Golden Vectors — populated from hand-verified calculator output
# =============================================================================

GOLDEN_VECTORS: list[GoldenVector] = []


def _add(
    id: str, cc: str, cur: str, gross: str,
    inc_tax: str, si: str, other: str, total: str, eff_rate: str,
    tol: str = "1", notes: str = "",
):
    """Helper to add a golden vector."""
    GOLDEN_VECTORS.append(GoldenVector(
        id=id, country_code=cc, currency_code=cur,
        gross_income=Decimal(gross),
        expected_income_tax=Decimal(inc_tax),
        expected_social_insurance=Decimal(si),
        expected_other_taxes=Decimal(other),
        expected_total_tax=Decimal(total),
        expected_effective_rate=Decimal(eff_rate),
        tolerance=Decimal(tol),
        notes=notes,
    ))


# --- GB — United Kingdom (2025-26 tax year) ---
_add("GB-20K", "GB", "GBP", "20000", "1486.00", "594.40", "0", "2080.40", "0.1040")
_add("GB-50K", "GB", "GBP", "50000", "7486.00", "2994.40", "0", "10480.40", "0.2096")
_add("GB-100K", "GB", "GBP", "100000", "27432.00", "4010.60", "0", "31442.60", "0.3144")
_add("GB-300K", "GB", "GBP", "300000", "121203.00", "8010.60", "0", "129213.60", "0.4307")

# --- DE — Germany (2025 tax year - updated thresholds) ---
_add("DE-20K", "DE", "EUR", "20000", "437", "4310.00", "0", "4747.00", "0.2374")
_add("DE-50K", "DE", "EUR", "50000", "6933", "10775.00", "0", "17708.00", "0.3542")
_add("DE-100K", "DE", "EUR", "100000", "23835", "17483.03", "462.31", "41780.34", "0.4178")
_add("DE-300K", "DE", "EUR", "300000", "107983", "17483.03", "5939.06", "131405.09", "0.4380")

# --- FR — France (2025 income) ---
_add("FR-20K", "FR", "EUR", "20000", "0", "4168.05", "0", "4168.05", "0.2084")
_add("FR-50K", "FR", "EUR", "50000", "4166", "10455.62", "0", "14621.62", "0.2924")
_add("FR-100K", "FR", "EUR", "100000", "15378", "20350.74", "0", "35728.74", "0.3573")
_add("FR-300K", "FR", "EUR", "300000", "81791", "60120.69", "0", "141911.69", "0.4730")

# --- SG — Singapore (2025 income / YA2026) ---
_add("SG-20K", "SG", "SGD", "20000", "0.00", "4000.00", "0", "4000.00", "0.2000")
_add("SG-50K", "SG", "SGD", "50000", "515.00", "10000.00", "0", "10515.00", "0.2103")
_add("SG-100K", "SG", "SGD", "100000", "3492.60", "17760.00", "0", "21252.60", "0.2125")
_add("SG-300K", "SG", "SGD", "300000", "36798.00", "17760.00", "0", "54558.00", "0.1819")

# --- HK — Hong Kong (2025/26 year of assessment, incl. HK$3,000 one-off reduction) ---
_add("HK-20K", "HK", "HKD", "20000", "0.00", "0", "0", "0.00", "0.0000")
_add("HK-50K", "HK", "HKD", "50000", "0.00", "0", "0", "0.00", "0.0000")
_add("HK-100K", "HK", "HKD", "100000", "0.00", "5000.00", "0", "5000.00", "0.0500")
_add("HK-300K", "HK", "HKD", "300000", "6420.00", "15000.00", "0", "21420.00", "0.0714")

# --- AE — UAE (no personal income tax) ---
_add("AE-20K", "AE", "AED", "20000", "0", "0", "0", "0", "0.0000")
_add("AE-50K", "AE", "AED", "50000", "0", "0", "0", "0", "0.0000")
_add("AE-100K", "AE", "AED", "100000", "0", "0", "0", "0", "0.0000")
_add("AE-300K", "AE", "AED", "300000", "0", "0", "0", "0", "0.0000")

# --- JP — Japan (2025 tax year) ---
_add("JP-3M", "JP", "JPY", "3000000", "34150", "456576", "116350", "607076", "0.2024")
_add("JP-5M", "JP", "JPY", "5000000", "118300", "721460", "245600", "1085360", "0.2171")
_add("JP-10M", "JP", "JPY", "10000000", "813900", "1262212", "655100", "2731212", "0.2731")
_add("JP-30M", "JP", "JPY", "30000000", "7741600", "1705188", "2801800", "12248588", "0.4083")

# --- AU — Australia (2025-26 financial year) ---
_add("AU-20K", "AU", "AUD", "20000", "0.00", "0", "0.00", "0.00", "0.0000")
_add("AU-50K", "AU", "AUD", "50000", "5538.00", "0", "1000.00", "6538.00", "0.1308")
_add("AU-100K", "AU", "AUD", "100000", "20788.00", "0", "2000.00", "22788.00", "0.2279")
_add("AU-300K", "AU", "AUD", "300000", "101138.00", "0", "10500.00", "111638.00", "0.3721")

# --- CA — Canada (2025 tax year, Ontario - updated thresholds) ---
_add("CA-20K", "CA", "CAD", "20000", "158.09", "1309.75", "0.00", "1467.84", "0.0734")
_add("CA-50K", "CA", "CAD", "50000", "5854.82", "3586.75", "600.00", "10041.57", "0.2008")
_add("CA-100K", "CA", "CAD", "100000", "19719.40", "5507.58", "750.00", "25976.98", "0.2598")
_add("CA-300K", "CA", "CAD", "300000", "114225.68", "5507.58", "900.00", "120633.26", "0.4021")

# --- IT — Italy (2025 tax year) ---
_add("IT-20K", "IT", "EUR", "20000", "1366.70", "1838.00", "-412.28", "2792.42", "0.1396")
_add("IT-50K", "IT", "EUR", "50000", "12132.82", "4595.00", "1148.75", "17876.57", "0.3575")
_add("IT-100K", "IT", "EUR", "100000", "31496.73", "9635.52", "2286.23", "43418.48", "0.4342")
_add("IT-300K", "IT", "EUR", "300000", "116593.79", "11735.37", "7293.10", "135622.26", "0.4521")

# --- ES — Spain (2025 tax year - updated combined rates) ---
_add("ES-20K", "ES", "EUR", "20000", "1882.99", "1296.00", "0", "3178.99", "0.1589")
_add("ES-50K", "ES", "EUR", "50000", "10563.38", "3240.00", "0", "13803.38", "0.2761")
_add("ES-100K", "ES", "EUR", "100000", "30785.61", "3888.37", "0", "34673.98", "0.3467")
_add("ES-300K", "ES", "EUR", "300000", "116618.50", "4276.99", "0", "120895.49", "0.4030")

# --- PT — Portugal (2025 tax year - updated brackets) ---
_add("PT-20K", "PT", "EUR", "20000", "2139.77", "2200.00", "0.00", "4339.77", "0.2170")
_add("PT-50K", "PT", "EUR", "50000", "11509.88", "5500.00", "0.00", "17009.88", "0.3402")
_add("PT-100K", "PT", "EUR", "100000", "31529.91", "11000.00", "225.00", "42754.91", "0.4275")
_add("PT-300K", "PT", "EUR", "300000", "116969.91", "33000.00", "5100.00", "155069.91", "0.5169")


# =============================================================================
# Test Class
# =============================================================================


@pytest.mark.golden
class TestGoldenVectors:
    """Compare calculator output against hand-verified golden vectors."""

    @pytest.mark.parametrize(
        "vector",
        GOLDEN_VECTORS,
        ids=lambda v: v.id,
    )
    def test_golden_vector(self, vector: GoldenVector):
        """Each golden vector must match within tolerance."""
        calc = CALCULATORS[vector.country_code]
        tax_input = InternationalTaxInput(
            country_code=vector.country_code,
            tax_year=2025,
            currency_code=vector.currency_code,
            gross_income=vector.gross_income,
        )
        result = calc.calculate(tax_input)

        tol = vector.tolerance

        assert abs(result.income_tax - vector.expected_income_tax) <= tol, (
            f"{vector.id}: income_tax {result.income_tax} != "
            f"expected {vector.expected_income_tax} (tol={tol})"
        )
        assert abs(result.social_insurance - vector.expected_social_insurance) <= tol, (
            f"{vector.id}: social_insurance {result.social_insurance} != "
            f"expected {vector.expected_social_insurance} (tol={tol})"
        )
        assert abs(result.other_taxes - vector.expected_other_taxes) <= tol, (
            f"{vector.id}: other_taxes {result.other_taxes} != "
            f"expected {vector.expected_other_taxes} (tol={tol})"
        )
        assert abs(result.total_tax - vector.expected_total_tax) <= tol, (
            f"{vector.id}: total_tax {result.total_tax} != "
            f"expected {vector.expected_total_tax} (tol={tol})"
        )

        # Effective rate tolerance is larger (0.01 = 1 percentage point)
        rate_tol = Decimal("0.005")
        assert abs(result.effective_rate - vector.expected_effective_rate) <= rate_tol, (
            f"{vector.id}: effective_rate {result.effective_rate} != "
            f"expected {vector.expected_effective_rate} (tol={rate_tol})"
        )

        # Structural invariant: tax + net = gross
        assert result.total_tax + result.net_income == result.gross_income, (
            f"{vector.id}: tax + net != gross"
        )
