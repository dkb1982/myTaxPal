# Review — Latest Tax Application Changes (Post-Pull)

**Date:** 2026-02-21  
**Reviewed commit:** `82bb2bf`  
**Summary:** Implement Additional Medicare Tax and NIIT in federal stage pipeline + Idaho state test classification fix.

---

## What was reviewed

Files changed in commit:
- `rules/federal/2025.yaml`
- `rules/federal/FEDERAL_EDGE_CASES_2025.md`
- `src/tax_estimator/calculation/stages/stage_04_adjustments_agi.py`
- `src/tax_estimator/models/tax_input.py`
- `src/tax_estimator/rules/schema.py`
- `tests/calculation/states/test_flat_tax_states.py`
- `tests/calculation/states/test_progressive_states.py`
- `verify_calculations.py`

Validation run:
- `pytest tests/ -q --tb=short` → **2131 passed**
- `verify_calculations.py` → **63 passed, 0 failed**

---

## ✅ What is fixed and looks good

1. **Additional Medicare Tax is now computed in stage pipeline**
   - Added in `stage_04_adjustments_agi.py`
   - Wired into final tax rollup (`additional_medicare_tax` consumed later in stage 11)

2. **NIIT is now computed in stage pipeline**
   - Added in `stage_04_adjustments_agi.py`
   - Stored as `niit` and included downstream in final totals

3. **Federal config schema + rules updated**
   - `rules/schema.py` includes NIIT fields
   - `rules/federal/2025.yaml` includes NIIT thresholds and rate

4. **Idaho classification mismatch resolved in tests**
   - Moved from progressive-state set to flat-tax set

5. **Verification harness updated and green**
   - High-income W-2 cases now pass with expected Additional Medicare values

---

## ⚠️ Important remaining issues

### 1) Additional Medicare depends on Box 5 being present
Current behavior uses `medicare_wages` only. If API/client omits Box 5, it defaults to 0 and Additional Medicare is under-calculated.

**Observed behavior:**
- `gross_wages=500000`, no `medicare_wages` → Additional Medicare = 0
- same with `medicare_wages=500000` → Additional Medicare = 2700

**Required fix:**
- In input normalization, default `medicare_wages` to `gross_wages` when not provided.

---

### 2) NIIT thresholds are still hardcoded in stage logic
Although NIIT thresholds were added to YAML/schema, stage implementation currently hardcodes thresholds and only reads `niit_rate` from config.

**Required fix:**
- Read filing-status thresholds from federal rules config (`niit_threshold_single/mfj/mfs`) instead of hardcoded values.

---

### 3) Additional Medicare appears W-2 only
Current implementation checks Medicare wages from W-2 records and does not clearly include high self-employment Medicare interactions.

**Required decision:**
- Confirm product scope for mixed W-2 + self-employment Additional Medicare treatment.
- If in-scope, implement and add dedicated tests.

---

## Suggested next actions

1. Add Box 5 fallback (`medicare_wages = gross_wages` when missing).
2. Replace hardcoded NIIT thresholds with YAML-config-driven thresholds.
3. Add edge tests:
   - missing Box 5 fallback
   - NIIT threshold config usage
   - mixed W-2/SE Additional Medicare if in scope

---

## Reviewer confidence

- **Current commit quality:** strong
- **Ready for merge:** yes, with awareness of the above caveats
- **Ready for production-signoff:** after addressing listed important issues
