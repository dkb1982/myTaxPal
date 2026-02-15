"""
Stage 10: Local Tax Calculation

Calculates local (city/county) income tax based on residence ZIP code.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.stages.base import CalculationStage, StageResult
from tax_estimator.calculation.locals.calculator import LocalCalculator
from tax_estimator.calculation.locals.models import LocalTaxInput
from tax_estimator.calculation.locals.zip_lookup import ZipJurisdictionLookup

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext


class LocalTaxCalculationStage(CalculationStage):
    """Calculates local income tax."""

    def __init__(self) -> None:
        """Initialize with local calculator and ZIP lookup."""
        self._local_calculator = LocalCalculator()
        self._zip_lookup = ZipJurisdictionLookup()

    @property
    def stage_id(self) -> str:
        return "local_tax"

    @property
    def stage_name(self) -> str:
        return "Local Tax Calculation"

    @property
    def stage_order(self) -> int:
        return 10

    @property
    def dependencies(self) -> list[str]:
        return ["state_tax"]  # Need state tax results

    def execute(self, context: CalculationContext) -> StageResult:
        """Calculate local income tax."""
        context.current_stage = self.stage_id
        input_data = context.input
        trace = context.trace

        # Check if we have a ZIP code in the input
        residence_zip = getattr(input_data, "residence_zip", None)

        if not residence_zip:
            # No ZIP code provided - skip local tax calculation
            context.set_result("local_results", [])
            context.set_result("total_local_tax", Decimal(0))

            trace.add_step(
                step_id="LOCAL-TAX-SKIPPED",
                label="Local Tax",
                formula="Local tax calculation skipped - no ZIP code",
                inputs={},
                result=Decimal(0),
                jurisdiction="local",
                note="No residence ZIP code provided",
            )

            return self._success("Local tax skipped (no ZIP)")

        # Look up local jurisdiction from ZIP
        try:
            lookup_result = self._zip_lookup.lookup(residence_zip)
            local_jurisdiction = lookup_result.get("local_jurisdiction")

            if not local_jurisdiction:
                # No local tax jurisdiction for this ZIP
                context.set_result("local_results", [])
                context.set_result("total_local_tax", Decimal(0))

                trace.add_step(
                    step_id="LOCAL-TAX-NONE",
                    label="Local Tax",
                    formula="No local tax jurisdiction for ZIP",
                    inputs={"zip": residence_zip},
                    result=Decimal(0),
                    jurisdiction="local",
                    note="No local income tax for this location",
                )

                return self._success("No local tax jurisdiction")

        except Exception as e:
            context.add_warning(f"Failed to look up local jurisdiction: {e}")
            context.set_result("local_results", [])
            context.set_result("total_local_tax", Decimal(0))
            return self._success("Local tax skipped (lookup error)")

        # Get values needed for local tax calculation
        federal_agi = context.get_decimal_result("agi")
        total_wages = input_data.total_wages()
        total_se_income = input_data.total_self_employment_net()
        state_taxable_income = context.get_decimal_result("state_taxable_income", federal_agi)
        state_tax = context.get_decimal_result("state_tax", Decimal(0))

        # Build local tax input
        local_input = LocalTaxInput(
            jurisdiction_id=local_jurisdiction,
            tax_year=input_data.tax_year,
            filing_status=input_data.filing_status.value,
            is_resident=True,
            total_income=federal_agi,
            wages=total_wages,
            self_employment_income=total_se_income,
            state_taxable_income=state_taxable_income,
            state_tax=state_tax,  # Used for surcharge calculations (e.g., Yonkers)
        )

        # Calculate local tax
        try:
            local_result = self._local_calculator.calculate(local_input)

            # Store local results
            context.set_result("local_results", [local_result])
            context.set_result("total_local_tax", local_result.total_tax)

            # Add trace step
            trace.add_step(
                step_id="LOCAL-TAX",
                label=f"Local Tax ({local_result.jurisdiction_name})",
                formula="Calculate local income tax based on jurisdiction rules",
                inputs={
                    "jurisdiction": local_jurisdiction,
                    "taxable_income": str(local_result.taxable_income),
                    "tax_type": local_result.tax_type.value,
                },
                result=local_result.total_tax,
                jurisdiction=local_jurisdiction,
                note=f"Local tax: ${local_result.total_tax:,.2f}",
            )

            return self._success(f"Local tax calculated: ${local_result.total_tax:,.2f}")

        except Exception as e:
            context.add_warning(f"Local tax calculation failed: {e}")
            context.set_result("local_results", [])
            context.set_result("total_local_tax", Decimal(0))

            trace.add_step(
                step_id="LOCAL-TAX-ERROR",
                label="Local Tax",
                formula="Local tax calculation failed",
                inputs={"jurisdiction": local_jurisdiction, "error": str(e)},
                result=Decimal(0),
                jurisdiction=local_jurisdiction,
                note="Local tax calculation was skipped due to an error",
            )

            return self._success("Local tax skipped (error)")
