# US Local/City Tax Verification — 2025 Tax Year

**Date:** 2026-02-17  
**Scope:** All 14 cities in `rules/locals/`  
**Approach:** Verify-only — no changes made  
**Sources:** Official city/state websites, SmartAsset, TurboTax, Tax Foundation, CCA Ohio, RITA Ohio, NerdWallet

---

## Summary

| # | City | State | YAML Rate | Actual 2025 Rate | Status | Key Issue |
|---|------|-------|-----------|-------------------|--------|-----------|
| 1 | New York City | NY | 3.078%–3.876% (4 brackets) | 3.078%–3.876% (4 brackets) | ✅ Rates correct | Bracket thresholds need full verification by filing status; base_tax values unverified |
| 2 | Yonkers | NY | 16.75% surcharge / 0.5% nonres | 16.75% surcharge / 0.5% nonres | 🟡 Partially correct | Surcharge may have changed — law references 15% in statute, but withholding tables use 16.75%. Verify which applies for 2025 |
| 3 | Philadelphia | PA | 3.75% res / 3.44% nonres | 3.74% res / 3.43% nonres | ❌ Wrong | Rates reduced for 2025 (effective July 1, 2025 per city ordinance). YAML has 2024 rates |
| 4 | Pittsburgh | PA | 3.0% res / 1.0% nonres | 3.0% res / 1.0% nonres | ✅ Correct | $52 LST and $12,000 exemption also correct |
| 5 | Detroit | MI | 2.4% res / 1.2% nonres | 2.4% res / 1.2% nonres | ✅ Correct | |
| 6 | Cleveland | OH | 2.5% flat | 2.5% flat | ✅ Correct | 100% credit, max 2.5% — matches CCA data |
| 7 | Columbus | OH | 2.5% flat | 2.5% flat | ✅ Correct | RITA-collected; credit system matches |
| 8 | Cincinnati | OH | 1.8% flat | 1.8% flat | ✅ Correct | Rate effective since 10/02/2020 per city website |
| 9 | Baltimore | MD | 3.2% piggyback | 3.3% piggyback | ❌ Wrong | Baltimore City increased rate from 3.20% to 3.30% retroactively for tax year 2025 (per MD Comptroller tax alert) |
| 10 | Wilmington | DE | 1.25% flat | 1.25% flat | ✅ Correct | Set by Delaware General Assembly |
| 11 | Louisville | KY | 2.25% flat | 2.2% res / 1.45% nonres | ❌ Wrong | Rate is 2.2% (not 2.25%), and YAML missing separate nonresident rate of 1.45% |
| 12 | Kansas City | MO | 1.0% flat | 1.0% flat | ✅ Correct | |
| 13 | St. Louis | MO | 1.0% flat | 1.0% flat | ✅ Correct | |
| 14 | Newark | NJ | 1.0% employer payroll | 1.0% employer payroll | ✅ Correct | Employer-only tax, not employee income tax. Questionable whether this belongs in a personal income tax calculator |

---

## Detailed Findings

### 1. New York City (ny_nyc.yaml) — ✅ Rates Correct

**Tax type:** Progressive city income tax, residents only  
**YAML:** 4 brackets per filing status (single, mfj, mfs, hoh, qss)

**Single filer brackets (YAML vs Actual):**

| Bracket | YAML Threshold | Actual 2025 | YAML Rate | Actual Rate | Match? |
|---------|---------------|-------------|-----------|-------------|--------|
| 1 | $0–$12,000 | $0–$12,000 | 3.078% | 3.078% | ✅ |
| 2 | $12,000–$25,000 | $12,000–$25,000 | 3.762% | 3.762% | ✅ |
| 3 | $25,000–$50,000 | $25,000–$50,000 | 3.819% | 3.819% | ✅ |
| 4 | $50,000+ | $50,000+ | 3.876% | 3.876% | ✅ |

**Notes:**
- Single filer brackets and rates confirmed via SmartAsset, NerdWallet, NYC Comptroller, and nycaccountingconsulting.com
- MFJ thresholds ($21,600 / $45,000 / $90,000) are in YAML but not independently verified from official 2025 NYC tax tables — should be checked against NYC-210 instructions
- HOH thresholds ($14,400 / $30,000 / $60,000) similarly need official verification
- `base_tax` values appear to be correctly computed cumulative amounts but should be validated
- NYC school tax credit ($125, income limit $250,000) is marked placeholder — needs verification
- Residents-only applicability is **correct** — non-residents working in NYC do NOT pay NYC income tax (confirmed multiple sources)

**Source:** SmartAsset NYC paycheck calculator; nycaccountingconsulting.com; NYC Comptroller report

---

### 2. Yonkers (ny_yonkers.yaml) — 🟡 Partially Correct

