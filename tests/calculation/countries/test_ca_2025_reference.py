"""
Canada 2025 reference tests (hand-calculated from CRA 2025 forms).

Sources:
- CRA 2025 rates (federal 14.5% blended lowest rate; ON, BC, AB brackets):
  https://www.canada.ca/en/revenue-agency/services/tax/individuals/tax-rates-brackets/last-year.html
- CRA indexation (BPA 16,129 / 14,538; Canada employment amount 1,471):
  https://www.canada.ca/en/revenue-agency/services/tax/individuals/frequently-asked-questions-individuals/adjustment-personal-income-tax-benefit-amounts.html
- ON428 2025 (BPA 12,747; surtax 20%/36% over 5,710/7,307; reduction 294; OHP chart):
  https://www.canada.ca/content/dam/cra-arc/formspubs/pbg/5006-c/5006-c-25e.pdf
- ON428-A 2025 (LIFT max 875, 5% over 32,500); Worksheet ON428 (DTC 10% / 2.9863%)
- BC428 2025 (BPA 12,932; reduction 562, 3.56% over 25,020); AB428 2025 (BPA 22,323, 8%)
- Foreign dividends: fully included in income, no gross-up or dividend tax
  credit (those apply to taxable Canadian corporations only); foreign tax
  credit not modelled:
  https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/personal-income/line-12100-interest-other-investment-income.html
  https://www.canada.ca/en/revenue-agency/services/tax/individuals/topics/about-your-tax-return/tax-return/completing-a-tax-return/deductions-credits-expenses/line-40425-federal-dividend-tax-credit.html
- CPP 2025: YMPE 71,300, exemption 3,500, 5.95% (4.95% base credit + 1% enhanced
  deduction); CPP2 4% to 81,200; EI 1.64% to 65,700.

Common payroll working for salaries >= 81,200 / 80,000:
  CPP 4,034.10 (base 3,356.10, enhanced 678.00); EI 1,077.48;
  CPP2 at 80k = 8,700 x 4% = 348.00.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.comparison_enhanced import compare_regions_enhanced
from tax_estimator.calculation.countries.ca import CACalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import CATaxInput, InternationalTaxInput

D = Decimal
TOL = D("0.05")


def _calc(breakdown: IncomeBreakdown | None = None, gross: str | None = None, **profile):
    if breakdown is None:
        breakdown = IncomeBreakdown(employment_wages=D(gross))
    tax_input = InternationalTaxInput(
        country_code="CA",
        tax_year=2025,
        gross_income=breakdown.total,
        income_breakdown=breakdown,
        ca=CATaxInput(**profile) if profile else None,
    )
    return CACalculator().calculate(tax_input)


def test_low_salary_30k_ontario():
    # CPP = 26,500 x 5.95% = 1,576.75 (base 1,311.75, enhanced 265) ; EI = 492.00
    # Net income = 30,000 - 265 = 29,735
    # Federal: 29,735 x 14.5% = 4,311.58 - (16,129 + 1,471 + 1,311.75 + 492) x 14.5%
    #          (2,813.54) = 1,498.03
    # Ontario: 29,735 x 5.05% = 1,501.62 - (12,747 + 1,311.75 + 492) x 5.05% (734.81)
    #          = 766.81 ; reduction max(0, 588 - 766.81) = 0 ; LIFT = 875 - 0 -> ON tax 0
    # OHP (25k-36k) = 300
    r = _calc(gross="30000")
    assert r.social_insurance == D("2068.75")
    assert abs(r.income_tax - D("1498.03")) <= TOL
    assert r.other_taxes == D("300.00")
    assert abs(r.total_tax - D("3866.78")) <= TOL


def test_mid_salary_80k_ontario():
    # Net income = 80,000 - 678 - 348 = 78,974
    # Federal: 8,319.375 + 21,599 x 20.5% = 12,747.17
    #          - (16,129 + 1,471 + 3,356.10 + 1,077.48) x 14.5% (3,194.87) = 9,552.30
    # Ontario: 2,670.74 + 26,088 x 9.15% = 5,057.80
    #          - (12,747 + 3,356.10 + 1,077.48) x 5.05% (867.62) = 4,190.17 ; no surtax
    # OHP (72,600-200,000) = 750
    # Total = 9,552.30 + 4,190.17 + 750 + 4,034.10 + 348 + 1,077.48 = 19,952.05
    # NOTE: the review's "~20,102" is not reproduced; the 2025 forms give 19,952.
    r = _calc(gross="80000")
    assert abs(r.income_tax - D("13742.47")) <= TOL
    assert r.social_insurance == D("5459.58")
    assert abs(r.total_tax - D("19952.05")) <= TOL


def test_high_salary_200k_ontario_bpa_phase_down_and_surtax():
    # Net income = 200,000 - 678 - 396 = 198,926
    # Federal: 36,495.57 + 21,044 x 29% = 42,598.33
    #   BPA = 16,129 - 1,591 x 21,044 / 75,532 = 15,685.73
    #   credits (15,685.73 + 1,471 + 3,356.10 + 1,077.48) x 14.5% = 3,130.60 -> 39,467.73
    # Ontario: 2,670.74 + 4,839.34 + 4,935.51 + 48,926 x 12.16% = 18,395.00 - 867.62
    #   = 17,527.37 ; surtax 20% x 11,817.37 + 36% x 10,220.37 = 6,042.81 -> 23,570.18
    # OHP 750 ; payroll 4,034.10 + 396 + 1,077.48
    r = _calc(gross="200000")
    assert abs(r.income_tax - D("63037.91")) <= TOL
    assert abs(r.total_tax - D("69295.49")) <= TOL


def test_salary_and_foreign_dividends_ontario():
    # Compare breakdown dividends are US-sourced -> foreign dividends (no gross-up/DTC).
    # 80k salary: deductions enhanced CPP 678 + CPP2 348 = 1,026 -> 78,974
    # Taxable income = 78,974 + 10,000 = 88,974 ; no CPP/EI on dividends
    # Federal: 8,319.375 + 31,599 x 20.5% = 14,797.17 - 3,194.87 = 11,602.30
    # Ontario: 2,670.743 + 36,088 x 9.15% = 5,972.80 - 867.62 = 5,105.18 ; surtax 0,
    #          reduction 0, LIFT 0 ; OHP 750
    # Total = 11,602.30 + 5,105.18 + 750 + 5,459.58 = 22,917.06
    bd = IncomeBreakdown(employment_wages=D("80000"), dividends_qualified=D("10000"))
    r = _calc(bd)
    assert r.taxable_income == D("88974.00")
    assert r.social_insurance == D("5459.58")
    assert abs(r.income_tax - D("16707.48")) <= TOL
    assert abs(r.total_tax - D("22917.06")) <= TOL
    assert any("foreign tax credit" in n for n in r.calculation_notes)


def test_foreign_dividends_and_gains_no_dividend_credit():
    # Review case: 20,000 dividends + 30,000 gains (previously C$450 via eligible DTC).
    # Taxable = 20,000 + 15,000 = 35,000
    # Federal: 35,000 x 14.5% = 5,075 - 16,129 x 14.5% (2,338.705) = 2,736.30
    # Ontario: 35,000 x 5.05% = 1,767.50 - 12,747 x 5.05% (643.72) = 1,123.78 ;
    #          reduction max(0, 588 - 1,123.78) = 0 ; OHP min(300, 6% x 10,000) = 300
    r = _calc(IncomeBreakdown(
        dividends_qualified=D("20000"), capital_gains_long_term=D("30000"),
    ))
    assert abs(r.total_tax - D("4160.08")) <= TOL


def test_bc_and_ab_80k():
    # BC: 2,493.52 + 29,695 x 7.7% = 4,780.04 - (12,932 + 4,433.58) x 5.06% (878.70)
    #     = 3,901.34 ; reduction 0 (net income >= 40,807)
    bc = _calc(gross="80000", province="BC")
    assert abs(bc.total_tax - D("18913.22")) <= TOL
    # AB: 60,000 x 8% + 18,974 x 10% = 6,697.40 - (22,323 + 4,433.58) x 8% (2,140.53)
    #     = 4,556.87 ; supplemental credit 25% x max(0, 2,140.53 - 4,800) = 0
    ab = _calc(gross="80000", province="AB")
    assert abs(ab.total_tax - D("19568.75")) <= TOL


def test_self_employment_pays_both_cpp_halves_no_ei():
    # Pensionable 56,500: base 2 x 4.95% = 5,593.50 ; enhanced 2 x 1% = 1,130 -> 6,723.50
    r = _calc(IncomeBreakdown(self_employment=D("60000")))
    assert r.social_insurance == D("6723.50")
    assert not any(c.component_id == "CA-EI" for c in r.breakdown)


def test_unsupported_provinces_raise():
    with pytest.raises(ValueError, match="Quebec"):
        _calc(gross="80000", province="QC")
    with pytest.raises(ValueError, match="not supported"):
        _calc(gross="80000", province="XX")


def test_compare_path_parity():
    bd = IncomeBreakdown(
        employment_wages=D("80000"),
        dividends_qualified=D("5000"),
        dividends_ordinary=D("5000"),
        capital_gains_long_term=D("10000"),
    )
    region = compare_regions_enhanced(["CA"], bd, base_currency="CAD").regions[0]
    assert region.total_tax_local == _calc(bd).total_tax
    assert region.international_breakdown.social_insurance == D("5459.58")
