"""Source-reviewed 2026 state policies, group 5 (NC, ND, OH, OK, OR, PA, RI).

See policies_2026_common for the supported profile (single, age 40, no
dependants, full-year resident employee, standard deduction, wages plus
dividends and direct capital gains). Each policy cites its primary sources in
rules/states/2026/<st>.yaml ``references``; year-specific constants that are
not plain YAML brackets/deductions live here with the statute or publication
that fixes them.

Ohio and Pennsylvania results feed city income taxes: as in 2025, Ohio's state
AGI is federal AGI and taxable income is AGI less the personal exemption, and
Pennsylvania's starting income is the sum of its taxable income classes.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal

from tax_estimator.calculation.states.policies_2026_common import (
    ZERO,
    PolicyFn,
    StateCreditComponent,
    StatePolicyComputation,
    StateRules,
    StateTaxInput,
    calculate_rate_schedule,
    component,
    credit,
    federal_eic_credit,
    flat_policy,
    irc_net_capital_gain,
    require_policy_inputs,
    round_dollar,
    schedule_policy,
)

D = Decimal

# Rev. Proc. 2025-32 sec. 4.06: 2026 federal EIC, no qualifying child, single
# filer, completed-phaseout AGI. Above it no state EIC warning is needed.
FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026 = D("19540")


def _state_eic(
    t: StateTaxInput,
    credit_id: str,
    name: str,
    pct: Decimal,
    liability: Decimal,
    *,
    refundable: bool,
) -> tuple[tuple[StateCreditComponent, ...], tuple[str, ...]]:
    """Percentage-of-federal EIC, applied only when eligibility is asserted."""
    return federal_eic_credit(
        t, credit_id, name, pct, liability,
        refundable=refundable, childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )


# ---------------------------------------------------------------------------
# North Carolina
# ---------------------------------------------------------------------------

def _nc(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    """G.S. 105-153.7 3.99% for 2026 (S.L. 2023-134) and G.S. 105-153.5 $12,750."""
    return flat_policy(
        t, r,
        notes=(
            "North Carolina 2026: flat 3.99% of federal AGI less the $12,750 standard "
            "deduction (NCDOR NC-30 for 2026); dividends and capital gains are taxed as "
            "ordinary income. Fixed cuts under S.L. 2026-41 begin in 2027.",
        ),
    )


# ---------------------------------------------------------------------------
# North Dakota
# ---------------------------------------------------------------------------

# N.D.C.C. 57-38-30.3(2)(d): 40% of net capital gain and qualified dividends.
_ND_EXCLUSION_RATE = D(".40")


def _nd(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    require_policy_inputs(t, "qualified_dividends", "net_short_term_gains", "net_long_term_gains")
    exclusion = (
        max(ZERO, t.qualified_dividends or ZERO)
        + irc_net_capital_gain(t.net_short_term_gains or ZERO, t.net_long_term_gains or ZERO)
    ) * _ND_EXCLUSION_RATE
    subtractions = (
        (component("ND-QD-LTCG", "40% qualified dividend and net capital gain exclusion",
                   exclusion),)
        if exclusion else ()
    )
    return schedule_policy(
        t, r,
        starting_income=t.federal_taxable_income,
        subtractions=subtractions,
        deduction=ZERO,
        notes=(
            "North Dakota 2026: ND-1 starts from federal taxable income, excludes 40% of "
            "qualified dividends and net capital gain, and applies the 2026 schedule "
            "(0% to $49,575, 1.95% to $250,400, 2.5% above; Form ND-1ES 2026).",
        ),
    )


# ---------------------------------------------------------------------------
# Ohio
# ---------------------------------------------------------------------------

# R.C. 5747.025 tiers; H.B. 96 Section 757.120(A) suspends indexing for 2025 and
# 2026, so the 2025 amounts apply. No exemption at MAGI of $500,000 or more (2026).
_OH_EXEMPTION_TIERS = ((D("40000"), D("2400")), (D("80000"), D("2150")))
_OH_EXEMPTION_TOP = D("1900")
_OH_EXEMPTION_MAGI_LIMIT_2026 = D("500000")
# R.C. 5747.022: $20 per exemption when MAGI less exemptions is under $30,000.
_OH_EXEMPTION_CREDIT = D("20")
_OH_EXEMPTION_CREDIT_LIMIT = D("30000")
# R.C. 5747.71: nonrefundable credit of 30% of the federal EIC.
_OH_EIC_RATE = D(".30")


def _oh_personal_exemption(magi: Decimal) -> Decimal:
    if magi >= _OH_EXEMPTION_MAGI_LIMIT_2026:
        return ZERO
    for limit, amount in _OH_EXEMPTION_TIERS:
        if magi <= limit:
            return amount
    return _OH_EXEMPTION_TOP


def _oh(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    agi = t.federal_agi
    exemption = _oh_personal_exemption(agi)
    taxable = max(ZERO, agi - exemption)
    schedule = calculate_rate_schedule(
        taxable, r.get_brackets_for_status(t.filing_status), use_published_base_tax=True,
    )
    # IT 1040 nonbusiness income tax is reported in whole dollars.
    tax = round_dollar(schedule.tax)
    credits: tuple[StateCreditComponent, ...] = ()
    remaining = tax
    if agi - exemption < _OH_EXEMPTION_CREDIT_LIMIT:
        exemption_credit = credit(
            "OH-EXEMPTION", "Ohio exemption credit", _OH_EXEMPTION_CREDIT, remaining,
        )
        credits += (exemption_credit,)
        remaining -= exemption_credit.amount_applied
    eic, warnings = _state_eic(
        t, "OH-EITC", "Ohio earned income credit", _OH_EIC_RATE, remaining, refundable=False,
    )
    return StatePolicyComputation(
        starting_income=agi,
        state_agi=agi,
        deduction_type="none",
        personal_exemption=exemption,
        taxable_income=taxable,
        ordinary_taxable_income=taxable,
        ordinary_tax=tax,
        tax_before_credits=tax,
        credits=credits + eic,
        marginal_rate=schedule.marginal_rate,
        bracket_breakdown=schedule.bracket_breakdown,
        notes=(
            "Ohio 2026: no tax when Ohio AGI less exemptions is $26,050 or less, otherwise "
            "$332 plus 2.75% of the excess (R.C. 5747.02(A)(3)(c), H.B. 96); MAGI-tiered "
            "personal exemption (none at $500,000 or more); tax in whole dollars.",
        ),
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Oklahoma
# ---------------------------------------------------------------------------

# 68 O.S. 2358: $1,000 personal exemption (standard deduction $6,350 in YAML).
_OK_PERSONAL_EXEMPTION = D("1000")
_OK_EIC_RATE = D(".05")
# 68 O.S. 2357.43 ties the Oklahoma EIC to the federal credit as it existed for
# tax year 2020: childless maximum $538, phase-out from $8,790 at 7.65%,
# investment income limit $3,650; fully phased out at $15,820 AGI.
_OK_2020_EIC_MAX = D("538")
_OK_2020_EIC_RATE = D(".0765")
_OK_2020_EIC_PHASEOUT = D("8790")
_OK_2020_INVESTMENT_LIMIT = D("3650")
_OK_2020_EIC_AGI_LIMIT = D("15820")


def _ok_2020_childless_eic(t: StateTaxInput) -> Decimal:
    """2020-law childless federal EIC amount used only by Oklahoma."""
    if t.federal_eitc_eligibility_asserted is not True:
        return ZERO
    investment_income = (
        max(ZERO, t.interest)
        + max(ZERO, t.dividends)
        + max(ZERO, (t.net_short_term_gains or ZERO) + (t.net_long_term_gains or ZERO))
    )
    if investment_income > _OK_2020_INVESTMENT_LIMIT:
        return ZERO
    earned = max(ZERO, t.wages)
    preliminary = min(_OK_2020_EIC_MAX, earned * _OK_2020_EIC_RATE)
    reduction = max(ZERO, max(earned, t.federal_agi) - _OK_2020_EIC_PHASEOUT) * _OK_2020_EIC_RATE
    return round_dollar(max(ZERO, preliminary - reduction))


def _ok(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    require_policy_inputs(t, "net_short_term_gains", "net_long_term_gains")
    base = schedule_policy(
        t, r,
        exemption=_OK_PERSONAL_EXEMPTION,
        notes=(
            "Oklahoma 2026: HB 2764 schedule (0% to $3,750, 2.5%, 3.5%, then 4.5% above "
            "$7,200) on federal AGI less the $6,350 standard deduction and $1,000 exemption; "
            "the exact schedule is used where Form 511 would use its $50-row tax table.",
            "Oklahoma EIC uses 5% of the 2020-law federal childless EIC, not the 2026 "
            "federal result.",
        ),
    )
    historical = _ok_2020_childless_eic(t)
    if historical:
        base.credits = (
            credit("OK-EITC", "Oklahoma earned income credit", historical * _OK_EIC_RATE,
                   base.tax_before_credits, refundable=True),
        )
    if (
        t.federal_eitc_eligibility_asserted is None
        and t.federal_earned_income_credit is None
        and t.federal_agi <= _OK_2020_EIC_AGI_LIMIT
    ):
        base.warnings = (
            "Oklahoma earned income credit omitted because federal EITC eligibility was "
            "not affirmatively asserted.",
        )
    return base


# ---------------------------------------------------------------------------
# Oregon
# ---------------------------------------------------------------------------

# ORS 316.695(3)(b)-(c),(f): 2026 indexed federal tax subtraction limits by AGI
# (single). Base $5,500/$4,400/$3,300/$2,200/$1,100 x CPI-U(Sep 2024-Aug 2025,
# 319.205) / CPI-U(Sep 2005-Aug 2006, 200.292), increase rounded down to $50.
_OR_FEDERAL_TAX_LIMITS_2026 = (
    (D("125000"), D("8750")),
    (D("130000"), D("7000")),
    (D("135000"), D("5250")),
    (D("140000"), D("3500")),
    (D("145000"), D("1750")),
)
# ORS 316.085(3),(5): $90 x 319.205 / 109.117 (H1 1986) = $263.28 -> $263;
# none when federal AGI exceeds $100,000 (single).
_OR_EXEMPTION_CREDIT_2026 = D("263")
_OR_EXEMPTION_CREDIT_AGI_LIMIT = D("100000")
_OR_EIC_RATE = D(".09")


def _or_federal_tax_limit(agi: Decimal) -> Decimal:
    for limit, amount in _OR_FEDERAL_TAX_LIMITS_2026:
        if agi < limit:
            return amount
    return ZERO


def _or(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    require_policy_inputs(t, "federal_income_tax_after_nonrefundable_credits")
    federal_tax = min(
        max(ZERO, t.federal_income_tax_after_nonrefundable_credits or ZERO),
        _or_federal_tax_limit(t.federal_agi),
    )
    subtractions = (
        (component("OR-FEDERAL-TAX", "Oregon federal income tax subtraction", federal_tax),)
        if federal_tax else ()
    )
    base = schedule_policy(
        t, r,
        subtractions=subtractions,
        notes=(
            "Oregon 2026: federal AGI less the federal tax subtraction (limited to $8,750 "
            "and phased out from $125,000 to $145,000 AGI) and the $2,910 standard "
            "deduction, on the 2026 Chart S schedule; the exact schedule is used where "
            "OR-40 would use its tax table. No kicker credit applies to 2026.",
        ),
        warnings=(
            "OR 2026 standard deduction $2,910, personal exemption credit $263 and federal "
            "tax subtraction limits computed from ORS 316.695(1)(c), 316.085(3) and "
            "316.695(3)(f) with BLS CPI-U (they match DOR withholding formulas 150-206-436 "
            "Rev. 12-31-25); Oregon DOR has not yet published the 2026 OR-40 "
            "instructions (provisional).",
        ),
    )
    credits: tuple[StateCreditComponent, ...] = ()
    if t.federal_agi <= _OR_EXEMPTION_CREDIT_AGI_LIMIT:
        credits += (
            credit("OR-EXEMPTION", "Oregon personal exemption credit",
                   _OR_EXEMPTION_CREDIT_2026, base.tax_before_credits),
        )
    eic, eic_warnings = _state_eic(
        t, "OR-EIC", "Oregon earned income credit", _OR_EIC_RATE, ZERO, refundable=True,
    )
    base.credits = credits + eic
    base.warnings = base.warnings + eic_warnings
    return base


# ---------------------------------------------------------------------------
# Pennsylvania
# ---------------------------------------------------------------------------

# Schedule SP (unmarried, no dependants): 100% forgiveness to $6,500 of
# eligibility income, then 10 points less per $250 through $8,750.
_PA_FORGIVENESS_FULL = D("6500")
_PA_FORGIVENESS_STEP = D("250")
_PA_FORGIVENESS_LAST = D("8750")
_PA_WPTC_RATE = D(".10")


def _pa_forgiveness_percentage(income: Decimal) -> Decimal:
    if income <= _PA_FORGIVENESS_FULL:
        return D(1)
    if income > _PA_FORGIVENESS_LAST:
        return ZERO
    steps = ((income - _PA_FORGIVENESS_FULL) / _PA_FORGIVENESS_STEP).to_integral_value(
        rounding=ROUND_CEILING
    )
    return max(ZERO, (D(10) - steps) / D(10))


def _pa(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    require_policy_inputs(t, "net_short_term_gains", "net_long_term_gains")
    net_gains = max(ZERO, (t.net_short_term_gains or ZERO) + (t.net_long_term_gains or ZERO))
    income = t.wages + t.interest + t.dividends + net_gains
    base = flat_policy(
        t, r,
        starting_income=income,
        deduction=ZERO,
        notes=(
            "Pennsylvania 2026: 3.07% of separately classified compensation, interest, "
            "dividends and net gains; a net loss in one class cannot offset another; no "
            "standard deduction or exemption.",
        ),
    )
    credits: tuple[StateCreditComponent, ...] = ()
    percentage = _pa_forgiveness_percentage(income)
    if percentage and base.tax_before_credits:
        credits += (
            credit("PA-TAX-FORGIVENESS", "Pennsylvania Tax Forgiveness",
                   base.tax_before_credits * percentage, base.tax_before_credits),
        )
    wptc, warnings = _state_eic(
        t, "PA-WPTC", "Working Pennsylvanians Tax Credit", _PA_WPTC_RATE, ZERO,
        refundable=True,
    )
    base.credits = credits + wptc
    base.warnings = warnings
    return base


# ---------------------------------------------------------------------------
# Rhode Island
# ---------------------------------------------------------------------------

# ADV 2025-22: 2026 standard deduction and exemption phase out in four 20% steps
# of $7,450 from $261,000 to $290,800 of modified federal AGI.
_RI_PHASEOUT_START = D("261000")
_RI_PHASEOUT_END = D("290800")
_RI_PHASEOUT_STEP = D("7450")
_RI_EIC_RATE = D(".16")


def _ri_phaseout_amount(full_amount: Decimal, agi: Decimal) -> Decimal:
    if agi <= _RI_PHASEOUT_START:
        return full_amount
    if agi > _RI_PHASEOUT_END:
        return ZERO
    steps = ((agi - _RI_PHASEOUT_START) / _RI_PHASEOUT_STEP).to_integral_value(
        rounding=ROUND_CEILING
    )
    return max(ZERO, full_amount * (D(5) - steps) / D(5))


def _ri(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    deduction = _ri_phaseout_amount(r.get_standard_deduction(t.filing_status), t.federal_agi)
    exemption = _ri_phaseout_amount(r.exemption.personal_amount, t.federal_agi)
    base = schedule_policy(
        t, r,
        deduction=deduction,
        exemption=exemption,
        notes=(
            "Rhode Island 2026: ADV 2025-22 schedule, $11,200 standard deduction and $5,250 "
            "exemption, both phased out between $261,000 and $290,800 modified AGI; the "
            "surtax on income over $1 million starts in 2027.",
        ),
    )
    base.credits, base.warnings = _state_eic(
        t, "RI-EIC", "Rhode Island earned income credit", _RI_EIC_RATE, ZERO, refundable=True,
    )
    return base


POLICIES: dict[str, PolicyFn] = {
    "NC": _nc,
    "ND": _nd,
    "OH": _oh,
    "OK": _ok,
    "OR": _or,
    "PA": _pa,
    "RI": _ri,
}

PENDING: dict[str, str] = {}
