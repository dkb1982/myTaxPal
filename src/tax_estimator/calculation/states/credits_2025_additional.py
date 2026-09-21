"""Additional automatic credits for the single/age-40 2025 resident policies.

CO: DR0104CR lines3–6, 2025 Book104 (50% refundable federal EIC).
https://tax.colorado.gov/sites/tax/files/documents/Book104_2025.pdf
IL: 2025 Schedule IL-E/EITC and Pub132 (20% refundable federal EIC).
https://tax.illinois.gov/research/publications/pubs/illinois-earned-income-tax-credit-information.html
IA: 2025 expanded instructions, refundable federal EIC ×15%.
https://revenue.iowa.gov/taxes/frequently-asked-questions/individual-income
KS: 2025 K40 line17/EIC worksheet and line22 (17%, refundable excess).
https://www.ksrevenue.gov/incomebook25.html
LA: 2025 IT540 instructions line16 (5% refundable federal EIC).
https://dam.ldr.la.gov/taxforms/IT540i-WEB-2025-Revised-7-26.pdf
MA: Form1 lines27/29 worksheets and MGL62 §5 (NTS/limited-income relief).
https://www.mass.gov/doc/2025-form-1-instructions/download
https://malegislature.gov/Laws/GeneralLaws/PartI/TitleIX/Chapter62/Section5

These augment the established state bases, never federal tax calculations.
"""
from decimal import Decimal, ROUND_HALF_UP

from tax_estimator.calculation.states.models import (
    StateCreditComponent, StatePolicyComputation, StateRules, StateTaxInput,
)
from tax_estimator.calculation.states.policy_common import StatePolicyError, require_policy_inputs

D = Decimal
ZERO = D(0)
EIC_RATES = {"CO": D(".50"), "IL": D(".20"), "IA": D(".15"), "KS": D(".17"), "LA": D(".05")}


def apply_additional_2025_credits(
    t: StateTaxInput, r: StateRules, c: StatePolicyComputation,
) -> StatePolicyComputation:
    if r.state_code not in {*EIC_RATES, "MA"}:
        return c
    if (not t.baseline_profile_supported or t.tax_year != 2025 or r.tax_year != 2025
            or t.filing_status != "single" or t.taxpayer_age_at_year_end != 40
            or not t.is_resident or t.num_dependents or t.can_be_claimed_as_dependent):
        raise StatePolicyError("Additional 2025 credits require the supported resident profile")

    if r.state_code in EIC_RATES:
        if t.federal_eitc_eligibility_asserted is not True:
            if t.federal_eitc_eligibility_asserted is None and t.federal_earned_income_credit is None:
                c.warnings += (f"{r.state_name} earned income credit omitted: federal claimant eligibility is not established.",)
            return c
        require_policy_inputs(t, "federal_earned_income_credit")
        amount = (t.federal_earned_income_credit * EIC_RATES[r.state_code]).quantize(D(".01"), rounding=ROUND_HALF_UP)
        if amount < 0:
            raise StatePolicyError("Federal earned income credit cannot be negative")
        if r.state_code == "KS":
            existing_nonref = sum((credit.amount_applied for credit in c.credits if not credit.is_refundable), ZERO)
            remaining = max(ZERO, c.tax_before_credits + c.surtax + c.recapture - existing_nonref)
            applied = min(amount, remaining)
            excess = amount - applied
            c.credits += (
                StateCreditComponent("KS-EIC-OFFSET", "Kansas earned income credit (tax offset)", amount, applied, False),
                StateCreditComponent("KS-EIC-REFUND", "Kansas earned income credit (refundable excess)", excess, excess, True),
            )
        else:
            c.credits += (StateCreditComponent(f"{r.state_code}-EIC", f"{r.state_name} earned income credit", amount, amount, True),)
        return c

    require_policy_inputs(t, "net_short_term_gains", "net_long_term_gains")
    if t.net_short_term_gains < 0 or t.net_long_term_gains < 0:
        raise StatePolicyError("Massachusetts signed capital losses require a separate state worksheet")
    # MA AGI worksheet line7 is BEFORE the Form1 employee-FICA deduction and
    # personal exemption. With no ScheduleY adjustments it equals gross income
    # in this positive-securities profile, not c.state_agi (which is after FICA).
    agi = t.federal_agi
    if agi <= D(8000):
        relief = c.tax_before_credits + c.surtax
        c.credits += (StateCreditComponent("MA-NTS", "Massachusetts No Tax Status relief", relief, relief, False),)
    elif agi <= D(14000):
        cap = (agi - D(8000)) * D(".10")
        relief = max(ZERO, c.tax_before_credits + c.surtax - cap)
        c.credits += (StateCreditComponent("MA-LIC", "Massachusetts limited income credit", relief, relief, False),)
    c.notes += ("MA No Tax Status / limited-income AGI is before employee FICA deductions; refundable EIC is separate.",)
    return c
