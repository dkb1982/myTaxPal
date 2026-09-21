"""Source-linked resident policies for the 2025 single/age-40 local baseline.

NYC: IT-201 lines47–54,69,69a; IT-215 NYC rate worksheet.
https://www.tax.ny.gov/forms/current-forms/it/it201i.htm
https://www.tax.ny.gov/forms/current-forms/it/it215i.htm
Philadelphia: 2025 SIT instructions lines1,6,12 and wage rates Jan/July2025.
https://www.phila.gov/media/20260128151226/2025-School-Income-Tax-SIT-instructions.pdf
Maryland: 2025 resident booklet, Worksheets 18B,19B,19C (single household).
https://www.marylandcomptroller.gov/content/dam/mdcomp/tax/instructions/2025/resident-booklet.pdf
Other source/base mappings are retained with local YAML and repair fixtures.
"""

from decimal import Decimal, ROUND_HALF_UP

from tax_estimator.calculation.locals.models import (
    LocalCreditComponent, LocalRules, LocalTaxComponent, LocalTaxInput, LocalTaxResult,
)

D = Decimal
ZERO = D(0)
CENT = D("0.01")
ADVERTISED = {"US-NY-NYC", "US-NY-YNK", "US-PA-PHL", "US-MI-DET",
              "US-OH-CLE", "US-OH-CIN", "US-OH-CMH", "US-MD-BAL",
              "US-IN-IND", "US-AL-BHM", "US-KY-LOU"}


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def nyc_eic_rate(agi: Decimal) -> Decimal:
    """IT-215 NYC EIC rate table and worksheet line4 four-place rounding."""
    for lower, upper, base in ((5000, 7500, ".30"), (15000, 17500, ".25"),
                               (20000, 22500, ".20"), (40000, 42500, ".15")):
        if agi < lower:
            return D(base)
        if agi < upper:
            reduction = ((agi - D(lower - 1)) * D(".00002")).quantize(D(".0001"), rounding=ROUND_HALF_UP)
            return D(base) - reduction
    return D(".10")


