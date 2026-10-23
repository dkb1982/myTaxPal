"""2026 reference values for group 2: DC, GA, HI, ID, IL, IN, IA, KS.

Hand calculations follow each state's 2026 law/published parameters (see the
references in rules/states/2026/<st>.yaml). Profile: single, age 40, full-year
resident, W-2 wages plus the stated dividends/gains. "Mixed" means wages $80,000
+ $5,000 ordinary (all qualified) dividends + $10,000 LTCG, so federal AGI is
$95,000. Federal taxable income (ID, IA) is federal AGI less the 2026 federal
single standard deduction of $16,100 (Rev. Proc. 2025-32). None of these states
taxes dividends or gains preferentially except Hawaii's 7.25% LTCG alternative.
"""

from decimal import Decimal as D  # noqa: N817 - compact exact-money fixtures

import pytest

from tax_estimator.calculation.states import policies_2026_g2
from tax_estimator.calculation.states.policies_2026 import PENDING_2026, POLICIES_2026
from tax_estimator.calculation.states.policy_common import StatePolicyError

from .helpers_2026 import compute_2026

MIXED = dict(
    wages=D("80000"),
    ordinary_dividends=D("5000"),
    qualified_dividends=D("5000"),
    net_long_term_gains=D("10000"),
)
W40, W100, W250 = (dict(wages=D(v)) for v in ("40000", "100000", "250000"))


def _tax(state: str, **kwargs) -> D:
    return compute_2026(state, **kwargs).total_tax


def test_group_2_registry() -> None:
    assert set(policies_2026_g2.POLICIES) == {"DC", "GA", "HI", "ID", "IL", "IN", "IA", "KS"}
    for code in policies_2026_g2.PENDING:
        assert code not in POLICIES_2026
        assert code in PENDING_2026
    for code in policies_2026_g2.POLICIES:
        assert POLICIES_2026[code] is policies_2026_g2.POLICIES[code]


# --- District of Columbia: schedule on AGI - $15,000 (D.C. Law 26-189) -------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (W40, D("1300.00")),     # 25,000: 400 + 15,000 x 6%
        (W100, D("5625.00")),    # 85,000: 3,500 + 25,000 x 8.5%
        (W250, D("18375.00")),   # 235,000: 3,500 + 175,000 x 8.5%
        (MIXED, D("5200.00")),   # 80,000: 3,500 + 20,000 x 8.5%
    ],
)
def test_dc_2026(kwargs, expected) -> None:
    result = compute_2026("DC", **kwargs)
    assert result.total_tax == expected
    assert any("provisional" in w for w in result.warnings)


def test_dc_2026_bracket_edge_and_childless_eic_guard() -> None:
    # Taxable exactly 250,000 (AGI 265,000): 3,500 + 190,000 x 8.5% = 19,650.
    assert _tax("DC", wages=D("265000")) == D("19650.00")
    # AGI 30,000: 15,000 taxable -> 400 + 5,000 x 6% = 700; EIC omitted with warning.
    low = compute_2026("DC", wages=D("30000"))
    assert low.total_tax == D("700.00")
    assert any("earned income tax credit omitted" in w for w in low.warnings)
    with pytest.raises(StatePolicyError):
        compute_2026(
            "DC", wages=D("30000"),
            federal_eitc_eligibility_asserted=True, federal_earned_income_credit=D("0"),
        )


# --- Georgia: 4.99% of (AGI - $15,000) (HB 463, 2026) ------------------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (W40, D("1247.50")),     # 25,000 x 4.99%
        (W100, D("4241.50")),    # 85,000 x 4.99%
        (W250, D("11726.50")),   # 235,000 x 4.99%
        (MIXED, D("3992.00")),   # 80,000 x 4.99%
    ],
)
def test_georgia_2026(kwargs, expected) -> None:
    assert _tax("GA", **kwargs) == expected


def test_georgia_2026_standard_deduction_floor() -> None:
    assert _tax("GA", wages=D("15000")) == D("0.00")
    low = compute_2026("GA", wages=D("19000"))   # 4,000 x 4.99% = 199.60
    assert low.total_tax == D("199.60")
    assert any("low income credit" in w for w in low.warnings)


# --- Hawaii: schedule on AGI - $8,000 - $1,144 (taxable = AGI - 9,144) --------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # 30,856: 859 + 6,856 x 6.8% = 1,325.208
        (W40, D("1325.21")),
        # 90,856: 2,539 + 42,856 x 7.6% = 5,796.056
        (W100, D("5796.06")),
        # 240,856: 16,466 + 15,856 x 9% = 17,893.04
        (W250, D("17893.04")),
        # 85,856; LTCG alt: 75,856 -> 2,539 + 27,856 x 7.6% = 4,656.056, + 10,000 x 7.25%
        # = 5,381.056 < regular 2,539 + 37,856 x 7.6% = 5,416.056
        (MIXED, D("5381.06")),
    ],
)
def test_hawaii_2026(kwargs, expected) -> None:
    assert _tax("HI", **kwargs) == expected


def test_hawaii_2026_capital_gain_floor() -> None:
    # AGI 60,000 -> taxable 50,856; preferential limited to 50,856 - 48,000 = 2,856.
    # Alt 2,539 + 2,856 x 7.25% = 2,746.06 < regular 2,539 + 2,856 x 7.6% = 2,756.056.
    result = compute_2026("HI", wages=D("50000"), net_long_term_gains=D("10000"))
    assert result.total_tax == D("2746.06")