**Tax type:** Mixed — resident surcharge on NY state tax + nonresident flat wage tax

| Component | YAML | Actual 2025 | Match? |
|-----------|------|-------------|--------|
| Resident surcharge | 16.75% of NY state tax | **Conflicting**: Statute says 15%; withholding tables/SmartAsset say 16.75% | ⚠️ |
| Nonresident rate | 0.5% of wages | 0.5% of wages | ✅ |

**Analysis:**
- The Justia statute reference says estimated tax payments should be "fifteen percent (15%)" of NY state tax
- However, SmartAsset, NerdWallet, and Reddit all cite 16.75% as the current resident surcharge rate
- The NY tax department withholding publication (NYS-50-T-Y) for 2026 confirms the Yonkers surcharge rate applies but the PDF was unreadable
- The ecode360 ordinance says the surcharge applies through "December 31, 2025" — may expire or be renewed
- **Most likely**: The 15% was the original statutory rate; it has been amended to 16.75% by subsequent legislation. The YAML value of 16.75% appears correct for current use, but the statutory authority should be confirmed
- Nonresident 0.5% rate confirmed: "non-residents pay 0.5% of wages" (SmartAsset)

**Source:** SmartAsset; Justia law.justia.com/codes/new-york/yts; ecode360.com; tax.ny.gov

---

### 3. Philadelphia (pa_philadelphia.yaml) — ❌ Wrong

**Tax type:** City wage tax, both residents and workers

| Component | YAML | Actual 2025 | Difference |
|-----------|------|-------------|------------|
| Resident rate | 3.75% | **3.74%** (effective Jul 1, 2025) | ❌ -0.01% |
| Nonresident rate | 3.44% | **3.43%** (effective Jul 1, 2025) | ❌ -0.01% |

**Details:**
- Philadelphia made tax rate changes for 2025 (announced June 18, 2025)
- Resident: 3.75% → 3.74%; Nonresident: 3.44% → 3.43%
- New rates apply to paychecks with pay dates after June 30, 2025
- The YAML uses the 2024 rates
- Tax base (wages only, not investment income) is correctly described

**Source:** phila.gov official announcement; alloysilverstein.com; USDA NFC bulletin

---

### 4. Pittsburgh (pa_pittsburgh.yaml) — ✅ Correct

**Tax type:** Earned income tax (municipal + school district) + Local Services Tax

| Component | YAML | Actual 2025 | Match? |
|-----------|------|-------------|--------|
| Resident total EIT | 3.0% (1% muni + 2% school) | 3.0% (1% muni + 2% school) | ✅ |
| Nonresident rate | 1.0% (municipal only) | 1.0% (municipal only) | ✅ |
| Local Services Tax | $52/year | $52/year | ✅ |
| LST low-income exemption | $12,000 | $12,000 | ✅ |

**Source:** TurboTax PA tax guide; University of Pittsburgh payroll; Cozen O'Connor legal alert; City of Pittsburgh LS-1 form

---

### 5. Detroit (mi_detroit.yaml) — ✅ Correct

**Tax type:** City income tax, both residents and workers

| Component | YAML | Actual 2025 | Match? |
|-----------|------|-------------|--------|
| Resident rate | 2.4% | 2.4% | ✅ |
| Nonresident rate | 1.2% | 1.2% | ✅ |
| Filing threshold | $600 | Needs verification | ⚠️ |

**Notes:**
- H&R Block confirms other Michigan cities use 1%/0.5%, but Detroit has special higher rate of 2.4%/1.2%
- ATS CPAs and Wayne State payroll both confirm 2.4% resident / 1.2% nonresident
- Tax base is "taxable income" (similar to federal) — correctly described
- Filing threshold of $600 is a common Michigan city threshold but should be confirmed against D-1040 instructions

**Source:** atscpas.com; H&R Block; Wayne State payroll department; michigan.gov

---

### 6. Cleveland (oh_cleveland.yaml) — ✅ Correct

**Tax type:** Municipal income tax, flat rate

| Component | YAML | Actual 2025 | Match? |
|-----------|------|-------------|--------|
| Rate | 2.5% | 2.5% | ✅ |
| Credit allowed | Yes, 100%, max 2.5% | Yes, 100%, max 2.5% | ✅ |
| Collection agency | CCA | CCA (Central Collection Agency) | ✅ |

**Source:** CCA Ohio (ccaohio.gov/tax-rates) — Cleveland listed at 2.50%, 100% credit, 2.50% credit limit

---

### 7. Columbus (oh_columbus.yaml) — ✅ Correct

**Tax type:** Municipal income tax, flat rate

| Component | YAML | Actual 2025 | Match? |
|-----------|------|-------------|--------|
| Rate | 2.5% | 2.5% | ✅ |
| Credit allowed | Yes, 100%, max 2.5% | Yes, 100% | ✅ |
| Collection agency | RITA | RITA (but Columbus actually self-administers) | ⚠️ Minor |

