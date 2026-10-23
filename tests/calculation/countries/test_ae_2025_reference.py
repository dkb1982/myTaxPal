"""
UAE 2025 reference tests.

The UAE levies no personal income tax (Federal Tax Authority, https://tax.gov.ae).
Expatriate employees have no mandatory social security. GPSSA pension for UAE
nationals (11% employee for those first insured from 31 Oct 2023, 5% legacy,
contributable salary capped at AED 70,000/month) is not modelled because the
input model has no nationality field; the calculator must say so.
"""

from decimal import Decimal

from tax_estimator.calculation.comparison_enhanced import compare_regions_enhanced
from tax_estimator.calculation.countries.ae import AECalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import InternationalTaxInput


def _calc(gross: str, **kwargs):
    return AECalculator().calculate(
        InternationalTaxInput(
            country_code="AE", tax_year=2025, currency_code="AED",
            gross_income=Decimal(gross), **kwargs,
        )
    )


def test_expat_salary_untaxed():
    r = _calc("600000")
    assert r.total_tax == Decimal("0")
    assert r.net_income == Decimal("600000")


def test_all_income_types_untaxed():
    bd = IncomeBreakdown(
        employment_wages=Decimal("300000"),
        dividends_ordinary=Decimal("50000"),
        capital_gains_short_term=Decimal("50000"),
        interest=Decimal("10000"),
        rental=Decimal("90000"),
    )
    r = _calc("500000", income_breakdown=bd)
    assert r.total_tax == Decimal("0")


def test_gpssa_limitation_disclosed():
    notes = " ".join(_calc("300000").calculation_notes)
    assert "GPSSA" in notes and "not modelled" in notes and "70,000" in notes


def test_compare_path_parity():
    bd = IncomeBreakdown(employment_wages=Decimal("300000"))
    compared = compare_regions_enhanced(regions=["AE"], income=bd, base_currency="AED")
    assert compared.regions[0].total_tax_local == _calc(
        "300000", income_breakdown=bd
    ).total_tax == Decimal("0")
