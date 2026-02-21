# Federal 2025 Tax Rules — Verification Report

**Date:** 2026-02-17  
**File reviewed:** `rules/federal/2025.yaml`  
**Severity:** HIGH — income tax brackets are completely fabricated; capital gains and SS wage base use stale 2024 values.

---

## Sources Used

| Source | URL |
|---|---|
| IRS — Federal income tax rates and brackets | https://www.irs.gov/filing/federal-income-tax-rates-and-brackets |
| IRS — Revenue Procedure 2024-40 (PDF) | https://www.irs.gov/pub/irs-drop/rp-24-40.pdf |
| IRS — Topic 409: Capital gains and losses | https://www.irs.gov/taxtopics/tc409 |
| Tax Foundation — 2025 Tax Brackets | https://taxfoundation.org/data/all/federal/2025-tax-brackets/ |
| SSA — 2025 Fact Sheet | https://www.ssa.gov/news/press/factsheets/colafacts2025.pdf |

---

## 1. Income Tax Brackets — ❌ WRONG (All Filing Statuses)

The YAML contains **4 fabricated brackets** at rates of 10%, 20%, 30%, 40%. The IRS defines **7 brackets** at 10%, 12%, 22%, 24%, 32%, 35%, 37%.

Every rate and every threshold is incorrect. This will produce wildly wrong estimates at any income level.

### 1a. Single Filers

| # | Current (WRONG) | Correct (IRS) |
|---|---|---|
| 1 | 10%: $0 – $10,000 | 10%: $0 – $11,925 |
| 2 | 20%: $10,000 – $50,000 | 12%: $11,925 – $48,475 |
| 3 | 30%: $50,000 – $100,000 | 22%: $48,475 – $103,350 |
| 4 | 40%: $100,000+ | 24%: $103,350 – $197,300 |
| 5 | *(missing)* | 32%: $197,300 – $250,525 |
| 6 | *(missing)* | 35%: $250,525 – $626,350 |
| 7 | *(missing)* | 37%: $626,350+ |

**Correct `base_tax` values for Single:**

| Bracket | Rate | base_tax |
|---|---|---|
| 1 | 10% | $0.00 |
| 2 | 12% | $1,192.50 |
| 3 | 22% | $5,578.50 |
| 4 | 24% | $17,651.00 |
| 5 | 32% | $40,199.00 |
| 6 | 35% | $57,231.00 |
| 7 | 37% | $188,769.75 |

### 1b. Married Filing Jointly (MFJ)

| # | Correct (IRS) |
|---|---|
| 1 | 10%: $0 – $23,850 |
| 2 | 12%: $23,850 – $96,950 |
| 3 | 22%: $96,950 – $206,700 |
| 4 | 24%: $206,700 – $394,600 |
| 5 | 32%: $394,600 – $501,050 |
| 6 | 35%: $501,050 – $751,600 |
| 7 | 37%: $751,600+ |

**Correct `base_tax` values for MFJ:**

| Bracket | Rate | base_tax |
|---|---|---|
| 1 | 10% | $0.00 |
| 2 | 12% | $2,385.00 |
| 3 | 22% | $11,157.00 |
| 4 | 24% | $35,302.00 |
| 5 | 32% | $80,398.00 |
| 6 | 35% | $114,462.00 |
| 7 | 37% | $202,154.50 |

### 1c. Married Filing Separately (MFS)

| # | Correct (IRS) |
|---|---|
| 1 | 10%: $0 – $11,925 |
| 2 | 12%: $11,925 – $48,475 |
| 3 | 22%: $48,475 – $103,350 |
| 4 | 24%: $103,350 – $197,300 |
| 5 | 32%: $197,300 – $250,525 |
| 6 | 35%: $250,525 – $375,800 |
| 7 | 37%: $375,800+ |

**Correct `base_tax` values for MFS:**

| Bracket | Rate | base_tax |
|---|---|---|
| 1 | 10% | $0.00 |
| 2 | 12% | $1,192.50 |
| 3 | 22% | $5,578.50 |
| 4 | 24% | $17,651.00 |
| 5 | 32% | $40,199.00 |
| 6 | 35% | $57,231.00 |
| 7 | 37% | $101,077.25 |

### 1d. Head of Household (HOH)

| # | Correct (IRS) |
|---|---|
| 1 | 10%: $0 – $17,000 |
| 2 | 12%: $17,000 – $64,850 |
| 3 | 22%: $64,850 – $103,350 |
| 4 | 24%: $103,350 – $197,300 |
| 5 | 32%: $197,300 – $250,500 |
| 6 | 35%: $250,500 – $626,350 |
| 7 | 37%: $626,350+ |

**Correct `base_tax` values for HOH:**

| Bracket | Rate | base_tax |
|---|---|---|
| 1 | 10% | $0.00 |
| 2 | 12% | $1,700.00 |
| 3 | 22% | $7,442.00 |
| 4 | 24% | $15,912.00 |
| 5 | 32% | $38,460.00 |
| 6 | 35% | $55,484.00 |
| 7 | 37% | $187,031.50 |

### 1e. Qualifying Surviving Spouse (QSS)

Same brackets as MFJ per IRS rules. Same `base_tax` values as MFJ.

---

## 2. Standard Deductions — ✅ CORRECT

No changes needed.

| Filing Status | YAML Value | IRS Value | Status |
|---|---|---|---|
| Single | $15,000 | $15,000 | ✅ |
| MFJ | $30,000 | $30,000 | ✅ |
| MFS | $15,000 | $15,000 | ✅ |
| HOH | $22,500 | $22,500 | ✅ |
| QSS | $30,000 | $30,000 | ✅ |

