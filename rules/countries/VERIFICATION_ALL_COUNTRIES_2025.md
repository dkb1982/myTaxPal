# International Countries — 2025 Tax Rules Verification Report

**Verified:** 2026-02-17
**Sources:** PwC Tax Summaries, government tax authority websites, NerdWallet, Wealthsimple
**GB covered separately in `gb/VERIFICATION_2025.md`**

---

## UAE (AE) — ✅ CORRECT
- YAML: `has_income_tax: false`, `rate_type: "none"`
- Reality: No personal income tax in UAE
- **Status: ✅ Correct**

---

## Australia (AU) — ✅ CORRECT

| Bracket | YAML | Official 2024-25 | Status |
|---------|------|-------------------|--------|
| $0–$18,200 | 0% | 0% | ✅ |
| $18,200–$45,000 | 16% | 16% | ✅ |
| $45,000–$135,000 | 30% | 30% | ✅ |
| $135,000–$190,000 | 37% | 37% | ✅ |
| $190,000+ | 45% | 45% | ✅ |

Note: These are the Stage 3 tax cuts rates effective from 1 July 2024 (2024-25 FY). All correct.

**Source:** ATO, H&R Block Australia

**Missing:** Medicare Levy (2% on most taxpayers) not mentioned in rate schedule.

---

## Canada (CA) — ❌ PARTIALLY WRONG

| Bracket | YAML | Official 2025 | Status |
|---------|------|---------------|--------|
| $0–$57,375 | 15% | 15% | ✅ |
| $57,375–$114,750 | 20.5% | 20.5% | ✅ |
| $114,750–$158,468 | 26% | 26% | ❌ Threshold wrong |
| $158,468–$221,708 | 29% | 29% | ❌ Threshold wrong |
| $221,708+ | 33% | 33% | ❌ Threshold wrong |

Correct 2025 thresholds:
- 26%: $114,750–**$177,882** (YAML has $158,468)
- 29%: $177,882–**$253,414** (YAML has $221,708)
- 33%: over **$253,414** (YAML has $221,708)

Rates are correct but brackets 3-5 have **wrong thresholds** (appear to be 2024 values).

CPP rate in YAML: 5.95% — needs verification for 2025.

**Source:** CRA via Wealthsimple

---

## Germany (DE) — ❌ WRONG THRESHOLDS

| Zone | YAML Threshold | Official 2025 | Status |
|------|---------------|---------------|--------|
| Tax-free (0%) | €0–€11,604 | €0–**€12,096** | ❌ |
| Progressive 14-24% | €11,604–€17,005 | €12,096–? | ❌ |
| Progressive 24-42% | €17,005–€66,760 | ?–**€68,429** | ❌ |
| 42% | €66,760–€277,825 | €68,430–€277,825 | ❌ low end |
| 45% | €277,825+ | €277,825+ | ✅ |

Germany uses a **formula-based progressive system** (not simple brackets) in the 14-42% zone. The YAML simplifies this into discrete brackets which is structurally imprecise. The tax-free threshold increased to €12,096 for 2025 (YAML has the 2024 value of €11,604).

Solidarity surcharge: 5.5% in YAML — ✅ correct rate, but only applies to higher incomes (not universal since 2021).

**Source:** PwC Germany Tax Summary

---

## Spain (ES) — ❌ WRONG RATES

| Bracket | YAML Rate | Official Combined Rate | Status |
|---------|----------|----------------------|--------|
| €0–€12,450 | 9.5% | **19%** | ❌ |
| €12,450–€20,200 | 12% | **24%** | ❌ |
| €20,200–€35,200 | 15% | **30%** | ❌ |
| €35,200–€60,000 | 18.5% | **37%** | ❌ |
| €60,000–€300,000 | 22.5% | **45%** | ❌ |
| €300,000+ | YAML has 24.5% | **47%** | ❌ |

**Every rate is exactly half of the real rate.** Spain's income tax (IRPF) is split between state and regional components. The YAML appears to only have the **state portion** (~50%) and is missing the regional portion entirely. The combined rates are approximately double what's in the YAML.

**Source:** Banco Santander IRPF calculator, movingtospain.com

---

## France (FR) — ✅ CORRECT

| Bracket | YAML | Official 2025 | Status |
|---------|------|---------------|--------|
| €0–€11,294 | 0% | 0% | ✅ |
| €11,294–€28,797 | 11% | 11% | ✅ |
| €28,797–€82,341 | 30% | 30% | ✅ |
| €82,341–€177,106 | 41% | 41% | ✅ |
| €177,106+ | 45% | 45% | ✅ |

Note: France applies the quotient familial (family quotient) system. These are the per-share rates. All match.

**Source:** service-public.gouv.fr (official French government)

---

## Hong Kong (HK) — ✅ CORRECT

| Bracket | YAML | Official 2024-25+ | Status |
|---------|------|-------------------|--------|
| $0–$50,000 | 2% | 2% | ✅ |
| $50,000–$100,000 | 6% | 6% | ✅ |
| $100,000–$150,000 | 10% | 10% | ✅ |
| $150,000–$200,000 | 14% | 14% | ✅ |
| $200,000+ | 17% | 17% | ✅ |
| Standard rate | 15% | **Two-tier: 15% on first $5M, 16% on remainder** | ❌ |

