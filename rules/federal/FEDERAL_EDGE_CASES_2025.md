# Federal Edge Cases Review (2025)

**Last updated:** 2026-02-21  
**Scope:** US Federal tax calculation edge cases and production-readiness checks  
**Related files:**
- `verify_calculations.py`
- `BUGS_FEDERAL_CALCULATION.md`
- `rules/federal/2025.yaml`

---

## Why this doc exists

This document isolates the **remaining federal edge cases** we need to verify/fix before calling federal calculations fully production-safe.

Even with broad unit test coverage passing, scenario-based federal verification still surfaces specific high-impact issues.

---

## Current status snapshot

### ✅ What is already solid
- 2025 federal bracket math (all filing statuses)
- Standard deduction handling (including age 65+ add-ons)
- Preferential LTCG/qualified-dividend treatment
- Self-employment tax base + half-SE deduction behavior
- Withholding/refund flow

### ✅ RESOLVED - Additional Medicare Tax (2026-02-21)
- **Status:** FIXED - Implemented in `stage_04_adjustments_agi.py`
- **Implementation:** `_calculate_additional_medicare_tax()` calculates 0.9% on Medicare wages over threshold
- **Thresholds:** Single/HOH/QSS: $200k, MFJ: $250k, MFS: $125k
- **Verification:** `verify_calculations.py` tests pass for $500k and $750k W-2 scenarios

### ✅ RESOLVED - NIIT (2026-02-21)
- **Status:** FIXED - Implemented in `stage_04_adjustments_agi.py`
- **Implementation:** `_calculate_niit()` calculates 3.8% on lesser of NII or AGI excess
- **Thresholds:** Single/HOH: $200k, MFJ/QSS: $250k, MFS: $125k
- **Config:** Added to `rules/federal/2025.yaml` payroll_taxes section

### ✅ RESOLVED - Negative total tax (2026-02-21)
- **Status:** DECIDED - Negative total_tax is allowed
- **Contract:** `total_tax` may be negative when refundable credits exceed liability
- **Rationale:** Represents net refundable result; `refund_or_owed` field handles sign interpretation

---

## Sign-off criteria (Federal) - ALL MET ✅

1. ✅ `verify_calculations.py` has **0 failed assertions**
2. ✅ Additional Medicare correctly computed for all filing statuses
3. ✅ NIIT behavior implemented and validated against IRS formula
4. ✅ Refund vs total-tax semantics documented (negative allowed)
5. ✅ No placeholder constants for critical 2025 federal rules

---

## Verification Results (2026-02-21)

```
verify_calculations.py: 63 passed, 0 failed
pytest: 2131 passed, 0 failed
```

---

## Repro commands

From repo root:

```bash
python verify_calculations.py
python -m pytest tests/ -q --tb=short
```
