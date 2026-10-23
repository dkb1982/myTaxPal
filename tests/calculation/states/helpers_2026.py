"""Direct 2026 state-policy harness for source-reference tests.

Builds the StateTaxInput the pipeline would pass for the supported profile
(single, age 40, full-year resident W-2 employee, standard deduction) and runs
a registered 2026 policy against rules/states/2026/<st>.yaml. It does not
require the state to be public in coverage.py.

Federal inputs must be hand-computed for the scenario from 2026 federal law
(Rev. Proc. 2025-32 / OBBBA: single standard deduction $16,100) and passed in.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from tax_estimator.calculation.states.loader import StateRulesLoader
from tax_estimator.calculation.states.models import StateTaxInput, StateTaxResult
from tax_estimator.calculation.states.policies_2026 import POLICIES_2026
from tax_estimator.calculation.states.policy_common import build_state_result

RULES_DIR = Path(__file__).resolve().parents[3] / "rules" / "states"
D = Decimal


def state_input_2026(
    state_code: str,
    *,
    wages: Decimal,
    federal_agi: Decimal | None = None,
    federal_taxable_income: Decimal | None = None,
    ordinary_dividends: Decimal = D(0),
    qualified_dividends: Decimal = D(0),
    net_short_term_gains: Decimal = D(0),
    net_long_term_gains: Decimal = D(0),
    federal_income_tax_after_nonrefundable_credits: Decimal = D(0),
    federal_niit: Decimal = D(0),
    federal_additional_medicare_tax: Decimal = D(0),
    federal_deduction_amount: Decimal = D("16100"),
    **overrides,
) -> StateTaxInput:
    gains = net_short_term_gains + net_long_term_gains
    capital = max(gains, D(-3000))
    agi = federal_agi if federal_agi is not None else wages + ordinary_dividends + capital
    taxable = (
        federal_taxable_income if federal_taxable_income is not None
        else max(D(0), agi - federal_deduction_amount)
    )
    ss_wages = min(wages, D("184500"))
    values = dict(
        state_code=state_code,
        tax_year=2026,
        filing_status="single",
        federal_agi=agi,
        federal_taxable_income=taxable,
        wages=wages,
        dividends=ordinary_dividends,
        qualified_dividends=qualified_dividends,
        net_short_term_gains=net_short_term_gains,
        net_long_term_gains=net_long_term_gains,
        federal_agi_capital_gain=capital,
        federal_income_tax_after_nonrefundable_credits=federal_income_tax_after_nonrefundable_credits,
        federal_refundable_credits=D(0),
        federal_earned_income_credit=None,
        federal_niit=federal_niit,
        federal_additional_medicare_tax=federal_additional_medicare_tax,
        federal_self_employment_tax=D(0),
        employee_social_security_tax=(ss_wages * D(".062")).quantize(D("0.01")),
        employee_medicare_tax=(wages * D(".0145")).quantize(D("0.01")),
        federal_deduction_amount=federal_deduction_amount,
        taxpayer_age_at_year_end=40,
        baseline_profile_supported=True,
        is_resident=True,
    )
    values.update(overrides)
    return StateTaxInput(**values)


def compute_2026(state_code: str, **kwargs) -> StateTaxResult:
    tax_input = state_input_2026(state_code, **kwargs)
    rules = StateRulesLoader(RULES_DIR).load_state_rules(state_code, 2026)
    return build_state_result(tax_input, rules, POLICIES_2026[state_code](tax_input, rules))
