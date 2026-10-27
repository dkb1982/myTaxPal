"""
Australia reference tests for tax_year 2025 = income year 2025-26
(1 July 2025 - 30 June 2026).

Sources:
- Resident rates 2025-26: 0 to 18,200 | 16% to 45,000 | 30% to 135,000
  | 37% to 190,000 | 45% above (Income Tax Rates Act 1986 Sch 7, heading
  "2024-25 or 2025-26" inserted by Act No. 28 of 2025):
  https://www.legislation.gov.au/C2025A00028/asmade/2025-03-27/text/original/pdf
- Medicare levy low-income threshold (singles) 28,011, shade-in 10% to 35,013,
  for 2025-26 and later years (Act No. 58 of 2026, Sch 5):
  https://www.legislation.gov.au/C2026A00058/asmade/2026-06-30/text/original/pdf
- MLS 2025-26 singles: 1% > 101,000 ; 1.25% > 118,000 ; 1.5% > 158,000:
  https://www.privatehealth.gov.au/health_insurance/surcharges_incentives/medicare_levy.htm
- HELP 2025-26: 15% of repayment income above 67,000 to 125,000, 17% above,
  capped at 10% of repayment income (HESA ss 154-10, 154-20):
  https://www.legislation.gov.au/C2004A01234/2026-07-01/2026-07-01/text/original/pdf
- LITO: 700 to 37,500 ; -5c/$ to 45,000 ; -1.5c/$ to 66,667:
  https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/tax-offsets/low-and-middle-income-earner-tax-offsets
- CGT 50% discount (ITAA 1997 Div 115).
- Foreign dividends are assessable income with no franking credit (franking
  credits attach only to dividends from Australian companies); foreign income
  tax offset not modelled:
  https://www.ato.gov.au/forms-and-instructions/you-and-your-shares-2022/dividends-and-non-resident-companies-and-shareholders
  https://www.ato.gov.au/forms-and-instructions/foreign-income-tax-offset-rules-guide-2022/when-a-foreign-income-tax-offset-applies
"""

from __future__ import annotations

from decimal import Decimal

from tax_estimator.calculation.comparison_enhanced import compare_regions_enhanced
from tax_estimator.calculation.countries.au import AUCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import AUTaxInput, InternationalTaxInput

D = Decimal


def _calc(breakdown: IncomeBreakdown | None = None, gross: str | None = None, **profile):
    if breakdown is None:
        breakdown = IncomeBreakdown(employment_wages=D(gross))
    tax_input = InternationalTaxInput(
        country_code="AU",
        tax_year=2025,
        gross_income=breakdown.total,
        income_breakdown=breakdown,
        au=AUTaxInput(**profile) if profile else None,
    )
    return AUCalculator().calculate(tax_input)


def test_low_salary_26_5k_reference():
    # Tax = (26,500 - 18,200) x 16% = 1,328 - LITO 700 = 628 ; Medicare 0 (< 28,011)
    r = _calc(gross="26500")
    assert r.total_tax == D("628.00")


def test_low_salary_30k_medicare_shade_in():
    # Tax = 11,800 x 16% = 1,888 - 700 = 1,188 ; Medicare = min(600, 10% x 1,989) = 198.90
    r = _calc(gross="30000")
    assert r.income_tax == D("1188.00")
    assert r.other_taxes == D("198.90")
    assert r.total_tax == D("1386.90")


def test_mid_salary_90k():
    # Tax = 4,288 + 45,000 x 30% = 17,788 ; LITO 0 ; Medicare 1,800 ; MLS 0 (< 101,000)
    r = _calc(gross="90000")
    assert r.total_tax == D("19588.00")


def test_high_salary_120k_mls_assumption_and_private_cover():
    # Tax = 4,288 + 75,000 x 30% = 26,788 ; Medicare 2,400 ;
    # MLS 1.25% (120,000 > 118,000) x 120,000 = 1,500
    r = _calc(gross="120000")
    assert r.total_tax == D("30688.00")
    assert any("no private hospital cover" in n for n in r.calculation_notes)
    covered = _calc(gross="120000", has_private_health=True)
    assert covered.total_tax == D("29188.00")


def test_salary_and_foreign_dividends():
    # Compare breakdown dividends are US-sourced -> unfranked foreign dividends.
    # 100,000 salary + 20,000 dividends: taxable 120,000, no gross-up, no franking credit
    # Tax = 4,288 + 75,000 x 30% = 26,788 ; LITO 0 ; Medicare 2,400 ; MLS 1.25% = 1,500
    bd = IncomeBreakdown(employment_wages=D("100000"), dividends_qualified=D("20000"))
    r = _calc(bd)
    assert r.taxable_income == D("120000.00")
    assert r.income_tax == D("26788.00")
    assert r.other_taxes == D("3900.00")
    assert r.total_tax == D("30688.00")
    assert not any("FRANKING" in c.component_id for c in r.breakdown)
    assert any("foreign income tax offset" in n for n in r.calculation_notes)
    # qualified vs ordinary label makes no difference for foreign dividends
    ordinary = _calc(IncomeBreakdown(employment_wages=D("100000"), dividends_ordinary=D("20000")))
    assert ordinary.total_tax == r.total_tax


def test_foreign_dividends_and_discounted_gains_not_zero_tax():
    # Review case: 20,000 dividends + 30,000 LT gains (previously 0 via franking).
    # Taxable = 20,000 + 30,000 x 50% = 35,000 ; tax = 16,800 x 16% = 2,688 - LITO 700
    # = 1,988 ; Medicare = min(2% x 35,000 = 700, 10% x 6,989 = 698.90) -> total 2,686.90
    r = _calc(IncomeBreakdown(
        dividends_qualified=D("20000"), capital_gains_long_term=D("30000"),
    ))
    assert r.income_tax == D("1988.00")
    assert r.total_tax == D("2686.90")
    assert not r.warnings


def test_non_resident_salary():
    r = _calc(gross="100000", is_resident=False)
    assert r.total_tax == D("30000.00")  # 30% from $1, no LITO, no Medicare


def test_compare_path_parity():
    bd = IncomeBreakdown(employment_wages=D("100000"), dividends_qualified=D("20000"))
    region = compare_regions_enhanced(["AU"], bd, base_currency="AUD").regions[0]
    assert region.total_tax_local == _calc(bd).total_tax == D("30688.00")


def test_help_marginal_repayment_2025_26():
    # (90,000 - 67,000) x 15% = 3,450 < 10% x 90,000 -> 3,450
    r = _calc(gross="90000", has_help_debt=True)
    help_part = next(c for c in r.breakdown if c.component_id == "AU-HELP")
    assert help_part.amount == D("3450.00")
    assert r.total_tax == D("23038.00")  # 19,588 + 3,450


def test_period_label_is_2025_26():
    r = _calc(gross="50000")
    assert any("2025-26" in n for n in r.calculation_notes)
