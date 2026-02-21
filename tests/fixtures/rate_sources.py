"""
Documented rate sources for all 12 country calculators.

Every rate constant used in the calculators is listed here with its official
source URL and the tax year it applies to. This file serves as the audit trail
for rate verification.

Last verified: 2025-02 (rates corrected in this QA pass)
"""

RATE_SOURCES = {
    # =========================================================================
    # GB — United Kingdom (2024-25 tax year)
    # =========================================================================
    "GB": {
        "tax_year": "2024-25",
        "income_tax_england": {
            "source": "https://www.gov.uk/income-tax-rates",
            "rates": "PA £12,570 | 20% to £50,270 | 40% to £125,140 | 45% above",
        },
        "income_tax_scotland": {
            "source": "https://www.gov.uk/scottish-income-tax/2024-to-2025-tax-year",
            "rates": "PA £12,570 | 19% to £14,876 | 20% to £26,561 | 21% to £43,662 | 42% to £75,000 | 45% to £125,140 | 48% above",
        },
        "national_insurance": {
            "source": "https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2024-to-2025",
            "rates": "8% on £12,570-£50,270 | 2% above £50,270",
        },
        "personal_allowance_taper": {
            "source": "https://www.gov.uk/income-tax-rates",
            "rates": "£1 reduction per £2 over £100,000",
        },
        "capital_gains_tax": {
            "source": "https://www.gov.uk/guidance/capital-gains-tax-rates-and-allowances",
            "rates": "AEA £3,000 | 18% basic | 24% higher (from 30 Oct 2024)",
        },
        "student_loans": {
            "source": "https://www.gov.uk/government/publications/sl3-student-loan-deduction-tables/2024-to-2025-student-and-postgraduate-loan-deduction-tables",
            "rates": "Plan 1: £24,990 @ 9% | Plan 2: £27,295 @ 9% | Plan 4: £31,395 @ 9% | Plan 5: £25,000 @ 9% | PG: £21,000 @ 6%",
        },
    },

    # =========================================================================
    # DE — Germany (2025 tax year)
    # =========================================================================
    "DE": {
        "tax_year": "2025",
        "income_tax": {
            "source": "https://www.bundesfinanzministerium.de",
            "rates": "Grundfreibetrag €12,084 | 14% zone to €17,005 | 24% zone to €66,760 | 42% to €277,825 | 45% above",
        },
        "solidarity_surcharge": {
            "source": "https://www.german-tax-consultants.com/german-taxes/solidarity-surcharge-solidaritaetszuschlag.html",
            "rates": "5.5% of income tax (threshold €18,950)",
        },
        "social_insurance": {
            "source": "https://www.grantthornton.de/en/insights/2025/draft-bill-on-the-social-insurance-calculation-values-sv-regulation-2026/",
            "rates": "Pension 9.3% (ceiling €96,600) | Health 7.3%+0.88% addon (ceiling €66,150) | Unemployment 1.3% | Care 1.7%+0.6% childless",
        },
        "werbungskosten": {
            "source": "https://germantaxes.de/tax-tips/income-related-expenses-lump-sum/",
            "rates": "€1,230 flat deduction",
        },
    },

    # =========================================================================
    # FR — France (2025 income, filed 2026)
    # =========================================================================
    "FR": {
        "tax_year": "2025",
        "income_tax": {
            "source": "https://www.service-public.fr/particuliers/actualites/A18045",
            "rates": "0% to €11,294 | 11% to €28,797 | 30% to €82,341 | 41% to €177,106 | 45% above (per part)",
        },
        "csg_crds": {
            "source": "https://www.cleiss.fr/docs/regimes/regime_france/an_a2.html",
            "rates": "CSG 9.2% | CRDS 0.5% | CSG deductible portion 6.8%",
        },
        "standard_deduction": {
            "source": "https://taxsummaries.pwc.com/france/individual/deductions",
            "rates": "10% of employment income (min €504, max €14,426)",
        },
        "quotient_familial": {
            "source": "https://www.connexionfrance.com/practical/explained-the-parts-system-for-tax-in-france/172585",
            "rates": "Cap per half-part: €1,791",
        },
    },

    # =========================================================================
    # SG — Singapore (YA 2025)
    # =========================================================================
    "SG": {
        "tax_year": "YA 2025",
        "income_tax": {
            "source": "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/tax-residency-and-tax-rates/individual-income-tax-rates",
            "rates": "0% to 20k | 2% to 30k | 3.5% to 40k | 7% to 80k | 11.5% to 120k | 15% to 160k | 18% to 200k | 19% to 240k | 19.5% to 280k | 20% to 320k | 22% to 500k | 23% to 1M | 24% above",
        },
        "cpf": {
            "source": "https://www.cpf.gov.sg/employer/infohub/news/cpf-related-announcements/new-contribution-rates",
            "rates": "Under 55: 20% (monthly cap SGD 6,800) | 55-60: 15% | 60-65: 9.5% | 65-70: 7% | 70+: 5%",
        },
    },

    # =========================================================================
    # HK — Hong Kong (2024-25 year of assessment)
    # =========================================================================
    "HK": {
        "tax_year": "2024-25",
        "salaries_tax": {
            "source": "https://www.gov.hk/en/residents/taxes/taxfiling/taxrates/salariesrates.htm",
            "rates": "2% to 50k | 6% to 100k | 10% to 150k | 14% to 200k | 17% above",
        },
        "standard_rate": {
            "source": "https://www.gov.hk/en/residents/taxes/taxfiling/taxrates/salariesrates.htm",
            "rates": "15% on first HKD 5M | 16% above (two-tier from 2024-25)",
        },
        "allowances": {
            "source": "https://www.gov.hk/en/residents/taxes/salaries/allowances/allowances/allowances.htm",
            "rates": "Basic: HKD 132,000 | Married: HKD 264,000",
        },
        "mpf": {
            "source": "https://www.mpfa.org.hk/en/mpf-system/mandatory-contributions/employees",
            "rates": "5% (max HKD 1,500/month, min income HKD 7,100/month)",
        },
    },

    # =========================================================================
    # AU — Australia (2024-25 financial year)
    # =========================================================================
    "AU": {
        "tax_year": "2024-25",
        "income_tax": {
            "source": "https://www.ato.gov.au/tax-rates-and-codes/tax-rates-australian-residents",
            "rates": "0% to $18,200 | 16% to $45,000 | 30% to $135,000 | 37% to $190,000 | 45% above",
        },
        "medicare_levy": {
            "source": "https://www.ato.gov.au/individuals-and-families/medicare-and-private-health-insurance/medicare-levy",
            "rates": "2% (threshold ~$26,000 for singles)",
        },
        "help": {
            "source": "https://www.ato.gov.au/tax-rates-and-codes/study-and-training-support-loans-rates-and-repayment-thresholds",
            "rates": "18-tier threshold system (2024-25 values)",
        },
    },

    # =========================================================================
    # CA — Canada (2025 tax year)
    # =========================================================================
    "CA": {
        "tax_year": "2025",
        "federal_income_tax": {
            "source": "https://www.canada.ca/en/revenue-agency/services/tax/individuals/frequently-asked-questions-individuals/canadian-income-tax-rates-individuals-current-previous-years.html",
            "rates": "15% to $57,375 | 20.5% to $114,750 | 26% to $158,468 | 29% to $221,708 | 33% above",
        },
        "federal_bpa": {
            "source": "https://www.canada.ca/en/revenue-agency",
            "rates": "BPA $16,129",
        },
        "ontario_provincial": {
            "source": "https://www.taxtips.ca/taxrates/on.htm",
            "rates": "5.05% to $52,886 | 9.15% to $105,775 | 11.16% to $150,000 | 12.16% to $220,000 | 13.16% above",
        },
        "cpp": {
            "source": "https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/payroll/payroll-deductions-contributions/canada-pension-plan-cpp/cpp-contribution-rates-maximums-exemptions.html",
            "rates": "5.95% (max earnings $71,300, BEX $3,500) | CPP2 4% (max $81,200)",
        },
        "ei": {
            "source": "https://www.canada.ca/en/employment-social-development/programs/ei/ei-list/reports/premium/rates2026.html",
            "rates": "1.64% (max earnings $65,700)",
        },
    },

    # =========================================================================
    # JP — Japan (2025 tax year)
    # =========================================================================
    "JP": {
        "tax_year": "2025",
        "income_tax": {
            "source": "https://taxsummaries.pwc.com/japan/individual/taxes-on-personal-income",
            "rates": "5% to ¥1.95M | 10% to ¥3.3M | 20% to ¥6.95M | 23% to ¥9M | 33% to ¥18M | 40% to ¥40M | 45% above",
        },
        "reconstruction_tax": {
            "source": "https://taxsummaries.pwc.com/japan/individual/taxes-on-personal-income",
            "rates": "2.1% of income tax (until 2037)",
        },
        "resident_tax": {
            "source": "https://mailmate.jp/blog/understand-residence-tax-in-japan",
            "rates": "10% (6% prefectural + 4% municipal) + ¥5,000 per-capita (waived below ~¥350k income)",
        },
        "social_insurance": {
            "source": "https://slasify.com/en/blog/employer-contribution-in-japan",
            "rates": "Health ~5% | Pension 9.15% | Employment 0.6% | LTC 0.9% (age 40-64)",
        },
        "deductions": {
            "source": "https://taxsummaries.pwc.com/japan/individual/deductions",
            "rates": "Employment deduction min ¥550,000 max ¥1,950,000 | Basic deduction ¥480,000",
        },
    },

    # =========================================================================
    # IT — Italy (2025 tax year)
    # =========================================================================
    "IT": {
        "tax_year": "2025",
        "irpef": {
            "source": "https://www.agenziaentrate.gov.it/portale/web/english/personal-income-tax-rates-and-calculation",
            "rates": "23% to €28,000 | 33% to €50,000 | 43% above",
        },
        "inps": {
            "source": "https://www.inps.it",
            "rates": "9.19% employee (ceiling €113,520)",
        },
        "regional_municipal": {
            "source": "https://taxsummaries.pwc.com/italy/individual/taxes-on-personal-income",
            "rates": "Regional ~1.73% | Municipal ~0.8% (varies by location)",
        },
    },

    # =========================================================================
    # ES — Spain (2025 tax year)
    # =========================================================================
    "ES": {
        "tax_year": "2025",
        "irpf": {
            "source": "https://www.agenciatributaria.es",
            "rates": "State: 9.5% to €12,450 | 12% to €20,200 | 15% to €35,200 | 18.5% to €60,000 | 22.5% to €300,000 | 24.5% above (+ matching regional rates = ~2x combined)",
        },
        "social_security": {
            "source": "https://taxsummaries.pwc.com/spain/individual/other-taxes",
            "rates": "Common 4.7% | Unemployment 1.55% | Training 0.1% (monthly ceiling €4,720.50)",
        },
    },

    # =========================================================================
    # PT — Portugal (2025 tax year)
    # =========================================================================
    "PT": {
        "tax_year": "2025",
        "irs": {
            "source": "https://taxsummaries.pwc.com/portugal/individual/taxes-on-personal-income",
            "rates": "13.25% to €7,703 | 18% to €11,623 | 23% to €16,472 | 26% to €21,321 | 32.75% to €27,146 | 37% to €39,791 | 43.5% to €51,997 | 45% to €81,199 | 48% above",
        },
        "social_security": {
            "source": "https://www.remofirst.com/post/social-security-in-portugal",
            "rates": "11% employee",
        },
        "solidarity_surcharge": {
            "source": "https://taxsummaries.pwc.com/portugal/individual/taxes-on-personal-income",
            "rates": "2.5% on €80k-€250k | 5% above €250k",
        },
    },

    # =========================================================================
    # AE — United Arab Emirates
    # =========================================================================
    "AE": {
        "tax_year": "N/A",
        "personal_income_tax": {
            "source": "https://taxsummaries.pwc.com/united-arab-emirates/individual/taxes-on-personal-income",
            "rates": "0% — no personal income tax",
        },
    },
}
