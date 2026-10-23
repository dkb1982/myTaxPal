"""Source-reviewed 2026 state policies, group 2 (DC, GA, HI, ID, IL, IN, IA, KS).

See policies_2026_common for the supported profile (single, age 40, no
dependants, full-year resident employee, standard deduction, wages plus
dividends and direct capital gains). Each policy cites its primary sources in
rules/states/2026/<st>.yaml ``references``; year-specific constants that are
not plain YAML brackets/deductions live here with the statute or publication
that fixes them.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal

from tax_estimator.calculation.states.policies_2026_common import (
    ZERO,
    PolicyFn,
    StateCreditComponent,
    StatePolicyComputation,
    StatePolicyError,
    StateRules,
    StateTaxInput,
    calculate_flat_tax,
    calculate_rate_schedule,
    credit,
    federal_eic_credit,
    flat_policy,
    require_policy_inputs,
    round_dollar,
    schedule_policy,
)

D = Decimal

# Rev. Proc. 2025-32 sec. 4.06: 2026 federal EIC, no qualifying child, single
# filer, completed-phaseout AGI. Above it no state EIC warning is needed.
FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026 = D("19540")


def _state_eic(
    t: StateTaxInput, credit_id: str, name: str, pct: Decimal, liability: Decimal,
) -> tuple[tuple[StateCreditComponent, ...], tuple[str, ...]]:
    """Refundable percentage-of-federal EIC, applied only when eligibility is asserted."""
    return federal_eic_credit(
        t, credit_id, name, pct, liability,
        refundable=True, childless_agi_limit=FEDERAL_CHILDLESS_EIC_AGI_LIMIT_2026,
    )


# ---------------------------------------------------------------------------
# District of Columbia
# ---------------------------------------------------------------------------

# D.C. Law 26-189 (FY2027 Budget Support Act, Subtitle VII-I) sets the 2026
# basic standard deduction at $15,000 increased by the cost-of-living adjustment
# with base year 2025; for 2026 the "preceding calendar year" is the base year,
# so the adjustment is zero. The YAML carries the $15,000.
# The DC childless EITC (Schedule ELC Section C) uses DC-indexed thresholds that
# OTR has not published for 2026 (2025: credit fully phased out at $30,941).
# Below this conservative ceiling a childless EITC could exist in 2026.
_DC_CHILDLESS_EIC_REVIEW_CEILING_2026 = D("34000")


def _dc(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    warnings: tuple[str, ...] = (
        "DC 2026 standard deduction $15,000 computed from D.C. Code § 47-1801.04(3A) "
        "as amended by D.C. Law 26-189 (zero cost-of-living adjustment in the base-year "
        "2025 formula); OTR has not yet published it (provisional).",
    )
    income = max(t.wages, t.federal_agi)
    if income <= _DC_CHILDLESS_EIC_REVIEW_CEILING_2026:
        if t.federal_eitc_eligibility_asserted is True:
            raise StatePolicyError(
                "DC 2026 childless earned income tax credit thresholds are not yet "
                "published; this income level is not supported for 2026"
            )
        if t.federal_eitc_eligibility_asserted is None:
            warnings += (
                "DC 2026 childless earned income tax credit omitted: claimant eligibility "
                "is not established and 2026 DC thresholds are not yet published.",
            )
    return schedule_policy(
        t, r,
        notes=(
            "DC 2026 tax uses the D.C. Code § 47-1806.03(a)(10) schedule and the DC basic "
            "standard deduction (no personal exemption); dividends and capital gains are "
            "taxed as ordinary income.",
        ),
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Georgia
# ---------------------------------------------------------------------------

def _ga(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    """O.C.G.A. § 48-7-20(a.1) 4.99% and § 48-7-27(a)(1)(B)(ii) $15,000 (HB 463, 2026)."""
    warnings: tuple[str, ...] = ()
    if t.federal_agi < D("20000"):
        warnings += (
            "Georgia 2026 low income credit (federal AGI under $20,000) is not modelled; "
            "the estimate may slightly overstate Georgia tax.",
        )
    return flat_policy(
        t, r,
        notes=(
            "Georgia 2026 flat 4.99% of federal AGI less the $15,000 standard deduction "
            "(HB 463, 2026); the one-time surplus refund credit relates to earlier tax "
            "years and is not included.",
        ),
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Hawaii
# ---------------------------------------------------------------------------

# HRS § 235-54 personal exemption (unchanged for 2026).
_HI_PERSONAL_EXEMPTION_2026 = D("1144")
# HRS § 235-51(f) alternative capital-gains tax: 7.25% with at least $48,000 of
# single taxable income kept in the regular schedule (brackets unchanged in 2026).
_HI_CAPITAL_GAIN_RATE = D(".0725")
_HI_CAPITAL_GAIN_FLOOR = D("48000")
_HI_EITC_RATE = D(".40")
# Form N-311 food/excise credit income table (single, one exemption).
_HI_FOOD_TABLE = (
    (D("15000"), D("220")), (D("20000"), D("200")), (D("25000"), D("170")),
    (D("30000"), D("140")), (D("40000"), D("110")),
)


def _hi(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    require_policy_inputs(t, "net_short_term_gains", "net_long_term_gains")
    if (t.net_short_term_gains or ZERO) < 0 or (t.net_long_term_gains or ZERO) < 0:
        raise StatePolicyError("Hawaii signed capital-loss combinations are not source-supported")
    deduction = r.get_standard_deduction(t.filing_status)
    exemption = _HI_PERSONAL_EXEMPTION_2026
    taxable = max(ZERO, t.federal_agi - deduction - exemption)
    brackets = r.get_brackets_for_status(t.filing_status)
    regular = calculate_rate_schedule(taxable, brackets, use_published_base_tax=True)
    lt = min(max(ZERO, t.net_long_term_gains or ZERO), taxable)
    preferential = max(ZERO, min(lt, taxable - _HI_CAPITAL_GAIN_FLOOR))
    ordinary = taxable - preferential
    ordinary_schedule = calculate_rate_schedule(ordinary, brackets, use_published_base_tax=True)
    alternative = ordinary_schedule.tax + preferential * _HI_CAPITAL_GAIN_RATE
    if regular.tax <= alternative:
        selected = regular.tax
        ordinary_tax, preferential_tax = regular.tax, ZERO
        ordinary_taxable, preferential_taxable = taxable, ZERO
        breakdown, marginal = regular.bracket_breakdown, regular.marginal_rate
    else:
        selected = alternative
        ordinary_tax, preferential_tax = ordinary_schedule.tax, preferential * _HI_CAPITAL_GAIN_RATE
        ordinary_taxable, preferential_taxable = ordinary, preferential
        breakdown, marginal = ordinary_schedule.bracket_breakdown, _HI_CAPITAL_GAIN_RATE
    eitc, warnings = _state_eic(
        t, "HI-EITC", "Hawaii earned income tax credit", _HI_EITC_RATE, selected,
    )
    food_amount = next((amount for limit, amount in _HI_FOOD_TABLE if t.federal_agi < limit), ZERO)
    if food_amount:
        warnings += (
            "Hawaii 2026 food/excise tax credit omitted: Form N-311 requires physical "
            "presence for more than nine months and not being confined for the entire "
            "year; these eligibility facts are not supplied. The income table alone would "
            f"allow ${food_amount} per qualified person.",
        )
    return StatePolicyComputation(
        starting_income=t.federal_agi,
        state_agi=t.federal_agi,
        deduction_type="standard",
        deduction_amount=deduction,
        personal_exemption=exemption,
        taxable_income=taxable,
        ordinary_taxable_income=ordinary_taxable,
        preferential_taxable_income=preferential_taxable,
        ordinary_tax=ordinary_tax,
        preferential_tax=preferential_tax,
        tax_before_credits=selected,
        credits=eitc,
        marginal_rate=marginal,
        bracket_breakdown=breakdown,
        notes=(
            "Hawaii 2026: $8,000 standard deduction (Act 46, SLH 2024) and $1,144 exemption; "
            "lower of regular tax and the 7.25% capital-gain alternative applied; uses the "
            "published rate-schedule base amounts rather than the legal tax table.",
        ),
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Idaho
# ---------------------------------------------------------------------------

# Idaho Code § 63-3024(2)(a),(3): 5.3% of taxable income over $2,500 indexed by
# CPI-U(prior calendar year) / CPI-U(1998). 2026: 2,500 x 321.943 / 163.0 =
# 4,937.78 -> $4,938 (BLS CPI-U annual averages; 2025 check: 313.689 -> $4,811).
_ID_ZERO_BRACKET_2026 = D("4938")
# Idaho Code § 63-3024A(1): $155 per person for tax year 2025 and thereafter.
_ID_FOOD_TAX_CREDIT = D("155")


def _id(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    if r.flat_rate is None:
        raise StatePolicyError("Idaho 2026 rules have no flat rate")
    # Idaho taxable income = federal AGI less the federal standard deduction
    # (HB 559, 2026: IRC conformity as of Jan 1 2026); no Idaho adjustments apply.
    taxable = max(ZERO, t.federal_taxable_income)
    tax = calculate_flat_tax(max(ZERO, taxable - _ID_ZERO_BRACKET_2026), r.flat_rate)
    food = credit(
        "ID-FOOD", "Idaho Food Tax Credit", _ID_FOOD_TAX_CREDIT, tax, refundable=True,
    )
    return StatePolicyComputation(
        starting_income=taxable,
        state_agi=taxable,
        taxable_income=taxable,
        ordinary_taxable_income=taxable,
        ordinary_tax=tax,
        tax_before_credits=tax,
        credits=(food,),
        marginal_rate=r.flat_rate if taxable > _ID_ZERO_BRACKET_2026 else ZERO,
        assumptions=(
            "Idaho Food Tax Credit assumes 12 qualifying resident months with no federal "
            "food-assistance benefits, incarceration, or unlawful U.S. residence; the "
            "taxpayer is not claimable as another person's dependent.",
        ),
        notes=(
            "Idaho 2026: 5.3% of Idaho taxable income over the first $4,938; the $155 "
            "refundable Food Tax Credit is separate from gross Idaho income tax.",
        ),
        warnings=(
            "ID 2026 zero-rate threshold $4,938 computed from Idaho Code § 63-3024(3) and "
            "the BLS 2025 CPI-U annual average; Idaho State Tax Commission has not yet "
            "published it (provisional).",
        ),
    )


# ---------------------------------------------------------------------------
# Illinois
# ---------------------------------------------------------------------------

# 35 ILCS 5/204(g): no exemption when federal AGI exceeds $250,000 (single).
_IL_EXEMPTION_AGI_LIMIT = D("250000")
_IL_EIC_RATE = D(".20")


def _il(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    allowed = t.federal_agi <= _IL_EXEMPTION_AGI_LIMIT
    exemption = r.exemption.personal_amount if allowed else ZERO
    base = flat_policy(
        t, r,
        exemption=exemption,
        notes=(
            "Illinois 2026: 4.95% of base income less the $2,925 exemption allowance, "
            "which is unavailable when federal AGI exceeds $250,000.",
        ),
    )
    base.credits, base.warnings = _state_eic(
        t, "IL-EIC", "Illinois earned income credit", _IL_EIC_RATE, base.tax_before_credits,
    )
    return base


# ---------------------------------------------------------------------------
# Indiana
# ---------------------------------------------------------------------------

_IN_EIC_RATE = D(".10")


def _in(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    base = flat_policy(
        t, r,
        exemption=r.exemption.personal_amount,
        notes=(
            "Indiana 2026 state adjusted gross income tax 2.95% after the $1,000 personal "
            "exemption; county income taxes are separate and not included.",
        ),
    )
    base.credits, base.warnings = _state_eic(
        t, "IN-EITC", "Indiana earned income tax credit", _IN_EIC_RATE, base.tax_before_credits,
    )
    return base


# ---------------------------------------------------------------------------
# Iowa
# ---------------------------------------------------------------------------

# Iowa Code § 422.12(1)(a)(1): $40 personal exemption credit; § 422.12B: 15%.
_IA_PERSONAL_CREDIT = D("40")
_IA_EIC_RATE = D(".15")


def _ia(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    base = flat_policy(
        t, r,
        starting_income=t.federal_taxable_income,
        deduction=ZERO,
        notes=(
            "Iowa 2026: flat 3.8% of federal taxable income (rolling IRC conformity); "
            "the local school district surtax is not included.",
        ),
    )
    personal = credit(
        "IA-PERSONAL", "Personal exemption credit", _IA_PERSONAL_CREDIT, base.tax_before_credits,
    )
    eic, warnings = _state_eic(
        t, "IA-EIC", "Iowa earned income credit", _IA_EIC_RATE,
        base.tax_before_credits - personal.amount_applied,
    )
    base.credits = (personal, *eic)
    base.warnings = warnings
    return base


# ---------------------------------------------------------------------------
# Kansas
# ---------------------------------------------------------------------------

_KS_TABLE_LIMIT = D("100000")
_KS_TABLE_WIDTH = D("50")
_KS_EIC_RATE = D(".17")


def _ks_table_tax(taxable: Decimal, r: StateRules) -> Decimal:
    """K-40 tax table: $50 rows "at least lo, not more than hi", tax at the row midpoint.

    Verified against every 2025 table row ($1,000-$100,000; same 2026 rates and
    $23,000 threshold); the table starts at $26.
    """
    whole = round_dollar(taxable)
    if whole < D("26"):
        return ZERO
    hi = (whole / _KS_TABLE_WIDTH).to_integral_value(rounding=ROUND_CEILING) * _KS_TABLE_WIDTH
    midpoint = (hi - D("49") + hi) / 2
    schedule = calculate_rate_schedule(
        midpoint, r.get_brackets_for_status("single"), use_published_base_tax=True,
    )
    return round_dollar(schedule.tax)


def _ks(t: StateTaxInput, r: StateRules) -> StatePolicyComputation:
    """K.S.A. 79-32,110 (5.2%/5.58%), 79-32,119 ($3,605), 79-32,121 ($9,160)."""
    base = schedule_policy(t, r, exemption=r.exemption.personal_amount)
    notes = (
        "Kansas 2026 rates unchanged: no SB 269 (K.S.A. 79-32,110c) reduction for tax "
        "year 2026 (KDOR Notice 25-06).",
    )
    if ZERO < base.taxable_income <= _KS_TABLE_LIMIT:
        table = _ks_table_tax(base.taxable_income, r)
        base.ordinary_tax = table
        base.tax_before_credits = table
        notes += (
            "Kansas $50-row tax-table midpoint convention used (taxable income to $100,000).",
        )
    base.notes = notes
    base.credits, base.warnings = _state_eic(
        t, "KS-EIC", "Kansas earned income credit", _KS_EIC_RATE, base.tax_before_credits,
    )
    return base


POLICIES: dict[str, PolicyFn] = {
    "DC": _dc,
    "GA": _ga,
    "HI": _hi,
    "ID": _id,
    "IL": _il,
    "IN": _in,
    "IA": _ia,
    "KS": _ks,
}

PENDING: dict[str, str] = {}
