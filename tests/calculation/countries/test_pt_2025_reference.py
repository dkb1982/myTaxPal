"""
Portugal IRS reference tests for 2025 income (hand-calculated from primary sources).

Sources:
- Lei n.o 55-A/2025 (art. 68 CIRS rates for 2025 income):
  https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/legislacao/diplomas_legislativos/Documents/Lei_55_A_2025.pdf
  12.5% to 8,059 | 16% to 12,160 | 21.5% to 17,233 | 24.4% to 22,306 | 31.4% to 28,400
  | 34.9% to 41,629 | 43.1% to 44,987 | 44.6% to 83,696 | 48% above
  Cumulative tax at bracket tops: 1,007.375 / 1,663.535 / 2,754.23 / 3,992.042
  / 5,905.558 / 10,522.479 / 11,969.777 / 29,233.991
- CIRS art. 25 (specific deduction = greater of 8.54 x IAS = 4,462.15 or SS):
  https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/codigos_tributarios/cirs_rep/Pages/irs25.aspx
- CIRS art. 72 (28% capital income/gains, 25% residential rent, n.14 aggregation):
  https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/codigos_tributarios/cirs_rep/Pages/irs72.aspx
- CIRS art. 68-A solidarity surcharge (taxable income): 2.5% on 80k-250k, 5% above.
- CIRS art. 78-B: EUR 250 general family expenses deduction (assumed fully used).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.comparison_enhanced import compare_regions_enhanced
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
        tax_year=2025,
        gross_income=breakdown.total,
        income_breakdown=breakdown,
        pt=PTTaxInput(**profile) if profile else None,
    )
    return PTCalculator().calculate(tax_input)


def test_low_salary_20k():
    # SS 2,200 < 4,462.15 -> deduction 4,462.15 ; taxable = 15,537.85
    # Tax = 1,663.535 + (15,537.85 - 12,160) x 21.5% = 2,389.77 ; - 250 = 2,139.77
    r = _calc(gross="20000")
    assert r.social_insurance == D("2200.00")
    assert abs(r.income_tax - D("2139.77")) <= TOL
    assert abs(r.total_tax - D("4339.77")) <= TOL


def test_mid_salary_50k_reference():
    # SS 5,500 > 4,462.15 -> deduction 5,500 (not both) ; taxable = 44,500
    # Tax = 10,522.479 + (44,500 - 41,629) x 43.1% = 11,759.88 ; - 250 = 11,509.88
    # Total = 17,009.88 (review reference ~17.0k)
    r = _calc(gross="50000")
    assert abs(r.income_tax - D("11509.88")) <= TOL
    assert abs(r.total_tax - D("17009.88")) <= TOL


def test_high_salary_150k_with_solidarity_on_taxable_income():
    # SS 16,500 ; taxable = 133,500
    # Tax = 29,233.991 + (133,500 - 83,696) x 48% = 53,139.91 ; - 250 = 52,889.91
    # Solidarity = (133,500 - 80,000) x 2.5% = 1,337.50 (on taxable, not gross)
    r = _calc(gross="150000")
    assert abs(r.income_tax - D("52889.91")) <= TOL
    assert r.other_taxes == D("1337.50")
    assert abs(r.total_tax - D("70727.41")) <= TOL


def test_salary_dividends_and_long_term_gains():
    # Salary part as in the 50k test; dividends 5,000 x 28% = 1,400;
    # long-term gains 10,000 x 28% = 2,800; no SS on investment income.
    bd = IncomeBreakdown(
        employment_wages=D("50000"),
        dividends_qualified=D("5000"),
        capital_gains_long_term=D("10000"),
    )
    r = _calc(bd)
    assert r.social_insurance == D("5500.00")
    assert abs(r.income_tax - D("15709.88")) <= TOL
    assert abs(r.total_tax - D("21209.88")) <= TOL


def test_short_term_gains_aggregated_at_top_bracket():
    # 100k salary: taxable wages 89,000 ; + 10,000 short-term gains = 99,000 >= 83,696
    # -> aggregated (art. 72 n.14): 29,233.991 + 15,304 x 48% = 36,579.91 ; - 250
    # Solidarity (99,000 - 80,000) x 2.5% = 475 ; SS 11,000
    bd = IncomeBreakdown(employment_wages=D("100000"), capital_gains_short_term=D("10000"))
    r = _calc(bd)
    assert abs(r.income_tax - D("36329.91")) <= TOL
    assert r.other_taxes == D("475.00")
    assert abs(r.total_tax - D("47804.91")) <= TOL


def test_legacy_nhr_is_not_zero():
    # 20% x (100,000 - 11,000 SS deduction) = 17,800 + SS 11,000
    r = _calc(gross="100000", is_nhr=True)
    assert r.income_tax == D("17800.00")
    assert r.social_insurance == D("11000.00")
    assert r.total_tax == D("28800.00")


def test_rental_and_rejections():
    r = _calc(IncomeBreakdown(rental=D("10000")))
    assert r.income_tax == D("2500.00")  # 25% residential autonomous rate
    assert r.social_insurance == 0
    with pytest.raises(ValueError, match="category B"):
        _calc(IncomeBreakdown(self_employment=D("30000")))


def test_compare_path_parity():
    bd = IncomeBreakdown(
        employment_wages=D("50000"),
        dividends_qualified=D("5000"),
        capital_gains_long_term=D("10000"),
    )
    region = compare_regions_enhanced(["PT"], bd, base_currency="EUR").regions[0]
    assert region.total_tax_local == _calc(bd).total_tax
    assert region.international_breakdown.social_insurance == D("5500.00")
