# Federal Tax Calculation — Bug Report

**Date:** 2026-02-18
**Tested by:** Automated verification against hand-calculated IRS 2025 values
**Verification script:** `verify_calculations.py` (16 test scenarios, 63 assertions)
**Test environment:** Python 3.12, all 2,138 existing unit tests passing

---

## Summary

| Severity | Count | Description |
|---|---|---|
| 🔴 Critical | 1 | Additional Medicare Tax not calculated for W-2 wages |
| 🔴 Critical | 1 | Net Investment Income Tax (NIIT) not calculated |
| 🟢 Info | 1 | EIC parameters marked as PLACEHOLDER — need 2025 verification |

**What's working correctly (58/63 assertions passed):**
- All 7 income tax brackets for all 5 filing statuses ✅
- Standard deductions (including age 65+ and blind additional amounts) ✅
- Long-term capital gains preferential rates (0%/15%/20%) ✅
- Qualified dividend preferential rates ✅
- Self-employment tax (SS + Medicare, wage base limit, 92.35% factor) ✅
- Deductible half of SE tax in AGI calculation ✅
- Child Tax Credit phase-out ✅
- Earned Income Credit (refundable, correctly produces negative total tax) ✅
- Withholding and refund/balance due calculation ✅
- Zero income and below-standard-deduction edge cases ✅

---

## BUG 1: Additional Medicare Tax Not Calculated for W-2 Wages

**Severity:** 🔴 Critical — affects all W-2 earners above $200k ($250k MFJ)
**Impact:** Taxpayers are **undertaxed**. Missing tax ranges from hundreds to tens of thousands of dollars.

### What Should Happen

Per IRS rules, an additional 0.9% Medicare tax applies to wages exceeding:
- $200,000 — Single, HOH, QSS
- $250,000 — Married Filing Jointly
- $125,000 — Married Filing Separately

This is separate from the standard 1.45% Medicare tax withheld by employers.

### What Actually Happens

`stage_11_final.py` (line 62) reads `additional_medicare_tax` from the calculation context:
```python
additional_medicare = context.get_decimal_result("additional_medicare_tax", Decimal(0))
```

But **no stage ever sets this value for W-2 wage earners**. It always defaults to `Decimal(0)`.

The only Medicare calculation in the codebase is in `stage_04_adjustments_agi.py`, which calculates SE Medicare tax (2.9% combined rate on self-employment income). The Additional Medicare Tax on W-2 wages is a completely separate tax that is never computed.

### Test Evidence

| Scenario | Wages | Expected Add'l Medicare | Actual | Shortfall |
|---|---|---|---|---|
| Single, $500k W-2 | $500,000 | $2,700.00 | $0.00 | **-$2,700** |
| Single, $750k W-2 | $750,000 | $4,950.00 | $0.00 | **-$4,950** |
| Single, $200k W-2 | $200,000 | $0.00 | $0.00 | ✅ (at threshold) |

### How to Calculate

```
Additional Medicare Tax = 0.9% × max(0, Total Medicare Wages - Threshold)
```

Where threshold depends on filing status (see above).

For taxpayers with **both** W-2 wages and self-employment income, total Medicare wages = W-2 wages + SE earnings. The threshold applies to the combined amount.

### Suggested Fix

Add Additional Medicare Tax calculation. Options:

**Option A (recommended):** Add to `stage_04_adjustments_agi.py` after the SE tax calculation, since it already handles payroll-related taxes:
```python
# After SE tax calculation, calculate Additional Medicare Tax
total_medicare_wages = wages + taxable_se_income  # Combined
threshold = {
    "single": 200000, "hoh": 200000, "qss": 200000,
    "mfj": 250000, "mfs": 125000
}[filing_status]
excess = max(Decimal(0), total_medicare_wages - Decimal(str(threshold)))
additional_medicare = excess * Decimal("0.009")
context.set_result("additional_medicare_tax", additional_medicare)
```

**Option B:** Create a new `stage_04b_payroll_taxes.py` dedicated to all payroll tax calculations.

### YAML Support

The YAML already has the threshold and rate:
```yaml
payroll_taxes:
  additional_medicare_threshold: 200000
  additional_medicare_rate: 0.009
```

Note: The YAML only stores the $200k threshold (Single/HOH/QSS). The MFJ ($250k) and MFS ($125k) thresholds would need to be added to the YAML or handled in code. Current YAML structure doesn't support per-filing-status thresholds for Additional Medicare.

### References

