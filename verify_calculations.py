#!/usr/bin/env python3
"""
Federal Tax Calculation Verification Script
============================================
Tests the calculation engine against hand-calculated expected values
using IRS 2025 brackets, deductions, and payroll tax rules.

Each test case includes the manual calculation so results can be audited.
"""

import sys
from decimal import Decimal
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from tax_estimator.calculation.engine import CalculationEngine
from tax_estimator.models.tax_input import (
    TaxInput, FilingStatus, WageIncome, SelfEmploymentIncome,
    InterestDividendIncome, CapitalGains, RetirementIncome,
    Adjustments, ItemizedDeductions, TaxpayerInfo, SpouseInfo, Dependent,
)

engine = CalculationEngine()

PASS = 0
FAIL = 0
ERRORS = []


def check(label, actual, expected, tolerance=1):
    """Compare actual vs expected with tolerance (default $1 for rounding)."""
    global PASS, FAIL
    actual_val = float(actual) if actual is not None else 0
    expected_val = float(expected)
    diff = abs(actual_val - expected_val)
    if diff <= tolerance:
        PASS += 1
        print(f"  ✅ {label}: ${actual_val:,.2f} (expected ${expected_val:,.2f})")
    else:
        FAIL += 1
        msg = f"  ❌ {label}: ${actual_val:,.2f} (expected ${expected_val:,.2f}, diff ${diff:,.2f})"
        print(msg)
        ERRORS.append(msg)


def test_1_single_w2_75k():
    """
    Test 1: Single filer, $75,000 W-2 wages
    -----------------------------------------
    Gross income:          $75,000
    Standard deduction:    -$15,000
    Taxable income:        $60,000

    Tax calculation (Single 2025 brackets):
      10% on $0-$11,925         = $1,192.50
      12% on $11,925-$48,475    = $4,386.00
      22% on $48,475-$60,000    = $2,535.50
      Total tax:                = $8,114.00

    Marginal rate: 22%
    Effective rate: $8,114 / $75,000 = 10.82%
    """
    print("\n" + "=" * 60)
    print("TEST 1: Single, $75k W-2 wages")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="TX",  # No state income tax
        wages=[WageIncome(employer_name="Acme", employer_state="TX", gross_wages=Decimal("75000"))],
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Gross income", f.gross_income, 75000)
    check("AGI", f.adjusted_gross_income, 75000)
    check("Taxable income", f.taxable_income, 60000)
    check("Tax before credits", f.tax_before_credits, 8114)
    check("Total tax", f.total_tax, 8114)


def test_2_mfj_w2_150k():
    """
    Test 2: MFJ, $150,000 W-2 wages
    ---------------------------------
    Gross income:          $150,000
    Standard deduction:    -$30,000
    Taxable income:        $120,000

    Tax calculation (MFJ 2025 brackets):
      10% on $0-$23,850         = $2,385.00
      12% on $23,850-$96,950    = $8,772.00
      22% on $96,950-$120,000   = $5,071.00
      Total tax:                = $16,228.00
    """
    print("\n" + "=" * 60)
    print("TEST 2: MFJ, $150k W-2 wages")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.MFJ,
        residence_state="TX",
        wages=[WageIncome(employer_name="Acme", employer_state="TX", gross_wages=Decimal("150000"))],
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Gross income", f.gross_income, 150000)
    check("Taxable income", f.taxable_income, 120000)
    check("Tax before credits", f.tax_before_credits, 16228)
    check("Total tax", f.total_tax, 16228)


def test_3_single_high_income_500k():
    """
    Test 3: Single, $500,000 W-2 wages
    ------------------------------------
    Gross income:          $500,000
    Standard deduction:    -$15,000
    Taxable income:        $485,000

    Tax calculation (Single 2025 brackets):
      10% on $0-$11,925             = $1,192.50
      12% on $11,925-$48,475        = $4,386.00
      22% on $48,475-$103,350       = $12,072.50
      24% on $103,350-$197,300      = $22,548.00
      32% on $197,300-$250,525      = $17,032.00
      35% on $250,525-$485,000      = $82,066.25
      Total tax:                    = $139,297.25

    Additional Medicare: 0.9% on ($500,000 - $200,000) = $2,700
    Total tax: $139,297 + $2,700 = $141,997
    """
    print("\n" + "=" * 60)
    print("TEST 3: Single, $500k W-2 wages (hits 35% bracket)")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="TX",
        wages=[WageIncome(employer_name="Acme", employer_state="TX", gross_wages=Decimal("500000"))],
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Gross income", f.gross_income, 500000)
    check("Taxable income", f.taxable_income, 485000)
    check("Tax before credits", f.tax_before_credits, 139297.25)
    # Additional Medicare = 0.9% * (500k - 200k) = $2,700
    check("Additional Medicare", f.additional_medicare_tax, 2700)
    check("Total tax", f.total_tax, 141997)


