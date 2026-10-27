"""Spain 2026 reference tests (hand calculations, Comunidad de Madrid resident).

Sources (retrieved 2026-10-27)
- LIRPF consolidated (BOE-A-2006-20764): state scale art. 63 (9.5/12/15/18.5/22.5/24.5%
  at 12,450 / 20,200 / 35,200 / 60,000 / 300,000), savings scale arts. 66/76 (9.5% to
  6,000, 10.5% to 50,000 per half), art. 20 reduction, art. 57 minimum 5,550,
  DA 61a deduction 590.89 up to 17,094 of gross work income (RDL 5/2026).
- Madrid (DLeg 1/2010 art. 1-2, BOE consolidated): 8.5% to 13,362.22; 10.7% to
  19,004.63; 12.8% to 35,425.68; 17.4% to 57,320.40; 20.5% above; minimum 5,956.65.
- Orden PJC/297/2026: max base 5,101.20/month (61,214.40/yr); employee 4.70% common,
  1.55% unemployment, 0.10% FP, 0.15% MEI; solidarity employee 0.19% (to +10% of the
  max base), 0.21% (to +50%), 0.24% above.
The personal minimum is a zero-rate band: tax = scale(base) - scale(minimum).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.countries.base import UnsupportedIncomeError
from tax_estimator.calculation.countries.es import ESCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import ESTaxInput, InternationalTaxInput

D = Decimal
CALC = ESCalculator()


def _calc(gross: str, breakdown: IncomeBreakdown | None = None, es: ESTaxInput | None = None):
    return CALC.calculate(
        InternationalTaxInput(
            country_code="ES", tax_year=2026, gross_income=D(gross),
            income_breakdown=breakdown, es=es,
        )
    )


def test_salary_40k():
    """EUR 40,000.

    SS = 1,880.00 + 620.00 + 40.00 + 60.00 = 2,600.00
    Net work 37,400 (no art. 20 reduction above 19,747.50); - 2,000 = base 35,400
    State: 4,362.75 + 200 x 18.5% = 4,399.75 - 5,550 x 9.5% (527.25) = 3,872.50
    Madrid: 1,739.52657 + 16,395.37 x 12.8% (2,098.60736) = 3,838.13393
            - 5,956.65 x 8.5% (506.31525) = 3,331.81868
    IRPF = 7,204.31868 -> 7,204.32; total = 9,804.32
    """
    r = _calc("40000")
    assert r.social_insurance == D("2600.00")
    assert r.taxable_income == D("35400.00")
    assert r.income_tax == D("7204.32")
    assert r.total_tax == D("9804.32")
    assert r.warnings == []


def test_salary_100k_max_base_and_solidarity():
    """EUR 100,000.

    SS on 61,214.40: 2,877.08 + 948.82 + 61.21 + 91.82 = 3,978.93
    Solidarity on 38,785.60: 6,121.44 x 0.19% (11.630736) + 24,485.76 x 0.21% (51.420096)
      + 8,178.40 x 0.24% (19.62816) = 82.68; SS total = 4,061.61
    Base = 100,000 - 4,061.61 - 2,000 = 93,938.39
    State: 8,950.75 + 33,938.39 x 22.5% = 16,586.88775 - 527.25 = 16,059.63775
    Madrid: 7,651.10225 + 36,617.99 x 20.5% = 15,157.7902 - 506.31525 = 14,651.47495
    IRPF = 30,711.11; total = 34,772.72
    """
    r = _calc("100000")
    assert r.social_insurance == D("4061.61")
    assert r.taxable_income == D("93938.39")
    assert r.income_tax == D("30711.11")
    assert r.total_tax == D("34772.72")


def test_salary_250k():
    """EUR 250,000.

    Solidarity on 188,785.60: 11.630736 + 51.420096 + 158,178.40 x 0.24% (379.62816)
      = 442.68; SS = 3,978.93 + 442.68 = 4,421.61
    Base = 243,578.39
    State: 8,950.75 + 183,578.39 x 22.5% = 50,255.88775 - 527.25 = 49,728.63775
    Madrid: 7,651.10225 + 186,257.99 x 20.5% = 45,833.9902 - 506.31525 = 45,327.67495
    IRPF = 95,056.31; total = 99,477.92
    """
    r = _calc("250000")
    assert r.social_insurance == D("4421.61")
    assert r.income_tax == D("95056.31")
    assert r.total_tax == D("99477.92")


def test_mixed_salary_and_savings_income():
    """EUR 40,000 salary + 3,000 dividends + 2,000 interest + 6,000 gains.

    General part unchanged (7,204.32). Savings base 11,000 (minimum already used):
    per half 6,000 x 9.5% + 5,000 x 10.5% = 1,095; both halves 2,190.00.
    Total = 2,600 + 7,204.32 + 2,190.00 = 11,994.32
    """
    bd = IncomeBreakdown(
        employment_wages=D("40000"), dividends_qualified=D("3000"), interest=D("2000"),
        capital_gains_long_term=D("6000"),
    )
    r = _calc("51000", breakdown=bd)
    assert r.income_tax == D("7204.32") + D("2190.00")
    assert r.social_insurance == D("2600.00")
    assert r.total_tax == D("11994.32")


def test_smi_level_wage_pays_no_irpf():
    """EUR 17,000 (below the 2026 SMI reference 17,094).

    SS = 799.00 + 263.50 + 17.00 + 25.50 = 1,105.00; net work 15,895
    Art. 20 reduction = 7,302 - 1.75 x 1,043 = 5,476.75; base = 15,895 - 2,000 - 5,476.75
      = 8,418.25
    State 8,418.25 x 9.5% - 527.25 = 272.48375; Madrid 8,418.25 x 8.5% - 506.31525 = 209.236
    Cuota = 481.72; DA 61a deduction 590.89 limited to 481.72 -> IRPF 0
    """
    r = _calc("17000")
    assert r.social_insurance == D("1105.00")
    assert r.income_tax == D("0")
    assert r.total_tax == D("1105.00")


def test_dependants_refused():
    with pytest.raises(UnsupportedIncomeError):
        _calc("50000", es=ESTaxInput(num_dependents=1))


def test_self_employment_refused():
    with pytest.raises(UnsupportedIncomeError):
        _calc("50000", breakdown=IncomeBreakdown(self_employment=D("50000")))


def test_community_without_verified_scale_refused():
    with pytest.raises(UnsupportedIncomeError, match="regional"):
        _calc("50000", es=ESTaxInput(autonomous_community="Cataluña"))
