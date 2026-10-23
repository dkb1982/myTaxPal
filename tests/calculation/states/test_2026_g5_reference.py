"""2026 reference values for group 5: NC, ND, OH, OK, OR, PA, RI.

Hand calculations follow each state's 2026 law/published parameters (see the
references in rules/states/2026/<st>.yaml). Profile: single, age 40, full-year
resident, W-2 wages plus the stated dividends/gains. "Mixed" means wages $80,000
+ $5,000 ordinary (all qualified) dividends + $10,000 LTCG, so federal AGI is
$95,000. Federal taxable income (ND) is federal AGI less the 2026 federal single
standard deduction of $16,100 (Rev. Proc. 2025-32): $23,900 / $83,900 /
$233,900 / mixed $78,900.

Oregon subtracts federal income tax, hand-computed from the 2026 single
brackets (10% to $12,400, 12% to $50,400, 22% to $105,700, 24% to $201,775,
32% to $256,225) and 0%/15% capital-gain rates (0% limit $49,450):
  $40,000:  23,900 -> 1,240 + 11,500 x 12% = 2,620
  $100,000: 83,900 -> 5,800 + 33,500 x 22% = 13,170
  $250,000: 233,900 -> 41,024 + 32,125 x 32% = 51,304
  mixed:    ordinary 63,900 -> 5,800 + 13,500 x 22% = 8,770; 15,000 x 15% = 2,250;
            total 11,020
  $127,000: 110,900 -> 17,966 + 5,200 x 24% = 19,214
"""

from decimal import Decimal as D  # noqa: N817 - compact exact-money fixtures

import pytest

from tax_estimator.calculation.states import policies_2026_g5
from tax_estimator.calculation.states.policies_2026 import PENDING_2026, POLICIES_2026

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


def test_group_5_registry() -> None:
    assert set(policies_2026_g5.POLICIES) == {"NC", "ND", "OH", "OK", "OR", "PA", "RI"}
    for code in policies_2026_g5.PENDING:
        assert code not in POLICIES_2026
        assert code in PENDING_2026
    for code in policies_2026_g5.POLICIES:
        assert POLICIES_2026[code] is policies_2026_g5.POLICIES[code]


# --- North Carolina: 3.99% of (AGI - $12,750) (NC-30 2026) -------------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (W40, D("1087.28")),     # 27,250 x 3.99% = 1,087.275
        (W100, D("3481.28")),    # 87,250 x 3.99% = 3,481.275
        (W250, D("9466.28")),    # 237,250 x 3.99% = 9,466.275
        (MIXED, D("3281.78")),   # 82,250 x 3.99% = 3,281.775
    ],
)
def test_north_carolina_2026(kwargs, expected) -> None:
    assert _tax("NC", **kwargs) == expected


def test_north_carolina_2026_standard_deduction_floor() -> None:
    assert _tax("NC", wages=D("12750")) == D("0.00")
    assert _tax("NC", wages=D("13750")) == D("39.90")   # 1,000 x 3.99%


# --- North Dakota: FTI - 40% (QD + net capital gain); ND-1ES 2026 schedule ----
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (W40, D("0.00")),        # 23,900 <= 49,575
        (W100, D("669.34")),     # (83,900 - 49,575) x 1.95% = 669.3375
        (W250, D("3594.34")),    # (233,900 - 49,575) x 1.95% = 3,594.3375
        # 78,900 - 40% x 15,000 = 72,900; (72,900 - 49,575) x 1.95% = 454.8375
        (MIXED, D("454.84")),
    ],
)
def test_north_dakota_2026(kwargs, expected) -> None:
    assert _tax("ND", **kwargs) == expected


def test_north_dakota_2026_top_bracket() -> None:
    # FTI 283,900: 3,916.09 + (283,900 - 250,400) x 2.5% = 3,916.09 + 837.50
    assert _tax("ND", wages=D("300000")) == D("4753.59")
    # FTI exactly 49,575 (AGI 65,675) is still in the 0% bracket.
    assert _tax("ND", wages=D("65675")) == D("0.00")