def test_4_single_top_bracket_750k():
    """
    Test 4: Single, $750,000 W-2 wages (hits 37% bracket)
    -------------------------------------------------------
    Gross income:          $750,000
    Standard deduction:    -$15,000
    Taxable income:        $735,000

    Tax calculation (Single 2025 brackets):
      base_tax at 37% bracket = $188,769.75
      37% on ($735,000 - $626,350) = $108,650 * 0.37 = $40,200.50
      Total ordinary tax: $188,769.75 + $40,200.50 = $228,970.25

    Additional Medicare: 0.9% * ($750,000 - $200,000) = $4,950
    Total tax: $228,970 + $4,950 = $233,920
    """
    print("\n" + "=" * 60)
    print("TEST 4: Single, $750k W-2 (top bracket 37%)")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="TX",
        wages=[WageIncome(employer_name="Acme", employer_state="TX", gross_wages=Decimal("750000"))],
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Taxable income", f.taxable_income, 735000)
    check("Tax before credits", f.tax_before_credits, 228970.25)
    check("Additional Medicare", f.additional_medicare_tax, 4950)
    check("Total tax", f.total_tax, 233920)


def test_5_hoh_45k():
    """
    Test 5: Head of Household, $45,000 W-2 wages
    -----------------------------------------------
    Gross income:          $45,000
    Standard deduction:    -$22,500
    Taxable income:        $22,500

    Tax (HOH 2025 brackets):
      10% on $0-$17,000     = $1,700.00
      12% on $17,000-$22,500 = $660.00
      Total tax:             = $2,360.00
    """
    print("\n" + "=" * 60)
    print("TEST 5: HOH, $45k W-2 wages")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.HOH,
        residence_state="TX",
        wages=[WageIncome(employer_name="Acme", employer_state="TX", gross_wages=Decimal("45000"))],
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Taxable income", f.taxable_income, 22500)
    check("Tax before credits", f.tax_before_credits, 2360)
    check("Total tax", f.total_tax, 2360)


def test_6_mfs_200k():
    """
    Test 6: MFS, $200,000 W-2 wages
    ---------------------------------
    Gross income:          $200,000
    Standard deduction:    -$15,000
    Taxable income:        $185,000

    Tax (MFS 2025 brackets):
      10% on $0-$11,925         = $1,192.50
      12% on $11,925-$48,475    = $4,386.00
      22% on $48,475-$103,350   = $12,072.50
      24% on $103,350-$185,000  = $19,596.00
      Total tax:                = $37,247.00
    """
    print("\n" + "=" * 60)
    print("TEST 6: MFS, $200k W-2 wages")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.MFS,
        residence_state="TX",
        wages=[WageIncome(employer_name="Acme", employer_state="TX", gross_wages=Decimal("200000"))],
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Taxable income", f.taxable_income, 185000)
    check("Tax before credits", f.tax_before_credits, 37247)
    check("Total tax", f.total_tax, 37247)


