"""France 2025-income reference tests (hand calculations).

Sources
- Barème revenus 2025 (11,600 / 29,579 / 84,577 / 181,917 at 0/11/30/41/45%) and
  quotient familial caps (1,807 per half-part; parent isolé 4,262):
  https://www.service-public.gouv.fr/particuliers/vosdroits/F1419
- Décote revenus 2025 (897 single / 1,483 couple, 45.25%):
  https://www.legifiscal.fr/actualites-fiscales/4474-ir-bareme-2026-quotient-familial-decote.html
- 10% abattement 2025 (min 509 / max 14,555):
  https://www.cfdt.fr/sinformer/dossier-impots/frais-professionnels-reels-des-salaries
- Employee contributions 2025 (PASS 47,100): vieillesse 6.90% (<=PASS) + 0.40%;
  AGIRC-ARRCO 3.15% T1 / 8.64% T2; CEG 0.86% / 1.08%; CET 0.14% if salary > PASS:
  https://www.legisocial.fr/reperes-sociaux/cotisations-agirc-arrco-2025.html
- CSG 9.2% (6.8% deductible) and CRDS 0.5% on 98.25% of gross salary.
- PFU 12.8% (art. 200 A CGI); prélèvements sociaux 17.2% on 2025 dividends/interest,
  18.6% on 2025 securities gains (LFSS 2026 CSG rise to 10.6%; see YAML notes).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.comparison_enhanced import compare_regions_enhanced
from tax_estimator.calculation.countries.fr import FRCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import FRTaxInput, InternationalTaxInput

D = Decimal
CALC = FRCalculator()


def _calc(gross: str, breakdown: IncomeBreakdown | None = None, fr: FRTaxInput | None = None):
    return CALC.calculate(
        InternationalTaxInput(
            country_code="FR", tax_year=2025, gross_income=D(gross),
            income_breakdown=breakdown, fr=fr,
        )
    )


def test_low_salary_20k_decote_cancels_tax():
    """EUR 20,000 non-cadre, single.

    Cotisations: 1,380 + 80 + 630 + 172 = 2,262.00
    CSG base 19,650: CSG 1,807.80 (deductible 1,336.20); CRDS 98.25
    Social total = 2,262 + 1,807.80 + 98.25 = 4,168.05
    Net imposable = 20,000 - 2,262 - 1,336.20 = 16,401.80; abattement 1,640.18
    RNI = 14,761; IR brut = (14,761 - 11,600) x 11% = 347.71
    Décote = 897 - 45.25% x 347.71 = 739.66 >= tax -> IR 0
    """
    r = _calc("20000")
    assert r.social_insurance == D("4168.05")
    assert r.taxable_income == D("14761")
    assert r.income_tax == D("0")
    assert r.total_tax == D("4168.05")


def test_mid_salary_50k_matches_brief_reference():
    """EUR 50,000 non-cadre, single: ~14.6k total.

    T1 = 47,100, T2 = 2,900
    Cotisations: 3,249.90 + 200.00 + 1,483.65 + 405.06 + 250.56 + 31.32 + CET 70.00 = 5,690.49
    CSG base 49,125: CSG 4,519.50 (deductible 3,340.50); CRDS 245.63 (245.625 half-up)
    Social = 5,690.49 + 4,519.50 + 245.63 = 10,455.62
    Net imposable = 50,000 - 5,690.49 - 3,340.50 = 40,969.01; abattement 4,096.90
    RNI = 36,872; IR = 17,979 x 11% + 7,293 x 30% = 1,977.69 + 2,187.90 = 4,165.59 -> 4,166
    Total = 14,621.62
    """
    r = _calc("50000")
    assert r.social_insurance == D("10455.62")
    assert r.taxable_income == D("36872")
    assert r.income_tax == D("4166")
    assert r.total_tax == D("14621.62")


def test_high_salary_150k():
    """EUR 150,000 non-cadre, single.

    Cotisations: 3,249.90 + 600 + 1,483.65 + 405.06 + T2 102,900 x 8.64% = 8,890.56
                 + 102,900 x 1.08% = 1,111.32 + CET 210 = 15,950.49
    CSG base 147,375: CSG 13,558.50 (deductible 10,021.50); CRDS 736.88
    Social = 30,245.87
    Net imposable = 150,000 - 15,950.49 - 10,021.50 = 124,028.01; abattement 12,402.80
    RNI = 111,625; IR = 18,477.09 + (111,625 - 84,577) x 41% = 29,566.77 -> 29,567
    Total = 59,812.87
    """
    r = _calc("150000")
    assert r.social_insurance == D("30245.87")
    assert r.taxable_income == D("111625")
    assert r.income_tax == D("29567")
    assert r.other_taxes == D("0")
    assert r.total_tax == D("59812.87")


def test_salary_plus_dividends_and_gains():
    """EUR 50,000 salary + 5,000 dividends + 10,000 long-term gains.

    PFU income tax 12.8% x 15,000 = 1,920; PS 17.2% x 5,000 = 860; PS 18.6% x 10,000 = 1,860
    Total = 14,621.62 + 1,920 + 860 + 1,860 = 19,261.62
    """
    bd = IncomeBreakdown(
        employment_wages=D("50000"), dividends_qualified=D("5000"),
        capital_gains_long_term=D("10000"),
    )
    r = _calc("65000", breakdown=bd)
    assert r.income_tax == D("4166") + D("1920.00")
    assert r.social_insurance == D("10455.62") + D("860.00") + D("1860.00")
    assert r.total_tax == D("19261.62")


def test_single_parent_one_child_quotient_and_decote():
    """EUR 50,000, single parent, 1 child: 2 parts (1 + 0.5 child + 0.5 parent isolé).

    IR at 2 parts: 2 x (18,436 - 11,600) x 11% = 1,503.92; benefit vs 1 part = 2,661.67
    < cap 4,262. Décote = 897 - 45.25% x 1,503.92 = 216.48 -> IR 1,287.44 -> 1,287
    """
    r = _calc("50000", fr=FRTaxInput(num_children=1, is_single_parent=True))
    assert r.income_tax == D("1287")


def test_single_parent_flag_without_children_has_no_half_part():
    r = _calc("50000", fr=FRTaxInput(is_single_parent=True))
    assert r.income_tax == D("4166")


def test_third_child_counts_as_full_part():
    """Married, 3 children: 2 + 0.5 + 0.5 + 1 = 4 parts."""
    assert CALC.parts(True, 3, False) == D("4.0")


def test_quotient_cap_binds_for_high_income_couple():
    """Married, 2 children, EUR 200,000 salary: QF benefit capped at 2 x 1,807 = 3,614."""
    r = _calc("200000", fr=FRTaxInput(is_married=True, num_children=2))
    rni = r.taxable_income
    tax2, _ = CALC.bareme(rni, D(2))
    assert r.income_tax == (tax2 - D(3614)).quantize(D(1))


def test_self_employment_rejected():
    with pytest.raises(ValueError, match="self-employment"):
        _calc("50000", breakdown=IncomeBreakdown(self_employment=D("50000")))


def test_compare_path_parity():
    bd = IncomeBreakdown(
        employment_wages=D("50000"), dividends_qualified=D("5000"),
        capital_gains_long_term=D("10000"),
    )
    direct = _calc("65000", breakdown=bd)
    comparison = compare_regions_enhanced(regions=["FR"], income=bd, base_currency="EUR")
    region = comparison.regions[0]
    assert region.total_tax_local == direct.total_tax == D("19261.62")
