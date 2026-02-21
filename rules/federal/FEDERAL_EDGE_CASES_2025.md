# Federal Edge Cases Review (2025)

**Last updated:** 2026-02-20  
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

### ⚠️ What still needs attention

#### 1) Additional Medicare Tax on high W-2 wages
- **Observed:** not applied in high-wage W-2 scenarios
- **Impact:** undertaxed results for affected filers
- **Evidence from `verify_calculations.py`:**
  - Single, $500k W-2 → expected add’l Medicare $2,700, actual $0
  - Single, $750k W-2 → expected add’l Medicare $4,950, actual $0

#### 2) Negative total tax in low-income edge case
- **Observed:** one low-income scenario returns negative total tax
- **Example:** Single, $10k income → expected $0 total tax in harness, actual `-632`
- **Note:** if this is intended refundable-credit behavior, this must be explicitly modeled and asserted consistently in tests/spec.

#### 3) NIIT coverage confirmation
- Historically flagged as missing in earlier review.
- Needs explicit re-verification in current code path with dedicated scenarios (high MAGI + investment income).

---

## Edge-case test matrix to run next

Use this as the canonical checklist for federal sign-off:

1. **Additional Medicare thresholds**
   - Single/HOH/QSS at $200k boundary
   - MFJ at $250k boundary
   - MFS at $125k boundary
   - Mixed W-2 + SE income combinations

2. **NIIT mechanics**
   - Cases where `NII < MAGI excess`
   - Cases where `MAGI excess < NII`
   - Zero NII / below threshold controls
   - Filing-status threshold changes

3. **Refundability / floor semantics**
   - Validate whether negative total tax is allowed at the chosen output layer
   - If allowed, confirm contract for API fields (`total_tax`, `refund`, `balance_due`) so consumers don’t misinterpret

4. **Preferential + ordinary interactions**
   - Large LTCG with moderate ordinary income
   - Dividend-heavy cases with withholding

5. **Boundary precision checks**
   - 0.01-dollar edge around bracket boundaries
   - Exact threshold values and just-over thresholds

---

## Repro commands

From repo root:

```bash
.venv/bin/python verify_calculations.py
.venv/bin/python -m pytest tests/calculation -q --tb=short
.venv/bin/python -m pytest tests/test_compare_invariants.py -q --tb=short
```

---

## Sign-off criteria (Federal)

Federal can be considered comfortable for production when all are true:

1. `verify_calculations.py` has **0 failed assertions** (or expected exceptions are explicitly documented and asserted).
2. Additional Medicare is correctly computed for all filing statuses and mixed-income cases.
3. NIIT behavior is covered by tests and validated against IRS formula logic.
4. Refund vs total-tax semantics are unambiguous and tested at API contract level.
5. No placeholder constants remain for critical 2025 federal rules without provenance.

---

## Notes for next review pass

- Prioritize Additional Medicare first (high confidence bug, high user impact).
- Then lock NIIT with explicit scenario tests.
- Finally normalize low-income negative-tax semantics (intentional refundable vs calculation leak).

Once these are resolved, re-run the full suite and attach updated output to this doc.
