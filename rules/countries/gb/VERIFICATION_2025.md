# GB (United Kingdom) 2025-26 Tax Rules — Verification Report

**Tax Year:** 6 April 2025 to 5 April 2026
**Verified:** 2026-02-17
**Sources:** gov.uk (HMRC), SLC, House of Commons Library

## ⚠️ IMPORTANT: Dual Source Issue

The GB tax rules exist in **two places** that are **out of sync**:

1. **YAML file** (`rules/countries/gb/2025.yaml`) — has NI at 12%/13.8% (2023-24 values)
2. **Python code** (`src/tax_estimator/calculation/countries/gb.py`) — has NI at 8% (2024-25 value), hardcoded rates

**The Python code is actually used for calculations**, not the YAML. The YAML appears to be reference data that's even more outdated. Both need updating to 2025-26, and ideally the Python should read from the YAML rather than hardcoding rates.

---

## 1. Income Tax Bands

| Field | YAML Value | Official Value | Status |
|-------|-----------|----------------|--------|
| Personal Allowance | £0–£12,570 @ 0% | £0–£12,570 @ 0% | ✅ CORRECT |
| Basic Rate | £12,570–£50,270 @ 20% | £12,571–£50,270 @ 20% | ✅ CORRECT |
| Higher Rate | £50,270–£125,140 @ 40% | £50,271–£125,140 @ 40% | ✅ CORRECT |
| Additional Rate | £125,140+ @ 45% | £125,140+ @ 45% | ✅ CORRECT |

**Source:** https://www.gov.uk/income-tax-rates

### base_tax Calculation Error

| Bracket | YAML base_tax | Correct base_tax | Status |
|---------|--------------|-------------------|--------|
| Basic (GB-2025-BASIC) | 0 | 0 | ✅ CORRECT |
| Higher (GB-2025-HIGHER) | 7,540 | 7,540 | ✅ CORRECT |
| Additional (GB-2025-ADDITIONAL) | **37,428** | **37,488** | ❌ WRONG (£60 off) |

Correct calculation for Additional base_tax:
- Basic band tax: (50,270 − 12,570) × 0.20 = 37,700 × 0.20 = £7,540
- Higher band tax: (125,140 − 50,270) × 0.40 = 74,870 × 0.40 = £29,948
- Total base_tax = 7,540 + 29,948 = **£37,488** (not £37,428)

### Note: Scotland & Wales
The YAML uses `filing_status: "all"` which applies England/NI rates. Scotland has different rates (19%/20%/21%/42%/45%/48% across 6 bands). Wales matches England/NI. The app may need to handle Scotland separately if it claims UK coverage.

---

## 2. Personal Allowance Taper

| Field | YAML Value | Official Value | Status |
|-------|-----------|----------------|--------|
| Base amount | £12,570 | £12,570 | ✅ CORRECT |
| Taper threshold | £100,000 | £100,000 | ✅ CORRECT |
| Taper rate | 0.5 (£1 per £2) | £1 per £2 over £100k | ✅ CORRECT |
| Minimum | 0 | £0 (at £125,140) | ✅ CORRECT |

**Source:** https://www.gov.uk/income-tax-rates

---

## 3. National Insurance (Class 1 Employee) — ❌ MAJOR ERRORS

| Field | YAML Value | Official 2025-26 Value | Status |
|-------|-----------|------------------------|--------|
| Employee rate | **12%** | **8%** | ❌ WRONG |
| Above UEL rate | *(not specified)* | **2%** | ❌ MISSING |
| Employer rate | **13.8%** | **15%** | ❌ WRONG |
| Employee floor (PT) | £12,570 | £12,570/year (£242/week) | ✅ CORRECT |
| Employee ceiling (UEL) | *(not specified)* | £50,270/year (£967/week) | ❌ MISSING |
| Employer floor (ST) | *(not specified)* | **£5,000/year** (£96/week) | ❌ MISSING |

### What happened:
- **12% employee rate** is from **2023-24 or earlier**. It was cut to 10% in Jan 2024, then to **8% from April 2024** onwards.
- **13.8% employer rate** is from **2024-25 or earlier**. It rose to **15% from April 2025** (Autumn Budget 2024).
- The **Secondary Threshold** dropped from £9,100 (2024-25) to **£5,000** (2025-26).
- The YAML is missing the **banded structure**: 8% between PT (£12,570) and UEL (£50,270), then 2% above UEL.
- The `notes` field says "12% on earnings 12,570 to 50,270, then 2%" — the 2% above UEL is correct but 12% is wrong.

### Correct NI Structure (2025-26):
```
Employee (Class 1 Primary):
  £0 to £12,570      → 0%
  £12,570 to £50,270  → 8%
  Above £50,270       → 2%

Employer (Class 1 Secondary):
  £0 to £5,000        → 0%
  Above £5,000        → 15%
```

**Source:** https://www.gov.uk/government/publications/rates-and-allowances-national-insurance-contributions/rates-and-allowances-national-insurance-contributions

---

## 4. Student Loan Repayment Thresholds — ❌ MOSTLY WRONG