def calculate_2025_local(t: LocalTaxInput, r: LocalRules, calculator) -> LocalTaxResult | None:
    if not t.baseline_profile_supported or r.jurisdiction_id not in ADVERTISED:
        return None
    if (t.tax_year != 2025 or r.tax_year != 2025 or t.filing_status != "single"
            or t.taxpayer_age_at_year_end != 40 or not t.is_resident
            or t.can_be_claimed_as_dependent or t.num_dependents or t.self_employment_income):
        raise ValueError("Local 2025 policy requires the single, age-40, full-year resident employee profile")
    for name in ("dividends", "qualified_dividends", "net_short_term_gains", "net_long_term_gains"):
        if getattr(t, name) is None:
            raise ValueError(f"Local supported-profile calculation requires {name}")
    if not ZERO <= t.qualified_dividends <= t.dividends:
        raise ValueError("Qualified dividends must be a subset of total dividends")
    params = r.policy_parameters
    credits = []
    components = []
    warnings = []
    notes = []
    assumptions = []
    breakdown = []
    city = r.jurisdiction_id
    taxable = calculator._get_taxable_income(t, r)
    rate = ZERO

    if city == "US-PA-PHL":
        if t.net_short_term_gains < 0 or t.net_long_term_gains < 0:
            raise ValueError("Philadelphia requires separate six-month net gains; signed federal gain/loss combinations are outside this profile")
        first = t.philly_first_half_wages
        short = t.philly_gains_held_six_months_or_less
        if t.wages > 0 and first is None:
            raise ValueError("Philadelphia requires philly_first_half_wages; annual wages do not establish payment timing")
        if t.net_short_term_gains > 0 and short is None:
            raise ValueError("Philadelphia requires philly_gains_held_six_months_or_less; federal ST gains may have been held longer than six months")
        first = ZERO if first is None else first
        short = ZERO if short is None else short
        if not ZERO <= first <= t.wages or not ZERO <= short <= t.net_short_term_gains:
            raise ValueError("Philadelphia category facts exceed corresponding annual income")
        wage_tax = money(first * params["resident_first_half_wage_rate"] + (t.wages - first) * params["resident_second_half_wage_rate"])
        school_base = t.dividends + short
        school_tax = money(school_base * params["school_income_tax_rate"])
        taxable = t.wages + school_base
        gross = wage_tax + school_tax
        rate = params["resident_second_half_wage_rate"]
        components.extend([
            LocalTaxComponent("PHL-WAGE", "Philadelphia resident Wage Tax", t.wages, wage_tax),
            LocalTaxComponent("PHL-SIT", "Philadelphia School Income Tax", school_base, school_tax),
        ])
        if t.wages:
            assumptions.append(f"Philadelphia uses supplied Jan–Jun wages ${first:,.2f}; the balance uses the July rate.")
        if t.net_short_term_gains:
            assumptions.append(f"Philadelphia taxes supplied six-month-or-less gains ${short:,.2f}; federal ST status alone is insufficient.")
        # PA Schedule SP Table 1: single/no children, partial relief through $8,750.
        if 0 < t.total_income <= D(8750) and t.wages:
            warnings.append("Philadelphia income-based Wage Tax relief is omitted: PA tax-forgiveness approval and a city refund claim have not been established.")
    elif city == "US-MI-DET":
        taxable = max(ZERO, t.total_income - params["personal_exemption"])
        rate = r.get_rate_for_residency(True)
        gross = money(taxable * rate)
        notes.append("Detroit resident wages and investment income, less the $600 personal exemption.")
    elif city == "US-NY-YNK":
        if t.yonkers_surcharge_base is None:
            raise ValueError("Yonkers requires the instructed New York surcharge-base liability")
        taxable = max(ZERO, t.yonkers_surcharge_base)
        rate = r.resident_surcharge_rate
        if rate is None:
            raise ValueError("Missing Yonkers surcharge rate")
        gross = money(taxable * rate)
        notes.append("Yonkers surcharge uses NY liability after applicable nonrefundable credits, before refundable state credits.")
    elif city == "US-NY-NYC":
        gross, breakdown, rate = calculator._apply_brackets(taxable, r.get_brackets_for_status("single"))
        gross = money(gross)
        household = ZERO
        if t.total_income <= params["household_credit_income_limit"]:
            household = params["household_credit"] if t.total_income <= params["household_credit_lower_limit"] else params["household_credit_upper"]
        credits.append(LocalCreditComponent("NYC-HOUSEHOLD", "NYC household credit", household, min(household, gross), False))
        fixed = params["school_fixed_credit"] if t.total_income <= params["school_fixed_income_limit"] else ZERO
        credits.append(LocalCreditComponent("NYC-SCHOOL-FIXED", "NYC school credit (fixed)", fixed, fixed, True))
        reduction = ZERO
        if t.total_income <= params["school_rate_income_limit"] and taxable > 0:
            threshold = params["school_rate_threshold"]
            reduction = taxable * params["school_lower_rate"] if taxable <= threshold else params["school_upper_base_credit"] + (taxable - threshold) * params["school_upper_rate"]
            reduction = money(reduction)
        credits.append(LocalCreditComponent("NYC-SCHOOL-RATE", "NYC school credit (rate reduction)", reduction, reduction, True))
        if t.federal_earned_income_credit is not None:
            if t.state_agi is None:
                raise ValueError("NYC EIC requires New York AGI")
            eic = money(t.federal_earned_income_credit * nyc_eic_rate(t.state_agi))
            credits.append(LocalCreditComponent("NYC-EIC", "NYC earned income credit", eic, eic, True))
        elif t.wages > 0 and t.total_income < D(19104):
            warnings.append("NYC earned income credit omitted: federal EIC claimant eligibility has not been established.")
    else:
        # Corrected state base is already net of its exemption for MD and IN.
        rate = r.get_rate_for_residency(True)
        gross = money(taxable * rate)

    if city == "US-MD-BAL":
        available_eic = ZERO
        if t.federal_earned_income_credit is not None:
            available_eic = money(t.federal_earned_income_credit * rate * 10)
        elif t.wages > 0 and t.total_income < D(19104):
            warnings.append("Baltimore local earned income credit omitted: federal EIC claimant eligibility has not been established.")
        applied_eic = min(gross, available_eic)
        credits.append(LocalCreditComponent("BAL-EIC", "Baltimore local earned income credit", available_eic, applied_eic, False))
        # In this profile Maryland has no additions: 18B line1 is federal AGI.
        poverty = money(t.wages * rate) if max(t.wages, t.total_income) < D(15650) else ZERO
        credits.append(LocalCreditComponent("BAL-POVERTY", "Baltimore local poverty level credit", poverty, min(poverty, gross - applied_eic), False))

    nonref = sum((c.amount_applied for c in credits if not c.is_refundable), ZERO)
    refundable = sum((c.amount_applied for c in credits if c.is_refundable), ZERO)
    other_credit = ZERO
    if t.local_taxes_paid_elsewhere:
        raise ValueError("Cross-jurisdiction local credits are outside the supported resident/work-city profile")
    net = money(gross - nonref - refundable - other_credit)
    if not components:
        components.append(LocalTaxComponent(city, r.jurisdiction_name, taxable, gross))
    return LocalTaxResult(
        jurisdiction_id=city, jurisdiction_name=r.jurisdiction_name, parent_state=r.parent_state,
        tax_year=t.tax_year, filing_status=t.filing_status, has_income_tax=r.has_income_tax,
        tax_type=r.tax_type, taxable_income=taxable, rate_applied=rate,
        tax_before_credits=gross, total_tax=net, net_tax=net,
        nonrefundable_credits=nonref, refundable_credits=refundable,
        credits=credits, tax_components=components, bracket_breakdown=breakdown,
        effective_rate=(net / t.total_income).quantize(D(".0001")) if t.total_income > 0 else ZERO,
        marginal_rate=rate, notes=notes, warnings=warnings, assumptions=assumptions,
    )
