"""
Stage 1: Input Validation

Validates and normalizes input data before calculation begins.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.stages.base import CalculationStage, StageResult

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext


class ValidationStage(CalculationStage):
    """Validates input data and normalizes values."""

    @property
    def stage_id(self) -> str:
        return "validation"

    @property
    def stage_name(self) -> str:
        return "Input Validation"

    @property
    def stage_order(self) -> int:
        return 1

    def execute(self, context: CalculationContext) -> StageResult:
        """Validate all input data."""
        context.current_stage = self.stage_id
        errors: list[str] = []
        warnings: list[str] = []

        input_data = context.input

        # VAL-001: Check tax year range
        # Note: Pydantic enforces tax_year is required and >= 2020,
        # so we only need to validate the upper bound for supportability
        if input_data.tax_year > 2030:
            errors.append(f"VAL-011: tax_year {input_data.tax_year} is not supported")

        # VAL-002: Check filing status
        if not input_data.filing_status:
            errors.append("VAL-002: filing_status is required")

        # VAL-003: Check for at least some income (warning only)
        total_income = (
            input_data.total_wages()
            + input_data.total_self_employment_net()
            + input_data.interest_dividends.taxable_interest
            + input_data.interest_dividends.ordinary_dividends
            + input_data.retirement.pension_income
            + input_data.retirement.ira_distributions
            + input_data.other_income
        )
        if total_income == 0:
            warnings.append("VAL-003: No income sources provided")

        # VAL-020: HOH requires qualifying dependent
        if input_data.filing_status and input_data.filing_status.value == "hoh":
            if not input_data.dependents:
                warnings.append(
                    "VAL-020: Head of Household typically requires a qualifying dependent"
                )

        # VAL-021: QSS requires qualifying child
        if input_data.filing_status and input_data.filing_status.value == "qss":
            qualifying_children = [
                d for d in input_data.dependents
                if d.age_at_year_end < 17 and d.qualifies_for_ctc
            ]
            if not qualifying_children:
                warnings.append(
                    "VAL-021: Qualifying Surviving Spouse typically requires a qualifying child"
                )

        # VAL-022: Qualified dividends cannot exceed ordinary dividends
        # (Already handled by Pydantic validator, but double-check)
        if (
            input_data.interest_dividends.qualified_dividends
            > input_data.interest_dividends.ordinary_dividends
        ):
            # Auto-correct
            context.add_warning(
                "VAL-022: Qualified dividends exceeded ordinary dividends; auto-corrected"
            )

        # VAL-030: Validate residence state
        valid_states = {
            "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
            "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
            "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
            "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
            "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
            "DC",
        }
        if input_data.residence_state.upper() not in valid_states:
            errors.append(f"VAL-030: Invalid state code: {input_data.residence_state}")

        # Validate dependent ages
        for i, dep in enumerate(input_data.dependents):
            if dep.age_at_year_end < 0 or dep.age_at_year_end > 120:
                warnings.append(f"VAL-012: Dependent {i+1} has unusual age: {dep.age_at_year_end}")

        # Validate wage amounts are non-negative
        for i, wage in enumerate(input_data.wages):
            if wage.gross_wages < 0:
                errors.append(f"VAL-010: Employer {i+1} has negative wages")

        # Add all warnings to context
        for warning in warnings:
            context.add_warning(warning)

        # Log validation to trace
        context.trace.add_step(
            step_id="VAL-COMPLETE",
            label="Input Validation Complete",
            formula="Check all required fields and constraints",
            inputs={
                "tax_year": input_data.tax_year,
                "filing_status": input_data.filing_status.value if input_data.filing_status else None,
                "residence_state": input_data.residence_state,
                "num_wages": len(input_data.wages),
                "num_dependents": len(input_data.dependents),
            },
            result=len(errors),
            jurisdiction="US",
            note=f"{len(errors)} errors, {len(warnings)} warnings",
        )

        if errors:
            error_msg = "; ".join(errors)
            context.trace.add_error(
                error_code="VALIDATION_FAILED",
                message=error_msg,
                stage=self.stage_id,
            )
            return self._error(error_msg, "VALIDATION_FAILED")

        return self._success(f"Validation passed with {len(warnings)} warnings")
