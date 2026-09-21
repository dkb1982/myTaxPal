"""
Stage 10: Local Tax Calculation

Calculates local (city/county) income tax from an explicit covered-city choice.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.comparison_regions import get_city_for_local_jurisdiction
from tax_estimator.calculation.locals.calculator import LocalCalculator
from tax_estimator.calculation.locals.models import LocalTaxInput
from tax_estimator.calculation.stages.base import CalculationStage, StageResult

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext


class LocalTaxCalculationStage(CalculationStage):
    """Calculates local income tax."""

    def __init__(self) -> None:
        """Initialize with the local calculator."""
        self._local_calculator = LocalCalculator()

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
        explicit_jurisdiction = input_data.local_jurisdiction_id

        if not residence_zip and not explicit_jurisdiction:
            context.add_warning(
                "Local tax is omitted because no explicit covered city was selected. "
                "A ZIP is optional and does not establish a local-tax jurisdiction."
            )
            # No explicit city was provided, so local tax cannot be calculated.
            context.set_result("local_results", [])
            context.set_result("total_local_tax", Decimal(0))

            trace.add_step(
                step_id="LOCAL-TAX-SKIPPED",
                label="Local Tax",
                formula="Local tax calculation skipped - no explicit city",
                inputs={},
                result=Decimal(0),
                jurisdiction="local",
                note="No explicit covered city selected",
            )

            return self._success("Local tax skipped (no explicit city)")

        # A ZIP can establish a state but not a city or local tax obligation.
        # Local tax therefore requires an explicit city selected from US_CITIES.
        try:
            city = get_city_for_local_jurisdiction(explicit_jurisdiction)
            if explicit_jurisdiction and city is None:
                return self._error("Unknown explicit local jurisdiction")
            if city and city.state_code != input_data.residence_state.upper():
                return self._error("Explicit local jurisdiction does not match residence state")
            local_jurisdiction = city.local_jurisdiction_id if city else None

            if not local_jurisdiction:
                context.add_warning(
                    "Local tax is omitted because no explicit covered city was selected. ZIP alone cannot confirm city/county obligations."
                )
                # No explicit local-tax jurisdiction was selected.
                context.set_result("local_results", [])
                context.set_result("total_local_tax", Decimal(0))

                trace.add_step(
                    step_id="LOCAL-TAX-NONE",
                    label="Local Tax",
                    formula="No explicit local tax jurisdiction",
                    inputs={"zip": residence_zip, "local_jurisdiction_id": explicit_jurisdiction},
                    result=Decimal(0),
                    jurisdiction="local",
                    note="ZIP alone cannot confirm a local jurisdiction; local tax may still apply",
                )

                return self._success("No local tax jurisdiction")

        except Exception as e:
            context.add_warning(f"Failed to look up local jurisdiction: {e}")
            context.set_result("local_results", [])
            context.set_result("total_local_tax", Decimal(0))
            return self._error(f"Local jurisdiction lookup failed: {e}")

        # Get values needed for local tax calculation
        federal_agi = context.get_decimal_result("agi")
        total_wages = input_data.total_wages()
        total_se_income = input_data.total_self_employment_net()
        state_taxable_income = context.get_decimal_result("state_taxable_income", federal_agi)
        state_tax = context.get_decimal_result("state_tax", Decimal(0))
        state_result = context.get_result("state_result")
        surcharge_base = None
        if state_result is not None:
            surcharge_base = (
                state_result.tax_before_credits + state_result.surtax
                + getattr(state_result, "recapture", Decimal(0))
                - getattr(state_result, "nonrefundable_credits", state_result.credits)
            )

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
            state_agi=state_result.state_agi if state_result else None,
            yonkers_surcharge_base=surcharge_base,
            dividends=context.get_decimal_result("ordinary_dividends"),
            qualified_dividends=context.get_decimal_result("qualified_dividends"),
            net_short_term_gains=context.get_decimal_result("net_short_term_gain"),
            net_long_term_gains=context.get_decimal_result("net_long_term_gain"),
            taxpayer_age_at_year_end=input_data.taxpayer.age_at_year_end,
            can_be_claimed_as_dependent=input_data.taxpayer.is_dependent,
            num_dependents=len(input_data.dependents),
            federal_earned_income_credit=context.get_result("federal_earned_income_credit"),
            federal_eitc_eligibility_asserted=input_data.eitc_eligibility_asserted,
            baseline_profile_supported=context.get_result("us_baseline_profile_supported", False),
            unsupported_profile_reasons=context.get_result("us_unsupported_profile_reasons", ()),
            philly_gains_held_six_months_or_less=input_data.us_scenario.philly_gains_held_six_months_or_less,
            philly_first_half_wages=input_data.us_scenario.philly_first_half_wages,
        )

        # Calculate local tax
        try:
            rules = self._local_calculator.loader.load_local_rules(
                local_jurisdiction, input_data.tax_year
            )
            if rules.parent_state.removeprefix("US-") != input_data.residence_state.upper():
                return self._error("Local jurisdiction/ZIP does not match residence state")
            local_result = self._local_calculator.calculate(local_input)
            context.add_warning(
                "Local estimate assumes full-year residence and work in the explicitly "
                "selected city/county."
            )
            for warning in local_result.warnings + local_result.assumptions:
                context.add_warning(warning)

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

            return self._error(f"Local tax calculation failed: {e}")