def test_7_single_ltcg():
    """
    Test 7: Single, $50k wages + $30k LTCG
    ----------------------------------------
    Gross income:          $80,000 ($50k wages + $30k LTCG)
    Standard deduction:    -$15,000
    Taxable income:        $65,000
    Ordinary income:       $35,000 ($50k - $15k deduction)
    Preferential income:   $30,000 (LTCG)

    Ordinary tax (Single brackets on $35,000):
      10% on $0-$11,925     = $1,192.50
      12% on $11,925-$35,000 = $2,769.00
      Total ordinary tax:    = $3,961.50

    Preferential tax:
      Single 0% threshold = $48,350
      Room at 0% = $48,350 - $35,000 = $13,350
      At 0%: $13,350 → $0
      At 15%: $30,000 - $13,350 = $16,650 → $2,497.50
      Total preferential tax: $2,497.50

    Total tax: $3,961.50 + $2,497.50 = $6,459.00
    """
    print("\n" + "=" * 60)
    print("TEST 7: Single, $50k wages + $30k LTCG")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="TX",
        wages=[WageIncome(employer_name="Acme", employer_state="TX", gross_wages=Decimal("50000"))],
        capital_gains=CapitalGains(long_term_gains=Decimal("30000")),
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Gross income", f.gross_income, 80000)
    check("Taxable income", f.taxable_income, 65000)
    check("Ordinary income", f.ordinary_income, 35000)
    check("Preferential income", f.preferential_income, 30000)
    check("Ordinary tax", f.ordinary_tax, 3961.50)
    check("Preferential tax", f.preferential_tax, 2497.50)
    check("Tax before credits", f.tax_before_credits, 6459)
    check("Total tax", f.total_tax, 6459)


def test_8_single_qualified_dividends():
    """
    Test 8: Single, $40k wages + $20k qualified dividends
    ------------------------------------------------------
    Gross income:          $60,000
    Standard deduction:    -$15,000
    Taxable income:        $45,000
    Ordinary income:       $25,000 ($40k - $15k)
    Preferential income:   $20,000 (qualified dividends)

    Ordinary tax on $25,000:
      10% on $0-$11,925     = $1,192.50
      12% on $11,925-$25,000 = $1,569.00
      Total:                 = $2,761.50

    Preferential tax:
      0% threshold = $48,350
      Room at 0% = $48,350 - $25,000 = $23,350 > $20,000
      All $20,000 at 0%: $0

    Total tax: $2,761.50
    """
    print("\n" + "=" * 60)
    print("TEST 8: Single, $40k wages + $20k qualified dividends (all at 0%)")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="TX",
        wages=[WageIncome(employer_name="Acme", employer_state="TX", gross_wages=Decimal("40000"))],
        interest_dividends=InterestDividendIncome(
            ordinary_dividends=Decimal("20000"),
            qualified_dividends=Decimal("20000"),
        ),
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Taxable income", f.taxable_income, 45000)
    check("Ordinary tax", f.ordinary_tax, 2761.50)
    check("Preferential tax", f.preferential_tax, 0)
    check("Total tax", f.total_tax, 2761.50)


def test_9_self_employment():
    """
    Test 9: Single, $100k self-employment income (no W-2)
    -------------------------------------------------------
    Gross SE income:       $100,000
    SE tax base:           $100,000 * 0.9235 = $92,350
    SS tax: $92,350 * 12.4% = $11,451.40
    Medicare tax: $92,350 * 2.9% = $2,678.15
    Total SE tax: $14,129.55

    Deductible SE tax: $14,129.55 / 2 = $7,064.78
    AGI: $100,000 - $7,064.78 = $92,935.22
    Taxable income: $92,935.22 - $15,000 = $77,935.22

    Ordinary tax on $77,935.22 (Single):
      10% on $0-$11,925         = $1,192.50
      12% on $11,925-$48,475    = $4,386.00
      22% on $48,475-$77,935.22 = $6,481.25
      Total income tax:         = $12,059.75

    Total tax: $12,059.75 + $14,129.55 = $26,189.30
    """
    print("\n" + "=" * 60)
    print("TEST 9: Single, $100k self-employment income")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="TX",
        self_employment=[SelfEmploymentIncome(business_name="Freelance", gross_income=Decimal("100000"))],
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Gross income", f.gross_income, 100000)
    # SE tax = $100k * 0.9235 * (0.124 + 0.029) = $14,129.56
    check("Self-employment tax", f.self_employment_tax, 14129.56, tolerance=2)
    # AGI = $100k - ($14,129.56 / 2)
    check("AGI", f.adjusted_gross_income, 92935.22, tolerance=2)
    # Taxable = AGI - $15k standard deduction
    check("Taxable income", f.taxable_income, 77935.22, tolerance=2)


