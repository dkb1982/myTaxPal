# Tax Estimator — Cross-Board Fix Requirements

**Date:** 2026-02-21  
**Owner:** Tax Estimator dev team  
**Scope:** Federal + State + International + validation/test integrity before production sign-off

---

## 1) Executive summary

The codebase has broad test coverage and many improvements already merged, but there are still **production-significant gaps**:

1. **Federal pipeline still misses key taxes in stage flow** (Additional Medicare, likely NIIT path mismatch).
2. **State classification mismatch** (Idaho is now flat tax in rules, tests still expect progressive behavior).
3. **Edge-case semantics need explicit contract** (negative total tax behavior at low income / refundable credits).

This document defines the exact requirements to close these gaps and get to deploy-safe status.

---

## 2) Current evidence baseline

### Latest runs
- Full suite: `pytest tests/ -q --tb=short`
  - **2124 passed, 2 failed**
  - Failures: `tests/calculation/states/test_progressive_states.py` for `ID`
- Federal scenario harness: `python verify_calculations.py`
  - **58 passed, 5 failed**
  - High-income W-2 scenarios still missing Additional Medicare
  - One low-income scenario returns negative total tax vs harness expectation

---

## 3) Mandatory fixes

## A) Federal calculation pipeline (Critical)

### A1. Additional Medicare Tax must be computed in stage pipeline
**Problem:** `stage_11_final.py` reads `additional_medicare_tax`, but upstream stage flow does not reliably set it.

**Requirement:**
- Implement Additional Medicare in the main federal stage path (not only comparison module).
- Thresholds by filing status:
  - Single / HOH / QSS: 200,000
  - MFJ: 250,000
  - MFS: 125,000
- Tax formula:
  - `0.009 * max(0, medicare_wages_total - threshold)`
- Include mixed W-2 + SE cases where applicable (combined Medicare wage base logic).

**Acceptance criteria:**
- `verify_calculations.py` high-income W-2 cases pass (no missing $2,700 / $4,950 deltas).
- Result fields correctly populate `additional_medicare_tax` in final output.

---

### A2. NIIT must be present in the same federal stage path
**Problem:** `stage_11_final.py` reads `niit`, but stage flow currently appears not to set it consistently.

**Requirement:**
- Implement NIIT in the federal stage pipeline with explicit filing-status thresholds.
- Formula:
  - `NIIT = 3.8% * min(net_investment_income, max(0, MAGI - threshold))`
- Ensure all final result structures include NIIT amount and metadata fields (if exposed).

**Acceptance criteria:**
- Dedicated tests added for:
  - `NII < MAGI excess`
  - `MAGI excess < NII`
  - below-threshold controls
- NIIT value non-zero for qualifying scenarios and zero otherwise.

---

### A3. Low-income negative total-tax behavior must be contract-defined
**Problem:** scenario with taxable income at/under deduction floor yields negative total tax in harness.

**Requirement:**
- Define expected API semantics clearly:
  - Option 1: `total_tax` may be negative (net refundable result), OR
  - Option 2: `total_tax` floors at zero and refunds represented separately.
- Align implementation + tests + docs to one contract.

**Acceptance criteria:**
- `verify_calculations.py` expectation updated and passing.
- API docs and response examples match implementation.

---

## B) State tax consistency (High)

### B1. Idaho classification alignment
**Problem:** Idaho rules now define `flat` tax, while progressive-state test expects graduated brackets.

**Requirement:**
- Update test inventory/classification to reflect Idaho as flat, OR revert Idaho rule if flat migration was unintended.
- Ensure bracket-breakdown assertions are not applied to flat states.

**Acceptance criteria:**
- Full suite has zero failures in state tests.
- No contradictory assumptions between `rules/states/id.yaml` and test parametrization.

---

## C) International and cross-country (Validation hardening)

### C1. Preserve current passing status with targeted regression checks
International currently passes, but this must remain stable while federal/state fixes land.

**Requirement:**
- Keep international/cross-country suites green after federal/state edits.
- Add at least one targeted regression test per modified country calculator where behavior changed materially.

**Acceptance criteria:**
- `tests/test_international.py` passes.
- `tests/test_compare_cross_country.py`, `tests/test_compare_golden.py`, `tests/test_compare_income_routing.py`, `tests/test_compare_invariants.py` all pass.

---

## 4) Test/QA gating requirements

Before release candidate tag:

1. `pytest tests/ -q --tb=short` → **all pass**
2. `python verify_calculations.py` → **all pass**
3. No unresolved TODO/FIXME in newly touched tax logic paths
4. Federal edge-case doc updated with final status:
   - `rules/federal/FEDERAL_EDGE_CASES_2025.md`

---

## 5) Deliverables checklist

- [ ] Additional Medicare implemented in stage pipeline and covered by tests
- [ ] NIIT implemented in stage pipeline and covered by tests
- [ ] Refund/negative-tax semantics finalized and documented
- [ ] Idaho state-type mismatch resolved (rules + tests aligned)
- [ ] Full suite green
- [ ] `verify_calculations.py` green
- [ ] Federal edge-case doc updated to resolved status

---

## 6) Suggested execution order

1. Idaho test alignment (quick red-to-green for state failure)
2. Additional Medicare stage-path implementation
3. NIIT stage-path implementation
4. Low-income tax-floor contract decision + implementation
5. Full test + harness pass, then update docs

---

## 7) Sign-off condition

**Production-ready sign-off requires both:**
- Full automated suite green, and
- Federal scenario harness green with no unresolved high-severity tax deltas.
