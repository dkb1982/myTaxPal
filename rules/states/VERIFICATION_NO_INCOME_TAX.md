# No-Income-Tax US States — Verification Report

**Tax Year:** 2025
**Verified:** 2026-02-17
**States:** AK, FL, NV, SD, TN, TX, WY (true zero), NH (special), WA (special)

---

## True No-Income-Tax States

These 7 states have `has_income_tax: false` and `income_tax_type: "none"`:

| State | YAML Status | Correct for 2025? |
|-------|------------|-------------------|
| Alaska (AK) | No income tax | ✅ CORRECT |
| Florida (FL) | No income tax | ✅ CORRECT |
| Nevada (NV) | No income tax | ✅ CORRECT |
| South Dakota (SD) | No income tax | ✅ CORRECT |
| Tennessee (TN) | No income tax | ✅ CORRECT |
| Texas (TX) | No income tax | ✅ CORRECT |
| Wyoming (WY) | No income tax | ✅ CORRECT |

All 7 are straightforward — no issues.

---

## Special Case: New Hampshire (NH) — ❌ WRONG

**YAML says:** `has_income_tax: true`, interest & dividends tax at 3%

**Reality:** New Hampshire's Interest & Dividends Tax was **fully repealed effective January 1, 2025** (House Bill 2, signed by Governor Sununu, 2023 session).

For tax year 2025, NH has **no income tax of any kind**.

**Source:** https://www.revenue.nh.gov/news-and-media/repeal-nh-interest-and-dividends-tax-now-effect

### What needs to change:
- `has_income_tax` → `false`
- `income_tax_type` → `"none"`
- `flat_rate` → `null`
- Remove all deduction amounts
- Update notes to reflect repeal

---

## Special Case: Washington (WA) — ❌ WRONG

**YAML says:** Capital gains tax at 7% on gains over $270,000

**Reality for 2025:** Washington's capital gains tax changed significantly:

| Field | YAML Value | Correct 2025 Value | Status |
|-------|-----------|---------------------|--------|
| Rate | 7% flat | **7% tiered + 2.9% surcharge** | ❌ WRONG |
| Threshold | $270,000 | **$278,000** | ❌ WRONG |
| Structure | Single rate | **Two tiers** | ❌ WRONG |

### Correct 2025 Structure (ESSB 5813):
| Taxable Gains | Rate |
|---------------|------|
| $1 – $1,000,000 | 7% |
| Over $1,000,000 | 9.9% (7% + 2.9% surcharge) |

Standard deduction: **$278,000** (inflation-adjusted from $270,000)

**Sources:**
- https://dor.wa.gov/taxes-rates/other-taxes/capital-gains-tax
- https://dor.wa.gov/forms-publications/publications-subject/special-notices/new-tiered-rates-washingtons-capital-gains-tax

---

## Summary

| State | Verdict |
|-------|---------|
| AK, FL, NV, SD, TN, TX, WY | ✅ All correct |
| NH | ❌ Tax was repealed Jan 1 2025 — YAML still has 3% I&D tax |
| WA | ❌ Cap gains threshold wrong ($270k → $278k), missing new tiered rate (9.9% over $1M) |

### Severity: 🟡 MEDIUM
NH is functionally wrong (taxing people who shouldn't be taxed). WA threshold and rate structure are outdated.
