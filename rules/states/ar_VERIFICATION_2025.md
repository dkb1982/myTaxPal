# Arkansas (AR) 2025 — Verification Report

**Verified:** 2026-02-17 | **Source:** efile.com, Arkansas EDC, Valur

## Tax Brackets — ❌ COMPLETELY WRONG

### YAML has (Single):
| Rate | Range |
|------|-------|
| 2% | $0–$10,000 |
| 4% | $10,000–$50,000 |
| 4.4% | $50,000+ |

### Correct 2025 (all filers — AR doesn't vary by filing status):
| Rate | Range |
|------|-------|
| 0% | $0–$5,499 |
| 2% | $5,500–$10,899 |
| 3% | $10,900–$15,599 |
| 3.4% | $15,600–$25,699 |
| 3.9% | $25,700+ |

### Issues:
- **3 brackets in YAML vs 5 in reality**
- **Missing the 0% bracket** (first $5,499 tax-free)
- **Top rate is 3.9%, not 4.4%** — AR reduced their top rate for 2025
- **Missing 3% and 3.4% brackets entirely**
- **Thresholds all wrong**
- AR does NOT vary brackets by filing status — YAML has separate Single/MFJ/MFS/HoH brackets which is incorrect

### Severity: 🔴 HIGH — wrong number of brackets, wrong rates, wrong thresholds, wrong filing status structure
