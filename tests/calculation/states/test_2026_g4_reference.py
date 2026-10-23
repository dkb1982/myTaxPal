"""2026 reference values for group 4: MS, MO, MT, NE, NJ, NM, NY.

Hand calculations follow each state's 2026 law/forms (see the references in
rules/states/2026/<st>.yaml). Profile: single, age 40, full-year resident, W-2
wages plus the stated dividends/gains. "Mixed" means wages $80,000 + $5,000
ordinary (all qualified) dividends + $10,000 LTCG, so federal AGI is $95,000.

2026 federal inputs (Rev. Proc. 2025-32 single brackets, $16,100 standard
deduction), used by Missouri's federal tax deduction:
  $40,000:  FTI 23,900 -> 1,240 + 11,500 x 12% = 2,620
  $100,000: FTI 83,900 -> 5,800 + 33,500 x 22% = 13,170
  $125,000: FTI 108,900 -> 17,966 + 3,200 x 24% = 18,734
  $250,000: FTI 233,900 -> 41,024 + 32,125 x 32% = 51,304
  Mixed:    FTI 78,900; ordinary 63,900 -> 5,800 + 13,500 x 22% = 8,770;
            15,000 preferential all above the 0% limit (49,450) at 15% = 2,250;
            total 11,020
"""

from decimal import Decimal as D  # noqa: N817 - compact exact-money fixtures

import pytest

from tax_estimator.calculation.states import policies_2026_g4
from tax_estimator.calculation.states.policies_2026 import PENDING_2026, POLICIES_2026

from .helpers_2026 import compute_2026

MIXED = dict(
    wages=D("80000"),
    ordinary_dividends=D("5000"),
    qualified_dividends=D("5000"),
    net_long_term_gains=D("10000"),
)
FED_TAX = {
    "40k": D("2620"),
    "100k": D("13170"),
    "125k": D("18734"),
    "250k": D("51304"),
    "mixed": D("11020"),
}


def _tax(state: str, **kwargs) -> D:
    return compute_2026(state, **kwargs).total_tax


def test_group_4_registry() -> None:
    assert set(policies_2026_g4.POLICIES) == {"MS", "MO", "MT", "NE", "NJ", "NM", "NY"}
    assert policies_2026_g4.PENDING == {}
    for code in policies_2026_g4.PENDING:
        assert code not in POLICIES_2026
        assert code in PENDING_2026
    for code in policies_2026_g4.POLICIES:
        assert POLICIES_2026[code] is policies_2026_g4.POLICIES[code]


# --- Mississippi: 4% of (AGI - 2,300 - 6,000 - 10,000 zero band) -------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(wages=D("40000")), D("868.00")),     # 31,700 - 10,000 = 21,700 x 4%
        (dict(wages=D("100000")), D("3268.00")),   # 81,700 x 4%
        (dict(wages=D("250000")), D("9268.00")),   # 231,700 x 4%
        (MIXED, D("3068.00")),                     # 86,700 - 10,000 = 76,700 x 4%
        (dict(wages=D("18300")), D("0.00")),       # taxable exactly 10,000
    ],
)
def test_mississippi_2026(kwargs, expected) -> None:
    assert _tax("MS", **kwargs) == expected


# --- Missouri: 2026 chart ($1,348 bands; $263 + 4.7% over $9,436) -----------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # MO AGI 40,000 -> 25% x 2,620 = 655; TI 40,000 - 655 - 16,100 = 23,245
        # 263 + 13,809 x 4.7% = 912.023
        (dict(wages=D("40000"), federal_income_tax_after_nonrefundable_credits=FED_TAX["40k"]),
         D("912.02")),
        # 15% x 13,170 = 1,975.50; TI 81,924.50; 263 + 72,488.50 x 4.7% = 3,669.9595
        (dict(wages=D("100000"), federal_income_tax_after_nonrefundable_credits=FED_TAX["100k"]),
         D("3669.96")),
        # 0%; TI 233,900; 263 + 224,464 x 4.7% = 10,812.808
        (dict(wages=D("250000"), federal_income_tax_after_nonrefundable_credits=FED_TAX["250k"]),
         D("10812.81")),
        # LTCG 10,000 subtracted -> MO AGI 85,000 -> 15% x 11,020 = 1,653
        # TI 95,000 - 10,000 - 1,653 - 16,100 = 67,247; 263 + 57,811 x 4.7% = 2,980.117
        (dict(MIXED, federal_income_tax_after_nonrefundable_credits=FED_TAX["mixed"]),
         D("2980.12")),
    ],
)
def test_missouri_2026(kwargs, expected) -> None:
    result = compute_2026("MO", **kwargs)
    assert result.total_tax == expected
    assert any("provisional" in w for w in result.warnings)