def test_10_refund_scenario():
    """
    Test 10: Single, $60k wages, $10k federal withholding
    -------------------------------------------------------
    Taxable income: $60,000 - $15,000 = $45,000

    Tax on $45,000 (Single):
      10% on $0-$11,925     = $1,192.50
      12% on $11,925-$45,000 = $3,969.00
      Total tax:             = $5,161.50

    Withholding: $10,000
    Refund: $5,161.50 - $10,000 = -$4,838.50 (refund of ~$4,839)
    """
    print("\n" + "=" * 60)
    print("TEST 10: Single, $60k with $10k withholding (refund scenario)")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="TX",
        wages=[WageIncome(
            employer_name="Acme", employer_state="TX",
            gross_wages=Decimal("60000"),
            federal_withholding=Decimal("10000"),
        )],
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Taxable income", f.taxable_income, 45000)
    check("Tax before credits", f.tax_before_credits, 5161.50)
    check("Total withholding", f.total_withholding, 10000)


def test_11_zero_income():
    """
    Test 11: Single, $0 income
    ---------------------------
    Everything should be zero.
    """
    print("\n" + "=" * 60)
    print("TEST 11: Single, $0 income")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="TX",
        wages=[WageIncome(employer_name="None", employer_state="TX", gross_wages=Decimal("0"))],
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Gross income", f.gross_income, 0)
    check("Taxable income", f.taxable_income, 0)
    check("Total tax", f.total_tax, 0)


def test_12_income_below_std_deduction():
    """
    Test 12: Single, $10,000 income (below standard deduction)
    ------------------------------------------------------------
    Gross: $10,000
    Standard deduction: $15,000
    Taxable income: $0 (can't go negative)
    Tax: $0
    """
    print("\n" + "=" * 60)
    print("TEST 12: Single, $10k (below standard deduction)")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="TX",
        wages=[WageIncome(employer_name="Acme", employer_state="TX", gross_wages=Decimal("10000"))],
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Gross income", f.gross_income, 10000)
    check("Taxable income", f.taxable_income, 0)
    check("Total tax", f.total_tax, 0)


def test_13_mfj_complex():
    """
    Test 13: MFJ, $200k wages + $50k LTCG + $10k interest
    --------------------------------------------------------
    Gross income: $200,000 + $50,000 + $10,000 = $260,000
    Standard deduction: -$30,000
    Taxable income: $230,000
    Ordinary income: $180,000 ($200k + $10k - $30k deduction)
    Preferential income: $50,000 (LTCG)

    Ordinary tax on $180,000 (MFJ):
      10% on $0-$23,850         = $2,385.00
      12% on $23,850-$96,950    = $8,772.00
      22% on $96,950-$180,000   = $18,271.00
      Total:                    = $29,428.00

    Preferential tax:
      MFJ 0% threshold = $96,700
      Room at 0% = $96,700 - $180,000 = negative → $0 at 0%
      MFJ 15% threshold = $600,050
      $180k + $50k = $230k < $600,050
      All $50,000 at 15%: $7,500

    Total tax: $29,428 + $7,500 = $36,928
    """
    print("\n" + "=" * 60)
    print("TEST 13: MFJ, $200k wages + $50k LTCG + $10k interest")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.MFJ,
        residence_state="TX",
        wages=[WageIncome(employer_name="Acme", employer_state="TX", gross_wages=Decimal("200000"))],
        capital_gains=CapitalGains(long_term_gains=Decimal("50000")),
        interest_dividends=InterestDividendIncome(taxable_interest=Decimal("10000")),
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Gross income", f.gross_income, 260000)
    check("Taxable income", f.taxable_income, 230000)
    check("Ordinary income", f.ordinary_income, 180000)
    check("Preferential income", f.preferential_income, 50000)
    check("Ordinary tax", f.ordinary_tax, 29428)
    check("Preferential tax", f.preferential_tax, 7500)
    check("Tax before credits", f.tax_before_credits, 36928)


