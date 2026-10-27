"""France 2026-income reference tests (hand calculations; PROVISIONAL barème).

Sources (retrieved 2026-10-27)
- Barème per part, décote (art. 197 CGI) as proposed by art. 2 of the Projet de loi
  de finances pour 2027 (AN n° 3210, tabled 1 Oct 2026, not enacted):
  https://www.assemblee-nationale.fr/dyn/opendata/PRJLANR5L17B3210.html
    0% to 11,844; 11% to 30,200; 30% to 86,353; 41% to 185,737; 45% above.
    Décote single: 915 - 45.25% x tax.
- 10% abattement limits 520 / 14,861: art. 83 3° CGI indexation on the first-bracket
  limit (11,844 / 11,600) applied to 509 / 14,555 (provisional derivation).
- PASS 2026 = 48,060 (arrêté du 22/12/2025). Employee rates unchanged: vieillesse
  6.90% (T1) + 0.40%; AGIRC-ARRCO 3.15% T1 / 8.64% T2; CEG 0.86% / 1.08%; CET 0.14%
  (salary > 1 PASS); CSG 9.2% (6.8% deductible) and CRDS 0.5% on 98.25% of gross up to
  4 PASS (Weblex / Legisocial 2026 tables).
- PFU 12.8% + 18.6% prélèvements sociaux on 2026 dividends/interest/gains (LFSS 2026
  art. 12; service-public F2329).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.countries.base import UnsupportedIncomeError
from tax_estimator.calculation.countries.fr import FRCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import FRTaxInput, InternationalTaxInput

D = Decimal
CALC = FRCalculator()


def _calc(gross: str, breakdown: IncomeBreakdown | None = None, fr: FRTaxInput | None = None):
    return CALC.calculate(
        InternationalTaxInput(
            country_code="FR", tax_year=2026, gross_income=D(gross),
            income_breakdown=breakdown, fr=fr,
        )
    )


def test_salary_40k_with_decote():
    """EUR 40,000 (below 1 PASS).

    Cotisations: 2,760.00 + 160.00 + 1,260.00 + 344.00 = 4,524.00
    CSG base 39,300.00: CSG 3,615.60 (deductible 2,672.40), CRDS 196.50
    Net taxable = 40,000 - 4,524.00 - 2,672.40 = 32,803.60; abattement 3,280.36
    RNI = 29,523.24 -> 29,523
    Tax = (29,523 - 11,844) x 11% = 1,944.69
    Décote = 915 - 0.4525 x 1,944.69 = 35.03; IR = 1,909.66 -> 1,910
    Social = 4,524.00 + 3,615.60 + 196.50 = 8,336.10; total = 10,246.10
    """
    r = _calc("40000")
    assert r.taxable_income == D("29523")
    assert r.income_tax == D("1910")
    assert r.social_insurance == D("8336.10")
    assert r.total_tax == D("10246.10")
    assert len(r.warnings) == 2
    assert all(w.endswith("(provisional)") for w in r.warnings)
    assert any("PLF 2027" in n for n in r.calculation_notes)


def test_salary_100k_tranche_2():
    """EUR 100,000 (T2 = 51,940).

    Cotisations: vieillesse 48,060 x 6.9% = 3,316.14 + 400.00; AGIRC-ARRCO T1 1,513.89,
      CEG T1 413.32 (413.316); T2 51,940 x 8.64% = 4,487.62, CEG T2 560.95; CET 140.00
      = 10,831.92
    CSG base 98,250: CSG 9,039.00, deductible 6,681.00, CRDS 491.25
    Net taxable = 100,000 - 10,831.92 - 6,681.00 = 82,487.08; abattement 8,248.71
    RNI = 74,238.37 -> 74,238
    Tax = 18,356 x 11% (2,019.16) + 44,038 x 30% (13,211.40) = 15,230.56 -> 15,231
    Social = 10,831.92 + 9,039.00 + 491.25 = 20,362.17; total = 35,593.17
    """
    r = _calc("100000")
    assert r.taxable_income == D("74238")
    assert r.income_tax == D("15231")
    assert r.social_insurance == D("20362.17")
    assert r.total_tax == D("35593.17")


def test_salary_250k_abattement_cap_and_csg_ceiling():
    """EUR 250,000: abattement capped at 14,861; CSG abattement only up to 4 PASS.

    Cotisations: 3,316.14 + 1,000.00 + 1,513.89 + 413.32 + T2 201,940 x 8.64% = 17,447.62
      + CEG T2 2,180.95 + CET 350.00 = 26,221.92
    CSG base = 192,240 x 98.25% + 57,760 = 246,635.80: CSG 22,690.49,
      deductible 16,771.23, CRDS 1,233.18
    Net taxable = 250,000 - 26,221.92 - 16,771.23 = 207,006.85; abattement 14,861 (cap)
    RNI = 192,145
    Tax = 59,612.50 (to 185,737) + 6,408 x 45% (2,883.60) = 62,496.10 -> 62,496
    RFR 192,145 < 250,000: no CEHR.
    Social = 26,221.92 + 22,690.49 + 1,233.18 = 50,145.59; total = 112,641.59
    """
    r = _calc("250000")
    assert r.taxable_income == D("192145")
    assert r.income_tax == D("62496")
    assert r.social_insurance == D("50145.59")
    assert r.other_taxes == D("0")
    assert r.total_tax == D("112641.59")


def test_mixed_salary_and_capital_income_pfu_31_4():
    """EUR 40,000 salary + 3,000 dividends + 2,000 interest + 6,000 gains.

    Salary part as above (IR 1,910; social 8,336.10).
    PFU 12.8% x 11,000 = 1,408.00; PS 18.6% x 5,000 = 930.00 and 18.6% x 6,000 = 1,116.00
    Total = 10,246.10 + 1,408.00 + 930.00 + 1,116.00 = 13,700.10
    """
    bd = IncomeBreakdown(
        employment_wages=D("40000"), dividends_qualified=D("3000"), interest=D("2000"),
        capital_gains_long_term=D("6000"),
    )
    r = _calc("51000", breakdown=bd)
    assert r.income_tax == D("1910") + D("1408.00")
    assert r.social_insurance == D("8336.10") + D("930.00") + D("1116.00")
    assert r.total_tax == D("13700.10")


@pytest.mark.parametrize(
    "profile",
    [FRTaxInput(is_married=True), FRTaxInput(num_children=1),
     FRTaxInput(is_single_parent=True, num_children=1)],
)
def test_married_or_dependants_refused(profile):
    with pytest.raises(UnsupportedIncomeError):
        _calc("50000", fr=profile)


def test_self_employment_refused():
    with pytest.raises(UnsupportedIncomeError):
        _calc("50000", breakdown=IncomeBreakdown(self_employment=D("50000")))
