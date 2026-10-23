# Code Review: Tax Estimator Calculation Engine (Phase 2)

**Review Date:** 2026-01-03
**Reviewer:** Code Review AI
**Resolution Date:** 2026-01-03

**Overall Assessment:** APPROVED (all critical issues resolved)

---

## Resolution Summary

All critical issues and important improvements identified in the original review have been addressed:

| Issue | Status | Resolution |
|-------|--------|------------|
| Float conversion in marginal rate | RESOLVED | Changed to Decimal comparison |
| SS taxability ignores filing status | RESOLVED | Added filing status parameter with correct thresholds |
| Hardcoded SS wage base | RESOLVED | Moved to rules YAML via PayrollTaxConfig |
| Redundant tax_year validation | RESOLVED | Removed redundant check |
| CTC phase-out uses ROUND_CEILING | RESOLVED | Changed to ROUND_DOWN per IRS rules |
| Type annotation for trace field | RESOLVED | Changed to `CalculationTrace \| None` |
| TraceStep result allows float | RESOLVED | Restricted to `Decimal \| int` |
| Private _skipped method | RESOLVED | Renamed to public `skipped()` method |
| UUID import inside method | RESOLVED | Moved to module level |
| Missing test coverage | RESOLVED | Added comprehensive tests |

---

## Changes Made

### Critical Issue Fixes

#### 1. [RESOLVED] Float Conversion in Marginal Rate Lookup
**File:** `stage_07_tax_computation.py`

Changed from float conversion to Decimal comparison:
```python
# Before (BUG)
income = float(taxable_income)
for bracket in sorted(brackets, key=lambda b: -b.income_from):
    if income >= bracket.income_from:

# After (FIXED)
for bracket in sorted(brackets, key=lambda b: -b.income_from):
    if taxable_income >= Decimal(str(bracket.income_from)):
```

#### 2. [RESOLVED] Social Security Taxability Filing Status
**File:** `stage_02_income_aggregation.py`

Added filing status parameter with correct thresholds:
- Single/HOH/MFS: $25,000 lower, $34,000 upper
- MFJ/QSS: $32,000 lower, $44,000 upper

```python
def _calculate_taxable_social_security(
    self, benefits: Decimal, other_income: Decimal, filing_status: str
) -> Decimal:
    if filing_status in ("mfj", "qss"):
        lower_threshold = Decimal(32000)
        upper_threshold = Decimal(44000)
    else:
        lower_threshold = Decimal(25000)
        upper_threshold = Decimal(34000)
```

#### 3. [RESOLVED] Hardcoded SS Wage Base
**Files:** `rules/schema.py`, `rules/federal/2025.yaml`, `stage_04_adjustments_agi.py`

Added `PayrollTaxConfig` model to schema and moved configuration to rules YAML:
```yaml
payroll_taxes:
  social_security_wage_base: 168600
  social_security_rate: 0.062
  medicare_rate: 0.0145
  additional_medicare_threshold: 200000
  additional_medicare_rate: 0.009
  self_employment_factor: 0.9235
```

#### 4. [RESOLVED] Redundant Validation Check
**File:** `stage_01_validation.py`

Removed redundant `if not input_data.tax_year` check since Pydantic already validates this.

#### 5. [RESOLVED] CTC Phase-out Rounding
**File:** `stage_08_credits.py`

Changed from `ROUND_CEILING` to `ROUND_DOWN` per IRS Publication 972:
```python
# Before
excess = ((agi - threshold) / 1000).to_integral_value(rounding="ROUND_CEILING")

# After
excess = ((agi - threshold) / 1000).to_integral_value(rounding="ROUND_DOWN")
```

### Important Improvement Fixes

#### 1. [RESOLVED] Type Annotation for Trace Field
**File:** `context.py`

Changed type annotation to properly express optional:
```python
trace: CalculationTrace | None = field(default=None)
```

#### 2. [RESOLVED] TraceStep Result Type
**File:** `trace.py`

Restricted result type to avoid float precision issues:
```python
# Before
result: Decimal | float | int

# After
result: Decimal | int
```

#### 3. [RESOLVED] Private _skipped Method
**File:** `base.py`, `pipeline.py`

Renamed `_skipped()` to public `skipped()` method for use by pipeline.

#### 4. [RESOLVED] UUID Import Location
**File:** `engine.py`

Moved `import uuid` from inside method to module level.

### New Test Coverage Added

- `test_credits.py` - Child Tax Credit, ACTC, ODC, EIC tests
- `test_preferential_rates.py` - 0%/15%/20% qualified dividend and LTCG tests
- `test_social_security_taxability.py` - SS benefit taxation by filing status
- `test_self_employment_tax.py` - SE tax edge cases including wage base limits

---

## Remaining TODOs (Non-Critical)

The following items were identified as suggestions or enhancements, not critical issues:

1. **Preferential Rate Thresholds** - Currently hardcoded in stage_07. Could be moved to rules YAML for better maintainability across tax years.

2. **EIC Parameters** - Hardcoded in stage_08. Could be moved to rules YAML.

3. **Charitable Contribution AGI Limits** - TODO in stage_05 for 60%/30%/20% limits.

4. **HSA Limit Validation** - TODO in stage_04 for annual HSA limits.

5. **Income Aggregation Refactoring** - Could break into smaller methods for readability.

6. **Validation for Spouse Required for MFJ** - Could add check that spouse is provided.

---

## Test Results

All 284 tests pass after the fixes:
- 169 calculation engine tests
- 115 other tests (API, schema, rules loader)

---

*Review Completed and Issues Resolved*
