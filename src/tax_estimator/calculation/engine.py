"""
Main calculation engine for tax estimation.

The CalculationEngine is the primary entry point for performing tax calculations.
It orchestrates the loading of rules and execution of the calculation pipeline.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from tax_estimator.calculation.context import CalculationContext
from tax_estimator.calculation.pipeline import CalculationPipeline, PipelineError
from tax_estimator.calculation.trace import CalculationTrace
from tax_estimator.models.tax_result import CalculationResult
from tax_estimator.rules.loader import get_rules_for_jurisdiction, RulesLoadError

if TYPE_CHECKING:
    from tax_estimator.models.tax_input import TaxInput


class CalculationEngine:
    """
    Main engine for performing tax calculations.

    Usage:
        engine = CalculationEngine()
        result = engine.calculate(tax_input)
    """

    def __init__(
        self,
        rules_dir: Path | None = None,
        include_trace: bool = True,
    ):
        """
        Initialize the calculation engine.

        Args:
            rules_dir: Optional custom directory for tax rules.
            include_trace: Whether to include calculation trace in results.
        """
        self._rules_dir = rules_dir
        self._include_trace = include_trace
        self._pipeline = CalculationPipeline()

    def calculate(self, tax_input: "TaxInput") -> CalculationResult:
        """
        Perform a complete tax calculation.

        Args:
            tax_input: The tax input data to calculate.

        Returns:
            CalculationResult with federal (and eventually state) tax results.
        """
        # Create calculation context
        trace = CalculationTrace(
            calculation_id=str(uuid.uuid4()),
            tax_year=tax_input.tax_year,
        )

        context = CalculationContext(
            input=tax_input,
            tax_year=tax_input.tax_year,
            trace=trace,
        )

        # Load federal rules
        try:
            federal_rules = get_rules_for_jurisdiction(
                "US",
                tax_input.tax_year,
                self._rules_dir,
            )
            context.jurisdiction_rules["US"] = federal_rules

            trace.add_step(
                step_id="RULES-LOADED",
                label="Tax Rules Loaded",
                formula="Load jurisdiction rules from YAML",
                inputs={
                    "jurisdiction": "US",
                    "tax_year": tax_input.tax_year,
                    "verification_status": federal_rules.verification.status.value,
                },
                result=1,
                jurisdiction="US",
                note=f"Rules loaded: {federal_rules.jurisdiction_name}",
            )

            # Warn if using placeholder rules
            if federal_rules.verification.status.value == "placeholder":
                context.add_warning(
                    "PLACEHOLDER RULES: Tax calculations use placeholder data for development. "
                    "Do not use for real tax decisions."
                )

        except RulesLoadError as e:
            # Cannot proceed without rules
            trace.add_error(
                error_code="RULES_LOAD_FAILED",
                message=str(e),
                stage="initialization",
            )
            trace.complete()

            return CalculationResult(
                success=False,
                tax_year=tax_input.tax_year,
                federal=None,
                trace=trace.to_dict() if self._include_trace else None,
                warnings=[],
                errors=[f"Failed to load tax rules: {e}"],
            )

        # Load state rules if residence state has income tax
        residence_state = tax_input.residence_state.upper()
        state_jurisdiction = f"US-{residence_state}"

        try:
            state_rules = get_rules_for_jurisdiction(
                state_jurisdiction,
                tax_input.tax_year,
                self._rules_dir,
            )
            context.jurisdiction_rules[state_jurisdiction] = state_rules
        except RulesLoadError:
            # State rules not available - this is OK for MVP
            # Just add a warning
            context.add_warning(
                f"State tax rules for {residence_state} not available. "
                "Only federal tax will be calculated."
            )

        # Execute the pipeline
        try:
            self._pipeline.execute(context)

            # Get the final result from context
            result = context.get_result("final_result")

            if result is None:
                # Pipeline completed but no result - shouldn't happen
                trace.complete()
                return CalculationResult(
                    success=False,
                    tax_year=tax_input.tax_year,
                    federal=None,
                    trace=trace.to_dict() if self._include_trace else None,
                    warnings=context.warnings,
                    errors=["Pipeline completed but no result generated"],
                )

            # Update trace inclusion
            if not self._include_trace:
                result = result.model_copy(update={"trace": None})

            return result

        except PipelineError as e:
            trace.complete()
            return CalculationResult(
                success=False,
                tax_year=tax_input.tax_year,
                federal=None,
                trace=trace.to_dict() if self._include_trace else None,
                warnings=context.warnings,
                errors=[str(e)],
            )

    def calculate_federal_only(self, tax_input: "TaxInput") -> CalculationResult:
        """
        Calculate federal tax only, ignoring state.

        This is a convenience method for simpler calculations.
        """
        return self.calculate(tax_input)

    @property
    def pipeline(self) -> CalculationPipeline:
        """Get the calculation pipeline."""
        return self._pipeline
