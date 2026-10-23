"""
Spain IRPF 2025 reference tests (hand-calculated from primary sources).

Sources:
- LIRPF arts. 19, 20, 56, 63, 66, 74, 76 (BOE consolidated):
  https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764
- Work-income reduction 2025 (base = gross - art. 19.2 a-e expenses):
  https://sede.agenciatributaria.gob.es/Sede/en_gb/ayuda/manuales-videos-folletos/manuales-ayuda-presentacion/irpf-2025/7-cumplimentacion-irpf/7_1-rendimientos-trabajo-personal/7_1_6-reduccion-obtencion-rendimientos-trabajo.html
- DA 61a low-wage deduction (Ley 5/2025): 340 - 0.2 x (gross work - 16,576):
  https://sede.agenciatributaria.gob.es/Sede/en_gb/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c18-cuota-liquida-resultante-autoliquidacion/deducciones-cuota-liquida-total/deduccion-obtencion-rendimientos-trabajo.html
- Madrid scale and minimum (EUR 5,956.65):
  https://www.comunidad.madrid/atencion-contribuyente/irpf
  https://sede.agenciatributaria.gob.es/Sede/en_gb/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c14-adecuacion-impuesto-circunstancias-personales/minimo-autonomico-personal-familiar/comunidad-madrid-importes-minimo-personal-familiar.html
- SS 2025: max base 4,909.50/month; employee 4.70 + 1.55 + 0.10 + 0.13 (MEI) = 6.48%.

Scales used in the working:
  State general: 9.5% to 12,450 | 12% to 20,200 | 15% to 35,200 | 18.5% to 60,000
                 | 22.5% to 300,000 | 24.5% above
  Madrid:        8.5% to 13,362.22 | 10.7% to 19,004.63 | 12.8% to 35,425.68
                 | 17.4% to 57,320.40 | 20.5% above
  Savings (state = regional): 9.5% to 6k | 10.5% to 50k | 11.5% to 200k | 13.5% to 300k | 15%
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tax_estimator.calculation.comparison_enhanced import compare_regions_enhanced
from tax_estimator.calculation.countries.es import ESCalculator
from tax_estimator.models.income_breakdown import IncomeBreakdown
from tax_estimator.models.international import ESTaxInput, InternationalTaxInput

D = Decimal
TOL = D("0.02")


def _calc(breakdown: IncomeBreakdown | None = None, gross: str | None = None, **profile):
    if breakdown is None:
        breakdown = IncomeBreakdown(employment_wages=D(gross))
    tax_input = InternationalTaxInput(
        country_code="ES",
        tax_year=2025,
        gross_income=breakdown.total,
        income_breakdown=breakdown,
        es=ESTaxInput(**profile) if profile else None,
    )
    return ESCalculator().calculate(tax_input)


def test_low_salary_18k_madrid():
    # SS = 18,000 x 6.48% = 1,166.40
    # Net work (a-e) = 16,833.60 -> reduction = 7,302 - 1.75 x (16,833.60 - 14,852) = 3,834.20
    # General base = 16,833.60 - 2,000 - 3,834.20 = 10,999.40
    # State:  10,999.40 x 9.5% - 5,550 x 9.5%        = 1,044.943 - 527.25  = 517.693
    # Madrid: 10,999.40 x 8.5% - 5,956.65 x 8.5%     =   934.949 - 506.315 = 428.634
    # DA 61a deduction = 340 - 0.2 x (18,000 - 16,576) = 55.20 (below the quota limit)
    # IRPF = 946.33 - 55.20 = 891.13 ; total = 2,057.53
    r = _calc(gross="18000")
    assert r.social_insurance == D("1166.40")
    assert abs(r.income_tax - D("891.13")) <= TOL
    assert abs(r.total_tax - D("2057.53")) <= TOL


def test_mid_salary_50k_madrid_and_generic_reference():
    # SS = 50,000 x 6.48% = 3,240.00 (reference SS 3,240)
    # Base = 50,000 - 3,240 - 2,000 = 44,760 (no reduction: net work > 19,747.50)
    # State: 1,182.75 + 930 + 2,250 + (44,760-35,200) x 18.5% = 6,131.35 - 527.25 = 5,604.10
    # Madrid: 1,135.79 + 603.74 + 2,101.89 + (44,760-35,425.68) x 17.4% = 5,465.59
    #         - 5,956.65 x 8.5% (506.32) = 4,959.27(5)
    r = _calc(gross="50000")
    assert r.social_insurance == D("3240.00")
    assert abs(r.income_tax - D("10563.38")) <= TOL
    assert abs(r.total_tax - D("13803.38")) <= TOL
    # The review's reference (~EUR 14,448) corresponds to the GENERIC state-mirror
    # regional scale: 2 x 5,604.10 + 3,240 = 14,448.20.
    generic = _calc(gross="50000", autonomous_community="Cataluña")
    assert abs(generic.total_tax - D("14448.20")) <= TOL
    assert any("GENERIC" in w for w in generic.warnings)


def test_high_salary_100k_madrid_with_solidarity():
    # SS capped: 58,914 x 6.48% = 3,817.63
    # Solidarity (employee share 4.70/28.30) on excess 41,086:
    #   5,891.40 x 0.92% + 23,565.60 x 1.00% + 11,629 x 1.17% = 54.20 + 235.66 + 136.06
    #   = 425.92 x 0.166078 = 70.74 -> SS = 3,888.37
    # Base = 100,000 - 3,888.37 - 2,000 = 94,111.63
    # State: 8,950.75 + (94,111.63 - 60,000) x 22.5% - 527.25 = 16,098.62
    # Madrid: 7,651.10 + (94,111.63 - 57,320.40) x 20.5% - 506.32 = 14,686.98
    r = _calc(gross="100000")
    assert r.social_insurance == D("3888.37")
    assert abs(r.income_tax - D("30785.61")) <= TOL
    assert abs(r.total_tax - D("34673.98")) <= TOL


def test_salary_dividends_and_long_term_gains_madrid():
    # Salary part as in the 50k test (IRPF 10,563.38, SS 3,240).
    # Savings base 15,000: state 6,000 x 9.5% + 9,000 x 10.5% = 1,515; regional the same.
    # No social security on dividends or gains.
    bd = IncomeBreakdown(
        employment_wages=D("50000"),
        dividends_qualified=D("5000"),
        capital_gains_long_term=D("10000"),
    )
    r = _calc(bd)
    assert r.social_insurance == D("3240.00")
    assert abs(r.income_tax - D("13593.38")) <= TOL
    assert abs(r.total_tax - D("16833.38")) <= TOL


def test_personal_minimum_spills_to_savings_base():
    # Only 20,000 of dividends: general base 0, minimum applied to savings base.
    # State: (570 + 14,000 x 10.5%) - 5,550 x 9.5%        = 2,040 - 527.25  = 1,512.75
    # Madrid: 2,040 - 5,956.65 x 9.5% (565.88)            = 1,474.12
    r = _calc(IncomeBreakdown(dividends_ordinary=D("20000")))
    assert r.social_insurance == 0
    assert abs(r.income_tax - D("2986.87")) <= TOL


def test_profile_capital_income_goes_to_savings_base():
    tax_input = InternationalTaxInput(
        country_code="ES",
        tax_year=2025,
        gross_income=D("70000"),
        es=ESTaxInput(employment_income=D("50000"), capital_income=D("20000")),
    )
    r = ESCalculator().calculate(tax_input)
    # 50k salary as above + savings 20,000: 2 x (570 + 14,000 x 10.5%) = 4,080
    assert r.social_insurance == D("3240.00")
    assert abs(r.income_tax - D("14643.38")) <= TOL


def test_rejections():
    with pytest.raises(ValueError, match="self-employment"):
        _calc(IncomeBreakdown(self_employment=D("30000")))
    with pytest.raises(ValueError, match="foral"):
        _calc(gross="50000", autonomous_community="Navarra")
    with pytest.raises(ValueError, match="unknown"):
        _calc(gross="50000", autonomous_community="Atlantis")


def test_compare_path_parity():
    bd = IncomeBreakdown(
        employment_wages=D("50000"),
        dividends_qualified=D("5000"),
        capital_gains_long_term=D("10000"),
    )
    result = compare_regions_enhanced(["ES"], bd, base_currency="EUR")
    region = result.regions[0]
    direct = _calc(bd)
    assert region.total_tax_local == direct.total_tax
    assert region.international_breakdown.social_insurance == D("3240.00")
