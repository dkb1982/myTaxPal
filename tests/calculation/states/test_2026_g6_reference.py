"""2026 reference values for group 6: SC, UT, VT, VA, WA, WV, WI.

Hand calculations follow each state's 2026 statute / published parameters (see
the references in rules/states/2026/<st>.yaml). Profile: single, age 40,
full-year resident, W-2 wages plus the stated dividends/gains. "Mixed" means
wages $80,000 + $5,000 ordinary (all qualified) dividends + $10,000 LTCG, so
federal AGI is $95,000. Utah uses the federal standard deduction ($16,100 for
2026, Rev. Proc. 2025-32); no state in this group uses federal tax as an input.
Graduated schedules use the exact rate schedule, not tax-table midpoints.
"""

from decimal import Decimal as D  # noqa: N817 - compact exact-money fixtures

import pytest

from tax_estimator.calculation.states import policies_2026_g6
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


def _provisional(result) -> bool:
    return any("provisional" in w for w in result.warnings)


def test_group_6_registry() -> None:
    assert set(policies_2026_g6.POLICIES) == {"SC", "UT", "VT", "VA", "WA", "WV", "WI"}
    for code in policies_2026_g6.PENDING:
        assert code not in POLICIES_2026
        assert code in PENDING_2026
    for code in policies_2026_g6.POLICIES:
        assert POLICIES_2026[code] is policies_2026_g6.POLICIES[code]


# --- South Carolina: federal AGI - SCIAD; 1.99% to 30,000, 5.21% x TI - 966 --
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # AGI 40,000 <= 40,000: SCIAD 15,000; TI 25,000 x 1.99% = 497.50
        (dict(wages=D("40000")), D("497.50")),
        # AGI >= 95,000: SCIAD 0; 100,000 x 5.21% - 966 = 4,244
        (dict(wages=D("100000")), D("4244.00")),
        # 250,000 x 5.21% - 966 = 12,059
        (dict(wages=D("250000")), D("12059.00")),
        # SCIAD 0 at AGI 95,000; 44% x 10,000 LTCG = 4,400 deduction;
        # TI 90,600 x 5.21% - 966 = 3,754.26
        (MIXED, D("3754.26")),
    ],
)
def test_south_carolina_2026(kwargs, expected) -> None:
    assert _tax("SC", **kwargs) == expected


def test_south_carolina_2026_sciad_phaseout_and_eitc() -> None:
    # AGI 60,000: reduction 15,000 x 20,000/55,000 = 5,454.55 -> rounded down
    # to 5,450; SCIAD 9,550; TI 50,450 x 5.21% - 966 = 1,662.445 -> 1,662.45
    assert _tax("SC", wages=D("60000")) == D("1662.45")
    # Wages 19,000: TI 4,000 x 1.99% = 79.60; EITC 125% x 50 = 62.50 (< $200 cap)
    result = compute_2026(
        "SC", wages=D("19000"),
        federal_eitc_eligibility_asserted=True, federal_earned_income_credit=D("50"),
    )
    assert result.total_tax == D("17.10")


# --- Utah: 4.45% of AGI less taxpayer credit (6% x 16,100 = 966) -----------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # 1,780 - (966 - 1.3% x (40,000 - 18,696)) = 1,780 - 689.048 -> 1,090.95
        (dict(wages=D("40000")), D("1090.95")),
        # credit fully phased out (1.3% x 81,304 > 966): 4,450
        (dict(wages=D("100000")), D("4450.00")),
        (dict(wages=D("250000")), D("11125.00")),
        # 95,000 x 4.45% = 4,227.50; 1.3% x 76,304 = 991.95 > 966 -> no credit
        (MIXED, D("4227.50")),
    ],
)
def test_utah_2026(kwargs, expected) -> None:
    assert _tax("UT", **kwargs) == expected


def test_utah_2026_taxpayer_credit_is_provisional() -> None:
    # 30,000 x 4.45% = 1,335; credit 966 - 1.3% x 11,304 = 819.048 -> 819.05
    result = compute_2026("UT", wages=D("30000"))
    assert result.total_tax == D("515.95")
    assert _provisional(result)
    assert not _provisional(compute_2026("UT", wages=D("100000")))


# --- Vermont: AGI - 7,850 - 5,400; 3.35/6.6/7.6/8.75% (50,750/122,850/256,300)
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # TI 26,750 x 3.35% = 896.125
        (dict(wages=D("40000")), D("896.13")),
        # TI 86,750: 1,700 + 36,000 x 6.6% = 4,076
        (dict(wages=D("100000")), D("4076.00")),
        # TI 236,750: 6,459 + 113,900 x 7.6% = 15,115.40 (> 3% x 250,000)
        (dict(wages=D("250000")), D("15115.40")),
        # $5,000 exclusion (< 40% x FTI 78,900); TI 76,750: 1,700 + 26,000 x 6.6%
        (MIXED, D("3416.00")),
    ],
)
def test_vermont_2026(kwargs, expected) -> None:
    result = compute_2026("VT", **kwargs)
    assert result.total_tax == expected
    assert _provisional(result)


def test_vermont_2026_capital_gain_exclusion_capped_at_40_percent_of_fti() -> None:
    # AGI 20,000, FTI 3,900 -> cap 1,560; TI 20,000 - 1,560 - 13,250 = 5,190
    # x 3.35% = 173.865
    assert _tax("VT", wages=D("10000"), net_long_term_gains=D("10000")) == D("173.87")


