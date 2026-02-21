# Alabama (AL) 2025 Tax Rules — Verification Report

**Tax Year:** 2025
**Verified:** 2026-02-17
**Source:** Alabama Department of Revenue (revenue.alabama.gov)

---

## 1. Tax Brackets — ❌ COMPLETELY WRONG

### Single / HoH / MFS (Official):
| Taxable Income | Rate |
|---------------|------|
| First $500 | 2% |
| Next $2,500 ($500–$3,000) | 4% |
| Over $3,000 | 5% |

### MFJ (Official):
| Taxable Income | Rate |
|---------------|------|
| First $1,000 | 2% |
| Next $5,000 ($1,000–$6,000) | 4% |
| Over $6,000 | 5% |

### What the YAML has (all wrong):
| Filing Status | YAML Brackets | Correct Brackets |
|--------------|---------------|------------------|
| Single | $0–10k/2%, $10k–50k/4%, $50k+/5% | $0–500/2%, $500–3k/4%, $3k+/5% |
| MFJ | $0–20k/2%, $20k–100k/4%, $100k+/5% | $0–1k/2%, $1k–6k/4%, $6k+/5% |
| MFS | $0–10k/2%, $10k–50k/4%, $50k+/5% | $0–500/2%, $500–3k/4%, $3k+/5% |
| HoH | $0–15k/2%, $15k–75k/4%, $75k+/5% | $0–500/2%, $500–3k/4%, $3k+/5% |

**The rates (2%, 4%, 5%) are correct but all thresholds are ~20x too high.** This would massively undertax people — e.g. someone earning $40k single would pay 2% on the whole amount in the YAML ($800) vs correctly paying ~$1,960.

### base_tax also wrong:
| Filing Status | YAML base_tax bracket 2 | Correct | YAML base_tax bracket 3 | Correct |
|--------------|------------------------|---------|------------------------|---------|
| Single | 200 | 10 | 1,800 | 110 |
| MFJ | 400 | 20 | 3,600 | 220 |

**Source:** https://www.revenue.alabama.gov/faqs/what-is-alabamas-individual-income-tax-rate/

---

## 2. Standard Deduction — ❌ WRONG

Alabama's standard deduction is **AGI-based** (sliding scale), not a fixed amount. The deduction phases out as AGI increases.

| Filing Status | YAML Amount | Approximate Correct Range |
|--------------|-------------|--------------------------|
| Single | $5,000 | $2,500 max (phases out above $20,499 AGI, gone at $30,499) |
| MFJ | $10,000 | $7,500 max (phases out above $20,499 AGI, gone at $30,499) |
| MFS | $5,000 | $3,750 max |
| HoH | $7,500 | $4,700 max (phases out similarly) |

The YAML uses simple fixed amounts. Alabama actually uses a chart where the deduction decreases as AGI increases. This is a structural issue — the engine would need to support AGI-based sliding deductions for Alabama.

---

## 3. Personal Exemptions — ❌ WRONG

| Field | YAML | Correct |
|-------|------|---------|
| personal_exemption_available | **false** | **true** |
| personal_exemption_amount | 0 | Single/MFS: **$1,500**, MFJ/HoH: **$3,000** |
| dependent_exemption_available | **false** | **true** |
| dependent_exemption_amount | 0 | **$1,000** per dependent (under 20 or student) |

**Source:** Alabama DOR FAQ

---

## 4. Missing: Federal Tax Deduction

Alabama is one of the few states that allows a **deduction for federal income tax paid**. This is not mentioned anywhere in the YAML. It significantly reduces Alabama taxable income for higher earners.

---

## Summary

| Section | Status |
|---------|--------|
| Tax rates (2%, 4%, 5%) | ✅ Correct |
| Tax bracket thresholds | ❌ All ~20x too high |
| base_tax values | ❌ Wrong (follows from wrong thresholds) |
| Standard deduction | ❌ Wrong (fixed amounts vs AGI-based sliding scale) |
| Personal exemptions | ❌ Missing entirely |
| Dependent exemptions | ❌ Missing entirely |
| Federal tax deduction | ❌ Missing entirely |

### Severity: 🔴 HIGH
Every bracket threshold is wrong. Would massively undertax everyone. Missing personal exemptions and federal tax deduction.
