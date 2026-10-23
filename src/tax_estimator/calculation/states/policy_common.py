"""Shared helpers for source-reviewed 2025 state tax policies."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal

from tax_estimator.calculation.states.models import (
    RateScheduleResult,
    StateBracket,
    StateBracketBreakdown,
    StatePolicyComputation,
    StateRules,
    StateTaxInput,
    StateTaxResult,
)

ZERO = Decimal(0)
CENT = Decimal("0.01")


class StatePolicyError(ValueError):
    """Raised when a reviewed policy cannot produce a supported result."""


def calculate_flat_tax(taxable_income: Decimal, rate: Decimal) -> Decimal:
    """Calculate a nonnegative flat-rate base tax without premature rounding."""
    return max(ZERO, taxable_income) * rate


def calculate_rate_schedule(
    taxable_income: Decimal,
    brackets: Sequence[StateBracket],
    *,
    use_published_base_tax: bool = False,
) -> RateScheduleResult:
    """Apply a progressive schedule, optionally honoring its published base tax."""
    if taxable_income <= 0:
        return RateScheduleResult(ZERO, (), ZERO)

    ordered = sorted(brackets, key=lambda bracket: bracket.income_from)
    if not ordered:
        raise StatePolicyError("A rate schedule requires at least one bracket")

    breakdown: list[StateBracketBreakdown] = []
    direct_tax = ZERO
    marginal_rate = ZERO
    active_bracket: StateBracket | None = None

    for bracket in ordered:
        if taxable_income <= bracket.income_from:
            break
        upper = bracket.income_to if bracket.income_to is not None else taxable_income
        income_in_bracket = max(ZERO, min(taxable_income, upper) - bracket.income_from)
        if income_in_bracket <= 0:
            continue
        tax_in_bracket = income_in_bracket * bracket.rate
        breakdown.append(
            StateBracketBreakdown(
                bracket_id=bracket.bracket_id,
                bracket_min=bracket.income_from,
                bracket_max=bracket.income_to,
                rate=bracket.rate,
                income_in_bracket=income_in_bracket,
                tax_in_bracket=tax_in_bracket,
            )
        )
        direct_tax += tax_in_bracket
        marginal_rate = bracket.rate
        active_bracket = bracket
        if bracket.income_to is None or taxable_income <= bracket.income_to:
            break

    if active_bracket is None:
        raise StatePolicyError("Taxable income does not fall within the rate schedule")

    published_adjustment = ZERO
    tax = direct_tax
    if use_published_base_tax:
        tax = (
            active_bracket.base_tax
            + (taxable_income - active_bracket.income_from) * active_bracket.rate
        )
        published_adjustment = tax - direct_tax
        if published_adjustment and breakdown:
            breakdown[-1] = replace(
                breakdown[-1],
                tax_in_bracket=breakdown[-1].tax_in_bracket + published_adjustment,
            )

    return RateScheduleResult(
        tax=tax,
        bracket_breakdown=tuple(breakdown),
        marginal_rate=marginal_rate,
        published_base_adjustment=published_adjustment,
    )


def apply_nonrefundable_credit(
    available: Decimal, offsettable_tax: Decimal
) -> tuple[Decimal, Decimal]:
    """Return the applied credit and remaining legally offsettable tax."""
    applied = min(max(ZERO, available), max(ZERO, offsettable_tax))
    return applied, max(ZERO, offsettable_tax - applied)


def irc_net_capital_gain(net_short_term_gains: Decimal, net_long_term_gains: Decimal) -> Decimal:
    """Return IRC net capital gain; qualified dividends are deliberately absent."""
    return max(
        ZERO,
        min(net_long_term_gains, net_short_term_gains + net_long_term_gains),
    )


# ---------------------------------------------------------------------------
# 2025 state treatment of the federal IRC section 199A (QBI) deduction.
#
# Only states whose computation starts from *federal taxable income* (Form 1040
# line 15) inherit the QBI deduction; federal-AGI starting points never see it.
# Each decision below was checked against the state's 2025 form, instructions or
# statute (retrieved 2026-10-23):
#
# CO  addback_high_agi  Starts from federal taxable income, so QBI is kept,
#     except C.R.S. 39-22-104(3)(o) adds back the full section 199A deduction for
#     tax years 2021-2025 when federal AGI exceeds $500,000 on a single return or
#     $1,000,000 on a joint return (taxpayers required to file Schedule F are
#     exempt; farm income is not modelled). 2025 DR 0104 line 3 "Qualified
#     Business Income Deduction Addback". HB25B-1001 removed the 2026 sunset.
#     https://colorado.public.law/statutes/crs_39-22-104
#     https://tax.colorado.gov/sites/tax/files/documents/DR0104_2025.pdf
#     https://leg.colorado.gov/bills/HB25B-1001
# ID  conforms  2025 Form 40 starts from federal AGI (line 7) and itself
#     subtracts the federal QBI deduction (line 18 = Form 1040 lines 13a+13b), so
#     federal taxable income including QBI is the right Idaho base.
#     https://tax.idaho.gov/wp-content/uploads/forms/EFO00089/EFO00089_03-02-2026.pdf
# IA  conforms  Starting point is federal taxable income with rolling IRC
#     conformity; no section 199A modification is listed for 2025.
#     https://revenue.iowa.gov/taxes/tax-guidance/individual-income-tax/1040-expanded-instructions/conformity-irc
# MT  addback  MCA 15-30-2120(2)(i) adds back "an amount equal to the qualified
#     business income deduction claimed" to federal taxable income (2025 Form 2
#     Schedule I, other additions).
#     https://archive.legmt.gov/bills/mca/title_0150/chapter_0300/part_0210/section_0200/0150-0300-0210-0200.html
# NM  disallowed  2025 PIT-1 starts from federal AGI (line 9) and subtracts only
#     the federal standard/itemized deduction (line 12); there is no QBI line, so
#     the base is federal taxable income *before* QBI.
#     https://taxsim.nber.org/historical_state_tax_forms/NM/2025/2025%20PIT%20Packet_Final.pdf
#     (archived copy of the NM TRD 2025 PIT packet)
# ND  conforms  ND-1 starts from federal taxable income, which "perpetually
#     conforms"; no section 199A addition.
#     https://www.tax.nd.gov/sites/www/files/documents/forms/individual/2025-iit/2025-individual-income-tax-booklet.pdf
# SC  addback  2025 SC1040 instructions, line e other additions: "Add back the
#     qualified business income deduction under IRC Section 199A."
#     https://dor.sc.gov/sites/dor/files/forms/SC1040Instr_2025.pdf
# ---------------------------------------------------------------------------
QBI_CONFORMITY_2025: dict[str, str] = {
    "CO": "addback_high_agi",
    "ID": "conforms",
    "IA": "conforms",
    "MT": "addback",
    "NM": "disallowed",
    "ND": "conforms",
    "SC": "addback",
}

CO_QBI_ADDBACK_AGI_THRESHOLD = {"joint": Decimal("1000000"), "other": Decimal("500000")}


def state_qbi_addback_2025(tax_input: StateTaxInput, state_code: str) -> Decimal:
    """Return the federal QBI deduction a 2025 state adds back to federal taxable income.

    Returns zero for conforming states, for states whose starting point is not
    federal taxable income, and whenever no federal QBI deduction was claimed.
    "disallowed" states start from pre-QBI income, which is arithmetically the
    same add-back; callers decide whether to present it as a modification.
    """
    qbi = max(ZERO, tax_input.federal_qbi_deduction)
    if not qbi:
        return ZERO
    treatment = QBI_CONFORMITY_2025.get(state_code.upper())
    if treatment in {"addback", "disallowed"}:
        return qbi
    if treatment == "addback_high_agi":
        key = "joint" if tax_input.filing_status == "mfj" else "other"
        if tax_input.federal_agi > CO_QBI_ADDBACK_AGI_THRESHOLD[key]:
            return qbi
    return ZERO


def require_policy_inputs(tax_input: StateTaxInput, *field_names: str) -> None:
    """Reject a supported-profile call whose required pipeline detail is absent."""
    missing = [name for name in field_names if getattr(tax_input, name) is None]
    if missing:
        raise StatePolicyError(
            "Reviewed state policy requires known input(s): " + ", ".join(missing)
        )


def build_state_result(
    tax_input: StateTaxInput,
    rules: StateRules,
    computation: StatePolicyComputation,
) -> StateTaxResult:
    """Validate a policy computation and publish one reconciled state result."""
    expected_state_agi = (
        computation.starting_income
        + sum((item.amount for item in computation.additions), ZERO)
        - sum((item.amount for item in computation.subtractions), ZERO)
    )
    if computation.state_agi != expected_state_agi:
        raise StatePolicyError(
            f"State AGI does not reconcile: {computation.state_agi} != {expected_state_agi}"
        )

    component_tax = (
        computation.ordinary_tax + computation.preferential_tax + computation.other_base_tax
    )
    if computation.tax_before_credits != component_tax:
        raise StatePolicyError(
            "Tax before credits does not reconcile to ordinary/preferential/other base tax"
        )

    ordinary_tax = computation.ordinary_tax.quantize(CENT, rounding=ROUND_HALF_UP)
    preferential_tax = computation.preferential_tax.quantize(CENT, rounding=ROUND_HALF_UP)
    other_base_tax = computation.other_base_tax.quantize(CENT, rounding=ROUND_HALF_UP)
    tax_before_credits = ordinary_tax + preferential_tax + other_base_tax
    surtax = computation.surtax.quantize(CENT, rounding=ROUND_HALF_UP)
    recapture = computation.recapture.quantize(CENT, rounding=ROUND_HALF_UP)

    normalized_credits = tuple(
        replace(
            credit,
            amount_available=credit.amount_available.quantize(CENT, rounding=ROUND_HALF_UP),
            amount_applied=credit.amount_applied.quantize(CENT, rounding=ROUND_HALF_UP),
        )
        for credit in computation.credits
    )
    nonrefundable = ZERO
    refundable = ZERO
    for credit in normalized_credits:
        if credit.amount_available < 0 or credit.amount_applied < 0:
            raise StatePolicyError(f"Credit {credit.credit_id} cannot be negative")
        if credit.amount_applied > credit.amount_available:
            raise StatePolicyError(
                f"Credit {credit.credit_id} applied amount exceeds available amount"
            )
        if credit.is_refundable:
            refundable += credit.amount_applied
        else:
            nonrefundable += credit.amount_applied

    precredit_liability = tax_before_credits + surtax + recapture
    if nonrefundable > max(ZERO, precredit_liability):
        raise StatePolicyError("Nonrefundable credits exceed total positive liability")

    total_tax = precredit_liability - nonrefundable - refundable
    effective_rate = (
        (total_tax / computation.state_agi).quantize(Decimal("0.0001"))
        if computation.state_agi > 0
        else ZERO
    )

    return StateTaxResult(
        state_code=rules.state_code,
        state_name=rules.state_name,
        tax_year=rules.tax_year,
        filing_status=tax_input.filing_status,
        has_income_tax=rules.has_income_tax,
        tax_type=computation.tax_type_override or rules.tax_type,
        gross_income=tax_input.federal_agi,
        starting_point=rules.starting_point.value,
        starting_income=computation.starting_income,
        state_agi=computation.state_agi,
        additions=list(computation.additions),
        subtractions=list(computation.subtractions),
        deduction_type=computation.deduction_type,
        deduction_amount=computation.deduction_amount,
        personal_exemption=computation.personal_exemption,
        dependent_exemption=computation.dependent_exemption,
        taxable_income=computation.taxable_income,
        ordinary_taxable_income=computation.ordinary_taxable_income,
        preferential_taxable_income=computation.preferential_taxable_income,
        tax_before_credits=tax_before_credits,
        ordinary_tax=ordinary_tax,
        preferential_tax=preferential_tax,
        other_base_tax=other_base_tax,
        surtax=surtax,
        recapture=recapture,
        total_tax=total_tax,
        credits=nonrefundable + refundable,
        nonrefundable_credits=nonrefundable,
        refundable_credits=refundable,
        credit_components=list(normalized_credits),
        net_tax=total_tax,
        effective_rate=effective_rate,
        marginal_rate=computation.marginal_rate,
        bracket_breakdown=list(computation.bracket_breakdown),
        is_resident=tax_input.is_resident,
        warnings=list(computation.warnings),
        notes=list(computation.notes),
        assumptions=list(computation.assumptions),
    )