def test_missouri_2026_federal_deduction_percentage_boundary() -> None:
    # MO AGI 125,000 -> 5% x 18,734 = 936.70; TI 107,963.30
    # 263 + 98,527.30 x 4.7% = 4,893.7831
    assert _tax(
        "MO", wages=D("125000"), federal_income_tax_after_nonrefundable_credits=FED_TAX["125k"]
    ) == D("4893.78")
    # MO AGI 125,001 -> 0%; TI 108,901; 263 + 99,465 x 4.7% = 4,937.855
    assert _tax(
        "MO", wages=D("125001"), federal_income_tax_after_nonrefundable_credits=D("18734.24")
    ) == D("4937.86")


# --- Montana: FTI; 4.7% to 47,500, 5.65% above; LTCG 3.0%/4.1% --------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(wages=D("40000")), D("1123.30")),    # 23,900 x 4.7%
        (dict(wages=D("100000")), D("4289.10")),   # 2,232.50 + 36,400 x 5.65%
        (dict(wages=D("250000")), D("12764.10")),  # 2,232.50 + 186,400 x 5.65%
        # FTI 78,900; LTCG 10,000; ordinary 68,900 -> 2,232.50 + 21,400 x 5.65%
        # = 3,441.60; ordinary above 47,500 so LTCG all 4.1% = 410
        (MIXED, D("3851.60")),
    ],
)
def test_montana_2026(kwargs, expected) -> None:
    assert _tax("MT", **kwargs) == expected


def test_montana_2026_capital_gain_straddles_threshold() -> None:
    # Wages 50,000 + LTCG 30,000: FTI 63,900, ordinary 33,900 x 4.7% = 1,593.30;
    # LTCG 13,600 x 3% = 408 + 16,400 x 4.1% = 672.40 -> 2,673.70
    assert _tax("MT", wages=D("50000"), net_long_term_gains=D("30000")) == D("2673.70")


# --- Nebraska: (AGI - 8,850) on 2026 schedule, less $176 credit -------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # 31,150: 825.71 + 6,390 x 4.55% = 1,116.455 -> 1,116.46 - 176
        (dict(wages=D("40000")), D("940.46")),
        # 91,150: 825.71 + 66,390 x 4.55% = 3,846.455 -> 3,846.46 - 176
        (dict(wages=D("100000")), D("3670.46")),
        # 241,150: 825.71 + 216,390 x 4.55% = 10,671.455 -> 10,671.46 - 176
        (dict(wages=D("250000")), D("10495.46")),
        # 86,150: 825.71 + 61,390 x 4.55% = 3,618.955 -> 3,618.96 - 176
        (MIXED, D("3442.96")),
    ],
)
def test_nebraska_2026(kwargs, expected) -> None:
    assert _tax("NE", **kwargs) == expected


def test_nebraska_2026_personal_credit_limited_to_tax() -> None:
    # 6,150: 101.60 + 2,020 x 3.51% = 172.502 -> credit limited to tax.
    assert _tax("NE", wages=D("15000")) == D("0.00")


