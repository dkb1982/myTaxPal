"""
Australia reference tests for tax_year 2026 = income year 2026-27
(1 July 2026 - 30 June 2027).

Sources (retrieved 2026-10-27):
- Resident rates 2026-27: 0 to 18,200 | 15% to 45,000 | 30% to 135,000
  | 37% to 190,000 | 45% above (Act No. 28 of 2025, Sch 1 item 2):
  https://www.legislation.gov.au/C2025A00028/asmade/2025-03-27/text/original/pdf
- Medicare levy 2%; singles low-income threshold 28,011 with 10% shade-in
  (Act No. 58 of 2026, Sch 5, 2025-26 and later years):
  https://www.legislation.gov.au/C2026A00058/asmade/2026-06-30/text/original/pdf
- MLS 2026-27 singles: 0% to 105,000 ; 1% to 123,000 ; 1.25% to 164,000 ; 1.5% above:
  https://www.privatehealth.gov.au/health_insurance/surcharges_incentives/medicare_levy.htm
- LITO: 700, less 5c per $ above 37,500 to 45,000, 1.5c per $ above (ITAA 1997 s 61-115).
- HELP 2026-27: 15% above 69,528 to 129,717, 17% above, capped at 10% of
  repayment income (HESA s 154-20; Gazette C2026G00249):
  https://www.legislation.gov.au/C2026G00249/asmade/2026-04-20/text/original/pdf
- CGT 50% discount (ITAA 1997 Div 115).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.countries.au import AUCalculator
from tax_estimator.calculation.countries.base import UnsupportedIncomeError
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import AUTaxInput, InternationalTaxInput

D = Decimal


def _calc(breakdown: IncomeBreakdown | None = None, gross: str | None = None, **profile):
    if breakdown is None:
        breakdown = IncomeBreakdown(employment_wages=D(gross))
    return AUCalculator().calculate(
        InternationalTaxInput(
            country_code="AU",
            tax_year=2026,
            gross_income=breakdown.total,
            income_breakdown=breakdown,
            au=AUTaxInput(**profile) if profile else None,
        )
    )


def test_wages_40k():
    # Tax 21,800 x 15% = 3,270 ; LITO 700 - 2,500 x 5% = 575 -> 2,695
    # Medicare 2% x 40,000 = 800 ; MLS 0
    r = _calc(gross="40000")
    assert r.income_tax == D("2695.00")
    assert r.other_taxes == D("800.00")
    assert r.total_tax == D("3495.00")


def test_wages_100k():
    # Tax 26,800 x 15% (4,020) + 55,000 x 30% (16,500) = 20,520 ; Medicare 2,000
    # MLS 0 (100,000 <= 105,000)
    r = _calc(gross="100000")
    assert r.income_tax == D("20520.00")
    assert r.total_tax == D("22520.00")


def test_wages_250k_with_and_without_private_cover():
    # Tax 51,370 + 60,000 x 45% (27,000) = 78,370 ; Medicare 5,000 ;
    # MLS 1.5% x 250,000 = 3,750 -> 87,120 ; with private cover 83,370
    r = _calc(gross="250000")
    assert r.income_tax == D("78370.00")
    assert r.total_tax == D("87120.00")
    assert _calc(gross="250000", has_private_health=True).total_tax == D("83370.00")


def test_mixed_wages_interest_dividends_gains_at_mls_boundary():
    # Wages 80,000 + interest 5,000 + foreign dividends 5,000 + LT gains 30,000
    # Taxable = 90,000 + 30,000 x 50% = 105,000
    # Tax 4,020 + 60,000 x 30% (18,000) = 22,020 ; Medicare 2,100 ;
    # MLS 0 (105,000 is within the 0% tier "up to $105,000")
    bd = IncomeBreakdown(
        employment_wages=D("80000"),
        interest=D("5000"),
        dividends_ordinary=D("5000"),
        capital_gains_long_term=D("30000"),
    )
    r = _calc(bd)
    assert r.taxable_income == D("105000.00")
    assert r.income_tax == D("22020.00")
    assert r.total_tax == D("24120.00")


def test_help_repayment_marginal_and_cap():
    # 100,000: (100,000 - 69,528) x 15% = 4,570.80 (< 10,000 cap)
    r = _calc(gross="100000", has_help_debt=True, has_private_health=True)
    assert next(c for c in r.breakdown if c.component_id == "AU-HELP").amount == D("4570.80")
    # 250,000: 60,189 x 15% (9,028.35) + 120,283 x 17% (20,448.11) = 29,476.46
    # > 10% x 250,000 = 25,000 -> 25,000
    r = _calc(gross="250000", has_help_debt=True, has_private_health=True)
    assert next(c for c in r.breakdown if c.component_id == "AU-HELP").amount == D("25000.00")


def test_non_resident_rates_unchanged():
    assert _calc(gross="100000", is_resident=False).total_tax == D("30000.00")


def test_period_label_and_no_warnings():
    r = _calc(gross="40000")
    assert any("2026-27" in n for n in r.calculation_notes)
    assert r.warnings == []


def test_business_income_refused_for_2026():
    with pytest.raises(UnsupportedIncomeError):
        _calc(IncomeBreakdown(self_employment=D("50000")))