Progressive rates all correct. Standard rate needs updating: from 2024-25 onwards, HK introduced a two-tiered standard rate (15% on first HK$5M net income, 16% on the rest). YAML only has 15%.

**Source:** gov.hk Inland Revenue Department

---

## Italy (IT) — ✅ CORRECT

| Bracket | YAML | Official 2025 IRPEF | Status |
|---------|------|---------------------|--------|
| €0–€28,000 | 23% | 23% | ✅ |
| €28,000–€50,000 | 35% | 35% | ✅ |
| €50,000+ | 43% | 43% | ✅ |

Italy consolidated from 4 to 3 IRPEF brackets starting 2024, and kept the same structure for 2025. YAML matches.

Note: Regional and municipal surcharges apply on top but vary by locality.

**Source:** PwC Italy Tax Summary, KPMG

---

## Japan (JP) — ✅ RATES CORRECT, needs threshold check

YAML rates: 5%, 10%, 20%, 23%, 33%, 40%, 45% — all match official NTA rates.

| Bracket | Official Threshold (JPY) |
|---------|------------------------|
| 5% | 0–1,950,000 |
| 10% | 1,950,000–3,300,000 |
| 20% | 3,300,000–6,950,000 |
| 23% | 6,950,000–9,000,000 |
| 33% | 9,000,000–18,000,000 |
| 40% | 18,000,000–40,000,000 |
| 45% | 40,000,000+ |

Need to verify YAML thresholds match these exactly (couldn't read full YAML brackets).

Reconstruction tax: 2.1% — ✅ correct.

Note: From 2025, Japan has a new **minimum tax** of 27.5% on income over ¥330M — not in YAML.

**Source:** PwC Japan Tax Summary

---

## Portugal (PT) — ❌ WRONG

| Bracket | YAML Rate | Official 2025 Rate | Status |
|---------|----------|--------------------| --------|
| €0–€7,703 | 13.25% | **12.50%** (€0–€8,059) | ❌ rate and threshold |
| €7,703–€11,623 | 18% | **16%** (€8,059–€12,160) | ❌ rate and threshold |
| €11,623–€16,472 | 23% | **21.5%** (€12,160–€17,233) | ❌ rate and threshold |
| €16,472–€21,321 | 26% | **24.4%** (€17,233–€22,306) | ❌ rate and threshold |
| €21,321–€27,146 | 32.75% | **31.4%** (€22,306–€28,400) | ❌ rate and threshold |
| €27,146–? | Continues... | **34.9%** (€28,400–€41,629) | ❌ |

Every bracket threshold and every rate is wrong. The YAML appears to be from a **previous year** — Portugal updated its brackets for 2025 with new thresholds and slightly different rates. Also, the top rate is now 48% (YAML may have old 48% or different).

Missing: 2.5% solidarity surcharge over €80,000 and 5% over €250,000.

**Source:** PwC Portugal Tax Summary

---

## Singapore (SG) — ❌ PARTIALLY WRONG

YAML brackets (from what I can see):

| Bracket | YAML Rate | Official YA2024+ Rate | Status |
|---------|----------|----------------------|--------|
| $0–$20,000 | 0% | 0% | ✅ |
| $20,000–$30,000 | 2% | 2% | ✅ |
| $30,000–$40,000 | 3.5% | 3.5% | ✅ |
| $40,000–$80,000 | 7% | 7% | ✅ |
| $80,000–$120,000 | 11.5% | 11.5% | ✅ |
| $120,000+ | ? | Continues to 24% | Need to verify |

Lower brackets appear correct. Singapore has rates up to **24%** (on income over $1M) from YA2024. Need to verify YAML includes the full bracket structure up to 24%.

The YAML employee CPF rate of 5% appears low — actual CPF employee rate is **20%** for workers under 55 (on first $6,800/month). This is a major error if included.

**Source:** IRAS (Inland Revenue Authority of Singapore)

---

## Summary Scorecard

| Country | Rate | Thresholds | Overall |
|---------|------|------------|---------|
| AE (UAE) | ✅ No tax | N/A | ✅ |
| AU (Australia) | ✅ | ✅ | ✅ |
| CA (Canada) | ✅ | ❌ (brackets 3-5 stale) | 🟡 |
| DE (Germany) | ✅ (rates) | ❌ (tax-free €11,604→€12,096) | 🟡 |
| ES (Spain) | ❌ (~half of real rates) | ✅ (thresholds OK) | 🔴 |
| FR (France) | ✅ | ✅ | ✅ |
| GB (UK) | See separate report | | 🔴 |
| HK (Hong Kong) | ✅ progressive | ❌ standard rate (needs two-tier) | 🟡 |
| IT (Italy) | ✅ | ✅ | ✅ |
| JP (Japan) | ✅ | Needs check | 🟡 |
| PT (Portugal) | ❌ (all rates wrong) | ❌ (all thresholds wrong) | 🔴 |
| SG (Singapore) | ✅ lower | CPF rate possibly wrong | 🟡 |

### Critical Issues:
1. **Spain**: Every rate is ~50% of the real combined rate (missing regional component)
2. **Portugal**: All rates and thresholds from a previous year
3. **Canada**: Upper bracket thresholds stale
4. **Germany**: Tax-free threshold not updated for 2025
5. **Singapore**: CPF employee rate of 5% should be 20% (if used for employee deductions)
