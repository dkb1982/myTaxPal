"""
Japan 2026 income (令和8年分) reference tests.

Expected values are hand-calculated from primary sources, not copied from
calculator output. Sources (retrieved 2026-10-27):
- NTA 令和8年分 年末調整のしかた (p.2-3 and the 給与所得控除後の給与等の金額の表):
  basic deduction 104万 (合計所得 ≤489万) / 67万 (≤655万) / 62万 (≤2,350万);
  employment income = salary - 740,000 for 741,000-2,190,999; fixed rows
  2,191,000-2,192,999 -> 1,451,000, 2,193,000-2,195,999 -> 1,453,000,
  2,196,000-2,199,999 -> 1,456,000; from 2.2M the unchanged 別表第五 formula.
  https://www.nta.go.jp/publication/pamph/gensen/nencho2026/pdf/nencho_all.pdf
- Income tax quick-deduction table unchanged; 2.1% reconstruction tax (x102.1%).
- Kyokai Kenpo Tokyo 令和8年度: health 9.85% (employee 4.925%), care 1.62%
  (0.81%), child support levy 0.23% (0.115%) from April 2026 premiums:
  https://www.kyoukaikenpo.or.jp/about/business/insurance_rate/rate_prefectures/r08/index.html
- Employees' pension 18.3% (employee 9.15%), standard monthly cap ¥650,000.
- Employment insurance 令和8年度, general business, employee 5/1000:
  https://jsite.mhlw.go.jp/yamagata-roudoukyoku/koyouhoken-20260316.html
- Resident tax 令和9年度: basic deduction ¥430k unchanged; 6% + 4%; adjustment
  credit (min ¥1,500 + ¥1,000); per-capita ¥5,000:
  https://www.city.sendai.jp/shiminze-kikaku/kurashi/tetsuzuki/zekin/kojin/kaisei/r8.html

Model conventions (as 2025): fiscal-year rates applied to all 12 months; the
child levy for 9 monthly premiums (April-December). Rounding: premiums round
50 sen down; taxable income down to ¥1,000; income tax + reconstruction tax
down to ¥100; municipal and prefectural levies each down to ¥100.
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.countries.base import UnsupportedIncomeError
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
            country_code="JP", tax_year=2026, currency_code="JPY",
            gross_income=Decimal(gross), **kwargs,
        )
    )


def _component(result, cid: str) -> Decimal:
    return next(c.amount for c in result.breakdown if c.component_id == cid)


def test_salary_4m():
    # Monthly 333,333 -> standard remuneration 340,000 (range 330,000-349,999)
    #   health  340,000 x 4.925% = 16,745 x 12 = 200,940
    #   pension 340,000 x 9.15%  = 31,110 x 12 = 373,320
    #   child levy 340,000 x 0.115% = 391 x 9 = 3,519
    #   employment insurance 4,000,000 x 0.5% = 20,000           -> SI 597,779
    # Employment income: 4,000,000 x 80% - 440,000 = 2,760,000
    # Basic deduction (≤ 4.89M) = 1,040,000
    # Taxable = 2,760,000 - 1,040,000 - 597,779 = 1,122,221 -> 1,122,000
    # Income tax 5% = 56,100 ; x 1.021 = 57,278 -> 57,200 ; reconstruction 1,100
    # Resident: 2,760,000 - 430,000 - 597,779 -> 1,732,000
    #   municipal 103,920 - 1,500 = 102,420 -> 102,400 ; prefectural 69,280 - 1,000
    #   = 68,280 -> 68,200 ; + 5,000 = 175,600
    r = _calc("4000000")
    assert r.social_insurance == Decimal("597779")
    assert _component(r, "JP-CHILD-LEVY") == Decimal("3519")
    assert _component(r, "JP-INCOME-TAX") == Decimal("56100")
    assert _component(r, "JP-RECON-TAX") == Decimal("1100")
    assert _component(r, "JP-RESIDENT-TAX") == Decimal("175600")
    assert r.total_tax == Decimal("830579")


def test_salary_10m():
    # Monthly 833,333 -> health standard 830,000 ; pension capped at 650,000
    #   health 830,000 x 4.925% = 40,877.5 -> 40,877 x 12 = 490,524
    #   pension 650,000 x 9.15% = 59,475 x 12 = 713,700
    #   child levy 830,000 x 0.115% = 954.5 -> 954 x 9 = 8,586
    #   employment insurance 50,000                               -> SI 1,262,810
    # Employment income 10,000,000 - 1,950,000 = 8,050,000 ; basic 620,000
    # Taxable 8,050,000 - 620,000 - 1,262,810 -> 6,167,000
    # Income tax 6,167,000 x 20% - 427,500 = 805,900 ; +16,923 = 822,823 -> 822,800
    # Resident: 6,357,000 ; municipal 381,420 - 1,500 -> 379,900 ;
    #   prefectural 254,280 - 1,000 -> 253,200 ; + 5,000 = 638,100
    r = _calc("10000000")
    assert r.social_insurance == Decimal("1262810")
    assert _component(r, "JP-INCOME-TAX") == Decimal("805900")
    assert _component(r, "JP-RECON-TAX") == Decimal("16900")
    assert _component(r, "JP-RESIDENT-TAX") == Decimal("638100")
    assert r.total_tax == Decimal("2723710")


def test_salary_25m():
    # Standard remuneration top grade 1,390,000
    #   health 1,390,000 x 4.925% = 68,457.5 -> 68,457 x 12 = 821,484
    #   pension 713,700 ; child levy 1,598.5 -> 1,598 x 9 = 14,382 ; EI 125,000
    #   -> SI 1,674,566
    # Employment income 23,050,000 ; basic 620,000 (≤ 23.5M)
    # Taxable 23,050,000 - 620,000 - 1,674,566 -> 20,755,000
    # Income tax 20,755,000 x 40% - 2,796,000 = 5,506,000 ; +115,626 -> 5,621,600
    # Resident: 23,050,000 - 430,000 - 1,674,566 -> 20,945,000 ;
    #   municipal 1,256,700 - 1,500 = 1,255,200 ; prefectural 837,800 - 1,000
    #   = 836,800 ; + 5,000 = 2,097,000
    r = _calc("25000000")
    assert r.social_insurance == Decimal("1674566")
    assert _component(r, "JP-INCOME-TAX") == Decimal("5506000")
    assert _component(r, "JP-RECON-TAX") == Decimal("115600")
    assert _component(r, "JP-RESIDENT-TAX") == Decimal("2097000")
    assert r.total_tax == Decimal("9393166")


def test_mixed_wages_dividends_gains_interest():
    # Wages 8,000,000: monthly 666,667 -> standard 680,000 ; pension 650,000
    #   health 680,000 x 4.925% = 33,490 x 12 = 401,880 ; pension 713,700
    #   child levy 782 x 9 = 7,038 ; EI 40,000                    -> SI 1,162,618
    # Employment income 8,000,000 x 90% - 1,100,000 = 6,100,000 ; basic 670,000
    #   (separately taxed income is outside 合計所得 for 申告不要 accounts)
    # Taxable 6,100,000 - 670,000 - 1,162,618 -> 4,267,000
    # Income tax 853,400 - 427,500 = 425,900 ; +8,943 = 434,843 -> 434,800
    # Resident: 4,507,000 ; municipal 270,420 - 1,500 -> 268,900 ;
    #   prefectural 180,280 - 1,000 -> 179,200 ; + 5,000 = 453,100
    # Separate 20.315%: dividends 1,000,000 -> 203,150 ; gains 2,000,000 -> 406,300 ;
    #   interest 100,000 -> 15,000 + 315 + 5,000 = 20,315          -> 629,765
    # Total = 425,900 + 8,900 + 453,100 + 1,162,618 + 629,765 = 2,680,283
    bd = IncomeBreakdown(
        employment_wages=Decimal("8000000"),
        dividends_qualified=Decimal("1000000"),
        capital_gains_long_term=Decimal("2000000"),
        interest=Decimal("100000"),
    )
    r = _calc("11100000", income_breakdown=bd)
    assert r.social_insurance == Decimal("1162618")
    assert _component(r, "JP-INCOME-TAX") == Decimal("425900")
    assert _component(r, "JP-RESIDENT-TAX") == Decimal("453100")
    assert r.total_tax == Decimal("2680283")


def test_special_minimum_fixed_row_2195000():
    # Salary 2,195,000 is in the 2,193,000-2,195,999 fixed row -> 1,453,000
    # Monthly 182,917 -> standard 180,000: health 8,865 x 12 = 106,380 ;
    #   pension 16,470 x 12 = 197,640 ; child levy 207 x 9 = 1,863 ;
    #   EI 2,195,000 x 0.5% = 10,975                               -> SI 316,858
    # Taxable 1,453,000 - 1,040,000 - 316,858 -> 96,000 ; tax 4,800 ; x1.021 -> 4,900
    # Resident: 1,453,000 - 430,000 - 316,858 -> 706,000 ; 42,360 - 1,500 -> 40,800 ;
    #   28,240 - 1,000 -> 27,200 ; + 5,000 = 73,000
    r = _calc("2195000")
    assert _component(r, "JP-EMP-DED") == Decimal("-742000")
    assert _component(r, "JP-INCOME-TAX") == Decimal("4800")
    assert _component(r, "JP-RESIDENT-TAX") == Decimal("73000")
    assert r.total_tax == Decimal("394758")


def test_salary_6m_age_40_64_care():
    # Standard 500,000: health 24,625 x 12 = 295,500 ; care 4,050 x 12 = 48,600 ;
    #   pension 549,000 ; child levy 575 x 9 = 5,175 ; EI 30,000   -> SI 928,275
    # Employment income 4,360,000 ; basic 1,040,000 ; taxable -> 2,391,000
    # Income tax 239,100 - 97,500 = 141,600 ; x1.021 -> 144,500 (recon 2,900)
    # Resident 3,001,000: 180,060 - 1,500 -> 178,500 ; 120,040 - 1,000 -> 119,000 ; +5,000
    r = _calc("6000000", jp=JPTaxInput(age_category=JPAgeCategory.AGE_40_TO_64))
    assert _component(r, "JP-LTC") == Decimal("48600")
    assert _component(r, "JP-RESIDENT-TAX") == Decimal("302500")
    assert r.total_tax == Decimal("1375275")


def test_family_and_business_profiles_refused():
    with pytest.raises(UnsupportedIncomeError):
        _calc("6000000", jp=JPTaxInput(has_spouse=True))
    with pytest.raises(UnsupportedIncomeError):
        _calc("6000000", jp=JPTaxInput(num_dependents=1))
    with pytest.raises(UnsupportedIncomeError):
        _calc("6000000", income_breakdown=IncomeBreakdown(
            employment_wages=Decimal("5000000"), self_employment=Decimal("1000000")))


def test_period_label():
    r = _calc("5000000")
    assert any("令和8年分" in n for n in r.calculation_notes)
    assert any("令和9年度" in n for n in r.calculation_notes)
