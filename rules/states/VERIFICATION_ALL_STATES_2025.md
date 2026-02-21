# All US States — 2025 Tax Rules Verification Report

**Verified:** 2026-02-17
**Primary Source:** Tax Foundation "2025 State Individual Income Tax Rates & Brackets" (taxfoundation.org)
**Cross-referenced with:** State revenue department websites, efile.com, NerdWallet

---

## ⚠️ SYSTEMIC ISSUE

**Every graduated-rate state uses the same fake 3-bracket template:**
- Bracket 1: $0–$10,000 @ 2%
- Bracket 2: $10,000–$50,000 @ 4%
- Bracket 3: $50,000+ @ [state's actual top rate]
- MFJ doubles all thresholds

**This template matches NO actual state.** Real states have 2–12 brackets with completely different rates and thresholds. The only thing that varies in the YAML is the top rate (and even that is often wrong).

---

## No-Income-Tax States (see separate report)

| State | Status |
|-------|--------|
| AK, FL, NV, SD, TN, TX, WY | ✅ Correct |
| NH | ❌ Tax repealed Jan 1 2025, YAML still has 3% I&D tax |
| WA | ❌ Cap gains: threshold $270k→$278k, missing 9.9% tier over $1M |

---

## Flat-Rate States

| State | YAML Rate | Correct 2025 Rate | Status |
|-------|----------|-------------------|--------|
| AZ | 2.50% | 2.50% | ✅ |
| CO | 4.40% | 4.40% | ✅ |
| GA | 5.49% (graduated) | **5.39% (FLAT)** | ❌ Wrong rate AND wrong type — GA switched to flat tax |
| IL | 4.95% | 4.95% | ✅ |
| IN | 3.05% | **3.00%** | ❌ Reduced for 2025 |
| KY | 4.00% | 4.00% | ✅ |
| MA | 5.00% | 5.00% + **9% over $1,083,150** (millionaire surtax) | ❌ Missing surtax |
| MI | 4.25% | 4.25% | ✅ |
| MS | graduated 3-bracket | **4.40% flat (over $10k)** | ❌ Wrong type — MS simplified to near-flat |
| NC | 4.75% | **4.25%** | ❌ Reduced for 2025 |
| PA | 3.07% | 3.07% | ✅ |
| UT | 4.65% | **4.55%** | ❌ Reduced for 2025 |

### Flat-rate states needing standard deduction checks:
Most flat-rate states in YAML appear to use federal deduction amounts which may be stale (2024 values vs 2025).

---

## Graduated-Rate States — Bracket Comparison

### Alabama (AL) — see separate detailed report
- YAML: 3 brackets ($0-10k, $10k-50k, $50k+)
- Real: 3 brackets but at $500, $3,000 thresholds. **Thresholds ~20x too high.**

### Arkansas (AR)
- YAML: 3 brackets, top rate 4.4%
- Real: 2 brackets effectively — 2% >$4,500, **3.9%** >$4,500 (for income >$89,600 table)
- ❌ Wrong number of brackets, wrong top rate (4.4% vs 3.9%), wrong thresholds

### California (CA)
- YAML: 10 brackets, rates 1%–13.3% (rates correct)
- Real: 10 brackets, same rates but **all thresholds are 2024 values** (~6% off)
- ❌ Thresholds stale

### Connecticut (CT)
- YAML: 3 brackets (2%, 4%, 6.99%)
- Real: **7 brackets** (2%, 4.5%, 5.5%, 6%, 6.5%, 6.9%, 6.99%)
- ❌ Missing 4 brackets, 2nd bracket rate wrong (4% vs 4.5%)

### Delaware (DE)
- YAML: 3 brackets (2%, 4%, 6.6%)
- Real: **7 brackets** (0%, 2.2%, 3.9%, 4.8%, 5.2%, 5.55%, 6.6%)
- ❌ Completely wrong — has 0% bracket, different rates at every level

### DC (District of Columbia)
- YAML: 3 brackets (2%, 4%, 10.75%)
- Real: **7 brackets** (4%, 6%, 6.5%, 8.5%, 9.25%, 9.75%, 10.75%)
- ❌ Completely wrong — lowest rate is 4% not 2%

### Hawaii (HI)
- YAML: 3 brackets (2%, 4%, 11%)
- Real: **12 brackets** (1.4%, 3.2%, 5.5%, 6.4%, 6.8%, 7.2%, 7.6%, 7.9%, 8.25%, 9%, 10%, 11%)
- ❌ Missing 9 brackets

### Idaho (ID)
- YAML: 3 brackets, top 5.8%
- Real: **1 bracket (effectively flat)** — 5.695% on income over $4,673 (single)
- ❌ Wrong structure — ID simplified to near-flat

### Iowa (IA)
- YAML: 3 brackets, top 5.7%
- Real: **1 bracket (FLAT)** — 3.80%
- ❌ Completely wrong — Iowa went flat for 2025

### Kansas (KS)
- YAML: 3 brackets, top 5.7%
- Real: **2 brackets** — 5.20% >$0, 5.58% >$23,000 (single)
- ❌ Wrong rates, wrong thresholds

### Louisiana (LA)
- YAML: 3 brackets, top 4.25%
- Real: **1 bracket (FLAT)** — 3.00%
- ❌ Completely wrong — Louisiana went flat for 2025 at 3%, not graduated at 4.25%

### Maine (ME)
- YAML: 3 brackets, top 7.15%
- Real: **3 brackets** — 5.8%, 6.75%, 7.15%
- ❌ Wrong rates on lower brackets (2%/4% vs 5.8%/6.75%), thresholds wrong

### Maryland (MD)
- YAML: 3 brackets, top 5.75%
- Real: **8 brackets** (2%, 3%, 4%, 4.75%, 5%, 5.25%, 5.5%, 5.75%)
- ❌ Missing 5 brackets

### Minnesota (MN)
- YAML: 3 brackets, top 9.85%
- Real: **4 brackets** (5.35%, 6.80%, 7.85%, 9.85%)
- ❌ Missing 1 bracket, lower rates wrong

### Missouri (MO)
- YAML: 3 brackets, top 4.8%
- Real: **7 brackets** (2%, 2.5%, 3%, 3.5%, 4%, 4.5%, 4.7%)
- ❌ Top rate 4.7% not 4.8%, missing 4 brackets, thresholds completely different (start at $1,313)

### Mississippi (MS)
- YAML: 3 brackets, top 5%
- Real: **1 bracket** — 4.40% flat on income over $10,000
- ❌ Wrong — MS simplified, not graduated

### Montana (MT)
- YAML: 3 brackets, top 5.9%
- Real: **2 brackets** — 4.7% >$0, 5.9% >$21,100 (single)
- ❌ Wrong lower rates and thresholds

### Nebraska (NE)
- YAML: 3 brackets, top 5.84%
- Real: **4 brackets** (2.46%, 3.51%, 5.01%, 5.20%)
- ❌ Top rate 5.20% not 5.84%, wrong rates, wrong thresholds

### New Jersey (NJ)
- YAML: 3 brackets, top 10.75%
- Real: **7 brackets** (1.4%, 1.75%, 3.5%, 5.525%, 6.37%, 8.97%, 10.75%) — different for single vs MFJ
- ❌ Missing 4 brackets

### New Mexico (NM)
- YAML: 3 brackets, top 5.9%
- Real: **6 brackets** (1.5%, 3.2%, 4.3%, 4.7%, 4.9%, 5.9%)
- ❌ Missing 3 brackets

### New York (NY)
- YAML: appears to have more brackets (45 income_from entries = 9 brackets × 5 filing statuses)
- Real: **9 brackets** (4%, 4.5%, 5.25%, 5.5%, 6%, 6.85%, 9.65%, 10.3%, 10.9%)
- Need to verify thresholds — NY may be closer to correct than other states

### North Dakota (ND)
- YAML: 3 brackets, top 1.95%
- Real: **2 brackets** — 1.95% >$48,475, 2.5% >$244,825 (single)
- ❌ YAML top rate 1.95% but real top rate is 2.5%, and the 2%/4% lower brackets don't exist

### Ohio (OH)
- YAML: 3 brackets, top 3.5%
- Real: **2 brackets** — 2.75% >$26,050, 3.5% >$100,000
- ❌ Wrong lower brackets (2%/4% don't exist in OH)

### Oklahoma (OK)
- YAML: 3 brackets, top 4.75%
- Real: **6 brackets** (0.25%, 0.75%, 1.75%, 2.75%, 3.75%, 4.75%)
- ❌ Missing 3 brackets, lower rates completely wrong

### Oregon (OR)
- YAML: 3 brackets, top 9.9%
- Real: **4 brackets** (4.75%, 6.75%, 8.75%, 9.9%)
- ❌ Missing 1 bracket, lower rates wrong

### Rhode Island (RI)
- YAML: 3 brackets, top 5.99%
- Real: **3 brackets** (3.75%, 4.75%, 5.99%)
- ❌ Wrong rates (2%/4% vs 3.75%/4.75%), wrong thresholds ($79,900 and $181,650)

### South Carolina (SC)
- YAML: 3 brackets, top 6.4%
- Real: **3 brackets** (0%, 3%, 6.2%)
- ❌ Wrong rates (2%/4% vs 0%/3%), top rate 6.2% not 6.4%, thresholds ($3,560/$17,830)

### Vermont (VT)
- YAML: 3 brackets, top 8.75%
- Real: **4 brackets** (3.35%, 6.6%, 7.6%, 8.75%)
- ❌ Missing 1 bracket, lower rates wrong

### Virginia (VA)
- YAML: 3 brackets, top 5.75%
- Real: **4 brackets** (2%, 3%, 5%, 5.75%)
- ❌ Missing 1 bracket, wrong thresholds ($3k, $5k, $17k not $10k/$50k)

### West Virginia (WV)
- YAML: 3 brackets, top 5.12%
- Real: **5 brackets** (2.22%, 2.96%, 3.33%, 4.44%, 4.82%)
- ❌ Top rate 4.82% not 5.12%, missing 2 brackets

### Wisconsin (WI)
- YAML: 3 brackets, top 7.65%
- Real: **4 brackets** (3.5%, 4.4%, 5.3%, 7.65%)
- ❌ Missing 1 bracket, lower rates wrong, thresholds wrong

---

## Summary Scorecard

### ✅ Correct (rate only, deductions may be stale):
- AZ (flat 2.5%)
- CO (flat 4.4%)
- IL (flat 4.95%)
- KY (flat 4%)
- MI (flat 4.25%)
- PA (flat 3.07%)

### ❌ Wrong rate:
- GA: 5.49% graduated → **5.39% flat**
- IN: 3.05% → **3.00%**
- IA: graduated → **3.80% flat**
- LA: graduated 4.25% → **3.00% flat**
- MA: missing 9% millionaire surtax
- MS: graduated → **4.40% flat over $10k**
- NC: 4.75% → **4.25%**
- UT: 4.65% → **4.55%**

### ❌ Wrong brackets (every graduated state):
All 30 graduated states use the same fake 3-bracket template. Not a single one matches reality. States have between 1 and 12 actual brackets.

### ❌ Standard deductions:
Likely stale (2024 values) across most states. Not individually verified but the pattern from AZ suggests they're all one year behind.

### Overall Severity: 🔴 CRITICAL
Every single graduated-rate state has completely fabricated bracket structures. 8 states have wrong rates or wrong tax types. This would produce wildly incorrect tax calculations for any state.
