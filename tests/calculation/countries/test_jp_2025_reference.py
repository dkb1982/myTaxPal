"""
Japan 2025 income (令和7年分) reference tests.

Expected values are hand-calculated from primary sources, not copied from
calculator output. Sources:
- Employment income deduction (給与所得控除, 2025: min ¥650k; 別表第五 below
  ¥6.6M = salary rounded down to ¥4,000):
  https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1410.htm
- Basic deduction tiers 2025 (95/88/68/63/58万 ...):
  https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1199.htm
- Income tax quick-deduction table + 2.1% reconstruction tax:
  https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/2260.htm
- Kyokai Kenpo Tokyo 2025: health 9.91% (employee 4.955%), care 1.59% (0.795%):
  https://www.kyoukaikenpo.or.jp/about/business/insurance_rate/rate_prefectures/r07/index.html
- Employees' pension 18.3% (employee 9.15%), standard monthly cap ¥650,000.
- Employment insurance, general business, employee 5.5/1000 from April 2025:
  https://www.mhlw.go.jp/content/001401966.pdf
- Resident tax: basic deduction ¥430k (unchanged for 令和8年度), 6% municipal +
  4% prefectural, adjustment credit (min ¥1,500 + ¥1,000), per-capita ¥5,000
  (¥3,000 + ¥1,000 + ¥1,000 forest environment tax), non-taxable line ¥450k
  total income (salary ¥1.1M):
  https://www2.city.kyoto.lg.jp/shikai/img/iinkai/soumushoubou/R08/data/080525gyouzai.pdf

Rounding: premiums round 50 sen down / 51 sen up; taxable income rounded
down to ¥1,000; income tax + reconstruction tax rounded down to ¥100;
municipal and prefectural income levies each rounded down to ¥100.
"""

from decimal import Decimal

from tax_estimator.calculation.comparison_enhanced import compare_regions_enhanced
from tax_estimator.calculation.countries.jp import JPCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import (
    InternationalTaxInput,
    JPAgeCategory,
    JPTaxInput,
)


def _calc(gross: str, **kwargs):
    return JPCalculator().calculate(
        InternationalTaxInput(
            country_code="JP", tax_year=2025, currency_code="JPY",
            gross_income=Decimal(gross), **kwargs,
        )
    )


def _component(result, cid: str) -> Decimal:
    return next(c.amount for c in result.breakdown if c.component_id == cid)


def test_salary_6m_under_40():
    # Salary ¥6,000,000, monthly ¥500,000 -> standard monthly remuneration ¥500,000
    #   health  500,000 x 4.955% = 24,775 x 12 = 297,300
    #   pension 500,000 x 9.15%  = 45,750 x 12 = 549,000
    #   employment insurance 6,000,000 x 0.55% = 33,000      -> SI 879,300
    # Employment income: 6,000,000 x 80% - 440,000 = 4,360,000
    # Basic deduction (income 3.36M-4.89M band) = 680,000
    # Taxable = 4,360,000 - 879,300 - 680,000 = 2,800,700 -> 2,800,000
    # Income tax = 2,800,000 x 10% - 97,500 = 182,500
    # + 2.1% = 3,832 -> 186,332 -> 186,300 (reconstruction 3,800)
    # Resident taxable = 4,360,000 - 879,300 - 430,000 = 3,050,700 -> 3,050,000
    #   municipal 183,000 - 1,500 = 181,500; prefectural 122,000 - 1,000 = 121,000
    #   + per-capita 5,000 = 307,500
    # Total = 879,300 + 182,500 + 3,800 + 307,500 = 1,373,100
    # (The review's ~¥1,377,800 assumed a ¥630k basic deduction; NTA No.1199
    # gives ¥680k for total income of ¥4.36M.)
    r = _calc("6000000")
    assert r.social_insurance == Decimal("879300")
    assert r.income_tax == Decimal("182500")
    assert _component(r, "JP-RECON-TAX") == Decimal("3800")
    assert _component(r, "JP-RESIDENT-TAX") == Decimal("307500")
    assert r.total_tax == Decimal("1373100")


def test_salary_5m_age_40_to_64_includes_care_insurance():
    # Monthly 416,667 -> standard ¥410,000
    #   health 20,315.5 -> 20,315 x 12 = 243,780
    #   care   410,000 x 0.795% = 3,259.5 -> 3,259 x 12 = 39,108
    #   pension 37,515 x 12 = 450,180; EI 27,500        -> SI 760,568
    # Employment income 5,000,000 x 80% - 440,000 = 3,560,000; basic 680,000
    # Taxable = 3,560,000 - 760,568 - 680,000 = 2,119,432 -> 2,119,000
    # Tax = 211,900 - 97,500 = 114,400; +2,402 = 116,802 -> 116,800 (recon 2,400)
    # Resident taxable 3,560,000 - 760,568 - 430,000 = 2,369,432 -> 2,369,000
    #   municipal 142,140 - 1,500 -> 140,600; prefectural 94,760 - 1,000 -> 93,700
    #   + 5,000 = 239,300
    # Total = 760,568 + 114,400 + 2,400 + 239,300 = 1,116,668
    r = _calc("5000000", jp=JPTaxInput(age_category=JPAgeCategory.AGE_40_TO_64))
    assert _component(r, "JP-LTC") == Decimal("39108")
    assert r.social_insurance == Decimal("760568")
    assert r.income_tax == Decimal("114400")
    assert r.total_tax == Decimal("1116668")


