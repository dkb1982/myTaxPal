"""
Stage 8: Credits

Applies tax credits (both nonrefundable and refundable).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.stages.base import CalculationStage, StageResult
from tax_estimator.models.tax_result import CreditDetail, CreditsResult

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext


class CreditsStage(CalculationStage):
    """Calculates and applies tax credits."""

    @property
    def stage_id(self) -> str:
        return "credits"

    @property
    def stage_name(self) -> str:
        return "Credits"

    @property
    def stage_order(self) -> int:
        return 8

    @property
    def dependencies(self) -> list[str]:
        return ["tax_computation"]

    def execute(self, context: CalculationContext) -> StageResult:
        """Calculate and apply all credits."""
        context.current_stage = self.stage_id
        input_data = context.input
        trace = context.trace

        tax_before_credits = context.get_decimal_result("tax_before_credits")
        agi = context.get_decimal_result("agi")

        nonrefundable_credits: list[CreditDetail] = []
        refundable_credits: list[CreditDetail] = []

        remaining_tax = tax_before_credits

        # ========== NONREFUNDABLE CREDITS ==========

        # Child Tax Credit
        ctc_result = self._calculate_child_tax_credit(context, agi)
        if ctc_result["total"] > 0:
            ctc_nonrefundable = min(ctc_result["nonrefundable"], remaining_tax)
            nonrefundable_credits.append(
                CreditDetail(
                    credit_id="US-CTC",
                    credit_name="Child Tax Credit",
                    credit_amount=ctc_result["total"],
                    amount_used=ctc_nonrefundable,
                    is_refundable=False,
                )
            )
            remaining_tax -= ctc_nonrefundable

            trace.add_step(
                step_id="CREDIT-CTC",
                label="Child Tax Credit",
                formula="$2,000 per qualifying child (under 17)",
                inputs={
                    "qualifying_children": ctc_result["qualifying_children"],
                    "base_credit": str(ctc_result["base"]),
                    "phase_out_reduction": str(ctc_result["phase_out"]),
                    "total_credit": str(ctc_result["total"]),
                },
                result=ctc_nonrefundable,
                jurisdiction="US",
            )

            # Additional Child Tax Credit (refundable portion)
            if ctc_result["refundable"] > 0:
                refundable_credits.append(
                    CreditDetail(
                        credit_id="US-ACTC",
                        credit_name="Additional Child Tax Credit",
                        credit_amount=ctc_result["refundable"],
                        amount_used=ctc_result["refundable"],
                        is_refundable=True,
                    )
                )

        # Other Dependent Credit ($500 per qualifying dependent not eligible for CTC)
        odc_result = self._calculate_other_dependent_credit(context, agi)
        if odc_result > 0:
            odc_used = min(odc_result, remaining_tax)
            nonrefundable_credits.append(
                CreditDetail(
                    credit_id="US-ODC",
                    credit_name="Other Dependent Credit",
                    credit_amount=odc_result,
                    amount_used=odc_used,
                    is_refundable=False,
                )
            )
            remaining_tax -= odc_used

            trace.add_step(
                step_id="CREDIT-ODC",
                label="Other Dependent Credit",
                formula="$500 per qualifying dependent not eligible for CTC",
                inputs={"credit": str(odc_result)},
                result=odc_used,
                jurisdiction="US",
            )

        # ========== REFUNDABLE CREDITS ==========

        # Earned Income Credit
        eic_result = self._calculate_earned_income_credit(context, agi)
        if eic_result > 0:
            refundable_credits.append(
                CreditDetail(
                    credit_id="US-EIC",
                    credit_name="Earned Income Credit",
                    credit_amount=eic_result,
                    amount_used=eic_result,
                    is_refundable=True,
                )
            )

            trace.add_step(
                step_id="CREDIT-EIC",
                label="Earned Income Credit",
                formula="Based on earned income and qualifying children",
                inputs={
                    "earned_income": str(context.get_decimal_result("earned_income")),
                    "qualifying_children": len([
                        d for d in input_data.dependents
                        if d.age_at_year_end < 19 or (d.is_student and d.age_at_year_end < 24)
                    ]),
                },
                result=eic_result,
                jurisdiction="US",
            )

        # Calculate totals
        total_nonrefundable = sum(c.amount_used for c in nonrefundable_credits)
        total_refundable = sum(c.amount_used for c in refundable_credits)
        total_credits = total_nonrefundable + total_refundable

        tax_after_nonrefundable = max(Decimal(0), tax_before_credits - total_nonrefundable)

        trace.add_step(
            step_id="CREDITS-TOTAL",
            label="Total Credits Applied",
            formula="Nonrefundable (limited to tax) + Refundable",
            inputs={
                "tax_before_credits": str(tax_before_credits),
                "nonrefundable": str(total_nonrefundable),
                "refundable": str(total_refundable),
            },
            result=total_credits,
            jurisdiction="US",
        )

        # Create result object
        credits_result = CreditsResult(
            nonrefundable_credits=nonrefundable_credits,
            refundable_credits=refundable_credits,
            total_nonrefundable=total_nonrefundable,
            total_refundable=total_refundable,
            total_credits=total_credits,
        )

        # Store results
        context.set_result("credits_result", credits_result)
        context.set_result("total_nonrefundable_credits", total_nonrefundable)
        context.set_result("total_refundable_credits", total_refundable)
        context.set_result("total_credits", total_credits)
        context.set_result("tax_after_nonrefundable", tax_after_nonrefundable)

        return self._success(f"Total credits: ${total_credits:,.2f}")

    def _calculate_child_tax_credit(
        self, context: "CalculationContext", agi: Decimal
    ) -> dict:
        """
        Calculate Child Tax Credit.

        - $2,000 per qualifying child under 17 with SSN
        - Phase-out: $50 reduction per $1,000 over threshold
        - Thresholds: $400,000 MFJ, $200,000 others
        - Refundable portion (ACTC): up to $1,700 per child (2025 PLACEHOLDER)
        """
        input_data = context.input
        filing_status = input_data.filing_status.value

        # Count qualifying children (under 17, has SSN, lived with taxpayer 6+ months)
        qualifying_children = [
            d for d in input_data.dependents
            if d.age_at_year_end < 17 and d.has_ssn and d.months_lived_with_you >= 6
        ]
        num_children = len(qualifying_children)

        if num_children == 0:
            return {
                "qualifying_children": 0,
                "base": Decimal(0),
                "phase_out": Decimal(0),
                "total": Decimal(0),
                "nonrefundable": Decimal(0),
                "refundable": Decimal(0),
            }

        # Base credit: $2,000 per child
        base_credit = Decimal(2000) * num_children

        # Phase-out thresholds
        threshold = Decimal(400000) if filing_status == "mfj" else Decimal(200000)

        # Phase-out: $50 per $1,000 over threshold
        # Per IRS Publication 972, the excess is rounded DOWN to the next $1,000
        phase_out = Decimal(0)
        if agi > threshold:
            excess = ((agi - threshold) / 1000).to_integral_value(rounding="ROUND_DOWN")
            phase_out = excess * 50

        total_credit = max(Decimal(0), base_credit - phase_out)

        # Refundable portion (ACTC): up to $1,700 per child (2025 PLACEHOLDER)
        max_refundable = Decimal(1700) * num_children
        refundable = min(total_credit, max_refundable)
        nonrefundable = total_credit - refundable

        return {
            "qualifying_children": num_children,
            "base": base_credit,
            "phase_out": phase_out,
            "total": total_credit,
            "nonrefundable": nonrefundable,
            "refundable": refundable,
        }

    def _calculate_other_dependent_credit(
        self, context: "CalculationContext", agi: Decimal
    ) -> Decimal:
        """
        Calculate Other Dependent Credit.

        $500 per qualifying dependent who doesn't qualify for CTC.
        Subject to same phase-out as CTC.
        """
        input_data = context.input
        filing_status = input_data.filing_status.value

        # Count dependents who don't qualify for CTC
        other_dependents = [
            d for d in input_data.dependents
            if d.age_at_year_end >= 17 or not d.has_ssn
        ]
        num_other = len(other_dependents)

        if num_other == 0:
            return Decimal(0)

        # Base credit: $500 per other dependent
        base_credit = Decimal(500) * num_other

        # Same phase-out as CTC
        threshold = Decimal(400000) if filing_status == "mfj" else Decimal(200000)

        # Per IRS rules, the excess is rounded DOWN to the next $1,000
        phase_out = Decimal(0)
        if agi > threshold:
            excess = ((agi - threshold) / 1000).to_integral_value(rounding="ROUND_DOWN")
            phase_out = excess * 50

        return max(Decimal(0), base_credit - phase_out)

    def _calculate_earned_income_credit(
        self, context: "CalculationContext", agi: Decimal
    ) -> Decimal:
        """
        Calculate Earned Income Credit.

        This is a simplified calculation. Full EIC requires:
        - Earned income within limits
        - Investment income under threshold
        - Filing status and children count
        - Phase-in and phase-out calculations
        """
        input_data = context.input
        filing_status = input_data.filing_status.value

        earned_income = context.get_decimal_result("earned_income", Decimal(0))
        investment_income = context.get_decimal_result("investment_income", Decimal(0))

        # Investment income limit (2025 PLACEHOLDER)
        investment_limit = Decimal(11600)
        if investment_income > investment_limit:
            return Decimal(0)

        # Cannot be MFS
        if filing_status == "mfs":
            return Decimal(0)

        # Count qualifying children for EIC (different from CTC)
        qualifying_children = [
            d for d in input_data.dependents
            if (d.age_at_year_end < 19 or (d.is_student and d.age_at_year_end < 24) or d.is_disabled)
            and d.months_lived_with_you >= 6
        ]
        num_children = min(len(qualifying_children), 3)  # Max 3 for EIC

        # EIC parameters by number of children (2025 PLACEHOLDER)
        eic_params = {
            0: {"max_credit": Decimal(632), "phase_in_end": Decimal(8490),
                "phase_out_start": Decimal(10330), "phase_out_end": Decimal(18591)},
            1: {"max_credit": Decimal(4213), "phase_in_end": Decimal(11750),
                "phase_out_start": Decimal(22120), "phase_out_end": Decimal(49084)},
            2: {"max_credit": Decimal(6960), "phase_in_end": Decimal(16510),
                "phase_out_start": Decimal(22120), "phase_out_end": Decimal(55768)},
            3: {"max_credit": Decimal(7830), "phase_in_end": Decimal(16510),
                "phase_out_start": Decimal(22120), "phase_out_end": Decimal(59899)},
        }

        params = eic_params[num_children]

        # MFJ adjustment
        mfj_additional = Decimal(6920) if filing_status == "mfj" else Decimal(0)
        phase_out_start = params["phase_out_start"] + mfj_additional
        phase_out_end = params["phase_out_end"] + mfj_additional

        # Use greater of earned income or AGI for phase-out
        income_for_eic = max(earned_income, agi)

        # Calculate credit
        if income_for_eic <= params["phase_in_end"]:
            # Phase-in
            credit_rate = params["max_credit"] / params["phase_in_end"]
            credit = earned_income * credit_rate
        elif income_for_eic <= phase_out_start:
            # Plateau
            credit = params["max_credit"]
        elif income_for_eic < phase_out_end:
            # Phase-out
            phase_out_rate = params["max_credit"] / (phase_out_end - phase_out_start)
            credit = params["max_credit"] - ((income_for_eic - phase_out_start) * phase_out_rate)
        else:
            # Above phase-out
            credit = Decimal(0)

        return max(Decimal(0), credit.quantize(Decimal("1")))
