"""Germany 2026 reference tests (hand calculations from primary sources).

Sources (retrieved 2026-10-27)
- §32a EStG "ab dem Veranlagungszeitraum 2026":
  https://www.gesetze-im-internet.de/estg/__32a.html
    zone 3 (17,800..69,878): ESt = (173.10 z + 2,397) z + 1,034.87, z = (zvE - 17,799)/10,000
    zone 4 (69,879..277,825): ESt = 0.42 x - 11,135.63; zvE and ESt floored to full euro
- SolZG §3 Abs. 3 / §6 Abs. 27: Freigrenze 2026 = 20,350 (single); Soli =
  min(5.5% ESt, 11.9% x (ESt - 20,350)):
  https://www.gesetze-im-internet.de/solzg_1995/__3.html
- SV 2026 employee shares: RV 9.3%, AV 1.3% (BBG 101,400, SVBezGrV 2026 §4);
  KV 7.3% + 1.45% (half of the 2.9% average Zusatzbeitrag), PV 1.8% + 0.6%
  childless (BBG 69,750).
- Vorsorgeaufwendungen §10 EStG: employee RV share + 96% of KV + PV (the 1,900 cap
  on other Vorsorge never reduces basic cover); Arbeitnehmer-Pauschbetrag 1,230;
  Sonderausgaben-Pauschbetrag 36.
- Abgeltungsteuer 25% after the 1,000 Sparer-Pauschbetrag, plus 5.5% Soli.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.countries.base import UnsupportedIncomeError
from tax_estimator.calculation.countries.de import DECalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import DETaxClass, DETaxInput, InternationalTaxInput

D = Decimal
CALC = DECalculator()


def _calc(gross: str, breakdown: IncomeBreakdown | None = None, de: DETaxInput | None = None):
    return CALC.calculate(
        InternationalTaxInput(
            country_code="DE", tax_year=2026, gross_income=D(gross),
            income_breakdown=breakdown, de=de,
        )
    )


def test_salary_40k():
    """EUR 40,000, class I, childless, no church.

    SV: RV 3,720.00 + AV 520.00 + KV 40,000 x 8.75% = 3,500.00 + PV 40,000 x 2.4% = 960.00
        = 8,700.00
    Vorsorge: 3,720 + 0.96 x 3,500 (3,360) + 960 = 8,040.00
    zvE = 40,000 - 1,230 - 36 - 8,040 = 30,694
    z = 1.2895; ESt = (173.10 x 1.2895 + 2,397) x 1.2895 + 1,034.87 = 4,413.63 -> 4,413
    Soli 0 (ESt below 20,350). Total = 4,413 + 8,700 = 13,113.00
    """
    r = _calc("40000")
    assert r.tax_year == 2026
    assert r.social_insurance == D("8700.00")
    assert r.taxable_income == D("30694")
    assert r.income_tax == D("4413")
    assert r.other_taxes == D("0")
    assert r.total_tax == D("13113.00")
    assert r.warnings == []
    assert any("Calendar 2026" in n for n in r.calculation_notes)


def test_salary_100k_soli_milderungszone():
    """EUR 100,000: KV/PV ceiling binds; Soli in the Milderungszone.

    SV: RV 9,300.00 + AV 1,300.00 + KV 69,750 x 8.75% = 6,103.125 -> 6,103.13
        + PV 69,750 x 2.4% = 1,674.00 = 18,377.13
    Vorsorge: 9,300 + 0.96 x 6,103.13 (5,859.0048) + 1,674 = 16,833.00
    zvE = 100,000 - 1,266 - 16,833.00 = 81,901
    ESt = 0.42 x 81,901 - 11,135.63 = 23,262.79 -> 23,262
    Soli = min(5.5% x 23,262 = 1,279.41, 11.9% x (23,262 - 20,350) = 346.528) -> 346.52
    Total = 23,262 + 346.52 + 18,377.13 = 41,985.65
    """
    r = _calc("100000")
    assert r.social_insurance == D("18377.13")
    assert r.taxable_income == D("81901")
    assert r.income_tax == D("23262")
    assert r.other_taxes == D("346.52")
    assert r.total_tax == D("41985.65")


def test_salary_250k_both_ceilings_full_soli():
    """EUR 250,000: both BBGs bind; Soli at the full 5.5%.

    SV: RV 101,400 x 9.3% = 9,430.20; AV 1,318.20; KV 6,103.13; PV 1,674.00 = 18,525.53
    Vorsorge: 9,430.20 + 5,859.0048 + 1,674 = 16,963.20
    zvE = 250,000 - 1,266 - 16,963.20 = 231,770.80 -> 231,770
    ESt = 0.42 x 231,770 - 11,135.63 = 86,207.77 -> 86,207
    Soli = min(5.5% x 86,207 = 4,741.385, 11.9% x 65,857) -> 4,741.38
    Total = 86,207 + 4,741.38 + 18,525.53 = 109,473.91
    """
    r = _calc("250000")
    assert r.social_insurance == D("18525.53")
    assert r.taxable_income == D("231770")
    assert r.income_tax == D("86207")
    assert r.other_taxes == D("4741.38")
    assert r.total_tax == D("109473.91")


def test_mixed_salary_dividends_interest_gains():
    """EUR 40,000 salary + 3,000 dividends + 2,000 interest + 6,000 gains.

    Salary part unchanged: ESt 4,413, SV 8,700 (no SV on capital income).
    Capital: (11,000 - 1,000) x 25% = 2,500.00; Soli 5.5% = 137.50.
    Total = 13,113 + 2,500 + 137.50 = 15,750.50
    """
    bd = IncomeBreakdown(
        employment_wages=D("40000"), dividends_qualified=D("3000"), interest=D("2000"),
        capital_gains_long_term=D("6000"),
    )
    r = _calc("51000", breakdown=bd)
    assert r.social_insurance == D("8700.00")
    assert r.income_tax == D("4413") + D("2500.00")
    assert r.other_taxes == D("137.50")
    assert r.total_tax == D("15750.50")


def test_church_tax_berlin_9_percent():
    """Church member outside BY/BW: 9% of tariff ESt 4,413 = 397.17."""
    r = _calc("40000", de=DETaxInput(has_church_membership=True, state="BE"))
    assert r.income_tax == D("4413")
    assert r.other_taxes == D("397.17")


@pytest.mark.parametrize(
    "profile",
    [
        DETaxInput(tax_class=DETaxClass.III),
        DETaxInput(tax_class=DETaxClass.IV),
        DETaxInput(tax_class=DETaxClass.II),
        DETaxInput(num_children=1),
    ],
)
def test_married_or_children_refused(profile):
    with pytest.raises(UnsupportedIncomeError):
        _calc("60000", de=profile)


def test_self_employment_refused():
    with pytest.raises(UnsupportedIncomeError):
        _calc("50000", breakdown=IncomeBreakdown(self_employment=D("50000")))
