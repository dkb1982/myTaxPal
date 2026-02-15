"""
Stage 5: Deductions

Calculates standard or itemized deductions.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tax_estimator.calculation.stages.base import CalculationStage, StageResult
from tax_estimator.models.tax_result import DeductionResult

if TYPE_CHECKING:
    from tax_estimator.calculation.context import CalculationContext


class DeductionsStage(CalculationStage):
    """Calculates deductions (standard or itemized)."""

    @property
    def stage_id(self) -> str:
        return "deductions"

    @property
    def stage_name(self) -> str:
        return "Deductions"

    @property
    def stage_order(self) -> int:
        return 5

    @property
    def dependencies(self) -> list[str]:
        return ["adjustments_agi"]

    def execute(self, context: CalculationContext) -> StageResult:
        """Calculate deductions."""
        context.current_stage = self.stage_id
        input_data = context.input
        trace = context.trace

        agi = context.get_decimal_result("agi")
        filing_status = input_data.filing_status.value

        # Get federal rules
        federal_rules = context.get_rules("US")
        if not federal_rules:
            return self._error("Federal rules not loaded", "RULES_NOT_FOUND")

        # Calculate standard deduction
        standard_deduction = self._calculate_standard_deduction(
            federal_rules,
            filing_status,
            input_data.taxpayer.age_65_or_older,
            input_data.taxpayer.is_blind,
            input_data.spouse.age_65_or_older if input_data.spouse else False,
            input_data.spouse.is_blind if input_data.spouse else False,
            input_data.taxpayer.is_dependent,
        )

        trace.add_step(
            step_id="DED-STD",
            label="Standard Deduction",
            formula="Base amount + Additional (age/blind)",
            inputs={
                "filing_status": filing_status,
                "age_65_plus": input_data.taxpayer.age_65_or_older,
                "blind": input_data.taxpayer.is_blind,
            },
            result=standard_deduction,
            jurisdiction="US",
        )

        # Calculate itemized deductions if provided
        itemized_total = Decimal(0)
        itemized_breakdown: dict[str, Decimal] = {}

        if input_data.itemized_deductions:
            itemized = input_data.itemized_deductions

            # Medical: Only amount exceeding 7.5% of AGI
            medical_threshold = agi * Decimal("0.075")
            medical_deductible = max(Decimal(0), itemized.medical_expenses - medical_threshold)
            itemized_breakdown["medical"] = medical_deductible

            # SALT: Capped at $10,000 ($5,000 MFS)
            salt_limit = Decimal(5000) if filing_status == "mfs" else Decimal(10000)
            salt_total = (
                itemized.state_local_taxes_paid
                + itemized.real_estate_taxes
                + itemized.personal_property_taxes
            )
            salt_deduction = min(salt_total, salt_limit)
            itemized_breakdown["salt"] = salt_deduction

            # Mortgage interest
            mortgage_interest = itemized.mortgage_interest
            itemized_breakdown["mortgage_interest"] = mortgage_interest

            # Charitable contributions
            charitable = itemized.charitable_cash + itemized.charitable_noncash
            # TODO: Apply AGI limits (60% cash, 30% property)
            itemized_breakdown["charitable"] = charitable

            # Other
            other = (
                itemized.casualty_loss
                + itemized.other_itemized
            )
            itemized_breakdown["other"] = other

            itemized_total = (
                medical_deductible
                + salt_deduction
                + mortgage_interest
                + charitable
                + other
            )

            trace.add_step(
                step_id="DED-ITEM",
                label="Total Itemized Deductions",
                formula="Medical (over 7.5% AGI) + SALT (capped) + Mortgage + Charitable + Other",
                inputs={
                    "medical_expenses": str(itemized.medical_expenses),
                    "medical_threshold": str(medical_threshold),
                    "medical_deductible": str(medical_deductible),
                    "salt_total": str(salt_total),
                    "salt_deduction": str(salt_deduction),
                    "mortgage_interest": str(mortgage_interest),
                    "charitable": str(charitable),
                    "other": str(other),
                },
                result=itemized_total,
                jurisdiction="US",
            )

        # Determine which to use
        use_itemized = input_data.force_itemize or itemized_total > standard_deduction
        deduction_used = itemized_total if use_itemized else standard_deduction
        method = "itemized" if use_itemized else "standard"

        trace.add_step(
            step_id="DED-CHOICE",
            label="Deduction Method Selected",
            formula="MAX(Standard Deduction, Itemized Deductions)",
            inputs={
                "standard": str(standard_deduction),
                "itemized": str(itemized_total),
                "force_itemize": input_data.force_itemize,
            },
            result=deduction_used,
            jurisdiction="US",
            note=f"Using {method} deduction",
        )

        # Create result object
        additional = self._get_additional_deduction(
            federal_rules,
            filing_status,
            input_data.taxpayer.age_65_or_older,
            input_data.taxpayer.is_blind,
            input_data.spouse.age_65_or_older if input_data.spouse else False,
            input_data.spouse.is_blind if input_data.spouse else False,
        )

        deduction_result = DeductionResult(
            method=method,
            standard_deduction_available=standard_deduction,
            itemized_deduction_total=itemized_total,
            deduction_used=deduction_used,
            additional_deduction=additional,
        )

        # Store results
        context.set_result("deduction_method", method)
        context.set_result("standard_deduction", standard_deduction)
        context.set_result("itemized_deduction", itemized_total)
        context.set_result("deduction_used", deduction_used)
        context.set_result("deduction_result", deduction_result)
        context.set_result("itemized_breakdown", itemized_breakdown)

        return self._success(f"Using {method} deduction: ${deduction_used:,.2f}")

    def _calculate_standard_deduction(
        self,
        rules: "JurisdictionRules",
        filing_status: str,
        age_65_plus: bool,
        blind: bool,
        spouse_age_65_plus: bool,
        spouse_blind: bool,
        is_dependent: bool,
    ) -> Decimal:
        """Calculate standard deduction amount."""
        from tax_estimator.rules.schema import FilingStatus as FSEnum

        # Convert string to enum
        fs_enum = FSEnum(filing_status)

        # Get base amount
        base_amount = Decimal(str(rules.get_standard_deduction(fs_enum)))

        # Check if taxpayer is claimed as dependent
        if is_dependent:
            # Reduced standard deduction for dependents
            for amt in rules.deductions.standard_deduction.amounts:
                if amt.filing_status == fs_enum and amt.dependent_claimed_elsewhere:
                    base_amount = Decimal(str(amt.dependent_claimed_elsewhere))
                    break

        # Add additional amounts for age/blindness
        additional = self._get_additional_deduction(
            rules, filing_status, age_65_plus, blind, spouse_age_65_plus, spouse_blind
        )

        return base_amount + additional

    def _get_additional_deduction(
        self,
        rules: "JurisdictionRules",
        filing_status: str,
        age_65_plus: bool,
        blind: bool,
        spouse_age_65_plus: bool,
        spouse_blind: bool,
    ) -> Decimal:
        """Get additional standard deduction for age/blindness."""
        from tax_estimator.rules.schema import FilingStatus as FSEnum

        fs_enum = FSEnum(filing_status)
        additional = Decimal(0)
        additional_amounts = rules.deductions.standard_deduction.additional_amounts

        # Find age 65+ amount
        age_amount = Decimal(0)
        for amt in additional_amounts:
            if amt.category == "age_65_plus" and amt.filing_status == fs_enum:
                age_amount = Decimal(str(amt.amount))
                break

        # Find blind amount
        blind_amount = Decimal(0)
        for amt in additional_amounts:
            if amt.category == "blind" and amt.filing_status == fs_enum:
                blind_amount = Decimal(str(amt.amount))
                break

        # Apply for taxpayer
        if age_65_plus:
            additional += age_amount
        if blind:
            additional += blind_amount

        # Apply for spouse (MFJ/MFS)
        if filing_status in ("mfj", "qss"):
            if spouse_age_65_plus:
                additional += age_amount
            if spouse_blind:
                additional += blind_amount

        return additional


# Import for type hints
if TYPE_CHECKING:
    from tax_estimator.rules.schema import JurisdictionRules
