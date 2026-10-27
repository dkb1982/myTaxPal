"""
Portugal IRS reference tests for 2026 income (hand-calculated from primary sources).

Sources (retrieved 2026-10-27):
- Lei n.o 73-A/2025 (OE 2026), art. 68 CIRS for 2026 income:
  https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/legislacao/diplomas_legislativos/Documents/Lei-73-A-2025.pdf
  12.5% to 8,342 | 15.7% to 12,587 | 21.2% to 17,838 | 24.1% to 23,089
  | 31.1% to 29,397 | 34.9% to 43,090 | 43.1% to 46,566 | 44.6% to 86,634 | 48%
  Tax per full band: 1,042.75 / 666.465 / 1,113.212 / 1,265.491 / 1,961.788
  / 4,778.857 / 1,498.156 / 17,870.328 (cumulative 30,197.047 at 86,634)
- IAS 2026 EUR 537.13 (Portaria 480-A/2025/1) -> art. 25 specific deduction
  8.54 x 537.13 = 4,587.09 (or SS if higher).
- CIRS art. 68-A (2.5% 80k-250k, 5% above), art. 72 (28% capital income and
  gains, n.14 aggregation at the last bracket), art. 78-B (EUR 250).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.countries.base import UnsupportedIncomeError
from tax_estimator.calculation.countries.pt import PTCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import InternationalTaxInput, PTTaxInput

D = Decimal
TOL = D("0.02")


def _calc(breakdown: IncomeBreakdown | None = None, gross: str | None = None, **profile):
    if breakdown is None:
        breakdown = IncomeBreakdown(employment_wages=D(gross))
    tax_input = InternationalTaxInput(
        country_code="PT",
        tax_year=2026,
        gross_income=breakdown.total,
        income_breakdown=breakdown,
        pt=PTTaxInput(**profile) if profile else None,
    )
    return PTCalculator().calculate(tax_input)


def test_40k_specific_deduction_floor():
    # SS 4,400 < 4,587.09 -> specific deduction 4,587.09 ; taxable 35,412.91
    # Scale: 1,042.75 + 666.465 + 1,113.212 + 1,265.491 + 1,961.788
    #        + 6,015.91 x 34.9% (2,099.553) = 8,149.26 ; - 250 = 7,899.26
    # Total = 7,899.26 + 4,400 = 12,299.26
    r = _calc(gross="40000")
    assert r.taxable_income == D("35412.91")
    assert r.social_insurance == D("4400.00")
    assert abs(r.income_tax - D("7899.26")) <= TOL
    assert abs(r.total_tax - D("12299.26")) <= TOL


def test_100k_top_bracket_and_solidarity():
    # SS 11,000 (specific) -> taxable 89,000
    # Scale: 30,197.047 + 2,366 x 48% (1,135.68) = 31,332.73 ; - 250 = 31,082.73
    # Solidarity 2.5% x 9,000 = 225 ; Total = 31,082.73 + 225 + 11,000 = 42,307.73
    r = _calc(gross="100000")
    assert abs(r.income_tax - D("31082.73")) <= TOL
    assert r.other_taxes == D("225.00")
    assert abs(r.total_tax - D("42307.73")) <= TOL


def test_250k():
    # SS 27,500 -> taxable 222,500 ; scale 30,197.047 + 135,866 x 48% (65,215.68)
    #   = 95,412.73 ; - 250 = 95,162.73 ; solidarity 2.5% x 142,500 = 3,562.50
    # Total = 95,162.73 + 3,562.50 + 27,500 = 126,225.23
    r = _calc(gross="250000")
    assert abs(r.total_tax - D("126225.23")) <= TOL


def test_mixed_wages_dividends_gains():
    # Wages 60,000: SS 6,600 -> taxable 53,400 ; scale 12,326.719 + 6,834 x 44.6%
    #   (3,047.964) = 15,374.68 ; - 250 = 15,124.68
    # Short gains 3,000 not aggregated (56,400 < 86,634) -> 28% with long gains:
    #   (3,000 + 10,000) x 28% = 3,640 ; dividends 5,000 x 28% = 1,400
    # Income tax = 15,124.68 + 3,640 + 1,400 = 20,164.68 ; Total + SS = 26,764.68
    bd = IncomeBreakdown(
        employment_wages=D("60000"),
        dividends_qualified=D("5000"),
        capital_gains_short_term=D("3000"),
        capital_gains_long_term=D("10000"),
    )
    r = _calc(bd)
    assert abs(r.income_tax - D("20164.68")) <= TOL
    assert abs(r.total_tax - D("26764.68")) <= TOL


def test_short_gains_below_2026_threshold_stay_separate():
    # 85,000 wages: taxable 75,650 + 10,000 short gains = 85,650 < 86,634 (2026)
    # -> gains taxed at 28% (2,800); scale 12,326.719 + 29,084 x 44.6% = 25,298.18
    r = _calc(IncomeBreakdown(employment_wages=D("85000"), capital_gains_short_term=D("10000")))
    assert abs(r.income_tax - D("27848.18")) <= TOL
    assert not any("aggregated" in n for n in r.calculation_notes)


def test_low_income_minimo_warning_uses_2026_threshold():
    # 15,000 wages: taxable 15,000 - 4,587.09 = 10,412.91 ; 1,042.75 + 2,070.91 x 15.7%
    #   (325.13) = 1,367.88 ; - 250 = 1,117.88 ; warning threshold 2.2 x 14 x 537.13
    r = _calc(gross="15000")
    assert abs(r.income_tax - D("1117.88")) <= TOL
    assert any("16,543.60" in w for w in r.warnings)


def test_family_and_self_employment_refused():
    with pytest.raises(UnsupportedIncomeError):
        _calc(gross="50000", is_married=True)
    with pytest.raises(UnsupportedIncomeError):
        _calc(gross="50000", num_dependents=2)
    with pytest.raises(UnsupportedIncomeError):
        _calc(IncomeBreakdown(employment_wages=D("40000"), self_employment=D("10000")))


def test_period_note():
    r = _calc(gross="40000")
    assert any("calendar 2026" in n and "73-A/2025" in n for n in r.calculation_notes)