**Notes:**
- Columbus collects its own income tax through the City Auditor's Income Tax Division — not RITA
- The rate and credit are correct
- United Way of Central Ohio confirms "The City of Columbus collects a 2.5% tax"

**Source:** columbus.gov; liveunitedcentralohio.org; RITA tax rates table

---

### 8. Cincinnati (oh_cincinnati.yaml) — ✅ Correct

**Tax type:** Municipal income tax, flat rate

| Component | YAML | Actual 2025 | Match? |
|-----------|------|-------------|--------|
| Rate | 1.8% | 1.8% | ✅ |
| Credit allowed | Yes | Yes | ✅ |

**Notes:**
- Rate of 1.8% effective since 10/02/2020 (reduced from prior 2.1%)
- Cincinnati's official FAQ confirms: "Anyone who lives or works in Cincinnati is subject to the 1.8% income tax"
- Credit system for taxes paid to work city is standard Ohio municipal practice

**Source:** cincinnati-oh.gov/finance; Cincinnati FAQ

---

### 9. Baltimore City (md_baltimore.yaml) — ❌ Wrong

**Tax type:** County/city piggyback on Maryland taxable income

| Component | YAML | Actual 2025 | Difference |
|-----------|------|-------------|------------|
| Piggyback rate | 3.2% | **3.3%** | ❌ +0.10% |

**Details:**
- Baltimore City retroactively increased its local income tax rate from 3.20% to 3.30% for tax year 2025
- This was enacted during the 2025 Maryland legislative session
- The maximum local rate cap was also raised from 3.20% to 3.30% statewide
- YAML also describes this as a "piggyback" tax — it's technically a flat rate on Maryland taxable income, not a percentage of Maryland state tax. The terminology in the YAML is correct in spirit (it piggybacks on the MD taxable income calculation)

**Source:** Maryland Comptroller tax alert; NFIB; wattercpa.com

---

### 10. Wilmington (de_wilmington.yaml) — ✅ Correct

**Tax type:** City wage tax, flat rate

| Component | YAML | Actual 2025 | Match? |
|-----------|------|-------------|--------|
| Rate | 1.25% | 1.25% | ✅ |

**Notes:**
- Rate set by Delaware General Assembly
- Applies to both residents and non-residents working in Wilmington
- Confirmed by City of Wilmington FY2025 tax rates document and tax-rates.org
- Tax base is earned income (wages + self-employment) — correctly described

**Source:** wilmdebudget.org FY25 tax rates PDF; wilmingtonde.gov; tax-rates.org

---

### 11. Louisville (ky_louisville.yaml) — ❌ Wrong

**Tax type:** Occupational license fee ("occupational tax")

| Component | YAML | Actual 2025 | Difference |
|-----------|------|-------------|------------|
| Rate | 2.25% (single flat rate) | **2.2% resident / 1.45% nonresident** | ❌ Wrong rate, missing nonresident distinction |

**Details:**
- Louisville Metro OL-3 form confirms: "Occupational Tax Rate of 2.2% (resident rate) or 1.45% (non-resident rate)"
- YAML has 2.25% as a single rate — wrong on two counts:
  1. Rate should be 2.2%, not 2.25%
  2. There should be separate resident/nonresident rates (like Philadelphia, Detroit)
- The YAML structure uses `flat_rates.rate` (single rate) but should use `flat_rates.resident_rate` and `flat_rates.nonresident_rate`
- Form name "OL-3" is correctly referenced

**Source:** louisvilleky.gov OL-3 form description; KACO data brief

---

### 12. Kansas City (mo_kansas_city.yaml) — ✅ Correct

**Tax type:** Earnings tax, flat rate

| Component | YAML | Actual 2025 | Match? |
|-----------|------|-------------|--------|
| Rate | 1.0% | 1.0% | ✅ |
| Form | RD-109 | RD-109 | ✅ |

**Notes:**
- Confirmed on kcmo.gov: "a 1 percent tax on an individual's earned income"
- Applies to both residents and workers (correctly described)
- As of January 1, 2025, all KCMO taxes must be filed electronically

**Source:** kcmo.gov official earnings tax page

---

### 13. St. Louis (mo_st_louis.yaml) — ✅ Correct

**Tax type:** Earnings tax, flat rate

| Component | YAML | Actual 2025 | Match? |
|-----------|------|-------------|--------|
| Rate | 1.0% | 1.0% | ✅ |
| Form | E-1 | E-1 | ✅ |

**Notes:**
- St. Louis city website confirms "low 1 percent rate"
- Multiple sources confirm 1% for both residents and workers

**Source:** stlouis-mo.gov; visaverge.com

---

