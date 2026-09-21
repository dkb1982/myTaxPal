"""Source-reviewed 2025 refundable credits for CA, DC, and MN.

This module is deliberately a post-policy hook: the state policy retains its
published income-tax computation and this adds only independently refundable
credits.  It supports the reviewed full-year resident, single, age-40,
no-dependent baseline; callers outside that contract must use the generic
unvalidated path.

Sources:
* DC 2025 D-40 Instructions, Schedule ELC, Section C (p. 25 printed / 26 PDF):
  https://otr.cfo.dc.gov/sites/default/files/dc/sites/otr/publication/attachments/2025_D40_Book_082026_v1.pdf
* Minnesota DOR, Working Family Credit (2025):
  https://www.revenue.state.mn.us/working-family-credit
* California FTB 2025 FTB 3514: exact CalEITC values are supplied by the
  official Part II lookup table through ``CA_EITC_TABLE`` below.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from tax_estimator.calculation.states.ca_eitc_2025 import CA_EITC_NO_CHILD_TABLE_2025
from tax_estimator.calculation.states.models import (
    StateCreditComponent,
    StatePolicyComputation,
    StateRules,
    StateTaxInput,
)
from tax_estimator.calculation.states.policy_common import StatePolicyError, require_policy_inputs

D = Decimal
ZERO = D("0")


def _supported(t: StateTaxInput, r: StateRules) -> bool:
    return (
        t.baseline_profile_supported
        and t.tax_year == 2025
        and r.tax_year == 2025
        and t.filing_status == "single"
        and t.taxpayer_age_at_year_end == 40
        and t.is_resident
        and not t.num_dependents
        and not t.can_be_claimed_as_dependent
    )


def _omit_for_unknown_eligibility(
    t: StateTaxInput, c: StatePolicyComputation, state_name: str, credit_name: str,
) -> bool:
    """Return True when no credit can safely be calculated from supplied facts."""
    if t.federal_eitc_eligibility_asserted is True:
        return False
    if t.federal_eitc_eligibility_asserted is None:
        c.warnings += (
            f"{state_name} {credit_name} omitted: claimant eligibility is not established.",
        )
    return True


def _refundable(credit_id: str, name: str, amount: Decimal) -> StateCreditComponent:
    amount = max(ZERO, amount).quantize(D(".01"), rounding=ROUND_HALF_UP)
    return StateCreditComponent(credit_id, name, amount, amount, True)


def _dc_childless_eic(t: StateTaxInput) -> Decimal:
    """2025 D-40 Schedule ELC Section C, childless worksheet.

    The reviewed model has wages as its sole earned-income input.  Federal AGI
    is the worksheet comparison amount in the direct-securities baseline.
    """
    earned = max(ZERO, t.wages)
    income = max(earned, t.federal_agi)
    if income > D("30941"):
        return ZERO
    tentative = earned * D(".0765") if earned < D("8484") else D("649")
    if income >= D("23288"):
        tentative -= (income - D("23288")) * D(".0848")
    return max(ZERO, tentative)


def _mn_working_family_credit(t: StateTaxInput) -> Decimal:
    """2025 Schedule M1CWFC lines 2–15 for no qualifying children."""
    # The schedule rounds return entries to whole dollars.  The reviewed profile
    # has wages as its only earned-income component and federal AGI as Form M1
    # income before the ordinary state deductions.
    earned = min(D("9480"), max(ZERO, t.wages))
    tentative = (earned * D(".04")).quantize(D("1"), rounding=ROUND_HALF_UP)
    phaseout_income = max(t.federal_agi, t.wages)
    reduction = max(ZERO, phaseout_income - D("31950")) * D(".12")
    return max(ZERO, tentative - reduction.quantize(D("1"), rounding=ROUND_HALF_UP))


def _investment_income(t: StateTaxInput) -> Decimal:
    """Known securities investment income for the constrained input contract."""
    require_policy_inputs(t, "net_short_term_gains", "net_long_term_gains")
    # A net capital loss does not offset dividends for this eligibility test.
    return t.interest + t.dividends + max(ZERO, t.net_short_term_gains + t.net_long_term_gains)


def _ca_eitc_table_credit(amount: Decimal) -> Decimal:
    """Return an exact official FTB 3514 no-child table amount, never interpolated."""
    whole_dollars = int(amount.quantize(D("1"), rounding=ROUND_HALF_UP))
    for lower, upper, credit in CA_EITC_NO_CHILD_TABLE_2025:
        if lower <= whole_dollars <= upper:
            return D(credit)
    return ZERO


def _ca_caleitc(t: StateTaxInput) -> Decimal:
    """FTB 3514 Step 6, Parts I–III for a filer with no qualifying children."""
    earned_credit = _ca_eitc_table_credit(max(ZERO, t.wages))
    if earned_credit == ZERO:
        return ZERO
    if t.federal_agi == t.wages or t.federal_agi < D("4661"):
        return earned_credit
    return min(earned_credit, _ca_eitc_table_credit(max(ZERO, t.federal_agi)))


def apply_ca_dc_mn_credits(
    t: StateTaxInput, r: StateRules, c: StatePolicyComputation,
) -> StatePolicyComputation:
    """Append available 2025 CA/DC/MN refundable credits to a state policy."""
    if r.state_code not in {"CA", "DC", "MN"}:
        return c
    if not _supported(t, r):
        raise StatePolicyError("CA/DC/MN 2025 credits require the supported resident profile")
    require_policy_inputs(t, "federal_agi")

    if r.state_code == "DC":
        if max(t.wages, t.federal_agi) > D("30941"):
            return c
        investment_income = _investment_income(t)
        if investment_income > D("11950"):
            c.notes += (
                "DC childless earned-income credit is unavailable above the "
                "$11,950 investment-income limit.",
            )
            return c
        if _omit_for_unknown_eligibility(t, c, "DC", "childless earned-income credit"):
            return c
        amount = _dc_childless_eic(t)
        if amount:
            c.credits += (_refundable("DC-EIC", "DC childless earned-income credit", amount),)
        c.notes += (
            "DC childless EIC follows 2025 D-40 Schedule ELC Section C; the amount is refundable.",
        )
        return c

    if r.state_code == "MN":
        if max(t.wages, t.federal_agi) >= D("35109"):
            # $379 less 12% of income above $31,950 reaches zero at $35,109.
            return c
        investment_income = _investment_income(t)
        if investment_income > D("11950"):
            c.notes += (
                "Minnesota Working Family Credit omitted: investment income above $11,950 "
                "requires an unsupported federal worksheet.",
            )
            return c
        if _omit_for_unknown_eligibility(t, c, "Minnesota", "Working Family Credit"):
            return c
        amount = _mn_working_family_credit(t)
        if amount:
            c.credits += (_refundable("MN-WFC", "Minnesota Working Family Credit", amount),)
        c.notes += ("MN Working Family Credit is 4% of reviewed earned income, capped at $379.",)
        return c

    # FTB 3514 Step 6 also has claimant, age, residency, identification, and
    # investment-income requirements.  The bounded profile establishes age and
    # residency; explicit assertion represents the remaining legal facts.
    if max(t.wages, t.federal_agi) >= D("32901"):
        return c
    investment_income = _investment_income(t)
    if investment_income > D("4814"):
        c.notes += ("California CalEITC is unavailable above the $4,814 investment-income limit.",)
        return c
    if _omit_for_unknown_eligibility(t, c, "California", "CalEITC"):
        return c
    amount = _ca_caleitc(t)
    if amount:
        c.credits += (_refundable("CA-EITC", "California earned income tax credit", amount),)
    c.notes += ("California CalEITC uses the exact 2025 FTB 3514 no-child lookup table.",)
    return c
