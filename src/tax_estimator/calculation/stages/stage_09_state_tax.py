"""
Stage 09: State Tax Calculation

Calculates state income tax for the residence state.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from tax_estimator.calculation.stages.base import CalculationStage, StageResult
from tax_estimator.calculation.states.calculator import StateCalculator
from tax_estimator.calculation.states.loader import StateRulesLoader
from tax_estimator.calculation.states.models import StateTaxInput
from tax_estimator.calculation.us_profile import (
    BASELINE_ASSUMPTIONS,
    MODELLED_TAX_SCOPE,
    baseline_profile_reasons,
)
from tax_estimator.models.tax_result import BracketBreakdown as ResultBracketBreakdown

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext


class StateTaxCalculationStage(CalculationStage):
    """Calculates state income tax."""

    def __init__(self, rules_dir: Path | None = None) -> None:
        """Initialize with state calculator."""
        self._rules_dir = rules_dir
        self._state_calculator = StateCalculator()
        loader = StateRulesLoader(rules_dir / "states" if rules_dir else None)
        self._state_calculator_2026 = StateCalculator(loader)

    @property
    def stage_id(self) -> str:
        return "state_tax"

    @property
    def stage_name(self) -> str:
        return "State Tax Calculation"

    @property
    def stage_order(self) -> int:
        return 9

    @property
    def dependencies(self) -> list[str]:
        return ["credits"]  # Need federal AGI and other data

    def execute(self, context: CalculationContext) -> StageResult:
        """Calculate state income tax."""
        context.current_stage = self.stage_id
        input_data = context.input
        trace = context.trace

        residence_state = input_data.residence_state.upper()

        # Get federal values
        federal_agi = context.get_decimal_result("agi")
        federal_taxable_income = context.get_decimal_result("taxable_income")
        total_wages = input_data.total_wages()

        # Get interest and dividends
        interest = Decimal(0)
        dividends = Decimal(0)
        if input_data.interest_dividends:
            interest = input_data.interest_dividends.taxable_interest
            dividends = input_data.interest_dividends.ordinary_dividends

        # Count dependents
        num_dependents = len(input_data.dependents)
        profile_reasons = baseline_profile_reasons(input_data, rules_root=self._rules_dir)

        # Build state tax input
        state_input = StateTaxInput(
            state_code=residence_state,
            tax_year=input_data.tax_year,
            filing_status=input_data.filing_status.value,
            federal_agi=federal_agi,
            federal_taxable_income=federal_taxable_income,
            wages=total_wages,
            interest=interest,
            dividends=dividends,
            qualified_dividends=context.get_decimal_result("qualified_dividends"),
            net_short_term_gains=context.get_decimal_result("net_short_term_gain"),
            net_long_term_gains=context.get_decimal_result("net_long_term_gain"),
            federal_agi_capital_gain=context.get_decimal_result("net_capital_for_income"),
            federal_income_tax_after_nonrefundable_credits=context.get_decimal_result("tax_after_nonrefundable"),
            federal_refundable_credits=context.get_decimal_result("total_refundable_credits"),
            federal_earned_income_credit=context.get_result("federal_earned_income_credit"),
            federal_niit=context.get_decimal_result("niit"),
            federal_additional_medicare_tax=context.get_decimal_result("additional_medicare_tax"),
            federal_self_employment_tax=context.get_decimal_result("self_employment_tax"),
            employee_social_security_tax=context.get_decimal_result("employee_social_security_tax"),
            employee_medicare_tax=context.get_decimal_result("employee_medicare_tax"),
            federal_deduction_amount=context.get_decimal_result("deduction_used"),
            # taxable_income above is post-QBI; states that disallow or add back
            # the section 199A deduction use this amount (stage 06 result).
            federal_qbi_deduction=context.get_decimal_result("qbi_deduction", Decimal(0)),
            federal_eitc_eligibility_asserted=input_data.eitc_eligibility_asserted,
            taxpayer_age_at_year_end=input_data.taxpayer.age_at_year_end,
            baseline_profile_supported=not profile_reasons,
            unsupported_profile_reasons=profile_reasons,
            az_post_2011_eligible_long_term_gains=input_data.us_scenario.az_post_2011_eligible_long_term_gains,
            num_dependents=num_dependents,
            age_65_or_older=input_data.taxpayer.age_65_or_older,
            is_blind=input_data.taxpayer.is_blind,
            can_be_claimed_as_dependent=input_data.taxpayer.is_dependent,
            spouse_age_65_or_older=bool(input_data.spouse and input_data.spouse.age_65_or_older),
            spouse_is_blind=bool(input_data.spouse and input_data.spouse.is_blind),
            is_resident=True,
        )

        # Calculate state tax
        try:
            calculator = (
                self._state_calculator_2026 if input_data.tax_year == 2026
                else self._state_calculator
            )
            state_result = calculator.calculate(state_input)
            context.add_warning(MODELLED_TAX_SCOPE)
            if not profile_reasons:
                context.add_warning(BASELINE_ASSUMPTIONS)
            else:
                context.add_warning("State/city profile outside source-checked scope: " + "; ".join(profile_reasons))
            for warning in state_result.warnings:
                context.add_warning(warning)
            for assumption in getattr(state_result, "assumptions", ()):
                context.add_warning(assumption)
            context.set_result("us_baseline_profile_supported", not profile_reasons)
            context.set_result("us_unsupported_profile_reasons", profile_reasons)

            # Convert bracket breakdown to result model format
            bracket_breakdown = []
            for idx, b in enumerate(state_result.bracket_breakdown):
                bracket_breakdown.append(
                    ResultBracketBreakdown(
                        bracket_id=b.bracket_id or f"state-{idx}",
                        bracket_min=b.bracket_min,
                        bracket_max=b.bracket_max,
                        rate=b.rate,
                        income_in_bracket=b.income_in_bracket,
                        tax_in_bracket=b.tax_in_bracket,
                    )
                )

            # Store state result
            context.set_result("state_result", state_result)
            context.set_result("state_bracket_breakdown", bracket_breakdown)
            context.set_result("state_tax", state_result.total_tax)
            context.set_result("state_taxable_income", state_result.taxable_income)
            context.set_result("state_effective_rate", state_result.effective_rate)
            context.set_result("state_marginal_rate", state_result.marginal_rate)

            # Add trace step
            trace.add_step(
                step_id="STATE-TAX",
                label=f"State Tax ({residence_state})",
                formula="Calculate state income tax based on state rules",
                inputs={
                    "state": residence_state,
                    "federal_agi": str(federal_agi),
                    "state_taxable_income": str(state_result.taxable_income),
                    "tax_type": state_result.tax_type.value,
                },
                result=state_result.total_tax,
                jurisdiction=f"US-{residence_state}",
                note=f"State tax: ${state_result.total_tax:,.2f} (effective rate: {state_result.effective_rate * 100:.2f}%)",
            )

            # Add warning if placeholder rules
            if state_result.notes:
                for note in state_result.notes:
                    if "placeholder" in note.lower():
                        context.add_warning(
                            f"State tax for {residence_state} uses placeholder rules. "
                            "Verify with official state tax tables."
                        )
                        break

            return self._success(f"State tax calculated: ${state_result.total_tax:,.2f}")

        except Exception as e:
            # The pipeline makes a selected state failure fatal.
            context.add_warning(f"State tax calculation failed for {residence_state}: {e}")
            context.set_result("state_result", None)
            context.set_result("state_tax", Decimal(0))

            trace.add_step(
                step_id="STATE-TAX-SKIPPED",
                label=f"State Tax ({residence_state})",
                formula="State tax calculation skipped",
                inputs={"state": residence_state, "error": str(e)},
                result=Decimal(0),
                jurisdiction=f"US-{residence_state}",
                note="State tax calculation was skipped due to an error",
            )

            return self._error(f"State tax calculation failed for {residence_state}: {e}")
