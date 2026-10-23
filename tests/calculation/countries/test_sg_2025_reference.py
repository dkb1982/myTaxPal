"""
Singapore YA2025 (2024 income) reference tests.

Period semantics: tax_year=2025 means Year of Assessment 2025, income earned in
calendar 2024. Expected values are hand-calculated from primary sources:
- Resident rates (YA2024 onwards), non-resident 15%-or-resident-rates on
  employment income, 24% on other income, YA2025 rebate 60% capped at S$200:
  https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates
- Earned income relief S$1,000 (<55), S$6,000 (55-59), S$8,000 (60+):
  https://www.iras.gov.sg/taxes/individual-income-tax/employees/deductions-for-individuals/personal-reliefs-and-tax-rebates/earned-income-relief
- CPF employee rates from 1 Jan 2024 (55 and below 20%, >55-60 16%, >60-65
  10.5%, >65-70 7.5%, >70 5%), OW ceiling S$6,800/month in 2024, annual
  salary ceiling S$102,000 (AW ceiling = 102,000 - OW subject to CPF):
  https://www.cpf.gov.sg/content/dam/web/employer/employer-obligations/documents/CPF_contribution_rates_from_1_Jan_2024.pdf
"""

from decimal import Decimal

from tax_estimator.calculation.comparison_enhanced import compare_regions_enhanced
from tax_estimator.calculation.countries.sg import SGCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import (
    InternationalTaxInput,
    SGResidentStatus,
    SGTaxInput,
)


def _calc(gross: str, **kwargs):
    return SGCalculator().calculate(
        InternationalTaxInput(
            country_code="SG", tax_year=2025, currency_code="SGD",
            gross_income=Decimal(gross), **kwargs,
        )
    )


def test_citizen_100k_age_35():
    # CPF: OW 100,000 capped at 6,800 x 12 = 81,600 x 20% = 16,320
    # Chargeable = 100,000 - EIR 1,000 - CPF 16,320 = 82,680
    # Tax = 3,350 (first 80k) + 2,680 x 11.5% (308.20) = 3,658.20
    # Rebate = min(60% x 3,658.20, 200) = 200 -> 3,458.20
    r = _calc("100000", sg=SGTaxInput(age=35))
    assert r.social_insurance == Decimal("16320.00")
    assert r.income_tax == Decimal("3458.20")
    assert r.total_tax == Decimal("19778.20")


def test_bonus_subject_to_additional_wage_ceiling_age_57():
    # OW 120,000 -> 81,600 subject; AW ceiling 102,000 - 81,600 = 20,400
    # Bonus 30,000 -> 20,400 subject; CPF (age 57: 16%) = 102,000 x 16% = 16,320
    # Chargeable = 150,000 - EIR 6,000 - 16,320 = 127,680
    # Tax = 7,950 + 7,680 x 15% (1,152) = 9,102 - rebate 200 = 8,902
    r = _calc(
        "150000",
        sg=SGTaxInput(age=57, employment_income=Decimal("120000"), bonus_income=Decimal("30000")),
    )
    assert r.social_insurance == Decimal("16320.00")
    assert r.income_tax == Decimal("8902.00")


def test_age_55_pays_20_percent_and_gets_55_59_relief():
    # "55 and below" -> 20% CPF: 81,600 x 20% = 16,320; EIR 6,000 (55-59)
    # Chargeable = 100,000 - 6,000 - 16,320 = 77,680
    # Tax = 550 + 37,680 x 7% (2,637.60) = 3,187.60 - 200 = 2,987.60
    r55 = _calc("100000", sg=SGTaxInput(age=55))
    assert r55.social_insurance == Decimal("16320.00")
    assert r55.income_tax == Decimal("2987.60")
    # Age 56 ("above 55 to 60") -> 16%: 81,600 x 16% = 13,056
    # Chargeable = 100,000 - 6,000 - 13,056 = 80,944
    # Tax = 3,350 + 944 x 11.5% (108.56) = 3,458.56 - 200 = 3,258.56
    r56 = _calc("100000", sg=SGTaxInput(age=56))
    assert r56.social_insurance == Decimal("13056.00")
    assert r56.income_tax == Decimal("3258.56")


def test_non_resident_higher_of_15_percent_or_resident_rates():
    # 100,000: 15% = 15,000 > resident rates without reliefs (5,650) -> 15,000
    nr = SGTaxInput(resident_status=SGResidentStatus.NON_RESIDENT, is_citizen_or_pr=False)
    r = _calc("100000", sg=nr)
    assert r.income_tax == Decimal("15000.00")
    assert r.social_insurance == Decimal("0")
    # 600,000: resident rates 84,150 + 100,000 x 23% = 107,150 > 90,000 (15%)
    r2 = _calc("600000", sg=nr)
    assert r2.income_tax == Decimal("107150.00")


def test_investment_income_exempt_rental_taxed():
    # Wages 80,000 -> CPF 80,000 x 20% = 16,000 (below the 81,600 OW cap)
    # Interest (approved bank), dividends (one-tier), gains: not taxed
    # Assessable = 80,000 + rental 12,000 = 92,000
    # Chargeable = 92,000 - EIR 1,000 - CPF 16,000 = 75,000
    # Tax = 550 + 35,000 x 7% (2,450) = 3,000 - rebate 200 = 2,800
    bd = IncomeBreakdown(
        employment_wages=Decimal("80000"),
        interest=Decimal("10000"),
        dividends_qualified=Decimal("20000"),
        capital_gains_long_term=Decimal("50000"),
        rental=Decimal("12000"),
    )
    r = _calc("172000", income_breakdown=bd)
    assert r.social_insurance == Decimal("16000.00")
    assert r.income_tax == Decimal("2800.00")


def test_period_label_in_notes():
    r = _calc("50000")
    assert any("YA2025" in n and "2024" in n for n in r.calculation_notes)


def test_compare_path_parity():
    bd = IncomeBreakdown(employment_wages=Decimal("100000"))
    direct = _calc("100000", income_breakdown=bd)
    compared = compare_regions_enhanced(regions=["SG"], income=bd, base_currency="SGD")
    region = compared.regions[0]
    assert region.total_tax_local == direct.total_tax == Decimal("19778.20")
    assert region.international_breakdown.income_tax == direct.income_tax
    assert region.international_breakdown.social_insurance == direct.social_insurance
