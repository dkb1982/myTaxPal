"""Italy 2025 reference tests (hand calculations).

Sources
- IRPEF 2025: 23% to 28,000; 35% to 50,000; 43% above (L. 207/2024).
- Detrazione lavoro dipendente, art. 13 c.1 and c.1.1 TUIR (incl. +65 for
  25,000 < R <= 35,000): https://www.brocardi.it/testo-unico-imposte-redditi/titolo-i/capo-i/art13.html
- Cuneo fiscale 2025 (L. 207/2024 art. 1 c.4-6, Circolare AdE 4/E/2025): payment
  7.1% / 5.3% / 4.8% of employment income (bands 8,500 / 15,000) when R <= 20,000;
  extra detrazione 1,000 for 20,000 < R <= 32,000, tapering to 0 at 40,000:
  https://www.fiscoetasse.com/new-rassegna-stampa/1178-taglio-cuneo-solo-fiscale-2025-esempi.html
- Trattamento integrativo 1,200 (DL 3/2020) when R <= 15,000 and gross IRPEF >
  detrazione - 75.
- INPS 2025: 9.19% + 1% above 55,448; massimale 120,607 (circolare INPS 26/2025).
- Addizionali: documented defaults 1.73% regional + 0.8% municipal (unverified), due
  only when net IRPEF > 0.
- Capital income: 26% imposta sostitutiva, no INPS.
- Rental: cedolare secca 21% of the annual rent, replacing IRPEF and addizionali
  (10% canone concordato and the IRPEF option not modelled); cedolare income
  counts in reddito complessivo for detrazioni (D.Lgs. 23/2011 art. 3 c.7):
  https://www.agenziaentrate.gov.it/portale/aree-tematiche/casa/affitto/cedolare-secca
  https://www.agenziaentrate.gov.it/portale/schede/fabbricatiterreni/cedolare-secca/scheda-informativa-cedolare-secca
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.comparison_enhanced import compare_regions_enhanced
from tax_estimator.calculation.countries.it import ITCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import InternationalTaxInput, ITTaxInput

D = Decimal
CALC = ITCalculator()


def _calc(gross: str, breakdown: IncomeBreakdown | None = None, it: ITTaxInput | None = None):
    return CALC.calculate(
        InternationalTaxInput(
            country_code="IT", tax_year=2025, gross_income=D(gross),
            income_breakdown=breakdown, it=it,
        )
    )


def test_low_salary_20k_cuneo_payment():
    """EUR 20,000: INPS 1,838.00; R = 18,162.00.

    IRPEF lorda = 18,162 x 23% = 4,177.26
    Detrazione = 1,910 + 1,190 x (28,000 - 18,162) / 13,000 = 1,910 + 900.5554 = 2,810.56
    Net IRPEF = 1,366.70 (no extra cuneo credit: R <= 20,000)
    Cuneo payment = 4.8% x 18,162 = 871.78 (non-taxable, reduces the burden)
    Addizionali = 18,162 x 1.73% = 314.20 + 18,162 x 0.8% = 145.30
    Total = 1,838.00 + 1,366.70 + 314.20 + 145.30 - 871.78 = 2,792.42
    """
    r = _calc("20000")
    assert r.social_insurance == D("1838.00")
    assert r.taxable_income == D("18162.00")
    assert r.income_tax == D("1366.70")
    assert r.other_taxes == D("314.20") + D("145.30") - D("871.78")
    assert r.total_tax == D("2792.42")


def test_mid_salary_30k_reference():
    """EUR 30,000: INPS 2,757.00; R = 27,243.00.

    IRPEF lorda = 27,243 x 23% = 6,265.89
    Detrazione art.13 = 1,910 + 1,190 x 757 / 13,000 = 1,979.29; +65 (c.1.1) = 2,044.29
    Extra cuneo credit = 1,000 (20,000 < R <= 32,000)
    Net IRPEF = 6,265.89 - 2,044.29 - 1,000 = 3,221.60
    (The brief's ~3,287 omits the 65 EUR increase in art. 13 c.1.1 TUIR.)
    Addizionali = 471.30 + 217.94 = 689.24; total = 2,757 + 3,221.60 + 689.24 = 6,667.84
    """
    r = _calc("30000")
    assert r.social_insurance == D("2757.00")
    assert r.income_tax == D("3221.60")
    assert r.other_taxes == D("689.24")
    assert r.total_tax == D("6667.84")


def test_high_salary_100k_additional_inps():
    """EUR 100,000: INPS = 9,190.00 + 1% x (100,000 - 55,448) = 445.52 -> 9,635.52.

    R = 90,364.48; IRPEF = 14,140 + 40,364.48 x 43% = 31,496.73; no credits
    Addizionali = 1,563.31 + 722.92 = 2,286.23; total = 43,418.48
    """
    r = _calc("100000")
    assert r.social_insurance == D("9635.52")
    assert r.taxable_income == D("90364.48")
    assert r.income_tax == D("31496.73")
    assert r.other_taxes == D("2286.23")
    assert r.total_tax == D("43418.48")


def test_inps_massimale():
    """EUR 300,000: INPS base capped at 120,607 -> 11,083.78 + 651.59 = 11,735.37."""
    assert _calc("300000").social_insurance == D("11735.37")


def test_salary_plus_dividends_and_gains():
    """EUR 30,000 salary + 5,000 dividends + 10,000 gains: +26% x 15,000 = 3,900, no INPS."""
    bd = IncomeBreakdown(
        employment_wages=D("30000"), dividends_qualified=D("5000"),
        capital_gains_long_term=D("10000"),
    )
    r = _calc("45000", breakdown=bd)
    assert r.social_insurance == D("2757.00")
    assert r.income_tax == D("3221.60") + D("3900.00")
    assert r.total_tax == D("10567.84")


def test_low_income_trattamento_integrativo_can_exceed_tax():
    """EUR 10,000: R 9,081; IRPEF 2,088.63 - 1,955 = 133.63; TI 1,200 (2,088.63 > 1,880);
    payment 5.3% x 9,081 = 481.29; addizionali 157.10 + 72.65.
    Total = 919 + 133.63 + 229.75 - 481.29 - 1,200 = -398.91 (net transfer to employee).
    """
    r = _calc("10000")
    assert r.total_tax == D("-398.91")


def test_salary_plus_rent_cedolare_secca():
    """EUR 40,000 salary + 12,000 rent.

    INPS = 40,000 x 9.19% = 3,676.00 ; IRPEF base R = 36,324.00 (rent excluded)
    IRPEF lorda = 6,440 + 8,324 x 35% = 9,353.40
    Credits use R + rent = 48,324: detrazione = 1,910 x (50,000 - 48,324) / 22,000
      = 145.51 ; cuneo extra credit 0 (> 40,000)
    Net IRPEF = 9,207.89 ; cedolare secca = 12,000 x 21% = 2,520.00
    Addizionali on R only: 628.41 + 290.59 = 919.00
    Total = 3,676 + 9,207.89 + 2,520 + 919 = 16,322.89
    (Salary only: credits 1,187.33 + 459.50 -> total 12,301.57.)
    """
    bd = IncomeBreakdown(employment_wages=D("40000"), rental=D("12000"))
    r = _calc("52000", breakdown=bd)
    assert r.social_insurance == D("3676.00")
    assert r.taxable_income == D("36324.00")
    assert r.income_tax == D("9207.89") + D("2520.00")
    assert r.other_taxes == D("919.00")
    assert r.total_tax == D("16322.89")
    assert _calc("40000").total_tax == D("12301.57")


def test_rental_compare_path_parity():
    bd = IncomeBreakdown(employment_wages=D("40000"), rental=D("12000"))
    region = compare_regions_enhanced(regions=["IT"], income=bd, base_currency="EUR").regions[0]
    assert region.total_tax_local == _calc("52000", breakdown=bd).total_tax == D("16322.89")


def test_self_employment_rejected():
    with pytest.raises(ValueError, match="self-employment"):
        _calc("10000", breakdown=IncomeBreakdown(self_employment=D("10000")))


def test_unknown_region_warns_and_uses_default():
    r = _calc("30000", it=ITTaxInput(region="Lombardia"))
    assert r.total_tax == D("6667.84")
    assert any("Lombardia" in w for w in r.warnings)


def test_compare_path_parity():
    bd = IncomeBreakdown(
        employment_wages=D("30000"), dividends_qualified=D("5000"),
        capital_gains_long_term=D("10000"),
    )
    direct = _calc("45000", breakdown=bd)
    comparison = compare_regions_enhanced(regions=["IT"], income=bd, base_currency="EUR")
    region = comparison.regions[0]
    assert region.total_tax_local == direct.total_tax == D("10567.84")
