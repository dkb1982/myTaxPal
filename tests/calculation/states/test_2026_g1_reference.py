"""2026 source-reference tests for group 1 (AL, AZ, AR, CA, CO, CT, DE).

Every expected value is hand-computed below from the official 2026 form or
worksheet logic cited in rules/states/2026/<st>.yaml, not from the code.

Federal inputs (2026, single, Rev. Proc. 2025-32: standard deduction $16,100;
brackets 10% to $12,400, 12% to $50,400 ($1,240 base), 22% to $105,700
($5,800), 24% to $201,775 ($17,966), 32% to $256,225 ($41,024); 0% capital-gain
rate up to $49,450 of taxable income):
  wages $40,000:  taxable 23,900; tax 1,240 + 11,500 x .12 = 2,620
  wages $100,000: taxable 83,900; tax 5,800 + 33,500 x .22 = 13,170
  wages $250,000: taxable 233,900; tax 41,024 + 32,125 x .32 = 51,304
  mixed (80,000 wages + 5,000 qualified dividends + 10,000 LTCG): AGI 95,000;
    taxable 78,900; ordinary 63,900 -> 5,800 + 13,500 x .22 = 8,770; the
    15,000 preferential income sits above $49,450 -> 15% = 2,250; total 11,020
  wages $30,000:  taxable 13,900; tax 1,240 + 1,500 x .12 = 1,420
  No NIIT (investment income/MAGI below $200,000), no refundable credits.
"""

from decimal import Decimal as D  # noqa: N817 - compact exact-money fixtures

import pytest

from tax_estimator.calculation.states import policies_2026_g1
from tax_estimator.calculation.states.policies_2026 import PENDING_2026, POLICIES_2026

from .helpers_2026 import compute_2026

FED = {
    "w40": D("2620"),
    "w100": D("13170"),
    "w250": D("51304"),
    "mixed": D("11020"),
}

SCENARIOS = {
    "w40": {"wages": D("40000")},
    "w100": {"wages": D("100000")},
    "w250": {"wages": D("250000")},
    "mixed": {
        "wages": D("80000"),
        "ordinary_dividends": D("5000"),
        "qualified_dividends": D("5000"),
        "net_long_term_gains": D("10000"),
    },
}


def _run(state: str, scenario: str, **extra):
    return compute_2026(
        state,
        federal_income_tax_after_nonrefundable_credits=FED[scenario],
        **SCENARIOS[scenario],
        **extra,
    )


# --- Registry ---------------------------------------------------------------


def test_group1_registry_partition() -> None:
    assert set(policies_2026_g1.POLICIES) == {"AL", "AZ", "CA", "CT", "DE"}
    assert set(policies_2026_g1.PENDING) == {"AR", "CO"}
    for state in policies_2026_g1.PENDING:
        assert state not in policies_2026_g1.POLICIES
        assert state not in POLICIES_2026
        assert state in PENDING_2026


# --- Alabama ----------------------------------------------------------------
# Form 40ES 2026: AGI - standard deduction (AGI >= $35,500 -> $2,500) - federal
# tax - $1,500 exemption; tax $110 + 5% over $3,000.
#   w40:   40,000 - 2,500 - 2,620 - 1,500 = 33,380 -> 110 + 30,380 x .05 = 1,629.00
#   w100: 100,000 - 2,500 - 13,170 - 1,500 = 82,830 -> 110 + 79,830 x .05 = 4,101.50
#   w250: 250,000 - 2,500 - 51,304 - 1,500 = 194,696 -> 110 + 191,696 x .05 = 9,694.80
#   mixed: 95,000 - 2,500 - 11,020 - 1,500 = 79,980 -> 110 + 76,980 x .05 = 3,959.00


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [("w40", "1629.00"), ("w100", "4101.50"), ("w250", "9694.80"), ("mixed", "3959.00")],
)
def test_alabama_reference(scenario: str, expected: str) -> None:
    assert _run("AL", scenario).total_tax == D(expected)


def test_alabama_sliding_standard_deduction_band() -> None:
    # AGI 30,000 is in the $30,000-$30,499 chart row: $2,775.
    # 30,000 - 2,775 - 1,420 - 1,500 = 24,305 -> 110 + 21,305 x .05 = 1,175.25
    result = compute_2026(
        "AL", wages=D("30000"), federal_income_tax_after_nonrefundable_credits=D("1420")
    )
    assert result.deduction_amount == D("2775")
    assert result.total_tax == D("1175.25")


# --- Arizona ----------------------------------------------------------------
# 2.5% x (AZ AGI - $16,100 provisional standard deduction).
#   w40: 23,900 x .025 = 597.50; w100: 83,900 x .025 = 2,097.50;
#   w250: 233,900 x .025 = 5,847.50
#   mixed: 25% post-2011 LTCG subtraction 2,500 -> AZ AGI 92,500;
#          76,400 x .025 = 1,910.00


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [("w40", "597.50"), ("w100", "2097.50"), ("w250", "5847.50")],
)
def test_arizona_reference(scenario: str, expected: str) -> None:
    result = _run("AZ", scenario)
    assert result.total_tax == D(expected)
    assert any("(provisional)" in w and "AZ 2026 standard deduction" in w for w in result.warnings)


def test_arizona_mixed_with_post_2011_gain() -> None:
    result = _run("AZ", "mixed", az_post_2011_eligible_long_term_gains=D("10000"))
    assert result.total_tax == D("1910.00")


