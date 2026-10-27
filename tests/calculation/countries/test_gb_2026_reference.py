"""
United Kingdom 2026/27 reference tests (tax_year=2026 = 6 April 2026 - 5 April 2027).

Hand calculations from primary sources (retrieved 2026-10-27):
- Personal Allowance £12,570 (taper above £100,000), basic band £37,700,
  higher to £125,140, 20/40/45%; dividend allowance £500 and dividend rates
  10.75% / 35.75% / 39.35% for 2026/27:
  https://www.gov.uk/government/publications/rates-and-allowances-income-tax/income-tax-rates-and-allowances-current-and-past
  https://www.gov.uk/government/publications/income-tax-changes-to-tax-rates-for-property-savings-and-dividend-income/income-tax-changes-to-tax-rates-for-property-savings-and-dividend-income
- Savings rates stay 20/40/45% until April 2027; PSA £1,000 basic / £500 higher:
  https://www.gov.uk/apply-tax-free-interest-on-savings/how-much-is-tax-free
- Class 1 employee NI: 8% between £12,570 and £50,270, 2% above; student loan
  thresholds (Plan 2 £29,385 at 9%); Scottish bands (taxable income: 19% to
  £3,967, 20% to £16,956, 21% to £31,092, 42% to £62,430, 45% to £125,140, 48%):
  https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2026-to-2027
- CGT: £3,000 annual exempt amount, 18% / 24%:
  https://www.gov.uk/guidance/capital-gains-tax-rates-and-allowances
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.countries.base import UnsupportedIncomeError
from tax_estimator.calculation.countries.gb import GBCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import (
    InternationalTaxInput,
    UKStudentLoanPlanType,
    UKTaxInput,
    UKTaxRegion,
)

D = Decimal


def _calc(breakdown: IncomeBreakdown, uk: UKTaxInput | None = None, year: int = 2026):
    return GBCalculator().calculate(
        InternationalTaxInput(
            country_code="GB",
            tax_year=year,
            currency_code="GBP",
            gross_income=breakdown.total,
            income_breakdown=breakdown,
            uk=uk,
        )
    )


def _wages(amount: str, uk: UKTaxInput | None = None):
    return _calc(IncomeBreakdown(employment_wages=D(amount)), uk)


def test_wages_40k():
    # Taxable 40,000 - 12,570 = 27,430 x 20% = 5,486.00
    # NI (40,000 - 12,570) x 8% = 2,194.40
    r = _wages("40000")
    assert r.income_tax == D("5486.00")
    assert r.social_insurance == D("2194.40")
    assert r.total_tax == D("7680.40")


def test_wages_100k():
    # Taxable 87,430: 37,700 x 20% = 7,540 + 49,730 x 40% = 19,892 -> 27,432
    # NI 37,700 x 8% = 3,016 + 49,730 x 2% = 994.60 -> 4,010.60
    r = _wages("100000")
    assert r.income_tax == D("27432.00")
    assert r.social_insurance == D("4010.60")


def test_wages_250k_allowance_fully_tapered():
    # PA nil (ANI >= 125,140). 7,540 + 87,440 x 40% (34,976) + 124,860 x 45% (56,187)
    # = 98,703 ; NI 3,016 + 199,730 x 2% (3,994.60) = 7,010.60
    r = _wages("250000")
    assert r.income_tax == D("98703.00")
    assert r.social_insurance == D("7010.60")
    assert r.total_tax == D("105713.60")


def test_mixed_wages_interest_dividends_gains():
    # Wages 60,000 + interest 2,000 + dividends 10,000 + gains 20,000.
    # Non-savings taxable 47,430: 7,540 + 9,730 x 40% (3,892) = 11,432
    # Higher-rate taxpayer: PSA 500; 1,500 x 40% = 600
    # Dividends: 500 allowance; 9,500 x 35.75% = 3,396.25
    # Income tax 15,428.25 ; CGT (20,000 - 3,000) x 24% = 4,080 (no basic band left)
    # NI 3,016 + 9,730 x 2% (194.60) = 3,210.60
    bd = IncomeBreakdown(
        employment_wages=D("60000"),
        interest=D("2000"),
        dividends_ordinary=D("10000"),
        capital_gains_long_term=D("20000"),
    )
    r = _calc(bd)
    div = next(x for x in r.breakdown if x.component_id == "GB-IT-DIVIDENDS")
    assert div.amount == D("3396.25")
    assert r.income_tax == D("19508.25")  # Income Tax + CGT
    assert r.social_insurance == D("3210.60")


def test_dividends_only_use_new_ordinary_rate():
    # 20,000 dividends: PA 12,570 + allowance 500 -> 6,930 x 10.75% = 744.975 -> 744.98
    r = _calc(IncomeBreakdown(dividends_ordinary=D("20000")))
    assert r.income_tax == D("744.98")
    assert r.social_insurance == 0


def test_scotland_40k():
    # Taxable 27,430: 3,967 x 19% (753.73) + 12,989 x 20% (2,597.80)
    # + 10,474 x 21% (2,199.54) = 5,551.07
    r = _wages("40000", UKTaxInput(tax_region=UKTaxRegion.SCOTLAND))
    assert r.income_tax == D("5551.07")
    assert r.social_insurance == D("2194.40")


def test_plan_2_student_loan_40k():
    # (40,000 - 29,385) x 9% = 955.35
    r = _wages("40000", UKTaxInput(student_loan_plan=UKStudentLoanPlanType.PLAN_2))
    assert r.other_taxes == D("955.35")


def test_period_label_and_no_provisional_warnings():
    r = _wages("40000")
    assert any("2026/27" in n for n in r.calculation_notes)
    assert r.warnings == []


def test_self_employment_refused_for_2026():
    with pytest.raises(UnsupportedIncomeError):
        _calc(IncomeBreakdown(self_employment=D("40000")))


def test_unknown_year_fails_closed():
    with pytest.raises(ValueError, match="No GB rules for tax year 2027"):
        _calc(IncomeBreakdown(employment_wages=D("40000")), year=2027)