# --- Ohio: AGI - MAGI-tiered exemption; $332 + 2.75% over $26,050; whole $ ---
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # exemption 2,400 -> 37,600; 332 + 11,550 x 2.75% = 649.625 -> 650
        (W40, D("650.00")),
        # exemption 1,900 -> 98,100; 332 + 72,050 x 2.75% = 2,313.375 -> 2,313
        (W100, D("2313.00")),
        # exemption 1,900 -> 248,100; 332 + 222,050 x 2.75% = 6,438.375 -> 6,438
        (W250, D("6438.00")),
        # exemption 1,900 -> 93,100; 332 + 67,050 x 2.75% = 2,175.875 -> 2,176
        (MIXED, D("2176.00")),
    ],
)
def test_ohio_2026(kwargs, expected) -> None:
    result = compute_2026("OH", **kwargs)
    assert result.total_tax == expected
    assert result.state_agi == result.starting_income  # city taxes read state AGI


def test_ohio_2026_cliff_exemption_credit_and_500k_limit() -> None:
    # 28,450 - 2,400 = 26,050: no tax at the threshold.
    assert _tax("OH", wages=D("28450")) == D("0.00")
    # 29,000 - 2,400 = 26,600: 332 + 550 x 2.75% = 347.125 -> 347, less $20 credit.
    assert _tax("OH", wages=D("29000")) == D("327.00")
    # MAGI 499,999: exemption 1,900 -> 498,099; 332 + 472,049 x 2.75% = 13,313.35
    assert _tax("OH", wages=D("499999")) == D("13313.00")
    # MAGI 500,000: no exemption; 332 + 473,950 x 2.75% = 13,365.625 -> 13,366
    assert _tax("OH", wages=D("500000")) == D("13366.00")


# --- Oklahoma: AGI - 6,350 - 1,000; HB 2764 schedule ------------------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (W40, D("1254.50")),     # 32,650: 109.25 + 25,450 x 4.5%
        (W100, D("3954.50")),    # 92,650: 109.25 + 85,450 x 4.5%
        (W250, D("10704.50")),   # 242,650: 109.25 + 235,450 x 4.5%
        (MIXED, D("3729.50")),   # 87,650: 109.25 + 80,450 x 4.5%
    ],
)
def test_oklahoma_2026(kwargs, expected) -> None:
    assert _tax("OK", **kwargs) == expected


def test_oklahoma_2026_low_brackets() -> None:
    assert _tax("OK", wages=D("11100")) == D("0.00")    # taxable 3,750 at 0%
    assert _tax("OK", wages=D("12250")) == D("28.75")   # taxable 4,900: 1,150 x 2.5%
    assert _tax("OK", wages=D("14550")) == D("109.25")  # 7,200: 28.75 + 2,300 x 3.5%


# --- Oregon: AGI - capped federal tax - 2,910; Chart S; $263 credit ----------
@pytest.mark.parametrize(
    ("kwargs", "federal_tax", "expected"),
    [
        # 40,000 - 2,620 - 2,910 = 34,470: 678 + 23,070 x 8.75% = 2,696.625; - 263
        (W40, D("2620"), D("2433.63")),
        # 100,000 - 8,750 - 2,910 = 88,340: 678 + 76,940 x 8.75% = 7,410.25; - 263
        (W100, D("13170"), D("7147.25")),
        # AGI >= 145,000: no subtraction, no credit; 247,090:
        # 10,618 + 122,090 x 9.9% = 22,704.91
        (W250, D("51304"), D("22704.91")),
        # 95,000 - 8,750 - 2,910 = 83,340: 678 + 71,940 x 8.75% = 6,972.75; - 263
        (MIXED, D("11020"), D("6709.75")),
    ],
)
def test_oregon_2026(kwargs, federal_tax, expected) -> None:
    result = compute_2026(
        "OR", federal_income_tax_after_nonrefundable_credits=federal_tax, **kwargs,
    )
    assert result.total_tax == expected
    assert any("provisional" in w for w in result.warnings)