def test_salary_8m_with_spouse_and_dependent():
    # Monthly 666,667 -> health grade ¥680,000, pension capped at ¥650,000
    #   health 680,000 x 4.955% = 33,694 x 12 = 404,328
    #   pension 650,000 x 9.15% = 59,475 x 12 = 713,700; EI 44,000 -> SI 1,162,028
    # Employment deduction 8,000,000 x 10% + 1,100,000 = 1,900,000 -> 6,100,000
    # Basic (4.89M-6.55M) 630,000; spouse 380,000; dependent 380,000
    # Taxable = 6,100,000 - 1,162,028 - 1,390,000 = 3,547,972 -> 3,547,000
    # Tax = 709,400 - 427,500 = 281,900; +5,919 = 287,819 -> 287,800 (recon 5,900)
    # Resident: 430,000 + 330,000 + 330,000 -> taxable 3,847,972 -> 3,847,000
    #   municipal 230,820 - 1,500 -> 229,300; prefectural 153,880 - 1,000 -> 152,800
    #   + 5,000 = 387,100
    # Total = 1,162,028 + 281,900 + 5,900 + 387,100 = 1,836,928
    r = _calc("8000000", jp=JPTaxInput(has_spouse=True, num_dependents=1))
    assert r.social_insurance == Decimal("1162028")
    assert r.income_tax == Decimal("281900")
    assert r.total_tax == Decimal("1836928")


def test_spouse_above_580k_gets_no_spouse_deduction():
    r = _calc("8000000", jp=JPTaxInput(has_spouse=True, spouse_income=Decimal("600000")))
    assert not any(c.component_id == "JP-SPOUSE-DED" for c in r.breakdown)
    r2 = _calc("8000000", jp=JPTaxInput(has_spouse=True, spouse_income=Decimal("580000")))
    assert _component(r2, "JP-SPOUSE-DED") == Decimal("-380000")


def test_bonus_profile_uses_bonus_premium_bases():
    # Regular salary 5,000,000 (std ¥410,000) + one bonus of 1,000,000
    #   health 243,780 + 1,000,000 x 4.955% = 49,550
    #   pension 450,180 + 1,000,000 x 9.15% = 91,500; EI 6,000,000 x 0.55% = 33,000
    #   SI = 868,010
    # Employment income on total salary 6,000,000 = 4,360,000; basic 680,000
    # Taxable 2,811,990 -> 2,811,000; tax 183,600; +3,855 = 187,455 -> 187,400
    # Resident taxable 3,061,990 -> 3,061,000: 182,160 -> 182,100; 121,440 -> 121,400
    #   + 5,000 = 308,500
    # Total = 868,010 + 183,600 + 3,800 + 308,500 = 1,363,910
    r = _calc(
        "6000000",
        jp=JPTaxInput(employment_income=Decimal("5000000"), bonus_income=Decimal("1000000")),
    )
    assert r.social_insurance == Decimal("868010")
    assert r.total_tax == Decimal("1363910")


def test_investment_income_taxed_separately_at_20_315_percent():
    # Salary part identical to test_salary_6m_under_40 (1,373,100), plus
    #   dividends 1,000,000: 150,000 + 3,150 + 50,000 = 203,150
    #   gains       500,000:  75,000 + 1,575 + 25,000 = 101,575
    #   interest    100,000:  15,000 +   315 +  5,000 =  20,315
    # No social insurance on investment income.
    # Total = 1,373,100 + 325,040 = 1,698,140
    bd = IncomeBreakdown(
        employment_wages=Decimal("6000000"),
        dividends_ordinary=Decimal("1000000"),
        capital_gains_long_term=Decimal("500000"),
        interest=Decimal("100000"),
    )
    r = _calc("7600000", income_breakdown=bd)
    assert r.social_insurance == Decimal("879300")
    assert r.total_tax == Decimal("1698140")
    assert r.income_tax == Decimal("182500") + Decimal("150000") + Decimal("75000") + Decimal(
        "15000"
    )


def test_salary_1_1m_is_at_resident_tax_non_taxable_line():
    # Monthly 91,667 -> standard ¥88,000 (enrolled at >= ¥88,000/month)
    #   health 88,000 x 4.955% = 4,360.4 -> 4,360 x 12 = 52,320
    #   pension 88,000 x 9.15% = 8,052 x 12 = 96,624; EI 6,050 -> SI 154,994
    # Employment income 1,100,000 - 650,000 = 450,000 (<= ¥450k: no resident tax)
    # Income tax: 450,000 - 950,000 basic deduction < 0 -> 0
    r = _calc("1100000")
    assert r.social_insurance == Decimal("154994")
    assert r.income_tax == Decimal("0")
    assert r.other_taxes == Decimal("0")
    assert r.total_tax == Decimal("154994")


def test_compare_path_parity():
    bd = IncomeBreakdown(
        employment_wages=Decimal("6000000"),
        dividends_qualified=Decimal("1000000"),
        capital_gains_short_term=Decimal("500000"),
        interest=Decimal("100000"),
    )
    direct = _calc("7600000", income_breakdown=bd)
    compared = compare_regions_enhanced(regions=["JP"], income=bd, base_currency="JPY")
    region = compared.regions[0]
    assert region.total_tax_local == direct.total_tax == Decimal("1698140")
    assert region.international_breakdown.income_tax == direct.income_tax
    assert region.international_breakdown.social_insurance == direct.social_insurance
    assert region.international_breakdown.other_taxes == direct.other_taxes
