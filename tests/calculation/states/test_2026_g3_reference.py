"""2026 reference values for group 3: KY, LA, ME, MD, MA, MI, MN.

Hand calculations follow each state's 2026 published parameters (see the
references in rules/states/2026/<st>.yaml). Profile: single, age 40, full-year
resident, W-2 wages plus the stated dividends/gains. "Mixed" means wages $80,000
+ $5,000 ordinary (all qualified) dividends + $10,000 LTCG, so federal AGI is
$95,000. None of these states uses federal tax as an input.
"""

from decimal import Decimal as D  # noqa: N817 - compact exact-money fixtures

import pytest

from tax_estimator.calculation.states import policies_2026_g3
from tax_estimator.calculation.states.policies_2026 import PENDING_2026, POLICIES_2026

from .helpers_2026 import compute_2026

MIXED = dict(
    wages=D("80000"),
    ordinary_dividends=D("5000"),
    qualified_dividends=D("5000"),
    net_long_term_gains=D("10000"),
)


def _tax(state: str, **kwargs) -> D:
    return compute_2026(state, **kwargs).total_tax


def test_group_3_registry() -> None:
    assert set(policies_2026_g3.POLICIES) == {"KY", "LA", "ME", "MD", "MA", "MI", "MN"}
    for code in policies_2026_g3.PENDING:
        assert code not in POLICIES_2026
        assert code in PENDING_2026
    for code in policies_2026_g3.POLICIES:
        assert POLICIES_2026[code] is policies_2026_g3.POLICIES[code]


# --- Kentucky: 3.5% of (federal AGI - $3,360) -------------------------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(wages=D("40000")), D("1282.40")),    # 36,640 x 3.5%
        (dict(wages=D("100000")), D("3382.40")),   # 96,640 x 3.5%
        (dict(wages=D("250000")), D("8632.40")),   # 246,640 x 3.5%
        (MIXED, D("3207.40")),                     # 91,640 x 3.5%
    ],
)
def test_kentucky_2026(kwargs, expected) -> None:
    assert _tax("KY", **kwargs) == expected


def test_kentucky_2026_family_size_credit_steps() -> None:
    # Threshold = 2026 HHS guideline $15,960. MGI 18,000 is above 112%
    # (17,875.20) and not above 116% (18,513.60) -> 60% credit.
    # Tax (18,000 - 3,360) x 3.5% = 512.40; credit 307.44; net 204.96.
    result = compute_2026("KY", wages=D("18000"))
    assert result.total_tax == D("204.96")
    assert any("provisional" in w for w in result.warnings)
    # At exactly 100% of the threshold the credit equals the liability.
    assert _tax("KY", wages=D("15960")) == D("0.00")
    # Above 133% (21,226.80) no credit: (21,227 - 3,360) x 3.5% = 625.345.
    assert _tax("KY", wages=D("21227")) == D("625.35")


# --- Louisiana: 3% of (federal AGI - $12,838) -------------------------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(wages=D("40000")), D("814.86")),     # 27,162 x 3%
        (dict(wages=D("100000")), D("2614.86")),   # 87,162 x 3%
        (dict(wages=D("250000")), D("7114.86")),   # 237,162 x 3%
        (MIXED, D("2464.86")),                     # 82,162 x 3%
    ],
)
def test_louisiana_2026(kwargs, expected) -> None:
    assert _tax("LA", **kwargs) == expected


def test_louisiana_2026_eic_when_asserted() -> None:
    # Wages 15,000: tax (15,000 - 12,838) x 3% = 64.86; 5% x federal EIC 400 = 20.
    result = compute_2026(
        "LA", wages=D("15000"),
        federal_eitc_eligibility_asserted=True, federal_earned_income_credit=D("400"),
    )
    assert result.total_tax == D("44.86")


