"""Italy 2026 reference tests (hand calculations from cited sources).

Sources (retrieved 2026-10-27)
- IRPEF 2026 (art. 11 TUIR as amended by art. 1 c.3 L. 199/2025): 23% to 28,000;
  33% to 50,000; 43% above.
  https://www.brocardi.it/testo-unico-imposte-redditi/titolo-i/capo-i/art11.html
- Detrazione lavoro dipendente (art. 13 TUIR), 28,000 < R <= 50,000:
  1,910 x (50,000 - R) / 22,000; +65 only for 25,000 < R <= 35,000.
- Cuneo fiscale (L. 207/2024, structural): extra detrazione 1,000 up to R 32,000,
  tapering to 0 at 40,000: 1,000 x (40,000 - R) / 8,000.
- INPS 2026 (circolare 6/2026): 9.19% employee + 1% above 56,224; massimale 122,295.
- Addizionali at the documented default rates: regional 1.73%, municipal 0.8% of R.
- Capital income: 26% imposta sostitutiva, outside IRPEF and INPS.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.countries.base import UnsupportedIncomeError
from tax_estimator.calculation.countries.it import ITCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import InternationalTaxInput, ITTaxInput

D = Decimal
CALC = ITCalculator()


def _calc(gross: str, breakdown: IncomeBreakdown | None = None, it: ITTaxInput | None = None):
    return CALC.calculate(
        InternationalTaxInput(
            country_code="IT", tax_year=2026, gross_income=D(gross),
            income_breakdown=breakdown, it=it,
        )
    )


def test_salary_40k_33_percent_band_and_cuneo_taper():
    """EUR 40,000.

    INPS 40,000 x 9.19% = 3,676.00; R = 36,324.00
    IRPEF lorda = 28,000 x 23% (6,440) + 8,324 x 33% (2,746.92) = 9,186.92
    Detrazione art. 13 = 1,910 x 13,676 / 22,000 = 1,187.3255 -> 1,187.33
    Cuneo extra = 1,000 x 3,676 / 8,000 = 459.50
    IRPEF netta = 9,186.92 - 1,646.83 = 7,540.09
    Addizionali: 36,324 x 1.73% = 628.41; x 0.8% = 290.59
    Total = 3,676.00 + 7,540.09 + 628.41 + 290.59 = 12,135.09
    """
    r = _calc("40000")
    assert r.social_insurance == D("3676.00")
    assert r.taxable_income == D("36324.00")
    assert r.income_tax == D("7540.09")
    assert r.other_taxes == D("919.00")  # 628.41 + 290.59
    assert r.total_tax == D("12135.09")
    assert r.marginal_rate == D("0.33")
    assert [w for w in r.warnings if "surtaxes use typical default rates" not in w] == []


def test_salary_100k_additional_inps_rate():
    """EUR 100,000.

    INPS = 9,190.00 + (100,000 - 56,224) x 1% (437.76) = 9,627.76; R = 90,372.24
    IRPEF = 6,440 + 7,260 + 40,372.24 x 43% (17,360.0632) = 31,060.06; no detrazioni
    Addizionali: 1,563.44 (1,563.4398) + 722.98 (722.97792)
    Total = 9,627.76 + 31,060.06 + 1,563.44 + 722.98 = 42,974.24
    """
    r = _calc("100000")
    assert r.social_insurance == D("9627.76")
    assert r.taxable_income == D("90372.24")
    assert r.income_tax == D("31060.06")
    assert r.total_tax == D("42974.24")


def test_salary_250k_inps_massimale():
    """EUR 250,000: INPS capped at the 122,295 massimale.

    INPS = 122,295 x 9.19% (11,238.9105) + 66,071 x 1% (660.71) = 11,899.62
    R = 238,100.38; IRPEF = 13,700 + 188,100.38 x 43% (80,883.1634) = 94,583.16
    Addizionali: 4,119.14 (4,119.1366) + 1,904.80 (1,904.80304)
    Total = 11,899.62 + 94,583.16 + 4,119.14 + 1,904.80 = 112,506.72
    """
    r = _calc("250000")
    assert r.social_insurance == D("11899.62")
    assert r.income_tax == D("94583.16")
    assert r.total_tax == D("112506.72")


def test_mixed_salary_and_capital_income():
    """EUR 40,000 salary + 3,000 dividends + 2,000 interest + 6,000 gains.

    Salary part as above (12,135.09); capital 11,000 x 26% = 2,860.00, outside IRPEF.
    Total = 14,995.09
    """
    bd = IncomeBreakdown(
        employment_wages=D("40000"), dividends_qualified=D("3000"), interest=D("2000"),
        capital_gains_long_term=D("6000"),
    )
    r = _calc("51000", breakdown=bd)
    assert r.income_tax == D("7540.09") + D("2860.00")
    assert r.social_insurance == D("3676.00")
    assert r.total_tax == D("14995.09")


def test_dependants_refused():
    with pytest.raises(UnsupportedIncomeError):
        _calc("50000", it=ITTaxInput(num_dependents=1))


def test_self_employment_refused():
    with pytest.raises(UnsupportedIncomeError):
        _calc("50000", breakdown=IncomeBreakdown(self_employment=D("50000")))


@pytest.mark.parametrize(
    "profile", [ITTaxInput(region="Lombardia"), ITTaxInput(municipality="Milano")]
)
def test_unverified_region_or_municipality_refused(profile):
    with pytest.raises(UnsupportedIncomeError, match="verified"):
        _calc("50000", it=profile)