| Plan | YAML Threshold | Official 2025-26 | Status |
|------|---------------|-------------------|--------|
| Plan 1 (pre-2012) | **£22,015** | **£26,065** | ❌ WRONG (2023-24 value) |
| Plan 2 (2012-2023) | **£27,295** | **£28,470** | ❌ WRONG (2023-24 value) |
| Plan 4 (Scotland) | **£27,660** | **£32,745** | ❌ WRONG (2023-24 value) |
| Plan 5 (post-2023) | £25,000 | £25,000 | ✅ CORRECT |
| Postgraduate | £21,000 | £21,000 | ✅ CORRECT |

All rates (9% for Plans 1/2/4/5, 6% for Postgraduate) are ✅ CORRECT.

**Source:** https://www.gov.uk/repaying-your-student-loan/what-you-pay

---

## 5. Deductions

| Field | YAML Value | Official Value | Status |
|-------|-----------|----------------|--------|
| Standard deduction available | false | N/A (UK uses Personal Allowance) | ✅ CORRECT |
| Personal exemption available | false | N/A | ✅ CORRECT |

---

## Summary

| Section | Verdict |
|---------|---------|
| Income tax rates & bands | ✅ Correct |
| base_tax (Additional bracket) | ❌ Off by £60 (37,428 → 37,488) |
| Personal Allowance taper | ✅ Correct |
| National Insurance employee rate | ❌ 12% should be 8% |
| National Insurance employer rate | ❌ 13.8% should be 15% |
| NI thresholds & banding | ❌ Missing UEL, wrong ST, missing banded structure |
| Student Loan Plan 1 threshold | ❌ £22,015 → £26,065 |
| Student Loan Plan 2 threshold | ❌ £27,295 → £28,470 |
| Student Loan Plan 4 threshold | ❌ £27,660 → £32,745 |
| Student Loan Plan 5 threshold | ✅ Correct |
| Postgraduate Loan threshold | ✅ Correct |
| Scotland handling | ⚠️ Not addressed (Scotland has 6 different tax bands) |

---

## 6. Python Code vs YAML Comparison (gb.py hardcoded values)

The Python code targets **2024-25**. Neither YAML nor Python is correct for **2025-26**.

| Field | YAML (2025.yaml) | Python (gb.py) | Correct 2025-26 |
|-------|-------------------|----------------|------------------|
| NI Employee Rate | 12% ❌ | 8% ✅ (for 2024-25) | 8% |
| NI Employer Rate | 13.8% ❌ | *Not calculated* | 15% |
| NI Primary Threshold | £12,570 | £12,570 | £12,570 ✅ |
| NI UEL | *Missing* | £50,270 | £50,270 ✅ |
| Student Loan Plan 1 | £22,015 ❌ | £24,990 ❌ | £26,065 |
| Student Loan Plan 2 | £27,295 ❌ | £27,295 ❌ | £28,470 |
| Student Loan Plan 4 | £27,660 ❌ | £31,395 ❌ | £32,745 |
| Student Loan Plan 5 | £25,000 ✅ | £25,000 ✅ | £25,000 |
| Postgraduate | £21,000 ✅ | £21,000 ✅ | £21,000 |
| Scotland brackets | *Not in YAML* | 2024-25 values ❌ | Changed for 2025-26 |

### Scotland 2025-26 Brackets (Python has 2024-25 values):
The Python code has `SCOTLAND_INCOME_TAX_BRACKETS` hardcoded. For 2025-26 the bands changed:
- Starter: £12,571–£15,397 @ 19%
- Basic: £15,398–£27,491 @ 20%
- Intermediate: £27,492–£43,662 @ 21%
- Higher: £43,663–£75,000 @ 42%
- Advanced: £75,001–£125,140 @ 45%
- Top: over £125,140 @ 48%

### Capital Gains Tax (Python only):
- AEA: £3,000 ✅ (correct for 2024-25 and 2025-26)
- Basic rate: 18% ✅ (correct for 2025-26)
- Higher rate: 24% ✅ (correct for 2025-26)

---

## Summary

| Section | YAML | Python Code | Correct 2025-26 |
|---------|------|-------------|------------------|
| Income tax (England/NI) | ✅ | ✅ | ✅ |
| base_tax Additional | ❌ (£60 off) | N/A (calculated) | £37,488 |
| Personal Allowance taper | ✅ | ✅ | ✅ |
| NI employee rate | ❌ 12% | ✅ 8% (2024-25) | 8% |
| NI employer rate | ❌ 13.8% | Not used | 15% |
| NI Secondary Threshold | Missing | Not used | £5,000 |
| Student Loan Plan 1 | ❌ £22,015 | ❌ £24,990 | £26,065 |
| Student Loan Plan 2 | ❌ £27,295 | ❌ £27,295 | £28,470 |
| Student Loan Plan 4 | ❌ £27,660 | ❌ £31,395 | £32,745 |
| Student Loan Plan 5 | ✅ | ✅ | ✅ |
| Postgraduate | ✅ | ✅ | ✅ |
| Scotland brackets | Not in YAML | ❌ 2024-25 | Changed |
| Capital Gains | Not in YAML | ✅ | ✅ |

### Severity: 🔴 HIGH
- Student loan thresholds wrong in **both** YAML and Python — Plans 1, 2, 4 all stale
- YAML NI rates are from 2023 (12%/13.8%), Python NI rate correct for 2024-25 but employer NI not calculated
- Scotland brackets in Python need updating for 2025-26
- Architectural concern: Python hardcodes rates instead of reading YAML — two sources of truth that drift