### 14. Newark (nj_newark.yaml) — ✅ Rate Correct, ⚠️ Structural Concern

**Tax type:** Employer payroll tax (NOT an employee income tax)

| Component | YAML | Actual 2025 | Match? |
|-----------|------|-------------|--------|
| Rate | 1.0% | 1.0% | ✅ |
| Applies to | Workers only | Employers with payroll > $2,500/quarter | ⚠️ |

**Structural concern:**
- Newark's payroll tax is an **employer-paid** tax, not an employee income tax
- It is levied on employers "having a payroll in excess of $2,500 in any calendar quarter"
- The YAML correctly notes `applies_to: "workers_only"` and `tax_type: "payroll_tax"` and mentions in notes it's an employer tax
- However, including this in a **personal income tax calculator** is questionable — it doesn't reduce an employee's paycheck directly
- Government and non-profit entities are exempt
- The calculator Python code would apply this as a deduction from the employee's perspective, which may overstate the individual's actual tax burden

**Source:** SAX Advisory; ecode360.com Newark ordinance; newarknj.gov payroll tax booklet

---

## Overall Assessment

### Scorecard

| Status | Count | Cities |
|--------|-------|--------|
| ✅ Correct | 8 | NYC (rates), Pittsburgh, Detroit, Cleveland, Columbus, Cincinnati, Kansas City, St. Louis |
| 🟡 Partially correct | 2 | Yonkers (surcharge rate ambiguity), Newark (rate OK but structural concern) |
| ❌ Wrong | 3 | Philadelphia (-0.01% on both rates), Baltimore (+0.10%), Louisville (wrong rate + missing nonres) |

### Systemic Issues

1. **All files marked PLACEHOLDER** — Every YAML file explicitly says "PLACEHOLDER - DO NOT USE FOR REAL TAX CALCULATIONS" which is good for liability but means none are production-ready

2. **No version tracking** — When rates change (like Philadelphia's mid-year change), there's no mechanism to handle split-year rates

3. **Newark inclusion** — An employer payroll tax doesn't belong in an individual income tax estimator

4. **Collection agency errors** — Columbus YAML says RITA but Columbus self-administers through City Auditor

5. **Missing cities** — Several major US cities with local income taxes are not included:
   - **San Francisco** (payroll tax + gross receipts)
   - **Portland, OR** (Arts Tax $35 flat + Metro Supportive Housing Services 1%)
   - **Denver, CO** ($5.75/month occupational privilege tax)
   - **Indianapolis, IN** (1.77% county tax)
   - Other Michigan cities (Grand Rapids 1.5%, Flint 1%, etc.)
   - Other Ohio cities (Toledo 2.25%, Dayton 2.5%, Akron 2.5%)
   - Other Pennsylvania cities (Reading, Scranton, etc. via PA EIT system)
   - Other Kentucky cities (Lexington 2.25%)

### Priority Fixes

1. **Baltimore** — Update rate from 3.2% to 3.3% (retroactive for entire 2025)
2. **Louisville** — Change rate to 2.2% resident / 1.45% nonresident; add `resident_rate` and `nonresident_rate` fields
3. **Philadelphia** — Update to 3.74% resident / 3.43% nonresident
4. **Yonkers** — Confirm whether 16.75% or 15% applies for 2025 from NY tax dept withholding tables
5. **Newark** — Consider removing or clearly flagging as employer-only tax
6. **Columbus** — Fix collection agency from RITA to City of Columbus Income Tax Division

---

## References

| City | Primary Source | URL |
|------|---------------|-----|
| NYC | SmartAsset / NYC Comptroller | smartasset.com/taxes/new-york-paycheck-calculator |
| Yonkers | NY Tax Dept / Justia | law.justia.com/codes/new-york/yts |
| Philadelphia | City of Philadelphia | phila.gov (Wage Tax employers page) |
| Pittsburgh | TurboTax / Pitt Payroll | blog.turbotax.intuit.com; payroll.pitt.edu |
| Detroit | ATS CPAs / Michigan.gov | atscpas.com; michigan.gov/taxes |
| Cleveland | CCA Ohio | ccaohio.gov/tax-rates |
| Columbus | City of Columbus | columbus.gov; liveunitedcentralohio.org |
| Cincinnati | City of Cincinnati | cincinnati-oh.gov/finance |
| Baltimore | MD Comptroller | marylandcomptroller.gov (tax alert) |
| Wilmington | City of Wilmington | wilmdebudget.org (FY25 tax rates) |
| Louisville | Louisville Metro | louisvilleky.gov (OL-3 form) |
| Kansas City | City of KC | kcmo.gov/earnings-tax |
| St. Louis | City of St. Louis | stlouis-mo.gov |
| Newark | SAX Advisory / Newark.gov | saxadvisorygroup.com; newarknj.gov |