def test_oregon_2026_federal_tax_phaseout_and_credit_limit() -> None:
    # AGI 127,000: limit 7,000; 127,000 - 7,000 - 2,910 = 117,090;
    # 678 + 105,690 x 8.75% = 9,925.875; no credit above $100,000.
    assert _tax(
        "OR", wages=D("127000"), federal_income_tax_after_nonrefundable_credits=D("19214"),
    ) == D("9925.88")
    # AGI 100,001: same limit, no exemption credit: 88,341 -> 7,410.3375
    assert _tax(
        "OR", wages=D("100001"), federal_income_tax_after_nonrefundable_credits=D("13170.22"),
    ) == D("7410.34")


# --- Pennsylvania: 3.07% of classes; Tax Forgiveness -------------------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (W40, D("1228.00")),     # 40,000 x 3.07%
        (W100, D("3070.00")),    # 100,000 x 3.07%
        (W250, D("7675.00")),    # 250,000 x 3.07%
        (MIXED, D("2916.50")),   # (80,000 + 5,000 + 10,000) x 3.07%
    ],
)
def test_pennsylvania_2026(kwargs, expected) -> None:
    result = compute_2026("PA", **kwargs)
    assert result.total_tax == expected
    assert result.starting_income == result.state_agi  # city taxes read state AGI


def test_pennsylvania_2026_forgiveness_and_class_losses() -> None:
    assert _tax("PA", wages=D("6500")) == D("0.00")
    # 7,000: 214.90 tax, 80% forgiven (2 steps of $250) -> 42.98
    assert _tax("PA", wages=D("7000")) == D("42.98")
    assert _tax("PA", wages=D("8751")) == D("268.66")   # 8,751 x 3.07%, no forgiveness
    # A net capital loss does not offset compensation: 50,000 x 3.07%.
    assert _tax("PA", wages=D("50000"), net_long_term_gains=D("-5000")) == D("1535.00")


# --- Rhode Island: AGI - 11,200 - 5,250 (phased out); ADV 2025-22 schedule ---
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (W40, D("883.13")),      # 23,550 x 3.75% = 883.125
        (W100, D("3148.13")),    # 83,550: 3,076.88 + 1,500 x 4.75%
        (W250, D("10857.17")),   # 233,550: 8,035.88 + 47,100 x 5.99%
        (MIXED, D("2945.63")),   # 78,550 x 3.75% = 2,945.625
    ],
)
def test_rhode_island_2026(kwargs, expected) -> None:
    assert _tax("RI", **kwargs) == expected


def test_rhode_island_2026_phaseout() -> None:
    # AGI 261,000: full amounts; 244,550: 8,035.88 + 58,100 x 5.99% = 11,516.07
    assert _tax("RI", wages=D("261000")) == D("11516.07")
    # AGI 270,000: ceil(9,000 / 7,450) = 2 steps -> 60%: 6,720 + 3,150;
    # 260,130: 8,035.88 + 73,680 x 5.99% = 12,449.312
    assert _tax("RI", wages=D("270000")) == D("12449.31")
    # AGI 291,000 > 290,800: nothing allowed; 8,035.88 + 104,550 x 5.99% = 14,298.425
    assert _tax("RI", wages=D("291000")) == D("14298.43")


def test_group_5_childless_eic_warning_when_unasserted() -> None:
    for state in ("OH", "OR", "PA", "RI"):
        kwargs = {}
        if state == "OR":
            kwargs["federal_income_tax_after_nonrefundable_credits"] = D("0")
        result = compute_2026(state, wages=D("15000"), **kwargs)
        assert any("earned income" in w.lower() or "working pennsylvanians" in w.lower()
                   for w in result.warnings), state
    ok = compute_2026("OK", wages=D("15000"))
    assert any("earned income credit omitted" in w for w in ok.warnings)
