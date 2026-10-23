"""Source-reviewed 2026 state policies, group 1 (AL, AZ, AR, CA, CO, CT, DE).

See policies_2026_common for the supported profile. Evidence for every
constant below is recorded in rules/states/2026/<st>.yaml ``references``.
Like the 2025 baseline, graduated taxes use the official rate schedules
(not the $50/$100 tax-table midpoints).
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from tax_estimator.calculation.states.policies_2026_common import (
    ZERO,
    PolicyFn,
    StateCreditComponent,
    StatePolicyComputation,
    StatePolicyError,
    StateRules,
    StateTaxInput,
    calculate_rate_schedule,
    component,
    credit,
    federal_eic_credit,
    flat_policy,
    require_policy_inputs,
    schedule_policy,
)

D = Decimal

# Rev. Proc. 2025-32: 2026 federal no-qualifying-child EIC completed phaseout (single).
FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026 = D("19540")


# --- Alabama ---------------------------------------------------------------


def _al_single_standard_deduction(agi: Decimal) -> Decimal:
    """Ala. Code 40-18-15(b) chart as published for 2026 (ADOR withholding booklet 01/26).

    $3,000 through $25,999; $25 less per $500 band from $26,000; $2,500 from $35,500.
    """
    if agi < D("26000"):
        return D("3000")
    if agi >= D("35500"):
        return D("2500")
    band = ((agi - D("26000")) / D("500")).to_integral_value(rounding=ROUND_FLOOR)
    return D("2975") - band * D("25")


def _al(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(
        tax_input, "federal_income_tax_after_nonrefundable_credits",
        "federal_niit", "federal_refundable_credits",
    )
    # Form 40ES 2026 line 3 / Form 40 federal tax deduction worksheet: Form 1040
    # income tax plus NIIT, less applicable refundable credits (only EIC here).
    federal_tax = max(
        ZERO,
        (tax_input.federal_income_tax_after_nonrefundable_credits or ZERO)
        + (tax_input.federal_niit or ZERO)
        - (tax_input.federal_refundable_credits or ZERO),
    )
    subtraction = component(
        "AL-FEDERAL-TAX", "Federal income-tax liability deduction", federal_tax
    )
    return schedule_policy(
        tax_input,
        rules,
        subtractions=(subtraction,),
        deduction=_al_single_standard_deduction(tax_input.federal_agi),
        exemption=D("1500"),
        notes=(
            "Alabama 2026 federal income-tax deduction (including NIIT, less refundable "
            "credits), sliding single standard deduction and $1,500 personal exemption "
            "applied.",
        ),
    )


# --- Arizona ---------------------------------------------------------------


def _az(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    if (tax_input.net_short_term_gains or ZERO) < 0 or (tax_input.net_long_term_gains or ZERO) < 0:
        raise StatePolicyError("Arizona signed capital-loss combinations are not source-supported")
    long_term = tax_input.net_long_term_gains or ZERO
    eligible = tax_input.az_post_2011_eligible_long_term_gains
    if long_term > 0 and eligible is None:
        raise StatePolicyError(
            "Arizona requires az_post_2011_eligible_long_term_gains when net "
            "long-term gains are positive"
        )
    eligible = ZERO if eligible is None else eligible
    if eligible < 0 or eligible > max(ZERO, long_term):
        raise StatePolicyError(
            "Arizona eligible post-2011 gain must be between zero and net long-term gain"
        )
    # A.R.S. 43-1022(22)(c): 25% of net LTCG from assets acquired after 2011.
    amount = eligible * D(".25")
    subtractions = (
        (component("AZ-POST-2011-LTCG", "25% post-2011 net LTCG subtraction", amount),)
        if amount
        else ()
    )
    warnings = (
        "AZ 2026 standard deduction computed from A.R.S. 43-1041(A),(H) (the $15,750 "
        "base adjusted as the federal basic standard deduction is under IRC 63, "
        "Rev. Proc. 2025-32); ADOR has not yet published it (provisional).",
    )
    if tax_input.federal_agi <= D("12500"):
        warnings += (
            "Arizona 2026 increased excise tax credit (A.R.S. 43-1072.01, up to $25, "
            "refundable) is not modelled and may reduce this result.",
        )
    return flat_policy(
        tax_input,
        rules,
        subtractions=subtractions,
        notes=("Arizona 2026 flat 2.5% rate applied to Arizona taxable income.",),
        warnings=warnings,
    )


# --- California ------------------------------------------------------------

CA_EXEMPTION_CREDIT_2026 = D("158")
# R&TC 17054.1 AGI threshold: 2025 $252,203 x 1.034 (CCPI June 2025-June 2026).
CA_EXEMPTION_PHASEOUT_THRESHOLD_2026 = D("260778")
# CalEITC is not computed for 2026: FTB 3514 2026 table is unpublished. The
# 2025 $32,900 income ceiling x 1.034 bounds where a warning is useful.
CA_EITC_WARNING_CEILING_2026 = D("34019")


def _ca(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    deduction = rules.get_standard_deduction(tax_input.filing_status)
    taxable = max(ZERO, tax_input.federal_agi - deduction)
    schedule = calculate_rate_schedule(
        taxable, rules.get_brackets_for_status(tax_input.filing_status), use_published_base_tax=True
    )
    excess = max(ZERO, tax_input.federal_agi - CA_EXEMPTION_PHASEOUT_THRESHOLD_2026)
    reduction = (excess / D("2500")).to_integral_value(rounding=ROUND_CEILING) * D("6")
    exemption = credit(
        "CA-PERSONAL", "Personal exemption credit",
        max(ZERO, CA_EXEMPTION_CREDIT_2026 - reduction), schedule.tax,
    )
    # R&TC 17043 Behavioral Health Services Tax: 1% of taxable income over $1m.
    surtax = max(ZERO, taxable - D("1000000")) * D(".01")
    warnings: tuple[str, ...] = ()
    if excess > 0:
        warnings += (
            "CA 2026 exemption-credit AGI phase-out threshold ($260,778) computed from "
            "R&TC 17054.1 and the 3.4% CCPI change; FTB has not yet published it "
            "(provisional).",
        )
    if (
        tax_input.federal_eitc_eligibility_asserted is not False
        and max(tax_input.wages, tax_input.federal_agi) < CA_EITC_WARNING_CEILING_2026
    ):
        warnings += (
            "California CalEITC omitted: FTB has not yet published the 2026 FTB 3514 "
            "credit table.",
        )
    return StatePolicyComputation(
        starting_income=tax_input.federal_agi,
        state_agi=tax_input.federal_agi,
        deduction_type="standard",
        deduction_amount=deduction,
        taxable_income=taxable,
        ordinary_taxable_income=taxable,
        ordinary_tax=schedule.tax,
        tax_before_credits=schedule.tax,
        surtax=surtax,
        credits=(exemption,),
        marginal_rate=schedule.marginal_rate,
        bracket_breakdown=schedule.bracket_breakdown,
        notes=(
            "FTB 2026 Schedule X (Tax News, October 2026) applied; the exemption credit "
            "cannot offset the Behavioral Health Services Tax. Renter's credit is not "
            "modelled.",
        ),
        warnings=warnings,
    )


# --- Connecticut -----------------------------------------------------------


def _ct_single_exemption(agi: Decimal) -> Decimal:
    """2026 CT-1040ES Table A, single column."""
    if agi <= D("30000"):
        return D("15000")
    if agi <= D("44000"):
        steps = ((agi - D("30000")) / D("1000")).to_integral_value(rounding=ROUND_CEILING)
        return D("15000") - steps * D("1000")
    return ZERO


def _ct_single_phaseout_addback(agi: Decimal) -> Decimal:
    """2026 CT-1040ES Table C (2% phase-out add-back), single column."""
    steps = ((agi - D("56500")) / D("5000")).to_integral_value(rounding=ROUND_CEILING)
    return min(D("250"), max(ZERO, steps * D("25")))


def _ct_single_recapture(agi: Decimal) -> Decimal:
    """2026 CT-1040ES Table D, single column."""
    if agi <= D("105000"):
        return ZERO
    if agi <= D("150000"):
        return ((agi - D("105000")) / D("5000")).to_integral_value(
            rounding=ROUND_CEILING
        ) * D("25")
    if agi <= D("200000"):
        return D("250")
    if agi <= D("345000"):
        return D("250") + ((agi - D("200000")) / D("5000")).to_integral_value(
            rounding=ROUND_CEILING
        ) * D("90")
    if agi <= D("500000"):
        return D("2950")
    return min(
        D("3400"),
        D("2950")
        + ((agi - D("500000")) / D("5000")).to_integral_value(rounding=ROUND_CEILING)
        * D("50"),
    )


_CT_SINGLE_CREDIT_BANDS = (
    ("18800", ".75"), ("19300", ".70"), ("19800", ".65"), ("20300", ".60"),
    ("20800", ".55"), ("21300", ".50"), ("21800", ".45"), ("22300", ".40"),
    ("25000", ".35"), ("25500", ".30"), ("26000", ".25"), ("26500", ".20"),
    ("31300", ".15"), ("31800", ".14"), ("32300", ".13"), ("32800", ".12"),
    ("33300", ".11"), ("60000", ".10"), ("60500", ".09"), ("61000", ".08"),
    ("61500", ".07"), ("62000", ".06"), ("62500", ".05"), ("63000", ".04"),
    ("63500", ".03"), ("64000", ".02"), ("64500", ".01"),
)


def _ct_single_personal_credit_rate(agi: Decimal) -> Decimal:
    """2026 CT-1040ES Table E, single column (the first band starts above $15,000;
    at or below that the exemption leaves no taxable income)."""
    for upper, rate in _CT_SINGLE_CREDIT_BANDS:
        if agi <= D(upper):
            return D(rate)
    return ZERO


def _ct(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    agi = tax_input.federal_agi
    exemption = _ct_single_exemption(agi)
    taxable = max(ZERO, agi - exemption)
    initial = calculate_rate_schedule(
        taxable,
        rules.get_brackets_for_status(tax_input.filing_status),
        use_published_base_tax=True,
    )
    addback = _ct_single_phaseout_addback(agi)
    recapture = _ct_single_recapture(agi)
    liability = initial.tax + addback + recapture
    personal = credit(
        "CT-PERSONAL",
        "Connecticut personal tax credit",
        liability * _ct_single_personal_credit_rate(agi),
        liability,
    )
    # CGS 12-704e: refundable credit of 40% of the federal EIC.
    eitc, warnings = federal_eic_credit(
        tax_input,
        "CT-EITC",
        "Connecticut earned income tax credit",
        D(".40"),
        liability,
        refundable=True,
        childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    return StatePolicyComputation(
        starting_income=agi,
        state_agi=agi,
        personal_exemption=exemption,
        taxable_income=taxable,
        ordinary_taxable_income=taxable,
        ordinary_tax=initial.tax,
        other_base_tax=addback,
        tax_before_credits=initial.tax + addback,
        recapture=recapture,
        credits=(personal, *eitc),
        marginal_rate=initial.marginal_rate,
        bracket_breakdown=initial.bracket_breakdown,
        notes=(
            "Connecticut 2026 CT-1040ES Tables A-E personal exemption, initial tax, "
            "2% phase-out add-back, recapture and personal tax credit applied.",
        ),
        warnings=warnings,
    )


# --- Delaware --------------------------------------------------------------


def _de(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    base = schedule_policy(
        tax_input,
        rules,
        notes=(
            "Delaware 2026 rate schedule, $3,250 single standard deduction and $110 "
            "personal credit applied.",
        ),
    )
    personal = credit("DE-PERSONAL", "Personal credit", D("110"), base.tax_before_credits)
    remaining = max(ZERO, base.tax_before_credits - personal.amount_applied)
    credits: tuple[StateCreditComponent, ...] = (personal,)
    warnings: tuple[str, ...] = ()
    asserted = tax_input.federal_eitc_eligibility_asserted
    if asserted is True:
        require_policy_inputs(tax_input, "federal_earned_income_credit")
        federal_eic = tax_input.federal_earned_income_credit or ZERO
        # 30 Del. C. 1117: elect 4.5% refundable or 20% nonrefundable; use the larger.
        refundable = federal_eic * D(".045")
        if refundable >= remaining:
            credits += (
                credit(
                    "DE-EITC-REFUNDABLE", "Delaware refundable earned income tax credit",
                    refundable, remaining, refundable=True,
                ),
            )
        else:
            credits += (
                credit(
                    "DE-EITC-NONREFUNDABLE",
                    "Delaware nonrefundable earned income tax credit",
                    federal_eic * D(".20"), remaining,
                ),
            )
    elif (
        asserted is None
        and tax_input.federal_earned_income_credit is None
        and (
            tax_input.num_dependents
            or tax_input.federal_agi <= FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026
        )
    ):
        warnings = (
            "Delaware earned income tax credit omitted because federal EITC eligibility "
            "was not affirmatively asserted.",
        )
    base.credits = credits
    base.warnings = warnings
    return base


POLICIES: dict[str, PolicyFn] = {
    "AL": _al,
    "AZ": _az,
    "CA": _ca,
    "CT": _ct,
    "DE": _de,
}

PENDING: dict[str, str] = {
    "AR": (
        "Arkansas indexes its 2026 tax brackets, standard deduction and low-income "
        "credit thresholds annually; DFA has not yet published the 2026 indexed amounts."
    ),
    "CO": (
        "Colorado 2026 changes (high-income deduction add-back limits, TABOR-linked "
        "rate and credit mechanisms) are not yet confirmed from Department of Revenue "
        "publications."
    ),
}