# --- New Jersey: gross income - $1,000 on Table A ---------------------------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(wages=D("40000")), D("682.50")),     # 39,000 x .035 - 682.50
        (dict(wages=D("100000")), D("4180.05")),   # 99,000 x .0637 - 2,126.25
        (dict(wages=D("250000")), D("13735.05")),  # 249,000 x .0637 - 2,126.25
        (MIXED, D("3861.55")),                     # 94,000 x .0637 - 2,126.25
    ],
)
def test_new_jersey_2026(kwargs, expected) -> None:
    assert _tax("NJ", **kwargs) == expected


def test_new_jersey_2026_ten_thousand_threshold() -> None:
    assert _tax("NJ", wages=D("10000")) == D("0.00")
    # 10,001 - 1,000 = 9,001 x 1.4% = 126.014
    assert _tax("NJ", wages=D("10001")) == D("126.01")


# --- New Mexico: FTI less capital-gain deduction; PIT-1 table <= $100,000 ---
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        # 23,900 -> band 23,800-23,900, midpoint 23,850:
        # 434.50 + 7,350 x 4.3% = 750.55 -> 751
        (dict(wages=D("40000")), D("751.00")),
        # 83,900 -> midpoint 83,850: 2,716.50 + 17,350 x 4.9% = 3,566.65 -> 3,567
        (dict(wages=D("100000")), D("3567.00")),
        # 233,900 > 100,000 -> statute: 9,748 + 23,900 x 5.9% = 11,158.10
        (dict(wages=D("250000")), D("11158.10")),
        # 78,900 - 2,500 = 76,400 -> midpoint 76,350:
        # 2,716.50 + 9,850 x 4.9% = 3,199.15 -> 3,199
        (MIXED, D("3199.00")),
    ],
)
def test_new_mexico_2026(kwargs, expected) -> None:
    assert _tax("NM", **kwargs) == expected


def test_new_mexico_2026_low_middle_income_exemption() -> None:
    # AGI 30,000: exemption 2,500 - 15% x 10,000 = 1,000; TI 30,000 - 16,100
    # - 1,000 = 12,900 -> midpoint 12,850: 82.50 + 7,350 x 3.2% = 317.70 -> 318
    # (matches the 2025 TRD table row 12,800-12,900 = $318; same statute).
    assert _tax("NM", wages=D("30000")) == D("318.00")


# --- New York: (AGI - 8,000) on 2026 schedule + §601(d-5) supplemental -------
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(wages=D("40000")), D("1563.40")),    # 586 + 18,100 x 5.4%
        (dict(wages=D("100000")), D("4860.65")),   # 4,191 + 11,350 x 5.9%
        # 242,000: 12,141 + 26,600 x 6.85% = 13,963.10; supplemental
        # 567 + 2,047 x (34,600 / 50,000 = .692) = 1,983.524
        (dict(wages=D("250000")), D("15946.62")),
        (MIXED, D("4565.65")),                     # 4,191 + 6,350 x 5.9%
    ],
)
def test_new_york_2026(kwargs, expected) -> None:
    assert _tax("NY", **kwargs) == expected


def test_new_york_2026_supplemental_tax_phase_in() -> None:
    # AGI 130,000, TI 122,000: 4,191 + 41,350 x 5.9% = 6,630.65;
    # 567 x (22,350 / 50,000 = .447) = 253.449
    result = compute_2026("NY", wages=D("130000"))
    assert result.recapture == D("253.45")
    assert result.total_tax == D("6884.10")
    # AGI 200,000 (>= 157,650): full 567; TI 192,000: 4,191 + 111,350 x 5.9%
    assert _tax("NY", wages=D("200000")) == D("11327.65")
    # AGI exactly 107,650: no supplemental tax.
    assert compute_2026("NY", wages=D("107650")).recapture == D("0.00")


def test_new_york_2026_household_credit() -> None:
    # AGI 20,000, TI 12,000: 473 + 300 x 5.15% = 488.45; household credit $45.
    assert _tax("NY", wages=D("20000")) == D("443.45")
    # AGI 28,001: no household credit; TI 20,001: 586 + 6,101 x 5.4% = 915.454
    assert _tax("NY", wages=D("28001")) == D("915.45")