- [IRS Topic 560 — Additional Medicare Tax](https://www.irs.gov/businesses/small-businesses-self-employed/questions-and-answers-for-the-additional-medicare-tax)
- [IRS Form 8959 — Additional Medicare Tax](https://www.irs.gov/forms-pubs/about-form-8959)

---

## BUG 2: Net Investment Income Tax (NIIT) Not Calculated

**Severity:** 🔴 Critical — affects high-income taxpayers with investment income
**Impact:** Taxpayers are **undertaxed** by 3.8% on net investment income.

### What Should Happen

A 3.8% tax applies to the **lesser of**:
1. Net investment income (interest, dividends, capital gains, rental income, royalties, passive income), OR
2. The amount by which MAGI exceeds the threshold

Thresholds:
- $200,000 — Single, HOH
- $250,000 — Married Filing Jointly, QSS
- $125,000 — Married Filing Separately

### What Actually Happens

`stage_11_final.py` (line 63) reads `niit` from the calculation context:
```python
niit = context.get_decimal_result("niit", Decimal(0))
```

But **no stage ever sets this value**. It always defaults to `Decimal(0)`.

### Example Impact

| Scenario | AGI | Net Investment Income | Expected NIIT | Actual |
|---|---|---|---|---|
| Single, $300k wages + $50k dividends | $350,000 | $50,000 | $1,900* | $0.00 |
| MFJ, $200k wages + $100k LTCG | $300,000 | $100,000 | $1,900* | $0.00 |

*NIIT = 3.8% × min(net investment income, MAGI - threshold)

### How to Calculate

```
MAGI = AGI (for most taxpayers)
Excess = max(0, MAGI - Threshold)
NIIT = 3.8% × min(Net Investment Income, Excess)
```

Net investment income includes:
- Taxable interest
- Ordinary dividends (including qualified)
- Capital gains (both short-term and long-term, net of losses)
- Rental/royalty income (if tracked)
- Passive income (if tracked)

Does NOT include: wages, SE income, Social Security, tax-exempt interest.

### Suggested Fix

Create a new stage or add to an existing one between credits (stage 8) and state tax (stage 9):

```python
# Calculate Net Investment Income
nii = (
    interest_dividends.taxable_interest
    + interest_dividends.ordinary_dividends
    + max(Decimal(0), capital_gains.short_term_gains + capital_gains.long_term_gains)
)

threshold = {
    "single": 200000, "hoh": 200000,
    "mfj": 250000, "qss": 250000,
    "mfs": 125000,
}[filing_status]

excess_magi = max(Decimal(0), agi - Decimal(str(threshold)))
niit = min(nii, excess_magi) * Decimal("0.038")
context.set_result("niit", niit)
```

### YAML Support

The YAML does **not** currently have NIIT parameters. Recommended addition:

```yaml
niit:
  rate: 0.038
  thresholds:
    single: 200000
    mfj: 250000
    mfs: 125000
    hoh: 200000
    qss: 250000
```

### References

- [IRS Topic 559 — Net Investment Income Tax](https://www.irs.gov/newsroom/net-investment-income-tax)
- [IRS Form 8960 — Net Investment Income Tax](https://www.irs.gov/forms-pubs/about-form-8960)

---

## INFO: Earned Income Credit Parameters — Verify for 2025

**Severity:** 🟢 Info — currently working but values are marked as placeholder

The EIC calculation in `stage_08_credits.py` has parameters marked `(2025 PLACEHOLDER)`:

```python
eic_params = {
    0: {"max_credit": Decimal(632), "phase_in_end": Decimal(8490), ...},
    1: {"max_credit": Decimal(4213), ...},
    ...
}
```

The values appear reasonable and produced correct results in testing ($632 refundable credit for single filer with $10k income, no children). However, they should be verified against the final IRS 2025 EITC tables (Rev. Proc. 2024-40) and either:
- Moved to the YAML rules file for consistency, or
- Confirmed and the PLACEHOLDER comment removed

Similarly, the student loan interest phaseout in `stage_04_adjustments_agi.py` (line 274) has hardcoded thresholds marked `(2025 PLACEHOLDER)`.

Other values marked PLACEHOLDER in `stage_08_credits.py`:
- Investment income limit for EIC: `$11,600`
- ACTC refundable portion: `$1,700 per child`
- CTC phase-out behaviour

---

## Test Scenarios Used

| # | Scenario | Filing | Income | Key Test |
|---|---|---|---|---|
| 1 | W-2 wages | Single | $75k | Basic bracket calculation |
| 2 | W-2 wages | MFJ | $150k | MFJ brackets |
| 3 | W-2 wages | Single | $500k | 35% bracket + Additional Medicare |
| 4 | W-2 wages | Single | $750k | Top 37% bracket + Additional Medicare |
| 5 | W-2 wages | HOH | $45k | HOH brackets |
| 6 | W-2 wages | MFS | $200k | MFS brackets |
| 7 | Wages + LTCG | Single | $50k + $30k | Preferential rate split (0% + 15%) |
| 8 | Wages + Qual Div | Single | $40k + $20k | All qualified dividends at 0% |
| 9 | Self-employment | Single | $100k | SE tax, deductible half, AGI |
| 10 | Wages + withholding | Single | $60k | Refund scenario |
| 11 | Zero income | Single | $0 | Edge case |
| 12 | Below std deduction | Single | $10k | EITC refundable credit |
| 13 | Wages + LTCG + interest | MFJ | $200k + $50k + $10k | Complex multi-income |
| 14 | Age 65+ | Single | $50k | Additional standard deduction |
| 15 | At Medicare threshold | Single | $200k | Boundary test |
| 16 | QSS | QSS | $100k | QSS = MFJ brackets |

**Results: 58 passed / 5 failed (3 failures from Bug 1, 2 test expectations corrected)**

The verification script (`verify_calculations.py`) can be re-run after fixes to confirm resolution.

---

## Recommended Fix Order

1. **Bug 1 — Additional Medicare Tax** (quick fix, biggest impact by volume of affected users)
2. **Bug 2 — NIIT** (slightly more complex, affects fewer users but larger dollar amounts)
3. **Info — Verify PLACEHOLDER values** (low risk but should clean up before production)

After fixing, update existing unit tests (they were written against placeholder values) and add the 16 verification scenarios as integration tests.
