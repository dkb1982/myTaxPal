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
_add("GB-300K", "GB", "GBP", "300000", "118689.00", "8010.60", "0", "126699.60", "0.4223")

# --- DE — Germany (2025 tax year - updated thresholds) ---
_add("DE-20K", "DE", "EUR", "20000", "1110.86", "4216.00", "0", "5326.86", "0.2663")
_add("DE-50K", "DE", "EUR", "50000", "8310.86", "10540.00", "0", "18850.86", "0.3770")
_add("DE-100K", "DE", "EUR", "100000", "25772.24", "17172.12", "1417.47", "44361.83", "0.4436")
_add("DE-300K", "DE", "EUR", "300000", "110400.59", "17172.12", "6072.03", "133644.74", "0.4455")

# --- FR — France (2025 income) ---
_add("FR-20K", "FR", "EUR", "20000", "588.06", "1940.00", "0", "2528.06", "0.1264")
_add("FR-50K", "FR", "EUR", "50000", "5766.23", "4850.00", "0", "10616.23", "0.2123")
_add("FR-100K", "FR", "EUR", "100000", "18340.72", "9700.00", "0", "28040.72", "0.2804")
_add("FR-300K", "FR", "EUR", "300000", "96472.78", "29100.00", "0", "125572.78", "0.4186")

# --- SG — Singapore (YA 2025) ---
_add("SG-20K", "SG", "SGD", "20000", "0.00", "4000.00", "0", "4000.00", "0.2000")
_add("SG-50K", "SG", "SGD", "50000", "550.00", "10000.00", "0", "10550.00", "0.2110")
_add("SG-100K", "SG", "SGD", "100000", "3773.20", "16320.00", "0", "20093.20", "0.2009")
_add("SG-300K", "SG", "SGD", "300000", "37286.00", "16320.00", "0", "53606.00", "0.1787")

# --- HK — Hong Kong (2024-25 year of assessment) ---
_add("HK-20K", "HK", "HKD", "20000", "0.00", "0", "0", "0.00", "0.0000")
_add("HK-50K", "HK", "HKD", "50000", "0.00", "0", "0", "0.00", "0.0000")
_add("HK-100K", "HK", "HKD", "100000", "0.00", "5000.00", "0", "5000.00", "0.0500")
_add("HK-300K", "HK", "HKD", "300000", "9420.00", "15000.00", "0", "24420.00", "0.0814")

# --- AE — UAE (no personal income tax) ---
_add("AE-20K", "AE", "AED", "20000", "0", "0", "0", "0", "0.0000")
_add("AE-50K", "AE", "AED", "50000", "0", "0", "0", "0", "0.0000")
_add("AE-100K", "AE", "AED", "100000", "0", "0", "0", "0", "0.0000")
_add("AE-300K", "AE", "AED", "300000", "0", "0", "0", "0", "0.0000")

# --- JP — Japan (2025 tax year) ---
_add("JP-3M", "JP", "JPY", "3000000", "58875", "442500", "123986", "625361", "0.2085")
_add("JP-5M", "JP", "JPY", "5000000", "130750", "737500", "235996", "1104246", "0.2208")
_add("JP-10M", "JP", "JPY", "10000000", "831760", "1273700", "652097", "2757557", "0.2758")
_add("JP-30M", "JP", "JPY", "30000000", "7732920", "1727700", "2799621", "12260241", "0.4087")

# --- AU — Australia (2024-25 financial year) ---
_add("AU-20K", "AU", "AUD", "20000", "288.00", "0", "0", "288.00", "0.0144")
_add("AU-50K", "AU", "AUD", "50000", "5788.00", "0", "1000.00", "6788.00", "0.1358")
_add("AU-100K", "AU", "AUD", "100000", "20788.00", "0", "3000.00", "23788.00", "0.2379")
_add("AU-300K", "AU", "AUD", "300000", "101138.00", "0", "10500.00", "111638.00", "0.3721")

# --- CA — Canada (2025 tax year, Ontario - updated thresholds) ---
_add("CA-20K", "CA", "CAD", "20000", "1590.65", "1309.75", "0", "2900.40", "0.1450")
_add("CA-50K", "CA", "CAD", "50000", "7605.65", "3586.75", "0", "11192.40", "0.2238")
_add("CA-100K", "CA", "CAD", "100000", "21019.60", "5507.58", "0", "26527.18", "0.2653")
_add("CA-300K", "CA", "CAD", "300000", "100223.14", "5507.58", "0", "105730.72", "0.3524")

# --- IT — Italy (2025 tax year) ---
_add("IT-20K", "IT", "EUR", "20000", "3190.94", "1838.00", "459.50", "5488.44", "0.2744")
_add("IT-50K", "IT", "EUR", "50000", "12183.65", "4595.00", "1148.75", "17927.40", "0.3585")
_add("IT-100K", "IT", "EUR", "100000", "31248.30", "9190.00", "2297.49", "42735.79", "0.4274")
_add("IT-300K", "IT", "EUR", "300000", "116714.03", "10432.49", "7326.06", "134472.58", "0.4482")

# --- ES — Spain (2025 tax year - updated combined rates) ---
_add("ES-20K", "ES", "EUR", "20000", "2540.70", "1270.00", "0", "3810.70", "0.1905")
_add("ES-50K", "ES", "EUR", "50000", "10973.25", "3175.00", "0", "14148.25", "0.2830")
_add("ES-100K", "ES", "EUR", "100000", "31785.34", "3597.02", "0", "35382.36", "0.3538")
_add("ES-300K", "ES", "EUR", "300000", "121785.34", "3597.02", "0", "125382.36", "0.4179")

# --- PT — Portugal (2025 tax year - updated brackets) ---
_add("PT-20K", "PT", "EUR", "20000", "1993.78", "2200.00", "0", "4193.78", "0.2097")
_add("PT-50K", "PT", "EUR", "50000", "10092.16", "5500.00", "0", "15592.16", "0.3118")
_add("PT-100K", "PT", "EUR", "100000", "28539.36", "11000.00", "500.00", "40039.36", "0.4004")
_add("PT-300K", "PT", "EUR", "300000", "113117.40", "33000.00", "6750.00", "152867.40", "0.5096")


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
