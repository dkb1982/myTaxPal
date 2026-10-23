"""
Hong Kong 2025/26 year of assessment reference tests.

Period semantics: tax_year=2025 means the 2025/26 year of assessment
(1 April 2025 - 31 March 2026). Sources:
- Progressive rates 2/6/10/14/17% on HK$50,000 bands; two-tier standard rate
  15% on first HK$5M and 16% above (from 2024/25); basic allowance 132,000,
  married 264,000, child 130,000 each, dependent parent (60+) 50,000:
  https://www.ird.gov.hk/eng/tax/ind_stp.htm
- MPF employee 5% of relevant income, nil below HK$7,100/month, capped at
  HK$1,500/month (HK$18,000/year deduction cap).
- One-off 2025/26 reduction 100% capped at HK$3,000, enacted (LegCo passed
  13 May 2026; gazetted 22 May 2026):
  https://www.ird.gov.hk/eng/ppr/archives/26051303.htm
  (covers salaries tax, tax under personal assessment and profits tax only;
  not property tax)
- Property Tax: 15% standard rate on net assessable value = rent less 20%
  statutory allowance for repairs and outgoings (IRD FAQ 2025/26 example:
  240,000 -> NAV 192,000 -> 28,800):
  https://www.ird.gov.hk/eng/faq/pty.htm
  https://www.ird.gov.hk/eng/tax/bir57se_notes.htm
"""

from decimal import Decimal

from tax_estimator.calculation.comparison_enhanced import compare_regions_enhanced
from tax_estimator.calculation.countries.hk import HKCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import HKTaxInput, InternationalTaxInput


def _calc(gross: str, **kwargs):
    return HKCalculator().calculate(
        InternationalTaxInput(
            country_code="HK", tax_year=2025, currency_code="HKD",
            gross_income=Decimal(gross), **kwargs,
        )
    )


def test_single_300k():
    # MPF: monthly relevant income 25,000 x 5% = 1,250 x 12 = 15,000
    # NCI = 300,000 - 15,000 - 132,000 = 153,000
    # Progressive = 1,000 + 3,000 + 5,000 + 3,000 x 14% (420) = 9,420
    # Standard = 285,000 x 15% = 42,750 -> progressive applies
    # Less one-off reduction min(9,420, 3,000) -> 6,420
    r = _calc("300000")
    assert r.social_insurance == Decimal("15000.00")
    assert r.income_tax == Decimal("6420.00")


def test_single_150k_fully_relieved_by_reduction():
    # MPF 12,500 x 5% = 625 x 12 = 7,500
    # NCI = 150,000 - 7,500 - 132,000 = 10,500 -> 2% = 210 -> reduction 210 -> 0
    r = _calc("150000")
    assert r.social_insurance == Decimal("7500.00")
    assert r.income_tax == Decimal("0.00")


def test_single_6m_two_tier_standard_rate():
    # MPF capped 18,000; net income 5,982,000
    # Standard = 5,000,000 x 15% + 982,000 x 16% = 750,000 + 157,120 = 907,120
    # Progressive on 5,850,000 = 16,000 + 5,650,000 x 17% = 976,500
    # Lower = 907,120 - 3,000 = 904,120
    r = _calc("6000000")
    assert r.income_tax == Decimal("904120.00")
    assert r.marginal_rate == Decimal("0.16")


def test_married_two_children_dependent_parent_800k():
    # MPF 18,000; allowances 264,000 + 2 x 130,000 + 50,000 = 574,000
    # NCI = 800,000 - 18,000 - 574,000 = 208,000
    # Progressive = 16,000 + 8,000 x 17% (1,360) = 17,360; standard 117,300
    # Less reduction 3,000 -> 14,360
    r = _calc(
        "800000",
        hk=HKTaxInput(is_married=True, num_children=2, has_dependent_parent=True),
    )
    assert r.income_tax == Decimal("14360.00")


def test_investment_income_not_salaries_tax():
    bd = IncomeBreakdown(
        employment_wages=Decimal("300000"),
        dividends_qualified=Decimal("50000"),
        capital_gains_long_term=Decimal("100000"),
    )
    r = _calc("450000", income_breakdown=bd)
    assert r.income_tax == Decimal("6420.00")
    assert r.social_insurance == Decimal("15000.00")


def test_salary_and_rental_property_tax():
    # Salaries tax as test_single_300k: 9,420 - 3,000 reduction = 6,420 ; MPF 15,000
    # Property Tax: NAV = 120,000 - 20% (24,000) = 96,000 x 15% = 14,400 (no reduction)
    # Total = 6,420 + 15,000 + 14,400 = 35,820
    bd = IncomeBreakdown(employment_wages=Decimal("300000"), rental=Decimal("120000"))
    r = _calc("420000", income_breakdown=bd)
    assert r.income_tax == Decimal("6420.00")
    assert r.other_taxes == Decimal("14400.00")
    assert r.total_tax == Decimal("35820.00")
    prop = next(c for c in r.breakdown if c.component_id == "HK-PROPERTY-TAX")
    assert prop.base == Decimal("96000.00")


def test_property_tax_ird_worked_example():
    # IRD FAQ 2025/26: rent 240,000 -> property tax 28,800 (no salary)
    r = _calc("240000", income_breakdown=IncomeBreakdown(rental=Decimal("240000")))
    assert r.income_tax == Decimal("0.00")
    assert r.total_tax == Decimal("28800.00")


def test_rental_compare_path_parity():
    bd = IncomeBreakdown(employment_wages=Decimal("300000"), rental=Decimal("120000"))
    direct = _calc("420000", income_breakdown=bd)
    region = compare_regions_enhanced(regions=["HK"], income=bd, base_currency="HKD").regions[0]
    assert region.total_tax_local == direct.total_tax == Decimal("35820.00")


def test_period_label_in_notes():
    assert any("2025/26" in n for n in _calc("300000").calculation_notes)


def test_compare_path_parity():
    bd = IncomeBreakdown(employment_wages=Decimal("300000"))
    direct = _calc("300000", income_breakdown=bd)
    compared = compare_regions_enhanced(regions=["HK"], income=bd, base_currency="HKD")
    region = compared.regions[0]
    assert region.total_tax_local == direct.total_tax == Decimal("21420.00")
