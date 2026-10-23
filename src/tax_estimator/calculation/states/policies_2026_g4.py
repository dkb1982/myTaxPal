"""Source-reviewed 2026 state policies, group 4 (MS, MO, MT, NE, NJ, NM, NY).

See policies_2026_common for the supported profile. Each policy cites its
primary sources in rules/states/2026/<st>.yaml ``references``; year-specific
constants that are not plain YAML brackets/deductions live here with the
statute or publication that fixes them.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from tax_estimator.calculation.states.policies_2026_common import (
    ZERO,
    PolicyFn,
    StateAmountComponent,
    StateCreditComponent,
    StatePolicyComputation,
    StatePolicyError,
    StateRules,
    StateTaxInput,
    calculate_rate_schedule,
    component,
    credit,
    federal_eic_credit,
    irc_net_capital_gain,
    require_policy_inputs,
    schedule_policy,
)

D = Decimal

# Rev. Proc. 2025-32: 2026 federal EIC, no qualifying child, single filer,
# completed-phaseout AGI.
FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026 = D("19540")


# ---------------------------------------------------------------------------
# Mississippi
# ---------------------------------------------------------------------------


def _ms(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    """Miss. Code §27-7-5 (HB 1, 2025): 0% on the first $10,000, 4% above (2026).

    The YAML encodes the $10,000 zero band as the first bracket. §27-7-17
    standard deduction $2,300; §27-7-21 personal exemption $6,000 (single).
    """
    base = schedule_policy(tax_input, rules, exemption=D("6000"))
    base.notes = (
        "Mississippi 2026: 4% on taxable income over $10,000 (Miss. Code §27-7-5 as "
        "amended by HB 1, 2025) after the $2,300 standard deduction and $6,000 exemption.",
    )
    return base


# ---------------------------------------------------------------------------
# Missouri
# ---------------------------------------------------------------------------


def _mo_federal_tax_percentage(missouri_agi: Decimal) -> Decimal:
    # RSMo 143.171.2 (tax years beginning on or after January 1, 2019).
    if missouri_agi <= D("25000"):
        return D(".35")
    if missouri_agi <= D("50000"):
        return D(".25")
    if missouri_agi <= D("100000"):
        return D(".15")
    if missouri_agi <= D("125000"):
        return D(".05")
    return ZERO


def _mo(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(
        tax_input,
        "federal_income_tax_after_nonrefundable_credits",
        "federal_agi_capital_gain",
    )
    # RSMo 143.121.3 (HB 594, 2025): 100% of federal capital-gain income is
    # subtracted for tax years beginning on or after January 1, 2025.
    capital_subtraction = max(ZERO, tax_input.federal_agi_capital_gain or ZERO)
    missouri_agi = tax_input.federal_agi - capital_subtraction
    # RSMo 143.171: limited federal income-tax deduction, $5,000 cap (single).
    federal_deduction = min(
        D("5000"),
        max(ZERO, tax_input.federal_income_tax_after_nonrefundable_credits or ZERO)
        * _mo_federal_tax_percentage(missouri_agi),
    )
    subtractions = tuple(
        x
        for x in (
            component(
                "MO-CAPITAL-GAIN", "Capital-gain income subtraction", capital_subtraction
            ),
            component(
                "MO-FEDERAL-TAX", "Limited federal income-tax deduction", federal_deduction
            ),
        )
        if x.amount
    )
    # RSMo 143.131: Missouri standard deduction equals the federal amount ($16,100).
    base = schedule_policy(tax_input, rules, subtractions=subtractions)
    base.notes = (
        "Missouri 2026: 0%-4.7% schedule with brackets indexed under RSMo 143.011; "
        "100% capital-gain subtraction (RSMo 143.121) and limited federal tax deduction "
        "(RSMo 143.171); $16,100 standard deduction (RSMo 143.131).",
    )
    base.warnings = (
        "MO 2026 bracket widths ($1,348) taken from the Department of Revenue 2026 "
        "withholding formula, which mirrors the RSMo 143.011 indexed tax table; the "
        "2026 MO-1040 tax chart has not yet been published (provisional).",
    )
    return base


# ---------------------------------------------------------------------------
# Montana
# ---------------------------------------------------------------------------

# MCA 15-30-2103 (temporary version through Dec 31 2026, HB 337 2025):
# single 4.7% to $47,500 and 5.65% above; net long-term capital gains 3.0%
# up to $47,500 less nonqualified taxable income and 4.1% above. Not indexed
# for 2026.
_MT_THRESHOLD = D("47500")
_MT_LTCG_LOW = D(".03")
_MT_LTCG_HIGH = D(".041")


def _mt(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    if (tax_input.net_short_term_gains or ZERO) < 0 or (tax_input.net_long_term_gains or ZERO) < 0:
        raise StatePolicyError("Montana signed capital-loss combinations are not source-supported")
    # MCA 15-30-2120(2): the federal QBI deduction is added back to federal
    # taxable income (zero for this wage/investment profile).
    qbi_addback = max(ZERO, tax_input.federal_qbi_deduction)
    additions = (
        (component("MT-QBI-ADDBACK", "Qualified business income deduction addback", qbi_addback),)
        if qbi_addback
        else ()
    )
    state_agi = tax_input.federal_taxable_income + qbi_addback
    taxable = max(ZERO, state_agi)
    lt = min(max(ZERO, tax_input.net_long_term_gains or ZERO), taxable)
    ordinary = taxable - lt
    ordinary_schedule = calculate_rate_schedule(
        ordinary, rules.get_brackets_for_status("single"), use_published_base_tax=True
    )
    lt_low = min(lt, max(ZERO, _MT_THRESHOLD - ordinary))
    lt_high = lt - lt_low
    lt_tax = lt_low * _MT_LTCG_LOW + lt_high * _MT_LTCG_HIGH
    total = ordinary_schedule.tax + lt_tax
    credits, warnings = federal_eic_credit(
        tax_input,
        "MT-EITC",
        "Montana earned income tax credit",
        D(".20"),  # MCA 15-30-2318 as amended by HB 337 (2025): 20% from 2026; refundable.
        total,
        refundable=True,
        childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    return StatePolicyComputation(
        starting_income=tax_input.federal_taxable_income,
        additions=additions,
        state_agi=state_agi,
        taxable_income=taxable,
        ordinary_taxable_income=ordinary,
        preferential_taxable_income=lt,
        ordinary_tax=ordinary_schedule.tax,
        preferential_tax=lt_tax,
        tax_before_credits=total,
        credits=credits,
        marginal_rate=_MT_LTCG_HIGH if lt_high else (
            _MT_LTCG_LOW if lt else ordinary_schedule.marginal_rate
        ),
        bracket_breakdown=ordinary_schedule.bracket_breakdown,
        warnings=warnings,
        notes=(
            "Montana 2026 (HB 337): federal taxable income taxed at 4.7% to $47,500 and "
            "5.65% above; net long-term capital gains stacked on top at 3.0%/4.1%; "
            "qualified dividends stay ordinary.",
        ),
    )


# ---------------------------------------------------------------------------
# Nebraska
# ---------------------------------------------------------------------------

_NE_PERSONAL_EXEMPTION_CREDIT = D("176")  # 2026 Form 1040N line 18.


def _ne(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    # 2026 Form 1040N: federal AGI less the $8,850 standard deduction; tax from
    # the 2026 Tax Calculation Schedule (required for e-filers).
    base = schedule_policy(tax_input, rules)
    liability = base.tax_before_credits
    credits: list[StateCreditComponent] = [
        credit(
            "NE-PERSONAL-EXEMPTION",
            "Nebraska personal exemption credit",
            _NE_PERSONAL_EXEMPTION_CREDIT,
            liability,
        )
    ]
    eitc, warnings = federal_eic_credit(
        tax_input,
        "NE-EITC",
        "Nebraska earned income credit",
        D(".10"),  # Neb. Rev. Stat. 77-2715.07; 2026 Form 1040N line 44; refundable.
        ZERO,
        refundable=True,
        childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    credits.extend(eitc)
    base.credits = tuple(credits)
    base.warnings = warnings
    base.notes = (
        "Nebraska 2026 Form 1040N: $8,850 standard deduction, 2.46%/3.51%/4.55% "
        "schedule (LB 754 rate reduction), $176 personal exemption credit; Nebraska "
        "EIC is 10% of an established federal EIC.",
    )
    return base


# ---------------------------------------------------------------------------
# New Jersey
# ---------------------------------------------------------------------------


def _nj(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    # N.J.S.A. 54A:5-1: net gains category may not create a loss that offsets
    # wages, interest or dividends.
    net_disposition_gain = max(
        ZERO,
        (tax_input.net_short_term_gains or ZERO) + (tax_input.net_long_term_gains or ZERO),
    )
    gross_income = (
        tax_input.wages
        + tax_input.interest
        + tax_input.dividends
        + net_disposition_gain
        + max(ZERO, tax_input.retirement_income)
    )
    base = schedule_policy(
        tax_input,
        rules,
        starting_income=gross_income,
        deduction=ZERO,
        exemption=D("1000"),  # N.J.S.A. 54A:3-1(a), single.
    )
    notes = [
        "New Jersey 2026 gross income tax: state-defined income categories, $1,000 "
        "exemption, N.J.S.A. 54A:2-1 rate schedule (taxpayers under $100,000 may use "
        "the rate schedule instead of the tax table).",
    ]
    # N.J.S.A. 54A:2-4: single filers with gross income of $10,000 or less owe no tax.
    if gross_income <= D("10000"):
        base.ordinary_tax = ZERO
        base.tax_before_credits = ZERO
        base.marginal_rate = ZERO
        base.bracket_breakdown = ()
        notes.append("Single filers with New Jersey gross income of $10,000 or less owe no tax.")
    credits, warnings = federal_eic_credit(
        tax_input,
        "NJ-EITC",
        "New Jersey earned income tax credit",
        D(".40"),  # N.J.S.A. 54A:4-7(b): 40% of federal EIC; refundable.
        base.tax_before_credits,
        refundable=True,
        childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    base.credits = credits
    base.warnings = warnings
    base.notes = tuple(notes)
    return base


# ---------------------------------------------------------------------------
# New Mexico
# ---------------------------------------------------------------------------

_NM_TABLE_LIMIT = D("100000")
_NM_TABLE_BAND = D("100")


def _nm_table_tax(taxable: Decimal, rules: StateRules) -> Decimal:
    """PIT-1 tax rate table: $100 bands ("more than / but not over"), tax at
    the band midpoint rounded to whole dollars; the first band ends at $60."""
    if taxable <= D("60"):
        return ZERO
    upper = (taxable / _NM_TABLE_BAND).to_integral_value(rounding=ROUND_CEILING) * _NM_TABLE_BAND
    midpoint = upper - D("50")
    if upper == _NM_TABLE_BAND:
        midpoint = D("80")  # band 60-100
    schedule = calculate_rate_schedule(
        midpoint, rules.get_brackets_for_status("single"), use_published_base_tax=True
    )
    return schedule.tax.quantize(D("1"), rounding=ROUND_HALF_UP)


def _nm(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    # NMSA 7-2-34: net capital gain deduction, up to $2,500 for gains other than
    # the sale of a New Mexico business.
    capital_deduction = min(
        D("2500"),
        irc_net_capital_gain(
            tax_input.net_short_term_gains or ZERO,
            tax_input.net_long_term_gains or ZERO,
        ),
    )
    subtraction_items: list[StateAmountComponent] = []
    if capital_deduction:
        subtraction_items.append(
            component(
                "NM-NET-CAPITAL-GAIN", "New Mexico net capital gain deduction", capital_deduction
            )
        )
    # NMSA 7-2-5.8: low- and middle-income exemption, one exemption, single:
    # $2,500 reduced by 15% of AGI over $20,000; none above $36,667.
    agi = tax_input.federal_agi
    low_middle = ZERO
    if agi <= D("36667"):
        low_middle = max(ZERO, D("2500") - D(".15") * max(ZERO, agi - D("20000")))
    if low_middle:
        subtraction_items.append(
            component(
                "NM-LOW-MIDDLE-EXEMPTION",
                "New Mexico low- and middle-income exemption",
                low_middle,
            )
        )
    # PIT-1 starts from federal AGI less the federal standard deduction (NM
    # standard deduction equals the federal amount, $16,100 for 2026); no QBI line.
    base = schedule_policy(
        tax_input,
        rules,
        starting_income=tax_input.federal_taxable_income_before_qbi,
        subtractions=tuple(subtraction_items),
        deduction=ZERO,
    )
    notes = [
        "New Mexico 2026: NMSA 7-2-7 rates (Laws 2024 ch. 67, not indexed) on federal AGI "
        "less the federal standard deduction; net capital gain deduction limited to $2,500.",
    ]
    if ZERO < base.taxable_income <= _NM_TABLE_LIMIT:
        base.ordinary_tax = _nm_table_tax(base.taxable_income, rules)
        base.tax_before_credits = base.ordinary_tax
        notes.append(
            "New Mexico PIT-1 tax rate table method ($100 bands, midpoint, whole dollars) "
            "used at or below $100,000 of taxable income."
        )
    warnings = []
    if agi <= D("36000"):
        warnings.append(
            "New Mexico low-income comprehensive tax rebate omitted because the input does "
            "not establish the separate inmate-status eligibility fact."
        )
    credits, eic_warnings = federal_eic_credit(
        tax_input,
        "NM-WFTC",
        "New Mexico Working Families Tax Credit",
        D(".25"),  # NMSA 7-2-18.15: 25% of federal EIC; refundable.
        base.tax_before_credits,
        refundable=True,
        childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    base.credits = credits
    base.warnings = eic_warnings + tuple(warnings)
    base.notes = tuple(notes)
    return base


# ---------------------------------------------------------------------------
# New York (state tax only; NYC/Yonkers read tax after nonrefundable credits)
# ---------------------------------------------------------------------------

_NY_STANDARD_DEDUCTION = D("8000")  # Tax Law §614(a), single.
_NY_RECAPTURE_AGI = D("107650")
_NY_PHASE_IN = D("50000")
# Tax Law §601(d-5)(3)(A)(i), taxable years beginning in 2026: unmarried
# individuals. (taxable income over, not over, recapture base, incremental
# benefit, NYAGI subtracted to get the applicable amount)
_NY_RECAPTURE_2026 = (
    (D("80650"), D("215400"), ZERO, D("567"), D("107650")),
    (D("215400"), D("1077550"), D("567"), D("2047"), D("215400")),
    (D("1077550"), D("5000000"), D("2614"), D("30172"), D("1077550")),
    (D("5000000"), D("25000000"), D("32786"), D("32500"), D("5000000")),
)
_NY_TOP_FLAT_RATE = D(".109")
_NY_SECOND_RATE = D(".059")


def _ny_phase_in(agi: Decimal, offset: Decimal) -> Decimal:
    # IT-201 worksheets round the phase-in fraction to four decimal places.
    return (min(_NY_PHASE_IN, max(ZERO, agi - offset)) / _NY_PHASE_IN).quantize(
        D("0.0001"), rounding=ROUND_HALF_UP
    )


def _ny_supplemental_tax(agi: Decimal, taxable: Decimal, tax: Decimal) -> Decimal:
    """Tax Law §601(d-5)(3), 2026 unmarried-individual supplemental tax."""
    if agi <= _NY_RECAPTURE_AGI:
        return ZERO
    if agi > D("25000000"):
        return max(ZERO, taxable * _NY_TOP_FLAT_RATE - tax)
    if taxable <= D("80650"):
        return max(ZERO, (taxable * _NY_SECOND_RATE - tax) * _ny_phase_in(agi, _NY_RECAPTURE_AGI))
    for low, high, recapture_base, increment, offset in _NY_RECAPTURE_2026:
        if low < taxable <= high:
            return recapture_base + increment * _ny_phase_in(agi, offset)
    # Taxable income above $25,000,000 with NYAGI not above it cannot occur.
    raise StatePolicyError("New York 2026 supplemental tax bracket not found")


def _ny_household_credit(agi: Decimal) -> Decimal:
    # Tax Law §606(b)(2)(A), single (household gross income = federal AGI here).
    for limit, amount in (
        (D("5000"), D("75")), (D("6000"), D("60")), (D("7000"), D("50")),
        (D("20000"), D("45")), (D("25000"), D("40")), (D("28000"), D("20")),
    ):
        if agi <= limit:
            return amount
    return ZERO


def _ny(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    agi = tax_input.federal_agi
    base = schedule_policy(tax_input, rules, deduction=_NY_STANDARD_DEDUCTION)
    base.deduction_type = "standard"
    base.recapture = _ny_supplemental_tax(agi, base.taxable_income, base.tax_before_credits)
    liability = base.tax_before_credits + base.recapture

    credits: list[StateCreditComponent] = []
    household = ZERO if tax_input.can_be_claimed_as_dependent else _ny_household_credit(agi)
    household_applied = ZERO
    if household:
        household_credit = credit(
            "NY-HOUSEHOLD", "New York State household credit", household, liability
        )
        household_applied = household_credit.amount_applied
        credits.append(household_credit)
    eitc, warnings = federal_eic_credit(
        tax_input,
        "NY-EITC",
        "New York State earned income credit",
        D(".30"),  # Tax Law §606(d)(1): 30% of federal EIC; refundable.
        liability,
        refundable=True,
        childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    for item in eitc:
        # §606(d)(1)(ii): reduced by the household credit allowed.
        amount = max(ZERO, item.amount_available - household_applied)
        credits.append(credit(item.credit_id, item.name, amount, ZERO, refundable=True))
    base.credits = tuple(credits)
    base.warnings = warnings
    base.notes = (
        "New York 2026: Tax Law §601(c)(1)(B)(vii) rate schedule (Ch. 59, Laws of 2025 "
        "middle-class cut) on NY AGI less the $8,000 standard deduction; supplemental "
        "tax per §601(d-5) above $107,650 NY AGI is shown as recapture.",
        "Continuous rate schedule is used where the filing instructions otherwise "
        "require the NYS tax table.",
        "The 2026 POWER energy rebate (Tax Law §606(uuu)) is advance-paid from 2024 "
        "return data and is not included in 2026 liability.",
    )
    return base


POLICIES: dict[str, PolicyFn] = {
    "MS": _ms,
    "MO": _mo,
    "MT": _mt,
    "NE": _ne,
    "NJ": _nj,
    "NM": _nm,
    "NY": _ny,
}

PENDING: dict[str, str] = {}