# --- Virginia: AGI - 8,750 - 930; 2/3/5/5.75%; whole dollars ---------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(wages=D("40000")), D("1486.00")),    # 720 + 13,320 x 5.75% = 1,485.90
        (dict(wages=D("100000")), D("4936.00")),   # 720 + 73,320 x 5.75% = 4,935.90
        (dict(wages=D("250000")), D("13561.00")),  # 720 + 223,320 x 5.75% = 13,560.90
        (MIXED, D("4648.00")),                     # 720 + 68,320 x 5.75% = 4,648.40
    ],
)
def test_virginia_2026(kwargs, expected) -> None:
    assert _tax("VA", **kwargs) == expected


def test_virginia_2026_low_income_thresholds() -> None:
    # VAGI below 11,950: no tax.
    assert _tax("VA", wages=D("11900")) == D("0.00")
    # AGI 15,000 <= 2026 poverty guideline 15,960: TI 5,320 -> 120 + 320 x 5% =
    # 136; $300 low-income credit eliminates it.
    assert _tax("VA", wages=D("15000")) == D("0.00")
    # AGI 16,000 > 15,960: TI 6,320 -> 120 + 1,320 x 5% = 186, no credit.
    assert _tax("VA", wages=D("16000")) == D("186.00")


# --- Washington: no wage tax; 7% (+2.9% over $1M) of LTCG above $290,000 ----
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(wages=D("40000")), D("0.00")),
        (dict(wages=D("100000")), D("0.00")),
        (dict(wages=D("250000")), D("0.00")),
        (MIXED, D("0.00")),
    ],
)
def test_washington_2026(kwargs, expected) -> None:
    assert _tax("WA", **kwargs) == expected


def test_washington_2026_capital_gains_excise_tiers() -> None:
    # LTCG 500,000: (500,000 - 290,000) x 7% = 14,700
    result = compute_2026("WA", wages=D("100000"), net_long_term_gains=D("500000"))
    assert result.total_tax == D("14700.00")
    assert result.has_income_tax is False
    assert _provisional(result)
    # LTCG 1,500,000: 1,210,000 x 7% + 210,000 x 2.9% = 84,700 + 6,090
    assert _tax("WA", wages=D("0"), net_long_term_gains=D("1500000")) == D("90790.00")
    # Short-term gains are not long-term capital gains: no excise.
    assert _tax("WA", wages=D("0"), net_short_term_gains=D("400000")) == D("0.00")
    # Just below the 2026 deduction.
    assert _tax("WA", wages=D("0"), net_long_term_gains=D("290000")) == D("0.00")


# --- West Virginia: AGI - 2,000; 2.11%-4.58% (SB 392); whole dollars --------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(wages=D("40000")), D("1043.00")),    # 632.50 + 13,000 x 3.16% = 1,043.30
        (dict(wages=D("100000")), D("3691.00")),   # 1,950.50 + 38,000 x 4.58% = 3,690.90
        (dict(wages=D("250000")), D("10561.00")),  # 1,950.50 + 188,000 x 4.58% = 10,560.90
        (MIXED, D("3462.00")),                     # 1,950.50 + 33,000 x 4.58% = 3,461.90
    ],
)
def test_west_virginia_2026(kwargs, expected) -> None:
    assert _tax("WV", **kwargs) == expected


def test_west_virginia_2026_family_tax_credit_steps() -> None:
    # At the 2026 guideline (15,960): TI 13,960 -> 211 + 3,960 x 2.81% = 322.28
    # -> 322; 100% credit.
    assert _tax("WV", wages=D("15960")) == D("0.00")
    # MFAGI 17,000 is 1,040 above: 4th $300 step -> 60% credit.
    # TI 15,000: 211 + 5,000 x 2.81% = 351.50 -> 352; credit 211.20; net 140.80.
    result = compute_2026("WV", wages=D("17000"))
    assert result.total_tax == D("140.80")
    assert _provisional(result)
    # 18,661 > guideline + 2,700: no credit. TI 16,661: 211 + 6,661 x 2.81% = 398.17
    assert _tax("WV", wages=D("18661")) == D("398.00")


# --- Wisconsin: sliding std deduction (13,960; -12% over 20,120), $700, ------
# --- 3.5/4.4/5.3/7.65% (15,110/51,950/332,720); whole dollars -----------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # deduction 13,960 - 12% x 19,880 = 11,574.40 -> 11,574; TI 27,726:
        # 528.85 + 12,616 x 4.4% = 1,083.954
        (dict(wages=D("40000")), D("1084.00")),
        # deduction 13,960 - 12% x 79,880 = 4,374.40 -> 4,374; TI 94,926:
        # 2,149.81 + 42,976 x 5.3% = 4,427.538
        (dict(wages=D("100000")), D("4428.00")),
        # deduction 0; TI 249,300: 2,149.81 + 197,350 x 5.3% = 12,609.36
        (dict(wages=D("250000")), D("12609.00")),
        # 30% x 10,000 = 3,000 excluded; WI AGI 92,000; deduction 13,960 -
        # 12% x 71,880 = 5,334.40 -> 5,334; TI 85,966: 2,149.81 + 34,016 x 5.3%
        # = 3,952.658
        (MIXED, D("3953.00")),
    ],
)
def test_wisconsin_2026(kwargs, expected) -> None:
    result = compute_2026("WI", **kwargs)
    assert result.total_tax == expected
    assert _provisional(result)


def test_wisconsin_2026_standard_deduction_phaseout_edges() -> None:
    # At the 20,120 threshold the full 13,960 applies: TI 5,460 x 3.5% = 191.10
    assert _tax("WI", wages=D("20120")) == D("191.00")
    # AGI 136,000: deduction 13,960 - 12% x 115,880 = 54.40 -> 54; TI 135,246:
    # 2,149.81 + 83,296 x 5.3% = 6,564.498
    assert _tax("WI", wages=D("136000")) == D("6564.00")