# --- Idaho: 5.3% x (federal taxable income - $4,938 provisional), less $155 ---
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (W40, D("849.99")),      # (23,900 - 4,938) x 5.3% = 1,004.986 -> 1,004.99 - 155
        (W100, D("4029.99")),    # 78,962 x 5.3% = 4,184.986 -> 4,184.99 - 155
        (W250, D("11979.99")),   # 228,962 x 5.3% = 12,134.986 -> 12,134.99 - 155
        (MIXED, D("3764.99")),   # (78,900 - 4,938) x 5.3% = 3,919.986 -> 3,919.99 - 155
    ],
)
def test_idaho_2026(kwargs, expected) -> None:
    result = compute_2026("ID", **kwargs)
    assert result.total_tax == expected
    assert any("provisional" in w for w in result.warnings)


def test_idaho_2026_zero_band_and_refundable_food_credit() -> None:
    # Federal taxable 3,900 is inside the $4,938 zero band; food credit refunds 155.
    assert _tax("ID", wages=D("20000")) == D("-155.00")


# --- Illinois: 4.95% x (AGI - $2,925 unless AGI > $250,000) ------------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (W40, D("1835.21")),     # 37,075 x 4.95% = 1,835.2125
        (W100, D("4805.21")),    # 97,075 x 4.95% = 4,805.2125
        (W250, D("12230.21")),   # AGI not over 250,000: 247,075 x 4.95% = 12,230.2125
        (MIXED, D("4557.71")),   # 92,075 x 4.95% = 4,557.7125
    ],
)
def test_illinois_2026(kwargs, expected) -> None:
    assert _tax("IL", **kwargs) == expected


def test_illinois_2026_exemption_cliff() -> None:
    # One dollar over $250,000 loses the exemption: 250,001 x 4.95% = 12,375.0495.
    assert _tax("IL", wages=D("250001")) == D("12375.05")


def test_illinois_2026_eic_when_asserted() -> None:
    # 15,000 wages: (15,000 - 2,925) x 4.95% = 597.7125; EIC 20% x 300 = 60 refundable.
    result = compute_2026(
        "IL", wages=D("15000"),
        federal_eitc_eligibility_asserted=True, federal_earned_income_credit=D("300"),
    )
    assert result.total_tax == D("537.71")


# --- Indiana: 2.95% x (AGI - $1,000) (state tax only) ------------------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (W40, D("1150.50")),     # 39,000 x 2.95%
        (W100, D("2920.50")),    # 99,000 x 2.95%
        (W250, D("7345.50")),    # 249,000 x 2.95%
        (MIXED, D("2773.00")),   # 94,000 x 2.95%
    ],
)
def test_indiana_2026(kwargs, expected) -> None:
    assert _tax("IN", **kwargs) == expected


# --- Iowa: 3.8% x federal taxable income - $40 credit ------------------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (W40, D("868.20")),      # 23,900 x 3.8% = 908.20 - 40
        (W100, D("3148.20")),    # 83,900 x 3.8% = 3,188.20 - 40
        (W250, D("8848.20")),    # 233,900 x 3.8% = 8,888.20 - 40
        (MIXED, D("2958.20")),   # 78,900 x 3.8% = 2,998.20 - 40
    ],
)
def test_iowa_2026(kwargs, expected) -> None:
    assert _tax("IA", **kwargs) == expected


def test_iowa_2026_refundable_eic_and_limited_exemption_credit() -> None:
    # Federal taxable 0 -> tax 0; $40 credit limited to 0; EIC 15% x 300 = 45 refunded.
    result = compute_2026(
        "IA", wages=D("15000"),
        federal_eitc_eligibility_asserted=True, federal_earned_income_credit=D("300"),
    )
    assert result.total_tax == D("-45.00")


# --- Kansas: taxable = AGI - 3,605 - 9,160; $50-row table to $100,000 --------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # 27,235 -> row 27,201-27,250, midpoint 27,225.5: 1,196 + 4,225.5 x 5.58% = 1,431.78
        (W40, D("1432.00")),
        # 87,235 -> midpoint 87,225.5: 1,196 + 64,225.5 x 5.58% = 4,779.78
        (W100, D("4780.00")),
        # 237,235 (schedule): 1,196 + 214,235 x 5.58% = 13,150.313
        (W250, D("13150.31")),
        # 82,235 -> midpoint 82,225.5: 1,196 + 59,225.5 x 5.58% = 4,500.78
        (MIXED, D("4501.00")),
    ],
)
def test_kansas_2026(kwargs, expected) -> None:
    assert _tax("KS", **kwargs) == expected


def test_kansas_2026_table_row_edges() -> None:
    # Taxable exactly 40,000 sits in row 39,951-40,000 (published 2025 table: $2,143;
    # 2026 rates/threshold unchanged): midpoint 39,975.5 -> 2,143.23.
    assert _tax("KS", wages=D("52765")) == D("2143.00")
    # Taxable 100,000 is the last table row (99,951-100,000 -> $5,491).
    assert _tax("KS", wages=D("112765")) == D("5491.00")
    # Taxable 100,001 uses the schedule: 1,196 + 77,001 x 5.58% = 5,492.6558.
    assert _tax("KS", wages=D("112766")) == D("5492.66")