# --- Maine: schedule 5.8% / 6.75% over 27,400 / 7.15% over 64,850 -----------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # 40,000 - 15,700 - 5,300 = 19,000 x 5.8% = 1,102.00
        (dict(wages=D("40000")), D("1102.00")),
        # AGI <= 102,250 so no phase-out; TI 79,000: 4,117 + 14,150 x 7.15%
        (dict(wages=D("100000")), D("5128.73")),
        # deduction fully phased out (AGI - 102,250 >= 75,000); exemption intact
        # TI 244,700: 4,117 + 179,850 x 7.15% = 16,976.275
        (dict(wages=D("250000")), D("16976.28")),
        # TI 95,000 - 21,000 = 74,000: 4,117 + 9,150 x 7.15% = 4,771.225
        (MIXED, D("4771.23")),
    ],
)
def test_maine_2026(kwargs, expected) -> None:
    assert _tax("ME", **kwargs) == expected


def test_maine_2026_standard_deduction_phaseout_and_surcharge() -> None:
    # AGI 140,000: worksheet line 5 = 37,750/75,000 = 0.50333 -> 0.5033 (four
    # decimals); deduction 15,700 - 15,700 x 0.5033 = 15,700 - 7,901.81 = 7,798.19;
    # TI 140,000 - 7,798.19 - 5,300 = 126,901.81:
    # 4,117 + 62,051.81 x 7.15% = 4,117 + 4,436.7044 = 8,553.70
    result = compute_2026("ME", wages=D("140000"))
    assert result.total_tax == D("8553.70")
    assert not any("provisional" in w for w in result.warnings)
    # AGI 1,200,000: deduction and exemption fully phased out; TI 1,200,000:
    # 4,117 + 1,135,150 x 7.15% = 85,280.225 -> 85,280.23; surcharge
    # 2% x 200,000 = 4,000.
    assert _tax("ME", wages=D("1200000")) == D("89280.23")


# --- Maryland (state only): $3,400 std ded, $3,200 exemption ----------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # TI 33,400 -> table band midpoint 33,425: 90 + 30,425 x 4.75% = 1,535.19 -> 1,535
        (dict(wages=D("40000")), D("1535.00")),
        # TI 93,400 -> midpoint 93,425: 90 + 90,425 x 4.75% = 4,385.19 -> 4,385
        (dict(wages=D("100000")), D("4385.00")),
        # exemption 0 above 150,000; TI 246,600: 7,260 + 96,600 x 5.5% = 12,573
        (dict(wages=D("250000")), D("12573.00")),
        # TI 88,400 -> midpoint 88,425: 90 + 85,425 x 4.75% = 4,147.69 -> 4,148
        (MIXED, D("4148.00")),
    ],
)
def test_maryland_2026(kwargs, expected) -> None:
    assert _tax("MD", **kwargs) == expected


def test_maryland_2026_capital_gain_surtax_threshold() -> None:
    # FAGI exactly 350,000: no 2% tax. TI 346,600: 12,760 + 96,600 x 5.75%.
    assert _tax("MD", wages=D("340000"), net_long_term_gains=D("10000")) == D("18314.50")
    # FAGI 450,000: TI 446,600: 12,760 + 196,600 x 5.75% = 24,064.50
    # plus 2% x 50,000 net capital gain = 1,000.
    assert _tax("MD", wages=D("400000"), net_long_term_gains=D("50000")) == D("25064.50")


# --- Massachusetts: 5% / 8.5% short-term, $4,400 exemption, FICA <= $2,000 --
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(wages=D("40000")), D("1680.00")),    # (40,000 - 2,000 - 4,400) x 5%
        (dict(wages=D("100000")), D("4680.00")),   # 93,600 x 5%
        (dict(wages=D("250000")), D("12180.00")),  # 243,600 x 5%
        (MIXED, D("4430.00")),                     # 88,600 x 5%
    ],
)
def test_massachusetts_2026(kwargs, expected) -> None:
    assert _tax("MA", **kwargs) == expected


def test_massachusetts_2026_short_term_gain_and_surtax() -> None:
    # 80,000 wages + 10,000 STCG: 10,000 x 8.5% + 73,600 x 5% = 850 + 3,680.
    assert _tax("MA", wages=D("80000"), net_short_term_gains=D("10000")) == D("4530.00")
    # 1,200,000 wages: TI 1,193,600 x 5% = 59,680; surtax
    # (1,193,600 - 1,107,750) x 4% = 3,434.
    assert _tax("MA", wages=D("1200000")) == D("63114.00")
    # Just under the 2026 threshold: TI 1,107,750 -> no surtax.
    assert _tax("MA", wages=D("1114150")) == D("55387.50")