def test_14_additional_std_deduction_age65():
    """
    Test 14: Single, age 65+, $50k wages
    --------------------------------------
    Standard deduction: $15,000 + $2,000 (age 65+) = $17,000
    Taxable income: $50,000 - $17,000 = $33,000

    Tax on $33,000 (Single):
      10% on $0-$11,925     = $1,192.50
      12% on $11,925-$33,000 = $2,529.00
      Total:                 = $3,721.50
    """
    print("\n" + "=" * 60)
    print("TEST 14: Single, age 65+, $50k (additional std deduction)")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="TX",
        taxpayer=TaxpayerInfo(age_65_or_older=True),
        wages=[WageIncome(employer_name="Acme", employer_state="TX", gross_wages=Decimal("50000"))],
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Taxable income", f.taxable_income, 33000)
    check("Tax before credits", f.tax_before_credits, 3721.50)


def test_15_ss_wage_base():
    """
    Test 15: Single, $200k wages — verify SS wage base of $176,100
    ----------------------------------------------------------------
    Additional Medicare: 0.9% * ($200,000 - $200,000) = $0
    (exactly at threshold, so no additional Medicare)
    
    This test mainly confirms the engine loads correctly at high income.
    Taxable: $200k - $15k = $185k
    
    Tax on $185k (Single):
      10% on $0-$11,925         = $1,192.50
      12% on $11,925-$48,475    = $4,386.00
      22% on $48,475-$103,350   = $12,072.50
      24% on $103,350-$185,000  = $19,596.00
      Total:                    = $37,247.00
    """
    print("\n" + "=" * 60)
    print("TEST 15: Single, $200k wages (SS wage base / Additional Medicare boundary)")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.SINGLE,
        residence_state="TX",
        wages=[WageIncome(employer_name="Acme", employer_state="TX", gross_wages=Decimal("200000"))],
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Tax before credits", f.tax_before_credits, 37247)
    check("Additional Medicare", f.additional_medicare_tax, 0)
    check("Total tax", f.total_tax, 37247)


def test_16_qss_same_as_mfj():
    """
    Test 16: QSS, $100k wages — should match MFJ brackets
    -------------------------------------------------------
    Taxable: $100k - $30k = $70k

    Tax (QSS = MFJ brackets):
      10% on $0-$23,850      = $2,385.00
      12% on $23,850-$70,000 = $5,538.00
      Total:                  = $7,923.00
    """
    print("\n" + "=" * 60)
    print("TEST 16: QSS, $100k wages (same brackets as MFJ)")
    print("=" * 60)

    inp = TaxInput(
        tax_year=2025,
        filing_status=FilingStatus.QSS,
        residence_state="TX",
        wages=[WageIncome(employer_name="Acme", employer_state="TX", gross_wages=Decimal("100000"))],
    )
    result = engine.calculate(inp)
    assert result.success, f"Calculation failed: {result.errors}"

    f = result.federal
    check("Taxable income", f.taxable_income, 70000)
    check("Tax before credits", f.tax_before_credits, 7923)


if __name__ == "__main__":
    print("=" * 60)
    print("FEDERAL TAX CALCULATION VERIFICATION")
    print("IRS 2025 Brackets — Hand-Calculated Expected Values")
    print("=" * 60)

    tests = [
        test_1_single_w2_75k,
        test_2_mfj_w2_150k,
        test_3_single_high_income_500k,
        test_4_single_top_bracket_750k,
        test_5_hoh_45k,
        test_6_mfs_200k,
        test_7_single_ltcg,
        test_8_single_qualified_dividends,
        test_9_self_employment,
        test_10_refund_scenario,
        test_11_zero_income,
        test_12_income_below_std_deduction,
        test_13_mfj_complex,
        test_14_additional_std_deduction_age65,
        test_15_ss_wage_base,
        test_16_qss_same_as_mfj,
    ]

    for test_fn in tests:
        try:
            test_fn()
        except Exception as e:
            FAIL += 1
            msg = f"  💥 {test_fn.__name__} CRASHED: {e}"
            print(msg)
            ERRORS.append(msg)

    print("\n" + "=" * 60)
    print(f"RESULTS: {PASS} passed, {FAIL} failed")
    print("=" * 60)

    if ERRORS:
        print("\nFAILURES:")
        for err in ERRORS:
            print(err)
        sys.exit(1)
    else:
        print("\n🎉 All calculations match expected IRS 2025 values!")
        sys.exit(0)
