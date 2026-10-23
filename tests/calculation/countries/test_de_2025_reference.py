"""Germany 2025 reference tests (hand calculations from primary sources).

Sources
- §32a EStG, Fassung ab 01.01.2025 (VZ 2025 tariff):
  https://www.buzer.de/gesetz/4499/al210146-0.htm
    zone 3 (17,444..68,480): ESt = (176.64 z + 2,397) z + 1,015.13, z = (zvE - 17,443)/10,000
    zone 4 (68,481..277,825): ESt = 0.42 x - 10,911.92; result floored to full euro
- SolZG 1995 §3 Abs. 3 (Freigrenze 2025: 19,950 single / 39,900 joint) and §4
  (max 11.9% of the excess): https://www.gesetze-im-internet.de/solzg_1995/BJNR097500993.html
- Employee social insurance 2025: RV 9.3%, AV 1.3% (BBG 96,600); KV 7.3% + 1.25%
  (half of the 2.5% average Zusatzbeitrag), PV 1.8% + 0.6% childless (BBG 66,150).
- Vorsorgeaufwendungen §10 EStG: employee RV share + 96% of KV (Krankengeld
  reduction, §10 Abs. 1 Nr. 3a S. 4) + PV. Arbeitnehmer-Pauschbetrag 1,230 (§9a),
  Sonderausgaben-Pauschbetrag 36 (§10c).
- Abgeltungsteuer §32d EStG: 25% after the 1,000 Sparer-Pauschbetrag (§20 Abs. 9),
  plus 5.5% Soli; with church tax the rate is e / (4 + k).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.comparison_enhanced import compare_regions_enhanced
from tax_estimator.calculation.countries.de import DECalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import DETaxClass, DETaxInput, InternationalTaxInput

D = Decimal
CALC = DECalculator()


def _calc(gross: str, breakdown: IncomeBreakdown | None = None, de: DETaxInput | None = None):
    return CALC.calculate(
        InternationalTaxInput(
            country_code="DE", tax_year=2025, gross_income=D(gross),
            income_breakdown=breakdown, de=de,
        )
    )


def test_low_salary_25k():
    """EUR 25,000, class I, no church, childless.

    SV: RV 2,325.00 + AV 325.00 + KV 25,000 x 8.55% = 2,137.50 + PV 25,000 x 2.4% = 600.00
        = 5,387.50
    Vorsorge: 2,325 + 0.96 x 2,137.50 (2,052.00) + 600 = 4,977.00
    zvE = 25,000 - 1,230 - 36 - 4,977 = 18,757
    z = 0.1314; ESt = (176.64 x 0.1314 + 2,397) x 0.1314 + 1,015.13 = 1,333.15 -> 1,333
    Soli 0 (below 19,950). Total = 1,333 + 5,387.50 = 6,720.50
    """
    r = _calc("25000")
    assert r.taxable_income == D("18757")
    assert r.income_tax == D("1333")
    assert r.social_insurance == D("5387.50")
    assert r.other_taxes == D("0")
    assert r.total_tax == D("6720.50")


def test_mid_salary_60k_matches_brief_reference():
    """EUR 60,000, class I: SV 12,930; zvE 46,789; ESt 9,570; total 22,500.

    SV: 5,580 + 780 + 5,130 + 1,440 = 12,930
    Vorsorge: 5,580 + 0.96 x 5,130 (4,924.80) + 1,440 = 11,944.80
    zvE = 60,000 - 1,230 - 36 - 11,944.80 = 46,789.20 -> 46,789
    z = 2.9346; ESt = (176.64 z + 2,397) z + 1,015.13 = 9,570.58 -> 9,570
    """
    r = _calc("60000")
    assert r.social_insurance == D("12930.00")
    assert r.taxable_income == D("46789")
    assert r.income_tax == D("9570")
    assert r.other_taxes == D("0")
    assert r.total_tax == D("22500.00")


def test_high_salary_150k_soli_and_ceilings():
    """EUR 150,000: both contribution ceilings bind; Soli at full 5.5%.

    SV: RV 96,600 x 9.3% = 8,983.80; AV 1,255.80; KV 66,150 x 8.55% = 5,655.83 (5,655.825
        rounded half-up); PV 66,150 x 2.4% = 1,587.60; total 17,483.03
    Vorsorge: 8,983.80 + 0.96 x 5,655.83 + 1,587.60 = 16,001.00
    zvE = 150,000 - 1,230 - 36 - 16,001.00 = 132,733
    ESt = 0.42 x 132,733 - 10,911.92 = 44,835.94 -> 44,835
    Soli = min(5.5% x 44,835 = 2,465.92, 11.9% x (44,835 - 19,950) = 2,961.31) = 2,465.92
    Total = 44,835 + 2,465.92 + 17,483.03 = 64,783.95
    """
    r = _calc("150000")
    assert r.social_insurance == D("17483.03")
    assert r.taxable_income == D("132733")
    assert r.income_tax == D("44835")
    assert r.other_taxes == D("2465.92")
    assert r.total_tax == D("64783.95")


def test_soli_milderungszone_100k():
    """EUR 100,000: zvE 82,733; ESt 23,835; Soli in the Milderungszone.

    Soli = min(5.5% x 23,835 = 1,310.93, 11.9% x (23,835 - 19,950) = 462.315) -> 462.31
    """
    r = _calc("100000")
    assert r.taxable_income == D("82733")
    assert r.income_tax == D("23835")
    assert r.other_taxes == D("462.31")


def test_salary_plus_dividends_and_gains():
    """EUR 60,000 salary + 5,000 dividends + 10,000 long-term gains.

    Salary part unchanged: ESt 9,570, SV 12,930 (no SV on capital income).
    Capital: (15,000 - 1,000) x 25% = 3,500.00; Soli 5.5% = 192.50.
    Total = 22,500 + 3,500 + 192.50 = 26,192.50
    """
    bd = IncomeBreakdown(
        employment_wages=D("60000"), dividends_qualified=D("5000"),
        capital_gains_long_term=D("10000"),
    )
    r = _calc("75000", breakdown=bd)
    assert r.social_insurance == D("12930.00")
    assert r.income_tax == D("9570") + D("3500.00")
    assert r.other_taxes == D("192.50")
    assert r.total_tax == D("26192.50")


def test_church_tax_bavaria_with_capital_income():
    """Church member in Bavaria (8%): tariff church tax and reduced Abgeltungsteuer.

    Church on ESt: 8% x 9,570 = 765.60
    Capital: 14,000 / (4 + 0.08) = 3,431.37; Soli 5.5% = 188.72; church 8% = 274.50
    """
    bd = IncomeBreakdown(employment_wages=D("60000"), interest=D("15000"))
    r = _calc("75000", breakdown=bd, de=DETaxInput(has_church_membership=True, state="BY"))
    assert r.income_tax == D("9570") + D("3431.37")
    assert r.other_taxes == D("765.60") + D("188.72") + D("274.50")


def test_splitting_only_for_class_iii():
    """Class III: Sonderausgaben 72; zvE 46,753; tax = 2 x tariff(23,376) = 2 x 2,499.

    z = (23,376 - 17,443) / 10,000 = 0.5933
    (176.64 x 0.5933 + 2,397) x 0.5933 + 1,015.13 = 2,499.45 -> 2,499
    Class IV is assessed on the basic tariff (same as class I).
    """
    r3 = _calc("60000", de=DETaxInput(tax_class=DETaxClass.III))
    assert r3.taxable_income == D("46753")
    assert r3.income_tax == D("4998")
    r4 = _calc("60000", de=DETaxInput(tax_class=DETaxClass.IV))
    assert r4.income_tax == D("9570")


def test_profile_investment_income_is_not_dropped():
    """A profile with capital income keeps it under the Abgeltungsteuer."""
    r = _calc("75000", de=DETaxInput(employment_income=D("60000"), capital_income=D("15000")))
    assert r.income_tax == D("9570") + D("3500.00")
    assert r.social_insurance == D("12930.00")


def test_self_employment_rejected():
    bd = IncomeBreakdown(self_employment=D("50000"))
    with pytest.raises(ValueError, match="self-employment"):
        _calc("50000", breakdown=bd)


def test_non_2025_year_rejected():
    with pytest.raises(ValueError, match="2025"):
        CALC.calculate(InternationalTaxInput(country_code="DE", tax_year=2026, gross_income=D("1")))


def test_compare_path_parity():
    """Compare mode (EUR base, no FX) returns the direct calculator's total."""
    bd = IncomeBreakdown(
        employment_wages=D("60000"), dividends_qualified=D("5000"),
        capital_gains_long_term=D("10000"),
    )
    direct = _calc("75000", breakdown=bd)
    comparison = compare_regions_enhanced(regions=["DE"], income=bd, base_currency="EUR")
    region = comparison.regions[0]
    assert region.total_tax_local == direct.total_tax == D("26192.50")
    assert region.total_tax_base == direct.total_tax