### Additional Standard Deduction — ✅ CORRECT

| Category | YAML | IRS | Status |
|---|---|---|---|
| Age 65+, Single/HOH | $2,000 | $2,000 | ✅ |
| Age 65+, MFJ/MFS | $1,600 | $1,600 | ✅ |
| Blind, Single/HOH | $2,000 | $2,000 | ✅ |
| Blind, MFJ/MFS | $1,600 | $1,600 | ✅ |

### Personal Exemption — ✅ CORRECT

$0 / not available (suspended by TCJA). Matches YAML.

---

## 3. Capital Gains / Qualified Dividend Thresholds — ❌ WRONG

All values are **2024 numbers**, not 2025. Source: IRS Topic 409.

| Filing Status | Field | Current (2024 value) | Correct (2025 value) |
|---|---|---|---|
| Single | 0% rate limit | $47,025 | **$48,350** |
| Single | 15% rate limit | $518,900 | **$533,400** |
| MFJ | 0% rate limit | $94,050 | **$96,700** |
| MFJ | 15% rate limit | $583,750 | **$600,050** |
| MFS | 0% rate limit | $47,025 | **$48,350** |
| MFS | 15% rate limit | $291,850 | **$300,000** |
| HOH | 0% rate limit | $63,000 | **$64,750** |
| HOH | 15% rate limit | $551,350 | **$566,700** |
| QSS | 0% rate limit | $94,050 | **$96,700** |
| QSS | 15% rate limit | $583,750 | **$600,050** |

---

## 4. Payroll Taxes (FICA) — ⚠️ PARTIALLY WRONG

| Field | Current | Correct 2025 | Status |
|---|---|---|---|
| SS wage base | $168,600 | **$176,100** | ❌ Uses 2024 value |
| SS rate (employee) | 6.2% | 6.2% | ✅ |
| Medicare rate | 1.45% | 1.45% | ✅ |
| Additional Medicare threshold | $200,000 | $200,000 | ✅ |
| Additional Medicare rate | 0.9% | 0.9% | ✅ |
| Self-employment factor | 0.9235 | 0.9235 | ✅ |

---

## 5. Alternative Minimum Tax (AMT) — ❓ NOT PRESENT

The YAML has no AMT section. If the calculation engine supports AMT, the following 2025 values should be added (source: Rev. Proc. 2024-40):

| Field | Single | MFJ | MFS |
|---|---|---|---|
| AMT exemption | $88,100 | $137,000 | $68,500 |
| 28% rate threshold | $239,100 | $239,100 | $119,550 |
| Phaseout threshold | $626,350 | $1,252,700 | $626,350 |

---

## 6. Other Issues

### 6a. Frontend 2024 Dropdown — No Rule Files Exist

The frontend (`static/index.html`) has a dropdown with both 2024 and 2025 tax years, but **no 2024 YAML rule files exist** in the `rules/` directory. Selecting 2024 will produce an error.

**Action:** Either create `rules/federal/2024.yaml` (and corresponding state/country files) or remove the 2024 option from the dropdown.

### 6b. YAML Header Comments

The file header says "FAKE tax values" and "intentionally unrealistic." Once corrected, update the header comments and the `verification` section at the bottom of the file:

```yaml
verification:
  status: "verified"
  last_verified: "2026-02-17"
  verified_by: "Team"
  notes: "Verified against IRS Rev. Proc. 2024-40 and IRS.gov"

references:
  - source_name: "IRS Revenue Procedure 2024-40"
    url: "https://www.irs.gov/pub/irs-drop/rp-24-40.pdf"
    retrieved_date: "2026-02-17"
  - source_name: "IRS Federal Income Tax Rates and Brackets"
    url: "https://www.irs.gov/filing/federal-income-tax-rates-and-brackets"
    retrieved_date: "2026-02-17"
  - source_name: "IRS Topic 409 - Capital Gains"
    url: "https://www.irs.gov/taxtopics/tc409"
    retrieved_date: "2026-02-17"
  - source_name: "SSA 2025 Fact Sheet"
    url: "https://www.ssa.gov/news/press/factsheets/colafacts2025.pdf"
    retrieved_date: "2026-02-17"
```

### 6c. Client-Side SS Wage Base

Note: `static/js/app.js` (line 64) has a **correct** hardcoded 2025 SS wage base of $176,100, but the YAML has the wrong value ($168,600). If the API serves the YAML value, the frontend fallback masks the bug but the API response would still be wrong.

---

## Summary of Required Changes

| # | What | Severity | Effort |
|---|---|---|---|
| 1 | Replace all income tax brackets (5 filing statuses × 7 brackets = 35 entries) | 🔴 Critical | Medium |
| 2 | Recalculate all `base_tax` values (35 entries) | 🔴 Critical | Medium |
| 3 | Update all 10 capital gains thresholds from 2024 → 2025 values | 🔴 Critical | Low |
| 4 | Update SS wage base from $168,600 → $176,100 | 🟡 Important | Trivial |
| 5 | Add AMT data (if engine supports it) | 🟡 Important | Low |
| 6 | Fix or remove 2024 dropdown option | 🟡 Important | Trivial |
| 7 | Update file header comments and verification metadata | 🟢 Cleanup | Trivial |

**Tests:** After changes, run the full suite (`pytest`). Expect test failures since existing tests were written against placeholder values — those tests will need updating to match real IRS brackets.