def test_arizona_requires_post_2011_gain_split() -> None:
    from tax_estimator.calculation.states.policy_common import StatePolicyError

    with pytest.raises(StatePolicyError):
        _run("AZ", "mixed")


def test_arizona_low_income_excise_credit_warning() -> None:
    result = compute_2026("AZ", wages=D("12000"))
    assert result.total_tax == D("0.00")
    assert any("43-1072.01" in w for w in result.warnings)


# --- California -------------------------------------------------------------
# FTB 2026 Schedule X; $5,900 standard deduction; $158 exemption credit.
#   w40:  34,100 -> 428.58 + 6,943 x .04 = 706.30; - 158 = 548.30
#   w100: 94,100 -> 3,310.88 + 18,903 x .093 = 5,068.859 -> 5,068.86; - 158 = 4,910.86
#   w250: 244,100 -> 3,310.88 + 168,903 x .093 = 19,018.859 -> 19,018.86; - 158 = 18,860.86
#   mixed: 89,100 -> 3,310.88 + 13,903 x .093 = 4,603.859 -> 4,603.86; - 158 = 4,445.86


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [("w40", "548.30"), ("w100", "4910.86"), ("w250", "18860.86"), ("mixed", "4445.86")],
)
def test_california_reference(scenario: str, expected: str) -> None:
    assert _run("CA", scenario).total_tax == D(expected)


def test_california_exemption_credit_phaseout() -> None:
    # AGI 270,000: excess over $260,778 = 9,222 -> ceil(9,222/2,500) = 4 -> $24;
    # credit 158 - 24 = 134. Taxable 264,100 -> 3,310.88 + 188,903 x .093
    # = 20,878.859 -> 20,878.86; - 134 = 20,744.86.
    result = compute_2026("CA", wages=D("270000"))
    assert result.total_tax == D("20744.86")
    assert any("260,778" in w and "(provisional)" in w for w in result.warnings)


def test_california_behavioral_health_services_tax() -> None:
    # Taxable 1,094,100 -> 74,675.27 + 325,887 x .123 = 114,759.371 -> 114,759.37;
    # +1% x 94,100 = 941.00; exemption credit fully phased out.
    result = compute_2026("CA", wages=D("1100000"))
    assert result.total_tax == D("115700.37")


def test_california_caleitc_warning_below_ceiling() -> None:
    result = compute_2026("CA", wages=D("20000"))
    assert any("CalEITC" in w for w in result.warnings)
    assert not any("CalEITC" in w for w in _run("CA", "w40").warnings)


# --- Connecticut ------------------------------------------------------------
# CT-1040ES 2026 Tables A-E (single).
#   w40:  exemption 5,000 (AGI 39,001-40,000); taxable 35,000 -> 200 + 25,000 x .045
#         = 1,325; Table C 0; D 0; Table E .10 -> 132.50; 1,192.50
#   w100: exemption 0; 2,000 + 50,000 x .055 = 4,750; Table C (96,500-101,500) 225;
#         D 0; E .00 -> 4,975.00
#   w250: 10,750 + 50,000 x .065 = 14,000; C 250; D (245,000-250,000) 1,150 -> 15,400.00
#   mixed: 2,000 + 45,000 x .055 = 4,475; C (91,500-96,500) 200 -> 4,675.00


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [("w40", "1192.50"), ("w100", "4975.00"), ("w250", "15400.00"), ("mixed", "4675.00")],
)
def test_connecticut_reference(scenario: str, expected: str) -> None:
    assert _run("CT", scenario).total_tax == D(expected)


def test_connecticut_recapture_boundary() -> None:
    # AGI 105,001: 4,750 + 5,001 x .06 = 5,050.06; C 250; D first band 25 -> 5,325.06
    assert compute_2026("CT", wages=D("105001")).total_tax == D("5325.06")
    # AGI 105,000: D 0 -> 4,750 + 5,000 x .06 + 250 = 5,300.00
    assert compute_2026("CT", wages=D("105000")).total_tax == D("5300.00")


# --- Delaware ---------------------------------------------------------------
# 2026 PIT-EST schedule; $3,250 standard deduction; $110 personal credit.
#   w40:  36,750 -> 1,001 + 11,750 x .0555 = 1,653.125 -> 1,653.13; - 110 = 1,543.13
#   w100: 96,750 -> 2,943.50 + 36,750 x .066 = 5,369.00; - 110 = 5,259.00
#   w250: 246,750 -> 2,943.50 + 186,750 x .066 = 15,269.00; - 110 = 15,159.00
#   mixed: 91,750 -> 2,943.50 + 31,750 x .066 = 5,039.00; - 110 = 4,929.00


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [("w40", "1543.13"), ("w100", "5259.00"), ("w250", "15159.00"), ("mixed", "4929.00")],
)
def test_delaware_reference(scenario: str, expected: str) -> None:
    assert _run("DE", scenario).total_tax == D(expected)


def test_delaware_low_income_and_eitc_warning() -> None:
    # Wages 10,000: 6,750 -> 66 + 1,750 x .039 = 134.25; - 110 = 24.25.
    result = compute_2026("DE", wages=D("10000"))
    assert result.total_tax == D("24.25")
    assert any("Delaware earned income tax credit omitted" in w for w in result.warnings)
    assert not _run("DE", "w40").warnings
