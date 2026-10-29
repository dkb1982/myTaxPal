"""Source-reviewed 2026 state policies, group 3 (KY, LA, ME, MD, MA, MI, MN).

See policies_2026_common for the supported profile. Each policy cites its
primary sources in rules/states/2026/<st>.yaml ``references``; year-specific
constants that are not plain YAML brackets/deductions live here with the
statute or publication that fixes them.
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

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
    credit,
    federal_eic_credit,
    flat_policy,
    irc_net_capital_gain,
    require_policy_inputs,
    round_dollar,
    schedule_policy,
)

D = Decimal

# Rev. Proc. 2025-32: 2026 federal EIC, no qualifying child, single filer,
# completed-phaseout AGI and disqualified investment income limit.
FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026 = D("19540")
FEDERAL_EIC_INVESTMENT_INCOME_LIMIT_2026 = D("12200")

# HHS 2026 poverty guideline, household of one, 48 states/DC (91 FR, Jan 15 2026).
HHS_POVERTY_GUIDELINE_ONE_2026 = D("15960")


def _eligible_eic_only_if_asserted(t: StateTaxInput) -> bool:
    return t.federal_eitc_eligibility_asserted is True


# ---------------------------------------------------------------------------
# Kentucky
# ---------------------------------------------------------------------------

_KY_FAMILY_SIZE_STEPS = (
    (D("1.00"), D("1.00")), (D("1.04"), D(".90")), (D("1.08"), D(".80")),
    (D("1.12"), D(".70")), (D("1.16"), D(".60")), (D("1.20"), D(".50")),
    (D("1.24"), D(".40")), (D("1.27"), D(".30")), (D("1.30"), D(".20")),
    (D("1.33"), D(".10")),
)


def _ky(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    """KRS 141.020(2)(f) 3.5%; KRS 141.081 indexed standard deduction ($3,360)."""
    base = flat_policy(tax_input, rules)
    # KRS 141.066(3): family size credit, threshold = HHS poverty guideline for a
    # family of one available on June 30 of the taxable year. Modified gross
    # income equals federal/Kentucky AGI for this profile; the 2025 policy's
    # greater-of treatment is retained.
    mgi = max(ZERO, tax_input.federal_agi, base.state_agi)
    threshold = HHS_POVERTY_GUIDELINE_ONE_2026
    percentage = ZERO
    for multiple, rate in _KY_FAMILY_SIZE_STEPS:
        if mgi <= threshold * multiple:
            percentage = rate
            break
    warnings: tuple[str, ...] = ()
    if percentage:
        base.credits = (
            credit(
                "KY-FAMILY-SIZE",
                "Kentucky family size tax credit",
                base.tax_before_credits * percentage,
                base.tax_before_credits,
            ),
        )
        warnings = (
            "KY 2026 family size tax credit thresholds computed from KRS 141.066 and the "
            "2026 HHS poverty guideline ($15,960); Kentucky DOR has not yet published the "
            "2026 Schedule ITC table (provisional).",
        )
    base.warnings = warnings
    base.notes = (
        "Kentucky 2026: 3.5% flat rate (KRS 141.020(2)(f)) on federal AGI less the "
        "$3,360 indexed standard deduction.",
    )
    return base


# ---------------------------------------------------------------------------
# Louisiana
# ---------------------------------------------------------------------------


def _la(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    """La. R.S. 47:32(A) 3%; R.S. 47:294 indexed standard deduction (RIB 26-019)."""
    base = flat_policy(tax_input, rules)
    credits, warnings = federal_eic_credit(
        tax_input,
        "LA-EIC",
        "Louisiana earned income credit",
        D(".05"),  # R.S. 47:297.8(A)(2), tax years 2019 through 2030; refundable (B).
        base.tax_before_credits,
        refundable=True,
        childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    base.credits = credits
    base.warnings = warnings
    base.notes = (
        "Louisiana 2026: 3% flat rate on federal AGI less the $12,838 inflation-adjusted "
        "standard deduction (LDR RIB 26-019).",
    )
    return base


# ---------------------------------------------------------------------------
# Maine
# ---------------------------------------------------------------------------

# 36 M.R.S. §5124-C(1-C)(A)(1): 2026 basic standard deduction $15,700 (MRS
# 2026 rate schedule, rev. May 20 2026). §5124-C(2)(A) phase-out threshold
# $102,250 as published on the MRS 2026 standard deduction phase-out worksheet
# (line 6a, rev. December 2025).
_ME_STD_DEDUCTION = D("15700")
_ME_STD_PHASEOUT_START = D("102250")
_ME_STD_PHASEOUT_RANGE = D("75000")
# §5126-A: exemption $5,300 (MRS schedule); phase-out begins at $341,000 per the
# MRS 2026 personal exemption phase-out worksheet (line 6b); range $125,000.
_ME_EXEMPTION = D("5300")
_ME_EXEMPTION_PHASEOUT_START = D("341000")
_ME_EXEMPTION_PHASEOUT_RANGE = D("125000")
# §5111(7): 2% surcharge on Maine taxable income over $1,000,000 (single), 2026.
_ME_SURCHARGE_THRESHOLD = D("1000000")
_ME_SURCHARGE_RATE = D(".02")


def _phase_fraction(agi: Decimal, start: Decimal, span: Decimal) -> Decimal:
    # MRS 2026 phase-out worksheets, line 5: fraction entered to four decimal places
    # ("__.____"); rounding direction is not stated, conventional rounding assumed.
    fraction = min(D(1), max(ZERO, agi - start) / span)
    return fraction.quantize(D("0.0001"), rounding=ROUND_HALF_UP)


def _me(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    agi = tax_input.federal_agi
    deduction = _ME_STD_DEDUCTION
    deduction -= deduction * _phase_fraction(agi, _ME_STD_PHASEOUT_START, _ME_STD_PHASEOUT_RANGE)
    exemption = _ME_EXEMPTION
    exemption -= exemption * _phase_fraction(
        agi, _ME_EXEMPTION_PHASEOUT_START, _ME_EXEMPTION_PHASEOUT_RANGE
    )
    base = schedule_policy(tax_input, rules, deduction=deduction, exemption=exemption)
    base.deduction_type = "standard"
    base.surtax = max(ZERO, base.taxable_income - _ME_SURCHARGE_THRESHOLD) * _ME_SURCHARGE_RATE
    eitc, warnings = federal_eic_credit(
        tax_input,
        "ME-EITC",
        "Maine earned income tax credit",
        D(".50"),  # 36 M.R.S. §5219-S(1-A), no qualifying child; refundable (4).
        base.tax_before_credits + base.surtax,
        refundable=True,
        childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    base.credits = eitc
    base.warnings = warnings
    base.notes = (
        "Maine 2026 rate schedule, $15,700 standard deduction and $5,300 exemption per "
        "MRS 2026 Individual Income Tax Rates (rev. May 20, 2026); 2% surcharge above "
        "$1,000,000 of Maine taxable income is shown as a surtax.",
    )
    return base


# ---------------------------------------------------------------------------
# Maryland (state income tax only; county/local tax is separate)
# ---------------------------------------------------------------------------

_MD_CAPITAL_GAIN_SURTAX_AGI = D("350000")


def _md_exemption(agi: Decimal) -> Decimal:
    # Tax-General §10-211(b)(1), (c)(1): $3,200, limited above $100,000 FAGI.
    if agi <= D("100000"):
        return D("3200")
    if agi <= D("125000"):
        return D("1600")
    if agi <= D("150000"):
        return D("800")
    return ZERO


def _md(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    agi = tax_input.federal_agi
    base = schedule_policy(tax_input, rules, exemption=_md_exemption(agi))
    notes = [
        "Maryland 2026 state tax per Tax-General §10-105(a)(1); county/local income tax "
        "is computed separately.",
    ]
    if ZERO < base.taxable_income < D("100000"):
        # Form 502 tax table: $50 bands, tax at the band midpoint, whole dollars.
        midpoint = (base.taxable_income / D("50")).to_integral_value(
            rounding=ROUND_FLOOR
        ) * D("50") + D("25")
        table = calculate_rate_schedule(
            midpoint, rules.get_brackets_for_status("single"), use_published_base_tax=True
        )
        base.ordinary_tax = round_dollar(table.tax)
        base.tax_before_credits = base.ordinary_tax
        notes.append(
            "Maryland $50-band tax table method (as on the 2025 Form 502) used below $100,000."
        )
    # §10-105(a)(3)-(4): additional 2% of net capital gain when FAGI > $350,000.
    net_gain = irc_net_capital_gain(
        tax_input.net_short_term_gains or ZERO, tax_input.net_long_term_gains or ZERO
    )
    if agi > _MD_CAPITAL_GAIN_SURTAX_AGI and net_gain:
        base.surtax = net_gain * D(".02")
        notes.append("Maryland 2% net-capital-gain tax shown separately as a surtax.")
    liability = base.tax_before_credits + base.surtax

    credits: list[StateCreditComponent] = []
    warnings: list[str] = []
    if tax_input.federal_eitc_eligibility_asserted is True:
        if tax_input.federal_earned_income_credit is None:
            warnings.append("Maryland EIC omitted because the federal EIC amount is unavailable.")
        else:
            # §10-704(c)(3): no qualifying child, 100% of federal EIC; excess refundable.
            federal_eic = max(ZERO, tax_input.federal_earned_income_credit)
            nonref = min(federal_eic, liability)
            credits.append(credit("MD-EITC", "Maryland earned income credit", nonref, liability))
            excess = federal_eic - nonref
            if excess:
                credits.append(
                    credit(
                        "MD-EITC-REFUND",
                        "Refundable Maryland earned income credit",
                        excess,
                        ZERO,
                        refundable=True,
                    )
                )
    elif tax_input.federal_eitc_eligibility_asserted is None and (
        agi <= FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026
    ):
        warnings.append(
            "Maryland EIC omitted because federal EITC eligibility was not affirmatively asserted."
        )

    # §10-709: poverty-level credit; FAGI and earned income not over the 2026 HHS
    # guideline for one exemption; lesser of tax after EIC or 5% of earned income.
    remaining = max(ZERO, liability - sum((c.amount_applied for c in credits), ZERO))
    if (
        agi <= HHS_POVERTY_GUIDELINE_ONE_2026
        and tax_input.wages <= HHS_POVERTY_GUIDELINE_ONE_2026
        and remaining > 0
    ):
        credits.append(
            credit(
                "MD-POVERTY",
                "Maryland poverty-level credit",
                tax_input.wages * D(".05"),
                remaining,
            )
        )
    base.credits = tuple(credits)
    warnings.append(
        "MD 2026 standard deduction ($3,400) computed from Tax-General §10-217(c) "
        "(2024-base cost-of-living adjustment, rounded down to $50); it matches the "
        "Comptroller's 2026 withholding guide but the Comptroller has not yet published "
        "2026 Form 502 instructions (provisional).",
    )
    base.warnings = tuple(warnings)
    base.notes = tuple(notes)
    return base


# ---------------------------------------------------------------------------
# Massachusetts
# ---------------------------------------------------------------------------

_MA_SURTAX_THRESHOLD_2026 = D("1107750")  # DOR certification, Nov 20 2025.


def _ma(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(
        tax_input,
        "net_short_term_gains",
        "net_long_term_gains",
        "employee_social_security_tax",
        "employee_medicare_tax",
    )
    st_gain = tax_input.net_short_term_gains or ZERO
    lt_gain = tax_input.net_long_term_gains or ZERO
    if st_gain < 0 or lt_gain < 0:
        raise StatePolicyError(
            "Massachusetts signed capital-loss combinations are not source-supported"
        )
    employee_fica = (tax_input.employee_social_security_tax or ZERO) + (
        tax_input.employee_medicare_tax or ZERO
    )
    fica_deduction = min(D("2000"), employee_fica)  # M.G.L. c. 62 §3(B)(a)(9)
    exemption = D("4400")  # M.G.L. c. 62 §3(B)(b)(1), single
    total_after = max(ZERO, tax_input.federal_agi - fica_deduction - exemption)
    st_taxable = min(st_gain, total_after)
    ordinary_taxable = total_after - st_taxable
    ordinary_tax = ordinary_taxable * D(".05")
    st_tax = st_taxable * D(".085")
    base_tax = ordinary_tax + st_tax
    surtax = max(ZERO, total_after - _MA_SURTAX_THRESHOLD_2026) * D(".04")

    credits: list[StateCreditComponent] = []
    notes = [
        "Massachusetts 2026: 5% Part B/Part A income and long-term gains, 8.5% short-term "
        "gains, 4% surtax above $1,107,750 of taxable income.",
    ]
    # M.G.L. c. 62 §5: No Tax Status / limited income credit, AGI before FICA and
    # exemption (Form 1 worksheets); single thresholds $8,000 and 1.75 x $8,000.
    agi = tax_input.federal_agi
    liability = base_tax + surtax
    if agi <= D("8000"):
        credits.append(credit("MA-NTS", "Massachusetts No Tax Status relief", liability, liability))
    elif agi <= D("14000"):
        cap = (agi - D("8000")) * D(".10")
        relief = max(ZERO, liability - cap)
        credits.append(credit("MA-LIC", "Massachusetts limited income credit", relief, liability))
    if credits:
        notes.append(
            "MA No Tax Status / limited-income AGI is before employee FICA deductions."
        )
    eitc, warnings = federal_eic_credit(
        tax_input,
        "MA-EITC",
        "Massachusetts earned income credit",
        D(".40"),  # M.G.L. c. 62 §6(h); refundable.
        liability,
        refundable=True,
        childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    credits.extend(eitc)
    return StatePolicyComputation(
        starting_income=tax_input.federal_agi,
        state_agi=tax_input.federal_agi - fica_deduction,
        subtractions=(
            StateAmountComponent(
                "MA-EMPLOYEE-FICA",
                "Employee Social Security and Medicare deduction (capped)",
                fica_deduction,
            ),
        ),
        deduction_type="none",
        deduction_amount=ZERO,
        personal_exemption=exemption,
        taxable_income=total_after,
        ordinary_taxable_income=ordinary_taxable,
        preferential_taxable_income=st_taxable,
        ordinary_tax=ordinary_tax,
        preferential_tax=st_tax,
        tax_before_credits=base_tax,
        surtax=surtax,
        credits=tuple(credits),
        marginal_rate=D(".085") if st_taxable else D(".05"),
        warnings=warnings,
        notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# Michigan
# ---------------------------------------------------------------------------


def _mi(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    """4.25% (Treasury 2026 determination); $5,900 personal exemption."""
    base = flat_policy(tax_input, rules, exemption=D("5900"))
    base.deduction_type = "none"
    credits, warnings = federal_eic_credit(
        tax_input,
        "MI-EITC",
        "Michigan earned income tax credit",
        D(".30"),  # MCL 206.272, 30% of federal EIC; refundable.
        base.tax_before_credits,
        refundable=True,
        childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    base.credits = credits
    base.warnings = warnings
    base.notes = (
        "Michigan 2026: 4.25% flat rate (Treasury found the MCL 206.51 reduction "
        "conditions unmet) on federal AGI less the $5,900 personal exemption.",
    )
    return base


# ---------------------------------------------------------------------------
# Minnesota
# ---------------------------------------------------------------------------

# Minn. Stat. 290.0123 subd. 5 as adjusted by DOR "Tax Year 2026 Inflation-
# Adjusted Amounts" (Dec 2025).
_MN_STD_PHASEOUT_1 = D("244400")
_MN_STD_PHASEOUT_2 = D("337800")
_MN_STD_80_PERCENT_AGI = D("1107750")
# Working family credit (290.0671, 290.0661 subd. 4), 2026 adjusted amounts.
_MN_WFC_EARNED_MAX = D("9690")
_MN_WFC_PHASEOUT = D("32680")


def _mn_working_family_credit(t: StateTaxInput) -> Decimal:
    """Schedule M1CWFC, no qualifying children; whole-dollar entries."""
    earned = min(_MN_WFC_EARNED_MAX, max(ZERO, t.wages))
    tentative = round_dollar(earned * D(".04"))
    income = max(t.federal_agi, t.wages)
    reduction = round_dollar(max(ZERO, income - _MN_WFC_PHASEOUT) * D(".12"))
    return max(ZERO, tentative - reduction)


def _mn(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    agi = tax_input.federal_agi
    full = rules.get_standard_deduction(tax_input.filing_status)
    if agi > _MN_STD_80_PERCENT_AGI:
        reduction = full * D(".80")
    else:
        reduction = min(
            (min(max(agi, _MN_STD_PHASEOUT_1), _MN_STD_PHASEOUT_2) - _MN_STD_PHASEOUT_1)
            * D(".03")
            + max(ZERO, agi - _MN_STD_PHASEOUT_2) * D(".10"),
            full * D(".80"),
        )
    base = schedule_policy(tax_input, rules, deduction=full - reduction)
    base.deduction_type = "standard"
    # 290.033: 1% of net investment income (IRC 1411(c)) in excess of $1,000,000.
    net_gain = max(ZERO, (tax_input.net_short_term_gains or ZERO)
                   + (tax_input.net_long_term_gains or ZERO))
    # IRC 1411(c)(1)(A)(i) gross income from interest and dividends, plus net gain.
    nii = tax_input.interest + max(ZERO, tax_input.dividends) + net_gain
    base.surtax = max(ZERO, nii - D("1000000")) * D(".01")

    notes = [
        "Minnesota 2026 brackets and standard deduction per DOR 2026 inflation-adjusted "
        "amounts; the 1% net investment income tax (Minn. Stat. 290.033) is a surtax.",
    ]
    warnings: tuple[str, ...] = ()
    amount = _mn_working_family_credit(tax_input)
    if amount:
        investment_income = tax_input.interest + max(ZERO, tax_input.dividends) + net_gain
        if investment_income > FEDERAL_EIC_INVESTMENT_INCOME_LIMIT_2026:
            notes.append(
                "Minnesota Working Family Credit omitted: investment income exceeds the 2026 "
                "federal EIC limit of $12,200."
            )
        elif _eligible_eic_only_if_asserted(tax_input):
            base.credits = (
                credit(
                    "MN-WFC", "Minnesota Working Family Credit", amount, ZERO, refundable=True
                ),
            )
            notes.append(
                "MN 2026 Working Family Credit: 4% of earned income up to $9,690, reduced by "
                "12% of income over $32,680; refundable."
            )
        elif tax_input.federal_eitc_eligibility_asserted is None:
            warnings = (
                "Minnesota Working Family Credit omitted: claimant eligibility is not "
                "established.",
            )
    base.notes = tuple(notes)
    base.warnings = warnings
    return base


POLICIES: dict[str, PolicyFn] = {
    "KY": _ky,
    "LA": _la,
    "ME": _me,
    "MD": _md,
    "MA": _ma,
    "MI": _mi,
    "MN": _mn,
}

PENDING: dict[str, str] = {}
