"""Source-reviewed 2026 resident policies for the single/age-40 local baseline.

City region id (e.g. "US-NY-NYC") -> policy(tax_input, rules, calculator)
returning a LocalTaxResult. Rules load from rules/locals/2026/<stem>.yaml.
A policy here stays private until coverage.py lists the city's evidence.

Rates, bases and credit parameters live in the YAML (``policy_2025`` is the
loader's historical key name for policy parameters; values there are 2026).
Sources per city are recorded in each YAML ``references`` block:
NYC/Yonkers: IT-2105-I (2026) NYC schedule, school credits, Yonkers 16.75%.
Philadelphia: phila.gov tax-rate history (Wage Tax 3.74% to 30 Jun, 3.735%
from 1 Jul 2026; SIT 3.735% for 2026). Detroit: Form 5469 (2026) 2.4%, $600.
Ohio cities: ORC 718.01(C)(2) intangible income exempt; CCA/Cincinnati/Columbus
2026 rates. Baltimore City: MD Comptroller 2026 local rates; Tax-General
10-704(d), 10-709(d). Marion County: IN DOR Departmental Notice #1 (2026).
Birmingham: FY2026 city budget book (1% of wages). Louisville: LMRC 2026
regulations (1.25% Metro + 0.20% transit + 0.75% school boards).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal

from tax_estimator.calculation.locals.models import (
    LocalCreditComponent,
    LocalRules,
    LocalTaxComponent,
    LocalTaxInput,
    LocalTaxResult,
)

LocalPolicyFn = Callable[[LocalTaxInput, LocalRules, object], LocalTaxResult]

D = Decimal
ZERO = D(0)
CENT = D("0.01")
TAX_YEAR = 2026

# Rev. Proc. 2025-32: 2026 completed-phaseout AGI, no qualifying children,
# single. Below it an unasserted EIC claim triggers an omission warning.
FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026 = D("19540")
# PA Schedule SP eligibility income table (single, no dependants): the 10%
# forgiveness tier ends at $8,750 (statutory, not indexed).
PA_SP_SINGLE_LIMIT = D("8750")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def nyc_eic_rate(agi: Decimal) -> Decimal:
    """Tax Law 1310(f) / IT-215 NYC EIC rate worksheet (four-place rounding)."""
    for lower, upper, base in ((5000, 7500, ".30"), (15000, 17500, ".25"),
                               (20000, 22500, ".20"), (40000, 42500, ".15")):
        if agi < lower:
            return D(base)
        if agi < upper:
            reduction = ((agi - D(lower - 1)) * D(".00002")).quantize(D(".0001"), rounding=ROUND_HALF_UP)
            return D(base) - reduction
    return D(".10")


def _check_profile(t: LocalTaxInput, r: LocalRules) -> None:
    if not t.baseline_profile_supported:
        raise ValueError("Local 2026 policy requires the supported single, age-40 baseline profile")
    if (t.tax_year != TAX_YEAR or r.tax_year != TAX_YEAR or t.filing_status != "single"
            or t.taxpayer_age_at_year_end != 40 or not t.is_resident
            or t.can_be_claimed_as_dependent or t.num_dependents or t.self_employment_income):
        raise ValueError("Local 2026 policy requires the single, age-40, full-year resident employee profile")
    for name in ("dividends", "qualified_dividends", "net_short_term_gains", "net_long_term_gains"):
        if getattr(t, name) is None:
            raise ValueError(f"Local supported-profile calculation requires {name}")
    if not ZERO <= t.qualified_dividends <= t.dividends:
        raise ValueError("Qualified dividends must be a subset of total dividends")
    if t.local_taxes_paid_elsewhere:
        raise ValueError("Cross-jurisdiction local credits are outside the supported resident/work-city profile")


def _eic_unasserted(t: LocalTaxInput) -> bool:
    return t.federal_earned_income_credit is None and t.wages > 0 and (
        t.total_income <= FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026
    )


def calculate_2026_local(t: LocalTaxInput, r: LocalRules, calculator) -> LocalTaxResult:
    _check_profile(t, r)
    city = r.jurisdiction_id
    if city not in LOCAL_POLICIES_2026:
        raise ValueError(f"No reviewed 2026 local policy for {city}")
    params = r.policy_parameters
    credits: list[LocalCreditComponent] = []
    components: list[LocalTaxComponent] = []
    warnings: list[str] = []
    notes: list[str] = []
    assumptions: list[str] = []
    breakdown = []
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
        first_rate = params["resident_first_half_wage_rate"]
        second_rate = params["resident_second_half_wage_rate"]
        wage_tax = money(first * first_rate + (t.wages - first) * second_rate)
        school_base = t.dividends + short
        school_tax = money(school_base * params["school_income_tax_rate"])
        taxable = t.wages + school_base
        gross = wage_tax + school_tax
        rate = second_rate
        components.extend([
            LocalTaxComponent("PHL-WAGE", "Philadelphia resident Wage Tax", t.wages, wage_tax),
            LocalTaxComponent("PHL-SIT", "Philadelphia School Income Tax", school_base, school_tax),
        ])
        if t.wages:
            assumptions.append(
                f"Philadelphia uses supplied Jan–Jun 2026 wages ${first:,.2f} at {first_rate * 100:.3f}%; "
                f"the balance uses the July 2026 rate {second_rate * 100:.3f}%."
            )
        if t.net_short_term_gains:
            assumptions.append(f"Philadelphia taxes supplied six-month-or-less gains ${short:,.2f}; federal ST status alone is insufficient.")
        if 0 < t.total_income <= PA_SP_SINGLE_LIMIT and t.wages:
            warnings.append("Philadelphia income-based Wage Tax relief is omitted: PA tax-forgiveness approval and a city refund claim have not been established.")
    elif city == "US-MI-DET":
        taxable = max(ZERO, t.total_income - params["personal_exemption"])
        rate = r.get_rate_for_residency(True)
        gross = money(taxable * rate)
        notes.append("Detroit resident wages and investment income, less the $600 city personal exemption.")
    elif city == "US-NY-YNK":
        if t.yonkers_surcharge_base is None:
            raise ValueError("Yonkers requires the instructed New York surcharge-base liability")
        taxable = max(ZERO, t.yonkers_surcharge_base)
        rate = r.resident_surcharge_rate
        if rate is None:
            raise ValueError("Missing Yonkers surcharge rate")
        gross = money(taxable * rate)
        notes.append("Yonkers surcharge (16.75%) uses NY liability after nonrefundable credits, before refundable state credits.")
    elif city == "US-NY-NYC":
        brackets = r.get_brackets_for_status("single")
        _, breakdown, rate = calculator._apply_brackets(taxable, brackets)
        # Tax Law 11-1701 / IT-2105-I state whole-dollar base amounts
        # ($369, $858, $1,813) plus the rate on the excess.
        active = [b for b in brackets if taxable > b.income_from]
        top = max(active, key=lambda b: b.income_from) if active else None
        gross = money(top.base_tax + (taxable - top.income_from) * top.rate) if top else ZERO
        if breakdown:
            # Put the whole-dollar base adjustment in the top row so rows sum to the tax.
            last = breakdown[-1]
            adjustment = gross - sum((b.tax_in_bracket for b in breakdown), ZERO)
            breakdown[-1] = replace(last, tax_in_bracket=last.tax_in_bracket + adjustment)
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
        elif _eic_unasserted(t):
            warnings.append("NYC earned income credit omitted: federal EIC claimant eligibility has not been established.")
        # IT-270 NYC income tax elimination credit requires at least one dependant.
        notes.append("NYC income tax elimination credit (IT-270) does not apply without dependants.")
    else:
        # Ohio cities, Birmingham and Louisville tax wages only; Baltimore City
        # and Marion County use the state base already net of exemptions.
        rate = r.get_rate_for_residency(True)
        gross = money(taxable * rate)

    if city == "US-MD-BAL":
        available_eic = ZERO
        if t.federal_earned_income_credit is not None:
            # Tax-General 10-704(d)(1): federal EIC x 10 x county rate, capped at county tax.
            available_eic = money(t.federal_earned_income_credit * rate * 10)
        elif _eic_unasserted(t):
            warnings.append("Baltimore local earned income credit omitted: federal EIC claimant eligibility has not been established.")
        applied_eic = min(gross, available_eic)
        credits.append(LocalCreditComponent("BAL-EIC", "Baltimore local earned income credit", available_eic, applied_eic, False))
        # Tax-General 10-709: FAGI (no MD modifications in this profile) and
        # earned income not over the HHS guideline available on 1 July 2026.
        guideline = params["poverty_income_guideline"]
        poverty = ZERO
        if t.total_income <= guideline and t.wages <= guideline and t.state_taxable_income > 0:
            if t.federal_earned_income_credit:
                warnings.append(
                    "Baltimore local poverty level credit omitted: eligibility requires the Maryland "
                    "EIC to be less than Maryland tax, which this local estimate cannot confirm."
                )
            else:
                poverty = money(t.wages * rate)
        credits.append(LocalCreditComponent("BAL-POVERTY", "Baltimore local poverty level credit", poverty, min(poverty, gross - applied_eic), False))

    nonref = sum((c.amount_applied for c in credits if not c.is_refundable), ZERO)
    refundable = sum((c.amount_applied for c in credits if c.is_refundable), ZERO)
    net = money(gross - nonref - refundable)
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


LOCAL_POLICIES_2026: dict[str, LocalPolicyFn] = {
    region: calculate_2026_local
    for region in (
        "US-NY-NYC", "US-NY-YNK", "US-PA-PHL", "US-MI-DET",
        "US-OH-CLE", "US-OH-CIN", "US-OH-CMH", "US-MD-BAL",
        "US-IN-IND", "US-AL-BHM", "US-KY-LOU",
    )
}

# City region id -> public-safe reason it is not yet enabled.
LOCAL_PENDING_2026: dict[str, str] = {}
