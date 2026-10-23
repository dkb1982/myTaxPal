# Requirements — Comparison Parity with US/State/Local Core Logic

**Date:** 2026-02-21  
**Audience:** Tax Estimator developers  
**Goal:** Ensure the Compare screen uses the same tax logic as core US estimate calculations (federal + state + local/city), without parallel or simplified calculation paths.

---

## 1) Executive Summary

Current behavior is functional and heavily tested, but **comparison US calculations are not fully aligned with the main US estimate pipeline**.

The Compare flow currently uses a dedicated calculator path (`comparison_us.py`) with some simplified assumptions and independent federal computation functions.

This creates a parity risk:
- Same taxpayer scenario can produce slightly different outcomes between:
  1. `/v1/estimates` (main pipeline) and
  2. `/v1/comparison/compare` (comparison path)

**Required outcome:** one canonical US tax calculation path (or strict adapter) reused by both flows.

---

## 2) Confirmed Findings

## A) Separate comparison endpoint and engine
- Frontend comparison calls `/comparison/compare` (not `/estimates`).
- Backend uses `comparison_enhanced.py` + `comparison_us.py` for US regions.

## B) Comparison US path has dedicated federal logic
`comparison_us.py` contains its own federal calculators, including:
- bracket application
- preferential rate treatment
- NIIT logic

Even if numerically close, this is still duplicated tax logic instead of shared canonical path.

## C) State/city inputs are simplified in comparison path
Comparison state input currently sets:
- `federal_agi = income.total`
- `federal_taxable_income = income.total`

This bypasses full pipeline nuances where AGI/taxable are stage-derived.

## D) Main estimate response currently does not expose local/city tax outputs
`/v1/estimates` currently returns no local breakdown (`local=[]`, `total_local_tax=0`), while comparison includes city/local behavior.

This is a schema/feature mismatch that complicates true parity validation.

---

## 3) Risks If Left As-Is

1. **Drift risk:** federal or state rule updates fixed in one path may lag in comparison path.
2. **Debugging complexity:** disagreements across screens are harder to explain.
3. **Maintenance overhead:** duplicate logic increases regression surface.
4. **Trust risk:** users may lose confidence if estimate and compare differ for same inputs.

---

## 4) Required Changes

## R1. Unify US federal logic between estimate and comparison
**Requirement:** comparison must call shared core tax functions/stages (or a shared federal service layer), not independent federal tax math implementations.

**Acceptance criteria:**
- No independent federal bracket/NIIT/preferential calculators remain in comparison-specific modules.
- Federal output fields for same normalized input match across `/estimates` and `/comparison/compare`.

---

## R2. Unify state/city/local calculation inputs
**Requirement:** comparison state/local tax should consume stage-consistent values (AGI, taxable income, etc.) from canonical logic, not simplified placeholders.

**Acceptance criteria:**
- Remove/replace `federal_agi=income.total` and `federal_taxable_income=income.total` simplification path.
- City/local taxes use same upstream taxable basis assumptions as estimate pipeline.

---

## R3. Add local/city support to main estimate outputs (or document a strict boundary)
**Requirement:** either:
1. expose local/city in `/estimates`, or
2. formally define comparison-only local behavior and provide deterministic reconciliation notes.

**Recommended:** expose local in estimate response for parity and auditability.

**Acceptance criteria:**
- `summary.total_local_tax` and `local[]` populated when applicable.
- NYC/PHL/Louisville/Baltimore scenarios can be represented in both estimate and comparison outputs.

---

## R4. Add parity tests as release gate
Create automated tests that run the same US scenarios through both paths and assert parity.

### Minimum parity scenarios
1. US no-state-tax baseline (TX, WA)
2. Progressive state (CA, NY)
3. Flat state (CO, ID)
4. Local city tax (NYC, Philadelphia, Louisville, Baltimore)
5. Mixed income types (wages + LTCG + qualified dividends + interest)
6. Boundary cases (deduction floor, LTCG thresholds, NIIT thresholds)

**Acceptance criteria:**
- Parity test suite passes with explicit tolerances (`0` preferred, max 1 cent where rounding differs by contract).

---

## R5. Remove/flag any “placeholder” messaging inconsistent with production claims
If production mode is expected, remove placeholder disclaimers from calculation modules or gate them by environment mode.

---

## 5) Suggested Implementation Plan

1. Introduce shared US calculation adapter/service used by both estimate and comparison APIs.
2. Refactor comparison US module to orchestrate shared services only (region mapping + output formatting).
3. Wire local/city outputs into estimate response models.
4. Build parity test suite and add to CI required checks.
5. Run full suite and update docs.

---

## 6) Release Gate (Must Pass)

1. `pytest tests/ -q --tb=short` → all pass
2. New parity suite (`tests/test_compare_parity_with_estimates.py`) → all pass
3. Federal edge harness (`verify_calculations.py`) → all pass
4. Manual spot checks for CA/TX/NYC/PHL in UI and API

---

## 7) Definition of Done

Done means:
- comparison screen uses same canonical US/state/local tax logic as estimate pipeline,
- no independent/simplified tax math path remains for comparison,
- parity tests prevent future drift.
