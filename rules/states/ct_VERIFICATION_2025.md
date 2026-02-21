# Connecticut (CT) 2025 — Verification Report

**Verified:** 2026-02-17 | **Source:** efile.com, CT General Assembly, Valur

## Tax Brackets — ❌ COMPLETELY WRONG

### YAML has (Single — 3 brackets):
| Rate | Range |
|------|-------|
| 2% | $0–$10,000 |
| 4% | $10,000–$50,000 |
| 6.99% | $50,000+ |

### Correct 2025 (Single — 7 brackets):
| Rate | Range |
|------|-------|
| 2% | $0–$10,000 |
| 4.5% | $10,000–$50,000 |
| 5.5% | $50,000–$100,000 |
| 6% | $100,000–$200,000 |
| 6.5% | $200,000–$250,000 |
| 6.9% | $250,000–$500,000 |
| 6.99% | $500,000+ |

### Issues:
- **3 brackets in YAML vs 7 in reality**
- **Second bracket rate wrong**: 4% should be **4.5%**
- **Missing 4 entire brackets** (5.5%, 6%, 6.5%, 6.9%)
- Jumps straight from 4% to 6.99%, skipping 4 intermediate rates
- MFJ and HoH brackets also completely wrong (different thresholds needed)
- CT also has a **tax recapture** (benefit recapture) for high incomes — not in YAML

### Severity: 🔴 HIGH — missing 4 of 7 brackets, would drastically overtax middle incomes