# --- Michigan: 4.25% of (federal AGI - $5,900) ------------------------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(wages=D("40000")), D("1449.25")),    # 34,100 x 4.25%
        (dict(wages=D("100000")), D("3999.25")),   # 94,100 x 4.25%
        (dict(wages=D("250000")), D("10374.25")),  # 244,100 x 4.25%
        (MIXED, D("3786.75")),                     # 89,100 x 4.25%
    ],
)
def test_michigan_2026(kwargs, expected) -> None:
    assert _tax("MI", **kwargs) == expected


# --- Minnesota: 5.35/6.8/7.85/9.85 at 33,310/109,430/203,150; $15,300 -------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # TI 24,700 x 5.35% = 1,321.45
        (dict(wages=D("40000")), D("1321.45")),
        # TI 84,700: 1,782.085 + 51,390 x 6.8% = 5,276.605
        (dict(wages=D("100000")), D("5276.61")),
        # deduction 15,300 - 3% x (250,000 - 244,400) = 15,132; TI 234,868:
        # 14,315.265 + 31,718 x 9.85% = 17,439.488
        (dict(wages=D("250000")), D("17439.49")),
        # TI 79,700: 1,782.085 + 46,390 x 6.8% = 4,936.605
        (MIXED, D("4936.61")),
    ],
)
def test_minnesota_2026(kwargs, expected) -> None:
    assert _tax("MN", **kwargs) == expected


def test_minnesota_2026_deduction_tiers_and_niit() -> None:
    # AGI 400,000: reduction 3% x 93,400 + 10% x 62,200 = 9,022 (< 80% = 12,240);
    # TI 393,722: 14,315.265 + 190,572 x 9.85% = 33,086.607
    assert _tax("MN", wages=D("400000")) == D("33086.61")
    # AGI 1,200,000 > 1,107,750: deduction cut 80% to 3,060; TI 1,196,940:
    # 14,315.265 + 993,790 x 9.85% = 112,203.58; NIIT 1% x (1,100,000 -
    # 1,000,000) = 1,000.
    assert (
        _tax("MN", wages=D("100000"), net_long_term_gains=D("1100000")) == D("113203.58")
    )
    # Minn. Stat. 290.033 taxes NII over $1,000,000, not AGI over $1,000,000:
    # 2,000,000 wages + 100,000 LTCG -> no NIIT. TI 2,096,940:
    # 14,315.265 + 1,893,790 x 9.85% = 200,853.58
    assert _tax("MN", wages=D("2000000"), net_long_term_gains=D("100000")) == D("200853.58")


def test_minnesota_2026_working_family_credit() -> None:
    # Wages 20,000: tax 4,700 x 5.35% = 251.45. WFC 4% x 9,690 = 387.60 -> 388,
    # below the 32,680 phase-out; refundable -> 251.45 - 388 = -136.55.
    result = compute_2026("MN", wages=D("20000"), federal_eitc_eligibility_asserted=True)
    assert result.total_tax == D("-136.55")
    # Wages 34,000: WFC 388 - round(12% x 1,320 = 158.40) = 230; tax 18,700 x 5.35%.
    assert _tax("MN", wages=D("34000"), federal_eitc_eligibility_asserted=True) == D("770.45")
    # Not asserted: credit omitted with a warning.
    unknown = compute_2026("MN", wages=D("20000"))
    assert unknown.total_tax == D("251.45")
    assert any("Working Family Credit" in w for w in unknown.warnings)


def test_minnesota_2026_niit_includes_interest() -> None:
    # Minn. Stat. 290.033(a): NII per IRC 1411(c), which includes interest.
    # NII = 300,000 interest + 900,000 dividends = 1,200,000;
    # surtax = 1% x (1,200,000 - 1,000,000) = 2,000 (before the fix interest was
    # dropped: NII 900,000 -> 0).
    result = compute_2026(
        "MN",
        wages=D("100000"),
        ordinary_dividends=D("900000"),
        federal_agi=D("1300000"),
        interest=D("300000"),
    )
    assert result.surtax == D("2000")
