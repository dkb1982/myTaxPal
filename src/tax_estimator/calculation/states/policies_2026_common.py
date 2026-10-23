"""Shared helpers for source-reviewed 2026 state policies.

2026 policies cover the same narrow profile as the 2025 baseline: single, age 40,
no dependants, full-year resident employee with W-2 wages, ordinary/qualified
dividends and short/long-term capital gains, standard deduction. Year-specific
constants (deductions, exemptions, credit tables, thresholds) belong in each
state's policy function or its rules/states/2026/<st>.yaml, never in this module.

Each group module (policies_2026_g1 ... g6) exports:

- ``POLICIES``: state code -> policy function returning StatePolicyComputation.
- ``PENDING``: state code -> public-safe reason the state is not yet enabled
  (for example, the agency has not published its 2026 indexed amounts).

A policy in ``POLICIES`` is not public until coverage.py registers its evidence.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal

from tax_estimator.calculation.states.models import (
    StateAmountComponent,
    StateCreditComponent,
    StatePolicyComputation,
    StateRules,
    StateTaxInput,
)
from tax_estimator.calculation.states.policy_common import (
    CENT,
    ZERO,
    StatePolicyError,
    apply_nonrefundable_credit,
    calculate_flat_tax,
    calculate_rate_schedule,
    irc_net_capital_gain,
    require_policy_inputs,
)

PolicyFn = Callable[[StateTaxInput, StateRules], StatePolicyComputation]

__all__ = [
    "CENT", "ZERO", "PolicyFn", "StateAmountComponent", "StateCreditComponent",
    "StatePolicyComputation", "StatePolicyError", "StateRules", "StateTaxInput",
    "apply_nonrefundable_credit", "calculate_flat_tax", "calculate_rate_schedule",
    "component", "credit", "federal_eic_credit", "flat_policy", "irc_net_capital_gain",
    "require_policy_inputs", "round_dollar", "schedule_policy",
]


def round_dollar(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def component(component_id: str, name: str, amount: Decimal) -> StateAmountComponent:
    return StateAmountComponent(component_id, name, amount)


def credit(
    credit_id: str,
    name: str,
    available: Decimal,
    liability: Decimal,
    *,
    refundable: bool = False,
) -> StateCreditComponent:
    """A credit limited to remaining liability unless refundable."""
    available = max(ZERO, available)
    applied = available if refundable else min(available, max(ZERO, liability))
    return StateCreditComponent(credit_id, name, available, applied, refundable)


def _state_agi(
    start: Decimal,
    additions: tuple[StateAmountComponent, ...],
    subtractions: tuple[StateAmountComponent, ...],
) -> Decimal:
    return (
        start
        + sum((x.amount for x in additions), ZERO)
        - sum((x.amount for x in subtractions), ZERO)
    )


def schedule_policy(
    tax_input: StateTaxInput,
    rules: StateRules,
    *,
    starting_income: Decimal | None = None,
    additions: tuple[StateAmountComponent, ...] = (),
    subtractions: tuple[StateAmountComponent, ...] = (),
    deduction: Decimal | None = None,
    exemption: Decimal = ZERO,
    use_published_base: bool = True,
    credits: tuple[StateCreditComponent, ...] = (),
    surtax: Decimal = ZERO,
    notes: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    assumptions: tuple[str, ...] = (),
) -> StatePolicyComputation:
    """Graduated schedule from the 2026 YAML brackets.

    ``deduction`` defaults to the YAML standard deduction for the filing status.
    Credits passed in must already be limited against the right liability.
    """
    start = tax_input.federal_agi if starting_income is None else starting_income
    state_agi = _state_agi(start, additions, subtractions)
    deduction_amount = (
        rules.get_standard_deduction(tax_input.filing_status) if deduction is None else deduction
    )
    taxable = max(ZERO, state_agi - deduction_amount - exemption)
    schedule = calculate_rate_schedule(
        taxable,
        rules.get_brackets_for_status(tax_input.filing_status),
        use_published_base_tax=use_published_base,
    )
    return StatePolicyComputation(
        starting_income=start,
        state_agi=state_agi,
        additions=additions,
        subtractions=subtractions,
        deduction_type="standard" if deduction_amount else "none",
        deduction_amount=deduction_amount,
        personal_exemption=exemption,
        taxable_income=taxable,
        ordinary_taxable_income=taxable,
        ordinary_tax=schedule.tax,
        tax_before_credits=schedule.tax,
        surtax=surtax,
        credits=credits,
        marginal_rate=schedule.marginal_rate,
        bracket_breakdown=schedule.bracket_breakdown,
        notes=notes,
        warnings=warnings,
        assumptions=assumptions,
    )


def flat_policy(
    tax_input: StateTaxInput,
    rules: StateRules,
    *,
    starting_income: Decimal | None = None,
    additions: tuple[StateAmountComponent, ...] = (),
    subtractions: tuple[StateAmountComponent, ...] = (),
    deduction: Decimal | None = None,
    exemption: Decimal = ZERO,
    credits: tuple[StateCreditComponent, ...] = (),
    surtax: Decimal = ZERO,
    notes: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    assumptions: tuple[str, ...] = (),
) -> StatePolicyComputation:
    """Flat rate from the 2026 YAML ``flat_rate``."""
    if rules.flat_rate is None:
        raise StatePolicyError(f"{rules.state_code} 2026 rules have no flat rate")
    start = tax_input.federal_agi if starting_income is None else starting_income
    state_agi = _state_agi(start, additions, subtractions)
    deduction_amount = (
        rules.get_standard_deduction(tax_input.filing_status) if deduction is None else deduction
    )
    taxable = max(ZERO, state_agi - deduction_amount - exemption)
    tax = calculate_flat_tax(taxable, rules.flat_rate)
    return StatePolicyComputation(
        starting_income=start,
        state_agi=state_agi,
        additions=additions,
        subtractions=subtractions,
        deduction_type="standard" if deduction_amount else "none",
        deduction_amount=deduction_amount,
        personal_exemption=exemption,
        taxable_income=taxable,
        ordinary_taxable_income=taxable,
        ordinary_tax=tax,
        tax_before_credits=tax,
        surtax=surtax,
        credits=credits,
        marginal_rate=rules.flat_rate,
        notes=notes,
        warnings=warnings,
        assumptions=assumptions,
    )


def federal_eic_credit(
    tax_input: StateTaxInput,
    credit_id: str,
    name: str,
    percentage: Decimal,
    liability: Decimal,
    *,
    refundable: bool,
    childless_agi_limit: Decimal,
) -> tuple[tuple[StateCreditComponent, ...], tuple[str, ...]]:
    """A state EIC computed as a percentage of the federal EIC.

    ``childless_agi_limit`` is the 2026 federal no-qualifying-child EIC
    completed-phaseout AGI for a single filer; above it no warning is needed.
    The credit is only applied when the user asserted federal EIC eligibility.
    """
    if tax_input.federal_eitc_eligibility_asserted is False:
        return (), ()
    if tax_input.federal_eitc_eligibility_asserted is None:
        if tax_input.federal_earned_income_credit is not None:
            return (), ()
        if not tax_input.num_dependents and tax_input.federal_agi > childless_agi_limit:
            return (), ()
        return (), (
            f"{name} omitted because federal EITC eligibility was not affirmatively asserted.",
        )
    require_policy_inputs(tax_input, "federal_earned_income_credit")
    assert tax_input.federal_earned_income_credit is not None
    amount = tax_input.federal_earned_income_credit * percentage
    return (credit(credit_id, name, amount, liability, refundable=refundable),), ()
