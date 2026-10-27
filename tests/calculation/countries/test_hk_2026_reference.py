"""
Hong Kong 2026/27 year of assessment reference tests (tax_year=2026).

Sources (retrieved 2026-10-27):
- Basic allowance HK$145,000 from 2026/27 (bill passed LegCo 13 May 2026,
  gazetted 22 May 2026); no change to progressive bands or standard rate:
  https://www.ird.gov.hk/eng/tax/budget.htm
- IRD worked example 1 (income 380,000 - basic allowance 145,000 = NCI
  235,000 -> tax 21,950) confirms bands 2/6/10/14/17% on HK$50,000 steps:
  https://www.ird.gov.hk/eng/pdf/2026/example2627.pdf
- Two-tier standard rate: 15% on the first HK$5M of net income, 16% above.
- MPF employee 5% of relevant income, nil below HK$7,100/month, capped at
  HK$1,500/month:
  https://www.mpfa.org.hk/en/mpf-system/mandatory-contributions/employees
- No one-off salaries tax reduction for 2026/27.
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.countries.base import UnsupportedIncomeError
from tax_estimator.calculation.countries.hk import HKCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import HKTaxInput, InternationalTaxInput

D = Decimal


def _calc(gross: str, **kwargs):
    return HKCalculator().calculate(
        InternationalTaxInput(
            country_code="HK", tax_year=2026, currency_code="HKD",
            gross_income=D(gross), **kwargs,
        )
    )


def test_wages_40k_below_mpf_floor_and_allowance():
    # 40,000 / 12 = 3,333 < 7,100 -> no MPF ; NCI = max(0, 40,000 - 145,000) = 0
    r = _calc("40000")
    assert r.social_insurance == D("0")
    assert r.income_tax == D("0.00")


def test_wages_100k_fully_covered_by_allowance():
    # MPF 100,000 x 5% = 5,000 ; NCI = max(0, 100,000 - 5,000 - 145,000) = 0
    r = _calc("100000")
    assert r.social_insurance == D("5000.00")
    assert r.income_tax == D("0.00")


def test_wages_250k_no_one_off_reduction():
    # MPF 250,000 x 5% = 12,500 ; NCI = 250,000 - 12,500 - 145,000 = 92,500
    # Progressive = 50,000 x 2% (1,000) + 42,500 x 6% (2,550) = 3,550
    # Standard = 237,500 x 15% = 35,625 -> progressive; no reduction for 2026/27
    r = _calc("250000")
    assert r.social_insurance == D("12500.00")
    assert r.income_tax == D("3550.00")
    assert not any(c.component_id == "HK-REDUCTION" for c in r.breakdown)


def test_ird_example_income_with_mpf():
    # 380,000: MPF capped 1,500 x 12 = 18,000 ; NCI = 380,000 - 18,000 - 145,000 = 217,000
    # Progressive = 16,000 (first 200,000) + 17,000 x 17% (2,890) = 18,890
    # (IRD's example ignores MPF: NCI 235,000 -> 16,000 + 35,000 x 17% = 21,950)
    r = _calc("380000")
    assert r.income_tax == D("18890.00")


def test_mixed_income_only_wages_taxed():
    # Wages 600,000 ; dividends, interest and gains are not taxed.
    # MPF 18,000 ; NCI = 600,000 - 18,000 - 145,000 = 437,000
    # Progressive = 16,000 + 237,000 x 17% (40,290) = 56,290 < standard 582,000 x 15%
    bd = IncomeBreakdown(
        employment_wages=D("600000"),
        dividends_qualified=D("50000"),
        interest=D("10000"),
        capital_gains_long_term=D("100000"),
    )
    r = _calc("760000", income_breakdown=bd)
    assert r.income_tax == D("56290.00")
    assert r.total_tax == D("74290.00")


def test_6m_two_tier_standard_rate():
    # Net income 6,000,000 - 18,000 = 5,982,000
    # Standard = 5,000,000 x 15% (750,000) + 982,000 x 16% (157,120) = 907,120
    # Progressive on 5,837,000 = 16,000 + 5,637,000 x 17% = 974,290 -> standard applies
    r = _calc("6000000")
    assert r.income_tax == D("907120.00")


def test_period_label_and_no_warnings():
    r = _calc("250000")
    assert any("2026/27" in n for n in r.calculation_notes)
    assert r.warnings == []


@pytest.mark.parametrize(
    "profile",
    [
        HKTaxInput(is_married=True),
        HKTaxInput(num_children=1),
        HKTaxInput(has_dependent_parent=True),
    ],
)
def test_family_profiles_refused_for_2026(profile):
    with pytest.raises(UnsupportedIncomeError):
        _calc("500000", hk=profile)


def test_self_employment_refused_for_2026():
    with pytest.raises(UnsupportedIncomeError):
        _calc("500000", income_breakdown=IncomeBreakdown(self_employment=D("500000")))
