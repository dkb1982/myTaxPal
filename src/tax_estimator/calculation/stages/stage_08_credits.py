"""
Stage 8: Credits

Applies tax credits (both nonrefundable and refundable).
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
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

        # Child Tax Credit, Other Dependent Credit, and ACTC share the
        # Schedule 8812 phaseout and liability limit.
        ctc_result = self._calculate_child_tax_credit(context, agi)
        if ctc_result["ctc_available"] > 0:
            ctc_nonrefundable = min(ctc_result["ctc_available"], remaining_tax)
            nonrefundable_credits.append(
                CreditDetail(
                    credit_id="US-CTC",
                    credit_name="Child Tax Credit",
                    credit_amount=ctc_result["ctc_available"],
                    amount_used=ctc_nonrefundable,
                    is_refundable=False,
                )
            )
            remaining_tax -= ctc_nonrefundable

            trace.add_step(
                step_id="CREDIT-CTC",
                label="Child Tax Credit",
                formula="2025 Schedule 8812 combined CTC/ODC worksheet",
                inputs={
                    "qualifying_children": ctc_result["qualifying_children"],
                    "base_credit": str(ctc_result["base"]),
                    "phase_out_reduction": str(ctc_result["phase_out"]),
                    "available_credit": str(ctc_result["combined_available"]),
                },
                result=ctc_nonrefundable,
                jurisdiction="US",
            )

        if ctc_result["odc_available"] > 0:
            odc_used = min(ctc_result["odc_available"], remaining_tax)
            nonrefundable_credits.append(
                CreditDetail(
                    credit_id="US-ODC",
                    credit_name="Other Dependent Credit",
                    credit_amount=ctc_result["odc_available"],
                    amount_used=odc_used,
                    is_refundable=False,
                )
            )
            remaining_tax -= odc_used

            trace.add_step(
                step_id="CREDIT-ODC",
                label="Other Dependent Credit",
                formula="$500 per qualifying dependent not eligible for CTC",
                inputs={"credit": str(ctc_result["odc_available"])},
                result=odc_used,
                jurisdiction="US",
            )

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

        # ========== REFUNDABLE CREDITS ==========

        # Earned Income Credit
        eic_result = self._calculate_earned_income_credit(context, agi)
        context.set_result(
            "federal_earned_income_credit",
            eic_result if context.get_result("federal_eic_assessed", False) else None,
        )
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
                    "qualifying_children": len(
                        [d for d in input_data.dependents if d.qualifies_for_eitc is True]
                    ),
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

    def _calculate_child_tax_credit(self, context: CalculationContext, agi: Decimal) -> dict:
        """Calculate the supported ordinary 2025 Schedule 8812 path."""
        input_data = context.input
        filing_status = input_data.filing_status.value
        federal_rules = context.get_rules("US")
        if federal_rules is None or federal_rules.federal_credits is None:
            raise ValueError("Federal credit configuration is required")
        config = federal_rules.federal_credits.child_tax_credit

        asserted_children = [d for d in input_data.dependents if d.qualifies_for_ctc]
        unclassified_dependents = [
            d for d in input_data.dependents if not d.qualifies_for_ctc and not d.qualifies_for_odc
        ]
        if unclassified_dependents:
            context.add_warning(
                "Dependent CTC/ODC omitted for one or more dependents because neither "
                "credit eligibility assertion was provided."
            )

        claimant_has_ssn = input_data.taxpayer.has_valid_ssn_for_ctc is True or (
            filing_status == "mfj"
            and input_data.spouse is not None
            and input_data.spouse.has_valid_ssn_for_ctc is True
        )
        if asserted_children and not claimant_has_ssn:
            context.add_warning(
                "CTC and ACTC omitted: no filer asserted the employment-valid SSN "
                "required for a 2025 claim."
            )

        if any(
            child.age_at_year_end >= 17 or not child.has_ssn or child.months_lived_with_you <= 6
            for child in asserted_children
        ):
            context.add_warning(
                "CTC/ACTC omitted for one or more asserted children because the supplied "
                "age, SSN, or residency facts do not satisfy the modeled eligibility tests."
            )

        qualifying_children = [
            d
            for d in input_data.dependents
            if claimant_has_ssn
            and d.qualifies_for_ctc
            and d.age_at_year_end < 17
            and d.has_ssn
            and d.months_lived_with_you > 6
        ]
        num_children = len(qualifying_children)
        num_other = len([d for d in input_data.dependents if d.qualifies_for_odc])

        ctc_base = Decimal(str(config.amount_per_child)) * num_children
        odc_base = Decimal(str(config.other_dependent_amount)) * num_other
        base_credit = ctc_base + odc_base
        threshold = Decimal(
            str(
                config.mfj_phaseout_threshold
                if filing_status == "mfj"
                else config.phaseout_threshold
            )
        )
        phase_out = Decimal(0)
        if agi > threshold:
            increments = (
                (agi - threshold) / Decimal(str(config.phaseout_increment))
            ).to_integral_value(rounding=ROUND_CEILING)
            phase_out = increments * Decimal(str(config.reduction_per_increment))

        combined_available = max(Decimal(0), base_credit - phase_out)
        # Preserve separate display rows while following the combined worksheet.
        ctc_available = min(ctc_base, combined_available)
        odc_available = min(odc_base, combined_available - ctc_available)
        liability = context.get_decimal_result("tax_before_credits")
        nonrefundable_used = min(combined_available, liability)
        unused_combined = combined_available - nonrefundable_used
        max_refundable = Decimal(str(config.refundable_amount_per_child)) * num_children
        earned_limit = max(
            Decimal(0),
            context.get_decimal_result("earned_income")
            - Decimal(str(config.refundable_earned_income_threshold)),
        ) * Decimal(str(config.refundable_rate))
        refundable_cap = min(unused_combined, max_refundable)
        refundable = min(refundable_cap, earned_limit)

        if num_children >= 3 and refundable < refundable_cap:
            # Part II-B depends on actual Box 4/6 payroll withholding and other
            # payments the model does not collect. Returning the general formula
            # as if final can understate ACTC. Preserve the universally available
            # earned-income result and surface that the alternative was not tested.
            context.add_warning(
                "ACTC uses the general earned-income formula only: the three-or-more-child "
                "Schedule 8812 payroll-tax alternative requires actual withholding inputs "
                "not collected by this estimator and could increase the credit."
            )

        return {
            "qualifying_children": num_children,
            "base": base_credit,
            "phase_out": phase_out,
            "combined_available": combined_available,
            "ctc_available": ctc_available,
            "odc_available": odc_available,
            "refundable": refundable.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        }

    def _calculate_earned_income_credit(self, context: CalculationContext, agi: Decimal) -> Decimal:
        """Calculate a continuous-formula 2025 EITC estimate."""
        context.set_result("federal_eic_assessed", True)
        input_data = context.input
        filing_status = input_data.filing_status.value
        earned_income = context.get_decimal_result("earned_income", Decimal(0))
        investment_income = context.get_decimal_result("investment_income", Decimal(0))
        federal_rules = context.get_rules("US")
        if federal_rules is None or federal_rules.federal_credits is None:
            raise ValueError("Federal credit configuration is required")
        credit_config = federal_rules.federal_credits
        investment_limit = Decimal(str(credit_config.eitc_investment_income_limit))
        if investment_income > investment_limit:
            return Decimal(0)

        if earned_income <= 0:
            return Decimal(0)

        if filing_status == "mfs":
            context.set_result("federal_eic_assessed", False)
            context.add_warning(
                "EITC omitted for MFS: separated-spouse eligibility is not represented "
                "by the available inputs."
            )
            return Decimal(0)

        qualifying_children = [
            d
            for d in input_data.dependents
            if d.qualifies_for_eitc is True
            and d.has_ssn
            and d.months_lived_with_you > 6
            and (
                d.age_at_year_end < 19 or (d.is_student and d.age_at_year_end < 24) or d.is_disabled
            )
        ]
        num_children = min(len(qualifying_children), 3)

        params = next(
            p for p in credit_config.eitc_parameters if p.qualifying_children == num_children
        )
        income_for_eic = max(earned_income, agi)
        phase_out_end = Decimal(
            str(params.mfj_phaseout_end if filing_status == "mfj" else params.phaseout_end)
        )
        if income_for_eic >= phase_out_end:
            return Decimal(0)

        if input_data.eitc_eligibility_asserted is not True:
            context.set_result("federal_eic_assessed", False)
            context.add_warning(
                "EITC omitted: claimant SSN, residency, dependency, and filing-status "
                "eligibility was not asserted."
            )
            return Decimal(0)

        if num_children == 0:
            ages = [input_data.taxpayer.age_at_year_end]
            if filing_status == "mfj" and input_data.spouse is not None:
                ages.append(input_data.spouse.age_at_year_end)
            known_eligible_age = any(age is not None and 25 <= age < 65 for age in ages)
            if not known_eligible_age:
                context.set_result("federal_eic_assessed", False)
                context.add_warning(
                    "Childless EITC omitted: no filer has a known year-end age from 25 through 64."
                )
                return Decimal(0)

        maximum_credit = Decimal(str(params.maximum_credit))
        phase_in_credit = min(maximum_credit, earned_income * Decimal(str(params.credit_rate)))
        phase_out_start = Decimal(
            str(params.mfj_phaseout_start if filing_status == "mfj" else params.phaseout_start)
        )
        phaseout_credit = maximum_credit
        if income_for_eic > phase_out_start:
            phaseout_credit -= (income_for_eic - phase_out_start) * Decimal(
                str(params.phaseout_rate)
            )
        credit = min(phase_in_credit, phaseout_credit)
        return max(Decimal(0), credit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
