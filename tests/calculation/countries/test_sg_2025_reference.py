"""
Singapore 2025 income (YA2026) reference tests.

Period semantics: tax_year=2025 means income earned in calendar 2025, assessed
in Year of Assessment 2026. Expected values are hand-calculated from primary sources:
- Resident rates (YA2024 onwards), non-resident 15%-or-resident-rates on
  employment income, 24% on other income; rebates listed only to YA2025:
  https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates
- No Personal Income Tax Rebate in the IRAS YA2026 sample calculations:
  https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/sample-income-tax-calculations
- Earned income relief S$1,000 (<55), S$6,000 (55-59), S$8,000 (60+).
- CPF employee rates from 1 Jan 2025 (55 and below 20%, >55-60 17%, >60-65
  11.5%, >65-70 7.5%, >70 5%), OW ceiling S$7,400/month in 2025, annual
  salary ceiling S$102,000 (AW ceiling = 102,000 - OW subject to CPF):
  https://www.cpf.gov.sg/content/dam/web/employer/employer-obligations/documents/CPF_contribution_rates_from_1_Jan_2025.pdf
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
    # CPF: OW 100,000 capped at 7,400 x 12 = 88,800 x 20% = 17,760
    # Chargeable = 100,000 - EIR 1,000 - CPF 17,760 = 81,240
    # Tax = 3,350 (first 80k) + 1,240 x 11.5% (142.60) = 3,492.60 ; no YA2026 rebate
    r = _calc("100000", sg=SGTaxInput(age=35))
    assert r.social_insurance == Decimal("17760.00")
    assert r.income_tax == Decimal("3492.60")
    assert r.total_tax == Decimal("21252.60")
    assert not any(c.component_id == "SG-REBATE" for c in r.breakdown)


def test_bonus_subject_to_additional_wage_ceiling_age_57():
    # OW 120,000 -> 88,800 subject; AW ceiling 102,000 - 88,800 = 13,200
    # Bonus 30,000 -> 13,200 subject; CPF (age 57: 17%) = 102,000 x 17% = 17,340
    # Chargeable = 150,000 - EIR 6,000 - 17,340 = 126,660
    # Tax = 7,950 + 6,660 x 15% (999) = 8,949
    r = _calc(
        "150000",
        sg=SGTaxInput(age=57, employment_income=Decimal("120000"), bonus_income=Decimal("30000")),
    )
    assert r.social_insurance == Decimal("17340.00")
    assert r.income_tax == Decimal("8949.00")


def test_age_55_pays_20_percent_and_gets_55_59_relief():
    # "55 and below" -> 20% CPF: 88,800 x 20% = 17,760; EIR 6,000 (55-59)
    # Chargeable = 100,000 - 6,000 - 17,760 = 76,240
    # Tax = 550 + 36,240 x 7% (2,536.80) = 3,086.80
    r55 = _calc("100000", sg=SGTaxInput(age=55))
    assert r55.social_insurance == Decimal("17760.00")
    assert r55.income_tax == Decimal("3086.80")
    # Age 56 ("above 55 to 60") -> 17%: 88,800 x 17% = 15,096
    # Chargeable = 100,000 - 6,000 - 15,096 = 78,904
    # Tax = 550 + 38,904 x 7% (2,723.28) = 3,273.28
    r56 = _calc("100000", sg=SGTaxInput(age=56))
    assert r56.social_insurance == Decimal("15096.00")
    assert r56.income_tax == Decimal("3273.28")


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
    # Wages 80,000 -> CPF 80,000 x 20% = 16,000 (below the 88,800 OW cap)
    # Interest (approved bank), dividends (one-tier), gains: not taxed
    # Assessable = 80,000 + rental 12,000 = 92,000
    # Chargeable = 92,000 - EIR 1,000 - CPF 16,000 = 75,000
    # Tax = 550 + 35,000 x 7% (2,450) = 3,000 (no YA2026 rebate)
    bd = IncomeBreakdown(
        employment_wages=Decimal("80000"),
        interest=Decimal("10000"),
        dividends_qualified=Decimal("20000"),
        capital_gains_long_term=Decimal("50000"),
        rental=Decimal("12000"),
    )
    r = _calc("172000", income_breakdown=bd)
    assert r.social_insurance == Decimal("16000.00")
    assert r.income_tax == Decimal("3000.00")


def test_period_label_in_notes():
    r = _calc("50000")
    assert any("YA2026" in n and "2025" in n for n in r.calculation_notes)


def test_compare_path_parity():
    bd = IncomeBreakdown(employment_wages=Decimal("100000"))
    direct = _calc("100000", income_breakdown=bd)
    compared = compare_regions_enhanced(regions=["SG"], income=bd, base_currency="SGD")
    region = compared.regions[0]
    assert region.total_tax_local == direct.total_tax == Decimal("21252.60")
    assert region.international_breakdown.income_tax == direct.income_tax
    assert region.international_breakdown.social_insurance == direct.social_insurance
