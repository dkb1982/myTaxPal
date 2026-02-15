"""
Stage 09: State Tax Calculation

Calculates state income tax for the residence state.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.stages.base import CalculationStage, StageResult
from tax_estimator.calculation.states.calculator import StateCalculator
from tax_estimator.calculation.states.models import StateTaxInput
from tax_estimator.models.tax_result import BracketBreakdown as ResultBracketBreakdown

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext


class StateTaxCalculationStage(CalculationStage):
    """Calculates state income tax."""

    def __init__(self) -> None:
        """Initialize with state calculator."""
        self._state_calculator = StateCalculator()

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
        total_se_income = input_data.total_self_employment_net()

        # Get interest and dividends
        interest = Decimal(0)
        dividends = Decimal(0)
        if input_data.interest_dividends:
            interest = input_data.interest_dividends.taxable_interest
            dividends = input_data.interest_dividends.ordinary_dividends

        # Count dependents
        num_dependents = len(input_data.dependents)

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
            num_dependents=num_dependents,
            is_resident=True,
        )

        # Calculate state tax
        try:
            state_result = self._state_calculator.calculate(state_input)

            # Convert bracket breakdown to result model format
            bracket_breakdown = []
            for idx, b in enumerate(state_result.bracket_breakdown):
                bracket_breakdown.append(ResultBracketBreakdown(
                    bracket_id=b.bracket_id or f"state-{idx}",
                    bracket_min=b.bracket_min,
                    bracket_max=b.bracket_max,
                    rate=b.rate,
                    income_in_bracket=b.income_in_bracket,
                    tax_in_bracket=b.tax_in_bracket,
                ))

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
                note=f"State tax: ${state_result.total_tax:,.2f} (effective rate: {state_result.effective_rate*100:.2f}%)",
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
            # State tax calculation failed - continue with just federal
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

            return self._success("State tax skipped (error)")
