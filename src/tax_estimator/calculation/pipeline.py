"""
Pipeline orchestration for tax calculation.

The pipeline manages the execution of calculation stages in the correct order,
handling dependencies and collecting results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tax_estimator.calculation.stages.base import StageStatus

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext
    from tax_estimator.calculation.stages.base import CalculationStage, StageResult


class PipelineError(Exception):
    """Exception raised when pipeline execution fails."""

    def __init__(self, stage_id: str, message: str, error_code: str | None = None):
        self.stage_id = stage_id
        self.error_code = error_code
        super().__init__(f"Pipeline failed at stage '{stage_id}': {message}")


class CalculationPipeline:
    """
    Orchestrates the execution of calculation stages.

    Stages are executed in order based on their stage_order property.
    The pipeline respects dependencies and handles errors gracefully.
    """

    def __init__(self, stages: list["CalculationStage"] | None = None):
        """
        Initialize the pipeline.

        Args:
            stages: List of stages to execute. If None, uses default stages.
        """
        if stages is None:
            stages = self._get_default_stages()

        # Sort stages by order
        self._stages = sorted(stages, key=lambda s: s.stage_order)
        self._stage_results: dict[str, "StageResult"] = {}

    def _get_default_stages(self) -> list["CalculationStage"]:
        """Get the default set of calculation stages."""
        from tax_estimator.calculation.stages import (
            AdjustmentsAGIStage,
            CreditsStage,
            DeductionsStage,
            FinalCalculationStage,
            IncomeAggregationStage,
            TaxableIncomeStage,
            TaxComputationStage,
            ValidationStage,
        )
        from tax_estimator.calculation.stages.stage_09_state_tax import (
            StateTaxCalculationStage,
        )
        from tax_estimator.calculation.stages.stage_10_local_tax import (
            LocalTaxCalculationStage,
        )

        return [
            ValidationStage(),
            IncomeAggregationStage(),
            AdjustmentsAGIStage(),
            DeductionsStage(),
            TaxableIncomeStage(),
            TaxComputationStage(),
            CreditsStage(),
            StateTaxCalculationStage(),
            LocalTaxCalculationStage(),
            FinalCalculationStage(),
        ]

    def execute(self, context: "CalculationContext") -> dict[str, "StageResult"]:
        """
        Execute all stages in order.

        Args:
            context: The calculation context to pass through stages.

        Returns:
            Dictionary mapping stage IDs to their results.

        Raises:
            PipelineError: If a critical stage fails.
        """
        self._stage_results = {}

        for stage in self._stages:
            # Check if stage should be skipped
            if stage.should_skip(context):
                result = stage.skipped("Stage skipped")
                self._stage_results[stage.stage_id] = result
                continue

            # Check dependencies
            for dep_id in stage.dependencies:
                dep_result = self._stage_results.get(dep_id)
                if dep_result is None:
                    raise PipelineError(
                        stage.stage_id,
                        f"Missing required dependency: {dep_id}",
                        "MISSING_DEPENDENCY",
                    )
                if dep_result.status == StageStatus.ERROR:
                    # Skip this stage if a dependency failed
                    result = stage.skipped(f"Skipped due to failed dependency: {dep_id}")
                    self._stage_results[stage.stage_id] = result
                    continue

            # Execute the stage
            try:
                result = stage.execute(context)
                self._stage_results[stage.stage_id] = result

                # Handle errors
                if result.status == StageStatus.ERROR:
                    # Record in trace
                    context.trace.add_error(
                        error_code=result.error_code or "STAGE_ERROR",
                        message=result.message or "Unknown error",
                        stage=stage.stage_id,
                    )

                    # For validation stage, this is a critical error
                    if stage.stage_id == "validation":
                        raise PipelineError(
                            stage.stage_id,
                            result.message or "Validation failed",
                            result.error_code,
                        )

            except PipelineError:
                raise
            except Exception as e:
                # Unexpected error
                error_msg = f"Unexpected error: {str(e)}"
                context.trace.add_error(
                    error_code="UNEXPECTED_ERROR",
                    message=error_msg,
                    stage=stage.stage_id,
                    details={"exception_type": type(e).__name__},
                )
                raise PipelineError(
                    stage.stage_id, error_msg, "UNEXPECTED_ERROR"
                ) from e

        return self._stage_results

    @property
    def stages(self) -> list["CalculationStage"]:
        """Get the list of stages."""
        return self._stages

    @property
    def stage_results(self) -> dict[str, "StageResult"]:
        """Get the results from the last execution."""
        return self._stage_results

    def get_stage_result(self, stage_id: str) -> "StageResult | None":
        """Get the result for a specific stage."""
        return self._stage_results.get(stage_id)
