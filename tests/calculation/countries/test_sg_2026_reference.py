"""
Singapore 2026 income (YA2027) reference tests (tax_year=2026).

Sources (retrieved 2026-10-27):
- Resident rates (YA2024 onwards); non-resident employment income at the
  higher of 15% or resident rates:
  https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates
- No Personal Income Tax Rebate announced for YA2027.
- Earned income relief S$1,000 (<55), S$6,000 (55-59), S$8,000 (60+).
- CPF employee rates from 1 Jan 2026: 55 and below 20%, >55-60 18%,
  >60-65 12.5%, >65-70 7.5%, >70 5%; OW ceiling S$8,000/month; annual salary
  ceiling S$102,000 (AW ceiling = 102,000 - OW subject to CPF):
  https://www.cpf.gov.sg/content/dam/web/employer/employer-obligations/documents/CPFcontributionratesfrom1Jan2026.pdf
"""

from decimal import Decimal

import pytest

from tax_estimator.calculation.countries.base import UnsupportedIncomeError
from tax_estimator.calculation.countries.sg import SGCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import (
    InternationalTaxInput,
    SGResidentStatus,
    SGTaxInput,
)

D = Decimal


def _calc(gross: str, **kwargs):
    return SGCalculator().calculate(
        InternationalTaxInput(
            country_code="SG", tax_year=2026, currency_code="SGD",
            gross_income=D(gross), **kwargs,
        )
    )


def test_wages_40k():
    # CPF 40,000 x 20% = 8,000 ; chargeable = 40,000 - 1,000 - 8,000 = 31,000
    # Tax = 200 + 1,000 x 3.5% = 235
    r = _calc("40000")
    assert r.social_insurance == D("8000.00")
    assert r.income_tax == D("235.00")


def test_wages_100k_new_ow_ceiling():
    # CPF: OW capped at 8,000 x 12 = 96,000 x 20% = 19,200
    # Chargeable = 100,000 - 1,000 - 19,200 = 79,800 ; tax = 550 + 39,800 x 7% = 3,336
    r = _calc("100000")
    assert r.social_insurance == D("19200.00")
    assert r.income_tax == D("3336.00")
    assert r.total_tax == D("22536.00")
    assert not any(c.component_id == "SG-REBATE" for c in r.breakdown)


def test_wages_250k():
    # CPF 96,000 x 20% = 19,200 ; chargeable = 250,000 - 1,000 - 19,200 = 229,800
    # Tax = 21,150 + 29,800 x 19% (5,662) = 26,812
    r = _calc("250000")
    assert r.income_tax == D("26812.00")
    assert r.total_tax == D("46012.00")


def test_mixed_income_only_wages_taxed():
    # Dividends (one-tier), bank interest and capital gains are not taxed: same as 100k wages.
    bd = IncomeBreakdown(
        employment_wages=D("100000"),
        dividends_qualified=D("20000"),
        interest=D("5000"),
        capital_gains_long_term=D("50000"),
    )
    r = _calc("175000", income_breakdown=bd)
    assert r.social_insurance == D("19200.00")
    assert r.income_tax == D("3336.00")


def test_bonus_and_age_58_rate():
    # OW 120,000 -> 96,000 subject ; AW ceiling 102,000 - 96,000 = 6,000 ; bonus -> 6,000
    # CPF 102,000 x 18% = 18,360 ; chargeable = 150,000 - EIR 6,000 - 18,360 = 125,640
    # Tax = 7,950 + 5,640 x 15% (846) = 8,796
    r = _calc(
        "150000",
        sg=SGTaxInput(age=58, employment_income=D("120000"), bonus_income=D("30000")),
    )
    assert r.social_insurance == D("18360.00")
    assert r.income_tax == D("8796.00")


def test_age_62_rate_and_relief():
    # CPF 96,000 x 12.5% = 12,000 ; chargeable = 100,000 - 8,000 - 12,000 = 80,000 -> 3,350
    r = _calc("100000", sg=SGTaxInput(age=62))
    assert r.social_insurance == D("12000.00")
    assert r.income_tax == D("3350.00")


def test_non_resident():
    nr = SGTaxInput(resident_status=SGResidentStatus.NON_RESIDENT, is_citizen_or_pr=False)
    assert _calc("100000", sg=nr).income_tax == D("15000.00")


def test_period_label_and_no_warnings():
    r = _calc("100000")
    assert any("YA2027" in n and "2026" in n for n in r.calculation_notes)
    assert r.warnings == []


def test_self_employment_refused_for_2026():
    with pytest.raises(UnsupportedIncomeError):
        _calc("80000", income_breakdown=IncomeBreakdown(self_employment=D("80000")))
