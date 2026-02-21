"""
Stage 11: Final Tax and Refund/Balance Due

Calculates final tax liability and determines refund or amount owed.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.stages.base import CalculationStage, StageResult
from tax_estimator.calculation.states.models import StateTaxType
from tax_estimator.models.tax_result import (
    CalculationResult,
    DeductionResult,
    FederalTaxResult,
    LocalTaxResult,
    StateTaxResult,
)

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext


class FinalCalculationStage(CalculationStage):
    """Calculates final tax and refund/balance due."""

    @property
    def stage_id(self) -> str:
        return "final_calculation"

    @property
    def stage_name(self) -> str:
        return "Final Tax Calculation"

    @property
    def stage_order(self) -> int:
        return 11

    @property
    def dependencies(self) -> list[str]:
        return ["local_tax"]  # Depends on state and local tax stages

    def execute(self, context: CalculationContext) -> StageResult:
        """Calculate final tax amounts."""
        context.current_stage = self.stage_id
        input_data = context.input
        trace = context.trace

        # Gather all components
        tax_before_credits = context.get_decimal_result("tax_before_credits")
        total_nonrefundable = context.get_decimal_result("total_nonrefundable_credits", Decimal(0))
        total_refundable = context.get_decimal_result("total_refundable_credits", Decimal(0))

        # Tax after nonrefundable credits
        tax_after_nonrefundable = max(Decimal(0), tax_before_credits - total_nonrefundable)

        # Add other taxes
        se_tax = context.get_decimal_result("self_employment_tax", Decimal(0))
        niit = context.get_decimal_result("niit", Decimal(0))
        additional_medicare = context.get_decimal_result("additional_medicare_tax", Decimal(0))

        # Total tax liability (before refundable credits)
        total_tax_before_refundable = tax_after_nonrefundable + se_tax + niit + additional_medicare

        # Apply refundable credits
        total_tax = total_tax_before_refundable - total_refundable
        # Total tax can go negative (refund from refundable credits)

        trace.add_step(
            step_id="FINAL-TAX",
            label="Total Federal Tax",
            formula="Tax after nonrefundable + Other taxes - Refundable credits",
            inputs={
                "tax_after_nonrefundable": str(tax_after_nonrefundable),
                "self_employment_tax": str(se_tax),
                "niit": str(niit),
                "additional_medicare": str(additional_medicare),
                "refundable_credits": str(total_refundable),
            },
            result=total_tax,
            jurisdiction="US",
        )

        # Calculate withholding
        total_withholding = input_data.total_federal_withholding()

        # Estimated payments
        estimated_payments = input_data.estimated_tax_payments

        # Calculate refund or amount owed
        refund_or_owed = total_tax - total_withholding - estimated_payments

        trace.add_step(
            step_id="FINAL-BALANCE",
            label="Refund or Balance Due",
            formula="Total Tax - Withholding - Estimated Payments",
            inputs={
                "total_tax": str(total_tax),
                "withholding": str(total_withholding),
                "estimated_payments": str(estimated_payments),
            },
            result=refund_or_owed,
            jurisdiction="US",
            note="Negative = Refund, Positive = Balance Due",
        )

        # Round final amounts to nearest dollar
        total_tax_rounded = total_tax.quantize(Decimal("1"))
        refund_or_owed_rounded = refund_or_owed.quantize(Decimal("1"))

        # Build federal result
        deduction_result = context.get_result("deduction_result")
        if not deduction_result:
            deduction_result = DeductionResult(
                method="standard",
                standard_deduction_available=context.get_decimal_result("standard_deduction"),
                itemized_deduction_total=context.get_decimal_result("itemized_deduction", Decimal(0)),
                deduction_used=context.get_decimal_result("deduction_used"),
                additional_deduction=Decimal(0),
            )

        credits_result = context.get_result("credits_result")
        bracket_breakdown = context.get_result("bracket_breakdown", [])

        federal_result = FederalTaxResult(
            gross_income=context.get_decimal_result("gross_income"),
            total_adjustments=context.get_decimal_result("total_adjustments", Decimal(0)),
            adjusted_gross_income=context.get_decimal_result("agi"),
            deduction=deduction_result,
            taxable_income=context.get_decimal_result("taxable_income"),
            ordinary_income=context.get_decimal_result("ordinary_income", Decimal(0)),
            preferential_income=context.get_decimal_result("preferential_income", Decimal(0)),
            tax_before_credits=tax_before_credits,
            ordinary_tax=context.get_decimal_result("ordinary_tax", Decimal(0)),
            preferential_tax=context.get_decimal_result("preferential_tax", Decimal(0)),
            preferential_rate_breakdown=context.get_result("preferential_rate_breakdown", []),
            bracket_breakdown=bracket_breakdown,
            credits=credits_result,
            self_employment_tax=se_tax,
            additional_medicare_tax=additional_medicare,
            net_investment_income_tax=niit,
            total_tax=total_tax_rounded,
            effective_rate=context.get_decimal_result("effective_rate", Decimal(0)),
            marginal_rate=context.get_decimal_result("marginal_rate", Decimal(0)),
            total_withholding=total_withholding,
            total_payments=estimated_payments,
        )

        # Build state tax results
        state_results = []
        state_result_data = context.get_result("state_result")
        state_tax_total = Decimal(0)

        if state_result_data:
            state_bracket_breakdown = context.get_result("state_bracket_breakdown", [])
            state_tax_total = state_result_data.total_tax

            state_tax_result = StateTaxResult(
                jurisdiction_id=f"US-{state_result_data.state_code}",
                jurisdiction_name=state_result_data.state_name,
                has_income_tax=state_result_data.has_income_tax,
                tax_type=state_result_data.tax_type.value,
                filing_status=state_result_data.filing_status,
                gross_income=state_result_data.gross_income,
                state_agi=state_result_data.state_agi,
                state_taxable_income=state_result_data.taxable_income,
                starting_point="federal_agi",  # Simplified - actual varies by state
                deduction_type=state_result_data.deduction_type,
                deduction_amount=state_result_data.deduction_amount,
                personal_exemption=state_result_data.personal_exemption,
                dependent_exemption=state_result_data.dependent_exemption,
                tax_before_credits=state_result_data.tax_before_credits,
                surtax=state_result_data.surtax,
                bracket_breakdown=state_bracket_breakdown,
                state_credits=state_result_data.credits,
                total_state_tax=state_result_data.total_tax,
                effective_rate=state_result_data.effective_rate,
                marginal_rate=state_result_data.marginal_rate,
                state_withholding=Decimal(0),  # TODO: Get from input
                is_resident=True,
                notes=state_result_data.notes,
            )
            state_results.append(state_tax_result)

        # Build local tax results
        local_results_data = context.get_result("local_results", [])
        local_tax_total = context.get_decimal_result("total_local_tax", Decimal(0))

        # Complete the trace
        context.trace.complete()

        # Calculate total tax liability across all jurisdictions
        total_tax_liability = total_tax_rounded + state_tax_total + local_tax_total

        # Build final result
        result = CalculationResult(
            success=True,
            tax_year=context.tax_year,
            federal=federal_result,
            states=state_results,
            total_tax_liability=total_tax_liability,
            total_withholding=total_withholding,
            total_payments=estimated_payments,
            trace=context.trace.to_dict(),
            warnings=context.warnings,
        )

        # Store result
        context.set_result("final_result", result)
        context.set_result("total_tax", total_tax_rounded)
        context.set_result("refund_or_owed", refund_or_owed_rounded)

        if refund_or_owed_rounded < 0:
            msg = f"Refund: ${abs(refund_or_owed_rounded):,.0f}"
        elif refund_or_owed_rounded > 0:
            msg = f"Balance due: ${refund_or_owed_rounded:,.0f}"
        else:
            msg = "No refund or balance due"

        return self._success(msg)
