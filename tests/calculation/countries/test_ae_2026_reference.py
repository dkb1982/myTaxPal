"""
UAE 2026 reference tests.

The UAE levies no personal income tax ("The UAE does not levy income tax on
individuals", https://u.ae/en/information-and-services/finance-and-investment/taxation,
retrieved 2026-10-27). Expatriate employees have no mandatory social security.
Every scenario therefore expects zero tax; self-employment is outside the 2026
scope (natural-person Corporate Tax above AED 1m turnover is not modelled).
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.countries.ae import AECalculator
from tax_estimator.calculation.countries.base import UnsupportedIncomeError
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import InternationalTaxInput


def _calc(gross: str, **kwargs):
    return AECalculator().calculate(
        InternationalTaxInput(
            country_code="AE", tax_year=2026, currency_code="AED",
            gross_income=Decimal(gross), **kwargs,
        )
    )


@pytest.mark.parametrize("wages", ["40000", "100000", "250000"])
def test_wages_untaxed(wages):
    r = _calc(wages, income_breakdown=IncomeBreakdown(employment_wages=Decimal(wages)))
    assert r.total_tax == Decimal("0")
    assert r.net_income == Decimal(wages)
    assert r.tax_year == 2026


def test_mixed_income_untaxed():
    bd = IncomeBreakdown(
        employment_wages=Decimal("300000"),
        dividends_ordinary=Decimal("50000"),
        capital_gains_long_term=Decimal("50000"),
        interest=Decimal("10000"),
    )
    r = _calc("410000", income_breakdown=bd)
    assert r.total_tax == Decimal("0")
    assert any("Calendar 2026" in n for n in r.calculation_notes)


def test_self_employment_refused():
    bd = IncomeBreakdown(employment_wages=Decimal("100000"), self_employment=Decimal("50000"))
    with pytest.raises(UnsupportedIncomeError):
        _calc("150000", income_breakdown=bd)
