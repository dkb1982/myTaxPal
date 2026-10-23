"""Source-reviewed 2026 state policies, group 6 (SC, UT, VT, VA, WA, WV, WI).

See policies_2026_common for the supported profile. Evidence for every
constant below is recorded in rules/states/2026/<st>.yaml ``references``.
Like the 2025 baseline, graduated taxes use the official rate schedules (not
the $50/$100 tax-table midpoints); where a state's table would differ by more
than rounding this is noted beside the state.

Indexed 2026 amounts that the state agency has not yet published are computed
from the statutory formula with published BLS CPI inputs and carry a
"(provisional)" warning. Each such reconstruction was checked against the
agency's own published amounts for at least two earlier years.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from tax_estimator.calculation.states.policies_2026_common import (
    ZERO,
    PolicyFn,
    StateCreditComponent,
    StatePolicyComputation,
    StateRules,
    StateTaxInput,
    component,
    credit,
    federal_eic_credit,
    flat_policy,
    irc_net_capital_gain,
    require_policy_inputs,
    round_dollar,
    schedule_policy,
)
from tax_estimator.calculation.states.models import StateTaxType

D = Decimal

# Rev. Proc. 2025-32: 2026 federal no-qualifying-child EIC completed phaseout (single).
FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026 = D("19540")

# HHS 2026 poverty guideline, household of one, 48 states/DC (91 FR, Jan 2026).
HHS_POVERTY_GUIDELINE_ONE_2026 = D("15960")


def _net_capital_gain(tax_input: StateTaxInput) -> Decimal:
    require_policy_inputs(tax_input, "net_short_term_gains", "net_long_term_gains")
    return irc_net_capital_gain(
        tax_input.net_short_term_gains or ZERO, tax_input.net_long_term_gains or ZERO
    )


def _as_tax(base: StatePolicyComputation, tax: Decimal) -> None:
    base.ordinary_tax = tax
    base.tax_before_credits = tax


# ---------------------------------------------------------------------------
# South Carolina — Act 110 of 2026 (H.4216); SCDOR Information Letter #26-20
# ---------------------------------------------------------------------------

# S.C. Code §12-6-1140(15) (Act 110): SCIAD for single filers.
_SC_SCIAD = D("15000")
_SC_SCIAD_PHASEOUT_START = D("40000")
_SC_SCIAD_PHASEOUT_RANGE = D("55000")
# §12-6-1150: 44% of net capital gain (assets held more than one year).
_SC_CAPITAL_GAIN_DEDUCTION = D(".44")
# §12-6-3632 (Act 110): 125% of the federal EITC, capped at $200, nonrefundable.
_SC_EITC_RATE = D("1.25")
_SC_EITC_CAP = D("200")


def _sc_sciad(agi: Decimal) -> Decimal:
    if agi <= _SC_SCIAD_PHASEOUT_START:
        return _SC_SCIAD
    fraction = (agi - _SC_SCIAD_PHASEOUT_START) / _SC_SCIAD_PHASEOUT_RANGE
    if fraction >= 1:
        return ZERO
    # "Any reduction amount which is not a multiple of ten dollars must be
    # rounded to the next lowest ten dollars."
    reduction = (_SC_SCIAD * fraction / 10).to_integral_value(rounding=ROUND_FLOOR) * 10
    return _SC_SCIAD - reduction


def _sc(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    """2026: federal AGI start (IRC §63(b)-(g) decoupled), SCIAD, 1.99%/5.21%."""
    gain_deduction = _net_capital_gain(tax_input) * _SC_CAPITAL_GAIN_DEDUCTION
    subtractions = (
        (component("SC-NET-CAPITAL-GAIN", "44% net capital gain deduction", gain_deduction),)
        if gain_deduction else ()
    )
    base = schedule_policy(
        tax_input,
        rules,
        subtractions=subtractions,
        deduction=_sc_sciad(tax_input.federal_agi),
        notes=(
            "South Carolina 2026 (Act 110 of 2026, SCDOR IL #26-20): taxable income starts "
            "from federal AGI; the South Carolina Income Adjusted Deduction ($15,000 single, "
            "phased out between $40,000 and $95,000 of federal AGI) replaces the federal "
            "standard deduction; tax is 1.99% up to $30,000 and 5.21% above (5.21% x TI - "
            "$966).",
        ),
    )
    base.deduction_type = "standard"
    eitc, warnings = federal_eic_credit(
        tax_input, "SC-EITC", "South Carolina earned income tax credit", _SC_EITC_RATE,
        base.tax_before_credits, refundable=False,
        childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    base.credits = tuple(
        credit(c.credit_id, c.name, min(c.amount_available, _SC_EITC_CAP),
               base.tax_before_credits)
        for c in eitc
    )
    base.warnings = warnings
    return base


# ---------------------------------------------------------------------------
# Utah — Utah Code §59-10-104 (4.45%, 2026 GS ch. 250), §59-10-1018, §59-10-1044
# ---------------------------------------------------------------------------

# §59-10-1018(4)(a) base $15,095 x CPI-U(12 months to Aug 2025)/CPI-U(12 months
# to Aug 2020) per (5), rounded to the nearest dollar. The same computation
# reproduces the Tax Commission's published $16,742 (2023), $17,652 (2024) and
# $18,213 (2025) exactly.
_UT_PHASEOUT_BASE = D("18696")
_UT_CREDIT_RATE = D(".06")
_UT_PHASEOUT_RATE = D(".013")
_UT_EITC_RATE = D(".20")


def _ut(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "federal_deduction_amount")
    base = flat_policy(tax_input, rules, deduction=ZERO)
    # Utah state taxable income equals federal AGI for this profile (no Utah
    # additions/subtractions for wages, dividends or capital gains).
    initial = max(ZERO, tax_input.federal_deduction_amount or ZERO) * _UT_CREDIT_RATE
    phaseout = max(ZERO, base.taxable_income - _UT_PHASEOUT_BASE) * _UT_PHASEOUT_RATE
    taxpayer_credit = max(ZERO, initial - phaseout)
    credits: list[StateCreditComponent] = []
    remaining = base.tax_before_credits
    warnings: list[str] = []
    if taxpayer_credit:
        c = credit("UT-TAXPAYER", "Utah taxpayer tax credit", taxpayer_credit, remaining)
        credits.append(c)
        remaining -= c.amount_applied
        warnings.append(
            "UT 2026 taxpayer tax credit phase-out base ($18,696) computed from Utah Code "
            "§59-10-1018(4)-(5) with BLS CPI-U; the Utah State Tax Commission has not yet "
            "published it (provisional)."
        )
    eitc, eitc_warnings = federal_eic_credit(
        tax_input, "UT-EITC", "Utah earned income tax credit", _UT_EITC_RATE, remaining,
        refundable=False, childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    # §59-10-1044(2)(b): the credit cannot exceed Utah W-2 wages.
    credits.extend(
        credit(c.credit_id, c.name, min(c.amount_available, tax_input.wages), remaining)
        for c in eitc
    )
    base.credits = tuple(credits)
    base.warnings = tuple(warnings) + eitc_warnings
    base.notes = (
        "Utah 2026: 4.45% of state taxable income (Utah Code §59-10-104, 2026 General "
        "Session ch. 250); nonrefundable taxpayer tax credit of 6% of the federal standard "
        "deduction, reduced by 1.3% of state taxable income above the indexed base.",
    )
    return base


# ---------------------------------------------------------------------------
# Vermont — 32 V.S.A. §5822 (rates), §5811(21) (deductions), §5828b (EITC)
# ---------------------------------------------------------------------------

# §5811(21)(C)-(D): $6,000 standard deduction and $4,150 exemption (2017 base)
# indexed by CPI-U (12 months to Aug 31) per IRC §1(f)(3) methodology, rounded
# down to $50: 2026 = $7,850 and $5,400. The brackets in YAML are the §5822(a)(3)
# 2017-base amounts indexed the same way (2026: $50,750/$122,850/$256,300).
# The same computation reproduces the published 2024 and 2025 schedules exactly,
# and the Department's 2026 withholding tables (GB-1210-2026) embed the same
# brackets (annual table less the $3,925 offset) and the $5,400 allowance.
_VT_STANDARD_DEDUCTION = D("7850")
_VT_EXEMPTION = D("5400")
# §5811(21)(B)(ii): $5,000 flat exclusion for publicly traded securities, capped
# at 40% of federal taxable income.
_VT_CAPITAL_GAIN_EXCLUSION = D("5000")
# §5822(a)(6): above $150,000 FAGI tax is the greater of the schedule or 3% of FAGI.
_VT_MINIMUM_TAX_AGI = D("150000")
_VT_MINIMUM_TAX_RATE = D(".03")


def _vt(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "federal_taxable_income")
    exclusion = min(
        _VT_CAPITAL_GAIN_EXCLUSION,
        _net_capital_gain(tax_input),
        max(ZERO, tax_input.federal_taxable_income) * D(".40"),
    )
    base = schedule_policy(
        tax_input,
        rules,
        subtractions=(
            (component("VT-CAPITAL-GAIN", "Vermont capital gain exclusion ($5,000 flat)",
                       exclusion),)
            if exclusion else ()
        ),
        deduction=_VT_STANDARD_DEDUCTION,
        exemption=_VT_EXEMPTION,
    )
    notes = [
        "Vermont 2026 rate schedule (3.35%-8.75%), $7,850 standard deduction and $5,400 "
        "personal exemption; publicly traded securities receive only the flat $5,000 "
        "capital gain exclusion.",
    ]
    if tax_input.federal_agi > _VT_MINIMUM_TAX_AGI:
        minimum = tax_input.federal_agi * _VT_MINIMUM_TAX_RATE
        if minimum > base.tax_before_credits:
            _as_tax(base, minimum)
            base.bracket_breakdown = ()
            notes.append("Vermont 3% of federal AGI minimum tax applies (32 V.S.A. §5822(a)(6)).")
    eitc, warnings = federal_eic_credit(
        tax_input, "VT-EITC", "Vermont earned income tax credit (no qualifying children)",
        D("1.00"),  # §5828b(a): 100% of the federal EITC; refundable under (b).
        base.tax_before_credits, refundable=True,
        childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    base.credits = eitc
    base.warnings = warnings + (
        "VT 2026 tax brackets, standard deduction ($7,850) and personal exemption ($5,400) "
        "computed from 32 V.S.A. §5822(b)(2) and §5811(21)(D) with BLS CPI-U; the Vermont "
        "Department of Taxes has not yet published the 2026 rate schedules (provisional).",
    )
    base.notes = tuple(notes)
    return base


# ---------------------------------------------------------------------------
# Virginia — Va. Code §58.1-320, §58.1-322.03, §58.1-321, §58.1-339.8
# ---------------------------------------------------------------------------

_VA_STANDARD_DEDUCTION = D("8750")  # §58.1-322.03(1)(b)(v): 2025 and 2026.
_VA_EXEMPTION = D("930")  # §58.1-322.03(2)(a).
_VA_NO_TAX_AGI = D("11950")  # §58.1-321(A): single, VAGI below $11,950.


def _va(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    base = schedule_policy(
        tax_input, rules, deduction=_VA_STANDARD_DEDUCTION, exemption=_VA_EXEMPTION,
    )
    # Whole-dollar tax as on Form 760 (tax table midpoints are not used).
    _as_tax(base, round_dollar(base.tax_before_credits))
    notes = [
        "Virginia 2026: $8,750 single standard deduction, $930 exemption, 2%-5.75% "
        "schedule, whole-dollar tax.",
    ]
    if tax_input.federal_agi < _VA_NO_TAX_AGI:
        _as_tax(base, ZERO)
        base.marginal_rate = ZERO
        base.bracket_breakdown = ()
        notes.append(
            "Single filers with Virginia AGI below $11,950 have no Virginia income tax "
            "(§58.1-321)."
        )
    # §58.1-339.8: $300 low-income credit (family VAGI <= 100% of the poverty
    # guideline published during the taxable year) OR the refundable 20% EITC,
    # never both. Refundable EITC extended through 2029 (2026 HB 30, Sp. Sess. I).
    low_income = (
        D("300") if tax_input.federal_agi <= HHS_POVERTY_GUIDELINE_ONE_2026 else ZERO
    )
    low_income_applied = min(low_income, base.tax_before_credits)
    eitc, warnings = federal_eic_credit(
        tax_input, "VA-EITC", "Virginia refundable earned income tax credit", D(".20"),
        base.tax_before_credits, refundable=True,
        childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )
    refundable_eitc = sum((c.amount_available for c in eitc), ZERO)
    if refundable_eitc > low_income_applied:
        base.credits = eitc
    elif low_income_applied:
        base.credits = (
            credit("VA-CLI", "Virginia low-income individuals credit", low_income,
                   base.tax_before_credits),
        )
    base.warnings = warnings
    base.notes = tuple(notes)
    return base


# ---------------------------------------------------------------------------
# Washington — capital gains excise, RCW 82.87 (no wage income tax)
# ---------------------------------------------------------------------------

# RCW 82.87.060(1)/82.87.150: standard deduction adjusted each October for the
# following year's taxes by the Seattle-area CPI-U (most current index on Oct 1
# vs. the same index 12 months earlier), rounded to the nearest $1,000:
# $278,000 x (Aug 2026 381.123 / Aug 2025 365.211) = $290,112 -> $290,000.
# The same computation reproduces DOR's published $262,000 (2023), $270,000
# (2024) and $278,000 (2025).
_WA_STANDARD_DEDUCTION = D("290000")
_WA_STANDARD_DEDUCTION_2025 = D("278000")
_WA_FIRST_TIER_RATE = D(".07")  # RCW 82.87.040(1)(a)
_WA_SECOND_TIER_THRESHOLD = D("1000000")  # RCW 82.87.040(1)(b), not indexed
_WA_SECOND_TIER_RATE = D(".029")


def _wa(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    require_policy_inputs(tax_input, "net_long_term_gains")
    # RCW 82.87.020: "federal net long-term capital gain" (long-term gains net of
    # long-term losses; short-term results do not offset it).
    lt_gain = max(ZERO, tax_input.net_long_term_gains or ZERO)
    taxable_gain = max(ZERO, lt_gain - _WA_STANDARD_DEDUCTION)
    excise = taxable_gain * _WA_FIRST_TIER_RATE + max(
        ZERO, taxable_gain - _WA_SECOND_TIER_THRESHOLD
    ) * _WA_SECOND_TIER_RATE
    warnings: list[str] = []
    if lt_gain > _WA_STANDARD_DEDUCTION_2025:
        warnings.append(
            "WA 2026 capital gains standard deduction ($290,000) computed from RCW "
            "82.87.150 with the BLS Seattle-area CPI-U; the Department of Revenue has not "
            "yet published it (provisional)."
        )
    if tax_input.federal_eitc_eligibility_asserted is not False and (
        tax_input.federal_agi <= FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026
    ):
        warnings.append(
            "Washington Working Families Tax Credit not estimated: the 2026 refund amounts "
            "(RCW 82.08.0206(3)(d)) are not yet published."
        )
    return StatePolicyComputation(
        starting_income=lt_gain,
        state_agi=lt_gain,
        taxable_income=taxable_gain,
        deduction_type="standard" if taxable_gain or lt_gain else "none",
        deduction_amount=min(lt_gain, _WA_STANDARD_DEDUCTION),
        preferential_taxable_income=taxable_gain,
        preferential_tax=excise,
        tax_before_credits=excise,
        tax_type_override=StateTaxType.CAPITAL_GAINS_EXCISE,
        marginal_rate=(
            _WA_FIRST_TIER_RATE + _WA_SECOND_TIER_RATE
            if taxable_gain > _WA_SECOND_TIER_THRESHOLD
            else _WA_FIRST_TIER_RATE if taxable_gain else ZERO
        ),
        warnings=tuple(warnings),
        notes=(
            "Washington has no tax on wages; the 2026 capital gains excise is 7% of "
            "long-term gains above the standard deduction plus 2.9% on the portion above "
            "$1,000,000.",
        ),
    )


# ---------------------------------------------------------------------------
# West Virginia — W. Va. Code §11-21-4j (2026 SB 392), §11-21-16, §11-21-22b
# ---------------------------------------------------------------------------

_WV_EXEMPTION = D("2000")  # §11-21-16(a)
_WV_FTC_STEP = D("300")  # §11-21-22b(b): 10% less credit per $300 above the guideline


def _wv_family_credit_rate(mfagi: Decimal) -> Decimal:
    excess = mfagi - HHS_POVERTY_GUIDELINE_ONE_2026
    if excess <= 0:
        return D(1)
    step = (excess / _WV_FTC_STEP).to_integral_value(rounding=ROUND_CEILING)
    return max(ZERO, (D(10) - step) / D(10))


def _wv(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    base = schedule_policy(tax_input, rules, deduction=ZERO, exemption=_WV_EXEMPTION)
    _as_tax(base, round_dollar(base.tax_before_credits))
    warnings: tuple[str, ...] = ()
    rate = _wv_family_credit_rate(tax_input.federal_agi)
    if rate and base.tax_before_credits:
        base.credits = (
            credit("WV-FAMILY", "West Virginia low-income family tax credit",
                   base.tax_before_credits * rate, base.tax_before_credits),
        )
        warnings = (
            "WV 2026 family tax credit thresholds computed from W. Va. Code §11-21-22a/22b "
            "and the 2026 HHS poverty guideline ($15,960); the Tax Division has not yet "
            "published the 2026 Schedule FTC-1 table (provisional).",
        )
    base.warnings = warnings
    base.notes = (
        "West Virginia 2026 rates per W. Va. Code §11-21-4j (2026 SB 392: 2.11%-4.58%); "
        "no standard deduction; one $2,000 exemption; whole-dollar tax.",
    )
    return base


# ---------------------------------------------------------------------------
# Wisconsin — Wis. Stat. §71.06(1r), (2e)(bm); §71.05(22)(dp), (dt); (6)(b)9.
# ---------------------------------------------------------------------------

# §71.05(22)(dp)1./(dt): $7,200 and $10,380 (single) x CPI-U Aug 2025/Aug 1999
# (323.976/167.1), rounded to the nearest $10: $13,960 and $20,120. The same
# computation reproduces the published 2025 table ($13,560; phase-out from
# about $19,550). Reduced by 12% of Wisconsin AGI above the threshold. The
# statute directs DOR to publish a $500-band table; the exact formula is used
# here, consistent with the exact rate schedule (difference is at most ~$30 of
# deduction, ~$2 of tax).
_WI_STANDARD_DEDUCTION = D("13960")
_WI_STANDARD_DEDUCTION_THRESHOLD = D("20120")
_WI_STANDARD_DEDUCTION_RATE = D(".12")
_WI_EXEMPTION = D("700")  # §71.05(23): $700 personal exemption (Form 1 line 10a)
_WI_CAPITAL_GAIN_EXCLUSION = D(".30")  # §71.05(6)(b)9.


def _wi(tax_input: StateTaxInput, rules: StateRules) -> StatePolicyComputation:
    exclusion = _net_capital_gain(tax_input) * _WI_CAPITAL_GAIN_EXCLUSION
    wi_agi = tax_input.federal_agi - exclusion
    deduction = round_dollar(max(
        ZERO,
        _WI_STANDARD_DEDUCTION
        - _WI_STANDARD_DEDUCTION_RATE * max(ZERO, wi_agi - _WI_STANDARD_DEDUCTION_THRESHOLD),
    ))
    base = schedule_policy(
        tax_input,
        rules,
        subtractions=(
            (component("WI-LTCG", "Wisconsin 30% net capital gain exclusion", exclusion),)
            if exclusion else ()
        ),
        deduction=deduction,
        exemption=_WI_EXEMPTION,
    )
    base.deduction_type = "standard"
    _as_tax(base, round_dollar(base.tax_before_credits))
    base.warnings = (
        "WI 2026 tax brackets and sliding standard deduction computed from Wis. Stat. "
        "§71.06(2e)(bm) and §71.05(22)(dt) with BLS CPI-U; the Wisconsin Department of "
        "Revenue has not yet published the 2026 amounts (provisional).",
    )
    base.notes = (
        "Wisconsin 2026: 3.5%/4.4%/5.3%/7.65% schedule (2025 Act 15 brackets indexed), "
        "income-dependent standard deduction after the 30% capital gain exclusion, $700 "
        "exemption, whole-dollar tax.",
    )
    return base


POLICIES: dict[str, PolicyFn] = {
    "SC": _sc,
    "UT": _ut,
    "VT": _vt,
    "VA": _va,
    "WA": _wa,
    "WV": _wv,
    "WI": _wi,
}

PENDING: dict[str, str] = {}
